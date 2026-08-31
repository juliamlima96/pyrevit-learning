# -*- coding: utf-8 -*-
"""
Adjust Wall Heights to Ceiling
- Unconnected Walls: adjusts WALL_USER_HEIGHT_PARAM
- Connected to Level Walls: adjusts WALL_TOP_OFFSET
- Finds the ceiling above each wall
- Adjusts wall top to match ceiling top
"""

import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, BuiltInParameter,
    Transaction, Element
)
from System.Windows.Forms import (
    Form, Label, Button, ListView, ListViewItem,
    FormStartPosition, MessageBox, MessageBoxButtons,
    MessageBoxIcon, CheckBox, FormBorderStyle, ColumnHeader, View,
    TextBox, RadioButton, GroupBox
)
from System.Drawing import Point, Size, Font, FontStyle, Color

uidoc = __revit__.ActiveUIDocument
doc   = __revit__.ActiveUIDocument.Document

# -------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------
def get_wall_midpoint(wall):
    loc = wall.Location
    if not loc:
        return None
    try:
        curve    = loc.Curve
        midparam = (curve.GetEndParameter(0) + curve.GetEndParameter(1)) / 2.0
        return curve.Evaluate(midparam, False)
    except:
        return None

def encontrar_ceiling_da_parede(wall, ceilings):
    mid = get_wall_midpoint(wall)
    if not mid:
        return None, 0

    wall_level = doc.GetElement(wall.LevelId)
    if not wall_level:
        return None, 0

    wall_level_elev = wall_level.Elevation
    base_offset     = wall.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET)
    wall_base_elev  = wall_level_elev + (base_offset.AsDouble() if base_offset else 0)

    best_ceiling = None
    best_topo    = 0

    for ceiling in ceilings:
        ceiling_level = doc.GetElement(ceiling.LevelId)
        if not ceiling_level:
            continue

        if abs(ceiling_level.Elevation - wall_level_elev) > 30:
            continue

        bb = ceiling.get_BoundingBox(None)
        if not bb:
            continue

        if (mid.X >= bb.Min.X and mid.X <= bb.Max.X and
                mid.Y >= bb.Min.Y and mid.Y <= bb.Max.Y):

            param_height  = ceiling.get_Parameter(BuiltInParameter.CEILING_HEIGHTABOVELEVEL_PARAM)
            height_offset = param_height.AsDouble() if param_height else 0
            ceiling_topo  = ceiling_level.Elevation + height_offset

            if ceiling_topo > wall_base_elev:
                if best_ceiling is None or ceiling_topo < best_topo:
                    best_ceiling = ceiling
                    best_topo    = ceiling_topo

    return best_ceiling, best_topo

# -------------------------------------------------------------
# ANALISE
# -------------------------------------------------------------
def analisar_paredes():
    walls = list(
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Walls)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    ceilings = list(
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Ceilings)
        .WhereElementIsNotElementType()
        .ToElements()
    )

    resultado = []

    for wall in walls:
        try:
            wall_level = doc.GetElement(wall.LevelId)
            if not wall_level:
                continue

            wall_level_elev = wall_level.Elevation

            param_base_offset = wall.get_Parameter(BuiltInParameter.WALL_BASE_OFFSET)
            base_offset       = param_base_offset.AsDouble() if param_base_offset else 0

            param_top_constraint = wall.get_Parameter(BuiltInParameter.WALL_HEIGHT_TYPE)
            if not param_top_constraint:
                continue

            top_constraint_id = param_top_constraint.AsElementId()

            try:
                is_unconnected = (top_constraint_id.Value == -1)
            except:
                is_unconnected = (str(top_constraint_id) == "-1")

            if is_unconnected:
                param_altura = wall.get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM)
                altura_atual = param_altura.AsDouble() if param_altura else 0
                topo_atual   = wall_level_elev + base_offset + altura_atual
                constraint   = "Unconnected"
                top_level_elev = 0
            else:
                top_level = doc.GetElement(top_constraint_id)
                if not top_level:
                    continue
                top_level_elev   = top_level.Elevation
                param_top_offset = wall.get_Parameter(BuiltInParameter.WALL_TOP_OFFSET)
                top_offset       = param_top_offset.AsDouble() if param_top_offset else 0
                topo_atual       = top_level_elev + top_offset
                altura_atual     = topo_atual - wall_level_elev - base_offset
                constraint       = "Connected: {}".format(top_level.Name)

            ceiling, ceiling_topo = encontrar_ceiling_da_parede(wall, ceilings)

            if ceiling:
                nova_altura    = ceiling_topo - wall_level_elev - base_offset
                diferenca      = abs((ceiling_topo - topo_atual) * 304.8)
                precisa_ajuste = diferenca > 1
            else:
                nova_altura    = altura_atual
                diferenca      = 0
                precisa_ajuste = False

            try:
                wall_type = doc.GetElement(wall.GetTypeId())
                tipo_nome = Element.Name.GetValue(wall_type) if wall_type else "N/A"
            except:
                tipo_nome = "N/A"

            resultado.append({
                "wall":            wall,
                "tipo":            tipo_nome,
                "nivel":           wall_level.Name,
                "constraint":      constraint,
                "is_unconnected":  is_unconnected,
                "top_level_elev":  top_level_elev,
                "base_offset":     base_offset,
                "wall_level_elev": wall_level_elev,
                "altura_atual":    altura_atual,
                "nova_altura":     nova_altura,
                "topo_atual":      topo_atual,
                "ceiling_topo":    ceiling_topo,
                "ceiling":         ceiling,
                "precisa_ajuste":  precisa_ajuste,
            })

        except Exception as ex:
            continue

    return resultado

