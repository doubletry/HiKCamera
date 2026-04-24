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
| **Parameter access** | Structured `cam.params.<Category>.<Node>` access with IDE completion, type/range/access validation, and explicit node grouping |
| **Camera information** | `get_camera_info()` retrieves common parameters (image size, frame rate, exposure, gain, pixel format, device model, etc.) in a single call |
| **Configuration management** | Export/import camera configuration files; save/load device user sets |
| **Frame capture – polling** | `start_grabbing()` + `get_frame()` |
| **Frame capture – callback** | `start_grabbing(callback=my_fn)` – custom callback receives a numpy array |
| **Pixel formats** | Mono8/10/12/16, Bayer GR/RG/GB/BG 8/10/12 (packed & planar), RGB/BGR 8, RGBA/BGRA 8, YUV422 (UYVY & YUYV) |
| **Output formats** | `MONO8`, `MONO16`, `BGR8`, `RGB8`, `BGRA8`, `RGBA8` (all as numpy arrays) |
| **SDK image processing** | SDK demosaic / colour conversion (`MV_CC_ConvertPixelTypeEx`) is the **default** decode path; OpenCV in `utils.raw_to_numpy` is kept as a fallback. Tunable via `cam.use_sdk_decode` and Bayer / ISP helpers. |
| **Image save & encode** | Captured frames are numpy arrays; save them with OpenCV (`cv2.imwrite`) and encode in-memory with `cam.encode_image(image, fmt)` when SDK-side compression is needed. |
| **Rotate / flip** | `cam.rotate_image(image, angle)` and `cam.flip_image(image, direction)` wrap `MV_CC_RotateImage` / `MV_CC_FlipImage` for MONO8/RGB8/BGR8 frames. |
| **Video recording** | Record returned numpy frames with OpenCV `cv2.VideoWriter`; see `demos/save_video.py` for a callback-based example that uses the camera FPS. |
| **SDK pixel conversion** | `sdk_convert_pixel()` is kept as a low-level helper (the `get_frame*` / callback pipeline now uses the SDK by default). |
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
from hikcamera import Hik, HikCamera

cameras = HikCamera.enumerate(Hik.TransportLayer.ALL)
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
from hikcamera import Hik, HikCamera

cameras = HikCamera.enumerate()
with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # Prefer the structured cam.params API for IDE completion and validation.
    cam.params.AcquisitionControl.ExposureTime.set(5000.0)
    cam.params.AnalogControl.Gain.set(1.0)
    cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)

    cam.start_grabbing()
    frame = cam.get_frame(timeout_ms=1000, output_format=Hik.OutputFormat.BGR8)
    cam.stop_grabbing()

cv2.imwrite("frame.png", frame)
```

Prefer the structured `cam.params.<Category>.<Node>` API. It keeps the
parameter node hierarchy visible in code and works naturally with separately
imported enum types such as `Hik.GainAuto.OFF`.

### Callback frame capture

```python
import numpy as np
from hikcamera import Hik, HikCamera

received_frames = []

def on_frame(image: np.ndarray, info: dict) -> None:
    received_frames.append(image)
    print(f"Frame {info['frame_num']}: {image.shape}")

with HikCamera.from_device_info(HikCamera.enumerate()[0]) as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.start_grabbing(callback=on_frame, output_format=Hik.OutputFormat.BGR8)

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
    DeviceDisconnectedError, Hik, HikCamera, HikCameraError,
)

disconnect_event = threading.Event()

def on_frame(image, info):
    print(f"Frame {info['frame_num']}")

def on_exception(exc: DeviceDisconnectedError):
    print(f"Camera disconnected: {exc}")
    disconnect_event.set()

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.start_grabbing(
        callback=on_frame,
        output_format=Hik.OutputFormat.BGR8,
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
    CameraConnectionError, CameraNotFoundError, Hik, HikCamera, HikCameraError,
)

# After disconnect detected, release resources via context manager exit,
# then retry in a new context:
while True:
    time.sleep(3)
    try:
        cam = HikCamera.from_ip("192.168.1.100")
        with cam:
            cam.open(Hik.AccessMode.EXCLUSIVE)
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
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(
        Hik.AccessMode.MONITOR,
        streaming_mode=Hik.StreamingMode.MULTICAST,
        multicast_ip="239.0.0.1",
    )
    cam.start_grabbing()
    ...
```

### GigE packet size configuration

By default, `open()` automatically detects and sets the optimal packet size
for GigE cameras.  You can also specify a manual value:

```python
from hikcamera import GIGE_PACKET_SIZE_DEFAULT, GIGE_PACKET_SIZE_JUMBO, Hik, HikCamera

# Auto-detect optimal packet size (default)
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)  # optimal packet size applied automatically
    ...

