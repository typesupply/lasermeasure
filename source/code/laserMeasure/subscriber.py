import math
from fontTools.misc import transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.pointPen import AbstractPointPen
from fontTools.misc import arrayTools
import defcon
import AppKit
from lib.tools import bezierTools
from fontParts.world import RGlyph
import merz
from mojo.roboFont import CreateCursor
from mojo import events
from mojo import tools
from mojo import subscriber
from mojo.extensions import (
    registerExtensionDefaults,
    getExtensionDefault,
    setExtensionDefault,
    removeExtensionDefault
)
from mojo import UI


extensionID = "com.typesupply.LaserMeasure."
defaults = {
    extensionID + "triggerCharacter" : "d",
    extensionID + "baseColor" : (0, 0.3, 1, 0.8),
    extensionID + "matchColor" : (1, 1, 0, 0.5),
    extensionID + "highlightStrokeWidth" : 10,
    extensionID + "highlightStrokeAlpha" : 0.2,
    extensionID + "measurementTextSize" : 12,
}

registerExtensionDefaults(defaults)

def getDefault(key):
    key = extensionID + key
    return getExtensionDefault(key)

# ----------
# Subscriber
# ----------

class LaserMeasureSubscriber(subscriber.Subscriber):

    debug = False

    def build(self):
        window = self.getGlyphEditor()
        self.containerBackground = window.extensionContainer(
            identifier=extensionID + "background",
            location="background",
            clear=True
        )
        self.containerForeground = window.extensionContainer(
            identifier=extensionID + "foreground",
            location="foreground",
            clear=True
        )
        # outline
        self.outlineBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.outlineForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.outlineWidthLayer = self.outlineBackground.appendLineSublayer()
        self.outlineHeightLayer = self.outlineBackground.appendLineSublayer()
        self.outlineTextLayer = self.outlineForeground.appendTextLineSublayer()
        # segment
        self.segmentBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.segmentForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.segmentMatchHighlightLayer = self.segmentBackground.appendPathSublayer()
        self.segmentHighlightLayer = self.segmentBackground.appendPathSublayer()
        self.segmentTextLayer = self.segmentForeground.appendTextLineSublayer()
        # handle
        self.handleBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.handleForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.handleMatchHighlightLayer = self.handleBackground.appendPathSublayer()
        self.handleHighlightLayer = self.handleBackground.appendPathSublayer()
        self.handleTextLayer = self.handleForeground.appendTextLineSublayer()
        # points
        self.pointBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.pointForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.pointLineLayer = self.pointBackground.appendLineSublayer()
        self.pointTextLayer = self.pointForeground.appendTextLineSublayer()
        # anchor
        self.anchorBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.anchorForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.anchorWidthLayer = self.anchorBackground.appendLineSublayer()
        self.anchorHeightLayer = self.anchorBackground.appendLineSublayer()
        self.anchorTextLayer = self.anchorForeground.appendTextLineSublayer()
        # go
        self.loadDefaults()

    def loadDefaults(self):
        # load
        baseColor = getDefault("baseColor")
        textColor = UI.getDefault("glyphViewBackgroundColor")
        matchColor = getDefault("matchColor")
        textSize = getDefault("measurementTextSize")
        highlightAlpha = getDefault("highlightStrokeAlpha")
        highlightWidth = getDefault("highlightStrokeWidth")
        self.triggerCharacter = getDefault("triggerCharacter")
        # build
        r, g, b, a = baseColor
        highlightColor = (r, g, b, a * highlightAlpha)
        lineAttributes = dict(
            strokeColor=baseColor,
            strokeWidth=1
        )
        highlightAttributes = dict(
            fillColor=None,
            strokeColor=highlightColor,
            strokeWidth=highlightWidth,
            strokeCap="round"
        )
        textAttributes = dict(
            backgroundColor=baseColor,
            fillColor=textColor,
            padding=(6, 3),
            cornerRadius=5,
            offset=(7, -7),
            horizontalAlignment="left",
            verticalAlignment="top",
            pointSize=textSize,
            weight="bold",
            figureStyle="regular"
        )
        # populate
        self.outlineWidthLayer.setPropertiesByName(lineAttributes)
        self.outlineHeightLayer.setPropertiesByName(lineAttributes)
        self.outlineTextLayer.setPropertiesByName(textAttributes)
        self.segmentMatchHighlightLayer.setPropertiesByName(highlightAttributes)
        self.segmentMatchHighlightLayer.setStrokeColor(matchColor)
        self.segmentHighlightLayer.setPropertiesByName(highlightAttributes)
        self.segmentTextLayer.setPropertiesByName(textAttributes)
        self.handleMatchHighlightLayer.setPropertiesByName(highlightAttributes)
        self.handleMatchHighlightLayer.setStrokeColor(matchColor)
        self.handleHighlightLayer.setPropertiesByName(highlightAttributes)
        self.handleTextLayer.setPropertiesByName(textAttributes)
        self.pointLineLayer.setPropertiesByName(lineAttributes)
        self.pointTextLayer.setPropertiesByName(textAttributes)
        self.anchorWidthLayer.setPropertiesByName(lineAttributes)
        self.anchorHeightLayer.setPropertiesByName(lineAttributes)
        self.anchorTextLayer.setPropertiesByName(textAttributes)

    def destroy(self):
        self.containerBackground.clearSublayers()
        self.containerForeground.clearSublayers()

    def hideLayers(self):
        self.containerBackground.setVisible(False)
        self.containerForeground.setVisible(False)

    def glyphEditorDidMouseDown(self, info):
        self.wantsMeasurements = False
        self.hideLayers()
        setCursorMode(None)

    wantsMeasurements = False

    def glyphEditorDidKeyDown(self, info):
        deviceState = info["deviceState"]
        if deviceState["keyDownWithoutModifiers"] != self.triggerCharacter:
            self.wantsMeasurements = False
        else:
            self.wantsMeasurements = True
            setCursorMode("searching")

    def glyphEditorDidKeyUp(self, info):
        self.wantsMeasurements = False
        self.hideLayers()
        setCursorMode(None)

    def glyphEditorDidMouseMove(self, info):
        if not self.wantsMeasurements:
            return
        glyph = info["glyph"]
        if not glyph.bounds:
            self.hideLayers()
            return
        deviceState = info["deviceState"]
        point = tuple(info["locationInGlyph"])
        anchorState = False
        handleState = False
        segmentState = False
        pointState = False
        outlineState = False
        cursorMode = "searching"
        if self.measureAnchors(point, glyph, deviceState):
            anchorState = True
            cursorMode = "hit"
        elif self.measureHandles(point, glyph, deviceState):
            handleState = True
            cursorMode = "hit"
        elif self.measureSegments(point, glyph, deviceState):
            segmentState = True
            cursorMode = "hit"
        elif self.measurePoints(point, glyph, deviceState):
            pointState = True
            cursorMode = "hit"
        elif self.measureOutline(point, glyph, deviceState):
            outlineState = True
        setCursorMode(cursorMode)
        self.anchorBackground.setVisible(anchorState)
        self.anchorForeground.setVisible(anchorState)
        self.handleBackground.setVisible(handleState)
        self.handleForeground.setVisible(handleState)
        self.segmentBackground.setVisible(segmentState)
        self.segmentForeground.setVisible(segmentState)
        self.pointBackground.setVisible(pointState)
        self.pointForeground.setVisible(pointState)
        self.outlineBackground.setVisible(outlineState)
        self.outlineForeground.setVisible(outlineState)
        self.containerBackground.setVisible(True)
        self.containerForeground.setVisible(True)

    def _conditionalRectFallbacks(self, point, glyph, deviceState):
        x, y = point
        if deviceState["optionDown"]:
            xBeforeFallback, yBeforeFallback, xAfterFallback, yAfterFallback = glyph.bounds
        else:
            font = glyph.font
            xBeforeFallback = min((0, x))
            xAfterFallback = max((glyph.width, x))
            verticalMetrics = [
                font.info.descender,
                0,
                font.info.xHeight,
                font.info.capHeight,
                font.info.ascender
            ]
            yBeforeFallback = min(verticalMetrics)
            yAfterFallback = max(verticalMetrics)
            for value in verticalMetrics:
                if value > yBeforeFallback and value <= y:
                    yBeforeFallback = value
                if value < yAfterFallback and value >= y:
                    yAfterFallback = value
        return xBeforeFallback, yBeforeFallback, xAfterFallback, yAfterFallback

    def measureAnchors(self,
            point,
            glyph,
            deviceState
        ):
        if not glyph.anchors:
            return
        if not glyph.bounds:
            return
        font = glyph.font
        tolerance = 20
        x, y = point
        xMin = x - tolerance
        yMin = y - tolerance
        xMax = x + tolerance
        yMax = y + tolerance
        hitRect = (xMin, yMin, xMax, yMax)
        xMin, yMin, xMax, yMax = glyph.bounds
        xMin -= font.info.unitsPerEm
        xMax += font.info.unitsPerEm
        yMin -= font.info.unitsPerEm
        yMax += font.info.unitsPerEm
        for anchor in glyph.anchors:
            anchorPoint = (anchor.x, anchor.y)
            if arrayTools.pointInRect(anchorPoint, hitRect):
                ax, ay = anchorPoint
                if x <= ax:
                    xStart = xMin
                    xStop = ax
                else:
                    xStart = ax
                    xStop = xMax
                if y <= ay:
                    yStart = yMin
                    yStop = ay
                else:
                    yStart = ay
                    yStop = yMax
                xBeforeFallback, yBeforeFallback, xAfterFallback, yAfterFallback = self._conditionalRectFallbacks(point, glyph, deviceState)
                xLine = (
                    (xStart, ay),
                    (xStop, ay)
                )
                xIntersections = tools.IntersectGlyphWithLine(
                    glyph,
                    xLine,
                    canHaveComponent=True,
                    addSideBearings=False
                )
                xIntersections = [oX for oX, oY in xIntersections]
                xIntersections.sort()
                if x <= ax:
                    if not xIntersections:
                        hitX = xBeforeFallback
                    else:
                        hitX = xIntersections[-1]
                else:
                    if not xIntersections:
                        hitX = xAfterFallback
                    else:
                        hitX = xIntersections[0]
                yLine = (
                    (ax, yStart),
                    (ax, yStop)
                )
                yIntersections = tools.IntersectGlyphWithLine(
                    glyph,
                    yLine,
                    canHaveComponent=True,
                    addSideBearings=False
                )
                yIntersections = [oY for oX, oY in yIntersections]
                yIntersections.sort()
                if y <= ay:
                    if not yIntersections:
                        hitY = yBeforeFallback
                    else:
                        hitY = yIntersections[-1]
                else:
                    if not yIntersections:
                        hitY = yAfterFallback
                    else:
                        hitY = yIntersections[0]
                width = abs(ax - hitX)
                height = abs(ay - hitY)
                with self.anchorWidthLayer.propertyGroup():
                    self.anchorWidthLayer.setStartPoint((hitX, ay))
                    self.anchorWidthLayer.setEndPoint((ax, ay))
                with self.anchorHeightLayer.propertyGroup():
                    self.anchorHeightLayer.setStartPoint((ax, ay))
                    self.anchorHeightLayer.setEndPoint((ax, hitY))
                with self.anchorTextLayer.propertyGroup():
                    self.anchorTextLayer.setPosition((ax, ay))
                    self.anchorTextLayer.setText(f"{width} × {height}")
                return True

    def measureHandles(self,
            point,
            glyph,
            deviceState
        ):
        hit = measureSegmentsAndHandles(
            point,
            glyph.getRepresentation(extensionID + "handlesAsLines"),
            self.handleHighlightLayer,
            self.handleTextLayer
        )
        if hit:
            points = hit[1]
            self._findMatchingHandles(
                points,
                glyph
            )
            self.handleMatchHighlightLayer.setVisible(True)
            return True
        else:
            self.handleMatchHighlightLayer.setVisible(False)

    def _findMatchingHandles(self,
            points,
            glyph
        ):
        layer = self.handleMatchHighlightLayer
        layerPen = merz.MerzPen()
        target = HandleMatcher(points)
        handles = glyph.getRepresentation(extensionID + "handles")
        for handle in handles:
            if target.compare(handle):
                layerPen.moveTo(handle[0])
                layerPen.lineTo(handle[1])
                layerPen.endPath()
        layer.setPath(layerPen.path)

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
            self.segmentMatchHighlightLayer.setVisible(True)
            return True
        else:
            self.segmentMatchHighlightLayer.setVisible(False)

    def _findMatchingSegments(self,
            segmentType,
            segmentPoints,
            glyph
        ):
        layer = self.segmentMatchHighlightLayer
        layerPen = merz.MerzPen()
        target = SegmentMatcher(segmentType, segmentPoints)
        segments = glyph.getRepresentation(extensionID + "segments")
        for otherSegmentType, otherSegmentPoints in segments:
            if target.compare(otherSegmentType, otherSegmentPoints):
                layerPen.moveTo(otherSegmentPoints[0])
                if otherSegmentType == "line":
                    layerPen.lineTo(otherSegmentPoints[1])
                elif otherSegmentType == "curve":
                    layerPen.curveTo(*otherSegmentPoints[1:])
                elif otherSegmentType == "qcurve":
                    layerPen.qCurveTo(*otherSegmentPoints[1:])
                layerPen.endPath()
        layer.setPath(layerPen.path)

    def measurePoints(self,
            point,
            glyph,
            deviceState
        ):
        pen = NearestPointsPointPen()
        glyph.drawPoints(pen)
        points = pen.find(point)
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
        xBeforeFallback, yBeforeFallback, xAfterFallback, yAfterFallback = self._conditionalRectFallbacks(point, glyph, deviceState)
        # width
        xLine = (
            (xMin, y),
            (xMax, y)
        )
        xIntersections = tools.IntersectGlyphWithLine(
            glyph,
            xLine,
            canHaveComponent=True,
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
            canHaveComponent=True,
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

# -------
# Cursors
# -------

def setCursorMode(mode):
    tool = events.getActiveEventTool()
    if mode == "searching":
        cursor = mainCursor
    elif mode == "hit":
        cursor = mainCursor
    else:
        cursor = tool.getDefaultCursor()
    tool.setCursor(cursor)

size = 15
black = AppKit.NSColor.colorWithCalibratedWhite_alpha_(0, 1)
white = AppKit.NSColor.whiteColor()
oval = AppKit.NSBezierPath.bezierPathWithOvalInRect_(
    ((5, 5), (size - 10, size - 10))
)

cursorImage = AppKit.NSImage.alloc().initWithSize_((size, size))
cursorImage.lockFocus()
white.set()
oval.setLineWidth_(2)
oval.stroke()
black.set()
oval.setLineWidth_(1)
oval.fill()
cursorImage.unlockFocus()
mainCursor = CreateCursor(
    cursorImage,
    hotSpot=(size/2, size/2)
)

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
    pen = merz.MerzPen()
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
    highlightLayer.setPath(pen.path)
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
    extensionID + "handlesAsLines",
    handlesAsLinesGlyphFactory
)


