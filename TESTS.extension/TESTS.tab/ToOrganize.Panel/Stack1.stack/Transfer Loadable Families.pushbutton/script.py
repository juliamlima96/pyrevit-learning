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
    ProgressBar, Panel
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

def get_material_names_from_symbols(symbols, doc, debug_messages):
    """Coleta nomes de TODOS os materiais das famílias selecionadas"""
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

def map_elements_using_material(material_name, tgt_doc, debug_messages):
    """
    Mapeia TODOS os elementos (tipos de família E tipos de sistema) que usam um material específico.
    Retorna: {element_id: {param_name: material_id}}
    """
    elements_map = {}

    try:
        # Buscar o material no target
        tgt_materials = FilteredElementCollector(tgt_doc).OfClass(Material).ToElements()
        target_material = None
        for mat in tgt_materials:
            if mat.Name == material_name:
                target_material = mat
                break

        if not target_material:
            debug_messages.append("  Material '{}' not found in target".format(material_name))
            return elements_map

        material_id = target_material.Id

        # 1. FAMILY SYMBOLS (portas, janelas, mobiliário, etc)
        all_symbols = FilteredElementCollector(tgt_doc).OfClass(FamilySymbol).WhereElementIsElementType().ToElements()
        
        for symbol in all_symbols:
            element_materials = {}

            for param in symbol.Parameters:
                try:
                    if param.StorageType == StorageType.ElementId and param.HasValue:
                        param_elem_id = param.AsElementId()
                        if param_elem_id == material_id:
                            element_materials[param.Definition.Name] = material_id
                except:
                    pass

            if element_materials:
                elements_map[symbol.Id] = element_materials
                debug_messages.append("    FamilySymbol '{}' uses material".format(get_name(symbol)))

        # 2. WALL TYPES
        wall_types = FilteredElementCollector(tgt_doc).OfClass(WallType).ToElements()
        for wall_type in wall_types:
            element_materials = {}
            
            # Verificar CompoundStructure
            try:
                compound_structure = wall_type.GetCompoundStructure()
                if compound_structure:
                    for i in range(compound_structure.LayerCount):
                        layer_material_id = compound_structure.GetMaterialId(i)
                        if layer_material_id == material_id:
                            element_materials["Layer_{}".format(i)] = material_id
            except:
                pass
            
            # Verificar parâmetros
            for param in wall_type.Parameters:
                try:
                    if param.StorageType == StorageType.ElementId and param.HasValue:
                        param_elem_id = param.AsElementId()
                        if param_elem_id == material_id:
                            element_materials[param.Definition.Name] = material_id
                except:
                    pass

            if element_materials:
                elements_map[wall_type.Id] = element_materials
                debug_messages.append("    WallType '{}' uses material".format(wall_type.Name))

        # 3. FLOOR TYPES
        floor_types = FilteredElementCollector(tgt_doc).OfClass(FloorType).ToElements()
        for floor_type in floor_types:
            element_materials = {}
            
            try:
                compound_structure = floor_type.GetCompoundStructure()
                if compound_structure:
                    for i in range(compound_structure.LayerCount):
                        layer_material_id = compound_structure.GetMaterialId(i)
                        if layer_material_id == material_id:
                            element_materials["Layer_{}".format(i)] = material_id
            except:
                pass
            
            for param in floor_type.Parameters:
                try:
                    if param.StorageType == StorageType.ElementId and param.HasValue:
                        param_elem_id = param.AsElementId()
                        if param_elem_id == material_id:
                            element_materials[param.Definition.Name] = material_id
                except:
                    pass

            if element_materials:
                elements_map[floor_type.Id] = element_materials
                debug_messages.append("    FloorType '{}' uses material".format(floor_type.Name))

        # 4. ROOF TYPES
        roof_types = FilteredElementCollector(tgt_doc).OfClass(RoofType).ToElements()
        for roof_type in roof_types:
            element_materials = {}
            
            try:
                compound_structure = roof_type.GetCompoundStructure()
                if compound_structure:
                    for i in range(compound_structure.LayerCount):
                        layer_material_id = compound_structure.GetMaterialId(i)
                        if layer_material_id == material_id:
                            element_materials["Layer_{}".format(i)] = material_id
            except:
                pass
            
            for param in roof_type.Parameters:
                try:
                    if param.StorageType == StorageType.ElementId and param.HasValue:
                        param_elem_id = param.AsElementId()
                        if param_elem_id == material_id:
                            element_materials[param.Definition.Name] = material_id
                except:
                    pass

            if element_materials:
                elements_map[roof_type.Id] = element_materials
                debug_messages.append("    RoofType '{}' uses material".format(roof_type.Name))

        # 5. CEILING TYPES
        ceiling_types = FilteredElementCollector(tgt_doc).OfClass(CeilingType).ToElements()
        for ceiling_type in ceiling_types:
            element_materials = {}
            
            try:
                compound_structure = ceiling_type.GetCompoundStructure()
                if compound_structure:
                    for i in range(compound_structure.LayerCount):
                        layer_material_id = compound_structure.GetMaterialId(i)
                        if layer_material_id == material_id:
                            element_materials["Layer_{}".format(i)] = material_id
            except:
                pass
            
            for param in ceiling_type.Parameters:
                try:
                    if param.StorageType == StorageType.ElementId and param.HasValue:
                        param_elem_id = param.AsElementId()
                        if param_elem_id == material_id:
                            element_materials[param.Definition.Name] = material_id
                except:
                    pass

            if element_materials:
                elements_map[ceiling_type.Id] = element_materials
                debug_messages.append("    CeilingType '{}' uses material".format(ceiling_type.Name))

    except Exception as ex:
        debug_messages.append("  Error mapping elements: {}".format(str(ex)))

    return elements_map

