from fontTools.pens.basePen import BasePen
import defcon
from fontParts.world import RGlyph
from mojo import events
from mojo import tools
from mojo import subscriber


class LaserMeasureSubscriber(subscriber.Subscriber):

    debug = True
    strokeColor = (0, 0.3, 1, 1)
    textColor = (1, 1, 1, 1)

    def build(self):
        r, g, b, a = self.strokeColor
        highlightColor = (r, g, b, a * 0.2)
        textAttributes = dict(
            backgroundColor=self.strokeColor,
            fillColor=self.textColor,
            padding=(6, 3),
            cornerRadius=5,
            offset=(7, 7),
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
            startPoint=(0, 100),
            endPoint=(100, 100),
            strokeColor=self.strokeColor,
            strokeWidth=(1)
        )
        self.outlineHeightLayer = self.outlineLayer.appendLineSublayer(
            startPoint=(100, 0),
            endPoint=(100, 100),
            strokeColor=self.strokeColor,
            strokeWidth=(1)
        )
        self.outlineTextLayer = self.outlineLayer.appendTextLineSublayer(
            horizontalAlignment="left",
            verticalAlignment="bottom",
            **textAttributes
        )
        # segment
        self.segmentLayer = self.container.appendBaseSublayer(
            visible=False
        )
        self.segmentHighlightLayer = self.segmentLayer.appendPathSublayer(
            fillColor=None,
            strokeColor=highlightColor,
            strokeWidth=10,
            strokeCap="round"
        )
        self.segmentTextLayer = self.segmentLayer.appendTextLineSublayer(
            horizontalAlignment="right",
            verticalAlignment="bottom",
            **textAttributes
        )
        # handle
        self.handleLayer = self.container.appendBaseSublayer(
            visible=False
        )
        self.handleHighlightLayer = self.handleLayer.appendPathSublayer(
            fillColor=None,
            strokeColor=highlightColor,
            strokeWidth=10,
            strokeCap="round"
        )
        self.handleTextLayer = self.handleLayer.appendTextLineSublayer(
            horizontalAlignment="right",
            verticalAlignment="bottom",
            **textAttributes
        )
        self.hideLayers()

    def destroy(self):
        self.container.clearSublayers()

    def hideLayers(self):
        self.outlineLayer.setVisible(False)
        self.segmentLayer.setVisible(False)
        self.handleLayer.setVisible(False)

    def glyphEditorDidChangeModifiers(self, info):
        deviceState = info["deviceState"]
        if not deviceState["capLockDown"]:
            self.hideLayers()
            return

    def glyphEditorDidMouseDown(self, info):
        self.hideLayers()

    def glyphEditorDidMouseMove(self, info):
        deviceState = info["deviceState"]
        if not deviceState["capLockDown"]:
            self.hideLayers()
            return
        glyph = info["glyph"]
        if not glyph.bounds:
            self.hideLayers()
            return
        point = tuple(info["locationInGlyph"])
        if deviceState["commandDown"]:
            self.outlineLayer.setVisible(False)
            if deviceState["optionDown"]:
                self.segmentLayer.setVisible(False)
                self.measureHandles(
                    point,
                    glyph,
                    deviceState
                )
                self.handleLayer.setVisible(True)
            else:
                self.handleLayer.setVisible(False)
                self.measureSegments(
                    point,
                    glyph,
                    deviceState
                )
                self.segmentLayer.setVisible(True)
        else:
            self.handleLayer.setVisible(False)
            self.segmentLayer.setVisible(False)
            self.measureOutline(
                point,
                glyph,
                deviceState
            )
            self.outlineLayer.setVisible(True)

    def measureHandles(self,
            point,
            glyph,
            deviceState
        ):
        glyph = glyph.getRepresentation("com.typesupply.LaserMeasure.handlesAsLines")
        measureSegmentsAndHandles(
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
        measureSegmentsAndHandles(
            point,
            glyph,
            self.segmentHighlightLayer,
            self.segmentTextLayer
        )

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
    if segment.type == "move":
        pen.lineTo((x2, y2))
    elif segment.type == "line":
        pen.lineTo((x2, y2))
    else:
        points = [(p.x, p.y) for p in segment.points]
        if segment.type == "curve":
            pen.curveTo(*points)
        elif segment.type == "qcurve":
            pen.qCurveTo(*points)
    pen.lineTo((x2, y2))
    pen.endPath()
    width = int(round(abs(x1 - x2)))
    height = int(round(abs(y1 - y2)))
    textLayer.setPosition((x, y))
    textLayer.setText(f"{width} × {height}")
    highlightLayer.setVisible(True)
    textLayer.setVisible(True)


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


def main():
    subscriber.registerGlyphEditorSubscriber(LaserMeasureSubscriber)

if __name__ == "__main__":
    main()