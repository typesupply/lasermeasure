import math
from fontTools.misc import transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.pointPen import AbstractPointPen
from fontTools.misc import arrayTools
from fontTools.misc.fixedTools import otRound
import defcon
import AppKit
import vanilla
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


extensionID = "com.typesupply.LaserMeasure"
extensionKeyStub = extensionID + "."

# --------
# Defaults
# --------

defaults = {
    extensionKeyStub + "showMeasurementsHUD" : True,
    extensionKeyStub + "triggerCharacter" : "d",
    extensionKeyStub + "baseColor" : (0, 0.3, 1, 0.8),
    extensionKeyStub + "matchColor" : (1, 0.7, 0, 0.9),
    extensionKeyStub + "highlightStrokeWidth" : 10,
    extensionKeyStub + "highlightOpacity" : 0.2,
    extensionKeyStub + "measurementTextSize" : 12,
    extensionKeyStub + "testSelection" : True,
    extensionKeyStub + "testSegments" : True,
    extensionKeyStub + "testSegmentMatches" : True,
    extensionKeyStub + "testOffCurves" : True,
    extensionKeyStub + "testOffCurveMatches" : True,
    extensionKeyStub + "testPoints" : True,
    extensionKeyStub + "testGeneral" : True,
    extensionKeyStub + "testAnchors" : True,
}

registerExtensionDefaults(defaults)

def internalGetDefault(key):
    key = extensionKeyStub + key
    return getExtensionDefault(key)

def internalSetDefault(key, value):
    key = extensionKeyStub + key
    setExtensionDefault(key, value)

# ----------
# Subscriber
# ----------

