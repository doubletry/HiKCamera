"""
Custom exceptions for the HiKCamera library.
HiKCamera 库自定义异常模块。

All exceptions inherit from HikCameraError, making it easy to catch
all library-specific errors with a single except clause.
所有异常均继承自 HikCameraError，方便通过单一 except 子句捕获
所有库级别的错误。
"""

from __future__ import annotations


class HikCameraError(Exception):
    """
    Base exception for all HiKCamera errors.
    所有 HiKCamera 错误的基类。
    """

    def __init__(self, message: str, error_code: int = 0) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        if self.error_code:
            return f"[0x{self.error_code:08X}] {self.message}"
        return self.message


class SDKNotFoundError(HikCameraError):
    """
    Raised when the Hikvision MVS SDK dynamic library cannot be located.
    当无法找到海康威视 MVS SDK 动态库时抛出。
    """


class CameraNotFoundError(HikCameraError):
    """
    Raised when no camera matches the given IP or serial number.
    当没有相机匹配给定的 IP 地址或序列号时抛出。
    """


class CameraConnectionError(HikCameraError):
    """
    Raised when a camera connection fails to open or is dropped.
    当相机连接打开失败或断开时抛出。
    """


class CameraAlreadyOpenError(HikCameraError):
    """
    Raised when trying to open a camera that is already open.
    当尝试打开已处于打开状态的相机时抛出。
    """


class CameraNotOpenError(HikCameraError):
    """
    Raised when an operation requires an open camera but none is open.
    当操作需要已打开的相机但相机未打开时抛出。
    """


class GrabbingError(HikCameraError):
    """
    Raised when frame grabbing encounters an unrecoverable error.
    当取帧过程遇到不可恢复的错误时抛出。
    """


class GrabbingNotStartedError(HikCameraError):
    """
    Raised when an image retrieval call is made before grabbing is started.
    当在未开始取帧的情况下调用图像获取函数时抛出。
    """


class FrameTimeoutError(HikCameraError):
    """
    Raised when a frame is not received within the specified timeout.
    当在指定超时时间内未收到帧时抛出。
    """


class ParameterError(HikCameraError):
    """
    Raised for generic parameter get/set errors.
    通用参数获取/设置错误时抛出。
    """


class ParameterNotSupportedError(ParameterError):
    """
    Raised when a parameter does not exist on the connected camera model.
    当参数在当前连接的相机型号上不存在时抛出。

    The Hikvision SDK returns specific error codes when a feature node is
    absent from the camera's GenICam XML description.  This exception wraps
    those codes so callers can easily distinguish "not supported" from other
    parameter errors.
    当特征节点在相机的 GenICam XML 描述中不存在时，海康威视 SDK 会返回特定
    错误码。此异常封装了这些错误码，便于调用者区分"不支持"和其他参数错误。
    """


class ParameterValueError(ParameterError):
    """
    Raised when a value does not match the expected type or allowed values
    for a known parameter.
    当值与已知参数的期望类型或允许值不匹配时抛出。
    """


class ParameterReadOnlyError(ParameterError):
    """
    Raised when trying to write a read-only parameter.
    当尝试写入只读参数时抛出。
    """


class PixelFormatError(HikCameraError):
    """
    Raised when an unsupported or mismatched pixel format is encountered.
    当遇到不支持或不匹配的像素格式时抛出。
    """


class ImageConversionError(HikCameraError):
    """
    Raised when an image buffer cannot be converted to a numpy array.
    当图像缓冲区无法转换为 numpy 数组时抛出。
    """
