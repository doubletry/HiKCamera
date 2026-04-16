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

    def test_hik_namespace_is_public_enum_entrypoint(self):
        from hikcamera import Hik
        assert hasattr(Hik, "AccessMode")
        assert hasattr(Hik, "TransportLayer")
        assert hasattr(Hik, "StreamingMode")
        assert hasattr(Hik, "PixelFormat")
        assert hasattr(Hik, "OutputFormat")

    def test_individual_enums_are_not_exported_from_package_root(self):
        import hikcamera
        assert not hasattr(hikcamera, "AccessMode")
        assert not hasattr(hikcamera, "TransportLayer")
        assert not hasattr(hikcamera, "StreamingMode")
        assert not hasattr(hikcamera, "PixelFormat")
        assert not hasattr(hikcamera, "OutputFormat")

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
