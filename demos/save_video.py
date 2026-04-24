"""
Demo: Capture a sequence of frames and save them as a video file.
演示：捕获一系列帧并保存为视频文件。

Frames are pulled from the SDK in polling mode and written to disk via
OpenCV's :class:`cv2.VideoWriter`.  This keeps the demo robust on every
platform (the SDK ``MV_CC_StartRecord`` MP4 path requires a separately
shipped ``MvFFmpegPlugin``; if the plugin is missing the SDK call can
block indefinitely while still holding the Python GIL, which also breaks
Ctrl+C).  Polling with a short timeout returns control to Python every
~200 ms so signals are delivered promptly.
帧通过 SDK 轮询模式获取，并通过 OpenCV 的 :class:`cv2.VideoWriter` 写入磁盘。
SDK 的 ``MV_CC_StartRecord`` MP4 路径在 Windows 上需要厂商单独提供的
``MvFFmpegPlugin``，缺少插件时该调用可能在 SDK 内部长时间阻塞并持有 GIL，
导致 Ctrl+C 也无法响应；用 OpenCV 录制可彻底规避该依赖，并配合短超时轮询，
使 Python 每 ~200 ms 取回一次控制权，保证 Ctrl+C 立即生效。

Usage / 用法::

    python save_video.py [--ip IP] [--sn SN] [--output PATH]
                         [--fps FPS] [--duration SECONDS]

Run ``pip install hikcamera`` (or ``pip install -e .`` from the repo root)
before executing this script.
执行此脚本前请先运行 ``pip install hikcamera``（或在仓库根目录下执行
``pip install -e .``）。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

from hikcamera import (
    FrameTimeoutError,
    Hik,
    HikCamera,
    HikCameraError,
    SDKNotFoundError,
)

# Map of output extensions to OpenCV FourCC codes.  ``mp4v`` is bundled with
# opencv-python on every platform; ``MJPG`` is the most portable AVI codec.
# 输出扩展名到 OpenCV FourCC 编码的映射。``mp4v`` 在所有平台上的
# opencv-python 均自带；``MJPG`` 是最通用的 AVI 编码。
_FOURCC_BY_EXTENSION: dict[str, str] = {
    ".mp4": "mp4v",
    ".m4v": "mp4v",
    ".mov": "mp4v",
    ".mkv": "mp4v",
    ".avi": "MJPG",
}


def fourcc_for_path(path: str | Path) -> str:
    """
    Return the OpenCV FourCC code matching *path*'s extension.
    返回与 *path* 扩展名对应的 OpenCV FourCC 编码。
    """
    suffix = Path(path).suffix.lower() or ".mp4"
    try:
        return _FOURCC_BY_EXTENSION[suffix]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported video extension {suffix!r}; "
            f"use one of {sorted(_FOURCC_BY_EXTENSION)}"
        ) from exc


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
    parser.add_argument("--fps", type=float, default=25.0, help="Video frame rate (default: 25)")
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Recording duration in seconds (default: 10)",
    )
    parser.add_argument("--exposure", type=float, help="Exposure time in µs")
    parser.add_argument("--gain", type=float, help="Analogue gain value")
    return parser.parse_args()


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
    output_path = Path(args.output)
    total_frames = 0
    writer: cv2.VideoWriter | None = None

    with cam:
        cam.open(Hik.AccessMode.EXCLUSIVE)
        print("Camera opened.")
        # Only create the output directory once the camera has opened, so a
        # failed connection does not leave behind empty directories.
        # 仅在相机成功打开后再创建输出目录，避免连接失败时遗留空目录。
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.exposure is not None:
            cam.params.AcquisitionControl.ExposureTime.set(args.exposure)
        if args.gain is not None:
            cam.params.AnalogControl.Gain.set(args.gain)

        cam.start_grabbing()
        print(f"Grabbing started. Recording for {args.duration:.1f} seconds …")
        try:
            # Grab the first frame to determine image dimensions
            # 抓取第一帧以确定图像尺寸
            first_frame = cam.get_frame(timeout_ms=5000, output_format=Hik.OutputFormat.BGR8)
            h, w = first_frame.shape[:2]
            print(f"Frame size: {w}×{h}")

            # -----------------------------------------------------------
            # Open the video writer / 打开视频写入器
            # -----------------------------------------------------------
            fourcc = cv2.VideoWriter_fourcc(*fourcc_for_path(output_path))
            writer = cv2.VideoWriter(str(output_path), fourcc, args.fps, (w, h))
            if not writer.isOpened():
                print(f"Failed to open VideoWriter for {output_path}")
                sys.exit(1)

            writer.write(first_frame)
            total_frames = 1
            end_time = time.monotonic() + args.duration

            try:
                # Cache the current time once per loop iteration so timeout
                # calculations stay consistent and avoid redundant calls.
                # 每轮循环缓存一次当前时间，便于保持超时计算一致并避免重复调用。
                now = time.monotonic()
                while now < end_time:
                    # Short timeout keeps Python responsive to Ctrl+C between frames.
                    # 短超时使主线程在帧间隔间能及时响应 Ctrl+C。
                    try:
                        frame = cam.get_frame(
                            timeout_ms=200,
                            output_format=Hik.OutputFormat.BGR8,
                        )
                    except FrameTimeoutError:
                        now = time.monotonic()
                        continue
                    writer.write(frame)
                    total_frames += 1
                    now = time.monotonic()
            except KeyboardInterrupt:
                print("\nCtrl+C received. Stopping recording …")
        finally:
            if writer is not None:
                writer.release()
            try:
                cam.stop_grabbing()
            except HikCameraError as exc:
                print(f"Error while stopping grabbing: {exc}")

    print(
        f"Video saved to {output_path}  "
        f"({total_frames} frames, {args.fps:.1f} fps requested)"
    )


if __name__ == "__main__":
    main()
