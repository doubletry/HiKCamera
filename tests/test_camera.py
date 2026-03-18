"""
Tests for hikcamera.camera (HikCamera class) using mocked SDK.
"""

from __future__ import annotations

import ctypes
from ctypes import c_ubyte, c_void_p
from unittest.mock import patch

import numpy as np
import pytest

from hikcamera.camera import (
    GIGE_PACKET_SIZE_DEFAULT,
    GIGE_PACKET_SIZE_JUMBO,
    DeviceInfo,
    HikCamera,
    _frame_info_to_dict,
    _int_to_ip,
    _ip_to_int,
)
from hikcamera.enums import AccessMode, MvErrorCode, OutputFormat, PixelFormat, StreamingMode
from hikcamera.exceptions import (
    CameraAlreadyOpenError,
    CameraConnectionError,
    CameraNotFoundError,
    CameraNotOpenError,
    FrameTimeoutError,
    GrabbingNotStartedError,
    HikCameraError,
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

    def test_open_auto_packet_size(self, mock_sdk):
        """open() with default packet_size=None auto-configures optimal size."""
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        mock_sdk.MV_CC_GetOptimalPacketSize.return_value = GIGE_PACKET_SIZE_JUMBO
        cam.open(AccessMode.EXCLUSIVE)
        assert cam.is_open
        mock_sdk.MV_CC_GetOptimalPacketSize.assert_called_once()
        # Check that SetIntValueEx was called with GevSCPSPacketSize
        calls = mock_sdk.MV_CC_SetIntValueEx.call_args_list
        gev_calls = [c for c in calls if c[0][1] == b"GevSCPSPacketSize"]
        assert len(gev_calls) == 1
        assert gev_calls[0][0][2] == GIGE_PACKET_SIZE_JUMBO

    def test_open_manual_packet_size(self, mock_sdk):
        """open() with explicit packet_size applies the given value."""
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        cam.open(AccessMode.EXCLUSIVE, packet_size=GIGE_PACKET_SIZE_DEFAULT)
        assert cam.is_open
        calls = mock_sdk.MV_CC_SetIntValueEx.call_args_list
        gev_calls = [c for c in calls if c[0][1] == b"GevSCPSPacketSize"]
        assert len(gev_calls) == 1
        assert gev_calls[0][0][2] == GIGE_PACKET_SIZE_DEFAULT
        # GetOptimalPacketSize should NOT be called for manual override
        mock_sdk.MV_CC_GetOptimalPacketSize.assert_not_called()

    def test_open_packet_size_non_gige_silent(self, mock_sdk):
        """open() silently ignores packet size errors for non-GigE cameras."""
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        mock_sdk.MV_CC_GetOptimalPacketSize.return_value = -1
        cam.open(AccessMode.EXCLUSIVE)  # should not raise
        assert cam.is_open


# ---------------------------------------------------------------------------
# GigE Packet Size / GigE 包大小
# ---------------------------------------------------------------------------

class TestPacketSize:
    def test_get_optimal_packet_size(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        mock_sdk.MV_CC_GetOptimalPacketSize.return_value = GIGE_PACKET_SIZE_JUMBO
        assert cam.get_optimal_packet_size() == GIGE_PACKET_SIZE_JUMBO

    def test_get_optimal_packet_size_failure(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        mock_sdk.MV_CC_GetOptimalPacketSize.return_value = -1
        with pytest.raises(HikCameraError, match="MV_CC_GetOptimalPacketSize"):
            cam.get_optimal_packet_size()

    def test_get_optimal_packet_size_not_open(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.get_optimal_packet_size()

    def test_set_packet_size(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_packet_size(GIGE_PACKET_SIZE_JUMBO)
        calls = mock_sdk.MV_CC_SetIntValueEx.call_args_list
        gev_calls = [c for c in calls if c[0][1] == b"GevSCPSPacketSize"]
        assert len(gev_calls) == 1
        assert gev_calls[0][0][2] == GIGE_PACKET_SIZE_JUMBO

    def test_get_packet_size(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)

        def side_effect(handle, name, p_val):
            if name == b"GevSCPSPacketSize":
                p_val._obj.nCurValue = GIGE_PACKET_SIZE_DEFAULT
                return MvErrorCode.MV_OK
            return MvErrorCode.MV_E_SUPPORT

        mock_sdk.MV_CC_GetIntValueEx.side_effect = side_effect
        assert cam.get_packet_size() == GIGE_PACKET_SIZE_DEFAULT

    def test_set_packet_size_not_open(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.set_packet_size(GIGE_PACKET_SIZE_JUMBO)

    def test_get_packet_size_not_open(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.get_packet_size()


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

    def test_set_parameter_auto_dispatch_enum_by_string(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_parameter("GainAuto", "Off")
        mock_sdk.MV_CC_SetEnumValueByString.assert_called()

    def test_set_parameter_string_for_non_enum_goes_to_string_setter(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.set_parameter("DeviceUserID", "MyCam")
        mock_sdk.MV_CC_SetStringValue.assert_called()

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
        # New chunk watermark fields
        assert "gain" in d
        assert "exposure_time" in d
        assert "average_brightness" in d
        assert "red" in d
        assert "green" in d
        assert "blue" in d
        assert "frame_counter" in d
        assert "trigger_index" in d

    def test_values(self):
        fi = make_frame_info(640, 480, frame_num=7)
        d = _frame_info_to_dict(fi)
        assert d["width"] == 640
        assert d["height"] == 480
        assert d["frame_num"] == 7


# ---------------------------------------------------------------------------
# Configuration export / import
# ---------------------------------------------------------------------------

class TestConfigExportImport:
    def test_export_config_calls_feature_save(self, mock_sdk, tmp_path):
        cam = make_camera_with_sdk(mock_sdk)
        out_file = str(tmp_path / "config.xml")
        cam.export_config(out_file)
        mock_sdk.MV_CC_FeatureSave.assert_called_once()

    def test_export_config_not_open_raises(self, mock_sdk, tmp_path):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.export_config(str(tmp_path / "config.xml"))

    def test_export_config_sdk_failure_raises(self, mock_sdk, tmp_path):
        from hikcamera.exceptions import HikCameraError

        cam = make_camera_with_sdk(mock_sdk)
        mock_sdk.MV_CC_FeatureSave.return_value = 0x80000000
        with pytest.raises(HikCameraError):
            cam.export_config(str(tmp_path / "config.xml"))

    def test_import_config_calls_feature_load(self, mock_sdk, tmp_path):
        cam = make_camera_with_sdk(mock_sdk)
        cfg = tmp_path / "config.xml"
        cfg.write_text("<config/>")
        cam.import_config(str(cfg))
        mock_sdk.MV_CC_FeatureLoad.assert_called_once()

    def test_import_config_not_open_raises(self, mock_sdk, tmp_path):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        cfg = tmp_path / "config.xml"
        cfg.write_text("<config/>")
        with pytest.raises(CameraNotOpenError):
            cam.import_config(str(cfg))

    def test_import_config_file_not_found_raises(self, mock_sdk, tmp_path):
        cam = make_camera_with_sdk(mock_sdk)
        with pytest.raises(FileNotFoundError):
            cam.import_config(str(tmp_path / "nonexistent.xml"))

    def test_import_config_sdk_failure_raises(self, mock_sdk, tmp_path):
        from hikcamera.exceptions import HikCameraError

        cam = make_camera_with_sdk(mock_sdk)
        cfg = tmp_path / "config.xml"
        cfg.write_text("<config/>")
        mock_sdk.MV_CC_FeatureLoad.return_value = 0x80000000
        with pytest.raises(HikCameraError):
            cam.import_config(str(cfg))


# ---------------------------------------------------------------------------
# User set save / load
# ---------------------------------------------------------------------------

class TestUserSet:
    def test_save_user_set(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.save_user_set("UserSet1")
        mock_sdk.MV_CC_SetEnumValueByString.assert_called_once()
        mock_sdk.MV_CC_SetCommandValue.assert_called_once()

    def test_save_user_set_default(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.save_user_set()
        # Verify UserSetSelector was set to "UserSet1" (default)
        call_args = mock_sdk.MV_CC_SetEnumValueByString.call_args
        assert call_args[0][1] == b"UserSetSelector"
        assert call_args[0][2] == b"UserSet1"

    def test_save_user_set_not_open_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.save_user_set()

    def test_save_user_set_not_supported_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        mock_sdk.MV_CC_SetEnumValueByString.return_value = MvErrorCode.MV_E_SUPPORT
        with pytest.raises(ParameterNotSupportedError):
            cam.save_user_set("UserSet1")

    def test_load_user_set(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        cam.load_user_set("UserSet2")
        call_args = mock_sdk.MV_CC_SetEnumValueByString.call_args
        assert call_args[0][2] == b"UserSet2"
        mock_sdk.MV_CC_SetCommandValue.assert_called_once()

    def test_load_user_set_not_open_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.load_user_set()


# ---------------------------------------------------------------------------
# Camera info
# ---------------------------------------------------------------------------

class TestCameraInfo:
    def _setup_param_responses(self, mock_sdk):
        """Configure mock SDK to return realistic parameter values."""
        def get_int_side_effect(handle, name, p_val):
            values = {
                b"Width": 1920,
                b"Height": 1080,
                b"OffsetX": 0,
                b"OffsetY": 0,
                b"PayloadSize": 1920 * 1080,
                b"WidthMax": 2048,
                b"HeightMax": 1536,
            }
            if name in values:
                p_val._obj.nCurValue = values[name]
                return MvErrorCode.MV_OK
            return MvErrorCode.MV_E_SUPPORT

        def get_float_side_effect(handle, name, p_val):
            values = {
                b"ExposureTime": 5000.0,
                b"Gain": 1.5,
                b"AcquisitionFrameRate": 30.0,
                b"ResultingFrameRate": 29.97,
                b"Gamma": 1.0,
            }
            if name in values:
                p_val._obj.fCurValue = values[name]
                return MvErrorCode.MV_OK
            return MvErrorCode.MV_E_SUPPORT

        def get_bool_side_effect(handle, name, p_val):
            values = {
                b"AcquisitionFrameRateEnable": 1,
                b"GammaEnable": 0,
            }
            if name in values:
                p_val._obj.value = values[name]
                return MvErrorCode.MV_OK
            return MvErrorCode.MV_E_SUPPORT

        def get_enum_side_effect(handle, name, p_val):
            values = {
                b"PixelFormat": 0x01080001,  # MONO8
                b"ExposureAuto": 0,
                b"GainAuto": 0,
            }
            if name in values:
                p_val._obj.nCurValue = values[name]
                return MvErrorCode.MV_OK
            return MvErrorCode.MV_E_SUPPORT

        def get_string_side_effect(handle, name, p_val):
            values = {
                b"DeviceModelName": b"MV-CA013-20UC",
                b"DeviceSerialNumber": b"SN123456",
                b"DeviceFirmwareVersion": b"1.0.0",
            }
            if name in values:
                val = values[name]
                p_val._obj.chCurValue = val + b"\x00" * (256 - len(val))
                return MvErrorCode.MV_OK
            return MvErrorCode.MV_E_SUPPORT

        mock_sdk.MV_CC_GetIntValueEx.side_effect = get_int_side_effect
        mock_sdk.MV_CC_GetFloatValue.side_effect = get_float_side_effect
        mock_sdk.MV_CC_GetBoolValue.side_effect = get_bool_side_effect
        mock_sdk.MV_CC_GetEnumValue.side_effect = get_enum_side_effect
        mock_sdk.MV_CC_GetStringValue.side_effect = get_string_side_effect

    def test_get_camera_info_returns_dict(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_param_responses(mock_sdk)
        info = cam.get_camera_info()
        assert isinstance(info, dict)

    def test_get_camera_info_contains_image_dimensions(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_param_responses(mock_sdk)
        info = cam.get_camera_info()
        assert info["Width"] == 1920
        assert info["Height"] == 1080

    def test_get_camera_info_contains_exposure_and_gain(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_param_responses(mock_sdk)
        info = cam.get_camera_info()
        assert info["ExposureTime"] == pytest.approx(5000.0)
        assert info["Gain"] == pytest.approx(1.5)

    def test_get_camera_info_contains_frame_rate(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_param_responses(mock_sdk)
        info = cam.get_camera_info()
        assert info["AcquisitionFrameRate"] == pytest.approx(30.0)

    def test_get_camera_info_contains_pixel_format(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_param_responses(mock_sdk)
        info = cam.get_camera_info()
        assert info["PixelFormat"] == 0x01080001

    def test_get_camera_info_contains_device_name(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_param_responses(mock_sdk)
        info = cam.get_camera_info()
        assert info["DeviceModelName"] == "MV-CA013-20UC"
        assert info["DeviceSerialNumber"] == "SN123456"

    def test_get_camera_info_skips_unsupported(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        # All calls return "not supported"
        mock_sdk.MV_CC_GetIntValueEx.return_value = MvErrorCode.MV_E_SUPPORT
        mock_sdk.MV_CC_GetFloatValue.return_value = MvErrorCode.MV_E_SUPPORT
        mock_sdk.MV_CC_GetBoolValue.return_value = MvErrorCode.MV_E_SUPPORT
        mock_sdk.MV_CC_GetEnumValue.return_value = MvErrorCode.MV_E_SUPPORT
        mock_sdk.MV_CC_GetStringValue.return_value = MvErrorCode.MV_E_SUPPORT
        info = cam.get_camera_info()
        assert info == {}

    def test_get_camera_info_not_open_raises(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk, open_it=False)
        with pytest.raises(CameraNotOpenError):
            cam.get_camera_info()

    def test_get_camera_info_contains_bool_params(self, mock_sdk):
        cam = make_camera_with_sdk(mock_sdk)
        self._setup_param_responses(mock_sdk)
        info = cam.get_camera_info()
        assert info["AcquisitionFrameRateEnable"] is True
        assert info["GammaEnable"] is False
