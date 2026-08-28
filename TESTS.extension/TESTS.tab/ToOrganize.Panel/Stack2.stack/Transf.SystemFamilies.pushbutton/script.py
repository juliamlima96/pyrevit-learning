# -*- coding: utf-8 -*-

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
clr.AddReference("System")

from Autodesk.Revit.DB import *
from System.Collections.Generic import List
from System.Windows.Forms import (
    Application, Form, Label, ComboBox, CheckedListBox, Button,
    FormStartPosition, ComboBoxStyle, MessageBox, MessageBoxButtons, DialogResult,
    TextBox, ProgressBar, FormBorderStyle, ProgressBarStyle, Padding
)
from System.Drawing import Point, Size, Font, FontStyle, ContentAlignment, Color
from System import Action

uidoc = __revit__.ActiveUIDocument
app = __revit__.Application
doc_opt = [d for d in app.Documents if not d.IsLinked]
doc_names = sorted(d.Title for d in doc_opt)

CATEGORY_MAP = {
    "Ceiling Types": lambda d: FilteredElementCollector(d).OfClass(CeilingType).ToElements(),
    "Floor Types": lambda d: FilteredElementCollector(d).OfClass(FloorType).ToElements(),
    "Roof Types": lambda d: FilteredElementCollector(d).OfClass(RoofType).ToElements(),
    "Wall Types": lambda d: FilteredElementCollector(d).OfClass(WallType).ToElements(),
    "Materials": lambda d: FilteredElementCollector(d).OfClass(Material).ToElements(),
}

# Maps category keys to BuiltInCategory for collecting instances
INSTANCE_CATEGORY_MAP = {
    "Ceiling Types": BuiltInCategory.OST_Ceilings,
    "Floor Types": BuiltInCategory.OST_Floors,
    "Roof Types": BuiltInCategory.OST_Roofs,
    "Wall Types": BuiltInCategory.OST_Walls,
}

class OverwriteHandler(IDuplicateTypeNamesHandler):
    def OnDuplicateTypeNamesFound(self, args):
        return DuplicateTypeAction.UseDestinationTypes

class WarningSwallower(IFailuresPreprocessor):
    """Suppresses all warnings (duplicate Type Mark, etc.) during transactions."""
    def PreprocessFailures(self, failuresAccessor):
        failures = failuresAccessor.GetFailureMessages()
        for f in failures:
            try:
                failuresAccessor.DeleteWarning(f)
            except:
                pass
        return FailureProcessingResult.Continue

def get_name(e):
    try:
        if isinstance(e, Material):
            return e.Name
        p = e.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
        if p and p.HasValue:
            return p.AsString()
        if isinstance(e, FamilySymbol):
            return "{}: {}".format(e.Family.Name, e.Name)
        return e.Name
    except:
        return ""


def copy_type_parameters(src_type, tgt_type):
    """Copy all writable parameters from source type to target type,
    including shared parameters. Matches by parameter name."""
    skip_params = {
        BuiltInParameter.SYMBOL_NAME_PARAM,
        BuiltInParameter.ELEM_FAMILY_PARAM,
        BuiltInParameter.ELEM_FAMILY_AND_TYPE_PARAM,
        BuiltInParameter.ELEM_TYPE_PARAM,
    }
    tgt_params_dict = {}
    for p in tgt_type.Parameters:
        if p.Definition and p.Definition.Name:
            tgt_params_dict[p.Definition.Name] = p

    for src_param in src_type.Parameters:
        try:
            if not src_param.HasValue or src_param.IsReadOnly:
                continue
            try:
                bip = src_param.Definition.BuiltInParameter
                if bip in skip_params:
                    continue
            except:
                pass
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
            elif st == StorageType.ElementId:
                v = src_param.AsElementId()
                if v and v != ElementId.InvalidElementId:
                    tgt_param.Set(v)
        except:
            pass

def collect_material_ids_from_types(src_elems, src_doc):
    """Collect all material IDs referenced by the given type elements."""
    material_ids = set()
    for type_element in src_elems:
        try:
            param = type_element.get_Parameter(BuiltInParameter.STRUCTURAL_MATERIAL_PARAM)
            if param and param.HasValue:
                mat_id = param.AsElementId()
                if mat_id and mat_id != ElementId.InvalidElementId:
                    material_ids.add(mat_id)
        except:
            pass
        try:
            cs = type_element.GetCompoundStructure()
            if cs:
                for layer in cs.GetLayers():
                    mat_id = layer.MaterialId
                    if mat_id and mat_id != ElementId.InvalidElementId:
                        material_ids.add(mat_id)
                for sweep_type in [WallSweepType.Sweep, WallSweepType.Reveal]:
                    try:
                        for sweep in cs.GetWallSweepsInfo(sweep_type):
                            mat_id = sweep.MaterialId
                            if mat_id and mat_id != ElementId.InvalidElementId:
                                material_ids.add(mat_id)
                    except:
                        pass
        except:
            pass
    return list(material_ids)

