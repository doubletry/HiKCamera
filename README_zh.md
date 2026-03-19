# HiKCamera

海康威视工业相机（MVS SDK）的 Python 3.12 库。

[English](README.md) | **中文**

[![CI](https://github.com/doubletry/HiKCamera/actions/workflows/ci.yml/badge.svg)](https://github.com/doubletry/HiKCamera/actions/workflows/ci.yml)

## 功能特性

| 功能 | 详情 |
|---|---|
| **相机枚举** | 查找主机上所有 GigE / USB3 / CameraLink 相机 |
| **灵活连接** | 通过 IP 地址或序列号连接 |
| **多种访问模式** | 独占、控制、监视、独占带切换、组播、单播 |
| **GigE 包大小** | 打开时自动检测最优包大小；支持手动配置 |
| **参数访问** | 获取/设置整型、浮点、布尔、枚举、字符串 GenICam 参数，完善的异常处理（不支持的参数会被优雅处理） |
| **相机信息** | `get_camera_info()` 一次调用即可获取常用参数（图像尺寸、帧率、曝光、增益、像素格式、设备型号等） |
| **配置管理** | 导出/导入相机配置文件；保存/加载设备用户集 |
| **帧捕获 – 轮询模式** | `start_grabbing()` + `get_frame()` |
| **帧捕获 – 回调模式** | `start_grabbing(callback=my_fn)` ── 自定义回调接收 numpy 数组 |
| **像素格式** | Mono8/10/12/16, Bayer GR/RG/GB/BG 8/10/12（紧凑和平面格式）, RGB/BGR 8, RGBA/BGRA 8, YUV422（UYVY 和 YUYV） |
| **输出格式** | `MONO8`、`MONO16`、`BGR8`、`RGB8`、`BGRA8`、`RGBA8`（均为 numpy 数组） |
| **SDK 像素转换** | `sdk_convert_pixel()` 将转换任务交由原生库完成 |
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
from hikcamera import HikCamera, TransportLayer

cameras = HikCamera.enumerate(TransportLayer.ALL)
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

### 轮询模式帧捕获

```python
import cv2
from hikcamera import HikCamera, AccessMode, OutputFormat

cameras = HikCamera.enumerate()
with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # 设置参数（自动忽略不支持的参数）
    cam.set_parameter("ExposureTime", 5000.0)
    cam.set_parameter("Gain", 1.0)

    cam.start_grabbing()
    frame = cam.get_frame(timeout_ms=1000, output_format=OutputFormat.BGR8)
    cam.stop_grabbing()

cv2.imwrite("frame.png", frame)
```

### 回调模式帧捕获

```python
import numpy as np
from hikcamera import HikCamera, AccessMode, OutputFormat

received_frames = []

def on_frame(image: np.ndarray, info: dict) -> None:
    received_frames.append(image)
    print(f"帧 {info['frame_num']}: {image.shape}")

with HikCamera.from_device_info(HikCamera.enumerate()[0]) as cam:
    cam.open(AccessMode.EXCLUSIVE)
    cam.start_grabbing(callback=on_frame, output_format=OutputFormat.BGR8)

    import time
    time.sleep(5)   # 采集 5 秒

    cam.stop_grabbing()
```

### 设备断开连接处理

使用回调模式取帧时，相机可能意外断开连接（如网线被拔出）。库会自动注册 SDK 异常
回调，并提供两种方式检测断开连接：

1. **`on_exception` 回调** ── 从 SDK 线程立即调用。
2. **`device_exception` 属性** ── 可从任意线程轮询。

`stop_grabbing()` 和 `get_frame()` 也会重新抛出已存储的异常。

```python
import threading
from hikcamera import (
    HikCamera, AccessMode, OutputFormat,
    DeviceDisconnectedError, HikCameraError,
)

disconnect_event = threading.Event()

def on_frame(image, info):
    print(f"帧 {info['frame_num']}")

def on_exception(exc: DeviceDisconnectedError):
    print(f"相机断开连接: {exc}")
    disconnect_event.set()

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)
    cam.start_grabbing(
        callback=on_frame,
        output_format=OutputFormat.BGR8,
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

断开连接后，需要释放旧的相机资源并创建新的句柄。典型模式：

```python
import time
from hikcamera import (
    HikCamera, AccessMode, OutputFormat,
    CameraNotFoundError, CameraConnectionError, HikCameraError,
)

def connect(ip: str) -> HikCamera:
    cam = HikCamera.from_ip(ip)
    cam.open(AccessMode.EXCLUSIVE)
    cam.start_grabbing(callback=on_frame, on_exception=on_exception)
    return cam

# 检测到断开连接后，清理旧相机：
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

# 重试循环
while True:
    time.sleep(3)
    try:
        cam = connect("192.168.1.100")
        print("重连成功！")
        break
    except (CameraNotFoundError, CameraConnectionError) as exc:
        print(f"重连失败: {exc}")
```

完整的生产级示例请参见 `demos/reconnect.py`。

### 组播流传输

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

### GigE 包大小配置

默认情况下，`open()` 会自动检测并设置 GigE 相机的最优包大小。
您也可以手动指定：

```python
from hikcamera import HikCamera, AccessMode, GIGE_PACKET_SIZE_DEFAULT, GIGE_PACKET_SIZE_JUMBO

# 自动检测最优包大小（默认行为）
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)  # 自动应用最优包大小
    ...

# 手动指定包大小（如 GIGE_PACKET_SIZE_DEFAULT 标准 MTU，
# GIGE_PACKET_SIZE_JUMBO 巨帧）
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE, packet_size=GIGE_PACKET_SIZE_JUMBO)
    ...

