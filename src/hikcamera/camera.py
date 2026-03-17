"""
High-level Hikvision industrial camera interface.

Typical usage (polling)
-----------------------

.. code-block:: python

    from hikcamera import HikCamera, AccessMode, OutputFormat

    cameras = HikCamera.enumerate()
    with HikCamera.from_device_info(cameras[0]) as cam:
        cam.open(AccessMode.EXCLUSIVE)
        cam.set_parameter("ExposureTime", 5000.0)
        cam.start_grabbing()
        frame = cam.get_frame(timeout_ms=1000, output_format=OutputFormat.BGR8)
        cam.stop_grabbing()

Typical usage (callback)
------------------------

.. code-block:: python

    import numpy as np
    from hikcamera import HikCamera, AccessMode, OutputFormat

    def on_frame(image: np.ndarray, frame_info: dict) -> None:
        print(f"Got frame {frame_info['frame_num']}: {image.shape}")

    cameras = HikCamera.enumerate()
    with HikCamera.from_device_info(cameras[0]) as cam:
        cam.open(AccessMode.EXCLUSIVE)
        cam.start_grabbing(callback=on_frame, output_format=OutputFormat.BGR8)
        import time; time.sleep(5)
        cam.stop_grabbing()
"""

from __future__ import annotations

import ctypes
import ipaddress
import logging
import socket
import struct
import threading
from collections.abc import Callable
from ctypes import POINTER, c_ubyte, c_uint, c_void_p
from typing import Any

import numpy as np

from .enums import AccessMode, MvErrorCode, OutputFormat, StreamingMode, TransportLayer
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
)
from .sdk_wrapper import (
    IMAGE_CALLBACK,
    MV_CC_DEVICE_INFO,
    MV_CC_DEVICE_INFO_LIST,
    MV_FRAME_OUT_INFO_EX,
    MV_PIXEL_CONVERT_PARAM,
    MVCC_ENUMVALUE,
    MVCC_FLOATVALUE,
    MVCC_INTVALUE_EX,
    MVCC_STRINGVALUE,
    load_sdk,
)
from .utils import raw_to_numpy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Error codes that mean "this parameter does not exist on this device"
_NOT_SUPPORTED_CODES: frozenset[int] = frozenset(
    {
        MvErrorCode.MV_E_SUPPORT,
        MvErrorCode.MV_E_NOTIMP,
        MvErrorCode.MV_E_GC_PROPERTY,
        MvErrorCode.MV_E_GC_ACCESS,
    }
)

_READ_ONLY_CODES: frozenset[int] = frozenset(
    {
        MvErrorCode.MV_E_GC_ACCESS,
    }
)


def _check(ret: int, operation: str = "") -> None:
    """
    Check an SDK return code; raise the appropriate exception on failure.

    Parameters
    ----------
    ret:
        SDK return code (0 = success).
    operation:
        Human-readable description used in the error message.
    """
    if ret == MvErrorCode.MV_OK:
        return
    code = ret & 0xFFFFFFFF
    msg = f"SDK error 0x{code:08X}" + (f" during {operation}" if operation else "")
    if code in _NOT_SUPPORTED_CODES:
        raise ParameterNotSupportedError(msg, code)
    if code == MvErrorCode.MV_E_GC_TIMEOUT:
        raise FrameTimeoutError(msg, code)
    if code == MvErrorCode.MV_E_PARAMETER:
        raise ParameterError(msg, code)
    raise HikCameraError(msg, code)


def _ip_to_int(ip: str) -> int:
    """Convert dotted-decimal IP string to big-endian integer."""
    return struct.unpack("!I", socket.inet_aton(ip))[0]


def _int_to_ip(n: int) -> str:
    """Convert big-endian integer to dotted-decimal IP string."""
    return socket.inet_ntoa(struct.pack("!I", n))


# ---------------------------------------------------------------------------
# DeviceInfo – a Python-friendly wrapper around MV_CC_DEVICE_INFO
# ---------------------------------------------------------------------------

