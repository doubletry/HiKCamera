# Camera Parameter Node Reference

This document lists all structured camera parameter nodes currently exposed by
`cam.params`, grouped by category. The tables are derived from
`src/hikcamera/params.py`, which mirrors the Hikvision MVS SDK V4.7.0 parameter
node table.

## Usage

- Read/write nodes: `cam.params.<Category>.<Node>.get()` / `set(value)`
- Command nodes: `cam.params.<Category>.<Node>.execute()`
- Enum values: always use `Hik.<EnumName>.<Member>`

Example:

```python
from hikcamera import Hik, HikCamera

with HikCamera.from_ip("192.168.1.100") as cam:
    cam.open(Hik.AccessMode.EXCLUSIVE)
    cam.params.AcquisitionControl.ExposureTime.set(5000.0)
    cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)
    cam.params.AcquisitionControl.TriggerSoftware.execute()
```

## Category index

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

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.DeviceControl.DeviceType` | `Hik.DeviceType` | `R` | — | — | Device type |
| `cam.params.DeviceControl.DeviceScanType` | `Hik.DeviceScanType` | `R` | — | — | Device sensor scan type |
| `cam.params.DeviceControl.DeviceVendorName` | `str` | `R` | — | — | Manufacturer name |
| `cam.params.DeviceControl.DeviceModelName` | `str` | `R` | — | — | Device model name |
| `cam.params.DeviceControl.DeviceManufacturerInfo` | `str` | `R` | — | — | Manufacturer info |
| `cam.params.DeviceControl.DeviceVersion` | `str` | `R` | — | — | Device version |
| `cam.params.DeviceControl.DeviceFirmwareVersion` | `str` | `R` | — | — | Firmware version |
| `cam.params.DeviceControl.DeviceSerialNumber` | `str` | `R` | — | — | Device serial number |
| `cam.params.DeviceControl.DeviceID` | `str` | `R` | — | — | Device ID |
| `cam.params.DeviceControl.DeviceUserID` | `str` | `R/W` | — | — | User-defined device name |
| `cam.params.DeviceControl.DeviceUptime` | `int` | `R` | — | min=0 | Device uptime |
| `cam.params.DeviceControl.DeviceLinkSelector` | `int` | `R/(W)` | — | min=0 | Device link selector |
| `cam.params.DeviceControl.DeviceLinkSpeed` | `int` | `R` | — | min=0 | Transmission link speed |
| `cam.params.DeviceControl.DeviceLinkConnectionCount` | `int` | `R` | — | min=0 | Device link connection count |
| `cam.params.DeviceControl.DeviceLinkHeartbeatMode` | `Hik.DeviceHeartbeatMode` | `R/W` | — | — | Heartbeat mode |
| `cam.params.DeviceControl.DeviceStreamChannelCount` | `int` | `R` | — | min=0 | Stream channel count |
| `cam.params.DeviceControl.DeviceStreamChannelSelector` | `int` | `R/(W)` | — | min=0 | Stream channel selector |
| `cam.params.DeviceControl.DeviceStreamChannelType` | `Hik.DeviceStreamChannelType` | `R` | — | — | Stream channel type |
| `cam.params.DeviceControl.DeviceStreamChannelLink` | `int` | `R` | — | min=0 | Stream channel link count |
| `cam.params.DeviceControl.DeviceStreamChannelEndianness` | `Hik.DeviceStreamChannelEndianness` | `R` | — | — | Image data byte order |
| `cam.params.DeviceControl.DeviceStreamChannelPacketSize` | `int` | `R/(W)` | — | min=220, max=9156, step=8 | Stream data packet size |
| `cam.params.DeviceControl.DeviceEventChannelCount` | `int` | `R` | — | min=0 | Event channel count |
| `cam.params.DeviceControl.DeviceCharacterSet` | `Hik.DeviceCharacterSet` | `R` | — | — | Character set in device registers |
| `cam.params.DeviceControl.DeviceReset` | `command` | `W` | — | — | Reset device |
| `cam.params.DeviceControl.DeviceMaxThroughput` | `int` | `R` | — | min=0 | Maximum device throughput |
| `cam.params.DeviceControl.DeviceConnectionSelector` | `int` | `R/(W)` | — | min=0 | Device connection selector |
| `cam.params.DeviceControl.DeviceConnectionSpeed` | `int` | `R` | `Mbps` | min=0 | Device connection speed |

## ImageFormatControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.ImageFormatControl.WidthMax` | `int` | `R` | — | min=1 | Maximum image width |
| `cam.params.ImageFormatControl.HeightMax` | `int` | `R` | — | min=1 | Maximum image height |
| `cam.params.ImageFormatControl.RegionSelector` | `Hik.RegionSelector` | `R/(W)` | — | — | ROI selector |
| `cam.params.ImageFormatControl.RegionDestination` | `Hik.RegionDestination` | `R/(W)` | — | — | Stream destination for region |
| `cam.params.ImageFormatControl.Width` | `int` | `R/(W)` | — | min=1 | ROI width |
| `cam.params.ImageFormatControl.Height` | `int` | `R/(W)` | — | min=1 | ROI height |
| `cam.params.ImageFormatControl.OffsetX` | `int` | `R/W` | — | min=0 | ROI horizontal offset |
| `cam.params.ImageFormatControl.OffsetY` | `int` | `R/W` | — | min=0 | ROI vertical offset |
| `cam.params.ImageFormatControl.ReverseScanDirection` | `bool` | `R/(W)` | — | — | Reverse scan direction |
| `cam.params.ImageFormatControl.PixelFormat` | `Hik.PixelFormat` | `R/(W)` | — | — | Image pixel format |
| `cam.params.ImageFormatControl.PixelSize` | `Hik.PixelSize` | `R/(W)` | — | — | Bits per pixel |
| `cam.params.ImageFormatControl.ImageCompressionMode` | `Hik.ImageCompressionMode` | `R/(W)` | — | — | Image compression mode |
| `cam.params.ImageFormatControl.ImageCompressionQuality` | `int` | `R/(W)` | — | min=50 | Image compression quality |
| `cam.params.ImageFormatControl.TestPatternGeneratorSelector` | `Hik.TestPatternGeneratorSelector` | `R/(W)` | — | — | Test pattern generator selector |
| `cam.params.ImageFormatControl.TestPattern` | `Hik.TestPattern` | `R/(W)` | — | — | Test pattern selection |
| `cam.params.ImageFormatControl.FrameSpecInfoSelector` | `Hik.FrameSpecInfoSelector` | `R/(W)` | — | — | Watermark info selector |
| `cam.params.ImageFormatControl.FrameSpecInfo` | `bool` | `R/W` | — | — | Enable watermark info |
| `cam.params.ImageFormatControl.BinningHorizontal` | `int` | `R/(W)` | — | min=1 | Horizontal binning |
| `cam.params.ImageFormatControl.BinningVertical` | `int` | `R/(W)` | — | min=1 | Vertical binning |
| `cam.params.ImageFormatControl.DecimationHorizontal` | `int` | `R/(W)` | — | min=1 | Horizontal decimation |
| `cam.params.ImageFormatControl.DecimationVertical` | `int` | `R/(W)` | — | min=1 | Vertical decimation |

## AcquisitionControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.AcquisitionControl.AcquisitionMode` | `Hik.AcquisitionMode` | `R/(W)` | — | — | Acquisition mode (single/multi/continuous) |
| `cam.params.AcquisitionControl.AcquisitionStart` | `command` | `W` | — | — | Start acquisition |
| `cam.params.AcquisitionControl.AcquisitionStop` | `command` | `W` | — | — | Stop acquisition |
| `cam.params.AcquisitionControl.AcquisitionBurstFrameCount` | `int` | `R/W` | — | min=0 | Burst frame count |
| `cam.params.AcquisitionControl.AcquisitionLineRate` | `int` | `R/W` | — | min=1 | Line rate |
| `cam.params.AcquisitionControl.AcquisitionLineRateEnable` | `bool` | `R/W` | — | — | Line rate control enable |
| `cam.params.AcquisitionControl.ResultingLineRate` | `int` | `R` | `Hz` | min=0 | Resulting line rate |
| `cam.params.AcquisitionControl.ResultingFrameRate` | `float` | `R` | `fps` | min=0.0 | Resulting frame rate |
| `cam.params.AcquisitionControl.AcquisitionFrameRate` | `float` | `R/W` | `fps` | min=0.0 | Acquisition frame rate |
| `cam.params.AcquisitionControl.AcquisitionFrameRateEnable` | `bool` | `R/W` | — | — | Frame rate control enable |
| `cam.params.AcquisitionControl.TriggerSelector` | `Hik.TriggerSelector` | `R/W` | — | — | Trigger event selector |
| `cam.params.AcquisitionControl.TriggerMode` | `Hik.TriggerMode` | `R/W` | — | — | Trigger mode (on/off) |
| `cam.params.AcquisitionControl.TriggerSource` | `Hik.TriggerSource` | `R/W` | — | — | Trigger source |
| `cam.params.AcquisitionControl.TriggerActivation` | `Hik.TriggerActivation` | `R/W` | — | — | Trigger activation edge/level |
| `cam.params.AcquisitionControl.TriggerDelay` | `float` | `R/W` | `us` | min=0.0 | Trigger delay |
| `cam.params.AcquisitionControl.TriggerSoftware` | `command` | `W` | — | — | Execute software trigger |
| `cam.params.AcquisitionControl.ExposureMode` | `Hik.ExposureMode` | `R/W` | — | — | Exposure mode |
| `cam.params.AcquisitionControl.ExposureTime` | `float` | `R/W` | `us` | min=0.0 | Exposure time |
| `cam.params.AcquisitionControl.ExposureAuto` | `Hik.ExposureAuto` | `R/W` | — | — | Auto exposure |
| `cam.params.AcquisitionControl.AutoExposureTimeLowerLimit` | `int` | `R/(W)` | `us` | min=0 | Auto exposure time lower limit |
| `cam.params.AcquisitionControl.AutoExposureTimeUpperLimit` | `int` | `R/(W)` | `us` | min=0 | Auto exposure time upper limit |
| `cam.params.AcquisitionControl.FrameTimeoutEnable` | `bool` | `R/W` | — | — | Frame timeout enable |
| `cam.params.AcquisitionControl.FrameTimeoutTime` | `int` | `R/W` | `ms` | min=87 | Frame timeout time |

## AnalogControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.AnalogControl.Gain` | `float` | `R/W` | `dB` | min=0.0 | Gain |
| `cam.params.AnalogControl.GainAuto` | `Hik.GainAuto` | `R/W` | — | — | Auto gain |
| `cam.params.AnalogControl.AutoGainLowerLimit` | `float` | `R/W` | `dB` | min=0.0 | Auto gain lower limit |
| `cam.params.AnalogControl.AutoGainUpperLimit` | `float` | `R/W` | `dB` | min=0.0 | Auto gain upper limit |
| `cam.params.AnalogControl.ADCGainEnable` | `bool` | `R/W` | — | — | ADC gain enable |
| `cam.params.AnalogControl.DigitalShift` | `float` | `R` | — | min=0.0 | Digital shift |
| `cam.params.AnalogControl.DigitalShiftEnable` | `bool` | `R/W` | — | — | Digital shift enable |
| `cam.params.AnalogControl.Brightness` | `int` | `R/W` | — | min=0 | Brightness |
| `cam.params.AnalogControl.BlackLevel` | `float` | `R/W` | — | min=0.0 | Black level |
| `cam.params.AnalogControl.BlackLevelEnable` | `bool` | `R/W` | — | — | Black level enable |
| `cam.params.AnalogControl.BalanceWhiteAuto` | `Hik.BalanceWhiteAuto` | `R/W` | — | — | Auto white balance |
| `cam.params.AnalogControl.BalanceRatioSelector` | `Hik.BalanceRatioSelector` | `R` | — | — | White balance ratio selector |
| `cam.params.AnalogControl.BalanceRatio` | `int` | `R` | — | min=0 | White balance ratio |
| `cam.params.AnalogControl.Gamma` | `float` | `R/W` | — | min=0.0 | Gamma correction |
| `cam.params.AnalogControl.GammaSelector` | `Hik.GammaSelector` | `R/W` | — | — | Gamma selector |
| `cam.params.AnalogControl.GammaEnable` | `bool` | `R/W` | — | — | Gamma enable |
| `cam.params.AnalogControl.Hue` | `int` | `R` | — | min=0 | Hue adjustment |
| `cam.params.AnalogControl.HueEnable` | `bool` | `R/W` | — | — | Hue enable |
| `cam.params.AnalogControl.Saturation` | `int` | `R` | — | min=0 | Saturation adjustment |
| `cam.params.AnalogControl.SaturationEnable` | `bool` | `R/W` | — | — | Saturation enable |
| `cam.params.AnalogControl.AutoFunctionAOISelector` | `Hik.AutoFunctionAOISelector` | `R/W` | — | — | Auto function AOI selector |
| `cam.params.AnalogControl.AutoFunctionAOIWidth` | `int` | `R/W` | — | min=0 | Auto function AOI width |
| `cam.params.AnalogControl.AutoFunctionAOIHeight` | `int` | `R/W` | — | min=0 | Auto function AOI height |
| `cam.params.AnalogControl.AutoFunctionAOIOffsetX` | `int` | `R` | — | min=0 | Auto function AOI horizontal offset |
| `cam.params.AnalogControl.AutoFunctionAOIUsageIntensity` | `bool` | `R/W` | — | — | Auto exposure based on AOI |
| `cam.params.AnalogControl.AutoFunctionAOIUsageWhiteBalance` | `bool` | `R` | — | — | Auto white balance based on AOI |

