"""
Integration tests for real camera connection and enumeration.
真实相机连接和枚举的集成测试。

These tests require a real Hikvision camera to be connected and accessible.
Tests are skipped if the camera is not available.

这些测试需要连接并可访问真实的海康威视相机。
如果相机不可用，测试将被跳过。
"""

from __future__ import annotations

import pytest

from hikcamera import DeviceInfo, Hik, HikCamera
from .conftest import REAL_CAMERA_IP


class TestRealCameraEnumeration:
    """Test camera enumeration with real hardware."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_enumerate_all_cameras(self, real_camera_available: bool):
        """Test enumerating all available cameras."""
        if not real_camera_available:
            pytest.skip("No real camera available")
        
        cameras = HikCamera.enumerate(Hik.TransportLayer.ALL)
        assert isinstance(cameras, list)
        assert len(cameras) > 0, "At least one camera should be found"
        
        # Verify each camera has valid device info
        for cam_info in cameras:
            assert isinstance(cam_info, DeviceInfo)
            assert cam_info.serial_number, "Serial number should not be empty"
            assert cam_info.model_name, "Model name should not be empty"

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_enumerate_gige_only(self, real_camera_available: bool):
        """Test enumerating only GigE cameras."""
        if not real_camera_available:
            pytest.skip("No real camera available")
        
        cameras = HikCamera.enumerate(Hik.TransportLayer.GIGE)
        assert isinstance(cameras, list)
        # All returned cameras should be GigE type
        for cam_info in cameras:
            assert cam_info.transport_layer == Hik.TransportLayer.GIGE

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_device_info_properties(self, real_camera_ip: str, real_camera_available: bool):
        """Test that device info contains expected properties."""
        if not real_camera_available:
            pytest.skip("No real camera available")
        
        cameras = HikCamera.enumerate(Hik.TransportLayer.GIGE)
        target_cam = None
        for cam_info in cameras:
            if cam_info.ip == real_camera_ip:
                target_cam = cam_info
                break
        
        assert target_cam is not None, f"Camera at {real_camera_ip} should be found"
        assert target_cam.ip == real_camera_ip
        assert target_cam.serial_number == "DA4860722"
        assert target_cam.model_name, "Model name should be present"


class TestRealCameraConnection:
    """Test camera connection with real hardware."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_connect_by_ip(self, real_camera: HikCamera, real_camera_ip: str):
        """Test connecting to camera by IP address."""
        assert real_camera is not None
        assert real_camera._is_open
        # Verify the camera info contains expected data
        cam_info = real_camera.get_camera_info()
        assert cam_info is not None

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_connect_by_serial_number(self, real_camera_by_sn: HikCamera):
        """Test connecting to camera by serial number."""
        assert real_camera_by_sn is not None
        assert real_camera_by_sn._is_open
        # Verify serial number from camera info
        cam_info = real_camera_by_sn.get_camera_info()
        assert "DeviceSerialNumber" in cam_info
        assert cam_info["DeviceSerialNumber"] == "DA4860722"

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_connect_exclusive_mode(self, real_camera_closed: HikCamera):
        """Test connecting in exclusive access mode."""
        real_camera_closed.open(Hik.AccessMode.EXCLUSIVE)
        assert real_camera_closed._is_open

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_connect_control_mode(self, real_camera_closed: HikCamera):
        """Test connecting in control access mode."""
        real_camera_closed.open(Hik.AccessMode.CONTROL)
        assert real_camera_closed._is_open

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_connect_monitor_mode(self, real_camera_closed: HikCamera):
        """Test connecting in monitor (read-only) access mode."""
        real_camera_closed.open(Hik.AccessMode.MONITOR)
        assert real_camera_closed._is_open

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_context_manager(self, real_camera_closed: HikCamera):
        """Test using camera with context manager."""
        # real_camera_closed provides a closed camera instance
        # We need to create a fresh instance for context manager test
        ip = REAL_CAMERA_IP
        
        with HikCamera.from_ip(ip) as cam:
            cam.open()
            assert cam._is_open
        # After exiting context, camera should be closed
        assert not cam._is_open

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_double_open_raises_error(self, real_camera: HikCamera):
        """Test that opening an already open camera raises an error."""
        from hikcamera.exceptions import CameraAlreadyOpenError
        
        with pytest.raises(CameraAlreadyOpenError):
            real_camera.open()

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_close_and_reopen(self, real_camera_closed: HikCamera):
        """Test closing and reopening a camera."""
        real_camera_closed.open()
        assert real_camera_closed._is_open
        
        real_camera_closed.close()
        assert not real_camera_closed._is_open
        
        real_camera_closed.open()
        assert real_camera_closed._is_open