class DeviceInfo:
    """
    Python-friendly wrapper around the SDK's ``MV_CC_DEVICE_INFO`` struct.

    Attributes
    ----------
    transport_layer : int
        The transport layer type (``MV_CC_DEVICE_INFO.nTLayerType``).
    ip : str | None
        IP address (GigE cameras only).
    serial_number : str
        Camera serial number.
    model_name : str
        Camera model name.
    user_defined_name : str
        User-defined name (may be empty).
    mac_address : str
        MAC address in ``XX:XX:XX:XX:XX:XX`` format.
    """

    def __init__(self, raw: MV_CC_DEVICE_INFO) -> None:
        self._raw = raw
        self.transport_layer: int = raw.nTLayerType

        mac_high = raw.nMacAddrHigh
        mac_low = raw.nMacAddrLow
        self.mac_address: str = (
            f"{(mac_high >> 8) & 0xFF:02X}:{mac_high & 0xFF:02X}:"
            f"{(mac_low >> 24) & 0xFF:02X}:{(mac_low >> 16) & 0xFF:02X}:"
            f"{(mac_low >> 8) & 0xFF:02X}:{mac_low & 0xFF:02X}"
        )

        if raw.nTLayerType == MV_CC_DEVICE_INFO.MV_GIGE_DEVICE:
            gi = raw.SpecialInfo.stGigEInfo
            self.ip: str | None = _int_to_ip(gi.nCurrentIp)
            self.serial_number: str = gi.chSerialNumber.decode("utf-8", errors="replace").strip("\x00")
            self.model_name: str = gi.chModelName.decode("utf-8", errors="replace").strip("\x00")
            self.user_defined_name: str = gi.chUserDefinedName.decode("utf-8", errors="replace").strip("\x00")
        elif raw.nTLayerType == MV_CC_DEVICE_INFO.MV_USB_DEVICE:
            ui = raw.SpecialInfo.stUsb3VInfo
            self.ip = None
            self.serial_number = ui.chSerialNumber.decode("utf-8", errors="replace").strip("\x00")
            self.model_name = ui.chModelName.decode("utf-8", errors="replace").strip("\x00")
            self.user_defined_name = ui.chUserDefinedName.decode("utf-8", errors="replace").strip("\x00")
        else:
            self.ip = None
            self.serial_number = ""
            self.model_name = "Unknown"
            self.user_defined_name = ""

    def __repr__(self) -> str:
        parts = [f"model={self.model_name!r}", f"sn={self.serial_number!r}"]
        if self.ip:
            parts.append(f"ip={self.ip!r}")
        return f"DeviceInfo({', '.join(parts)})"


# ---------------------------------------------------------------------------
# HikCamera
# ---------------------------------------------------------------------------

