# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
clr.AddReference("System")

from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Structure import StructuralType
from System.Collections.Generic import List
from System.Windows.Forms import (
    Application, Form, Label, ComboBox, CheckedListBox, Button, TextBox, CheckBox,
    FormStartPosition, ComboBoxStyle, MessageBox, MessageBoxButtons, DialogResult,
    ProgressBar, Panel, Padding
)
from System.Drawing import Point, Size
from System.Threading import Thread, ThreadStart
from System.Threading.Tasks import Task
import System
import sys

uidoc = __revit__.ActiveUIDocument
app = __revit__.Application
doc_opt = [d for d in app.Documents if not d.IsLinked]
doc_names = sorted(d.Title for d in doc_opt)

def get_door_types(doc):
    collector = FilteredElementCollector(doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_Doors).WhereElementIsElementType()
    return list(collector)

def get_window_types(doc):
    collector = FilteredElementCollector(doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_Windows).WhereElementIsElementType()
    return list(collector)

def get_casework_types(doc):
    collector = FilteredElementCollector(doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_Casework).WhereElementIsElementType()
    return list(collector)

def get_furniture_types(doc):
    collector = FilteredElementCollector(doc).OfClass(FamilySymbol).OfCategory(BuiltInCategory.OST_Furniture).WhereElementIsElementType()
    return list(collector)

CATEGORY_MAP = {
    "Casework": (get_casework_types, BuiltInCategory.OST_Casework),
    "Door Types": (get_door_types, BuiltInCategory.OST_Doors),
    "Furniture": (get_furniture_types, BuiltInCategory.OST_Furniture),
    "Window Types": (get_window_types, BuiltInCategory.OST_Windows),
}

class OverwriteHandler(IDuplicateTypeNamesHandler):
    def OnDuplicateTypeNamesFound(self, args):
        return DuplicateTypeAction.UseDestinationTypes

class FamilyLoadOptions(IFamilyLoadOptions):
    """Always overwrite family and shared parameters when loading."""
    def OnFamilyFound(self, familyInUse, overwriteParameterValues):
        overwriteParameterValues = True
        return True
    def OnSharedFamilyFound(self, sharedFamily, familyInUse, source, overwriteParameterValues):
        overwriteParameterValues = True
        source = FamilySource.Family
        return True

def get_name(e):
    try:
        if isinstance(e, FamilySymbol):
            family_name = e.Family.Name
            type_name = e.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString()
            return "{}: {}".format(family_name, type_name)
        return e.Name
    except:
        try:
            return e.Name
        except:
            return "Unknown"

# ─────────────────────────────────────────────────────────────
# MATERIAL HELPERS  (same logic as system families script)
# ─────────────────────────────────────────────────────────────

def get_material_names_from_symbols(symbols, doc, debug_messages):
    """Collect names of ALL materials referenced by the selected FamilySymbols."""
    material_names = set()
    for symbol in symbols:
        try:
            for param in symbol.Parameters:
                try:
                    if param.StorageType == StorageType.ElementId and param.HasValue:
                        elem_id = param.AsElementId()
                        if elem_id and elem_id != ElementId.InvalidElementId:
                            elem = doc.GetElement(elem_id)
                            if elem and isinstance(elem, Material):
                                material_names.add(elem.Name)
                                debug_messages.append("  Material found: {} (in {})".format(elem.Name, get_name(symbol)))
                except:
                    pass
        except:
            pass
    return material_names


