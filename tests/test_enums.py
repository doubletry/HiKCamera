"""Tests for hikcamera.enums."""

from __future__ import annotations

from hikcamera import Hik
from hikcamera.enums import (
    AccessMode,
    GainAuto,
    MvErrorCode,
    OutputFormat,
    PixelFormat,
    TransportLayer,
)


class TestAccessMode:
    def test_values_are_ints(self):
        for member in AccessMode:
            assert isinstance(member.value, int)

    def test_exclusive(self):
        assert AccessMode.EXCLUSIVE == 1

    def test_monitor(self):
        assert AccessMode.MONITOR == 6


class TestTransportLayer:
    def test_gige_is_flag(self):
        assert TransportLayer.GIGE & TransportLayer.ALL == TransportLayer.GIGE

    def test_all_combines(self):
        assert TransportLayer.ALL == TransportLayer.GIGE | TransportLayer.USB | TransportLayer.CAMERALINK


class TestPixelFormat:
    def test_mono8_value(self):
        assert PixelFormat.MONO8 == 0x01080001

    def test_bayer_formats_present(self):
        bayer_names = [n for n in PixelFormat.__members__ if n.startswith("BAYER")]
        assert len(bayer_names) >= 16

    def test_rgb_bgr_present(self):
        assert PixelFormat.RGB8_PACKED in PixelFormat.__members__.values()
        assert PixelFormat.BGR8_PACKED in PixelFormat.__members__.values()


class TestOutputFormat:
    def test_all_members(self):
        names = {f.name for f in OutputFormat}
        expected = {"MONO8", "MONO16", "BGR8", "RGB8", "BGRA8", "RGBA8"}
        assert names == expected


class TestMvErrorCode:
    def test_ok_is_zero(self):
        assert MvErrorCode.MV_OK == 0

    def test_not_supported(self):
        assert MvErrorCode.MV_E_SUPPORT == 0x80000001


class TestHikNamespace:
    def test_reexports_parameter_enums(self):
        assert Hik.GainAuto is GainAuto
        assert Hik.GainAuto.OFF == GainAuto.OFF
