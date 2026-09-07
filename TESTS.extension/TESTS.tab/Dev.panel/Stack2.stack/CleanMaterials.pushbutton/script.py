# -*- coding: utf-8 -*-

# ╦╔╦╗╔═╗╔═╗╦═╗╔╦╗╔═╗
# ║║║║╠═╝║ ║╠╦╝ ║ ╚═╗
# ╩╩ ╩╩  ╚═╝╩╚═ ╩ ╚═╝
#==================================================
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import * 
from Autodesk.Revit.UI import TaskDialog
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
used_materials = set()

#collector of all elements
elements = FilteredElementCollector(doc).WhereElementIsNotElementType()

#find used materials
for element in elements:
    material_ids = element.GetMaterialIds(False)

    for material_id in material_ids:
        used_materials.add(material_id)

#find unused materials
unused_material_ids = List[ElementId]()

for material in all_materials:
    if material.Id in used_materials:
        continue
    unused_material_ids.Add(material.Id)

if unused_material_ids.Count == 0:
    TaskDialog.Show(
        "Clean Materials",
        "No unused materials found."
    )
else:
    # ╔╦╗╦═╗╔═╗╔╗╔╔═╗╔═╗╔═╗╔╦╗╦╔═╗╔╗╔
    #  ║ ╠╦╝╠═╣║║║╚═╗╠═╣║   ║ ║║ ║║║║
    #  ╩ ╩╚═╩ ╩╝╚╝╚═╝╩ ╩╚═╝ ╩ ╩╚═╝╝╚╝
    #==================================================
    t = Transaction(doc, "Clean Materials")

    t.Start()
    try:
        deleted_ids = doc.Delete(unused_material_ids)

        t.Commit()

    except:

        t.RollBack()
        raise
    TaskDialog.Show(
        "Clean Materials",
        "{} materials were deleted".format(deleted_ids.Count)
    )