def reapply_material_to_elements(elements_map, material_name, tgt_doc, debug_messages):
    """
    Reaplica o material (agora com novo ID) aos elementos mapeados.
    Suporta FamilySymbols e tipos de sistema (Wall, Floor, Roof, Ceiling).
    """
    reapplied = 0

    try:
        # Buscar o novo material (recém copiado)
        tgt_materials = FilteredElementCollector(tgt_doc).OfClass(Material).ToElements()
        new_material = None
        for mat in tgt_materials:
            if mat.Name == material_name:
                new_material = mat
                break

        if not new_material:
            debug_messages.append("  NEW material '{}' not found!".format(material_name))
            return 0

        new_material_id = new_material.Id
        debug_messages.append("  New material ID: {}".format(new_material_id.IntegerValue))

        # Reaplicar aos elementos
        for elem_id, param_dict in elements_map.items():
            element = tgt_doc.GetElement(elem_id)
            if not element:
                continue

            # Verificar se é um tipo com CompoundStructure
            has_compound = False
            try:
                if isinstance(element, WallType) or isinstance(element, FloorType) or isinstance(element, RoofType) or isinstance(element, CeilingType):
                    compound_structure = element.GetCompoundStructure()
                    if compound_structure:
                        has_compound = True
                        
                        # Reaplicar nas layers
                        for param_name in param_dict.keys():
                            if param_name.startswith("Layer_"):
                                layer_index = int(param_name.split("_")[1])
                                try:
                                    compound_structure.SetMaterialId(layer_index, new_material_id)
                                    reapplied += 1
                                    debug_messages.append("    Reapplied to '{}' -> Layer {}".format(get_name(element), layer_index))
                                except Exception as ex:
                                    debug_messages.append("    Failed layer {} in '{}': {}".format(layer_index, get_name(element), str(ex)))
                        
                        # Aplicar o CompoundStructure de volta
                        element.SetCompoundStructure(compound_structure)
            except:
                pass

            # Reaplicar parâmetros normais
            for param_name in param_dict.keys():
                if not param_name.startswith("Layer_"):  # Skip layers já processadas
                    param = element.LookupParameter(param_name)
                    if param and not param.IsReadOnly:
                        try:
                            param.Set(new_material_id)
                            reapplied += 1
                            debug_messages.append("    Reapplied to '{}' -> '{}'".format(get_name(element), param_name))
                        except Exception as ex:
                            debug_messages.append("    Failed to reapply to '{}': {}".format(get_name(element), str(ex)))

    except Exception as ex:
        debug_messages.append("  Error reapplying material: {}".format(str(ex)))

    return reapplied

