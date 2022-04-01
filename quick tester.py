import math
from fontTools.pens.basePen import BasePen
from fontTools.pens.pointPen import AbstractPointPen
from mojo import tools
from lib.tools import bezierTools

def _formatCoordinateForSearching(x, y):
    x = int(round(x))
    y = int(round(y))
    return f"{x},{y}"

def normalizeAngle(angle):
    if angle < 0:
        angle = 360 + angle
    return angle

def roundTo(value, multiple):
    value = int(round(value / float(multiple))) * multiple
    return value

class NearestPointsPointPen(AbstractPointPen):

    def __init__(self):
        self.onCurvePoints = []
        self.offCurvePoints = []
        self.searchString = None

    def beginPath(self, **kwargs):
        pass

    def endPath(self, **kwargs):
        pass

    def addComponent(self, **kwargs):
        pass

    def addPoint(self, pt, segmentType=None, **kwargs):
        if segmentType is None:
            self.offCurvePoints.append(pt)
        else:
            self.onCurvePoints.append(pt)

    def find(self, glyph, location):
        # get the sequence of points for
        # eliminating point1-point2 sequences.
        if self.searchString is None:
            l = []
            for x, y in self.onCurvePoints:
                l.append(_formatCoordinateForSearching(x, y))
            if l:
                l.append(l[0])
            self.searchString = " ".join(l)
        angleRoundingIncrement = 10
        collinearityTolerance = 0.2
        rightAngleTolerance = 20
        # find nearest points for angles
        # rotating around the location
        angles = {}
        for point in self.onCurvePoints:
            angle = bezierTools.calculateAngle(*sorted((location, point)))
            angle = normalizeAngle(angle)
            angle = roundTo(angle, angleRoundingIncrement)
            if angle not in angles:
                angles[angle] = []
            distance = bezierTools.distanceFromPointToPoint(point, location)
            angles[angle].append((distance, point))
        nearest = []
        for angle, points in angles.items():
            points.sort()
            distance, point = points[0]
            nearest.append((angle, distance, point))
        if len(nearest) < 2:
            return
        # filter candidates
        tested = set()
        candidates = []
        for angle1, distance1, point1 in nearest:
            for angle2, distance2, point2 in nearest:
                if point1 == point2:
                    continue
                # already tested
                k = tuple(sorted((point1, point2)))
                if k in tested:
                    continue
                # if point1 is immediately followed by
                # point2, skip. this is better handled
                # by the segment measurements.
                s = " ".join((
                    _formatCoordinateForSearching(*point1),
                    _formatCoordinateForSearching(*point2)
                ))
                if s in self.searchString:
                    continue
                s = " ".join((
                    _formatCoordinateForSearching(*point2),
                    _formatCoordinateForSearching(*point1)
                ))
                if s in self.searchString:
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
                # if the line between point1 and point2
                # is not close to a right angle, skip.
                angle = bezierTools.calculateAngle(point1, point2)
                angle = normalizeAngle(angle)
                if angle <= rightAngleTolerance:
                    angleVariation = angle
                elif angle >= (90 - rightAngleTolerance) and angle <= (90 + rightAngleTolerance):
                    angleVariation = abs(90 - angle)
                elif angle >= (180 - rightAngleTolerance) and angle <= (180 + rightAngleTolerance):
                    angleVariation = abs(180 - angle)
                elif angle >= (270 - rightAngleTolerance) and angle <= (270 + rightAngleTolerance):
                    angleVariation = abs(270 - angle)
                elif angle >= (360 - rightAngleTolerance):
                    angleVariation = 360 - angle
                else:
                    continue
                angleVariation = round(angleVariation, -1)
                angleVariation = 0
                distance = bezierTools.distanceFromPointToPoint(point1, point2)
                distance = int(round(distance))
                candidates.append((angleVariation, distance, (point1, point2)))
        if not candidates:
            return
        candidates.sort()
        return candidates[0][-1]

pen = NearestPointsPointPen()
glyph = CurrentGlyph()
glyph.drawPoints(pen)
x = 337
y = 515
location = (x, y)
hit = pen.find(glyph, location)
print(hit)