def copy_material_properties(src_mat, tgt_mat, tgt_doc):
    """Copy all visual and parametric properties from source material to target material."""
    try:
        for attr in [
            "Color", "Transparency", "Shininess", "Smoothness",
            "UseRenderAppearanceForShading", "MaterialClass", "MaterialCategory",
            "SurfaceForegroundPatternColor", "SurfaceBackgroundPatternColor",
            "CutForegroundPatternColor", "CutBackgroundPatternColor",
        ]:
            try:
                setattr(tgt_mat, attr, getattr(src_mat, attr))
            except:
                pass

        for id_attr in [
            "AppearanceAssetId", "ThermalAssetId", "StructuralAssetId",
            "SurfaceForegroundPatternId", "SurfaceBackgroundPatternId",
            "CutForegroundPatternId", "CutBackgroundPatternId",
        ]:
            try:
                src_id = getattr(src_mat, id_attr)
                if src_id and src_id != ElementId.InvalidElementId:
                    setattr(tgt_mat, id_attr, src_id)
                else:
                    setattr(tgt_mat, id_attr, ElementId.InvalidElementId)
            except:
                pass

        tgt_params_dict = {}
        for p in tgt_mat.Parameters:
            if p.Definition and p.Definition.Name:
                tgt_params_dict[p.Definition.Name] = p

        for src_param in src_mat.Parameters:
            try:
                if not src_param.HasValue or src_param.IsReadOnly:
                    continue
                param_name = src_param.Definition.Name
                if param_name not in tgt_params_dict:
                    continue
                tgt_param = tgt_params_dict[param_name]
                if tgt_param.IsReadOnly:
                    continue
                st = src_param.StorageType
                if st == StorageType.String:
                    v = src_param.AsString()
                    if v is not None:
                        tgt_param.Set(v)
                elif st == StorageType.Integer:
                    tgt_param.Set(src_param.AsInteger())
                elif st == StorageType.Double:
                    tgt_param.Set(src_param.AsDouble())
            except:
                pass
        return True
    except:
        return False


def overwrite_materials_by_name(material_names, src_doc, tgt_doc, debug_messages):
    """
    For each material name:
      - If it already exists in target  → overwrite properties in-place (ID preserved).
      - If it does not exist in target  → copy from source.
    Returns count of materials processed.
    """
    replaced = 0
    if not material_names:
        return replaced

    src_mats = {m.Name: m for m in FilteredElementCollector(src_doc).OfClass(Material).ToElements()}
    tgt_mats = {m.Name: m for m in FilteredElementCollector(tgt_doc).OfClass(Material).ToElements()}

    to_overwrite = {}
    to_copy_new  = []

    for name in material_names:
        if name not in src_mats:
            debug_messages.append("  Material '{}' not found in source, skipping".format(name))
            continue
        if name in tgt_mats:
            to_overwrite[name] = (src_mats[name], tgt_mats[name])
        else:
            to_copy_new.append(src_mats[name].Id)

    # Overwrite existing materials in-place
    if to_overwrite:
        t = Transaction(tgt_doc, "Overwrite Materials")
        t.Start()
        try:
            for name, (src_mat, tgt_mat) in to_overwrite.items():
                if copy_material_properties(src_mat, tgt_mat, tgt_doc):
                    replaced += 1
                    debug_messages.append("  Material overwritten in-place: {}".format(name))
                else:
                    debug_messages.append("  Material overwrite failed: {}".format(name))
            t.Commit()
        except Exception as ex:
            t.RollBack()
            debug_messages.append("  Material overwrite transaction failed: {}".format(str(ex)))

    # Copy brand-new materials
    if to_copy_new:
        ids_to_copy = List[ElementId]()
        for mid in to_copy_new:
            ids_to_copy.Add(mid)
        t2 = Transaction(tgt_doc, "Copy New Materials")
        t2.Start()
        try:
            opts = CopyPasteOptions()
            opts.SetDuplicateTypeNamesHandler(OverwriteHandler())
            copied = ElementTransformUtils.CopyElements(src_doc, ids_to_copy, tgt_doc, None, opts)
            replaced += copied.Count
            debug_messages.append("  New materials copied: {}".format(copied.Count))
            t2.Commit()
        except Exception as ex:
            t2.RollBack()
            debug_messages.append("  New material copy failed: {}".format(str(ex)))

    return replaced


