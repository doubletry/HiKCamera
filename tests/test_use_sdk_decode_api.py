"""
Tests for the use_sdk_decode setter / getter API and that constructors no
longer accept the legacy ``use_sdk_decode=`` keyword argument.
针对 use_sdk_decode setter / getter 以及"构造函数不再接受
``use_sdk_decode=``"的回归测试。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hikcamera.camera import HikCamera


class TestUseSdkDecodeApi:
    def test_default_is_true(self):
        with patch("hikcamera.camera.load_sdk"):
            cam = HikCamera()
        assert cam.get_use_sdk_decode() is True
        assert cam.use_sdk_decode is True

    def test_set_false_then_get(self):
        with patch("hikcamera.camera.load_sdk"):
            cam = HikCamera()
        cam.set_use_sdk_decode(False)
        assert cam.get_use_sdk_decode() is False
        assert cam.use_sdk_decode is False

    def test_set_use_sdk_decode_rejects_non_bool(self):
        with patch("hikcamera.camera.load_sdk"):
            cam = HikCamera()
        with pytest.raises(TypeError):
            cam.set_use_sdk_decode("yes")  # type: ignore[arg-type]

    def test_init_rejects_use_sdk_decode_kwarg(self):
        with patch("hikcamera.camera.load_sdk"):
            with pytest.raises(TypeError):
                HikCamera(use_sdk_decode=False)  # type: ignore[call-arg]

    def test_factory_rejects_use_sdk_decode_kwarg(self):
        with patch("hikcamera.camera.load_sdk"):
            with pytest.raises(TypeError):
                HikCamera.from_serial_number(  # type: ignore[call-arg]
                    "SN0", use_sdk_decode=False
                )
            with pytest.raises(TypeError):
                HikCamera.from_ip(  # type: ignore[call-arg]
                    "192.168.1.1", use_sdk_decode=False
                )
            with pytest.raises(TypeError):
                HikCamera.from_device_info(  # type: ignore[call-arg]
                    object(), use_sdk_decode=False
                )

    def test_set_true_when_open_applies_bayer_quality(self):
        """
        Toggling SDK decode back on while the camera is open should mirror
        ``open()`` and call ``set_bayer_cvt_quality(BEST)``.
        相机已打开时将 SDK 解码切回启用，应复刻 ``open()`` 的行为，
        调用 ``set_bayer_cvt_quality(BEST)``。
        """
        with patch("hikcamera.camera.load_sdk"):
            cam = HikCamera()
        cam._is_open = True
        cam.use_sdk_decode = False  # simulate previously disabled
        with patch.object(cam, "set_bayer_cvt_quality") as m:
            cam.set_use_sdk_decode(True)
            m.assert_called_once()
        assert cam.use_sdk_decode is True

    def test_set_true_when_closed_does_not_call_sdk(self):
        with patch("hikcamera.camera.load_sdk"):
            cam = HikCamera()
        cam.use_sdk_decode = False
        with patch.object(cam, "set_bayer_cvt_quality") as m:
            cam.set_use_sdk_decode(True)
            m.assert_not_called()

    def test_set_false_when_open_does_not_call_sdk(self):
        with patch("hikcamera.camera.load_sdk"):
            cam = HikCamera()
        cam._is_open = True
        with patch.object(cam, "set_bayer_cvt_quality") as m:
            cam.set_use_sdk_decode(False)
            m.assert_not_called()