# -------------------------------------------------------------
# APLICAR
# -------------------------------------------------------------
def aplicar_ajustes(items_selecionados):
    ajustados = 0
    falhas    = 0

    with Transaction(doc, "Adjust Wall Heights") as tx:
        tx.Start()
        for item in items_selecionados:
            try:
                if item["is_unconnected"]:
                    param = item["wall"].get_Parameter(BuiltInParameter.WALL_USER_HEIGHT_PARAM)
                    if param and not param.IsReadOnly:
                        param.Set(item["nova_altura"])
                        ajustados += 1
                    else:
                        falhas += 1
                else:
                    novo_offset = item["ceiling_topo"] - item["top_level_elev"]
                    param = item["wall"].get_Parameter(BuiltInParameter.WALL_TOP_OFFSET)
                    if param and not param.IsReadOnly:
                        param.Set(novo_offset)
                        ajustados += 1
                    else:
                        falhas += 1
            except:
                falhas += 1

        tx.Commit()

    return ajustados, falhas

# -------------------------------------------------------------
# INTERFACE
# -------------------------------------------------------------
class AjustarParedesForm(Form):
    def __init__(self):
        self.Text            = "Adjust Wall Heights to Ceiling"
        self.Size            = Size(1060, 650)
        self.StartPosition   = FormStartPosition.CenterScreen
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox     = False
        self.dados           = []
        self._build_ui()
        self._carregar_dados()

    def _build_ui(self):
        # Checkbox
        self.chk_apenas_problemas = CheckBox(
            Text="Show only walls that need adjustment",
            Location=Point(15, 15), Size=Size(350, 20),
            Font=Font("Segoe UI", 9), Checked=True, Parent=self)
        self.chk_apenas_problemas.CheckedChanged += self._on_filtro

        # GroupBox filtro por tipo
        grp = GroupBox(
            Text="Filter by Wall Type",
            Location=Point(15, 42), Size=Size(1020, 55),
            Font=Font("Segoe UI", 9), Parent=self)

        self.rb_none = RadioButton(
            Text="No filter", Location=Point(10, 22),
            Size=Size(80, 20), Checked=True,
            Font=Font("Segoe UI", 9), Parent=grp)
        self.rb_none.CheckedChanged += self._on_filtro

        self.rb_contains = RadioButton(
            Text="Contains:", Location=Point(100, 22),
            Size=Size(80, 20),
            Font=Font("Segoe UI", 9), Parent=grp)
        self.rb_contains.CheckedChanged += self._on_filtro

        self.txt_contains = TextBox(
            Location=Point(185, 20), Size=Size(200, 22),
            Font=Font("Segoe UI", 9), Parent=grp)
        self.txt_contains.TextChanged += self._on_filtro

        self.rb_not_contains = RadioButton(
            Text="Does Not Contain:", Location=Point(405, 22),
            Size=Size(145, 20),
            Font=Font("Segoe UI", 9), Parent=grp)
        self.rb_not_contains.CheckedChanged += self._on_filtro

        self.txt_not_contains = TextBox(
            Location=Point(555, 20), Size=Size(200, 22),
            Font=Font("Segoe UI", 9), Parent=grp)
        self.txt_not_contains.TextChanged += self._on_filtro

        # ListView
        self.lv = ListView(
            Location=Point(15, 108), Size=Size(1020, 400),
            View=View.Details, FullRowSelect=True,
            GridLines=True, CheckBoxes=True,
            Font=Font("Segoe UI", 9), Parent=self)

        for col_text, col_width in [
            ("Wall Type", 220), ("Level", 80), ("Constraint", 130),
            ("Current Height mm", 130), ("New Height mm", 120),
            ("Current Top mm", 110), ("Ceiling Top mm", 120)]:
            col       = ColumnHeader()
            col.Text  = col_text
            col.Width = col_width
            self.lv.Columns.Add(col)

        self.lv.ItemChecked += self._on_item_checked

        # Legenda
        Label(
            Text="Red = needs adjustment",
            Location=Point(15, 515), Size=Size(300, 18),
            Font=Font("Segoe UI", 8), Parent=self)

        # Botoes
        Button(
            Text="Select All", Location=Point(15, 538),
            Size=Size(100, 28), Font=Font("Segoe UI", 9),
            Parent=self).Click += self._sel_todos

        Button(
            Text="Deselect All", Location=Point(125, 538),
            Size=Size(100, 28), Font=Font("Segoe UI", 9),
            Parent=self).Click += self._sel_nenhum

        self.lbl_status = Label(
            Text="", Location=Point(235, 543),
            Size=Size(500, 20), Font=Font("Segoe UI", 9),
            Parent=self)

        btn_aplicar = Button(
            Text="Apply Adjustments", Location=Point(900, 538),
            Size=Size(135, 28),
            Font=Font("Segoe UI", 10, FontStyle.Bold),
            Parent=self)
        btn_aplicar.BackColor = Color.FromArgb(0, 120, 215)
        btn_aplicar.ForeColor = Color.White
        btn_aplicar.Click    += self._on_aplicar

    def _carregar_dados(self):
        self.dados = analisar_paredes()
        self._refresh_lista()

    def _refresh_lista(self):
        self.lv.Items.Clear()
        apenas_problemas  = self.chk_apenas_problemas.Checked
        usar_contains     = self.rb_contains.Checked
        usar_not_contains = self.rb_not_contains.Checked
        txt_contains      = self.txt_contains.Text.strip().lower()
        txt_not_contains  = self.txt_not_contains.Text.strip().lower()

        for item in self.dados:
            if apenas_problemas and not item["precisa_ajuste"]:
                continue

            tipo_lower = item["tipo"].lower()

            if usar_contains and txt_contains:
                if txt_contains not in tipo_lower:
                    continue

            if usar_not_contains and txt_not_contains:
                if txt_not_contains in tipo_lower:
                    continue

            altura_atual_mm = int(round(item["altura_atual"]  * 304.8))
            nova_altura_mm  = int(round(item["nova_altura"]    * 304.8))
            topo_atual_mm   = int(round(item["topo_atual"]     * 304.8))
            ceiling_topo_mm = int(round(item["ceiling_topo"]   * 304.8)) if item["ceiling"] else 0

            lvi = ListViewItem(item["tipo"])
            lvi.SubItems.Add(item["nivel"])
            lvi.SubItems.Add(item["constraint"])
            lvi.SubItems.Add(str(altura_atual_mm))
            lvi.SubItems.Add(str(nova_altura_mm))
            lvi.SubItems.Add(str(topo_atual_mm))
            lvi.SubItems.Add(str(ceiling_topo_mm) if item["ceiling"] else "No ceiling")
            lvi.Tag     = item
            lvi.Checked = item["precisa_ajuste"]

            if item["precisa_ajuste"]:
                lvi.BackColor = Color.FromArgb(255, 180, 180)

            self.lv.Items.Add(lvi)

        self._atualizar_status()

    def _atualizar_status(self):
        total   = self.lv.Items.Count
        checked = sum(1 for i in range(total) if self.lv.Items[i].Checked)
        self.lbl_status.Text = "Selected: {} / {} walls".format(checked, total)

    def _on_filtro(self, s, e):
        self._refresh_lista()

    def _on_item_checked(self, s, e):
        self._atualizar_status()

    def _sel_todos(self, s, e):
        for i in range(self.lv.Items.Count):
            self.lv.Items[i].Checked = True
        self._atualizar_status()

    def _sel_nenhum(self, s, e):
        for i in range(self.lv.Items.Count):
            self.lv.Items[i].Checked = False
        self._atualizar_status()

    def _on_aplicar(self, s, e):
        selecionados = [self.lv.Items[i].Tag
                        for i in range(self.lv.Items.Count)
                        if self.lv.Items[i].Checked]

        if not selecionados:
            MessageBox.Show("No walls selected.", "Warning",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return

        resultado = MessageBox.Show(
            "Adjust {} walls?".format(len(selecionados)),
            "Confirm", MessageBoxButtons.YesNo, MessageBoxIcon.Question)

        if str(resultado) != "Yes":
            return

        ajustados, falhas = aplicar_ajustes(selecionados)

        MessageBox.Show(
            "Done!\n\nAdjusted: {}\nFailed: {}".format(ajustados, falhas),
            "Result", MessageBoxButtons.OK, MessageBoxIcon.Information)

        self._carregar_dados()

# -------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------
if __name__ == "__main__":
    AjustarParedesForm().ShowDialog()