> **See also – host-side ISP helpers:** the SDK image-processing pipeline can
> apply Bayer-quality, gamma, CCM, contrast, purple-fringe and ISP processing
> on the host without changing GenICam node values. See
> `cam.set_bayer_cvt_quality`, `cam.set_bayer_filter_enable`,
> `cam.set_bayer_gamma`, `cam.set_gamma`, `cam.set_bayer_ccm`,
> `cam.image_contrast`, `cam.purple_fringing`, `cam.set_isp_config` and
> `cam.isp_process` (defined in `hikcamera.camera`).

## LUTControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.LUTControl.LUTSelector` | `Hik.LUTSelector` | `R/W` | — | — | LUT channel selector |
| `cam.params.LUTControl.LUTEnable` | `bool` | `R/W` | — | — | LUT enable |
| `cam.params.LUTControl.LUTIndex` | `int` | `R/W` | — | min=0 | LUT index |
| `cam.params.LUTControl.LUTValue` | `int` | `R/W` | — | — | LUT value |

## EncoderControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.EncoderControl.EncoderSelector` | `Hik.EncoderSelector` | `R/W` | — | — | Encoder selector |
| `cam.params.EncoderControl.EncoderSourceA` | `Hik.LineSelector` | `R/W` | — | — | Encoder source A |
| `cam.params.EncoderControl.EncoderSourceB` | `Hik.LineSelector` | `R/W` | — | — | Encoder source B |
| `cam.params.EncoderControl.EncoderTriggerMode` | `Hik.EncoderTriggerMode` | `R/W` | — | — | Encoder trigger mode |
| `cam.params.EncoderControl.EncoderCounterMode` | `Hik.EncoderCounterMode` | `R/W` | — | — | Encoder counter mode |
| `cam.params.EncoderControl.EncoderCounter` | `int` | `R` | — | min=0 | Encoder counter value |
| `cam.params.EncoderControl.EncoderCounterMax` | `int` | `R/W` | — | min=1 | Encoder counter max |
| `cam.params.EncoderControl.EncoderCounterReset` | `command` | `R/W` | — | — | Encoder counter reset |
| `cam.params.EncoderControl.EncoderMaxReverseCounter` | `int` | `R/W` | — | min=1 | Encoder max reverse counter |
| `cam.params.EncoderControl.EncoderReverseCounterReset` | `command` | `R/W` | — | — | Encoder reverse counter reset |

## FrequencyConverterControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.FrequencyConverterControl.InputSource` | `Hik.LineSelector` | `R/W` | — | — | Frequency converter input source |
| `cam.params.FrequencyConverterControl.SignalAlignment` | `Hik.FrequencyConverterSignalAlignment` | `R/W` | — | — | Signal alignment edge |
| `cam.params.FrequencyConverterControl.PreDivider` | `int` | `R/W` | — | min=1 | Pre-divider |
| `cam.params.FrequencyConverterControl.Multiplier` | `int` | `R/W` | — | min=1 | Multiplier |
| `cam.params.FrequencyConverterControl.PostDivider` | `int` | `R/W` | — | min=1 | Post-divider |

## ShadingCorrection

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.ShadingCorrection.ShadingSelector` | `Hik.ShadingSelector` | `R/W` | — | — | Shading correction selector |
| `cam.params.ShadingCorrection.ActivateShading` | `command` | `R/(W)` | — | — | Activate shading correction |
| `cam.params.ShadingCorrection.NUCEnable` | `bool` | `R/W` | — | — | NUC enable |
| `cam.params.ShadingCorrection.PRNUCEnable` | `bool` | `R/W` | — | — | PRNUC enable |

## DigitalIOControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.DigitalIOControl.LineSelector` | `Hik.LineSelector` | `R/W` | — | — | I/O line selector |
| `cam.params.DigitalIOControl.LineMode` | `Hik.LineMode` | `R/(W)` | — | — | I/O line mode |
| `cam.params.DigitalIOControl.LineStatus` | `bool` | `R/(W)` | — | — | I/O line status |
| `cam.params.DigitalIOControl.LineStatusAll` | `int` | `R` | — | min=0 | All I/O line status |
| `cam.params.DigitalIOControl.LineDebouncerTime` | `int` | `R/W` | — | — | I/O debouncer time |

## TransportLayerControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.TransportLayerControl.PayloadSize` | `int` | `R` | — | min=0 | Payload size per frame |
| `cam.params.TransportLayerControl.GevVersionMajor` | `int` | `R` | — | — | GEV major version |
| `cam.params.TransportLayerControl.GevVersionMinor` | `int` | `R` | — | — | GEV minor version |
| `cam.params.TransportLayerControl.GevDeviceModeIsBigEndian` | `bool` | `R` | — | — | Big-endian mode |
| `cam.params.TransportLayerControl.GevDeviceModeCharacterSet` | `Hik.GevDeviceModeCharacterSet` | `R` | — | — | Character set |
| `cam.params.TransportLayerControl.GevInterfaceSelector` | `int` | `R/(W)` | — | min=0 | GEV interface selector |
| `cam.params.TransportLayerControl.GevMACAddress` | `int` | `R` | — | — | MAC address |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationLLA` | `bool` | `R` | — | — | Is LLA IP configuration |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationDHCP` | `bool` | `R/W` | — | — | Is DHCP IP configuration |
| `cam.params.TransportLayerControl.GevCurrentIPConfigurationPersistentIP` | `bool` | `R/W` | — | — | Is persistent (static) IP configuration |
| `cam.params.TransportLayerControl.GevCurrentIPAddress` | `int` | `R` | — | — | Current IP address |
| `cam.params.TransportLayerControl.GevCurrentSubnetMask` | `int` | `R` | — | — | Current subnet mask |
| `cam.params.TransportLayerControl.GevCurrentDefaultGateway` | `int` | `R` | — | — | Current default gateway |
| `cam.params.TransportLayerControl.GevFirstURL` | `str` | `R` | — | — | First XML URL |
| `cam.params.TransportLayerControl.GevSecondURL` | `str` | `R` | — | — | Second XML URL |
| `cam.params.TransportLayerControl.GevNumberOfInterfaces` | `int` | `R` | — | min=0 | Number of GEV interfaces |
| `cam.params.TransportLayerControl.GevPersistentIPAddress` | `int` | `R/W` | — | min=0 | Persistent IP address |
| `cam.params.TransportLayerControl.GevPersistentSubnetMask` | `int` | `R/W` | — | min=0 | Persistent subnet mask |
| `cam.params.TransportLayerControl.GevPersistentDefaultGateway` | `int` | `R/W` | — | min=0 | Persistent default gateway |
| `cam.params.TransportLayerControl.GevLinkSpeed` | `int` | `R` | — | min=0 | GEV link speed |
| `cam.params.TransportLayerControl.GevMessageChannelCount` | `int` | `R` | — | min=0 | Message channel count |
| `cam.params.TransportLayerControl.GevStreamChannelCount` | `int` | `R` | — | min=0 | Stream channel count |
| `cam.params.TransportLayerControl.GevHeartbeatTimeout` | `int` | `R/W` | — | min=0 | Heartbeat timeout |
| `cam.params.TransportLayerControl.GevGVCPHeartbeatDisable` | `bool` | `R/W` | — | — | Disable GVCP heartbeat |
| `cam.params.TransportLayerControl.GevTimestampTickFrequency` | `int` | `R` | `Hz` | min=0 | Timestamp tick frequency |
| `cam.params.TransportLayerControl.GevTimestampControlLatch` | `command` | `W` | — | — | Latch timestamp |
| `cam.params.TransportLayerControl.GevTimestampControlReset` | `command` | `W` | — | — | Reset timestamp |
| `cam.params.TransportLayerControl.GevTimestampControlLatchReset` | `command` | `W` | — | — | Latch and reset timestamp |
| `cam.params.TransportLayerControl.GevTimestampValue` | `int` | `R` | — | — | Timestamp value |
| `cam.params.TransportLayerControl.GevCCP` | `Hik.GevCCP` | `R/W` | — | — | Control channel privilege |
| `cam.params.TransportLayerControl.GevStreamChannelSelector` | `int` | `R/W` | — | min=0 | Stream channel selector |
| `cam.params.TransportLayerControl.GevSCPInterfaceIndex` | `int` | `R` | — | min=0 | GEV interface index |
| `cam.params.TransportLayerControl.GevSCPHostPort` | `int` | `R/(W)` | — | min=0 | Host port |
| `cam.params.TransportLayerControl.GevSCPDirection` | `int` | `R` | — | min=0 | Stream channel direction |
| `cam.params.TransportLayerControl.GevSCPSFireTestPacket` | `bool` | `R/(W)` | — | — | Fire test packet enable |
| `cam.params.TransportLayerControl.GevSCPSDoNotFragment` | `bool` | `R/W` | — | — | Do not fragment |
| `cam.params.TransportLayerControl.GevSCPSBigEndian` | `bool` | `R` | — | — | Stream data big-endian |
| `cam.params.TransportLayerControl.GevSCPSPacketSize` | `int` | `R/W` | — | min=220, max=9156, step=8 | Network packet size |
| `cam.params.TransportLayerControl.GevSCPD` | `int` | `R/W` | — | min=0 | Inter-packet delay |
| `cam.params.TransportLayerControl.GevSCDA` | `int` | `R` | — | — | Stream data destination address |
| `cam.params.TransportLayerControl.GevSCSP` | `int` | `R` | — | — | Stream data source port |

## UserSetControl

| Structured path | Data type | Access | Unit | Range | Description |
|---|---|---|---|---|---|
| `cam.params.UserSetControl.UserSetCurrent` | `int` | `R` | — | min=0 | Current user set |
| `cam.params.UserSetControl.UserSetSelector` | `Hik.UserSetSelector` | `R/W` | — | — | User set selector |
| `cam.params.UserSetControl.UserSetLoad` | `command` | `W` | — | — | Load user set |
| `cam.params.UserSetControl.UserSetSave` | `command` | `W` | — | — | Save user set |
| `cam.params.UserSetControl.UserSetDefault` | `Hik.UserSetDefault` | `R/W` | — | — | Default user set loaded at boot |

