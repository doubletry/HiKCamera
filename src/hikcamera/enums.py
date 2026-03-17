"""
Enumerations used by the HiKCamera library.
HiKCamera 库使用的枚举类型。

These values mirror the constants defined in the Hikvision MVS SDK headers
(MvCameraControl.h and MvErrorDefine.h).  Using Python enumerations gives
callers type-safe, readable access to the underlying integer constants.
这些值与海康威视 MVS SDK 头文件（MvCameraControl.h 和 MvErrorDefine.h）中
定义的常量一一对应。使用 Python 枚举可为调用者提供类型安全、可读性强的访问方式。
"""

from __future__ import annotations

from enum import IntEnum, IntFlag

# ---------------------------------------------------------------------------
# SDK error codes (subset) / SDK 错误码（部分）
# ---------------------------------------------------------------------------

class MvErrorCode(IntEnum):
    """
    Common Hikvision SDK error codes.
    海康威视 SDK 常用错误码。
    """

    # Generic / 通用
    MV_OK = 0x00000000
    MV_E_HANDLE = 0x80000000         # Invalid handle or handle type mismatch / 无效句柄或句柄类型不匹配
    MV_E_SUPPORT = 0x80000001         # Not supported / 不支持
    MV_E_BUFOVER = 0x80000002         # Buffer overflow / 缓冲区溢出
    MV_E_CALLORDER = 0x80000003       # Function calling order error / 函数调用顺序错误
    MV_E_PARAMETER = 0x80000004       # Incorrect parameter / 参数错误
    MV_E_RESOURCE = 0x80000006        # Apply resource failed / 申请资源失败
    MV_E_NODATA = 0x80000007          # No data / 无数据
    MV_E_PRECONDITION = 0x80000008    # Precondition error or running environment changed / 前置条件错误或运行环境改变
    MV_E_VERSION = 0x80000009         # Version mismatch / 版本不匹配
    MV_E_NOENOUGH_BUF = 0x8000000A   # Insufficient memory / 内存不足
    MV_E_ABNORMAL_IMAGE = 0x8000000B  # Abnormal image, e.g. overexposure or underexposure / 图像异常（如过曝或欠曝）
    MV_E_LOAD_LIBRARY = 0x8000000C   # Load dynamic library failed / 加载动态库失败
    MV_E_NOOUTBUF = 0x8000000D        # No output buffer / 无输出缓冲区
    MV_E_ENCRYPT = 0x8000000E         # Encryption error / 加密错误
    MV_E_OPENFILE = 0x8000000F        # Open file error / 打开文件错误
    MV_E_FILE = 0x80000010            # File error / 文件错误
    MV_E_DYNAMICLIB = 0x80000011      # Dynamic library related error / 动态库相关错误

    # GenICam
    MV_E_GC_GENERIC = 0x80000100      # Generic error / 通用错误
    MV_E_GC_ARGUMENT = 0x80000101     # Invalid argument / 无效参数
    MV_E_GC_RANGE = 0x80000102        # Out of range / 超出范围
    MV_E_GC_PROPERTY = 0x80000103     # Property error / 属性错误
    MV_E_GC_RUNTIME = 0x80000104      # Runtime error / 运行时错误
    MV_E_GC_LOGICAL = 0x80000105      # Logical error / 逻辑错误
    MV_E_GC_ACCESS = 0x80000106       # Access denied (e.g. write to read-only) / 访问被拒绝（如写只读参数）
    MV_E_GC_TIMEOUT = 0x80000107      # Timeout / 超时
    MV_E_GC_DYNAMICCAST = 0x80000108  # Bad dynamic cast / 动态转换失败
    MV_E_GC_UNKNOWNTYPE = 0x8000010D  # Unknown type in GenICam / GenICam 未知类型
    MV_E_GC_INVALIDADDR = 0x8000010E  # Invalid address / 无效地址

    # GigE-specific / GigE 专用
    MV_E_NOTIMP = 0x80000200          # Not implemented (feature absent on device) / 未实现（设备不具备该功能）
    MV_E_UNKNOW = 0x800000FF          # Unknown error / 未知错误


# ---------------------------------------------------------------------------
# Camera access modes / 相机访问模式
# ---------------------------------------------------------------------------

class AccessMode(IntEnum):
    """
    Camera access mode passed to :py:meth:`HikCamera.open`.
    传入 :py:meth:`HikCamera.open` 的相机访问模式。

    These values correspond to ``MV_ACCESS_MODE`` in the SDK.
    这些值对应 SDK 中的 ``MV_ACCESS_MODE``。
    """

    EXCLUSIVE = 1
    """Exclusive access – only one application can connect.
    独占访问 ── 仅允许一个应用程序连接。"""

    EXCLUSIVE_WITH_SWITCH = 2
    """
    Exclusive access with takeover permission.  Another exclusive owner can
    take control by re-opening with this mode.
    带切换权限的独占访问。另一独占者可通过此模式重新打开以夺取控制权。
    """

    CONTROL = 3
    """
    Control access – one application controls the camera; others may observe.
    控制访问 ── 一个应用控制相机，其他应用可观察。
    """

    CONTROL_WITH_SWITCH = 4
    """
    Control access with takeover permission.
    带切换权限的控制访问。
    """

    CONTROL_SLAVE = 5
    """
    Slave/observer access alongside a control owner.
    与控制者并行的从属/观察访问。
    """

    MONITOR = 6
    """
    Read-only monitor access.  Cannot change camera parameters.
    只读监视访问，不可更改相机参数。
    """

    OPEN = 7
    """
    Open access – minimal, used mainly to read device information.
    开放访问 ── 最低权限，主要用于读取设备信息。
    """