class TestRealCameraDeviceInfo:
    """Test camera device information retrieval."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_get_camera_info(self, real_camera: HikCamera):
        """Test retrieving comprehensive camera information."""
        info = real_camera.get_camera_info()
        
        assert info is not None
        assert isinstance(info, dict)
        
        # Check for common parameters
        from hikcamera.params import (
            AcquisitionControl,
            AnalogControl,
            DeviceControl,
            ImageFormatControl,
        )
        
        # These should be present for most cameras
        assert ImageFormatControl.Width in info or info.get(ImageFormatControl.Width) is not None
        assert ImageFormatControl.Height in info or info.get(ImageFormatControl.Height) is not None
        assert DeviceControl.DeviceModelName in info or info.get(DeviceControl.DeviceModelName) is not None

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_device_model_name(self, real_camera: HikCamera):
        """Test retrieving device model name."""
        from hikcamera.params import DeviceControl
        
        model_name = real_camera.params.DeviceControl.DeviceModelName.get()
        assert model_name is not None
        assert isinstance(model_name, str)
        assert len(model_name) > 0

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_device_serial_number(self, real_camera: HikCamera):
        """Test retrieving device serial number."""
        from hikcamera.params import DeviceControl
        
        serial = real_camera.params.DeviceControl.DeviceSerialNumber.get()
        assert serial is not None
        assert isinstance(serial, str)
        assert serial == "DA4860722"

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_image_dimensions(self, real_camera: HikCamera):
        """Test retrieving image dimensions."""
        from hikcamera.params import ImageFormatControl
        
        width = real_camera.params.ImageFormatControl.Width.get()
        height = real_camera.params.ImageFormatControl.Height.get()
        
        assert width is not None
        assert height is not None
        assert isinstance(width, int)
        assert isinstance(height, int)
        assert width > 0
        assert height > 0


class TestRealCameraGigEPacketSize:
    """Test GigE packet size configuration."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_get_optimal_packet_size(self, real_camera: HikCamera):
        """Test getting optimal packet size."""
        packet_size = real_camera.get_optimal_packet_size()
        
        assert packet_size is not None
        assert isinstance(packet_size, int)
        assert packet_size > 0
        # Typical values: 1500 (standard MTU) or 8164+ (jumbo frames)
        assert packet_size >= 1500

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_get_current_packet_size(self, real_camera: HikCamera):
        """Test getting current packet size."""
        packet_size = real_camera.get_packet_size()
        
        assert packet_size is not None
        assert isinstance(packet_size, int)
        assert packet_size > 0

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_set_packet_size(self, real_camera: HikCamera):
        """Test setting packet size manually."""
        from hikcamera import GIGE_PACKET_SIZE_DEFAULT
        
        original_size = real_camera.get_packet_size()
        
        # Set to standard MTU
        real_camera.set_packet_size(GIGE_PACKET_SIZE_DEFAULT)
        new_size = real_camera.get_packet_size()
        assert new_size == GIGE_PACKET_SIZE_DEFAULT
        
        # Restore original size
        real_camera.set_packet_size(original_size)

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_open_with_auto_packet_size(self, real_camera_closed: HikCamera):
        """Test that open() automatically sets optimal packet size."""
        real_camera_closed.open()
        
        packet_size = real_camera_closed.get_packet_size()
        assert packet_size is not None
        assert packet_size >= 1500

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_open_with_manual_packet_size(self, real_camera_closed: HikCamera):
        """Test opening camera with manual packet size."""
        from hikcamera import GIGE_PACKET_SIZE_JUMBO
        
        real_camera_closed.open(packet_size=GIGE_PACKET_SIZE_JUMBO)
        packet_size = real_camera_closed.get_packet_size()
        assert packet_size == GIGE_PACKET_SIZE_JUMBO


class TestRealCameraMulticast:
    """Test multicast streaming mode."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_open_multicast_mode(self, real_camera_closed: HikCamera):
        """Test opening camera in multicast mode."""
        # Note: This test may fail if network doesn't support multicast
        try:
            real_camera_closed.open(
                Hik.AccessMode.MONITOR,
                streaming_mode=Hik.StreamingMode.MULTICAST,
                multicast_ip="239.0.0.1",
            )
            assert real_camera_closed._is_open
        except Exception as e:
            pytest.skip(f"Multicast not supported or configured: {e}")
