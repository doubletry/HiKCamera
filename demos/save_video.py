"""
Demo: Capture a sequence of frames and save them as a video file.
演示：捕获一系列帧并保存为视频文件。

Uses the SDK-backed :py:meth:`~hikcamera.HikCamera.record` context manager
together with polling-based acquisition for a simple, robust demo flow.
使用 SDK 提供的 :py:meth:`~hikcamera.HikCamera.record` 上下文管理器，
配合轮询取帧实现一个简单、稳健的示例流程。

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

from hikcamera import (
    FrameTimeoutError,
    Hik,
    HikCamera,
    HikCameraError,
    SDKNotFoundError,
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


def infer_record_format(path: str | Path) -> Hik.RecordFormat:
    """
    Infer the SDK recorder format from the output file extension.
    根据输出文件扩展名推断 SDK 录制格式。
    """
    suffix = Path(path).suffix.lower()
    if suffix == ".avi":
        return Hik.RecordFormat.AVI
    if suffix in {"", ".mp4"}:
        return Hik.RecordFormat.MP4
    raise ValueError(
        f"Cannot infer record format from extension {suffix!r}; "
        "use a .mp4 or .avi output path"
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
    with cam:
        cam.open(Hik.AccessMode.EXCLUSIVE)
        print("Camera opened.")

        if args.exposure is not None:
            cam.params.AcquisitionControl.ExposureTime.set(args.exposure)
        if args.gain is not None:
            cam.params.AnalogControl.Gain.set(args.gain)

        # Grab the first frame to get image dimensions
        # 抓取第一帧以获取图像尺寸
        cam.start_grabbing()
        print(f"Grabbing started. Recording for {args.duration:.1f} seconds …")
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        total_frames = 0
        try:
            first_frame = cam.get_frame(timeout_ms=5000, output_format=Hik.OutputFormat.BGR8)
            h, w = first_frame.shape[:2]
            print(f"Frame size: {w}×{h}")

            # -----------------------------------------------------------
            # Open the SDK recorder / 打开 SDK 录制器
            # -----------------------------------------------------------
            with cam.record(
                output_path,
                fps=args.fps,
                width=w,
                height=h,
                fmt=infer_record_format(output_path),
            ) as recorder:
                recorder.write(first_frame)
                total_frames = 1
                end_time = time.monotonic() + args.duration

                try:
                    now = time.monotonic()
                    while now < end_time:
                        remaining_ms = max(1, int((end_time - now) * 1000))
                        try:
                            frame = cam.get_frame(
                                timeout_ms=min(remaining_ms, 1000),
                                output_format=Hik.OutputFormat.BGR8,
                            )
                        except FrameTimeoutError:
                            now = time.monotonic()
                            continue
                        recorder.write(frame)
                        total_frames += 1
                        now = time.monotonic()
                except KeyboardInterrupt:
                    print("\nCtrl+C received. Stopping recording …")
        finally:
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
