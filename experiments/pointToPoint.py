import pprint
import math
from fontTools.ufoLib.glifLib import readGlyphFromString
from fontTools.pens.pointPen import AbstractPointPen
from fontParts.world import RGlyph
from lib.tools import bezierTools
from mojo import tools
from drawBot.drawBotDrawingTools import _drawBotDrawingTool as bot

# ----------------------
# Code for subscriber.py
# ----------------------

class NearestPointsPointPen(AbstractPointPen):

    def __init__(self):
        self.onCurvePoints = []
        self.contourOnCurveCounts = {}
        self._currentContour = 0
        self._pointIndex = 0

    def beginPath(self, **kwargs):
        pass

    def endPath(self, **kwargs):
        self.contourOnCurveCounts[self._currentContour] = self._pointIndex
        self._currentContour += 1
        self._pointIndex = 0

    def addComponent(self, *args, **kwargs):
        pass

    def addPoint(self, pt, segmentType=None, **kwargs):
        if segmentType is not None:
            self.onCurvePoints.append((self._currentContour, self._pointIndex, pt))
            self._pointIndex += 1

    def find(self, glyph, location):
        collinearityTolerance = 0.2
        rightAngleTolerance = 20
        # calculate angle and distance from
        # location to all points.
        points = []
        for contourIndex, pointIndex, point in self.onCurvePoints:
            angle = bezierTools.calculateAngle(*sorted((location, point)))
            angle = normalizeAngle(angle)
            # eliminate wonky angles now
            if getRightAngleVariance(angle, rightAngleTolerance) is None:
                continue
            distance = bezierTools.distanceFromPointToPoint(point, location)
            points.append((angle, distance, contourIndex, pointIndex, point))
        if len(points) < 2:
            return
        # test all combinations and filter combinations
        # that don't meet various criteria. the filters
        # should be organized from least to most expensive.
        tested = set()
        candidates = []
        for angle1, distance1, contourIndex1, pointIndex1, point1 in points:
            contour1Count = self.contourOnCurveCounts[contourIndex1]
            for angle2, distance2, contourIndex2, pointIndex2, point2 in points:
                if point1 == point2:
                    continue
                # already tested
                k = tuple(sorted((point1, point2)))
                if k in tested:
                    continue
                # if point1 and point2 are on the same
                # contour and they are next to each
                # other sequentially, skip.
                if contourIndex1 == contourIndex2:
                    if abs(pointIndex1 - pointIndex2) == 1:
                        continue
                    if {pointIndex1, pointIndex2} == {0, contour1Count - 1}:
                        continue
                # if the location is not roughly in the middle
                # of point1 and point2, skip.
                totalEstimatedDistance = distance1 + distance2
                t = distance1 / totalEstimatedDistance
                if t < 0.35 or t > 0.65:
                    continue
                # if point1 - location - point2 are not
                # relatively collinear, skip.
                x1, y1 = point1
                x2, y2 = location
                x3, y3 = point2
                dx1 = x2 - x1
                dy1 = y2 - y1
                dx2 = x3 - x2
                dy2 = y3 - y2
                a1 = math.atan2(dx1, dy1)
                a2 = math.atan2(dx2, dy2)
                collinearity = abs(a1 - a2)
                if collinearity > collinearityTolerance:
                    continue
                # if the line between point1 and point2
                # is not close to a right angle, skip.
                angle = bezierTools.calculateAngle(point1, point2)
                angle = normalizeAngle(angle)
                angleVariation = getRightAngleVariance(angle, rightAngleTolerance)
                if angleVariation is None:
                    continue
                angleVariation = round(angleVariation, -1)
                # if the line between point1 and point2
                # intersects a line in the glyph, skip.
                line = ((x1, y1), (x3, y3))
                intersections = tools.IntersectGlyphWithLine(
                    glyph,
                    line,
                    canHaveComponent=False,
                    addSideBearings=False
                )
                for point in line:
                    if point in intersections:
                        intersections.remove(point)
                if intersections:
                    continue
                # store
                distance = bezierTools.distanceFromPointToPoint(point1, point2)
                candidates.append((angleVariation, distance, (point1, point2)))
        if not candidates:
            return
        candidates.sort()
        return candidates[0][-1]


def normalizeAngle(angle):
    if angle < 0:
        angle = 360 + angle
    return angle

def getRightAngleVariance(angle, tolerance):
    angleVariation = None
    if angle <= tolerance:
        angleVariation = angle
    elif angle >= (90 - tolerance) and angle <= (90 + tolerance):
        angleVariation = abs(90 - angle)
    elif angle >= (180 - tolerance) and angle <= (180 + tolerance):
        angleVariation = abs(180 - angle)
    elif angle >= (270 - tolerance) and angle <= (270 + tolerance):
        angleVariation = abs(270 - angle)
    elif angle >= (360 - tolerance):
        angleVariation = 360 - angle
    return angleVariation