def copy_material_properties(src_mat, tgt_mat, tgt_doc):
    """Copy ALL properties from source material to target material"""
    try:
        try:
            src_appearance_id = src_mat.AppearanceAssetId
            if src_appearance_id and src_appearance_id != ElementId.InvalidElementId:
                tgt_mat.AppearanceAssetId = src_appearance_id
        except:
            pass

        try:
            src_thermal_id = src_mat.ThermalAssetId
            if src_thermal_id and src_thermal_id != ElementId.InvalidElementId:
                tgt_mat.ThermalAssetId = src_thermal_id
        except:
            pass

        try:
            src_structural_id = src_mat.StructuralAssetId
            if src_structural_id and src_structural_id != ElementId.InvalidElementId:
                tgt_mat.StructuralAssetId = src_structural_id
        except:
            pass

        try:
            tgt_mat.Color = src_mat.Color
        except:
            pass

        try:
            tgt_mat.Transparency = src_mat.Transparency
        except:
            pass

        try:
            tgt_mat.Shininess = src_mat.Shininess
        except:
            pass

        try:
            tgt_mat.Smoothness = src_mat.Smoothness
        except:
            pass

        try:
            tgt_mat.UseRenderAppearanceForShading = src_mat.UseRenderAppearanceForShading
        except:
            pass

        try:
            src_pattern_id = src_mat.SurfaceForegroundPatternId
            if src_pattern_id and src_pattern_id != ElementId.InvalidElementId:
                tgt_mat.SurfaceForegroundPatternId = src_pattern_id
            else:
                tgt_mat.SurfaceForegroundPatternId = ElementId.InvalidElementId
        except:
            pass

        try:
            tgt_mat.SurfaceForegroundPatternColor = src_mat.SurfaceForegroundPatternColor
        except:
            pass

        try:
            src_pattern_id = src_mat.SurfaceBackgroundPatternId
            if src_pattern_id and src_pattern_id != ElementId.InvalidElementId:
                tgt_mat.SurfaceBackgroundPatternId = src_pattern_id
            else:
                tgt_mat.SurfaceBackgroundPatternId = ElementId.InvalidElementId
        except:
            pass

        try:
            tgt_mat.SurfaceBackgroundPatternColor = src_mat.SurfaceBackgroundPatternColor
        except:
            pass

        try:
            src_pattern_id = src_mat.CutForegroundPatternId
            if src_pattern_id and src_pattern_id != ElementId.InvalidElementId:
                tgt_mat.CutForegroundPatternId = src_pattern_id
            else:
                tgt_mat.CutForegroundPatternId = ElementId.InvalidElementId
        except:
            pass

        try:
            tgt_mat.CutForegroundPatternColor = src_mat.CutForegroundPatternColor
        except:
            pass

        try:
            src_pattern_id = src_mat.CutBackgroundPatternId
            if src_pattern_id and src_pattern_id != ElementId.InvalidElementId:
                tgt_mat.CutBackgroundPatternId = src_pattern_id
            else:
                tgt_mat.CutBackgroundPatternId = ElementId.InvalidElementId
        except:
            pass

        try:
            tgt_mat.CutBackgroundPatternColor = src_mat.CutBackgroundPatternColor
        except:
            pass

        try:
            tgt_mat.MaterialClass = src_mat.MaterialClass
        except:
            pass

        try:
            tgt_mat.MaterialCategory = src_mat.MaterialCategory
        except:
            pass

        src_params = src_mat.Parameters
        tgt_params_dict = {}
        for tgt_param in tgt_mat.Parameters:
            if tgt_param.Definition and tgt_param.Definition.Name:
                tgt_params_dict[tgt_param.Definition.Name] = tgt_param

        for src_param in src_params:
            try:
                if not src_param.HasValue:
                    continue
                param_name = src_param.Definition.Name
                if src_param.IsReadOnly:
                    continue
                if param_name in tgt_params_dict:
                    tgt_param = tgt_params_dict[param_name]
                    if tgt_param.IsReadOnly:
                        continue
                    storage_type = src_param.StorageType
                    if storage_type == StorageType.String:
                        value = src_param.AsString()
                        if value:
                            tgt_param.Set(value)
                    elif storage_type == StorageType.Integer:
                        value = src_param.AsInteger()
                        tgt_param.Set(value)
                    elif storage_type == StorageType.Double:
                        value = src_param.AsDouble()
                        tgt_param.Set(value)
                    elif storage_type == StorageType.ElementId:
                        value = src_param.AsElementId()
                        if value and value != ElementId.InvalidElementId:
                            tgt_param.Set(value)
            except:
                pass

        try:
            src_param = src_mat.get_Parameter(BuiltInParameter.ALL_MODEL_DESCRIPTION)
            tgt_param = tgt_mat.get_Parameter(BuiltInParameter.ALL_MODEL_DESCRIPTION)
            if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                tgt_param.Set(src_param.AsString())
        except:
            pass

        try:
            src_param = src_mat.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
            tgt_param = tgt_mat.get_Parameter(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
            if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                tgt_param.Set(src_param.AsString())
        except:
            pass

        try:
            src_param = src_mat.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)
            tgt_param = tgt_mat.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)
            if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                tgt_param.Set(src_param.AsString())
        except:
            pass

        try:
            src_param = src_mat.get_Parameter(BuiltInParameter.KEYNOTE_PARAM)
            tgt_param = tgt_mat.get_Parameter(BuiltInParameter.KEYNOTE_PARAM)
            if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                tgt_param.Set(src_param.AsString())
        except:
            pass

        try:
            src_param = src_mat.get_Parameter(BuiltInParameter.ALL_MODEL_MANUFACTURER)
            tgt_param = tgt_mat.get_Parameter(BuiltInParameter.ALL_MODEL_MANUFACTURER)
            if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                tgt_param.Set(src_param.AsString())
        except:
            pass

        try:
            src_param = src_mat.get_Parameter(BuiltInParameter.ALL_MODEL_MODEL)
            tgt_param = tgt_mat.get_Parameter(BuiltInParameter.ALL_MODEL_MODEL)
            if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                tgt_param.Set(src_param.AsString())
        except:
            pass

        try:
            src_param = src_mat.get_Parameter(BuiltInParameter.ALL_MODEL_URL)
            tgt_param = tgt_mat.get_Parameter(BuiltInParameter.ALL_MODEL_URL)
            if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                tgt_param.Set(src_param.AsString())
        except:
            pass

        try:
            src_param = src_mat.get_Parameter(BuiltInParameter.ALL_MODEL_COST)
            tgt_param = tgt_mat.get_Parameter(BuiltInParameter.ALL_MODEL_COST)
            if src_param and tgt_param and src_param.HasValue and not tgt_param.IsReadOnly:
                tgt_param.Set(src_param.AsDouble())
        except:
            pass

        return True
    except Exception as ex:
        return False

