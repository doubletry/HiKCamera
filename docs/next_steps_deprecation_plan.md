# Structured Parameter API Notes

## Current public direction

The public parameter workflow is now centered on the structured proxy API:

- `cam.params.AcquisitionControl.ExposureTime.set(5000.0)`
- `cam.params.AcquisitionControl.ExposureTime.get()`
- `cam.params.AnalogControl.GainAuto.set(Hik.GainAuto.OFF)`
- `cam.params.AcquisitionControl.TriggerSoftware.execute()`

Enum values should be imported through the library-scoped `Hik` namespace (for
example `Hik.GainAuto.OFF` and `Hik.UserSetSelector.USER_SET_1`) so editors can
provide enum member completion directly from the enum type.

## Follow-up work

1. Keep the structured proxy API and the parameter node tables synchronized with
   the SDK parameter documentation whenever new nodes are added.
2. Continue improving documentation examples so every parameter category example
   shows the full `cam.params.<Category>.<Node>` path explicitly.
3. Consider adding richer generated API documentation or type stubs in the
   future if stronger editor hints are needed for dynamically created proxy
   objects.
4. Keep `get_camera_info()` examples aligned with `ParamNode` key access.
5. **`HikCamera.sdk_convert_pixel`** remains public for backward compatibility
   but is now considered a low-level helper – the high-level
   `get_frame*` / callback path goes through the SDK pipeline automatically
   when `use_sdk_decode=True` (the default). It may be moved to an
   underscore-prefixed name in a future major release. New code should
   save / record the returned numpy frames with OpenCV, and only use the
   library helpers where SDK-side processing is still required
   (`encode_image`, `rotate_image`, `flip_image`).
