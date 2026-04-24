from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from hikcamera.enums import Hik


def _load_demo_module(name: str):
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "demos" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"demo_{name}", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeRecordingSession:
    def __init__(self) -> None:
        self.write = MagicMock()

    def __enter__(self) -> _FakeRecordingSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeCamera:
    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame
        self.open = MagicMock()
        self.start_grabbing = MagicMock()
        self.stop_grabbing = MagicMock()
        self.save_image_to_file = MagicMock()
        self.record_session = _FakeRecordingSession()
        self.record = MagicMock(return_value=self.record_session)
        self.params = SimpleNamespace(
            AcquisitionControl=SimpleNamespace(ExposureTime=SimpleNamespace(set=MagicMock())),
            AnalogControl=SimpleNamespace(Gain=SimpleNamespace(set=MagicMock())),
        )
        self._get_frame_calls = 0

    def __enter__(self) -> _FakeCamera:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get_frame(self, *args, **kwargs) -> np.ndarray:
        self._get_frame_calls += 1
        return self._frame.copy()


def test_save_image_demo_runs_without_explicit_bayer_quality(tmp_path, monkeypatch) -> None:
    module = _load_demo_module("save_image")
    fake_cam = _FakeCamera(np.zeros((4, 6, 3), dtype=np.uint8))

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            ip=None,
            sn="DA4860722",
            output=str(tmp_path / "image.png"),
            format="BGR8",
            timeout=1000,
            exposure=None,
            gain=None,
        ),
    )
    monkeypatch.setattr(module.HikCamera, "from_serial_number", lambda sn: fake_cam)

    module.main()

    fake_cam.open.assert_called_once_with(Hik.AccessMode.EXCLUSIVE)
    fake_cam.start_grabbing.assert_called_once()
    fake_cam.stop_grabbing.assert_called_once()
    fake_cam.save_image_to_file.assert_called_once()


def test_save_video_demo_records_first_frame_and_stops_grabbing(tmp_path, monkeypatch) -> None:
    module = _load_demo_module("save_video")
    fake_cam = _FakeCamera(np.zeros((4, 6, 3), dtype=np.uint8))

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            ip=None,
            sn="DA4860722",
            output=str(tmp_path / "video.mp4"),
            fps=25.0,
            duration=0.0,
            exposure=None,
            gain=None,
        ),
    )
    monkeypatch.setattr(module.HikCamera, "from_serial_number", lambda sn: fake_cam)
    monotonic = iter([10.0, 10.1])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(monotonic))

    module.main()

    fake_cam.open.assert_called_once_with(Hik.AccessMode.EXCLUSIVE)
    fake_cam.start_grabbing.assert_called_once()
    fake_cam.stop_grabbing.assert_called_once()
    fake_cam.record.assert_called_once_with(
        Path(tmp_path / "video.mp4"),
        fps=25.0,
        width=6,
        height=4,
        fmt=Hik.RecordFormat.MP4,
    )
    fake_cam.record_session.write.assert_called_once()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("out.mp4", Hik.RecordFormat.MP4),
        ("out.avi", Hik.RecordFormat.AVI),
        ("out", Hik.RecordFormat.MP4),
    ],
)
def test_save_video_demo_infers_record_format(path: str, expected: Hik.RecordFormat) -> None:
    module = _load_demo_module("save_video")
    assert module.infer_record_format(path) == expected


def test_save_video_demo_rejects_unknown_record_extension() -> None:
    module = _load_demo_module("save_video")
    with pytest.raises(ValueError):
        module.infer_record_format("out.mkv")
