from mojo import roboFont
from laserMeasure.settingsWindow import LaserMeasureSettingsWindowController

version = roboFont.version
versionMajor, versionMinor = version.split(".", 1)
versionMinor = versionMinor.split(".")[0]
versionMajor = "".join([i for i in versionMajor if i in "0123456789"])
versionMinor = "".join([i for i in versionMinor if i in "0123456789"])
versionMajor = int(versionMajor)
versionMinor = int(versionMinor)

note = """
The settings window is only available in
RoboFont 4.2+. However, you can change the
settings with a script as described in
the documentation.
""".strip()

if versionMajor == 4 and versionMinor < 2:
    print(note)
else:
    roboFont.OpenWindow(LaserMeasureSettingsWindowController)