def replace_materials_with_mapping(material_names, src_doc, tgt_doc, debug_messages, progress_callback=None):
    """
    Para cada material:
    1. Mapear elementos que o usam
    2. Deletar material
    3. Copiar material do source
    4. Reaplicar aos elementos
    """
    total_replaced = 0
    total_materials = len(material_names)

    for idx, mat_name in enumerate(material_names):
        if progress_callback:
            progress_callback("Processing material: {}".format(mat_name), idx, total_materials)
        
        debug_messages.append("\\n>>> Processing material: {}".format(mat_name))

        # 1. MAPEAR elementos que usam o material
        debug_messages.append("  Step 1: Mapping elements using this material...")
        elements_map = map_elements_using_material(mat_name, tgt_doc, debug_messages)
        debug_messages.append("  Found {} elements using this material".format(len(elements_map)))

        # 2. DELETAR material do target
        debug_messages.append("  Step 2: Deleting old material...")
        try:
            tgt_materials = FilteredElementCollector(tgt_doc).OfClass(Material).ToElements()
            old_mat = None
            for mat in tgt_materials:
                if mat.Name == mat_name:
                    old_mat = mat
                    break

            if old_mat:
                deleted = tgt_doc.Delete(old_mat.Id)
                debug_messages.append("  Deleted (removed {} items)".format(deleted.Count))
            else:
                debug_messages.append("  Material not found in target, will copy new")
        except Exception as ex:
            debug_messages.append("  Could not delete: {}".format(str(ex)))

        # 3. COPIAR material do source
        debug_messages.append("  Step 3: Copying material from source...")
        try:
            src_materials = FilteredElementCollector(src_doc).OfClass(Material).ToElements()
            src_mat = None
            for mat in src_materials:
                if mat.Name == mat_name:
                    src_mat = mat
                    break

            if src_mat:
                materials_to_copy = List[ElementId]()
                materials_to_copy.Add(src_mat.Id)

                opts = CopyPasteOptions()
                opts.SetDuplicateTypeNamesHandler(OverwriteHandler())

                copied_ids = ElementTransformUtils.CopyElements(src_doc, materials_to_copy, tgt_doc, None, opts)
                if copied_ids.Count > 0:
                    debug_messages.append("  Copied successfully")
                    total_replaced += 1
                else:
                    debug_messages.append("  Copy returned 0 elements!")
            else:
                debug_messages.append("  Material not found in source!")
        except Exception as ex:
            debug_messages.append("  Copy failed: {}".format(str(ex)))

        # 4. REAPLICAR material aos elementos mapeados
        if elements_map:
            debug_messages.append("  Step 4: Reapplying material to mapped elements...")
            reapplied = reapply_material_to_elements(elements_map, mat_name, tgt_doc, debug_messages)
            debug_messages.append("  Reapplied to {} parameters".format(reapplied))

    return total_replaced

def save_instance_data(instance, doc):
    data = {
        'type_name': None,
        'host_id': None,
        'level_name': None,
        'elevation_offset': 0.0,
        'location_point': None,
        'rotation': 0.0,
        'facing_flipped': False,
        'hand_flipped': False,
        'sill_height': None,
        'valid': False,
        'error': None
    }

    try:
        symbol = instance.Symbol
        if not symbol:
            data['error'] = "No symbol"
            return data
        data['type_name'] = get_name(symbol)

        location = instance.Location
        if not isinstance(location, LocationPoint):
            data['error'] = "No location point"
            return data

        data['location_point'] = location.Point
        try:
            data['rotation'] = location.Rotation
        except:
            pass

        if hasattr(instance, 'Host'):
            try:
                host = instance.Host
                if host:
                    data['host_id'] = host.Id
            except:
                pass

        level = None

        try:
            param = instance.get_Parameter(BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM)
            if param and param.HasValue:
                level_id = param.AsElementId()
                if level_id and level_id != ElementId.InvalidElementId:
                    level = doc.GetElement(level_id)
                    if level:
                        try:
                            offset_param = instance.get_Parameter(BuiltInParameter.INSTANCE_ELEVATION_PARAM)
                            if offset_param and offset_param.HasValue:
                                data['elevation_offset'] = offset_param.AsDouble()
                        except:
                            pass
        except:
            pass

        if not level:
            try:
                if hasattr(instance, 'LevelId') and instance.LevelId:
                    level = doc.GetElement(instance.LevelId)
            except:
                pass

        if not level:
            try:
                param = instance.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM)
                if param and param.HasValue:
                    level = doc.GetElement(param.AsElementId())
            except:
                pass

        if level:
            data['level_name'] = level.Name
        else:
            data['error'] = "No level"
            return data

        try:
            data['facing_flipped'] = instance.FacingFlipped
            data['hand_flipped'] = instance.HandFlipped
        except:
            pass

        try:
            param = instance.get_Parameter(BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM)
            if param and param.HasValue:
                data['sill_height'] = param.AsDouble()
        except:
            pass

        data['valid'] = True

    except Exception as ex:
        data['error'] = "Exception: {}".format(str(ex))

    return data

