"""
Enumerations used by the HiKCamera library.

These values mirror the constants defined in the Hikvision MVS SDK headers
(MvCameraControl.h and MvErrorDefine.h).  Using Python enumerations gives
callers type-safe, readable access to the underlying integer constants.
"""

from __future__ import annotations

from enum import IntEnum, IntFlag

# ---------------------------------------------------------------------------
# SDK error codes (subset)
# ---------------------------------------------------------------------------

class MvErrorCode(IntEnum):
    """Common Hikvision SDK error codes."""

    # Generic
    MV_OK = 0x00000000
    MV_E_HANDLE = 0x80000000         # Invalid handle or handle type mismatch
    MV_E_SUPPORT = 0x80000001         # Not supported
    MV_E_BUFOVER = 0x80000002         # Buffer overflow
    MV_E_CALLORDER = 0x80000003       # Function calling order error
    MV_E_PARAMETER = 0x80000004       # Incorrect parameter
    MV_E_RESOURCE = 0x80000006        # Apply resource failed
    MV_E_NODATA = 0x80000007          # No data
    MV_E_PRECONDITION = 0x80000008    # Precondition error or running environment changed
    MV_E_VERSION = 0x80000009         # Version mismatch
    MV_E_NOENOUGH_BUF = 0x8000000A   # Insufficient memory
    MV_E_ABNORMAL_IMAGE = 0x8000000B  # Abnormal image, e.g. overexposure or underexposure
    MV_E_LOAD_LIBRARY = 0x8000000C   # Load dynamic library failed
    MV_E_NOOUTBUF = 0x8000000D        # No output buffer
    MV_E_ENCRYPT = 0x8000000E         # Encryption error
    MV_E_OPENFILE = 0x8000000F        # Open file error
    MV_E_FILE = 0x80000010            # File error
    MV_E_DYNAMICLIB = 0x80000011      # Dynamic library related error

    # GenICam
    MV_E_GC_GENERIC = 0x80000100      # Generic error
    MV_E_GC_ARGUMENT = 0x80000101     # Invalid argument
    MV_E_GC_RANGE = 0x80000102        # Out of range
    MV_E_GC_PROPERTY = 0x80000103     # Property error
    MV_E_GC_RUNTIME = 0x80000104      # Runtime error
    MV_E_GC_LOGICAL = 0x80000105      # Logical error
    MV_E_GC_ACCESS = 0x80000106       # Access denied (e.g. write to read-only)
    MV_E_GC_TIMEOUT = 0x80000107      # Timeout
    MV_E_GC_DYNAMICCAST = 0x80000108  # Bad dynamic cast
    MV_E_GC_UNKNOWNTYPE = 0x8000010D  # Unknown type in GenICam
    MV_E_GC_INVALIDADDR = 0x8000010E  # Invalid address

    # GigE-specific
    MV_E_NOTIMP = 0x80000200          # Not implemented (feature absent on device)
    MV_E_UNKNOW = 0x800000FF          # Unknown error


# ---------------------------------------------------------------------------
# Camera access modes
# ---------------------------------------------------------------------------

class AccessMode(IntEnum):
    """
    Camera access mode passed to :py:meth:`HikCamera.open`.

    These values correspond to ``MV_ACCESS_MODE`` in the SDK.
    """

    EXCLUSIVE = 1
    """Exclusive access – only one application can connect."""

    EXCLUSIVE_WITH_SWITCH = 2
    """
    Exclusive access with takeover permission.  Another exclusive owner can
    take control by re-opening with this mode.
    """

    CONTROL = 3
    """
    Control access – one application controls the camera; others may observe.
    """

    CONTROL_WITH_SWITCH = 4
    """
    Control access with takeover permission.
    """

    CONTROL_SLAVE = 5
    """
    Slave/observer access alongside a control owner.
    """

    MONITOR = 6
    """
    Read-only monitor access.  Cannot change camera parameters.
    """

    OPEN = 7
    """
    Open access – minimal, used mainly to read device information.
    """


# ---------------------------------------------------------------------------
# Transport layer / device interface type
# ---------------------------------------------------------------------------