def copy_type_parameters(src_symbol, tgt_symbol, src_doc, tgt_doc, debug_messages):
    """Copy writable type parameters and material parameters from src to tgt symbol."""
    params_copied = 0

    type_params_to_copy = [
        BuiltInParameter.ALL_MODEL_TYPE_MARK,
        BuiltInParameter.UNIFORMAT_CODE,
        BuiltInParameter.KEYNOTE_PARAM,
        BuiltInParameter.ALL_MODEL_DESCRIPTION,
        BuiltInParameter.ALL_MODEL_MANUFACTURER,
        BuiltInParameter.ALL_MODEL_MODEL,
        BuiltInParameter.ALL_MODEL_URL,
        BuiltInParameter.UNIFORMAT_DESCRIPTION,
        BuiltInParameter.ALL_MODEL_COST,
        BuiltInParameter.FIRE_RATING,
    ]

    try:
        for param_id in type_params_to_copy:
            try:
                src_param = src_symbol.get_Parameter(param_id)
                tgt_param = tgt_symbol.get_Parameter(param_id)
                if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                    st = src_param.StorageType
                    if st == StorageType.String:
                        v = src_param.AsString()
                        if v:
                            tgt_param.Set(v)
                            params_copied += 1
                    elif st == StorageType.Integer:
                        tgt_param.Set(src_param.AsInteger())
                        params_copied += 1
                    elif st == StorageType.Double:
                        tgt_param.Set(src_param.AsDouble())
                        params_copied += 1
            except:
                pass

        # Copy material parameters by matching name
        tgt_mats = {m.Name: m for m in FilteredElementCollector(tgt_doc).OfClass(Material).ToElements()}
        for param in src_symbol.Parameters:
            try:
                if param.StorageType == StorageType.ElementId and param.HasValue:
                    src_elem_id = param.AsElementId()
                    if src_elem_id and src_elem_id != ElementId.InvalidElementId:
                        src_elem = src_doc.GetElement(src_elem_id)
                        if src_elem and isinstance(src_elem, Material):
                            tgt_param = tgt_symbol.LookupParameter(param.Definition.Name)
                            if tgt_param and not tgt_param.IsReadOnly:
                                tgt_mat = tgt_mats.get(src_elem.Name)
                                if tgt_mat:
                                    tgt_param.Set(tgt_mat.Id)
                                    params_copied += 1
            except:
                pass
    except:
        pass

    return params_copied


def get_builtincategory_from_symbols(symbols):
    if not symbols:
        return None
    cat_id = symbols[0].Category.Id.IntegerValue
    category_mapping = {
        int(BuiltInCategory.OST_Doors):     BuiltInCategory.OST_Doors,
        int(BuiltInCategory.OST_Windows):   BuiltInCategory.OST_Windows,
        int(BuiltInCategory.OST_Casework):  BuiltInCategory.OST_Casework,
        int(BuiltInCategory.OST_Furniture): BuiltInCategory.OST_Furniture,
    }
    return category_mapping.get(cat_id, None)


# ─────────────────────────────────────────────────────────────
# INSTANCE SHARED PARAMETER HELPERS
# ─────────────────────────────────────────────────────────────

def get_instances_by_type_name(doc_ref, built_in_cat):
    """Returns dict: type_name -> [instances] for a given BuiltInCategory."""
    result = {}
    for inst in FilteredElementCollector(doc_ref) \
            .OfCategory(built_in_cat) \
            .WhereElementIsNotElementType().ToElements():
        try:
            tid = inst.GetTypeId()
            if tid and tid != ElementId.InvalidElementId:
                type_elem = doc_ref.GetElement(tid)
                if type_elem:
                    tname = get_name(type_elem)
                    if tname and tname != "Unknown":
                        if tname not in result:
                            result[tname] = []
                        result[tname].append(inst)
        except:
            pass
    return result


