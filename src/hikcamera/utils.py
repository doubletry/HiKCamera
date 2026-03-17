"""
Image conversion utilities.

All conversion routines accept raw pixel data (as a ``bytes`` or
``ctypes`` array) together with frame metadata and return a ``numpy``
``ndarray``.

Pixel unpacking steps
---------------------
1. Packed Bayer/mono formats (10-bit packed, 12-bit packed) are unpacked
   to 16-bit planar representation in Python before handing off to OpenCV.
2. Bayer patterns are demosaiced via :pyfunc:`cv2.cvtColor`.
3. The result is reshaped/retyped according to the requested
   :py:class:`~hikcamera.enums.OutputFormat`.

Note
----
For best performance on high-throughput applications prefer using the
SDK's built-in ``MV_CC_ConvertPixelType`` (exposed via
:py:meth:`~hikcamera.camera.HikCamera._sdk_convert`) which offloads
conversion to the native library.
"""

from __future__ import annotations

import ctypes
from ctypes import c_ubyte
from typing import TYPE_CHECKING

import cv2
import numpy as np

from .enums import OutputFormat, PixelFormat
from .exceptions import ImageConversionError, PixelFormatError

if TYPE_CHECKING:
    pass  # pragma: no cover

# ---------------------------------------------------------------------------
# Internal mappings
# ---------------------------------------------------------------------------

# Map PixelFormat → (cv2_bayer_code | None, bits_per_pixel, n_channels_raw)
# bits_per_pixel is bits per sample (8, 10, 12, 16) for packed/planar logic.
#
# NOTE: OpenCV's Bayer naming convention is the *opposite* of the PFNC/SDK
# convention used by Hikvision cameras.  The SDK reports the pattern from
# the sensor's perspective (top-left pixel), while OpenCV flips it.
# Mapping: SDK BayerRG ↔ OpenCV COLOR_BAYER_BG
#          SDK BayerGR ↔ OpenCV COLOR_BAYER_GB
#          SDK BayerGB ↔ OpenCV COLOR_BAYER_GR
#          SDK BayerBG ↔ OpenCV COLOR_BAYER_RG
_FORMAT_INFO: dict[int, tuple[int | None, int, int]] = {
    # Mono
    PixelFormat.MONO8: (None, 8, 1),
    PixelFormat.MONO10: (None, 16, 1),
    PixelFormat.MONO10_PACKED: (None, 10, 1),
    PixelFormat.MONO12: (None, 16, 1),
    PixelFormat.MONO12_PACKED: (None, 12, 1),
    PixelFormat.MONO14: (None, 16, 1),
    PixelFormat.MONO16: (None, 16, 1),
    # Bayer 8-bit (SDK pattern → OpenCV swapped pattern)
    PixelFormat.BAYER_GR8: (cv2.COLOR_BAYER_GB2BGR, 8, 1),
    PixelFormat.BAYER_RG8: (cv2.COLOR_BAYER_BG2BGR, 8, 1),
    PixelFormat.BAYER_GB8: (cv2.COLOR_BAYER_GR2BGR, 8, 1),
    PixelFormat.BAYER_BG8: (cv2.COLOR_BAYER_RG2BGR, 8, 1),
    # Bayer 10/12-bit planar (stored in 16-bit words)
    PixelFormat.BAYER_GR10: (cv2.COLOR_BAYER_GB2BGR, 16, 1),
    PixelFormat.BAYER_RG10: (cv2.COLOR_BAYER_BG2BGR, 16, 1),
    PixelFormat.BAYER_GB10: (cv2.COLOR_BAYER_GR2BGR, 16, 1),
    PixelFormat.BAYER_BG10: (cv2.COLOR_BAYER_RG2BGR, 16, 1),
    PixelFormat.BAYER_GR12: (cv2.COLOR_BAYER_GB2BGR, 16, 1),
    PixelFormat.BAYER_RG12: (cv2.COLOR_BAYER_BG2BGR, 16, 1),
    PixelFormat.BAYER_GB12: (cv2.COLOR_BAYER_GR2BGR, 16, 1),
    PixelFormat.BAYER_BG12: (cv2.COLOR_BAYER_RG2BGR, 16, 1),
    # RGB/BGR – the SDK delivers these as packed interleaved
    PixelFormat.RGB8_PACKED: (cv2.COLOR_RGB2BGR, 8, 3),
    PixelFormat.BGR8_PACKED: (None, 8, 3),
    PixelFormat.RGBA8_PACKED: (cv2.COLOR_RGBA2BGRA, 8, 4),
    PixelFormat.BGRA8_PACKED: (None, 8, 4),
    # YUV
    PixelFormat.YUV422_PACKED: (cv2.COLOR_YUV2BGR_UYVY, 8, 2),
    PixelFormat.YUV422_YUYV_PACKED: (cv2.COLOR_YUV2BGR_YUYV, 8, 2),
    PixelFormat.YCBCR422_8: (cv2.COLOR_YUV2BGR_Y422, 8, 2),
}

