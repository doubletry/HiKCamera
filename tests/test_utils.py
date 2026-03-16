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
        buf[0] = 255  # R of first pixel (RGB order)
        out = raw_to_numpy(buf, w, h, PixelFormat.RGB8_PACKED, OutputFormat.BGR8)
        # After RGB→BGR conversion, R=255 maps to BGR channel 2
        assert out[0, 0, 2] == 255
        assert out[0, 0, 0] == 0  # B channel is zero

    def test_rgba_to_bgra(self):
        """RGBA8_PACKED (4-ch) should reshape to (H,W,4) before cvtColor."""
        w, h = 8, 8
        buf = np.zeros(w * h * 4, dtype=np.uint8)
        buf[0] = 100  # R of first pixel
        buf[1] = 200  # G of first pixel
        buf[2] = 50   # B of first pixel
        buf[3] = 255  # A of first pixel
        out = raw_to_numpy(buf, w, h, PixelFormat.RGBA8_PACKED, OutputFormat.BGRA8)
        assert out.shape == (h, w, 4)
        # After RGBA→BGRA: B=50, G=200, R=100, A=255
        assert out[0, 0, 0] == 50   # B
        assert out[0, 0, 1] == 200  # G
        assert out[0, 0, 2] == 100  # R
        assert out[0, 0, 3] == 255  # A


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

    def test_decode_packed10_non_multiple_of_4(self):
        """Tail pixels (total not a multiple of 4) should be decoded, not left as zero."""
        # 5 pixels = 1 full group (4 px, 5 bytes) + 1 tail pixel (needs 5 more bytes)
        w, h = 5, 1
        # First group: 4 pixels all = 0x000 (all-zero bytes)
        # Second group: 1 tail pixel with high byte 0x10 and low bits 0x01
        # pixel value = (0x10 << 2) | 0x01 = 65
        buf = np.array(
            [0x00, 0x00, 0x00, 0x00, 0x00,  # group 1: 4 zero pixels
             0x10, 0x00, 0x00, 0x00, 0x01],  # group 2: tail pixel
            dtype=np.uint8,
        )
        out = _decode_packed10(buf, w, h, PixelFormat.MONO10_PACKED)
        assert out.shape == (h, w)
        assert out[0, 4] == 65  # tail pixel should be decoded


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

    def test_decode_packed12_odd_pixel_count(self):
        """When total_pixels is odd the last pixel must still be decoded."""
        # 3 pixels = 1 full pair (2 px, 3 bytes) + 1 tail pixel (2 bytes)
        # pair: all zero
        # tail pixel: high byte 0xAB, low nibble 0x0C → (0xAB << 4) | 0x0C = 2748
        w, h = 3, 1
        buf = np.array(
            [0x00, 0x00, 0x00,  # pair: 2 zero pixels
             0xAB, 0x0C],       # tail: 1 pixel
            dtype=np.uint8,
        )
        out = _decode_packed12(buf, w, h, PixelFormat.MONO12_PACKED)
        assert out.shape == (h, w)
        assert out[0, 2] == (0xAB << 4) | 0x0C


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
