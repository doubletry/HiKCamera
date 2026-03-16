"""
HiKCamera – Python library for Hikvision industrial cameras.

Quick start
-----------

.. code-block:: python

    from hikcamera import HikCamera, AccessMode, OutputFormat

    # Enumerate available cameras
    cameras = HikCamera.enumerate()
    print(cameras)

    # Open the first camera exclusively
    with HikCamera.from_device_info(cameras[0]) as cam:
        cam.open(AccessMode.EXCLUSIVE)

        # Adjust parameters (silently ignores unsupported ones)
        cam.set_parameter("ExposureTime", 5000.0)
        cam.set_parameter("Gain", 1.0)

        # Poll for frames
        cam.start_grabbing()
        frame = cam.get_frame(timeout_ms=1000, output_format=OutputFormat.BGR8)
        cam.stop_grabbing()

Public API
----------
The following names are exported at the package level for convenience:

- :py:class:`~hikcamera.camera.HikCamera`
- :py:class:`~hikcamera.camera.DeviceInfo`
- :py:func:`~hikcamera.camera.enumerate_cameras`
- :py:class:`~hikcamera.enums.AccessMode`
- :py:class:`~hikcamera.enums.TransportLayer`
- :py:class:`~hikcamera.enums.StreamingMode`
- :py:class:`~hikcamera.enums.PixelFormat`
- :py:class:`~hikcamera.enums.OutputFormat`
- All exceptions from :py:mod:`hikcamera.exceptions`
"""

from __future__ import annotations

from .camera import DeviceInfo, HikCamera, enumerate_cameras
from .enums import AccessMode, MvErrorCode, OutputFormat, PixelFormat, StreamingMode, TransportLayer
from .exceptions import (
    CameraAlreadyOpenError,
    CameraConnectionError,
    CameraNotFoundError,
    CameraNotOpenError,
    FrameTimeoutError,
    GrabbingError,
    GrabbingNotStartedError,
    HikCameraError,
    ImageConversionError,
    ParameterError,
    ParameterNotSupportedError,
    ParameterReadOnlyError,
    PixelFormatError,
    SDKNotFoundError,
)

__all__ = [
    # Camera classes
    "HikCamera",
    "DeviceInfo",
    "enumerate_cameras",
    # Enumerations
    "AccessMode",
    "TransportLayer",
    "StreamingMode",
    "PixelFormat",
    "OutputFormat",
    "MvErrorCode",
    # Exceptions
    "HikCameraError",
    "SDKNotFoundError",
    "CameraNotFoundError",
    "CameraConnectionError",
    "CameraAlreadyOpenError",
    "CameraNotOpenError",
    "GrabbingError",
    "GrabbingNotStartedError",
    "FrameTimeoutError",
    "ParameterError",
    "ParameterNotSupportedError",
    "ParameterReadOnlyError",
    "PixelFormatError",
    "ImageConversionError",
]

__version__ = "0.1.0"
