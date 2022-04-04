from mojo import roboFont
from mojo.UI import CurrentFontWindow
from laserMeasure.namedValuesSheet import NamedValuesSheetController

version = roboFont.version
versionMajor, versionMinor = version.split(".", 1)
versionMinor = versionMinor.split(".")[0]
versionMajor = "".join([i for i in versionMajor if i in "0123456789"])
versionMinor = "".join([i for i in versionMinor if i in "0123456789"])
versionMajor = int(versionMajor)
versionMinor = int(versionMinor)

note = """
The named values sheet is only available
in RoboFont 4.2+.
""".strip()

if versionMajor == 4 and versionMinor < 2:
    print(note)
else:
    window = CurrentFontWindow()
    if window is not None:
        font = window.document.getFont()
        NamedValuesSheetController(window.w, font)
