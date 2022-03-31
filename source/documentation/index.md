# Laser Measure

Press `d` and move the cursor to activate.

- To get the width and height of a segment: hover over the segment.
  Other segments with the same width and height will be highlighted.
- To get the width and height of a handle: hover over a handle.
  Other handles with the same width and height will be highlighted.
- To get the width and height between two points, hover between the
  two points. (Only points with angles of +/- 20° from right angles
  will be shown.)
- To get the width and height between the nearest outline lines,
  hover between the lines you want to measure.
- To get the distance between the exterior of glyph's outline
  and the closest horizontal and vertical metrics, hover between
  the outline and the metrics you want to measure.
- To get the distance between the exterior of glyph's outline
  and glyph's bounding box, hold option and hover outside of
  glyph's outline.

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

```python
from mojo.extensions import setExtensionDefault

setExtensionDefault(
    "com.typesupply.LaserMeasure.triggerCharacter",
    "m"
)
setExtensionDefault(
    "com.typesupply.LaserMeasure.baseColor",
    (1, 0, 1, 0.5)
)
```

# To Do

- annoying edge case where a segment is not hit with the
  segment test but is hit with the point to point test.
  maybe pre-disqualify (point1, point2)?
- optimize findAdjacentValues
- should the value used in `selector.segmentStrokeHitByPoint_`
  vary with the zoom level?
- use italic angle for vertical ray?