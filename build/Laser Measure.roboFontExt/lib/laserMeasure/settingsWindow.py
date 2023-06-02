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

        : Trigger Character:
        [__]                                        @triggerCharacter

        ---

        : Laser Color:
        * ColorWell                                 @baseColor

        : Text Size:
        [__] points                                 @measurementTextSize

        ---

        : Measure:
        [ ] Selected Points                         @testSelection
        [ ] General                                 @testGeneral
        [ ] Segments                                @testSegments
        [ ] Off Curve Handles                       @testOffCurves
        [ ] Points                                  @testPoints
        [ ] Anchors                                 @testAnchors

        ---

        : Highlight:
        [ ] Matching Segments                       @testSegmentMatches
        [ ] Matching Off Curve Handles              @testOffCurveMatches

        : Auto-Highlight:
        [ ] Matching Segments                       @autoTestSegmentMatches

        : Highlight Opacity:
        --X--                                       @highlightOpacity

        : Highlight Width:
        [__] pixels                                 @highlightStrokeWidth

        ---

        : Animate Matches:
        [ ]                                         @highlightAnimate
        : Animation Duration:
        [__] seconds                                @highlightAnimationDuration

        ---

        : HUD:
        [ ] Show Named Values List                  @showMeasurementsHUD
        """
        colorWellWidth = 100
        colorWellHeight = 20
        numberEntryWidth = 40
        descriptionData = dict(
            content=dict(
                titleColumnWidth=125,
                itemColumnWidth=220
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
                valueWidth=numberEntryWidth,
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
                valueWidth=numberEntryWidth,
                valueType="integer",
                value=internalGetDefault("highlightStrokeWidth")
            ),
            highlightOpacity=dict(
                minValue=0,
                maxValue=1.0,
                tickMarks=3,
                value=internalGetDefault("highlightOpacity")
            ),
            highlightAnimate=dict(
                value=internalGetDefault("highlightAnimate")
            ),
            highlightAnimationDuration=dict(
                valueWidth=numberEntryWidth,
                valueType="number",
                minValue=0.1,
                maxValue=5.0,
                value=internalGetDefault("highlightAnimationDuration")
            ),
            measurementTextSize=dict(
                valueWidth=numberEntryWidth,
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
        self.set_defaults()

    def triggerCharacterCallback(self, sender):
        # Keep the character limited to a length of 1, and lowercase it.
        character = sender.get()
        if len(character) > 1:
            character = character[-1]
            self.w.getItem("triggerCharacter").set(character.lower())
        self.set_defaults()

    def set_defaults(self):
        for key, value in self.w.getItemValues().items():
            existing = internalGetDefault(key)
            if existing == value:
                continue
            internalSetDefault(key, value)
        postEvent(
            extensionID + ".defaultsChanged"
        )


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
