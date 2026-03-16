"""
Low-level wrapper around the Hikvision MVS SDK dynamic library.

This module locates the shared library at runtime and wraps every C function
used by :py:mod:`hikcamera.camera` via :py:mod:`ctypes`.  Callers should
use the high-level :py:class:`~hikcamera.camera.HikCamera` class instead.

Platform notes
--------------
* **Linux**: ``libMvCameraControl.so``  (installed by the MVS SDK into
  ``/opt/MVS/lib/64/`` or ``/opt/MVS/lib/32/``)
* **Windows**: ``MvCameraControl.dll``  (installed into
  ``C:\\Program Files (x86)\\MVS\\Runtime\\Win64_x64\\``)

The SDK can be downloaded from
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
    c_uint64,
    c_void_p,
)
from typing import TYPE_CHECKING

from .exceptions import SDKNotFoundError

if TYPE_CHECKING:
    pass  # pragma: no cover

# ---------------------------------------------------------------------------
# Type aliases matching the SDK's typedefs
# ---------------------------------------------------------------------------
MV_HANDLE = c_void_p
MV_INT_VALUE = c_int
MV_FLOAT_VALUE = c_float
MV_BOOL_VALUE = c_uint  # MV_BOOL in SDK

# ---------------------------------------------------------------------------
# SDK structs
# ---------------------------------------------------------------------------

_MV_GIGE_DEVICE_INFO_MAX_STR_LEN = 64
_MV_USB3_DEVICE_INFO_MAX_STR_LEN = 64
_MV_MAX_XML_SYMBOL_STRLEN = 64
_MV_MAX_XML_STRVALUE_STRLEN = 256
_MAX_DEVICE_NUM = 256


class MV_GIGE_DEVICE_INFO(Structure):  # noqa: N801
    """GigE device information returned by MV_CC_EnumDevices."""

    _fields_ = [
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
    """USB3 Vision device information."""

    _fields_ = [
        ("CrtlInEndPoint", c_uint8),
        ("CrtlOutEndPoint", c_uint8),
        ("AuxInEndPoint", c_uint8),
        ("AuxOutEndPoint", c_uint8),
        ("chVendorName", c_char * 32),
        ("chModelName", c_char * 32),
        ("chFamilyName", c_char * 32),
        ("chDeviceVersion", c_char * 32),
        ("chManufacturerSpecificInfo", c_char * 48),
        ("chSerialNumber", c_char * 16),
        ("chUserDefinedName", c_char * 16),
        ("DeviceGUID", c_uint64),
        ("DeviceAbility", c_uint),
        ("nReserved", c_uint * 2),
    ]


class _MV_DEVICE_INFO_UNION(ctypes.Union):  # noqa: N801
    _fields_ = [
        ("stGigEInfo", MV_GIGE_DEVICE_INFO),
        ("stUsb3VInfo", MV_USB3_DEVICE_INFO),
        ("nReserved", c_uint * 60),
    ]


class MV_CC_DEVICE_INFO(Structure):  # noqa: N801
    """Top-level device information structure."""

    MV_GIGE_DEVICE = 1
    MV_USB_DEVICE = 4
    MV_CAMERALINK_DEVICE = 8

    _fields_ = [
        ("nMajorVer", c_uint16),
        ("nMinorVer", c_uint16),
        ("nMacAddrHigh", c_uint),
        ("nMacAddrLow", c_uint),
        ("nTLayerType", c_uint),
        ("nReserved", c_uint * 4),
        ("SpecialInfo", _MV_DEVICE_INFO_UNION),
    ]


class MV_CC_DEVICE_INFO_LIST(Structure):  # noqa: N801
    """List of device information pointers returned by MV_CC_EnumDevices."""

    _fields_ = [
        ("nDeviceNum", c_uint),
        ("pDeviceInfo", POINTER(MV_CC_DEVICE_INFO) * _MAX_DEVICE_NUM),
    ]


class MV_FRAME_OUT_INFO_EX(Structure):  # noqa: N801
    """Per-frame metadata returned with each captured frame."""

    _fields_ = [
        ("nWidth", c_uint16),
        ("nHeight", c_uint16),
        ("enPixelType", c_uint),          # PixelType_Gvsp_*
        ("nFrameNum", c_uint),
        ("nDevTimeStampHigh", c_uint),
        ("nDevTimeStampLow", c_uint),
        ("nReserved0", c_uint),
        ("nHostTimeStamp", c_int64),
        ("nFrameLen", c_uint),
        ("nLostPacket", c_uint),
        ("nReserved", c_uint * 2),
    ]


class MV_FRAME_OUT(Structure):  # noqa: N801
    """Output structure from MV_CC_GetImageBuffer."""

    _fields_ = [
        ("pBufAddr", POINTER(c_ubyte)),
        ("stFrameInfo", MV_FRAME_OUT_INFO_EX),
        ("nRes", c_uint * 16),
    ]


class MVCC_INTVALUE_EX(Structure):  # noqa: N801
    """Integer parameter value with min/max/increment metadata."""

    _fields_ = [
        ("nCurValue", c_int64),
        ("nMax", c_int64),
        ("nMin", c_int64),
        ("nInc", c_int64),
        ("nReserved", c_uint * 16),
    ]


class MVCC_FLOATVALUE(Structure):  # noqa: N801
    """Float parameter value with min/max metadata."""

    _fields_ = [
        ("fCurValue", c_float),
        ("fMax", c_float),
        ("fMin", c_float),
        ("nReserved", c_uint * 4),
    ]


class MVCC_ENUMVALUE(Structure):  # noqa: N801
    """Enum parameter value with supported entries."""

    _fields_ = [
        ("nCurValue", c_uint),
        ("nSupportedNum", c_uint),
        ("nSupportValue", c_uint * 64),
        ("nReserved", c_uint * 5),
    ]


class MVCC_STRINGVALUE(Structure):  # noqa: N801
    """String parameter value."""

    _fields_ = [
        ("chCurValue", c_char * _MV_MAX_XML_STRVALUE_STRLEN),
        ("nMaxLength", c_int64),
        ("nReserved", c_uint * 2),
    ]


class MV_PIXEL_CONVERT_PARAM(Structure):  # noqa: N801
    """Parameter block for MV_CC_ConvertPixelType."""

    _fields_ = [
        ("nWidth", c_uint16),
        ("nHeight", c_uint16),
        ("enSrcPixelType", c_uint),
        ("pSrcData", POINTER(c_ubyte)),
        ("nSrcDataLen", c_uint),
        ("enDstPixelType", c_uint),
        ("pDstBuffer", POINTER(c_ubyte)),
        ("nDstBufferSize", c_uint),
        ("nDstLen", c_uint),
        ("nReserved", c_uint * 4),
    ]


# ---------------------------------------------------------------------------
# Callback type
# ---------------------------------------------------------------------------

IMAGE_CALLBACK = ctypes.CFUNCTYPE(
    None,
    POINTER(c_ubyte),       # pData
    POINTER(MV_FRAME_OUT_INFO_EX),  # pFrameInfo
    c_void_p,               # pUser
)

# ---------------------------------------------------------------------------
# SDK library loading
# ---------------------------------------------------------------------------

_LIB_PATHS_LINUX = [
    "/opt/MVS/lib/64/libMvCameraControl.so",
    "/opt/MVS/lib/32/libMvCameraControl.so",
    "/usr/lib/libMvCameraControl.so",
]

_LIB_PATHS_WINDOWS = [
    r"C:\Program Files (x86)\MVS\Runtime\Win64_x64\MvCameraControl.dll",
    r"C:\Program Files\MVS\Runtime\Win64_x64\MvCameraControl.dll",
    r"C:\Program Files (x86)\MVS\Runtime\Win32_i86\MvCameraControl.dll",
]


def _find_library() -> str:
    """
    Search the file system for the Hikvision MVS SDK shared library.

    Returns
    -------
    str
        Absolute path to the shared library.

    Raises
    ------
    SDKNotFoundError
        When the library cannot be found.
    """
    system = platform.system()

    # 1. Honour explicit override via environment variable
    env_path = os.environ.get("HIKCAMERA_SDK_PATH")
    if env_path:
        if os.path.isfile(env_path):
            return env_path
        raise SDKNotFoundError(
            f"HIKCAMERA_SDK_PATH={env_path!r} is set but the file does not exist."
        )

    # 2. Platform-specific search paths
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

    The library is loaded once and cached for subsequent calls.

    Returns
    -------
    ctypes.CDLL
        Loaded SDK library handle.

    Raises
    ------
    SDKNotFoundError
        When the library cannot be found or loaded.
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
    return _sdk_lib


_sdk_lib: ctypes.CDLL | None = None


def _configure_sdk_argtypes(lib: ctypes.CDLL) -> None:  # noqa: PLR0915
    """
    Set ``argtypes`` and ``restype`` for every SDK function used by this library.

    Configuring the types prevents ctypes from silently truncating 64-bit
    pointer arguments on some platforms.
    """

    def _set(name: str, argtypes: list, restype=c_int) -> None:  # type: ignore[assignment]
        func = getattr(lib, name, None)
        if func is not None:
            func.argtypes = argtypes
            func.restype = restype

    # Enumeration
    _set("MV_CC_EnumDevices", [c_uint, POINTER(MV_CC_DEVICE_INFO_LIST)])
    _set("MV_CC_EnumDevicesEx", [c_uint, POINTER(MV_CC_DEVICE_INFO_LIST), c_void_p])

    # Handle lifecycle
    _set("MV_CC_CreateHandle", [POINTER(c_void_p), POINTER(MV_CC_DEVICE_INFO)])
    _set("MV_CC_DestroyHandle", [c_void_p])

    # Open / close
    _set("MV_CC_OpenDevice", [c_void_p, c_uint, c_uint16])
    _set("MV_CC_CloseDevice", [c_void_p])
    _set("MV_CC_IsDeviceConnected", [c_void_p], c_uint)

    # Grabbing
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

    # Integer parameters
    _set("MV_CC_GetIntValueEx", [c_void_p, ctypes.c_char_p, POINTER(MVCC_INTVALUE_EX)])
    _set("MV_CC_SetIntValueEx", [c_void_p, ctypes.c_char_p, c_int64])

    # Float parameters
    _set("MV_CC_GetFloatValue", [c_void_p, ctypes.c_char_p, POINTER(MVCC_FLOATVALUE)])
    _set("MV_CC_SetFloatValue", [c_void_p, ctypes.c_char_p, c_float])

    # Bool parameters
    _set("MV_CC_GetBoolValue", [c_void_p, ctypes.c_char_p, POINTER(c_uint)])
    _set("MV_CC_SetBoolValue", [c_void_p, ctypes.c_char_p, c_uint])

    # Enum parameters
    _set("MV_CC_GetEnumValue", [c_void_p, ctypes.c_char_p, POINTER(MVCC_ENUMVALUE)])
    _set("MV_CC_SetEnumValue", [c_void_p, ctypes.c_char_p, c_uint])
    _set("MV_CC_SetEnumValueByString", [c_void_p, ctypes.c_char_p, ctypes.c_char_p])

    # String parameters
    _set("MV_CC_GetStringValue", [c_void_p, ctypes.c_char_p, POINTER(MVCC_STRINGVALUE)])
    _set("MV_CC_SetStringValue", [c_void_p, ctypes.c_char_p, ctypes.c_char_p])

    # Command execution
    _set("MV_CC_SetCommandValue", [c_void_p, ctypes.c_char_p])

    # Pixel conversion
    _set("MV_CC_ConvertPixelType", [c_void_p, POINTER(MV_PIXEL_CONVERT_PARAM)])

    # GigE multicast
    _set("MV_GIGE_SetMulticastIP", [c_void_p, c_uint])

    # SDK version
    _set("MV_CC_GetSDKVersion", [], c_uint)
