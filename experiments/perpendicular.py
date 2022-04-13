import math
import merz
import defcon
from mojo.subscriber import Subscriber, registerGlyphEditorSubscriber
from lib.tools import bezierTools
from fontTools.misc import bezierTools as ftBezierTools
from mojo import tools

radius = 25

class PerpendicularTest(Subscriber):

    debug = True

    def build(self):
        glyphEditor = self.getGlyphEditor()
        self.container = glyphEditor.extensionContainer(
            identifier="com.typesupply.LaserMeasure.experiments.perindicular.background",
            location="background",
            clear=True
        )
        self.cursorLayer = self.container.appendOvalSublayer(
            fillColor=(1, 1, 0, 0.2),
            size=(radius * 2, radius * 2),
            anchor=(0.5, 0.5)
        )
        self.segmentLayer = self.container.appendPathSublayer(
            fillColor=None,
            strokeColor=(1, 0, 0, 0.2),
            strokeWidth=10,
            strokeCap="round"
        )
        self.pointsLayer = self.container.appendBaseSublayer()
        self.insertionPointAngle = self.container.appendLineSublayer(
            strokeColor=(0, 1, 0, 0.5),
            strokeWidth=1
        )
        self.insertionPointLayer = self.container.appendOvalSublayer(
            fillColor=(0, 1, 0, 0.75),
            size=(5, 5),
            anchor=(0.5, 0.5)
        )
        self.rayAngle = self.container.appendLineSublayer(
            strokeColor=(1, 0, 0, 0.5),
            strokeWidth=1
        )
        self.foundDots = self.container.appendBaseSublayer()
        self.foundLine = self.container.appendLineSublayer(
            strokeColor=(0, 0, 1, 0.5),
            strokeWidth=2
        )

    def destroy(self):
        self.container.clearSublayers()

    def glyphEditorDidMouseMove(self, info):
        # clear
        self.pointsLayer.clearSublayers()
        self.segmentLayer.setPath(None)
        self.foundLine.setStartPoint((0, 0))
        self.foundLine.setEndPoint((0, 0))
        self.foundDots.clearSublayers()
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
        # find the closest segment
        selector = glyph.getRepresentation("doodle.GlyphSelection")
        found = selector.segmentStrokeHitByPoint_(
            defcon.Point(cursorPoint),
            radius / scale # XXX this is wrong
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
        # find the intersection
        intersection = None
        if segmentType == "line":
            intersection = bezierTools.intersectCircleLine(
                cursorPoint,
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
                cursorPoint,
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
        for point in intersection.points:
            self.pointsLayer.appendOvalSublayer(
                size=(5, 5),
                position=(point.x, point.y),
                fillColor=(1, 0, 0, 0.75),
                anchor=(0.5, 0.5)
            )
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
        # highlight the intersection
        self.insertionPointLayer.setPosition(hit)
        self.insertionPointAngle.setStartPoint(angleAnchor1)
        self.insertionPointAngle.setEndPoint(angleAnchor2)
        # calculate the angles
        angle = bezierTools.calculateAngle(angleAnchor1, angleAnchor2)
        if contour.pointInside(cursorPoint):
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
        d = 1000
        a = math.radians(perpendicular)
        rayX = hit[0] + math.cos(a) * d
        rayY = hit[1] + math.sin(a) * d
        # show the ray
        self.rayAngle.setStartPoint(hit)
        self.rayAngle.setEndPoint((rayX, rayY))
        # find the intersection
        intersections = tools.IntersectGlyphWithLine(
            glyph,
            (hit, (rayX, rayY)),
            canHaveComponent=False,
            addSideBearings=False
        )
        intersection = None
        if intersections:
            sorter = []
            for intersection in intersections:
                if intersection == hit:
                    continue
                distance = bezierTools.distanceFromPointToPoint(hit, intersection)
                sorter.append((distance, intersection))
            if sorter:
                sorter.sort()
                intersection = sorter[0][-1]
        # display the thing found to measure
        for point in intersections:
            self.foundDots.appendOvalSublayer(
                position=point,
                size=(10, 10),
                anchor=(0.5, 0.5),
                fillColor=(0, 0, 0, 0.25)
            )
        if intersection:
            self.foundLine.setStartPoint(hit)
            self.foundLine.setEndPoint(intersection)


if __name__ == '__main__':
    registerGlyphEditorSubscriber(PerpendicularTest)