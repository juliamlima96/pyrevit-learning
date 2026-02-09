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
Prefix = values['prefix']
Find = values['find']
Replace = values['replace']
Suffix = values['suffix']

if not values['prefix'] and not values['find'] and not values['replace'] and not values['suffix']:
    forms.alert("No values provided.")
    script.exit()

#change names of selected views
renaming_views = []
duplicated_keys = set()
temp_keys =set((v.ViewType, v.Name) for v in selected_views)

for view in selected_views:
    old_name = view.Name
    base_name = old_name

    if Find and Find in old_name:
        base_name = old_name.replace(Find, Replace)

    new_name = Prefix + base_name + Suffix
    old_key = (view.ViewType, old_name)
    new_key = (view.ViewType, new_name)

    #discard temporarily
    temp_keys.discard(old_key)

    if new_key in temp_keys:
        duplicated_keys.add(new_key)
        temp_keys.add(old_key) #undo discard of old key
        continue


    if (new_key in existing_keys) and (new_name != old_name):
        duplicated_keys.add((old_key))
        temp_keys.add(old_key) #undo discard of old key
        continue

    temp_keys.add(new_key)

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
if not renaming_views:
    forms.alert("No views renamed. Please check for naming conflicts.")
    script.exit()  

failed = []

t = Transaction(doc, "Rename Views")
t.Start()

print ("Renaming Views...")
for view in selected_views
