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

    def __init__(self, frame: np.ndarray, fps: float = 30.0) -> None:
        self._frame = frame
        h, w = frame.shape[:2]
        self.open = MagicMock()
        self.start_grabbing = MagicMock()
        self.stop_grabbing = MagicMock()
        self.params = SimpleNamespace(
            AcquisitionControl=SimpleNamespace(
                ExposureTime=SimpleNamespace(set=MagicMock()),
                ResultingFrameRate=SimpleNamespace(get=MagicMock(return_value=fps)),
                AcquisitionFrameRate=SimpleNamespace(get=MagicMock(return_value=fps)),
            ),
            AnalogControl=SimpleNamespace(Gain=SimpleNamespace(set=MagicMock())),
            ImageFormatControl=SimpleNamespace(
                Width=SimpleNamespace(get=MagicMock(return_value=w)),
                Height=SimpleNamespace(get=MagicMock(return_value=h)),
            ),
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
    imwrite = MagicMock(return_value=True)

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
    monkeypatch.setattr(module.cv2, "imwrite", imwrite)

    module.main()

    fake_cam.open.assert_called_once_with(Hik.AccessMode.EXCLUSIVE)
    fake_cam.start_grabbing.assert_called_once()
    fake_cam.stop_grabbing.assert_called_once()
    imwrite.assert_called_once()
    saved_path, saved_image = imwrite.call_args.args
    assert saved_path == str(tmp_path / "image.png")
    np.testing.assert_array_equal(saved_image, fake_cam._frame)


@pytest.mark.parametrize(
    ("fmt", "frame", "expected"),
    [
        (
            "RGB8",
            np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8),
            np.array([[[3, 2, 1], [6, 5, 4]]], dtype=np.uint8),
        ),
        (
            "RGBA8",
            np.array([[[1, 2, 3, 40], [4, 5, 6, 70]]], dtype=np.uint8),
            np.array([[[3, 2, 1, 40], [6, 5, 4, 70]]], dtype=np.uint8),
        ),
    ],
)
def test_save_image_demo_converts_rgb_channel_order_for_opencv(
    tmp_path, monkeypatch, fmt: str, frame: np.ndarray, expected: np.ndarray
) -> None:
    module = _load_demo_module("save_image")
    fake_cam = _FakeCamera(frame)
    imwrite = MagicMock(return_value=True)

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            ip=None,
            sn="DA4860722",
            output=str(tmp_path / "image.png"),
            format=fmt,
            timeout=1000,
            exposure=None,
            gain=None,
        ),
    )
    monkeypatch.setattr(module.HikCamera, "from_serial_number", lambda sn: fake_cam)
    monkeypatch.setattr(module.cv2, "imwrite", imwrite)

    module.main()

    saved_image = imwrite.call_args.args[1]
    np.testing.assert_array_equal(saved_image, expected)


def test_save_image_demo_raises_when_opencv_cannot_write(tmp_path, monkeypatch) -> None:
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
    monkeypatch.setattr(module.cv2, "imwrite", MagicMock(return_value=False))

    with pytest.raises(RuntimeError, match="Failed to save image"):
        module.main()


def test_save_video_demo_writes_frames_via_callback(tmp_path, monkeypatch) -> None:
    module = _load_demo_module("save_video")
    fake_cam = _FakeCamera(np.zeros((4, 6, 3), dtype=np.uint8), fps=30.0)

    output_path = tmp_path / "video.mp4"
    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            ip=None,
            sn="DA4860722",
            output=str(output_path),
            duration=0.2,
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

    # Capture the registered SDK callback so the test can synthesise frames.
    # 捕获注册的 SDK 回调，以便测试用例合成帧。
    captured: dict[str, object] = {}

    def _fake_start(callback, output_format):  # noqa: ARG001
        captured["callback"] = callback

    fake_cam.start_grabbing.side_effect = _fake_start
    monotonic_values = iter([100.0, 100.0, 100.1, 100.2, 100.2])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(monotonic_values))

    delivered = False

    def _fake_sleep(_s: float) -> None:
        nonlocal delivered
        if delivered:
            return
        delivered = True
        cb = captured["callback"]
        assert callable(cb)
        cb(np.zeros((4, 6, 3), dtype=np.uint8), {"frame_num": 1})
        cb(np.zeros((4, 6, 3), dtype=np.uint8), {"frame_num": 2})

    monkeypatch.setattr(module.time, "sleep", _fake_sleep)

    module.main()

    fake_cam.open.assert_called_once_with(Hik.AccessMode.EXCLUSIVE)
    fake_cam.start_grabbing.assert_called_once()
    fake_cam.stop_grabbing.assert_called_once()
    # FPS pulled from the camera (30.0), not from a CLI flag.
    # 帧率取自相机（30.0），而非 CLI 参数。
    writer_factory.assert_called_once_with(str(output_path), 0x7634706D, 30.0, (6, 4))
    fake_writer.release.assert_called_once()

    assert fake_writer.write.call_count == 2


def test_save_video_demo_ignores_callback_during_shutdown(tmp_path, monkeypatch) -> None:
    module = _load_demo_module("save_video")
    fake_cam = _FakeCamera(np.zeros((4, 6, 3), dtype=np.uint8), fps=30.0)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            ip=None,
            sn="DA4860722",
            output=str(tmp_path / "video.mp4"),
            duration=0.0,
            exposure=None,
            gain=None,
        ),
    )
    monkeypatch.setattr(module.HikCamera, "from_serial_number", lambda sn: fake_cam)

    fake_writer = MagicMock()
    fake_writer.isOpened.return_value = True
    monkeypatch.setattr(module.cv2, "VideoWriter", MagicMock(return_value=fake_writer))
    monkeypatch.setattr(module.cv2, "VideoWriter_fourcc", lambda *args: 0)

    def _fake_start(callback, output_format):  # noqa: ARG001
        captured["callback"] = callback

    def _fake_stop() -> None:
        cb = captured["callback"]
        assert callable(cb)
        cb(np.ones((4, 6, 3), dtype=np.uint8), {"frame_num": 99})

    fake_cam.start_grabbing.side_effect = _fake_start
    fake_cam.stop_grabbing.side_effect = _fake_stop
    monkeypatch.setattr(module.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)

    module.main()

    fake_writer.write.assert_not_called()
    fake_writer.release.assert_called_once()


def test_save_video_demo_aborts_when_writer_cannot_be_opened(
    tmp_path, monkeypatch, capsys
) -> None:
    module = _load_demo_module("save_video")
    fake_cam = _FakeCamera(np.zeros((4, 6, 3), dtype=np.uint8))

    monkeypatch.setattr(
        module,
        "parse_args",
        lambda: argparse.Namespace(
            ip=None,
            sn="DA4860722",
            output=str(tmp_path / "video.mp4"),
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

    captured = capsys.readouterr()
    assert "Failed to open VideoWriter for" in captured.out
    assert "codec mp4v" in captured.out
    assert "output path is writable" in captured.out
    assert "supports the requested codec" in captured.out
    assert ".avi suffix" in captured.out

    # Writer failed to open before grabbing started, so nothing to stop.
    # 写入器在开始取流之前失败，因此无需停止取流。
    fake_cam.start_grabbing.assert_not_called()
    fake_cam.stop_grabbing.assert_not_called()


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
