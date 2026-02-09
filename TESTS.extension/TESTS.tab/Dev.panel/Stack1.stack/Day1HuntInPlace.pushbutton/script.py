#-*- coding: utf-8 -*-

# ╦╔╦╗╔═╗╔═╗╦═╗╔╦╗╔═╗
# ║║║║╠═╝║ ║╠╦╝ ║ ╚═╗
# ╩╩ ╩╩  ╚═╝╩╚═ ╩ ╚═╝
#==================================================
from Autodesk.Revit.DB import *
from pyrevit import script
output = script.get_output()


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

#Get all loadable families in the document

elements = FilteredElementCollector(doc).OfClass(FamilyInstance)

#Discards Elements With no Type / Family:

for elem in elements:
    type_id = elem.GetTypeId()
    if type_id == ElementId.InvalidElementId:
            continue
    
    elem_type = doc.GetElement(type_id)
    if not elem_type:
        continue
    if not hasattr(elem_type, "Family"):
        continue
   
    elem_id = elem.Id
    family = elem_type.Family
    if not family.IsInPlace:
        continue

    #output.print_md("### Family: {} | TypeId: {} | instanceId: {} | FamilyId: {}".format(family.Name, type_id, elem_id, family.Id))

    inst_link = output.linkify (elem_id)

    output.print_md("Family: {} | Instance Link: {}".format(family.Name, inst_link))
#==================================================