# Structured Parameter API Notes

## Current public direction

The public parameter workflow is now centered on the structured proxy API:

- `cam.params.AcquisitionControl.ExposureTime.set(5000.0)`
- `cam.params.AcquisitionControl.ExposureTime.get()`
- `cam.params.AnalogControl.GainAuto.set(enums.GainAuto.OFF)`
- `cam.params.AcquisitionControl.TriggerSoftware.execute()`

Enum values should be imported from `hikcamera.enums` (for example
`enums.GainAuto.OFF` and `enums.UserSetSelector.USER_SET_1`) so editors can
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
