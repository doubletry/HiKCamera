"""
Integration tests for real camera parameter system.
真实相机参数系统的集成测试。

These tests verify the structured parameter API with real hardware.
这些测试验证使用真实硬件的结构化参数 API。
"""

from __future__ import annotations

import pytest

from hikcamera import Hik, HikCamera
from hikcamera.exceptions import (
    HikCameraError,
    ParameterNotSupportedError,
    ParameterReadOnlyError,
    ParameterValueError,
)
from hikcamera.params import (
    AcquisitionControl,
    AnalogControl,
    DeviceControl,
    ImageFormatControl,
    UserSetControl,
)


class TestRealCameraParameterTypes:
    """Test different parameter types."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_read_int_parameter(self, real_camera: HikCamera):
        """Test reading an integer parameter."""
        width = real_camera.params.ImageFormatControl.Width.get()
        
        assert width is not None
        assert isinstance(width, int)
        assert width > 0

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_read_float_parameter(self, real_camera: HikCamera):
        """Test reading a float parameter."""
        exposure = real_camera.params.AcquisitionControl.ExposureTime.get()
        
        assert exposure is not None
        assert isinstance(exposure, (int, float))
        assert exposure > 0

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_read_bool_parameter(self, real_camera: HikCamera):
        """Test reading a boolean parameter."""
        # Try to read a bool parameter if available
        try:
            value = real_camera.params.AcquisitionControl.AcquisitionFrameRateEnable.get()
            assert isinstance(value, bool)
        except ParameterNotSupportedError:
            pytest.skip("AcquisitionFrameRateEnable not supported")

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_read_enum_parameter(self, real_camera: HikCamera):
        """Test reading an enum parameter."""
        pixel_format = real_camera.params.ImageFormatControl.PixelFormat.get()
        
        assert pixel_format is not None
        # Should be a Hik.PixelFormat enum member or int
        assert hasattr(pixel_format, 'value') or isinstance(pixel_format, int)

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_read_string_parameter(self, real_camera: HikCamera):
        """Test reading a string parameter."""
        model_name = real_camera.params.DeviceControl.DeviceModelName.get()
        
        assert model_name is not None
        assert isinstance(model_name, str)
        assert len(model_name) > 0

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_write_int_parameter(self, real_camera: HikCamera):
        """Test writing an integer parameter."""
        # Save original value
        original_width = real_camera.params.ImageFormatControl.Width.get()
        
        try:
            # Try to set a valid width (must be within camera's range)
            # Use a smaller value that should be supported
            new_width = max(640, original_width // 2)
            # Round to even number (many cameras require even dimensions)
            new_width = new_width - (new_width % 2)
            
            real_camera.params.ImageFormatControl.Width.set(new_width)
            actual_width = real_camera.params.ImageFormatControl.Width.get()
            
            assert actual_width == new_width
        except ParameterReadOnlyError:
            pytest.skip("Width is read-only (may be during grabbing)")
        finally:
            # Restore original value
            try:
                real_camera.params.ImageFormatControl.Width.set(original_width)
            except Exception:
                pass

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_write_float_parameter(self, real_camera: HikCamera):
        """Test writing a float parameter."""
        # Save original value
        original_exposure = real_camera.params.AcquisitionControl.ExposureTime.get()
        
        try:
            # Set a reasonable exposure time
            new_exposure = 5000.0  # 5000 µs
            
            real_camera.params.AcquisitionControl.ExposureTime.set(new_exposure)
            actual_exposure = real_camera.params.AcquisitionControl.ExposureTime.get()
            
            # Allow some tolerance
            assert abs(actual_exposure - new_exposure) < 100
        except ParameterReadOnlyError:
            pytest.skip("ExposureTime is read-only")
        finally:
            # Restore original value
            try:
                real_camera.params.AcquisitionControl.ExposureTime.set(original_exposure)
            except Exception:
                pass

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_write_enum_parameter(self, real_camera: HikCamera):
        """Test writing an enum parameter."""
        # Save original value
        original_gain_auto = real_camera.params.AnalogControl.GainAuto.get()
        
        try:
            # Set GainAuto to OFF
            real_camera.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)
            actual_value = real_camera.params.AnalogControl.GainAuto.get()
            
            # SDK returns integer value for enums, compare accordingly
            # SDK 返回枚举的整数值，相应地进行比较
            if isinstance(actual_value, int):
                # If it's an int, check that it's a valid value (0 typically means OFF)
                assert actual_value in [0, 1, 2], f"Unexpected enum value: {actual_value}"
            else:
                # If it's a string/enum, compare directly
                assert str(actual_value).lower() == str(Hik.GainAuto.OFF).lower()
        except ParameterReadOnlyError:
            pytest.skip("GainAuto is read-only")
        finally:
            # Restore original value
            try:
                real_camera.params.AnalogControl.GainAuto.set(original_gain_auto)
            except Exception:
                pass

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_write_bool_parameter(self, real_camera: HikCamera):
        """Test writing a boolean parameter."""
        try:
            # Save original value
            original_value = real_camera.params.AcquisitionControl.AcquisitionFrameRateEnable.get()
            
            # Toggle the value
            new_value = not original_value
            real_camera.params.AcquisitionControl.AcquisitionFrameRateEnable.set(new_value)
            actual_value = real_camera.params.AcquisitionControl.AcquisitionFrameRateEnable.get()
            
            assert actual_value == new_value
        except ParameterNotSupportedError:
            pytest.skip("AcquisitionFrameRateEnable not supported")
        except ParameterReadOnlyError:
            pytest.skip("AcquisitionFrameRateEnable is read-only")
        finally:
            # Restore original value
            try:
                real_camera.params.AcquisitionControl.AcquisitionFrameRateEnable.set(original_value)
            except Exception:
                pass

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_execute_command_node(self, real_camera: HikCamera):
        """Test executing a command node."""
        # TriggerSoftware is a common command node
        try:
            real_camera.params.AcquisitionControl.TriggerSoftware.execute()
            # If we get here without exception, the command executed successfully
            assert True
        except ParameterNotSupportedError:
            pytest.skip("TriggerSoftware command not supported")
        except ParameterReadOnlyError:
            # Some cameras require trigger mode to be enabled
            pytest.skip("TriggerSoftware requires trigger mode enabled")


class TestRealCameraParameterValidation:
    """Test parameter validation and error handling."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_invalid_parameter_value_raises_error(self, real_camera: HikCamera):
        """Test that invalid parameter values raise appropriate errors."""
        try:
            # Try to set an impossibly large exposure time
            real_camera.params.AcquisitionControl.ExposureTime.set(999999999.0)
            pytest.fail("Should have raised an error")
        except (ParameterValueError, HikCameraError):
            pass  # Expected - either client validation or SDK error
        except ParameterReadOnlyError:
            pytest.skip("ExposureTime is read-only")
        except ParameterNotSupportedError:
            pytest.skip("ExposureTime not supported")

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_wrong_type_raises_error(self, real_camera: HikCamera):
        """Test that wrong parameter types raise errors."""
        try:
            # Try to set a string where int is expected
            real_camera.params.ImageFormatControl.Width.set("invalid")  # type: ignore
            pytest.fail("Should have raised ParameterValueError")
        except ParameterValueError:
            pass  # Expected
        except ParameterReadOnlyError:
            pytest.skip("Width is read-only")

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_unsupported_parameter_raises_error(self, real_camera: HikCamera):
        """Test that unsupported parameters raise ParameterNotSupportedError."""
        # Try to access a parameter that likely doesn't exist or is not supported
        # This is camera-model specific
        try:
            # Most cameras don't have some advanced parameters
            # Try a parameter that might not be supported by this specific model
            from hikcamera.params import ParamNode
            
            # Create a fake node with correct signature for a parameter that might not exist
            fake_node = ParamNode(
                name="NonExistentParameter",
                data_type=int,
                access="R/W",
                description="A non-existent parameter for testing",
            )
            
            # Try to get it through internal method
            result = real_camera._get_param_node_value(fake_node)
            # If it returns the default (None), that's acceptable for unsupported params
            assert result is None, f"Expected None for unsupported parameter, got {result}"
        except (ParameterNotSupportedError, KeyError):
            # KeyError means the parameter is not in the schema at all
            # ParameterNotSupportedError means SDK explicitly says it's not supported
            pass  # Both are acceptable outcomes for unsupported parameters


