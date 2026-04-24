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


class _FakeCamera:
    """
    Minimal HikCamera stand-in covering only the surface used by the demos.
    覆盖 demo 所需 HikCamera 接口的最小替身。
    """

    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame
        self.open = MagicMock()
        self.start_grabbing = MagicMock()
        self.stop_grabbing = MagicMock()
        self.save_image_to_file = MagicMock()
        self.params = SimpleNamespace(
            AcquisitionControl=SimpleNamespace(ExposureTime=SimpleNamespace(set=MagicMock())),
            AnalogControl=SimpleNamespace(Gain=SimpleNamespace(set=MagicMock())),
        )

    def __enter__(self) -> _FakeCamera:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get_frame(self, *args, **kwargs) -> np.ndarray:
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


def test_save_video_demo_writes_first_frame_via_opencv(tmp_path, monkeypatch) -> None:
    module = _load_demo_module("save_video")
    fake_cam = _FakeCamera(np.zeros((4, 6, 3), dtype=np.uint8))

    output_path = tmp_path / "video.mp4"
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            ip=None,
            sn="DA4860722",
            output=str(output_path),
            fps=25.0,
            duration=0.0,
            exposure=None,
            gain=None,
        ),
    )
    monkeypatch.setattr(module.HikCamera, "from_serial_number", lambda sn: fake_cam)

    fake_writer = MagicMock()
    fake_writer.isOpened.return_value = True
    writer_factory = MagicMock(return_value=fake_writer)
    monkeypatch.setattr(module.cv2, "VideoWriter", writer_factory)
    monkeypatch.setattr(module.cv2, "VideoWriter_fourcc", lambda *args: 0x7634706D)
    # duration=0 means no second frame is read after the first one
    # duration=0 表示首帧之后不会再读取额外帧
    monkeypatch.setattr(module.time, "monotonic", lambda: 100.0)

    module.main()

    fake_cam.open.assert_called_once_with(Hik.AccessMode.EXCLUSIVE)
    fake_cam.start_grabbing.assert_called_once()
    fake_cam.stop_grabbing.assert_called_once()
    writer_factory.assert_called_once_with(str(output_path), 0x7634706D, 25.0, (6, 4))
    fake_writer.write.assert_called_once()
    fake_writer.release.assert_called_once()


def test_save_video_demo_aborts_when_writer_cannot_be_opened(tmp_path, monkeypatch) -> None:
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
            duration=1.0,
            exposure=None,
            gain=None,
        ),
    )
    monkeypatch.setattr(module.HikCamera, "from_serial_number", lambda sn: fake_cam)

    fake_writer = MagicMock()
    fake_writer.isOpened.return_value = False
    monkeypatch.setattr(module.cv2, "VideoWriter", MagicMock(return_value=fake_writer))
    monkeypatch.setattr(module.cv2, "VideoWriter_fourcc", lambda *args: 0)

    with pytest.raises(SystemExit):
        module.main()

    fake_cam.stop_grabbing.assert_called_once()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("out.mp4", "mp4v"),
        ("out.MP4", "mp4v"),
        ("out.mov", "mp4v"),
        ("out.mkv", "mp4v"),
        ("out.avi", "MJPG"),
        ("out", "mp4v"),
    ],
)
def test_save_video_demo_resolves_fourcc_for_extension(path: str, expected: str) -> None:
    module = _load_demo_module("save_video")
    assert module.fourcc_for_path(path) == expected


def test_save_video_demo_rejects_unknown_video_extension() -> None:
    module = _load_demo_module("save_video")
    with pytest.raises(ValueError):
        module.fourcc_for_path("out.xyz")
