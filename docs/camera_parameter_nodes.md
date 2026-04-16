# Camera Parameter Node Reference / 相机参数节点参考

This document lists all structured camera parameter nodes currently exposed by
`cam.params`, grouped by category. The tables are derived from
`src/hikcamera/params.py`, which mirrors the Hikvision MVS SDK V4.7.0 parameter
node table.

本文汇总当前 `cam.params` 暴露的全部结构化相机参数节点，并按分类分组。
这些表格来自 `src/hikcamera/params.py` 中的 `ParamNode` 定义，对应海康
MVS SDK V4.7.0 开发文档中的参数节点表。

## Usage / 使用方式

- Read/write nodes / 读写节点: `cam.params.<Category>.<Node>.get()` / `set(value)`
- Command nodes / 命令节点: `cam.params.<Category>.<Node>.execute()`
- Enum values / 枚举值: always use `Hik.<EnumName>.<Member>`
- 枚举值统一通过 `Hik.<枚举名>.<成员>` 传入

Example / 示例：

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.params.AcquisitionControl.ExposureTime.set(5000.0)
    cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)
    cam.params.AcquisitionControl.TriggerSoftware.execute()
```

## Category index / 分类索引

- [`DeviceControl`](#devicecontrol) (27 nodes)
- [`ImageFormatControl`](#imageformatcontrol) (21 nodes)
- [`AcquisitionControl`](#acquisitioncontrol) (23 nodes)
- [`AnalogControl`](#analogcontrol) (26 nodes)
- [`LUTControl`](#lutcontrol) (4 nodes)
- [`EncoderControl`](#encodercontrol) (10 nodes)
- [`FrequencyConverterControl`](#frequencyconvertercontrol) (5 nodes)
- [`ShadingCorrection`](#shadingcorrection) (4 nodes)
- [`DigitalIOControl`](#digitaliocontrol) (5 nodes)
- [`TransportLayerControl`](#transportlayercontrol) (41 nodes)
- [`UserSetControl`](#usersetcontrol) (5 nodes)

## DeviceControl

Device Control parameters.  设备控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.DeviceControl.DeviceType` | `Hik.DeviceType` | `R` | — | — | 设备类型 / Device type |
| `cam.params.DeviceControl.DeviceScanType` | `Hik.DeviceScanType` | `R` | — | — | 设备 sensor 的扫描方式 / Device sensor scan type |
| `cam.params.DeviceControl.DeviceVendorName` | `str` | `R` | — | — | 设备的制造商名称 / Manufacturer name |
| `cam.params.DeviceControl.DeviceModelName` | `str` | `R` | — | — | 设备型号 / Device model name |
| `cam.params.DeviceControl.DeviceManufacturerInfo` | `str` | `R` | — | — | 设备的制造商信息 / Manufacturer info |
| `cam.params.DeviceControl.DeviceVersion` | `str` | `R` | — | — | 设备版本 / Device version |
| `cam.params.DeviceControl.DeviceFirmwareVersion` | `str` | `R` | — | — | 固件版本 / Firmware version |
| `cam.params.DeviceControl.DeviceSerialNumber` | `str` | `R` | — | — | 设备序列号 / Device serial number |
| `cam.params.DeviceControl.DeviceID` | `str` | `R` | — | — | 设备 ID / Device ID |
| `cam.params.DeviceControl.DeviceUserID` | `str` | `R/W` | — | — | 用户自定义的名称 / User-defined device name |
| `cam.params.DeviceControl.DeviceUptime` | `int` | `R` | — | min=0 | 设备运行时间 / Device uptime |
| `cam.params.DeviceControl.DeviceLinkSelector` | `int` | `R/(W)` | — | min=0 | 设备连接选择 / Device link selector |
| `cam.params.DeviceControl.DeviceLinkSpeed` | `int` | `R` | — | min=0 | 传输链路速度 / Transmission link speed |
| `cam.params.DeviceControl.DeviceLinkConnectionCount` | `int` | `R` | — | min=0 | 设备连接数量 / Device link connection count |
| `cam.params.DeviceControl.DeviceLinkHeartbeatMode` | `Hik.DeviceHeartbeatMode` | `R/W` | — | — | 是否需要心跳 / Heartbeat mode |
| `cam.params.DeviceControl.DeviceStreamChannelCount` | `int` | `R` | — | min=0 | 流通道数量 / Stream channel count |
| `cam.params.DeviceControl.DeviceStreamChannelSelector` | `int` | `R/(W)` | — | min=0 | 流通道选择 / Stream channel selector |
| `cam.params.DeviceControl.DeviceStreamChannelType` | `Hik.DeviceStreamChannelType` | `R` | — | — | 流通道类型 / Stream channel type |
| `cam.params.DeviceControl.DeviceStreamChannelLink` | `int` | `R` | — | min=0 | 流通道连接数量 / Stream channel link count |
| `cam.params.DeviceControl.DeviceStreamChannelEndianness` | `Hik.DeviceStreamChannelEndianness` | `R` | — | — | 图像数据的字节序 / Image data byte order |
| `cam.params.DeviceControl.DeviceStreamChannelPacketSize` | `int` | `R/(W)` | — | min=220, max=9156, step=8 | 接收端流数据的包大小 / Stream data packet size |
| `cam.params.DeviceControl.DeviceEventChannelCount` | `int` | `R` | — | min=0 | 设备支持的事件通道数 / Event channel count |
| `cam.params.DeviceControl.DeviceCharacterSet` | `Hik.DeviceCharacterSet` | `R` | — | — | 设备寄存器中使用的字符集 / Character set in device registers |
| `cam.params.DeviceControl.DeviceReset` | `command` | `W` | — | — | 重启设备 / Reset device |
| `cam.params.DeviceControl.DeviceMaxThroughput` | `int` | `R` | — | min=0 | 设备最大吞吐量 / Maximum device throughput |
| `cam.params.DeviceControl.DeviceConnectionSelector` | `int` | `R/(W)` | — | min=0 | 设备连接选择 / Device connection selector |
| `cam.params.DeviceControl.DeviceConnectionSpeed` | `int` | `R` | `Mbps` | min=0 | 设备连接速度 / Device connection speed |

