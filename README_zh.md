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
| **参数访问** | 获取/设置整型、浮点、布尔、枚举、字符串 GenICam 参数，完善的异常处理（不支持的参数会被优雅处理） |
| **相机信息** | `get_camera_info()` 一次调用即可获取常用参数（图像尺寸、帧率、曝光、增益、像素格式、设备型号等） |
| **配置管理** | 导出/导入相机配置文件；保存/加载设备用户集 |
| **帧捕获 – 轮询模式** | `start_grabbing()` + `get_frame()` |
| **帧捕获 – 回调模式** | `start_grabbing(callback=my_fn)` ── 自定义回调接收 numpy 数组 |
| **像素格式** | Mono8/10/12/16, Bayer GR/RG/GB/BG 8/10/12（紧凑和平面格式）, RGB/BGR 8, RGBA/BGRA 8, YUV422（UYVY 和 YUYV） |
| **输出格式** | `MONO8`、`MONO16`、`BGR8`、`RGB8`、`BGRA8`、`RGBA8`（均为 numpy 数组） |
| **SDK 像素转换** | `sdk_convert_pixel()` 将转换任务交由原生库完成 |
| **示例程序** | 保存单张图像、录制视频 |

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
# 通过 pip 安装（发布到 PyPI 后）
pip install hikcamera

# 或从源码通过 Poetry 安装
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

### 带错误处理的参数访问

```python
from hikcamera import HikCamera, ParameterNotSupportedError, ParameterReadOnlyError

with HikCamera.from_device_info(cameras[0]) as cam:
    cam.open()

    # 安全方式：自动忽略当前型号不支持的参数
    cam.set_parameter("GainAuto", "Off")

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

## 示例程序

```bash
# 保存单张图像
python demos/save_image.py --ip 192.168.1.100 --output image.png --format BGR8

# 录制 10 秒视频
python demos/save_video.py --ip 192.168.1.100 --output video.mp4 --fps 25 --duration 10
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
4. 通过可信发布机制发布到 PyPI

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
