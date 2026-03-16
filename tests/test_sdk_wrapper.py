"""
Tests for the hikcamera.sdk_wrapper module.

These tests validate the library-finding logic using environment variable
overrides and mock filesystem helpers.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from hikcamera.exceptions import SDKNotFoundError
from hikcamera.sdk_wrapper import _find_library, load_sdk


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
