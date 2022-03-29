import math
from fontTools.misc import transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.pointPen import AbstractPointPen
import defcon
from lib.tools import bezierTools
from fontParts.world import RGlyph
from mojo import events
from mojo import tools
from mojo import subscriber


class LaserMeasureSubscriber(subscriber.Subscriber):

    debug = True
    strokeColor = (0, 0.3, 1, 1)
    textColor = (1, 1, 1, 1)
    matchColor = (1, 1, 0, 0.5)
    activateWithCharacter = "m"

    def build(self):
        r, g, b, a = self.strokeColor
        highlightColor = (r, g, b, a * 0.2)
        lineAttributes = dict(
            strokeColor=self.strokeColor,
            strokeWidth=1
        )
        highlightAttributes = dict(
            fillColor=None,
            strokeColor=highlightColor,
            strokeWidth=10,
            strokeCap="round"
        )
        textAttributes = dict(
            backgroundColor=self.strokeColor,
            fillColor=self.textColor,
            padding=(6, 3),
            cornerRadius=5,
            offset=(7, 7),
            horizontalAlignment="left",
            verticalAlignment="bottom",
            pointSize=12,
            weight="bold",
            figureStyle="regular"
        )
        window = self.getGlyphEditor()
        self.container = window.extensionContainer(
            identifier="com.typesupply.LaserMeasure.foreground",
            location="foreground",
            clear=True
        )
        # outline
        self.outlineLayer = self.container.appendBaseSublayer(
            visible=False
        )
        self.outlineWidthLayer = self.outlineLayer.appendLineSublayer(
            **lineAttributes
        )
        self.outlineHeightLayer = self.outlineLayer.appendLineSublayer(
            **lineAttributes
        )
        self.outlineTextLayer = self.outlineLayer.appendTextLineSublayer(
            **textAttributes
        )
        # segment match
        self.matchLayer = self.container.appendBaseSublayer(
            visible=False
        )
        self.matchHighlightLayer = self.container.appendPathSublayer(
            **highlightAttributes
        )
        self.matchHighlightLayer.setStrokeColor(self.matchColor)
        # segment
        self.segmentLayer = self.container.appendBaseSublayer(
            visible=False
        )
        self.segmentHighlightLayer = self.segmentLayer.appendPathSublayer(
            **highlightAttributes
        )
        self.segmentTextLayer = self.segmentLayer.appendTextLineSublayer(
            **textAttributes
        )
        # handle
        self.handleLayer = self.container.appendBaseSublayer(
            visible=False
        )
        self.handleHighlightLayer = self.handleLayer.appendPathSublayer(
            **highlightAttributes
        )
        self.handleTextLayer = self.handleLayer.appendTextLineSublayer(
            **textAttributes
        )
        self.hideLayers()
        # points
        self.pointLayer = self.container.appendBaseSublayer(
            visible=False
        )
        self.pointLineLayer = self.pointLayer.appendLineSublayer(
            **lineAttributes
        )
        self.pointTextLayer = self.pointLayer.appendTextLineSublayer(
            **textAttributes
        )

    def destroy(self):
        self.container.clearSublayers()

    def hideLayers(self):
        self.container.setVisible(False)

    def glyphEditorDidMouseDown(self, info):
        self.wantsMeasurements = False
        self.hideLayers()

    wantsMeasurements = False

    def glyphEditorDidKeyDown(self, info):
        deviceState = info["deviceState"]
        if deviceState["keyDownWithoutModifiers"] != self.activateWithCharacter:
            self.wantsMeasurements = False
        else:
            self.wantsMeasurements = True

    def glyphEditorDidKeyUp(self, info):
        self.wantsMeasurements = False
        self.hideLayers()

    def glyphEditorDidMouseMove(self, info):
        if not self.wantsMeasurements:
            return
        glyph = info["glyph"]
        if not glyph.bounds:
            self.hideLayers()
            return
        deviceState = info["deviceState"]
        point = tuple(info["locationInGlyph"])
        handleState = False
        segmentState = False
        pointState = False
        outlineState = False
        if self.measureHandles(point, glyph, deviceState):
            handleState = True
        elif self.measureSegments(point, glyph, deviceState):
            segmentState = True
        elif self.measurePoints(point, glyph, deviceState):
            pointState = True
        elif self.measureOutline(point, glyph, deviceState):
            outlineState = True
        self.handleLayer.setVisible(handleState)
        self.segmentLayer.setVisible(segmentState)
        self.pointLayer.setVisible(pointState)
        self.outlineLayer.setVisible(outlineState)
        self.container.setVisible(True)

    def measureHandles(self,
            point,
            glyph,
            deviceState
        ):
        glyph = glyph.getRepresentation("com.typesupply.LaserMeasure.handlesAsLines")
        return measureSegmentsAndHandles(
            point,
            glyph,
            self.handleHighlightLayer,
            self.handleTextLayer
        )

    def measureSegments(self,
            point,
            glyph,
            deviceState
        ):
        hit = measureSegmentsAndHandles(
            point,
            glyph,
            self.segmentHighlightLayer,
            self.segmentTextLayer
        )
        if hit:
            segmentType, segmentPoints = hit
            self._findMatchingSegments(
                segmentType,
                segmentPoints,
                glyph
            )
            self.matchHighlightLayer.setVisible(True)
            return True
        else:
            self.matchHighlightLayer.setVisible(False)

    def _findMatchingSegments(self,
            segmentType,
            segmentPoints,
            glyph
        ):
        # XXX
        # This is horribly inefficient.
        # 1. don't draw with the layer pen.
        #    draw to CGPen and set the path.
        # 2. get the segments from a representation.
        layer = self.matchHighlightLayer
        layerPen = layer.getPen()
        target = SegmentMatcher(segmentType, segmentPoints)
        segmentsPen = SegmentsPen()
        glyph.draw(segmentsPen)
        for otherSegmentType, otherSegmentPoints in segmentsPen.segments:
            if target.compare(otherSegmentType, otherSegmentPoints):
                layerPen.moveTo(otherSegmentPoints[0])
                if otherSegmentType == "line":
                    layerPen.lineTo(otherSegmentPoints[1])
                elif otherSegmentType == "curve":
                    layerPen.curveTo(*otherSegmentPoints[1:])
                elif otherSegmentType == "qcurve":
                    layerPen.qCurveTo(*otherSegmentPoints[1:])
                layerPen.endPath()


    def measurePoints(self,
            point,
            glyph,
            deviceState
        ):
        pen = NearestPointsPointPen(point)
        glyph.drawPoints(pen)
        points = pen.getPoints()
        if not points:
            return
        point1, point2 = points
        x1, y1 = point1
        x2, y2 = point2
        width = int(round(abs(x1 - x2)))
        height = int(round(abs(y1 - y2)))
        self.pointLineLayer.setStartPoint(point1)
        self.pointLineLayer.setEndPoint(point2)
        self.pointTextLayer.setPosition(point)
        self.pointTextLayer.setText(f"{width} × {height}")
        return True

    def measureOutline(self,
            point,
            glyph,
            deviceState
        ):
        font = glyph.font
        x, y = point
        xMin = -font.info.unitsPerEm
        xMax = glyph.width + font.info.unitsPerEm
        yMin = font.info.descender - font.info.unitsPerEm
        yMax = font.info.ascender + font.info.unitsPerEm
        # - ignore components
        calculateWithComponents = not deviceState["controlDown"]
        # - measure with bounds
        if deviceState["optionDown"]:
            xBeforeFallback, yBeforeFallback, xAfterFallback, yAfterFallback = glyph.bounds
        # - measure with glyph rect
        else:
            xBeforeFallback = min((0, x))
            xAfterFallback = max((glyph.width, x))
            yBeforeFallback = 1
            yAfterFallback = font.info.ascender
        # width
        xLine = (
            (xMin, y),
            (xMax, y)
        )
        xIntersections = tools.IntersectGlyphWithLine(
            glyph,
            xLine,
            canHaveComponent=calculateWithComponents,
            addSideBearings=False
        )
        xIntersections = [oX for oX, oY in xIntersections]
        x1, x2, width = findAdjacentValues(
            x,
            xIntersections,
            beforeFallback=xBeforeFallback,
            afterFallback=xAfterFallback
        )
        # height
        yLine = (
            (x, yMin),
            (x, yMax)
        )
        yIntersections = tools.IntersectGlyphWithLine(
            glyph,
            yLine,
            canHaveComponent=calculateWithComponents,
            addSideBearings=False
        )
        yIntersections = [oY for oX, oY in yIntersections]
        y1, y2, height = findAdjacentValues(
            y,
            yIntersections,
            beforeFallback=yBeforeFallback,
            afterFallback=yAfterFallback
        )
        # display
        with self.outlineWidthLayer.propertyGroup():
            self.outlineWidthLayer.setStartPoint((x1, y))
            self.outlineWidthLayer.setEndPoint((x1 + width, y))
        with self.outlineHeightLayer.propertyGroup():
            self.outlineHeightLayer.setStartPoint((x, y1))
            self.outlineHeightLayer.setEndPoint((x, y1 + height))
        with self.outlineTextLayer.propertyGroup():
            self.outlineTextLayer.setPosition((x, y))
            self.outlineTextLayer.setText(f"{width} × {height}")
        return True

