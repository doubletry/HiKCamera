"""
Demo: Handle camera disconnection during callback-based frame capture.
演示：在回调模式取帧期间处理相机断开连接。

This example shows how to use the ``on_exception`` callback in
:py:meth:`~hikcamera.camera.HikCamera.start_grabbing` to detect a camera
disconnection **immediately**, rather than waiting until
:py:meth:`~hikcamera.camera.HikCamera.stop_grabbing` is called.
本示例展示如何使用 :py:meth:`~hikcamera.camera.HikCamera.start_grabbing` 中的
``on_exception`` 回调来**即时**检测相机断开连接，而非等到调用
:py:meth:`~hikcamera.camera.HikCamera.stop_grabbing` 时才发现。

Usage / 用法::

    python exception_handling.py [--ip IP] [--sn SN] [--duration SECONDS]

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
from typing import Any

import numpy as np

from hikcamera import (
    DeviceDisconnectedError,
    Hik,
    HikCamera,
    HikCameraError,
    SDKNotFoundError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo: handle camera disconnection during callback frame capture."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ip", help="Camera IP address (GigE)")
    group.add_argument("--sn", help="Camera serial number")
    parser.add_argument(
        "--duration",
        type=float,
        default=30.0,
        help="Capture duration in seconds (default: 30)",
    )
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
    # Set up disconnect detection / 设置断开连接检测
    # ---------------------------------------------------------------
    #
    # Use a threading.Event so the main loop can react immediately
    # when the SDK exception callback fires.
    # 使用 threading.Event，以便当 SDK 异常回调触发时主循环能立即响应。
    disconnect_event = threading.Event()
    frame_count = 0

    def on_frame(image: np.ndarray, frame_info: dict[str, Any]) -> None:
        nonlocal frame_count
        frame_count += 1
        if frame_count % 100 == 0:
            print(f"  Received {frame_count} frames …")

    def on_exception(exc: DeviceDisconnectedError) -> None:
        """
        Called from the SDK thread when the camera reports a device
        exception (e.g. disconnection).  Sets the event so the main
        thread wakes up.
        当相机报告设备异常（如断开连接）时从 SDK 线程调用。
        设置事件以唤醒主线程。
        """
        print(f"\n⚠  Device exception received: {exc}")
        disconnect_event.set()

    # ---------------------------------------------------------------
    # Open and start grabbing / 打开相机并开始取帧
    # ---------------------------------------------------------------
    with cam:
        cam.open(Hik.AccessMode.EXCLUSIVE)
        print("Camera opened.")

        cam.start_grabbing(
            callback=on_frame,
            output_format=Hik.OutputFormat.BGR8,
            on_exception=on_exception,
        )
        print(f"Grabbing started.  Will capture for up to {args.duration:.0f}s …")
        print("(Unplug the camera cable to test disconnect detection)\n")

        # ---------------------------------------------------------------
        # Main loop: wait for duration or disconnection
        # 主循环：等待采集时长或检测到断开连接
        # ---------------------------------------------------------------
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            # Wait up to 1 second, but wake immediately on disconnect
            # 最多等待 1 秒，但断开连接时立即唤醒
            if disconnect_event.wait(timeout=1.0):
                print("\nCamera disconnected! Stopping gracefully …")
                break

        # ---------------------------------------------------------------
        # Stop grabbing with exception handling
        # 带异常处理地停止取帧
        # ---------------------------------------------------------------
        try:
            cam.stop_grabbing()
            print("Grabbing stopped normally.")
        except DeviceDisconnectedError as exc:
            # This is expected when the camera disconnected during grabbing.
            # stop_grabbing() re-raises the stored exception so the caller
            # knows exactly why streaming ended.
            # 当相机在取帧期间断开连接时，这是预期行为。
            # stop_grabbing() 会重新抛出存储的异常，以便调用者知道流中断的原因。
            print(f"Caught DeviceDisconnectedError on stop: {exc}")
        except HikCameraError as exc:
            print(f"Caught HikCameraError on stop: {exc}")

    print(f"\nTotal frames received: {frame_count}")

    # ---------------------------------------------------------------
    # You can also check device_exception proactively
    # 也可以主动检查 device_exception 属性
    # ---------------------------------------------------------------
    # During grabbing you can poll cam.device_exception at any time:
    # 取帧期间可以随时轮询 cam.device_exception：
    #
    #     if cam.device_exception is not None:
    #         print("Camera disconnected!")


if __name__ == "__main__":
    main()
