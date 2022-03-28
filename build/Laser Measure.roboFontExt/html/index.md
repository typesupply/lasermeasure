# Laser Measure

Press `m` to activate. Hover over a handle or segment to get the length and width. Hover between two points to get the length and width between them. Hover anywhere else to get a length and width measurement of the nearest outlines or left/right and top/bottom metrics. Hold option to measure the edge of the glyph's bounds instead of the metrics.

## To Do
- in collinear mode, prefer hits that are closer to 90 and 0
- move highlights and strokes to background layer
- highlight segments/handles with the same values
- is ignore components necessary?
- go back to caps lock
- need smarter fallbacks when mousing
  outside of the standard glyph rect
- should the value used in `selector.segmentStrokeHitByPoint_`
  vary with the zoom level?
- anchor to outline measurements using the collinear snap
- use italic angle for vertical ray?
- prefs:
  - color