def overwrite_materials_by_name(material_ids, src_doc, tgt_doc):
    """SOBRESCREVE materiais do destino que têm o MESMO NOME"""
    stats = {
        "materials_overwritten": 0,
        "materials_copied_new": 0,
        "materials_failed": 0
    }

    if not material_ids:
        return stats

    try:
        src_materials = {}
        for mat_id in material_ids:
            mat = src_doc.GetElement(mat_id)
            if mat and isinstance(mat, Material):
                src_materials[mat.Name] = mat

        tgt_materials = {}
        for mat in FilteredElementCollector(tgt_doc).OfClass(Material):
            tgt_materials[mat.Name] = mat

        materials_to_overwrite = {}
        materials_to_copy_new = []

        for mat_name, src_mat in src_materials.items():
            if mat_name in tgt_materials:
                materials_to_overwrite[mat_name] = (src_mat, tgt_materials[mat_name])
            else:
                materials_to_copy_new.append(src_mat.Id)

        if materials_to_overwrite:
            t1 = Transaction(tgt_doc, "Overwrite Materials by Name")
            t1.Start()
            try:
                for mat_name, (src_mat, tgt_mat) in materials_to_overwrite.items():
                    success = copy_material_properties(src_mat, tgt_mat, tgt_doc)
                    if success:
                        stats["materials_overwritten"] += 1
                    else:
                        stats["materials_failed"] += 1
                t1.Commit()
            except Exception as ex:
                t1.RollBack()
                stats["materials_failed"] += len(materials_to_overwrite)

        if materials_to_copy_new:
            to_copy = List[ElementId]()
            for mat_id in materials_to_copy_new:
                to_copy.Add(mat_id)

            if to_copy.Count > 0:
                t2 = Transaction(tgt_doc, "Copy New Materials")
                t2.Start()
                try:
                    opts = CopyPasteOptions()
                    opts.SetDuplicateTypeNamesHandler(OverwriteHandler())
                    copied_ids = ElementTransformUtils.CopyElements(src_doc, to_copy, tgt_doc, None, opts)
                    stats["materials_copied_new"] = copied_ids.Count
                    t2.Commit()
                except:
                    t2.RollBack()
    except:
        pass

    return stats