# -----
# Tests
# -----

glif1 = """
<?xml version='1.0' encoding='UTF-8'?>
<glyph name="test1" format="2">
  <advance width="290"/>
  <outline>
    <contour>
      <point x="100.0" y="0.0" type="line"/>
      <point x="190.0" y="0.0" type="line"/>
      <point x="190.0" y="750.0" type="line"/>
      <point x="100.0" y="750.0" type="line"/>
    </contour>
  </outline>
</glyph>
""".strip()

glif2 = """
<?xml version='1.0' encoding='UTF-8'?>
<glyph name="test2" format="2">
  <advance width="350"/>
  <outline>
    <contour>
      <point x="130" y="665" type="line"/>
      <point x="130" y="85" type="line"/>
      <point x="100" y="0" type="line"/>
      <point x="250" y="0" type="line"/>
      <point x="220" y="85" type="line"/>
      <point x="220" y="665" type="line"/>
      <point x="250" y="750" type="line"/>
      <point x="100" y="750" type="line"/>
    </contour>
  </outline>
</glyph>
""".strip()

glif3 = """
<?xml version='1.0' encoding='UTF-8'?>
<glyph name="C" format="2">
  <advance width="970"/>
  <unicode hex="0043"/>
  <outline>
    <contour>
      <point x="485" y="-10" type="curve" smooth="yes"/>
      <point x="697" y="-10"/>
      <point x="870" y="163"/>
      <point x="870" y="375" type="curve" smooth="yes"/>
      <point x="870" y="587"/>
      <point x="697" y="760"/>
      <point x="485" y="760" type="curve" smooth="yes"/>
      <point x="273" y="760"/>
      <point x="100" y="587"/>
      <point x="100" y="375" type="curve" smooth="yes"/>
      <point x="100" y="163"/>
      <point x="273" y="-10"/>
    </contour>
    <contour>
      <point x="545" y="183" type="curve"/>
      <point x="435" y="183"/>
      <point x="293" y="325"/>
      <point x="293" y="435" type="curve" smooth="yes"/>
      <point x="293" y="515"/>
      <point x="345" y="567"/>
      <point x="425" y="567" type="curve"/>
      <point x="535" y="567"/>
      <point x="677" y="425"/>
      <point x="677" y="315" type="curve" smooth="yes"/>
      <point x="677" y="235"/>
      <point x="625" y="183"/>
    </contour>
  </outline>
</glyph>
""".strip()


def testGlyph(glif):
    glyph = RGlyph()
    readGlyphFromString(glif, glyph, pointPen=glyph.getPointPen())
    pen = NearestPointsPointPen()
    glyph.drawPoints(pen)

    dotSize = 10
    buffer = 100
    step = 5
    width = buffer + glyph.width + buffer
    height = buffer + glyph.bounds[-1] + buffer
    xSteps = int(width / step) + 1
    ySteps = int(height / 5) + 1
    xStart = -buffer
    yStart = -buffer
    print(f"testing {xSteps * ySteps} locations...")

    hits = {}
    for xi in range(xSteps):
        x = xStart + (xi * step)
        for yi in range(ySteps):
            y = yStart + (yi * step)
            hit = pen.find(glyph, (x, y))
            if hit is not None:
                if hit not in hits:
                    hits[hit] = []
                hits[hit].append((x, y))

    for (point1, point2), locations in hits.items():
        bot.newPage(width=width, height=height)
        bot.translate(buffer, buffer)
        bot.fill(None)
        bot.stroke(0, 0, 0, 1)
        bot.strokeWidth(1)
        bot.drawGlyph(glyph)
        # point - location - point
        bot.stroke(1, 1, 0, 0.25)
        for location in locations:
            bot.line(point1, location)
            bot.line(location, point2)
        # point, point
        bot.stroke(None)
        bot.fill(1, 0, 0, 0.75)
        x1, y1 = point1
        x2, y2 = point2
        offset = dotSize / 2
        bot.oval(x1-offset, y1-offset, dotSize, dotSize)
        bot.oval(x2-offset, y2-offset, dotSize, dotSize)
        # locations
        bot.fill(0, 0, 1, 0.05)
        for location in locations:
            x, y = location
            bot.oval(x-offset, y-offset, dotSize, dotSize)



bot.newDrawing()
testGlyph(glif1)
testGlyph(glif2)
testGlyph(glif3)