def recreate_instance(data, symbol, doc, debug_list):
    if not data.get('valid', False):
        debug_list.append("SKIP: {}".format(data.get('error', 'Invalid')))
        return None

    try:
        level = None
        all_levels = FilteredElementCollector(doc).OfClass(Level).ToElements()

        for lev in all_levels:
            if lev.Name == data['level_name']:
                level = lev
                break

        if not level:
            debug_list.append("FAIL: Level '{}' not found".format(data['level_name']))
            return None

        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()

        location_point = data['location_point']
        new_instance = None

        if data['host_id']:
            host = doc.GetElement(data['host_id'])
            if host:
                try:
                    new_instance = doc.Create.NewFamilyInstance(location_point, symbol, host, level, StructuralType.NonStructural)
                    debug_list.append("SUCCESS with host")
                except Exception as ex:
                    debug_list.append("Failed with host: {}".format(str(ex)))

        if not new_instance:
            try:
                new_instance = doc.Create.NewFamilyInstance(location_point, symbol, level, StructuralType.NonStructural)
                debug_list.append("SUCCESS without host")
            except Exception as ex:
                debug_list.append("Failed without host: {}".format(str(ex)))

        if not new_instance:
            return None

        doc.Regenerate()

        try:
            schedule_level_param = new_instance.get_Parameter(BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM)
            if schedule_level_param and not schedule_level_param.IsReadOnly:
                schedule_level_param.Set(level.Id)
        except:
            pass

        if data['elevation_offset'] != 0.0:
            try:
                offset_param = new_instance.get_Parameter(BuiltInParameter.INSTANCE_ELEVATION_PARAM)
                if offset_param and not offset_param.IsReadOnly:
                    offset_param.Set(data['elevation_offset'])
            except:
                pass

        if data['rotation'] != 0.0:
            try:
                loc = new_instance.Location
                if isinstance(loc, LocationPoint):
                    z_axis = Line.CreateBound(location_point, XYZ(location_point.X, location_point.Y, location_point.Z + 10))
                    loc.Rotate(z_axis, data['rotation'])
            except:
                pass

        try:
            if hasattr(new_instance, 'HandFlipped') and new_instance.HandFlipped != data['hand_flipped']:
                new_instance.flipHand()
        except:
            pass

        try:
            if hasattr(new_instance, 'FacingFlipped') and new_instance.FacingFlipped != data['facing_flipped']:
                new_instance.flipFacing()
        except:
            pass

        if data['sill_height'] is not None:
            try:
                param = new_instance.get_Parameter(BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM)
                if param and not param.IsReadOnly:
                    param.Set(data['sill_height'])
            except:
                pass

        return new_instance

    except Exception as ex:
        debug_list.append("EXCEPTION: {}".format(str(ex)))
        return None

