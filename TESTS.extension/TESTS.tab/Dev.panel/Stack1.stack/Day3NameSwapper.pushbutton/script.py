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
for view in selected_views:
    old_name = view.Name
    base_name = old_name

    if Find and Find in old_name:
        base_name = old_name.replace(Find, Replace)

    new_name = Prefix + base_name + Suffix
    old_key = (view.ViewType, old_name)
    new_key = (view.ViewType, new_name)

    #duplicates in general list of views
    if (new_key in existing_keys) and (new_name != old_name):
        duplicated_keys.add((view, old_name, new_name))
        continue

    #unchanged names
    if (new_name == old_name):
        eq_name_keys.add((view, old_name))
        continue


    #duplicates in the temporary list
    if new_key in temp_keys:
        duplicated_keys.add((view, old_name, new_name))
        continue
    else:
        temp_keys.add(new_key)
        final_keys.add((view, old_name, new_name))

    if not final_keys:
        forms.alert("No views to rename. All new names are either duplicates or unchanged.")
        script.exit()

#rename views that are not duplicates
t = Transaction(doc, "Rename Views")

try:
    t.Start()

    for view, old_name, new_name in final_keys:
        view.Name = new_name

    t.Commit()

except Exception as e:
    if t.HasStarted():
        t.RollBack()
    forms.alert("An error occurred: {}".format(str(e)))
    script.exit()


print ("Names changed:")
for view, on,nn in sorted(list(final_keys), key=lambda x: (str(x[0].ViewType), x[1])):
    print(" - {} ({}) -> {}".format(on, view.ViewType, nn))

print("Conflicts:")
for view, on, nn in sorted(list(duplicated_keys), key=lambda x: (str(x[0].ViewType), x[1])):
    if not duplicated_keys:
        continue
    print(" - {} ({}) -> {}".format(on, view.ViewType, nn))

print("Unchanged:")
for view, on in sorted(list(eq_name_keys), key=lambda x: (str(x[0].ViewType), x[1])):
    if not eq_name_keys:
        continue
    print(" - {} ({})".format(on, view.ViewType))