# Collinear Points
# ----------------

class NearestPointsPointPen(AbstractPointPen):

    def __init__(self):
        self.onCurvePoints = []
        self.offCurvePoints = []

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

    def find(self, location):
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
        # use collinearity with the location
        # to eliminate point combinations that
        # don't make sense. then further narrow
        # down based on how close to a right angle
        # the line between points is.
        tested = set()
        candidates = []
        for angle1, distance1, point1 in nearest:
            for angle2, distance2, point2 in nearest:
                if point1 == point2:
                    continue
                k = tuple(sorted((point1, point2)))
                if k in tested:
                    continue
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
                # XXX future candidate eliminators can go here.
                # - something that eliminates
                #   lines that cut across contours.
                #   for example the top curve on a b
                #   snapping to the bottom of the counter.
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


def normalizeAngle(angle):
    if angle < 0:
        angle = 360 + angle
    return angle

def roundTo(value, multiple):
    value = int(round(value / float(multiple))) * multiple
    return value


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
        if makeReversedSegment(segment) == self.original:
            return False
        if type != self.type:
            return False
        if len(segment) != len(self.original):
            return False
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

def segmentsGlyphFactory(glyph):
    segmentsPen = SegmentsPen()
    glyph.draw(segmentsPen)
    return segmentsPen.segments