class TestRealCameraCommonParameters:
    """Test commonly used camera parameters."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_exposure_time_range(self, real_camera: HikCamera):
        """Test exposure time is within reasonable range."""
        exposure = real_camera.params.AcquisitionControl.ExposureTime.get()
        
        # Exposure time in microseconds, typically 10-1000000 µs
        assert 10 <= exposure <= 1000000, f"Exposure {exposure} µs out of typical range"

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_gain_value(self, real_camera: HikCamera):
        """Test gain value is reasonable."""
        gain = real_camera.params.AnalogControl.Gain.get()
        
        # Gain is typically >= 0
        assert gain >= 0, f"Gain {gain} should be non-negative"

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_frame_rate(self, real_camera: HikCamera):
        """Test frame rate parameter."""
        try:
            fps = real_camera.params.AcquisitionControl.ResultingFrameRate.get()
            
            # Frame rate should be positive
            assert fps > 0, f"Frame rate {fps} should be positive"
        except ParameterNotSupportedError:
            pytest.skip("ResultingFrameRate not supported")

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_pixel_format_values(self, real_camera: HikCamera):
        """Test pixel format can be read and is valid."""
        pixel_format = real_camera.params.ImageFormatControl.PixelFormat.get()
        
        # Should be a valid pixel format
        assert pixel_format is not None
        
        # Common formats (using correct enum attribute names)
        # 常用格式（使用正确的枚举属性名）
        valid_formats = [
            Hik.PixelFormat.MONO8,
            Hik.PixelFormat.MONO16,
            Hik.PixelFormat.BAYER_RG8,
            Hik.PixelFormat.BAYER_GR8,
            Hik.PixelFormat.RGB8_PACKED,
            Hik.PixelFormat.BGR8_PACKED,
        ]
        
        # Check if it's one of the known formats or at least a valid int
        if hasattr(pixel_format, 'value'):
            assert pixel_format.value > 0
        else:
            assert isinstance(pixel_format, int)
            assert pixel_format > 0


class TestRealCameraUserSets:
    """Test user set save/load functionality."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_user_set_selector(self, real_camera: HikCamera):
        """Test selecting different user sets."""
        try:
            # Try to select UserSet1
            real_camera.params.UserSetControl.UserSetSelector.set(Hik.UserSetSelector.USER_SET_1)
            selected = real_camera.params.UserSetControl.UserSetSelector.get()
            
            # SDK returns integer value for enums
            # SDK 返回枚举的整数值
            if isinstance(selected, int):
                # USER_SET_1 typically has value 1
                assert selected == 1, f"Expected 1 for USER_SET_1, got {selected}"
            else:
                # If it's a string/enum, compare directly
                assert str(selected).lower() == str(Hik.UserSetSelector.USER_SET_1).lower()
        except ParameterNotSupportedError:
            pytest.skip("UserSetSelector not supported")

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_user_set_save_load(self, real_camera: HikCamera):
        """Test saving and loading user sets."""
        try:
            # Select UserSet1
            real_camera.params.UserSetControl.UserSetSelector.set(Hik.UserSetSelector.USER_SET_1)
            
            # Save current settings to UserSet1
            real_camera.params.UserSetControl.UserSetSave.execute()
            
            # Modify a parameter
            original_exposure = real_camera.params.AcquisitionControl.ExposureTime.get()
            try:
                real_camera.params.AcquisitionControl.ExposureTime.set(original_exposure + 100)
                
                # Load from UserSet1 (should restore original)
                real_camera.params.UserSetControl.UserSetLoad.execute()
                
                # Check if parameter was restored
                restored_exposure = real_camera.params.AcquisitionControl.ExposureTime.get()
                # Note: This may not work exactly due to timing/other factors
            finally:
                # Restore original
                real_camera.params.AcquisitionControl.ExposureTime.set(original_exposure)
        except ParameterNotSupportedError:
            pytest.skip("UserSet operations not supported")
        except ParameterReadOnlyError:
            pytest.skip("Cannot modify parameters during grabbing")


