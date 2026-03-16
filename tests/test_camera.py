"""
Tests for hikcamera.camera (HikCamera class) using mocked SDK.
"""

from __future__ import annotations

import ctypes
from ctypes import c_ubyte, c_void_p
from unittest.mock import patch

import numpy as np
import pytest

from hikcamera.camera import DeviceInfo, HikCamera, _frame_info_to_dict, _int_to_ip, _ip_to_int
from hikcamera.enums import AccessMode, MvErrorCode, OutputFormat, PixelFormat, StreamingMode
from hikcamera.exceptions import (
    CameraAlreadyOpenError,
    CameraConnectionError,
    CameraNotFoundError,
    CameraNotOpenError,
    FrameTimeoutError,
    GrabbingNotStartedError,
    ParameterNotSupportedError,
    ParameterReadOnlyError,
)
from hikcamera.sdk_wrapper import (
    MV_CC_DEVICE_INFO,
)
from tests.conftest import make_device_info_list, make_frame_info, make_gige_device_info

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_camera_with_sdk(mock_sdk, open_it: bool = True) -> HikCamera:
    """Create a HikCamera backed by mock_sdk, optionally already opened."""
    import threading
    cam = HikCamera.__new__(HikCamera)
    cam._sdk = mock_sdk
    cam._handle = c_void_p(0x1234)
    dev = make_gige_device_info()
    cam._device_info = dev
    cam._is_open = False
    cam._is_grabbing = False
    cam._frame_buffer = None
    cam._frame_buffer_size = 0
    cam._callback_ref = None
    cam._user_callback = None
    cam._output_format_for_callback = OutputFormat.BGR8
    cam._lock = threading.Lock()
    if open_it:
        cam._is_open = True
    return cam


# ---------------------------------------------------------------------------
# DeviceInfo tests
# ---------------------------------------------------------------------------

class TestDeviceInfo:
    def test_gige_fields(self, gige_device):
        info = DeviceInfo(gige_device)
        assert info.ip == "192.168.1.100"
        assert info.serial_number == "SN123456"
        assert info.model_name == "MV-CA013-20UC"
        assert info.user_defined_name == "TestCam"
        assert info.transport_layer == MV_CC_DEVICE_INFO.MV_GIGE_DEVICE

    def test_mac_address_format(self, gige_device):
        info = DeviceInfo(gige_device)
        parts = info.mac_address.split(":")
        assert len(parts) == 6
        for part in parts:
            assert len(part) == 2

    def test_repr(self, gige_device):
        info = DeviceInfo(gige_device)
        r = repr(info)
        assert "DeviceInfo" in r
        assert "MV-CA013-20UC" in r


# ---------------------------------------------------------------------------
# enumerate tests
# ---------------------------------------------------------------------------

class TestEnumerate:
    def test_enumerate_returns_list(self, mock_sdk):
        dev = make_gige_device_info()
        _ = make_device_info_list(dev)

        def side_effect(transport, p_list):
            p_list._obj.nDeviceNum = 1
            p_list._obj.pDeviceInfo[0] = ctypes.pointer(dev)
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_EnumDevices.side_effect = side_effect

        with patch("hikcamera.camera.load_sdk", return_value=mock_sdk):
            devices = HikCamera.enumerate()

        assert len(devices) == 1
        assert devices[0].serial_number == "SN123456"

    def test_enumerate_empty(self, mock_sdk):
        def side_effect(transport, p_list):
            p_list._obj.nDeviceNum = 0
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_EnumDevices.side_effect = side_effect

        with patch("hikcamera.camera.load_sdk", return_value=mock_sdk):
            devices = HikCamera.enumerate()

        assert devices == []


# ---------------------------------------------------------------------------
# from_ip / from_serial_number
# ---------------------------------------------------------------------------

