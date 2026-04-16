"""
Tests for hikcamera.params (ParamNode, category namespaces, validation).
"""

from __future__ import annotations

import pytest

from hikcamera.enums import (
    GainAuto,
    PixelFormat,
    TriggerMode,
)
from hikcamera.exceptions import (
    ParameterReadOnlyError,
    ParameterValueError,
)
from hikcamera.params import (
    ALL_CATEGORIES,
    PARAM_NODE_LOOKUP,
    AcquisitionControl,
    AnalogControl,
    DeviceControl,
    DigitalIOControl,
    EncoderControl,
    FrequencyConverterControl,
    ImageFormatControl,
    LUTControl,
    ParamNode,
    ShadingCorrection,
    TransportLayerControl,
    UserSetControl,
    _build_node_lookup,
    _build_param_schema,
)

# ---------------------------------------------------------------------------
# ParamNode basics / ParamNode 基础
# ---------------------------------------------------------------------------

class TestParamNodeBasics:
    """Test ParamNode dataclass properties and str conversion."""

    def test_str_returns_name(self):
        node = ParamNode("ExposureTime", float, "R/W", "Exposure time")
        assert str(node) == "ExposureTime"

    def test_frozen(self):
        node = ParamNode("Width", int, "R/W", "Width")
        with pytest.raises(AttributeError):
            node.name = "Height"  # type: ignore[misc]

    def test_optional_fields_default_to_none(self):
        node = ParamNode("Foo", int, "R/W", "desc")
        assert node.unit is None
        assert node.min_value is None
        assert node.max_value is None
        assert node.step is None

    def test_all_fields_populated(self):
        node = ParamNode(
            "GevSCPSPacketSize", int, "R/W", "Packet size",
            unit="bytes", min_value=220, max_value=9156, step=8,
        )
        assert node.name == "GevSCPSPacketSize"
        assert node.data_type is int
        assert node.access == "R/W"
        assert node.unit == "bytes"
        assert node.min_value == 220
        assert node.max_value == 9156
        assert node.step == 8


# ---------------------------------------------------------------------------
# ParamNode.validate() – type validation / 类型校验
# ---------------------------------------------------------------------------

class TestParamNodeTypeValidation:
    """Test type checking in ParamNode.validate()."""

    def test_int_accepts_int(self):
        node = ParamNode("Width", int, "R/W", "Width", min_value=1)
        assert node.validate(1280) == 1280

    def test_int_rejects_bool(self):
        node = ParamNode("Width", int, "R/W", "Width")
        with pytest.raises(ParameterValueError, match="expects int"):
            node.validate(True)

    def test_int_rejects_str(self):
        node = ParamNode("Width", int, "R/W", "Width")
        with pytest.raises(ParameterValueError, match="expects int"):
            node.validate("1280")

    def test_int_rejects_float(self):
        node = ParamNode("Width", int, "R/W", "Width")
        with pytest.raises(ParameterValueError, match="expects int"):
            node.validate(12.5)

    def test_float_accepts_float(self):
        node = ParamNode("ExposureTime", float, "R/W", "Exposure")
        assert node.validate(5000.0) == 5000.0

    def test_float_promotes_int(self):
        node = ParamNode("ExposureTime", float, "R/W", "Exposure")
        result = node.validate(5000)
        assert result == 5000.0
        assert isinstance(result, float)

    def test_float_rejects_bool(self):
        node = ParamNode("ExposureTime", float, "R/W", "Exposure")
        with pytest.raises(ParameterValueError, match="expects float"):
            node.validate(True)

    def test_float_rejects_str(self):
        node = ParamNode("ExposureTime", float, "R/W", "Exposure")
        with pytest.raises(ParameterValueError, match="expects float"):
            node.validate("fast")

    def test_bool_accepts_bool(self):
        node = ParamNode("GammaEnable", bool, "R/W", "Gamma enable")
        assert node.validate(True) is True
        assert node.validate(False) is False

    def test_bool_rejects_int(self):
        node = ParamNode("GammaEnable", bool, "R/W", "Gamma enable")
        with pytest.raises(ParameterValueError, match="expects bool"):
            node.validate(1)

    def test_bool_rejects_str(self):
        node = ParamNode("GammaEnable", bool, "R/W", "Gamma enable")
        with pytest.raises(ParameterValueError, match="expects bool"):
            node.validate("true")

    def test_str_accepts_str(self):
        node = ParamNode("DeviceUserID", str, "R/W", "User ID")
        assert node.validate("MyCam") == "MyCam"

    def test_str_rejects_int(self):
        node = ParamNode("DeviceUserID", str, "R/W", "User ID")
        with pytest.raises(ParameterValueError, match="expects str"):
            node.validate(42)

    def test_enum_accepts_correct_enum(self):
        node = ParamNode("GainAuto", GainAuto, "R/W", "Auto gain")
        assert node.validate(GainAuto.OFF) == GainAuto.OFF

    def test_enum_paramnode_exposes_data_type_attribute(self):
        assert AnalogControl.GainAuto.data_type is GainAuto
        assert UserSetControl.UserSetSelector.data_type.__name__ == "UserSetSelector"

    def test_enum_rejects_raw_string(self):
        node = ParamNode("GainAuto", GainAuto, "R/W", "Auto gain")
        with pytest.raises(ParameterValueError, match="expects GainAuto"):
            node.validate("Off")

    def test_enum_rejects_wrong_enum(self):
        node = ParamNode("GainAuto", GainAuto, "R/W", "Auto gain")
        with pytest.raises(ParameterValueError, match="expects GainAuto"):
            node.validate(TriggerMode.OFF)

    def test_enum_rejects_float(self):
        node = ParamNode("GainAuto", GainAuto, "R/W", "Auto gain")
        with pytest.raises(ParameterValueError, match="expects GainAuto"):
            node.validate(3.14)

    def test_int_enum_accepts_correct_member(self):
        node = ParamNode("PixelFormat", PixelFormat, "R/(W)", "Pixel format")
        assert node.validate(PixelFormat.MONO8) == PixelFormat.MONO8

    def test_int_enum_rejects_raw_int(self):
        node = ParamNode("PixelFormat", PixelFormat, "R/(W)", "Pixel format")
        with pytest.raises(ParameterValueError, match="expects PixelFormat"):
            node.validate(0x01080001)

    def test_command_node_accepts_any(self):
        node = ParamNode("DeviceReset", "command", "W", "Reset device")
        assert node.validate(None) is None
        assert node.validate(1) == 1