# -----
# Tools
# -----

def findAdjacentValues(
        value,
        otherValues,
        beforeFallback,
        afterFallback
    ):
    # XXX
    # this can probably be optimized
    # with bisect.bisect
    before = []
    after = []
    for otherValue in otherValues:
        d = abs(value - otherValue)
        if otherValue <= value:
            before.append((d, otherValue))
        if otherValue >= value:
            after.append((d, otherValue))
    if not before:
        before.append((0, beforeFallback))
    if not after:
        after.append((0, afterFallback))
    v1 = min(before)[1]
    v2 = min(after)[1]
    d = int(round(abs(v1 - v2)))
    return v1, v2, d


# Segments and Handles
# --------------------

def measureSegmentsAndHandles(
        point,
        glyph,
        highlightLayer,
        textLayer
    ):
    x, y = point
    selector = glyph.getRepresentation("doodle.GlyphSelection")
    point = defcon.Point(point)
    found = selector.segmentStrokeHitByPoint_(point, 5)
    if not found:
        highlightLayer.setVisible(False)
        textLayer.setVisible(False)
        return
    contourIndex, segmentIndex, nsSegment = found
    contour = glyph[contourIndex]
    segments = contour.segments
    segment = segments[segmentIndex]
    prevSegment = segments[segmentIndex - 1]
    x1, y1 = (prevSegment.onCurve.x, prevSegment.onCurve.y)
    x2, y2 = (segment.onCurve.x, segment.onCurve.y)
    pen = highlightLayer.getPen()
    pen.moveTo((x1, y1))
    segmentType = segment.type
    if segmentType == "move":
        segmentType = "line"
    if segment.type == "line":
        pen.lineTo((x2, y2))
        points = [(x1, y1), (x2, y2)]
    else:
        points = [(p.x, p.y) for p in segment.points]
        if segment.type == "curve":
            pen.curveTo(*points)
        elif segment.type == "qcurve":
            pen.qCurveTo(*points)
        points.insert(0, (x1, y1))
    pen.lineTo((x2, y2))
    pen.endPath()
    width = int(round(abs(x1 - x2)))
    height = int(round(abs(y1 - y2)))
    textLayer.setPosition((x, y))
    textLayer.setText(f"{width} × {height}")
    highlightLayer.setVisible(True)
    textLayer.setVisible(True)
    return segmentType, points