class TestFromIpAndSN:
    def _patch_enumerate(self, mock_sdk, devices):
        devs = [d._raw if isinstance(d, DeviceInfo) else d for d in devices]

        def side_effect(transport, p_list):
            p_list._obj.nDeviceNum = len(devs)
            for i, d in enumerate(devs):
                p_list._obj.pDeviceInfo[i] = ctypes.pointer(d)
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_EnumDevices.side_effect = side_effect

    def test_from_ip_found(self, mock_sdk):
        dev = make_gige_device_info(ip=0xC0A80164)  # 192.168.1.100
        self._patch_enumerate(mock_sdk, [dev])
        mock_sdk.MV_CC_CreateHandle.return_value = MvErrorCode.MV_OK

        with patch("hikcamera.camera.load_sdk", return_value=mock_sdk):
            cam = HikCamera.from_ip("192.168.1.100")
        assert cam is not None

    def test_from_ip_not_found(self, mock_sdk):
        dev = make_gige_device_info(ip=0xC0A80164)
        self._patch_enumerate(mock_sdk, [dev])

        with patch("hikcamera.camera.load_sdk", return_value=mock_sdk):
            with pytest.raises(CameraNotFoundError):
                HikCamera.from_ip("10.0.0.1")

    def test_from_ip_invalid(self, mock_sdk):
        with patch("hikcamera.camera.load_sdk", return_value=mock_sdk):
            with pytest.raises(ValueError):
                HikCamera.from_ip("not-an-ip")

    def test_from_serial_number_found(self, mock_sdk):
        dev = make_gige_device_info(serial=b"ABC9999\x00")
        self._patch_enumerate(mock_sdk, [dev])
        mock_sdk.MV_CC_CreateHandle.return_value = MvErrorCode.MV_OK

        with patch("hikcamera.camera.load_sdk", return_value=mock_sdk):
            cam = HikCamera.from_serial_number("ABC9999")
        assert cam is not None

    def test_from_serial_number_not_found(self, mock_sdk):
        dev = make_gige_device_info(serial=b"ABC9999\x00")
        self._patch_enumerate(mock_sdk, [dev])

        with patch("hikcamera.camera.load_sdk", return_value=mock_sdk):
            with pytest.raises(CameraNotFoundError):
                HikCamera.from_serial_number("XXXXXXXX")


# ---------------------------------------------------------------------------
# Open / close
# ---------------------------------------------------------------------------