# 打开后查询或修改包大小
with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)
    print(cam.get_packet_size())          # 当前包大小
    print(cam.get_optimal_packet_size())  # SDK 推荐的最优值
    cam.set_packet_size(GIGE_PACKET_SIZE_DEFAULT)  # 手动覆盖
```

### 带错误处理的参数访问

```python
from hikcamera import HikCamera, ParameterNotSupportedError, ParameterReadOnlyError, GainAuto

with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open()

    # 安全方式：自动忽略当前型号不支持的参数
    cam.set_parameter("GainAuto", GainAuto.OFF)

    # 或显式处理
    try:
        value = cam.get_float_parameter("ExposureTime")
    except ParameterNotSupportedError:
        print("此相机不支持 ExposureTime 参数")

    try:
        cam.set_int_parameter("Width", 1920)
    except ParameterReadOnlyError:
        print("取帧期间 Width 为只读参数")
```

### 获取相机信息

```python
from hikcamera import HikCamera, AccessMode

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # 一次获取所有常用相机参数
    info = cam.get_camera_info()
    print(f"分辨率: {info.get('Width')}x{info.get('Height')}")
    print(f"曝光: {info.get('ExposureTime')} µs")
    print(f"增益: {info.get('Gain')}")
    print(f"帧率: {info.get('AcquisitionFrameRate')} fps")
    print(f"像素格式: {info.get('PixelFormat')}")
    print(f"型号: {info.get('DeviceModelName')}")
```

### 导出 / 导入相机配置

```python
from hikcamera import HikCamera, AccessMode

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # 导出当前配置到文件
    cam.export_config("camera_config.xml")

    # 从文件导入配置
    cam.import_config("camera_config.xml")
```

### 保存 / 加载设备用户集

```python
from hikcamera import HikCamera, AccessMode

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # 保存当前参数到用户集 1
    cam.save_user_set("UserSet1")

    # 稍后，从用户集 1 恢复参数
    cam.load_user_set("UserSet1")
