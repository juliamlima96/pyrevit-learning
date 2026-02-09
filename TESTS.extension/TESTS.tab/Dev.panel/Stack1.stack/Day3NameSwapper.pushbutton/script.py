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

#collector to get all views in the project, and create a set of existing (ViewType, Name) combinations to check against when renaming views.
all_views = FilteredElementCollector(doc).OfClass(View).ToElements()
existing_keys = set([(v.ViewType, v.Name) for v in all_views])

#forms to select views to be renamed
selected_views = forms.select_views(
    title="Select Views to Rename",
    button_name="Select"
)
if not selected_views:
    forms.alert("No views selected.")
    script.exit()

#define UI-forms form renaming components
components = [Label('Prefix'), TextBox('prefix'), 
              Label('Find'), TextBox('find'), 
              Label('Replace'), TextBox('replace'),
              Label('Suffix'), TextBox('suffix'),
                Separator(),
                Button ('Rename')
              ]

#Display Form to users
form = FlexForm('View Renamer', components)
form.show()

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
temp_keys =set()
eq_name_keys = set()

#check for duplicates in the general list
for view in selected_views:
    old_name = view.Name
    base_name = old_name

    if Find and Find in old_name:
        base_name = old_name.replace(Find, Replace)

    new_name = Prefix + base_name + Suffix
    old_key = (view.ViewType, old_name)
    new_key = (view.ViewType, new_name)

    if (new_key in existing_keys) and (new_name != old_name):
        duplicated_keys.add((view.ViewType, old_name, new_name))
        continue
    if (new_name == old_name):
        eq_name_keys.add(old_key)
        continue
    
    #check for duplicates in the temporary list
    if new_key in temp_keys:
        duplicated_keys.add((view.ViewType, old_name, new_name))
        temp_keys.discard(new_key) #remove from temp keys to avoid multiple duplicates
        continue

    temp_keys.add((new_key))


print ("names changed:")
for nvt, nn in sorted(list(temp_keys), key=lambda x: (str(x[0]), x[1])):
    print(" - {} ({})".format(nvt,nn))

print("Conflicts:")
for vt, on, nn in sorted(list(duplicated_keys), key=lambda x: (str(x[0]), x[1])):
    print(" - {} ({}) -> ({})".format(vt, on, nn))

print("Unchanged:")
for vt, on in sorted(list(eq_name_keys), key=lambda x: (str(x[0]), x[1])):
    print(" - {} ({})".format(on, vt))

#temporary list (validation)
#================================================
#    renaming_views.append((view, old_name, new_name))
#    print(old_name, "==>", new_name)
#
#print("Conflicts:")
#for vt, nm in sorted(list(duplicated_keys), key=lambda x: (str(x[0]), x[1])):
#    print(" - {} ({})".format(nm, vt))
#==================================================

#Apply renaming in Revit

