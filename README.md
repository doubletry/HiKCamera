# HiKCamera

A Python 3.12 library for Hikvision industrial cameras (MVS SDK).

**English** | [中文](README_zh.md)

[![CI](https://github.com/doubletry/HiKCamera/actions/workflows/ci.yml/badge.svg)](https://github.com/doubletry/HiKCamera/actions/workflows/ci.yml)

## Features

| Feature | Details |
|---|---|
| **Camera enumeration** | Find all GigE / USB3 / CameraLink cameras on the host |
| **Flexible connection** | Connect by IP address or serial number; serial lookup prioritizes faster layer-specific SDK scans |
| **Multiple access modes** | Exclusive, Control, Monitor, Exclusive-With-Switch, Multicast, Unicast |
| **GigE packet size** | Auto-detect optimal packet size on open; manual override supported |
| **Parameter access** | Prefer structured `ParamNode` groups for get/set operations with IDE completion, type/range/access validation; legacy string names remain compatible for now |
| **Camera information** | `get_camera_info()` retrieves common parameters (image size, frame rate, exposure, gain, pixel format, device model, etc.) in a single call |
| **Configuration management** | Export/import camera configuration files; save/load device user sets |
| **Frame capture – polling** | `start_grabbing()` + `get_frame()` |
| **Frame capture – callback** | `start_grabbing(callback=my_fn)` – custom callback receives a numpy array |
| **Pixel formats** | Mono8/10/12/16, Bayer GR/RG/GB/BG 8/10/12 (packed & planar), RGB/BGR 8, RGBA/BGRA 8, YUV422 (UYVY & YUYV) |
| **Output formats** | `MONO8`, `MONO16`, `BGR8`, `RGB8`, `BGRA8`, `RGBA8` (all as numpy arrays) |
| **SDK pixel conversion** | `sdk_convert_pixel()` offloads conversion to the native library |
| **Device disconnect detection** | `on_exception` callback + `device_exception` property for real-time disconnect detection; automatic reconnection pattern |
| **Demos** | Save single image, record video, exception handling, auto-reconnect |

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

`from_serial_number()` now checks GigE, USB, then CameraLink in order when you
search across all transport layers, so common GigE setups avoid waiting for
unrelated SDK scans.

### Polling frame capture

```python
import cv2
from hikcamera import (
    AccessMode,
    AcquisitionControl,
    AnalogControl,
    HikCamera,
    OutputFormat,
)

cameras = HikCamera.enumerate()
with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Prefer structured ParamNode parameters for IDE completion and validation.
    # String names are still supported for backward compatibility, but will be
    # gradually deprecated in future releases.
    cam.set_parameter(AcquisitionControl.ExposureTime, 5000.0)
    cam.set_parameter(AnalogControl.Gain, 1.0)

    cam.start_grabbing()
    frame = cam.get_frame(timeout_ms=1000, output_format=OutputFormat.BGR8)
    cam.stop_grabbing()

cv2.imwrite("frame.png", frame)
```

Prefer `ParamNode`-based access such as `AcquisitionControl.ExposureTime` and
`AnalogControl.Gain`. Legacy string-based calls like
`cam.set_parameter("ExposureTime", 5000.0)` remain compatible for now, but new
code should migrate to the structured API because string-based parameter names
will be gradually deprecated.

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

### Device disconnection handling

When using callback-based grabbing, the camera might disconnect unexpectedly
(e.g. network cable unplugged).  The library registers an SDK exception
callback automatically and provides two ways to detect disconnection:

1. **`on_exception` callback** – invoked immediately from the SDK thread.
2. **`device_exception` property** – can be polled from any thread.

`stop_grabbing()`, `get_frame()`, and `get_frame_ex()` also re-raise the stored exception.

```python
import threading
from hikcamera import (
    HikCamera, AccessMode, OutputFormat,
    DeviceDisconnectedError, HikCameraError,
)

disconnect_event = threading.Event()

def on_frame(image, info):
    print(f"Frame {info['frame_num']}")

def on_exception(exc: DeviceDisconnectedError):
    print(f"Camera disconnected: {exc}")
    disconnect_event.set()

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)
    cam.start_grabbing(
        callback=on_frame,
        output_format=OutputFormat.BGR8,
        on_exception=on_exception,       # ← immediate notification
    )

    # Wait for disconnect or timeout
    disconnect_event.wait(timeout=30)

    try:
        cam.stop_grabbing()
    except DeviceDisconnectedError:
        print("Confirmed: camera was disconnected")
```

You can also poll `cam.device_exception` during grabbing:

```python
# Inside a polling loop
if cam.device_exception is not None:
    print("Camera disconnected!")
```

### Reconnection after disconnection

After a disconnection, the old camera resources must be released and a new
handle created.  Use a context manager (`with`) per camera instance so the
SDK handle is always destroyed — even on errors:

```python
import time
from hikcamera import (
    HikCamera, AccessMode, OutputFormat,
    CameraNotFoundError, CameraConnectionError, HikCameraError,
)

# After disconnect detected, release resources via context manager exit,
# then retry in a new context:
while True:
    time.sleep(3)
    try:
        cam = HikCamera.from_ip("192.168.1.100")
        with cam:
            cam.open(AccessMode.EXCLUSIVE)
            cam.start_grabbing(callback=on_frame, on_exception=on_exception)
            print("Reconnected!")
            ...  # run until next disconnect
    except (CameraNotFoundError, CameraConnectionError) as exc:
        print(f"Reconnect failed: {exc}")
        # cam's context manager ensures handle cleanup on exception
```

See `demos/reconnect.py` for a complete, production-ready example.

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
from hikcamera import (
    AnalogControl,
    HikCamera,
    ParameterNotSupportedError,
    ParameterReadOnlyError,
    AcquisitionControl,
    ImageFormatControl,
)

with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open()

    # Preferred: ParamNode-based access
    cam.set_parameter(AnalogControl.GainAuto, AnalogControl.GainAuto.OFF)

    # ParamNode-based read access
    try:
        value = cam.get_parameter(AcquisitionControl.ExposureTime)
    except ParameterNotSupportedError:
        print("ExposureTime not available on this camera")

    try:
        cam.set_parameter(ImageFormatControl.Width, 1920)
    except ParameterReadOnlyError:
        print("Width is read-only while grabbing")
```

#### ⚠️ Legacy compatibility example *(compatibility path only)*

> _Legacy compatibility path: kept for migration and older codebases. Prefer the structured API shown above._

```python
with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open()

    width = cam.get_int_parameter("Width")
    cam.set_int_parameter("Width", width)
    exposure = cam.get_parameter("ExposureTime")
```

### Get camera information

```python
from hikcamera import AccessMode, AcquisitionControl, AnalogControl, DeviceControl, HikCamera, ImageFormatControl

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Get all common camera parameters at once
    info = cam.get_camera_info()
    print(f"Resolution: {info.get(ImageFormatControl.Width)}x{info.get(ImageFormatControl.Height)}")
    print(f"Exposure: {info.get(AcquisitionControl.ExposureTime)} µs")
    print(f"Gain: {info.get(AnalogControl.Gain)}")
    print(f"Frame rate: {info.get(AcquisitionControl.AcquisitionFrameRate)} fps")
    print(f"Pixel format: {info.get(ImageFormatControl.PixelFormat)}")
    print(f"Model: {info.get(DeviceControl.DeviceModelName)}")
```

#### ⚠️ Legacy compatibility example *(compatibility path only)*

> _Legacy compatibility path: kept for migration and older codebases. Prefer the structured API shown above._

```python
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)
    info = cam.get_camera_info()

    width = info["Width"]
    model = info["DeviceModelName"]
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
from hikcamera import AccessMode, HikCamera, UserSetControl

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Preferred: structured enum values
    cam.save_user_set(UserSetControl.UserSetSelector.USER_SET_1)

    # Later, restore parameters from user set 1
    cam.load_user_set(UserSetControl.UserSetSelector.USER_SET_1)
```

#### ⚠️ Legacy compatibility example *(compatibility path only)*

> _Legacy compatibility path: kept for migration and older codebases. Prefer the structured API shown above._

```python
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)
    cam.save_user_set("UserSet1")
    cam.load_user_set("UserSet1")