# ---------------------------------------------------------------------------
# Transport layer / device interface type
# 传输层 / 设备接口类型
# ---------------------------------------------------------------------------

class TransportLayer(IntFlag):
    """
    Bit-mask that selects which transport layers to scan when enumerating.
    枚举时选择扫描哪些传输层的位掩码。

    These values correspond to ``MV_TRANSTYPE_*`` defines in the SDK.
    这些值对应 SDK 中的 ``MV_TRANSTYPE_*`` 宏定义。
    """

    GIGE = 0x00000001      # GigE Vision (GEV) / GigE 视觉
    USB = 0x00000004       # USB3 Vision (U3V) / USB3 视觉
    CAMERALINK = 0x00000008  # CameraLink (via frame grabber) / CameraLink（通过采集卡）
    ALL = GIGE | USB | CAMERALINK
    """Scan all supported transport layers. / 扫描所有支持的传输层。"""


# ---------------------------------------------------------------------------
# Multicast / unicast connection hints
# 组播 / 单播连接选项
# ---------------------------------------------------------------------------

class StreamingMode(IntEnum):
    """
    Unicast vs. multicast streaming hint used when opening a GigE camera.
    打开 GigE 相机时使用的单播/组播流传输提示。
    """

    UNICAST = 0
    """Standard unicast streaming (one receiver). / 标准单播流传输（单一接收端）。"""

    MULTICAST = 1
    """Multicast streaming (multiple receivers share the same stream).
    组播流传输（多个接收端共享同一流）。"""


# ---------------------------------------------------------------------------
# Pixel format constants / 像素格式常量
# ---------------------------------------------------------------------------

class PixelFormat(IntEnum):
    """
    Common Hikvision / PFNC pixel format codes.
    海康威视 / PFNC 常用像素格式码。

    These are the values returned by the ``PixelFormat`` camera parameter.
    这些是相机 ``PixelFormat`` 参数返回的值。
    """

    # Monochrome / 灰度
    MONO8 = 0x01080001
    MONO10 = 0x01100003
    MONO10_PACKED = 0x010C0004
    MONO12 = 0x01100005
    MONO12_PACKED = 0x010C0006
    MONO14 = 0x01100025
    MONO16 = 0x01100007

    # Bayer
    BAYER_GR8 = 0x01080008
    BAYER_RG8 = 0x01080009
    BAYER_GB8 = 0x0108000A
    BAYER_BG8 = 0x0108000B
    BAYER_GR10 = 0x0110000C
    BAYER_RG10 = 0x0110000D
    BAYER_GB10 = 0x0110000E
    BAYER_BG10 = 0x0110000F
    BAYER_GR12 = 0x01100010
    BAYER_RG12 = 0x01100011
    BAYER_GB12 = 0x01100012
    BAYER_BG12 = 0x01100013
    BAYER_GR10_PACKED = 0x010C0026
    BAYER_RG10_PACKED = 0x010C0027
    BAYER_GB10_PACKED = 0x010C0028
    BAYER_BG10_PACKED = 0x010C0029
    BAYER_GR12_PACKED = 0x010C002A
    BAYER_RG12_PACKED = 0x010C002B
    BAYER_GB12_PACKED = 0x010C002C
    BAYER_BG12_PACKED = 0x010C002D

    # RGB / BGR
    RGB8_PACKED = 0x02180014
    BGR8_PACKED = 0x02180015
    RGBA8_PACKED = 0x02200016
    BGRA8_PACKED = 0x02200017

    # YUV / YCbCr
    YUV411_PACKED = 0x020C001E
    YUV422_PACKED = 0x0210001F
    YUV422_YUYV_PACKED = 0x02100032
    YUV444_PACKED = 0x02180020
    YCBCR422_8 = 0x0210003B


# ---------------------------------------------------------------------------
# Image output format (what numpy array shape/dtype to produce)
# 图像输出格式（numpy 数组的 shape/dtype）
# ---------------------------------------------------------------------------

class OutputFormat(IntEnum):
    """
    Requested output format for the numpy array returned by frame-capture calls.
    帧捕获调用返回的 numpy 数组的期望输出格式。

    The SDK always decodes into the intermediate ``convert_pixel_type`` first,
    then HiKCamera reshapes the buffer into the right numpy dtype/shape.
    SDK 首先将数据解码为中间 ``convert_pixel_type``，
    然后 HiKCamera 将缓冲区重塑为正确的 numpy dtype/shape。
    """

    MONO8 = 0
    """Grayscale 8-bit  →  shape (H, W),  dtype uint8
    8 位灰度  →  shape (H, W),  dtype uint8"""

    MONO16 = 1
    """Grayscale 16-bit  →  shape (H, W),  dtype uint16
    16 位灰度  →  shape (H, W),  dtype uint16"""

    BGR8 = 2
    """BGR 24-bit  →  shape (H, W, 3),  dtype uint8  (OpenCV-native)
    BGR 24 位  →  shape (H, W, 3),  dtype uint8（OpenCV 原生格式）"""

    RGB8 = 3
    """RGB 24-bit  →  shape (H, W, 3),  dtype uint8
    RGB 24 位  →  shape (H, W, 3),  dtype uint8"""

    BGRA8 = 4
    """BGRA 32-bit  →  shape (H, W, 4),  dtype uint8
    BGRA 32 位  →  shape (H, W, 4),  dtype uint8"""

    RGBA8 = 5
    """RGBA 32-bit  →  shape (H, W, 4),  dtype uint8
    RGBA 32 位  →  shape (H, W, 4),  dtype uint8"""