class HikCamera:
    """
    High-level interface to a single Hikvision industrial camera.

    The class manages the full lifecycle (create handle → open → grabbing →
    close → destroy handle) and exposes convenience methods for parameter
    access and frame capture.

    Construction
    ------------
    Use the class-methods :py:meth:`from_device_info`, :py:meth:`from_ip`,
    or :py:meth:`from_serial_number` rather than calling ``__init__``
    directly.

    Context manager support
    -----------------------
    ``HikCamera`` supports the ``with`` statement.  The device handle is
    destroyed automatically on exit (but :py:meth:`stop_grabbing` and
    :py:meth:`close` must be called before ``__exit__`` if grabbing is
    still active, or use ``HikCamera`` methods directly).

    Thread safety
    -------------
    Each camera instance is not thread-safe by itself.  Use external locking
    when sharing an instance across threads.
    """

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._sdk = load_sdk()
        self._handle: c_void_p = c_void_p(None)
        self._device_info: MV_CC_DEVICE_INFO | None = None
        self._is_open: bool = False
        self._is_grabbing: bool = False
        self._frame_buffer: ctypes.Array[c_ubyte] | None = None
        self._frame_buffer_size: int = 0
        self._callback_ref: IMAGE_CALLBACK | None = None  # keep reference alive
        self._user_callback: Callable[[np.ndarray, dict[str, Any]], None] | None = None
        self._output_format_for_callback: OutputFormat = OutputFormat.BGR8
        self._lock: threading.Lock = threading.Lock()

    @classmethod
    def enumerate(
        cls,
        transport_layers: TransportLayer = TransportLayer.ALL,
    ) -> list[DeviceInfo]:
        """
        Enumerate all accessible cameras on the host.

        Parameters
        ----------
        transport_layers:
            Bitmask of transport layers to scan.  Default is all layers.

        Returns
        -------
        list[DeviceInfo]
            One :py:class:`DeviceInfo` per discovered camera (may be empty).

        Raises
        ------
        SDKNotFoundError
            When the MVS SDK library cannot be loaded.
        HikCameraError
            When the SDK enumeration call fails.
        """
        sdk = load_sdk()
        dev_list = MV_CC_DEVICE_INFO_LIST()
        ret = sdk.MV_CC_EnumDevices(int(transport_layers), ctypes.byref(dev_list))
        _check(ret, "MV_CC_EnumDevices")
        result: list[DeviceInfo] = []
        for i in range(dev_list.nDeviceNum):
            ptr = dev_list.pDeviceInfo[i]
            if ptr:
                result.append(DeviceInfo(ptr.contents))
        logger.debug("Enumerated %d camera(s)", len(result))
        return result

    @classmethod
    def from_device_info(cls, device_info: DeviceInfo) -> HikCamera:
        """
        Create a :py:class:`HikCamera` from a :py:class:`DeviceInfo` object.

        Parameters
        ----------
        device_info:
            A :py:class:`DeviceInfo` obtained from :py:meth:`enumerate`.

        Returns
        -------
        HikCamera
            A camera instance with an SDK handle created.  Call
            :py:meth:`open` before grabbing frames.
        """
        cam = cls()
        cam._device_info = device_info._raw
        ret = cam._sdk.MV_CC_CreateHandle(ctypes.byref(cam._handle), ctypes.byref(device_info._raw))
        _check(ret, "MV_CC_CreateHandle")
        logger.debug("Created handle for %s", device_info)
        return cam

    @classmethod
    def from_ip(
        cls,
        ip: str,
        transport_layers: TransportLayer = TransportLayer.GIGE,
    ) -> HikCamera:
        """
        Find and create a handle for the camera at the given IP address.

        Parameters
        ----------
        ip:
            Dotted-decimal IP address (e.g. ``"192.168.1.100"``).
        transport_layers:
            Transport layers to search (default: GigE only).

        Returns
        -------
        HikCamera

        Raises
        ------
        CameraNotFoundError
            When no camera with that IP is found during enumeration.
        """
        # Validate the IP string first
        try:
            ipaddress.ip_address(ip)
        except ValueError as exc:
            raise ValueError(f"Invalid IP address: {ip!r}") from exc

        devices = cls.enumerate(transport_layers)
        for dev in devices:
            if dev.ip == ip:
                return cls.from_device_info(dev)
        raise CameraNotFoundError(f"No camera found with IP {ip!r}")

    @classmethod
    def from_serial_number(
        cls,
        serial_number: str,
        transport_layers: TransportLayer = TransportLayer.ALL,
    ) -> HikCamera:
        """
        Find and create a handle for the camera with the given serial number.

        Parameters
        ----------
        serial_number:
            Camera serial number string.
        transport_layers:
            Transport layers to search.

        Returns
        -------
        HikCamera

        Raises
        ------
        CameraNotFoundError
            When no camera with that serial number is found.
        """
        devices = cls.enumerate(transport_layers)
        for dev in devices:
            if dev.serial_number == serial_number:
                return cls.from_device_info(dev)
        raise CameraNotFoundError(f"No camera found with serial number {serial_number!r}")

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> HikCamera:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        """Stop grabbing, close the device, and destroy the SDK handle."""
        try:
            if self._is_grabbing:
                self.stop_grabbing()
        except HikCameraError:
            pass
        try:
            if self._is_open:
                self.close()
        except HikCameraError:
            pass
        if self._handle:
            try:
                self._sdk.MV_CC_DestroyHandle(self._handle)
            except Exception:  # noqa: BLE001
                pass
            self._handle = c_void_p(None)

    # ------------------------------------------------------------------
    # Open / close
    # ------------------------------------------------------------------

    def open(
        self,
        access_mode: AccessMode = AccessMode.EXCLUSIVE,
        streaming_mode: StreamingMode = StreamingMode.UNICAST,
        multicast_ip: str | None = None,
    ) -> None:
        """
        Open the camera with the specified access mode.

        Parameters
        ----------
        access_mode:
            How to connect to the camera.  See :py:class:`~hikcamera.enums.AccessMode`.
        streaming_mode:
            Unicast (default) or multicast.  GigE cameras only.
        multicast_ip:
            Multicast group IP (required when ``streaming_mode`` is
            :py:attr:`~hikcamera.enums.StreamingMode.MULTICAST`).

        Raises
        ------
        CameraAlreadyOpenError
            When the camera is already open.
        CameraConnectionError
            When the SDK open call fails.
        """
        if self._is_open:
            raise CameraAlreadyOpenError("Camera is already open")

        # For multicast, configure the group IP before opening
        if streaming_mode == StreamingMode.MULTICAST:
            if multicast_ip is None:
                raise ValueError("multicast_ip must be provided for multicast streaming")
            mc_int = _ip_to_int(multicast_ip)
            ret = self._sdk.MV_GIGE_SetMulticastIP(self._handle, mc_int)
            if ret != MvErrorCode.MV_OK:
                logger.warning("MV_GIGE_SetMulticastIP returned 0x%08X (may not be GigE camera)", ret & 0xFFFFFFFF)

        ret = self._sdk.MV_CC_OpenDevice(self._handle, int(access_mode), 0)
        if ret != MvErrorCode.MV_OK:
            code = ret & 0xFFFFFFFF
            raise CameraConnectionError(
                f"Failed to open camera (access_mode={access_mode.name}): "
                f"SDK error 0x{code:08X}",
                code,
            )
        self._is_open = True
        logger.info("Camera opened in %s mode", access_mode.name)

    def close(self) -> None:
        """
        Close the camera connection.

        Raises
        ------
        CameraNotOpenError
            When the camera is not open.
        """
        if not self._is_open:
            raise CameraNotOpenError("Camera is not open")
        ret = self._sdk.MV_CC_CloseDevice(self._handle)
        _check(ret, "MV_CC_CloseDevice")
        self._is_open = False
        logger.info("Camera closed")

    @property
    def is_open(self) -> bool:
        """Whether the camera device is currently open."""
        return self._is_open

    @property
    def is_connected(self) -> bool:
        """
        Whether the camera is physically connected (checks the SDK).

        Note: This may return ``False`` immediately after opening if the
        SDK has not yet completed initialisation.
        """
        if not self._is_open:
            return False
        return bool(self._sdk.MV_CC_IsDeviceConnected(self._handle))

    # ------------------------------------------------------------------
    # Grabbing
    # ------------------------------------------------------------------

    def start_grabbing(
        self,
        callback: Callable[[np.ndarray, dict[str, Any]], None] | None = None,
        output_format: OutputFormat = OutputFormat.BGR8,
    ) -> None:
        """
        Start image acquisition.

        Parameters
        ----------
        callback:
            Optional user-provided callback.  When supplied, frame data is
            decoded and passed to *callback* from an SDK-managed thread as::

                callback(image: np.ndarray, frame_info: dict)

            where *frame_info* contains ``frame_num``, ``width``, ``height``,
            ``pixel_format``, ``timestamp``, and ``frame_length`` keys.

            When *callback* is ``None``, use :py:meth:`get_frame` to pull
            frames manually.
        output_format:
            Pixel format of the numpy array delivered to *callback* or
            returned by :py:meth:`get_frame`.

        Raises
        ------
        CameraNotOpenError
            When the camera is not open.
        GrabbingError
            When the SDK start-grabbing call fails.
        """
        if not self._is_open:
            raise CameraNotOpenError("Cannot start grabbing: camera is not open")
        if self._is_grabbing:
            logger.warning("start_grabbing called while already grabbing; ignoring")
            return

        self._output_format_for_callback = output_format

        if callback is not None:
            self._user_callback = callback
            sdk_cb = IMAGE_CALLBACK(self._internal_callback)
            self._callback_ref = sdk_cb  # prevent garbage collection
            ret = self._sdk.MV_CC_RegisterImageCallBackEx(self._handle, sdk_cb, None)
            _check(ret, "MV_CC_RegisterImageCallBackEx")

        ret = self._sdk.MV_CC_StartGrabbing(self._handle)
        if ret != MvErrorCode.MV_OK:
            self._callback_ref = None
            self._user_callback = None
            code = ret & 0xFFFFFFFF
            raise GrabbingError(f"MV_CC_StartGrabbing failed: 0x{code:08X}", code)

        self._is_grabbing = True
        logger.info("Grabbing started (callback=%s, output_format=%s)", callback is not None, output_format.name)

    def stop_grabbing(self) -> None:
        """
        Stop image acquisition.

        Raises
        ------
        GrabbingNotStartedError
            When grabbing has not been started.
        """
        if not self._is_grabbing:
            raise GrabbingNotStartedError("Grabbing has not been started")
        ret = self._sdk.MV_CC_StopGrabbing(self._handle)
        self._is_grabbing = False
        self._callback_ref = None
        self._user_callback = None
        _check(ret, "MV_CC_StopGrabbing")
        logger.info("Grabbing stopped")

    @property
    def is_grabbing(self) -> bool:
        """Whether image acquisition is currently active."""
        return self._is_grabbing

    # ------------------------------------------------------------------
    # Frame retrieval (polling mode)
    # ------------------------------------------------------------------

    def get_frame(
        self,
        timeout_ms: int = 1000,
        output_format: OutputFormat = OutputFormat.BGR8,
    ) -> np.ndarray:
        """
        Retrieve one frame (polling mode).

        Allocates / reuses an internal buffer sized to the current
        ``PayloadSize`` camera parameter.

        Parameters
        ----------
        timeout_ms:
            Maximum time to wait for a frame in milliseconds.
        output_format:
            Desired numpy array format.

        Returns
        -------
        numpy.ndarray
            Decoded image.

        Raises
        ------
        CameraNotOpenError
            When the camera is not open.
        GrabbingNotStartedError
            When :py:meth:`start_grabbing` has not been called.
        FrameTimeoutError
            When no frame arrives within *timeout_ms*.
        ImageConversionError
            When the frame buffer cannot be converted.
        """
        if not self._is_open:
            raise CameraNotOpenError("Camera is not open")
        if not self._is_grabbing:
            raise GrabbingNotStartedError("Call start_grabbing() before get_frame()")

        self._ensure_frame_buffer()

        frame_info = MV_FRAME_OUT_INFO_EX()
        ret = self._sdk.MV_CC_GetOneFrameTimeout(
            self._handle,
            self._frame_buffer,
            self._frame_buffer_size,
            ctypes.byref(frame_info),
            timeout_ms,
        )
        if ret == MvErrorCode.MV_E_GC_TIMEOUT:
            raise FrameTimeoutError(f"No frame received within {timeout_ms} ms")
        _check(ret, "MV_CC_GetOneFrameTimeout")

        return self._decode_frame(self._frame_buffer, frame_info, output_format)

    def get_frame_ex(
        self,
        timeout_ms: int = 1000,
        output_format: OutputFormat = OutputFormat.BGR8,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Retrieve one frame together with its metadata.

        Like :py:meth:`get_frame` but also returns a dictionary with frame
        metadata (frame number, timestamp, pixel format, etc.).

        Returns
        -------
        tuple[numpy.ndarray, dict[str, Any]]
            ``(image, frame_info_dict)``
        """
        if not self._is_open:
            raise CameraNotOpenError("Camera is not open")
        if not self._is_grabbing:
            raise GrabbingNotStartedError("Call start_grabbing() before get_frame_ex()")

        self._ensure_frame_buffer()

        frame_info = MV_FRAME_OUT_INFO_EX()
        ret = self._sdk.MV_CC_GetOneFrameTimeout(
            self._handle,
            self._frame_buffer,
            self._frame_buffer_size,
            ctypes.byref(frame_info),
            timeout_ms,
        )
        if ret == MvErrorCode.MV_E_GC_TIMEOUT:
            raise FrameTimeoutError(f"No frame received within {timeout_ms} ms")
        _check(ret, "MV_CC_GetOneFrameTimeout")

        image = self._decode_frame(self._frame_buffer, frame_info, output_format)
        meta = _frame_info_to_dict(frame_info)
        return image, meta

    # ------------------------------------------------------------------
    # Internal callback
    # ------------------------------------------------------------------

    def _internal_callback(
        self,
        p_data: POINTER(c_ubyte),
        p_frame_info: POINTER(MV_FRAME_OUT_INFO_EX),
        p_user: c_void_p,
    ) -> None:
        """
        SDK-level callback trampoline.

        Called from an internal SDK thread.  Decodes the image and
        forwards it to the user-supplied callback.
        """
        if self._user_callback is None:
            return
        try:
            frame_info = p_frame_info.contents
            frame_len = frame_info.nFrameLen
            w = frame_info.nWidth
            h = frame_info.nHeight
            pf = frame_info.enPixelType

            # Copy the buffer so it is safe to use after the callback returns
            buf = np.ctypeslib.as_array(p_data, shape=(frame_len,)).copy()
            image = raw_to_numpy(buf, w, h, pf, self._output_format_for_callback)
            meta = _frame_info_to_dict(frame_info)
            self._user_callback(image, meta)
        except Exception:  # noqa: BLE001
            logger.exception("Exception in image callback")

    # ------------------------------------------------------------------
    # Parameter access
    # ------------------------------------------------------------------

    def get_int_parameter(self, name: str) -> int:
        """
        Get an integer camera parameter by name.

        Parameters
        ----------
        name:
            GenICam parameter name (e.g. ``"Width"``, ``"Height"``).

        Returns
        -------
        int

        Raises
        ------
        ParameterNotSupportedError
            When the parameter does not exist on this camera model.
        ParameterError
            When another SDK error occurs.
        """
        self._assert_open()
        val = MVCC_INTVALUE_EX()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetIntValueEx(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetIntValueEx({name!r})")
        return int(val.nCurValue)

    def set_int_parameter(self, name: str, value: int) -> None:
        """
        Set an integer camera parameter.

        Raises
        ------
        ParameterNotSupportedError
            When the parameter does not exist.
        ParameterReadOnlyError
            When the parameter is read-only.
        ParameterError
            On other SDK errors.
        """
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetIntValueEx(self._handle, name_bytes, int(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetIntValueEx({name!r})")

    def get_float_parameter(self, name: str) -> float:
        """Get a float camera parameter by name."""
        self._assert_open()
        val = MVCC_FLOATVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetFloatValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetFloatValue({name!r})")
        return float(val.fCurValue)

    def set_float_parameter(self, name: str, value: float) -> None:
        """Set a float camera parameter."""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetFloatValue(self._handle, name_bytes, float(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetFloatValue({name!r})")

    def get_bool_parameter(self, name: str) -> bool:
        """Get a boolean camera parameter."""
        self._assert_open()
        val = c_uint(0)
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetBoolValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetBoolValue({name!r})")
        return bool(val.value)

    def set_bool_parameter(self, name: str, value: bool) -> None:
        """Set a boolean camera parameter."""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetBoolValue(self._handle, name_bytes, int(bool(value)))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetBoolValue({name!r})")

    def get_enum_parameter(self, name: str) -> int:
        """Get an enum camera parameter (as raw integer value)."""
        self._assert_open()
        val = MVCC_ENUMVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetEnumValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetEnumValue({name!r})")
        return int(val.nCurValue)

    def set_enum_parameter(self, name: str, value: int) -> None:
        """Set an enum camera parameter by integer value."""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetEnumValue(self._handle, name_bytes, int(value))
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetEnumValue({name!r})")

    def set_enum_parameter_by_string(self, name: str, string_value: str) -> None:
        """Set an enum camera parameter by string (symbolic name)."""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        val_bytes = string_value.encode("utf-8")
        ret = self._sdk.MV_CC_SetEnumValueByString(self._handle, name_bytes, val_bytes)
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetEnumValueByString({name!r}={string_value!r})")

    def get_string_parameter(self, name: str) -> str:
        """Get a string camera parameter."""
        self._assert_open()
        val = MVCC_STRINGVALUE()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_GetStringValue(self._handle, name_bytes, ctypes.byref(val))
        _check(ret, f"MV_CC_GetStringValue({name!r})")
        return val.chCurValue.decode("utf-8", errors="replace").strip("\x00")

    def set_string_parameter(self, name: str, value: str) -> None:
        """Set a string camera parameter."""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        val_bytes = value.encode("utf-8")
        ret = self._sdk.MV_CC_SetStringValue(self._handle, name_bytes, val_bytes)
        if ret & 0xFFFFFFFF == MvErrorCode.MV_E_GC_ACCESS:
            raise ParameterReadOnlyError(
                f"Parameter {name!r} is read-only",
                MvErrorCode.MV_E_GC_ACCESS,
            )
        _check(ret, f"MV_CC_SetStringValue({name!r})")

    def execute_command(self, name: str) -> None:
        """Execute a GenICam command node (e.g. ``"TriggerSoftware"``)."""
        self._assert_open()
        name_bytes = name.encode("utf-8")
        ret = self._sdk.MV_CC_SetCommandValue(self._handle, name_bytes)
        _check(ret, f"MV_CC_SetCommandValue({name!r})")

    def set_parameter(self, name: str, value: int | float | bool | str) -> None:
        """
        Set a camera parameter with automatic type dispatch.

        Dispatches by Python type: bool → integer → float → string.
        Silently absorbs :py:exc:`ParameterNotSupportedError` when the
        parameter is absent on this camera model (logs a debug message).

        Parameters
        ----------
        name:
            GenICam node name.
        value:
            New value.  The method will pick the most appropriate SDK call
            based on the Python type.

        Raises
        ------
        ParameterReadOnlyError
            When the parameter is read-only.
        ParameterError
            When the underlying SDK call fails for an unrelated reason.
        """
        try:
            if isinstance(value, bool):
                self.set_bool_parameter(name, value)
            elif isinstance(value, int):
                self.set_int_parameter(name, value)
            elif isinstance(value, float):
                self.set_float_parameter(name, value)
            else:
                self.set_string_parameter(name, str(value))
        except ParameterNotSupportedError:
            logger.debug("Parameter %r not supported on this camera; skipping", name)

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """
        Get a camera parameter with automatic type dispatch.

        Tries integer → float → string in order.  Returns *default* when
        the parameter is absent on this camera model.

        Parameters
        ----------
        name:
            GenICam node name.
        default:
            Value returned when the parameter is not supported.
        """
        for getter in (
            self.get_int_parameter,
            self.get_float_parameter,
            self.get_string_parameter,
        ):
            try:
                return getter(name)
            except ParameterNotSupportedError:
                continue
            except ParameterError:
                continue
        return default

    # ------------------------------------------------------------------
    # SDK pixel conversion
    # ------------------------------------------------------------------

    def sdk_convert_pixel(
        self,
        src_data: bytes | np.ndarray,
        width: int,
        height: int,
        src_format: int,
        dst_format: int,
    ) -> np.ndarray:
        """
        Convert a raw frame buffer using the SDK's ``MV_CC_ConvertPixelType``.

        This is faster than the pure-Python conversion in
        :py:mod:`hikcamera.utils` for large, high-bit-depth images.

        Parameters
        ----------
        src_data:
            Raw source pixel data.
        width, height:
            Frame dimensions in pixels.
        src_format:
            Source pixel format (a :py:class:`~hikcamera.enums.PixelFormat`).
        dst_format:
            Destination pixel format.

        Returns
        -------
        numpy.ndarray
            Converted image data as a 1-D ``uint8`` array (caller is
            responsible for reshaping).

        Raises
        ------
        CameraNotOpenError
            When the camera is not open.
        ImageConversionError
            When the SDK conversion fails.
        """
        self._assert_open()
        if isinstance(src_data, np.ndarray):
            src_bytes = src_data.tobytes()
        else:
            src_bytes = bytes(src_data)

        # Estimate destination buffer size (worst case: 4 bytes/pixel)
        dst_size = width * height * 4
        dst_buf = (c_ubyte * dst_size)()

        src_buf = (c_ubyte * len(src_bytes)).from_buffer_copy(src_bytes)

        params = MV_PIXEL_CONVERT_PARAM()
        params.nWidth = width
        params.nHeight = height
        params.enSrcPixelType = src_format
        params.pSrcData = src_buf
        params.nSrcDataLen = len(src_bytes)
        params.enDstPixelType = dst_format
        params.pDstBuffer = dst_buf
        params.nDstBufferSize = dst_size

        ret = self._sdk.MV_CC_ConvertPixelType(self._handle, ctypes.byref(params))
        if ret != MvErrorCode.MV_OK:
            code = ret & 0xFFFFFFFF
            raise ImageConversionError(
                f"MV_CC_ConvertPixelType failed: 0x{code:08X}", code
            )

        return np.ctypeslib.as_array(dst_buf, shape=(params.nDstLen,)).copy()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assert_open(self) -> None:
        if not self._is_open:
            raise CameraNotOpenError("Camera is not open")

    def _ensure_frame_buffer(self) -> None:
        """Allocate (or reallocate) the frame buffer based on PayloadSize."""
        try:
            payload_size = self.get_int_parameter("PayloadSize")
        except ParameterError:
            payload_size = 0

        # Use a reasonable fallback if PayloadSize is unavailable
        if payload_size <= 0:
            payload_size = 10 * 1024 * 1024  # 10 MiB

        if self._frame_buffer is None or self._frame_buffer_size < payload_size:
            self._frame_buffer = (c_ubyte * payload_size)()
            self._frame_buffer_size = payload_size

    def _decode_frame(
        self,
        data: ctypes.Array[c_ubyte],
        frame_info: MV_FRAME_OUT_INFO_EX,
        output_format: OutputFormat,
    ) -> np.ndarray:
        """Decode a frame buffer to a numpy array."""
        w = frame_info.nWidth
        h = frame_info.nHeight
        pf = frame_info.enPixelType
        buf = np.ctypeslib.as_array(data, shape=(frame_info.nFrameLen,))
        return raw_to_numpy(buf, w, h, pf, output_format)


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def enumerate_cameras(
    transport_layers: TransportLayer = TransportLayer.ALL,
) -> list[DeviceInfo]:
    """
    Enumerate all accessible cameras.

    This is a module-level shortcut for :py:meth:`HikCamera.enumerate`.

    Parameters
    ----------
    transport_layers:
        Transport layers to scan.

    Returns
    -------
    list[DeviceInfo]
    """
    return HikCamera.enumerate(transport_layers)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _frame_info_to_dict(frame_info: MV_FRAME_OUT_INFO_EX) -> dict[str, Any]:
    """Convert an ``MV_FRAME_OUT_INFO_EX`` struct to a plain Python dict."""
    ts_high = frame_info.nDevTimeStampHigh
    ts_low = frame_info.nDevTimeStampLow
    timestamp_ns = (ts_high << 32 | ts_low)
    return {
        "frame_num": frame_info.nFrameNum,
        "width": frame_info.nWidth,
        "height": frame_info.nHeight,
        "pixel_format": frame_info.enPixelType,
        "frame_length": frame_info.nFrameLen,
        "timestamp_ns": timestamp_ns,
        "host_timestamp_ns": frame_info.nHostTimeStamp,
        "lost_packets": frame_info.nLostPacket,
        "gain": frame_info.fGain,
        "exposure_time": frame_info.fExposureTime,
        "average_brightness": frame_info.nAverageBrightness,
        "red": frame_info.nRed,
        "green": frame_info.nGreen,
        "blue": frame_info.nBlue,
        "frame_counter": frame_info.nFrameCounter,
        "trigger_index": frame_info.nTriggerIndex,
    }
