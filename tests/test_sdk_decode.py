"""
Tests for the SDK-backed decode pipeline (`_sdk_decode_frame`).
"""

from __future__ import annotations

import ctypes
from ctypes import c_ubyte
from unittest.mock import MagicMock

import numpy as np
import pytest

from hikcamera.enums import MvErrorCode, OutputFormat, PixelFormat
from hikcamera.exceptions import FeatureUnsupportedError, ImageConversionError
from hikcamera.sdk_wrapper import MV_CC_PIXEL_CONVERT_PARAM_EX


def _convert_side_effect(fill_byte: int = 0x55):
    """Return a side-effect that copies dummy data into the dst buffer."""

    def _side_effect(handle, p_params):
        params = ctypes.cast(p_params, ctypes.POINTER(MV_CC_PIXEL_CONVERT_PARAM_EX)).contents
        size = params.nDstBufferSize
        ctypes.memset(params.pDstBuffer, fill_byte, size)
        params.nDstLen = size
        return MvErrorCode.MV_OK

    return _side_effect


class TestSdkDecodeFormatSelection:
    @pytest.mark.parametrize(
        "output_format,expected_dst,expected_shape,expected_dtype",
        [
            (OutputFormat.MONO8, PixelFormat.MONO8, (4, 4), np.uint8),
            (OutputFormat.MONO16, PixelFormat.MONO16, (4, 4), np.uint16),
            (OutputFormat.BGR8, PixelFormat.BGR8_PACKED, (4, 4, 3), np.uint8),
            (OutputFormat.RGB8, PixelFormat.RGB8_PACKED, (4, 4, 3), np.uint8),
        ],
    )
    def test_destination_pixel_type_and_shape(
        self,
        camera_with_mock_sdk,
        output_format,
        expected_dst,
        expected_shape,
        expected_dtype,
    ):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_ConvertPixelTypeEx.side_effect = _convert_side_effect()

        # Use a Bayer source so SDK conversion is required.
        # 使用 Bayer 源以触发 SDK 转换。
        src_format = int(PixelFormat.BAYER_RG8)
        src_data = bytes([0xAA] * (4 * 4))
        out = cam._sdk_decode_frame(src_data, 4, 4, src_format, len(src_data), output_format)

        assert out.shape == expected_shape
        assert out.dtype == expected_dtype

        # Verify the SDK was invoked with the expected destination pixel type.
        # 验证调用 SDK 时使用了期望的目标像素类型。
        call = cam._sdk.MV_CC_ConvertPixelTypeEx.call_args
        params = ctypes.cast(call.args[1], ctypes.POINTER(MV_CC_PIXEL_CONVERT_PARAM_EX)).contents
        assert params.enDstPixelType == int(expected_dst)
        assert params.enSrcPixelType == src_format
        # Buffer sized exactly (no W*H*4 worst-case waste).
        # 目标缓冲区按精确大小分配（不再使用 W*H*4 的最差估算）。
        bpp = (1 if expected_dtype == np.uint8 else 2) * (
            expected_shape[2] if len(expected_shape) == 3 else 1
        )
        assert params.nDstBufferSize == 4 * 4 * bpp


class TestRgbaAlphaAppend:
    @pytest.mark.parametrize(
        "output_format,expected_dst",
        [
            (OutputFormat.BGRA8, PixelFormat.BGR8_PACKED),
            (OutputFormat.RGBA8, PixelFormat.RGB8_PACKED),
        ],
    )
    def test_alpha_channel_is_opaque(self, camera_with_mock_sdk, output_format, expected_dst):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_ConvertPixelTypeEx.side_effect = _convert_side_effect(fill_byte=0x42)

        src_data = bytes([0x00] * 16)
        out = cam._sdk_decode_frame(
            src_data, 4, 4, int(PixelFormat.BAYER_GB8), len(src_data), output_format
        )

        assert out.shape == (4, 4, 4)
        assert out.dtype == np.uint8
        # First three channels come from the SDK-mocked fill byte.
        # 前三个通道来自 SDK mock 填充的字节。
        assert (out[..., :3] == 0x42).all()
        # Alpha channel is fully opaque.
        # alpha 通道完全不透明。
        assert (out[..., 3] == 0xFF).all()

        call = cam._sdk.MV_CC_ConvertPixelTypeEx.call_args
        params = ctypes.cast(call.args[1], ctypes.POINTER(MV_CC_PIXEL_CONVERT_PARAM_EX)).contents
        assert params.enDstPixelType == int(expected_dst)


