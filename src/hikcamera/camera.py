"""
High-level Hikvision industrial camera interface.
海康威视工业相机高层接口。

Typical usage (polling) / 典型用法（轮询模式）
----------------------------------------------

.. code-block:: python

    from hikcamera import AccessMode, HikCamera, OutputFormat

    cameras = HikCamera.enumerate()
    with HikCamera.from_device_info(cameras[0]) as cam:
        cam.open(AccessMode.EXCLUSIVE)
        cam.params.AcquisitionControl.ExposureTime.set(5000.0)
        cam.start_grabbing()
        frame = cam.get_frame(timeout_ms=1000, output_format=OutputFormat.BGR8)
        cam.stop_grabbing()

Typical usage (callback) / 典型用法（回调模式）
-----------------------------------------------

.. code-block:: python

    import numpy as np
    from hikcamera import HikCamera, AccessMode, OutputFormat

    def on_frame(image: np.ndarray, frame_info: dict) -> None:
        print(f"Got frame {frame_info['frame_num']}: {image.shape}")

    cameras = HikCamera.enumerate()
    with HikCamera.from_device_info(cameras[0]) as cam:
        cam.open(AccessMode.EXCLUSIVE)
        cam.start_grabbing(callback=on_frame, output_format=OutputFormat.BGR8)
        import time; time.sleep(5)
        cam.stop_grabbing()
"""

from __future__ import annotations

import ctypes
import ipaddress
import logging
import os
import socket
import struct
import threading
from collections import OrderedDict
from collections.abc import Callable
from ctypes import POINTER, c_ubyte, c_uint, c_void_p
from enum import IntEnum, StrEnum
from typing import Any

import numpy as np

from .enums import (
    AccessMode,
    MvErrorCode,
    OutputFormat,
    StreamingMode,
    TransportLayer,
    UserSetSelector,
)
from .exceptions import (
    CameraAlreadyOpenError,
    CameraConnectionError,
    CameraNotFoundError,
    CameraNotOpenError,
    DeviceDisconnectedError,
    FrameTimeoutError,
    GrabbingError,
    GrabbingNotStartedError,
    HikCameraError,
    ImageConversionError,
    ParameterError,
    ParameterNotSupportedError,
    ParameterReadOnlyError,
    ParameterValueError,
)
from .params import (
    ALL_CATEGORIES,
    AcquisitionControl,
    AnalogControl,
    DeviceControl,
    ImageFormatControl,
    ParamNode,
    TransportLayerControl,
    UserSetControl,
    _build_param_schema,
)
from .sdk_wrapper import (
    EXCEPTION_CALLBACK,
    IMAGE_CALLBACK,
    MV_CC_DEVICE_INFO,
    MV_CC_DEVICE_INFO_LIST,
    MV_CC_PIXEL_CONVERT_PARAM_EX,
    MV_FRAME_OUT_INFO_EX,
    MVCC_ENUMVALUE,
    MVCC_FLOATVALUE,
    MVCC_INTVALUE_EX,
    MVCC_STRINGVALUE,
    load_sdk,
)
from .utils import raw_to_numpy

logger = logging.getLogger(__name__)

_MAX_GIGE_PACKET_SIZE_CACHE_ENTRIES: int = 64
_GIGE_PACKET_SIZE_CACHE: OrderedDict[str, int] = OrderedDict()


class CameraInfoDict(dict[str, Any]):
    """
    Dictionary returned by :meth:`HikCamera.get_camera_info`.
    :meth:`HikCamera.get_camera_info` 返回的字典类型。

    This is a module-level compatibility helper for the public
    :meth:`HikCamera.get_camera_info` API rather than a standalone data model.
    It is not re-exported at the package level, and exists so the returned
    mapping keeps standard ``dict`` behavior while accepting both legacy string
    keys and :class:`~hikcamera.params.ParamNode` lookups during the migration
    period. If legacy string-key access is deprecated in a future release, this
    helper is expected to remain as a thin mapping wrapper around the public
    ``get_camera_info()`` result, with lookup behavior narrowed toward the
    supported access patterns of that release.
    这是公开 API :meth:`HikCamera.get_camera_info` 在模块层面的兼容辅助类型，
    而不是独立的数据模型。它不会在包级别重新导出，其作用是在迁移期间保持标准
    ``dict`` 行为的同时，兼容旧字符串 key 和
    :class:`~hikcamera.params.ParamNode` 取值方式。

    Values are stored under legacy string node names for backward
    compatibility, but lookups also accept :class:`~hikcamera.params.ParamNode`
    instances.
    值仍以旧的字符串节点名存储以保持向后兼容，但取值时也支持
    :class:`~hikcamera.params.ParamNode` 实例。
    """

    @staticmethod
    def _normalize_key(key: object) -> str | object:
        """
        Convert ParamNode keys to their GenICam string names.
        将 ParamNode key 转换为对应的 GenICam 字符串名称。

        Non-ParamNode keys are returned unchanged.
        非 ParamNode 的 key 将原样返回。
        """
        if isinstance(key, ParamNode):
            return key.name
        return key

    def __getitem__(self, key: object) -> Any:
        return super().__getitem__(self._normalize_key(key))

    def get(self, key: object, default: Any = None) -> Any:
        return super().get(self._normalize_key(key), default)

    def __contains__(self, key: object) -> bool:
        return super().__contains__(self._normalize_key(key))


def _get_category_nodes(category: type) -> tuple[tuple[str, ParamNode], ...]:
    """
    Return all ``ParamNode`` members declared on a category class.
    返回分类类上声明的全部 ``ParamNode`` 成员。
    """
    return tuple(
        (attr_name, attr)
        for attr_name, attr in vars(category).items()
        if isinstance(attr, ParamNode)
    )


class BoundParamNode:
    """
    Camera-bound view of a :class:`ParamNode`.
    绑定到相机实例的 :class:`ParamNode` 视图。
    """

    __slots__ = ("_camera", "_node")

    def __init__(self, camera: HikCamera, node: ParamNode) -> None:
        self._camera = camera
        self._node = node

    @property
    def node(self) -> ParamNode:
        return self._node

    def get(self, default: Any = None) -> Any:
        return self._camera._get_param_node_value(self._node, default)

    def set(self, value: Any) -> None:
        self._camera._set_param_node_value(self._node, value)

    def execute(self) -> None:
        self._camera._execute_param_node(self._node)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._node.name!r})"


class BoundCategoryProxy:
    """
    Camera-bound proxy for one parameter category.
    单个参数分类的相机绑定代理。
    """

    def __init__(self, camera: HikCamera, category: type) -> None:
        self._camera = camera
        self._category = category
        for attr_name, node in _get_category_nodes(category):
            object.__setattr__(self, attr_name, BoundParamNode(camera, node))

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_camera", "_category"}:
            object.__setattr__(self, name, value)
            return
        raise AttributeError(f"{type(self).__name__!s} is read-only")


class CameraParamsProxy:
    """
    Root proxy exposed as ``cam.params``.
    通过 ``cam.params`` 暴露的根代理对象。
    """

    def __init__(self, camera: HikCamera) -> None:
        self._camera = camera
        for category in ALL_CATEGORIES:
            object.__setattr__(self, category.__name__, BoundCategoryProxy(camera, category))

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_camera":
            object.__setattr__(self, name, value)
            return
        raise AttributeError(f"{type(self).__name__!s} is read-only")


def _cache_gige_packet_size(cache_key: str, packet_size: int) -> None:
    """
    Store a GigE packet-size hint in a bounded LRU cache.
    在有界 LRU 缓存中保存 GigE 包大小提示。
    """
    _GIGE_PACKET_SIZE_CACHE[cache_key] = packet_size
    _GIGE_PACKET_SIZE_CACHE.move_to_end(cache_key)
    while len(_GIGE_PACKET_SIZE_CACHE) > _MAX_GIGE_PACKET_SIZE_CACHE_ENTRIES:
        _GIGE_PACKET_SIZE_CACHE.popitem(last=False)


def _get_cached_gige_packet_size(cache_key: str) -> int | None:
    """
    Read a cached GigE packet-size hint and refresh its LRU position.
    读取缓存的 GigE 包大小提示并刷新其 LRU 位置。
    """
    packet_size = _GIGE_PACKET_SIZE_CACHE.get(cache_key)
    if packet_size is not None:
        _GIGE_PACKET_SIZE_CACHE.move_to_end(cache_key)
    return packet_size

# ---------------------------------------------------------------------------
# Constants / 常量
# ---------------------------------------------------------------------------

#: Standard Ethernet MTU packet size (bytes).  Works on any network without
#: jumbo-frame support.
#: 标准以太网 MTU 包大小（字节），适用于任何不支持巨帧的网络。
GIGE_PACKET_SIZE_DEFAULT: int = 1500