def copy_type_parameters(src_symbol, tgt_symbol, src_doc, tgt_doc, debug_messages):
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
                    if src_param.StorageType == StorageType.String:
                        value = src_param.AsString()
                        if value:
                            tgt_param.Set(value)
                            params_copied += 1
                    elif src_param.StorageType == StorageType.Integer:
                        tgt_param.Set(src_param.AsInteger())
                        params_copied += 1
                    elif src_param.StorageType == StorageType.Double:
                        tgt_param.Set(src_param.AsDouble())
                        params_copied += 1
            except:
                pass

        # Copiar parâmetros de material
        for param in src_symbol.Parameters:
            try:
                if param.StorageType == StorageType.ElementId and param.HasValue:
                    src_elem_id = param.AsElementId()
                    if src_elem_id and src_elem_id != ElementId.InvalidElementId:
                        src_elem = src_doc.GetElement(src_elem_id)
                        if src_elem and isinstance(src_elem, Material):
                            tgt_param = tgt_symbol.LookupParameter(param.Definition.Name)
                            if tgt_param and not tgt_param.IsReadOnly:
                                tgt_materials = FilteredElementCollector(tgt_doc).OfClass(Material).ToElements()
                                tgt_mat = next((m for m in tgt_materials if m.Name == src_elem.Name), None)
                                if tgt_mat:
                                    try:
                                        tgt_param.Set(tgt_mat.Id)
                                        debug_messages.append("  Material: {} -> {}".format(param.Definition.Name, src_elem.Name))
                                        params_copied += 1
                                    except Exception as ex:
                                        debug_messages.append("  Failed material {}: {}".format(src_elem.Name, str(ex)))
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
        int(BuiltInCategory.OST_Doors): BuiltInCategory.OST_Doors,
        int(BuiltInCategory.OST_Windows): BuiltInCategory.OST_Windows,
        int(BuiltInCategory.OST_Casework): BuiltInCategory.OST_Casework,
        int(BuiltInCategory.OST_Furniture): BuiltInCategory.OST_Furniture,
    }
    return category_mapping.get(cat_id, None)

