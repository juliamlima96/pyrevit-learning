# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

from Autodesk.Revit.DB import *
from System.Collections.Generic import List
from System.Windows.Forms import (
    Application, Form, Label, ComboBox, CheckedListBox, Button,
    FormStartPosition, ComboBoxStyle, MessageBox, MessageBoxButtons, DialogResult
)
from System.Drawing import Point, Size

uidoc = __revit__.ActiveUIDocument
app = __revit__.Application
doc_opt = [d for d in app.Documents if not d.IsLinked]
doc_names = sorted(d.Title for d in doc_opt)

CATEGORY_MAP = {
    "Ceiling Types": lambda d: FilteredElementCollector(d).OfClass(CeilingType).ToElements(),
    "Dimension Styles": lambda d: FilteredElementCollector(d).OfClass(DimensionType).ToElements(),
    "Door Types": lambda d: FilteredElementCollector(d).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_Doors).ToElements(),
    "Filters": lambda d: FilteredElementCollector(d).OfClass(ParameterFilterElement).ToElements(),
    "Fill Patterns": lambda d: FilteredElementCollector(d).OfClass(FillPatternElement).ToElements(),
    "Floor Types": lambda d: FilteredElementCollector(d).OfClass(FloorType).ToElements(),
    "Level Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType() if isinstance(e, LevelType)],
    "Line Patterns": lambda d: FilteredElementCollector(d).OfClass(LinePatternElement).ToElements(),
    "Materials": lambda d: FilteredElementCollector(d).OfClass(Material).ToElements(),
    "Roof Types": lambda d: FilteredElementCollector(d).OfClass(RoofType).ToElements(),
    "Text Types": lambda d: [e for e in FilteredElementCollector(d).WhereElementIsElementType() if isinstance(e, TextNoteType)],
    "View Templates": lambda d: [v for v in FilteredElementCollector(d).OfClass(View).WhereElementIsNotElementType() if v.IsTemplate],
    "Wall Types": lambda d: FilteredElementCollector(d).OfClass(WallType).ToElements(),
}

class OverwriteHandler(IDuplicateTypeNamesHandler):
    """Force overwrite of duplicate types"""
    def OnDuplicateTypeNamesFound(self, args):
        return DuplicateTypeAction.UseDestinationTypes

def get_name(e):
    try:
        p = e.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
        if p and p.HasValue:
            return p.AsString()
        if isinstance(e, FamilySymbol):
            return "{}: {}".format(e.Family.Name, e.Name)
        return e.Name
    except:
        return ""

def delete_existing_types(tgt_doc, cat_key, names_to_replace):
    """Delete existing types that will be replaced"""
    deleted = 0
    try:
        tgt_elems = CATEGORY_MAP[cat_key](tgt_doc)
        ids_to_delete = List[ElementId]()
        
        for elem in tgt_elems:
            elem_name = get_name(elem)
            if elem_name in names_to_replace:
                ids_to_delete.Add(elem.Id)
        
        if ids_to_delete.Count > 0:
            t = Transaction(tgt_doc, "Delete Existing Types")
            t.Start()
            try:
                deleted_ids = tgt_doc.Delete(ids_to_delete)
                deleted = deleted_ids.Count
                t.Commit()
            except:
                t.RollBack()
    except:
        pass
    
    return deleted

def copy_with_dependencies(src_elems, src_doc, tgt_doc):
    """Copy elements with ALL their dependencies"""
    copied = 0
    
    try:
        all_ids = List[ElementId]()
        for elem in src_elems:
            all_ids.Add(elem.Id)
        
        if all_ids.Count == 0:
            return 0
        
        t = Transaction(tgt_doc, "Copy Elements with Dependencies")
        t.Start()
        try:
            opts = CopyPasteOptions()
            opts.SetDuplicateTypeNamesHandler(OverwriteHandler())
            
            copied_ids = ElementTransformUtils.CopyElements(
                src_doc, 
                all_ids, 
                tgt_doc, 
                None, 
                opts
            )
            copied = copied_ids.Count
            t.Commit()
        except:
            t.RollBack()
    except:
        pass
    
    return copied

def transfer_by_deletion_and_copy(src_elems, src_doc, tgt_doc, cat_key):
    """Complete replacement: delete existing, then copy fresh from source"""
    
    names_to_replace = set(get_name(e) for e in src_elems if get_name(e))
    
    stats = {
        "deleted": 0,
        "copied": 0
    }
    
    stats["deleted"] = delete_existing_types(tgt_doc, cat_key, names_to_replace)
    stats["copied"] = copy_with_dependencies(src_elems, src_doc, tgt_doc)
    
    return stats