# Packed Bayer/mono formats that need custom unpacking
_PACKED10_FORMATS = {
    PixelFormat.MONO10_PACKED,
    PixelFormat.BAYER_GR10_PACKED,
    PixelFormat.BAYER_RG10_PACKED,
    PixelFormat.BAYER_GB10_PACKED,
    PixelFormat.BAYER_BG10_PACKED,
}
_PACKED12_FORMATS = {
    PixelFormat.MONO12_PACKED,
    PixelFormat.BAYER_GR12_PACKED,
    PixelFormat.BAYER_RG12_PACKED,
    PixelFormat.BAYER_GB12_PACKED,
    PixelFormat.BAYER_BG12_PACKED,
}

# Bayer conversion codes for 16-bit (10/12-bit unpacked to 16-bit)
# Same SDK↔OpenCV swap as _FORMAT_INFO above.
_BAYER_16_CODES: dict[int, int] = {
    PixelFormat.BAYER_GR10_PACKED: cv2.COLOR_BAYER_GB2BGR,
    PixelFormat.BAYER_RG10_PACKED: cv2.COLOR_BAYER_BG2BGR,
    PixelFormat.BAYER_GB10_PACKED: cv2.COLOR_BAYER_GR2BGR,
    PixelFormat.BAYER_BG10_PACKED: cv2.COLOR_BAYER_RG2BGR,
    PixelFormat.BAYER_GR12_PACKED: cv2.COLOR_BAYER_GB2BGR,
    PixelFormat.BAYER_RG12_PACKED: cv2.COLOR_BAYER_BG2BGR,
    PixelFormat.BAYER_GB12_PACKED: cv2.COLOR_BAYER_GR2BGR,
    PixelFormat.BAYER_BG12_PACKED: cv2.COLOR_BAYER_RG2BGR,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def raw_to_numpy(
    data: bytes | ctypes.Array[c_ubyte] | np.ndarray,
    width: int,
    height: int,
    pixel_format: int,
    output_format: OutputFormat = OutputFormat.BGR8,
) -> np.ndarray:
    """
    Convert a raw frame buffer to a numpy array.

    Parameters
    ----------
    data:
        Raw pixel data – can be ``bytes``, a ctypes ``c_ubyte`` array,
        or an existing ``uint8`` numpy array.
    width:
        Image width in pixels.
    height:
        Image height in pixels.
    pixel_format:
        Source pixel format (a :py:class:`~hikcamera.enums.PixelFormat`
        value or any raw integer from the SDK).
    output_format:
        Desired output format (default BGR8 for OpenCV compatibility).

    Returns
    -------
    numpy.ndarray
        Decoded image in the requested format.

    Raises
    ------
    PixelFormatError
        When *pixel_format* is not recognised.
    ImageConversionError
        When an error occurs during conversion.
    """
    # Normalise raw data to a uint8 numpy array
    if isinstance(data, np.ndarray):
        buf: np.ndarray = data.view(np.uint8).ravel()
    elif isinstance(data, (bytes, bytearray)):
        buf = np.frombuffer(data, dtype=np.uint8)
    else:
        # ctypes array
        buf = np.ctypeslib.as_array(data).ravel()

    try:
        img = _decode(buf, width, height, pixel_format)
    except (PixelFormatError, ImageConversionError):
        raise
    except Exception as exc:
        raise ImageConversionError(f"Unexpected error during image decoding: {exc}") from exc

    return _to_output_format(img, output_format)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _decode(buf: np.ndarray, width: int, height: int, pixel_format: int) -> np.ndarray:
    """Decode raw bytes to a BGR/mono uint8/uint16 ndarray."""

    if pixel_format in _PACKED10_FORMATS:
        return _decode_packed10(buf, width, height, pixel_format)

    if pixel_format in _PACKED12_FORMATS:
        return _decode_packed12(buf, width, height, pixel_format)

    info = _FORMAT_INFO.get(pixel_format)
    if info is None:
        raise PixelFormatError(
            f"Unsupported pixel format: 0x{pixel_format:08X}. "
            "Use the SDK's MV_CC_ConvertPixelType to convert to a supported format."
        )

    cv2_code, bpp, n_ch = info

    if bpp == 8:
        if n_ch == 1:
            arr = buf.reshape(height, width)
        else:
            arr = buf.reshape(height, width, n_ch)
        if cv2_code is not None:
            return cv2.cvtColor(arr, cv2_code)
        return arr
    elif bpp == 16:
        # 16-bit little-endian (10 or 12 bit stored in 16-bit words)
        arr16 = buf.view(np.uint16).reshape(height, width)
        if cv2_code is not None:
            # cvtColor requires uint16 for 16-bit Bayer
            return cv2.cvtColor(arr16, cv2_code)
        return arr16
    elif bpp in (10, 12):
        # Should have been caught above; fall through with error
        pass

    raise PixelFormatError(f"Cannot decode pixel format 0x{pixel_format:08X}")


def _decode_packed10(buf: np.ndarray, width: int, height: int, pixel_format: int) -> np.ndarray:
    """
    Unpack 10-bit packed data.

    The HIK/PFNC 10-bit packed format stores 4 pixels in 5 bytes:
    ``[p0[9:2], p1[9:2], p2[9:2], p3[9:2], {p3[1:0],p2[1:0],p1[1:0],p0[1:0]}]``
    """
    total_pixels = width * height
    packed_len = (total_pixels * 10 + 7) // 8
    if buf.size < packed_len:
        raise ImageConversionError(
            f"Buffer too small for 10-bit packed: expected {packed_len} bytes, got {buf.size}"
        )

    out = np.zeros(total_pixels, dtype=np.uint16)
    idx = 0
    pix = 0
    while pix + 3 < total_pixels:
        b = buf[idx: idx + 5]
        out[pix] = (int(b[0]) << 2) | (int(b[4]) & 0x03)
        out[pix + 1] = (int(b[1]) << 2) | ((int(b[4]) >> 2) & 0x03)
        out[pix + 2] = (int(b[2]) << 2) | ((int(b[4]) >> 4) & 0x03)
        out[pix + 3] = (int(b[3]) << 2) | ((int(b[4]) >> 6) & 0x03)
        idx += 5
        pix += 4

    # Handle remaining 1–3 pixels in the final partial group
    remaining = total_pixels - pix
    if remaining > 0:
        b = buf[idx: idx + 5]
        if remaining >= 1:
            out[pix] = (int(b[0]) << 2) | (int(b[4]) & 0x03)
        if remaining >= 2:
            out[pix + 1] = (int(b[1]) << 2) | ((int(b[4]) >> 2) & 0x03)
        if remaining >= 3:
            out[pix + 2] = (int(b[2]) << 2) | ((int(b[4]) >> 4) & 0x03)

    arr16 = out.reshape(height, width)
    bayer_code = _BAYER_16_CODES.get(pixel_format)
    if bayer_code is not None:
        return cv2.cvtColor(arr16, bayer_code)
    return arr16


def _decode_packed12(buf: np.ndarray, width: int, height: int, pixel_format: int) -> np.ndarray:
    """
    Unpack 12-bit packed data.

    The HIK/PFNC 12-bit packed format stores 2 pixels in 3 bytes:
    ``[p0[11:4], p1[11:4], {p1[3:0], p0[3:0]}]``
    """
    total_pixels = width * height
    packed_len = (total_pixels * 12 + 7) // 8
    if buf.size < packed_len:
        raise ImageConversionError(
            f"Buffer too small for 12-bit packed: expected {packed_len} bytes, got {buf.size}"
        )

    out = np.zeros(total_pixels, dtype=np.uint16)
    idx = 0
    pix = 0
    while pix + 1 < total_pixels:
        b = buf[idx: idx + 3]
        lo = int(b[2])
        out[pix] = (int(b[0]) << 4) | (lo & 0x0F)
        out[pix + 1] = (int(b[1]) << 4) | ((lo >> 4) & 0x0F)
        idx += 3
        pix += 2

    # Handle the final pixel when total_pixels is odd
    if pix < total_pixels:
        b = buf[idx: idx + 2]
        out[pix] = (int(b[0]) << 4) | (int(b[1]) & 0x0F)

    arr16 = out.reshape(height, width)
    bayer_code = _BAYER_16_CODES.get(pixel_format)
    if bayer_code is not None:
        return cv2.cvtColor(arr16, bayer_code)
    return arr16


def _to_output_format(img: np.ndarray, fmt: OutputFormat) -> np.ndarray:
    """
    Convert a decoded image array to the requested :py:class:`OutputFormat`.

    Parameters
    ----------
    img:
        Decoded source image (may be mono or BGR, 8-bit or 16-bit).
    fmt:
        Requested output format.

    Returns
    -------
    numpy.ndarray
    """
    is_color = img.ndim == 3
    is_16bit = img.dtype == np.uint16

    match fmt:
        case OutputFormat.MONO8:
            if is_color:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if is_16bit:
                img = (img >> 8).astype(np.uint8)
            return img

        case OutputFormat.MONO16:
            if is_color:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if not is_16bit:
                img = img.astype(np.uint16) * 257  # scale 0–255 → 0–65535
            return img

        case OutputFormat.BGR8:
            if not is_color:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if is_16bit:
                img = (img >> 8).astype(np.uint8)
            if img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img

        case OutputFormat.RGB8:
            if not is_color:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            if is_16bit:
                img = (img >> 8).astype(np.uint8)
            if img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return img

        case OutputFormat.BGRA8:
            if not is_color:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
            elif img.ndim == 3 and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            if is_16bit:
                img = (img >> 8).astype(np.uint8)
            return img

        case OutputFormat.RGBA8:
            if not is_color:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGBA)
            elif img.ndim == 3 and img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
            elif img.ndim == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            if is_16bit:
                img = (img >> 8).astype(np.uint8)
            return img

        case _:
            raise PixelFormatError(f"Unknown output format: {fmt}")
