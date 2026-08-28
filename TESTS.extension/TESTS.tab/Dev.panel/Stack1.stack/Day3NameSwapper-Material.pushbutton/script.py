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


#forms to select views to be renamed
selected_names = forms.SelectFromList.show(existing_names,
    title="Select Materials to Rename",
    button_name="Select",
    multiselect=True
)
if not selected_names:
    script.exit()

selected_materials = ([(m) for m in all_materials if m.Name in selected_names])

#define UI-forms form renaming components
components = [Label('Prefix'), TextBox('prefix'), 
              Label('Find'), TextBox('find'), 
              Label('Replace'), TextBox('replace'),
              Label('Suffix'), TextBox('suffix'),
                Separator(),
                Button ('Rename')
              ]

#Display Form to users
form = FlexForm('Material Renamer', components)
form.show()

if not form.values:
    script.exit()

#Read user input
values = form.values
Prefix = values['prefix'] or "" 
Find = values['find'] or ""
Replace = values['replace'] or ""
Suffix = values['suffix'] or ""

if not values['prefix'] and not values['find'] and not values['replace'] and not values['suffix']:
    forms.alert("No values provided.")
    script.exit()

#change names of selected views
duplicated_keys = set()
eq_name_keys = set()
temp_keys =set()
final_keys = set()

#check for duplicates
for material in selected_materials:
    old_name = material.Name
    base_name = old_name

    if Find and Find in old_name:
        base_name = old_name.replace(Find, Replace)

    new_name = Prefix + base_name + Suffix

    #duplicates in general list of views
    if (new_name in existing_names) and (new_name != old_name):
        duplicated_keys.add((old_name, new_name))
        continue

    #unchanged names
    if (new_name == old_name):
        eq_name_keys.add((old_name))
        continue


    #duplicates in the temporary list
    if new_name in temp_keys:
        duplicated_keys.add((old_name, new_name))
        continue
    else:
        temp_keys.add(new_name)
        final_keys.add((material, old_name, new_name))

if not final_keys:
    forms.alert("No materials to rename. All new names are either duplicates or unchanged.")
    script.exit()

#rename materials that are not duplicates
t = Transaction(doc, "Rename Materials")

try:
    t.Start()

    for material, old_name, new_name in final_keys:
        material.Name = new_name

    t.Commit()

except Exception as e:
    if t.HasStarted():
        t.RollBack()
    forms.alert("An error occurred: {}".format(str(e)))
    script.exit()


print ("Names changed:")
for material, old_name, new_name in sorted(list(final_keys), key=lambda x: (str(x[1]))):
    print(" - {} -> {}".format(old_name, new_name))

print("Conflicts:")
for old_name, new_name in sorted(list(duplicated_keys), key=lambda x: (str(x[0]))):
    if not duplicated_keys:
        continue
    print(" - {} -> {}".format(old_name, new_name))

print("Unchanged:")
for old_name in sorted(list(eq_name_keys), key=lambda x: (str(x[0]))):
    if not eq_name_keys:
        continue
    print(" - {}".format(old_name))



