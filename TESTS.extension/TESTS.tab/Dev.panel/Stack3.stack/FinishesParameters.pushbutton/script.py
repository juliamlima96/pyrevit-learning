 # -*- coding: utf-8 -*-

# ╦╔╦╗╔═╗╔═╗╦═╗╔╦╗╔═╗
# ║║║║╠═╝║ ║╠╦╝ ║ ╚═╗
# ╩╩ ╩╩  ╚═╝╩╚═ ╩ ╚═╝
#==================================================
from Autodesk.Revit.DB import *
from pyrevit import forms, script
from rpw.ui.forms import FlexForm, Label, ComboBox, TextBox, Button, CheckBox, Separator

#.NET Imports
import clr
clr.AddReference('System')
from System.Collections.Generic import List


# ╦  ╦╔═╗╦═╗╦╔═╗╔╗ ╦  ╔═╗╔═╗
# ╚╗╔╝╠═╣╠╦╝║╠═╣╠╩╗║  ║╣ ╚═╗
#  ╚╝ ╩ ╩╩╚═╩╩ ╩╚═╝╩═╝╚═╝╚═╝
#==================================================
app    = __revit__.Application
uidoc  = __revit__.ActiveUIDocument
doc    = __revit__.ActiveUIDocument.Document #type:Document


# ╔╦╗╔═╗╦╔╗╔
# ║║║╠═╣║║║║
# ╩ ╩╩ ╩╩╝╚╝
#==================================================

#collector to get all finishes
all_finishes = []

#Parameters
type_mark = BuiltInParameter.ALL_MODEL_TYPE_MARK
ass_code = BuiltInParameter.UNIFORMAT_CODE

# collect Floor Types
floor_types = FilteredElementCollector(doc).OfClass(FloorType).ToElements()

for floor in floor_types:
    all_finishes.append(floor)

# collect Wall Types
wall_types = FilteredElementCollector(doc).OfClass(WallType).ToElements()

for wall in wall_types:
    all_finishes.append(wall)

# collect Ceiling Types
ceiling_types = FilteredElementCollector(doc).OfClass(CeilingType).ToElements()

for ceiling in ceiling_types:
    all_finishes.append(ceiling)

# name collector
finishes_names = []
for e in all_finishes:
    finishes_names.append(Element.Name.GetValue(e))

#forms to select views to be renamed
selected_names = forms.SelectFromList.show(finishes_names,
    title="Select Finishes",
    button_name="Select",
    multiselect=True
)
if not selected_names:
    script.exit()

# Take code from name
codes = {}

for name in selected_names:
    if name.startswith("H+A_ID_"):
        code = name[len("H+A_ID_"):]
    else:
        code = name

    codes[name] = code

#Start Transaction
t = Transaction(doc, "Update Finish Marks")
t.Start()

for e in all_finishes:

    if Element.Name.GetValue(e) in selected_names:

        code = codes[Element.Name.GetValue(e)]

        asscode = e.get_Parameter(ass_code)

        if asscode and not asscode.IsReadOnly:
            asscode.Set(code)

        typemark = e.get_Parameter(type_mark)

        if typemark and not typemark.IsReadOnly:
            typemark.Set(code)

t.Commit()

print("selected:")

for name in selected_names:
    print(" - {}".format(name))