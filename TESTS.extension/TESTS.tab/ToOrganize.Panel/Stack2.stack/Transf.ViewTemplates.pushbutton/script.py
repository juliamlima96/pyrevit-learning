# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import *
from pyrevit import script, forms
from System.Collections.Generic import List


uidoc = __revit__.ActiveUIDocument
current_doc = uidoc.Document
app = __revit__.Application
output = script.get_output()


class DuplicateTypeNamesHandler(IDuplicateTypeNamesHandler):
    def OnDuplicateTypeNamesFound(self, args):
        return DuplicateTypeAction.UseDestinationTypes


def get_element_id_value(element_id):
    try:
        return element_id.Value
    except:
        return element_id.IntegerValue


def collect_filters_from_viewtemplates(viewtemplates):
    filter_ids = {}

    for vt in viewtemplates:
        try:
            ids = vt.GetFilters()
            for fid in ids:
                filter_ids[get_element_id_value(fid)] = fid
        except:
            pass

    return filter_ids.values()

def copy_viewtemplates_and_filters(source_doc, target_doc, selected_viewtemplates):
    ids_to_copy = {}

    # Adiciona os View Templates
    for vt in selected_viewtemplates:
        ids_to_copy[get_element_id_value(vt.Id)] = vt.Id

    # Adiciona os Filters usados nesses View Templates
    filter_ids = collect_filters_from_viewtemplates(selected_viewtemplates)

    for fid in filter_ids:
        ids_to_copy[get_element_id_value(fid)] = fid

    if not ids_to_copy:
        print("Nothing to copy to {}".format(target_doc.Title))
        return

    ids_list = List[ElementId]()

    for eid in ids_to_copy.values():
        ids_list.Add(eid)

    copy_options = CopyPasteOptions()
    copy_options.SetDuplicateTypeNamesHandler(DuplicateTypeNamesHandler())

    t = Transaction(target_doc, "Transfer View Templates and Filters")

    try:
        t.Start()

        copied_ids = ElementTransformUtils.CopyElements(
            source_doc,
            ids_list,
            target_doc,
            Transform.Identity,
            copy_options
        )

        t.Commit()

        print("Copied to: {}".format(target_doc.Title))
        print("Total elements copied: {}".format(copied_ids.Count))
        print("-" * 50)

    except Exception as ex:
        if t.HasStarted():
            t.RollBack()

        print("FAILED copying to: {}".format(target_doc.Title))
        print(str(ex))
        print("-" * 50)


# --------------------------------------------------
# COLLECT DOCUMENTS
# --------------------------------------------------

all_docs = [d for d in app.Documents]
doc_options = [d for d in all_docs if not d.IsLinked]
doc_names = sorted([d.Title for d in doc_options])


# --------------------------------------------------
# COLLECT SOURCE PROJECT
# --------------------------------------------------

source_proj = forms.SelectFromList.show(
    doc_names,
    multiselect=False,
    title="Source Project"
)

if not source_proj:
    forms.alert("No source project selected.")
    script.exit()

source_doc = None

for d in doc_options:
    if d.Title == source_proj:
        source_doc = d
        break

if source_doc is None:
    forms.alert("Source document not found.")
    script.exit()


# --------------------------------------------------
# COLLECT TARGET PROJECTS
# --------------------------------------------------

target_proj = forms.SelectFromList.show(
    doc_names,
    multiselect=True,
    title="Target Project"
)

if not target_proj:
    forms.alert("No target project selected.")
    script.exit()

target_docs = []

for d in doc_options:
    if d.Title in target_proj:
        if d.Title != source_doc.Title:
            target_docs.append(d)

if not target_docs:
    forms.alert("No valid target project selected.")
    script.exit()


# --------------------------------------------------
# COLLECT VIEW TEMPLATES FROM SOURCE DOC
# --------------------------------------------------

viewtemplates = []

all_views = FilteredElementCollector(source_doc).OfClass(View).ToElements()

for v in all_views:
    if v.IsTemplate:
        viewtemplates.append(v)

viewtemplates = sorted(viewtemplates, key=lambda x: x.Name)


# --------------------------------------------------
# SELECT VIEW TEMPLATES
# --------------------------------------------------

selected_viewtemplates = forms.SelectFromList.show(
    viewtemplates,
    name_attr="Name",
    multiselect=True,
    title="Select View Templates from Source Project"
)

if not selected_viewtemplates:
    forms.alert("No view template selected.")
    script.exit()


# --------------------------------------------------
# COPY VIEW TEMPLATES + FILTERS
# --------------------------------------------------

for target_doc in target_docs:
    copy_viewtemplates_and_filters(
        source_doc,
        target_doc,
        selected_viewtemplates
    )

forms.alert("Transfer completed. Check pyRevit output for details.")