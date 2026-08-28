# -*- coding: utf-8 -*-

import clr
clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import TaskDialog

from pyrevit import forms

doc = __revit__.ActiveUIDocument.Document

# Selecionar sheet de referência
selected_sheets = forms.select_sheets(
    title='Select Reference Sheet',
    button_name='Select Reference',
    multiple=False
)

if not selected_sheets:
    forms.alert("No sheet selected.", exitscript=True)

ref_sheet = selected_sheets

def get_titleblock_on_sheet(sheet):
    titleblocks = FilteredElementCollector(doc, sheet.Id)\
        .OfCategory(BuiltInCategory.OST_TitleBlocks)\
        .WhereElementIsNotElementType()\
        .ToElements()

    if titleblocks:
        return titleblocks[0]

    return None

def get_location_point(elem):
    loc = elem.Location

    if loc and isinstance(loc, LocationPoint):
        return loc.Point

    return None

# Reference titleblock
ref_tb = get_titleblock_on_sheet(ref_sheet)

if ref_tb is None:
    forms.alert("No title block found on reference sheet.", exitscript=True)

ref_point = get_location_point(ref_tb)

if ref_point is None:
    forms.alert("Could not get title block location.", exitscript=True)

# Collect sheets
all_sheets = FilteredElementCollector(doc)\
    .OfClass(ViewSheet)\
    .ToElements()

t = Transaction(doc, "Align Sheet Title Blocks")
t.Start()

moved = 0
skipped = []

try:

    for sheet in all_sheets:

        if sheet.Id == ref_sheet.Id:
            continue

        tb = get_titleblock_on_sheet(sheet)

        if tb is None:
            skipped.append("{} - no title block".format(sheet.SheetNumber))
            continue

        current_point = get_location_point(tb)

        if current_point is None:
            skipped.append("{} - no location point".format(sheet.SheetNumber))
            continue

        vector = ref_point - current_point

        if vector.GetLength() > 0.0001:
            ElementTransformUtils.MoveElement(doc, tb.Id, vector)
            moved += 1

    t.Commit()

except Exception as ex:

    t.RollBack()
    forms.alert(str(ex))
    raise

msg = "{} sheets aligned.".format(moved)

if skipped:
    msg += "\n\nSkipped:\n"
    msg += "\n".join(skipped)

forms.alert(msg, title="Finished")