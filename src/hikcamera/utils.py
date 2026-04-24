"""
Image conversion utilities.
图像转换工具模块。

All conversion routines accept raw pixel data (as a ``bytes`` or
``ctypes`` array) together with frame metadata and return a ``numpy``
``ndarray``.
所有转换例程接受原始像素数据（``bytes`` 或 ``ctypes`` 数组）以及
帧元数据，并返回 ``numpy`` ``ndarray``。

Pixel unpacking steps / 像素解包步骤
-------------------------------------
1. Packed Bayer/mono formats (10-bit packed, 12-bit packed) are unpacked
   to 16-bit planar representation in Python before handing off to OpenCV.
   紧凑型 Bayer/灰度格式（10 位、12 位紧凑）先在 Python 中解包为
   16 位平面表示，再交给 OpenCV 处理。
2. Bayer patterns are demosaiced via :pyfunc:`cv2.cvtColor`.
   Bayer 图案通过 :pyfunc:`cv2.cvtColor` 进行去马赛克。
3. The result is reshaped/retyped according to the requested
   :py:class:`~hikcamera.enums.OutputFormat`.
   结果按照所请求的 :py:class:`~hikcamera.enums.OutputFormat` 重塑/转型。

Note / 注意
-----------
This module is the **OpenCV-based fallback** image-conversion path.
The SDK pipeline (``MV_CC_ConvertPixelTypeEx``, optionally preceded by
``MV_CC_HB_Decode``) is preferred whenever a :py:class:`HikCamera`
instance is open with ``use_sdk_decode=True`` (the default).
本模块为基于 OpenCV 的**回退**图像转换路径。
当 :py:class:`HikCamera` 实例已打开且 ``use_sdk_decode=True``（默认）时，
优先使用 SDK 管线（``MV_CC_ConvertPixelTypeEx``，必要时先经过
``MV_CC_HB_Decode``）。

For low-level direct access to the SDK conversion you can also call
:py:meth:`~hikcamera.camera.HikCamera.sdk_convert_pixel` (kept as a
public helper for back-compat).
如需直接调用 SDK 转换，可使用
:py:meth:`~hikcamera.camera.HikCamera.sdk_convert_pixel`
（作为公开辅助方法保留以兼容旧代码）。
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
# Internal mappings / 内部映射
# ---------------------------------------------------------------------------

# Map PixelFormat → (cv2_bayer_code | None, bits_per_pixel, n_channels_raw)
# 映射 PixelFormat → (cv2 Bayer 转换码 | None, 每像素位数, 原始通道数)
# bits_per_pixel is bits per sample (8, 10, 12, 16) for packed/planar logic.
# bits_per_pixel 指每个采样的位数（8、10、12、16），用于紧凑/平面格式逻辑。
#
# NOTE: OpenCV's Bayer naming convention is the *opposite* of the PFNC/SDK
# convention used by Hikvision cameras.  The SDK reports the pattern from
# the sensor's perspective (top-left pixel), while OpenCV flips it.
# 注意：OpenCV 的 Bayer 命名约定与海康威视相机使用的 PFNC/SDK 约定*相反*。
# SDK 从传感器角度（左上角像素）报告图案，而 OpenCV 则翻转。
# Mapping / 映射关系:
#   SDK BayerRG ↔ OpenCV COLOR_BAYER_BG
#   SDK BayerGR ↔ OpenCV COLOR_BAYER_GB
#   SDK BayerGB ↔ OpenCV COLOR_BAYER_GR
#   SDK BayerBG ↔ OpenCV COLOR_BAYER_RG
_FORMAT_INFO: dict[int, tuple[int | None, int, int]] = {
    # Mono / 灰度
    PixelFormat.MONO8: (None, 8, 1),
    PixelFormat.MONO10: (None, 16, 1),
    PixelFormat.MONO10_PACKED: (None, 10, 1),
    PixelFormat.MONO12: (None, 16, 1),
    PixelFormat.MONO12_PACKED: (None, 12, 1),
    PixelFormat.MONO14: (None, 16, 1),
    PixelFormat.MONO16: (None, 16, 1),
    # Bayer 8-bit (SDK pattern → OpenCV swapped pattern)
    # Bayer 8 位（SDK 图案 → OpenCV 翻转后的图案）
    PixelFormat.BAYER_GR8: (cv2.COLOR_BAYER_GB2BGR, 8, 1),
    PixelFormat.BAYER_RG8: (cv2.COLOR_BAYER_BG2BGR, 8, 1),
    PixelFormat.BAYER_GB8: (cv2.COLOR_BAYER_GR2BGR, 8, 1),
    PixelFormat.BAYER_BG8: (cv2.COLOR_BAYER_RG2BGR, 8, 1),
    # Bayer 10/12-bit planar (stored in 16-bit words)
    # Bayer 10/12 位平面格式（存储在 16 位字中）
    PixelFormat.BAYER_GR10: (cv2.COLOR_BAYER_GB2BGR, 16, 1),
    PixelFormat.BAYER_RG10: (cv2.COLOR_BAYER_BG2BGR, 16, 1),
    PixelFormat.BAYER_GB10: (cv2.COLOR_BAYER_GR2BGR, 16, 1),
    PixelFormat.BAYER_BG10: (cv2.COLOR_BAYER_RG2BGR, 16, 1),
    PixelFormat.BAYER_GR12: (cv2.COLOR_BAYER_GB2BGR, 16, 1),
    PixelFormat.BAYER_RG12: (cv2.COLOR_BAYER_BG2BGR, 16, 1),
    PixelFormat.BAYER_GB12: (cv2.COLOR_BAYER_GR2BGR, 16, 1),
    PixelFormat.BAYER_BG12: (cv2.COLOR_BAYER_RG2BGR, 16, 1),
    # RGB/BGR – the SDK delivers these as packed interleaved
    # RGB/BGR ── SDK 以交织紧凑格式传递
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
# 需要自定义解包的紧凑型 Bayer/灰度格式
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
# 16 位 Bayer 转换码（10/12 位解包为 16 位）
# Same SDK↔OpenCV swap as _FORMAT_INFO above.
# 与上方 _FORMAT_INFO 相同的 SDK↔OpenCV 翻转映射。
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
# Public API / 公开接口
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
    将原始帧缓冲区转换为 numpy 数组。

    Parameters / 参数
    -----------------
    data:
        Raw pixel data – can be ``bytes``, a ctypes ``c_ubyte`` array,
        or an existing ``uint8`` numpy array.
        原始像素数据 ── 可为 ``bytes``、ctypes ``c_ubyte`` 数组或
        现有的 ``uint8`` numpy 数组。
    width:
        Image width in pixels. / 图像宽度（像素）。
    height:
        Image height in pixels. / 图像高度（像素）。
    pixel_format:
        Source pixel format (a :py:class:`~hikcamera.enums.PixelFormat`
        value or any raw integer from the SDK).
        源像素格式（:py:class:`~hikcamera.enums.PixelFormat` 值或 SDK 的原始整数值）。
    output_format:
        Desired output format (default BGR8 for OpenCV compatibility).
        期望的输出格式（默认 BGR8，兼容 OpenCV）。

    Returns / 返回
    --------------
    numpy.ndarray
        Decoded image in the requested format.
        按请求格式解码后的图像。

    Raises / 异常
    -------------
    PixelFormatError
        When *pixel_format* is not recognised.
        当 *pixel_format* 无法识别时抛出。
    ImageConversionError
        When an error occurs during conversion.
        当转换过程中发生错误时抛出。
    """
    # Normalise raw data to a uint8 numpy array
    # 将原始数据统一为 uint8 numpy 数组
    if isinstance(data, np.ndarray):
        buf: np.ndarray = data.view(np.uint8).ravel()
    elif isinstance(data, (bytes, bytearray)):
        buf = np.frombuffer(data, dtype=np.uint8)
    else:
        # ctypes array / ctypes 数组
        buf = np.ctypeslib.as_array(data).ravel()

    try:
        img = _decode(buf, width, height, pixel_format)
    except (PixelFormatError, ImageConversionError):
        raise
    except Exception as exc:
        raise ImageConversionError(f"Unexpected error during image decoding: {exc}") from exc

    return _to_output_format(img, output_format)