#: Jumbo-frame packet size (bytes) commonly used for high-throughput GigE
#: Vision cameras.  Requires all switches/NICs on the path to support ≥ 9 KB
#: MTU.
#: 巨帧包大小（字节），常用于高吞吐量 GigE Vision 相机。
#: 要求路径上所有交换机/网卡支持 ≥ 9 KB MTU。
GIGE_PACKET_SIZE_JUMBO: int = 8164

# Fallback frame-buffer size when PayloadSize is unavailable (10 MiB).
# 当 PayloadSize 不可用时的帧缓冲区回退大小（10 MiB）。
_DEFAULT_FRAME_BUFFER_SIZE: int = 10 * 1024 * 1024

# SDK exception message type for device disconnection.
# SDK 设备断开连接异常消息类型。
_MV_EXCEPTION_DEV_DISCONNECT: int = 0x00008001

# GenICam parameter schema auto-built from :mod:`hikcamera.params` definitions.
# This replaces the old hard-coded dict with a single source of truth derived
# from :class:`ParamNode` metadata across all category namespace classes.
# GenICam 参数模式，从 :mod:`hikcamera.params` 定义自动构建。
# 此映射取代旧的硬编码字典，作为由所有分类命名空间类中
# :class:`ParamNode` 元数据派生的唯一真实来源。
_PARAMETER_SCHEMA: dict[str, type] = _build_param_schema()
# ---------------------------------------------------------------------------
# Helpers / 辅助函数
# ---------------------------------------------------------------------------

# Error codes that mean "this parameter does not exist on this device"
# 表示"该参数在此设备上不存在"的错误码
_NOT_SUPPORTED_CODES: frozenset[int] = frozenset(
    {
        MvErrorCode.MV_E_SUPPORT,
        MvErrorCode.MV_E_NOTIMP,
        MvErrorCode.MV_E_GC_PROPERTY,
        MvErrorCode.MV_E_GC_ACCESS,
    }
)

_READ_ONLY_CODES: frozenset[int] = frozenset(
    {
        MvErrorCode.MV_E_GC_ACCESS,
    }
)


def _check(ret: int, operation: str = "") -> None:
    """
    Check an SDK return code; raise the appropriate exception on failure.
    检查 SDK 返回码；失败时抛出对应的异常。

    Parameters / 参数
    -----------------
    ret:
        SDK return code (0 = success).
        SDK 返回码（0 = 成功）。
    operation:
        Human-readable description used in the error message.
        用于错误消息的可读描述。
    """
    if ret == MvErrorCode.MV_OK:
        return
    code = ret & 0xFFFFFFFF
    msg = f"SDK error 0x{code:08X}" + (f" during {operation}" if operation else "")
    if code in _NOT_SUPPORTED_CODES:
        raise ParameterNotSupportedError(msg, code)
    if code == MvErrorCode.MV_E_GC_TIMEOUT:
        raise FrameTimeoutError(msg, code)
    if code == MvErrorCode.MV_E_PARAMETER:
        raise ParameterError(msg, code)
    raise HikCameraError(msg, code)


def _ip_to_int(ip: str) -> int:
    """
    Convert dotted-decimal IP string to big-endian integer.
    将点分十进制 IP 字符串转换为大端序整数。
    """
    return struct.unpack("!I", socket.inet_aton(ip))[0]


def _int_to_ip(n: int) -> str:
    """
    Convert big-endian integer to dotted-decimal IP string.
    将大端序整数转换为点分十进制 IP 字符串。
    """
    return socket.inet_ntoa(struct.pack("!I", n))


def _transport_layer_search_order(transport_layers: TransportLayer) -> tuple[TransportLayer, ...]:
    """
    Expand a transport-layer bitmask into an ordered scan sequence.
    将传输层位掩码展开为有序扫描序列。
    """
    ordered_layers: list[TransportLayer] = []
    for layer in (
        TransportLayer.GIGE,
        TransportLayer.USB,
        TransportLayer.CAMERALINK,
    ):
        if transport_layers & layer:
            ordered_layers.append(layer)
    return tuple(ordered_layers)


# ---------------------------------------------------------------------------
# DeviceInfo – a Python-friendly wrapper around MV_CC_DEVICE_INFO
# DeviceInfo ── 对 MV_CC_DEVICE_INFO 的 Python 友好封装
# ---------------------------------------------------------------------------

class DeviceInfo:
    """
    Python-friendly wrapper around the SDK's ``MV_CC_DEVICE_INFO`` struct.
    对 SDK ``MV_CC_DEVICE_INFO`` 结构体的 Python 友好封装。

    Attributes / 属性
    -----------------
    transport_layer : int
        The transport layer type (``MV_CC_DEVICE_INFO.nTLayerType``).
        传输层类型。
    ip : str | None
        IP address (GigE cameras only).
        IP 地址（仅 GigE 相机）。
    serial_number : str
        Camera serial number. / 相机序列号。
    model_name : str
        Camera model name. / 相机型号名称。
    user_defined_name : str
        User-defined name (may be empty).
        用户自定义名称（可能为空）。
    mac_address : str
        MAC address in ``XX:XX:XX:XX:XX:XX`` format.
        ``XX:XX:XX:XX:XX:XX`` 格式的 MAC 地址。
    """

    def __init__(self, raw: MV_CC_DEVICE_INFO) -> None:
        self._raw = raw
        self.transport_layer: int = raw.nTLayerType

        mac_high = raw.nMacAddrHigh
        mac_low = raw.nMacAddrLow
        self.mac_address: str = (
            f"{(mac_high >> 8) & 0xFF:02X}:{mac_high & 0xFF:02X}:"
            f"{(mac_low >> 24) & 0xFF:02X}:{(mac_low >> 16) & 0xFF:02X}:"
            f"{(mac_low >> 8) & 0xFF:02X}:{mac_low & 0xFF:02X}"
        )

        if raw.nTLayerType == MV_CC_DEVICE_INFO.MV_GIGE_DEVICE:
            gi = raw.SpecialInfo.stGigEInfo
            self.ip: str | None = _int_to_ip(gi.nCurrentIp)
            self.serial_number: str = gi.chSerialNumber.decode("utf-8", errors="replace").strip("\x00")
            self.model_name: str = gi.chModelName.decode("utf-8", errors="replace").strip("\x00")
            self.user_defined_name: str = gi.chUserDefinedName.decode("utf-8", errors="replace").strip("\x00")
        elif raw.nTLayerType == MV_CC_DEVICE_INFO.MV_USB_DEVICE:
            ui = raw.SpecialInfo.stUsb3VInfo
            self.ip = None
            self.serial_number = ui.chSerialNumber.decode("utf-8", errors="replace").strip("\x00")
            self.model_name = ui.chModelName.decode("utf-8", errors="replace").strip("\x00")
            self.user_defined_name = ui.chUserDefinedName.decode("utf-8", errors="replace").strip("\x00")
        else:
            self.ip = None
            self.serial_number = ""
            self.model_name = "Unknown"
            self.user_defined_name = ""

    def __repr__(self) -> str:
        parts = [f"model={self.model_name!r}", f"sn={self.serial_number!r}"]
        if self.ip:
            parts.append(f"ip={self.ip!r}")
        return f"DeviceInfo({', '.join(parts)})"


# ---------------------------------------------------------------------------
# HikCamera
# ---------------------------------------------------------------------------

