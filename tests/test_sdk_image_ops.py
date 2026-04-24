"""
Tests for SDK-backed image operations: rotate, flip, save, encode, plus
Bayer pipeline tuning helpers.
"""

from __future__ import annotations

import ctypes
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import hikcamera.camera as camera_module
from hikcamera.enums import (
    BayerCvtQuality,
    FlipDirection,
    Hik,
    ImageFileFormat,
    MvErrorCode,
    PixelFormat,
    RotateAngle,
)
from hikcamera.exceptions import FeatureUnsupportedError, PixelFormatError
from hikcamera.sdk_wrapper import (
    MV_CC_FLIP_IMAGE_PARAM,
    MV_CC_ROTATE_IMAGE_PARAM,
    MV_SAVE_IMAGE_PARAM_EX3,
    MV_SAVE_IMG_TO_FILE_PARAM_EX,
)

# ---------------------------------------------------------------------------
# rotate_image
# ---------------------------------------------------------------------------

class TestRotateImage:
    def test_rotate_calls_sdk_with_correct_params(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        captured: dict = {}

        def side_effect(handle, p_params):
            params = ctypes.cast(
                p_params, ctypes.POINTER(MV_CC_ROTATE_IMAGE_PARAM)
            ).contents
            captured["angle"] = int(params.enRotationAngle)
            captured["pixel_type"] = int(params.enPixelType)
            captured["w"] = int(params.nWidth)
            captured["h"] = int(params.nHeight)
            ctypes.memset(params.pDstBuf, 0xAB, params.nDstBufSize)
            params.nDstBufLen = params.nDstBufSize
            return MvErrorCode.MV_OK

        cam._sdk.MV_CC_RotateImage = MagicMock(side_effect=side_effect)
        img = np.zeros((4, 6, 3), dtype=np.uint8)
        out = cam.rotate_image(img, RotateAngle.DEG_90)

        assert captured["angle"] == int(RotateAngle.DEG_90)
        assert captured["pixel_type"] == int(PixelFormat.BGR8_PACKED)
        assert captured["w"] == 6
        assert captured["h"] == 4
        # 90° rotation swaps width and height.
        # 90° 旋转交换宽高。
        assert out.shape == (6, 4, 3)

    def test_rotate_180_keeps_dimensions(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_RotateImage = MagicMock(return_value=MvErrorCode.MV_OK)
        img = np.zeros((3, 5), dtype=np.uint8)
        out = cam.rotate_image(img, RotateAngle.DEG_180)
        assert out.shape == (3, 5)

    def test_rotate_rejects_unsupported_dtype(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        with pytest.raises(PixelFormatError):
            cam.rotate_image(np.zeros((4, 4), dtype=np.uint16), RotateAngle.DEG_90)

    def test_rotate_rejects_wrong_channel_count(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        with pytest.raises(PixelFormatError):
            cam.rotate_image(np.zeros((4, 4, 4), dtype=np.uint8), RotateAngle.DEG_90)

    def test_rotate_unsupported_when_symbol_missing(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        if hasattr(cam._sdk, "MV_CC_RotateImage"):
            del cam._sdk.MV_CC_RotateImage
        with pytest.raises(FeatureUnsupportedError):
            cam.rotate_image(np.zeros((4, 4), dtype=np.uint8), RotateAngle.DEG_90)


# ---------------------------------------------------------------------------
# flip_image
# ---------------------------------------------------------------------------

class TestFlipImage:
    def test_flip_calls_sdk_with_correct_direction(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        captured: dict = {}

        def side_effect(handle, p_params):
            params = ctypes.cast(
                p_params, ctypes.POINTER(MV_CC_FLIP_IMAGE_PARAM)
            ).contents
            captured["dir"] = int(params.enFlipType)
            return MvErrorCode.MV_OK

        cam._sdk.MV_CC_FlipImage = MagicMock(side_effect=side_effect)
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        out = cam.flip_image(img, FlipDirection.VERTICAL)
        assert captured["dir"] == int(FlipDirection.VERTICAL)
        assert out.shape == (4, 4, 3)

    def test_flip_rejects_invalid_dtype(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        with pytest.raises(PixelFormatError):
            cam.flip_image(np.zeros((4, 4), dtype=np.float32), FlipDirection.HORIZONTAL)


# ---------------------------------------------------------------------------
# save_image_to_file
# ---------------------------------------------------------------------------

class TestSaveImageToFile:
    @pytest.mark.parametrize(
        "ext,expected_fmt",
        [
            (".png", ImageFileFormat.PNG),
            (".jpg", ImageFileFormat.JPEG),
            (".jpeg", ImageFileFormat.JPEG),
            (".bmp", ImageFileFormat.BMP),
            (".tif", ImageFileFormat.TIFF),
            (".tiff", ImageFileFormat.TIFF),
        ],
    )
    def test_format_inferred_from_extension(self, camera_with_mock_sdk, tmp_path, ext, expected_fmt):
        cam = camera_with_mock_sdk
        captured: dict = {}

        def side_effect(handle, p_params):
            params = ctypes.cast(
                p_params, ctypes.POINTER(MV_SAVE_IMG_TO_FILE_PARAM_EX)
            ).contents
            captured["fmt"] = int(params.enImageType)
            captured["path"] = bytes(params.pImagePath).rstrip(b"\x00")
            captured["pixel_type"] = int(params.enPixelType)
            captured["w"] = int(params.nWidth)
            captured["h"] = int(params.nHeight)
            return MvErrorCode.MV_OK

        cam._sdk.MV_CC_SaveImageToFileEx = MagicMock(side_effect=side_effect)
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        out_path = tmp_path / f"image{ext}"
        cam.save_image_to_file(img, out_path)
        assert captured["fmt"] == int(expected_fmt)
        assert captured["path"] == str(out_path).encode()
        assert captured["pixel_type"] == int(PixelFormat.BGR8_PACKED)
        assert captured["w"] == 4
        assert captured["h"] == 4

    def test_unknown_extension_requires_explicit_fmt(self, camera_with_mock_sdk, tmp_path):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_SaveImageToFileEx = MagicMock(return_value=MvErrorCode.MV_OK)
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        with pytest.raises(ValueError):
            cam.save_image_to_file(img, tmp_path / "image.xyz")

    def test_save_propagates_sdk_error(self, camera_with_mock_sdk, tmp_path):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_SaveImageToFileEx = MagicMock(return_value=MvErrorCode.MV_E_PARAMETER)
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        with patch.object(camera_module.cv2, "imwrite", return_value=True) as fallback:
            cam.save_image_to_file(img, tmp_path / "image.png")
        fallback.assert_called_once()

    def test_save_falls_back_when_camera_is_closed(self, camera_with_mock_sdk, tmp_path):
        cam = camera_with_mock_sdk
        cam._is_open = False
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        with patch.object(camera_module.cv2, "imwrite", return_value=True) as fallback:
            cam.save_image_to_file(img, tmp_path / "image.png")
        fallback.assert_called_once()


# ---------------------------------------------------------------------------
# encode_image
# ---------------------------------------------------------------------------

class TestEncodeImage:
    def test_encode_returns_bytes(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk

        encoded_bytes = b"\xFF\xD8\xFF\xE0DUMMY-JPEG"

        def side_effect(handle, p_params):
            params = ctypes.cast(
                p_params, ctypes.POINTER(MV_SAVE_IMAGE_PARAM_EX3)
            ).contents
            for i, b in enumerate(encoded_bytes):
                params.pImageBuffer[i] = b
            params.nImageLen = len(encoded_bytes)
            return MvErrorCode.MV_OK

        cam._sdk.MV_CC_SaveImageEx3 = MagicMock(side_effect=side_effect)
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        out = cam.encode_image(img, ImageFileFormat.JPEG, jpeg_quality=80)
        assert out == encoded_bytes


# ---------------------------------------------------------------------------
# Bayer pipeline tuning
# ---------------------------------------------------------------------------

class TestBayerCvtQuality:
    def test_set_bayer_cvt_quality_calls_sdk(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_SetBayerCvtQuality = MagicMock(return_value=MvErrorCode.MV_OK)
        cam.set_bayer_cvt_quality(BayerCvtQuality.BEST)
        cam._sdk.MV_CC_SetBayerCvtQuality.assert_called_once()
        args = cam._sdk.MV_CC_SetBayerCvtQuality.call_args.args
        assert int(args[1].value) == int(BayerCvtQuality.BEST) == 2

    def test_open_applies_best_default(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._is_open = False  # exercise the open() path
        cam._sdk.MV_CC_OpenDevice = MagicMock(return_value=MvErrorCode.MV_OK)
        cam._sdk.MV_CC_SetBayerCvtQuality = MagicMock(return_value=MvErrorCode.MV_OK)
        # Use a fixed packet size to avoid GigE auto-detection.
        # 使用固定数据包大小，避免 GigE 自动检测。
        cam.open(Hik.AccessMode.EXCLUSIVE, packet_size=1500)
        cam._sdk.MV_CC_SetBayerCvtQuality.assert_called_once()
        args = cam._sdk.MV_CC_SetBayerCvtQuality.call_args.args
        assert int(args[1].value) == 2

    def test_missing_symbol_does_not_break_open(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._is_open = False
        cam._sdk.MV_CC_OpenDevice = MagicMock(return_value=MvErrorCode.MV_OK)
        if hasattr(cam._sdk, "MV_CC_SetBayerCvtQuality"):
            del cam._sdk.MV_CC_SetBayerCvtQuality
        cam.open(Hik.AccessMode.EXCLUSIVE, packet_size=1500)
        assert cam._is_open is True


class TestBayerFilterAndGamma:
    def test_set_bayer_filter_enable(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_SetBayerFilterEnable = MagicMock(return_value=MvErrorCode.MV_OK)
        cam.set_bayer_filter_enable(True)
        args = cam._sdk.MV_CC_SetBayerFilterEnable.call_args.args
        assert int(args[1].value) == 1

    def test_set_bayer_gamma_value(self, camera_with_mock_sdk):
        cam = camera_with_mock_sdk
        cam._sdk.MV_CC_SetBayerGammaValue = MagicMock(return_value=MvErrorCode.MV_OK)
        cam.set_bayer_gamma(0.45)
        args = cam._sdk.MV_CC_SetBayerGammaValue.call_args.args
        assert pytest.approx(float(args[1].value), abs=1e-5) == 0.45
