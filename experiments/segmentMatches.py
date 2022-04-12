import math
import defcon
from fontTools.misc import transform
from fontTools.pens.basePen import BasePen

extensionKeyStub = "com.typesupply.LaserMeasure."

class RelativeSegment:

    def __init__(self, type, segment):
        if type == "move":
            type = "line"
        self.type = type
        self.original = tuple(segment)
        self._base = None
        self._reversedBase = None

    def __repr__(self):
        o = repr(self.original)
        b = repr(self.base)
        return f"{o}-{b}"

    def __hash__(self):
        return hash(self.base)

    def _get_base(self):
        if self._base is None:
            self._base = makePointsRelative(self.original)
        return self._base

    base = property(_get_base)

    def _get_reversedBase(self):
        if self._reversedBase is None:
            points = reversePoints(self.original)
            self._reversedBase = makePointsRelative(points)
        return self._reversedBase

    reversedBase = property(_get_reversedBase)

    def __cmp__(self, other):
        return self.__eq__(other)

    def __eq__(self, other):
        segment = other.base
        # obvious mismatches
        if other.type != self.type:
            return False
        if len(segment) != len(self.original):
            return False
        # obvious matches
        if segment == self.base:
            return True
        if segment == self.reversedBase:
            return True
        # transform and compare
        base = self.base
        reversedBase = self.reversedBase
        transformers = (
            ("rotated90", [base, rotate90Transform.transformPoints]),
            ("rotated180", [base, rotate180Transform.transformPoints]),
            ("rotated270", [base, rotate270Transform.transformPoints]),
            ("flippedHorizontal", [base, flipHorizontalTransform.transformPoints]),
            ("flippedVertical", [base, flipVerticalTransform.transformPoints]),
            ("reversedRotated90", [reversedBase, rotate90Transform.transformPoints]),
            ("reversedRotated180", [reversedBase, rotate180Transform.transformPoints]),
            ("reversedRotated270", [reversedBase, rotate270Transform.transformPoints]),
            ("reversedFlippedHorizontal", [reversedBase, flipHorizontalTransform.transformPoints]),
            ("reversedFlippedVertical", [reversedBase, flipVerticalTransform.transformPoints]),
        )
        for attr, (points, transformer) in transformers:
            if not hasattr(self, attr):
                transformed = tuple(transformer(points))
                setattr(self, attr, transformed)
            transformed = getattr(self, attr)
            if segment == transformed:
                return True
        return False


class RelativeSegmentsPen(BasePen):

    def __init__(self):
        super().__init__()
        self.prevPoint = None
        self.segments = []

    def _moveTo(self, pt):
        self.firstPoint = pt
        self.prevPoint = pt

    def _lineTo(self, pt):
        self.segments.append(RelativeSegment("line", (self.prevPoint, pt)))
        self.prevPoint = pt

    def _curveToOne(self, pt1, pt2, pt3):
        self.segments.append(RelativeSegment("curve", (self.prevPoint, pt1, pt2, pt3)))
        self.prevPoint = pt3

    def _qCurveToOne(self, pt1, pt2):
        self.segments.append(RelativeSegment("qcurve", (self.prevPoint, pt1, pt2)))
        self.prevPoint = pt2

    def _closePath(self):
        if self.prevPoint != self.firstPoint:
            self.segments.append(RelativeSegment("line", (self.prevPoint, self.firstPoint)))
        self.firstPoint = None
        self.prevPoint = None

    def _endPath(self):
        self.firstPoint = None
        self.prevPoint = None

    def addComponent(self, *args, **kwargs):
        pass


def relativeSegmentsGlyphFactory(glyph):
    segmentsPen = RelativeSegmentsPen()
    glyph.draw(segmentsPen)
    return segmentsPen.segments

defcon.registerRepresentationFactory(
    defcon.Glyph,
    extensionKeyStub + "relativeSegments",
    relativeSegmentsGlyphFactory
)

def segmentGroupsGlyphFactory(glyph):
    segments = glyph.getRepresentation(extensionKeyStub + "relativeSegments")
    tree = {}
    for segment in segments:
        key = None
        for candidateKey in tree.keys():
            if candidateKey == segment:
                key = candidateKey
                break
        if key is None:
            key = segment
        if key not in tree:
            tree[key] = []
        tree[key].append(segment)
    grouped = []
    for key, segments in tree.items():
        if len(segments) < 2:
            continue
        grouped.append(segments)
    return grouped


defcon.registerRepresentationFactory(
    defcon.Glyph,
    extensionKeyStub + "segmentGroups",
    segmentGroupsGlyphFactory
)


def makePointRelative(point, basePoint):
    px, py = point
    bx, by = basePoint
    x = px - bx
    y = py - by
    return (x, y)

def makePointsRelative(points):
    points = [(0, 0)] + [
        makePointRelative(p, points[0])
        for p in points[1:]
    ]
    return tuple(points)

def reversePoints(points):
    return tuple(reversed(points))

rotate90Transform = transform.Transform().rotate(math.radians(90))
rotate180Transform = transform.Transform().rotate(math.radians(180))
rotate270Transform = transform.Transform().rotate(math.radians(270))
flipHorizontalTransform = transform.Scale(1, -1)
flipVerticalTransform = transform.Scale(-1, 1)

# ----
# Test
# ----

from drawBot.drawBotDrawingTools import _drawBotDrawingTool as bot

defaultColorRotation = [
    (1, 0.5, 0, 0.5),
    (0, 1, 0, 0.5),
    (1, 0, 1, 0.5),
    (0, 0, 1, 0.5),
    (1, 0, 0, 0.5),
    (0, 1, 1, 0.5)
]

bot.newDrawing()

padding = 100

font = CurrentFont()
for name in font.glyphOrder:
    # if name != "O":
    #     continue
    glyph = font[name]
    if not len(glyph):
        continue
    glyph.asDefcon().destroyAllRepresentations()
    groups = segmentGroupsGlyphFactory(glyph)
    width = padding + glyph.width + padding
    height = padding + font.info.unitsPerEm + padding
    bot.newPage(width, height)
    bot.translate(padding, -font.info.descender + padding)
    bot.fill(None)
    colors = list(defaultColorRotation)
    for group in groups:
        pen = bot.BezierPath()
        color = colors.pop(0)
        colors.append(color)
        bot.stroke(*color)
        bot.strokeWidth(15)
        bot.lineCap("round")
        for segment in group:
            pen.moveTo(segment.original[0])
            if segment.type == "line":
                pen.lineTo(segment.original[1])
            elif segment.type == "curve":
                pen.curveTo(*segment.original[1:])
            pen.endPath()
        bot.drawPath(pen)
    bot.strokeWidth(1)
    bot.stroke(0, 0, 0, 1)
    pen = bot.BezierPath()
    glyph.draw(pen, components=False)
    bot.drawPath(pen)