## ImageFormatControl

Image Format Control parameters.  图像格式控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.ImageFormatControl.WidthMax` | `int` | `R` | — | min=1 | 图像最大宽度 / Maximum image width |
| `cam.params.ImageFormatControl.HeightMax` | `int` | `R` | — | min=1 | 图像最大高度 / Maximum image height |
| `cam.params.ImageFormatControl.RegionSelector` | `Hik.RegionSelector` | `R/(W)` | — | — | ROI 选择器 / ROI selector |
| `cam.params.ImageFormatControl.RegionDestination` | `Hik.RegionDestination` | `R/(W)` | — | — | 该 ROI 对应的码流 / Stream destination for region |
| `cam.params.ImageFormatControl.Width` | `int` | `R/(W)` | — | min=1 | ROI 的宽 / ROI width |
| `cam.params.ImageFormatControl.Height` | `int` | `R/(W)` | — | min=1 | ROI 的高 / ROI height |
| `cam.params.ImageFormatControl.OffsetX` | `int` | `R/W` | — | min=0 | ROI 的水平方向偏移量 / ROI horizontal offset |
| `cam.params.ImageFormatControl.OffsetY` | `int` | `R/W` | — | min=0 | ROI 的竖直方向偏移量 / ROI vertical offset |
| `cam.params.ImageFormatControl.ReverseScanDirection` | `bool` | `R/(W)` | — | — | 转换扫描方向 / Reverse scan direction |
| `cam.params.ImageFormatControl.PixelFormat` | `Hik.PixelFormat` | `R/(W)` | — | — | 图像像素格式 / Image pixel format |
| `cam.params.ImageFormatControl.PixelSize` | `Hik.PixelSize` | `R/(W)` | — | — | 一个像素包含的比特数 / Bits per pixel |
| `cam.params.ImageFormatControl.ImageCompressionMode` | `Hik.ImageCompressionMode` | `R/(W)` | — | — | 图像压缩模式 / Image compression mode |
| `cam.params.ImageFormatControl.ImageCompressionQuality` | `int` | `R/(W)` | — | min=50 | 图像压缩质量 / Image compression quality |
| `cam.params.ImageFormatControl.TestPatternGeneratorSelector` | `Hik.TestPatternGeneratorSelector` | `R/(W)` | — | — | 测试图像生成器选择 / Test pattern generator selector |
| `cam.params.ImageFormatControl.TestPattern` | `Hik.TestPattern` | `R/(W)` | — | — | 测试图像选择 / Test pattern selection |
| `cam.params.ImageFormatControl.FrameSpecInfoSelector` | `Hik.FrameSpecInfoSelector` | `R/(W)` | — | — | 水印信息选择 / Watermark info selector |
| `cam.params.ImageFormatControl.FrameSpecInfo` | `bool` | `R/W` | — | — | 是否使能该水印信息 / Enable watermark info |
| `cam.params.ImageFormatControl.BinningHorizontal` | `int` | `R/(W)` | — | min=1 | 水平合并 / Horizontal binning |
| `cam.params.ImageFormatControl.BinningVertical` | `int` | `R/(W)` | — | min=1 | 垂直合并 / Vertical binning |
| `cam.params.ImageFormatControl.DecimationHorizontal` | `int` | `R/(W)` | — | min=1 | 水平抽取 / Horizontal decimation |
| `cam.params.ImageFormatControl.DecimationVertical` | `int` | `R/(W)` | — | min=1 | 垂直抽取 / Vertical decimation |

## AcquisitionControl

Acquisition Control parameters.  采集控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.AcquisitionControl.AcquisitionMode` | `Hik.AcquisitionMode` | `R/(W)` | — | — | 采集模式 / Acquisition mode (single/multi/continuous) |
| `cam.params.AcquisitionControl.AcquisitionStart` | `command` | `W` | — | — | 开始取流 / Start acquisition |
| `cam.params.AcquisitionControl.AcquisitionStop` | `command` | `W` | — | — | 结束取流 / Stop acquisition |
| `cam.params.AcquisitionControl.AcquisitionBurstFrameCount` | `int` | `R/W` | — | min=0 | 一次触发采集的帧数 / Burst frame count |
| `cam.params.AcquisitionControl.AcquisitionLineRate` | `int` | `R/W` | — | min=1 | 行频设置 / Line rate |
| `cam.params.AcquisitionControl.AcquisitionLineRateEnable` | `bool` | `R/W` | — | — | 行频控制使能 / Line rate control enable |
| `cam.params.AcquisitionControl.ResultingLineRate` | `int` | `R` | `Hz` | min=0 | 实际行频 / Resulting line rate |
| `cam.params.AcquisitionControl.ResultingFrameRate` | `float` | `R` | `fps` | min=0.0 | 相机的实际采集帧率 / Resulting frame rate |
| `cam.params.AcquisitionControl.AcquisitionFrameRate` | `float` | `R/W` | `fps` | min=0.0 | 采集帧率 / Acquisition frame rate |
| `cam.params.AcquisitionControl.AcquisitionFrameRateEnable` | `bool` | `R/W` | — | — | 帧率控制使能 / Frame rate control enable |
| `cam.params.AcquisitionControl.TriggerSelector` | `Hik.TriggerSelector` | `R/W` | — | — | 触发事件选择 / Trigger event selector |
| `cam.params.AcquisitionControl.TriggerMode` | `Hik.TriggerMode` | `R/W` | — | — | 触发模式 / Trigger mode (on/off) |
| `cam.params.AcquisitionControl.TriggerSource` | `Hik.TriggerSource` | `R/W` | — | — | 触发源 / Trigger source |
| `cam.params.AcquisitionControl.TriggerActivation` | `Hik.TriggerActivation` | `R/W` | — | — | 触发沿/电平 / Trigger activation edge/level |
| `cam.params.AcquisitionControl.TriggerDelay` | `float` | `R/W` | `us` | min=0.0 | 触发延时 / Trigger delay |
| `cam.params.AcquisitionControl.TriggerSoftware` | `command` | `W` | — | — | 软触发执行 / Execute software trigger |
| `cam.params.AcquisitionControl.ExposureMode` | `Hik.ExposureMode` | `R/W` | — | — | 曝光模式选择 / Exposure mode |
| `cam.params.AcquisitionControl.ExposureTime` | `float` | `R/W` | `us` | min=0.0 | 曝光时间 / Exposure time |
| `cam.params.AcquisitionControl.ExposureAuto` | `Hik.ExposureAuto` | `R/W` | — | — | 自动曝光 / Auto exposure |
| `cam.params.AcquisitionControl.AutoExposureTimeLowerLimit` | `int` | `R/(W)` | `us` | min=0 | 自动曝光时间下限 / Auto exposure time lower limit |
| `cam.params.AcquisitionControl.AutoExposureTimeUpperLimit` | `int` | `R/(W)` | `us` | min=0 | 自动曝光时间上限 / Auto exposure time upper limit |
| `cam.params.AcquisitionControl.FrameTimeoutEnable` | `bool` | `R/W` | — | — | 帧超时使能 / Frame timeout enable |
| `cam.params.AcquisitionControl.FrameTimeoutTime` | `int` | `R/W` | `ms` | min=87 | 帧超时时间 / Frame timeout time |

