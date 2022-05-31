import math
import random
from fontTools.misc import bezierTools as ftBezierTools
from fontTools.ufoLib.glifLib import readGlyphFromString
import defcon
from fontParts.world import RGlyph
import drawBot as bot
from lib.tools import bezierTools
from mojo.tools import IntersectGlyphWithLine

def roundPoint(pt):
    x, y = pt
    x = round(x)
    y = round(y)
    return (x, y)

def findPerpendicularDistanceForPoint(glyph, location, scale=1):
    radius = 10 / scale
    # Is the location close to a segment?
    selector = glyph.getRepresentation("doodle.GlyphSelection")
    found = selector.segmentStrokeHitByPoint_(
        defcon.Point(location),
        radius
    )
    if not found:
        return
    # Convert the fontParts segment into a complete sequence of points.
    contourIndex, segmentIndex, nsSegment = found
    contour = glyph[contourIndex]
    prevSegmentIndex = segmentIndex - 1
    if prevSegmentIndex < 0:
        prevSegmentIndex = len(contour.segments) - 1
    prevSegment = contour.segments[prevSegmentIndex]
    segment = contour.segments[segmentIndex]
    segmentType = segment.type
    segmentPoints = [
        (prevSegment.onCurve.x, prevSegment.onCurve.y)
    ] + [(p.x, p.y) for p in segment.points]
    # Create a point that hits the segment near the location.
    intersection = None
    if segmentType == "line":
        intersection = bezierTools.intersectCircleLine(
            location,
            radius,
            segmentPoints[0],
            segmentPoints[1]
        )
    elif segmentType == "curve":
        intersection = bezierTools.intersectCubicCircle(
            segmentPoints[0],
            segmentPoints[1],
            segmentPoints[2],
            segmentPoints[3],
            location,
            radius
        )
    elif segmentType == "qcurve":
        # XXX
        # this will require conversion to
        # cubic and I don't want to deal
        # with that right now so...
        # but, it's possible.
        return
    else:
        return
    if intersection is None or not intersection.points:
        return
    # XXX
    # There is an edge case here that I don't have the
    # brain power to sort out right now: if the circle
    # used for the intersection test above extends past
    # the start or end point, the only t will be the
    # part of the circle that does intersect. this will
    # throw off the calculation. This needs to be fixed.
    #
    # test segment: [(437, 252), (437, 64)]
    # location: (440, 71)
    # radius: 10
    # function: bezierTools.intersectCircleLine
    # XXX
    t = sum(intersection.t) / len(intersection.t)
    if segmentType == "line":
        angleAnchor1 = segmentPoints[0]
        angleAnchor2 = segmentPoints[1]
        hit = ftBezierTools.linePointAtT(
            segmentPoints[0],
            segmentPoints[1],
            t
        )
    elif segmentType == "curve":
        splitSegment1, splitSegment2 = ftBezierTools.splitCubicAtT(
            segmentPoints[0],
            segmentPoints[1],
            segmentPoints[2],
            segmentPoints[3],
            t
        )
        hit = splitSegment1[-1]
        angleAnchor1 = splitSegment1[-2]
        angleAnchor2 = splitSegment2[1]
    else:
        # XXX see note about qcurve above
        pass
    # Calculate the angle of the segment at the new point.
    angle = bezierTools.calculateAngle(angleAnchor1, angleAnchor2)
    # Calculate the perpendicular angle.
    if contour.pointInside(location):
        if contour.clockwise:
            delta = -90
        else:
            delta = 90
    else:
        if contour.clockwise:
            delta = 90
        else:
            delta = -90
    perpendicular = angle + delta
    # Create a line from the new point along the perpendicular angle.
    d = 1000
    a = math.radians(perpendicular)
    rayX = hit[0] + math.cos(a) * d
    rayY = hit[1] + math.sin(a) * d
    # Find the intersections between the glyph and the line.
    intersections = IntersectGlyphWithLine(
        glyph,
        (hit, (rayX, rayY)),
        canHaveComponent=False,
        addSideBearings=False
    )
    # Find the intersection nearest the original location.
    intersection = None
    if intersections:
        sorter = []
        for i in intersections:
            if roundPoint(i) == roundPoint(hit):
                continue
            distance = bezierTools.distanceFromPointToPoint(hit, i)
            sorter.append((distance, i))
        if sorter:
            sorter.sort()
            intersection = sorter[0][-1]
    if intersection is None:
        return
    # Return the point and the intersection.
    return (hit, intersection)


# ----
# Test
# ----

glif = """
<?xml version='1.0' encoding='UTF-8'?>
<glyph name="A" format="2">
  <advance width="500"/>
  <outline>
    <contour>
      <point x="250" y="0" type="curve" smooth="yes"/>
      <point x="500" y="0" type="line"/>
      <point x="500" y="375" type="line"/>
      <point x="375" y="500" type="line"/>
      <point x="250" y="500" type="line" smooth="yes"/>
      <point x="112" y="500"/>
      <point x="0" y="388"/>
      <point x="0" y="250" type="curve" smooth="yes"/>
      <point x="0" y="112"/>
      <point x="112" y="0"/>
    </contour>
    <contour>
      <point x="437" y="252" type="curve" smooth="yes"/>
      <point x="437" y="64" type="line"/>
      <point x="250" y="64" type="line"/>
      <point x="67" y="252" type="line"/>
      <point x="67" y="355"/>
      <point x="148" y="436"/>
      <point x="252" y="436" type="curve" smooth="yes"/>
      <point x="355" y="436"/>
      <point x="437" y="355"/>
    </contour>
  </outline>
</glyph>
""".strip()

glyph = RGlyph()
readGlyphFromString(glif, glyph, glyph.getPointPen())

padding = 50
w, h = glyph.bounds[2:]
w += padding * 2
h += padding * 2
bot.size(w, h)
bot.translate(padding, padding)
bot.fill(0, 0, 0, 0.05)
bot.stroke(0, 0, 0, 0.5)
bot.strokeWidth(1)
bot.drawGlyph(glyph)

xMin, yMin, xMax, yMax = glyph.bounds
xMin -= padding / 2
yMin -= padding / 2
xMax += padding / 2
yMax += padding / 2

counter = 0
while counter < 50:
    x = random.randint(xMin, xMax)
    y = random.randint(yMin, yMax)
    hit = findPerpendicularDistanceForPoint(glyph, (x, y))
    if not hit:
        continue
    r = random.random()
    g = random.random()
    b = random.random()
    bot.fill(None)
    bot.stroke(r, g, b, 1)
    bot.strokeWidth(1)
    bot.line(hit[0], hit[1])
    bot.stroke(None)
    bot.fill(r, g, b, 1)
    bot.oval(x-2, y-2, 4, 4)
    counter += 1