class TestOpenClose:
    def test_open_sets_is_open(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        cam.open(AccessMode.EXCLUSIVE)
        assert cam.is_open

    def test_open_already_open_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=True)
        with pytest.raises(CameraAlreadyOpenError):
            cam.open(AccessMode.EXCLUSIVE)

    def test_open_sdk_failure_raises(self, mock_sdk):
        mock_sdk.MV_CC_OpenDevice.return_value = 0x80000000
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraConnectionError):
            cam.open(AccessMode.EXCLUSIVE)

    def test_close_clears_is_open(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=True)
        cam.close()
        assert not cam.is_open

    def test_close_not_open_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.close()

    def test_open_multicast(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        cam.open(
            AccessMode.MONITOR,
            streaming_mode=StreamingMode.MULTICAST,
            multicast_ip="239.0.0.1",
        )
        assert cam.is_open
        mock_sdk.MV_GIGE_SetMulticastIP.assert_called_once()

    def test_open_multicast_missing_ip(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(ValueError, match="multicast_ip"):
            cam.open(AccessMode.MONITOR, streaming_mode=StreamingMode.MULTICAST)

    def test_context_manager(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with cam:
            cam._is_open = True
        assert not cam.is_open


# ---------------------------------------------------------------------------
# Grabbing
# ---------------------------------------------------------------------------

class TestGrabbing:
    def test_start_stop_grabbing(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.start_grabbing()
        assert cam.is_grabbing
        cam.stop_grabbing()
        assert not cam.is_grabbing

    def test_start_grabbing_not_open(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.start_grabbing()

    def test_stop_grabbing_not_started(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        with pytest.raises(GrabbingNotStartedError):
            cam.stop_grabbing()

    def test_start_twice_is_idempotent(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.start_grabbing()
        cam.start_grabbing()  # should not raise
        assert cam.is_grabbing
        cam.stop_grabbing()


# ---------------------------------------------------------------------------
# get_frame (polling)
# ---------------------------------------------------------------------------

class TestGetFrame:
    def _setup_frame(self, mock_sdk, width=64, height=48):
        """Configure mock SDK to return a MONO8 frame."""
        fi = make_frame_info(width, height, int(PixelFormat.MONO8), frame_len=width * height)

        def get_frame_side_effect(handle, p_buf, buf_size, p_frame_info, timeout):
            p_frame_info._obj.nWidth = fi.nWidth
            p_frame_info._obj.nHeight = fi.nHeight
            p_frame_info._obj.enPixelType = fi.enPixelType
            p_frame_info._obj.nFrameNum = fi.nFrameNum
            p_frame_info._obj.nFrameLen = fi.nFrameLen
            # Fill buffer with gradient
            for i in range(min(buf_size, fi.nFrameLen)):
                p_buf[i] = i % 256
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_GetOneFrameTimeout.side_effect = get_frame_side_effect

        # PayloadSize
        def get_int_side_effect(handle, name, p_val):
            if name == b"PayloadSize":
                p_val._obj.nCurValue = width * height
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_GetIntValueEx.side_effect = get_int_side_effect
        return fi

    def test_get_frame_returns_ndarray(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_frame(mock_sdk, 64, 48)
        cam._is_grabbing = True
        frame = cam.get_frame(timeout_ms=100, output_format=OutputFormat.MONO8)
        assert isinstance(frame, np.ndarray)
        assert frame.shape == (48, 64)

    def test_get_frame_not_open_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.get_frame()

    def test_get_frame_not_grabbing_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        with pytest.raises(GrabbingNotStartedError):
            cam.get_frame()

    def test_get_frame_timeout_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam._is_grabbing = True
        cam._frame_buffer = (c_ubyte * 1024)()
        cam._frame_buffer_size = 1024
        mock_sdk.MV_CC_GetOneFrameTimeout.return_value = MvErrorCode.MV_E_GC_TIMEOUT
        with pytest.raises(FrameTimeoutError):
            cam.get_frame(timeout_ms=100)

    def test_get_frame_ex_returns_tuple(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_frame(mock_sdk, 32, 24)
        cam._is_grabbing = True
        result = cam.get_frame_ex(timeout_ms=100, output_format=OutputFormat.MONO8)
        assert isinstance(result, tuple)
        assert len(result) == 2
        image, meta = result
        assert isinstance(image, np.ndarray)
        assert isinstance(meta, dict)
        assert "frame_num" in meta
        assert "width" in meta


# ---------------------------------------------------------------------------
# Parameter access
# ---------------------------------------------------------------------------

class TestParameters:
    def test_get_int_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)

        def side_effect(handle, name, p_val):
            p_val._obj.nCurValue = 1920
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_GetIntValueEx.side_effect = side_effect
        assert cam.get_int_parameter("Width") == 1920

    def test_set_int_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_int_parameter("Width", 1920)
        mock_sdk.MV_CC_SetIntValueEx.assert_called_once()

    def test_get_float_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)

        def side_effect(handle, name, p_val):
            p_val._obj.fCurValue = 5000.0
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_GetFloatValue.side_effect = side_effect
        assert cam.get_float_parameter("ExposureTime") == pytest.approx(5000.0)

    def test_set_float_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_float_parameter("ExposureTime", 5000.0)
        mock_sdk.MV_CC_SetFloatValue.assert_called_once()

    def test_get_bool_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)

        def side_effect(handle, name, p_val):
            p_val._obj.value = 1
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_GetBoolValue.side_effect = side_effect
        assert cam.get_bool_parameter("AcquisitionFrameRateEnable") is True

    def test_set_bool_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_bool_parameter("AcquisitionFrameRateEnable", True)
        mock_sdk.MV_CC_SetBoolValue.assert_called_once()

    def test_get_enum_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)

        def side_effect(handle, name, p_val):
            p_val._obj.nCurValue = 0x01080001
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_GetEnumValue.side_effect = side_effect
        assert cam.get_enum_parameter("PixelFormat") == 0x01080001

    def test_set_enum_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_enum_parameter("PixelFormat", 0x01080001)
        mock_sdk.MV_CC_SetEnumValue.assert_called_once()

    def test_set_enum_by_string(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_enum_parameter_by_string("PixelFormat", "Mono8")
        mock_sdk.MV_CC_SetEnumValueByString.assert_called_once()

    def test_get_string_parameter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)

        def side_effect(handle, name, p_val):
            p_val._obj.chCurValue = b"Continuous\x00" + b"\x00" * 245
            return MvErrorCode.MV_OK

        mock_sdk.MV_CC_GetStringValue.side_effect = side_effect
        assert cam.get_string_parameter("AcquisitionMode") == "Continuous"

    def test_execute_command(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.execute_command("TriggerSoftware")
        mock_sdk.MV_CC_SetCommandValue.assert_called_once()

    # Error handling

    def test_not_supported_raises_parameter_not_supported(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        mock_sdk.MV_CC_GetIntValueEx.return_value = MvErrorCode.MV_E_SUPPORT
        with pytest.raises(ParameterNotSupportedError):
            cam.get_int_parameter("SomeFeature")

    def test_read_only_raises_parameter_read_only(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        mock_sdk.MV_CC_SetIntValueEx.return_value = MvErrorCode.MV_E_GC_ACCESS
        with pytest.raises(ParameterReadOnlyError):
            cam.set_int_parameter("DeviceLinkSpeed", 999)

    def test_not_open_raises_camera_not_open(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.get_int_parameter("Width")

    def test_set_parameter_auto_dispatch_int(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_parameter("Width", 1280)
        mock_sdk.MV_CC_SetIntValueEx.assert_called()

    def test_set_parameter_auto_dispatch_float(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_parameter("ExposureTime", 5000.0)
        mock_sdk.MV_CC_SetFloatValue.assert_called()

    def test_set_parameter_auto_dispatch_bool(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_parameter("AcquisitionFrameRateEnable", True)
        mock_sdk.MV_CC_SetBoolValue.assert_called()

    def test_set_parameter_silently_ignores_not_supported(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        mock_sdk.MV_CC_SetIntValueEx.return_value = MvErrorCode.MV_E_SUPPORT
        # Should NOT raise
        cam.set_parameter("UnknownFeature", 42)

    def test_get_parameter_returns_default_on_not_supported(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        mock_sdk.MV_CC_GetIntValueEx.return_value = MvErrorCode.MV_E_SUPPORT
        mock_sdk.MV_CC_GetFloatValue.return_value = MvErrorCode.MV_E_SUPPORT
        mock_sdk.MV_CC_GetStringValue.return_value = MvErrorCode.MV_E_SUPPORT
        result = cam.get_parameter("NoSuchFeature", default="fallback")
        assert result == "fallback"


# ---------------------------------------------------------------------------
# Callback mode
# ---------------------------------------------------------------------------

class TestCallback:
    def test_start_grabbing_with_callback_registers(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        frames = []

        def my_callback(image, info):
            frames.append(image)

        cam.start_grabbing(callback=my_callback, output_format=OutputFormat.MONO8)
        assert cam.is_grabbing
        assert cam._user_callback is my_callback
        mock_sdk.MV_CC_RegisterImageCallBackEx.assert_called_once()
        cam.stop_grabbing()

    def test_internal_callback_decodes_frame(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        received = []

        def my_callback(image, info):
            received.append((image, info))

        cam._user_callback = my_callback
        cam._output_format_for_callback = OutputFormat.MONO8

        # Build a fake 8x8 MONO8 frame
        w, h = 8, 8
        buf_data = np.arange(w * h, dtype=np.uint8)
        p_data = buf_data.ctypes.data_as(ctypes.POINTER(c_ubyte))

        fi = make_frame_info(w, h, int(PixelFormat.MONO8), frame_len=w * h)
        p_fi = ctypes.pointer(fi)

        cam._internal_callback(p_data, p_fi, None)

        assert len(received) == 1
        img, meta = received[0]
        assert img.shape == (h, w)
        assert meta["width"] == w
        assert meta["height"] == h


# ---------------------------------------------------------------------------
# IP / integer conversion helpers
# ---------------------------------------------------------------------------

class TestIPHelpers:
    def test_ip_to_int_roundtrip(self):
        ip = "192.168.1.100"
        assert _int_to_ip(_ip_to_int(ip)) == ip

    def test_known_value(self):
        assert _ip_to_int("192.168.1.100") == 0xC0A80164


# ---------------------------------------------------------------------------
# frame_info_to_dict
# ---------------------------------------------------------------------------

class TestFrameInfoToDict:
    def test_keys(self):
        fi = make_frame_info(1920, 1080)
        d = _frame_info_to_dict(fi)
        assert "frame_num" in d
        assert "width" in d
        assert "height" in d
        assert "pixel_format" in d
        assert "frame_length" in d
        assert "timestamp_ns" in d

    def test_values(self):
        fi = make_frame_info(640, 480, frame_num=7)
        d = _frame_info_to_dict(fi)
        assert d["width"] == 640
        assert d["height"] == 480
        assert d["frame_num"] == 7