# ---------------------------------------------------------------------------
# ParamNode.validate() – range validation / 范围校验
# ---------------------------------------------------------------------------

class TestParamNodeRangeValidation:
    """Test numeric range checking in ParamNode.validate()."""

    def test_min_value_passes(self):
        node = ParamNode("Width", int, "R/W", "Width", min_value=1)
        assert node.validate(1) == 1
        assert node.validate(1920) == 1920

    def test_min_value_rejects_below(self):
        node = ParamNode("Width", int, "R/W", "Width", min_value=1)
        with pytest.raises(ParameterValueError, match="below minimum"):
            node.validate(0)

    def test_max_value_passes(self):
        node = ParamNode(
            "GevSCPSPacketSize", int, "R/W", "Packet size",
            min_value=220, max_value=9156,
        )
        assert node.validate(1500) == 1500
        assert node.validate(9156) == 9156

    def test_max_value_rejects_above(self):
        node = ParamNode(
            "GevSCPSPacketSize", int, "R/W", "Packet size",
            min_value=220, max_value=9156,
        )
        with pytest.raises(ParameterValueError, match="above maximum"):
            node.validate(10000)

    def test_float_min_value_passes(self):
        node = ParamNode("ExposureTime", float, "R/W", "Exposure", min_value=0.0)
        assert node.validate(0.0) == 0.0
        assert node.validate(100000.0) == 100000.0

    def test_float_min_value_rejects_below(self):
        node = ParamNode("ExposureTime", float, "R/W", "Exposure", min_value=0.0)
        with pytest.raises(ParameterValueError, match="below minimum"):
            node.validate(-1.0)

    def test_float_promoted_int_checked_against_range(self):
        node = ParamNode("ExposureTime", float, "R/W", "Exposure", min_value=0.0)
        # int promoted to float should still be range-checked
        assert node.validate(5000) == 5000.0
        with pytest.raises(ParameterValueError, match="below minimum"):
            node.validate(-1)

    def test_range_error_includes_unit(self):
        node = ParamNode(
            "ExposureTime", float, "R/W", "Exposure", unit="us", min_value=0.0,
        )
        with pytest.raises(ParameterValueError, match="us"):
            node.validate(-1.0)

    def test_no_range_skips_check(self):
        node = ParamNode("LUTValue", int, "R/W", "LUT value")
        # Without min/max, any int should pass
        assert node.validate(-100) == -100
        assert node.validate(999999) == 999999