```

## Adjustable Parameters

The camera exposes **GenICam** standard parameters via the MVS SDK. The table
below lists the commonly used parameters that `get_camera_info()` collects
automatically, but new code should prefer `ParamNode`-based
`get_parameter()` / `set_parameter()` access. The older typed getter/setter
helpers remain available for backward compatibility, but should be considered
compatibility APIs and may be gradually deprecated.

> **Note:** Not every camera model supports every parameter.  Unsupported
> parameters raise `ParameterNotSupportedError` (or are silently skipped by
> `set_parameter()` / `get_parameter()`). The documentation below separates the
> recommended structured API from the legacy compatibility API to avoid mixing
> the two styles in one place.

### Recommended structured API

| Method / style | Description |
|---|---|
| `set_parameter(param_node, value)` | Recommended write path. Pass `ParamNode` members such as `AcquisitionControl.ExposureTime` or `AnalogControl.GainAuto`; this enables IDE completion plus type/range/access validation before SDK calls |
| `get_parameter(param_node, default=None)` | Recommended read path. Known nodes are read with schema-aware dispatch (including bool/enum/string/int/float) |
| `cam.<CommandNode>()` | Recommended command invocation for command nodes, e.g. `cam.TriggerSoftware()` / `cam.UserSetLoad()` |
| `save_user_set(user_set)` / `load_user_set(user_set)` | Recommended with structured enum members such as `UserSetControl.UserSetSelector.USER_SET_1` |
| `get_camera_info()` | Recommended with `ParamNode` keys such as `info[ImageFormatControl.Width]` or `info.get(AcquisitionControl.ExposureTime)` |
| `get_optimal_packet_size()` | Query SDK for the optimal GigE packet size (GigE only) |
| `get_packet_size()` / `set_packet_size(size)` | Get/set GigE streaming packet size (`GevSCPSPacketSize`) |

### ⚠️ Legacy compatibility API *(gradually deprecated compatibility path)*

> _Use these interfaces only when migrating older code. New code should prefer the structured API above._

| Method / style | Description |
|---|---|
| `set_parameter(name, value)` | Legacy string-based writes such as `set_parameter("ExposureTime", 5000.0)` remain compatible for now |
| `get_parameter(name, default=None)` | Legacy string-based reads remain compatible; unknown legacy strings still fall back to int → float → string probing |
| `get_int_parameter(name)` / `set_int_parameter(name, value)` | Legacy compatibility helpers for integer parameters |
| `get_float_parameter(name)` / `set_float_parameter(name, value)` | Legacy compatibility helpers for float parameters |
| `get_bool_parameter(name)` / `set_bool_parameter(name, value)` | Legacy compatibility helpers for boolean parameters |
| `get_enum_parameter(name)` / `set_enum_parameter(name, value)` | Legacy compatibility helpers for enum parameters |
| `set_enum_parameter_by_string(name, string_value)` | Legacy helper for enum writes by symbolic name (e.g. `"Off"`, `"Continuous"`) |
| `get_string_parameter(name)` / `set_string_parameter(name, value)` | Legacy compatibility helpers for string parameters |
| `execute_command(name)` | Legacy string-based command invocation; prefer `cam.<CommandNode>()` in new code |
| `save_user_set("UserSet1")` / `load_user_set("UserSet1")` | Legacy string-based user-set helpers remain compatible for now |
| `info["Width"]` / `info["DeviceModelName"]` | Legacy string-key access on `get_camera_info()` results remains compatible for now |

### Common parameters

#### Image format

| ParamNode member | Type | R/W | Description |
|---|---|---|---|
| `ImageFormatControl.Width` | int | R/W ¹ | Image width in pixels |
| `ImageFormatControl.Height` | int | R/W ¹ | Image height in pixels |
| `ImageFormatControl.OffsetX` | int | R/W | Horizontal offset (ROI origin) |
| `ImageFormatControl.OffsetY` | int | R/W | Vertical offset (ROI origin) |
| `ImageFormatControl.PixelFormat` | enum | R/W | Pixel format (raw `int`; wrap with `PixelFormat(val)` to get the enum) |
| `ImageFormatControl.WidthMax` | int | R | Maximum allowed width |
| `ImageFormatControl.HeightMax` | int | R | Maximum allowed height |
| `TransportLayerControl.PayloadSize` | int | R | Image payload size in bytes |

> ¹ May become read-only while grabbing, depending on camera model.

#### Exposure & gain

| ParamNode member | Type | R/W | Description |
|---|---|---|---|
| `AcquisitionControl.ExposureTime` | float | R/W | Exposure time in µs |
| `AcquisitionControl.ExposureAuto` | enum | R/W | Auto-exposure mode (`Off` / `Once` / `Continuous`) |
| `AnalogControl.Gain` | float | R/W | Gain value in dB |
| `AnalogControl.GainAuto` | enum | R/W | Auto-gain mode (`Off` / `Once` / `Continuous`) |
| `AnalogControl.Gamma` | float | R/W | Gamma correction value |
| `AnalogControl.GammaEnable` | bool | R/W | Enable / disable gamma correction |

#### Frame rate

| ParamNode member | Type | R/W | Description |
|---|---|---|---|
| `AcquisitionControl.AcquisitionFrameRate` | float | R/W | Target acquisition frame rate (fps) |
| `AcquisitionControl.AcquisitionFrameRateEnable` | bool | R/W | Enable / disable frame rate limiting |
| `AcquisitionControl.ResultingFrameRate` | float | R | Actual resulting frame rate (fps) |

#### Trigger

| ParamNode member | Type | R/W | Description |
|---|---|---|---|
| `AcquisitionControl.TriggerMode` | enum | R/W | Trigger mode (`On` / `Off`) |
| `AcquisitionControl.TriggerSource` | enum | R/W | Trigger source (e.g. `Software`, `Line0`) |

#### White balance

| ParamNode member | Type | R/W | Description |
|---|---|---|---|
| `AnalogControl.BalanceWhiteAuto` | enum | R/W | Auto white-balance mode (`Off` / `Once` / `Continuous`) |

#### Device info (read-only)

| ParamNode member | Type | R/W | Description |
|---|---|---|---|
| `DeviceControl.DeviceModelName` | string | R | Camera model name |
| `DeviceControl.DeviceSerialNumber` | string | R | Serial number |
| `DeviceControl.DeviceFirmwareVersion` | string | R | Firmware version |
| `DeviceControl.DeviceUserID` | string | R/W | User-defined camera identifier |

#### GigE network (GigE cameras only)

| ParamNode member | Type | R/W | Description |
|---|---|---|---|
| `TransportLayerControl.GevSCPSPacketSize` | int | R/W | GigE streaming packet size in bytes (auto-configured on `open()`) |

#### Common commands

Prefer bound command-style calls such as `cam.TriggerSoftware()`. The legacy
`execute_command("TriggerSoftware")` form remains compatible for now, but may be
gradually deprecated.

| ParamNode member | Preferred call | Description |
|---|---|---|
| `AcquisitionControl.TriggerSoftware` | `cam.TriggerSoftware()` | Fire a software trigger |
| `UserSetControl.UserSetSave` | `cam.UserSetSave()` | Save current parameters to the selected user set |
| `UserSetControl.UserSetLoad` | `cam.UserSetLoad()` | Load parameters from the selected user set |

### Example: reading & writing parameters

```python
from hikcamera import (
    AccessMode,
    AcquisitionControl,
    AnalogControl,
    HikCamera,
    ImageFormatControl,
    UserSetControl,
)

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # Read all common parameters at once
    info = cam.get_camera_info()
    print(info)

    # Preferred high-level convenience API: structured ParamNode objects
    cam.set_parameter(AcquisitionControl.ExposureTime, 5000.0)
    cam.set_parameter(AnalogControl.Gain, 2.5)
    cam.set_parameter(AcquisitionControl.AcquisitionFrameRateEnable, True)
    cam.set_parameter(AnalogControl.GainAuto, AnalogControl.GainAuto.OFF)

    # ParamNode-based read access
    exposure = cam.get_parameter(AcquisitionControl.ExposureTime)
    width = cam.get_parameter(ImageFormatControl.Width)

    # Preferred command invocation
    cam.TriggerSoftware()

    # High-level user-set helper with structured enum value
    cam.save_user_set(UserSetControl.UserSetSelector.USER_SET_1)
```

## Demos

```bash
# Save a single image
python demos/save_image.py --ip 192.168.1.100 --output image.png --format BGR8

# Record a 10-second video
python demos/save_video.py --ip 192.168.1.100 --output video.mp4 --fps 25 --duration 10

# Exception handling (disconnect detection)
python demos/exception_handling.py --ip 192.168.1.100 --duration 30

# Automatic reconnection after disconnect
python demos/reconnect.py --ip 192.168.1.100 --retry-interval 3
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
  exception_handling.py  # Demo: detect camera disconnection during grabbing
  reconnect.py         # Demo: automatic reconnection after disconnect
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
