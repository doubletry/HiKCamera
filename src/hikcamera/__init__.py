"""
HiKCamera – Python library for Hikvision industrial cameras.
HiKCamera – 海康威视工业相机 Python 库。

Quick start / 快速上手
----------------------

.. code-block:: python

    from hikcamera import (
        Hik,
        HikCamera,
    )

    # Enumerate available cameras / 枚举可用相机
    cameras = HikCamera.enumerate()
    print(cameras)

    # Open the first camera exclusively / 以独占模式打开第一台相机
    with HikCamera.from_device_info(cameras[0]) as cam:
        cam.open(Hik.AccessMode.EXCLUSIVE)

        # Prefer the structured ``cam.params`` API for IDE completion and
        # validation.
        # 优先使用结构化 ``cam.params`` API，以获得 IDE 补全和校验。
        cam.params.AcquisitionControl.ExposureTime.set(5000.0)
        cam.params.AnalogControl.Gain.set(1.0)
        cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)

        # Poll for frames / 轮询取帧
        cam.start_grabbing()
        frame = cam.get_frame(timeout_ms=1000, output_format=Hik.OutputFormat.BGR8)
        cam.stop_grabbing()

Public API / 公开接口
---------------------
The following names are exported at the package level for convenience:
以下名称在包级别导出，方便直接使用：

- :py:class:`~hikcamera.camera.HikCamera`
- :py:class:`~hikcamera.camera.DeviceInfo`
- :py:func:`~hikcamera.camera.enumerate_cameras`
- :py:class:`~hikcamera.enums.Hik`
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
from .enums import Hik
from .exceptions import (
    CameraAlreadyOpenError,
    CameraConnectionError,
    CameraNotFoundError,
    CameraNotOpenError,
    DeviceDisconnectedError,
    FeatureUnsupportedError,
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
    "Hik",
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
    "FeatureUnsupportedError",
]

try:
    from importlib.metadata import version as _metadata_version

    __version__ = _metadata_version("hikcamera")
except Exception:  # pragma: no cover – fallback for editable/dev installs
    __version__ = "0.1.0"