class LaserMeasureSubscriber(subscriber.Subscriber):

    debug = False

    # Display Structure
    # -----------------
    #
    # There are two containers:
    # - one for background stuff
    # - one for foreground stuff
    #
    # Each measurement type has its own layer
    # for displaying its data. Text is compiled
    # on one layer with sublayers that are
    # positioned relative to each other and
    # the super.

    def build(self):
        window = self.getGlyphEditor()

        # Glyph Editor Overlay
        # --------------------

        self.hud = LaserMeasureNamedValuesHUD(window, self.hudAddNamedValueCallback)


        # Glyph Editor Contents
        # ---------------------

        self.containerBackground = window.extensionContainer(
            identifier=extensionKeyStub + "background",
            location="background",
            clear=True
        )
        self.containerForeground = window.extensionContainer(
            identifier=extensionKeyStub + "foreground",
            location="foreground",
            clear=True
        )
        # text
        self.textLayer = self.containerForeground.appendBaseSublayer(
            visible=True
        )
        self.measurementsTextLayer = self.textLayer.appendTextLineSublayer(
            visible=False,
            name="measurements"
        )
        self.namesTextLayer = self.textLayer.appendTextLineSublayer(
            visible=False,
            name="names"
        )
        self.selectionMeasurementsTextLayer = self.textLayer.appendTextLineSublayer(
            visible=False,
            name="selection"
        )
        self.selectionNamesTextLayer = self.textLayer.appendTextLineSublayer(
            visible=False,
            name="selectionNames"
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
        # segment
        self.segmentBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.segmentForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.segmentMatchHighlightLayer = self.segmentBackground.appendPathSublayer()
        self.segmentHighlightLayer = self.segmentBackground.appendPathSublayer()
        # handle
        self.handleBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.handleForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.handleMatchHighlightLayer = self.handleBackground.appendPathSublayer()
        self.handleHighlightLayer = self.handleBackground.appendPathSublayer()
        # points
        self.pointBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.pointForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.pointLineLayer = self.pointBackground.appendLineSublayer()
        # anchor
        self.anchorBackground = self.containerBackground.appendBaseSublayer(
            visible=False
        )
        self.anchorForeground = self.containerForeground.appendBaseSublayer(
            visible=False
        )
        self.anchorWidthLayer = self.anchorBackground.appendLineSublayer()
        self.anchorHeightLayer = self.anchorBackground.appendLineSublayer()
        # register for defaults change
        events.addObserver(
            self,
            "extensionDefaultsChanged",
            extensionID + ".defaultsChanged"
        )
        # go
        self.clearText()
        self.loadNamedMeasurements()
        self.loadDefaults()

    def loadDefaults(self):
        # load
        self.triggerCharacter = internalGetDefault("triggerCharacter")
        self.doTestSelection = internalGetDefault("testSelection")
        self.doTestSegments = internalGetDefault("testSegments")
        self.doTestSegmentMatches = internalGetDefault("testSegmentMatches")
        self.doTestOffCurves = internalGetDefault("testOffCurves")
        self.doTestOffCurveMatches = internalGetDefault("testOffCurveMatches")
        self.doTestPoints = internalGetDefault("testPoints")
        self.doTestGeneral = internalGetDefault("testGeneral")
        self.doTestAnchors = internalGetDefault("testAnchors")
        mainColor = internalGetDefault("baseColor")
        backgroundColor = UI.getDefault("glyphViewBackgroundColor")
        matchColor = internalGetDefault("matchColor")
        textSize = internalGetDefault("measurementTextSize")
        highlightOpacity = internalGetDefault("highlightOpacity")
        highlightWidth = internalGetDefault("highlightStrokeWidth")
        # build
        lineAttributes = dict(
            strokeColor=mainColor,
            strokeWidth=1
        )
        highlightAttributes = dict(
            fillColor=None,
            strokeColor=mainColor,
            strokeWidth=highlightWidth,
            strokeCap="round",
            opacity=highlightOpacity
        )
        textAttributes = dict(
            backgroundColor=mainColor,
            fillColor=backgroundColor,
            padding=(6, 3),
            cornerRadius=5,
            horizontalAlignment="left",
            verticalAlignment="top",
            pointSize=textSize,
            weight="bold",
            figureStyle="regular"
        )
        measurementTextAttributes = dict(textAttributes)
        measurementTextAttributes.update(dict(
        ))
        namesTextAttributes = dict(textAttributes)
        namesTextAttributes.update(dict(
            backgroundColor=matchColor
        ))
        selectionMeasurementsTextAttributes = dict(textAttributes)
        selectionMeasurementsTextAttributes.update(dict(
            borderColor=mainColor,
            backgroundColor=backgroundColor,
            fillColor=mainColor,
            borderWidth=1
        ))
        selectionNamesTextAttributes = dict(selectionMeasurementsTextAttributes)
        selectionNamesTextAttributes.update(dict(
            borderColor=matchColor,
            fillColor=matchColor
        ))
        # populate
        self.measurementsTextLayer.setPropertiesByName(textAttributes)
        self.namesTextLayer.setPropertiesByName(namesTextAttributes)
        self.selectionMeasurementsTextLayer.setPropertiesByName(selectionMeasurementsTextAttributes)
        self.selectionNamesTextLayer.setPropertiesByName(selectionNamesTextAttributes)
        self.outlineWidthLayer.setPropertiesByName(lineAttributes)
        self.outlineHeightLayer.setPropertiesByName(lineAttributes)
        self.segmentMatchHighlightLayer.setPropertiesByName(highlightAttributes)
        self.segmentMatchHighlightLayer.setStrokeColor(matchColor)
        self.segmentHighlightLayer.setPropertiesByName(highlightAttributes)
        self.handleMatchHighlightLayer.setPropertiesByName(highlightAttributes)
        self.handleMatchHighlightLayer.setStrokeColor(matchColor)
        self.handleHighlightLayer.setPropertiesByName(highlightAttributes)
        self.pointLineLayer.setPropertiesByName(lineAttributes)
        self.anchorWidthLayer.setPropertiesByName(lineAttributes)
        self.anchorHeightLayer.setPropertiesByName(lineAttributes)
        self.hud.update()

    def loadNamedMeasurements(self):
        libKey = extensionID + ".measurements"
        font = self.getFont()
        stored = font.lib.get(libKey, {})
        self.hud.setItems(stored)
        self.namedWidthMeasurements = {}
        self.namedHeightMeasurements = {}
        self.namedWidthHeightMeasurements = {}
        for name, data in stored.items():
            width = data.get("width")
            height = data.get("height")
            key = None
            location = None
            if width is not None and height is not None:
                location = self.namedWidthHeightMeasurements
                key = (width, height)
            elif width is not None:
                location = self.namedWidthMeasurements
                key = width
                name = f"W: {name}"
            elif height is not None:
                location = self.namedHeightMeasurements
                key = height
                name = f"H: {name}"
            if key not in location:
                location[key] = []
            location[key].append(name)
        dicts = [
            self.namedWidthMeasurements,
            self.namedHeightMeasurements,
            self.namedWidthHeightMeasurements
        ]
        for d in dicts:
            for d, v in d.items():
                v.sort()

    def destroy(self):
        self.containerBackground.clearSublayers()
        self.containerForeground.clearSublayers()
        events.removeObserver(
            self,
            extensionID + ".defaultsChanged"
        )

    def hideLayers(self):
        self.containerBackground.setVisible(False)
        self.containerForeground.setVisible(False)
        self.clearText()

    # Objects
    # -------

    def getFont(self):
        return self.getGlyphEditor().document.getFont()

    # Events
    # ------

    def roboFontDidChangePreferences(self, info):
        self.loadDefaults()

    def extensionDefaultsChanged(self, event):
        self.loadDefaults()

    def fontMeasurementsChanged(self, info):
        self.loadNamedMeasurements()

    wantsMeasurements = False
    currentDisplayFocalPoint = None
    currentMeasurements = None
    currentSelectionMeasurements = None
    currentNames = None
    currentSelectionNames = None

    def glyphEditorDidKeyDown(self, info):
        deviceState = info["deviceState"]
        if deviceState["keyDownWithoutModifiers"] != self.triggerCharacter:
            self.wantsMeasurements = False
        else:
            self.wantsMeasurements = True
            selectionState = False
            glyph = info["glyph"]
            if self.doTestSelection:
                selectionState = self.measureSelection(
                    glyph,
                    deviceState
                )
                self.findSelectionNames()
                if selectionState:
                    editor = info["glyphEditor"]
                    view = editor.getGlyphView()
                    position = view._getMousePosition()
                    position = view._converPointFromViewToGlyphSpace(position)
                    position = (position.x, position.y)
                    if position != self.currentDisplayFocalPoint:
                        self.currentDisplayFocalPoint = position
                        self.updateText()
            setCursorMode("searching")
            self.hud.show(self.currentSelectionMeasurements is not None)

    def glyphEditorDidKeyUp(self, info):
        self.wantsMeasurements = False
        self.hideLayers()
        setCursorMode(None)
        self.hud.hide()

    def glyphEditorDidMouseDown(self, info):
        self.wantsMeasurements = False
        self.hideLayers()
        setCursorMode(None)

    def glyphEditorDidMouseMove(self, info):
        if not self.wantsMeasurements:
            return
        self.selectionMeasurementsTextLayer.setVisible(False)
        glyph = info["glyph"]
        if not glyph.bounds:
            self.hideLayers()
            return
        deviceState = info["deviceState"]
        point = tuple(info["locationInGlyph"])
        self.currentDisplayFocalPoint = point
        self.currentMeasurements = None
        anchorState = False
        handleState = False
        segmentState = False
        pointState = False
        outlineState = False
        cursorMode = "searching"
        while 1:
            if self.doTestAnchors:
                if self.measureAnchors(point, glyph, deviceState):
                    anchorState = True
                    cursorMode = "hit"
                    break
            if self.doTestOffCurves:
                if self.measureHandles(point, glyph, deviceState):
                    handleState = True
                    cursorMode = "hit"
                    break
            if self.doTestSegments:
                if self.measureSegments(point, glyph, deviceState):
                    segmentState = True
                    cursorMode = "hit"
                    break
            if self.doTestPoints:
                if self.measurePoints(point, glyph, deviceState):
                    pointState = True
                    cursorMode = "hit"
                    break
            if self.doTestGeneral:
                if self.measureOutline(point, glyph, deviceState):
                    outlineState = True
                    break
            break
        self.findNames()
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
        self.updateText()

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
            yBeforeFallback = min((yBeforeFallback, y))
            yAfterFallback = max((yAfterFallback, y))
        return xBeforeFallback, yBeforeFallback, xAfterFallback, yAfterFallback

    def hudAddNamedValueCallback(self, sender):
        from .namedValuesSheet import NamedValuesSheetController
        font = self.getFont()
        measurements = self.currentSelectionMeasurements
        if not measurements:
            return
        width, height = measurements
        if width == 0:
            width = None
        if height == 0:
            height = None
        items = font.lib.get(extensionKeyStub + "measurements", {})
        i = 0
        while 1:
            i += 1
            name = f"Name{i}"
            if name in items:
                continue
            item = {}
            if width is not None:
                item["width"] = width
            if height is not None:
                item["height"] = height
            items[name] = item
            break
        font.lib[extensionKeyStub + "measurements"] = items
        self.glyphEditorDidKeyUp({})
        window = UI.CurrentFontWindow()
        NamedValuesSheetController(window.w, font)

    # Text
    # ----

    def clearText(self):
        self.currentDisplayFocalPoint = None
        self.currentMeasurements = None
        self.currentSelectionMeasurements = None
        self.currentNames = None
        self.currentSelectionNames = None

    def updateText(self):
        cursorOffset = 7
        textBlockOffset = 5
        if self.currentDisplayFocalPoint is not None:
            x, y = self.currentDisplayFocalPoint
            x += cursorOffset
            y -= cursorOffset
            self.textLayer.setPosition((x, y))
        displayOrder = [
            ("measurements", self.currentMeasurements, self.measurementsTextLayer, formatWidthHeightString),
            ("names", self.currentNames, self.namesTextLayer, formatNames),
            ("selection", self.currentSelectionMeasurements, self.selectionMeasurementsTextLayer, formatWidthHeightString),
            ("selectionNames", self.currentSelectionNames, self.selectionNamesTextLayer, formatNames)
        ]
        position = (
            dict(
                point="left",
                relative="super"
            ),
            dict(
                point="top",
                relative="super"
            )
        )
        visible = []
        hidden = []
        for (name, contents, layer, formatter) in displayOrder:
            if not contents:
                hidden.append(layer)
                continue
            layer.setText(
                formatter(*contents)
            )
            x = dict(position[0])
            y = dict(position[1])
            layer.setPosition((x, y))
            visible.append(layer)
            position[0]["relative"] = name
            position[1]["relative"] = name
            position[1]["relativePoint"] = "bottom"
            position[1]["offset"] = -textBlockOffset
        for layer in hidden:
            layer.setVisible(False)
        for layer in visible:
            layer.setVisible(True)
        if not self.containerForeground.getVisible():
            self.containerForeground.setVisible(True)

    # Names
    # -----

    def findNames(self):
        self.currentNames = None
        if not self.currentMeasurements:
            return
        w, h = self.currentMeasurements
        names = self.namedWidthHeightMeasurements.get((w, h), [])
        names += self.namedWidthMeasurements.get(w, [])
        names += self.namedHeightMeasurements.get(h, [])
        if names:
            self.currentNames = names

    def findSelectionNames(self):
        self.currentSelectionNames = None
        if not self.currentSelectionMeasurements:
            return
        w, h = self.currentSelectionMeasurements
        names = self.namedWidthHeightMeasurements.get((w, h), [])
        names += self.namedWidthMeasurements.get(w, [])
        names += self.namedHeightMeasurements.get(h, [])
        if names:
            self.currentSelectionNames = names

    # Measurements
    # ------------
    #
    # These perform measurements and update the contents
    # of their layers as needed. (These do not update text
    # because it is more efficient to do that at the end.)
    # Each of these must return True if they found something
    # to measure. This will be used to stop further searching
    # and know which layers should be visible.
    #
    # These should place the measurements they find at
    # self.currentMeasurements and  the text updating
    # system will pull and format the data as needed.

    def measureSelection(self,
            glyph,
            deviceState
        ):
        xValues = set()
        yValues = set()
        for contour in glyph.selectedContours:
            for point in contour.selectedPoints:
                xValues.add(point.x)
                yValues.add(point.y)
        if len(xValues) < 2 and len(yValues) < 2:
            return
        xMin = min(xValues)
        xMax = max(xValues)
        yMin = min(yValues)
        yMax = max(yValues)
        width = xMax - xMin
        height = yMax - yMin
        measurements = (width, height)
        if measurements == self.currentSelectionMeasurements:
            return
        self.currentSelectionMeasurements = (width, height)
        return True

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
                with self.measurementsTextLayer.propertyGroup():
                    self.currentDisplayFocalPoint = (ax, ay)
                    self.currentMeasurements = (width, height)
                return True

    def measureHandles(self,
            point,
            glyph,
            deviceState
        ):
        hit = measureSegmentsAndHandles(
            point,
            glyph.getRepresentation(extensionKeyStub + "handlesAsLines"),
            self.handleHighlightLayer
        )
        if not self.doTestOffCurveMatches:
            self.handleMatchHighlightLayer.setVisible(False)
            return bool(hit)
        if hit:
            segmentType, points, measurements = hit
            self._findMatchingHandles(
                points,
                glyph
            )
            self.handleMatchHighlightLayer.setVisible(True)
            self.currentMeasurements = measurements
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
        handles = glyph.getRepresentation(extensionKeyStub + "handles")
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
            self.segmentHighlightLayer
        )
        if not self.doTestSegmentMatches:
            self.segmentMatchHighlightLayer.setVisible(False)
            return bool(hit)
        if hit:
            segmentType, segmentPoints, measurements = hit
            self._findMatchingSegments(
                segmentType,
                segmentPoints,
                glyph
            )
            self.segmentMatchHighlightLayer.setVisible(True)
            self.currentMeasurements = measurements
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
        segments = glyph.getRepresentation(extensionKeyStub + "segments")
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
        pen = glyph.getRepresentation(extensionKeyStub + "nearestPointSearcher")
        points = pen.find(glyph, point)
        if not points:
            return
        point1, point2 = points
        x1, y1 = point1
        x2, y2 = point2
        width = int(round(abs(x1 - x2)))
        height = int(round(abs(y1 - y2)))
        self.pointLineLayer.setStartPoint(point1)
        self.pointLineLayer.setEndPoint(point2)
        self.currentMeasurements = (width, height)
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
        with self.measurementsTextLayer.propertyGroup():
            self.currentMeasurements = (width, height)
        return True


