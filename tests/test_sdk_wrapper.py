"""
Tests for the hikcamera.sdk_wrapper module.

These tests validate the library-finding logic using environment variable
overrides and mock filesystem helpers, and verify SDK struct definitions
match the official Hikvision MVS SDK.
"""

from __future__ import annotations

import ctypes
import os
from unittest.mock import MagicMock, patch

import pytest

from hikcamera.exceptions import SDKNotFoundError
from hikcamera.sdk_wrapper import (
    MV_CC_DEVICE_INFO,
    MV_CC_PIXEL_CONVERT_PARAM_EX,
    MV_FRAME_OUT_INFO_EX,
    MV_GIGE_DEVICE_INFO,
    MV_PIXEL_CONVERT_PARAM,
    MV_USB3_DEVICE_INFO,
    MVCC_ENUMVALUE,
    _find_library,
    finalize_sdk,
    load_sdk,
)


class TestFindLibrary:
    def test_env_override_valid(self, tmp_path):
        """HIKCAMERA_SDK_PATH pointing to an existing file is returned as-is."""
        fake_lib = tmp_path / "libMvCameraControl.so"
        fake_lib.write_bytes(b"\x7fELF")  # dummy ELF header

        with patch.dict(os.environ, {"HIKCAMERA_SDK_PATH": str(fake_lib)}):
            path = _find_library()

        assert path == str(fake_lib)

    def test_env_override_missing_raises(self, tmp_path):
        """HIKCAMERA_SDK_PATH pointing to a nonexistent file raises SDKNotFoundError."""
        with patch.dict(os.environ, {"HIKCAMERA_SDK_PATH": "/nonexistent/lib.so"}):
            # Ensure path really doesn't exist
            with pytest.raises(SDKNotFoundError, match="HIKCAMERA_SDK_PATH"):
                _find_library()

    def test_not_found_raises(self):
        """No lib in standard paths → SDKNotFoundError."""
        # Remove env override if present and patch all known paths
        env_clean = {k: v for k, v in os.environ.items() if k != "HIKCAMERA_SDK_PATH"}
        with (
            patch.dict(os.environ, env_clean, clear=True),
            patch("hikcamera.sdk_wrapper._LIB_PATHS_LINUX", ["/nonexistent1.so"]),
            patch("hikcamera.sdk_wrapper._LIB_PATHS_WINDOWS", []),
            patch("ctypes.util.find_library", return_value=None),
        ):
            with pytest.raises(SDKNotFoundError):
                _find_library()


class TestLoadSDK:
    def test_load_sdk_caches(self, tmp_path):
        """load_sdk returns the same object on repeated calls."""
        fake_lib = tmp_path / "libMvCameraControl.so"
        fake_lib.write_bytes(b"\x7fELF")

        mock_lib = MagicMock()

        with (
            patch.dict(os.environ, {"HIKCAMERA_SDK_PATH": str(fake_lib)}),
            patch("ctypes.CDLL", return_value=mock_lib),
            patch("hikcamera.sdk_wrapper._sdk_lib", None),
            patch("hikcamera.sdk_wrapper._configure_sdk_argtypes"),
        ):
            lib1 = load_sdk()
            lib2 = load_sdk()

        assert lib1 is lib2

    def test_load_sdk_raises_on_missing(self):
        env_clean = {k: v for k, v in os.environ.items() if k != "HIKCAMERA_SDK_PATH"}
        with (
            patch.dict(os.environ, env_clean, clear=True),
            patch("hikcamera.sdk_wrapper._LIB_PATHS_LINUX", ["/nope.so"]),
            patch("hikcamera.sdk_wrapper._LIB_PATHS_WINDOWS", []),
            patch("ctypes.util.find_library", return_value=None),
            patch("hikcamera.sdk_wrapper._sdk_lib", None),
        ):
            with pytest.raises(SDKNotFoundError):
                load_sdk()


# ---------------------------------------------------------------------------
# Struct definition tests
# ---------------------------------------------------------------------------

