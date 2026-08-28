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
    TextBox, ProgressBar, FormBorderStyle, ProgressBarStyle
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

class OverwriteHandler(IDuplicateTypeNamesHandler):
    def OnDuplicateTypeNamesFound(self, args):
        return DuplicateTypeAction.UseDestinationTypes

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

def find_elements_using_type(type_element, doc):
    """Find all instances using a specific type"""
    elements = []
    try:
        type_id = type_element.Id
        if isinstance(type_element, WallType):
            all_elements = FilteredElementCollector(doc).OfClass(Wall).WhereElementIsNotElementType().ToElements()
        elif isinstance(type_element, FloorType):
            all_elements = FilteredElementCollector(doc).OfClass(Floor).WhereElementIsNotElementType().ToElements()
        elif isinstance(type_element, CeilingType):
            all_elements = FilteredElementCollector(doc).OfClass(Ceiling).WhereElementIsNotElementType().ToElements()
        elif isinstance(type_element, RoofType):
            all_elements = FilteredElementCollector(doc).OfClass(RoofBase).WhereElementIsNotElementType().ToElements()
        else:
            return elements

        for elem in all_elements:
            try:
                if elem.GetTypeId() == type_id:
                    elements.append(elem)
            except:
                pass
    except:
        pass

    return elements

def get_materials_from_type(type_element, src_doc):
    """Get all materials used by a type element"""
    materials = {}
    try:
        param = type_element.get_Parameter(BuiltInParameter.STRUCTURAL_MATERIAL_PARAM)
        if param and param.HasValue:
            mat_id = param.AsElementId()
            if mat_id and mat_id != ElementId.InvalidElementId:
                mat = src_doc.GetElement(mat_id)
                if mat and isinstance(mat, Material):
                    materials[mat.Name] = mat

        if hasattr(type_element, 'GetCompoundStructure'):
            cs = type_element.GetCompoundStructure()
            if cs:
                for layer in cs.GetLayers():
                    mat_id = layer.MaterialId
                    if mat_id and mat_id != ElementId.InvalidElementId:
                        mat = src_doc.GetElement(mat_id)
                        if mat and isinstance(mat, Material):
                            materials[mat.Name] = mat

                for sweep_type in [WallSweepType.Sweep, WallSweepType.Reveal]:
                    try:
                        sweeps = cs.GetWallSweepsInfo(sweep_type)
                        for sweep in sweeps:
                            mat_id = sweep.MaterialId
                            if mat_id and mat_id != ElementId.InvalidElementId:
                                mat = src_doc.GetElement(mat_id)
                                if mat and isinstance(mat, Material):
                                    materials[mat.Name] = mat
                    except:
                        pass
    except:
        pass

    return materials

def collect_material_ids_from_types(elements, src_doc):
    """Collect material IDs from types"""
    material_ids = set()
    for element in elements:
        materials = get_materials_from_type(element, src_doc)
        for mat in materials.values():
            material_ids.add(mat.Id)
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

def get_boundary_curves_from_element(element):
    """Get boundary curves from floor or ceiling"""
    curves = []
    try:
        sketch = element.GetSketch()
        if sketch:
            profile = sketch.Profile
            for curve_array in profile:
                for curve in curve_array:
                    curves.append(curve)
            if curves:
                return curves
    except:
        pass

    try:
        options = Options()
        options.ComputeReferences = True
        options.IncludeNonVisibleObjects = True
        geom_elem = element.get_Geometry(options)
        for geom_obj in geom_elem:
            if isinstance(geom_obj, Solid):
                for face in geom_obj.Faces:
                    if isinstance(face, PlanarFace):
                        edge_array = face.EdgeLoops
                        if edge_array.Size > 0:
                            edge_loop = edge_array.get_Item(0)
                            for edge in edge_loop:
                                curve = edge.AsCurve()
                                if curve:
                                    curves.append(curve)
                        if curves:
                            return curves
    except:
        pass

    return curves

