# Laser Measure

Press `m` to activate. Hover over a handle or segment to get the length and width. Hover between two points to get the length and width between them. Hover anywhere else to get a length and width measurement of the nearest outlines or left/right and top/bottom metrics. Hold option to measure the edge of the glyph's bounds instead of the metrics.

## To Do
- is ignore components necessary?
- is the key too far from the modifiers in practice?
- need smarter fallbacks when mousing
  outside of the standard glyph rect
- should the value used in `selector.segmentStrokeHitByPoint_`
  vary with the zoom level?
- anchor to outline measurements
- use italic angle for vertical ray?
- prefs:
  - color