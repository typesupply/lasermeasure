import ezui
from mojo.events import postEvent

if __name__ == "__main__":
    from subscriber import (
        internalGetDefault,
        internalSetDefault,
        extensionID
    )
    import legacy
else:
    from .subscriber import (
        internalGetDefault,
        internalSetDefault,
        extensionID
    )
    from . import legacy

class _LaserMeasureSettingsWindowController(ezui.WindowController):

    def build(self):
        content = """
        = TwoColumnForm

        : Measure:
        [ ] Selected Points                         @testSelection
        :
        [ ] General                                 @testGeneral
        :
        [ ] Segments                                @testSegments
        :
        [ ] Off Curve Handles                       @testOffCurves
        :
        [ ] Points                                  @testPoints
        :
        [ ] Anchors                                 @testAnchors
        :
        [ ] Highlight Matching Segments             @testSegmentMatches
        :
        [ ] Highlight Matching Off Curve Handles    @testOffCurveMatches

        ---

        : Auto Measure:
        [ ] Matching Segments                       @autoTestSegmentMatches

        ---

        : Trigger Character:
        [__]                                        @triggerCharacter

        : Base Color:
        * ColorWell                                 @baseColor

        : Highlight Width:
        [__] pixels                                 @highlightStrokeWidth

        : Highlight Opacity:
        --X--                                       @highlightOpacity

        : Text Size:
        [__] points                                 @measurementTextSize

        ---

        : HUD
        [ ] Show Named Values List                  @showMeasurementsHUD
        """
        colorWellWidth = 100
        colorWellHeight = 20
        numberEntryWidth = 75
        descriptionData = dict(
            content=dict(
                titleColumnWidth=125,
                itemColumnWidth=265
            ),
            testSelection=dict(
                value=internalGetDefault("testSelection")
            ),
            testGeneral=dict(
                value=internalGetDefault("testGeneral")
            ),
            testSegments=dict(
                value=internalGetDefault("testSegments")
            ),
            testOffCurves=dict(
                value=internalGetDefault("testOffCurves")
            ),
            testPoints=dict(
                value=internalGetDefault("testPoints")
            ),
            testAnchors=dict(
                value=internalGetDefault("testAnchors")
            ),
            testSegmentMatches=dict(
                value=internalGetDefault("testSegmentMatches")
            ),
            testOffCurveMatches=dict(
                value=internalGetDefault("testOffCurveMatches")
            ),
            triggerCharacter=dict(
                width=20,
                value=internalGetDefault("triggerCharacter")
            ),
            autoTestSegmentMatches=dict(
                value=internalGetDefault("autoTestSegmentMatches")
            ),
            baseColor=dict(
                width=colorWellWidth,
                height=colorWellHeight,
                color=tuple(internalGetDefault("baseColor"))
            ),
            highlightStrokeWidth=dict(
                width=numberEntryWidth,
                valueType="integer",
                value=internalGetDefault("highlightStrokeWidth")
            ),
            highlightOpacity=dict(
                minValue=0,
                maxValue=1.0,
                value=internalGetDefault("highlightOpacity")
            ),
            measurementTextSize=dict(
                width=numberEntryWidth,
                valueType="number",
                value=internalGetDefault("measurementTextSize")
            ),
            showMeasurementsHUD=dict(
                value=internalGetDefault("showMeasurementsHUD")
            )
        )
        self.w = ezui.EZWindow(
            title="Laser Measure Settings",
            content=content,
            descriptionData=descriptionData,
            controller=self
        )

    def started(self):
        self.w.open()

    def contentCallback(self, sender):
        for key, value in sender.getItemValues().items():
            existing = internalGetDefault(key)
            if existing == value:
                continue
            internalSetDefault(key, value)
        postEvent(
            extensionID + ".defaultsChanged"
        )

    def triggerCharacterCallback(self, sender):
        if len(sender.get()) == 1:
            self.contentCallback(sender)


note = """
The settings window is only available in
RoboFont 4.2+. However, you can change the
settings with a script as described in
the documentation.
""".strip()

def LaserMeasureSettingsWindowController(*args, **kwargs):
    if legacy.versionMajor == 4 and legacy.versionMinor < 2:
        print(note)
    else:
        _LaserMeasureSettingsWindowController(*args, **kwargs)

if __name__ == "__main__":
    LaserMeasureSettingsWindowController()