class HikCamera:
    """
    High-level interface to a single Hikvision industrial camera.
    单台海康威视工业相机的高层接口。

    The class manages the full lifecycle (create handle → open → grabbing →
    close → destroy handle) and exposes convenience methods for parameter
    access and frame capture.
    此类管理完整生命周期（创建句柄 → 打开 → 取帧 → 关闭 → 销毁句柄），
    并提供参数访问和帧捕获的便捷方法。

    Construction / 构造
    -------------------
    Use the class-methods :py:meth:`from_device_info`, :py:meth:`from_ip`,
    or :py:meth:`from_serial_number` rather than calling ``__init__``
    directly.
    建议使用类方法 :py:meth:`from_device_info`、:py:meth:`from_ip` 或
    :py:meth:`from_serial_number`，而非直接调用 ``__init__``。

    Context manager support / 上下文管理器支持
    ------------------------------------------
    ``HikCamera`` supports the ``with`` statement.  The device handle is
    destroyed automatically on exit (but :py:meth:`stop_grabbing` and
    :py:meth:`close` must be called before ``__exit__`` if grabbing is
    still active, or use ``HikCamera`` methods directly).
    ``HikCamera`` 支持 ``with`` 语句。退出时自动销毁设备句柄（但如果仍在
    取帧，需在 ``__exit__`` 前调用 :py:meth:`stop_grabbing` 和
    :py:meth:`close`，或直接使用 ``HikCamera`` 方法）。

    Thread safety / 线程安全
    ------------------------
    Each camera instance is not thread-safe by itself.  Use external locking
    when sharing an instance across threads.
    单个相机实例本身不是线程安全的。跨线程共享实例时请使用外部锁。
    """

    # ------------------------------------------------------------------
    # Construction helpers / 构造辅助方法
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._sdk = load_sdk()
        self._handle: c_void_p = c_void_p(None)
        self._device_info: MV_CC_DEVICE_INFO | None = None
        self._is_open: bool = False
        self._is_grabbing: bool = False
        self._frame_buffer: ctypes.Array[c_ubyte] | None = None
        self._frame_buffer_size: int = 0
        self._callback_ref: IMAGE_CALLBACK | None = None  # keep reference alive
        self._user_callback: Callable[[np.ndarray, dict[str, Any]], None] | None = None
        self._output_format_for_callback: OutputFormat = OutputFormat.BGR8
        self._exception_callback_ref: EXCEPTION_CALLBACK | None = None
        self._device_exception: DeviceDisconnectedError | None = None
        self._on_device_exception: Callable[[DeviceDisconnectedError], None] | None = None
        self._lock: threading.Lock = threading.Lock()
        self._params_proxy: CameraParamsProxy | None = None

    @property
    def params(self) -> CameraParamsProxy:
        """
        Structured parameter access root.
        结构化参数访问入口。
        """
        params_proxy = getattr(self, "_params_proxy", None)
        if params_proxy is None:
            params_proxy = CameraParamsProxy(self)
            self._params_proxy = params_proxy
        return params_proxy

    @classmethod
    def enumerate(
        cls,
        transport_layers: TransportLayer = TransportLayer.ALL,
    ) -> list[DeviceInfo]:
        """
        Enumerate all accessible cameras on the host.
        枚举主机上所有可访问的相机。

        Parameters / 参数
        -----------------
        transport_layers:
            Bitmask of transport layers to scan.  Default is all layers.
            要扫描的传输层位掩码，默认为所有层。

        Returns / 返回
        --------------
        list[DeviceInfo]
            One :py:class:`DeviceInfo` per discovered camera (may be empty).
            每个发现的相机对应一个 :py:class:`DeviceInfo`（可能为空列表）。

        Raises / 异常
        -------------
        SDKNotFoundError
            When the MVS SDK library cannot be loaded.
            当无法加载 MVS SDK 库时抛出。
        HikCameraError
            When the SDK enumeration call fails.
            当 SDK 枚举调用失败时抛出。
        """
        sdk = load_sdk()
        dev_list = MV_CC_DEVICE_INFO_LIST()
        ret = sdk.MV_CC_EnumDevices(int(transport_layers), ctypes.byref(dev_list))
        _check(ret, "MV_CC_EnumDevices")
        result: list[DeviceInfo] = []
        for i in range(dev_list.nDeviceNum):
            ptr = dev_list.pDeviceInfo[i]
            if ptr:
                result.append(DeviceInfo(ptr.contents))
        logger.debug("Enumerated %d camera(s)", len(result))
        return result

    @classmethod
    def _enumerate_raw(
        cls,
        transport_layer: TransportLayer,
    ) -> list[MV_CC_DEVICE_INFO]:
        """
        Enumerate devices for a single transport layer and return raw structs.
        枚举单个传输层的设备并返回原始结构体。
        """
        sdk = load_sdk()
        dev_list = MV_CC_DEVICE_INFO_LIST()
        ret = sdk.MV_CC_EnumDevices(int(transport_layer), ctypes.byref(dev_list))
        _check(ret, "MV_CC_EnumDevices")
        result: list[MV_CC_DEVICE_INFO] = []
        for i in range(dev_list.nDeviceNum):
            ptr = dev_list.pDeviceInfo[i]
            if ptr:
                result.append(ptr.contents)
        return result

    @classmethod
    def from_device_info(cls, device_info: DeviceInfo) -> HikCamera:
        """
        Create a :py:class:`HikCamera` from a :py:class:`DeviceInfo` object.
        从 :py:class:`DeviceInfo` 对象创建 :py:class:`HikCamera`。

        Parameters / 参数
        -----------------
        device_info:
            A :py:class:`DeviceInfo` obtained from :py:meth:`enumerate`.
            从 :py:meth:`enumerate` 获取的 :py:class:`DeviceInfo`。

        Returns / 返回
        --------------
        HikCamera
            A camera instance with an SDK handle created.  Call
            :py:meth:`open` before grabbing frames.
            已创建 SDK 句柄的相机实例。取帧前需调用 :py:meth:`open`。
        """
        cam = cls()
        cam._device_info = device_info._raw
        create_handle = getattr(cam._sdk, "MV_CC_CreateHandleWithoutLog", None)
        api_name = "MV_CC_CreateHandleWithoutLog"
        if create_handle is None:
            create_handle = cam._sdk.MV_CC_CreateHandle
            api_name = "MV_CC_CreateHandle"
        ret = create_handle(ctypes.byref(cam._handle), ctypes.byref(device_info._raw))
        _check(ret, api_name)
        logger.debug("Created handle for %s", device_info)
        return cam

    @classmethod
    def from_ip(
        cls,
        ip: str,
        transport_layers: TransportLayer = TransportLayer.GIGE,
    ) -> HikCamera:
        """
        Find and create a handle for the camera at the given IP address.
        查找并为指定 IP 地址的相机创建句柄。

        Parameters / 参数
        -----------------
        ip:
            Dotted-decimal IP address (e.g. ``"192.168.1.100"``).
            点分十进制 IP 地址（如 ``"192.168.1.100"``）。
        transport_layers:
            Transport layers to search (default: GigE only).
            要搜索的传输层（默认仅 GigE）。

        Returns / 返回
        --------------
        HikCamera

        Raises / 异常
        -------------
        CameraNotFoundError
            When no camera with that IP is found during enumeration.
            枚举时未找到该 IP 的相机时抛出。
        """
        # Validate the IP string first
        try:
            ipaddress.ip_address(ip)
        except ValueError as exc:
            raise ValueError(f"Invalid IP address: {ip!r}") from exc

        devices = cls.enumerate(transport_layers)
        for dev in devices:
            if dev.ip == ip:
                return cls.from_device_info(dev)
        raise CameraNotFoundError(f"No camera found with IP {ip!r}")

    @classmethod
    def from_serial_number(
        cls,
        serial_number: str,
        transport_layers: TransportLayer = TransportLayer.ALL,
    ) -> HikCamera:
        """
        Find and create a handle for the camera with the given serial number.
        查找并为指定序列号的相机创建句柄。

        Parameters / 参数
        -----------------
        serial_number:
            Camera serial number string.
            相机序列号字符串。
        transport_layers:
            Transport layers to search.
            要搜索的传输层。

        Returns / 返回
        --------------
        HikCamera

        Raises / 异常
        -------------
        CameraNotFoundError
            When no camera with that serial number is found.
            未找到该序列号的相机时抛出。
        """
        for layer in _transport_layer_search_order(transport_layers):
            devices = cls._enumerate_raw(layer)
            for raw_device in devices:
                device_info = DeviceInfo(raw_device)
                if device_info.serial_number == serial_number:
                    return cls.from_device_info(device_info)
        raise CameraNotFoundError(f"No camera found with serial number {serial_number!r}")

    # ------------------------------------------------------------------
    # Context manager / 上下文管理器
    # ------------------------------------------------------------------

    def __enter__(self) -> HikCamera:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        """
        Stop grabbing, close the device, and destroy the SDK handle.
        停止取帧、关闭设备并销毁 SDK 句柄。
        """
        try:
            if self._is_grabbing:
                self.stop_grabbing()
        except HikCameraError:
            pass
        try:
            if self._is_open:
                self.close()
        except HikCameraError:
            pass
        if self._handle:
            try:
                self._sdk.MV_CC_DestroyHandle(self._handle)
            except Exception:  # noqa: BLE001
                pass
            self._handle = c_void_p(None)

    # ------------------------------------------------------------------
    # Open / close / 打开 / 关闭
    # ------------------------------------------------------------------

    def open(
        self,
        access_mode: AccessMode = AccessMode.EXCLUSIVE,
        streaming_mode: StreamingMode = StreamingMode.UNICAST,
        multicast_ip: str | None = None,
        packet_size: int | None = None,
    ) -> None:
        """
        Open the camera with the specified access mode.
        以指定的访问模式打开相机。

        Parameters / 参数
        -----------------
        access_mode:
            How to connect to the camera.  See :py:class:`~hikcamera.enums.AccessMode`.
            连接相机的方式。参见 :py:class:`~hikcamera.enums.AccessMode`。
        streaming_mode:
            Unicast (default) or multicast.  GigE cameras only.
            单播（默认）或组播，仅限 GigE 相机。
        multicast_ip:
            Multicast group IP (required when ``streaming_mode`` is
            :py:attr:`~hikcamera.enums.StreamingMode.MULTICAST`).
            组播组 IP（当 ``streaming_mode`` 为
            :py:attr:`~hikcamera.enums.StreamingMode.MULTICAST` 时必填）。
        packet_size:
            GigE network packet size (``GevSCPSPacketSize``) in bytes.
            GigE 网络包大小（``GevSCPSPacketSize``），单位为字节。

            * ``None`` (default) – auto-detect optimal packet size via
              ``MV_CC_GetOptimalPacketSize`` and apply it.
              ``None``（默认）── 通过 ``MV_CC_GetOptimalPacketSize`` 自动检测
              最优包大小并应用。
            * Positive ``int`` – use the given value directly (e.g.
              :py:data:`GIGE_PACKET_SIZE_DEFAULT`,
              :py:data:`GIGE_PACKET_SIZE_JUMBO`).  Only effective for GigE
              cameras.
              正整数 ── 直接使用指定值（如
              :py:data:`GIGE_PACKET_SIZE_DEFAULT`、
              :py:data:`GIGE_PACKET_SIZE_JUMBO`）。仅对 GigE 相机有效。

        Raises / 异常
        -------------
        CameraAlreadyOpenError
            When the camera is already open.
            当相机已处于打开状态时抛出。
        CameraConnectionError
            When the SDK open call fails.
            当 SDK 打开调用失败时抛出。
        """
        if self._is_open:
            raise CameraAlreadyOpenError("Camera is already open")

        # For multicast, configure the group IP before opening
        # 组播模式下，在打开前配置组播 IP
        if streaming_mode == StreamingMode.MULTICAST:
            if multicast_ip is None:
                raise ValueError("multicast_ip must be provided for multicast streaming")
            mc_int = _ip_to_int(multicast_ip)
            ret = self._sdk.MV_GIGE_SetMulticastIP(self._handle, mc_int)
            if ret != MvErrorCode.MV_OK:
                logger.warning("MV_GIGE_SetMulticastIP returned 0x%08X (may not be GigE camera)", ret & 0xFFFFFFFF)

        ret = self._sdk.MV_CC_OpenDevice(self._handle, int(access_mode), 0)
        if ret != MvErrorCode.MV_OK:
            code = ret & 0xFFFFFFFF
            raise CameraConnectionError(
                f"Failed to open camera (access_mode={access_mode.name}): "
                f"SDK error 0x{code:08X}",
                code,
            )
        self._is_open = True
        logger.info("Camera opened in %s mode", access_mode.name)

        # Configure GigE packet size after opening
        # 打开后配置 GigE 包大小
        self._configure_packet_size(packet_size)

    def close(self) -> None:
        """
        Close the camera connection.
        关闭相机连接。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open.
            当相机未打开时抛出。
        """
        if not self._is_open:
            raise CameraNotOpenError("Camera is not open")
        ret = self._sdk.MV_CC_CloseDevice(self._handle)
        _check(ret, "MV_CC_CloseDevice")
        self._is_open = False
        # Safe to release the exception callback reference now that the
        # device is closed – the SDK will no longer invoke it.
        # 设备关闭后可以安全释放异常回调引用——SDK 不会再调用它。
        self._exception_callback_ref = None
        logger.info("Camera closed")

    @property
    def is_open(self) -> bool:
        """
        Whether the camera device is currently open.
        相机设备当前是否已打开。
        """
        return self._is_open

    @property
    def is_connected(self) -> bool:
        """
        Whether the camera is physically connected (checks the SDK).
        相机是否物理连接（通过 SDK 检查）。

        Note: This may return ``False`` immediately after opening if the
        SDK has not yet completed initialisation.
        注意：如果 SDK 尚未完成初始化，在刚打开后可能返回 ``False``。
        """
        if not self._is_open:
            return False
        return bool(self._sdk.MV_CC_IsDeviceConnected(self._handle))

    # ------------------------------------------------------------------
    # GigE packet size / GigE 包大小
    # ------------------------------------------------------------------

    def _configure_packet_size(self, packet_size: int | None) -> None:
        """
        Apply GigE packet size configuration after opening.
        打开后应用 GigE 包大小配置。

        Called automatically by :py:meth:`open`.  When *packet_size* is
        ``None``, the SDK is asked for the optimal value.  A positive
        integer is used as-is.  Errors are logged but never raised – this
        keeps the method safe for non-GigE cameras.
        由 :py:meth:`open` 自动调用。当 *packet_size* 为 ``None`` 时，
        通过 SDK 查询最优值。正整数直接使用。错误仅记录日志不抛异常，
        以确保对非 GigE 相机安全。
        """
        if packet_size is not None:
            # Validate caller-supplied value / 校验调用方提供的值
            if not isinstance(packet_size, int) or packet_size <= 0:
                raise ValueError(
                    f"packet_size must be a positive integer, got {packet_size!r}"
                )
            # Manual override / 手动指定
            try:
                self.set_packet_size(packet_size)
                cache_key = self._packet_size_cache_key()
                if cache_key is not None:
                    _cache_gige_packet_size(cache_key, packet_size)
            except ParameterError:
                logger.debug(
                    "Could not set GevSCPSPacketSize=%d (may not be a GigE camera)",
                    packet_size,
                )
        else:
            cache_key = self._packet_size_cache_key()
            cached_packet_size = None if cache_key is None else _get_cached_gige_packet_size(cache_key)
            # Auto-detect optimal / 自动检测最优值
            try:
                if cached_packet_size is not None:
                    try:
                        self.set_packet_size(cached_packet_size)
                    except ParameterError:
                        if cache_key is not None:
                            _GIGE_PACKET_SIZE_CACHE.pop(cache_key, None)
                        logger.debug(
                            "Cached GigE packet size %d is no longer valid; re-probing",
                            cached_packet_size,
                        )
                    else:
                        logger.debug("GigE packet size restored from cache: %d", cached_packet_size)
                        return
                optimal = self.get_optimal_packet_size()
                if optimal > 0:
                    self.set_packet_size(optimal)
                    if cache_key is not None:
                        _cache_gige_packet_size(cache_key, optimal)
                    logger.debug("GigE packet size set to optimal value %d", optimal)
            except (ParameterError, HikCameraError):
                logger.debug("Could not auto-configure GigE packet size (may not be a GigE camera)")

    def _packet_size_cache_key(self) -> str | None:
        """
        Return a stable cache key for GigE packet-size reuse.
        返回用于复用 GigE 包大小的稳定缓存键。
        """
        if self._device_info is None:
            return None
        if self._device_info.nTLayerType != int(TransportLayer.GIGE):
            return None
        device_info = DeviceInfo(self._device_info)
        if device_info.serial_number:
            return f"sn:{device_info.serial_number}"
        if device_info.ip:
            return f"ip:{device_info.ip}"
        return f"mac:{device_info.mac_address}"

    def get_optimal_packet_size(self) -> int:
        """
        Query the SDK for the optimal GigE packet size for this camera.
        查询 SDK 以获取此相机的最优 GigE 包大小。

        This calls ``MV_CC_GetOptimalPacketSize`` which probes the
        network path and returns the largest packet size that can be
        transmitted without fragmentation.
        此方法调用 ``MV_CC_GetOptimalPacketSize``，它会探测网络路径并
        返回不会导致分片的最大包大小。

        Returns / 返回
        --------------
        int
            Optimal packet size in bytes (typically
            :py:data:`GIGE_PACKET_SIZE_DEFAULT` or
            :py:data:`GIGE_PACKET_SIZE_JUMBO`).
            最优包大小（字节），通常为
            :py:data:`GIGE_PACKET_SIZE_DEFAULT` 或
            :py:data:`GIGE_PACKET_SIZE_JUMBO`。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        HikCameraError
            When the SDK call fails (e.g. non-GigE camera).
            当 SDK 调用失败时（如非 GigE 相机）抛出。
        """
        self._assert_open()
        func = getattr(self._sdk, "MV_CC_GetOptimalPacketSize", None)
        if func is None:
            raise HikCameraError(
                "MV_CC_GetOptimalPacketSize is not available in this SDK version"
            )
        ret = func(self._handle)
        if ret <= 0:
            raise HikCameraError(
                f"MV_CC_GetOptimalPacketSize failed (returned {ret}); "
                "camera may not be GigE",
            )
        return int(ret)

    def set_packet_size(self, size: int) -> None:
        """
        Set the GigE streaming packet size (``GevSCPSPacketSize``).
        设置 GigE 流传输包大小（``GevSCPSPacketSize``）。

        A larger packet size (e.g. :py:data:`GIGE_PACKET_SIZE_JUMBO` for
        jumbo frames) improves throughput but requires that every network
        device on the path supports the MTU.  A safe default is
        :py:data:`GIGE_PACKET_SIZE_DEFAULT`.
        较大的包大小（如 :py:data:`GIGE_PACKET_SIZE_JUMBO` 用于巨帧）可提高
        吞吐量，但要求路径上的所有网络设备都支持该 MTU。安全默认值为
        :py:data:`GIGE_PACKET_SIZE_DEFAULT`。

        Parameters / 参数
        -----------------
        size:
            Packet size in bytes. / 包大小（字节）。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        ParameterNotSupportedError
            When the camera does not support this parameter (non-GigE).
            当相机不支持此参数时（非 GigE 相机）抛出。
        ParameterError
            When the SDK call fails. / 当 SDK 调用失败时抛出。
        """
        self.params.TransportLayerControl.GevSCPSPacketSize.set(size)
        logger.debug("GevSCPSPacketSize set to %d", size)

    def get_packet_size(self) -> int:
        """
        Get the current GigE streaming packet size (``GevSCPSPacketSize``).
        获取当前 GigE 流传输包大小（``GevSCPSPacketSize``）。

        Returns / 返回
        --------------
        int
            Current packet size in bytes. / 当前包大小（字节）。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        ParameterNotSupportedError
            When the camera does not support this parameter (non-GigE).
            当相机不支持此参数时（非 GigE 相机）抛出。
        """
        return self.params.TransportLayerControl.GevSCPSPacketSize.get()

    # ------------------------------------------------------------------
    # Grabbing / 取帧
    # ------------------------------------------------------------------

    def start_grabbing(
        self,
        callback: Callable[[np.ndarray, dict[str, Any]], None] | None = None,
        output_format: OutputFormat = OutputFormat.BGR8,
        on_exception: Callable[[DeviceDisconnectedError], None] | None = None,
    ) -> None:
        """
        Start image acquisition.
        开始图像采集。

        Parameters / 参数
        -----------------
        callback:
            Optional user-provided callback.  When supplied, frame data is
            decoded and passed to *callback* from an SDK-managed thread as::
            可选的用户回调。当提供时，帧数据会被解码并从 SDK 管理的线程
            传递给 *callback*，格式为::

                callback(image: np.ndarray, frame_info: dict)

            where *frame_info* contains ``frame_num``, ``width``, ``height``,
            ``pixel_format``, ``timestamp``, and ``frame_length`` keys.
            其中 *frame_info* 包含 ``frame_num``、``width``、``height``、
            ``pixel_format``、``timestamp`` 和 ``frame_length`` 等键。

            When *callback* is ``None``, use :py:meth:`get_frame` to pull
            frames manually.
            当 *callback* 为 ``None`` 时，使用 :py:meth:`get_frame` 手动拉取帧。
        output_format:
            Pixel format of the numpy array delivered to *callback* or
            returned by :py:meth:`get_frame`.
            传递给 *callback* 或由 :py:meth:`get_frame` 返回的 numpy 数组的像素格式。
        on_exception:
            Optional callback invoked from the SDK thread when the camera
            reports a device exception (e.g. disconnection).  Receives a
            :py:class:`~hikcamera.exceptions.DeviceDisconnectedError` instance.
            可选的回调，当相机报告设备异常（如断开连接）时从 SDK 线程调用。
            接收一个 :py:class:`~hikcamera.exceptions.DeviceDisconnectedError` 实例。

            Even without this callback the exception is stored internally and
            re-raised by :py:meth:`stop_grabbing`, :py:meth:`get_frame`, and
            :py:meth:`get_frame_ex`.
            即使未提供此回调，异常也会在内部存储，并在
            :py:meth:`stop_grabbing`、:py:meth:`get_frame` 和 :py:meth:`get_frame_ex` 中重新抛出。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open.
            当相机未打开时抛出。
        GrabbingError
            When the SDK start-grabbing call fails.
            当 SDK 开始取帧调用失败时抛出。
        """
        if not self._is_open:
            raise CameraNotOpenError("Cannot start grabbing: camera is not open")
        if self._is_grabbing:
            logger.warning("start_grabbing called while already grabbing; ignoring")
            return

        self._output_format_for_callback = output_format
        self._device_exception = None
        self._on_device_exception = on_exception

        # Register the device-exception callback so disconnections are detected
        # 注册设备异常回调以检测断开连接
        self._register_exception_callback()

        if callback is not None:
            self._user_callback = callback
            sdk_cb = IMAGE_CALLBACK(self._internal_callback)
            self._callback_ref = sdk_cb  # prevent garbage collection
            ret = self._sdk.MV_CC_RegisterImageCallBackEx(self._handle, sdk_cb, None)
            _check(ret, "MV_CC_RegisterImageCallBackEx")

        ret = self._sdk.MV_CC_StartGrabbing(self._handle)
        if ret != MvErrorCode.MV_OK:
            self._callback_ref = None
            self._user_callback = None
            self._on_device_exception = None
            # Note: _exception_callback_ref is intentionally kept alive here.
            # The SDK may still invoke the registered callback after
            # StartGrabbing fails; dropping the reference could cause a
            # use-after-free crash.  It will be cleared when the handle is
            # closed/destroyed.
            # 注意：此处故意保留 _exception_callback_ref。StartGrabbing 失败后
            # SDK 仍可能调用已注册的回调；释放引用可能导致野指针崩溃。
            # 该引用将在句柄关闭/销毁时清理。
            code = ret & 0xFFFFFFFF
            raise GrabbingError(f"MV_CC_StartGrabbing failed: 0x{code:08X}", code)

        self._is_grabbing = True
        logger.info("Grabbing started (callback=%s, output_format=%s)", callback is not None, output_format.name)

    def stop_grabbing(self) -> None:
        """
        Stop image acquisition.
        停止图像采集。

        Raises / 异常
        -------------
        GrabbingNotStartedError
            When grabbing has not been started.
            当未开始取帧时抛出。
        DeviceDisconnectedError
            When a device disconnection was detected during grabbing.
            当取帧期间检测到设备断开连接时抛出。
        """
        if not self._is_grabbing:
            raise GrabbingNotStartedError("Grabbing has not been started")
        ret = self._sdk.MV_CC_StopGrabbing(self._handle)
        self._is_grabbing = False
        # Clear frame grabbing callbacks; keep exception callback alive
        # until the handle is closed to avoid native calls into GC'ed Python
        # 清除帧采集回调；保留异常回调直到句柄关闭，以避免原生代码调用被 GC 的 Python 对象
        self._callback_ref = None
        self._user_callback = None
        self._on_device_exception = None
        pending = self._device_exception
        self._device_exception = None
        # Re-raise a stored device exception instead of the stop-grabbing error
        # 优先重新抛出存储的设备异常，而非停止取帧错误
        if pending is not None:
            raise pending
        _check(ret, "MV_CC_StopGrabbing")
        logger.info("Grabbing stopped")

    @property
    def is_grabbing(self) -> bool:
        """
        Whether image acquisition is currently active.
        当前是否正在进行图像采集。
        """
        return self._is_grabbing

    @property
    def device_exception(self) -> DeviceDisconnectedError | None:
        """
        Pending device exception detected during grabbing, or ``None``.
        取帧期间检测到的待处理设备异常，或 ``None``。

        This is set asynchronously by the SDK exception callback thread
        when the camera reports a device-level error (e.g. disconnection).
        当相机报告设备级错误（如断开连接）时，由 SDK 异常回调线程异步设置。
        """
        return self._device_exception

    # ------------------------------------------------------------------
    # Frame retrieval (polling mode) / 帧获取（轮询模式）
    # ------------------------------------------------------------------

    def get_frame(
        self,
        timeout_ms: int = 1000,
        output_format: OutputFormat = OutputFormat.BGR8,
    ) -> np.ndarray:
        """
        Retrieve one frame (polling mode).
        获取一帧（轮询模式）。

        Allocates / reuses an internal buffer sized to the current
        ``PayloadSize`` camera parameter.
        根据当前 ``PayloadSize`` 相机参数分配/复用内部缓冲区。

        Parameters / 参数
        -----------------
        timeout_ms:
            Maximum time to wait for a frame in milliseconds.
            等待帧的最长时间（毫秒）。
        output_format:
            Desired numpy array format.
            期望的 numpy 数组格式。

        Returns / 返回
        --------------
        numpy.ndarray
            Decoded image. / 解码后的图像。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        GrabbingNotStartedError
            When :py:meth:`start_grabbing` has not been called.
            当未调用 :py:meth:`start_grabbing` 时抛出。
        FrameTimeoutError
            When no frame arrives within *timeout_ms*.
            当在 *timeout_ms* 内未收到帧时抛出。
        ImageConversionError
            When the frame buffer cannot be converted.
            当帧缓冲区无法转换时抛出。
        """
        if not self._is_open:
            raise CameraNotOpenError("Camera is not open")
        if not self._is_grabbing:
            raise GrabbingNotStartedError("Call start_grabbing() before get_frame()")
        if self._device_exception is not None:
            raise self._device_exception

        self._ensure_frame_buffer()

        frame_info = MV_FRAME_OUT_INFO_EX()
        ret = self._sdk.MV_CC_GetOneFrameTimeout(
            self._handle,
            self._frame_buffer,
            self._frame_buffer_size,
            ctypes.byref(frame_info),
            timeout_ms,
        )
        if ret == MvErrorCode.MV_E_GC_TIMEOUT:
            raise FrameTimeoutError(f"No frame received within {timeout_ms} ms")
        _check(ret, "MV_CC_GetOneFrameTimeout")

        return self._decode_frame(self._frame_buffer, frame_info, output_format)

    def get_frame_ex(
        self,
        timeout_ms: int = 1000,
        output_format: OutputFormat = OutputFormat.BGR8,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Retrieve one frame together with its metadata.
        获取一帧及其元数据。

        Like :py:meth:`get_frame` but also returns a dictionary with frame
        metadata (frame number, timestamp, pixel format, etc.).
        类似 :py:meth:`get_frame`，但同时返回包含帧元数据（帧号、时间戳、
        像素格式等）的字典。

        Returns / 返回
        --------------
        tuple[numpy.ndarray, dict[str, Any]]
            ``(image, frame_info_dict)``
        """
        if not self._is_open:
            raise CameraNotOpenError("Camera is not open")
        if not self._is_grabbing:
            raise GrabbingNotStartedError("Call start_grabbing() before get_frame_ex()")
        if self._device_exception is not None:
            raise self._device_exception

        self._ensure_frame_buffer()

        frame_info = MV_FRAME_OUT_INFO_EX()
        ret = self._sdk.MV_CC_GetOneFrameTimeout(
            self._handle,
            self._frame_buffer,
            self._frame_buffer_size,
            ctypes.byref(frame_info),
            timeout_ms,
        )
        if ret == MvErrorCode.MV_E_GC_TIMEOUT:
            raise FrameTimeoutError(f"No frame received within {timeout_ms} ms")
        _check(ret, "MV_CC_GetOneFrameTimeout")

        image = self._decode_frame(self._frame_buffer, frame_info, output_format)
        meta = _frame_info_to_dict(frame_info)
        return image, meta

    # ------------------------------------------------------------------
    # Internal callback / 内部回调
    # ------------------------------------------------------------------

    def _register_exception_callback(self) -> None:
        """
        Register the SDK-level device exception callback.
        注册 SDK 级别的设备异常回调。

        The callback is invoked from an SDK-internal thread when a device
        exception (e.g. disconnection) occurs.  It stores the exception in
        ``_device_exception`` and optionally notifies the user via
        ``_on_device_exception``.
        当设备异常（如断开连接）发生时，从 SDK 内部线程调用此回调。
        异常被存储到 ``_device_exception`` 中，并可选地通过
        ``_on_device_exception`` 通知用户。
        """
        register_fn = getattr(self._sdk, "MV_CC_RegisterExceptionCallBack", None)
        if register_fn is None:
            logger.debug("MV_CC_RegisterExceptionCallBack not available in SDK")
            return
        sdk_cb = EXCEPTION_CALLBACK(self._internal_exception_callback)
        self._exception_callback_ref = sdk_cb  # prevent garbage collection
        ret = register_fn(self._handle, sdk_cb, None)
        if ret != MvErrorCode.MV_OK:
            logger.warning(
                "MV_CC_RegisterExceptionCallBack returned 0x%08X",
                ret & 0xFFFFFFFF,
            )
            self._exception_callback_ref = None

    def _internal_exception_callback(
        self,
        msg_type: int,
        p_user: c_void_p,
    ) -> None:
        """
        SDK-level exception callback trampoline.
        SDK 级别的异常回调中转函数。

        Called from an internal SDK thread when the camera reports a device
        exception such as disconnection.
        当相机报告设备异常（如断开连接）时从 SDK 内部线程调用。
        """
        if msg_type == _MV_EXCEPTION_DEV_DISCONNECT:
            exc = DeviceDisconnectedError(
                "Camera disconnected during operation",
                msg_type,
            )
        else:
            # The SDK currently only documents MV_EXCEPTION_DEV_DISCONNECT;
            # treat any other message type as an unexpected device exception.
            # SDK 目前仅记录了 MV_EXCEPTION_DEV_DISCONNECT；
            # 将其他消息类型视为意外的设备异常。
            exc = DeviceDisconnectedError(
                f"Unexpected device exception 0x{msg_type:08X}",
                msg_type,
            )
        logger.error("Device exception received: %s", exc)
        self._device_exception = exc
        if self._on_device_exception is not None:
            try:
                self._on_device_exception(exc)
            except Exception:  # noqa: BLE001
                logger.exception("Exception in on_device_exception callback")

    def _internal_callback(
        self,
        p_data: POINTER(c_ubyte),
        p_frame_info: POINTER(MV_FRAME_OUT_INFO_EX),
        p_user: c_void_p,
    ) -> None:
        """
        SDK-level callback trampoline.
        SDK 级别的回调中转函数。

        Called from an internal SDK thread.  Decodes the image and
        forwards it to the user-supplied callback.
        从 SDK 内部线程调用。解码图像并转发至用户提供的回调。
        """
        if self._user_callback is None:
            return
        try:
            frame_info = p_frame_info.contents
            frame_len = frame_info.nFrameLen
            w = frame_info.nWidth
            h = frame_info.nHeight
            pf = frame_info.enPixelType

            # Copy the buffer so it is safe to use after the callback returns
            # 复制缓冲区，确保回调返回后仍可安全使用
            buf = np.ctypeslib.as_array(p_data, shape=(frame_len,)).copy()
            image = raw_to_numpy(buf, w, h, pf, self._output_format_for_callback)
            meta = _frame_info_to_dict(frame_info)
            self._user_callback(image, meta)
        except Exception:  # noqa: BLE001
            logger.exception("Exception in image callback")

    # ------------------------------------------------------------------
    # Parameter access / 参数访问
    # ------------------------------------------------------------------

    def _get_int_value(self, name: str) -> int:
        """Read an integer GenICam node. / 读取整型 GenICam 节点。"""
        self._assert_open()
        val = MVCC_INTVALUE_EX()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetIntValueEx(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetIntValueEx({name!r})")
        return int(val.nCurValue)

    def _set_int_value(self, name: str, value: int) -> None:
        """Write an integer GenICam node. / 写入整型 GenICam 节点。"""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetIntValueEx(self._handle, name_bytes, int(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetIntValueEx({name!r})")

    def _get_float_value(self, name: str) -> float:
        """Read a float GenICam node. / 读取浮点型 GenICam 节点。"""
        self._assert_open()
        val = MVCC_FLOATVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetFloatValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetFloatValue({name!r})")
        return float(val.fCurValue)

    def _set_float_value(self, name: str, value: float) -> None:
        """Write a float GenICam node. / 写入浮点型 GenICam 节点。"""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetFloatValue(self._handle, name_bytes, float(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetFloatValue({name!r})")

    def _get_bool_value(self, name: str) -> bool:
        """Read a boolean GenICam node. / 读取布尔型 GenICam 节点。"""
        self._assert_open()
        val = c_uint(0)
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetBoolValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetBoolValue({name!r})")
        return bool(val.value)

    def _set_bool_value(self, name: str, value: bool) -> None:
        """Write a boolean GenICam node. / 写入布尔型 GenICam 节点。"""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetBoolValue(self._handle, name_bytes, int(bool(value)))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetBoolValue({name!r})")

    def _get_enum_value(self, name: str) -> int:
        """Read an enum GenICam node as its raw SDK integer value."""
        self._assert_open()
        val = MVCC_ENUMVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetEnumValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetEnumValue({name!r})")
        return int(val.nCurValue)

    def _set_enum_value(self, name: str, value: int) -> None:
        """Write an enum GenICam node by integer value."""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetEnumValue(self._handle, name_bytes, int(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetEnumValue({name!r})")

    def _set_enum_value_by_string(self, name: str, string_value: str) -> None:
        """Write an enum GenICam node by symbolic string value."""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        val_bytes = string_value.encode("utf-8")
        ret = self._sdk.MV_CC_SetEnumValueByString(self._handle, name_bytes, val_bytes)
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetEnumValueByString({name!r}={string_value!r})")

    def _get_string_value(self, name: str) -> str:
        """Read a string GenICam node. / 读取字符串 GenICam 节点。"""
        self._assert_open()
        val = MVCC_STRINGVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetStringValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetStringValue({name!r})")
        return val.chCurValue.decode("utf-8", errors="replace").strip("\x00")

    def _set_string_value(self, name: str, value: str) -> None:
        """Write a string GenICam node. / 写入字符串 GenICam 节点。"""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        val_bytes = value.encode("utf-8")
        ret = self._sdk.MV_CC_SetStringValue(self._handle, name_bytes, val_bytes)
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetStringValue({name!r})")

    def _execute_param_node(self, node: ParamNode) -> None:
        """Execute a command-type ``ParamNode``. / 执行命令型 ``ParamNode``。"""
        if node.data_type != "command":
            raise ParameterValueError(f"Parameter {node.name!r} is not a command node")
        self._assert_open()
        name_bytes = node.name.encode("utf-8")
        ret = self._sdk.MV_CC_SetCommandValue(self._handle, name_bytes)
        _check(ret, f"MV_CC_SetCommandValue({node.name!r})")

    # ------------------------------------------------------------------
    # Configuration file import / export
    # 配置文件导入 / 导出
    # ------------------------------------------------------------------

    def export_config(self, file_path: str) -> None:
        """
        Export the current camera configuration to a file.
        将当前相机配置导出到文件。

        Uses the SDK's ``MV_CC_FeatureSave`` to write all GenICam
        parameters to an XML-format configuration file.
        使用 SDK 的 ``MV_CC_FeatureSave`` 将所有 GenICam 参数写入
        XML 格式的配置文件。

        Parameters / 参数
        -----------------
        file_path:
            Destination file path (e.g. ``"camera_config.xml"``).
            目标文件路径（如 ``"camera_config.xml"``）。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open.
            当相机未打开时抛出。
        HikCameraError
            When the SDK call fails.
            当 SDK 调用失败时抛出。
        """
        self._assert_open()
        path_bytes = os.fsencode(os.path.abspath(file_path))
        ret = self._sdk.MV_CC_FeatureSave(self._handle, path_bytes)
        _check(ret, f"MV_CC_FeatureSave({file_path!r})")
        logger.info("Camera configuration exported to %s", file_path)

    def import_config(self, file_path: str) -> None:
        """
        Import camera configuration from a file.
        从文件导入相机配置。

        Uses the SDK's ``MV_CC_FeatureLoad`` to restore GenICam
        parameters from a previously exported XML configuration file.
        使用 SDK 的 ``MV_CC_FeatureLoad`` 从之前导出的 XML 配置文件
        恢复 GenICam 参数。

        Parameters / 参数
        -----------------
        file_path:
            Source file path (e.g. ``"camera_config.xml"``).
            源文件路径（如 ``"camera_config.xml"``）。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open.
            当相机未打开时抛出。
        FileNotFoundError
            When *file_path* does not exist.
            当 *file_path* 不存在时抛出。
        HikCameraError
            When the SDK call fails.
            当 SDK 调用失败时抛出。
        """
        self._assert_open()
        abs_path = os.path.abspath(file_path)
        if not os.path.isfile(abs_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path!r}")
        path_bytes = os.fsencode(abs_path)
        ret = self._sdk.MV_CC_FeatureLoad(self._handle, path_bytes)
        _check(ret, f"MV_CC_FeatureLoad({file_path!r})")
        logger.info("Camera configuration imported from %s", file_path)

    # ------------------------------------------------------------------
    # User set save / load / 用户集保存 / 加载
    # ------------------------------------------------------------------

    def save_user_set(
        self,
        user_set: UserSetSelector = UserSetSelector.USER_SET_1,
    ) -> None:
        """
        Save the current camera parameters to a user set stored on the device.
        将当前相机参数保存至设备上的用户集。

        Parameters / 参数
        -----------------
        user_set:
            Structured enum value such as ``UserSetSelector.USER_SET_1``.
            结构化枚举值，例如 ``UserSetSelector.USER_SET_1``。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        ParameterNotSupportedError
            When the device does not support user sets.
            当设备不支持用户集时抛出。
        HikCameraError
            When the SDK call fails. / 当 SDK 调用失败时抛出。
        """
        self._assert_open()
        validated_selector = UserSetControl.UserSetSelector.validate(user_set)
        self.params.UserSetControl.UserSetSelector.set(validated_selector)
        self.params.UserSetControl.UserSetSave.execute()
        logger.info("Camera parameters saved to user set %r", str(validated_selector))

    def load_user_set(
        self,
        user_set: UserSetSelector = UserSetSelector.USER_SET_1,
    ) -> None:
        """
        Load camera parameters from a user set stored on the device.
        从设备上存储的用户集加载相机参数。

        Parameters / 参数
        -----------------
        user_set:
            Structured enum value such as ``UserSetSelector.USER_SET_1``.
            结构化枚举值，例如 ``UserSetSelector.USER_SET_1``。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        ParameterNotSupportedError
            When the device does not support user sets.
            当设备不支持用户集时抛出。
        HikCameraError
            When the SDK call fails. / 当 SDK 调用失败时抛出。
        """
        self._assert_open()
        validated_selector = UserSetControl.UserSetSelector.validate(user_set)
        self.params.UserSetControl.UserSetSelector.set(validated_selector)
        self.params.UserSetControl.UserSetLoad.execute()
        logger.info("Camera parameters loaded from user set %r", str(validated_selector))

    # ------------------------------------------------------------------
    # Camera information / 相机信息
    # ------------------------------------------------------------------

    def get_camera_info(self) -> dict[str, Any]:
        """
        Retrieve common camera parameters as a dictionary.
        以字典形式获取常用相机参数。

        This method can be called any time after :py:meth:`open` (before
        or during grabbing).  It collects commonly used parameters such
        as image size, frame rate, exposure, and gain.
        此方法可在 :py:meth:`open` 之后的任何时间调用（取帧前或取帧期间）。
        它收集图像尺寸、帧率、曝光和增益等常用参数。

        Parameters that are not supported by the camera model are
        silently omitted from the result.
        相机型号不支持的参数将被静默忽略，不包含在结果中。

        Returns / 返回
        --------------
        dict[str, Any]
            A dictionary-like object with available parameter values.
            Stored keys remain the legacy string names (for backward
            compatibility), but lookups also accept ``ParamNode`` objects such
            as ``ImageFormatControl.Width`` and ``AcquisitionControl.ExposureTime``.
            String-key access remains supported for now, but new code should
            prefer ``ParamNode`` lookups and string-key access may be gradually
            deprecated in a future release.
            包含可用参数值的类字典对象。实际存储的键仍是旧的字符串名称
            （保持向后兼容），但取值时也支持 ``ParamNode``，例如
            ``ImageFormatControl.Width``、``AcquisitionControl.ExposureTime``。
            目前仍兼容字符串 key，但新代码应优先使用 ``ParamNode`` 访问；
            后续版本中字符串 key 访问可能会逐步废弃。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        """
        self._assert_open()
        info: CameraInfoDict = CameraInfoDict()
        missing = object()

        for node in (
            ImageFormatControl.Width,
            ImageFormatControl.Height,
            ImageFormatControl.OffsetX,
            ImageFormatControl.OffsetY,
            TransportLayerControl.PayloadSize,
            ImageFormatControl.WidthMax,
            ImageFormatControl.HeightMax,
            AcquisitionControl.ExposureTime,
            AnalogControl.Gain,
            AcquisitionControl.AcquisitionFrameRate,
            AcquisitionControl.ResultingFrameRate,
            AnalogControl.Gamma,
            AcquisitionControl.AcquisitionFrameRateEnable,
            AnalogControl.GammaEnable,
            ImageFormatControl.PixelFormat,
            AcquisitionControl.ExposureAuto,
            AnalogControl.GainAuto,
            AnalogControl.BalanceWhiteAuto,
            AcquisitionControl.TriggerMode,
            AcquisitionControl.TriggerSource,
            DeviceControl.DeviceModelName,
            DeviceControl.DeviceSerialNumber,
            DeviceControl.DeviceFirmwareVersion,
            DeviceControl.DeviceUserID,
        ):
            value = self._get_param_node_value(node, default=missing)
            if value is not missing:
                info[node.name] = value

        return info

    def _set_param_node_value(self, node: ParamNode, value: Any) -> None:
        """Validate and write a structured parameter node."""
        if node.data_type == "command":
            raise ParameterValueError(
                f"Parameter {node.name!r} is a command node; use execute() instead"
            )
        name = node.name
        value = node.validate(value)
        expected_type = _PARAMETER_SCHEMA[name]
        self._write_value_for_node_type(name, value, expected_type)

    def _write_value_for_node_type(
        self,
        name: str,
        value: int | float | bool | str,
        expected_type: type,
    ) -> None:
        """Validate *value* with ``isinstance`` and dispatch the SDK call.

        通过 ``isinstance`` 校验 *value* 并分派 SDK 调用。

        Dispatch is based on *expected_type* (from the schema), **not** the
        runtime type of *value*.  This prevents ``bool`` (a subclass of
        ``int``) from accidentally routing to the bool setter for an ``int``
        schema entry, and prevents ``StrEnum``/``IntEnum`` subclass values
        from being routed to the wrong setter for plain ``str``/``int``
        schema entries.
        分派基于 *expected_type*（来自模式），而非 *value* 的运行时类型。这样
        可以避免 ``bool``（``int`` 的子类）意外地为 ``int`` 模式条目路由到
        布尔 setter，同时也防止 ``StrEnum``/``IntEnum`` 子类值为纯
        ``str``/``int`` 模式条目路由到错误的 setter。
        """
        # Reject bool for int/float schemas (bool is a subclass of int).
        # 对 int/float 模式拒绝 bool 值（bool 是 int 的子类）。
        if expected_type in (int, float) and isinstance(value, bool):
            raise ParameterValueError(
                f"Parameter {name!r} expects {expected_type.__name__}, "
                f"got bool: {value!r}"
            )

        # Allow int → float promotion (int is naturally promotable to float).
        # 允许 int → float 自动提升（int 可自然提升为 float）。
        if expected_type is float and isinstance(value, int):
            value = float(value)

        if not isinstance(value, expected_type):
            raise ParameterValueError(
                f"Parameter {name!r} expects {expected_type.__name__}, "
                f"got {type(value).__name__}: {value!r}"
            )

        # Dispatch based on *expected_type* (schema), not the runtime type.
        # 基于 *expected_type*（模式）分派，而非运行时类型。
        if expected_type is bool:
            self._set_bool_value(name, value)
        elif expected_type is int:
            self._set_int_value(name, value)
        elif expected_type is float:
            self._set_float_value(name, value)
        elif expected_type is str:
            self._set_string_value(name, value)
        elif issubclass(expected_type, StrEnum):
            self._set_enum_value_by_string(name, str(value))
        elif issubclass(expected_type, IntEnum):
            self._set_enum_value(name, int(value))
        else:  # pragma: no cover – defensive
            raise ParameterValueError(
                f"Unsupported schema type {expected_type.__name__} for parameter {name!r}"
            )

    def _get_param_node_value(self, node: ParamNode, default: Any = None) -> Any:
        """Read a structured parameter node and return *default* if unsupported."""
        if node.data_type == "command":
            return default
        name = node.name
        expected_type = _PARAMETER_SCHEMA[name]
        getters: tuple[Callable[[str], Any], ...]
        if expected_type is bool:
            getters = (self._get_bool_value,)
        elif expected_type is int:
            getters = (self._get_int_value,)
        elif expected_type is float:
            getters = (self._get_float_value,)
        elif expected_type is str:
            getters = (self._get_string_value,)
        elif issubclass(expected_type, (StrEnum, IntEnum)):
            getters = (self._get_enum_value,)
        else:
            getters = ()

        for getter in getters:
            try:
                return getter(name)
            except (ParameterNotSupportedError, ParameterError):
                continue
        return default

    # ------------------------------------------------------------------
    # SDK pixel conversion / SDK 像素转换
    # ------------------------------------------------------------------

    def sdk_convert_pixel(
        self,
        src_data: bytes | np.ndarray,
        width: int,
        height: int,
        src_format: int,
        dst_format: int,
    ) -> np.ndarray:
        """
        Convert a raw frame buffer using the SDK's ``MV_CC_ConvertPixelTypeEx``.
        使用 SDK 的 ``MV_CC_ConvertPixelTypeEx`` 转换原始帧缓冲区。

        This is faster than the pure-Python conversion in
        :py:mod:`hikcamera.utils` for large, high-bit-depth images.
        对于大尺寸、高位深图像，比 :py:mod:`hikcamera.utils` 中的纯 Python
        转换更快。

        Parameters / 参数
        -----------------
        src_data:
            Raw source pixel data. / 原始源像素数据。
        width, height:
            Frame dimensions in pixels. / 帧尺寸（像素）。
        src_format:
            Source pixel format (a :py:class:`~hikcamera.enums.PixelFormat`).
            源像素格式（:py:class:`~hikcamera.enums.PixelFormat`）。
        dst_format:
            Destination pixel format. / 目标像素格式。

        Returns / 返回
        --------------
        numpy.ndarray
            Converted image data as a 1-D ``uint8`` array (caller is
            responsible for reshaping).
            转换后的图像数据，为一维 ``uint8`` 数组（调用者负责重塑形状）。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        ImageConversionError
            When the SDK conversion fails. / 当 SDK 转换失败时抛出。
        """
        self._assert_open()
        if isinstance(src_data, np.ndarray):
            src_bytes = src_data.tobytes()
        else:
            src_bytes = bytes(src_data)

        # Estimate destination buffer size (worst case: 4 bytes/pixel)
        # 估算目标缓冲区大小（最差情况：4 字节/像素）
        dst_size = width * height * 4
        dst_buf = (c_ubyte * dst_size)()

        src_buf = (c_ubyte * len(src_bytes)).from_buffer_copy(src_bytes)

        params = MV_CC_PIXEL_CONVERT_PARAM_EX()
        params.nWidth = width
        params.nHeight = height
        params.enSrcPixelType = src_format
        params.pSrcData = src_buf
        params.nSrcDataLen = len(src_bytes)
        params.enDstPixelType = dst_format
        params.pDstBuffer = dst_buf
        params.nDstBufferSize = dst_size

        ret = self._sdk.MV_CC_ConvertPixelTypeEx(self._handle, ctypes.byref(params))
        if ret != MvErrorCode.MV_OK:
            code = ret & 0xFFFFFFFF
            raise ImageConversionError(
                f"MV_CC_ConvertPixelTypeEx failed: 0x{code:08X}", code
            )

        return np.ctypeslib.as_array(dst_buf, shape=(params.nDstLen,)).copy()

    # ------------------------------------------------------------------
    # Private helpers / 内部辅助方法
    # ------------------------------------------------------------------

    def _assert_open(self) -> None:
        if not self._is_open:
            raise CameraNotOpenError("Camera is not open")

    def _ensure_frame_buffer(self) -> None:
        """
        Allocate (or reallocate) the frame buffer based on PayloadSize.
        根据 PayloadSize 分配（或重新分配）帧缓冲区。
        """
        payload_size = self.params.TransportLayerControl.PayloadSize.get(default=0)

        # Use a reasonable fallback if PayloadSize is unavailable
        # 如果 PayloadSize 不可用，使用合理的回退值
        if payload_size <= 0:
            payload_size = _DEFAULT_FRAME_BUFFER_SIZE

        if self._frame_buffer is None or self._frame_buffer_size < payload_size:
            self._frame_buffer = (c_ubyte * payload_size)()
            self._frame_buffer_size = payload_size

    def _decode_frame(
        self,
        data: ctypes.Array[c_ubyte],
        frame_info: MV_FRAME_OUT_INFO_EX,
        output_format: OutputFormat,
    ) -> np.ndarray:
        """
        Decode a frame buffer to a numpy array.
        将帧缓冲区解码为 numpy 数组。
        """
        w = frame_info.nWidth
        h = frame_info.nHeight
        pf = frame_info.enPixelType
        buf = np.ctypeslib.as_array(data, shape=(frame_info.nFrameLen,))
        return raw_to_numpy(buf, w, h, pf, output_format)


# ---------------------------------------------------------------------------
# Module-level convenience functions / 模块级便捷函数
# ---------------------------------------------------------------------------

def enumerate_cameras(
    transport_layers: TransportLayer = TransportLayer.ALL,
) -> list[DeviceInfo]:
    """
    Enumerate all accessible cameras.
    枚举所有可访问的相机。

    This is a module-level shortcut for :py:meth:`HikCamera.enumerate`.
    这是 :py:meth:`HikCamera.enumerate` 的模块级快捷方式。

    Parameters / 参数
    -----------------
    transport_layers:
        Transport layers to scan. / 要扫描的传输层。

    Returns / 返回
    --------------
    list[DeviceInfo]
    """
    return HikCamera.enumerate(transport_layers)


# ---------------------------------------------------------------------------
# Helpers / 辅助函数
# ---------------------------------------------------------------------------

def _frame_info_to_dict(frame_info: MV_FRAME_OUT_INFO_EX) -> dict[str, Any]:
    """
    Convert an ``MV_FRAME_OUT_INFO_EX`` struct to a plain Python dict.
    将 ``MV_FRAME_OUT_INFO_EX`` 结构体转换为普通 Python 字典。
    """
    ts_high = frame_info.nDevTimeStampHigh
    ts_low = frame_info.nDevTimeStampLow
    timestamp_ns = (ts_high << 32 | ts_low)
    return {
        "frame_num": frame_info.nFrameNum,
        "width": frame_info.nWidth,
        "height": frame_info.nHeight,
        "pixel_format": frame_info.enPixelType,
        "frame_length": frame_info.nFrameLen,
        "timestamp_ns": timestamp_ns,
        "host_timestamp_ns": frame_info.nHostTimeStamp,
        "lost_packets": frame_info.nLostPacket,
        "gain": frame_info.fGain,
        "exposure_time": frame_info.fExposureTime,
        "average_brightness": frame_info.nAverageBrightness,
        "red": frame_info.nRed,
        "green": frame_info.nGreen,
        "blue": frame_info.nBlue,
        "frame_counter": frame_info.nFrameCounter,
        "trigger_index": frame_info.nTriggerIndex,
    }
