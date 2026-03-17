"""Tests for hikcamera.exceptions."""

from __future__ import annotations

import pytest

from hikcamera.exceptions import (
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


class TestHikCameraError:
    def test_message_only(self):
        exc = HikCameraError("something went wrong")
        assert str(exc) == "something went wrong"
        assert exc.error_code == 0

    def test_message_with_code(self):
        exc = HikCameraError("bad param", 0x80000004)
        assert "0x80000004" in str(exc)
        assert exc.error_code == 0x80000004

    def test_is_exception(self):
        with pytest.raises(HikCameraError):
            raise HikCameraError("test")


class TestExceptionHierarchy:
    """All custom exceptions must be catchable as HikCameraError."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            SDKNotFoundError,
            CameraNotFoundError,
            CameraConnectionError,
            CameraAlreadyOpenError,
            CameraNotOpenError,
            GrabbingError,
            GrabbingNotStartedError,
            FrameTimeoutError,
            ParameterError,
            ParameterNotSupportedError,
            ParameterReadOnlyError,
            PixelFormatError,
            ImageConversionError,
        ],
    )
    def test_catchable_as_base(self, exc_class):
        with pytest.raises(HikCameraError):
            raise exc_class("test error")

    def test_parameter_not_supported_is_parameter_error(self):
        with pytest.raises(ParameterError):
            raise ParameterNotSupportedError("not supported")

    def test_parameter_read_only_is_parameter_error(self):
        with pytest.raises(ParameterError):
            raise ParameterReadOnlyError("read-only")