class TransportLayer(IntFlag):
    """
    Bit-mask that selects which transport layers to scan when enumerating.

    These values correspond to ``MV_TRANSTYPE_*`` defines in the SDK.
    """

    GIGE = 0x00000001      # GigE Vision (GEV)
    USB = 0x00000004       # USB3 Vision (U3V)
    CAMERALINK = 0x00000008  # CameraLink (via frame grabber)
    ALL = GIGE | USB | CAMERALINK
    """Scan all supported transport layers."""


# ---------------------------------------------------------------------------
# Multicast / unicast connection hints
# ---------------------------------------------------------------------------

class StreamingMode(IntEnum):
    """Unicast vs. multicast streaming hint used when opening a GigE camera."""

    UNICAST = 0
    """Standard unicast streaming (one receiver)."""

    MULTICAST = 1
    """Multicast streaming (multiple receivers share the same stream)."""


# ---------------------------------------------------------------------------
# Pixel format constants
# ---------------------------------------------------------------------------

class PixelFormat(IntEnum):
    """
    Common Hikvision / PFNC pixel format codes.

    These are the values returned by the ``PixelFormat`` camera parameter.
    """

    # Monochrome
    MONO8 = 0x01080001
    MONO10 = 0x01100003
    MONO10_PACKED = 0x010C0004
    MONO12 = 0x01100005
    MONO12_PACKED = 0x010C0006
    MONO14 = 0x01100025
    MONO16 = 0x01100007

    # Bayer
    BAYER_GR8 = 0x01080008
    BAYER_RG8 = 0x01080009
    BAYER_GB8 = 0x0108000A
    BAYER_BG8 = 0x0108000B
    BAYER_GR10 = 0x0110000C
    BAYER_RG10 = 0x0110000D
    BAYER_GB10 = 0x0110000E
    BAYER_BG10 = 0x0110000F
    BAYER_GR12 = 0x01100010
    BAYER_RG12 = 0x01100011
    BAYER_GB12 = 0x01100012
    BAYER_BG12 = 0x01100013
    BAYER_GR10_PACKED = 0x010C0026
    BAYER_RG10_PACKED = 0x010C0027
    BAYER_GB10_PACKED = 0x010C0028
    BAYER_BG10_PACKED = 0x010C0029
    BAYER_GR12_PACKED = 0x010C002A
    BAYER_RG12_PACKED = 0x010C002B
    BAYER_GB12_PACKED = 0x010C002C
    BAYER_BG12_PACKED = 0x010C002D

    # RGB / BGR
    RGB8_PACKED = 0x02180014
    BGR8_PACKED = 0x02180015
    RGBA8_PACKED = 0x02200016
    BGRA8_PACKED = 0x02200017

    # YUV / YCbCr
    YUV411_PACKED = 0x020C001E
    YUV422_PACKED = 0x0210001F
    YUV444_PACKED = 0x02180020
    YCBCR422_8 = 0x0210003B


# ---------------------------------------------------------------------------
# Image output format (what numpy array shape/dtype to produce)
# ---------------------------------------------------------------------------

class OutputFormat(IntEnum):
    """
    Requested output format for the numpy array returned by frame-capture calls.

    The SDK always decodes into the intermediate ``convert_pixel_type`` first,
    then HiKCamera reshapes the buffer into the right numpy dtype/shape.
    """

    MONO8 = 0
    """Grayscale 8-bit  →  shape (H, W),  dtype uint8"""

    MONO16 = 1
    """Grayscale 16-bit  →  shape (H, W),  dtype uint16"""

    BGR8 = 2
    """BGR 24-bit  →  shape (H, W, 3),  dtype uint8  (OpenCV-native)"""

    RGB8 = 3
    """RGB 24-bit  →  shape (H, W, 3),  dtype uint8"""

    BGRA8 = 4
    """BGRA 32-bit  →  shape (H, W, 4),  dtype uint8"""

    RGBA8 = 5
    """RGBA 32-bit  →  shape (H, W, 4),  dtype uint8"""
