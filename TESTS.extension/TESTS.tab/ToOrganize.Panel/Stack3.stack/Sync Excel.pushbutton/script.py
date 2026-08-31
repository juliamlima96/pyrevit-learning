# -*- coding: UTF-8 -*-
__title__ = "Sync\nExcel"
__doc__ = "Synchronizes parameters between Excel and Revit elements."
__author__ = "pyRevit Script"

import clr
import os

_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_CONFIG_FILE = os.path.join(_SCRIPT_DIR, "last_path.txt")

def _ler_ultimo_caminho():
    """Le o ultimo caminho guardado em last_path.txt."""
    try:
        if os.path.isfile(_CONFIG_FILE):
            with open(_CONFIG_FILE, "r") as f:
                caminho = f.read().strip()
            if caminho and os.path.isfile(caminho):
                return caminho
    except:
        pass
    return None

def _guardar_ultimo_caminho(caminho):
    """Guarda o caminho em last_path.txt para a proxima sessao."""
    try:
        with open(_CONFIG_FILE, "w") as f:
            f.write(caminho)
    except:
        pass


clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')
clr.AddReference('System.Windows.Forms')
clr.AddReference('System.Xml')
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

import System
import System.IO as SIO
import System.IO.Packaging as SIP
import System.Xml as SX
import System.Text as ST
import System.Windows as SW
import System.Windows.Controls as SWC
import System.Windows.Media as SWM
import System.Windows.Data as SWD
import System.Windows.Forms as SWF
import System.Collections.ObjectModel as SCO
from System import Array, String, Object

from Autodesk.Revit.DB import (
    Transaction, StorageType, FilteredElementCollector,
    ElementIsElementTypeFilter, BuiltInCategory
)
from pyrevit import revit
doc   = revit.doc
uidoc = revit.uidoc

Window               = SW.Window
Thickness            = SW.Thickness
HorizontalAlignment  = SW.HorizontalAlignment
VerticalAlignment    = SW.VerticalAlignment
Visibility           = SW.Visibility
GridLength           = SW.GridLength
MessageBox           = SW.MessageBox
MessageBoxButton     = SW.MessageBoxButton
MessageBoxImage      = SW.MessageBoxImage
MessageBoxResult     = SW.MessageBoxResult
Grid                 = SWC.Grid
RowDefinition        = SWC.RowDefinition
ColumnDefinition     = SWC.ColumnDefinition
DataGrid             = SWC.DataGrid
DataGridTextColumn   = SWC.DataGridTextColumn
DataGridCheckBoxColumn = SWC.DataGridCheckBoxColumn
DataGridLength       = SWC.DataGridLength
Button               = SWC.Button
Label                = SWC.Label
TextBox              = SWC.TextBox
StackPanel           = SWC.StackPanel
Border               = SWC.Border
ScrollViewer         = SWC.ScrollViewer
ComboBox             = SWC.ComboBox
ComboBoxItem         = SWC.ComboBoxItem
DockPanel            = SWC.DockPanel
Orientation          = SWC.Orientation
ListBox              = SWC.ListBox
ListBoxItem          = SWC.ListBoxItem
CheckBox             = SWC.CheckBox
SolidColorBrush      = SWM.SolidColorBrush
Color                = SWM.Color
Binding              = SWD.Binding
OpenFileDialog       = SWF.OpenFileDialog
DialogResult         = SWF.DialogResult
ObservableCollection = SCO.ObservableCollection

# =============================================================================
#  CORES
# =============================================================================
def cor(h):
    h = h.lstrip('#')
    return Color.FromRgb(int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))
def pincel(h):
    return SolidColorBrush(cor(h))

C_BG      = "#FFFFFF"
C_SURFACE = "#F5F5F5"
C_BORDER  = "#D0D0D0"
C_ACCENT  = "#217346"
C_BLUE    = "#1565C0"
C_TEXT    = "#212121"
C_MUTED   = "#767676"
C_HDR     = "#217346"
C_WHITE   = "#FFFFFF"
C_GRID    = "#E0E0E0"

# =============================================================================
#  LEITOR / ESCRITOR XLSX
# =============================================================================
XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS  = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WB_REL  = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
STR_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"

def _read_part_xml(pkg, uri_str):
    uri  = SIP.PackUriHelper.CreatePartUri(System.Uri(uri_str, System.UriKind.Relative))
    if not pkg.PartExists(uri): return None
    part   = pkg.GetPart(uri)
    stream = part.GetStream()
    xdoc   = SX.XmlDocument()
    xdoc.Load(stream)
    stream.Close()
    return xdoc

def _get_shared_strings(pkg, wb_uri_str):
    wb_uri  = SIP.PackUriHelper.CreatePartUri(System.Uri(wb_uri_str, System.UriKind.Relative))
    wb_part = pkg.GetPart(wb_uri)
    ss_uri  = None
    for rel in wb_part.GetRelationships():
        if rel.RelationshipType == STR_REL:
            t = rel.TargetUri.ToString()
            if not t.startswith("/"): t = wb_uri_str.rsplit("/",1)[0] + "/" + t
            ss_uri = t; break
    if not ss_uri: return []
    xdoc = _read_part_xml(pkg, ss_uri)
    if not xdoc: return []
    nm = SX.XmlNamespaceManager(xdoc.NameTable)
    nm.AddNamespace("x", XLSX_NS)
    strings = []
    for node in xdoc.SelectNodes("//x:si", nm):
        val = ""
        for t in node.SelectNodes(".//x:t", nm): val += t.InnerText
        strings.append(val)
    return strings

def _col_index(col_str):
    r = 0
    for ch in col_str.upper(): r = r * 26 + (ord(ch) - ord('A') + 1)
    return r - 1

def _cell_ref_to_rc(ref):
    col_str = ""; row_str = ""
    for ch in ref:
        if ch.isalpha(): col_str += ch
        else:            row_str += ch
    return int(row_str) - 1, _col_index(col_str)

def _read_sheet(pkg, sheet_uri_str, shared_strings):
    xdoc = _read_part_xml(pkg, sheet_uri_str)
    if not xdoc: return []
    nm = SX.XmlNamespaceManager(xdoc.NameTable)
    nm.AddNamespace("x", XLSX_NS)
    row_nodes = xdoc.SelectNodes("//x:sheetData/x:row", nm)
    if not row_nodes: return []
    raw_rows = {}; max_col = 0
    for rn in row_nodes:
        r_attr  = rn.Attributes["r"]
        row_idx = int(r_attr.Value) - 1 if r_attr else len(raw_rows)
        cells   = {}
        for cn in rn.SelectNodes("x:c", nm):
            ref_a = cn.Attributes["r"]
            if not ref_a: continue
            ri, ci = _cell_ref_to_rc(ref_a.Value)
            if ci > max_col: max_col = ci
            t_a    = cn.Attributes["t"]
            v_node = cn.SelectSingleNode("x:v", nm)
            val    = ""
            if v_node and v_node.InnerText:
                raw = v_node.InnerText
                if t_a and t_a.Value == "s":
                    idx = int(raw); val = shared_strings[idx] if idx < len(shared_strings) else ""
                elif t_a and t_a.Value == "b":
                    val = "TRUE" if raw == "1" else "FALSE"
                else: val = raw
            cells[ci] = val
        raw_rows[row_idx] = cells
    if not raw_rows: return []
    num_cols = max_col + 1
    all_rows = []
    for ri in sorted(raw_rows.keys()):
        all_rows.append([raw_rows[ri].get(ci, "") for ci in range(num_cols)])
    return all_rows

