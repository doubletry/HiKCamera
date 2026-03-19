"""
High-level Hikvision industrial camera interface.
海康威视工业相机高层接口。

Typical usage (polling) / 典型用法（轮询模式）
----------------------------------------------

.. code-block:: python

    from hikcamera import HikCamera, AccessMode, OutputFormat

    cameras = HikCamera.enumerate()
    with HikCamera.from_device_info(cameras[0]) as cam:
        cam.open(AccessMode.EXCLUSIVE)
        cam.set_parameter("ExposureTime", 5000.0)
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
from collections.abc import Callable
from ctypes import POINTER, c_ubyte, c_uint, c_void_p
from enum import IntEnum, StrEnum
from typing import Any

import numpy as np

from .enums import (
    AccessMode,
    AcquisitionMode,
    BalanceWhiteAuto,
    ExposureAuto,
    GainAuto,
    GammaSelector,
    LineMode,
    LineSelector,
    MvErrorCode,
    OutputFormat,
    PixelFormat,
    StreamingMode,
    TransportLayer,
    TriggerActivation,
    TriggerMode,
    TriggerSelector,
    TriggerSource,
    UserSetDefault,
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

# GenICam parameter schema used by :py:meth:`set_parameter` for automatic
# type dispatch and value validation.  Each entry maps a GenICam node name to
# its expected Python type.  For enum parameters the value is the concrete
# ``StrEnum`` or ``IntEnum`` subclass; ``isinstance(value, expected_type)`` is
# used for validation.  Parameters not listed here fall back to Python-type
# dispatch.
# GenICam 参数模式，供 :py:meth:`set_parameter` 用于自动类型分派与值校验。
# 每个条目将 GenICam 节点名称映射到其期望的 Python 类型。枚举参数的值为具体
# 的 ``StrEnum`` 或 ``IntEnum`` 子类；使用 ``isinstance(value, expected_type)``
# 进行校验。此处未列出的参数按 Python 类型回退分派。
_PARAMETER_SCHEMA: dict[str, type] = {
    # Image format / 图像格式
    "Width": int,
    "Height": int,
    "OffsetX": int,
    "OffsetY": int,

    # Exposure & gain / 曝光与增益
    "ExposureTime": float,
    "ExposureAuto": ExposureAuto,
    "Gain": float,
    "GainAuto": GainAuto,
    "Gamma": float,
    "GammaEnable": bool,
    "GammaSelector": GammaSelector,

    # Frame rate / 帧率
    "AcquisitionFrameRate": float,
    "AcquisitionFrameRateEnable": bool,

    # Acquisition / 采集
    "AcquisitionMode": AcquisitionMode,

    # Trigger / 触发
    "TriggerMode": TriggerMode,
    "TriggerSource": TriggerSource,
    "TriggerActivation": TriggerActivation,
    "TriggerSelector": TriggerSelector,

    # I/O / 输入输出
    "LineSelector": LineSelector,
    "LineMode": LineMode,

    # White balance / 白平衡
    "BalanceWhiteAuto": BalanceWhiteAuto,

    # User set / 用户集
    "UserSetSelector": UserSetSelector,
    "UserSetDefault": UserSetDefault,

    # Device info (string) / 设备信息（字符串）
    "DeviceUserID": str,

    # GigE network / GigE 网络
    "GevSCPSPacketSize": int,

    # Pixel format / 像素格式
    "PixelFormat": PixelFormat,

    # Binning / 合并
    "BinningHorizontal": int,
    "BinningVertical": int,
    "DecimationHorizontal": int,
    "DecimationVertical": int,
}

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
        ret = cam._sdk.MV_CC_CreateHandle(ctypes.byref(cam._handle), ctypes.byref(device_info._raw))
        _check(ret, "MV_CC_CreateHandle")
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
        devices = cls.enumerate(transport_layers)
        for dev in devices:
            if dev.serial_number == serial_number:
                return cls.from_device_info(dev)
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
            except ParameterError:
                logger.debug(
                    "Could not set GevSCPSPacketSize=%d (may not be a GigE camera)",
                    packet_size,
                )
        else:
            # Auto-detect optimal / 自动检测最优值
            try:
                optimal = self.get_optimal_packet_size()
                if optimal > 0:
                    self.set_packet_size(optimal)
                    logger.debug("GigE packet size set to optimal value %d", optimal)
            except (ParameterError, HikCameraError):
                logger.debug("Could not auto-configure GigE packet size (may not be a GigE camera)")

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
        self.set_int_parameter("GevSCPSPacketSize", size)
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
        return self.get_int_parameter("GevSCPSPacketSize")

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
            re-raised by :py:meth:`stop_grabbing` and :py:meth:`get_frame`.
            即使未提供此回调，异常也会在内部存储，并在
            :py:meth:`stop_grabbing` 和 :py:meth:`get_frame` 中重新抛出。

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
            self._exception_callback_ref = None
            self._on_device_exception = None
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
        self._callback_ref = None
        self._user_callback = None
        self._exception_callback_ref = None
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
            exc = DeviceDisconnectedError(
                f"Device exception 0x{msg_type:08X}",
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

    def get_int_parameter(self, name: str) -> int:
        """
        Get an integer camera parameter by name.
        按名称获取整型相机参数。

        Parameters / 参数
        -----------------
        name:
            GenICam parameter name (e.g. ``"Width"``, ``"Height"``).
            GenICam 参数名称（如 ``"Width"``、``"Height"``）。

        Returns / 返回
        --------------
        int

        Raises / 异常
        -------------
        ParameterNotSupportedError
            When the parameter does not exist on this camera model.
            当参数在此相机型号上不存在时抛出。
        ParameterError
            When another SDK error occurs.
            当发生其他 SDK 错误时抛出。
        """
        self._assert_open()
        val = MVCC_INTVALUE_EX()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetIntValueEx(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetIntValueEx({name!r})")
        return int(val.nCurValue)

    def set_int_parameter(self, name: str, value: int) -> None:
        """
        Set an integer camera parameter.
        设置整型相机参数。

        Raises / 异常
        -------------
        ParameterNotSupportedError
            When the parameter does not exist.
            当参数不存在时抛出。
        ParameterReadOnlyError
            When the parameter is read-only.
            当参数为只读时抛出。
        ParameterError
            On other SDK errors. / 其他 SDK 错误时抛出。
        """
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetIntValueEx(self._handle, name_bytes, int(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetIntValueEx({name!r})")

    def get_float_parameter(self, name: str) -> float:
        """
        Get a float camera parameter by name.
        按名称获取浮点型相机参数。
        """
        self._assert_open()
        val = MVCC_FLOATVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetFloatValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetFloatValue({name!r})")
        return float(val.fCurValue)

    def set_float_parameter(self, name: str, value: float) -> None:
        """
        Set a float camera parameter.
        设置浮点型相机参数。
        """
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetFloatValue(self._handle, name_bytes, float(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetFloatValue({name!r})")

    def get_bool_parameter(self, name: str) -> bool:
        """
        Get a boolean camera parameter.
        获取布尔型相机参数。
        """
        self._assert_open()
        val = c_uint(0)
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetBoolValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetBoolValue({name!r})")
        return bool(val.value)

    def set_bool_parameter(self, name: str, value: bool) -> None:
        """
        Set a boolean camera parameter.
        设置布尔型相机参数。
        """
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetBoolValue(self._handle, name_bytes, int(bool(value)))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetBoolValue({name!r})")

    def get_enum_parameter(self, name: str) -> int:
        """
        Get an enum camera parameter (as raw integer value).
        获取枚举型相机参数（返回原始整数值）。
        """
        self._assert_open()
        val = MVCC_ENUMVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetEnumValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetEnumValue({name!r})")
        return int(val.nCurValue)

    def set_enum_parameter(self, name: str, value: int) -> None:
        """
        Set an enum camera parameter by integer value.
        按整数值设置枚举型相机参数。
        """
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetEnumValue(self._handle, name_bytes, int(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetEnumValue({name!r})")

    def set_enum_parameter_by_string(self, name: str, string_value: str) -> None:
        """
        Set an enum camera parameter by string (symbolic name).
        按字符串（符号名称）设置枚举型相机参数。
        """
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

    def get_string_parameter(self, name: str) -> str:
        """
        Get a string camera parameter.
        获取字符串型相机参数。
        """
        self._assert_open()
        val = MVCC_STRINGVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetStringValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetStringValue({name!r})")
        return val.chCurValue.decode("utf-8", errors="replace").strip("\x00")

    def set_string_parameter(self, name: str, value: str) -> None:
        """
        Set a string camera parameter.
        设置字符串型相机参数。
        """
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

    def execute_command(self, name: str) -> None:
        """
        Execute a GenICam command node (e.g. ``"TriggerSoftware"``).
        执行 GenICam 命令节点（如 ``"TriggerSoftware"``）。
        """
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetCommandValue(self._handle, name_bytes)
        _check(ret, f"MV_CC_SetCommandValue({name!r})")

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

    def save_user_set(self, user_set: str = "UserSet1") -> None:
        """
        Save the current camera parameters to a user set stored on the device.
        将当前相机参数保存至设备上的用户集。

        Parameters / 参数
        -----------------
        user_set:
            Name of the user set (e.g. ``"UserSet1"``, ``"UserSet2"``,
            ``"UserSet3"``).  The available sets depend on the camera
            model.
            用户集名称（如 ``"UserSet1"``、``"UserSet2"``、``"UserSet3"``）。
            可用的用户集取决于相机型号。

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
        self.set_enum_parameter_by_string("UserSetSelector", user_set)
        self.execute_command("UserSetSave")
        logger.info("Camera parameters saved to user set %r", user_set)

    def load_user_set(self, user_set: str = "UserSet1") -> None:
        """
        Load camera parameters from a user set stored on the device.
        从设备上存储的用户集加载相机参数。

        Parameters / 参数
        -----------------
        user_set:
            Name of the user set to load.
            要加载的用户集名称。

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
        self.set_enum_parameter_by_string("UserSetSelector", user_set)
        self.execute_command("UserSetLoad")
        logger.info("Camera parameters loaded from user set %r", user_set)

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
            A dictionary with available parameter values.  Typical keys
            include ``"Width"``, ``"Height"``, ``"PixelFormat"``,
            ``"ExposureTime"``, ``"Gain"``, ``"AcquisitionFrameRate"``,
            ``"PayloadSize"``, ``"DeviceModelName"``, etc.
            包含可用参数值的字典。典型键包括 ``"Width"``、``"Height"``、
            ``"PixelFormat"``、``"ExposureTime"``、``"Gain"``、
            ``"AcquisitionFrameRate"``、``"PayloadSize"``、
            ``"DeviceModelName"`` 等。

        Raises / 异常
        -------------
        CameraNotOpenError
            When the camera is not open. / 当相机未打开时抛出。
        """
        self._assert_open()
        info: dict[str, Any] = {}

        # Integer parameters / 整型参数
        for name in (
            "Width",
            "Height",
            "OffsetX",
            "OffsetY",
            "PayloadSize",
            "WidthMax",
            "HeightMax",
        ):
            try:
                info[name] = self.get_int_parameter(name)
            except (ParameterNotSupportedError, ParameterError):
                pass

        # Float parameters / 浮点参数
        for name in (
            "ExposureTime",
            "Gain",
            "AcquisitionFrameRate",
            "ResultingFrameRate",
            "Gamma",
        ):
            try:
                info[name] = self.get_float_parameter(name)
            except (ParameterNotSupportedError, ParameterError):
                pass

        # Bool parameters / 布尔参数
        for name in (
            "AcquisitionFrameRateEnable",
            "GammaEnable",
        ):
            try:
                info[name] = self.get_bool_parameter(name)
            except (ParameterNotSupportedError, ParameterError):
                pass

        # Enum parameters (returned as raw integer values)
        # 枚举参数（返回原始整数值）
        for name in (
            "PixelFormat",
            "ExposureAuto",
            "GainAuto",
            "BalanceWhiteAuto",
            "TriggerMode",
            "TriggerSource",
        ):
            try:
                info[name] = self.get_enum_parameter(name)
            except (ParameterNotSupportedError, ParameterError):
                pass

        # String parameters / 字符串参数
        for name in (
            "DeviceModelName",
            "DeviceSerialNumber",
            "DeviceFirmwareVersion",
            "DeviceUserID",
        ):
            try:
                info[name] = self.get_string_parameter(name)
            except (ParameterNotSupportedError, ParameterError):
                pass

        return info

    def set_parameter(self, name: str, value: int | float | bool | str) -> None:
        """
        Set a camera parameter with automatic type dispatch and validation.
        自动类型分派并校验设置相机参数。

        If *name* appears in :data:`_PARAMETER_SCHEMA`, the value is validated
        via ``isinstance(value, expected_type)`` **before** any SDK call is
        made.  For enum parameters the expected type is the corresponding
        ``StrEnum`` / ``IntEnum`` subclass (e.g. :py:class:`GainAuto`), so
        only values of that exact enum type are accepted.  For parameters not
        in the schema, dispatch falls back to Python type:
        bool → integer → float → string.
        Silently absorbs :py:exc:`ParameterNotSupportedError` when the
        parameter is absent on this camera model (logs a debug message).

        如果 *name* 存在于 :data:`_PARAMETER_SCHEMA`，则在调用 SDK 之前，先通过
        ``isinstance(value, expected_type)`` 进行校验。枚举参数的期望类型为对应
        的 ``StrEnum`` / ``IntEnum`` 子类（如 :py:class:`GainAuto`），因此只接受
        该枚举类型的值。不在模式中的参数按 Python 类型回退分派：
        bool → 整型 → 浮点 → 字符串。
        当参数在此相机型号上不存在时，静默吸收
        :py:exc:`ParameterNotSupportedError`（输出调试日志）。

        Parameters / 参数
        -----------------
        name:
            GenICam node name. / GenICam 节点名称。
        value:
            New value.  For schema-registered parameters, the value must be an
            instance of the declared type (e.g. ``GainAuto.OFF`` for
            ``"GainAuto"``).  For unknown parameters the method dispatches by
            Python type.
            新值。对于已注册模式的参数，值必须是声明类型的实例（如 ``"GainAuto"``
            需传入 ``GainAuto.OFF``）。对于未知参数，按 Python 类型分派。

        Raises / 异常
        -------------
        ParameterValueError
            When the value does not match the expected type for a known
            parameter.
            当值与已知参数的期望类型不匹配时抛出。
        ParameterReadOnlyError
            When the parameter is read-only. / 当参数为只读时抛出。
        ParameterError
            When the underlying SDK call fails for an unrelated reason.
            当底层 SDK 调用因其他原因失败时抛出。
        """
        expected_type = _PARAMETER_SCHEMA.get(name)
        try:
            if expected_type is not None:
                self._set_parameter_by_schema(name, value, expected_type)
            elif isinstance(value, bool):
                self.set_bool_parameter(name, value)
            elif isinstance(value, int):
                self.set_int_parameter(name, value)
            elif isinstance(value, float):
                self.set_float_parameter(name, value)
            else:
                self.set_string_parameter(name, str(value))
        except ParameterNotSupportedError:
            logger.debug("Parameter %r not supported on this camera; skipping", name)

    def _set_parameter_by_schema(
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
            self.set_bool_parameter(name, value)
        elif expected_type is int:
            self.set_int_parameter(name, value)
        elif expected_type is float:
            self.set_float_parameter(name, value)
        elif expected_type is str:
            self.set_string_parameter(name, value)
        elif issubclass(expected_type, StrEnum):
            self.set_enum_parameter_by_string(name, str(value))
        elif issubclass(expected_type, IntEnum):
            self.set_enum_parameter(name, int(value))
        else:  # pragma: no cover – defensive
            raise ParameterValueError(
                f"Unsupported schema type {expected_type.__name__} for parameter {name!r}"
            )

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """
        Get a camera parameter with automatic type dispatch.
        自动类型分派获取相机参数。

        Tries integer → float → string in order.  Returns *default* when
        the parameter is absent on this camera model.
        按 整型 → 浮点 → 字符串 的顺序尝试。当参数在此相机型号上不存在时
        返回 *default*。

        Parameters / 参数
        -----------------
        name:
            GenICam node name. / GenICam 节点名称。
        default:
            Value returned when the parameter is not supported.
            当参数不受支持时返回的值。
        """
        for getter in (
            self.get_int_parameter,
            self.get_float_parameter,
            self.get_string_parameter,
        ):
            try:
                return getter(name)
            except ParameterNotSupportedError:
                continue
            except ParameterError:
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
        try:
            payload_size = self.get_int_parameter("PayloadSize")
        except ParameterError:
            payload_size = 0

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
