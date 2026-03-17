# HiKCamera

A Python 3.12 library for Hikvision industrial cameras (MVS SDK).

**English** | [中文](README_zh.md)

[![CI](https://github.com/doubletry/HiKCamera/actions/workflows/ci.yml/badge.svg)](https://github.com/doubletry/HiKCamera/actions/workflows/ci.yml)

## Features

| Feature | Details |
|---|---|
| **Camera enumeration** | Find all GigE / USB3 / CameraLink cameras on the host |
| **Flexible connection** | Connect by IP address or serial number |
| **Multiple access modes** | Exclusive, Control, Monitor, Exclusive-With-Switch, Multicast, Unicast |
| **Parameter access** | Get/set integer, float, bool, enum, string GenICam parameters with full exception handling (missing parameters are handled gracefully) |
| **Camera information** | `get_camera_info()` retrieves common parameters (image size, frame rate, exposure, gain, pixel format, device model, etc.) in a single call |
| **Configuration management** | Export/import camera configuration files; save/load device user sets |
| **Frame capture – polling** | `start_grabbing()` + `get_frame()` |
| **Frame capture – callback** | `start_grabbing(callback=my_fn)` – custom callback receives a numpy array |
| **Pixel formats** | Mono8/10/12/16, Bayer GR/RG/GB/BG 8/10/12 (packed & planar), RGB/BGR 8, RGBA/BGRA 8, YUV422 (UYVY & YUYV) |
| **Output formats** | `MONO8`, `MONO16`, `BGR8`, `RGB8`, `BGRA8`, `RGBA8` (all as numpy arrays) |
| **SDK pixel conversion** | `sdk_convert_pixel()` offloads conversion to the native library |
| **Demos** | Save single image, record video |

## Prerequisites

Install the **Hikvision MVS SDK** for your platform from:
<https://www.hikrobotics.com/cn/machinevision/service/download/?module=0>

| Platform | Default library path |
|---|---|
| Linux (64-bit) | `/opt/MVS/lib/64/libMvCameraControl.so` |
| Windows (64-bit) | `C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64\MvCameraControl.dll` |

You can override the path with the `HIKCAMERA_SDK_PATH` environment variable.

## Installation

```bash
# Install with pip (once published to PyPI)
pip install hikcamera

# Or install from source with Poetry
git clone https://github.com/doubletry/HiKCamera.git
cd HiKCamera
poetry install
```

## Quick Start

### Enumerate cameras

```python
from hikcamera import HikCamera, TransportLayer

cameras = HikCamera.enumerate(TransportLayer.ALL)
for cam in cameras:
    print(cam)
```

### Connect by IP (GigE)

```python
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open()
    ...
```

### Connect by serial number

```python
with HikCamera.from_serial_number("SN123456") as cam:
    cam.open()
    ...
```

### Polling frame capture

```python
import cv2
from hikcamera import HikCamera, AccessMode, OutputFormat

cameras = HikCamera.enumerate()
with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Adjust parameters (silently ignores unsupported ones)
    cam.set_parameter("ExposureTime", 5000.0)
    cam.set_parameter("Gain", 1.0)

    cam.start_grabbing()
    frame = cam.get_frame(timeout_ms=1000, output_format=OutputFormat.BGR8)
    cam.stop_grabbing()

cv2.imwrite("frame.png", frame)
```

### Callback frame capture

```python
import numpy as np
from hikcamera import HikCamera, AccessMode, OutputFormat

received_frames = []

def on_frame(image: np.ndarray, info: dict) -> None:
    received_frames.append(image)
    print(f"Frame {info['frame_num']}: {image.shape}")

with HikCamera.from_device_info(HikCamera.enumerate()[0]) as cam:
    cam.open(AccessMode.EXCLUSIVE)
    cam.start_grabbing(callback=on_frame, output_format=OutputFormat.BGR8)

    import time
    time.sleep(5)   # collect frames for 5 seconds

    cam.stop_grabbing()
```

### Multicast streaming

```python
from hikcamera import HikCamera, AccessMode, StreamingMode

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(
        AccessMode.MONITOR,
        streaming_mode=StreamingMode.MULTICAST,
        multicast_ip="239.0.0.1",
    )
    cam.start_grabbing()
    ...
```

### Parameter access with error handling

```python
from hikcamera import HikCamera, ParameterNotSupportedError, ParameterReadOnlyError

with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open()

    # Safe: silently ignores parameters not present on this model
    cam.set_parameter("GainAuto", "Off")

    # Or handle explicitly
    try:
        value = cam.get_float_parameter("ExposureTime")
    except ParameterNotSupportedError:
        print("ExposureTime not available on this camera")

    try:
        cam.set_int_parameter("Width", 1920)
    except ParameterReadOnlyError:
        print("Width is read-only while grabbing")
```

### Get camera information

```python
from hikcamera import HikCamera, AccessMode

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Get all common camera parameters at once
    info = cam.get_camera_info()
    print(f"Resolution: {info.get('Width')}x{info.get('Height')}")
    print(f"Exposure: {info.get('ExposureTime')} µs")
    print(f"Gain: {info.get('Gain')}")
    print(f"Frame rate: {info.get('AcquisitionFrameRate')} fps")
    print(f"Pixel format: {info.get('PixelFormat')}")
    print(f"Model: {info.get('DeviceModelName')}")
```

### Export / import camera configuration

```python
from hikcamera import HikCamera, AccessMode

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Export current configuration to a file
    cam.export_config("camera_config.xml")

    # Import configuration from a file
    cam.import_config("camera_config.xml")
```

### Save / load device user sets

```python
from hikcamera import HikCamera, AccessMode

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Save current parameters to user set 1
    cam.save_user_set("UserSet1")

    # Later, restore parameters from user set 1
    cam.load_user_set("UserSet1")
```

## Demos

```bash
# Save a single image
python demos/save_image.py --ip 192.168.1.100 --output image.png --format BGR8

# Record a 10-second video
python demos/save_video.py --ip 192.168.1.100 --output video.mp4 --fps 25 --duration 10
```

## Project Layout

```
src/
  hikcamera/
    __init__.py        # Public API
    camera.py          # HikCamera class
    enums.py           # Enumerations (AccessMode, PixelFormat, OutputFormat, …)
    exceptions.py      # Exception hierarchy
    sdk_wrapper.py     # ctypes bindings to the MVS SDK
    utils.py           # Image conversion (raw bytes → numpy)
demos/
  save_image.py        # Demo: capture and save a single frame
  save_video.py        # Demo: capture frames and save as video
tests/
  conftest.py          # Fixtures and mock SDK helpers
  test_camera.py       # HikCamera tests
  test_enums.py        # Enum tests
  test_exceptions.py   # Exception hierarchy tests
  test_integration.py  # Public API smoke tests
  test_sdk_wrapper.py  # SDK library loader tests
  test_utils.py        # Image conversion tests
```

## Development

```bash
# Install dev dependencies
poetry install --with dev

# Run tests
poetry run pytest

# Lint
poetry run ruff check src/ tests/
```

## Release

Pushing a version tag triggers the release workflow, which:
1. Runs the test suite
2. Builds the wheel and sdist
3. Creates a GitHub Release with the distribution files
4. Publishes to PyPI via trusted publishing

```bash
git tag v1.0.0
git push origin v1.0.0
```

## SDK Compatibility

The ctypes struct definitions in ``sdk_wrapper.py`` are aligned with the
official Hikvision MVS SDK ``CameraParams.h`` header (tested against
MVS SDK v4.x).  Key structs:

- **``MV_GIGE_DEVICE_INFO``** – includes ``nIpCfgOption``, ``nIpCfgCurrent``
  before ``nCurrentIp``; 16-byte ``chSerialNumber``
- **``MV_USB3_DEVICE_INFO``** – includes ``StreamEndPoint``, ``EventEndPoint``,
  ``idVendor``, ``idProduct``, ``nDeviceNumber``, ``chDeviceGUID``; all
  string fields are 64 bytes
- **``MV_FRAME_OUT_INFO_EX``** – includes all chunk watermark fields
  (``nSecondCount``, ``fGain``, ``fExposureTime``, ``nRed``/``nGreen``/``nBlue``,
  ``nFrameCounter``, ``nTriggerIndex``, ROI offsets, etc.) between
  ``nFrameLen`` and ``nLostPacket``
- **``MV_CC_PIXEL_CONVERT_PARAM``** – field order matches SDK:
  ``nDstLen`` before ``nDstBufferSize``

Bayer pattern naming follows the OpenCV convention (opposite of PFNC/SDK):
SDK ``BayerRG`` → OpenCV ``COLOR_BAYER_BG2BGR``.

## License

MIT