defcon.registerRepresentationFactory(
    defcon.Glyph,
    extensionID + "segments",
    segmentsGlyphFactory
)


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
    return tuple(reversed(points))

rotate90Transform = transform.Transform().rotate(math.radians(90))
rotate180Transform = transform.Transform().rotate(math.radians(180))
rotate270Transform = transform.Transform().rotate(math.radians(270))
flipHorizontalTransform = transform.Scale(1, -1)
flipVerticalTransform = transform.Scale(-1, 1)


# Handle Matching
# ---------------

class HandleMatcher(SegmentMatcher):

    def __init__(self, points):
        super().__init__(None, points)

    def compare(self, points):
        return super().compare(None, points)


class HandlesPen(BasePen):

    def __init__(self):
        super().__init__()
        self.handles = []

    def _moveTo(self, pt):
        self.prevPoint = pt

    def _lineTo(self, pt):
        self.prevPoint = pt

    def _curveToOne(self, pt1, pt2, pt3):
        self.handles.append((self.prevPoint, pt1))
        self.handles.append((pt2, pt3))
        self.prevPoint = pt3

    def _qCurveToOne(self, pt1, pt2):
        self.handles.append((self.prevPoint, pt1))
        self.handles.append((pt1, pt2))
        self.prevPoint = pt2

    def _closePath(self):
        self.prevPoint = None

    def _endPath(self):
        self.prevPoint = None

def handlesGlyphFactory(glyph):
    handlesPen = HandlesPen()
    glyph.draw(handlesPen)
    return handlesPen.handles

defcon.registerRepresentationFactory(
    defcon.Glyph,
    extensionID + "handles",
    handlesGlyphFactory
)


# --
# Go
# --

def main():
    subscriber.registerGlyphEditorSubscriber(LaserMeasureSubscriber)

if __name__ == "__main__":
    if AppKit.NSUserName() == "tal":
        for key in defaults.keys():
            removeExtensionDefault(key)
        registerExtensionDefaults(defaults)
    LaserMeasureSubscriber.debug = True
    main()