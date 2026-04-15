# Next Steps Deprecation Plan

## Structured parameter API migration

The project now has a structured `ParamNode`-based parameter API. Future
documentation and examples should continue to prioritize:

- `cam.set_parameter(AcquisitionControl.ExposureTime, 5000.0)`
- `cam.get_parameter(AcquisitionControl.ExposureTime)`
- `info[ImageFormatControl.Width]` for values returned by `get_camera_info()`

## Legacy APIs planned for gradual deprecation

The following legacy interfaces are still supported for backward compatibility,
but should be documented as compatibility APIs and considered for gradual
deprecation in a future release:

- String-based parameter names in `set_parameter()` / `get_parameter()`
- Typed parameter helpers such as:
  - `get_int_parameter()` / `set_int_parameter()`
  - `get_float_parameter()` / `set_float_parameter()`
  - `get_bool_parameter()` / `set_bool_parameter()`
  - `get_enum_parameter()` / `set_enum_parameter()`
  - `get_string_parameter()` / `set_string_parameter()`
- String-key access on `get_camera_info()` results

## Recommended rollout

1. Keep all legacy interfaces working during the transition period.
2. Prefer `ParamNode` usage in all demos, docs, and new tests.
3. Add deprecation warnings only after the migration guidance is fully
   reflected in release notes and documentation.
4. Eventually switch examples and public recommendations entirely to the
   `ParamNode` path.
