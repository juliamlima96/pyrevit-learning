# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import *  
from pyrevit import script,forms

app    = __revit__.Application
uidoc  = __revit__.ActiveUIDocument
doc    = __revit__.ActiveUIDocument.Document #type:Document

elements = FilteredElementCollector(doc).WherePasses(ALL_MODEL_MARK).WhereElementIsNotElementType().ToElements()

mark_el = []
for e in elements:
    if not ALL_MODEL_MARK.HasValue(e):
        continue
    else:
        mark_el.append(e)

forms.alert("Encontrados {} elementos com marca.".format(len(mark_el)))










    
