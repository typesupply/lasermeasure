# Laser Measure

- turn caps lock on to activate
- hold command to enter segment mode
- hold command + option to enter handle mode
- in regular mode:
    - hold control to ignore components
    - hold option to use glyph.bounds
      instead of metrics for edge measurements

## To Do
- are the key commands for segment/handle
  measurement too cumbersome in practice?
- need smarter fallbacks when mousing
  outside of the standard glyph rect
- option for measuring between the closest
  on curve points. this will be tricky
  if the points are not 90° from each other.
  but this will be useful in italics.
- prefs:
  - color