def ler_excel(caminho, nome_sheet=None):
    pkg = SIP.Package.Open(caminho, SIO.FileMode.Open, SIO.FileAccess.Read)
    try:
        wb_uri_str = None
        for rel in pkg.GetRelationships():
            if rel.RelationshipType == WB_REL:
                t = rel.TargetUri.ToString()
                wb_uri_str = t if t.startswith("/") else "/" + t; break
        if not wb_uri_str: return [], [], []
        shared  = _get_shared_strings(pkg, wb_uri_str)
        wb_doc  = _read_part_xml(pkg, wb_uri_str)
        nm      = SX.XmlNamespaceManager(wb_doc.NameTable)
        nm.AddNamespace("x", XLSX_NS); nm.AddNamespace("r", REL_NS)
        sheets = []; sheet_rels = {}
        for sn in wb_doc.SelectNodes("//x:sheets/x:sheet", nm) or []:
            name = sn.Attributes["name"].Value
            rid  = sn.Attributes["r:id"].Value if sn.Attributes["r:id"] else None
            sheets.append(name)
            if rid: sheet_rels[name] = rid
        target = nome_sheet if (nome_sheet and nome_sheet in sheets) else (sheets[0] if sheets else None)
        if not target: return [], [], sheets
        rid     = sheet_rels.get(target)
        wb_uri  = SIP.PackUriHelper.CreatePartUri(System.Uri(wb_uri_str, System.UriKind.Relative))
        wb_part = pkg.GetPart(wb_uri)
        sheet_uri = None
        for rel in wb_part.GetRelationships():
            if rel.Id == rid:
                t = rel.TargetUri.ToString()
                if not t.startswith("/"): t = wb_uri_str.rsplit("/",1)[0] + "/" + t
                sheet_uri = t; break
        if not sheet_uri: return [], [], sheets
        dados = _read_sheet(pkg, sheet_uri, shared)
    finally:
        pkg.Close()
    if not dados: return [], [], sheets
    # Detetar linha de cabecalho = linha com mais celulas preenchidas
    # nas primeiras 20 linhas. Usada so para popular o combo de colunas.
    best_idx = 0
    best_count = 0
    for i, row in enumerate(dados[:20]):
        count = sum(1 for c in row if c and c.strip())
        if count > best_count:
            best_count = count
            best_idx = i
    cabecalhos = dados[best_idx]
    # _linhas = TODAS as linhas (para sync inteligente)
    return cabecalhos, dados, sheets

def guardar_xlsx(caminho, cabecalhos, linhas):
    mem = SIO.MemoryStream(SIO.File.ReadAllBytes(caminho))
    pkg = SIP.Package.Open(mem, SIO.FileMode.Open, SIO.FileAccess.ReadWrite)
    try:
        wb_uri_str = None
        for rel in pkg.GetRelationships():
            if rel.RelationshipType == WB_REL:
                t = rel.TargetUri.ToString()
                wb_uri_str = t if t.startswith("/") else "/" + t; break
        wb_doc = _read_part_xml(pkg, wb_uri_str)
        nm = SX.XmlNamespaceManager(wb_doc.NameTable)
        nm.AddNamespace("x", XLSX_NS); nm.AddNamespace("r", REL_NS)
        sheets = []; sheet_rels = {}
        for sn in wb_doc.SelectNodes("//x:sheets/x:sheet", nm) or []:
            name = sn.Attributes["name"].Value
            rid  = sn.Attributes["r:id"].Value if sn.Attributes["r:id"] else None
            sheets.append(name)
            if rid: sheet_rels[name] = rid
        rid     = sheet_rels.get(sheets[0]) if sheets else None
        wb_uri  = SIP.PackUriHelper.CreatePartUri(System.Uri(wb_uri_str, System.UriKind.Relative))
        wb_part = pkg.GetPart(wb_uri)
        sheet_uri = None
        for rel in wb_part.GetRelationships():
            if rel.Id == rid:
                t = rel.TargetUri.ToString()
                if not t.startswith("/"): t = wb_uri_str.rsplit("/",1)[0] + "/" + t
                sheet_uri = t; break
        def col_letter(n):
            s = ""; n += 1
            while n:
                n, r = divmod(n - 1, 26); s = chr(65 + r) + s
            return s
        todas    = [cabecalhos] + list(linhas)
        rows_xml = ""
        for ri, row in enumerate(todas):
            cells_xml = ""
            for ci, val in enumerate(row):
                ref   = "{}{}".format(col_letter(ci), ri + 1)
                v_str = "{}".format(val).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                cells_xml += '<c r="{}" t="inlineStr"><is><t>{}</t></is></c>'.format(ref, v_str)
            rows_xml += '<row r="{}">{}</row>'.format(ri + 1, cells_xml)
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>{}</sheetData></worksheet>'
        ).format(rows_xml)
        s_uri  = SIP.PackUriHelper.CreatePartUri(System.Uri(sheet_uri, System.UriKind.Relative))
        part   = pkg.GetPart(s_uri)
        stream = part.GetStream(SIO.FileMode.Create, SIO.FileAccess.Write)
        b      = ST.Encoding.UTF8.GetBytes(sheet_xml)
        stream.Write(b, 0, b.Length); stream.Close()
        pkg.Flush()
    finally:
        pkg.Close()
    mem.Seek(0, SIO.SeekOrigin.Begin)
    SIO.File.WriteAllBytes(caminho, mem.ToArray())
    mem.Close()

# =============================================================================
#  HELPERS REVIT
# =============================================================================
# Categorias suportadas
SUPPORTED_CATEGORIES = [
    (BuiltInCategory.OST_Walls,              "Walls"),
    (BuiltInCategory.OST_Floors,             "Floors"),
    (BuiltInCategory.OST_Ceilings,           "Ceilings"),
    (BuiltInCategory.OST_Doors,              "Doors"),
    (BuiltInCategory.OST_Windows,            "Windows"),
    (BuiltInCategory.OST_PlumbingFixtures,   "Plumbing Fixtures"),
    (BuiltInCategory.OST_Furniture,          "Furniture"),
    (BuiltInCategory.OST_LightingFixtures,   "Lighting Fixtures"),
    (BuiltInCategory.OST_Casework,           "Casework"),
    (BuiltInCategory.OST_Materials,          "Materials"),
    (BuiltInCategory.OST_Rooms,              "Rooms")
]
MAT_CAT = "Materials"

def get_all_syncable_elements():
    """Devolve instancias unicas por Type das categorias suportadas."""
    result = []
    seen_ids = set()
    for bic, cat_nome in SUPPORTED_CATEGORIES:
        try:
            if cat_nome == MAT_CAT:
                # Materiais sao directamente elementos (nao instancias com TypeId)
                mats = (FilteredElementCollector(doc)
                        .OfCategory(bic)
                        .WhereElementIsNotElementType()
                        .ToElements())
                for el in mats:
                    try:
                        eid = el.Id.IntegerValue
                        if eid not in seen_ids:
                            seen_ids.add(eid)
                            result.append((cat_nome, el))
                    except:
                        continue
            else:
                elems = (FilteredElementCollector(doc)
                         .OfCategory(bic)
                         .WhereElementIsNotElementType()
                         .ToElements())
                for el in elems:
                    try:
                        eid = el.Id.IntegerValue
                        if eid not in seen_ids:
                            seen_ids.add(eid)
                            result.append((cat_nome, el))
                    except:
                        continue
        except:
            continue
    return result

