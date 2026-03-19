"""
Demo: Automatic reconnection after camera disconnection.
演示：相机断开连接后自动重连。

When a Hikvision camera is disconnected during callback-based grabbing,
the SDK fires an exception callback.  This demo shows a robust reconnect
loop that:

1. Detects the disconnection via ``on_exception``.
2. Cleans up the old camera resources.
3. Periodically re-enumerates cameras and re-opens the same device.
4. Resumes frame capture.

当海康威视相机在回调取帧期间断开连接时，SDK 会触发异常回调。本示例展示一个
健壮的重连循环：

1. 通过 ``on_exception`` 检测断开连接。
2. 清理旧的相机资源。
3. 周期性地重新枚举相机并重新打开同一设备。
4. 恢复帧采集。

Usage / 用法::

    python reconnect.py --ip 192.168.1.100
    python reconnect.py --sn SN123456

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
    AccessMode,
    CameraConnectionError,
    CameraNotFoundError,
    DeviceDisconnectedError,
    HikCamera,
    HikCameraError,
    OutputFormat,
    SDKNotFoundError,
    TransportLayer,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demo: automatic camera reconnection after disconnection."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ip", help="Camera IP address (GigE)")
    group.add_argument("--sn", help="Camera serial number")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum reconnection attempts (0 = unlimited, default: 0)",
    )
    parser.add_argument(
        "--retry-interval",
        type=float,
        default=3.0,
        help="Seconds between reconnection attempts (default: 3)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Camera connection helpers / 相机连接辅助函数
# ---------------------------------------------------------------------------

def connect_camera(
    ip: str | None,
    sn: str | None,
) -> HikCamera:
    """
    Create a HikCamera handle by IP or serial number.
    通过 IP 或序列号创建 HikCamera 句柄。
    """
    if ip:
        return HikCamera.from_ip(ip, TransportLayer.GIGE)
    assert sn is not None
    return HikCamera.from_serial_number(sn)


def open_and_start(
    cam: HikCamera,
    on_frame: Any,
    on_exception: Any,
) -> None:
    """
    Open the camera and start callback-based grabbing.
    打开相机并开始回调模式取帧。
    """
    cam.open(AccessMode.EXCLUSIVE)
    cam.start_grabbing(
        callback=on_frame,
        output_format=OutputFormat.BGR8,
        on_exception=on_exception,
    )


def cleanup_camera(cam: HikCamera) -> None:
    """
    Safely stop grabbing and close the camera, ignoring errors.
    安全地停止取帧并关闭相机，忽略错误。
    """
    try:
        if cam.is_grabbing:
            cam.stop_grabbing()
    except HikCameraError:
        pass
    try:
        if cam.is_open:
            cam.close()
    except HikCameraError:
        pass


# ---------------------------------------------------------------------------
# Main reconnection loop / 主重连循环
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Shared state between threads / 线程间共享状态
    disconnect_event = threading.Event()
    frame_count = 0

    def on_frame(image: np.ndarray, frame_info: dict[str, Any]) -> None:
        nonlocal frame_count
        frame_count += 1
        if frame_count % 100 == 0:
            print(f"  [{frame_count} frames received]")

    def on_exception(exc: DeviceDisconnectedError) -> None:
        print(f"\n⚠  Device exception: {exc}")
        disconnect_event.set()

    # ---------------------------------------------------------------
    # Initial connection / 首次连接
    # ---------------------------------------------------------------
    try:
        cam = connect_camera(args.ip, args.sn)
    except (SDKNotFoundError, CameraNotFoundError) as exc:
        print(f"Cannot connect: {exc}")
        sys.exit(1)

    try:
        open_and_start(cam, on_frame, on_exception)
    except HikCameraError as exc:
        print(f"Failed to open/start camera: {exc}")
        sys.exit(1)

    identifier = args.ip or args.sn
    print(f"Camera {identifier} connected.  Capturing frames …")
    print("Press Ctrl+C to exit.  Unplug the cable to test reconnection.\n")

    retries = 0

    try:
        while True:
            # Normal operation: wait for disconnect or Ctrl+C
            # 正常运行：等待断开连接或 Ctrl+C
            if disconnect_event.wait(timeout=1.0):
                # -------------------------------------------------------
                # Disconnection detected → clean up and reconnect
                # 检测到断开连接 → 清理并重连
                # -------------------------------------------------------
                print(f"\nCamera {identifier} lost.  Cleaning up …")
                cleanup_camera(cam)

                # Check retry limit / 检查重试次数限制
                if args.max_retries > 0:
                    retries += 1
                    if retries > args.max_retries:
                        print(f"Max retries ({args.max_retries}) exceeded.  Exiting.")
                        break

                # Reconnection loop / 重连循环
                print(
                    f"Attempting to reconnect (interval={args.retry_interval}s, "
                    f"attempt={retries if args.max_retries > 0 else 'unlimited'}) …"
                )
                while True:
                    time.sleep(args.retry_interval)
                    try:
                        cam = connect_camera(args.ip, args.sn)
                        open_and_start(cam, on_frame, on_exception)
                        # Success! Reset state.
                        # 成功！重置状态。
                        disconnect_event.clear()
                        print(f"✓  Camera {identifier} reconnected.  Resuming capture …\n")
                        break
                    except (CameraNotFoundError, CameraConnectionError) as exc:
                        print(f"  Reconnect failed: {exc}")
                        if args.max_retries > 0:
                            retries += 1
                            if retries > args.max_retries:
                                print(
                                    f"Max retries ({args.max_retries}) exceeded.  Exiting."
                                )
                                break
                        continue
                    except HikCameraError as exc:
                        print(f"  Unexpected error during reconnect: {exc}")
                        if args.max_retries > 0:
                            retries += 1
                            if retries > args.max_retries:
                                print(
                                    f"Max retries ({args.max_retries}) exceeded.  Exiting."
                                )
                                break
                        continue
                else:
                    # Inner while-loop completed normally (reconnected)
                    # 内层 while 循环正常退出（已重连）
                    continue
                # Inner while-loop was broken (max retries exceeded)
                # 内层 while 循环被 break（超过最大重试次数）
                break

    except KeyboardInterrupt:
        print("\n\nCtrl+C received.  Shutting down …")

    # ---------------------------------------------------------------
    # Final cleanup / 最终清理
    # ---------------------------------------------------------------
    cleanup_camera(cam)
    print(f"Total frames received: {frame_count}")


if __name__ == "__main__":
    main()
