"""Tests for hikcamera.utils (image conversion)."""

from __future__ import annotations

import numpy as np
import pytest

from hikcamera.enums import OutputFormat, PixelFormat
from hikcamera.exceptions import ImageConversionError, PixelFormatError
from hikcamera.utils import _decode_packed10, _decode_packed12, raw_to_numpy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_mono8_frame(width: int = 64, height: int = 48) -> np.ndarray:
    """Create a gradient mono8 frame."""
    frame = np.arange(width * height, dtype=np.uint8)
    return frame


def make_bgr8_frame(width: int = 64, height: int = 48) -> np.ndarray:
    """Create a random BGR frame."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8).ravel()


def make_mono16_frame(width: int = 64, height: int = 48) -> np.ndarray:
    """Create a 16-bit mono frame (stored as little-endian uint16)."""
    data = np.arange(width * height, dtype=np.uint16)
    return data.view(np.uint8)


# ---------------------------------------------------------------------------
# MONO8 tests
# ---------------------------------------------------------------------------

class TestMono8:
    def test_to_mono8(self):
        w, h = 64, 48
        buf = make_mono8_frame(w, h)
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO8, OutputFormat.MONO8)
        assert out.shape == (h, w)
        assert out.dtype == np.uint8

    def test_to_bgr8(self):
        w, h = 64, 48
        buf = make_mono8_frame(w, h)
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO8, OutputFormat.BGR8)
        assert out.shape == (h, w, 3)
        assert out.dtype == np.uint8
        # Gray expanded to BGR – all channels should be equal
        assert np.all(out[:, :, 0] == out[:, :, 1])
        assert np.all(out[:, :, 1] == out[:, :, 2])

    def test_to_rgb8(self):
        w, h = 64, 48
        buf = make_mono8_frame(w, h)
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO8, OutputFormat.RGB8)
        assert out.shape == (h, w, 3)

    def test_to_bgra8(self):
        w, h = 64, 48
        buf = make_mono8_frame(w, h)
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO8, OutputFormat.BGRA8)
        assert out.shape == (h, w, 4)

    def test_to_rgba8(self):
        w, h = 64, 48
        buf = make_mono8_frame(w, h)
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO8, OutputFormat.RGBA8)
        assert out.shape == (h, w, 4)

    def test_to_mono16_upscales(self):
        w, h = 8, 8
        buf = np.full(w * h, 128, dtype=np.uint8)
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO8, OutputFormat.MONO16)
        assert out.dtype == np.uint16
        # 128 * 257 = 32896
        assert int(out[0, 0]) == 128 * 257

    def test_bytes_input(self):
        w, h = 4, 4
        buf = bytes(range(w * h))
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO8, OutputFormat.MONO8)
        assert out.shape == (h, w)

    def test_bytearray_input(self):
        w, h = 4, 4
        buf = bytearray(range(w * h))
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO8, OutputFormat.MONO8)
        assert out.shape == (h, w)


# ---------------------------------------------------------------------------
# BGR8 tests
# ---------------------------------------------------------------------------

class TestBGR8:
    def test_bgr_to_bgr(self):
        w, h = 32, 24
        buf = make_bgr8_frame(w, h)
        out = raw_to_numpy(buf, w, h, PixelFormat.BGR8_PACKED, OutputFormat.BGR8)
        assert out.shape == (h, w, 3)
        assert out.dtype == np.uint8

    def test_bgr_to_rgb(self):
        w, h = 32, 24
        buf = make_bgr8_frame(w, h).reshape(h, w, 3)
        original = buf.copy()
        flat_buf = buf.ravel()
        out = raw_to_numpy(flat_buf, w, h, PixelFormat.BGR8_PACKED, OutputFormat.RGB8)
        # R and B channels should be swapped compared to BGR
        assert np.array_equal(out[:, :, 0], original[:, :, 2])
        assert np.array_equal(out[:, :, 2], original[:, :, 0])

    def test_bgr_to_mono8(self):
        w, h = 32, 24
        buf = make_bgr8_frame(w, h)
        out = raw_to_numpy(buf, w, h, PixelFormat.BGR8_PACKED, OutputFormat.MONO8)
        assert out.shape == (h, w)
        assert out.dtype == np.uint8

    def test_rgb_to_bgr(self):
        w, h = 16, 16
        buf = np.zeros(w * h * 3, dtype=np.uint8)
        buf[0] = 255  # R of first pixel
        out = raw_to_numpy(buf, w, h, PixelFormat.RGB8_PACKED, OutputFormat.BGR8)
        # After RGB→BGR conversion, the first pixel's B channel should be 255
        assert out[0, 0, 0] == 255


# ---------------------------------------------------------------------------
# MONO16 tests
# ---------------------------------------------------------------------------

class TestMono16:
    def test_to_mono16(self):
        w, h = 16, 16
        buf = make_mono16_frame(w, h)
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO16, OutputFormat.MONO16)
        assert out.shape == (h, w)
        assert out.dtype == np.uint16

    def test_mono16_to_mono8_downscales(self):
        w, h = 8, 8
        # All pixels = 0xFF00 in uint16 → should map to 0xFF in uint8
        data = np.full(w * h, 0xFF00, dtype=np.uint16)
        buf = data.view(np.uint8)
        out = raw_to_numpy(buf, w, h, PixelFormat.MONO16, OutputFormat.MONO8)
        assert out.dtype == np.uint8
        assert int(out[0, 0]) == 0xFF


# ---------------------------------------------------------------------------
# Packed format tests
# ---------------------------------------------------------------------------

class TestPacked10:
    def test_decode_packed10_output_shape(self):
        w, h = 4, 1
        # Construct packed buffer: 4 pixels in 5 bytes
        # pixels all = 0x3FF (1023) max 10-bit value
        # byte layout: [0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        buf = np.array([0xFF, 0xFF, 0xFF, 0xFF, 0xFF], dtype=np.uint8)
        out = _decode_packed10(buf, w, h, PixelFormat.MONO10_PACKED)
        assert out.shape == (h, w)
        assert out.dtype == np.uint16

    def test_decode_packed10_zero(self):
        w, h = 4, 1
        buf = np.zeros(5, dtype=np.uint8)
        out = _decode_packed10(buf, w, h, PixelFormat.MONO10_PACKED)
        assert np.all(out == 0)

    def test_decode_packed10_buffer_too_small(self):
        w, h = 100, 100
        buf = np.zeros(10, dtype=np.uint8)  # way too small
        with pytest.raises(ImageConversionError):
            _decode_packed10(buf, w, h, PixelFormat.MONO10_PACKED)


class TestPacked12:
    def test_decode_packed12_output_shape(self):
        w, h = 2, 1
        # 2 pixels in 3 bytes
        buf = np.array([0xAB, 0xCD, 0xEF], dtype=np.uint8)
        out = _decode_packed12(buf, w, h, PixelFormat.MONO12_PACKED)
        assert out.shape == (h, w)
        assert out.dtype == np.uint16

    def test_decode_packed12_zero(self):
        w, h = 2, 1
        buf = np.zeros(3, dtype=np.uint8)
        out = _decode_packed12(buf, w, h, PixelFormat.MONO12_PACKED)
        assert np.all(out == 0)

    def test_decode_packed12_buffer_too_small(self):
        w, h = 100, 100
        buf = np.zeros(5, dtype=np.uint8)
        with pytest.raises(ImageConversionError):
            _decode_packed12(buf, w, h, PixelFormat.MONO12_PACKED)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_unsupported_format_raises(self):
        buf = np.zeros(64, dtype=np.uint8)
        with pytest.raises(PixelFormatError):
            raw_to_numpy(buf, 8, 8, 0xDEADBEEF, OutputFormat.BGR8)

    def test_numpy_input(self):
        w, h = 8, 8
        arr = np.zeros(w * h, dtype=np.uint8)
        out = raw_to_numpy(arr, w, h, PixelFormat.MONO8, OutputFormat.MONO8)
        assert out.shape == (h, w)