class TestStructDefinitions:
    """Verify that SDK struct field offsets and sizes match the official
    Hikvision MVS SDK ``CameraParams.h`` header."""

    def test_gige_device_info_has_ip_config_fields(self):
        """MV_GIGE_DEVICE_INFO must include nIpCfgOption and nIpCfgCurrent
        before nCurrentIp, matching the official SDK struct layout."""
        gi = MV_GIGE_DEVICE_INFO()
        assert hasattr(gi, "nIpCfgOption")
        assert hasattr(gi, "nIpCfgCurrent")
        assert hasattr(gi, "nCurrentIp")
        assert hasattr(gi, "chSerialNumber")

    def test_gige_device_info_ip_offset(self):
        """nCurrentIp should be at offset 8 (after two uint32 fields)."""
        offset = MV_GIGE_DEVICE_INFO.nCurrentIp.offset
        assert offset == 8, f"nCurrentIp at offset {offset}, expected 8"

    def test_gige_device_info_serial_populated(self):
        """Setting chSerialNumber should be readable after struct assignment."""
        gi = MV_GIGE_DEVICE_INFO()
        gi.nCurrentIp = 0xC0A80164  # 192.168.1.100
        gi.chSerialNumber = b"DA12345678\x00" + b"\x00" * 5
        dev = MV_CC_DEVICE_INFO()
        dev.nTLayerType = MV_CC_DEVICE_INFO.MV_GIGE_DEVICE
        dev.SpecialInfo.stGigEInfo = gi

        read_gi = dev.SpecialInfo.stGigEInfo
        assert read_gi.nCurrentIp == 0xC0A80164
        sn = read_gi.chSerialNumber.decode("utf-8", errors="replace").strip("\x00")
        assert sn == "DA12345678"

    def test_usb3_device_info_has_correct_fields(self):
        """MV_USB3_DEVICE_INFO should have SDK-correct field layout:
        StreamEndPoint, EventEndPoint, idVendor, idProduct, nDeviceNumber,
        chDeviceGUID, and 64-byte char arrays."""
        ui = MV_USB3_DEVICE_INFO()
        assert hasattr(ui, "StreamEndPoint")
        assert hasattr(ui, "EventEndPoint")
        assert hasattr(ui, "idVendor")
        assert hasattr(ui, "idProduct")
        assert hasattr(ui, "nDeviceNumber")
        assert hasattr(ui, "chDeviceGUID")
        assert hasattr(ui, "chVendorName")
        assert hasattr(ui, "chSerialNumber")
        assert hasattr(ui, "nbcdUSB")
        assert hasattr(ui, "nDeviceAddress")
        # chSerialNumber should accept 64-byte data
        ui.chSerialNumber = b"A" * 63 + b"\x00"
        assert ui.chSerialNumber == b"A" * 63

    def test_usb3_device_info_idvendor_offset(self):
        """idVendor should be at offset 4 (after 4 endpoint bytes)."""
        offset = MV_USB3_DEVICE_INFO.idVendor.offset
        assert offset == 4, f"idVendor at offset {offset}, expected 4"

    def test_frame_out_info_ex_has_all_chunk_fields(self):
        """MV_FRAME_OUT_INFO_EX must include all chunk watermark fields
        between nFrameLen and nLostPacket."""
        fi = MV_FRAME_OUT_INFO_EX()
        assert hasattr(fi, "nSecondCount")
        assert hasattr(fi, "nCycleCount")
        assert hasattr(fi, "nCycleOffset")
        assert hasattr(fi, "fGain")
        assert hasattr(fi, "fExposureTime")
        assert hasattr(fi, "nAverageBrightness")
        assert hasattr(fi, "nRed")
        assert hasattr(fi, "nGreen")
        assert hasattr(fi, "nBlue")
        assert hasattr(fi, "nFrameCounter")
        assert hasattr(fi, "nTriggerIndex")
        assert hasattr(fi, "nInput")
        assert hasattr(fi, "nOutput")
        assert hasattr(fi, "nOffsetX")
        assert hasattr(fi, "nOffsetY")
        assert hasattr(fi, "nChunkWidth")
        assert hasattr(fi, "nChunkHeight")
        assert hasattr(fi, "nLostPacket")
        assert hasattr(fi, "nUnparsedChunkNum")

    def test_frame_out_info_ex_field_order(self):
        """nLostPacket must come after the chunk watermark fields,
        not directly after nFrameLen."""
        lost_offset = MV_FRAME_OUT_INFO_EX.nLostPacket.offset
        frame_len_offset = MV_FRAME_OUT_INFO_EX.nFrameLen.offset
        # There are 15 fields (mix of uint32, float, uint16) between
        # nFrameLen and nLostPacket, totalling at least 60 bytes
        assert lost_offset > frame_len_offset + 60, (
            f"nLostPacket at offset {lost_offset} is too close to "
            f"nFrameLen at offset {frame_len_offset}"
        )

    def test_frame_out_info_ex_size(self):
        """Struct should be large enough for the SDK to write to safely."""
        assert ctypes.sizeof(MV_FRAME_OUT_INFO_EX) >= 200

    def test_device_info_has_dev_type_info(self):
        """MV_CC_DEVICE_INFO must include nDevTypeInfo field (SDK v4.7.0)."""
        dev = MV_CC_DEVICE_INFO()
        assert hasattr(dev, "nDevTypeInfo")
        dev.nDevTypeInfo = 42
        assert dev.nDevTypeInfo == 42

    def test_device_info_dev_type_info_offset(self):
        """nDevTypeInfo should be at offset 16 (after nMajorVer(2) + nMinorVer(2)
        + nMacAddrHigh(4) + nMacAddrLow(4) + nTLayerType(4) = 16)."""
        offset = MV_CC_DEVICE_INFO.nDevTypeInfo.offset
        assert offset == 16, f"nDevTypeInfo at offset {offset}, expected 16"

    def test_device_info_reserved_after_dev_type(self):
        """nReserved should be at offset 20 (after nDevTypeInfo) and have
        3 elements per SDK v4.7.0."""
        offset = MV_CC_DEVICE_INFO.nReserved.offset
        assert offset == 20, f"nReserved at offset {offset}, expected 20"
        dev = MV_CC_DEVICE_INFO()
        assert ctypes.sizeof(dev.nReserved) == 3 * 4

    def test_device_info_special_info_offset(self):
        """SpecialInfo union offset should be 32 (unchanged total layout
        size before union: 2+2+4+4+4+4+12 = 32)."""
        offset = MV_CC_DEVICE_INFO.SpecialInfo.offset
        assert offset == 32, f"SpecialInfo at offset {offset}, expected 32"

    def test_enum_value_reserved_size(self):
        """MVCC_ENUMVALUE.nReserved should have 4 elements per SDK v4.7.0."""
        ev = MVCC_ENUMVALUE()
        assert hasattr(ev, "nReserved")
        assert ctypes.sizeof(ev.nReserved) == 4 * 4

    def test_pixel_convert_param_ex_width_is_uint(self):
        """MV_CC_PIXEL_CONVERT_PARAM_EX.nWidth should be unsigned int (4 bytes),
        not unsigned short (2 bytes), matching the EX struct in SDK v4.7.0."""
        assert MV_CC_PIXEL_CONVERT_PARAM_EX.nWidth.size == 4, (
            f"nWidth size is {MV_CC_PIXEL_CONVERT_PARAM_EX.nWidth.size}, expected 4"
        )
        assert MV_CC_PIXEL_CONVERT_PARAM_EX.nHeight.size == 4, (
            f"nHeight size is {MV_CC_PIXEL_CONVERT_PARAM_EX.nHeight.size}, expected 4"
        )

    def test_pixel_convert_param_backward_compat_alias(self):
        """MV_PIXEL_CONVERT_PARAM should be an alias for
        MV_CC_PIXEL_CONVERT_PARAM_EX for backward compatibility."""
        assert MV_PIXEL_CONVERT_PARAM is MV_CC_PIXEL_CONVERT_PARAM_EX


class TestFinalizeSdk:
    def test_finalize_sdk_no_op_when_not_loaded(self):
        """finalize_sdk should not raise when SDK was never loaded."""
        with patch("hikcamera.sdk_wrapper._sdk_lib", None):
            finalize_sdk()  # should be a no-op
