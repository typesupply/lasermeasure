from mojo.UI import CurrentFontWindow
from laserMeasure.namedValuesSheet import NamedValuesSheetController

window = CurrentFontWindow()
if window is not None:
    font = window.document.getFont()
    openNamedValuesSheetController(window.w, font)