def save_wall_data(wall):
    """Save complete wall data"""
    data = {
        'element_type': 'Wall',
        'curve': None,
        'level_id': None,
        'height': 10.0,
        'offset': 0.0,
        'flipped': False,
        'structural': False,
        'location_line': None,
        'top_constraint': None,
        'top_offset': 0.0
    }

    try:
        location = wall.Location
        if isinstance(location, LocationCurve):
            data['curve'] = location.Curve

        param = wall.get_Parameter(BuiltInParameter.WALL_BASE_CONSTRAINT)
        if param and param.HasValue:
            data['level_id'] = param.AsElementId()

        param = wall.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET)
        if param and param.HasValue:
            data['offset'] = param.AsDouble()

        param = wall.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM)
        if param and param.HasValue:
            data['height'] = param.AsDouble()

        param = wall.get_Parameter(BuiltInParameter.WALL_HEIGHT_TYPE)
        if param and param.HasValue:
            data['top_constraint'] = param.AsElementId()

        param = wall.get_Parameter(BuiltInParameter.WALL_TOP_OFFSET)
        if param and param.HasValue:
            data['top_offset'] = param.AsDouble()

        try:
            data['flipped'] = wall.Flipped
        except:
            pass

        param = wall.get_Parameter(BuiltInParameter.WALL_STRUCTURAL_SIGNIFICANT)
        if param and param.HasValue:
            data['structural'] = param.AsInteger() == 1

        param = wall.get_Parameter(BuiltInParameter.WALL_KEY_REF_PARAM)
        if param and param.HasValue:
            data['location_line'] = param.AsInteger()
    except:
        pass

    return data

def save_floor_data(floor):
    """Save complete floor data"""
    data = {
        'element_type': 'Floor',
        'level_id': None,
        'offset': 0.0,
        'structural': False,
        'curves': []
    }

    try:
        param = floor.get_Parameter(BuiltInParameter.LEVEL_PARAM)
        if param and param.HasValue:
            data['level_id'] = param.AsElementId()

        param = floor.get_Parameter(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM)
        if param and param.HasValue:
            data['offset'] = param.AsDouble()

        param = floor.get_Parameter(BuiltInParameter.FLOOR_PARAM_IS_STRUCTURAL)
        if param and param.HasValue:
            data['structural'] = param.AsInteger() == 1

        curves = get_boundary_curves_from_element(floor)
        data['curves'] = curves
    except:
        pass

    return data

def save_ceiling_data(ceiling):
    """Save complete ceiling data"""
    data = {
        'element_type': 'Ceiling',
        'level_id': None,
        'offset': 0.0,
        'curves': []
    }

    try:
        param = ceiling.get_Parameter(BuiltInParameter.LEVEL_PARAM)
        if param and param.HasValue:
            data['level_id'] = param.AsElementId()

        param = ceiling.get_Parameter(BuiltInParameter.CEILING_HEIGHTABOVELEVEL_PARAM)
        if param and param.HasValue:
            data['offset'] = param.AsDouble()

        curves = get_boundary_curves_from_element(ceiling)
        data['curves'] = curves
    except:
        pass

    return data

def save_roof_data(roof):
    """Save complete roof data"""
    data = {
        'element_type': 'Roof',
        'level_id': None,
        'offset': 0.0,
        'curves': [],
        'roof_type': None
    }

    try:
        param = roof.get_Parameter(BuiltInParameter.ROOF_BASE_LEVEL_PARAM)
        if param and param.HasValue:
            data['level_id'] = param.AsElementId()

        param = roof.get_Parameter(BuiltInParameter.ROOF_LEVEL_OFFSET_PARAM)
        if param and param.HasValue:
            data['offset'] = param.AsDouble()

        if isinstance(roof, FootPrintRoof):
            data['roof_type'] = 'FootPrint'
            curves = get_boundary_curves_from_element(roof)
            data['curves'] = curves
        elif isinstance(roof, ExtrusionRoof):
            data['roof_type'] = 'Extrusion'
    except:
        pass

    return data