def get_shared_instance_params(instance):
    """Extracts shared (non-built-in) instance parameter values from an element.
    Returns dict: param_name -> (StorageType, value)"""
    params = {}
    for p in instance.Parameters:
        try:
            if p.IsReadOnly or not p.HasValue:
                continue
            # Skip built-in parameters (only want shared/project params)
            try:
                bip = p.Definition.BuiltInParameter
                if bip != BuiltInParameter.INVALID:
                    continue
            except:
                pass
            st = p.StorageType
            if st == StorageType.String:
                params[p.Definition.Name] = (st, p.AsString())
            elif st == StorageType.Integer:
                params[p.Definition.Name] = (st, p.AsInteger())
            elif st == StorageType.Double:
                params[p.Definition.Name] = (st, p.AsDouble())
            elif st == StorageType.ElementId:
                params[p.Definition.Name] = (st, p.AsElementId())
        except:
            pass
    return params


def apply_shared_instance_params(instances, param_values):
    """Applies shared parameter values to a list of target instances.
    param_values: dict from get_shared_instance_params."""
    count = 0
    for inst in instances:
        for p in inst.Parameters:
            try:
                if p.IsReadOnly:
                    continue
                pname = p.Definition.Name
                if pname not in param_values:
                    continue
                # Skip built-in parameters
                try:
                    bip = p.Definition.BuiltInParameter
                    if bip != BuiltInParameter.INVALID:
                        continue
                except:
                    pass
                st, val = param_values[pname]
                if st != p.StorageType or val is None:
                    continue
                if st == StorageType.String:
                    p.Set(val)
                    count += 1
                elif st == StorageType.Integer:
                    p.Set(val)
                    count += 1
                elif st == StorageType.Double:
                    p.Set(val)
                    count += 1
                elif st == StorageType.ElementId:
                    if val != ElementId.InvalidElementId:
                        p.Set(val)
                        count += 1
            except:
                pass
    return count


# ─────────────────────────────────────────────────────────────
# CORE TRANSFER  –  non-destructive, annotation-safe
# ─────────────────────────────────────────────────────────────

