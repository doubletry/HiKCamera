"""
Demo: Capture a sequence of frames and save them as a video file.
演示：捕获一系列帧并保存为视频文件。

Uses the callback-based acquisition mode so no frames are dropped
between calls.
使用基于回调的采集模式以避免帧丢失。

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
import queue
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from hikcamera import (
    AccessMode,
    AcquisitionControl,
    AnalogControl,
    HikCamera,
    OutputFormat,
    SDKNotFoundError,
    TransportLayer,
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


def main() -> None:
    args = parse_args()

    # ---------------------------------------------------------------
    # Locate camera / 定位相机
    # ---------------------------------------------------------------
    try:
        if args.ip:
            print(f"Connecting to camera at IP {args.ip} …")
            cam = HikCamera.from_ip(args.ip, TransportLayer.GIGE)
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
    # Thread-safe frame queue / 线程安全帧队列
    # ---------------------------------------------------------------
    frame_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=256)

    def on_frame(image: np.ndarray, frame_info: dict[str, Any]) -> None:
        """
        Enqueue decoded frames (drop oldest if full to avoid blocking).
        将解码后的帧入队（队列满时丢弃最旧帧以避免阻塞）。
        """
        try:
            frame_queue.put_nowait(image)
        except queue.Full:
            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass
            frame_queue.put_nowait(image)

    # ---------------------------------------------------------------
    # Open and start grabbing / 打开相机并开始取帧
    # ---------------------------------------------------------------
    with cam:
        cam.open(AccessMode.EXCLUSIVE)
        print("Camera opened.")

        if args.exposure is not None:
            cam.set_parameter(AcquisitionControl.ExposureTime, args.exposure)
        if args.gain is not None:
            cam.set_parameter(AnalogControl.Gain, args.gain)

        # Grab the first frame to get image dimensions
        # 抓取第一帧以获取图像尺寸
        cam.start_grabbing()
        print(f"Grabbing started. Recording for {args.duration:.1f} seconds …")

        # Wait for the first frame to determine size
        # 等待第一帧以确定尺寸
        first_frame: np.ndarray | None = None
        deadline = time.monotonic() + 5.0
        while first_frame is None and time.monotonic() < deadline:
            try:
                first_frame = cam.get_frame(timeout_ms=500, output_format=OutputFormat.BGR8)
            except Exception:  # noqa: BLE001
                continue

        if first_frame is None:
            print("Failed to receive any frames. Aborting.")
            cam.stop_grabbing()
            sys.exit(1)

        h, w = first_frame.shape[:2]
        print(f"Frame size: {w}×{h}")

        cam.stop_grabbing()

        # Restart with callback / 以回调模式重新启动
        cam.start_grabbing(callback=on_frame, output_format=OutputFormat.BGR8)

        # ---------------------------------------------------------------
        # Set up video writer / 设置视频写入器
        # ---------------------------------------------------------------
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output_path), fourcc, args.fps, (w, h))
        if not writer.isOpened():
            print(f"Failed to open VideoWriter for {output_path}")
            cam.stop_grabbing()
            sys.exit(1)

        # ---------------------------------------------------------------
        # Write first frame then collect remaining frames
        # 写入第一帧，然后采集剩余帧
        # ---------------------------------------------------------------
        writer.write(first_frame)
        total_frames = 1
        end_time = time.monotonic() + args.duration

        while time.monotonic() < end_time:
            try:
                frame = frame_queue.get(timeout=0.1)
                writer.write(frame)
                total_frames += 1
            except queue.Empty:
                continue

        cam.stop_grabbing()
        writer.release()

    print(
        f"Video saved to {output_path}  "
        f"({total_frames} frames, {args.fps:.1f} fps requested)"
    )


if __name__ == "__main__":
    main()
