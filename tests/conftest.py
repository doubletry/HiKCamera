"""
Shared pytest fixtures and mock helpers for the HiKCamera test suite.

All tests that exercise camera operations use a mocked SDK to avoid
requiring actual hardware or the Hikvision SDK libraries.
"""

from __future__ import annotations

import ctypes

# Make sure the src package is importable without installing
import sys
from ctypes import c_void_p
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import hikcamera.camera as camera_module
from hikcamera.camera import GIGE_PACKET_SIZE_JUMBO
from hikcamera.enums import MvErrorCode
from hikcamera.sdk_wrapper import (
    MV_CC_DEVICE_INFO,
    MV_CC_DEVICE_INFO_LIST,
    MV_FRAME_OUT_INFO_EX,
    MV_GIGE_DEVICE_INFO,
)

# ---------------------------------------------------------------------------
# Helpers to build fake SDK structures
# ---------------------------------------------------------------------------

def make_gige_device_info(
    ip: int = 0xC0A80164,  # 192.168.1.100
    serial: bytes = b"SN123456\x00",
    model: bytes = b"MV-CA013-20UC\x00",
    user_name: bytes = b"TestCam\x00",
) -> MV_CC_DEVICE_INFO:
    """Return a populated ``MV_CC_DEVICE_INFO`` for a GigE camera."""
    dev = MV_CC_DEVICE_INFO()
    dev.nMajorVer = 3
    dev.nMinorVer = 0
    dev.nMacAddrHigh = 0x00E04B01
    dev.nMacAddrLow = 0x23456789
    dev.nTLayerType = MV_CC_DEVICE_INFO.MV_GIGE_DEVICE

    gi = MV_GIGE_DEVICE_INFO()
    gi.nCurrentIp = ip
    gi.chSerialNumber = (serial + b"\x00" * 16)[:16]
    gi.chModelName = (model + b"\x00" * 32)[:32]
    gi.chUserDefinedName = (user_name + b"\x00" * 16)[:16]

    dev.SpecialInfo.stGigEInfo = gi
    return dev


def make_device_info_list(*devices: MV_CC_DEVICE_INFO) -> MV_CC_DEVICE_INFO_LIST:
    """Wrap one or more device structs in an ``MV_CC_DEVICE_INFO_LIST``."""
    lst = MV_CC_DEVICE_INFO_LIST()
    lst.nDeviceNum = len(devices)
    for i, dev in enumerate(devices):
        lst.pDeviceInfo[i] = ctypes.pointer(dev)
    return lst


# ---------------------------------------------------------------------------
# Mock SDK
# ---------------------------------------------------------------------------

class MockSDK:
    """
    A minimal mock of the Hikvision SDK CDLL that records calls and returns
    success (MV_OK = 0) by default.

    Override individual method side effects in tests as needed.
    """

    def __init__(self) -> None:
        self.MV_CC_EnumDevices = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_CreateHandleWithoutLog = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_CreateHandle = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_DestroyHandle = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_OpenDevice = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_CloseDevice = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_IsDeviceConnected = MagicMock(return_value=1)
        self.MV_CC_StartGrabbing = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_StopGrabbing = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_RegisterImageCallBackEx = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_RegisterExceptionCallBack = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_GetOneFrameTimeout = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_GetImageBuffer = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_FreeImageBuffer = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_GetIntValueEx = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_SetIntValueEx = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_GetFloatValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_SetFloatValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_GetBoolValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_SetBoolValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_GetEnumValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_SetEnumValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_SetEnumValueByString = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_GetStringValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_SetStringValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_SetCommandValue = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_ConvertPixelTypeEx = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_GIGE_SetMulticastIP = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_GetOptimalPacketSize = MagicMock(return_value=GIGE_PACKET_SIZE_JUMBO)
        self.MV_CC_GetSDKVersion = MagicMock(return_value=0x03000000)
        self.MV_CC_FeatureSave = MagicMock(return_value=MvErrorCode.MV_OK)
        self.MV_CC_FeatureLoad = MagicMock(return_value=MvErrorCode.MV_OK)


def make_frame_info(
    width: int = 640,
    height: int = 480,
    pixel_format: int = 0x01080001,  # MONO8
    frame_num: int = 1,
    frame_len: int | None = None,
) -> MV_FRAME_OUT_INFO_EX:
    """Build a populated ``MV_FRAME_OUT_INFO_EX``."""
    fi = MV_FRAME_OUT_INFO_EX()
    fi.nWidth = width
    fi.nHeight = height
    fi.enPixelType = pixel_format
    fi.nFrameNum = frame_num
    fi.nFrameLen = frame_len if frame_len is not None else width * height
    fi.nDevTimeStampHigh = 0
    fi.nDevTimeStampLow = 0
    fi.nHostTimeStamp = 0
    fi.nLostPacket = 0
    return fi


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_sdk() -> MockSDK:
    """Return a fresh MockSDK instance."""
    return MockSDK()


@pytest.fixture(autouse=True)
def clear_packet_size_cache():
    """Keep packet-size cache isolated between tests."""
    camera_module._GIGE_PACKET_SIZE_CACHE.clear()
    yield
    camera_module._GIGE_PACKET_SIZE_CACHE.clear()


@pytest.fixture()
def gige_device() -> MV_CC_DEVICE_INFO:
    """Return a single GigE device info struct."""
    return make_gige_device_info()


@pytest.fixture()
def camera_with_mock_sdk(mock_sdk):
    """
    Return an open, non-grabbing ``HikCamera`` instance backed by MockSDK.

    The ``_sdk`` attribute is replaced with *mock_sdk* so no real SDK calls
    are made.
    """
    from hikcamera.camera import HikCamera

    dev = make_gige_device_info()
    dev_info_list = make_device_info_list(dev)

    def _enum_side_effect(transport, p_list):
        p_list._obj.nDeviceNum = dev_info_list.nDeviceNum
        for i in range(dev_info_list.nDeviceNum):
            p_list._obj.pDeviceInfo[i] = dev_info_list.pDeviceInfo[i]
        return MvErrorCode.MV_OK

    mock_sdk.MV_CC_EnumDevices.side_effect = _enum_side_effect

    cam = HikCamera.__new__(HikCamera)
    # Manually initialise so we can inject the mock
    import threading
    cam._sdk = mock_sdk
    cam._handle = c_void_p(None)
    cam._device_info = dev
    cam._is_open = False
    cam._is_grabbing = False
    cam._frame_buffer = None
    cam._frame_buffer_size = 0
    cam._callback_ref = None
    cam._user_callback = None
    from hikcamera.enums import OutputFormat
    cam._output_format_for_callback = OutputFormat.BGR8
    cam._exception_callback_ref = None
    cam._device_exception = None
    cam._on_device_exception = None
    cam._lock = threading.Lock()
    cam._params_proxy = None

    # Simulate CreateHandle setting a non-null handle
    def _create_handle(p_handle, p_dev_info):
        p_handle._obj.value = 0x1234ABCD
        return MvErrorCode.MV_OK

    mock_sdk.MV_CC_CreateHandleWithoutLog.side_effect = _create_handle
    mock_sdk.MV_CC_CreateHandle.side_effect = _create_handle
    mock_sdk.MV_CC_OpenDevice.return_value = MvErrorCode.MV_OK

    # Open the camera
    cam._is_open = True  # skip real open for fixture simplicity
    return cam
