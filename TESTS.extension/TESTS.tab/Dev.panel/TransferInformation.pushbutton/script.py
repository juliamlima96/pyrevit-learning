# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import *  
from pyrevit import script,forms

app    = __revit__.Application
uidoc  = __revit__.ActiveUIDocument
doc    = __revit__.ActiveUIDocument.Document

all_docs = [d for d in app.Documents]
doc_options = [d for d in all_docs if not d.IsLinked]
doc_names = sorted([d.Title for d in doc_options])

#collect source project
source_proj = forms.SelectFromList.show(doc_names, multiselect = False, title="Source Project")
if not source_proj:
    forms.alert("No source project selected.")
    script.exit()

for d in doc_options:
    if d.Title == source_proj:
        source_doc = d

#collect elements
elements_source_doc = FilteredElementCollector(source_doc).OfClass(FamilySymbol)
elements_current_doc = FilteredElementCollector(doc).OfClass(FamilySymbol)

#categories
categories = set()

for e in elements_source_doc:
    if e.Category:
        categories.add(e.Category.Name)

categories = sorted(categories)

#select category
select_category = forms.SelectFromList.show(categories, title="Select Category to Transfer")

#get elements of that category
category_elem_source = [e for e in elements_source_doc if e.Category and e.Category.Name == select_category]
category_elem_current = [e for e in elements_current_doc if e.Category and e.Category.Name == select_category]

#compare between source and target docs
final_elems = []
for e in category_elem_source:
    fam_name = e.Family.Name if e.Family else "<sem família>"
    type_name = Element.Name.GetValue(e)
    match = False
    for c in category_elem_current:
        fam_name_c = c.Family.Name if c.Family else "<sem família>"
        type_name_c = Element.Name.GetValue(c)
        if fam_name == fam_name_c and type_name == type_name_c:
            match = True
    if match:
        final_elems.append(e)

#get parameters
params = set()
for e in final_elems:
    for p in e.Parameters:
        if p and (not p.IsReadOnly) and (p.StorageType == StorageType.String) and (p.HasValue) and (p.TypeId != "autodesk.parameter.group:ifc-1.0.0"):
            params.add((e.Family.Name, p.Definition.Name, p.AsString()))

params = sorted(params)

#test print
print("Categories: ")
print(select_category)

print("source Document: ")
print(source_doc.Title)

print("Elements in Category: ")
for e in final_elems:
    fam_name = e.Family.Name if e.Family else "<sem família>"
    type_name = Element.Name.GetValue(e)  # mais seguro que e.Name
    print(" - {} : {}".format(fam_name, type_name))

print("Parameters: ")
for p in params:
    print(" - {}".format(p))





    