# Manual packet size (e.g. GIGE_PACKET_SIZE_DEFAULT for standard MTU,
# GIGE_PACKET_SIZE_JUMBO for jumbo frames)
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE, packet_size=GIGE_PACKET_SIZE_JUMBO)
    ...

# Query or change packet size after opening
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    print(cam.get_packet_size())       # current packet size
    print(cam.get_optimal_packet_size())  # SDK-recommended optimal size
    cam.set_packet_size(GIGE_PACKET_SIZE_DEFAULT)  # manual override
```

### Parameter access with error handling

```python
from hikcamera import Hik, HikCamera, ParameterNotSupportedError, ParameterReadOnlyError

with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open()

    try:
        cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)
        value = cam.params.AcquisitionControl.ExposureTime.get()
    except ParameterNotSupportedError:
        print("ExposureTime not available on this camera")

    try:
        cam.params.ImageFormatControl.Width.set(1920)
    except ParameterReadOnlyError:
        print("Width is read-only while grabbing")
```

### Get camera information

```python
from hikcamera import AcquisitionControl, AnalogControl, DeviceControl, Hik, HikCamera, ImageFormatControl

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # Get all common camera parameters at once
    info = cam.get_camera_info()
    print(f"Resolution: {info.get(ImageFormatControl.Width)}x{info.get(ImageFormatControl.Height)}")
    print(f"Exposure: {info.get(AcquisitionControl.ExposureTime)} µs")
    print(f"Gain: {info.get(AnalogControl.Gain)}")
    print(f"Frame rate: {info.get(AcquisitionControl.AcquisitionFrameRate)} fps")
    print(f"Pixel format: {info.get(ImageFormatControl.PixelFormat)}")
    print(f"Model: {info.get(DeviceControl.DeviceModelName)}")
```

### Export / import camera configuration

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # Export current configuration to a file
    cam.export_config("camera_config.xml")

    # Import configuration from a file
    cam.import_config("camera_config.xml")
```

### Save / load device user sets

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    cam.params.UserSetControl.UserSetSelector.set(Hik.UserSetSelector.USER_SET_1)
    cam.params.UserSetControl.UserSetSave.execute()

    # Later, restore parameters from user set 1
    cam.params.UserSetControl.UserSetSelector.set(Hik.UserSetSelector.USER_SET_1)
    cam.params.UserSetControl.UserSetLoad.execute()
```

## Adjustable Parameters

The camera exposes **GenICam** standard parameters via the MVS SDK. The table
below lists a few common nodes. The recommended public API is the structured
`cam.params.<Category>.<Node>` path.

> **Note:** Not every camera model supports every parameter. Unsupported
> parameters raise `ParameterNotSupportedError` when read or written through the
> structured API.

### Structured parameter API

- `cam.params.<Category>.<Node>.set(value)`  
  Recommended write path with node-level type/range/access validation.
- `cam.params.<Category>.<Node>.get(default=None)`  
  Recommended read path for structured nodes.
- `cam.params.<Category>.<Command>.execute()`  
  Recommended command invocation for command nodes.
- `get_camera_info()`  
  Batch-read common parameters, then access them with `ParamNode` keys such as
  `info[ImageFormatControl.Width]` or `info.get(AcquisitionControl.ExposureTime)`.
- `get_optimal_packet_size()`  
  Query SDK for the optimal GigE packet size (GigE only).
- `get_packet_size()` / `set_packet_size(size)`  
  Get/set GigE streaming packet size (`GevSCPSPacketSize`).

### Common parameters

| Structured path | Type | Description |
|---|---|---|
| `cam.params.ImageFormatControl.Width` | `int` | ROI width |
| `cam.params.ImageFormatControl.Height` | `int` | ROI height |
| `cam.params.ImageFormatControl.PixelFormat` | `Hik.PixelFormat` | Pixel format |
| `cam.params.AcquisitionControl.ExposureTime` | `float` | Exposure time in µs |
| `cam.params.AcquisitionControl.ExposureAuto` | `Hik.ExposureAuto` | Auto-exposure mode |
| `cam.params.AnalogControl.Gain` | `float` | Gain value |
| `cam.params.AnalogControl.GainAuto` | `Hik.GainAuto` | Auto-gain mode |
| `cam.params.AcquisitionControl.AcquisitionFrameRate` | `float` | Target frame rate |
| `cam.params.AcquisitionControl.TriggerMode` | `Hik.TriggerMode` | Trigger enable / disable |
| `cam.params.AcquisitionControl.TriggerSource` | `Hik.TriggerSource` | Trigger source |
| `cam.params.DeviceControl.DeviceUserID` | `str` | User-defined camera name |
| `cam.params.TransportLayerControl.GevSCPSPacketSize` | `int` | GigE packet size |

### Common command nodes

| Structured path | Call style | Description |
|---|---|---|
| `cam.params.AcquisitionControl.TriggerSoftware` | `.execute()` | Fire a software trigger |
| `cam.params.UserSetControl.UserSetSelector` | `.set(Hik.UserSetSelector.USER_SET_1)` | Select the device user set |
| `cam.params.UserSetControl.UserSetSave` | `.execute()` | Save current parameters to the selected user set |
| `cam.params.UserSetControl.UserSetLoad` | `.execute()` | Load parameters from the selected user set |

For the complete parameter node tables, see
[`docs/camera_parameter_nodes.md`](docs/camera_parameter_nodes.md). For the
Chinese version, see
[`docs/camera_parameter_nodes_zh.md`](docs/camera_parameter_nodes_zh.md).

### Example: reading & writing common parameters

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # Read all common parameters at once
    info = cam.get_camera_info()
    print(info)

    cam.params.AcquisitionControl.ExposureTime.set(5000.0)
    cam.params.AnalogControl.Gain.set(2.5)
    cam.params.AcquisitionControl.AcquisitionFrameRateEnable.set(True)
    cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)

    exposure = cam.params.AcquisitionControl.ExposureTime.get()
    width = cam.params.ImageFormatControl.Width.get()

    cam.params.AcquisitionControl.TriggerSoftware.execute()

    cam.params.UserSetControl.UserSetSelector.set(Hik.UserSetSelector.USER_SET_1)
    cam.params.UserSetControl.UserSetSave.execute()
```