## AnalogControl

Analog Control parameters.  模拟控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.AnalogControl.Gain` | `float` | `R/W` | `dB` | min=0.0 | 增益值 / Gain |
| `cam.params.AnalogControl.GainAuto` | `Hik.GainAuto` | `R/W` | — | — | 自动增益 / Auto gain |
| `cam.params.AnalogControl.AutoGainLowerLimit` | `float` | `R/W` | `dB` | min=0.0 | 自动增益值下限 / Auto gain lower limit |
| `cam.params.AnalogControl.AutoGainUpperLimit` | `float` | `R/W` | `dB` | min=0.0 | 自动增益值上限 / Auto gain upper limit |
| `cam.params.AnalogControl.ADCGainEnable` | `bool` | `R/W` | — | — | ADC 增益使能 / ADC gain enable |
| `cam.params.AnalogControl.DigitalShift` | `float` | `R` | — | min=0.0 | 数字偏移调节 / Digital shift |
| `cam.params.AnalogControl.DigitalShiftEnable` | `bool` | `R/W` | — | — | 数字偏移使能 / Digital shift enable |
| `cam.params.AnalogControl.Brightness` | `int` | `R/W` | — | min=0 | 亮度 / Brightness |
| `cam.params.AnalogControl.BlackLevel` | `float` | `R/W` | — | min=0.0 | 黑电平调节 / Black level |
| `cam.params.AnalogControl.BlackLevelEnable` | `bool` | `R/W` | — | — | 黑电平调节使能 / Black level enable |
| `cam.params.AnalogControl.BalanceWhiteAuto` | `Hik.BalanceWhiteAuto` | `R/W` | — | — | 自动白平衡 / Auto white balance |
| `cam.params.AnalogControl.BalanceRatioSelector` | `Hik.BalanceRatioSelector` | `R` | — | — | 白平衡比例选择 / White balance ratio selector |
| `cam.params.AnalogControl.BalanceRatio` | `int` | `R` | — | min=0 | 白平衡值 / White balance ratio |
| `cam.params.AnalogControl.Gamma` | `float` | `R/W` | — | min=0.0 | 伽马调节 / Gamma correction |
| `cam.params.AnalogControl.GammaSelector` | `Hik.GammaSelector` | `R/W` | — | — | Gamma 选择 / Gamma selector |
| `cam.params.AnalogControl.GammaEnable` | `bool` | `R/W` | — | — | Gamma 使能 / Gamma enable |
| `cam.params.AnalogControl.Hue` | `int` | `R` | — | min=0 | 色度值调节 / Hue adjustment |
| `cam.params.AnalogControl.HueEnable` | `bool` | `R/W` | — | — | 色度使能 / Hue enable |
| `cam.params.AnalogControl.Saturation` | `int` | `R` | — | min=0 | 饱和度值调节 / Saturation adjustment |
| `cam.params.AnalogControl.SaturationEnable` | `bool` | `R/W` | — | — | 饱和度使能 / Saturation enable |
| `cam.params.AnalogControl.AutoFunctionAOISelector` | `Hik.AutoFunctionAOISelector` | `R/W` | — | — | 自动 AOI 选择 / Auto function AOI selector |
| `cam.params.AnalogControl.AutoFunctionAOIWidth` | `int` | `R/W` | — | min=0 | 自动 AOI 宽 / Auto function AOI width |
| `cam.params.AnalogControl.AutoFunctionAOIHeight` | `int` | `R/W` | — | min=0 | 自动 AOI 高 / Auto function AOI height |
| `cam.params.AnalogControl.AutoFunctionAOIOffsetX` | `int` | `R` | — | min=0 | 自动 AOI 水平方向偏移 / Auto function AOI horizontal offset |
| `cam.params.AnalogControl.AutoFunctionAOIUsageIntensity` | `bool` | `R/W` | — | — | 根据 AOI 区域自动曝光 / Auto exposure based on AOI |
| `cam.params.AnalogControl.AutoFunctionAOIUsageWhiteBalance` | `bool` | `R` | — | — | 根据 AOI 区域自动白平衡 / Auto white balance based on AOI |

## LUTControl

LUT Control parameters.  LUT 控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.LUTControl.LUTSelector` | `Hik.LUTSelector` | `R/W` | — | — | LUT 通道选择 / LUT channel selector |
| `cam.params.LUTControl.LUTEnable` | `bool` | `R/W` | — | — | LUT 使能 / LUT enable |
| `cam.params.LUTControl.LUTIndex` | `int` | `R/W` | — | min=0 | LUT 索引号 / LUT index |
| `cam.params.LUTControl.LUTValue` | `int` | `R/W` | — | — | LUT 值 / LUT value |

