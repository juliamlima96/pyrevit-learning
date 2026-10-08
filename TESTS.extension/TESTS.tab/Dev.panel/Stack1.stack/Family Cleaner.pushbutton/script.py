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


# ╔╦╗╔═╗╦╔╗╔
# ║║║╠═╣║║║║
# ╩ ╩╩ ╩╩╝╚╝
#==================================================

#check if doc is a family document
if not doc.IsFamilyDocument:
    forms.alert("This Document is not Family Document.")
    script.exit() 

#==================================================
#LIST PARAMETERS TO BE CLEANED / DELETED
#family parameter list
family_manager = doc.FamilyManager
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



# print
for param in parameters:
    data_type = param.Definition.GetDataType()
    print(param.Definition.Name, param.IsReadOnly, data_type.TypeId)

print ("----------------")
for param in array_param:
    data_type = param.Definition.GetDataType()
    print(param.Definition.Name, param.IsReadOnly, data_type.TypeId)

print ("----------------")
print ("PARAMETERS TO BE CLEARED")
for param in param_tobecleared:
    data_type = param.Definition.GetDataType()
    if filter_notdimensions(param):
        print(param.Definition.Name, param.IsReadOnly, data_type.TypeId)

print ("----------------")
print ("PARAMETERS TO BE DELETED")
for param in param_tobedeleted:
    data_type = param.Definition.GetDataType()
    if filter_notdimensions(param):
        print(param.Definition.Name, param.IsReadOnly, data_type.TypeId)

#==================================================
#CREATE NEW TYPE "STANDARD" AND DELETE ALL OTHERS
types = family_manager.Types

print ("----------------")
print ("TYPES")
for type in types:
    print(type.Name)