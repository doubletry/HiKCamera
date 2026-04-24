# HiKCamera

海康威视工业相机（MVS SDK）的 Python 3.12 库。

[English](README.md) | **中文**

[![CI](https://github.com/doubletry/HiKCamera/actions/workflows/ci.yml/badge.svg)](https://github.com/doubletry/HiKCamera/actions/workflows/ci.yml)

## 功能特性

| 功能 | 详情 |
|---|---|
| **相机枚举** | 查找主机上所有 GigE / USB3 / CameraLink 相机 |
| **灵活连接** | 通过 IP 地址或序列号连接；按序列号搜索时优先使用更快的分层 SDK 枚举 |
| **多种访问模式** | 独占、控制、监视、独占带切换、组播、单播 |
| **GigE 包大小** | 打开时自动检测最优包大小；支持手动配置 |
| **参数访问** | 使用结构化 `cam.params.<分类>.<节点>` 方式读写参数，具备 IDE 补全、类型/范围/访问权限校验与明确的节点分组 |
| **相机信息** | `get_camera_info()` 一次调用即可获取常用参数（图像尺寸、帧率、曝光、增益、像素格式、设备型号等） |
| **配置管理** | 导出/导入相机配置文件；保存/加载设备用户集 |
| **帧捕获 – 轮询模式** | `start_grabbing()` + `get_frame()` |
| **帧捕获 – 回调模式** | `start_grabbing(callback=my_fn)` ── 自定义回调接收 numpy 数组 |
| **像素格式** | Mono8/10/12/16, Bayer GR/RG/GB/BG 8/10/12（紧凑和平面格式）, RGB/BGR 8, RGBA/BGRA 8, YUV422（UYVY 和 YUYV） |
| **输出格式** | `MONO8`、`MONO16`、`BGR8`、`RGB8`、`BGRA8`、`RGBA8`（均为 numpy 数组） |
| **SDK 图像处理** | SDK 去马赛克 / 颜色转换（`MV_CC_ConvertPixelTypeEx`）作为**默认**解码路径；`utils.raw_to_numpy` 中的 OpenCV 路径作为回退保留。可通过 `cam.use_sdk_decode` 与 Bayer / ISP 调优 API 控制。 |
| **图像保存与编码** | `cam.save_image_to_file(image, "out.png")` 与 `cam.encode_image(image, fmt)` 使用 `MV_CC_SaveImageToFileEx` / `MV_CC_SaveImageEx3`（>65535 像素自动切换到 `MV_CC_SaveImageToFileEx2`）。 |
| **旋转 / 翻转** | `cam.rotate_image(image, angle)`、`cam.flip_image(image, direction)` 封装 `MV_CC_RotateImage` / `MV_CC_FlipImage`，支持 MONO8/RGB8/BGR8。 |
| **视频录制** | `with cam.record(path, fps, w, h) as rec: rec.write(frame)` 封装 `MV_CC_StartRecord` / `MV_CC_InputOneFrame` / `MV_CC_StopRecord`。 |
| **SDK 像素转换** | `sdk_convert_pixel()` 作为底层辅助方法保留（`get_frame*` / 回调路径默认使用 SDK 管线）。 |
| **设备断开检测** | `on_exception` 回调 + `device_exception` 属性实时检测断开连接；自动重连模式 |
| **示例程序** | 保存单张图像、录制视频、异常处理、自动重连 |

## 前置要求

请从以下地址下载并安装适合您平台的 **海康威视 MVS SDK**：
<https://www.hikrobotics.com/cn/machinevision/service/download/?module=0>

| 平台 | 默认库路径 |
|---|---|
| Linux（64 位） | `/opt/MVS/lib/64/libMvCameraControl.so` |
| Windows（64 位） | `C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64\MvCameraControl.dll` |

您可以通过 `HIKCAMERA_SDK_PATH` 环境变量覆盖默认路径。

## 安装

```bash
# 从源码通过 Poetry 安装
git clone https://github.com/doubletry/HiKCamera.git
cd HiKCamera
poetry install
```

## 快速上手

### 枚举相机

```python
from hikcamera import Hik, HikCamera

cameras = HikCamera.enumerate(Hik.TransportLayer.ALL)
for cam in cameras:
    print(cam)
```

### 通过 IP 连接（GigE）

```python
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open()
    ...
```

### 通过序列号连接

```python
with HikCamera.from_serial_number("SN123456") as cam:
    cam.open()
    ...
```

当在所有传输层中按序列号搜索时，`from_serial_number()` 会按 GigE → USB →
CameraLink 的顺序优先扫描，因此常见的 GigE 场景无需等待无关传输层的 SDK
枚举完成。

### 轮询模式帧捕获

```python
import cv2
from hikcamera import Hik, HikCamera

cameras = HikCamera.enumerate()
with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # 优先使用结构化 cam.params API，以获得 IDE 补全和校验。
    cam.params.AcquisitionControl.ExposureTime.set(5000.0)
    cam.params.AnalogControl.Gain.set(1.0)
    cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)

    cam.start_grabbing()
    frame = cam.get_frame(timeout_ms=1000, output_format=Hik.OutputFormat.BGR8)
    cam.stop_grabbing()

cv2.imwrite("frame.png", frame)
```

推荐统一使用 `cam.params.<分类>.<节点>` 结构化 API，这样代码里可以直接
看到参数节点归属，并且枚举值可自然配合单独导入的 `Hik.GainAuto.OFF` 使用。

### 回调模式帧捕获

```python
import numpy as np
from hikcamera import Hik, HikCamera

received_frames = []

def on_frame(image: np.ndarray, info: dict) -> None:
    received_frames.append(image)
    print(f"帧 {info['frame_num']}: {image.shape}")

with HikCamera.from_device_info(HikCamera.enumerate()[0]) as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.start_grabbing(callback=on_frame, output_format=Hik.OutputFormat.BGR8)

    import time
    time.sleep(5)   # 采集 5 秒

    cam.stop_grabbing()
```

### 设备断开连接处理

使用回调模式取帧时，相机可能意外断开连接（如网线被拔出）。库会自动注册 SDK 异常
回调，并提供两种方式检测断开连接：

1. **`on_exception` 回调** ── 从 SDK 线程立即调用。
2. **`device_exception` 属性** ── 可从任意线程轮询。

`stop_grabbing()`、`get_frame()` 和 `get_frame_ex()` 也会重新抛出已存储的异常。

```python
import threading
from hikcamera import (
    DeviceDisconnectedError, Hik, HikCamera, HikCameraError,
)

disconnect_event = threading.Event()

def on_frame(image, info):
    print(f"帧 {info['frame_num']}")

def on_exception(exc: DeviceDisconnectedError):
    print(f"相机断开连接: {exc}")
    disconnect_event.set()

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.start_grabbing(
        callback=on_frame,
        output_format=Hik.OutputFormat.BGR8,
        on_exception=on_exception,       # ← 即时通知
    )

    # 等待断开连接或超时
    disconnect_event.wait(timeout=30)

    try:
        cam.stop_grabbing()
    except DeviceDisconnectedError:
        print("确认：相机已断开连接")
```

也可以在取帧期间轮询 `cam.device_exception`：

```python
# 在轮询循环中
if cam.device_exception is not None:
    print("相机断开连接！")
```

### 断开连接后重连

断开连接后，需要释放旧的相机资源并创建新的句柄。对每个相机实例使用上下文管理器
（`with`），确保 SDK 句柄始终被销毁——即使发生错误：

```python
import time
from hikcamera import (
    CameraConnectionError, CameraNotFoundError, Hik, HikCamera, HikCameraError,
)

# 检测到断开连接后，通过上下文管理器退出释放资源，
# 然后在新的上下文中重试：
while True:
    time.sleep(3)
    try:
        cam = HikCamera.from_ip("192.168.1.100")
        with cam:
            cam.open(Hik.AccessMode.EXCLUSIVE)
            cam.start_grabbing(callback=on_frame, on_exception=on_exception)
            print("重连成功！")
            ...  # 运行直到下次断开连接
    except (CameraNotFoundError, CameraConnectionError) as exc:
        print(f"重连失败: {exc}")
        # cam 的上下文管理器确保异常时清理句柄
```

完整的生产级示例请参见 `demos/reconnect.py`。

### 组播流传输

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

### GigE 包大小配置

默认情况下，`open()` 会自动检测并设置 GigE 相机的最优包大小。
您也可以手动指定：

```python
from hikcamera import GIGE_PACKET_SIZE_DEFAULT, GIGE_PACKET_SIZE_JUMBO, Hik, HikCamera

# 自动检测最优包大小（默认行为）
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)  # 自动应用最优包大小
    ...

# 手动指定包大小（如 GIGE_PACKET_SIZE_DEFAULT 标准 MTU，
# GIGE_PACKET_SIZE_JUMBO 巨帧）
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE, packet_size=GIGE_PACKET_SIZE_JUMBO)
    ...

# 打开后查询或修改包大小
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    print(cam.get_packet_size())          # 当前包大小
    print(cam.get_optimal_packet_size())  # SDK 推荐的最优值
    cam.set_packet_size(GIGE_PACKET_SIZE_DEFAULT)  # 手动覆盖
```

### 带错误处理的参数访问

```python
from hikcamera import Hik, HikCamera, ParameterNotSupportedError, ParameterReadOnlyError

with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open()

    try:
        cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)
        value = cam.params.AcquisitionControl.ExposureTime.get()
    except ParameterNotSupportedError:
        print("此相机不支持 ExposureTime 参数")

    try:
        cam.params.ImageFormatControl.Width.set(1920)
    except ParameterReadOnlyError:
        print("取帧期间 Width 为只读参数")
```

### 获取相机信息

```python
from hikcamera import AcquisitionControl, AnalogControl, DeviceControl, Hik, HikCamera, ImageFormatControl

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # 一次获取所有常用相机参数
    info = cam.get_camera_info()
    print(f"分辨率: {info.get(ImageFormatControl.Width)}x{info.get(ImageFormatControl.Height)}")
    print(f"曝光: {info.get(AcquisitionControl.ExposureTime)} µs")
    print(f"增益: {info.get(AnalogControl.Gain)}")
    print(f"帧率: {info.get(AcquisitionControl.AcquisitionFrameRate)} fps")
    print(f"像素格式: {info.get(ImageFormatControl.PixelFormat)}")
    print(f"型号: {info.get(DeviceControl.DeviceModelName)}")
```

### 导出 / 导入相机配置

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # 导出当前配置到文件
    cam.export_config("camera_config.xml")

    # 从文件导入配置
    cam.import_config("camera_config.xml")
```

### 保存 / 加载设备用户集

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    cam.params.UserSetControl.UserSetSelector.set(Hik.UserSetSelector.USER_SET_1)
    cam.params.UserSetControl.UserSetSave.execute()

    # 稍后，从用户集 1 恢复参数
    cam.params.UserSetControl.UserSetSelector.set(Hik.UserSetSelector.USER_SET_1)
    cam.params.UserSetControl.UserSetLoad.execute()
```

## 可调参数

相机通过 MVS SDK 暴露 **GenICam** 标准参数。下表只列出少量常用节点；推荐统一
使用结构化 `cam.params.<分类>.<节点>` 访问路径。

> **注意：** 并非每个型号的相机都支持所有参数。通过结构化 API 读写时，如
> 节点不受支持会抛出 `ParameterNotSupportedError`。

### 结构化参数 API

- `cam.params.<分类>.<节点>.set(value)`  
  推荐的写入方式，具备节点级类型/范围/访问权限校验。
- `cam.params.<分类>.<节点>.get(default=None)`  
  推荐的读取方式。
- `cam.params.<分类>.<命令>.execute()`  
  推荐的命令调用方式。
- `get_camera_info()`  
  批量读取常用参数，再用 `ParamNode` key 访问，例如
  `info[ImageFormatControl.Width]`、`info.get(AcquisitionControl.ExposureTime)`。
- `get_optimal_packet_size()`  
  查询 SDK 获取 GigE 最优包大小（仅 GigE 相机）。
- `get_packet_size()` / `set_packet_size(size)`  
  获取/设置 GigE 流传输包大小（`GevSCPSPacketSize`）。

### 常用参数

| 结构化路径 | 类型 | 说明 |
|---|---|---|
| `cam.params.ImageFormatControl.Width` | `int` | ROI 宽度 |
| `cam.params.ImageFormatControl.Height` | `int` | ROI 高度 |
| `cam.params.ImageFormatControl.PixelFormat` | `Hik.PixelFormat` | 像素格式 |
| `cam.params.AcquisitionControl.ExposureTime` | `float` | 曝光时间（µs） |
| `cam.params.AcquisitionControl.ExposureAuto` | `Hik.ExposureAuto` | 自动曝光模式 |
| `cam.params.AnalogControl.Gain` | `float` | 增益值 |
| `cam.params.AnalogControl.GainAuto` | `Hik.GainAuto` | 自动增益模式 |
| `cam.params.AcquisitionControl.AcquisitionFrameRate` | `float` | 目标帧率 |
| `cam.params.AcquisitionControl.TriggerMode` | `Hik.TriggerMode` | 触发开关 |
| `cam.params.AcquisitionControl.TriggerSource` | `Hik.TriggerSource` | 触发源 |
| `cam.params.DeviceControl.DeviceUserID` | `str` | 用户自定义相机名称 |
| `cam.params.TransportLayerControl.GevSCPSPacketSize` | `int` | GigE 包大小 |

### 常用命令节点

| 结构化路径 | 调用方式 | 说明 |
|---|---|---|
| `cam.params.AcquisitionControl.TriggerSoftware` | `.execute()` | 发送软触发 |
| `cam.params.UserSetControl.UserSetSelector` | `.set(Hik.UserSetSelector.USER_SET_1)` | 选择设备用户集 |
| `cam.params.UserSetControl.UserSetSave` | `.execute()` | 将当前参数保存到选定的用户集 |
| `cam.params.UserSetControl.UserSetLoad` | `.execute()` | 从选定的用户集加载参数 |

完整参数节点总表请参见
[`docs/camera_parameter_nodes_zh.md`](docs/camera_parameter_nodes_zh.md)。
英文版请参见
[`docs/camera_parameter_nodes.md`](docs/camera_parameter_nodes.md)。

### 示例：读写常用参数

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # 一次读取所有常用参数
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

## 与 MVS 输出保持一致

当 `use_sdk_decode=True`（默认）时，`HikCamera` 通过海康 SDK 图像处理管线
解码帧，输出与 MVS 桌面应用一致。以下调优 API 可用于复刻任何自定义 MVS
配置：

```python
cam.set_bayer_cvt_quality(Hik.BayerCvtQuality.BEST)   # 默认；FAST/BALANCED/BEST/BEST_PLUS
cam.set_bayer_filter_enable(True)                     # Bayer 平滑滤波
cam.set_bayer_gamma(0.45)                             # Bayer 伽玛
cam.set_gamma(Hik.PixelFormat.RGB8_PACKED, 0.45)      # 非 Bayer 像素的伽玛
cam.set_bayer_ccm([[1024, 0, 0], [0, 1024, 0], [0, 0, 1024]])
img = cam.image_contrast(img, contrast_factor=120)
img = cam.purple_fringing(img, purple_value=10)
cam.set_isp_config("/path/to/isp.xml")
img = cam.isp_process(img)
```

设置 `cam.use_sdk_decode = False`（或在构造时使用
`HikCamera(use_sdk_decode=False)` /
`HikCamera.from_device_info(..., use_sdk_decode=False)`）即可回退到
`hikcamera.utils.raw_to_numpy` 的 OpenCV 管线。

## 图像保存、编码、旋转、翻转与录制

```python
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.start_grabbing()

    image = cam.get_frame(output_format=Hik.OutputFormat.BGR8)

    # 通过 MV_CC_SaveImageToFileEx 保存图像
    cam.save_image_to_file(image, "out.png")          # 根据扩展名推断格式
    cam.save_image_to_file(image, "out.jpg", jpeg_quality=85)

    # 通过 MV_CC_SaveImageEx3 在内存中编码为 JPEG 字节
    jpeg_bytes = cam.encode_image(image, Hik.ImageFileFormat.JPEG)

    # 通过 MV_CC_RotateImage / MV_CC_FlipImage 旋转 / 翻转
    rotated = cam.rotate_image(image, Hik.RotateAngle.DEG_90)
    flipped = cam.flip_image(image, Hik.FlipDirection.HORIZONTAL)

    # 从 BGR8 图像录制一小段 MP4
    h, w = image.shape[:2]
    with cam.record("out.mp4", fps=25, width=w, height=h, fmt=Hik.RecordFormat.MP4) as rec:
        rec.write(image)
        for _ in range(100):
            rec.write(cam.get_frame(output_format=Hik.OutputFormat.BGR8))

    cam.stop_grabbing()
```

## 示例程序

```bash
# 保存单张图像
python demos/save_image.py --ip 192.168.1.100 --output image.png --format BGR8

# 录制 10 秒视频
python demos/save_video.py --ip 192.168.1.100 --output video.mp4 --duration 10

# 异常处理（断开连接检测）
python demos/exception_handling.py --ip 192.168.1.100 --duration 30

# 断开连接后自动重连
python demos/reconnect.py --ip 192.168.1.100 --retry-interval 3
```

## 项目结构

```
src/
  hikcamera/
    __init__.py        # 公开接口
    camera.py          # HikCamera 类
    enums.py           # 为 Hik 命名空间提供成员定义的枚举类型
    exceptions.py      # 异常层级
    sdk_wrapper.py     # MVS SDK 的 ctypes 绑定
    utils.py           # 图像转换（原始字节 → numpy）
demos/
  save_image.py        # 示例：捕获并保存单帧
  save_video.py        # 示例：捕获帧并保存为视频
  exception_handling.py  # 示例：取帧期间检测相机断开连接
  reconnect.py         # 示例：断开连接后自动重连
docs/
  camera_parameter_nodes.md  # 英文版结构化相机参数节点参考
  camera_parameter_nodes_zh.md  # 完整的中文版结构化相机参数节点参考
tests/
  conftest.py          # 测试夹具和模拟 SDK 辅助工具
  test_camera.py       # HikCamera 测试
  test_enums.py        # 枚举测试
  test_exceptions.py   # 异常层级测试
  test_integration.py  # 公开接口冒烟测试
  test_sdk_wrapper.py  # SDK 库加载器测试
  test_utils.py        # 图像转换测试
```

## 开发

```bash
# 安装开发依赖
poetry install --with dev

# 运行测试
poetry run pytest

# 代码检查
poetry run ruff check src/ tests/
```

## 发布

推送版本标签将触发发布工作流，该流程会：
1. 运行测试套件
2. 构建 wheel 和 sdist
3. 创建 GitHub Release 并附带分发文件

```bash
git tag v1.0.0
git push origin v1.0.0
```

## SDK 兼容性

``sdk_wrapper.py`` 中的 ctypes 结构体定义与官方海康威视 MVS SDK
``CameraParams.h`` 头文件对齐（已在 MVS SDK v4.x 上测试）。关键结构体：

- **``MV_GIGE_DEVICE_INFO``** ── 在 ``nCurrentIp`` 之前包含 ``nIpCfgOption``、
  ``nIpCfgCurrent``；``chSerialNumber`` 为 16 字节
- **``MV_USB3_DEVICE_INFO``** ── 包含 ``StreamEndPoint``、``EventEndPoint``、
  ``idVendor``、``idProduct``、``nDeviceNumber``、``chDeviceGUID``；所有
  字符串字段均为 64 字节
- **``MV_FRAME_OUT_INFO_EX``** ── 在 ``nFrameLen`` 和 ``nLostPacket`` 之间
  包含所有 chunk 水印字段（``nSecondCount``、``fGain``、``fExposureTime``、
  ``nRed``/``nGreen``/``nBlue``、``nFrameCounter``、``nTriggerIndex``、
  ROI 偏移等）
- **``MV_CC_PIXEL_CONVERT_PARAM``** ── 字段顺序与 SDK 一致：
  ``nDstLen`` 在 ``nDstBufferSize`` 之前

Bayer 图案命名遵循 OpenCV 约定（与 PFNC/SDK 相反）：
SDK ``BayerRG`` → OpenCV ``COLOR_BAYER_BG2BGR``。

## 许可证

MIT