# ---------------------------------------------------------------------------
# ParamNode.validate() – access mode / 访问模式
# ---------------------------------------------------------------------------

class TestParamNodeAccessMode:
    """Test read-only rejection in ParamNode.validate()."""

    def test_read_only_raises(self):
        node = ParamNode("DeviceModelName", str, "R", "Model name")
        with pytest.raises(ParameterReadOnlyError, match="read-only"):
            node.validate("anything")

    def test_read_only_int_raises(self):
        node = ParamNode("WidthMax", int, "R", "Max width")
        with pytest.raises(ParameterReadOnlyError):
            node.validate(1920)

    def test_rw_allows_write(self):
        node = ParamNode("OffsetX", int, "R/W", "Offset X", min_value=0)
        assert node.validate(100) == 100

    def test_r_w_bracket_allows_write(self):
        """R/(W) nodes should allow writes."""
        node = ParamNode("Width", int, "R/(W)", "Width", min_value=1)
        assert node.validate(1280) == 1280

    def test_write_only_allows_write(self):
        node = ParamNode("DeviceReset", "command", "W", "Reset")
        assert node.validate(None) is None


# ---------------------------------------------------------------------------
# Category namespace classes / 分类命名空间类
# ---------------------------------------------------------------------------

class TestCategoryNamespaces:
    """Test that all category classes expose ParamNode attributes."""

    def test_all_categories_tuple(self):
        assert len(ALL_CATEGORIES) == 11
        assert DeviceControl in ALL_CATEGORIES
        assert ImageFormatControl in ALL_CATEGORIES
        assert AcquisitionControl in ALL_CATEGORIES
        assert AnalogControl in ALL_CATEGORIES
        assert LUTControl in ALL_CATEGORIES
        assert EncoderControl in ALL_CATEGORIES
        assert FrequencyConverterControl in ALL_CATEGORIES
        assert ShadingCorrection in ALL_CATEGORIES
        assert DigitalIOControl in ALL_CATEGORIES
        assert TransportLayerControl in ALL_CATEGORIES
        assert UserSetControl in ALL_CATEGORIES

    def test_each_category_has_param_nodes(self):
        for category in ALL_CATEGORIES:
            nodes = [
                attr for attr_name in dir(category)
                if isinstance(attr := getattr(category, attr_name), ParamNode)
            ]
            assert len(nodes) > 0, f"{category.__name__} has no ParamNode attributes"

    def test_device_control_sample_nodes(self):
        assert isinstance(DeviceControl.DeviceUserID, ParamNode)
        assert DeviceControl.DeviceUserID.name == "DeviceUserID"
        assert DeviceControl.DeviceUserID.data_type is str
        assert DeviceControl.DeviceUserID.access == "R/W"

    def test_image_format_control_sample_nodes(self):
        assert isinstance(ImageFormatControl.Width, ParamNode)
        assert ImageFormatControl.Width.name == "Width"
        assert ImageFormatControl.Width.data_type is int
        assert ImageFormatControl.Width.min_value == 1

    def test_acquisition_control_exposure_time(self):
        node = AcquisitionControl.ExposureTime
        assert node.name == "ExposureTime"
        assert node.data_type is float
        assert node.access == "R/W"
        assert node.unit == "us"
        assert node.min_value == 0.0

    def test_analog_control_gain(self):
        node = AnalogControl.Gain
        assert node.name == "Gain"
        assert node.data_type is float
        assert node.unit == "dB"

    def test_transport_layer_packet_size(self):
        node = TransportLayerControl.GevSCPSPacketSize
        assert node.name == "GevSCPSPacketSize"
        assert node.data_type is int
        assert node.min_value == 220
        assert node.max_value == 9156
        assert node.step == 8

    def test_user_set_control_nodes(self):
        assert UserSetControl.UserSetLoad.data_type == "command"
        assert UserSetControl.UserSetLoad.access == "W"
        assert isinstance(UserSetControl.UserSetSelector, ParamNode)

    def test_acquisition_control_trigger_software_command(self):
        assert AcquisitionControl.TriggerSoftware.data_type == "command"
        assert AcquisitionControl.TriggerSoftware.access == "W"


# ---------------------------------------------------------------------------
# Schema and lookup builders / 模式和查找表构建器
# ---------------------------------------------------------------------------