## Matching MVS output

When `use_sdk_decode=True` (the default) `HikCamera` decodes frames through the
Hikvision SDK image-processing pipeline, so output matches the MVS desktop
application. The following tuning APIs let you mirror any custom MVS profile:

```python
cam.set_bayer_cvt_quality(Hik.BayerCvtQuality.BEST)   # default; FAST/BALANCED/BEST/BEST_PLUS
cam.set_bayer_filter_enable(True)                     # Bayer smooth filter
cam.set_bayer_gamma(0.45)                             # Bayer gamma value
cam.set_gamma(Hik.PixelFormat.RGB8_PACKED, 0.45)      # gamma for non-Bayer formats
cam.set_bayer_ccm([[1024, 0, 0], [0, 1024, 0], [0, 0, 1024]])
img = cam.image_contrast(img, contrast_factor=120)
img = cam.purple_fringing(img, purple_value=10)
cam.set_isp_config("/path/to/isp.xml")
img = cam.isp_process(img)
```

Set `cam.use_sdk_decode = False` (or pass `HikCamera(use_sdk_decode=False)` /
`HikCamera.from_device_info(..., use_sdk_decode=False)` *via the constructor*)
to fall back to the OpenCV-based pipeline in `hikcamera.utils.raw_to_numpy`.

## Image save, video save, encode, rotate & flip

```python
import cv2

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.start_grabbing()

    image = cam.get_frame(output_format=Hik.OutputFormat.BGR8)

    # Save the decoded numpy image with OpenCV
    cv2.imwrite("out.png", image)

    # Encode in-memory to a JPEG byte string via MV_CC_SaveImageEx3
    jpeg_bytes = cam.encode_image(image, Hik.ImageFileFormat.JPEG)

    # Rotate / flip via MV_CC_RotateImage / MV_CC_FlipImage
    rotated = cam.rotate_image(image, Hik.RotateAngle.DEG_90)
    flipped = cam.flip_image(image, Hik.FlipDirection.HORIZONTAL)

    # Record a short MP4 clip from BGR8 frames with OpenCV
    h, w = image.shape[:2]
    fps = cam.params.AcquisitionControl.ResultingFrameRate.get()
    writer = cv2.VideoWriter(
        "out.mp4",
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h),
    )
    writer.write(image)
    for _ in range(100):
        writer.write(cam.get_frame(output_format=Hik.OutputFormat.BGR8))
    writer.release()

    cam.stop_grabbing()
```

## Demos

```bash
# Save a single image
python demos/save_image.py --ip 192.168.1.100 --output image.png --format BGR8

# Record a 10-second video
python demos/save_video.py --ip 192.168.1.100 --output video.mp4 --duration 10

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
    enums.py           # Enumeration definitions used to populate the Hik namespace
    exceptions.py      # Exception hierarchy
    sdk_wrapper.py     # ctypes bindings to the MVS SDK
    utils.py           # Image conversion (raw bytes → numpy)
demos/
  save_image.py        # Demo: capture and save a single frame
  save_video.py        # Demo: capture frames and save as video
  exception_handling.py  # Demo: detect camera disconnection during grabbing
  reconnect.py         # Demo: automatic reconnection after disconnect
docs/
  camera_parameter_nodes.md  # Full structured camera parameter node reference
  camera_parameter_nodes_zh.md  # 中文版结构化相机参数节点参考
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