class HandlesToLinesPen(BasePen):

    def __init__(self, outPen):
        super().__init__()
        self.outPen = outPen
        self.prevPoint = None
        self.handles = []

    def _moveTo(self, pt):
        self.prevPoint = pt

    def _lineTo(self, pt):
        self.prevPoint = pt

    def _curveToOne(self, pt1, pt2, pt3):
        self.outPen.moveTo(self.prevPoint)
        self.outPen.lineTo(pt1)
        self.outPen.endPath()
        self.outPen.moveTo(pt2)
        self.outPen.lineTo(pt3)
        self.outPen.endPath()
        self.prevPoint = pt3

    def _qCurveToOne(self, pt1, pt2):
        self.outPen.moveTo(self.prevPoint)
        self.outPen.lineTo(pt1)
        self.outPen.endPath()
        self.outPen.moveTo(pt1)
        self.outPen.lineTo(pt2)
        self.outPen.endPath()
        self.prevPoint = pt2

    def _closePath(self):
        self.prevPoint = None

    def _endPath(self):
        self.prevPoint = None


def handlesAsLinesGlyphFactory(glyph):
    outGlyph = RGlyph()
    pen = HandlesToLinesPen(outGlyph.getPen())
    glyph.draw(pen)
    return outGlyph

defcon.registerRepresentationFactory(
    defcon.Glyph,
    "com.typesupply.LaserMeasure.handlesAsLines",
    handlesAsLinesGlyphFactory
)


# Collinear Points
# ----------------

