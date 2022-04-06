import ezui
from mojo import events

if __name__ == "__main__":
    from subscriber import extensionID
    import legacy
else:
    from .subscriber import extensionID
    from . import legacy


libKey = extensionID + ".measurements"

class _NamedValuesSheetController(ezui.WindowController):

    def build(self, parent, font):
        self.font = font

        content = """
        |-----------------------|
        | name | width | height |     @measurementTable
        |-----------------------|
        |                       |
        |-----------------------|
        > (+-)                        @addRemoveMeasurementButton

        =========================

        (Cancel)                      @cancelButton
        (Apply)                       @applyButton
        """
        descriptionData = dict(
            measurementTable=dict(
                columnDescriptions=[
                    dict(
                        identifier="name",
                        title="Name",
                        editable=True
                    ),
                    dict(
                        identifier="width",
                        title="Width",
                        width=50,
                        editable=True
                    ),
                    dict(
                        identifier="height",
                        title="Height",
                        width=50,
                        editable=True
                    )
                ],
                width=250,
                height=200,
                itemPrototype=dict(
                    name="Name",
                    width=None,
                    height=None
                )
            ),
        )
        self.w = ezui.EZSheet(
            content=content,
            descriptionData=descriptionData,
            defaultButton="applyButton",
            parent=parent,
            controller=self
        )

    def started(self):
        self.table = self.w.getItem("measurementTable")
        stored = self.font.lib.get(libKey, {})
        items = []
        for name, data in stored.items():
            item = self.table.makeItem(name=name, **data)
            items.append(item)
        self.table.set(items)
        self.w.open()

    def cancelButtonCallback(self, sender):
        self.w.close()

    def applyButtonCallback(self, sender):
        items = self.table.get()
        self.w.close()
        fontData = dict()
        for item in items:
            data = {}
            name = item["name"]
            width = item["width"]
            if width:
                try:
                    width = int(width)
                    data["width"] = width
                except ValueError:
                    pass
            height = item["height"]
            if height:
                try:
                    height = int(height)
                    data["height"] = height
                except ValueError:
                    pass
            fontData[name] = data
        if fontData:
            self.font.lib[libKey] = fontData
        events.postEvent(
            extensionID + ".measurementsChanged",
            font=self.font
        )

    def addRemoveMeasurementButtonAddCallback(self, sender):
        item = self.table.makeItem()
        items = self.table.get()
        items.append(item)
        self.table.set(items)

    def addRemoveMeasurementButtonRemoveCallback(self, sender):
        selection = self.table.getSelectedIndexes()
        items = self.table.get()
        for index in reversed(sorted(selection)):
            del items[index]
        self.table.set(items)


note = """
The named values sheet is only available
in RoboFont 4.2+.
""".strip()

def NamedValuesSheetController(*args, **kwargs):
    if legacy.versionMajor == 4 and legacy.versionMinor < 2:
        print(note)
    else:
        _NamedValuesSheetController(*args, **kwargs)

if __name__ == "__main__":
    from mojo.UI import CurrentFontWindow
    window = CurrentFontWindow()
    font = window.document.getFont()
    s = NamedValuesSheetController(window.w, font)