def transfer_materials_only(src_materials, src_doc, tgt_doc):
    """Transfer only materials"""
    stats = {
        "materials_overwritten": 0,
        "materials_copied_new": 0,
        "materials_failed": 0
    }

    if not src_materials:
        return stats

    try:
        material_ids = [mat.Id for mat in src_materials]
        mat_stats = overwrite_materials_by_name(material_ids, src_doc, tgt_doc)
        stats["materials_overwritten"] = mat_stats["materials_overwritten"]
        stats["materials_copied_new"] = mat_stats["materials_copied_new"]
        stats["materials_failed"] = mat_stats["materials_failed"]
    except:
        pass

    return stats


def get_instances_by_type_name(doc_ref, cat_key):
    """Returns dict: type_name -> [instances] for a given category in a document."""
    if cat_key not in INSTANCE_CATEGORY_MAP:
        return {}

    bic = INSTANCE_CATEGORY_MAP[cat_key]
    result = {}

    for inst in FilteredElementCollector(doc_ref).OfCategory(bic) \
            .WhereElementIsNotElementType().ToElements():
        try:
            tid = inst.GetTypeId()
            if tid and tid != ElementId.InvalidElementId:
                type_elem = doc_ref.GetElement(tid)
                if type_elem:
                    tname = get_name(type_elem)
                    if tname:
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
                if st != p.StorageType:
                    continue
                if val is None:
                    continue
                if st == StorageType.String:
                    p.Set(val)
                elif st == StorageType.Integer:
                    p.Set(val)
                elif st == StorageType.Double:
                    p.Set(val)
                elif st == StorageType.ElementId:
                    if val != ElementId.InvalidElementId:
                        p.Set(val)
            except:
                pass