try:
    subscriber.registerSubscriberEvent(
        subscriberEventName=extensionID + ".measurementsChanged",
        methodName="fontMeasurementsChanged",
        lowLevelEventNames=[extensionID + ".measurementsChanged"],
        dispatcher="roboFont",
        delay=0.1
    )
except AssertionError:
    pass

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

def formatWidthHeightString(width, height):
    width = otRound(width)
    height = otRound(height)
    s = f"{width} × {height}"
    return s

def formatNames(*args):
    return "\n".join(args)

# Adjacent Values
# ---------------

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
        highlightLayer
    ):
    x, y = point
    selector = glyph.getRepresentation("doodle.GlyphSelection")
    point = defcon.Point(point)
    found = selector.segmentStrokeHitByPoint_(point, 5)
    if not found:
        highlightLayer.setVisible(False)
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
    highlightLayer.setVisible(True)
    return segmentType, points, (width, height)


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

    def addComponent(self, *args, **kwargs):
        pass


def handlesAsLinesGlyphFactory(glyph):
    outGlyph = RGlyph()
    pen = HandlesToLinesPen(outGlyph.getPen())
    glyph.draw(pen)
    return outGlyph

defcon.registerRepresentationFactory(
    defcon.Glyph,
    extensionKeyStub + "handlesAsLines",
    handlesAsLinesGlyphFactory
)


