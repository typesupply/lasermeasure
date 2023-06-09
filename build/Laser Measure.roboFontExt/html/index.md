# Laser Measure

To get the measurements of the current selection. Press and hold trigger
character (`d` is the default). The width and height of the current
selection will be displayed in an outlined rectangle.

To dynamically measure items, press and hold `d` and move the cursor
to what you want to measure. The found width and height will be
displayed in a filled rectangle. These are the things that are
dynamically measured:

- **Segments** To get the width and height of a segment: hover over
  the segment. Other segments with the same width and height will
  be highlighted.
- **Off Curve Handles** To get the width and height of a handle:
  hover over a handle. Other handles with the same width and height
  will be highlighted.
- **Two On Curve Points** To get the width and height between two
  points, hover between the two points. (Only points with angles of
  +/- 20° from right angles will be shown.)
- **Outline Intersection** To get the width and height between the
  nearest outline lines, hover between the lines you want to measure.
- **Exterior of Outline and Metrics** To get the distance between the
  exterior of glyph's outline and the closest horizontal and vertical
  metrics, hover between the outline and the metrics you want to measure.
- **Exterior of Metrics and Outline Bounds** To get the distance between
  the exterior of glyph's outline and glyph's bounding box, hold option
  and hover outside of glyph's outline.
- **Anchor and Outline** To get the distance between an anchor and a
  glyph's outline, hover between the anchor and the outline.
- **Anchor and Metrics** To get the distance between an anchor and a
  glyph's metrics, hover between the anchor and the metrics.
- **Anchor and Outline Bounds** To get the distance between an anchor
  and a glyph's bounding box, hold option and hover between the anchor
  and the glyph's outline.

## Automatic Segment Matching

Segments that have the same structure and measurements will be highlighted
with a rotating set of colors.

## Named Values

Widths, heights or height and width combinations can be defined as
font-specific named values. During measuring, if any of these values
is matched, it will be displayed next to the measurement. These
values are defined in the "Named Values" sheet. If you define a width
and no height, any height will be matched. If you define a height and
no width, any width will be matched.

### Reference List

When the trigger character is pressed, a list of all named values
will be shown in the upper right corner of the glyph editor. If
you have points selected, a `+` button will appear. Pressing this
will open the named values sheet with a new entry based on the
current selection.

### Storage Format

Values are stored in `font.lib` under the key `com.typesupply.LaserMeasure.measurements`.
The data is stored as a dict of value names and dicts as values. The
value dict has `width` and/or `height` keys. If `width` is defined but
`height` is not any height will match. If `height` if defined but
`width` is not any width will match.

```python
key = "com.typesupply.LaserMeasure.measurements"

stored = font.lib.get(key, {})
stored["My Width"] = dict(width=100)
stored["My Height"] = dict(height=50)
stored["My Combination"] = dict(width=200, height=100)

font.lib[key] = stored

# to make the changes immediately available
# in open glyph editors, post this event:

from mojo import events

events.postEvent(
  extensionID + "com.typesupply.LaserMeasure.measurementsChanged",
  font=font
)
```

## Settings

If you want to change a settings, use the settings window. This window
if only available in RoboFont 4.2 and later. If you are using an earlier
version you'll need to do it with code using these keys until a window
is ready:

```
com.typesupply.LaserMeasure.triggerCharacter
com.typesupply.LaserMeasure.baseColor
com.typesupply.LaserMeasure.matchColors
com.typesupply.LaserMeasure.highlightStrokeWidth
com.typesupply.LaserMeasure.highlightOpacity
com.typesupply.LaserMeasure.measurementTextSize
com.typesupply.LaserMeasure.showMeasurementsHUD
com.typesupply.LaserMeasure.testSelection
com.typesupply.LaserMeasure.testSegments
com.typesupply.LaserMeasure.testSegmentMatches
com.typesupply.LaserMeasure.testOffCurves
com.typesupply.LaserMeasure.testOffCurveMatches
com.typesupply.LaserMeasure.testPoints
com.typesupply.LaserMeasure.testGeneral
com.typesupply.LaserMeasure.testAnchors
com.typesupply.LaserMeasure.autoTestSegmentMatches
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

## Scripting

Named values font.lib key: `com.typesupply.LaserMeasure.measurements`

Persistent measurement functions:

```
storePersistentPointMeasurementReferences
removePersistentPointMeasurementReferences
clearPersistentPointMeasurementReferences
getPersistentPointMeasurementReferences
getPersistentPointMeasurements
```