def transfer_with_element_preservation(src_elems, src_doc, tgt_doc, cat_key, progress_form=None):
    """
    Non-destructive transfer: overwrites type properties in-place.
    Never deletes or recreates instances, preserving tags, annotations and geometry references.
    """
    stats = {
        "materials_overwritten": 0,
        "materials_copied_new": 0,
        "materials_failed": 0,
        "types_copied": 0,
        "types_overwritten": 0,
        "types_failed": 0,
    }

    if not src_elems:
        return stats

    # Step 1: Ensure materials exist in target (10-30%)
    if progress_form:
        progress_form.update_progress(10)

    material_ids = collect_material_ids_from_types(src_elems, src_doc)
    if material_ids:
        mat_stats = overwrite_materials_by_name(material_ids, src_doc, tgt_doc)
        stats["materials_overwritten"] = mat_stats["materials_overwritten"]
        stats["materials_copied_new"] = mat_stats["materials_copied_new"]
        stats["materials_failed"] = mat_stats["materials_failed"]

    if progress_form:
        progress_form.update_progress(30)

    # Build lookup of existing target types by name
    tgt_elems = CATEGORY_MAP[cat_key](tgt_doc)
    tgt_dict = {get_name(e): e for e in tgt_elems if get_name(e)}

    src_dict = {get_name(e): e for e in src_elems if get_name(e)}

    # Separate: types that already exist in target vs new types
    types_to_overwrite = {}   # name -> (src_type, tgt_type)
    types_to_copy_new = []    # src ElementIds for brand new types

    for name, src_type in src_dict.items():
        if name in tgt_dict:
            types_to_overwrite[name] = (src_type, tgt_dict[name])
        else:
            types_to_copy_new.append(src_type.Id)

    if progress_form:
        progress_form.update_progress(40)

    # Step 2: Copy brand-new types that don't exist yet in target (40-60%)
    if types_to_copy_new:
        to_copy = List[ElementId]()
        for eid in types_to_copy_new:
            to_copy.Add(eid)
        t_new = Transaction(tgt_doc, "Copy New Types")
        opts_fail = t_new.GetFailureHandlingOptions()
        opts_fail.SetFailuresPreprocessor(WarningSwallower())
        t_new.SetFailureHandlingOptions(opts_fail)
        t_new.Start()
        try:
            opts = CopyPasteOptions()
            opts.SetDuplicateTypeNamesHandler(OverwriteHandler())
            copied_ids = ElementTransformUtils.CopyElements(src_doc, to_copy, tgt_doc, None, opts)
            stats["types_copied"] = copied_ids.Count
            t_new.Commit()
        except:
            t_new.RollBack()

    if progress_form:
        progress_form.update_progress(60)

    # Step 3: Overwrite existing types using CopyElements (60-80%)
    # Same method as Transfer Project Standards:
    # rename old → CopyElements from source → redirect instances → delete old
    # This brings EVERYTHING: compound structure, sweeps, profiles, parameters.
    bic = INSTANCE_CATEGORY_MAP.get(cat_key)

    for name, (src_type, old_tgt_type) in types_to_overwrite.items():
        try:
            # 3a. Rename old target type to _TMP_ to free the name
            tmp_name = "_TMP_{}".format(name)
            t_rename = Transaction(tgt_doc, "Rename to TMP")
            opts_r = t_rename.GetFailureHandlingOptions()
            opts_r.SetFailuresPreprocessor(WarningSwallower())
            t_rename.SetFailureHandlingOptions(opts_r)
            t_rename.Start()
            try:
                old_tgt_type.Name = tmp_name
                t_rename.Commit()
            except:
                t_rename.RollBack()
                stats["types_failed"] += 1
                continue

            # 3b. CopyElements the source type — name is now free
            ids = List[ElementId]()
            ids.Add(src_type.Id)
            t_copy = Transaction(tgt_doc, "Copy Type from Source")
            opts_fail2 = t_copy.GetFailureHandlingOptions()
            opts_fail2.SetFailuresPreprocessor(WarningSwallower())
            t_copy.SetFailureHandlingOptions(opts_fail2)
            t_copy.Start()
            try:
                opts = CopyPasteOptions()
                opts.SetDuplicateTypeNamesHandler(OverwriteHandler())
                copied_ids = ElementTransformUtils.CopyElements(src_doc, ids, tgt_doc, None, opts)
                if copied_ids.Count == 0:
                    t_copy.RollBack()
                    # Undo rename
                    t_undo = Transaction(tgt_doc, "Undo Rename")
                    t_undo.Start()
                    try:
                        old_tgt_type.Name = name
                        t_undo.Commit()
                    except:
                        t_undo.RollBack()
                    stats["types_failed"] += 1
                    continue
                new_type = tgt_doc.GetElement(list(copied_ids)[0])
                t_copy.Commit()
            except:
                t_copy.RollBack()
                # Undo rename
                t_undo = Transaction(tgt_doc, "Undo Rename")
                t_undo.Start()
                try:
                    old_tgt_type.Name = name
                    t_undo.Commit()
                except:
                    t_undo.RollBack()
                stats["types_failed"] += 1
                continue

            # 3c. Redirect all instances from _TMP_ type to the new type
            if bic and new_type:
                t_redirect = Transaction(tgt_doc, "Redirect Instances")
                t_redirect.Start()
                try:
                    all_instances = FilteredElementCollector(tgt_doc) \
                        .OfCategory(bic) \
                        .WhereElementIsNotElementType() \
                        .ToElements()
                    for inst in all_instances:
                        try:
                            if inst.GetTypeId() == old_tgt_type.Id:
                                inst.ChangeTypeId(new_type.Id)
                        except:
                            pass
                    t_redirect.Commit()
                except:
                    t_redirect.RollBack()

            # 3d. Delete the _TMP_ type (now unreferenced)
            t_del = Transaction(tgt_doc, "Delete TMP Type")
            t_del.Start()
            try:
                tgt_doc.Delete(old_tgt_type.Id)
                t_del.Commit()
            except:
                t_del.RollBack()

            # 3e. Copy type parameters (shared params, etc.)
            if new_type:
                t_params = Transaction(tgt_doc, "Copy Type Parameters")
                t_params.Start()
                try:
                    copy_type_parameters(src_type, new_type)
                    t_params.Commit()
                except:
                    t_params.RollBack()

            stats["types_overwritten"] += 1

        except:
            stats["types_failed"] += 1

    if progress_form:
        progress_form.update_progress(80)

    # Step 4: Copy shared instance parameters (80-100%)
    # For each transferred type, get shared param values from ONE source instance
    # and apply to ALL target instances of the same type.
    if cat_key in INSTANCE_CATEGORY_MAP:
        src_instances = get_instances_by_type_name(src_doc, cat_key)
        tgt_instances = get_instances_by_type_name(tgt_doc, cat_key)

        # Collect type names that were transferred (both overwritten and new)
        transferred_names = set(types_to_overwrite.keys())
        for eid in types_to_copy_new:
            src_type = src_doc.GetElement(eid)
            if src_type:
                n = get_name(src_type)
                if n:
                    transferred_names.add(n)

        t_inst = Transaction(tgt_doc, "Copy Instance Shared Parameters")
        t_inst.Start()
        try:
            for type_name in transferred_names:
                src_insts = src_instances.get(type_name, [])
                tgt_insts = tgt_instances.get(type_name, [])
                if src_insts and tgt_insts:
                    # Get shared param values from first source instance
                    param_values = get_shared_instance_params(src_insts[0])
                    if param_values:
                        apply_shared_instance_params(tgt_insts, param_values)
            t_inst.Commit()
        except:
            t_inst.RollBack()

    if progress_form:
        progress_form.update_progress(100)

    return stats