def recreate_wall(wall_data, new_type_id, doc):
    """Recreate wall from saved data"""
    try:
        curve = wall_data['curve']
        level_id = wall_data['level_id']

        if not curve or not level_id:
            return None

        level = doc.GetElement(level_id)
        if not level:
            return None

        new_wall = Wall.Create(
            doc, curve, new_type_id, level_id,
            wall_data['height'], wall_data['offset'],
            wall_data['flipped'], wall_data['structural']
        )

        if new_wall:
            if wall_data['location_line'] is not None:
                param = new_wall.get_Parameter(BuiltInParameter.WALL_KEY_REF_PARAM)
                if param and not param.IsReadOnly:
                    param.Set(wall_data['location_line'])

            if wall_data['top_constraint']:
                param = new_wall.get_Parameter(BuiltInParameter.WALL_HEIGHT_TYPE)
                if param and not param.IsReadOnly:
                    param.Set(wall_data['top_constraint'])

            if wall_data['top_offset'] != 0.0:
                param = new_wall.get_Parameter(BuiltInParameter.WALL_TOP_OFFSET)
                if param and not param.IsReadOnly:
                    param.Set(wall_data['top_offset'])

        return new_wall
    except:
        return None

def recreate_floor(floor_data, new_type_id, doc):
    """Recreate floor from saved data"""
    try:
        level_id = floor_data['level_id']
        curves = floor_data['curves']

        if not level_id or not curves or len(curves) == 0:
            return None

        level = doc.GetElement(level_id)
        if not level:
            return None

        try:
            curve_array = CurveArray()
            for curve in curves:
                curve_array.Append(curve)

            if curve_array.Size > 0:
                new_floor = doc.Create.NewFloor(
                    curve_array, new_type_id, level_id, floor_data['structural']
                )

                if new_floor and floor_data['offset'] != 0.0:
                    param = new_floor.get_Parameter(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM)
                    if param and not param.IsReadOnly:
                        param.Set(floor_data['offset'])

                return new_floor
        except:
            pass

        try:
            curve_loop = CurveLoop()
            for curve in curves:
                curve_loop.Append(curve)

            curve_loops = List[CurveLoop]()
            curve_loops.Add(curve_loop)

            new_floor = Floor.Create(doc, curve_loops, new_type_id, level_id)

            if new_floor:
                if floor_data['offset'] != 0.0:
                    param = new_floor.get_Parameter(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM)
                    if param and not param.IsReadOnly:
                        param.Set(floor_data['offset'])

                if floor_data['structural']:
                    param = new_floor.get_Parameter(BuiltInParameter.FLOOR_PARAM_IS_STRUCTURAL)
                    if param and not param.IsReadOnly:
                        param.Set(1)

            return new_floor
        except:
            pass
    except:
        pass

    return None

def recreate_ceiling(ceiling_data, new_type_id, doc):
    """Recreate ceiling from saved data"""
    try:
        level_id = ceiling_data['level_id']
        curves = ceiling_data['curves']

        if not level_id or not curves or len(curves) == 0:
            return None

        level = doc.GetElement(level_id)
        if not level:
            return None

        try:
            curve_array = CurveArray()
            for curve in curves:
                curve_array.Append(curve)

            if curve_array.Size > 0:
                new_ceiling = doc.Create.NewCeiling(curve_array, new_type_id, level_id)

                if new_ceiling and ceiling_data['offset'] != 0.0:
                    param = new_ceiling.get_Parameter(BuiltInParameter.CEILING_HEIGHTABOVELEVEL_PARAM)
                    if param and not param.IsReadOnly:
                        param.Set(ceiling_data['offset'])

                return new_ceiling
        except:
            pass

        try:
            curve_loop = CurveLoop()
            for curve in curves:
                curve_loop.Append(curve)

            curve_loops = List[CurveLoop]()
            curve_loops.Add(curve_loop)

            new_ceiling = Ceiling.Create(doc, curve_loops, new_type_id, level_id)

            if new_ceiling and ceiling_data['offset'] != 0.0:
                param = new_ceiling.get_Parameter(BuiltInParameter.CEILING_HEIGHTABOVELEVEL_PARAM)
                if param and not param.IsReadOnly:
                    param.Set(ceiling_data['offset'])

            return new_ceiling
        except:
            pass
    except:
        pass

    return None

