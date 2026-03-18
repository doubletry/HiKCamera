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
| **GigE packet size** | Auto-detect optimal packet size on open; manual override supported |
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
# Install from source with Poetry
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

### GigE packet size configuration

By default, `open()` automatically detects and sets the optimal packet size
for GigE cameras.  You can also specify a manual value:

```python
from hikcamera import HikCamera, AccessMode, GIGE_PACKET_SIZE_DEFAULT, GIGE_PACKET_SIZE_JUMBO

# Auto-detect optimal packet size (default)
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)  # optimal packet size applied automatically
    ...

# Manual packet size (e.g. GIGE_PACKET_SIZE_DEFAULT for standard MTU,
# GIGE_PACKET_SIZE_JUMBO for jumbo frames)
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE, packet_size=GIGE_PACKET_SIZE_JUMBO)
    ...

# Query or change packet size after opening
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)
    print(cam.get_packet_size())       # current packet size
    print(cam.get_optimal_packet_size())  # SDK-recommended optimal size
    cam.set_packet_size(GIGE_PACKET_SIZE_DEFAULT)  # manual override
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

## Adjustable Parameters

The camera exposes **GenICam** standard parameters via the MVS SDK.  The table
below lists the commonly used parameters that `get_camera_info()` collects
automatically, but you can access **any** GenICam node by name through the
typed getter/setter methods.

> **Note:** Not every camera model supports every parameter.  Unsupported
> parameters raise `ParameterNotSupportedError` (or are silently skipped by
> `set_parameter()` / `get_parameter()`).

### Parameter access methods

| Method | Description |
|---|---|
| `set_parameter(name, value)` | Auto-dispatch by Python type (bool → int → float → str); silently skips unsupported parameters |
| `get_parameter(name, default=None)` | Auto-tries int → float → string; returns *default* if unsupported |
| `get_int_parameter(name)` / `set_int_parameter(name, value)` | Integer parameter access |
| `get_float_parameter(name)` / `set_float_parameter(name, value)` | Float parameter access |
| `get_bool_parameter(name)` / `set_bool_parameter(name, value)` | Boolean parameter access |
| `get_enum_parameter(name)` / `set_enum_parameter(name, value)` | Enum parameter access (integer value) |
| `set_enum_parameter_by_string(name, string_value)` | Enum parameter set by symbolic name (e.g. `"Off"`, `"Continuous"`) |
| `get_string_parameter(name)` / `set_string_parameter(name, value)` | String parameter access |
| `execute_command(name)` | Execute a command node (e.g. `"TriggerSoftware"`) |
| `get_camera_info()` | Retrieve all common parameters listed below in a single call |
| `get_optimal_packet_size()` | Query SDK for the optimal GigE packet size (GigE only) |
| `get_packet_size()` / `set_packet_size(size)` | Get/set GigE streaming packet size (`GevSCPSPacketSize`) |

### Common parameters

#### Image format

| Parameter | Type | R/W | Description |
|---|---|---|---|
| `Width` | int | R/W ¹ | Image width in pixels |
| `Height` | int | R/W ¹ | Image height in pixels |
| `OffsetX` | int | R/W | Horizontal offset (ROI origin) |
| `OffsetY` | int | R/W | Vertical offset (ROI origin) |
| `PixelFormat` | enum | R/W | Pixel format (raw `int`; wrap with `PixelFormat(val)` to get the enum) |
| `WidthMax` | int | R | Maximum allowed width |
| `HeightMax` | int | R | Maximum allowed height |
| `PayloadSize` | int | R | Image payload size in bytes |

> ¹ May become read-only while grabbing, depending on camera model.

#### Exposure & gain

| Parameter | Type | R/W | Description |
|---|---|---|---|
| `ExposureTime` | float | R/W | Exposure time in µs |
| `ExposureAuto` | enum | R/W | Auto-exposure mode (`Off` / `Once` / `Continuous`) |
| `Gain` | float | R/W | Gain value in dB |
| `GainAuto` | enum | R/W | Auto-gain mode (`Off` / `Once` / `Continuous`) |
| `Gamma` | float | R/W | Gamma correction value |
| `GammaEnable` | bool | R/W | Enable / disable gamma correction |

#### Frame rate

| Parameter | Type | R/W | Description |
|---|---|---|---|
| `AcquisitionFrameRate` | float | R/W | Target acquisition frame rate (fps) |
| `AcquisitionFrameRateEnable` | bool | R/W | Enable / disable frame rate limiting |
| `ResultingFrameRate` | float | R | Actual resulting frame rate (fps) |

#### Trigger

| Parameter | Type | R/W | Description |
|---|---|---|---|
| `TriggerMode` | enum | R/W | Trigger mode (`On` / `Off`) |
| `TriggerSource` | enum | R/W | Trigger source (e.g. `Software`, `Line0`) |

#### White balance

| Parameter | Type | R/W | Description |
|---|---|---|---|
| `BalanceWhiteAuto` | enum | R/W | Auto white-balance mode (`Off` / `Once` / `Continuous`) |

#### Device info (read-only)

| Parameter | Type | R/W | Description |
|---|---|---|---|
| `DeviceModelName` | string | R | Camera model name |
| `DeviceSerialNumber` | string | R | Serial number |
| `DeviceFirmwareVersion` | string | R | Firmware version |
| `DeviceUserID` | string | R/W | User-defined camera identifier |

#### GigE network (GigE cameras only)

| Parameter | Type | R/W | Description |
|---|---|---|---|
| `GevSCPSPacketSize` | int | R/W | GigE streaming packet size in bytes (auto-configured on `open()`) |

#### Common commands

These nodes are executed via `execute_command()`:

| Command | Description |
|---|---|
| `TriggerSoftware` | Fire a software trigger |
| `UserSetSave` | Save current parameters to the selected user set |
| `UserSetLoad` | Load parameters from the selected user set |

### Example: reading & writing parameters

```python
from hikcamera import HikCamera, AccessMode

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Read all common parameters at once
    info = cam.get_camera_info()
    print(info)

    # High-level convenience (auto type dispatch)
    cam.set_parameter("ExposureTime", 5000.0)
    cam.set_parameter("Gain", 2.5)
    cam.set_parameter("AcquisitionFrameRateEnable", True)
    cam.set_parameter("GainAuto", "Off")          # enum by string

    # Typed access (gives full error info)
    exposure = cam.get_float_parameter("ExposureTime")
    width = cam.get_int_parameter("Width")

    # Execute a command
    cam.execute_command("TriggerSoftware")
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
