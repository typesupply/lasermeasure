import merz
import defcon
from mojo.subscriber import Subscriber, registerGlyphEditorSubscriber

radius = 25

class SegmentScaleTest(Subscriber):

    debug = True

    def build(self):
        glyphEditor = self.getGlyphEditor()
        self.container = glyphEditor.extensionContainer(
            identifier="com.typesupply.LaserMeasure.experiments.segmentScale.background",
            location="background",
            clear=True
        )
        self.cursorLayer = self.container.appendOvalSublayer(
            fillColor=(1, 1, 0, 1),
            size=(radius * 2, radius * 2),
            anchor=(0.5, 0.5)
        )
        self.segmentLayer = self.container.appendPathSublayer(
            fillColor=None,
            strokeColor=(1, 0, 0, 0.2),
            strokeWidth=10,
            strokeCap="round"
        )

    def destroy(self):
        self.container.clearSublayers()

    def glyphEditorDidMouseMove(self, info):
        # clear
        self.segmentLayer.setPath(None)
        # get the new stuff
        window = self.getGlyphEditor()
        editor = window.getGlyphView()
        scale = editor.scale()
        glyph = window.getGlyph()
        if glyph is None:
            return
        glyph = glyph.asFontParts()
        deviceState = info["deviceState"]
        cursorPoint = tuple(info["locationInGlyph"])
        # update the cursor
        self.cursorLayer.setPosition(cursorPoint)
        s = radius / scale * 2
        self.cursorLayer.setSize((s, s))
        # find the closest segment
        selector = glyph.getRepresentation("doodle.GlyphSelection")
        found = selector.segmentStrokeHitByPoint_(
            defcon.Point(cursorPoint),
            radius / scale
        )
        if not found:
            return
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
        # highlight the hit segment
        pen = merz.MerzPen()
        pen.moveTo(segmentPoints[0])
        if segmentType == "move":
            segmentType = "line"
        if segmentType == "line":
            pen.lineTo(segmentPoints[1])
        else:
            if segmentType == "curve":
                pen.curveTo(*segmentPoints[1:])
            elif segmentType == "qcurve":
                pen.qCurveTo(*segmentPoints[1:])
        pen.endPath()
        self.segmentLayer.setPath(pen.path)


if __name__ == '__main__':
    registerGlyphEditorSubscriber(SegmentScaleTest)