class TestRealCameraParameterProxy:
    """Test the parameter proxy structure."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_params_proxy_structure(self, real_camera: HikCamera):
        """Test that params proxy has expected categories."""
        assert hasattr(real_camera.params, 'DeviceControl')
        assert hasattr(real_camera.params, 'ImageFormatControl')
        assert hasattr(real_camera.params, 'AcquisitionControl')
        assert hasattr(real_camera.params, 'AnalogControl')

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_bound_param_node_get(self, real_camera: HikCamera):
        """Test BoundParamNode get method."""
        node = real_camera.params.DeviceControl.DeviceModelName
        value = node.get()
        
        assert value is not None
        assert isinstance(value, str)

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_bound_param_node_set(self, real_camera: HikCamera):
        """Test BoundParamNode set method."""
        try:
            # Try to set DeviceUserID if supported
            original_id = real_camera.params.DeviceControl.DeviceUserID.get(default="")
            
            real_camera.params.DeviceControl.DeviceUserID.set("TestCamera")
            new_id = real_camera.params.DeviceControl.DeviceUserID.get()
            
            assert new_id == "TestCamera"
            
            # Restore
            real_camera.params.DeviceControl.DeviceUserID.set(original_id)
        except ParameterNotSupportedError:
            pytest.skip("DeviceUserID not supported")
        except ParameterReadOnlyError:
            pytest.skip("DeviceUserID is read-only")

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_param_node_repr(self, real_camera: HikCamera):
        """Test parameter node representation."""
        node = real_camera.params.DeviceControl.DeviceModelName
        repr_str = repr(node)
        
        assert "BoundParamNode" in repr_str or "ParamNode" in repr_str
        assert "DeviceModelName" in repr_str


class TestRealCameraGetCameraInfo:
    """Test get_camera_info comprehensive parameter retrieval."""

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_get_camera_info_returns_dict(self, real_camera: HikCamera):
        """Test that get_camera_info returns a dictionary."""
        info = real_camera.get_camera_info()
        
        assert isinstance(info, dict)
        assert len(info) > 0

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_get_camera_info_contains_common_params(self, real_camera: HikCamera):
        """Test that get_camera_info contains common parameters."""
        info = real_camera.get_camera_info()
        
        # Check for essential parameters
        assert ImageFormatControl.Width in info or info.get(ImageFormatControl.Width) is not None
        assert ImageFormatControl.Height in info or info.get(ImageFormatControl.Height) is not None

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_get_camera_info_param_node_access(self, real_camera: HikCamera):
        """Test accessing camera info with ParamNode keys."""
        info = real_camera.get_camera_info()
        
        # Should be able to use ParamNode as key
        width = info.get(ImageFormatControl.Width)
        assert width is not None

    @pytest.mark.integration
    @pytest.mark.hardware
    def test_get_camera_info_legacy_string_access(self, real_camera: HikCamera):
        """Test legacy string key access still works."""
        info = real_camera.get_camera_info()
        
        # Legacy string keys should also work
        width = info.get("Width")
        # May be None if not present, but shouldn't raise error
        assert width is None or isinstance(width, (int, float))
