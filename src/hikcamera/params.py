"""
Structured camera parameter definitions with type-safe validation.
相机参数结构化定义与类型安全校验。

This module provides :class:`ParamNode` descriptors and category namespace
classes that mirror the parameter node table from the Hikvision SDK
development guide (V4.7.0).  Each parameter carries metadata including
its GenICam name, expected data type, access mode, description, and
optional numeric range.

Typical usage / 典型用法
-----------------------

.. code-block:: python

    from hikcamera import Hik, HikCamera

    cam = HikCamera.from_ip("192.168.1.100")
    cam.open(Hik.AccessMode.EXCLUSIVE)

    # IDE auto-completion & validation before the SDK call
    cam.params.AcquisitionControl.ExposureTime.set(5000.0)
    cam.params.AnalogControl.Gain.set(10.0)
    cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol, overload

from .enums import Hik
from .exceptions import ParameterReadOnlyError, ParameterValueError

if TYPE_CHECKING:
    from .camera import BoundParamNode

    class _BoundNodeOwner(Protocol):
        _camera: Any



@dataclass(frozen=True, slots=True)
class ParamNode:
    """
    Immutable descriptor for a single GenICam parameter node.
    单个 GenICam 参数节点的不可变描述。

    Each instance carries the metadata needed for IDE auto-completion, type
    checking, and range validation **before** any SDK call is issued.
    每个实例包含在发出任何 SDK 调用 **之前** 用于 IDE 自动补全、类型检查
    和范围校验所需的元数据。

    Attributes / 属性
    -----------------
    name:
        GenICam node name (the ``key`` parameter for ``_GetNode``).
        GenICam 节点名称（``_GetNode`` 的 ``key`` 参数）。
    data_type:
        Expected Python type or enum class.  One of ``int``, ``float``,
        ``bool``, ``str``, a ``StrEnum`` / ``IntEnum`` subclass, or the
        literal string ``"command"`` for command nodes.
        期望的 Python 类型或枚举类。可为 ``int``、``float``、``bool``、
        ``str``、``StrEnum`` / ``IntEnum`` 子类，或命令节点的字面字符串
        ``"command"``。
    access:
        Access mode as documented in the SDK parameter node table.
        SDK 参数节点表中记录的访问模式。
    description:
        Human-readable description (bilingual).
        可读描述（双语）。
    unit:
        Physical unit (e.g. ``"us"``, ``"dB"``, ``"fps"``), or ``None``.
        物理单位（如 ``"us"``、``"dB"``、``"fps"``），或 ``None``。
    min_value:
        Minimum allowed value for numeric types, or ``None``.
        数值类型的最小允许值，或 ``None``。
    max_value:
        Maximum allowed value for numeric types, or ``None``.
        数值类型的最大允许值，或 ``None``。
    step:
        Step / increment for integer types, or ``None``.
        整型的步进/增量，或 ``None``。
    """

    name: str
    data_type: type | str
    access: Literal["R", "W", "R/W", "R/(W)"]
    description: str
    unit: str | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    step: int | None = None

    if TYPE_CHECKING:
        @overload
        def __get__(self, instance: None, owner: type | None = None) -> ParamNode: ...

        @overload
        def __get__(
            self,
            instance: _BoundNodeOwner,
            owner: type | None = None,
        ) -> BoundParamNode: ...

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        """
        Return the raw descriptor on class access, or a camera-bound node view
        on bound category instances.
        在类访问时返回原始描述符，在绑定分类实例上访问时返回相机绑定节点视图。
        """
        if instance is None:
            return self
        from .camera import BoundParamNode

        return BoundParamNode(instance._camera, self)

    # ------------------------------------------------------------------
    # Validation / 校验
    # ------------------------------------------------------------------

    def validate(self, value: Any) -> Any:
        """
        Validate *value* against this node's metadata and return the
        (possibly promoted) value.

        根据此节点的元数据校验 *value*，并返回（可能已提升类型的）值。

        Raises / 异常
        -------------
        ParameterReadOnlyError
            When the node is read-only (``access == "R"``).
            当节点为只读（``access == "R"``）时抛出。
        ParameterValueError
            When the value type or range is invalid.
            当值的类型或范围无效时抛出。
        """
        # 1. Read-only check / 只读检查
        if self.access == "R":
            raise ParameterReadOnlyError(
                f"Parameter {self.name!r} is read-only (access={self.access!r})"
            )

        # 2. Command nodes / 命令节点
        if self.data_type == "command":
            return value  # Command nodes accept any trigger value

        expected_type: type = self.data_type  # type: ignore[assignment]

        # 3. Reject bool for int/float schemas / 对 int/float 拒绝 bool
        if expected_type in (int, float) and isinstance(value, bool):
            raise ParameterValueError(
                f"Parameter {self.name!r} expects {expected_type.__name__}, "
                f"got bool: {value!r}"
            )

        # 4. Allow int → float promotion / 允许 int → float 提升
        if expected_type is float and isinstance(value, int):
            value = float(value)

        # 5. Type check / 类型检查
        if not isinstance(value, expected_type):
            type_name = expected_type.__name__ if isinstance(expected_type, type) else str(expected_type)
            raise ParameterValueError(
                f"Parameter {self.name!r} expects {type_name}, "
                f"got {type(value).__name__}: {value!r}"
            )

        # 6. Range check for numeric types / 数值类型的范围检查
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if self.min_value is not None and value < self.min_value:
                raise ParameterValueError(
                    f"Parameter {self.name!r}: value {value!r} is below "
                    f"minimum {self.min_value}"
                    + (f" {self.unit}" if self.unit else "")
                )
            if self.max_value is not None and value > self.max_value:
                raise ParameterValueError(
                    f"Parameter {self.name!r}: value {value!r} is above "
                    f"maximum {self.max_value}"
                    + (f" {self.unit}" if self.unit else "")
                )

        return value

    # Allow ParamNode to be used directly as a string key (its name).
    # 允许 ParamNode 直接作为字符串键（其名称）使用。
    def __str__(self) -> str:
        return self.name

# ===================================================================
# Category namespace classes / 分类命名空间类
# ===================================================================
# Each class groups related parameters from the SDK parameter node table.
# 每个类将 SDK 参数节点表中相关的参数分组。

class DeviceControl:
    """
    Device Control parameters.  设备控制参数。
    """
    DeviceType = ParamNode(
        "DeviceType", Hik.DeviceType, "R",
        "设备类型 / Device type",
    )
    DeviceScanType = ParamNode(
        "DeviceScanType", Hik.DeviceScanType, "R",
        "设备 sensor 的扫描方式 / Device sensor scan type",
    )
    DeviceVendorName = ParamNode(
        "DeviceVendorName", str, "R",
        "设备的制造商名称 / Manufacturer name",
    )
    DeviceModelName = ParamNode(
        "DeviceModelName", str, "R",
        "设备型号 / Device model name",
    )
    DeviceManufacturerInfo = ParamNode(
        "DeviceManufacturerInfo", str, "R",
        "设备的制造商信息 / Manufacturer info",
    )
    DeviceVersion = ParamNode(
        "DeviceVersion", str, "R",
        "设备版本 / Device version",
    )
    DeviceFirmwareVersion = ParamNode(
        "DeviceFirmwareVersion", str, "R",
        "固件版本 / Firmware version",
    )
    DeviceSerialNumber = ParamNode(
        "DeviceSerialNumber", str, "R",
        "设备序列号 / Device serial number",
    )
    DeviceID = ParamNode(
        "DeviceID", str, "R",
        "设备 ID / Device ID",
    )
    DeviceUserID = ParamNode(
        "DeviceUserID", str, "R/W",
        "用户自定义的名称 / User-defined device name",
    )
    DeviceUptime = ParamNode(
        "DeviceUptime", int, "R",
        "设备运行时间 / Device uptime", min_value=0,
    )
    DeviceLinkSelector = ParamNode(
        "DeviceLinkSelector", int, "R/(W)",
        "设备连接选择 / Device link selector", min_value=0,
    )
    DeviceLinkSpeed = ParamNode(
        "DeviceLinkSpeed", int, "R",
        "传输链路速度 / Transmission link speed", min_value=0,
    )
    DeviceLinkConnectionCount = ParamNode(
        "DeviceLinkConnectionCount", int, "R",
        "设备连接数量 / Device link connection count", min_value=0,
    )
    DeviceLinkHeartbeatMode = ParamNode(
        "DeviceLinkHeartbeatMode", Hik.DeviceHeartbeatMode, "R/W",
        "是否需要心跳 / Heartbeat mode",
    )
    DeviceStreamChannelCount = ParamNode(
        "DeviceStreamChannelCount", int, "R",
        "流通道数量 / Stream channel count", min_value=0,
    )
    DeviceStreamChannelSelector = ParamNode(
        "DeviceStreamChannelSelector", int, "R/(W)",
        "流通道选择 / Stream channel selector", min_value=0,
    )
    DeviceStreamChannelType = ParamNode(
        "DeviceStreamChannelType", Hik.DeviceStreamChannelType, "R",
        "流通道类型 / Stream channel type",
    )
    DeviceStreamChannelLink = ParamNode(
        "DeviceStreamChannelLink", int, "R",
        "流通道连接数量 / Stream channel link count", min_value=0,
    )
    DeviceStreamChannelEndianness = ParamNode(
        "DeviceStreamChannelEndianness", Hik.DeviceStreamChannelEndianness, "R",
        "图像数据的字节序 / Image data byte order",
    )
    DeviceStreamChannelPacketSize = ParamNode(
        "DeviceStreamChannelPacketSize", int, "R/(W)",
        "接收端流数据的包大小 / Stream data packet size",
        min_value=220, max_value=9156, step=8,
    )
    DeviceEventChannelCount = ParamNode(
        "DeviceEventChannelCount", int, "R",
        "设备支持的事件通道数 / Event channel count", min_value=0,
    )
    DeviceCharacterSet = ParamNode(
        "DeviceCharacterSet", Hik.DeviceCharacterSet, "R",
        "设备寄存器中使用的字符集 / Character set in device registers",
    )
    DeviceReset = ParamNode(
        "DeviceReset", "command", "W",
        "重启设备 / Reset device",
    )
    DeviceMaxThroughput = ParamNode(
        "DeviceMaxThroughput", int, "R",
        "设备最大吞吐量 / Maximum device throughput", min_value=0,
    )
    DeviceConnectionSelector = ParamNode(
        "DeviceConnectionSelector", int, "R/(W)",
        "设备连接选择 / Device connection selector", min_value=0,
    )
    DeviceConnectionSpeed = ParamNode(
        "DeviceConnectionSpeed", int, "R",
        "设备连接速度 / Device connection speed", unit="Mbps", min_value=0,
    )


class ImageFormatControl:
    """
    Image Format Control parameters.  图像格式控制参数。
    """
    WidthMax = ParamNode(
        "WidthMax", int, "R",
        "图像最大宽度 / Maximum image width", min_value=1,
    )
    HeightMax = ParamNode(
        "HeightMax", int, "R",
        "图像最大高度 / Maximum image height", min_value=1,
    )
    RegionSelector = ParamNode(
        "RegionSelector", Hik.RegionSelector, "R/(W)",
        "ROI 选择器 / ROI selector",
    )
    RegionDestination = ParamNode(
        "RegionDestination", Hik.RegionDestination, "R/(W)",
        "该 ROI 对应的码流 / Stream destination for region",
    )
    Width = ParamNode(
        "Width", int, "R/(W)",
        "ROI 的宽 / ROI width", min_value=1,
    )
    Height = ParamNode(
        "Height", int, "R/(W)",
        "ROI 的高 / ROI height", min_value=1,
    )
    OffsetX = ParamNode(
        "OffsetX", int, "R/W",
        "ROI 的水平方向偏移量 / ROI horizontal offset", min_value=0,
    )
    OffsetY = ParamNode(
        "OffsetY", int, "R/W",
        "ROI 的竖直方向偏移量 / ROI vertical offset", min_value=0,
    )
    ReverseScanDirection = ParamNode(
        "ReverseScanDirection", bool, "R/(W)",
        "转换扫描方向 / Reverse scan direction",
    )
    PixelFormat = ParamNode(
        "PixelFormat", Hik.PixelFormat, "R/(W)",
        "图像像素格式 / Image pixel format",
    )
    PixelSize = ParamNode(
        "PixelSize", Hik.PixelSize, "R/(W)",
        "一个像素包含的比特数 / Bits per pixel",
    )
    ImageCompressionMode = ParamNode(
        "ImageCompressionMode", Hik.ImageCompressionMode, "R/(W)",
        "图像压缩模式 / Image compression mode",
    )
    ImageCompressionQuality = ParamNode(
        "ImageCompressionQuality", int, "R/(W)",
        "图像压缩质量 / Image compression quality", min_value=50,
    )
    TestPatternGeneratorSelector = ParamNode(
        "TestPatternGeneratorSelector", Hik.TestPatternGeneratorSelector, "R/(W)",
        "测试图像生成器选择 / Test pattern generator selector",
    )
    TestPattern = ParamNode(
        "TestPattern", Hik.TestPattern, "R/(W)",
        "测试图像选择 / Test pattern selection",
    )
    FrameSpecInfoSelector = ParamNode(
        "FrameSpecInfoSelector", Hik.FrameSpecInfoSelector, "R/(W)",
        "水印信息选择 / Watermark info selector",
    )
    FrameSpecInfo = ParamNode(
        "FrameSpecInfo", bool, "R/W",
        "是否使能该水印信息 / Enable watermark info",
    )
    BinningHorizontal = ParamNode(
        "BinningHorizontal", int, "R/(W)",
        "水平合并 / Horizontal binning", min_value=1,
    )
    BinningVertical = ParamNode(
        "BinningVertical", int, "R/(W)",
        "垂直合并 / Vertical binning", min_value=1,
    )
    DecimationHorizontal = ParamNode(
        "DecimationHorizontal", int, "R/(W)",
        "水平抽取 / Horizontal decimation", min_value=1,
    )
    DecimationVertical = ParamNode(
        "DecimationVertical", int, "R/(W)",
        "垂直抽取 / Vertical decimation", min_value=1,
    )


class AcquisitionControl:
    """
    Acquisition Control parameters.  采集控制参数。
    """
    AcquisitionMode = ParamNode(
        "AcquisitionMode", Hik.AcquisitionMode, "R/(W)",
        "采集模式 / Acquisition mode (single/multi/continuous)",
    )
    AcquisitionStart = ParamNode(
        "AcquisitionStart", "command", "W",
        "开始取流 / Start acquisition",
    )
    AcquisitionStop = ParamNode(
        "AcquisitionStop", "command", "W",
        "结束取流 / Stop acquisition",
    )
    AcquisitionBurstFrameCount = ParamNode(
        "AcquisitionBurstFrameCount", int, "R/W",
        "一次触发采集的帧数 / Burst frame count", min_value=0,
    )
    AcquisitionLineRate = ParamNode(
        "AcquisitionLineRate", int, "R/W",
        "行频设置 / Line rate", min_value=1,
    )
    AcquisitionLineRateEnable = ParamNode(
        "AcquisitionLineRateEnable", bool, "R/W",
        "行频控制使能 / Line rate control enable",
    )
    ResultingLineRate = ParamNode(
        "ResultingLineRate", int, "R",
        "实际行频 / Resulting line rate", unit="Hz", min_value=0,
    )
    ResultingFrameRate = ParamNode(
        "ResultingFrameRate", float, "R",
        "相机的实际采集帧率 / Resulting frame rate", unit="fps", min_value=0.0,
    )
    AcquisitionFrameRate = ParamNode(
        "AcquisitionFrameRate", float, "R/W",
        "采集帧率 / Acquisition frame rate", unit="fps", min_value=0.0,
    )
    AcquisitionFrameRateEnable = ParamNode(
        "AcquisitionFrameRateEnable", bool, "R/W",
        "帧率控制使能 / Frame rate control enable",
    )
    TriggerSelector = ParamNode(
        "TriggerSelector", Hik.TriggerSelector, "R/W",
        "触发事件选择 / Trigger event selector",
    )
    TriggerMode = ParamNode(
        "TriggerMode", Hik.TriggerMode, "R/W",
        "触发模式 / Trigger mode (on/off)",
    )
    TriggerSource = ParamNode(
        "TriggerSource", Hik.TriggerSource, "R/W",
        "触发源 / Trigger source",
    )
    TriggerActivation = ParamNode(
        "TriggerActivation", Hik.TriggerActivation, "R/W",
        "触发沿/电平 / Trigger activation edge/level",
    )
    TriggerDelay = ParamNode(
        "TriggerDelay", float, "R/W",
        "触发延时 / Trigger delay", unit="us", min_value=0.0,
    )
    TriggerSoftware = ParamNode(
        "TriggerSoftware", "command", "W",
        "软触发执行 / Execute software trigger",
    )
    ExposureMode = ParamNode(
        "ExposureMode", Hik.ExposureMode, "R/W",
        "曝光模式选择 / Exposure mode",
    )
    ExposureTime = ParamNode(
        "ExposureTime", float, "R/W",
        "曝光时间 / Exposure time", unit="us", min_value=0.0,
    )
    ExposureAuto = ParamNode(
        "ExposureAuto", Hik.ExposureAuto, "R/W",
        "自动曝光 / Auto exposure",
    )
    AutoExposureTimeLowerLimit = ParamNode(
        "AutoExposureTimeLowerLimit", int, "R/(W)",
        "自动曝光时间下限 / Auto exposure time lower limit", unit="us", min_value=0,
    )
    AutoExposureTimeUpperLimit = ParamNode(
        "AutoExposureTimeUpperLimit", int, "R/(W)",
        "自动曝光时间上限 / Auto exposure time upper limit", unit="us", min_value=0,
    )
    FrameTimeoutEnable = ParamNode(
        "FrameTimeoutEnable", bool, "R/W",
        "帧超时使能 / Frame timeout enable",
    )
    FrameTimeoutTime = ParamNode(
        "FrameTimeoutTime", int, "R/W",
        "帧超时时间 / Frame timeout time", unit="ms", min_value=87,
    )


class AnalogControl:
    """
    Analog Control parameters.  模拟控制参数。
    """
    Gain = ParamNode(
        "Gain", float, "R/W",
        "增益值 / Gain", unit="dB", min_value=0.0,
    )
    GainAuto = ParamNode(
        "GainAuto", Hik.GainAuto, "R/W",
        "自动增益 / Auto gain",
    )
    AutoGainLowerLimit = ParamNode(
        "AutoGainLowerLimit", float, "R/W",
        "自动增益值下限 / Auto gain lower limit", unit="dB", min_value=0.0,
    )
    AutoGainUpperLimit = ParamNode(
        "AutoGainUpperLimit", float, "R/W",
        "自动增益值上限 / Auto gain upper limit", unit="dB", min_value=0.0,
    )
    ADCGainEnable = ParamNode(
        "ADCGainEnable", bool, "R/W",
        "ADC 增益使能 / ADC gain enable",
    )
    DigitalShift = ParamNode(
        "DigitalShift", float, "R",
        "数字偏移调节 / Digital shift", min_value=0.0,
    )
    DigitalShiftEnable = ParamNode(
        "DigitalShiftEnable", bool, "R/W",
        "数字偏移使能 / Digital shift enable",
    )
    Brightness = ParamNode(
        "Brightness", int, "R/W",
        "亮度 / Brightness", min_value=0,
    )
    BlackLevel = ParamNode(
        "BlackLevel", float, "R/W",
        "黑电平调节 / Black level", min_value=0.0,
    )
    BlackLevelEnable = ParamNode(
        "BlackLevelEnable", bool, "R/W",
        "黑电平调节使能 / Black level enable",
    )
    BalanceWhiteAuto = ParamNode(
        "BalanceWhiteAuto", Hik.BalanceWhiteAuto, "R/W",
        "自动白平衡 / Auto white balance",
    )
    BalanceRatioSelector = ParamNode(
        "BalanceRatioSelector", Hik.BalanceRatioSelector, "R",
        "白平衡比例选择 / White balance ratio selector",
    )
    BalanceRatio = ParamNode(
        "BalanceRatio", int, "R",
        "白平衡值 / White balance ratio", min_value=0,
    )
    Gamma = ParamNode(
        "Gamma", float, "R/W",
        "伽马调节 / Gamma correction", min_value=0.0,
    )
    GammaSelector = ParamNode(
        "GammaSelector", Hik.GammaSelector, "R/W",
        "Gamma 选择 / Gamma selector",
    )
    GammaEnable = ParamNode(
        "GammaEnable", bool, "R/W",
        "Gamma 使能 / Gamma enable",
    )
    Hue = ParamNode(
        "Hue", int, "R",
        "色度值调节 / Hue adjustment", min_value=0,
    )
    HueEnable = ParamNode(
        "HueEnable", bool, "R/W",
        "色度使能 / Hue enable",
    )
    Saturation = ParamNode(
        "Saturation", int, "R",
        "饱和度值调节 / Saturation adjustment", min_value=0,
    )
    SaturationEnable = ParamNode(
        "SaturationEnable", bool, "R/W",
        "饱和度使能 / Saturation enable",
    )
    AutoFunctionAOISelector = ParamNode(
        "AutoFunctionAOISelector", Hik.AutoFunctionAOISelector, "R/W",
        "自动 AOI 选择 / Auto function AOI selector",
    )
    AutoFunctionAOIWidth = ParamNode(
        "AutoFunctionAOIWidth", int, "R/W",
        "自动 AOI 宽 / Auto function AOI width", min_value=0,
    )
    AutoFunctionAOIHeight = ParamNode(
        "AutoFunctionAOIHeight", int, "R/W",
        "自动 AOI 高 / Auto function AOI height", min_value=0,
    )
    AutoFunctionAOIOffsetX = ParamNode(
        "AutoFunctionAOIOffsetX", int, "R",
        "自动 AOI 水平方向偏移 / Auto function AOI horizontal offset", min_value=0,
    )
    AutoFunctionAOIUsageIntensity = ParamNode(
        "AutoFunctionAOIUsageIntensity", bool, "R/W",
        "根据 AOI 区域自动曝光 / Auto exposure based on AOI",
    )
    AutoFunctionAOIUsageWhiteBalance = ParamNode(
        "AutoFunctionAOIUsageWhiteBalance", bool, "R",
        "根据 AOI 区域自动白平衡 / Auto white balance based on AOI",
    )


class LUTControl:
    """
    LUT Control parameters.  LUT 控制参数。
    """
    LUTSelector = ParamNode(
        "LUTSelector", Hik.LUTSelector, "R/W",
        "LUT 通道选择 / LUT channel selector",
    )
    LUTEnable = ParamNode(
        "LUTEnable", bool, "R/W",
        "LUT 使能 / LUT enable",
    )
    LUTIndex = ParamNode(
        "LUTIndex", int, "R/W",
        "LUT 索引号 / LUT index", min_value=0,
    )
    LUTValue = ParamNode(
        "LUTValue", int, "R/W",
        "LUT 值 / LUT value",
    )


class EncoderControl:
    """
    Encoder Control parameters.  编码器控制参数。
    """
    EncoderSelector = ParamNode(
        "EncoderSelector", Hik.EncoderSelector, "R/W",
        "编码器选择 / Encoder selector",
    )
    EncoderSourceA = ParamNode(
        "EncoderSourceA", Hik.LineSelector, "R/W",
        "编码器 A 源选择 / Encoder source A",
    )
    EncoderSourceB = ParamNode(
        "EncoderSourceB", Hik.LineSelector, "R/W",
        "编码器 B 源选择 / Encoder source B",
    )
    EncoderTriggerMode = ParamNode(
        "EncoderTriggerMode", Hik.EncoderTriggerMode, "R/W",
        "编码器触发模式 / Encoder trigger mode",
    )
    EncoderCounterMode = ParamNode(
        "EncoderCounterMode", Hik.EncoderCounterMode, "R/W",
        "编码器计数模式 / Encoder counter mode",
    )
    EncoderCounter = ParamNode(
        "EncoderCounter", int, "R",
        "编码器计数器值 / Encoder counter value", min_value=0,
    )
    EncoderCounterMax = ParamNode(
        "EncoderCounterMax", int, "R/W",
        "编码器计数器最大值 / Encoder counter max", min_value=1,
    )
    # NOTE: The SDK documentation (V4.7.0) marks these command nodes as "R/W".
    # This is unusual for commands but matches the official parameter node table.
    # 注：SDK 文档（V4.7.0）将这些命令节点标记为 "R/W"。
    # 这对命令来说不常见，但与官方参数节点表一致。
    EncoderCounterReset = ParamNode(
        "EncoderCounterReset", "command", "R/W",
        "编码器计数器复位 / Encoder counter reset",
    )
    EncoderMaxReverseCounter = ParamNode(
        "EncoderMaxReverseCounter", int, "R/W",
        "编码器最大反转计数器值 / Encoder max reverse counter", min_value=1,
    )
    EncoderReverseCounterReset = ParamNode(
        "EncoderReverseCounterReset", "command", "R/W",
        "编码器反转计数器复位 / Encoder reverse counter reset",
    )


class FrequencyConverterControl:
    """
    Frequency Converter Control parameters.  分频器控制参数。
    """
    InputSource = ParamNode(
        "InputSource", Hik.LineSelector, "R/W",
        "分频器输入源 / Frequency converter input source",
    )
    SignalAlignment = ParamNode(
        "SignalAlignment", Hik.FrequencyConverterSignalAlignment, "R/W",
        "分频器信号方向 / Signal alignment edge",
    )
    PreDivider = ParamNode(
        "PreDivider", int, "R/W",
        "前置分频器调节 / Pre-divider", min_value=1,
    )
    Multiplier = ParamNode(
        "Multiplier", int, "R/W",
        "倍频器调节 / Multiplier", min_value=1,
    )
    PostDivider = ParamNode(
        "PostDivider", int, "R/W",
        "后置分频器调节 / Post-divider", min_value=1,
    )


class ShadingCorrection:
    """
    Shading Correction parameters.  明暗场校正参数。
    """
    ShadingSelector = ParamNode(
        "ShadingSelector", Hik.ShadingSelector, "R/W",
        "明暗场校正选择 / Shading correction selector",
    )
    # NOTE: The SDK documentation (V4.7.0) marks this command node as "R/(W)".
    # 注：SDK 文档（V4.7.0）将此命令节点标记为 "R/(W)"。
    ActivateShading = ParamNode(
        "ActivateShading", "command", "R/(W)",
        "主动校正 / Activate shading correction",
    )
    NUCEnable = ParamNode(
        "NUCEnable", bool, "R/W",
        "NUC 使能开关 / NUC enable",
    )
    PRNUCEnable = ParamNode(
        "PRNUCEnable", bool, "R/W",
        "PRNUC 状态开关 / PRNUC enable",
    )


class DigitalIOControl:
    """
    Digital IO Control parameters.  数字 IO 控制参数。
    """
    LineSelector = ParamNode(
        "LineSelector", Hik.LineSelector, "R/W",
        "I/O 选择 / I/O line selector",
    )
    LineMode = ParamNode(
        "LineMode", Hik.LineMode, "R/(W)",
        "I/O 模式 / I/O line mode",
    )
    LineStatus = ParamNode(
        "LineStatus", bool, "R/(W)",
        "I/O 状态 / I/O line status",
    )
    LineStatusAll = ParamNode(
        "LineStatusAll", int, "R",
        "所有 I/O 状态 / All I/O line status", min_value=0,
    )
    LineDebouncerTime = ParamNode(
        "LineDebouncerTime", int, "R/W",
        "I/O 去抖时间 / I/O debouncer time",
    )


class TransportLayerControl:
    """
    Transport Layer Control parameters.  传输层控制参数。
    """
    PayloadSize = ParamNode(
        "PayloadSize", int, "R",
        "一帧数据的大小 / Payload size per frame", min_value=0,
    )
    GevVersionMajor = ParamNode(
        "GevVersionMajor", int, "R",
        "GEV 主版本号 / GEV major version",
    )
    GevVersionMinor = ParamNode(
        "GevVersionMinor", int, "R",
        "GEV 副版本号 / GEV minor version",
    )
    GevDeviceModeIsBigEndian = ParamNode(
        "GevDeviceModeIsBigEndian", bool, "R",
        "大端模式 / Big-endian mode",
    )
    GevDeviceModeCharacterSet = ParamNode(
        "GevDeviceModeCharacterSet", Hik.GevDeviceModeCharacterSet, "R",
        "字符集 / Character set",
    )
    GevInterfaceSelector = ParamNode(
        "GevInterfaceSelector", int, "R/(W)",
        "GEV 接口选择 / GEV interface selector", min_value=0,
    )
    GevMACAddress = ParamNode(
        "GevMACAddress", int, "R",
        "MAC 地址 / MAC address",
    )
    GevCurrentIPConfigurationLLA = ParamNode(
        "GevCurrentIPConfigurationLLA", bool, "R",
        "IP 是否为 LLA / Is LLA IP configuration",
    )
    GevCurrentIPConfigurationDHCP = ParamNode(
        "GevCurrentIPConfigurationDHCP", bool, "R/W",
        "IP 是否为 DHCP / Is DHCP IP configuration",
    )
    GevCurrentIPConfigurationPersistentIP = ParamNode(
        "GevCurrentIPConfigurationPersistentIP", bool, "R/W",
        "IP 是否为静态 IP / Is persistent (static) IP configuration",
    )
    GevCurrentIPAddress = ParamNode(
        "GevCurrentIPAddress", int, "R",
        "IP 地址 / Current IP address",
    )
    GevCurrentSubnetMask = ParamNode(
        "GevCurrentSubnetMask", int, "R",
        "子网掩码 / Current subnet mask",
    )
    GevCurrentDefaultGateway = ParamNode(
        "GevCurrentDefaultGateway", int, "R",
        "默认网关 / Current default gateway",
    )
    GevFirstURL = ParamNode(
        "GevFirstURL", str, "R",
        "XML 第一选择路径 / First XML URL",
    )
    GevSecondURL = ParamNode(
        "GevSecondURL", str, "R",
        "XML 第二选择路径 / Second XML URL",
    )
    GevNumberOfInterfaces = ParamNode(
        "GevNumberOfInterfaces", int, "R",
        "GEV 接口数 / Number of GEV interfaces", min_value=0,
    )
    GevPersistentIPAddress = ParamNode(
        "GevPersistentIPAddress", int, "R/W",
        "静态 IP 地址 / Persistent IP address", min_value=0,
    )
    GevPersistentSubnetMask = ParamNode(
        "GevPersistentSubnetMask", int, "R/W",
        "静态子网掩码 / Persistent subnet mask", min_value=0,
    )
    GevPersistentDefaultGateway = ParamNode(
        "GevPersistentDefaultGateway", int, "R/W",
        "静态默认网关 / Persistent default gateway", min_value=0,
    )
    GevLinkSpeed = ParamNode(
        "GevLinkSpeed", int, "R",
        "网络速率 / GEV link speed", min_value=0,
    )
    GevMessageChannelCount = ParamNode(
        "GevMessageChannelCount", int, "R",
        "消息通道数 / Message channel count", min_value=0,
    )
    GevStreamChannelCount = ParamNode(
        "GevStreamChannelCount", int, "R",
        "流通道 / Stream channel count", min_value=0,
    )
    GevHeartbeatTimeout = ParamNode(
        "GevHeartbeatTimeout", int, "R/W",
        "心跳超时时间 / Heartbeat timeout", min_value=0,
    )
    GevGVCPHeartbeatDisable = ParamNode(
        "GevGVCPHeartbeatDisable", bool, "R/W",
        "关闭心跳 / Disable GVCP heartbeat",
    )
    GevTimestampTickFrequency = ParamNode(
        "GevTimestampTickFrequency", int, "R",
        "时间戳频率 / Timestamp tick frequency", unit="Hz", min_value=0,
    )
    GevTimestampControlLatch = ParamNode(
        "GevTimestampControlLatch", "command", "W",
        "获取时间戳 / Latch timestamp",
    )
    GevTimestampControlReset = ParamNode(
        "GevTimestampControlReset", "command", "W",
        "复位时间戳 / Reset timestamp",
    )
    GevTimestampControlLatchReset = ParamNode(
        "GevTimestampControlLatchReset", "command", "W",
        "复位并获取时间戳 / Latch and reset timestamp",
    )
    GevTimestampValue = ParamNode(
        "GevTimestampValue", int, "R",
        "时间戳值 / Timestamp value",
    )
    GevCCP = ParamNode(
        "GevCCP", Hik.GevCCP, "R/W",
        "App 端的控制权限 / Control channel privilege",
    )
    GevStreamChannelSelector = ParamNode(
        "GevStreamChannelSelector", int, "R/W",
        "流通道选择 / Stream channel selector", min_value=0,
    )
    GevSCPInterfaceIndex = ParamNode(
        "GevSCPInterfaceIndex", int, "R",
        "GEV 接口索引 / GEV interface index", min_value=0,
    )
    GevSCPHostPort = ParamNode(
        "GevSCPHostPort", int, "R/(W)",
        "主机端口 / Host port", min_value=0,
    )
    GevSCPDirection = ParamNode(
        "GevSCPDirection", int, "R",
        "流通道方向 / Stream channel direction", min_value=0,
    )
    GevSCPSFireTestPacket = ParamNode(
        "GevSCPSFireTestPacket", bool, "R/(W)",
        "Fire Test Packet 使能 / Fire test packet enable",
    )
    GevSCPSDoNotFragment = ParamNode(
        "GevSCPSDoNotFragment", bool, "R/W",
        "GEV SCP 不分段 / Do not fragment",
    )
    GevSCPSBigEndian = ParamNode(
        "GevSCPSBigEndian", bool, "R",
        "流数据大小端 / Stream data big-endian",
    )
    GevSCPSPacketSize = ParamNode(
        "GevSCPSPacketSize", int, "R/W",
        "网络包大小 / Network packet size",
        min_value=220, max_value=9156, step=8,
    )
    GevSCPD = ParamNode(
        "GevSCPD", int, "R/W",
        "发包延时 / Inter-packet delay", min_value=0,
    )
    GevSCDA = ParamNode(
        "GevSCDA", int, "R",
        "流数据的目的地址 / Stream data destination address",
    )
    GevSCSP = ParamNode(
        "GevSCSP", int, "R",
        "流数据的源端口 / Stream data source port",
    )


class UserSetControl:
    """
    User Set Control parameters.  用户集控制参数。
    """
    UserSetCurrent = ParamNode(
        "UserSetCurrent", int, "R",
        "当前用户参数 / Current user set", min_value=0,
    )
    UserSetSelector = ParamNode(
        "UserSetSelector", Hik.UserSetSelector, "R/W",
        "设置载入的参数 / User set selector",
    )
    UserSetLoad = ParamNode(
        "UserSetLoad", "command", "W",
        "加载 / Load user set",
    )
    UserSetSave = ParamNode(
        "UserSetSave", "command", "W",
        "保存 / Save user set",
    )
    UserSetDefault = ParamNode(
        "UserSetDefault", Hik.UserSetDefault, "R/W",
        "默认用户集 / Default user set loaded at boot",
    )


# ===================================================================
# All category classes for iteration / 所有分类类（用于遍历）
# ===================================================================

ALL_CATEGORIES: tuple[type, ...] = (
    DeviceControl,
    ImageFormatControl,
    AcquisitionControl,
    AnalogControl,
    LUTControl,
    EncoderControl,
    FrequencyConverterControl,
    ShadingCorrection,
    DigitalIOControl,
    TransportLayerControl,
    UserSetControl,
)


def _build_param_schema() -> dict[str, type]:
    """
    Build a mapping from GenICam node name → expected Python type from all
    :class:`ParamNode` definitions across every category class.

    从所有分类类的 :class:`ParamNode` 定义中构建 GenICam 节点名 → 期望 Python
    类型的映射。

    This replaces the old hard-coded ``_PARAMETER_SCHEMA`` dictionary in
    ``camera.py`` with a single source of truth derived from ParamNode metadata.
    """
    schema: dict[str, type] = {}
    for category in ALL_CATEGORIES:
        for attr_name in dir(category):
            attr = getattr(category, attr_name)
            if isinstance(attr, ParamNode) and attr.data_type != "command":
                schema[attr.name] = attr.data_type  # type: ignore[assignment]
    return schema


def _build_node_lookup() -> dict[str, ParamNode]:
    """
    Build a mapping from GenICam node name → :class:`ParamNode`.
    构建 GenICam 节点名 → :class:`ParamNode` 的映射。
    """
    lookup: dict[str, ParamNode] = {}
    for category in ALL_CATEGORIES:
        for attr_name in dir(category):
            attr = getattr(category, attr_name)
            if isinstance(attr, ParamNode):
                lookup[attr.name] = attr
    return lookup


#: Pre-built lookup from GenICam name → ParamNode.
#: 预构建的 GenICam 名称 → ParamNode 查找表。
PARAM_NODE_LOOKUP: dict[str, ParamNode] = _build_node_lookup()