def transfer_loadable_families(src_symbols, src_doc, tgt_doc, progress_callback=None):
    """
    Transfer loadable family types from src_doc to tgt_doc WITHOUT deleting instances.

    Strategy for types that already exist in target:
      1. Copy the source type under a temporary name  (_TMP_<name>)
      2. Redirect every existing instance to the temp type via ChangeTypeId
      3. Delete the old type (now unreferenced)
      4. Rename the temp type to the correct name
      5. Copy type parameters from source to the renamed type

    New types (not present in target) are simply copied directly.
    Annotations, tags and dimensions attached to instances are never touched.
    """
    stats = {
        "types_overwritten": 0,
        "types_copied_new": 0,
        "types_failed": 0,
        "materials_replaced": 0,
        "parameters_copied": 0,
        "debug_messages": [],
    }
    dbg = stats["debug_messages"]

    try:
        dbg.append("=== SCRIPT START ===")
        dbg.append("Source: {}".format(src_doc.Title))
        dbg.append("Target: {}".format(tgt_doc.Title))

        if not src_symbols:
            return stats

        built_in_cat = get_builtincategory_from_symbols(src_symbols)
        if not built_in_cat:
            dbg.append("ERROR: could not determine category")
            return stats

        src_dict = {get_name(s): s for s in src_symbols if get_name(s) != "Unknown"}

        # ── Step 0: Materials ──────────────────────────────────────────────
        if progress_callback:
            progress_callback("Processing materials...", 0, 6)

        dbg.append("\n=== STEP 0: MATERIALS ===")
        material_names = get_material_names_from_symbols(src_symbols, src_doc, dbg)
        dbg.append("Found {} unique materials".format(len(material_names)))

        if material_names:
            stats["materials_replaced"] = overwrite_materials_by_name(
                material_names, src_doc, tgt_doc, dbg
            )

        # ── Step 1: Collect existing target types ──────────────────────────
        if progress_callback:
            progress_callback("Collecting target types...", 1, 6)

        dbg.append("\n=== STEP 1: TARGET TYPES ===")
        if built_in_cat == BuiltInCategory.OST_Doors:
            tgt_symbols = get_door_types(tgt_doc)
        elif built_in_cat == BuiltInCategory.OST_Windows:
            tgt_symbols = get_window_types(tgt_doc)
        elif built_in_cat == BuiltInCategory.OST_Casework:
            tgt_symbols = get_casework_types(tgt_doc)
        elif built_in_cat == BuiltInCategory.OST_Furniture:
            tgt_symbols = get_furniture_types(tgt_doc)
        else:
            return stats

        tgt_dict = {get_name(s): s for s in tgt_symbols if get_name(s) != "Unknown"}

        dbg.append("Source types: {}  |  Target types: {}".format(len(src_dict), len(tgt_dict)))

        # ── Step 2: Reload families from source into target ──────────────
        # Using LoadFamily overwrites the family in-place without renaming.
        # This handles ALL cases: new types, existing types, and new families.
        if progress_callback:
            progress_callback("Reloading families...", 2, 6)

        dbg.append("\n=== STEP 2: RELOAD FAMILIES ===")

        # Group source symbols by family name
        families_to_reload = {}
        for name, src_sym in src_dict.items():
            try:
                if isinstance(src_sym, FamilySymbol) and src_sym.Family:
                    fam_name = src_sym.Family.Name
                    if fam_name not in families_to_reload:
                        families_to_reload[fam_name] = []
                    families_to_reload[fam_name].append((name, src_sym))
            except:
                pass

        for fam_name, syms in families_to_reload.items():
            try:
                src_family = syms[0][1].Family
                fam_doc = src_doc.EditFamily(src_family)
                if fam_doc:
                    try:
                        loaded_family = clr.Reference[Family]()
                        fam_doc.LoadFamily(tgt_doc, FamilyLoadOptions(), loaded_family)
                        dbg.append("  Reloaded family: {} ({} types)".format(fam_name, len(syms)))
                        for sym_name, _ in syms:
                            if sym_name in tgt_dict:
                                stats["types_overwritten"] += 1
                            else:
                                stats["types_copied_new"] += 1
                    except Exception as ex:
                        dbg.append("  Reload failed for {}: {}".format(fam_name, str(ex)))
                        stats["types_failed"] += len(syms)
                    finally:
                        fam_doc.Close(False)
                else:
                    dbg.append("  Could not open family doc for: {}".format(fam_name))
                    stats["types_failed"] += len(syms)
            except Exception as ex:
                dbg.append("  Family edit failed for {}: {}".format(fam_name, str(ex)))
                stats["types_failed"] += len(syms)

        if progress_callback:
            progress_callback("Families reloaded.", 3, 6)

        # ── Step 4: Copy type parameters ──────────────────────────────────
        if progress_callback:
            progress_callback("Copying parameters...", 4, 6)

        dbg.append("\n=== STEP 4: COPY PARAMETERS ===")

        if built_in_cat == BuiltInCategory.OST_Doors:
            final_tgt = get_door_types(tgt_doc)
        elif built_in_cat == BuiltInCategory.OST_Windows:
            final_tgt = get_window_types(tgt_doc)
        elif built_in_cat == BuiltInCategory.OST_Casework:
            final_tgt = get_casework_types(tgt_doc)
        else:
            final_tgt = get_furniture_types(tgt_doc)

        final_tgt_dict = {get_name(s): s for s in final_tgt if get_name(s) != "Unknown"}

        t_params = Transaction(tgt_doc, "Copy Type Parameters")
        t_params.Start()
        try:
            for name, src_sym in src_dict.items():
                if name in final_tgt_dict:
                    n = copy_type_parameters(src_sym, final_tgt_dict[name], src_doc, tgt_doc, dbg)
                    stats["parameters_copied"] += n
            t_params.Commit()
            dbg.append("Parameters copied: {}".format(stats["parameters_copied"]))
        except Exception as ex:
            t_params.RollBack()
            dbg.append("Parameters transaction failed: {}".format(str(ex)))

        if progress_callback:
            progress_callback("Copying instance shared parameters...", 5, 6)

        # ── Step 5: Copy instance shared parameters ──────────────────────
        dbg.append("\n=== STEP 5: COPY INSTANCE SHARED PARAMETERS ===")

        src_instances = get_instances_by_type_name(src_doc, built_in_cat)
        tgt_instances = get_instances_by_type_name(tgt_doc, built_in_cat)

        instance_params_copied = 0
        t_inst = Transaction(tgt_doc, "Copy Instance Shared Parameters")
        t_inst.Start()
        try:
            for type_name in src_dict.keys():
                src_insts = src_instances.get(type_name, [])
                tgt_insts = tgt_instances.get(type_name, [])
                if src_insts and tgt_insts:
                    param_values = get_shared_instance_params(src_insts[0])
                    if param_values:
                        n = apply_shared_instance_params(tgt_insts, param_values)
                        instance_params_copied += n
                        dbg.append("  {}: {} params applied to {} instances".format(
                            type_name, len(param_values), len(tgt_insts)))
            t_inst.Commit()
            dbg.append("Instance shared parameters copied: {}".format(instance_params_copied))
        except Exception as ex:
            t_inst.RollBack()
            dbg.append("Instance params transaction failed: {}".format(str(ex)))

        if progress_callback:
            progress_callback("Done.", 6, 6)

        dbg.append("\n=== COMPLETE ===")
        dbg.append("Types overwritten (non-destructive): {}".format(stats["types_overwritten"]))
        dbg.append("New types copied: {}".format(stats["types_copied_new"]))
        dbg.append("Failed: {}".format(stats["types_failed"]))
        dbg.append("Materials replaced: {}".format(stats["materials_replaced"]))

    except Exception as ex:
        dbg.append("\n=== FATAL ERROR ===")
        dbg.append(str(ex))

    return stats