class TestPassthroughAvoidsSdkCall:
    def test_mono8_to_mono8_passthrough(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_ConvertPixelTypeEx.reset_mock()

        data = np.arange(16, dtype=np.uint8).tobytes()
        out = cam._sdk_decode_frame(
            data, 4, 4, int(PixelFormat.MONO8), len(data), OutputFormat.MONO8
        )

        cam._sdk.MV_CC_ConvertPixelTypeEx.assert_not_called()
        assert out.shape == (4, 4)
        assert out.dtype == np.uint8
        assert out[0, 1] == 1

    def test_bgr8_to_bgr8_passthrough(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_ConvertPixelTypeEx.reset_mock()

        data = bytes([7] * (4 * 4 * 3))
        out = cam._sdk_decode_frame(
            data, 4, 4, int(PixelFormat.BGR8_PACKED), len(data), OutputFormat.BGR8
        )

        cam._sdk.MV_CC_ConvertPixelTypeEx.assert_not_called()
        assert out.shape == (4, 4, 3)
        assert (out == 7).all()


class TestDecodeFallback:
    def test_falls_back_when_sdk_returns_error(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_ConvertPixelTypeEx.side_effect = None
        cam._sdk.MV_CC_ConvertPixelTypeEx.return_value = MvErrorCode.MV_E_SUPPORT

        # Build a valid MONO8 buffer; OpenCV fallback in raw_to_numpy should
        # successfully reshape it.
        # 构造有效的 MONO8 缓冲区；raw_to_numpy 中的 OpenCV 回退应能成功重塑。
        data = np.full(16, 0x33, dtype=np.uint8)
        from hikcamera.sdk_wrapper import MV_FRAME_OUT_INFO_EX

        fi = MV_FRAME_OUT_INFO_EX()
        fi.nWidth = 4
        fi.nHeight = 4
        fi.enPixelType = int(PixelFormat.MONO8)
        fi.nFrameLen = 16
        buf_ctypes = (c_ubyte * 16)(*data.tolist())

        out = cam._decode_frame(buf_ctypes, fi, OutputFormat.MONO8)
        assert out.shape == (4, 4)

    def test_falls_back_when_symbol_missing(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        # Simulate older SDK without ConvertPixelTypeEx.
        # 模拟未导出 ConvertPixelTypeEx 的旧版 SDK。
        del cam._sdk.MV_CC_ConvertPixelTypeEx

        data = np.full(16, 0x44, dtype=np.uint8)
        from hikcamera.sdk_wrapper import MV_FRAME_OUT_INFO_EX

        fi = MV_FRAME_OUT_INFO_EX()
        fi.nWidth = 4
        fi.nHeight = 4
        # Use a Bayer source so the SDK pipeline is actually attempted.
        # 使用 Bayer 源以确保会尝试 SDK 管线。
        fi.enPixelType = int(PixelFormat.BAYER_RG8)
        fi.nFrameLen = 16
        buf_ctypes = (c_ubyte * 16)(*data.tolist())

        # Should not raise – falls back to raw_to_numpy (OpenCV).
        # 不应抛异常 ── 回退到 raw_to_numpy（OpenCV）。
        out = cam._decode_frame(buf_ctypes, fi, OutputFormat.BGR8)
        assert out.shape == (4, 4, 3)

    def test_use_sdk_decode_false_skips_sdk(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam.set_use_sdk_decode(False)
        cam._sdk.MV_CC_ConvertPixelTypeEx.reset_mock()

        data = np.full(16, 0x55, dtype=np.uint8)
        from hikcamera.sdk_wrapper import MV_FRAME_OUT_INFO_EX

        fi = MV_FRAME_OUT_INFO_EX()
        fi.nWidth = 4
        fi.nHeight = 4
        fi.enPixelType = int(PixelFormat.MONO8)
        fi.nFrameLen = 16
        buf_ctypes = (c_ubyte * 16)(*data.tolist())

        cam._decode_frame(buf_ctypes, fi, OutputFormat.MONO8)
        cam._sdk.MV_CC_ConvertPixelTypeEx.assert_not_called()


class TestHbDecode:
    def test_hb_decode_runs_before_pixel_conversion(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk

        # Install a mock MV_CC_HB_Decode that fills the dst buf and reports
        # a normal MONO8 output type.
        # 安装一个 mock MV_CC_HB_Decode：填充 dst 缓冲区并报告 MONO8 输出。
        from hikcamera.sdk_wrapper import MV_CC_HB_DECODE_PARAM

        call_order: list[str] = []

        def hb_side_effect(handle, p_params):
            call_order.append("hb")
            params = ctypes.cast(
                p_params, ctypes.POINTER(MV_CC_HB_DECODE_PARAM)
            ).contents
            ctypes.memset(params.pDstBuf, 0x77, 16)
            params.nDstBufLen = 16
            params.enDstPixelType = int(PixelFormat.MONO8)
            return MvErrorCode.MV_OK

        cam._sdk.MV_CC_HB_Decode = MagicMock(side_effect=hb_side_effect)

        def convert_side_effect(handle, p_params):
            call_order.append("convert")
            return _convert_side_effect()(handle, p_params)

        cam._sdk.MV_CC_ConvertPixelTypeEx.side_effect = convert_side_effect

        # 0x80000000 is the HB-coded pixel-type prefix.
        # 0x80000000 是 HB 编码像素类型的前缀。
        hb_pixel_type = 0x80000001
        src_data = bytes([0x00] * 16)
        out = cam._sdk_decode_frame(
            src_data, 4, 4, hb_pixel_type, len(src_data), OutputFormat.MONO8
        )

        assert call_order[0] == "hb"
        # MONO8 source after HB decode → MONO8 dest is a passthrough, so the
        # convert function is *not* called for this particular case.
        # HB 解码后 MONO8 → MONO8 为直通，因此本例不会再次调用 convert。
        assert "convert" not in call_order
        assert out.shape == (4, 4)
        assert (out == 0x77).all()

    def test_hb_decode_allocates_safe_buffer_for_multichannel_outputs(
        self, camera_with_mock_sdk
    ):
        cam = camera_with_mock_sdk

        from hikcamera.sdk_wrapper import MV_CC_HB_DECODE_PARAM

        captured: dict[str, int] = {}

        def hb_side_effect(handle, p_params):
            params = ctypes.cast(
                p_params, ctypes.POINTER(MV_CC_HB_DECODE_PARAM)
            ).contents
            captured["dst_size"] = int(params.nDstBufSize)
            ctypes.memset(params.pDstBuf, 0x12, 4 * 4 * 3)
            params.nDstBufLen = 4 * 4 * 3
            params.enDstPixelType = int(PixelFormat.RGB8_PACKED)
            return MvErrorCode.MV_OK

        cam._sdk.MV_CC_HB_Decode = MagicMock(side_effect=hb_side_effect)
        out = cam._sdk_decode_frame(
            b"\x00" * 16, 4, 4, 0x80000001, 16, OutputFormat.RGB8
        )

        assert captured["dst_size"] == 4 * 4 * 4
        assert out.shape == (4, 4, 3)
        assert (out == 0x12).all()

    def test_hb_decode_rejects_invalid_reported_output_length(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk

        from hikcamera.sdk_wrapper import MV_CC_HB_DECODE_PARAM

        def hb_side_effect(handle, p_params):
            params = ctypes.cast(
                p_params, ctypes.POINTER(MV_CC_HB_DECODE_PARAM)
            ).contents
            params.nDstBufLen = params.nDstBufSize + 1
            params.enDstPixelType = int(PixelFormat.MONO8)
            return MvErrorCode.MV_OK

        cam._sdk.MV_CC_HB_Decode = MagicMock(side_effect=hb_side_effect)

        with pytest.raises(ImageConversionError, match="invalid output length"):
            cam._sdk_decode_frame(b"\x00" * 16, 4, 4, 0x80000001, 16, OutputFormat.MONO8)

    def test_hb_decode_missing_raises_unsupported(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        # Ensure HB symbol is missing.
        # 确保 HB 符号缺失。
        if hasattr(cam._sdk, "MV_CC_HB_Decode"):
            del cam._sdk.MV_CC_HB_Decode
        with pytest.raises(FeatureUnsupportedError):
            cam._sdk_decode_frame(
                b"\x00" * 16, 4, 4, 0x80000001, 16, OutputFormat.MONO8
            )