def transfer_loadable_families(src_symbols, src_doc, tgt_doc, progress_callback=None):
    stats = {
        "instances_saved": 0,
        "instances_valid": 0,
        "types_deleted": 0,
        "types_copied": 0,
        "materials_copied": 0,
        "parameters_copied": 0,
        "instances_recreated": 0,
        "instances_failed": 0,
        "debug_messages": []
    }

    try:
        stats["debug_messages"].append("=== SCRIPT START ===")
        stats["debug_messages"].append("Source: {}".format(src_doc.Title))
        stats["debug_messages"].append("Target: {}".format(tgt_doc.Title))

        if not src_symbols:
            return stats

        built_in_cat = get_builtincategory_from_symbols(src_symbols)
        if not built_in_cat:
            return stats

        src_dict = {get_name(e): e for e in src_symbols}

        # STEP 0: Coletar nomes dos materiais
        if progress_callback:
            progress_callback("Collecting materials...", 0, 6)
        
        stats["debug_messages"].append("\\n=== STEP 0: COLLECTING MATERIAL NAMES ===")
        material_names = get_material_names_from_symbols(src_symbols, src_doc, stats["debug_messages"])
        stats["debug_messages"].append("Found {} unique materials".format(len(material_names)))

        # STEP 0.5: Mapear, Deletar, Copiar e Reaplicar materiais
        if material_names:
            if progress_callback:
                progress_callback("Replacing materials...", 1, 6)
            
            stats["debug_messages"].append("\\n=== STEP 0.5: REPLACE MATERIALS WITH MAPPING ===")
            t_mat = Transaction(tgt_doc, "Replace Materials")
            t_mat.Start()
            try:
                stats["materials_copied"] = replace_materials_with_mapping(material_names, src_doc, tgt_doc, stats["debug_messages"], progress_callback)
                t_mat.Commit()
                stats["debug_messages"].append("\\n>>> Materials replaced: {}".format(stats["materials_copied"]))
            except Exception as ex:
                t_mat.RollBack()
                stats["debug_messages"].append("Material transaction failed: {}".format(str(ex)))

        # STEP 1: Collecting target types
        if progress_callback:
            progress_callback("Collecting target types...", 2, 6)
        
        stats["debug_messages"].append("\\n=== STEP 1: COLLECTING TARGET TYPES ===")

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

        tgt_dict = {get_name(e): e for e in tgt_symbols}

        # STEP 2: Saving instances
        if progress_callback:
            progress_callback("Saving instances...", 3, 6)
        
        stats["debug_messages"].append("\\n=== STEP 2: SAVING INSTANCES ===")
        instances_data_by_type = {}

        for type_name in src_dict.keys():
            if type_name in tgt_dict:
                old_symbol = tgt_dict[type_name]
                all_instances = FilteredElementCollector(tgt_doc).OfClass(FamilyInstance).OfCategory(built_in_cat).WhereElementIsNotElementType().ToElements()
                instances_data_by_type[type_name] = []

                for instance in all_instances:
                    try:
                        if instance.Symbol.Id == old_symbol.Id:
                            data = save_instance_data(instance, tgt_doc)
                            instances_data_by_type[type_name].append(data)
                            stats["instances_saved"] += 1
                            if data.get('valid', False):
                                stats["instances_valid"] += 1
                    except:
                        pass

        # STEP 3: Deleting old types
        if progress_callback:
            progress_callback("Deleting old types...", 4, 6)
        
        stats["debug_messages"].append("\\n=== STEP 3: DELETING OLD TYPES ===")
        types_deleted = 0

        t_del = Transaction(tgt_doc, "Delete Old Types")
        t_del.Start()
        try:
            for type_name in src_dict.keys():
                if type_name in tgt_dict:
                    old_symbol = tgt_dict[type_name]
                    try:
                        deleted = tgt_doc.Delete(old_symbol.Id)
                        types_deleted += deleted.Count
                        stats["debug_messages"].append("Deleted: {} ({} items)".format(type_name, deleted.Count))
                    except Exception as ex:
                        stats["debug_messages"].append("Cannot delete {}: {}".format(type_name, str(ex)))

            t_del.Commit()
        except Exception as ex:
            t_del.RollBack()
            stats["debug_messages"].append("Delete failed: {}".format(str(ex)))

        stats["types_deleted"] = types_deleted

        # STEP 4: Copying new types
        if progress_callback:
            progress_callback("Copying new types...", 5, 6)
        
        stats["debug_messages"].append("\\n=== STEP 4: COPYING NEW TYPES ===")
        types_to_copy = List[ElementId]([s.Id for s in src_symbols])

        if types_to_copy.Count > 0:
            t2 = Transaction(tgt_doc, "Copy New Types")
            t2.Start()
            try:
                opts = CopyPasteOptions()
                opts.SetDuplicateTypeNamesHandler(OverwriteHandler())
                copied_ids = ElementTransformUtils.CopyElements(src_doc, types_to_copy, tgt_doc, None, opts)
                stats["types_copied"] = copied_ids.Count
                stats["debug_messages"].append("Copied: {} elements".format(copied_ids.Count))
                t2.Commit()
            except Exception as ex:
                t2.RollBack()
                stats["debug_messages"].append("Copy failed: {}".format(str(ex)))
                return stats

        if built_in_cat == BuiltInCategory.OST_Doors:
            final_tgt_symbols = get_door_types(tgt_doc)
        elif built_in_cat == BuiltInCategory.OST_Windows:
            final_tgt_symbols = get_window_types(tgt_doc)
        elif built_in_cat == BuiltInCategory.OST_Casework:
            final_tgt_symbols = get_casework_types(tgt_doc)
        elif built_in_cat == BuiltInCategory.OST_Furniture:
            final_tgt_symbols = get_furniture_types(tgt_doc)
        else:
            return stats

        final_tgt_dict = {get_name(e): e for e in final_tgt_symbols}

        stats["debug_messages"].append("\\n=== STEP 5: COPYING PARAMETERS ===")
        t3 = Transaction(tgt_doc, "Copy Parameters")
        t3.Start()
        try:
            for type_name in src_dict.keys():
                if type_name in final_tgt_dict:
                    params_copied = copy_type_parameters(src_dict[type_name], final_tgt_dict[type_name], src_doc, tgt_doc, stats["debug_messages"])
                    stats["parameters_copied"] += params_copied
            t3.Commit()
        except Exception as ex:
            t3.RollBack()
            stats["debug_messages"].append("Parameters failed: {}".format(str(ex)))

        # STEP 6: Recreating instances
        if progress_callback:
            progress_callback("Recreating instances...", 6, 6)
        
        stats["debug_messages"].append("\\n=== STEP 6: RECREATING INSTANCES ===")

        if instances_data_by_type:
            t4 = Transaction(tgt_doc, "Recreate Instances")
            t4.Start()
            try:
                for type_name, instances_list in instances_data_by_type.items():
                    if type_name in final_tgt_dict:
                        new_symbol = final_tgt_dict[type_name]

                        for instance_data in instances_list:
                            debug_list = []
                            new_instance = recreate_instance(instance_data, new_symbol, tgt_doc, debug_list)

                            if new_instance:
                                stats["instances_recreated"] += 1
                            else:
                                stats["instances_failed"] += 1

                            stats["debug_messages"].extend(debug_list)

                t4.Commit()
            except:
                t4.RollBack()

        stats["debug_messages"].append("\\n=== COMPLETE ===")
        stats["debug_messages"].append("Materials: {}".format(stats["materials_copied"]))
        stats["debug_messages"].append("Types: {}".format(types_deleted))
        stats["debug_messages"].append("Instances: {}".format(stats["instances_recreated"]))

    except Exception as ex:
        stats["debug_messages"].append("\\n=== ERROR ===")
        stats["debug_messages"].append(str(ex))

    return stats