# ─────────────────────────────────────────────────────────────
# UI  –  unchanged from original
# ─────────────────────────────────────────────────────────────

class ProjectSelectorForm(Form):
    def __init__(self):
        self.Text = "Replace Loadable Families"
        self.Size = Size(580, 555)
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimumSize = Size(580, 555)
        self.Padding = Padding(20)

        Label(Text="Source Project:", Location=Point(30, 40), Size=Size(130, 20), Parent=self)
        self.cmb_src = ComboBox(Location=Point(30, 62), Size=Size(510, 23), DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for n in doc_names:
            self.cmb_src.Items.Add(n)

        Label(Text="Target Projects:", Location=Point(30, 100), Size=Size(130, 20), Parent=self)
        self.chk_tgt = CheckedListBox(Location=Point(30, 122), Size=Size(510, 295), ScrollAlwaysVisible=True, Parent=self)
        for n in doc_names:
            self.chk_tgt.Items.Add(n)

        btn = Button(Text="Next", Location=Point(460, 455), Size=Size(90, 30), Parent=self)
        btn.Click += self.next

    def next(self, s, e):
        if not self.cmb_src.SelectedItem or self.chk_tgt.CheckedItems.Count == 0:
            MessageBox.Show("Select source and target.", "Error")
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
        self.all_names = []
        self.selected_items = set()
        self.common_names = set()

        self.Text = "Replace Loadable Families"
        self.Size = Size(640, 730)
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimumSize = Size(640, 730)
        self.Padding = Padding(20)

        Label(Text="Category:", Location=Point(30, 40), Size=Size(130, 20), Parent=self)
        self.cmb_cat = ComboBox(Location=Point(30, 62), Size=Size(550, 23), DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for c in sorted(CATEGORY_MAP.keys()):
            self.cmb_cat.Items.Add(c)
        self.cmb_cat.SelectedIndexChanged += self.load

        Label(Text="Search:", Location=Point(30, 100), Size=Size(60, 20), Parent=self)
        self.txt_search = TextBox(Location=Point(95, 98), Size=Size(490, 23), Parent=self)
        self.txt_search.TextChanged += self.filter_items

        Label(Text="Items:", Location=Point(30, 135), Size=Size(200, 20), Parent=self)
        self.chk_items = CheckedListBox(Location=Point(30, 157), Size=Size(550, 390), ScrollAlwaysVisible=True, Parent=self)
        self.chk_items.ItemCheck += self.item_checked

        self.show_mode = "all"

        Button(Text="All",           Location=Point(30,  567), Size=Size(80,  25), Parent=self).Click += self.sel_all
        Button(Text="None",          Location=Point(120, 567), Size=Size(80,  25), Parent=self).Click += self.sel_none
        Button(Text="Show Selected", Location=Point(210, 567), Size=Size(100, 25), Parent=self).Click += self.show_selected
        Button(Text="Show All",      Location=Point(320, 567), Size=Size(90,  25), Parent=self).Click += self.show_all
        Button(Text="Show Common",   Location=Point(420, 567), Size=Size(110, 25), Parent=self).Click += self.show_common

        self.lbl_count = Label(Text="Selected: 0", Location=Point(540, 570), Size=Size(140, 20), Parent=self)

        btn_back = Button(Text="Back", Location=Point(410, 648), Size=Size(90, 30), Parent=self)
        btn_back.Click += self.go_back

        btn_transfer = Button(Text="Transfer", Location=Point(510, 648), Size=Size(90, 30), Parent=self)
        btn_transfer.Click += self.transfer

    def go_back(self, s, e):
        self.Close()
        ProjectSelectorForm().ShowDialog()

    def show_selected(self, s, e):
        self.show_mode = "selected"
        self.filter_items(None, None)

    def show_all(self, s, e):
        self.show_mode = "all"
        self.filter_items(None, None)

    def item_checked(self, sender, e):
        item_name = self.chk_items.Items[e.Index]
        if e.NewValue == System.Windows.Forms.CheckState.Checked:
            self.selected_items.add(item_name)
        else:
            self.selected_items.discard(item_name)
        self.lbl_count.Text = "Selected: {}".format(len(self.selected_items))

    def load(self, s, e):
        self.all_names = []
        self.common_names = set()
        key = self.cmb_cat.SelectedItem
        if not key:
            return
        try:
            func, bic = CATEGORY_MAP[key]
            elems = func(self.src_doc)
            self.all_names = sorted(set(get_name(e) for e in elems if get_name(e) != "Unknown"))

            # Collect target names to find common
            tgt_names = set()
            for tgt_doc in self.tgt_docs:
                try:
                    tgt_elems = func(tgt_doc)
                    for elem in tgt_elems:
                        tname = get_name(elem)
                        if tname and tname != "Unknown":
                            tgt_names.add(tname)
                except:
                    pass

            self.common_names = set(self.all_names) & tgt_names
            self.filter_items(None, None)
        except Exception as ex:
            MessageBox.Show("Error: {}".format(str(ex)), "Error")

    def filter_items(self, s, e):
        search_text = self.txt_search.Text.lower()
        self.chk_items.ItemCheck -= self.item_checked
        self.chk_items.Items.Clear()
        for n in self.all_names:
            if search_text and search_text not in n.lower():
                continue
            if self.show_mode == "selected" and n not in self.selected_items:
                continue
            if self.show_mode == "common" and n not in self.common_names:
                continue
            idx = self.chk_items.Items.Add(n)
            if n in self.selected_items:
                self.chk_items.SetItemChecked(idx, True)
        self.chk_items.ItemCheck += self.item_checked

    def show_common(self, s, e):
        """Show only items that exist in both source and target projects."""
        if not self.common_names:
            MessageBox.Show("No common items found between source and target.", "Info")
            return
        self.show_mode = "common"
        self.filter_items(None, None)

    def sel_all(self, s, e):
        self.chk_items.ItemCheck -= self.item_checked
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, True)
            self.selected_items.add(self.chk_items.Items[i])
        self.chk_items.ItemCheck += self.item_checked
        self.lbl_count.Text = "Selected: {}".format(len(self.selected_items))

    def sel_none(self, s, e):
        self.chk_items.ItemCheck -= self.item_checked
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, False)
            self.selected_items.discard(self.chk_items.Items[i])
        self.chk_items.ItemCheck += self.item_checked
        self.lbl_count.Text = "Selected: {}".format(len(self.selected_items))

    def transfer(self, s, e):
        if not self.selected_items:
            MessageBox.Show("No items selected.", "Warning")
            return

        result = MessageBox.Show("Overwrite items?", "Confirm", MessageBoxButtons.YesNo)
        if result != DialogResult.Yes:
            return

        all_selected_symbols = []
        for cat_key, (func, _) in CATEGORY_MAP.items():
            src_elems = func(self.src_doc)
            for elem in src_elems:
                if get_name(elem) in self.selected_items:
                    all_selected_symbols.append(elem)

        if not all_selected_symbols:
            MessageBox.Show("No elements found.", "Error")
            return

        progress_form = ProgressForm(all_selected_symbols, self.src_doc, self.tgt_docs)
        progress_form.ShowDialog()
        self.Close()


