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
    MV_FRAME_OUT_INFO_EX,
    MV_GIGE_DEVICE_INFO,
    MV_USB3_DEVICE_INFO,
    _find_library,
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
    """Verify that SDK struct field offsets and sizes are correct."""

    def test_gige_device_info_has_ip_config_fields(self):
        """MV_GIGE_DEVICE_INFO must include nIpCfgOption and nIpCfgCurrent
        before nCurrentIp, matching the official SDK struct layout."""
        gi = MV_GIGE_DEVICE_INFO()
        # Verify the fields exist
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

        # Read back through the union
        read_gi = dev.SpecialInfo.stGigEInfo
        assert read_gi.nCurrentIp == 0xC0A80164
        sn = read_gi.chSerialNumber.decode("utf-8", errors="replace").strip("\x00")
        assert sn == "DA12345678"

    def test_usb3_device_info_field_sizes(self):
        """MV_USB3_DEVICE_INFO should have 64-byte fields for names/serial."""
        ui = MV_USB3_DEVICE_INFO()
        assert hasattr(ui, "chVendorName")
        assert hasattr(ui, "chSerialNumber")
        assert hasattr(ui, "nbcdUSB")
        assert hasattr(ui, "nDeviceAddress")
        # chSerialNumber should be 64 bytes (not 16)
        assert len(ui.chSerialNumber) <= 64
        # Verify we can write a long serial number
        ui.chSerialNumber = b"A" * 63 + b"\x00"
        assert ui.chSerialNumber == b"A" * 63

    def test_frame_out_info_ex_has_second_count(self):
        """MV_FRAME_OUT_INFO_EX must include nSecondCount field."""
        fi = MV_FRAME_OUT_INFO_EX()
        assert hasattr(fi, "nSecondCount")
        assert hasattr(fi, "nUnparsedChunkNum")
        # Struct should be large enough for the SDK to write to safely
        assert ctypes.sizeof(fi) >= 200  # SDK struct is ~220 bytes
