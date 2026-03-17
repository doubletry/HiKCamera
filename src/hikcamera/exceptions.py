"""
Custom exceptions for the HiKCamera library.

All exceptions inherit from HikCameraError, making it easy to catch
all library-specific errors with a single except clause.
"""

from __future__ import annotations


class HikCameraError(Exception):
    """Base exception for all HiKCamera errors."""

    def __init__(self, message: str, error_code: int = 0) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        if self.error_code:
            return f"[0x{self.error_code:08X}] {self.message}"
        return self.message


class SDKNotFoundError(HikCameraError):
    """Raised when the Hikvision MVS SDK dynamic library cannot be located."""


class CameraNotFoundError(HikCameraError):
    """Raised when no camera matches the given IP or serial number."""


class CameraConnectionError(HikCameraError):
    """Raised when a camera connection fails to open or is dropped."""


class CameraAlreadyOpenError(HikCameraError):
    """Raised when trying to open a camera that is already open."""


class CameraNotOpenError(HikCameraError):
    """Raised when an operation requires an open camera but none is open."""


class GrabbingError(HikCameraError):
    """Raised when frame grabbing encounters an unrecoverable error."""


class GrabbingNotStartedError(HikCameraError):
    """Raised when an image retrieval call is made before grabbing is started."""


class FrameTimeoutError(HikCameraError):
    """Raised when a frame is not received within the specified timeout."""


class ParameterError(HikCameraError):
    """Raised for generic parameter get/set errors."""


class ParameterNotSupportedError(ParameterError):
    """
    Raised when a parameter does not exist on the connected camera model.

    The Hikvision SDK returns specific error codes when a feature node is
    absent from the camera's GenICam XML description.  This exception wraps
    those codes so callers can easily distinguish "not supported" from other
    parameter errors.
    """


class ParameterReadOnlyError(ParameterError):
    """Raised when trying to write a read-only parameter."""


class PixelFormatError(HikCameraError):
    """Raised when an unsupported or mismatched pixel format is encountered."""


class ImageConversionError(HikCameraError):
    """Raised when an image buffer cannot be converted to a numpy array."""