class ProgressForm(Form):
    def __init__(self, symbols, src_doc, tgt_docs):
        self.symbols  = symbols
        self.src_doc  = src_doc
        self.tgt_docs = tgt_docs
        self.total_stats = {
            "types_overwritten": 0,
            "types_copied_new":  0,
            "types_failed":      0,
            "materials_replaced": 0,
            "parameters_copied":  0,
            "debug_messages":    [],
        }

        self.Text = "Transfer Progress"
        self.Size = Size(500, 200)
        self.StartPosition = FormStartPosition.CenterScreen
        self.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedDialog
        self.MaximizeBox = False
        self.MinimizeBox = False

        self.lbl_status = Label(
            Text="Processing...",
            Location=Point(20, 30),
            Size=Size(460, 20),
            Parent=self,
            TextAlign=System.Drawing.ContentAlignment.MiddleCenter
        )

        self.progress_bar = ProgressBar(
            Location=Point(20, 60),
            Size=Size(460, 30),
            Minimum=0,
            Maximum=100,
            Parent=self
        )

        self.Shown += self.start_process

    def start_process(self, sender, e):
        Application.DoEvents()

        for tgt_doc in self.tgt_docs:
            Application.DoEvents()

            tg = TransactionGroup(tgt_doc, "Replace Loadable Families")
            tg.Start()
            try:
                stats = transfer_loadable_families(
                    self.symbols,
                    self.src_doc,
                    tgt_doc,
                    self.update_progress
                )
                for k in self.total_stats:
                    if k == "debug_messages":
                        self.total_stats[k].extend(stats.get(k, []))
                    else:
                        self.total_stats[k] += stats.get(k, 0)
                tg.Assimilate()
            except Exception as ex:
                tg.RollBack()
                self.total_stats["debug_messages"].append("Transaction failed: {}".format(str(ex)))

        # Save debug log
        try:
            import os
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            with open(os.path.join(desktop, "revit_debug.txt"), "w") as f:
                f.write("\n".join(self.total_stats["debug_messages"]))
        except:
            pass

        MessageBox.Show("Transfer complete!", "Complete")
        self.Close()

    def update_progress(self, message, current, total):
        if total > 0:
            self.progress_bar.Value = int((float(current) / float(total)) * 100)
        self.lbl_status.Text = message
        Application.DoEvents()


if __name__ == "__main__":
    ProjectSelectorForm().ShowDialog()
