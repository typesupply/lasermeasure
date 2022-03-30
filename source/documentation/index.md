# Laser Measure

Press `m` to activate. Hover over a handle or segment to get the length and width. Hover between two points to get the length and width between them. Hover anywhere else to get a length and width measurement of the nearest outlines or left/right and top/bottom metrics. Hold option to measure the edge of the glyph's bounds instead of the metrics.

## Defaults

If you want to change a default, do it with code using these keys until a window is ready:

```
com.typesupply.LaserMeasure.triggerCharacter
com.typesupply.LaserMeasure.baseColor
com.typesupply.LaserMeasure.matchColor
com.typesupply.LaserMeasure.highlightStrokeWidth
com.typesupply.LaserMeasure.highlightStrokeAlpha
com.typesupply.LaserMeasure.measurementTextSize
```

## To Do

- try Frederik's close by line code
- in collinear mode, prefer hits that are closer to 90 and 0
- change cursor based on hit
- anchor to outline measurements using the collinear snap
- need smarter fallbacks when mousing outside of the standard glyph rect
- optimize findAdjacentValues
- is ignore components necessary?
- should the value used in `selector.segmentStrokeHitByPoint_` vary with the zoom level?
- use italic angle for vertical ray?