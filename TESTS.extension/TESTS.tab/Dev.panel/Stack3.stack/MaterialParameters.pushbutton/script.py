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

#collector to get all materials
all_materials = FilteredElementCollector(doc).OfClass(Material).ToElements()
existing_names = sorted([v.Name for v in all_materials])

#Mark Parameter
all_marks = BuiltInParameter.ALL_MODEL_MARK


#forms to select views to be renamed
selected_names = forms.SelectFromList.show(existing_names,
    title="Select Materials to Rename",
    button_name="Select",
    multiselect=True
)
if not selected_names:
    script.exit()

#Get selected Material Elements
selected_materials = ([(m) for m in all_materials if m.Name in selected_names])

# Take code from name
marks = {}

for name in selected_names:
    if name.startswith("H+A_ID_"):
        mark = name[len("H+A_ID_"):]
    else:
        mark = name

    marks[name] = mark


# Start transaction
t = Transaction(doc, "Update Material Marks")
t.Start()

for material in all_materials:

    if material.Name in selected_names:

        mark = marks[material.Name]

        parameter = material.get_Parameter(all_marks)

        if parameter and not parameter.IsReadOnly:
            parameter.Set(mark)

t.Commit()


# List results
print("selected:")

for material in all_materials:

    if material.Name in selected_names:

        print(" - {} : {}".format(
            material.Name,
            marks[material.Name]
        ))