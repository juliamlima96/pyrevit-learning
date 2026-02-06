# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import *  
from pyrevit import script,forms

uidoc = __revit__.ActiveUIDocument
current_doc = uidoc.Document
app = __revit__.Application

all_docs = [d for d in app.Documents]
doc_options = [d for d in all_docs if not d.IsLinked]
doc_names = sorted([d.Title for d in doc_options])



#COLLECT SOURCE PROJECT
source_proj = forms.SelectFromList.show(doc_names, multiselect = False, title="Source Project")
if not source_proj:
    forms.alert("No source project selected.")
    script.exit()

for d in doc_options:
    if d.Title == source_proj:
        source_doc = d


#COLLECT TARGET PROJECTS
target_proj = forms.SelectFromList.show(doc_names, multiselect = True, title="Target Project")
if not target_proj:
    forms.alert("No target project selected.")
    script.exit()

target_docs = []
for d in doc_options:
    if d.Title in target_proj:
        target_docs.append(d)

#COLLECT CATEGORIES
CATEGORY_MAP= {
    "Ceiling Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType().ToElements() if isinstance(e, CeilingType)],
    "Dimension Styles": lambda d: list(FilteredElementCollector(d).OfClass(DimensionType).ToElements()),
    "Filters": lambda d: list(FilteredElementCollector(d).OfClass(ParameterFilterElement).ToElements()),
    "Fill Patterns": lambda d: list(FilteredElementCollector(d).OfClass(FillPatternElement).ToElements()),
    "Filled Region Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType().ToElements() if isinstance(e, FilledRegionType)],
    "Floor Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType().ToElements() if isinstance(e, FloorType)],
    "Keynoting Settings": lambda d: list(FilteredElementCollector(d).OfClass(KeynoteTable).ToElements()),
    "Level Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType().ToElements() if isinstance(e, LevelType)],
    "Line Patterns": lambda d: list(FilteredElementCollector(d).OfClass(LinePatternElement).ToElements()),
    "Line Styles": lambda doc: [gs for gs in FilteredElementCollector(doc).OfClass(GraphicsStyle).ToElements()
    if gs
    and gs.GraphicsStyleCategory
    and gs.GraphicsStyleCategory.Parent
    and gs.GraphicsStyleCategory.Parent.Id.IntegerValue == int(BuiltInCategory.OST_Lines)
    and gs.GraphicsStyleType == GraphicsStyleType.Projection
],
    "Materials": lambda d: list(FilteredElementCollector(d).OfClass(Material).ToElements()),
    "Phase Settings": lambda d: list(FilteredElementCollector(d).OfClass(Phase).ToElements()),
    "Roof Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType().ToElements() if isinstance(e, RoofType)],
    "Text Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType().ToElements() if isinstance(e, TextNoteType)],
    "View Templates": lambda d: [v for v in FilteredElementCollector(d).OfClass(View).WhereElementIsNotElementType().ToElements() if v.IsTemplate],
    "Viewport Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType().ToElements() if e.Category and e.Category.Id.IntegerValue == int(BuiltInCategory.OST_Viewports)],
    "Wall Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType().ToElements() if isinstance(e, WallType)],
}
category_names = sorted(CATEGORY_MAP.keys())

cat_key = forms.SelectFromList.show(category_names, multiselect = False, title = "Select Category")
if not cat_key:
    forms.alert("No category selected.")
    script.exit()

#COLLECT ELEMENTS
def get_name(el):
    #Line Styles (GraphicStyle)
    try:
        if isinstance(el, GraphicsStyle) and el.GraphicsStyleCategory:
            return el.GraphicsStyleCategory.Name
    except:
        pass

    #General Types
    try:
        p = el.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
        if p and p.HasValue:
            n = p.AsString()
            if n:
                return n
    except:
        pass

    #General Fallback
    try:
        if hasattr(el,"Name") and el.Name:
            return el.Name
    except:
        pass

    #Last Fallback
    try:
        return "Id {}".format(el.Id.IntegerValue)
    except:
        return "No name"


selected_elements = []

src_elements = CATEGORY_MAP [cat_key](source_doc)

name_to_elements = {}
for e in src_elements:
    n = get_name(e)
    if not n:
        continue
    name_to_elements.setdefault(n, []).append(e)

    names = sorted(name_to_elements.keys())

picked_names = forms.SelectFromList.show(names, multiselect=True,title="{} (Source: {})".format(cat_key,source_doc.Title))

if picked_names:   
    for n in picked_names:
        selected_elements.extend(name_to_elements[n])

forms.alert("Selecionados {} elemento(s) no total.".format(len(selected_elements)))

    