class NearestPointsPointPen(AbstractPointPen):

    def __init__(self, point):
        self.point = point
        self.negative = []
        self.positive = []

    def beginPath(self, **kwargs):
        pass

    def endPath(self, **kwargs):
        pass

    def addComponent(self, **kwargs):
        pass

    def addPoint(self, pt, **kwargs):
        import math
        distance = bezierTools.distanceFromPointToPoint(
            self.point,
            pt
        )
        angle = bezierTools.calculateAngle(
            self.point,
            pt
        )
        if angle < 0:
            self.negative.append((distance, pt))
        else:
            self.positive.append((distance, pt))

    def getPoints(self):
        if self.negative and self.positive:
            self.negative.sort()
            self.positive.sort()
            prevPrevPoint = None
            prevPoint = self.negative[0][1]
            point = self.point
            nextPoint = self.positive[0][1]
            nextNextPoint = None
            if len(self.negative) > 1:
                prevPrevPoint = self.negative[1][1]
            if len(self.positive) > 1:
                nextNextPoint = self.positive[1][1]
            candidates = [
                (prevPoint, point, nextPoint),
                (prevPrevPoint, point, nextPoint),
                (prevPoint, point, nextNextPoint),
                (prevPrevPoint, point, nextNextPoint)
            ]
            for candidate in candidates:
                if None in candidate:
                    continue
                if isCloseToCollinear(prevPoint, point, nextPoint):
                    return (prevPoint, nextPoint)
        return None

collinearityTolerance = 0.1

def isCloseToCollinear(pt1, pt2, pt3):
    dx1, dy1 = pt2[0] - pt1[0], pt2[1] - pt1[1]
    dx2, dy2 = pt3[0] - pt2[0], pt3[1] - pt2[1]
    a1 = math.atan2(dx1, dy1)
    a2 = math.atan2(dx2, dy2)
    return abs(a1 - a2) < collinearityTolerance


# Segment Matching
# ----------------

class SegmentMatcher:

    def __init__(self, type, segment):
        if type == "move":
            type = "line"
        self.type = type
        self.original = tuple(segment)

    def compare(self, type, segment):
        if segment == self.original:
            return False
        if type != self.type:
            return False
        if len(segment) != len(self.original):
            return False
        og = segment
        segment = makeRelativeSegment(segment)
        generators = (
            ("base", None),
            ("rotated90", [rotate90Transform.transformPoints]),
            ("rotated180", [rotate180Transform.transformPoints]),
            ("rotated270", [rotate270Transform.transformPoints]),
            ("flippedHorizontal", [flipHorizontalTransform.transformPoints]),
            ("flippedVertical", [flipVerticalTransform.transformPoints]),
            ("reversedBase", [makeReversedSegment]),
            ("reversedRotated90", [makeReversedSegment, rotate90Transform.transformPoints]),
            ("reversedRotated180", [makeReversedSegment, rotate180Transform.transformPoints]),
            ("reversedRotated270", [makeReversedSegment, rotate270Transform.transformPoints]),
            ("reversedFlippedHorizontal", [makeReversedSegment, flipHorizontalTransform.transformPoints]),
            ("reversedFlippedVertical", [makeReversedSegment, flipVerticalTransform.transformPoints]),
        )
        for attr, generator in generators:
            if not hasattr(self, attr):
                value = self.original
                if generator is not None:
                    for g in generator:
                        value = g(value)
                value = makeRelativeSegment(value)
                setattr(self, attr, value)
            value = getattr(self, attr)
            if segment == value:
                return True
        return False


class SegmentsPen(BasePen):

    def __init__(self):
        super().__init__()
        self.prevPoint = None
        self.segments = []

    def _moveTo(self, pt):
        self.prevPoint = pt

    def _lineTo(self, pt):
        self.segments.append(("line", (self.prevPoint, pt)))
        self.prevPoint = pt

    def _curveToOne(self, pt1, pt2, pt3):
        self.segments.append(("curve", (self.prevPoint, pt1, pt2, pt3)))
        self.prevPoint = pt3

    def _qCurveToOne(self, pt1, pt2):
        self.segments.append(("qcurve", (self.prevPoint, pt1, pt2)))
        self.prevPoint = pt2

    def _closePath(self):
        self.prevPoint = None

    def _endPath(self):
        self.prevPoint = None


def makeRelativePoint(point, basePoint):
    px, py = point
    bx, by = basePoint
    x = px - bx
    y = py - by
    return (x, y)

def makeRelativeSegment(points):
    points = [(0, 0)] + [
        makeRelativePoint(p, points[0])
        for p in points[1:]
    ]
    return points

def makeReversedSegment(points):
    return list(reversed(points))

rotate90Transform = transform.Transform().rotate(math.radians(90))
rotate180Transform = transform.Transform().rotate(math.radians(180))
rotate270Transform = transform.Transform().rotate(math.radians(270))
flipHorizontalTransform = transform.Scale(1, -1)
flipVerticalTransform = transform.Scale(-1, 1)


# --
# Go
# --

def main():
    subscriber.registerGlyphEditorSubscriber(LaserMeasureSubscriber)

if __name__ == "__main__":
    main()