# Collinear Points
# ----------------

def _formatCoordinateForSearching(x, y):
    x = int(round(x))
    y = int(round(y))
    return f"{x},{y}"

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


def nearestPointSearcherGlyphFactory(glyph):
    pen = NearestPointsPointPen()
    glyph.drawPoints(pen)
    return pen

defcon.registerRepresentationFactory(
    defcon.Glyph,
    extensionKeyStub + "nearestPointSearcher",
    nearestPointSearcherGlyphFactory
)

def normalizeAngle(angle):
    if angle < 0:
        angle = 360 + angle
    return angle

def roundTo(value, multiple):
    value = int(round(value / float(multiple))) * multiple
    return value

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
        self.firstPoint = pt
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
        if self.prevPoint != self.firstPoint:
            self.segments.append(("line", (self.prevPoint, self.firstPoint)))
        self.firstPoint = None
        self.prevPoint = None

    def _endPath(self):
        self.firstPoint = None
        self.prevPoint = None


def segmentsGlyphFactory(glyph):
    segmentsPen = SegmentsPen()
    glyph.draw(segmentsPen)
    return segmentsPen.segments

defcon.registerRepresentationFactory(
    defcon.Glyph,
    extensionKeyStub + "segments",
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
    extensionKeyStub + "handles",
    handlesGlyphFactory
)


