"""
Tests for the SDK-backed video recording lifecycle.
"""

from __future__ import annotations

import ctypes
from unittest.mock import MagicMock

import numpy as np
import pytest

from hikcamera.enums import Hik, MvErrorCode, PixelFormat, RecordFormat
from hikcamera.exceptions import FeatureUnsupportedError, HikCameraError
from hikcamera.sdk_wrapper import (
    MV_CC_INPUT_FRAME_INFO,
    MV_CC_RECORD_PARAM,
)


@pytest.fixture()
def recording_camera(camera_with_mock_sdk):
    cam = camera_with_mock_sdk
    cam._sdk.MV_CC_StartRecord = MagicMock(return_value=MvErrorCode.MV_OK)
    cam._sdk.MV_CC_InputOneFrame = MagicMock(return_value=MvErrorCode.MV_OK)
    cam._sdk.MV_CC_StopRecord = MagicMock(return_value=MvErrorCode.MV_OK)
    return cam


class TestRecordContextManager:
    def test_lifecycle_calls_start_input_stop(self, recording_camera, tmp_path):
        cam = recording_camera
        out = tmp_path / "out.mp4"

        captured: dict = {}

        def start_side_effect(handle, p_params):
            params = ctypes.cast(p_params, ctypes.POINTER(MV_CC_RECORD_PARAM)).contents
            captured["w"] = int(params.nWidth)
            captured["h"] = int(params.nHeight)
            captured["fps"] = float(params.fFrameRate)
            captured["fmt"] = int(params.enRecordFmtType)
            captured["pixel"] = int(params.enPixelType)
            captured["path"] = bytes(params.strFilePath).rstrip(b"\x00")
            return MvErrorCode.MV_OK

        def input_side_effect(handle, p_params):
            params = ctypes.cast(
                p_params, ctypes.POINTER(MV_CC_INPUT_FRAME_INFO)
            ).contents
            captured.setdefault("frame_lens", []).append(int(params.nDataLen))
            return MvErrorCode.MV_OK

        cam._sdk.MV_CC_StartRecord.side_effect = start_side_effect
        cam._sdk.MV_CC_InputOneFrame.side_effect = input_side_effect

        with cam.record(out, fps=30.0, width=8, height=4, fmt=RecordFormat.MP4) as rec:
            for _ in range(3):
                rec.write(np.zeros((4, 8, 3), dtype=np.uint8))

        assert cam._sdk.MV_CC_StartRecord.call_count == 1
        assert cam._sdk.MV_CC_InputOneFrame.call_count == 3
        assert cam._sdk.MV_CC_StopRecord.call_count == 1
        assert captured["w"] == 8
        assert captured["h"] == 4
        assert captured["fps"] == 30.0
        assert captured["fmt"] == int(RecordFormat.MP4)
        assert captured["pixel"] == int(PixelFormat.BGR8_PACKED)
        assert captured["path"] == str(out).encode()
        assert captured["frame_lens"] == [4 * 8 * 3] * 3
        assert cam._is_recording is False

    def test_stop_called_on_exception(self, recording_camera, tmp_path):
        cam = recording_camera
        with pytest.raises(RuntimeError):
            with cam.record(tmp_path / "x.mp4", fps=10, width=4, height=4):
                raise RuntimeError("boom")
        cam._sdk.MV_CC_StopRecord.assert_called_once()
        assert cam._is_recording is False


class TestRecordExplicitMethods:
    def test_start_then_stop(self, recording_camera, tmp_path):
        cam = recording_camera
        cam.start_record(tmp_path / "y.avi", fps=15.0, width=2, height=2,
                         fmt=Hik.RecordFormat.AVI)
        assert cam._is_recording is True
        cam.stop_record()
        assert cam._is_recording is False

    def test_double_start_raises(self, recording_camera, tmp_path):
        cam = recording_camera
        cam.start_record(tmp_path / "z.mp4", fps=15.0, width=2, height=2)
        with pytest.raises(HikCameraError):
            cam.start_record(tmp_path / "z2.mp4", fps=15.0, width=2, height=2)
        cam.stop_record()

    def test_input_without_start_raises(self, recording_camera):
        cam = recording_camera
        with pytest.raises(HikCameraError):
            cam.input_recorded_frame(np.zeros((2, 2, 3), dtype=np.uint8))

    def test_missing_start_symbol_raises_unsupported(self, camera_with_mock_sdk, tmp_path):
        cam = camera_with_mock_sdk
        if hasattr(cam._sdk, "MV_CC_StartRecord"):
            del cam._sdk.MV_CC_StartRecord
        with pytest.raises(FeatureUnsupportedError):
            cam.start_record(tmp_path / "x.mp4", fps=10.0, width=2, height=2)
