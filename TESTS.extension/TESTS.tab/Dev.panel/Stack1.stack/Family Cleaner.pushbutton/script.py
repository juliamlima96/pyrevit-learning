 # -*- coding: utf-8 -*-

# ╦╔╦╗╔═╗╔═╗╦═╗╔╦╗╔═╗
# ║║║║╠═╝║ ║╠╦╝ ║ ╚═╗
# ╩╩ ╩╩  ╚═╝╩╚═ ╩ ╚═╝
#==================================================
#.NET Imports
import clr
clr.AddReference('System')
clr.AddReference("System.Core")

from Autodesk.Revit.DB import *
from System.Collections.Generic import HashSet
from pyrevit import forms, script

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
#==================================================
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
#==================================================
all_views  = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Views).WhereElementIsNotElementType().ToElements()

print("----3D VIEWS BEFORE-----")
views_3d = [
    view for view in all_views
    if view.ViewType == ViewType.ThreeD
    and not view.IsTemplate
    and view.Name != "{3D}"
]

for view in views_3d:
    print(view.Name)

t = Transaction(doc, 'Rename 3D View')
t.Start()
try:
    n = 1
    for view in views_3d:
        view.Name = "View {}".format(n)

        if view.IsLocked:
            view.Unlock()

        n += 1
    t.Commit()
except:
    t.RollBack()


print("-----3D VIEWS AFTER----")
for view in views_3d:
    print(view.Name)


#==================================================
#LIST PARAMETERS TO BE CLEANED / DELETED
#==================================================
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

    if data_type == SpecTypeId.Boolean.YesNo:
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


t = Transaction(doc, 'Clean Family Parameters')
t.Start()

#subtransaction to clear formulas
st1 = SubTransaction(doc)
st1.Start()
try:        
    for param in param_tobecleared:
        if param.Formula:
            family_manager.SetFormula(param, None)

    st1.Commit()
except:
    st1.RollBack()

#subtransaction to clear values
st2 = SubTransaction(doc)
st2.Start()
try:
    count_cleared = 0
    for param in param_tobecleared:
        if param.StorageType == StorageType.String:
            family_manager.Set(param, "")
            count_cleared += 1
        elif param.StorageType == StorageType.ElementId:
            family_manager.Set(param, ElementId.InvalidElementId)
            count_cleared += 1

    st2.Commit()
except:
    st2.RollBack()

#subtransaction to delete parameters
st3 = SubTransaction(doc)
st3.Start()
try:
    count_deleted = 0
    for param in param_tobedeleted:
        family_manager.RemoveParameter(param)
        count_deleted += 1

    st3.Commit()
except:
    st3.RollBack()  
t.Commit()

print("------PARAMETERS------")

print("Parameters cleared: {}".format(count_cleared))
print("Parameters deleted: {}".format(count_deleted))

#==================================================
#REMOVE MATERIALS
#==================================================
materials = FilteredElementCollector(doc)\
    .OfClass(Material)\
    .ToElements()

appearance_assets = FilteredElementCollector(doc)\
    .OfClass(AppearanceAssetElement)\
    .ToElements()

property_assets = FilteredElementCollector(doc)\
    .OfClass(PropertySetElement)\
    .ToElements()

print("------MATERIALS------")

t = Transaction(doc, 'Remove Materials and Assets')
t.Start()

count_removed = 0
count_assets = 0

try:
    # STEP 1 - DELETE MATERIALS
    for material in materials:
        doc.Delete(material.Id)
        count_removed += 1

    # STEP 2 - DELETE APPEARANCE ASSETS
    for asset in appearance_assets:
        try:
            doc.Delete(asset.Id)
            count_assets += 1
        except Exception as e:
            print("Cannot delete asset {}: {}".format(
                asset.Name, e
            ))

    # STEP 3 - DELETE PHYSICAL ASSETS
    for asset in property_assets:
        try:
            doc.Delete(asset.Id)
            count_assets += 1
        except Exception as e:
            print("Cannot delete asset {}: {}".format(
                asset.Name, e
            ))

    t.Commit()

except Exception as e:
    t.RollBack()
    print("ERROR: {}".format(e))

print("------RESULTS------")
print("{} materials removed".format(count_removed))
print("{} assets removed".format(count_assets))