## EncoderControl

Encoder Control parameters.  编码器控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.EncoderControl.EncoderSelector` | `Hik.EncoderSelector` | `R/W` | — | — | 编码器选择 / Encoder selector |
| `cam.params.EncoderControl.EncoderSourceA` | `Hik.LineSelector` | `R/W` | — | — | 编码器 A 源选择 / Encoder source A |
| `cam.params.EncoderControl.EncoderSourceB` | `Hik.LineSelector` | `R/W` | — | — | 编码器 B 源选择 / Encoder source B |
| `cam.params.EncoderControl.EncoderTriggerMode` | `Hik.EncoderTriggerMode` | `R/W` | — | — | 编码器触发模式 / Encoder trigger mode |
| `cam.params.EncoderControl.EncoderCounterMode` | `Hik.EncoderCounterMode` | `R/W` | — | — | 编码器计数模式 / Encoder counter mode |
| `cam.params.EncoderControl.EncoderCounter` | `int` | `R` | — | min=0 | 编码器计数器值 / Encoder counter value |
| `cam.params.EncoderControl.EncoderCounterMax` | `int` | `R/W` | — | min=1 | 编码器计数器最大值 / Encoder counter max |
| `cam.params.EncoderControl.EncoderCounterReset` | `command` | `R/W` | — | — | 编码器计数器复位 / Encoder counter reset |
| `cam.params.EncoderControl.EncoderMaxReverseCounter` | `int` | `R/W` | — | min=1 | 编码器最大反转计数器值 / Encoder max reverse counter |
| `cam.params.EncoderControl.EncoderReverseCounterReset` | `command` | `R/W` | — | — | 编码器反转计数器复位 / Encoder reverse counter reset |

## FrequencyConverterControl

Frequency Converter Control parameters.  分频器控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.FrequencyConverterControl.InputSource` | `Hik.LineSelector` | `R/W` | — | — | 分频器输入源 / Frequency converter input source |
| `cam.params.FrequencyConverterControl.SignalAlignment` | `Hik.FrequencyConverterSignalAlignment` | `R/W` | — | — | 分频器信号方向 / Signal alignment edge |
| `cam.params.FrequencyConverterControl.PreDivider` | `int` | `R/W` | — | min=1 | 前置分频器调节 / Pre-divider |
| `cam.params.FrequencyConverterControl.Multiplier` | `int` | `R/W` | — | min=1 | 倍频器调节 / Multiplier |
| `cam.params.FrequencyConverterControl.PostDivider` | `int` | `R/W` | — | min=1 | 后置分频器调节 / Post-divider |

