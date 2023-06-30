import math
import statistics
from fontTools.misc import transform
from fontTools.pens.basePen import BasePen
from fontTools.pens.pointPen import AbstractPointPen
from fontTools.misc import arrayTools
from fontTools.misc.fixedTools import otRound
import defcon
import AppKit
import Quartz
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
    extensionKeyStub + "highlightStrokeWidth" : 7,
    extensionKeyStub + "highlightOpacity" : 0.3,
    extensionKeyStub + "highlightAnimate" : False,
    extensionKeyStub + "highlightAnimationDuration" : 1,
    extensionKeyStub + "persistentMeasurementsColor" : (1, 0.5, 0, 1),
    extensionKeyStub + "persistentMeasurementsStrokeWidth" : 15,
    extensionKeyStub + "persistentMeasurementsOpacity" : 1.0,
    extensionKeyStub + "measurementTextSize" : 12,
    extensionKeyStub + "testSelection" : True,
    extensionKeyStub + "testSegments" : True,
    extensionKeyStub + "testSegmentMatches" : True,
    extensionKeyStub + "testOffCurves" : True,
    extensionKeyStub + "testOffCurveMatches" : True,
    extensionKeyStub + "testPoints" : True,
    extensionKeyStub + "testGeneral" : True,
    extensionKeyStub + "testAnchors" : True,
    extensionKeyStub + "autoTestSegmentMatches" : True,
    extensionKeyStub + "showPersistentMeasurements" : True,
    extensionKeyStub + "matchColors" : [
        (1, 0.6, 0, 0.9),
        (0.3, 1, 0, 0.9),
        (0, 1, 0.8, 0.9),
        (0.6, 0.5, 1, 0.9),
        (1, 0.5, 0.5, 0.9),
        (0.9, 0.9, 0, 0.9),
        (0.5, 0.5, 0.5, 0.9)
    ],
}

persistentMakeTrigger = "\r" # return
persistentBreakTrigger = "\u001b" # escape

cursorOffset = 7
textBlockOffset = 5

registerExtensionDefaults(defaults)

def internalGetDefault(key):
    key = extensionKeyStub + key
    return getExtensionDefault(key)

def internalSetDefault(key, value):
    key = extensionKeyStub + key
    setExtensionDefault(key, value)

# ------------------
# Persistent Storage
# ------------------

persistentPointsKey = extensionKeyStub + "persistentPointMeasurements"

def _getPointIdentifiers(points):
    return tuple(sorted([point.getIdentifier() for point in points]))

def _getIdentifierToPointMapping(glyph):
    # XXX make this a factory
    identifierToPointMapping = {}
    for contour in glyph:
        for point in contour.points:
            if point.identifier is None:
                continue
            identifierToPointMapping[point.identifier] = point
    return identifierToPointMapping

def storePersistentPointMeasurementReferences(glyph, points):
    f"""
    Store the identifiers of points in the glyph lib
    as a peristent measurement reference. The points
    will be stored at the key:

        {persistentPointsKey}

    The identifiers will be stored as a sorted list
    of identifiers. The sorting is required.
    """
    identifiers = _getPointIdentifiers(points)
    if persistentPointsKey not in glyph.lib:
        glyph.lib[persistentPointsKey] = []
    existing = glyph.lib[persistentPointsKey]
    if identifiers not in existing:
        existing.append(identifiers)
        glyph.lib[persistentPointsKey] = existing

def removePersistentPointMeasurementReferences(glyph, points):
    """
    Remove the identifiers of points in the glyph
    lib persistent measurement references.
    """
    if persistentPointsKey not in glyph.lib:
        return
    identifiers = _getPointIdentifiers(points)
    existing = glyph.lib[persistentPointsKey]
    if identifiers in existing:
        existing.remove(identifiers)
    if existing:
        glyph.lib[persistentPointsKey] = existing
    else:
        del glyph.lib[persistentPointsKey]

def clearPersistentPointMeasurementReferences(glyph, points):
    """
    Clear all persistent point measurements in the glyph.
    """
    if persistentPointsKey in glyph.lib:
        del glyph.lib[persistentPointsKey]

def getPersistentPointMeasurementReferences(glyph):
    """
    Return all persistent measurement references.
    """
    return glyph.lib.get(persistentPointsKey, [])

def getPersistentPointMeasurements(
        glyph,
        namedWidthHeightMeasurements=None,
        namedWidthMeasurements=None,
        namedHeightMeasurements=None
    ):
    """
    Get measurement data about all linked points
    in the glyph. The data will be a list of
    dictionaries with this form:

        {
            points : list of point objects
            positions : list of (x, y) for the points
            measurements : (width, height)
            names: matched named measurements
        }
    """
    if namedWidthHeightMeasurements is None:
        font = glyph.font
        namedWidthHeightMeasurements, namedWidthMeasurements, namedHeightMeasurements = loadNamedMeasurements(font)
    links = getPersistentPointMeasurementReferences(glyph)
    if not links:
        return []
    identifierToPointMapping = _getIdentifierToPointMapping(glyph)
    measurements = []
    for link in links:
        linkedPoints = []
        for identifier in link:
            point = identifierToPointMapping.get(identifier)
            if point is None:
                # XXX missing point.
                # skip? destroy this link?
                continue
            linkedPoints.append(point)
        if len(linkedPoints) >= 2:
            linkedPointMeasurements = measurePoints(linkedPoints)
            if linkedPointMeasurements is None:
                continue
            data = dict(
                points=linkedPoints,
                positions=[point.position for point in linkedPoints],
                measurements=linkedPointMeasurements,
                names=findMatchingNamedMeasurements(
                    linkedPointMeasurements,
                    namedWidthHeightMeasurements=namedWidthHeightMeasurements,
                    namedWidthMeasurements=namedWidthMeasurements,
                    namedHeightMeasurements=namedHeightMeasurements
                )
            )
            measurements.append(data)
    return measurements

