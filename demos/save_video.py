"""
Demo: Capture a sequence of frames and save them as a video file.
演示：捕获一系列帧并保存为视频文件。

Frames are delivered from the SDK via a callback, while access to the OpenCV
writer is synchronised so shutdown cannot race with an in-flight callback. The
demo queries the camera for its actual ``ResultingFrameRate`` so the recorded
file plays back at the same rate the device produces frames — there is no
``--fps`` option to keep out of sync with reality.
帧由 SDK 通过回调推送，OpenCV 写入器的访问则通过锁同步，避免关闭阶段与正在
执行的回调发生竞争。Demo 会查询相机的 ``ResultingFrameRate`` 作为录制帧率，
使录像的播放速率与相机实际采集速率一致；不再提供 ``--fps`` 参数以避免人为
帧率与实际帧率不一致。

The OpenCV writer is used instead of the SDK ``MV_CC_StartRecord`` MP4 path
because that path requires the separately shipped ``MvFFmpegPlugin`` and can
block while holding the Python GIL when the plugin is missing.  The main
thread only sleeps in short increments so Ctrl+C is delivered promptly.
之所以使用 OpenCV 写入器而非 SDK 的 ``MV_CC_StartRecord`` MP4 录制路径，
是因为该路径需要厂商单独提供的 ``MvFFmpegPlugin``，缺失时可能在持有 GIL
的情况下阻塞。主线程仅做短暂休眠，确保 Ctrl+C 能立即响应。

Usage / 用法::

    python save_video.py [--ip IP] [--sn SN] [--output PATH]
                         [--duration SECONDS]

Run ``pip install hikcamera`` (or ``pip install -e .`` from the repo root)
before executing this script.
执行此脚本前请先运行 ``pip install hikcamera``（或在仓库根目录下执行
``pip install -e .``）。
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from hikcamera import (
    Hik,
    HikCamera,
    HikCameraError,
    SDKNotFoundError,
)

# Candidate FourCC codes to try for each output extension.  MP4 support varies
# by OpenCV build / OS codec pack, so the demo also falls back to MJPG-in-AVI
# when MP4-like paths cannot be opened.
# 每种输出扩展名要尝试的 FourCC 候选列表。不同 OpenCV 构建 / 操作系统的 MP4
# 支持差异较大，因此当 MP4 类路径无法打开时，Demo 还会回退到 AVI+MJPG。
_FOURCC_CANDIDATES_BY_EXTENSION: dict[str, tuple[str, ...]] = {
    ".mp4": ("mp4v",),
    ".m4v": ("mp4v",),
    ".mov": ("mp4v",),
    ".mkv": ("mp4v",),
    ".avi": ("MJPG",),
}


def fourcc_for_path(path: str | Path) -> str:
    """
    Return the OpenCV FourCC code matching *path*'s extension.
    返回与 *path* 扩展名对应的 OpenCV FourCC 编码。
    """
    suffix = Path(path).suffix.lower() or ".mp4"
    try:
        return _FOURCC_CANDIDATES_BY_EXTENSION[suffix][0]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported video extension {suffix!r}; "
            f"use one of {sorted(_FOURCC_CANDIDATES_BY_EXTENSION)}"
        ) from exc


def _writer_candidates(path: str | Path) -> list[tuple[Path, str]]:
    """
    Return candidate (path, fourcc) pairs for opening a VideoWriter.
    返回用于打开 VideoWriter 的候选 (path, fourcc) 组合。
    """
    output_path = Path(path)
    suffix = output_path.suffix.lower() or ".mp4"
    try:
        fourccs = _FOURCC_CANDIDATES_BY_EXTENSION[suffix]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported video extension {suffix!r}; "
            f"use one of {sorted(_FOURCC_CANDIDATES_BY_EXTENSION)}"
        ) from exc

    candidates = [(output_path, fourcc) for fourcc in fourccs]
    if suffix != ".avi":
        candidates.append((output_path.with_suffix(".avi"), "MJPG"))
    return candidates


def _open_video_writer(
    path: str | Path, fps: float, frame_size: tuple[int, int]
) -> tuple[cv2.VideoWriter, Path]:
    """
    Open a VideoWriter, falling back to a more portable AVI+MJPG output when
    the requested path cannot be opened on the current OpenCV build.
    在当前 OpenCV 构建无法打开请求的输出路径时，打开 VideoWriter 并回退到
    兼容性更好的 AVI+MJPG 输出。
    """
    attempted: list[str] = []
    for candidate_path, fourcc_name in _writer_candidates(path):
        writer = cv2.VideoWriter(
            str(candidate_path),
            cv2.VideoWriter_fourcc(*fourcc_name),
            fps,
            frame_size,
        )
        if writer.isOpened():
            return writer, candidate_path
        writer.release()
        attempted.append(f"{candidate_path.name} ({fourcc_name})")

    attempted_str = ", ".join(attempted)
    raise RuntimeError(
        f"Failed to open VideoWriter for {path}. Tried: {attempted_str}. "
        "Try passing --output with an .avi suffix if your OpenCV build lacks MP4 support."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture frames from a Hikvision camera and save as a video."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ip", help="Camera IP address (GigE)")
    group.add_argument("--sn", help="Camera serial number")
    parser.add_argument(
        "--output",
        default="captured_video.mp4",
        help="Output video file path (default: captured_video.mp4)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Recording duration in seconds (default: 10)",
    )
    parser.add_argument("--exposure", type=float, help="Exposure time in µs")
    parser.add_argument("--gain", type=float, help="Analogue gain value")
    return parser.parse_args()


def _resolve_camera_fps(cam: HikCamera) -> float:
    """
    Read the camera's actual frame rate.
    读取相机的实际帧率。

    Prefers ``ResultingFrameRate`` (the rate the device is actually
    delivering after exposure / bandwidth / trigger constraints) and falls
    back to ``AcquisitionFrameRate`` for cameras that do not expose the
    resulting node.
    优先读取 ``ResultingFrameRate``（相机在曝光、带宽、触发等约束下的实际
    采集帧率）；若相机不支持该节点，则回退至 ``AcquisitionFrameRate``。
    """
    acq = cam.params.AcquisitionControl
    for node in (acq.ResultingFrameRate, acq.AcquisitionFrameRate):
        try:
            value = float(node.get())
        except HikCameraError:
            continue
        if value > 0.0:
            return value
    raise HikCameraError(
        "Camera did not report a positive frame rate via ResultingFrameRate "
        "or AcquisitionFrameRate."
    )


def main() -> None:
    args = parse_args()

    # ---------------------------------------------------------------
    # Locate camera / 定位相机
    # ---------------------------------------------------------------
    try:
        if args.ip:
            print(f"Connecting to camera at IP {args.ip} …")
            cam = HikCamera.from_ip(args.ip, Hik.TransportLayer.GIGE)
        elif args.sn:
            print(f"Connecting to camera with serial number {args.sn} …")
            cam = HikCamera.from_serial_number(args.sn)
        else:
            print("Enumerating cameras …")
            devices = HikCamera.enumerate()
            if not devices:
                print("No cameras found. Check connections and SDK installation.")
                sys.exit(1)
            print(f"Found {len(devices)} camera(s): {devices}")
            cam = HikCamera.from_device_info(devices[0])
    except SDKNotFoundError as exc:
        print(f"SDK not found: {exc}")
        sys.exit(1)

    # ---------------------------------------------------------------
    # Open and start grabbing / 打开相机并开始取帧
    # ---------------------------------------------------------------
    requested_output_path = Path(args.output)
    output_path = requested_output_path
    writer: cv2.VideoWriter | None = None

    # Shared state between the SDK callback thread and main thread.
    # 在 SDK 回调线程与主线程之间共享的状态。
    state_lock = threading.Lock()
    frame_count = 0
    stopping = False

    with cam:
        cam.open(Hik.AccessMode.EXCLUSIVE)
        print("Camera opened.")
        # Only create the output directory once the camera has opened, so a
        # failed connection does not leave behind empty directories.
        # 仅在相机成功打开后再创建输出目录，避免连接失败时遗留空目录。
        requested_output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.exposure is not None:
            cam.params.AcquisitionControl.ExposureTime.set(args.exposure)
        if args.gain is not None:
            cam.params.AnalogControl.Gain.set(args.gain)

        # Determine frame size and FPS up-front so the writer can be opened
        # before the first callback arrives.
        # 在第一帧回调到达之前先确定帧尺寸与帧率，便于提前打开写入器。
        width = int(cam.params.ImageFormatControl.Width.get())
        height = int(cam.params.ImageFormatControl.Height.get())
        fps = _resolve_camera_fps(cam)
        print(f"Frame size: {width}×{height}")
        print(f"Camera frame rate: {fps:.2f} fps")

        try:
            writer, output_path = _open_video_writer(output_path, fps, (width, height))
        except RuntimeError as exc:
            print(str(exc))
            sys.exit(1)
        if output_path != requested_output_path:
            print(
                "VideoWriter for "
                f"{requested_output_path} was unavailable; falling back to {output_path}."
            )

        def on_frame(image: np.ndarray, _info: dict[str, Any]) -> None:
            """
            SDK callback: write each frame to the OpenCV writer.
            SDK 回调：将每一帧写入 OpenCV 写入器。
            """
            nonlocal frame_count
            with state_lock:
                if stopping or writer is None:
                    return
                try:
                    writer.write(image)
                    frame_count += 1
                except Exception:  # noqa: BLE001  # never let exceptions cross SDK thread
                    return

        cam.start_grabbing(callback=on_frame, output_format=Hik.OutputFormat.BGR8)
        print(f"Grabbing started. Recording for {args.duration:.1f} seconds …")
        try:
            end_time = time.monotonic() + args.duration
            try:
                # Sleep in small slices so KeyboardInterrupt is delivered
                # promptly between waits — frames are pushed by the callback
                # thread, no polling is needed here.
                # 以小步长休眠，确保等待之间能及时响应 KeyboardInterrupt；
                # 帧由回调线程推送，主线程无需轮询。
                while True:
                    remaining = end_time - time.monotonic()
                    if remaining <= 0:
                        break
                    time.sleep(min(0.1, remaining))
            except KeyboardInterrupt:
                print("\nCtrl+C received. Stopping recording …")
        finally:
            # Mark shutdown under the callback lock so the writer cannot race
            # with writer.release().
            # 在与回调相同的锁下标记关闭状态，确保不会与 writer.release() 竞争。
            with state_lock:
                stopping = True
            try:
                cam.stop_grabbing()
            except HikCameraError as exc:
                print(f"Error while stopping grabbing: {exc}")
            with state_lock:
                writer_to_release = writer
                writer = None
            # Release outside the lock so cleanup does not block the callback
            # path longer than necessary once the writer reference is detached.
            # 在锁外释放，避免在 writer 引用已摘除后仍长时间阻塞回调路径。
            if writer_to_release is not None:
                writer_to_release.release()

    with state_lock:
        total_frames = frame_count
    print(
        f"Video saved to {output_path}  "
        f"({total_frames} frames, {fps:.2f} fps)"
    )


if __name__ == "__main__":
    main()