def recreate_roof(roof_data, new_type_id, doc):
    """Recreate roof from saved data"""
    try:
        level_id = roof_data['level_id']
        curves = roof_data['curves']
        roof_type = roof_data['roof_type']

        if not level_id or not curves or len(curves) == 0 or roof_type != 'FootPrint':
            return None

        level = doc.GetElement(level_id)
        if not level:
            return None

        curve_array = CurveArray()
        for curve in curves:
            curve_array.Append(curve)

        if curve_array.Size > 0:
            model_curve_array = ModelCurveArray()
            new_roof = doc.Create.NewFootPrintRoof(
                curve_array, level_id, new_type_id, model_curve_array
            )

            if new_roof and roof_data['offset'] != 0.0:
                param = new_roof.get_Parameter(BuiltInParameter.ROOF_LEVEL_OFFSET_PARAM)
                if param and not param.IsReadOnly:
                    param.Set(roof_data['offset'])

            return new_roof
    except:
        pass

    return None

def save_elements_data(elements):
    """Save data for all elements"""
    saved_data = []
    for elem in elements:
        try:
            if isinstance(elem, Wall):
                data = save_wall_data(elem)
                saved_data.append(data)
            elif isinstance(elem, Floor):
                data = save_floor_data(elem)
                if data['curves'] and len(data['curves']) > 0:
                    saved_data.append(data)
            elif isinstance(elem, Ceiling):
                data = save_ceiling_data(elem)
                if data['curves'] and len(data['curves']) > 0:
                    saved_data.append(data)
            elif isinstance(elem, RoofBase):
                data = save_roof_data(elem)
                if data['curves'] and len(data['curves']) > 0:
                    saved_data.append(data)
        except:
            pass

    return saved_data

def recreate_elements(saved_data, new_type_id, doc):
    """Recreate all elements from saved data"""
    recreated = 0
    for data in saved_data:
        try:
            elem_type = data.get('element_type')
            new_elem = None

            if elem_type == 'Wall':
                new_elem = recreate_wall(data, new_type_id, doc)
            elif elem_type == 'Floor':
                new_elem = recreate_floor(data, new_type_id, doc)
            elif elem_type == 'Ceiling':
                new_elem = recreate_ceiling(data, new_type_id, doc)
            elif elem_type == 'Roof':
                new_elem = recreate_roof(data, new_type_id, doc)

            if new_elem:
                recreated += 1
        except:
            pass

    return recreated