## ShadingCorrection

Shading Correction parameters.  明暗场校正参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.ShadingCorrection.ShadingSelector` | `Hik.ShadingSelector` | `R/W` | — | — | 明暗场校正选择 / Shading correction selector |
| `cam.params.ShadingCorrection.ActivateShading` | `command` | `R/(W)` | — | — | 主动校正 / Activate shading correction |
| `cam.params.ShadingCorrection.NUCEnable` | `bool` | `R/W` | — | — | NUC 使能开关 / NUC enable |
| `cam.params.ShadingCorrection.PRNUCEnable` | `bool` | `R/W` | — | — | PRNUC 状态开关 / PRNUC enable |

## DigitalIOControl

Digital IO Control parameters.  数字 IO 控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.DigitalIOControl.LineSelector` | `Hik.LineSelector` | `R/W` | — | — | I/O 选择 / I/O line selector |
| `cam.params.DigitalIOControl.LineMode` | `Hik.LineMode` | `R/(W)` | — | — | I/O 模式 / I/O line mode |
| `cam.params.DigitalIOControl.LineStatus` | `bool` | `R/(W)` | — | — | I/O 状态 / I/O line status |
| `cam.params.DigitalIOControl.LineStatusAll` | `int` | `R` | — | min=0 | 所有 I/O 状态 / All I/O line status |
| `cam.params.DigitalIOControl.LineDebouncerTime` | `int` | `R/W` | — | — | I/O 去抖时间 / I/O debouncer time |

