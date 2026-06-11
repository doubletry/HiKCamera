"""
Shared pytest fixtures and mock helpers for the HiKCamera test suite.

All tests that exercise camera operations use a mocked SDK to avoid
requiring actual hardware or the Hikvision SDK libraries.
"""

from __future__ import annotations

import ctypes
import os
import socket

# Make sure the src package is importable without installing
import sys
from ctypes import c_void_p
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import hikcamera.camera as camera_module
from hikcamera.camera import GIGE_PACKET_SIZE_JUMBO, HikCamera
from hikcamera.enums import MvErrorCode, OutputFormat
from hikcamera.sdk_wrapper import (
    MV_CC_DEVICE_INFO,
    MV_CC_DEVICE_INFO_LIST,
    MV_FRAME_OUT_INFO_EX,
    MV_GIGE_DEVICE_INFO,
)

# ---------------------------------------------------------------------------
# Real camera configuration / 真实相机配置
# ---------------------------------------------------------------------------

REAL_CAMERA_IP = os.environ.get("HIKCAMERA_TEST_IP", "192.168.1.1")
REAL_CAMERA_SN = os.environ.get("HIKCAMERA_TEST_SN", "DA4860722")


def is_camera_reachable(ip: str = REAL_CAMERA_IP, timeout: float = 2.0) -> bool:
    """
    Check if a camera is reachable via GVCP protocol or ICMP ping.
    通过 GVCP 协议或 ICMP ping 检查相机是否可达。
    
    Tries multiple methods:
    1. TCP connection to GVCP port (3956) - GigE Vision Control Protocol
    2. ICMP ping as fallback
    
    尝试多种方法：
    1. TCP连接到GVCP端口(3956) - GigE Vision控制协议
    2. ICMP ping作为备选方案
    
    Note: Industrial cameras use GVCP/GVSP protocols, not HTTP (port 80).
    注意：工业相机使用GVCP/GVSP协议，不使用HTTP（80端口）。
    """
    # Method 1: Try GVCP port (standard for GigE Vision cameras)
    # 方法1：尝试GVCP端口（GigE Vision相机的标准端口）
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, 3956))  # GVCP port
        sock.close()
        if result == 0:
            return True
    except Exception:
        pass
    
    # Method 2: Fallback to ICMP ping
    # 方法2：ICMP ping作为备选
    try:
        import subprocess
        # Windows ping command
        result = subprocess.run(
            ['ping', '-n', '1', '-w', str(int(timeout * 1000)), ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 1
        )
        return result.returncode == 0
    except Exception:
        return False

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
    cam.use_sdk_decode = True
    cam._is_recording = False

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


# ---------------------------------------------------------------------------
# Real camera fixtures / 真实相机 fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def real_camera_ip() -> str:
    """Return the IP address of the real test camera."""
    return REAL_CAMERA_IP


@pytest.fixture(scope="session")
def real_camera_sn() -> str:
    """Return the serial number of the real test camera."""
    return REAL_CAMERA_SN


@pytest.fixture(scope="session")
def real_camera_available() -> bool:
    """Check if the real camera is available."""
    return is_camera_reachable()


@pytest.fixture(scope="session")
def real_camera_session(real_camera_available: bool, real_camera_ip: str):
    """
    Provide a session-scoped real camera instance for integration tests.
    
    This fixture creates ONE camera instance that is reused across all tests
    in the session to avoid exclusive access conflicts.
    
    提供会话级别的真实相机实例用于集成测试。
    
    此 fixture 创建一个相机实例，在会话中的所有测试中复用以避免独占访问冲突。
    """
    if not real_camera_available:
        pytest.skip(f"Real camera at {real_camera_ip} is not available")
    
    cam = HikCamera.from_ip(real_camera_ip)
    cam.open()
    yield cam
    # Cleanup at the end of session
    try:
        if cam.is_grabbing:
            cam.stop_grabbing()
        cam.close()
    except Exception:
        pass


@pytest.fixture()
def real_camera(real_camera_session: HikCamera):
    """
    Provide the session-scoped camera instance for individual tests.
    
    Tests should NOT close this camera - it's managed by the session fixture.
    
    为单个测试提供会话级别的相机实例。
    
    测试不应关闭此相机 - 它由会话 fixture 管理。
    """
    return real_camera_session


@pytest.fixture()
def real_camera_by_sn(real_camera_session: HikCamera):
    """
    Return the same camera instance (connected by IP, but SN tests can use it).
    
    返回相同的相机实例（通过IP连接，但SN测试可以使用它）。
    """
    return real_camera_session


@pytest.fixture()
def real_camera_closed(real_camera_available: bool, real_camera_ip: str, real_camera_session: HikCamera):
    """
    Provide a real camera instance that is NOT opened.
    Useful for testing open/close behavior.
    
    Note: This temporarily closes the session camera to test close/open scenarios.
    The session camera will be reopened after this fixture completes.
    
    提供未打开的真实相机实例，用于测试打开/关闭行为。
    
    注意：这会临时关闭会话相机以测试关闭/打开场景。
    此 fixture 完成后会重新打开会话相机。
    """
    if not real_camera_available:
        pytest.skip(f"Real camera at {real_camera_ip} is not available")
    
    # Temporarily close session camera to allow new connection tests
    was_grabbing = real_camera_session.is_grabbing
    if was_grabbing:
        real_camera_session.stop_grabbing()
    real_camera_session.close()
    
    try:
        # Create a new instance for testing
        cam = HikCamera.from_ip(real_camera_ip)
        with cam:
            yield cam
    finally:
        # Reopen session camera
        try:
            real_camera_session.open()
            if was_grabbing:
                real_camera_session.start_grabbing()
        except Exception:
            pass