def get_elem_display_name(cat_nome, el):
    try:
        name = el.Name
        if name: return name
    except:
        pass
    return "ID:{}".format(el.Id.IntegerValue)

def get_elem_tipo_nome(cat_nome, el):
    if cat_nome == MAT_CAT:
        try:
            return el.Name or ""
        except:
            return ""
    try:
        tid = el.GetTypeId()
        if tid and tid.IntegerValue != -1:
            t = doc.GetElement(tid)
            if t: return t.Name or ""
    except:
        pass
    return ""

def get_elem_familia_nome(cat_nome, el):
    try:
        tid = el.GetTypeId()
        if tid and tid.IntegerValue != -1:
            t = doc.GetElement(tid)
            if t and hasattr(t, "Family") and t.Family:
                return t.Family.Name or ""
    except:
        pass
    return ""

def get_elem_cat_nome(cat_nome, el):
    return cat_nome

def get_element_type_obj(elem):
    try:
        tid = elem.GetTypeId()
        if tid and tid.IntegerValue != -1:
            return doc.GetElement(tid)
    except:
        pass
    return None

def get_all_params(elem):
    params = {}
    # Para Materials os parametros estao no proprio elemento, nao no Type
    try:
        cat = elem.Category
        if cat and cat.Id.IntegerValue == int(BuiltInCategory.OST_Materials):
            for p in elem.Parameters:
                if p.Definition:
                    params[p.Definition.Name] = p
            return params
    except:
        pass
    # Parametros de instancia
    for p in elem.GetOrderedParameters():
        if p.Definition:
            params[p.Definition.Name] = p
    # Parametros de tipo
    et = get_element_type_obj(elem)
    if et:
        for p in et.GetOrderedParameters():
            if p.Definition:
                params[p.Definition.Name] = p
    return params

def read_param(p):
    if p is None: return ""
    st = p.StorageType
    if st == StorageType.String:    return p.AsString() or ""
    if st == StorageType.Double:    return "{}".format(p.AsDouble())
    if st == StorageType.Integer:   return "{}".format(p.AsInteger())
    if st == StorageType.ElementId: return "{}".format(p.AsElementId().IntegerValue)
    return ""

def write_param(p, value):
    if p is None or p.IsReadOnly: return False
    try:
        st = p.StorageType
        if st == StorageType.String:    p.Set(value)
        elif st == StorageType.Double:  p.Set(float(value))
        elif st == StorageType.Integer: p.Set(int(float(value)))
        return True
    except:
        return False

# =============================================================================
#  MODELOS DE DADOS
# =============================================================================
class ParamItem(object):
    def __init__(self, nome, match, chave=False, checked=False):
        self.Nome    = nome
        self.Match   = match
        self.Chave   = chave
        self.Checked = checked

    @property
    def Estado(self):
        if self.Chave:  return "key"
        if self.Match:  return "match"
        return "no match"


class ElemItem(object):
    """
    Representa uma linha no grid de elementos.
    O estado Checked e PERSISTENTE - nao e recriado ao filtrar.
    """
    def __init__(self, tipo, elem):
        self.elem    = elem
        self.Checked = False
        self.Nome      = get_elem_display_name(tipo, elem)
        self.Categoria = get_elem_cat_nome(tipo, elem)
        self.Familia   = get_elem_familia_nome(tipo, elem)
        self.Tipo      = get_elem_tipo_nome(tipo, elem)
        self.ElemId    = str(elem.Id.IntegerValue)