class TestSchemaAndLookup:
    """Test _build_param_schema() and _build_node_lookup()."""

    def test_schema_contains_known_params(self):
        schema = _build_param_schema()
        assert schema["Width"] is int
        assert schema["ExposureTime"] is float
        assert schema["GainAuto"] is GainAuto
        assert schema["GammaEnable"] is bool
        assert schema["DeviceUserID"] is str
        assert schema["PixelFormat"] is PixelFormat

    def test_schema_excludes_command_nodes(self):
        schema = _build_param_schema()
        assert "DeviceReset" not in schema
        assert "UserSetLoad" not in schema
        assert "UserSetSave" not in schema
        assert "AcquisitionStart" not in schema
        assert "TriggerSoftware" not in schema

    def test_node_lookup_contains_all_nodes(self):
        lookup = _build_node_lookup()
        # Spot check
        assert "ExposureTime" in lookup
        assert "Width" in lookup
        assert "GainAuto" in lookup
        assert "DeviceReset" in lookup  # commands ARE in lookup
        assert "GevSCPSPacketSize" in lookup
        assert "TriggerSoftware" in lookup

    def test_param_node_lookup_is_pre_built(self):
        assert isinstance(PARAM_NODE_LOOKUP, dict)
        assert len(PARAM_NODE_LOOKUP) > 50  # sanity: we defined many nodes
        assert PARAM_NODE_LOOKUP["ExposureTime"] is AcquisitionControl.ExposureTime

    def test_schema_backward_compatible_with_old_entries(self):
        """All parameters from the old hard-coded schema must still be present."""
        schema = _build_param_schema()
        old_params = [
            "Width", "Height", "OffsetX", "OffsetY",
            "ExposureTime", "ExposureAuto", "Gain", "GainAuto",
            "Gamma", "GammaEnable", "GammaSelector",
            "AcquisitionFrameRate", "AcquisitionFrameRateEnable",
            "AcquisitionMode",
            "TriggerMode", "TriggerSource", "TriggerActivation", "TriggerSelector",
            "LineSelector", "LineMode",
            "BalanceWhiteAuto",
            "UserSetSelector", "UserSetDefault",
            "DeviceUserID",
            "GevSCPSPacketSize",
            "PixelFormat",
            "BinningHorizontal", "BinningVertical",
            "DecimationHorizontal", "DecimationVertical",
        ]
        for name in old_params:
            assert name in schema, f"Old schema entry {name!r} missing from auto-built schema"


# ---------------------------------------------------------------------------
# Integration: cam.params proxy
# ---------------------------------------------------------------------------

class TestStructuredParamProxy:
    """Test ``cam.params`` structured parameter access."""

    def test_set_int(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam.params.ImageFormatControl.Width.set(1280)
        cam._sdk.MV_CC_SetIntValueEx.assert_called()

    def test_set_float(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam.params.AcquisitionControl.ExposureTime.set(5000.0)
        cam._sdk.MV_CC_SetFloatValue.assert_called()

    def test_set_bool(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam.params.AcquisitionControl.AcquisitionFrameRateEnable.set(True)
        cam._sdk.MV_CC_SetBoolValue.assert_called()

    def test_set_enum(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam.params.AnalogControl.GainAuto.set(GainAuto.OFF)
        cam._sdk.MV_CC_SetEnumValueByString.assert_called()

    def test_set_string(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam.params.DeviceControl.DeviceUserID.set("MyCam")
        cam._sdk.MV_CC_SetStringValue.assert_called()

    def test_set_rejects_read_only(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        with pytest.raises(ParameterReadOnlyError, match="read-only"):
            cam.params.DeviceControl.DeviceModelName.set("NewModel")

    def test_set_validates_range(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        with pytest.raises(ParameterValueError, match="below minimum"):
            cam.params.ImageFormatControl.Width.set(0)

    def test_set_validates_type(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        with pytest.raises(ParameterValueError, match="expects float"):
            cam.params.AcquisitionControl.ExposureTime.set("fast")

    def test_set_float_accepts_int(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam.params.AcquisitionControl.ExposureTime.set(5000)
        cam._sdk.MV_CC_SetFloatValue.assert_called()

    def test_get_with_param_node(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        result = cam.params.ImageFormatControl.Width.get()
        assert result is not None or result == 0

    def test_get_returns_default_when_not_supported(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_GetIntValueEx.return_value = 0x80000001
        assert cam.params.ImageFormatControl.Width.get(default="fallback") == "fallback"
