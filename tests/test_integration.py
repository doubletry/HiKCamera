"""
Integration-style smoke tests.

These tests import the top-level ``hikcamera`` package and verify that the
public API is correctly exported without requiring the SDK or any hardware.
"""

from __future__ import annotations


class TestPublicAPI:
    """Verify that all advertised symbols are importable from the package root."""

    def test_import_hikcamera(self):
        import hikcamera  # noqa: F401

    def test_hik_camera_class(self):
        from hikcamera import HikCamera
        assert callable(HikCamera)

    def test_device_info_class(self):
        from hikcamera import DeviceInfo
        assert callable(DeviceInfo)

    def test_enumerate_cameras_function(self):
        from hikcamera import enumerate_cameras
        assert callable(enumerate_cameras)

    def test_access_mode_enum(self):
        from hikcamera import AccessMode
        assert hasattr(AccessMode, "EXCLUSIVE")
        assert hasattr(AccessMode, "MONITOR")

    def test_transport_layer_enum(self):
        from hikcamera import TransportLayer
        assert hasattr(TransportLayer, "GIGE")
        assert hasattr(TransportLayer, "USB")

    def test_streaming_mode_enum(self):
        from hikcamera import StreamingMode
        assert hasattr(StreamingMode, "UNICAST")
        assert hasattr(StreamingMode, "MULTICAST")

    def test_pixel_format_enum(self):
        from hikcamera import PixelFormat
        assert hasattr(PixelFormat, "MONO8")
        assert hasattr(PixelFormat, "BGR8_PACKED")

    def test_output_format_enum(self):
        from hikcamera import OutputFormat
        assert hasattr(OutputFormat, "BGR8")
        assert hasattr(OutputFormat, "MONO8")

    def test_exceptions_exported(self):
        import hikcamera
        exception_names = [
            "HikCameraError",
            "SDKNotFoundError",
            "SDKInitializationError",
            "CameraNotFoundError",
            "CameraConnectionError",
            "CameraAlreadyOpenError",
            "CameraNotOpenError",
            "GrabbingError",
            "GrabbingNotStartedError",
            "FrameTimeoutError",
            "ParameterError",
            "ParameterNotSupportedError",
            "ParameterReadOnlyError",
            "PixelFormatError",
            "ImageConversionError",
        ]
        for name in exception_names:
            assert hasattr(hikcamera, name), f"Missing: {name}"

    def test_version_attribute(self):
        import hikcamera
        assert hasattr(hikcamera, "__version__")
        assert isinstance(hikcamera.__version__, str)


class TestNewFeatures:
    """Verify that newly added features are accessible on the HikCamera class."""

    def test_export_config_method(self):
        from hikcamera import HikCamera
        assert hasattr(HikCamera, "export_config")
        assert callable(getattr(HikCamera, "export_config"))

    def test_import_config_method(self):
        from hikcamera import HikCamera
        assert hasattr(HikCamera, "import_config")
        assert callable(getattr(HikCamera, "import_config"))

    def test_save_user_set_method(self):
        from hikcamera import HikCamera
        assert hasattr(HikCamera, "save_user_set")
        assert callable(getattr(HikCamera, "save_user_set"))

    def test_load_user_set_method(self):
        from hikcamera import HikCamera
        assert hasattr(HikCamera, "load_user_set")
        assert callable(getattr(HikCamera, "load_user_set"))

    def test_get_camera_info_method(self):
        from hikcamera import HikCamera
        assert hasattr(HikCamera, "get_camera_info")
        assert callable(getattr(HikCamera, "get_camera_info"))