class ProjectSelectorForm(Form):
    def __init__(self):
        self.Text = "Copy & Replace Standards"
        self.Size = Size(480, 480)
        self.StartPosition = FormStartPosition.CenterScreen

        Label(Text="Source Project:", Location=Point(10, 20), Size=Size(130, 20), Parent=self)
        self.cmb_src = ComboBox(Location=Point(10, 40), Size=Size(450, 23),
                                DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for n in doc_names: 
            self.cmb_src.Items.Add(n)

        Label(Text="Target Projects:", Location=Point(10, 80), Size=Size(130, 20), Parent=self)
        self.chk_tgt = CheckedListBox(Location=Point(10, 100), Size=Size(450, 300),
                                      ScrollAlwaysVisible=True, Parent=self)
        for n in doc_names: 
            self.chk_tgt.Items.Add(n)

        btn = Button(Text="Next", Location=Point(370, 410), Size=Size(90, 30), Parent=self)
        btn.Click += self.next

    def next(self, s, e):
        if not self.cmb_src.SelectedItem or self.chk_tgt.CheckedItems.Count == 0:
            MessageBox.Show("Select source and at least one target.", "Error")
            return
        
        src_title = self.cmb_src.SelectedItem
        tgt_titles = [self.chk_tgt.Items[i] for i in self.chk_tgt.CheckedIndices]
        src_doc = next(d for d in doc_opt if d.Title == src_title)
        tgt_docs = [d for d in doc_opt if d.Title in tgt_titles]
        
        self.Hide()
        CategorySelectorForm(src_doc, tgt_docs).ShowDialog()
        self.Close()

class CategorySelectorForm(Form):
    def __init__(self, src_doc, tgt_docs):
        self.src_doc = src_doc
        self.tgt_docs = tgt_docs
        self.Text = "Select Category and Items to Replace"
        self.Size = Size(520, 620)
        self.StartPosition = FormStartPosition.CenterScreen

        Label(Text="Category:", Location=Point(10, 20), Size=Size(130, 20), Parent=self)
        self.cmb_cat = ComboBox(Location=Point(10, 40), Size=Size(490, 23),
                                DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for c in sorted(CATEGORY_MAP.keys()): 
            self.cmb_cat.Items.Add(c)
        self.cmb_cat.SelectedIndexChanged += self.load

        Label(Text="Items to Copy & Replace:", Location=Point(10, 80), Size=Size(200, 20), Parent=self)
        self.chk_items = CheckedListBox(Location=Point(10, 100), Size=Size(490, 400),
                                        ScrollAlwaysVisible=True, Parent=self)

        Button(Text="All", Location=Point(10, 510), Size=Size(80, 25), Parent=self).Click += self.sel_all
        Button(Text="None", Location=Point(100, 510), Size=Size(80, 25), Parent=self).Click += self.sel_none
        Button(Text="Copy & Replace", Location=Point(380, 550), Size=Size(130, 30), Parent=self).Click += self.transfer

    def load(self, s, e):
        self.chk_items.Items.Clear()
        key = self.cmb_cat.SelectedItem
        if not key: 
            return
        try:
            elems = CATEGORY_MAP[key](self.src_doc)
            names = sorted(n for n in (get_name(e) for e in elems) if n)
            for n in names: 
                self.chk_items.Items.Add(n)
        except Exception as ex:
            MessageBox.Show("Error loading: {}".format(ex), "Error")

    def sel_all(self, s, e):
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, True)

    def sel_none(self, s, e):
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, False)

    def transfer(self, s, e):
        cat_key = self.cmb_cat.SelectedItem
        sel_names = [self.chk_items.Items[i] for i in self.chk_items.CheckedIndices]
        
        if not cat_key or not sel_names:
            MessageBox.Show("Select category and items.", "Warning")
            return

        # Confirm action
        result = MessageBox.Show(
            "This will DELETE and REPLACE {} items in {} target project(s).\n\nContinue?".format(
                len(sel_names), 
                len(self.tgt_docs)
            ),
            "Confirm Replace",
            MessageBoxButtons.YesNo
        )
        
        if result != DialogResult.Yes:
            return

        src_elems = CATEGORY_MAP[cat_key](self.src_doc)
        src_sel = [e for e in src_elems if get_name(e) in sel_names]

        total_deleted = 0
        total_copied = 0
        errors = []

        for tgt_doc in self.tgt_docs:
            tg = TransactionGroup(tgt_doc, "Copy & Replace Standards")
            tg.Start()
            try:
                stats = transfer_by_deletion_and_copy(src_sel, self.src_doc, tgt_doc, cat_key)
                total_deleted += stats["deleted"]
                total_copied += stats["copied"]
                tg.Assimilate()
            except Exception as ex:
                tg.RollBack()
                errors.append("{}: {}".format(tgt_doc.Title, str(ex)))

        # Show results
        msg = "Transfer complete!\n\n"
        msg += "{} items deleted from target(s)\n".format(total_deleted)
        msg += "{} items copied with dependencies\n".format(total_copied)
        
        if errors:
            msg += "\n\nErrors:\n" + "\n".join(errors)
        
        MessageBox.Show(msg, "Complete" if not errors else "Complete with Errors")
        self.Close()

if __name__ == "__main__":
    ProjectSelectorForm().ShowDialog()