# ===== FORMULÁRIO DE PROGRESSO =====
class ProgressForm(Form):
    def __init__(self):
        self.Text = "Transfer Progress"
        self.Size = Size(490, 195)
        self.StartPosition = FormStartPosition.CenterScreen
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox = False
        self.MinimizeBox = False
        self.BackColor = Color.FromArgb(240, 240, 240)

        self.lbl_processing = Label(
            Text="Processing...",
            Location=Point(18, 63),
            Size=Size(454, 20),
            Parent=self,
            Font=Font("Segoe UI", 9, FontStyle.Regular)
        )
        self.lbl_processing.TextAlign = ContentAlignment.MiddleCenter

        self.progress_bar = ProgressBar(
            Location=Point(18, 91),
            Size=Size(454, 23),
            Parent=self,
            Minimum=0,
            Maximum=100,
            Value=0,
            Style=ProgressBarStyle.Continuous
        )

    def update_progress(self, value):
        try:
            if self.InvokeRequired:
                self.Invoke(Action[int](self.update_progress), value)
            else:
                self.progress_bar.Value = min(value, 100)
                Application.DoEvents()
        except:
            pass

class ProjectSelectorForm(Form):
    def __init__(self):
        self.Text = "Transfer Items"
        self.Size = Size(580, 560)
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimumSize = Size(580, 560)
        self.Padding = Padding(20)

        Label(Text="Source Project:", Location=Point(30, 40), Size=Size(130, 20), Parent=self)

        self.cmb_src = ComboBox(Location=Point(30, 62), Size=Size(510, 23),
                                DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for n in doc_names:
            self.cmb_src.Items.Add(n)

        Label(Text="Target Projects:", Location=Point(30, 100), Size=Size(130, 20), Parent=self)

        self.chk_tgt = CheckedListBox(Location=Point(30, 122), Size=Size(510, 295),
                                      ScrollAlwaysVisible=True, Parent=self)
        for n in doc_names:
            self.chk_tgt.Items.Add(n)

        btn = Button(Text="Next", Location=Point(460, 460), Size=Size(90, 30), Parent=self)
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
        self.all_items = []
        self.all_elements = {}
        self.common_names = set()

        # Persistent selection per category: {cat_key: set(names)}
        self.selections = {}
        # Cache elements per category: {cat_key: {name: elem}}
        self.cache = {}
        self.current_cat = None

        self.Text = "Transfer Items"
        self.Size = Size(710, 720)
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimumSize = Size(710, 720)
        self.Padding = Padding(20)

        Label(Text="Category:", Location=Point(30, 40), Size=Size(130, 20), Parent=self)

        self.cmb_cat = ComboBox(Location=Point(30, 62), Size=Size(630, 23),
                                DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for c in sorted(CATEGORY_MAP.keys()):
            self.cmb_cat.Items.Add(c)
        self.cmb_cat.SelectedIndexChanged += self.on_category_changed

        Label(Text="Search:", Location=Point(30, 100), Size=Size(60, 20), Parent=self)

        self.txt_search = TextBox(Location=Point(90, 98), Size=Size(580, 23), Parent=self)
        self.txt_search.TextChanged += self.filter_items

        Label(Text="Items:", Location=Point(30, 130), Size=Size(450, 20), Parent=self)

        self.chk_items = CheckedListBox(Location=Point(30, 152), Size=Size(630, 340),
                                        ScrollAlwaysVisible=True, Parent=self)
        self.chk_items.ItemCheck += self.update_selected_count

        Button(Text="All", Location=Point(30, 500), Size=Size(70, 25), Parent=self).Click += self.sel_all
        Button(Text="None", Location=Point(108, 500), Size=Size(70, 25), Parent=self).Click += self.sel_none
        Button(Text="Show Selected", Location=Point(186, 500), Size=Size(110, 25), Parent=self).Click += self.show_selected
        Button(Text="Show All", Location=Point(304, 500), Size=Size(90, 25), Parent=self).Click += self.show_all
        Button(Text="Show Common", Location=Point(402, 500), Size=Size(110, 25), Parent=self).Click += self.show_common

        self.lbl_selected = Label(
            Text="Selected: 0",
            Location=Point(520, 503), Size=Size(140, 20),
            Parent=self, Font=Font("Segoe UI", 9, FontStyle.Regular))
        self.lbl_selected.TextAlign = ContentAlignment.MiddleLeft

        # Total selection summary across all categories
        self.lbl_total = Label(
            Text="",
            Location=Point(30, 535), Size=Size(630, 40),
            Parent=self, Font=Font("Segoe UI", 8, FontStyle.Regular))
        self.lbl_total.ForeColor = Color.FromArgb(80, 80, 80)

        # Botão Back
        btn_back = Button(Text="Back", Location=Point(500, 640), Size=Size(70, 30), Parent=self)
        btn_back.Click += self.go_back

        # Botão Transfer
        btn_transfer = Button(Text="Transfer", Location=Point(580, 640), Size=Size(90, 30), Parent=self)
        btn_transfer.BackColor = Color.FromArgb(0, 100, 200)
        btn_transfer.ForeColor = Color.White
        btn_transfer.Font = Font("Segoe UI", 9, FontStyle.Bold)
        btn_transfer.Click += self.transfer

    def _save_current_selection(self):
        """Save checkbox state for the current category."""
        if self.current_cat:
            selected = set()
            for i in range(self.chk_items.Items.Count):
                if self.chk_items.GetItemChecked(i):
                    selected.add(self.chk_items.Items[i])
            self.selections[self.current_cat] = selected

    def _restore_selection(self, cat_key):
        """Restore checkbox state for a category."""
        saved = self.selections.get(cat_key, set())
        for i in range(self.chk_items.Items.Count):
            if self.chk_items.Items[i] in saved:
                self.chk_items.SetItemChecked(i, True)

    def _update_total_label(self):
        """Update the summary label showing selections across all categories."""
        parts = []
        total = 0
        for cat in sorted(self.selections.keys()):
            count = len(self.selections[cat])
            if count > 0:
                parts.append("{}: {}".format(cat, count))
                total += count
        if parts:
            self.lbl_total.Text = "Total: {} items  |  {}".format(total, "  |  ".join(parts))
        else:
            self.lbl_total.Text = ""

    def update_selected_count(self, s, e):
        try:
            self.BeginInvoke(Action(self._update_count_delayed))
        except:
            pass

    def _update_count_delayed(self):
        try:
            count = self.chk_items.CheckedItems.Count
            self.lbl_selected.Text = "Selected: {}".format(count)
        except:
            pass

    def go_back(self, s, e):
        self.Hide()
        ProjectSelectorForm().ShowDialog()
        self.Close()

    def on_category_changed(self, s, e):
        """Save current selection, load new category, restore its selection."""
        self._save_current_selection()
        self._update_total_label()

        key = self.cmb_cat.SelectedItem
        if not key:
            return

        self.current_cat = key
        self.txt_search.Text = ""

        # Use cache if already loaded
        if key in self.cache:
            self.all_elements = self.cache[key]
            self.all_items = sorted(self.all_elements.keys())
        else:
            self.all_elements = {}
            self.all_items = []
            try:
                elems = CATEGORY_MAP[key](self.src_doc)
                for elem in elems:
                    name = get_name(elem)
                    if name:
                        self.all_elements[name] = elem
                self.all_items = sorted(self.all_elements.keys())
                self.cache[key] = dict(self.all_elements)
            except Exception as ex:
                MessageBox.Show("Error loading: {}".format(ex), "Error")
                return

        # Compute common names
        self.common_names = set()
        tgt_names = set()
        for tgt_doc in self.tgt_docs:
            try:
                tgt_elems = CATEGORY_MAP[key](tgt_doc)
                for elem in tgt_elems:
                    tname = get_name(elem)
                    if tname:
                        tgt_names.add(tname)
            except:
                pass
        self.common_names = set(self.all_items) & tgt_names

        # Populate list and restore selection
        self.chk_items.Items.Clear()
        for n in self.all_items:
            self.chk_items.Items.Add(n)
        self._restore_selection(key)
        self._update_count_delayed()

    def filter_items(self, s, e):
        search_text = self.txt_search.Text.lower()

        # Save current checks before clearing
        checked_items = set()
        for i in range(self.chk_items.Items.Count):
            if self.chk_items.GetItemChecked(i):
                checked_items.add(self.chk_items.Items[i])

        # Merge with saved selection for this category
        saved = self.selections.get(self.current_cat, set())
        checked_items = checked_items | saved

        self.chk_items.Items.Clear()
        for item in self.all_items:
            if search_text and search_text not in item.lower():
                continue
            idx = self.chk_items.Items.Add(item)
            if item in checked_items:
                self.chk_items.SetItemChecked(idx, True)

        self._update_count_delayed()

    def show_selected(self, s, e):
        self._save_current_selection()
        checked_items = self.selections.get(self.current_cat, set())

        if not checked_items:
            MessageBox.Show("No items selected.", "Info")
            return

        self.chk_items.Items.Clear()
        for item in sorted(checked_items):
            idx = self.chk_items.Items.Add(item)
            self.chk_items.SetItemChecked(idx, True)

    def show_all(self, s, e):
        self._save_current_selection()
        self.txt_search.Text = ""

        self.chk_items.Items.Clear()
        for n in self.all_items:
            self.chk_items.Items.Add(n)
        self._restore_selection(self.current_cat)
        self._update_count_delayed()

    def show_common(self, s, e):
        if not self.common_names:
            MessageBox.Show("No common items found between source and target.", "Info")
            return

        self._save_current_selection()
        saved = self.selections.get(self.current_cat, set())

        self.chk_items.Items.Clear()
        for item in sorted(self.common_names):
            idx = self.chk_items.Items.Add(item)
            if item in saved:
                self.chk_items.SetItemChecked(idx, True)

        self._update_count_delayed()

    def sel_all(self, s, e):
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, True)
        self._save_current_selection()
        self._update_count_delayed()
        self._update_total_label()

    def sel_none(self, s, e):
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, False)
        self._save_current_selection()
        self._update_count_delayed()
        self._update_total_label()

    def transfer(self, s, e):
        # Save current category selection first
        self._save_current_selection()

        # Collect all selections across all categories
        all_transfers = {}
        for cat_key, names in self.selections.items():
            if names:
                all_transfers[cat_key] = names

        if not all_transfers:
            MessageBox.Show("No items selected in any category.", "Warning")
            return

        # Build summary
        summary_parts = []
        total_items = 0
        for cat in sorted(all_transfers.keys()):
            count = len(all_transfers[cat])
            summary_parts.append("  {}: {} items".format(cat, count))
            total_items += count
        summary = "Transfer {} items?\n\n{}".format(total_items, "\n".join(summary_parts))

        result = MessageBox.Show(summary, "Confirm Transfer", MessageBoxButtons.YesNo)
        if result != DialogResult.Yes:
            return

        progress_form = ProgressForm()
        progress_form.Show()
        Application.DoEvents()

        errors = []
        total_steps = len(all_transfers) * len(self.tgt_docs)
        current_step = 0

        for cat_key, sel_names in all_transfers.items():
            for tgt_doc in self.tgt_docs:
                current_step += 1
                pct = int((current_step / float(max(total_steps, 1))) * 100)
                progress_form.update_progress(pct)

                if cat_key == "Materials":
                    src_elems = CATEGORY_MAP[cat_key](self.src_doc)
                    src_sel = [elem for elem in src_elems if get_name(elem) in sel_names]

                    tg = TransactionGroup(tgt_doc, "Material Overwrite")
                    tg.Start()
                    try:
                        transfer_materials_only(src_sel, self.src_doc, tgt_doc)
                        tg.Assimilate()
                    except Exception as ex:
                        tg.RollBack()
                        errors.append("{} - {}: {}".format(cat_key, tgt_doc.Title, str(ex)))
                else:
                    cached = self.cache.get(cat_key, {})
                    src_elems = [cached[name] for name in sel_names if name in cached]

                    tg = TransactionGroup(tgt_doc, "Transfer {}".format(cat_key))
                    tg.Start()
                    try:
                        transfer_with_element_preservation(src_elems, self.src_doc, tgt_doc, cat_key, progress_form)
                        tg.Assimilate()
                    except Exception as ex:
                        tg.RollBack()
                        errors.append("{} - {}: {}".format(cat_key, tgt_doc.Title, str(ex)))

        progress_form.update_progress(100)
        Application.DoEvents()
        progress_form.Close()

        if errors:
            MessageBox.Show("Transfer complete with errors:\n\n{}".format("\n".join(errors)), "Complete")
        else:
            MessageBox.Show("Transfer complete!", "Complete")

        self.Close()

if __name__ == "__main__":
    ProjectSelectorForm().ShowDialog()
