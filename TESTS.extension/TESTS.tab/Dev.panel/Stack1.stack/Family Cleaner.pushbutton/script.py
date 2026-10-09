 # -*- coding: utf-8 -*-

# ╦╔╦╗╔═╗╔═╗╦═╗╔╦╗╔═╗
# ║║║║╠═╝║ ║╠╦╝ ║ ╚═╗
# ╩╩ ╩╩  ╚═╝╩╚═ ╩ ╚═╝
#==================================================
from Autodesk.Revit.DB import *
from pyrevit import forms, script
from rpw.ui.forms import FlexForm, Label, TextBox, Button, Separator

#.NET Imports
import clr
clr.AddReference('System')


# ╦  ╦╔═╗╦═╗╦╔═╗╔╗ ╦  ╔═╗╔═╗
# ╚╗╔╝╠═╣╠╦╝║╠═╣╠╩╗║  ║╣ ╚═╗
#  ╚╝ ╩ ╩╩╚═╩╩ ╩╚═╝╩═╝╚═╝╚═╝
#==================================================
app    = __revit__.Application
uidoc  = __revit__.ActiveUIDocument
doc    = __revit__.ActiveUIDocument.Document #type:Document

family_manager = doc.FamilyManager

# ╔╦╗╔═╗╦╔╗╔
# ║║║╠═╣║║║║
# ╩ ╩╩ ╩╩╝╚╝
#==================================================

#check if doc is a family document
if not doc.IsFamilyDocument:
    forms.alert("This Document is not Family Document.")
    script.exit() 

#==================================================
#LIST TYPES
types = family_manager.Types

print("------TYPES BEFORE------")
for type in types:
    print(type.Name)

t = Transaction(doc, 'Clear Types')
t.Start()
try:
    family_manager.NewType("Standard")
    for type in types:
        if type.Name != "Standard":
            family_manager.CurrentType = type
            family_manager.DeleteCurrentType()  
    
    t.Commit()
except:
    t.RollBack()

types = family_manager.Types
print("------FINAL TYPE------")
for type in types:
    print(type.Name)

#==================================================
#RENAME 3D VIEW
all_views  = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Views).WhereElementIsNotElementType().ToElements()


print("----3D VIEWS BEFORE-----")
for view in all_views:
    if view.ViewType == ViewType.ThreeD:
        print (view.Name)

t = Transaction(doc, 'Rename 3D View')
t.Start()
try:
    n = 1
    for view in all_views:
            if view.ViewType == ViewType.ThreeD and view.Name != "{3D}":
                view.Name = "View {}".format(n)
                n += 1    
    t.Commit()
except:
    t.RollBack()


print("-----3D VIEWS AFTER----")
for view in all_views:
    if view.ViewType == ViewType.ThreeD:
        print (view.Name)

#==================================================
#LIST PARAMETERS TO BE CLEANED / DELETED
#family parameter list
parameters = family_manager.Parameters

#array parameters
arrays = FilteredElementCollector(doc)\
    .OfClass(BaseArray)\
    .ToElements()

array_param = []

for array in arrays:
    if array.Label:
        array_param.append(array.Label)

# Expand protection to related parameters
while True:
    protected_names = set(
        p.Definition.Name for p in array_param
    )

    new_parameters = []

    for param in parameters:
        if not param.Formula:
            continue

        param_name = param.Definition.Name

        # Protected parameter:
        # protect parameters used in its formula
        if param_name in protected_names:
            for related_param in parameters:
                related_name = related_param.Definition.Name

                if related_name in protected_names:
                    continue

                if related_name in param.Formula:
                    new_parameters.append(related_param)

        # Unprotected parameter:
        # protect it if its formula uses a protected parameter
        else:
            for protected_name in protected_names:
                if protected_name in param.Formula:
                    new_parameters.append(param)
                    break

    # Add new parameters without duplicating names
    added = False

    for param in new_parameters:
        param_name = param.Definition.Name

        if param_name not in protected_names:
            array_param.append(param)
            protected_names.add(param_name)
            added = True

    if not added:
        break

#filter for parameter we don't wanna touch
def filter_notdimensions(param):
    data_type = param.Definition.GetDataType()
    data_name = param.Definition.Name

    if data_type == SpecTypeId.Length:
        return False

    if data_type == SpecTypeId.Angle:
        return False

    if data_name in [p.Definition.Name for p in array_param]:
        return False

    return True


#Split parameters to be cleared / to be deleted
param_tobedeleted = []
param_tobecleared =[]
for param in parameters:
    is_builtin = param.Id.Value < 0

    if filter_notdimensions(param):
        if not is_builtin:
            param_tobedeleted.append(param)
        else:
            param_tobecleared.append(param)

t = Transaction(doc, 'Parameters')
t.Start()
try:
    count = 0
    for param in param_tobedeleted:
        family_manager.RemoveParameter(param)
        count += 1
    t.Commit()
except:
    t.RollBack()


print("{} parameters to be deleted".format(count))