# ---------------------------------------------------------------------------
# Internal helpers / 内部辅助函数
# ---------------------------------------------------------------------------

def _decode(buf: np.ndarray, width: int, height: int, pixel_format: int) -> np.ndarray:
    """
    Decode raw bytes to a BGR/mono uint8/uint16 ndarray.
    将原始字节解码为 BGR/灰度 uint8/uint16 ndarray。
    """

    if pixel_format in _PACKED10_FORMATS:
        return _decode_packed10(buf, width, height, pixel_format)

    if pixel_format in _PACKED12_FORMATS:
        return _decode_packed12(buf, width, height, pixel_format)

    info = _FORMAT_INFO.get(pixel_format)
    if info is None:
        raise PixelFormatError(
            f"Unsupported pixel format: 0x{pixel_format:08X}. "
            "Use the SDK's MV_CC_ConvertPixelTypeEx to convert to a supported format."
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
        # 16 位小端序（10 或 12 位存储在 16 位字中）
        arr16 = buf.view(np.uint16).reshape(height, width)
        if cv2_code is not None:
            # cvtColor requires uint16 for 16-bit Bayer
            # cvtColor 对 16 位 Bayer 需要 uint16 类型
            return cv2.cvtColor(arr16, cv2_code)
        return arr16
    elif bpp in (10, 12):
        # Should have been caught above; fall through with error
        # 应在上方被捕获；此处直接报错
        pass

    raise PixelFormatError(f"Cannot decode pixel format 0x{pixel_format:08X}")


def _decode_packed10(buf: np.ndarray, width: int, height: int, pixel_format: int) -> np.ndarray:
    """
    Unpack 10-bit packed data.
    解包 10 位紧凑数据。

    The HIK/PFNC 10-bit packed format stores 4 pixels in 5 bytes:
    HIK/PFNC 10 位紧凑格式将 4 个像素存储在 5 个字节中：
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
    # 处理最后不完整组中剩余的 1–3 个像素
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
    解包 12 位紧凑数据。

    The HIK/PFNC 12-bit packed format stores 2 pixels in 3 bytes:
    HIK/PFNC 12 位紧凑格式将 2 个像素存储在 3 个字节中：
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
    # 当总像素数为奇数时处理最后一个像素
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
    将解码后的图像数组转换为请求的 :py:class:`OutputFormat`。

    Parameters / 参数
    -----------------
    img:
        Decoded source image (may be mono or BGR, 8-bit or 16-bit).
        解码后的源图像（可为灰度或 BGR，8 位或 16 位）。
    fmt:
        Requested output format. / 请求的输出格式。

    Returns / 返回
    --------------
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