def transfer_with_element_preservation(src_elems, src_doc, tgt_doc, cat_key, progress_form=None):
    """Complete workflow for types"""
    stats = {
        "materials_overwritten": 0,
        "materials_copied_new": 0,
        "materials_failed": 0,
        "elements_found": 0,
        "elements_deleted": 0,
        "types_deleted": 0,
        "types_copied": 0,
        "elements_recreated": 0
    }

    if progress_form:
        progress_form.update_progress(10)

    material_ids = collect_material_ids_from_types(src_elems, src_doc)

    if material_ids:
        if progress_form:
            progress_form.update_progress(20)
        mat_stats = overwrite_materials_by_name(material_ids, src_doc, tgt_doc)
        stats["materials_overwritten"] = mat_stats["materials_overwritten"]
        stats["materials_copied_new"] = mat_stats["materials_copied_new"]
        stats["materials_failed"] = mat_stats["materials_failed"]

    if progress_form:
        progress_form.update_progress(30)

    type_elements_map = {}
    src_dict = {get_name(e): e for e in src_elems if get_name(e)}
    tgt_elems = CATEGORY_MAP[cat_key](tgt_doc)
    tgt_dict = {get_name(e): e for e in tgt_elems if get_name(e)}

    for type_name in src_dict.keys():
        if type_name in tgt_dict:
            old_type = tgt_dict[type_name]
            elements_using_type = find_elements_using_type(old_type, tgt_doc)
            if elements_using_type:
                saved_data = save_elements_data(elements_using_type)
                type_elements_map[type_name] = (saved_data, old_type.Id, elements_using_type)
                stats["elements_found"] += len(elements_using_type)

    if progress_form:
        progress_form.update_progress(40)

    elements_to_delete = List[ElementId]()
    for type_name, (saved_data, type_id, elements) in type_elements_map.items():
        for elem in elements:
            elements_to_delete.Add(elem.Id)

    if elements_to_delete.Count > 0:
        t1 = Transaction(tgt_doc, "Delete Elements")
        t1.Start()
        try:
            deleted = tgt_doc.Delete(elements_to_delete)
            stats["elements_deleted"] = deleted.Count
            t1.Commit()
        except:
            t1.RollBack()

    if progress_form:
        progress_form.update_progress(55)

    types_to_delete = List[ElementId]()
    for type_name in src_dict.keys():
        if type_name in tgt_dict:
            types_to_delete.Add(tgt_dict[type_name].Id)

    if types_to_delete.Count > 0:
        t2 = Transaction(tgt_doc, "Delete Types")
        t2.Start()
        try:
            deleted = tgt_doc.Delete(types_to_delete)
            stats["types_deleted"] = deleted.Count
            t2.Commit()
        except:
            t2.RollBack()

    if progress_form:
        progress_form.update_progress(70)

    to_copy = List[ElementId]([e.Id for e in src_dict.values()])

    if to_copy.Count > 0:
        t3 = Transaction(tgt_doc, "Copy New Types")
        t3.Start()
        try:
            opts = CopyPasteOptions()
            opts.SetDuplicateTypeNamesHandler(OverwriteHandler())
            copied_ids = ElementTransformUtils.CopyElements(src_doc, to_copy, tgt_doc, None, opts)
            stats["types_copied"] = copied_ids.Count
            t3.Commit()
        except:
            t3.RollBack()

    if progress_form:
        progress_form.update_progress(85)

    new_tgt_elems = CATEGORY_MAP[cat_key](tgt_doc)
    new_tgt_dict = {get_name(e): e for e in new_tgt_elems if get_name(e)}

    if type_elements_map:
        t4 = Transaction(tgt_doc, "Recreate Elements")
        t4.Start()
        try:
            for type_name, (saved_data, old_type_id, old_elements) in type_elements_map.items():
                if type_name in new_tgt_dict:
                    new_type = new_tgt_dict[type_name]
                    new_type_id = new_type.Id
                    recreated = recreate_elements(saved_data, new_type_id, tgt_doc)
                    stats["elements_recreated"] += recreated
            t4.Commit()
        except:
            t4.RollBack()

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
        self.Size = Size(550, 480)
        self.StartPosition = FormStartPosition.CenterScreen

        Label(Text="Source Project:", Location=Point(10, 20), Size=Size(130, 20), Parent=self)

        self.cmb_src = ComboBox(Location=Point(10, 40), Size=Size(520, 23),
                                DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for n in doc_names:
            self.cmb_src.Items.Add(n)

        Label(Text="Target Projects:", Location=Point(10, 80), Size=Size(130, 20), Parent=self)

        self.chk_tgt = CheckedListBox(Location=Point(10, 100), Size=Size(520, 300),
                                      ScrollAlwaysVisible=True, Parent=self)
        for n in doc_names:
            self.chk_tgt.Items.Add(n)

        btn = Button(Text="Next", Location=Point(440, 410), Size=Size(90, 30), Parent=self)
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

        self.Text = "Transfer Items"
        self.Size = Size(680, 620)
        self.StartPosition = FormStartPosition.CenterScreen

        Label(Text="Category:", Location=Point(10, 20), Size=Size(130, 20), Parent=self)

        self.cmb_cat = ComboBox(Location=Point(10, 40), Size=Size(650, 23),
                                DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for c in sorted(CATEGORY_MAP.keys()):
            self.cmb_cat.Items.Add(c)
        self.cmb_cat.SelectedIndexChanged += self.load

        Label(Text="Search:", Location=Point(10, 80), Size=Size(60, 20), Parent=self)

        self.txt_search = TextBox(Location=Point(70, 78), Size=Size(590, 23), Parent=self)
        self.txt_search.TextChanged += self.filter_items

        Label(Text="Items:", Location=Point(10, 110), Size=Size(450, 20), Parent=self)

        self.chk_items = CheckedListBox(Location=Point(10, 130), Size=Size(650, 350),
                                        ScrollAlwaysVisible=True, Parent=self)
        self.chk_items.ItemCheck += self.update_selected_count

        Button(Text="All", Location=Point(10, 490), Size=Size(80, 25), Parent=self).Click += self.sel_all
        Button(Text="None", Location=Point(100, 490), Size=Size(80, 25), Parent=self).Click += self.sel_none
        Button(Text="Show Selected", Location=Point(190, 490), Size=Size(120, 25), Parent=self).Click += self.show_selected
        Button(Text="Show All", Location=Point(320, 490), Size=Size(100, 25), Parent=self).Click += self.show_all

        # Label "Selected: X" ao lado do botão Show All
        self.lbl_selected = Label(
            Text="Selected: 0",
            Location=Point(430, 493),
            Size=Size(90, 20),
            Parent=self,
            Font=Font("Segoe UI", 9, FontStyle.Regular)
        )
        self.lbl_selected.TextAlign = ContentAlignment.MiddleLeft

        # Botão Back
        btn_back = Button(Text="Back", Location=Point(525, 550), Size=Size(60, 30), Parent=self)
        btn_back.Click += self.go_back

        # Botão Transfer
        btn_transfer = Button(Text="Transfer", Location=Point(590, 550), Size=Size(80, 30), Parent=self)
        btn_transfer.Click += self.transfer

    def update_selected_count(self, s, e):
        """Atualiza o contador de itens selecionados"""
        try:
            self.BeginInvoke(Action(self._update_count_delayed))
        except:
            pass

    def _update_count_delayed(self):
        """Atualiza o contador após a mudança de seleção"""
        try:
            count = self.chk_items.CheckedItems.Count
            self.lbl_selected.Text = "Selected: {}".format(count)
        except:
            pass

    def go_back(self, s, e):
        """Volta para a tela de seleção de projetos"""
        self.Hide()
        ProjectSelectorForm().ShowDialog()
        self.Close()

    def load(self, s, e):
        self.chk_items.Items.Clear()
        self.all_items = []
        self.all_elements = {}
        self.txt_search.Text = ""
        self.lbl_selected.Text = "Selected: 0"

        key = self.cmb_cat.SelectedItem
        if not key:
            return

        try:
            elems = CATEGORY_MAP[key](self.src_doc)
            for elem in elems:
                name = get_name(elem)
                if name:
                    self.all_elements[name] = elem

            names = sorted(self.all_elements.keys())
            self.all_items = names
            for n in names:
                self.chk_items.Items.Add(n)
        except Exception as ex:
            MessageBox.Show("Error loading: {}".format(ex), "Error")

    def filter_items(self, s, e):
        search_text = self.txt_search.Text.lower()

        checked_items = set()
        for i in range(self.chk_items.Items.Count):
            if self.chk_items.GetItemChecked(i):
                checked_items.add(self.chk_items.Items[i])

        self.chk_items.Items.Clear()

        for item in self.all_items:
            if search_text in item.lower():
                idx = self.chk_items.Items.Add(item)
                if item in checked_items:
                    self.chk_items.SetItemChecked(idx, True)

        self._update_count_delayed()

    def show_selected(self, s, e):
        checked_items = []
        for i in range(self.chk_items.Items.Count):
            if self.chk_items.GetItemChecked(i):
                checked_items.append(self.chk_items.Items[i])

        if not checked_items:
            MessageBox.Show("No items selected.", "Info")
            return

        self.chk_items.Items.Clear()
        for item in checked_items:
            idx = self.chk_items.Items.Add(item)
            self.chk_items.SetItemChecked(idx, True)

    def show_all(self, s, e):
        self.txt_search.Text = ""
        self.filter_items(None, None)

    def sel_all(self, s, e):
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, True)
        self._update_count_delayed()

    def sel_none(self, s, e):
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, False)
        self._update_count_delayed()

    def transfer(self, s, e):
        cat_key = self.cmb_cat.SelectedItem
        sel_names = [self.chk_items.Items[i] for i in self.chk_items.CheckedIndices]

        if not cat_key or not sel_names:
            MessageBox.Show("Select category and items.", "Warning")
            return

        result = MessageBox.Show(
            "Overwrite items?",
            "Confirm Transfer",
            MessageBoxButtons.YesNo
        )

        if result != DialogResult.Yes:
            return

        progress_form = ProgressForm()
        progress_form.Show()
        Application.DoEvents()

        if cat_key == "Materials":
            src_elems = CATEGORY_MAP[cat_key](self.src_doc)
            src_sel = [e for e in src_elems if get_name(e) in sel_names]

            total_stats = {
                "materials_overwritten": 0,
                "materials_copied_new": 0,
                "materials_failed": 0
            }

            errors = []
            total_docs = len(self.tgt_docs)

            for idx, tgt_doc in enumerate(self.tgt_docs):
                progress_value = int((idx / float(total_docs)) * 100)
                progress_form.update_progress(progress_value)

                tg = TransactionGroup(tgt_doc, "Material Overwrite")
                tg.Start()
                try:
                    stats = transfer_materials_only(src_sel, self.src_doc, tgt_doc)
                    for k in total_stats:
                        total_stats[k] += stats[k]
                    tg.Assimilate()
                except Exception as ex:
                    tg.RollBack()
                    errors.append("{}: {}".format(tgt_doc.Title, str(ex)))

            progress_form.update_progress(100)
            Application.DoEvents()

            progress_form.Close()

            if errors:
                MessageBox.Show("Transfer complete!", "Complete with Errors")
            else:
                MessageBox.Show("Transfer complete!", "Complete")

            self.Close()

        else:
            src_elems = [self.all_elements[name] for name in sel_names if name in self.all_elements]

            total_stats = {
                "materials_overwritten": 0,
                "materials_copied_new": 0,
                "materials_failed": 0,
                "elements_found": 0,
                "elements_deleted": 0,
                "types_deleted": 0,
                "types_copied": 0,
                "elements_recreated": 0
            }

            errors = []
            total_docs = len(self.tgt_docs)

            for idx, tgt_doc in enumerate(self.tgt_docs):
                base_progress = int((idx / float(total_docs)) * 100)
                progress_form.update_progress(base_progress)

                tg = TransactionGroup(tgt_doc, "Transfer with Material Overwrite")
                tg.Start()
                try:
                    stats = transfer_with_element_preservation(src_elems, self.src_doc, tgt_doc, cat_key, progress_form)
                    for k in total_stats:
                        total_stats[k] += stats[k]
                    tg.Assimilate()
                except Exception as ex:
                    tg.RollBack()
                    errors.append("{}: {}".format(tgt_doc.Title, str(ex)))

            progress_form.update_progress(100)
            Application.DoEvents()

            progress_form.Close()

            if errors:
                MessageBox.Show("Transfer complete!", "Complete with Errors")
            else:
                MessageBox.Show("Transfer complete!", "Complete")

            self.Close()

if __name__ == "__main__":
    ProjectSelectorForm().ShowDialog()
