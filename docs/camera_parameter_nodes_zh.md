# 相机参数节点参考

本文汇总当前 `cam.params` 暴露的全部结构化相机参数节点，并按分类分组。
这些表格来自 `src/hikcamera/params.py` 中的 `ParamNode` 定义，对应海康
MVS SDK V4.7.0 开发文档中的参数节点表。

## 使用方式

- 读写节点：`cam.params.<分类>.<节点>.get()` / `set(value)`
- 命令节点：`cam.params.<分类>.<节点>.execute()`
- 枚举值统一通过 `Hik.<枚举名>.<成员>` 传入

示例：

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.params.AcquisitionControl.ExposureTime.set(5000.0)
    cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)
    cam.params.AcquisitionControl.TriggerSoftware.execute()
```

## 分类索引

- [`DeviceControl`](#devicecontrol)（27 个节点）
- [`ImageFormatControl`](#imageformatcontrol)（21 个节点）
- [`AcquisitionControl`](#acquisitioncontrol)（23 个节点）
- [`AnalogControl`](#analogcontrol)（26 个节点）
- [`LUTControl`](#lutcontrol)（4 个节点）
- [`EncoderControl`](#encodercontrol)（10 个节点）
- [`FrequencyConverterControl`](#frequencyconvertercontrol)（5 个节点）
- [`ShadingCorrection`](#shadingcorrection)（4 个节点）
- [`DigitalIOControl`](#digitaliocontrol)（5 个节点）
- [`TransportLayerControl`](#transportlayercontrol)（41 个节点）
- [`UserSetControl`](#usersetcontrol)（5 个节点）

## DeviceControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.DeviceControl.DeviceType` | `Hik.DeviceType` | `R` | — | — | 设备类型 |
| `cam.params.DeviceControl.DeviceScanType` | `Hik.DeviceScanType` | `R` | — | — | 设备 sensor 的扫描方式 |
| `cam.params.DeviceControl.DeviceVendorName` | `str` | `R` | — | — | 设备的制造商名称 |
| `cam.params.DeviceControl.DeviceModelName` | `str` | `R` | — | — | 设备型号 |
| `cam.params.DeviceControl.DeviceManufacturerInfo` | `str` | `R` | — | — | 设备的制造商信息 |
| `cam.params.DeviceControl.DeviceVersion` | `str` | `R` | — | — | 设备版本 |
| `cam.params.DeviceControl.DeviceFirmwareVersion` | `str` | `R` | — | — | 固件版本 |
| `cam.params.DeviceControl.DeviceSerialNumber` | `str` | `R` | — | — | 设备序列号 |
| `cam.params.DeviceControl.DeviceID` | `str` | `R` | — | — | 设备 ID |
| `cam.params.DeviceControl.DeviceUserID` | `str` | `R/W` | — | — | 用户自定义的名称 |
| `cam.params.DeviceControl.DeviceUptime` | `int` | `R` | — | min=0 | 设备运行时间 |
| `cam.params.DeviceControl.DeviceLinkSelector` | `int` | `R/(W)` | — | min=0 | 设备连接选择 |
| `cam.params.DeviceControl.DeviceLinkSpeed` | `int` | `R` | — | min=0 | 传输链路速度 |
| `cam.params.DeviceControl.DeviceLinkConnectionCount` | `int` | `R` | — | min=0 | 设备连接数量 |
| `cam.params.DeviceControl.DeviceLinkHeartbeatMode` | `Hik.DeviceHeartbeatMode` | `R/W` | — | — | 是否需要心跳 |
| `cam.params.DeviceControl.DeviceStreamChannelCount` | `int` | `R` | — | min=0 | 流通道数量 |
| `cam.params.DeviceControl.DeviceStreamChannelSelector` | `int` | `R/(W)` | — | min=0 | 流通道选择 |
| `cam.params.DeviceControl.DeviceStreamChannelType` | `Hik.DeviceStreamChannelType` | `R` | — | — | 流通道类型 |
| `cam.params.DeviceControl.DeviceStreamChannelLink` | `int` | `R` | — | min=0 | 流通道连接数量 |
| `cam.params.DeviceControl.DeviceStreamChannelEndianness` | `Hik.DeviceStreamChannelEndianness` | `R` | — | — | 图像数据的字节序 |
| `cam.params.DeviceControl.DeviceStreamChannelPacketSize` | `int` | `R/(W)` | — | min=220, max=9156, step=8 | 接收端流数据的包大小 |
| `cam.params.DeviceControl.DeviceEventChannelCount` | `int` | `R` | — | min=0 | 设备支持的事件通道数 |
| `cam.params.DeviceControl.DeviceCharacterSet` | `Hik.DeviceCharacterSet` | `R` | — | — | 设备寄存器中使用的字符集 |
| `cam.params.DeviceControl.DeviceReset` | `command` | `W` | — | — | 重启设备 |
| `cam.params.DeviceControl.DeviceMaxThroughput` | `int` | `R` | — | min=0 | 设备最大吞吐量 |
| `cam.params.DeviceControl.DeviceConnectionSelector` | `int` | `R/(W)` | — | min=0 | 设备连接选择 |
| `cam.params.DeviceControl.DeviceConnectionSpeed` | `int` | `R` | `Mbps` | min=0 | 设备连接速度 |

## ImageFormatControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.ImageFormatControl.WidthMax` | `int` | `R` | — | min=1 | 图像最大宽度 |
| `cam.params.ImageFormatControl.HeightMax` | `int` | `R` | — | min=1 | 图像最大高度 |
| `cam.params.ImageFormatControl.RegionSelector` | `Hik.RegionSelector` | `R/(W)` | — | — | ROI 选择器 |
| `cam.params.ImageFormatControl.RegionDestination` | `Hik.RegionDestination` | `R/(W)` | — | — | 该 ROI 对应的码流 |
| `cam.params.ImageFormatControl.Width` | `int` | `R/(W)` | — | min=1 | ROI 的宽 |
| `cam.params.ImageFormatControl.Height` | `int` | `R/(W)` | — | min=1 | ROI 的高 |
| `cam.params.ImageFormatControl.OffsetX` | `int` | `R/W` | — | min=0 | ROI 的水平方向偏移量 |
| `cam.params.ImageFormatControl.OffsetY` | `int` | `R/W` | — | min=0 | ROI 的竖直方向偏移量 |
| `cam.params.ImageFormatControl.ReverseScanDirection` | `bool` | `R/(W)` | — | — | 转换扫描方向 |
| `cam.params.ImageFormatControl.PixelFormat` | `Hik.PixelFormat` | `R/(W)` | — | — | 图像像素格式 |
| `cam.params.ImageFormatControl.PixelSize` | `Hik.PixelSize` | `R/(W)` | — | — | 一个像素包含的比特数 |
| `cam.params.ImageFormatControl.ImageCompressionMode` | `Hik.ImageCompressionMode` | `R/(W)` | — | — | 图像压缩模式 |
| `cam.params.ImageFormatControl.ImageCompressionQuality` | `int` | `R/(W)` | — | min=50 | 图像压缩质量 |
| `cam.params.ImageFormatControl.TestPatternGeneratorSelector` | `Hik.TestPatternGeneratorSelector` | `R/(W)` | — | — | 测试图像生成器选择 |
| `cam.params.ImageFormatControl.TestPattern` | `Hik.TestPattern` | `R/(W)` | — | — | 测试图像选择 |
| `cam.params.ImageFormatControl.FrameSpecInfoSelector` | `Hik.FrameSpecInfoSelector` | `R/(W)` | — | — | 水印信息选择 |
| `cam.params.ImageFormatControl.FrameSpecInfo` | `bool` | `R/W` | — | — | 是否使能该水印信息 |
| `cam.params.ImageFormatControl.BinningHorizontal` | `int` | `R/(W)` | — | min=1 | 水平合并 |
| `cam.params.ImageFormatControl.BinningVertical` | `int` | `R/(W)` | — | min=1 | 垂直合并 |
| `cam.params.ImageFormatControl.DecimationHorizontal` | `int` | `R/(W)` | — | min=1 | 水平抽取 |
| `cam.params.ImageFormatControl.DecimationVertical` | `int` | `R/(W)` | — | min=1 | 垂直抽取 |

## AcquisitionControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.AcquisitionControl.AcquisitionMode` | `Hik.AcquisitionMode` | `R/(W)` | — | — | 采集模式 |
| `cam.params.AcquisitionControl.AcquisitionStart` | `command` | `W` | — | — | 开始取流 |
| `cam.params.AcquisitionControl.AcquisitionStop` | `command` | `W` | — | — | 结束取流 |
| `cam.params.AcquisitionControl.AcquisitionBurstFrameCount` | `int` | `R/W` | — | min=0 | 一次触发采集的帧数 |
| `cam.params.AcquisitionControl.AcquisitionLineRate` | `int` | `R/W` | — | min=1 | 行频设置 |
| `cam.params.AcquisitionControl.AcquisitionLineRateEnable` | `bool` | `R/W` | — | — | 行频控制使能 |
| `cam.params.AcquisitionControl.ResultingLineRate` | `int` | `R` | `Hz` | min=0 | 实际行频 |
| `cam.params.AcquisitionControl.ResultingFrameRate` | `float` | `R` | `fps` | min=0.0 | 相机的实际采集帧率 |
| `cam.params.AcquisitionControl.AcquisitionFrameRate` | `float` | `R/W` | `fps` | min=0.0 | 采集帧率 |
| `cam.params.AcquisitionControl.AcquisitionFrameRateEnable` | `bool` | `R/W` | — | — | 帧率控制使能 |
| `cam.params.AcquisitionControl.TriggerSelector` | `Hik.TriggerSelector` | `R/W` | — | — | 触发事件选择 |
| `cam.params.AcquisitionControl.TriggerMode` | `Hik.TriggerMode` | `R/W` | — | — | 触发模式 |
| `cam.params.AcquisitionControl.TriggerSource` | `Hik.TriggerSource` | `R/W` | — | — | 触发源 |
| `cam.params.AcquisitionControl.TriggerActivation` | `Hik.TriggerActivation` | `R/W` | — | — | 触发沿/电平 |
| `cam.params.AcquisitionControl.TriggerDelay` | `float` | `R/W` | `us` | min=0.0 | 触发延时 |
| `cam.params.AcquisitionControl.TriggerSoftware` | `command` | `W` | — | — | 软触发执行 |
| `cam.params.AcquisitionControl.ExposureMode` | `Hik.ExposureMode` | `R/W` | — | — | 曝光模式选择 |
| `cam.params.AcquisitionControl.ExposureTime` | `float` | `R/W` | `us` | min=0.0 | 曝光时间 |
| `cam.params.AcquisitionControl.ExposureAuto` | `Hik.ExposureAuto` | `R/W` | — | — | 自动曝光 |
| `cam.params.AcquisitionControl.AutoExposureTimeLowerLimit` | `int` | `R/(W)` | `us` | min=0 | 自动曝光时间下限 |
| `cam.params.AcquisitionControl.AutoExposureTimeUpperLimit` | `int` | `R/(W)` | `us` | min=0 | 自动曝光时间上限 |
| `cam.params.AcquisitionControl.FrameTimeoutEnable` | `bool` | `R/W` | — | — | 帧超时使能 |
| `cam.params.AcquisitionControl.FrameTimeoutTime` | `int` | `R/W` | `ms` | min=87 | 帧超时时间 |

## AnalogControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.AnalogControl.Gain` | `float` | `R/W` | `dB` | min=0.0 | 增益值 |
| `cam.params.AnalogControl.GainAuto` | `Hik.GainAuto` | `R/W` | — | — | 自动增益 |
| `cam.params.AnalogControl.AutoGainLowerLimit` | `float` | `R/W` | `dB` | min=0.0 | 自动增益值下限 |
| `cam.params.AnalogControl.AutoGainUpperLimit` | `float` | `R/W` | `dB` | min=0.0 | 自动增益值上限 |
| `cam.params.AnalogControl.ADCGainEnable` | `bool` | `R/W` | — | — | ADC 增益使能 |
| `cam.params.AnalogControl.DigitalShift` | `float` | `R` | — | min=0.0 | 数字偏移调节 |
| `cam.params.AnalogControl.DigitalShiftEnable` | `bool` | `R/W` | — | — | 数字偏移使能 |
| `cam.params.AnalogControl.Brightness` | `int` | `R/W` | — | min=0 | 亮度 |
| `cam.params.AnalogControl.BlackLevel` | `float` | `R/W` | — | min=0.0 | 黑电平调节 |
| `cam.params.AnalogControl.BlackLevelEnable` | `bool` | `R/W` | — | — | 黑电平调节使能 |
| `cam.params.AnalogControl.BalanceWhiteAuto` | `Hik.BalanceWhiteAuto` | `R/W` | — | — | 自动白平衡 |
| `cam.params.AnalogControl.BalanceRatioSelector` | `Hik.BalanceRatioSelector` | `R` | — | — | 白平衡比例选择 |
| `cam.params.AnalogControl.BalanceRatio` | `int` | `R` | — | min=0 | 白平衡值 |
| `cam.params.AnalogControl.Gamma` | `float` | `R/W` | — | min=0.0 | 伽马调节 |
| `cam.params.AnalogControl.GammaSelector` | `Hik.GammaSelector` | `R/W` | — | — | Gamma 选择 |
| `cam.params.AnalogControl.GammaEnable` | `bool` | `R/W` | — | — | Gamma 使能 |
| `cam.params.AnalogControl.Hue` | `int` | `R` | — | min=0 | 色度值调节 |
| `cam.params.AnalogControl.HueEnable` | `bool` | `R/W` | — | — | 色度使能 |
| `cam.params.AnalogControl.Saturation` | `int` | `R` | — | min=0 | 饱和度值调节 |
| `cam.params.AnalogControl.SaturationEnable` | `bool` | `R/W` | — | — | 饱和度使能 |
| `cam.params.AnalogControl.AutoFunctionAOISelector` | `Hik.AutoFunctionAOISelector` | `R/W` | — | — | 自动 AOI 选择 |
| `cam.params.AnalogControl.AutoFunctionAOIWidth` | `int` | `R/W` | — | min=0 | 自动 AOI 宽 |
| `cam.params.AnalogControl.AutoFunctionAOIHeight` | `int` | `R/W` | — | min=0 | 自动 AOI 高 |
| `cam.params.AnalogControl.AutoFunctionAOIOffsetX` | `int` | `R` | — | min=0 | 自动 AOI 水平方向偏移 |
| `cam.params.AnalogControl.AutoFunctionAOIUsageIntensity` | `bool` | `R/W` | — | — | 根据 AOI 区域自动曝光 |
| `cam.params.AnalogControl.AutoFunctionAOIUsageWhiteBalance` | `bool` | `R` | — | — | 根据 AOI 区域自动白平衡 |

## LUTControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.LUTControl.LUTSelector` | `Hik.LUTSelector` | `R/W` | — | — | LUT 通道选择 |
| `cam.params.LUTControl.LUTEnable` | `bool` | `R/W` | — | — | LUT 使能 |
| `cam.params.LUTControl.LUTIndex` | `int` | `R/W` | — | min=0 | LUT 索引号 |
| `cam.params.LUTControl.LUTValue` | `int` | `R/W` | — | — | LUT 值 |

## EncoderControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.EncoderControl.EncoderSelector` | `Hik.EncoderSelector` | `R/W` | — | — | 编码器选择 |
| `cam.params.EncoderControl.EncoderSourceA` | `Hik.LineSelector` | `R/W` | — | — | 编码器 A 源选择 |
| `cam.params.EncoderControl.EncoderSourceB` | `Hik.LineSelector` | `R/W` | — | — | 编码器 B 源选择 |
| `cam.params.EncoderControl.EncoderTriggerMode` | `Hik.EncoderTriggerMode` | `R/W` | — | — | 编码器触发模式 |
| `cam.params.EncoderControl.EncoderCounterMode` | `Hik.EncoderCounterMode` | `R/W` | — | — | 编码器计数模式 |
| `cam.params.EncoderControl.EncoderCounter` | `int` | `R` | — | min=0 | 编码器计数器值 |
| `cam.params.EncoderControl.EncoderCounterMax` | `int` | `R/W` | — | min=1 | 编码器计数器最大值 |
| `cam.params.EncoderControl.EncoderCounterReset` | `command` | `R/W` | — | — | 编码器计数器复位 |
| `cam.params.EncoderControl.EncoderMaxReverseCounter` | `int` | `R/W` | — | min=1 | 编码器最大反转计数器值 |
| `cam.params.EncoderControl.EncoderReverseCounterReset` | `command` | `R/W` | — | — | 编码器反转计数器复位 |

## FrequencyConverterControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.FrequencyConverterControl.InputSource` | `Hik.LineSelector` | `R/W` | — | — | 分频器输入源 |
| `cam.params.FrequencyConverterControl.SignalAlignment` | `Hik.FrequencyConverterSignalAlignment` | `R/W` | — | — | 分频器信号方向 |
| `cam.params.FrequencyConverterControl.PreDivider` | `int` | `R/W` | — | min=1 | 前置分频器调节 |
| `cam.params.FrequencyConverterControl.Multiplier` | `int` | `R/W` | — | min=1 | 倍频器调节 |
| `cam.params.FrequencyConverterControl.PostDivider` | `int` | `R/W` | — | min=1 | 后置分频器调节 |

## ShadingCorrection

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.ShadingCorrection.ShadingSelector` | `Hik.ShadingSelector` | `R/W` | — | — | 明暗场校正选择 |
| `cam.params.ShadingCorrection.ActivateShading` | `command` | `R/(W)` | — | — | 主动校正 |
| `cam.params.ShadingCorrection.NUCEnable` | `bool` | `R/W` | — | — | NUC 使能开关 |
| `cam.params.ShadingCorrection.PRNUCEnable` | `bool` | `R/W` | — | — | PRNUC 状态开关 |

## DigitalIOControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.DigitalIOControl.LineSelector` | `Hik.LineSelector` | `R/W` | — | — | I/O 选择 |
| `cam.params.DigitalIOControl.LineMode` | `Hik.LineMode` | `R/(W)` | — | — | I/O 模式 |
| `cam.params.DigitalIOControl.LineStatus` | `bool` | `R/(W)` | — | — | I/O 状态 |
| `cam.params.DigitalIOControl.LineStatusAll` | `int` | `R` | — | min=0 | 所有 I/O 状态 |
| `cam.params.DigitalIOControl.LineDebouncerTime` | `int` | `R/W` | — | — | I/O 去抖时间 |

## TransportLayerControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.TransportLayerControl.PayloadSize` | `int` | `R` | — | min=0 | 一帧数据的大小 |
| `cam.params.TransportLayerControl.GevVersionMajor` | `int` | `R` | — | — | GEV 主版本号 |
| `cam.params.TransportLayerControl.GevVersionMinor` | `int` | `R` | — | — | GEV 副版本号 |
| `cam.params.TransportLayerControl.GevDeviceModeIsBigEndian` | `bool` | `R` | — | — | 大端模式 |
| `cam.params.TransportLayerControl.GevDeviceModeCharacterSet` | `Hik.GevDeviceModeCharacterSet` | `R` | — | — | 字符集 |
| `cam.params.TransportLayerControl.GevInterfaceSelector` | `int` | `R/(W)` | — | min=0 | GEV 接口选择 |
| `cam.params.TransportLayerControl.GevMACAddress` | `int` | `R` | — | — | MAC 地址 |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationLLA` | `bool` | `R` | — | — | IP 是否为 LLA |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationDHCP` | `bool` | `R/W` | — | — | IP 是否为 DHCP |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationPersistentIP` | `bool` | `R/W` | — | — | IP 是否为静态 IP |
| `cam.params.TransportLayerControl.GevCurrentIPAddress` | `int` | `R` | — | — | IP 地址 |
| `cam.params.TransportLayerControl.GevCurrentSubnetMask` | `int` | `R` | — | — | 子网掩码 |
| `cam.params.TransportLayerControl.GevCurrentDefaultGateway` | `int` | `R` | — | — | 默认网关 |
| `cam.params.TransportLayerControl.GevFirstURL` | `str` | `R` | — | — | XML 第一选择路径 |
| `cam.params.TransportLayerControl.GevSecondURL` | `str` | `R` | — | — | XML 第二选择路径 |
| `cam.params.TransportLayerControl.GevNumberOfInterfaces` | `int` | `R` | — | min=0 | GEV 接口数 |
| `cam.params.TransportLayerControl.GevPersistentIPAddress` | `int` | `R/W` | — | min=0 | 静态 IP 地址 |
| `cam.params.TransportLayerControl.GevPersistentSubnetMask` | `int` | `R/W` | — | min=0 | 静态子网掩码 |
| `cam.params.TransportLayerControl.GevPersistentDefaultGateway` | `int` | `R/W` | — | min=0 | 静态默认网关 |
| `cam.params.TransportLayerControl.GevLinkSpeed` | `int` | `R` | — | min=0 | 网络速率 |
| `cam.params.TransportLayerControl.GevMessageChannelCount` | `int` | `R` | — | min=0 | 消息通道数 |
| `cam.params.TransportLayerControl.GevStreamChannelCount` | `int` | `R` | — | min=0 | 流通道 |
| `cam.params.TransportLayerControl.GevHeartbeatTimeout` | `int` | `R/W` | — | min=0 | 心跳超时时间 |
| `cam.params.TransportLayerControl.GevGVCPHeartbeatDisable` | `bool` | `R/W` | — | — | 关闭心跳 |
| `cam.params.TransportLayerControl.GevTimestampTickFrequency` | `int` | `R` | `Hz` | min=0 | 时间戳频率 |
| `cam.params.TransportLayerControl.GevTimestampControlLatch` | `command` | `W` | — | — | 获取时间戳 |
| `cam.params.TransportLayerControl.GevTimestampControlReset` | `command` | `W` | — | — | 复位时间戳 |
| `cam.params.TransportLayerControl.GevTimestampControlLatchReset` | `command` | `W` | — | — | 复位并获取时间戳 |
| `cam.params.TransportLayerControl.GevTimestampValue` | `int` | `R` | — | — | 时间戳值 |
| `cam.params.TransportLayerControl.GevCCP` | `Hik.GevCCP` | `R/W` | — | — | App 端的控制权限 |
| `cam.params.TransportLayerControl.GevStreamChannelSelector` | `int` | `R/W` | — | min=0 | 流通道选择 |
| `cam.params.TransportLayerControl.GevSCPInterfaceIndex` | `int` | `R` | — | min=0 | GEV 接口索引 |
| `cam.params.TransportLayerControl.GevSCPHostPort` | `int` | `R/(W)` | — | min=0 | 主机端口 |
| `cam.params.TransportLayerControl.GevSCPDirection` | `int` | `R` | — | min=0 | 流通道方向 |
| `cam.params.TransportLayerControl.GevSCPSFireTestPacket` | `bool` | `R/(W)` | — | — | Fire Test Packet 使能 |
| `cam.params.TransportLayerControl.GevSCPSDoNotFragment` | `bool` | `R/W` | — | — | GEV SCP 不分段 |
| `cam.params.TransportLayerControl.GevSCPSBigEndian` | `bool` | `R` | — | — | 流数据大小端 |
| `cam.params.TransportLayerControl.GevSCPSPacketSize` | `int` | `R/W` | — | min=220, max=9156, step=8 | 网络包大小 |
| `cam.params.TransportLayerControl.GevSCPD` | `int` | `R/W` | — | min=0 | 发包延时 |
| `cam.params.TransportLayerControl.GevSCDA` | `int` | `R` | — | — | 流数据的目的地址 |
| `cam.params.TransportLayerControl.GevSCSP` | `int` | `R` | — | — | 流数据的源端口 |

## UserSetControl

| 结构化路径 | 数据类型 | 访问权限 | 单位 | 范围 | 说明 |
|---|---|---|---|---|---|
| `cam.params.UserSetControl.UserSetCurrent` | `int` | `R` | — | min=0 | 当前用户参数 |
| `cam.params.UserSetControl.UserSetSelector` | `Hik.UserSetSelector` | `R/W` | — | — | 设置载入的参数 |
| `cam.params.UserSetControl.UserSetLoad` | `command` | `W` | — | — | 加载 |
| `cam.params.UserSetControl.UserSetSave` | `command` | `W` | — | — | 保存 |
| `cam.params.UserSetControl.UserSetDefault` | `Hik.UserSetDefault` | `R/W` | — | — | 默认用户集 |

