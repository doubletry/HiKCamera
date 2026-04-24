"""
Demo: Save a single frame from a Hikvision camera with OpenCV.
演示：从海康威视相机采集单帧并用 OpenCV 保存。

Usage / 用法::

    python save_image.py [--ip IP] [--sn SN] [--output PATH] [--format FORMAT]

If neither --ip nor --sn is given, the first discovered camera is used.
如果未指定 --ip 或 --sn，则使用第一台发现的相机。

Run ``pip install hikcamera`` (or ``pip install -e .`` from the repo root)
before executing this script.
执行此脚本前请先运行 ``pip install hikcamera``（或在仓库根目录下执行
``pip install -e .``）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from hikcamera import (
    Hik,
    HikCamera,
    SDKNotFoundError,
)


def _image_for_imwrite(
    image: np.ndarray, output_format: Hik.OutputFormat
) -> np.ndarray:
    """
    Convert RGB/RGBA frames into OpenCV's BGR/BGRA channel order before saving.
    在保存前将 RGB/RGBA 图像转换为 OpenCV 使用的 BGR/BGRA 通道顺序。
    """
    if output_format == Hik.OutputFormat.RGB8:
        return np.ascontiguousarray(image[..., ::-1])
    if output_format == Hik.OutputFormat.RGBA8:
        return np.ascontiguousarray(image[..., [2, 1, 0, 3]])
    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save a single image from a Hikvision camera.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--ip", help="Camera IP address (GigE)")
    group.add_argument("--sn", help="Camera serial number")
    parser.add_argument(
        "--output",
        default="captured_image.png",
        help="Output file path (default: captured_image.png)",
    )
    parser.add_argument(
        "--format",
        default="BGR8",
        choices=[f.name for f in Hik.OutputFormat],
        help="Output pixel format (default: BGR8)",
    )
    parser.add_argument("--timeout", type=int, default=3000, help="Frame timeout in ms")
    parser.add_argument("--exposure", type=float, help="Exposure time in µs")
    parser.add_argument("--gain", type=float, help="Analogue gain value")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_format = Hik.OutputFormat[args.format]

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
            print(f"Found {len(devices)} camera(s):")
            for i, d in enumerate(devices):
                print(f"  [{i}] {d}")
            cam = HikCamera.from_device_info(devices[0])
            print(f"Using camera: {devices[0]}")
    except SDKNotFoundError as exc:
        print(f"SDK not found: {exc}")
        sys.exit(1)

    # ---------------------------------------------------------------
    # Open, configure, capture / 打开、配置、采集
    # ---------------------------------------------------------------
    with cam:
        cam.open(Hik.AccessMode.EXCLUSIVE)
        print("Camera opened.")

        if args.exposure is not None:
            cam.params.AcquisitionControl.ExposureTime.set(args.exposure)
            print(f"ExposureTime set to {args.exposure} µs")

        if args.gain is not None:
            cam.params.AnalogControl.Gain.set(args.gain)
            print(f"Gain set to {args.gain}")

        cam.start_grabbing()
        print("Grabbing started. Waiting for frame …")

        image: np.ndarray = cam.get_frame(
            timeout_ms=args.timeout, output_format=output_format
        )
        cam.stop_grabbing()

        # -----------------------------------------------------------
        # Save the decoded numpy image with OpenCV.
        # 通过 OpenCV 保存解码后的 numpy 图像。
        # -----------------------------------------------------------
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image_to_save = _image_for_imwrite(image, output_format)
        if not cv2.imwrite(str(output_path), image_to_save):
            raise RuntimeError(
                "Failed to save image to "
                f"{output_path}. Check that the directory exists, the file "
                "extension is supported by OpenCV, and the process has write "
                "permission."
            )

    print(f"Image saved to {output_path}  (shape={image.shape}, dtype={image.dtype})")


if __name__ == "__main__":
    main()