```

## 可调参数

相机通过 MVS SDK 暴露 **GenICam** 标准参数。下表列出了 `get_camera_info()` 自动
收集的常用参数，但您可以通过带类型的 getter/setter 方法按名称访问**任何** GenICam
节点。

> **注意：** 并非每个型号的相机都支持所有参数。不支持的参数会抛出
> `ParameterNotSupportedError`（或被 `set_parameter()` / `get_parameter()` 静默跳过）。

### 参数访问方法

| 方法 | 说明 |
|---|---|
| `set_parameter(name, value)` | 通过 `isinstance` 校验的自动分派；枚举参数需传入对应枚举值（如 `GainAuto.OFF`）；自动跳过不支持的参数 |
| `get_parameter(name, default=None)` | 按 int → float → string 顺序尝试；不支持时返回 *default* |
| `get_int_parameter(name)` / `set_int_parameter(name, value)` | 整型参数访问 |
| `get_float_parameter(name)` / `set_float_parameter(name, value)` | 浮点型参数访问 |
| `get_bool_parameter(name)` / `set_bool_parameter(name, value)` | 布尔型参数访问 |
| `get_enum_parameter(name)` / `set_enum_parameter(name, value)` | 枚举型参数访问（整数值） |
| `set_enum_parameter_by_string(name, string_value)` | 按符号名称设置枚举参数（如 `"Off"`、`"Continuous"`） |
| `get_string_parameter(name)` / `set_string_parameter(name, value)` | 字符串型参数访问 |
| `execute_command(name)` | 执行命令节点（如 `"TriggerSoftware"`） |
| `get_camera_info()` | 一次调用获取下表中所有常用参数 |
| `get_optimal_packet_size()` | 查询 SDK 获取 GigE 最优包大小（仅 GigE 相机） |
| `get_packet_size()` / `set_packet_size(size)` | 获取/设置 GigE 流传输包大小（`GevSCPSPacketSize`） |

### 常用参数

#### 图像格式

| 参数名 | 类型 | 读写 | 说明 |
|---|---|---|---|
| `Width` | int | R/W ¹ | 图像宽度（像素） |
| `Height` | int | R/W ¹ | 图像高度（像素） |
| `OffsetX` | int | R/W | 水平偏移（ROI 起点） |
| `OffsetY` | int | R/W | 垂直偏移（ROI 起点） |
| `PixelFormat` | enum | R/W | 像素格式（返回原始 `int`；可通过 `PixelFormat(val)` 转换为枚举） |
| `WidthMax` | int | R | 最大允许宽度 |
| `HeightMax` | int | R | 最大允许高度 |
| `PayloadSize` | int | R | 图像数据负载大小（字节） |

> ¹ 取帧期间可能变为只读，取决于相机型号。

#### 曝光与增益

| 参数名 | 类型 | 读写 | 说明 |
|---|---|---|---|
| `ExposureTime` | float | R/W | 曝光时间（µs） |
| `ExposureAuto` | enum | R/W | 自动曝光模式（`Off` / `Once` / `Continuous`） |
| `Gain` | float | R/W | 增益值（dB） |
| `GainAuto` | enum | R/W | 自动增益模式（`Off` / `Once` / `Continuous`） |
| `Gamma` | float | R/W | Gamma 校正值 |
| `GammaEnable` | bool | R/W | 启用 / 禁用 Gamma 校正 |

#### 帧率

| 参数名 | 类型 | 读写 | 说明 |
|---|---|---|---|
| `AcquisitionFrameRate` | float | R/W | 目标采集帧率（fps） |
| `AcquisitionFrameRateEnable` | bool | R/W | 启用 / 禁用帧率限制 |
| `ResultingFrameRate` | float | R | 实际帧率（fps） |

#### 触发

| 参数名 | 类型 | 读写 | 说明 |
|---|---|---|---|
| `TriggerMode` | enum | R/W | 触发模式（`On` / `Off`） |
| `TriggerSource` | enum | R/W | 触发源（如 `Software`、`Line0`） |

#### 白平衡

| 参数名 | 类型 | 读写 | 说明 |
|---|---|---|---|
| `BalanceWhiteAuto` | enum | R/W | 自动白平衡模式（`Off` / `Once` / `Continuous`） |

#### 设备信息（只读）

| 参数名 | 类型 | 读写 | 说明 |
|---|---|---|---|
| `DeviceModelName` | string | R | 相机型号名称 |
| `DeviceSerialNumber` | string | R | 序列号 |
| `DeviceFirmwareVersion` | string | R | 固件版本 |
| `DeviceUserID` | string | R/W | 用户自定义相机标识 |

#### GigE 网络（仅 GigE 相机）

| 参数名 | 类型 | 读写 | 说明 |
|---|---|---|---|
| `GevSCPSPacketSize` | int | R/W | GigE 流传输包大小（字节），`open()` 时自动配置 |

#### 常用命令

以下节点通过 `execute_command()` 执行：

| 命令 | 说明 |
|---|---|
| `TriggerSoftware` | 发送软触发 |
| `UserSetSave` | 将当前参数保存到选定的用户集 |
| `UserSetLoad` | 从选定的用户集加载参数 |

### 示例：读写参数

```python
from hikcamera import HikCamera, AccessMode, GainAuto

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(AccessMode.EXCLUSIVE)

    # 一次读取所有常用参数
    info = cam.get_camera_info()
    print(info)

    # 高层便捷方法（自动类型分派）
    cam.set_parameter("ExposureTime", 5000.0)
    cam.set_parameter("Gain", 2.5)
    cam.set_parameter("AcquisitionFrameRateEnable", True)
    cam.set_parameter("GainAuto", GainAuto.OFF)    # 类型化枚举

    # 带类型的访问方式（可获取完整错误信息）
    exposure = cam.get_float_parameter("ExposureTime")
    width = cam.get_int_parameter("Width")

    # 执行命令
    cam.execute_command("TriggerSoftware")
```

## 示例程序

```bash
# 保存单张图像
python demos/save_image.py --ip 192.168.1.100 --output image.png --format BGR8

# 录制 10 秒视频
python demos/save_video.py --ip 192.168.1.100 --output video.mp4 --fps 25 --duration 10

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
    enums.py           # 枚举类型（AccessMode、PixelFormat、OutputFormat 等）
    exceptions.py      # 异常层级
    sdk_wrapper.py     # MVS SDK 的 ctypes 绑定
    utils.py           # 图像转换（原始字节 → numpy）
demos/
  save_image.py        # 示例：捕获并保存单帧
  save_video.py        # 示例：捕获帧并保存为视频
  exception_handling.py  # 示例：取帧期间检测相机断开连接
  reconnect.py         # 示例：断开连接后自动重连
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