# ---
# HUD
# ---

class LaserMeasureNamedValuesHUD:

    def __init__(self, glyphEditor, buttonCallback):
        self.items = {}

        group = vanilla.Group((0, 0, 0, 0))
        group.background = merz.MerzView((0, 0, 0, 0))
        group.button = vanilla.ImageButton(
            (-20, 0, 20, 20),
            bordered=False,
            callback=buttonCallback
        )
        group.textView = merz.MerzView((0, 25, 0, 0))

        self.group = group
        self.background = group.background.getMerzContainer()
        self.button = group.button
        self.textView = group.textView
        self.textContainer = group.textView.getMerzContainer()

        self.update()
        group.show(False)

        glyphEditor.addGlyphEditorSubview(
            group,
            identifier=extensionID + ".LaserMeasureNamedValuesHUD",
            clear=True
        )

    def show(self, showButton):
        if self.button.isVisible() != showButton:
            self.button.show(showButton)
        if not self.group.isVisible():
            self.group.show(True)

    def hide(self):
        self.group.show(False)

    def setItems(self, items):
        self.items = items
        self.update()

    def update(self):
        color = getExtensionDefault(extensionID + ".matchColor")
        r, g, b, a = color
        lineColor = (r, g, b, a * 0.25)
        backgroundColor = tuple(UI.getDefault("glyphViewBackgroundColor"))
        r, g, b, a = backgroundColor
        backgroundColor = (r, g, b, 0.8)

        # Background
        self.background.setBackgroundColor(backgroundColor)

        # Button
        image = AppKit.NSImage.alloc().initWithSize_((20, 20))
        path = AppKit.NSBezierPath.bezierPathWithOvalInRect_(((2, 2), (16, 16)))
        path.moveToPoint_((10, 6))
        path.lineToPoint_((10, 14))
        path.moveToPoint_((6, 10))
        path.lineToPoint_((14, 10))
        path.setLineWidth_(1)
        path.setLineCapStyle_(AppKit.NSLineCapStyleRound)
        image.lockFocus()
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*backgroundColor).set()
        path.fill()
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*color).set()
        path.stroke()
        image.unlockFocus()
        self.button.setImage(imageObject=image)

        # Text
        items = self.items
        unpacked = []
        for name, item in items.items():
            width = item.get("width")
            if width is None:
                width = ""
            else:
                width = str(width)
            height = item.get("height")
            if height is None:
                height = ""
            else:
                height = str(height)
            item = dict(name=name, width=width, height=height)
            unpacked.append((name.lower(), width, height, item))
        unpacked.sort()
        items = [i[-1] for i in unpacked]

        pointSize = 12
        textAttributes = dict(
            pointSize=pointSize,
            padding=(0, pointSize / 4),
            horizontalAlignment="right",
            weight="medium",
            figureStyle="tabular",
            fillColor=color
        )
        font = merz.text.makeFont(
            "system",
            weight=textAttributes["weight"],
            figureStyle=textAttributes["figureStyle"],
            pointSize=textAttributes["pointSize"],
        )

        nameWidths = []
        numberWidths = []
        for item in items:
            nameWidths.append(calculateTextWidth(item["name"], font))
            numberWidths.append(calculateTextWidth(item["width"], font))
            numberWidths.append(calculateTextWidth(item["height"], font))

        buttonWidth = 20
        buttonHeight = 30
        pointSize = textAttributes["pointSize"]
        nameWidth = 0
        numberWidth = 0
        if items:
            nameWidth = max(nameWidths)
            numberWidth = max(numberWidths)
        rowHeight = pointSize * 2
        columnSpacing = pointSize * 0.75
        totalWidth = nameWidth + columnSpacing + numberWidth + columnSpacing + numberWidth
        totalWidth = max((buttonWidth, totalWidth))
        textViewHeight = rowHeight * (len(items) + 1)
        totalHeight = textViewHeight + buttonHeight
        xStart = -25
        yStart = 10

        x, y, w, h = self.group.getPosSize()
        self.group.setPosSize((-totalWidth + xStart, yStart, totalWidth, totalHeight))
        if items:
            items.insert(0, dict(name="", width="W", height="H"))

        self.textContainer.clearSublayers()

        top = textViewHeight

        if items:
            self.textContainer.appendBaseSublayer(
                name=f"topLine",
                position=(0, top - 1),
                size=(totalWidth, 1),
                borderColor=lineColor,
                borderWidth=1
            )

        for i, item in enumerate(items):
            name = item["name"]
            width = item["width"]
            height = item["height"]
            y = top - rowHeight
            # name
            self.textContainer.appendTextBoxSublayer(
                name=f"name{i}",
                text=name,
                position=(0, y),
                size=(nameWidth, rowHeight),
                **textAttributes
            )
            # width
            self.textContainer.appendTextBoxSublayer(
                name=f"width{i}",
                text=width,
                position=(
                    nameWidth + columnSpacing,
                    y
                ),
                size=(numberWidth, rowHeight),
                **textAttributes
            )
            # height
            self.textContainer.appendTextBoxSublayer(
                name=f"height{i}",
                text=height,
                position=(
                    nameWidth + columnSpacing + numberWidth + columnSpacing,
                    y
                ),
                size=(numberWidth, rowHeight),
                **textAttributes
            )
            # line
            self.textContainer.appendBaseSublayer(
                name=f"line{i}",
                position=(0, y),
                size=(totalWidth, 1),
                borderColor=lineColor,
                borderWidth=1
            )
            top -= rowHeight


def calculateTextWidth(text, font):
    attrs = {
        AppKit.NSFontAttributeName : font
    }
    s = AppKit.NSAttributedString.alloc().initWithString_attributes_(text, attrs)
    width = s.size()[0]
    return width


# --
# Go
# --

def main():
    subscriber.registerGlyphEditorSubscriber(LaserMeasureSubscriber)

if __name__ == "__main__":
    if AppKit.NSUserName() in ("tal", "talleming"):
        for key in defaults.keys():
            removeExtensionDefault(key)
        registerExtensionDefaults(defaults)
    LaserMeasureSubscriber.debug = True
    main()