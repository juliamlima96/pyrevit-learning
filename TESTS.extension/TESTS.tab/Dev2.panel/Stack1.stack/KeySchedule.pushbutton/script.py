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
elements_source_doc = FilteredElementCollector(source_doc).OfClass(FamilySymbol).ToElements()
elements_current_doc = FilteredElementCollector(doc).OfClass(FamilySymbol).ToElements()

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

    for c in category_elem_current:
        fam_name_c = c.Family.Name if c.Family else "<sem família>"
        type_name_c = Element.Name.GetValue(c)

        if fam_name == fam_name_c and type_name == type_name_c:
            final_elems.append((e, c))
            break

#get parameters
params = set()
for source_e, current_e in final_elems:
    for p in source_e.Parameters:
        if p and (not p.IsReadOnly) and (p.StorageType == StorageType.String) and (p.HasValue) and (p.AsString() != ""):
            params.add((source_e.Family.Name, Element.Name.GetValue(source_e), p.Definition.Name, p.AsString()))


unique_params = set([p[2] for p in params])
unique_params = sorted(unique_params)

#select parameters
select_params = forms.SelectFromList.show(unique_params, title="Select Parameters to be Transferred", multiselect=True)
if not select_params:
    script.exit()

#transaction
t = Transaction(doc, 'Transfer Parameters')
t.Start()

copied = 0
skipped = 0

missing_in_target = set()
not_string = set()
read_only = set()

for source_e, current_e in final_elems:
    for param_name in select_params:
        source_param = source_e.LookupParameter(param_name)
        current_param = current_e.LookupParameter(param_name)

        if source_param is None:
            continue
        
        if current_param is None:
            missing_in_target.add(param_name)
            continue

        if current_param.StorageType != StorageType.String:
            not_string.add(param_name)
            continue

        if current_param.IsReadOnly:
            read_only.add(param_name)
            continue

        val = source_param.AsString()
        if (val is None) or (val ==""):
            continue

        try:
            current_param.Set(val)
            copied += 1
        except Exception as ex:
            print("Failed to set parameter '{}' to {}: {}".format(param_name, val, ex))
            skipped += 1
            

t.Commit()

#test print
print("Categories: ")
print(select_category)

print("source Document: ")
print(source_doc.Title)


print("Total Parameters Copied: {}".format(copied))
print("Total Parameters Skipped: {}".format(skipped))

if missing_in_target:
    print("\nMissing in TARGET:")
    for n in sorted(missing_in_target):
        print(" - {}".format(n))

if read_only:
    print("\nREAD-ONLY in TARGET:")
    for n in sorted(read_only):
        print(" - {}".format(n))

if not_string:
    print("\nNot STRING (skipped):")
    for n in sorted(not_string):
        print(" - {}".format(n))





    
