"""
HiKCamera – Python library for Hikvision industrial cameras.
HiKCamera – 海康威视工业相机 Python 库。

Quick start / 快速上手
----------------------

.. code-block:: python

    from hikcamera import (
        AccessMode,
        AcquisitionControl,
        AnalogControl,
        HikCamera,
        OutputFormat,
    )

    # Enumerate available cameras / 枚举可用相机
    cameras = HikCamera.enumerate()
    print(cameras)

    # Open the first camera exclusively / 以独占模式打开第一台相机
    with HikCamera.from_device_info(cameras[0]) as cam:
        cam.open(AccessMode.EXCLUSIVE)

        # Prefer ParamNode-based configuration for IDE completion and
        # validation. Legacy string names remain compatible for now, but will
        # be gradually deprecated.
        # 优先使用 ParamNode 配置方式以获得 IDE 补全和校验。旧字符串参数名
        # 当前仍兼容，但后续会逐步废弃。
        cam.set_parameter(AcquisitionControl.ExposureTime, 5000.0)
        cam.set_parameter(AnalogControl.Gain, 1.0)

        # Poll for frames / 轮询取帧
        cam.start_grabbing()
        frame = cam.get_frame(timeout_ms=1000, output_format=OutputFormat.BGR8)
        cam.stop_grabbing()

Public API / 公开接口
---------------------
The following names are exported at the package level for convenience:
以下名称在包级别导出，方便直接使用：

- :py:class:`~hikcamera.camera.HikCamera`
- :py:class:`~hikcamera.camera.DeviceInfo`
- :py:func:`~hikcamera.camera.enumerate_cameras`
- :py:class:`~hikcamera.enums.AccessMode`
- :py:class:`~hikcamera.enums.TransportLayer`
- :py:class:`~hikcamera.enums.StreamingMode`
- :py:class:`~hikcamera.enums.PixelFormat`
- :py:class:`~hikcamera.enums.OutputFormat`
- All exceptions from :py:mod:`hikcamera.exceptions`
  （:py:mod:`hikcamera.exceptions` 中的所有异常）
"""

from __future__ import annotations

from .camera import (
    GIGE_PACKET_SIZE_DEFAULT,
    GIGE_PACKET_SIZE_JUMBO,
    DeviceInfo,
    HikCamera,
    enumerate_cameras,
)
from .enums import (
    AccessMode,
    AcquisitionMode,
    AutoFunctionAOISelector,
    BalanceRatioSelector,
    BalanceWhiteAuto,
    DeviceCharacterSet,
    DeviceHeartbeatMode,
    DeviceScanType,
    DeviceStreamChannelEndianness,
    DeviceStreamChannelType,
    DeviceType,
    EncoderCounterMode,
    EncoderSelector,
    EncoderTriggerMode,
    ExposureAuto,
    ExposureMode,
    FrameSpecInfoSelector,
    FrequencyConverterSignalAlignment,
    GainAuto,
    GammaSelector,
    GevCCP,
    GevDeviceModeCharacterSet,
    ImageCompressionMode,
    LineMode,
    LineSelector,
    LUTSelector,
    MvErrorCode,
    OutputFormat,
    PixelFormat,
    PixelSize,
    RegionDestination,
    RegionSelector,
    ShadingSelector,
    StreamingMode,
    TestPattern,
    TestPatternGeneratorSelector,
    TransportLayer,
    TriggerActivation,
    TriggerMode,
    TriggerSelector,
    TriggerSource,
    UserSetDefault,
    UserSetSelector,
)
from .exceptions import (
    CameraAlreadyOpenError,
    CameraConnectionError,
    CameraNotFoundError,
    CameraNotOpenError,
    DeviceDisconnectedError,
    FrameTimeoutError,
    GrabbingError,
    GrabbingNotStartedError,
    HikCameraError,
    ImageConversionError,
    ParameterError,
    ParameterNotSupportedError,
    ParameterReadOnlyError,
    ParameterValueError,
    PixelFormatError,
    SDKInitializationError,
    SDKNotFoundError,
)
from .params import (
    AcquisitionControl,
    AnalogControl,
    DeviceControl,
    DigitalIOControl,
    EncoderControl,
    FrequencyConverterControl,
    ImageFormatControl,
    LUTControl,
    ParamNode,
    ShadingCorrection,
    TransportLayerControl,
    UserSetControl,
)
from .sdk_wrapper import finalize_sdk

__all__ = [
    # Camera classes / 相机类
    "HikCamera",
    "DeviceInfo",
    "enumerate_cameras",
    # SDK lifecycle / SDK 生命周期
    "finalize_sdk",
    # Constants / 常量
    "GIGE_PACKET_SIZE_DEFAULT",
    "GIGE_PACKET_SIZE_JUMBO",
    # Enumerations / 枚举类型
    "AccessMode",
    "TransportLayer",
    "StreamingMode",
    "PixelFormat",
    "OutputFormat",
    "MvErrorCode",
    # Parameter value enumerations / 参数值枚举
    "ExposureAuto",
    "GainAuto",
    "GammaSelector",
    "AcquisitionMode",
    "TriggerMode",
    "TriggerSource",
    "TriggerActivation",
    "TriggerSelector",
    "LineSelector",
    "LineMode",
    "BalanceWhiteAuto",
    "UserSetSelector",
    "UserSetDefault",
    # New parameter value enumerations / 新增参数值枚举
    "DeviceType",
    "DeviceScanType",
    "DeviceHeartbeatMode",
    "DeviceStreamChannelType",
    "DeviceStreamChannelEndianness",
    "DeviceCharacterSet",
    "RegionSelector",
    "RegionDestination",
    "PixelSize",
    "ImageCompressionMode",
    "TestPatternGeneratorSelector",
    "TestPattern",
    "FrameSpecInfoSelector",
    "ExposureMode",
    "BalanceRatioSelector",
    "AutoFunctionAOISelector",
    "LUTSelector",
    "EncoderSelector",
    "EncoderTriggerMode",
    "EncoderCounterMode",
    "FrequencyConverterSignalAlignment",
    "ShadingSelector",
    "GevCCP",
    "GevDeviceModeCharacterSet",
    # Structured parameter groups / 结构化参数组
    "ParamNode",
    "DeviceControl",
    "ImageFormatControl",
    "AcquisitionControl",
    "AnalogControl",
    "LUTControl",
    "EncoderControl",
    "FrequencyConverterControl",
    "ShadingCorrection",
    "DigitalIOControl",
    "TransportLayerControl",
    "UserSetControl",
    # Exceptions / 异常
    "HikCameraError",
    "SDKNotFoundError",
    "SDKInitializationError",
    "CameraNotFoundError",
    "CameraConnectionError",
    "CameraAlreadyOpenError",
    "CameraNotOpenError",
    "DeviceDisconnectedError",
    "GrabbingError",
    "GrabbingNotStartedError",
    "FrameTimeoutError",
    "ParameterError",
    "ParameterNotSupportedError",
    "ParameterReadOnlyError",
    "ParameterValueError",
    "PixelFormatError",
    "ImageConversionError",
]

try:
    from importlib.metadata import version as _metadata_version

    __version__ = _metadata_version("hikcamera")
except Exception:  # pragma: no cover – fallback for editable/dev installs
    __version__ = "0.1.0"
