"""
Low-level wrapper around the Hikvision MVS SDK dynamic library.
海康威视 MVS SDK 动态库的底层封装模块。

This module locates the shared library at runtime and wraps every C function
used by :py:mod:`hikcamera.camera` via :py:mod:`ctypes`.  Callers should
use the high-level :py:class:`~hikcamera.camera.HikCamera` class instead.
本模块在运行时定位共享库，并通过 :py:mod:`ctypes` 封装
:py:mod:`hikcamera.camera` 所用的全部 C 函数。调用者应使用
高层接口 :py:class:`~hikcamera.camera.HikCamera`。

Platform notes / 平台说明
-------------------------
* **Linux**: ``libMvCameraControl.so``  (installed by the MVS SDK into
  ``/opt/MVS/lib/64/`` or ``/opt/MVS/lib/32/``)
  （MVS SDK 安装至 ``/opt/MVS/lib/64/`` 或 ``/opt/MVS/lib/32/``）
* **Windows**: ``MvCameraControl.dll``  (installed into
  ``C:\\Program Files (x86)\\Common Files\\MVS\\Runtime\\Win64_x64\\``
  or legacy ``C:\\Program Files (x86)\\MVS\\Runtime\\Win64_x64\\``)
  （安装至 ``C:\\Program Files (x86)\\Common Files\\MVS\\Runtime\\Win64_x64\\``
  或旧版 ``C:\\Program Files (x86)\\MVS\\Runtime\\Win64_x64\\``）

The SDK can be downloaded from
SDK 可从以下地址下载：
https://www.hikrobotics.com/cn/machinevision/service/download/?module=0
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import platform
from ctypes import (
    POINTER,
    Structure,
    c_char,
    c_float,
    c_int,
    c_int64,
    c_ubyte,
    c_uint,
    c_uint8,
    c_uint16,
    c_void_p,
)
from typing import TYPE_CHECKING

from .exceptions import SDKNotFoundError

if TYPE_CHECKING:
    pass  # pragma: no cover

# ---------------------------------------------------------------------------
# Type aliases matching the SDK's typedefs
# 与 SDK typedef 对应的类型别名
# ---------------------------------------------------------------------------
MV_HANDLE = c_void_p
MV_INT_VALUE = c_int
MV_FLOAT_VALUE = c_float
MV_BOOL_VALUE = c_uint  # MV_BOOL in SDK

# ---------------------------------------------------------------------------
# SDK structs / SDK 结构体
# ---------------------------------------------------------------------------

_MV_GIGE_DEVICE_INFO_MAX_STR_LEN = 64
_MV_USB3_DEVICE_INFO_MAX_STR_LEN = 64
_MV_MAX_XML_SYMBOL_STRLEN = 64
_MV_MAX_XML_STRVALUE_STRLEN = 256
_MAX_DEVICE_NUM = 256


class MV_GIGE_DEVICE_INFO(Structure):  # noqa: N801
    """
    GigE device information returned by MV_CC_EnumDevices.
    MV_CC_EnumDevices 返回的 GigE 设备信息。
    """

    _fields_ = [
        ("nIpCfgOption", c_uint),
        ("nIpCfgCurrent", c_uint),
        ("nCurrentIp", c_uint),
        ("nCurrentSubNetMask", c_uint),
        ("nDefultGateWay", c_uint),
        ("chManufacturerName", c_char * 32),
        ("chModelName", c_char * 32),
        ("chDeviceVersion", c_char * 32),
        ("chManufacturerSpecificInfo", c_char * 48),
        ("chSerialNumber", c_char * 16),
        ("chUserDefinedName", c_char * 16),
        ("nNetExport", c_uint),
        ("nReserved", c_uint * 4),
    ]


class MV_USB3_DEVICE_INFO(Structure):  # noqa: N801
    """
    USB3 Vision device information.
    USB3 Vision 设备信息。

    Matches the ``MV_USB3_DEVICE_INFO`` struct in the SDK header
    ``CameraParams.h``.
    对应 SDK 头文件 ``CameraParams.h`` 中的 ``MV_USB3_DEVICE_INFO`` 结构体。
    """

    _fields_ = [
        ("CrtlInEndPoint", c_uint8),
        ("CrtlOutEndPoint", c_uint8),
        ("StreamEndPoint", c_uint8),
        ("EventEndPoint", c_uint8),
        ("idVendor", c_uint16),
        ("idProduct", c_uint16),
        ("nDeviceNumber", c_uint),
        ("chDeviceGUID", c_char * _MV_USB3_DEVICE_INFO_MAX_STR_LEN),
        ("chVendorName", c_char * _MV_USB3_DEVICE_INFO_MAX_STR_LEN),
        ("chModelName", c_char * _MV_USB3_DEVICE_INFO_MAX_STR_LEN),
        ("chFamilyName", c_char * _MV_USB3_DEVICE_INFO_MAX_STR_LEN),
        ("chDeviceVersion", c_char * _MV_USB3_DEVICE_INFO_MAX_STR_LEN),
        ("chManufacturerName", c_char * _MV_USB3_DEVICE_INFO_MAX_STR_LEN),
        ("chSerialNumber", c_char * _MV_USB3_DEVICE_INFO_MAX_STR_LEN),
        ("chUserDefinedName", c_char * _MV_USB3_DEVICE_INFO_MAX_STR_LEN),
        ("nbcdUSB", c_uint),
        ("nDeviceAddress", c_uint),
        ("nReserved", c_uint * 2),
    ]


class _MV_DEVICE_INFO_UNION(ctypes.Union):  # noqa: N801
    _fields_ = [
        ("stGigEInfo", MV_GIGE_DEVICE_INFO),
        ("stUsb3VInfo", MV_USB3_DEVICE_INFO),
        ("nReserved", c_uint * 60),
    ]


class MV_CC_DEVICE_INFO(Structure):  # noqa: N801
    """
    Top-level device information structure.
    顶层设备信息结构体。
    """

    MV_GIGE_DEVICE = 1
    MV_USB_DEVICE = 4
    MV_CAMERALINK_DEVICE = 8

    _fields_ = [
        ("nMajorVer", c_uint16),
        ("nMinorVer", c_uint16),
        ("nMacAddrHigh", c_uint),
        ("nMacAddrLow", c_uint),
        ("nTLayerType", c_uint),
        ("nDevTypeInfo", c_uint),
        ("nReserved", c_uint * 3),
        ("SpecialInfo", _MV_DEVICE_INFO_UNION),
    ]


class MV_CC_DEVICE_INFO_LIST(Structure):  # noqa: N801
    """
    List of device information pointers returned by MV_CC_EnumDevices.
    MV_CC_EnumDevices 返回的设备信息指针列表。
    """

    _fields_ = [
        ("nDeviceNum", c_uint),
        ("pDeviceInfo", POINTER(MV_CC_DEVICE_INFO) * _MAX_DEVICE_NUM),
    ]


class MV_FRAME_OUT_INFO_EX(Structure):  # noqa: N801
    """
    Per-frame metadata returned with each captured frame.
    随每帧返回的帧元数据。

    Matches the ``MV_FRAME_OUT_INFO_EX`` struct in the SDK header
    ``CameraParams.h``.  The struct includes chunk/watermark fields
    between ``nFrameLen`` and ``nLostPacket`` that must be present to
    keep the correct memory layout.
    对应 SDK 头文件 ``CameraParams.h`` 中的 ``MV_FRAME_OUT_INFO_EX`` 结构体。
    该结构体在 ``nFrameLen`` 和 ``nLostPacket`` 之间包含 chunk/水印字段，
    必须保留以维持正确的内存布局。
    """

    _fields_ = [
        ("nWidth", c_uint16),
        ("nHeight", c_uint16),
        ("enPixelType", c_uint),          # PixelType_Gvsp_* / 像素类型
        ("nFrameNum", c_uint),
        ("nDevTimeStampHigh", c_uint),
        ("nDevTimeStampLow", c_uint),
        ("nReserved0", c_uint),           # padding for 8-byte alignment / 8 字节对齐填充
        ("nHostTimeStamp", c_int64),
        ("nFrameLen", c_uint),
        # ---- chunk watermark fields / chunk 水印字段 ----
        ("nSecondCount", c_uint),
        ("nCycleCount", c_uint),
        ("nCycleOffset", c_uint),
        ("fGain", c_float),
        ("fExposureTime", c_float),
        ("nAverageBrightness", c_uint),
        # white balance / 白平衡
        ("nRed", c_uint),
        ("nGreen", c_uint),
        ("nBlue", c_uint),
        ("nFrameCounter", c_uint),
        ("nTriggerIndex", c_uint),
        # input / output / 输入 / 输出
        ("nInput", c_uint),
        ("nOutput", c_uint),
        # ROI region / ROI 区域
        ("nOffsetX", c_uint16),
        ("nOffsetY", c_uint16),
        ("nChunkWidth", c_uint16),
        ("nChunkHeight", c_uint16),
        # ---- end of chunk fields / chunk 字段结束 ----
        ("nLostPacket", c_uint),
        ("nUnparsedChunkNum", c_uint),
        # SDK union: MV_CHUNK_DATA_CONTENT* | int64 (alignment padding).
        # SDK 联合体：MV_CHUNK_DATA_CONTENT* | int64（对齐填充）。
        # We use c_void_p (pointer-sized) which matches on both 32- and 64-bit.
        # 此处使用 c_void_p（指针大小），在 32 位和 64 位平台均兼容。
        ("UnparsedChunkList", c_void_p),
        ("nReserved", c_uint * 36),
    ]


class MV_FRAME_OUT(Structure):  # noqa: N801
    """
    Output structure from MV_CC_GetImageBuffer.
    MV_CC_GetImageBuffer 的输出结构体。
    """

    _fields_ = [
        ("pBufAddr", POINTER(c_ubyte)),
        ("stFrameInfo", MV_FRAME_OUT_INFO_EX),
        ("nRes", c_uint * 16),
    ]


class MVCC_INTVALUE_EX(Structure):  # noqa: N801
    """
    Integer parameter value with min/max/increment metadata.
    整型参数值，包含最小值/最大值/步进元数据。
    """

    _fields_ = [
        ("nCurValue", c_int64),
        ("nMax", c_int64),
        ("nMin", c_int64),
        ("nInc", c_int64),
        ("nReserved", c_uint * 16),
    ]


class MVCC_FLOATVALUE(Structure):  # noqa: N801
    """
    Float parameter value with min/max metadata.
    浮点参数值，包含最小值/最大值元数据。
    """

    _fields_ = [
        ("fCurValue", c_float),
        ("fMax", c_float),
        ("fMin", c_float),
        ("nReserved", c_uint * 4),
    ]


class MVCC_ENUMVALUE(Structure):  # noqa: N801
    """
    Enum parameter value with supported entries.
    枚举参数值，包含支持的枚举项。
    """

    _fields_ = [
        ("nCurValue", c_uint),
        ("nSupportedNum", c_uint),
        ("nSupportValue", c_uint * 64),
        ("nReserved", c_uint * 4),
    ]


class MVCC_STRINGVALUE(Structure):  # noqa: N801
    """
    String parameter value.
    字符串参数值。
    """

    _fields_ = [
        ("chCurValue", c_char * _MV_MAX_XML_STRVALUE_STRLEN),
        ("nMaxLength", c_int64),
        ("nReserved", c_uint * 2),
    ]


class MV_CC_PIXEL_CONVERT_PARAM_EX(Structure):  # noqa: N801
    """
    Parameter block for MV_CC_ConvertPixelTypeEx.
    MV_CC_ConvertPixelTypeEx 的参数块。

    Matches the ``MV_CC_PIXEL_CONVERT_PARAM_EX`` struct in the SDK.
    对应 SDK 中的 ``MV_CC_PIXEL_CONVERT_PARAM_EX`` 结构体。
    Note: the SDK field order is ``nDstLen`` *before* ``nDstBufferSize``.
    注意：SDK 中 ``nDstLen`` 在 ``nDstBufferSize`` *之前*。
    """

    _fields_ = [
        ("nWidth", c_uint),
        ("nHeight", c_uint),
        ("enSrcPixelType", c_uint),
        ("pSrcData", POINTER(c_ubyte)),
        ("nSrcDataLen", c_uint),
        ("enDstPixelType", c_uint),
        ("pDstBuffer", POINTER(c_ubyte)),
        ("nDstLen", c_uint),
        ("nDstBufferSize", c_uint),
        ("nReserved", c_uint * 4),
    ]


# Backward-compatible alias for the old struct name
# 旧结构体名称的向后兼容别名
MV_PIXEL_CONVERT_PARAM = MV_CC_PIXEL_CONVERT_PARAM_EX


# ---------------------------------------------------------------------------
# Callback type / 回调类型
# ---------------------------------------------------------------------------

IMAGE_CALLBACK = ctypes.CFUNCTYPE(
    None,
    POINTER(c_ubyte),       # pData
    POINTER(MV_FRAME_OUT_INFO_EX),  # pFrameInfo
    c_void_p,               # pUser
)

# ---------------------------------------------------------------------------
# SDK library loading / SDK 库加载
# ---------------------------------------------------------------------------

_LIB_PATHS_LINUX = [
    "/opt/MVS/lib/64/libMvCameraControl.so",
    "/opt/MVS/lib/32/libMvCameraControl.so",
    "/usr/lib/libMvCameraControl.so",
]

_LIB_PATHS_WINDOWS = [
    # Current SDK (v4.x) installs into Common Files
    # 当前 SDK（v4.x）安装至 Common Files
    r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64\MvCameraControl.dll",
    r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win32_i86\MvCameraControl.dll",
    # Legacy SDK paths (v3.x and earlier)
    # 旧版 SDK 路径（v3.x 及更早版本）
    r"C:\Program Files (x86)\MVS\Runtime\Win64_x64\MvCameraControl.dll",
    r"C:\Program Files\MVS\Runtime\Win64_x64\MvCameraControl.dll",
    r"C:\Program Files (x86)\MVS\Runtime\Win32_i86\MvCameraControl.dll",
]


def _find_library() -> str:
    """
    Search the file system for the Hikvision MVS SDK shared library.
    在文件系统中搜索海康威视 MVS SDK 共享库。

    Returns / 返回
    --------------
    str
        Absolute path to the shared library.
        共享库的绝对路径。

    Raises / 异常
    -------------
    SDKNotFoundError
        When the library cannot be found.
        当无法找到库时抛出。
    """
    system = platform.system()

    # 1. Honour explicit override via environment variable
    # 1. 优先使用环境变量覆盖
    env_path = os.environ.get("HIKCAMERA_SDK_PATH")
    if env_path:
        if os.path.isfile(env_path):
            return env_path
        raise SDKNotFoundError(
            f"HIKCAMERA_SDK_PATH={env_path!r} is set but the file does not exist."
        )

    # 2. Platform-specific search paths
    # 2. 平台特定搜索路径
    candidates: list[str]
    if system == "Linux":
        candidates = _LIB_PATHS_LINUX
    elif system == "Windows":
        candidates = _LIB_PATHS_WINDOWS
    else:
        candidates = []

    for path in candidates:
        if os.path.isfile(path):
            return path

    # 3. Fall back to ctypes.util
    # 3. 回退到 ctypes.util 查找
    name = ctypes.util.find_library("MvCameraControl")
    if name:
        return name

    raise SDKNotFoundError(
        "Hikvision MVS SDK shared library not found. "
        "Install the MVS SDK from "
        "https://www.hikrobotics.com/cn/machinevision/service/download/?module=0 "
        "or set the HIKCAMERA_SDK_PATH environment variable to the library path."
    )


def load_sdk() -> ctypes.CDLL:
    """
    Load and return the Hikvision MVS SDK shared library.
    加载并返回海康威视 MVS SDK 共享库。

    The library is loaded once and cached for subsequent calls.
    On first load, ``MV_CC_Initialize`` is called automatically.
    库仅加载一次，后续调用使用缓存。
    首次加载时，会自动调用 ``MV_CC_Initialize``。

    Returns / 返回
    --------------
    ctypes.CDLL
        Loaded SDK library handle.
        加载后的 SDK 库句柄。

    Raises / 异常
    -------------
    SDKNotFoundError
        When the library cannot be found or loaded.
        当无法找到或加载库时抛出。
    """
    global _sdk_lib  # noqa: PLW0603
    if _sdk_lib is not None:
        return _sdk_lib

    path = _find_library()
    try:
        _sdk_lib = ctypes.CDLL(path)
    except OSError as exc:
        raise SDKNotFoundError(f"Failed to load SDK library from {path!r}: {exc}") from exc

    _configure_sdk_argtypes(_sdk_lib)

    # Initialize the SDK (required since SDK v4.x)
    # 初始化 SDK（SDK v4.x 起必须调用）
    init_fn = getattr(_sdk_lib, "MV_CC_Initialize", None)
    if init_fn is not None:
        init_fn()

    return _sdk_lib


def finalize_sdk() -> None:
    """
    Finalize the Hikvision MVS SDK and release global resources.
    终止海康威视 MVS SDK 并释放全局资源。

    Should be called before program exit when the SDK is no longer needed.
    It is safe to call this function even if :py:func:`load_sdk` was never
    called or the library is not available.
    当不再需要 SDK 时，应在程序退出前调用。
    即使从未调用过 :py:func:`load_sdk` 或库不可用，调用本函数也是安全的。
    """
    global _sdk_lib  # noqa: PLW0603
    if _sdk_lib is None:
        return
    finalize_fn = getattr(_sdk_lib, "MV_CC_Finalize", None)
    if finalize_fn is not None:
        finalize_fn()
    _sdk_lib = None


_sdk_lib: ctypes.CDLL | None = None


def _configure_sdk_argtypes(lib: ctypes.CDLL) -> None:  # noqa: PLR0915
    """
    Set ``argtypes`` and ``restype`` for every SDK function used by this library.
    为本库使用的每个 SDK 函数设置 ``argtypes`` 和 ``restype``。

    Configuring the types prevents ctypes from silently truncating 64-bit
    pointer arguments on some platforms.
    配置类型可防止 ctypes 在某些平台上静默截断 64 位指针参数。
    """

    def _set(name: str, argtypes: list, restype=c_int) -> None:  # type: ignore[assignment]
        func = getattr(lib, name, None)
        if func is not None:
            func.argtypes = argtypes
            func.restype = restype

    # SDK initialization / SDK 初始化
    _set("MV_CC_Initialize", [])
    _set("MV_CC_Finalize", [])

    # Enumeration / 设备枚举
    _set("MV_CC_EnumDevices", [c_uint, POINTER(MV_CC_DEVICE_INFO_LIST)])
    _set("MV_CC_EnumDevicesEx", [c_uint, POINTER(MV_CC_DEVICE_INFO_LIST), c_void_p])

    # Handle lifecycle / 句柄生命周期
    _set("MV_CC_CreateHandle", [POINTER(c_void_p), POINTER(MV_CC_DEVICE_INFO)])
    _set("MV_CC_DestroyHandle", [c_void_p])

    # Open / close / 打开 / 关闭
    _set("MV_CC_OpenDevice", [c_void_p, c_uint, c_uint16])
    _set("MV_CC_CloseDevice", [c_void_p])
    _set("MV_CC_IsDeviceConnected", [c_void_p], c_uint)

    # Grabbing / 取帧
    _set("MV_CC_StartGrabbing", [c_void_p])
    _set("MV_CC_StopGrabbing", [c_void_p])
    _set("MV_CC_GetImageBuffer", [c_void_p, POINTER(MV_FRAME_OUT), c_uint])
    _set("MV_CC_FreeImageBuffer", [c_void_p, POINTER(MV_FRAME_OUT)])
    _set(
        "MV_CC_GetOneFrameTimeout",
        [c_void_p, POINTER(c_ubyte), c_uint, POINTER(MV_FRAME_OUT_INFO_EX), c_uint],
    )
    _set(
        "MV_CC_RegisterImageCallBackEx",
        [c_void_p, IMAGE_CALLBACK, c_void_p],
    )

    # Integer parameters / 整型参数
    _set("MV_CC_GetIntValueEx", [c_void_p, ctypes.c_char_p, POINTER(MVCC_INTVALUE_EX)])
    _set("MV_CC_SetIntValueEx", [c_void_p, ctypes.c_char_p, c_int64])

    # Float parameters / 浮点参数
    _set("MV_CC_GetFloatValue", [c_void_p, ctypes.c_char_p, POINTER(MVCC_FLOATVALUE)])
    _set("MV_CC_SetFloatValue", [c_void_p, ctypes.c_char_p, c_float])

    # Bool parameters / 布尔参数
    _set("MV_CC_GetBoolValue", [c_void_p, ctypes.c_char_p, POINTER(c_uint)])
    _set("MV_CC_SetBoolValue", [c_void_p, ctypes.c_char_p, c_uint])

    # Enum parameters / 枚举参数
    _set("MV_CC_GetEnumValue", [c_void_p, ctypes.c_char_p, POINTER(MVCC_ENUMVALUE)])
    _set("MV_CC_SetEnumValue", [c_void_p, ctypes.c_char_p, c_uint])
    _set("MV_CC_SetEnumValueByString", [c_void_p, ctypes.c_char_p, ctypes.c_char_p])

    # String parameters / 字符串参数
    _set("MV_CC_GetStringValue", [c_void_p, ctypes.c_char_p, POINTER(MVCC_STRINGVALUE)])
    _set("MV_CC_SetStringValue", [c_void_p, ctypes.c_char_p, ctypes.c_char_p])

    # Command execution / 命令执行
    _set("MV_CC_SetCommandValue", [c_void_p, ctypes.c_char_p])

    # Pixel conversion / 像素转换
    _set("MV_CC_ConvertPixelTypeEx", [c_void_p, POINTER(MV_CC_PIXEL_CONVERT_PARAM_EX)])

    # GigE multicast / GigE 组播
    _set("MV_GIGE_SetMulticastIP", [c_void_p, c_uint])

    # GigE optimal packet size / GigE 最优包大小
    _set("MV_CC_GetOptimalPacketSize", [c_void_p])

    # Feature save / load (camera configuration files)
    # 特征保存 / 加载（相机配置文件）
    _set("MV_CC_FeatureSave", [c_void_p, ctypes.c_char_p])
    _set("MV_CC_FeatureLoad", [c_void_p, ctypes.c_char_p])

    # SDK version / SDK 版本
    _set("MV_CC_GetSDKVersion", [], c_uint)