## TransportLayerControl

Transport Layer Control parameters.  传输层控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.TransportLayerControl.PayloadSize` | `int` | `R` | — | min=0 | 一帧数据的大小 / Payload size per frame |
| `cam.params.TransportLayerControl.GevVersionMajor` | `int` | `R` | — | — | GEV 主版本号 / GEV major version |
| `cam.params.TransportLayerControl.GevVersionMinor` | `int` | `R` | — | — | GEV 副版本号 / GEV minor version |
| `cam.params.TransportLayerControl.GevDeviceModeIsBigEndian` | `bool` | `R` | — | — | 大端模式 / Big-endian mode |
| `cam.params.TransportLayerControl.GevDeviceModeCharacterSet` | `Hik.GevDeviceModeCharacterSet` | `R` | — | — | 字符集 / Character set |
| `cam.params.TransportLayerControl.GevInterfaceSelector` | `int` | `R/(W)` | — | min=0 | GEV 接口选择 / GEV interface selector |
| `cam.params.TransportLayerControl.GevMACAddress` | `int` | `R` | — | — | MAC 地址 / MAC address |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationLLA` | `bool` | `R` | — | — | IP 是否为 LLA / Is LLA IP configuration |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationDHCP` | `bool` | `R/W` | — | — | IP 是否为 DHCP / Is DHCP IP configuration |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationPersistentIP` | `bool` | `R/W` | — | — | IP 是否为静态 IP / Is persistent (static) IP configuration |
| `cam.params.TransportLayerControl.GevCurrentIPAddress` | `int` | `R` | — | — | IP 地址 / Current IP address |
| `cam.params.TransportLayerControl.GevCurrentSubnetMask` | `int` | `R` | — | — | 子网掩码 / Current subnet mask |
| `cam.params.TransportLayerControl.GevCurrentDefaultGateway` | `int` | `R` | — | — | 默认网关 / Current default gateway |
| `cam.params.TransportLayerControl.GevFirstURL` | `str` | `R` | — | — | XML 第一选择路径 / First XML URL |
| `cam.params.TransportLayerControl.GevSecondURL` | `str` | `R` | — | — | XML 第二选择路径 / Second XML URL |
| `cam.params.TransportLayerControl.GevNumberOfInterfaces` | `int` | `R` | — | min=0 | GEV 接口数 / Number of GEV interfaces |
| `cam.params.TransportLayerControl.GevPersistentIPAddress` | `int` | `R/W` | — | min=0 | 静态 IP 地址 / Persistent IP address |
| `cam.params.TransportLayerControl.GevPersistentSubnetMask` | `int` | `R/W` | — | min=0 | 静态子网掩码 / Persistent subnet mask |
| `cam.params.TransportLayerControl.GevPersistentDefaultGateway` | `int` | `R/W` | — | min=0 | 静态默认网关 / Persistent default gateway |
| `cam.params.TransportLayerControl.GevLinkSpeed` | `int` | `R` | — | min=0 | 网络速率 / GEV link speed |
| `cam.params.TransportLayerControl.GevMessageChannelCount` | `int` | `R` | — | min=0 | 消息通道数 / Message channel count |
| `cam.params.TransportLayerControl.GevStreamChannelCount` | `int` | `R` | — | min=0 | 流通道 / Stream channel count |
| `cam.params.TransportLayerControl.GevHeartbeatTimeout` | `int` | `R/W` | — | min=0 | 心跳超时时间 / Heartbeat timeout |
| `cam.params.TransportLayerControl.GevGVCPHeartbeatDisable` | `bool` | `R/W` | — | — | 关闭心跳 / Disable GVCP heartbeat |
| `cam.params.TransportLayerControl.GevTimestampTickFrequency` | `int` | `R` | `Hz` | min=0 | 时间戳频率 / Timestamp tick frequency |
| `cam.params.TransportLayerControl.GevTimestampControlLatch` | `command` | `W` | — | — | 获取时间戳 / Latch timestamp |
| `cam.params.TransportLayerControl.GevTimestampControlReset` | `command` | `W` | — | — | 复位时间戳 / Reset timestamp |
| `cam.params.TransportLayerControl.GevTimestampControlLatchReset` | `command` | `W` | — | — | 复位并获取时间戳 / Latch and reset timestamp |
| `cam.params.TransportLayerControl.GevTimestampValue` | `int` | `R` | — | — | 时间戳值 / Timestamp value |
| `cam.params.TransportLayerControl.GevCCP` | `Hik.GevCCP` | `R/W` | — | — | App 端的控制权限 / Control channel privilege |
| `cam.params.TransportLayerControl.GevStreamChannelSelector` | `int` | `R/W` | — | min=0 | 流通道选择 / Stream channel selector |
| `cam.params.TransportLayerControl.GevSCPInterfaceIndex` | `int` | `R` | — | min=0 | GEV 接口索引 / GEV interface index |
| `cam.params.TransportLayerControl.GevSCPHostPort` | `int` | `R/(W)` | — | min=0 | 主机端口 / Host port |
| `cam.params.TransportLayerControl.GevSCPDirection` | `int` | `R` | — | min=0 | 流通道方向 / Stream channel direction |
| `cam.params.TransportLayerControl.GevSCPSFireTestPacket` | `bool` | `R/(W)` | — | — | Fire Test Packet 使能 / Fire test packet enable |
| `cam.params.TransportLayerControl.GevSCPSDoNotFragment` | `bool` | `R/W` | — | — | GEV SCP 不分段 / Do not fragment |
| `cam.params.TransportLayerControl.GevSCPSBigEndian` | `bool` | `R` | — | — | 流数据大小端 / Stream data big-endian |
| `cam.params.TransportLayerControl.GevSCPSPacketSize` | `int` | `R/W` | — | min=220, max=9156, step=8 | 网络包大小 / Network packet size |
| `cam.params.TransportLayerControl.GevSCPD` | `int` | `R/W` | — | min=0 | 发包延时 / Inter-packet delay |
| `cam.params.TransportLayerControl.GevSCDA` | `int` | `R` | — | — | 流数据的目的地址 / Stream data destination address |
| `cam.params.TransportLayerControl.GevSCSP` | `int` | `R` | — | — | 流数据的源端口 / Stream data source port |

## UserSetControl

User Set Control parameters.  用户集控制参数。

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.UserSetControl.UserSetCurrent` | `int` | `R` | — | min=0 | 当前用户参数 / Current user set |
| `cam.params.UserSetControl.UserSetSelector` | `Hik.UserSetSelector` | `R/W` | — | — | 设置载入的参数 / User set selector |
| `cam.params.UserSetControl.UserSetLoad` | `command` | `W` | — | — | 加载 / Load user set |
| `cam.params.UserSetControl.UserSetSave` | `command` | `W` | — | — | 保存 / Save user set |
| `cam.params.UserSetControl.UserSetDefault` | `Hik.UserSetDefault` | `R/W` | — | — | 默认用户集 / Default user set loaded at boot |