class ProjectSelectorForm(Form):
    def __init__(self):
        self.Text = "Replace Loadable Families"
        self.Size = Size(550, 480)
        self.StartPosition = FormStartPosition.CenterScreen

        Label(Text="Source Project:", Location=Point(10, 20), Size=Size(130, 20), Parent=self)
        self.cmb_src = ComboBox(Location=Point(10, 40), Size=Size(520, 23), DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for n in doc_names: 
            self.cmb_src.Items.Add(n)

        Label(Text="Target Projects:", Location=Point(10, 80), Size=Size(130, 20), Parent=self)
        self.chk_tgt = CheckedListBox(Location=Point(10, 100), Size=Size(520, 300), ScrollAlwaysVisible=True, Parent=self)
        for n in doc_names: 
            self.chk_tgt.Items.Add(n)

        btn = Button(Text="Next", Location=Point(440, 410), Size=Size(90, 30), Parent=self)
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

        self.Text = "Replace Loadable Families"
        self.Size = Size(600, 690)
        self.StartPosition = FormStartPosition.CenterScreen

        Label(Text="Category:", Location=Point(10, 20), Size=Size(130, 20), Parent=self)
        self.cmb_cat = ComboBox(Location=Point(10, 40), Size=Size(570, 23), DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for c in sorted(CATEGORY_MAP.keys()): 
            self.cmb_cat.Items.Add(c)
        self.cmb_cat.SelectedIndexChanged += self.load

        Label(Text="Search:", Location=Point(10, 80), Size=Size(60, 20), Parent=self)
        self.txt_search = TextBox(Location=Point(75, 78), Size=Size(510, 23), Parent=self)
        self.txt_search.TextChanged += self.filter_items

        Label(Text="Items:", Location=Point(10, 115), Size=Size(200, 20), Parent=self)
        self.chk_items = CheckedListBox(Location=Point(10, 135), Size=Size(570, 400), ScrollAlwaysVisible=True, Parent=self)
        self.chk_items.ItemCheck += self.item_checked

        # Variável para controlar o filtro
        self.show_mode = "all"  # "all", "selected"

        # Botões na linha inferior
        Button(Text="All", Location=Point(10, 545), Size=Size(90, 25), Parent=self).Click += self.sel_all
        Button(Text="None", Location=Point(110, 545), Size=Size(90, 25), Parent=self).Click += self.sel_none
        Button(Text="Show Selected", Location=Point(210, 545), Size=Size(110, 25), Parent=self).Click += self.show_selected
        Button(Text="Show All", Location=Point(330, 545), Size=Size(110, 25), Parent=self).Click += self.show_all

        self.lbl_count = Label(Text="Selected: 0", Location=Point(450, 548), Size=Size(140, 20), Parent=self)

        # BOTÃO BACK
        btn_back = Button(Text="Back", Location=Point(390, 620), Size=Size(90, 30), Parent=self)
        btn_back.Click += self.go_back

        # BOTÃO TRANSFER
        btn_transfer = Button(Text="Transfer", Location=Point(490, 620), Size=Size(90, 30), Parent=self)
        btn_transfer.Click += self.transfer

    def go_back(self, s, e):
        """Volta para a tela de seleção de projetos"""
        self.Close()
        ProjectSelectorForm().ShowDialog()

    def show_selected(self, s, e):
        """Mostra apenas itens selecionados"""
        self.show_mode = "selected"
        self.filter_items(None, None)

    def show_all(self, s, e):
        """Mostra todos os itens"""
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

        key = self.cmb_cat.SelectedItem
        if not key: 
            return
        try:
            func, _ = CATEGORY_MAP[key]
            elems = func(self.src_doc)
            self.all_names = sorted(set(get_name(e) for e in elems if get_name(e) != "Unknown"))

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

            idx = self.chk_items.Items.Add(n)

            if n in self.selected_items:
                self.chk_items.SetItemChecked(idx, True)

        self.chk_items.ItemCheck += self.item_checked

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
                elem_name = get_name(elem)
                if elem_name in self.selected_items:
                    all_selected_symbols.append(elem)

        if not all_selected_symbols:
            MessageBox.Show("No elements found.", "Error")
            return

        # CRIAR JANELA DE PROGRESSO
        progress_form = ProgressForm(all_selected_symbols, self.src_doc, self.tgt_docs)
        progress_form.ShowDialog()

        self.Close()

class ProgressForm(Form):
    def __init__(self, symbols, src_doc, tgt_docs):
        self.symbols = symbols
        self.src_doc = src_doc
        self.tgt_docs = tgt_docs
        self.total_stats = {
            "instances_saved": 0,
            "instances_valid": 0,
            "types_deleted": 0,
            "types_copied": 0,
            "materials_copied": 0,
            "parameters_copied": 0,
            "instances_recreated": 0,
            "instances_failed": 0,
            "debug_messages": []
        }

        self.Text = "Transfer Progress"
        self.Size = Size(500, 200)
        self.StartPosition = FormStartPosition.CenterScreen
        self.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedDialog
        self.MaximizeBox = False
        self.MinimizeBox = False

        # Label de status - acima da barra
        self.lbl_status = Label(
            Text="Processing...",
            Location=Point(20, 30),
            Size=Size(460, 20),
            Parent=self,
            TextAlign=System.Drawing.ContentAlignment.MiddleCenter
        )

        # Barra de progresso
        self.progress_bar = ProgressBar(
            Location=Point(20, 60),
            Size=Size(460, 30),
            Minimum=0,
            Maximum=100,
            Parent=self
        )

        # Iniciar o processo quando o form é mostrado
        self.Shown += self.start_process

    def start_process(self, sender, e):
        """Inicia o processo de transferência"""
        Application.DoEvents()
        
        for doc_idx, tgt_doc in enumerate(self.tgt_docs):
            Application.DoEvents()

            tg = TransactionGroup(tgt_doc, "Replace Types")
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
                        self.total_stats[k].extend(stats[k])
                    else:
                        self.total_stats[k] += stats[k]
                
                tg.Assimilate()
            except Exception as ex:
                tg.RollBack()
                self.total_stats["debug_messages"].append("Transaction failed: {}".format(str(ex)))

        # Salvar log
        try:
            import os
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            debug_file = os.path.join(desktop, "revit_debug.txt")
            with open(debug_file, 'w') as f:
                f.write("\\n".join(self.total_stats["debug_messages"]))
        except:
            pass

        # Mostrar mensagem simples de conclusão
        MessageBox.Show("Transfer complete!", "Complete")
        
        self.Close()

    def update_progress(self, message, current, total):
        """Atualiza a barra de progresso"""
        if total > 0:
            percentage = int((float(current) / float(total)) * 100)
            self.progress_bar.Value = percentage
        
        Application.DoEvents()

if __name__ == "__main__":
    ProjectSelectorForm().ShowDialog()
