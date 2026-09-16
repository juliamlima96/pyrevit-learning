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

for param in parameters:
    if param.Formula:
        for array in array_param:
            array_name = array.Definition.Name
            if array_name in param.Formula:
                array_param.append(param)

#filter for parameter we don't wanna touch
def filter_notdimensions(param):
    data_type = param.Definition.GetDataType()

    if data_type == SpecTypeId.Length:
        return False

    if data_type == SpecTypeId.Angle:
        return False

    if param in array_param:
        return False

    return True

for param in parameters:
    data_type = param.Definition.GetDataType()
    if filter_notdimensions(param):
        print(param.Definition.Name, param.IsReadOnly, data_type.TypeId)

print ("----------------")

for array in array_param:
    print(array.Definition.Name)