# ----------
# Subscriber
# ----------

emptyPath = Quartz.CGPathCreateMutable()

class LaserMeasureSubscriber(subscriber.Subscriber):

    debug = False

    # Display Structure
    # -----------------
    #
    # There are three containers:
    # - passive (background): visible between key up and key down
    # - active (background): visible with key down and mouse move
    # - text (foreground): visible between key up and key down
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

        self.hud = LaserMeasureNamedValuesHUD(
            window,
            self.hudAddNamedValueCallback,
            self.hudShowNamedValuesCallback
        )

        # Glyph Editor Contents
        # ---------------------

        self.activeContainer = window.extensionContainer(
            identifier=extensionKeyStub + "background",
            location="background",
            clear=True
        )
        self.passiveContainer = window.extensionContainer(
            identifier=extensionKeyStub + "autoBackground",
            location="background",
            clear=True
        )
        self.textContainer = window.extensionContainer(
            identifier=extensionKeyStub + "foreground",
            location="foreground",
            clear=True
        )
        # persistent measurements
        self.persistentMeasurementsBaseLayer = self.passiveContainer.appendBaseSublayer(
            visible=True
        )
        self.persistentMeasurementsTextBaseLayer = self.textContainer.appendBaseSublayer(
            visible=True
        )
        # auto segment matches
        self.autoSegmentMatchBaseLayer = self.passiveContainer.appendBaseSublayer(
            visible=True
        )
        # text
        self.textBaseLayer = self.textContainer.appendBaseSublayer(
            visible=True
        )
        self.measurementsTextContainer = self.textBaseLayer.appendBaseSublayer(
            visible=False
        )
        self.measurementsTextLayer = self.measurementsTextContainer.appendTextLineSublayer(
            visible=False,
            name="measurements"
        )
        self.namesTextLayer = self.measurementsTextContainer.appendTextLineSublayer(
            visible=False,
            name="names"
        )
        self.selectionMeasurementsTextLayer = self.measurementsTextContainer.appendTextLineSublayer(
            visible=False,
            name="selection"
        )
        self.selectionNamesTextLayer = self.measurementsTextContainer.appendTextLineSublayer(
            visible=False,
            name="selectionNames"
        )
        # outline
        self.outlineBaseLayer = self.activeContainer.appendBaseSublayer(
            visible=False
        )
        self.outlineWidthLayer = self.outlineBaseLayer.appendLineSublayer()
        self.outlineHeightLayer = self.outlineBaseLayer.appendLineSublayer()
        # segment
        self.segmentBaseLayer = self.activeContainer.appendBaseSublayer(
            visible=False
        )
        self.segmentMatchHighlightLayer = self.segmentBaseLayer.appendPathSublayer(
            name="segmentMatchHighlightLayer"
        )
        self.segmentHighlightLayer = self.segmentBaseLayer.appendPathSublayer()
        # handle
        self.handleBaseLayer = self.activeContainer.appendBaseSublayer(
            visible=False
        )
        self.handleMatchHighlightLayer = self.handleBaseLayer.appendPathSublayer(
            name="handleMatchHighlightLayer"
        )
        self.handleHighlightLayer = self.handleBaseLayer.appendPathSublayer()
        # points
        self.pointBaseLayer = self.activeContainer.appendBaseSublayer(
            visible=False
        )
        self.pointHighlightLayer = self.pointBaseLayer.appendLineSublayer()
        # anchor
        self.anchorBaseLayer = self.activeContainer.appendBaseSublayer(
            visible=False
        )
        self.anchorWidthLayer = self.anchorBaseLayer.appendLineSublayer()
        self.anchorHeightLayer = self.anchorBaseLayer.appendLineSublayer()
        # register for defaults change
        events.addObserver(
            self,
            "extensionDefaultsChanged",
            extensionID + ".defaultsChanged"
        )
        
        self.point = (0,0)
        # go
        self.clearText()
        self.loadNamedMeasurements()
        self.loadDefaults()
        
    def loadDefaults(self):
        # load
        self.showMeasurementsHUD = internalGetDefault("showMeasurementsHUD")
        self.triggerCharacter = internalGetDefault("triggerCharacter")
        self.doTestSelection = internalGetDefault("testSelection")
        self.doTestSegments = internalGetDefault("testSegments")
        self.doTestSegmentMatches = internalGetDefault("testSegmentMatches")
        self.doTestOffCurves = internalGetDefault("testOffCurves")
        self.doTestOffCurveMatches = internalGetDefault("testOffCurveMatches")
        self.doTestPoints = internalGetDefault("testPoints")
        self.doTestGeneral = internalGetDefault("testGeneral")
        self.doTestAnchors = internalGetDefault("testAnchors")
        self.doAutoTestSegmentMatches = internalGetDefault("autoTestSegmentMatches")
        self.showPersistentMeasurements = internalGetDefault("showPersistentMeasurements")
        mainColor = internalGetDefault("baseColor")
        backgroundColor = UI.getDefault("glyphViewBackgroundColor")
        matchColors = internalGetDefault("matchColors")
        textSize = internalGetDefault("measurementTextSize")
        highlightOpacity = internalGetDefault("highlightOpacity")
        highlightWidth = internalGetDefault("highlightStrokeWidth")
        persistentMeasurementsColor = internalGetDefault("persistentMeasurementsColor")
        persistentMeasurementsStrokeWidth = internalGetDefault("persistentMeasurementsStrokeWidth")
        persistentMeasurementsOpacity = internalGetDefault("persistentMeasurementsOpacity")
        if not matchColors:
            matchColors = [mainColor]
        self.highlightWidth1 = highlightWidth
        self.highlightWidth2 = highlightWidth * 3
        self.highlightAnimate = internalGetDefault("highlightAnimate")
        self.highlightAnimationDuration = internalGetDefault("highlightAnimationDuration")
        self.matchColors = matchColors
        self.matchStrokeWidth = highlightWidth
        self.matchStrokeOpacity = highlightOpacity
        self.persistentMeasurementsColor = persistentMeasurementsColor
        self.persistentMeasurementsStrokeWidth = persistentMeasurementsStrokeWidth
        self.persistentMeasurementsOpacity = persistentMeasurementsOpacity
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
        self.genericTextAttributes = textAttributes = dict(
            backgroundColor=mainColor,
            fillColor=backgroundColor,
            padding=(6, 3),
            cornerRadius=5,
            horizontalAlignment="left",
            verticalAlignment="top",
            pointSize=textSize,
            weight="bold",
            figureStyle="tabular"
        )
        measurementTextAttributes = dict(textAttributes)
        measurementTextAttributes.update(dict(
        ))
        namesTextAttributes = dict(textAttributes)
        selectionMeasurementsTextAttributes = dict(textAttributes)
        selectionMeasurementsTextAttributes.update(dict(
            borderColor=mainColor,
            backgroundColor=backgroundColor,
            fillColor=mainColor,
            borderWidth=1
        ))
        selectionNamesTextAttributes = dict(selectionMeasurementsTextAttributes)
        # populate
        self.autoSegmentMatchBaseLayer.setOpacity(highlightOpacity)
        self.persistentMeasurementsBaseLayer.setOpacity(persistentMeasurementsOpacity)
        self.persistentMeasurementsTextBaseLayer.setOpacity(persistentMeasurementsOpacity)
        self.measurementsTextLayer.setPropertiesByName(textAttributes)
        self.namesTextLayer.setPropertiesByName(namesTextAttributes)
        self.selectionMeasurementsTextLayer.setPropertiesByName(selectionMeasurementsTextAttributes)
        self.selectionNamesTextLayer.setPropertiesByName(selectionNamesTextAttributes)
        self.outlineWidthLayer.setPropertiesByName(lineAttributes)
        self.outlineHeightLayer.setPropertiesByName(lineAttributes)
        self.segmentMatchHighlightLayer.setPropertiesByName(highlightAttributes)
        self.segmentMatchHighlightLayer.setStrokeColor(mainColor)
        self.segmentHighlightLayer.setPropertiesByName(highlightAttributes)
        self.handleMatchHighlightLayer.setPropertiesByName(highlightAttributes)
        self.handleMatchHighlightLayer.setStrokeColor(mainColor)
        self.handleHighlightLayer.setPropertiesByName(highlightAttributes)
        self.pointHighlightLayer.setPropertiesByName(highlightAttributes)
        self.anchorWidthLayer.setPropertiesByName(lineAttributes)
        self.anchorHeightLayer.setPropertiesByName(lineAttributes)
        self.hud.update()

    def loadNamedMeasurements(self):
        libKey = extensionID + ".measurements"
        font = self.getFont()
        stored = font.lib.get(libKey, {})
        self.hud.setItems(stored)
        self.namedWidthHeightMeasurements, self.namedWidthMeasurements, self.namedHeightMeasurements = loadNamedMeasurements(font)

    def destroy(self):
        self.activeContainer.clearSublayers()
        self.textContainer.clearSublayers()
        events.removeObserver(
            self,
            extensionID + ".defaultsChanged"
        )

    def hideLayers(self):
        self.autoSegmentMatchBaseLayer.setVisible(False)
        self.persistentMeasurementsBaseLayer.setVisible(False)
        self.measurementsTextContainer.setVisible(False)
        self.activeContainer.setVisible(False)
        self.textContainer.setVisible(False)
        self.clearText()
        # clear the animating layers so that
        # they are starting from scratch with
        # the next session. otherwise, a pref
        # change and a match on the previous
        # match won't reflect the pref change.
        self.segmentMatchHighlightLayer.clearAnimation()
        self.handleMatchHighlightLayer.clearAnimation()
        self.segmentMatchHighlightLayer.setPath(emptyPath)
        self.handleMatchHighlightLayer.setPath(emptyPath)

    # Objects
    # -------

    def getFont(self):
        window = self.getGlyphEditor()
        glyph = window.getGlyph()
        # in single window mode glyph will
        # be None at start up, so hack around
        if glyph is None:
            font = window.document.getFont()
        else:
            font = glyph.font
        return font

    # Events
    # ------

    def roboFontDidChangePreferences(self, info):
        self.loadDefaults()

    def extensionDefaultsChanged(self, event):
        self.loadDefaults()

    def fontMeasurementsChanged(self, info):
        self.loadNamedMeasurements()

    needAutoSegmentHighlightRebuild = True
    needPersistentMeasurementsRebuild = True

    def glyphEditorDidSetGlyph(self, info):
        self.needAutoSegmentHighlightRebuild = True
        self.needPersistentMeasurementsRebuild = True

    def glyphEditorGlyphDidChangeContours(self, info):
        self.needAutoSegmentHighlightRebuild = True
        self.needPersistentMeasurementsRebuild = True

    triggerPressed = False
    wantsMeasurements = False
    currentDisplayFocalPoint = None
    currentMeasurements = None
    currentSelectionMeasurements = None
    currentNames = None
    currentSelectionNames = None
    currentAutoSegmentMatches = None

    def glyphEditorDidKeyDown(self, info):
        deviceState = info["deviceState"]
        if deviceState["keyDownWithoutModifiers"] != self.triggerCharacter:
            self.wantsMeasurements = False
        else:
            self.triggerPressed = True
            self.wantsMeasurements = True
            selectionState = False
            glyph = info["glyph"]
            if self.doAutoTestSegmentMatches:
                self.autoMeasureSegments(
                    glyph,
                    deviceState
                )
            self.autoSegmentMatchBaseLayer.setVisible(self.doAutoTestSegmentMatches)
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
            if self.showPersistentMeasurements:
                self.updatePersistentMeasurements(glyph)
                self.persistentMeasurementsBaseLayer.setVisible(True)
            self.persistentMeasurementsTextBaseLayer.setVisible(self.showPersistentMeasurements)
            setCursorMode("searching")
            if self.showMeasurementsHUD:
                self.hud.show(self.currentSelectionMeasurements is not None)
            self.textContainer.setVisible(True)
            
            # Start measuring now
            self.initiateLaser(self.point, glyph, deviceState)

    def glyphEditorDidKeyUp(self, info):
        if "deviceState" not in info:
            keyDownWithoutModifiers = self.triggerCharacter
        else:
            deviceState = info["deviceState"]
            keyDownWithoutModifiers = deviceState["keyDownWithoutModifiers"]
        if self.triggerPressed:
            if keyDownWithoutModifiers in (persistentMakeTrigger, persistentBreakTrigger):
                glyph = info["glyph"]
                if keyDownWithoutModifiers == persistentMakeTrigger:
                    self.makePersistentMeasurements(glyph, deviceState)
                elif keyDownWithoutModifiers == persistentBreakTrigger:
                    self.breakPersistentMeasurements(glyph, deviceState)
            elif keyDownWithoutModifiers == self.triggerCharacter:
                self.triggerPressed = False
                self.wantsMeasurements = False
                self.hideLayers()
                setCursorMode(None)
                self.hud.hide()

    def glyphEditorDidMouseDown(self, info):
        self.wantsMeasurements = False
        self.hideLayers()
        setCursorMode(None)

    # glyphEditorDidMouseMoveDelay = 0.05
    def glyphEditorDidMouseMove(self, info):
        self.point = tuple(info["locationInGlyph"])
        deviceState = info["deviceState"]
        glyph = info["glyph"]
        self.initiateLaser(self.point, glyph, deviceState)
        
    def initiateLaser(self, point, glyph, deviceState):
        if not self.wantsMeasurements:
            return
        self.selectionMeasurementsTextLayer.setVisible(False)
        if not glyph.bounds:
            self.hideLayers()
            return
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
                if self.measureBetweenPoints(point, glyph, deviceState):
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
        self.anchorBaseLayer.setVisible(anchorState)
        self.handleBaseLayer.setVisible(handleState)
        self.segmentBaseLayer.setVisible(segmentState)
        self.pointBaseLayer.setVisible(pointState)
        self.outlineBaseLayer.setVisible(outlineState)
        self.activeContainer.setVisible(True)
        self.measurementsTextContainer.setVisible(True)
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

    def hudShowNamedValuesCallback(self, sender):
        from .namedValuesSheet import NamedValuesSheetController
        font = self.getFont()
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
        if self.currentDisplayFocalPoint is not None:
            x, y = self.currentDisplayFocalPoint
            x += cursorOffset
            y -= cursorOffset
            self.textBaseLayer.setPosition((x, y))
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
        if not self.textContainer.getVisible():
            self.textContainer.setVisible(True)

    # Names
    # -----

    def findNames(self):
        self.currentNames = None
        if not self.currentMeasurements:
            return
        names = findMatchingNamedMeasurements(
            self.currentMeasurements,
            namedWidthHeightMeasurements=self.namedWidthHeightMeasurements,
            namedWidthMeasurements=self.namedWidthMeasurements,
            namedHeightMeasurements=self.namedHeightMeasurements
        )
        if names:
            self.currentNames = names

    def findSelectionNames(self):
        self.currentSelectionNames = None
        if not self.currentSelectionMeasurements:
            return
        names = findMatchingNamedMeasurements(
            self.currentSelectionMeasurements,
            namedWidthHeightMeasurements=self.namedWidthHeightMeasurements,
            namedWidthMeasurements=self.namedWidthMeasurements,
            namedHeightMeasurements=self.namedHeightMeasurements
        )
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
    # self.currentMeasurements and the text updating
    # system will pull and format the data as needed.

    def autoMeasureSegments(self,
            glyph,
            deviceState
        ):
        if not self.needAutoSegmentHighlightRebuild:
            return
        self.autoSegmentMatchBaseLayer.clearSublayers()
        groups = glyph.getRepresentation(extensionKeyStub + "segmentGroups")
        if groups == self.currentAutoSegmentMatches:
            return
        colors = list(self.matchColors)
        strokeWidth = self.matchStrokeWidth
        for type, segments in groups:
            color = colors.pop(0)
            colors.append(color)
            pen = merz.MerzPen()
            for segment in segments:
                pen.moveTo(segment[0])
                if type == "line":
                    pen.lineTo(segment[1])
                elif type == "curve":
                    pen.curveTo(*segment[1:])
                elif type == "qcurve":
                    pen.qCurveTo(*segment[1:])
                pen.endPath()
            layer = self.autoSegmentMatchBaseLayer.appendPathSublayer(
                strokeColor=color,
                fillColor=None,
                strokeWidth=strokeWidth,
                path=pen.path
            )
        self.needAutoSegmentHighlightRebuild = False

    def measureSelection(self,
            glyph,
            deviceState
        ):
        points = getSelectedPoints(glyph)
        measurements = measurePoints(points)
        if not measurements:
            return
        if measurements == self.currentSelectionMeasurements:
            return
        self.currentSelectionMeasurements = measurements
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
        window = self.getGlyphEditor()
        editor = window.getGlyphView()
        scale = editor.scale()
        hit = measureSegmentsAndHandles(
            point,
            glyph.getRepresentation(extensionKeyStub + "handlesAsLines"),
            scale,
            self.handleHighlightLayer
        )
        if hit:
            segmentType, points, measurements = hit
            self.currentMeasurements = measurements
            if self.doTestOffCurveMatches:
                self._findMatchingHandles(
                    points,
                    glyph
                )
                self.handleMatchHighlightLayer.setVisible(True)
                return True
            else:
                self.handleMatchHighlightLayer.setVisible(False)
                return bool(hit)
        else:
            self.handleMatchHighlightLayer.setVisible(False)

    def _findMatchingHandles(self,
            points,
            glyph
        ):
        layer = self.handleMatchHighlightLayer
        layerPen = merz.MerzPen()
        target = RelativeHandle(points)
        handles = glyph.getRepresentation(extensionKeyStub + "relativeHandles")
        haveMatch = False
        for handle in handles:
            if handle.isSame(target):
                continue
            if handle == target:
                haveMatch = True
                layerPen.moveTo(handle.original[0])
                layerPen.lineTo(handle.original[1])
                layerPen.endPath()
        self._setMatchedPath(haveMatch, layer, layerPen)

    def measureSegments(self,
            point,
            glyph,
            deviceState
        ):
        window = self.getGlyphEditor()
        editor = window.getGlyphView()
        scale = editor.scale()
        hit = measureSegmentsAndHandles(
            point,
            glyph,
            scale,
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
        target = RelativeSegment(segmentType, segmentPoints)
        segments = glyph.getRepresentation(extensionKeyStub + "relativeSegments")
        haveMatch = False
        for segment in segments:
            if segment.isSame(target):
                continue
            if segment == target:
                haveMatch = True
                layerPen.moveTo(segment.original[0])
                if segment.type == "line":
                    layerPen.lineTo(segment.original[1])
                elif segment.type == "curve":
                    layerPen.curveTo(*segment.original[1:])
                elif segment.type == "qcurve":
                    layerPen.qCurveTo(*segment.original[1:])
                layerPen.endPath()
        self._setMatchedPath(haveMatch, layer, layerPen)

    def _setMatchedPath(self, haveMatch, layer, layerPen):
        # static
        if not self.highlightAnimate:
            with layer.propertyGroup():
                layer.setPath(layerPen.path)
                layer.setStrokeWidth(self.highlightWidth1)
                layer.setOpacity(1.0)
        # animated
        else:
            if not haveMatch:
                layer.clearAnimation()
                layer.setPath(layerPen.path)
                return
            if Quartz.CGPathEqualToPath(layer.getPath(), layerPen.path):
                return
            layer.setPath(layerPen.path)
            animationSettings = dict(
                duration=self.highlightAnimationDuration,
                repeatCount="loop",
                reverse=False,
                restore=True
            )
            with layer.propertyGroup():
                layer.setStrokeWidth(self.highlightWidth1)
                layer.setOpacity(1.0)
            with layer.propertyGroup(**animationSettings):
                layer.setStrokeWidth(self.highlightWidth2)
                layer.setOpacity(0)

    def measureBetweenPoints(self,
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
        self.pointHighlightLayer.setStartPoint(point1)
        self.pointHighlightLayer.setEndPoint(point2)
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

    # Persistent
    # ----------

    def makePersistentMeasurements(self, glyph, deviceState):
        points = getSelectedPoints(glyph)
        if len(points) != 2:
            AppKit.NSBeep()
            return
        storePersistentPointMeasurementReferences(glyph, points)
        self.needPersistentMeasurementsRebuild = True
        self.updatePersistentMeasurements(glyph)

    def breakPersistentMeasurements(self, glyph, deviceState):
        points = getSelectedPoints(glyph)
        removePersistentPointMeasurementReferences(glyph, points)
        self.needPersistentMeasurementsRebuild = True
        self.updatePersistentMeasurements(glyph)

    def updatePersistentMeasurements(self, glyph):
        if not self.needPersistentMeasurementsRebuild:
            return
        persistentMeasurements = getPersistentPointMeasurements(
            glyph,
            namedWidthHeightMeasurements=self.namedWidthHeightMeasurements,
            namedWidthMeasurements=self.namedWidthMeasurements,
            namedHeightMeasurements=self.namedHeightMeasurements
        )
        self.persistentMeasurementsBaseLayer.clearSublayers()
        layer = self.persistentMeasurementsTextBaseLayer.clearSublayers()
        color = self.persistentMeasurementsColor
        strokeWidth = self.persistentMeasurementsStrokeWidth
        highlightProperties = dict(
            fillColor=None,
            strokeColor=color,
            strokeWidth=strokeWidth,
            strokeDash=(1, 2)
        )
        textAttributes = dict(self.genericTextAttributes)
        textAttributes["horizontalAlignment"] = "center"
        textAttributes["verticalAlignment"] = "center"
        textAttributes["backgroundColor"] = color
        for data in persistentMeasurements:
            positions = data["positions"]
            measurements = data["measurements"]
            names = data["names"]
            pen = merz.MerzPen()
            pen.moveTo(positions[0])
            for position in positions[1:]:
                pen.lineTo(position)
            pen.endPath()
            layer = self.persistentMeasurementsBaseLayer.appendPathSublayer(
                path=pen.path,
                **highlightProperties
            )
            xPositions = set()
            yPositions = set()
            for (x, y) in positions:
                xPositions.add(x)
                yPositions.add(y)
            xPosition = statistics.median(xPositions)
            yPosition = statistics.median(yPositions)
            text = [formatWidthHeightString(*measurements)]
            if names:
                text.append(formatNames(*names))
            text = "\n".join(text)
            textData = dict(textAttributes)
            textData["text"] = text
            textData["position"] = (xPosition, yPosition)
            textData["offset"] = (0, 0)
            layer = self.persistentMeasurementsTextBaseLayer.appendTextLineSublayer(
                **textData
            )
        self.needPersistentMeasurementsRebuild = False


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


# Named Measurements
# ------------------

def loadNamedMeasurements(font):
    namedWidthMeasurements = {}
    namedHeightMeasurements = {}
    namedWidthHeightMeasurements = {}
    libKey = extensionID + ".measurements"
    if font is not None:
        stored = font.lib.get(libKey, {})
        for name, data in stored.items():
            width = data.get("width")
            height = data.get("height")
            key = None
            location = None
            if width is not None and height is not None:
                location = namedWidthHeightMeasurements
                key = (width, height)
            elif width is not None:
                location = namedWidthMeasurements
                key = width
                name = f"W: {name}"
            elif height is not None:
                location = namedHeightMeasurements
                key = height
                name = f"H: {name}"
            if location is None:
                continue
            if key not in location:
                location[key] = []
            location[key].append(name)
        dicts = [
            namedWidthMeasurements,
            namedHeightMeasurements,
            namedWidthHeightMeasurements
        ]
        for d in dicts:
            for d, v in d.items():
                v.sort()
    return namedWidthHeightMeasurements, namedWidthMeasurements, namedHeightMeasurements


def findMatchingNamedMeasurements(
        measurements,
        namedWidthHeightMeasurements,
        namedWidthMeasurements,
        namedHeightMeasurements
    ):
    w, h = measurements
    names = []
    names += namedWidthHeightMeasurements.get((w, h), [])
    names += namedWidthMeasurements.get(w, [])
    names += namedHeightMeasurements.get(h, [])
    return names

# Points
# ------

def getSelectedPoints(glyph):
    points = []
    for contour in glyph.selectedContours:
        points.extend([point for point in contour.selectedPoints])
    return points

def measurePoints(points):
    xValues = set()
    yValues = set()
    for point in points:
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
    return measurements

# Segments and Handles
# --------------------

def measureSegmentsAndHandles(
        point,
        glyph,
        scale,
        highlightLayer
    ):
    x, y = point
    selector = glyph.getRepresentation("doodle.GlyphSelection")
    point = defcon.Point(point)
    found = selector.segmentStrokeHitByPoint_(point, 5 / scale)
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

class NearestPointsPointPen(AbstractPointPen):

    def __init__(self):
        self.onCurvePoints = []
        self.contourOnCurveCounts = {}
        self._currentContour = 0
        self._pointIndex = 0
        self._pointCombinationValidity = {}

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
        font = glyph.font
        unitsPerEm = font.info.unitsPerEm
        # filter to the closest points
        points = []
        for contourIndex, pointIndex, point in self.onCurvePoints:
            distance = bezierTools.distanceFromPointToPoint(location, point)
            points.append((distance, contourIndex, pointIndex, point))
        points.sort()
        points = points[:50]
        candidates = []
        while len(candidates) < 100:
            tested = set()
            for distanceToCursor1, contour1Index, point1Index, point1 in points:
                contour1Count =  self.contourOnCurveCounts[contour1Index]
                contour1 = glyph.contours[contour1Index]
                contour1Width, contour1Height = getContourWidthHeight(contour1)
                for distanceToCursor2, contour2Index, point2Index, point2 in points:
                    if point1 == point2:
                        continue
                    # already tested in this call
                    combination = frozenset((point1, point2))
                    if combination in tested:
                        continue
                    tested.add(combination)
                    # already tested validity of combination
                    combinationIdentifier = frozenset(((contour1Index, point1Index), (contour2Index, point2Index)))
                    if not self._pointCombinationValidity.get(combinationIdentifier, True):
                        continue
                    self._pointCombinationValidity[combinationIdentifier] = False
                    # point1 and point2 can't be sequential on the same contour
                    contour2Count =  self.contourOnCurveCounts[contour2Index]
                    if contour1Index == contour2Index:
                        if abs(point1Index - point2Index) == 1:
                            continue
                        if {point1Index, point2Index} == {0, contour1Count - 1}:
                            continue
                    # the distance must be lower than the max
                    # if the line is not a multiple of 90 degrees
                    angle = bezierTools.calculateAngle(point1, point2)
                    angle = normalizeAngle(angle)
                    if not isRightAngle(angle):
                        contour2 = glyph.contours[contour2Index]
                        contour2Width, contour2Height = getContourWidthHeight(contour2)
                        distanceLimit = max((contour1Width, contour1Height, contour2Width, contour2Height)) * 0.5
                        distance = bezierTools.distanceFromPointToPoint(point1, point2)
                        if distance > distanceLimit:
                            continue
                    self._pointCombinationValidity[combinationIdentifier] = True
                    # location must be midway-ish between points
                    distanceToCursor = distanceToCursor1 + distanceToCursor2
                    t = distanceToCursor1 / distanceToCursor
                    if t < 0.35 or t > 0.65:
                        continue
                    # point1-location-point2 must be close to collinear
                    distance = bezierTools.distanceFromPointToPoint(point1, point2)
                    tolerance = calcCollinearityTolerance(distance, unitsPerEm)
                    if not isCollinear(point1, location, point2, tolerance):
                        continue
                    # store
                    candidates.append((distanceToCursor, (point1, point2)))
            break
        # sort by distance
        candidates.sort()
        # only test a limited number
        for candidate in candidates[:10]:
            point1, point2 = candidate[-1]
            line = (point1, point2)
            intersections = tools.IntersectGlyphWithLine(
                glyph,
                line,
                canHaveComponent=False,
                addSideBearings=False
            )
            if intersections:
                for point in line:
                    if point in intersections:
                        intersections.remove(point)
            if intersections:
                continue
            return (point1, point2)


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

def isRightAngle(angle):
    tolerance = 1
    if angle <= tolerance:
        return True
    elif angle >= (90 - tolerance) and angle <= (90 + tolerance):
        return True
    elif angle >= (180 - tolerance) and angle <= (180 + tolerance):
        return True
    elif angle >= (270 - tolerance) and angle <= (270 + tolerance):
        return True
    elif angle >= (360 - tolerance):
        return True
    return False

def isCollinear(point1, location, point2, tolerance):
    tolerance = math.radians(tolerance)
    x1, y1 = point1
    x2, y2 = location
    x3, y3 = point2
    dx1 = x2 - x1
    dy1 = y2 - y1
    dx2 = x3 - x2
    dy2 = y3 - y2
    a1 = math.atan2(dy1, dx1)
    a2 = math.atan2(dy2, dx2)
    collinearity = abs(a1 - a2)
    if collinearity > math.pi:
        collinearity = math.pi * 2 - collinearity
    if collinearity > tolerance:
       return False
    return True

maxCollinearityTolerance = 30
minCollinearityTolerance = 2
collinearityToleranceRange = maxCollinearityTolerance - minCollinearityTolerance

def calcCollinearityTolerance(distance, unitsPerEm):
    minDistance = unitsPerEm * 0.02
    maxDistance = unitsPerEm * 0.5
    if distance < minDistance:
        return maxCollinearityTolerance
    elif distance > maxDistance:
        return minCollinearityTolerance
    proportion = (distance - minDistance) / (maxDistance - minDistance)
    tolerance = maxCollinearityTolerance - (collinearityToleranceRange * proportion)
    return tolerance

def getContourWidthHeight(contour):
    xMin, yMin, xMax, yMax = contour.bounds
    w = xMax - xMin
    h = yMax - yMin
    return (w, h)

# Segment Matching
# ----------------

class RelativeSegment:

    def __init__(self, type, segment):
        if type == "move":
            type = "line"
        self.type = type
        self.original = tuple(segment)
        self._reversedOriginal = None
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

    def _get_reversedOriginal(self):
        if self._reversedOriginal is None:
            self._reversedOriginal = reversePoints(self.original)
        return self._reversedOriginal

    reversedOriginal = property(_get_reversedOriginal)

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

    def isSame(self, other):
        if other.original == self.original:
            return True
        if other.original == self.reversedOriginal:
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
    sorter = []
    for key, segments in tree.items():
        if len(segments) < 2:
            continue
        segments = tuple(sorted([s.original for s in segments]))
        sorter.append((key.type, segments))
    return list(sorted(sorter))

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


# Handle Matching
# ---------------

class RelativeHandle(RelativeSegment):

    def __init__(self, points):
        super().__init__("line", points)


class RelativeHandlesPen(BasePen):

    def __init__(self):
        super().__init__()
        self.handles = []

    def _moveTo(self, pt):
        self.prevPoint = pt

    def _lineTo(self, pt):
        self.prevPoint = pt

    def _curveToOne(self, pt1, pt2, pt3):
        self.handles.append(RelativeHandle((self.prevPoint, pt1)))
        self.handles.append(RelativeHandle((pt2, pt3)))
        self.prevPoint = pt3

    def _qCurveToOne(self, pt1, pt2):
        self.handles.append(RelativeHandle((self.prevPoint, pt1)))
        self.handles.append(RelativeHandle((pt1, pt2)))
        self.prevPoint = pt2

    def _closePath(self):
        self.prevPoint = None

    def _endPath(self):
        self.prevPoint = None


def relativeHandlesGlyphFactory(glyph):
    handlesPen = RelativeHandlesPen()
    glyph.draw(handlesPen)
    return handlesPen.handles

defcon.registerRepresentationFactory(
    defcon.Glyph,
    extensionKeyStub + "relativeHandles",
    relativeHandlesGlyphFactory
)


# ---
# HUD
# ---

hudPadding = 10

class LaserMeasureNamedValuesHUD:

    def __init__(self, glyphEditor, addButtonCallback, showButtonCallback):
        self.items = {}

        subview = vanilla.Group((0, 0, 0, 0))
        subview.background = merz.MerzView((0, 0, 0, 0))
        group = subview.group = vanilla.Group((hudPadding, hudPadding, 0, 0))
        group.addButton = vanilla.ImageButton(
            (-42, 0, 20, 20),
            bordered=False,
            callback=addButtonCallback
        )
        group.editButton = vanilla.ImageButton(
            (-20, 0, 20, 20),
            bordered=False,
            callback=showButtonCallback
        )
        group.textView = merz.MerzView((0, 0, 0, 0))

        self.subview = subview
        self.background = subview.background.getMerzContainer()
        self.background.setCornerRadius(hudPadding)
        self.group = group
        self.addButton = group.addButton
        self.editButton = group.editButton
        self.textView = group.textView
        self.textContainer = group.textView.getMerzContainer()

        self.update()
        subview.show(False)

        glyphEditor.addGlyphEditorSubview(
            subview,
            identifier=extensionID + ".LaserMeasureNamedValuesHUD",
            clear=True
        )

    def show(self, showButton):
        if self.addButton.isVisible() != showButton:
            self.addButton.show(showButton)
        if not self.subview.isVisible():
            self.subview.show(True)

    def hide(self):
        self.subview.show(False)

    def setItems(self, items):
        self.items = items
        self.update()

    def update(self):
        color = getExtensionDefault(extensionID + ".baseColor")
        r, g, b, a = color
        lineColor = (r, g, b, a * 0.25)
        backgroundColor = tuple(UI.getDefault("glyphViewBackgroundColor"))

        # Background
        self.background.setBackgroundColor(backgroundColor)
        self.background.setOpacity(0.9)

        # Add Button
        image = AppKit.NSImage.alloc().initWithSize_((20, 20))
        linePath = AppKit.NSBezierPath.bezierPathWithOvalInRect_(((2, 2), (16, 16)))
        linePath.moveToPoint_((10, 6))
        linePath.lineToPoint_((10, 14))
        linePath.moveToPoint_((6, 10))
        linePath.lineToPoint_((14, 10))
        linePath.setLineWidth_(1)
        linePath.setLineCapStyle_(AppKit.NSLineCapStyleRound)
        image.lockFocus()
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*backgroundColor).set()
        linePath.fill()
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*color).set()
        linePath.stroke()
        image.unlockFocus()
        self.addButton.setImage(imageObject=image)

        # Edit Button
        image = AppKit.NSImage.alloc().initWithSize_((20, 20))
        linePath = AppKit.NSBezierPath.bezierPathWithOvalInRect_(((2, 2), (16, 16)))
        linePath.setLineWidth_(1)
        linePath.setLineCapStyle_(AppKit.NSLineCapStyleRound)
        fillPath = AppKit.NSBezierPath.bezierPath()
        fillPath.appendBezierPathWithOvalInRect_(((6, 9), (2, 2)))
        fillPath.appendBezierPathWithOvalInRect_(((9, 9), (2, 2)))
        fillPath.appendBezierPathWithOvalInRect_(((12, 9), (2, 2)))
        image.lockFocus()
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*backgroundColor).set()
        linePath.fill()
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*color).set()
        linePath.stroke()
        fillPath.fill()

        image.unlockFocus()
        self.editButton.setImage(imageObject=image)

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
        nameTextAttributes = dict(textAttributes)
        nameTextAttributes["horizontalAlignment"] = "left"
        font = merz.text.makeFont(
            "system",
            weight=textAttributes["weight"],
            figureStyle=textAttributes["figureStyle"],
            pointSize=textAttributes["pointSize"],
        )

        nameWidths = []
        numberWidths = [
            calculateTextWidth("W", font),
            calculateTextWidth("H", font)
        ]
        for item in items:
            nameWidths.append(calculateTextWidth(item["name"], font))
            numberWidths.append(calculateTextWidth(item["width"], font))
            numberWidths.append(calculateTextWidth(item["height"], font))

        buttonWidth = 42
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
        textViewHeight = 0
        if items:
            textViewHeight = rowHeight * (len(items) + 1)
        totalHeight = textViewHeight + buttonHeight
        totalWidth += hudPadding * 2
        totalHeight += hudPadding * 2
        xStart = -25
        yStart = 10

        self.group.setPosSize((hudPadding, hudPadding, totalWidth - (hudPadding * 2), totalHeight - (hudPadding * 2)))
        self.subview.setPosSize((-totalWidth + xStart, yStart, totalWidth, totalHeight))
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
                **nameTextAttributes
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