# =============================================================================
#  JANELA PRINCIPAL
# =============================================================================
class SyncWindow(Window):

    def __init__(self):
        self.Title  = "Sync Excel <-> Revit"
        self.Width  = 1140
        self.Height = 720
        self.MinWidth  = 880
        self.MinHeight = 560
        self.Background = pincel(C_BG)
        self.WindowStartupLocation = SW.WindowStartupLocation.CenterScreen

        self._caminho      = None
        self._cabecalhos   = []
        self._linhas       = []
        self._sheets       = []
        self._param_items  = []
        # _master_items: lista COMPLETA de ElemItem, nunca recriada
        # o estado Checked vive aqui para ser persistente entre filtros
        self._master_items = []
        # _view_items: subconjunto visivel (aponta para os mesmos objetos)
        self._view_items   = []
        self._mostrar_sel  = False   # flag "Mostrar so selecionados"

        self._build_ui()
        self._carregar_elementos()
        self._auto_carregar_ultimo()

    # =========================================================================
    #  BUILD UI
    # =========================================================================
    def _build_ui(self):
        raiz = Grid()
        for h in [52, -1, 46, 26]:
            rd = RowDefinition()
            rd.Height = GridLength(1, SW.GridUnitType.Star) if h == -1 else GridLength(h)
            raiz.RowDefinitions.Add(rd)
        els = [self._topo(), self._corpo(), self._acoes(), self._rodape()]
        for i, el in enumerate(els):
            SWC.Grid.SetRow(el, i)
            raiz.Children.Add(el)
        self.Content = raiz

    def _topo(self):
        b = Border(); b.Background = pincel(C_HDR)
        p = StackPanel(); p.Orientation = Orientation.Horizontal
        p.Margin = Thickness(16, 0, 0, 0)
        p.VerticalAlignment = VerticalAlignment.Center
        t = Label(); t.Content = "Sync Excel <-> Revit"
        t.Foreground = pincel(C_WHITE); t.FontSize = 16
        t.FontWeight = SW.FontWeights.SemiBold
        t.VerticalAlignment = VerticalAlignment.Center
        s = Label(); s.Content = "  Select parameters and elements to synchronize"
        s.Foreground = SolidColorBrush(Color.FromArgb(180,255,255,255))
        s.FontSize = 11; s.VerticalAlignment = VerticalAlignment.Center
        p.Children.Add(t); p.Children.Add(s)
        b.Child = p; return b

    def _corpo(self):
        outer = Grid()
        cd0 = ColumnDefinition(); cd0.Width = GridLength(360)
        cd1 = ColumnDefinition(); cd1.Width = GridLength(1, SW.GridUnitType.Star)
        outer.ColumnDefinitions.Add(cd0)
        outer.ColumnDefinitions.Add(cd1)
        left  = self._painel_esq()
        right = self._painel_dir()
        SWC.Grid.SetColumn(left, 0)
        SWC.Grid.SetColumn(right, 1)
        outer.Children.Add(left)
        outer.Children.Add(right)
        return outer

    # -------------------------------------------------------------------------
    #  PAINEL ESQUERDO
    # -------------------------------------------------------------------------
    def _painel_esq(self):
        b = Border()
        b.BorderBrush = pincel(C_BORDER)
        b.BorderThickness = Thickness(0, 0, 1, 0)

        root = Grid()
        for h in [GridLength(44), GridLength(36), GridLength(36),
                  GridLength(36), GridLength(1, SW.GridUnitType.Star), GridLength(32)]:
            rd = RowDefinition(); rd.Height = h
            root.RowDefinitions.Add(rd)

        # Linha 0: ficheiro Excel
        file_b = Border()
        file_b.Background = pincel(C_SURFACE)
        file_b.BorderBrush = pincel(C_BORDER)
        file_b.BorderThickness = Thickness(0, 0, 0, 1)
        file_dock = DockPanel()
        file_dock.Margin = Thickness(8, 0, 8, 0)
        file_dock.VerticalAlignment = VerticalAlignment.Center
        btn_abrir = self._btn("...", C_ACCENT)
        btn_abrir.Width = 30; btn_abrir.Click += self._on_abrir
        SWC.DockPanel.SetDock(btn_abrir, SWC.Dock.Right)
        file_dock.Children.Add(btn_abrir)
        self.txt_path = TextBox()
        self.txt_path.IsReadOnly = True
        self.txt_path.Background = pincel(C_BG)
        self.txt_path.Foreground = pincel(C_MUTED)
        self.txt_path.BorderBrush = pincel(C_BORDER)
        self.txt_path.BorderThickness = Thickness(1)
        self.txt_path.Padding = Thickness(6, 3, 6, 3)
        self.txt_path.FontSize = 11
        self.txt_path.Text = "No file selected..."
        self.txt_path.VerticalAlignment = VerticalAlignment.Center
        file_dock.Children.Add(self.txt_path)
        file_b.Child = file_dock
        SWC.Grid.SetRow(file_b, 0); root.Children.Add(file_b)

        # Linha 1: sheet + chave
        sc_b = Border()
        sc_b.Background = pincel(C_SURFACE)
        sc_b.BorderBrush = pincel(C_BORDER)
        sc_b.BorderThickness = Thickness(0, 0, 0, 1)
        sc_dock = DockPanel()
        sc_dock.Margin = Thickness(8, 0, 8, 0)
        sc_dock.VerticalAlignment = VerticalAlignment.Center

        lbl_sh = Label(); lbl_sh.Content = "Sheet:"
        lbl_sh.Foreground = pincel(C_TEXT); lbl_sh.FontSize = 11
        lbl_sh.VerticalAlignment = VerticalAlignment.Center
        lbl_sh.Padding = Thickness(0, 0, 4, 0)
        SWC.DockPanel.SetDock(lbl_sh, SWC.Dock.Left)
        sc_dock.Children.Add(lbl_sh)

        self.combo_sheet = ComboBox()
        self.combo_sheet.Background = pincel(C_BG)
        self.combo_sheet.Foreground = pincel(C_TEXT)
        self.combo_sheet.BorderBrush = pincel(C_BORDER)
        self.combo_sheet.FontSize = 11
        self.combo_sheet.Width = 100
        self.combo_sheet.IsEnabled = False
        self.combo_sheet.VerticalAlignment = VerticalAlignment.Center
        self.combo_sheet.SelectionChanged += self._on_sheet_changed
        SWC.DockPanel.SetDock(self.combo_sheet, SWC.Dock.Left)
        sc_dock.Children.Add(self.combo_sheet)

        lbl_ch = Label(); lbl_ch.Content = "  Key:"
        lbl_ch.Foreground = pincel(C_TEXT); lbl_ch.FontSize = 11
        lbl_ch.VerticalAlignment = VerticalAlignment.Center
        lbl_ch.Padding = Thickness(0, 0, 4, 0)
        SWC.DockPanel.SetDock(lbl_ch, SWC.Dock.Left)
        sc_dock.Children.Add(lbl_ch)

        self.combo_chave = ComboBox()
        self.combo_chave.Background = pincel(C_BG)
        self.combo_chave.Foreground = pincel(C_TEXT)
        self.combo_chave.BorderBrush = pincel(C_BORDER)
        self.combo_chave.FontSize = 11
        self.combo_chave.IsEnabled = False
        self.combo_chave.VerticalAlignment = VerticalAlignment.Center
        self.combo_chave.SelectionChanged += self._on_config_changed
        sc_dock.Children.Add(self.combo_chave)

        sc_b.Child = sc_dock
        SWC.Grid.SetRow(sc_b, 1); root.Children.Add(sc_b)


        # Linha 1: combo categoria + combo tipo familia
        cat_b = Border()
        cat_b.Background = pincel(C_SURFACE)
        cat_b.BorderBrush = pincel(C_BORDER)
        cat_b.BorderThickness = Thickness(0, 0, 0, 1)
        cat_dock = DockPanel()
        cat_dock.Margin = Thickness(6, 0, 6, 0)
        cat_dock.VerticalAlignment = VerticalAlignment.Center

        lbl_cat = Label(); lbl_cat.Content = "Category:"
        lbl_cat.Foreground = pincel(C_TEXT); lbl_cat.FontSize = 11
        lbl_cat.VerticalAlignment = VerticalAlignment.Center
        lbl_cat.Padding = Thickness(0, 0, 4, 0)
        SWC.DockPanel.SetDock(lbl_cat, SWC.Dock.Left)
        cat_dock.Children.Add(lbl_cat)

        self.combo_cat = ComboBox()
        self.combo_cat.Background = pincel(C_BG)
        self.combo_cat.Foreground = pincel(C_TEXT)
        self.combo_cat.BorderBrush = pincel(C_BORDER)
        self.combo_cat.FontSize = 11
        self.combo_cat.VerticalAlignment = VerticalAlignment.Center
        self.combo_cat.SelectionChanged += self._on_filtro_changed
        cat_dock.Children.Add(self.combo_cat)
        cat_b.Child = cat_dock
        SWC.Grid.SetRow(cat_b, 2); root.Children.Add(cat_b)

        # Linha 2: filtro texto + botoes sel/desel/mostrar-sel
        filt_b = Border()
        filt_b.BorderBrush = pincel(C_BORDER)
        filt_b.BorderThickness = Thickness(0, 0, 0, 1)
        filt_dock = DockPanel()
        filt_dock.Margin = Thickness(4, 0, 4, 0)
        filt_dock.VerticalAlignment = VerticalAlignment.Center

        self.btn_mostrar_sel = self._btn("Sel.", "#1565C0")
        self.btn_mostrar_sel.FontSize = 10
        self.btn_mostrar_sel.Width = 36
        self.btn_mostrar_sel.Click += self._on_toggle_mostrar_sel
        SWC.DockPanel.SetDock(self.btn_mostrar_sel, SWC.Dock.Right)
        filt_dock.Children.Add(self.btn_mostrar_sel)

        btn_desel_e = self._btn("None", "#757575")
        btn_desel_e.FontSize = 10
        btn_desel_e.Click += self._on_desel_elems
        SWC.DockPanel.SetDock(btn_desel_e, SWC.Dock.Right)
        filt_dock.Children.Add(btn_desel_e)

        btn_sel_e = self._btn("All", C_ACCENT)
        btn_sel_e.FontSize = 10
        btn_sel_e.Click += self._on_sel_elems
        SWC.DockPanel.SetDock(btn_sel_e, SWC.Dock.Right)
        filt_dock.Children.Add(btn_sel_e)

        self.txt_filtro_elem = TextBox()
        self.txt_filtro_elem.Background = pincel(C_BG)
        self.txt_filtro_elem.Foreground = pincel(C_TEXT)
        self.txt_filtro_elem.BorderBrush = pincel(C_BORDER)
        self.txt_filtro_elem.BorderThickness = Thickness(1)
        self.txt_filtro_elem.Padding = Thickness(6, 2, 6, 2)
        self.txt_filtro_elem.FontSize = 11
        self.txt_filtro_elem.VerticalAlignment = VerticalAlignment.Center
        self.txt_filtro_elem.TextChanged += self._on_filtro_changed
        filt_dock.Children.Add(self.txt_filtro_elem)
        filt_b.Child = filt_dock
        SWC.Grid.SetRow(filt_b, 3); root.Children.Add(filt_b)

        # Linha 3: DataGrid elementos
        self.grid_elems = DataGrid()
        self.grid_elems.IsReadOnly = False
        self.grid_elems.AutoGenerateColumns = False
        self.grid_elems.Background = pincel(C_BG)
        self.grid_elems.Foreground = pincel(C_TEXT)
        self.grid_elems.BorderThickness = Thickness(0)
        self.grid_elems.GridLinesVisibility = SWC.DataGridGridLinesVisibility.Horizontal
        self.grid_elems.HorizontalGridLinesBrush = pincel(C_GRID)
        self.grid_elems.RowBackground = pincel(C_BG)
        self.grid_elems.AlternatingRowBackground = pincel(C_SURFACE)
        self.grid_elems.ColumnHeaderHeight = 26
        self.grid_elems.RowHeight = 22
        self.grid_elems.FontSize = 11
        self.grid_elems.CanUserResizeColumns = True
        self.grid_elems.CanUserSortColumns = True
        self.grid_elems.SelectionUnit = SWC.DataGridSelectionUnit.FullRow

        col_chk = DataGridCheckBoxColumn()
        col_chk.Header = ""
        col_chk.Binding = Binding("Checked")
        col_chk.Width = DataGridLength(30)
        self.grid_elems.Columns.Add(col_chk)

        col_nome = DataGridTextColumn()
        col_nome.Header = "Name / Family"
        col_nome.Binding = Binding("Nome")
        col_nome.IsReadOnly = True
        col_nome.Width = DataGridLength(1, SWC.DataGridLengthUnitType.Star)
        self.grid_elems.Columns.Add(col_nome)

        col_tipo = DataGridTextColumn()
        col_tipo.Header = "Revit Type"
        col_tipo.Binding = Binding("Tipo")
        col_tipo.IsReadOnly = True
        col_tipo.Width = DataGridLength(100)
        self.grid_elems.Columns.Add(col_tipo)

        SWC.Grid.SetRow(self.grid_elems, 4); root.Children.Add(self.grid_elems)

        # Linha 4: contador
        count_b = Border()
        count_b.Background = pincel(C_SURFACE)
        count_b.BorderBrush = pincel(C_BORDER)
        count_b.BorderThickness = Thickness(0, 1, 0, 0)
        self.lbl_count_elems = Label()
        self.lbl_count_elems.Content = "0 elements"
        self.lbl_count_elems.Foreground = pincel(C_MUTED)
        self.lbl_count_elems.FontSize = 11
        self.lbl_count_elems.Margin = Thickness(8, 0, 0, 0)
        self.lbl_count_elems.VerticalAlignment = VerticalAlignment.Center
        count_b.Child = self.lbl_count_elems
        SWC.Grid.SetRow(count_b, 5); root.Children.Add(count_b)

        b.Child = root; return b

    # -------------------------------------------------------------------------
    #  PAINEL DIREITO
    # -------------------------------------------------------------------------
    def _painel_dir(self):
        outer = Grid()
        for h in [36, 36, -1, 28, 110]:
            rd = RowDefinition()
            rd.Height = GridLength(1, SW.GridUnitType.Star) if h == -1 else GridLength(h)
            outer.RowDefinitions.Add(rd)

        # Cabecalho
        hdr = Border()
        hdr.Background = pincel(C_SURFACE)
        hdr.BorderBrush = pincel(C_BORDER)
        hdr.BorderThickness = Thickness(0, 0, 0, 1)
        lbl_hdr = Label(); lbl_hdr.Content = "Parameters to synchronize"
        lbl_hdr.FontSize = 13; lbl_hdr.FontWeight = SW.FontWeights.SemiBold
        lbl_hdr.Foreground = pincel(C_TEXT)
        lbl_hdr.Margin = Thickness(12, 0, 0, 0)
        lbl_hdr.VerticalAlignment = VerticalAlignment.Center
        hdr.Child = lbl_hdr
        SWC.Grid.SetRow(hdr, 0); outer.Children.Add(hdr)

        # Filtro parametros
        filt_bar = Border()
        filt_bar.Background = pincel(C_SURFACE)
        filt_bar.BorderBrush = pincel(C_BORDER)
        filt_bar.BorderThickness = Thickness(0, 0, 0, 1)
        filt_dock = DockPanel()
        filt_dock.Margin = Thickness(8, 0, 8, 0)
        filt_dock.VerticalAlignment = VerticalAlignment.Center

        btn_desel = self._btn("Limpar", "#757575")
        btn_desel.FontSize = 11; btn_desel.Click += self._on_desel_params
        SWC.DockPanel.SetDock(btn_desel, SWC.Dock.Right)
        filt_dock.Children.Add(btn_desel)

        btn_sel_all = self._btn("Select matched", C_ACCENT)
        btn_sel_all.FontSize = 11; btn_sel_all.Click += self._on_sel_params_match
        SWC.DockPanel.SetDock(btn_sel_all, SWC.Dock.Right)
        filt_dock.Children.Add(btn_sel_all)

        lbl_f = Label(); lbl_f.Content = "Filter:"
        lbl_f.Foreground = pincel(C_TEXT); lbl_f.FontSize = 11
        lbl_f.VerticalAlignment = VerticalAlignment.Center
        lbl_f.Margin = Thickness(0, 0, 4, 0)
        SWC.DockPanel.SetDock(lbl_f, SWC.Dock.Left)
        filt_dock.Children.Add(lbl_f)

        self.txt_filtro_param = TextBox()
        self.txt_filtro_param.Background = pincel(C_BG)
        self.txt_filtro_param.Foreground = pincel(C_TEXT)
        self.txt_filtro_param.BorderBrush = pincel(C_BORDER)
        self.txt_filtro_param.BorderThickness = Thickness(1)
        self.txt_filtro_param.Padding = Thickness(6, 2, 6, 2)
        self.txt_filtro_param.FontSize = 11
        self.txt_filtro_param.VerticalAlignment = VerticalAlignment.Center
        self.txt_filtro_param.TextChanged += self._on_filtro_param
        filt_dock.Children.Add(self.txt_filtro_param)

        filt_bar.Child = filt_dock
        SWC.Grid.SetRow(filt_bar, 1); outer.Children.Add(filt_bar)

        # DataGrid parametros
        self.grid_params = DataGrid()
        self.grid_params.IsReadOnly = False
        self.grid_params.AutoGenerateColumns = False
        self.grid_params.Background = pincel(C_BG)
        self.grid_params.Foreground = pincel(C_TEXT)
        self.grid_params.BorderThickness = Thickness(0)
        self.grid_params.GridLinesVisibility = SWC.DataGridGridLinesVisibility.Horizontal
        self.grid_params.HorizontalGridLinesBrush = pincel(C_GRID)
        self.grid_params.RowBackground = pincel(C_BG)
        self.grid_params.AlternatingRowBackground = pincel(C_SURFACE)
        self.grid_params.ColumnHeaderHeight = 28
        self.grid_params.RowHeight = 26
        self.grid_params.FontSize = 12
        self.grid_params.CanUserResizeColumns = True
        self.grid_params.CanUserSortColumns = False
        self.grid_params.SelectionUnit = SWC.DataGridSelectionUnit.FullRow

        col_chk2 = DataGridCheckBoxColumn()
        col_chk2.Header = ""
        col_chk2.Binding = Binding("Checked")
        col_chk2.Width = DataGridLength(40)
        self.grid_params.Columns.Add(col_chk2)

        col_pnome = DataGridTextColumn()
        col_pnome.Header = "Excel Column / Revit Parameter"
        col_pnome.Binding = Binding("Nome")
        col_pnome.IsReadOnly = True
        col_pnome.Width = DataGridLength(1, SWC.DataGridLengthUnitType.Star)
        self.grid_params.Columns.Add(col_pnome)

        # Coluna Match - circulo verde se der match
        col_est = SWC.DataGridTemplateColumn()
        col_est.Header = "Match"
        col_est.Width = DataGridLength(60)
        col_est.IsReadOnly = True
        xaml_template = """
<DataTemplate xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
              xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">
    <Ellipse Width="12" Height="12" HorizontalAlignment="Center" VerticalAlignment="Center">
        <Ellipse.Style>
            <Style TargetType="Ellipse">
                <Setter Property="Fill" Value="Transparent"/>
                <Setter Property="Stroke" Value="#555555"/>
                <Setter Property="StrokeThickness" Value="1.5"/>
                <Style.Triggers>
                    <DataTrigger Binding="{Binding Match}" Value="True">
                        <Setter Property="Fill" Value="#4CAF50"/>
                        <Setter Property="Stroke" Value="#388E3C"/>
                        <Setter Property="StrokeThickness" Value="0"/>
                    </DataTrigger>
                </Style.Triggers>
            </Style>
        </Ellipse.Style>
    </Ellipse>
</DataTemplate>"""
        import System.Xml as SX2
        import System.Windows.Markup as SWMk
        col_est.CellTemplate = SWMk.XamlReader.Parse(xaml_template)
        self.grid_params.Columns.Add(col_est)

        SWC.Grid.SetRow(self.grid_params, 2); outer.Children.Add(self.grid_params)

        # Contador parametros
        count_bar = Border()
        count_bar.Background = pincel(C_SURFACE)
        count_bar.BorderBrush = pincel(C_BORDER)
        count_bar.BorderThickness = Thickness(0, 1, 0, 0)
        self.lbl_count = Label()
        self.lbl_count.Content = "0 parameters selected"
        self.lbl_count.Foreground = pincel(C_MUTED)
        self.lbl_count.FontSize = 11
        self.lbl_count.Margin = Thickness(12, 0, 0, 0)
        self.lbl_count.VerticalAlignment = VerticalAlignment.Center
        count_bar.Child = self.lbl_count
        SWC.Grid.SetRow(count_bar, 3); outer.Children.Add(count_bar)

        # Log
        log_b = Border()
        log_b.BorderBrush = pincel(C_BORDER)
        log_b.BorderThickness = Thickness(0, 1, 0, 0)
        log_stack = StackPanel()
        lbl_log = Label(); lbl_log.Content = "Log"
        lbl_log.FontSize = 11; lbl_log.FontWeight = SW.FontWeights.SemiBold
        lbl_log.Foreground = pincel(C_TEXT)
        lbl_log.Margin = Thickness(12, 4, 0, 2); lbl_log.Padding = Thickness(0)
        log_stack.Children.Add(lbl_log)
        self.txt_log = TextBox()
        self.txt_log.IsReadOnly = True
        self.txt_log.Background = pincel(C_SURFACE)
        self.txt_log.Foreground = pincel(C_TEXT)
        self.txt_log.BorderBrush = pincel(C_BORDER)
        self.txt_log.BorderThickness = Thickness(0, 1, 0, 0)
        self.txt_log.FontSize = 10
        self.txt_log.FontFamily = SWM.FontFamily("Consolas")
        self.txt_log.VerticalScrollBarVisibility = SWC.ScrollBarVisibility.Auto
        self.txt_log.Height = 72
        self.txt_log.TextWrapping = SW.TextWrapping.Wrap
        self.txt_log.AcceptsReturn = True
        log_stack.Children.Add(self.txt_log)
        log_b.Child = log_stack
        SWC.Grid.SetRow(log_b, 4); outer.Children.Add(log_b)

        return outer

    def _acoes(self):
        b = Border()
        b.Background = pincel(C_SURFACE)
        b.BorderBrush = pincel(C_BORDER)
        b.BorderThickness = Thickness(0, 1, 0, 1)
        dock = DockPanel()
        dock.Margin = Thickness(12, 0, 12, 0)
        dock.VerticalAlignment = VerticalAlignment.Center

        self.btn_e2r = self._btn("Excel -> Revit", C_ACCENT)
        self.btn_e2r.FontWeight = SW.FontWeights.Bold
        self.btn_e2r.IsEnabled = False
        self.btn_e2r.Click += self._on_excel_to_revit
        SWC.DockPanel.SetDock(self.btn_e2r, SWC.Dock.Left)
        dock.Children.Add(self.btn_e2r)

        sep = Label(); sep.Content = "|"
        sep.Foreground = pincel(C_BORDER)
        sep.Margin = Thickness(8, 0, 8, 0)
        sep.VerticalAlignment = VerticalAlignment.Center
        SWC.DockPanel.SetDock(sep, SWC.Dock.Left)
        dock.Children.Add(sep)

        self.btn_r2e = self._btn("Revit -> Excel", C_BLUE)
        self.btn_r2e.FontWeight = SW.FontWeights.Bold
        self.btn_r2e.IsEnabled = False
        self.btn_r2e.Click += self._on_revit_to_excel
        SWC.DockPanel.SetDock(self.btn_r2e, SWC.Dock.Left)
        dock.Children.Add(self.btn_r2e)

        btn_close = self._btn("Close", "#757575")
        btn_close.Click += lambda s, e: self.Close()
        SWC.DockPanel.SetDock(btn_close, SWC.Dock.Right)
        dock.Children.Add(btn_close)

        btn_diag = self._btn("Diagnostico", "#795548")
        btn_diag.Click += self._on_diagnostico
        SWC.DockPanel.SetDock(btn_diag, SWC.Dock.Right)
        dock.Children.Add(btn_diag)

        b.Child = dock; return b

    def _rodape(self):
        b = Border(); b.Background = pincel(C_SURFACE)
        self.lbl_status = Label()
        self.lbl_status.Content = "Ready"
        self.lbl_status.Foreground = pincel(C_MUTED)
        self.lbl_status.FontSize = 11
        self.lbl_status.Margin = Thickness(12, 0, 0, 0)
        self.lbl_status.VerticalAlignment = VerticalAlignment.Center
        b.Child = self.lbl_status; return b

    # =========================================================================
    #  HELPERS UI
    # =========================================================================
    def _btn(self, t, c):
        b = Button(); b.Content = t
        b.Background = pincel(c); b.Foreground = pincel(C_WHITE)
        b.BorderThickness = Thickness(0)
        b.Padding = Thickness(10, 5, 10, 5)
        b.FontSize = 12; b.Margin = Thickness(0, 0, 4, 0)
        b.VerticalAlignment = VerticalAlignment.Center
        return b

    def _log(self, msg):
        self.txt_log.Text = (self.txt_log.Text + "\n" + msg).strip()
        self.txt_log.ScrollToEnd()

    def _status(self, msg):
        self.lbl_status.Content = msg

    def _get_cat_filtro(self):
        idx = self.combo_cat.SelectedIndex
        if idx > 0:
            return self.combo_cat.Items[idx].Content
        return None

    # =========================================================================
    #  LOGICA - ELEMENTOS
    # =========================================================================
    def _carregar_elementos(self):
        """Carrega TODOS os elementos uma vez e cria _master_items."""
        self._status("Loading elements...")
        try:
            pairs = get_all_syncable_elements()
        except Exception as ex:
            pairs = []
            self._log("Error loading: " + str(ex))

        self._master_items = []
        for tipo, el in pairs:
            try:
                self._master_items.append(ElemItem(tipo, el))
            except:
                pass

        # popular combo categorias com as categorias fixas suportadas
        self.combo_cat.Items.Clear()
        ci_all = ComboBoxItem(); ci_all.Content = "(All)"
        self.combo_cat.Items.Add(ci_all)
        for _, cat_nome in SUPPORTED_CATEGORIES:
            ci = ComboBoxItem(); ci.Content = cat_nome
            self.combo_cat.Items.Add(ci)
        self.combo_cat.SelectedIndex = 0

        self._status("Ready")
        self._atualizar_view()

    def _atualizar_view(self):
        """
        Reconstroi _view_items a partir de _master_items aplicando filtros,
        MAS NAO recria os ElemItem - reutiliza os existentes para preservar Checked.
        """
        f_texto  = self.txt_filtro_elem.Text.strip().lower() if self.txt_filtro_elem.Text else ""
        f_cat    = self._get_cat_filtro()

        self._view_items = []
        for ei in self._master_items:
            # filtro categoria
            if f_cat and ei.Categoria != f_cat: continue
            # filtro "mostrar so selecionados"
            if self._mostrar_sel and not ei.Checked: continue
            # filtro texto
            if f_texto:
                txt = (ei.Nome + ei.Tipo + ei.Familia + ei.Categoria + ei.ElemId).lower()
                if f_texto not in txt: continue
            self._view_items.append(ei)

        col = ObservableCollection[Object]()
        for ei in self._view_items:
            col.Add(ei)
        self.grid_elems.ItemsSource = col

        sel_total = sum(1 for ei in self._master_items if ei.Checked)
        self.lbl_count_elems.Content = "{} visible | {} selected (total)".format(
            len(self._view_items), sel_total)

        self._atualizar_grid_params()
        self._check_botoes()

    def _get_elems_selecionados(self):
        """Devolve elementos com Checked=True de _master_items (todos, nao so os visiveis)."""
        return [ei.elem for ei in self._master_items if ei.Checked]

    # =========================================================================
    #  LOGICA - PARAMETROS
    # =========================================================================
    def _get_params_revit(self):
        """Recolhe parametros dos elementos SELECIONADOS (de _master_items)."""
        params = set()
        for ei in self._master_items:
            if not ei.Checked: continue
            try:
                for name in get_all_params(ei.elem).keys():
                    params.add(name)
            except:
                pass
        return params

    def _get_chave_col(self):
        idx = self.combo_chave.SelectedIndex
        if 0 <= idx < len(self._cabecalhos):
            return self._cabecalhos[idx]
        return None

    def _atualizar_grid_params(self):
        if not self._cabecalhos:
            self.grid_params.ItemsSource = None
            self._param_items = []
            self._atualizar_count_params(); return

        params_revit = self._get_params_revit()
        # Normalizar nomes Revit (sem espacos) para match robusto
        params_revit_norm = {"".join(n.split()): n for n in params_revit}
        chave        = self._get_chave_col()
        prev         = {p.Nome: p.Checked for p in self._param_items}

        self._param_items = []
        for cab in self._cabecalhos:
            if not cab: continue
            e_chave  = (cab == chave)
            cab_norm = "".join(cab.split())
            match    = cab_norm in params_revit_norm
            checked  = prev.get(cab, False)
            self._param_items.append(ParamItem(cab, match, chave=e_chave, checked=checked))

        self._popular_grid_params("")
        self._atualizar_count_params()

    def _popular_grid_params(self, filtro):
        items = ObservableCollection[Object]()
        f = filtro.lower() if filtro else ""
        for p in self._param_items:
            if f and f not in p.Nome.lower(): continue
            items.Add(p)
        self.grid_params.ItemsSource = items

    def _atualizar_count_params(self):
        sel         = sum(1 for p in self._param_items if p.Checked and not p.Chave)
        total_match = sum(1 for p in self._param_items if p.Match and not p.Chave)
        self.lbl_count.Content = "{} selected of {} with match".format(sel, total_match)
        self._check_botoes()

    def _get_mapeamento_selecionado(self):
        mapa = []
        for p in self._param_items:
            if p.Chave or not p.Checked or not p.Match: continue
            if p.Nome in self._cabecalhos:
                mapa.append((self._cabecalhos.index(p.Nome), p.Nome))
        return mapa

    def _check_botoes(self):
        ok = (bool(self._caminho) and
              bool(self._get_chave_col()) and
              bool(self._get_elems_selecionados()) and
              any(p.Checked and p.Match and not p.Chave for p in self._param_items))
        self.btn_e2r.IsEnabled = ok
        self.btn_r2e.IsEnabled = ok

    # =========================================================================
    #  EVENTOS - ELEMENTOS
    # =========================================================================
    def _on_filtro_changed(self, sender, e):
        self._atualizar_view()

    def _on_toggle_mostrar_sel(self, sender, e):
        self._mostrar_sel = not self._mostrar_sel
        if self._mostrar_sel:
            self.btn_mostrar_sel.Background = pincel(C_ACCENT)
            self.btn_mostrar_sel.Content = "Sel."
        else:
            self.btn_mostrar_sel.Background = pincel(C_BLUE)
            self.btn_mostrar_sel.Content = "Sel."
        self._atualizar_view()

    def _on_sel_elems(self, sender, e):
        # Marca como checked todos os items visiveis atualmente
        for ei in self._view_items:
            ei.Checked = True
        self._atualizar_view()

    def _on_desel_elems(self, sender, e):
        # Desmarca todos os items visiveis atualmente
        for ei in self._view_items:
            ei.Checked = False
        self._atualizar_view()

    # =========================================================================
    #  EVENTOS - FICHEIRO / PARAMETROS
    # =========================================================================
    def _auto_carregar_ultimo(self):
        """Carrega automaticamente o ultimo ficheiro Excel ao abrir o plugin."""
        caminho = _ler_ultimo_caminho()
        if not caminho:
            return
        try:
            cabs, linhas, sheets = ler_excel(caminho)
            self._caminho = caminho
            self.txt_path.Text = os.path.basename(caminho)
            self.txt_path.Foreground = pincel(C_TEXT)
            self._cabecalhos = cabs; self._linhas = linhas; self._sheets = sheets
            self.combo_sheet.Items.Clear()
            for s in sheets:
                item = ComboBoxItem(); item.Content = s
                self.combo_sheet.Items.Add(item)
            self.combo_sheet.SelectedIndex = 0
            self.combo_sheet.IsEnabled = True
            self._popular_combo_chave()
            self._atualizar_grid_params()
            self._log("Auto-loaded: {}".format(os.path.basename(caminho)))
        except:
            pass

    def _on_abrir(self, sender, e):
        dlg = OpenFileDialog()
        dlg.Title = "Select Excel file"
        dlg.Filter = "Excel (*.xlsx)|*.xlsx"
        if dlg.ShowDialog() != DialogResult.OK: return
        self._caminho = dlg.FileName
        _guardar_ultimo_caminho(self._caminho)
        self.txt_path.Text = os.path.basename(self._caminho)
        self.txt_path.Foreground = pincel(C_TEXT)
        try:
            cabs, linhas, sheets = ler_excel(self._caminho)
            self._cabecalhos = cabs; self._linhas = linhas; self._sheets = sheets
            self.combo_sheet.Items.Clear()
            for s in sheets:
                item = ComboBoxItem(); item.Content = s
                self.combo_sheet.Items.Add(item)
            self.combo_sheet.SelectedIndex = 0
            self.combo_sheet.IsEnabled = True
            self._popular_combo_chave()
            self._atualizar_grid_params()
            self._log("Loaded: {} | {} rows | {} columns".format(
                os.path.basename(self._caminho), len(linhas), len(cabs)))
        except Exception as ex:
            MessageBox.Show("Error reading Excel:\n" + str(ex), "Error",
                            MessageBoxButton.OK, MessageBoxImage.Error)

    def _on_sheet_changed(self, sender, e):
        if not self._caminho: return
        idx = self.combo_sheet.SelectedIndex
        if idx < 0 or idx >= len(self._sheets): return
        try:
            cabs, linhas, _ = ler_excel(self._caminho, self._sheets[idx])
            self._cabecalhos = cabs; self._linhas = linhas
            self._popular_combo_chave()
            self._atualizar_grid_params()
        except Exception as ex:
            self._log("Error changing sheet: " + str(ex))

    def _popular_combo_chave(self):
        self.combo_chave.Items.Clear()
        for cab in self._cabecalhos:
            item = ComboBoxItem()
            item.Content = cab if cab else "(empty)"
            self.combo_chave.Items.Add(item)
        self.combo_chave.IsEnabled = True
        for pref in ["Type Mark", "CODE", "Code", "Mark", "ID", "Name"]:
            for i, cab in enumerate(self._cabecalhos):
                if cab == pref:
                    self.combo_chave.SelectedIndex = i; return
        if self._cabecalhos: self.combo_chave.SelectedIndex = 0

    def _on_config_changed(self, sender, e):
        self._atualizar_grid_params()

    def _on_filtro_param(self, sender, e):
        self._popular_grid_params(self.txt_filtro_param.Text.strip())

    def _on_sel_params_match(self, sender, e):
        for p in self._param_items:
            if not p.Chave and p.Match: p.Checked = True
        self._popular_grid_params(self.txt_filtro_param.Text.strip())
        self._atualizar_count_params()

    def _on_desel_params(self, sender, e):
        for p in self._param_items:
            if not p.Chave: p.Checked = False
        self._popular_grid_params(self.txt_filtro_param.Text.strip())
        self._atualizar_count_params()

    # =========================================================================
    #  SINCRONIZACAO
    # =========================================================================
    def _on_diagnostico(self, sender, e):
        from pyrevit import forms
        msg = []
        if not self._cabecalhos:
            MessageBox.Show("Selecciona primeiro um ficheiro Excel.", "Diagnostico",
                            MessageBoxButton.OK, MessageBoxImage.Warning)
            return
        msg.append("Excel: {}".format(os.path.basename(self._caminho) if self._caminho else "?"))
        msg.append("Cabecalhos lidos ({} total):".format(len(self._cabecalhos)))
        for c in self._cabecalhos:
            msg.append("  [{}]".format(c))
        msg.append("")

        # Parametros Revit dos elementos seleccionados
        params_revit = self._get_params_revit()
        msg.append("Parametros Revit encontrados: {}".format(len(params_revit)))
        msg.append("")
        msg.append("--- Match Excel vs Revit ---")
        for c in self._cabecalhos:
            if not c: continue
            status = "OK" if c in params_revit else "SEM MATCH"
            msg.append("  [{}] {}".format(status, c))

        MessageBox.Show("\n".join(msg), "Diagnostico Excel vs Revit",
                        MessageBoxButton.OK, MessageBoxImage.Information)

    def _on_excel_to_revit(self, sender, e):
        chave     = self._get_chave_col()
        mapa      = self._get_mapeamento_selecionado()
        elems     = self._get_elems_selecionados()
        chave_idx = self._cabecalhos.index(chave)

        # Construir set de codigos Revit validos para filtrar o Excel
        revit_keys = set()
        for el in elems:
            p_el = get_all_params(el).get(chave)
            if p_el:
                v = read_param(p_el).strip()
                if v: revit_keys.add(v)
        # Varrer TODAS as linhas do Excel
        # So usa linhas cujo valor na coluna chave existe no Revit
        # Assim titulos, cabecalhos e linhas vazias sao ignorados automaticamente
        excel_dict = {}
        for linha in self._linhas:
            if chave_idx >= len(linha): continue
            key = linha[chave_idx].strip()
            if not key or key not in revit_keys: continue
            row = {}
            for col_idx, col_name in mapa:
                row[col_name] = linha[col_idx] if col_idx < len(linha) else ""
            excel_dict[key] = row

        ok = 0; skip = 0; erros = 0
        t = Transaction(doc, "Sync Excel -> Revit")
        t.Start()
        try:
            for el in elems:
                params      = get_all_params(el)
                # Mapa normalizado: sem espacos -> parametro real
                params_norm = {"".join(k.split()): v for k, v in params.items()}
                p_chave     = params.get(chave) or params_norm.get("".join(chave.split()))
                if not p_chave: skip += 1; continue
                chave_val = read_param(p_chave).strip()
                if chave_val not in excel_dict:
                    skip += 1; continue
                row = excel_dict[chave_val]
                for col_name, valor in row.items():
                    col_norm = "".join(col_name.split())
                    p = params.get(col_name) or params_norm.get(col_norm)
                    if write_param(p, valor): ok += 1
                    else:
                        erros += 1
                        self._log("ERROR: [{}] {} -> read-only".format(chave_val, col_name))
            t.Commit()
        except Exception as ex:
            t.RollbackIfNotCommitted()
            MessageBox.Show("Error:\n" + str(ex), "Error", MessageBoxButton.OK, MessageBoxImage.Error)
            return

        self._log("--- Excel->Revit: {} OK | {} skipped | {} errors ---".format(ok, skip, erros))
        self._status("Excel->Revit: {} parameters updated".format(ok))

    def _on_revit_to_excel(self, sender, e):
        chave     = self._get_chave_col()
        mapa      = self._get_mapeamento_selecionado()
        elems     = self._get_elems_selecionados()
        chave_idx = self._cabecalhos.index(chave)

        revit_dict = {}
        for el in elems:
            params    = get_all_params(el)
            p_chave   = params.get(chave)
            if not p_chave: continue
            chave_val = read_param(p_chave).strip()
            if not chave_val: continue
            row = {}
            for col_idx, col_name in mapa:
                p = params.get(col_name)
                row[col_name] = read_param(p) if p else ""
            revit_dict[chave_val] = row

        # Varrer TODAS as linhas, modificar so as com codigo Revit valido
        # Titulos, cabecalhos e linhas vazias ficam intactos
        novas = []; ok = 0
        for linha in self._linhas:
            nova = list(linha)
            key  = nova[chave_idx].strip() if chave_idx < len(nova) else ""
            if key and key in revit_dict:
                for col_idx, col_name in mapa:
                    while len(nova) <= col_idx: nova.append("")
                    nova[col_idx] = revit_dict[key].get(col_name, "")
                    ok += 1
            novas.append(nova)

        try:
            guardar_xlsx(self._caminho, self._cabecalhos, novas)
            self._linhas = novas
            self._log("--- Revit->Excel: {} values exported ---".format(ok))
            self._status("Revit->Excel: {} values written to Excel".format(ok))
        except Exception as ex:
            MessageBox.Show("Error saving:\n" + str(ex), "Error",
                            MessageBoxButton.OK, MessageBoxImage.Error)


# =============================================================================
janela = SyncWindow()
janela.ShowDialog()