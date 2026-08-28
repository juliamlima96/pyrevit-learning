# -*- coding: utf-8 -*-
"""
Adjust Room Heights to Ceiling
- Adjusts Unbounded Height of each Room to match the Ceiling above it
"""

import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, BuiltInParameter,
    Transaction
)
from Autodesk.Revit.DB.Architecture import Room
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
def get_rooms():
    return [r for r in
            FilteredElementCollector(doc)
            .OfCategory(BuiltInCategory.OST_Rooms)
            .WhereElementIsNotElementType()
            .ToElements()
            if r.Area > 0]

def get_ceilings():
    return list(
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Ceilings)
        .WhereElementIsNotElementType()
        .ToElements()
    )

def find_ceiling_for_room(room, ceilings):
    loc = room.Location
    if not loc:
        return None, 0

    room_center = loc.Point
    room_level  = doc.GetElement(room.LevelId)
    if not room_level:
        return None, 0

    room_elev    = room_level.Elevation
    best_ceiling = None
    best_altura  = 0

    for ceiling in ceilings:
        ceiling_level = doc.GetElement(ceiling.LevelId)
        if not ceiling_level:
            continue
        if abs(ceiling_level.Elevation - room_elev) > 30:
            continue

        bb = ceiling.get_BoundingBox(None)
        if not bb:
            continue

        if (room_center.X >= bb.Min.X and room_center.X <= bb.Max.X and
                room_center.Y >= bb.Min.Y and room_center.Y <= bb.Max.Y):

            param  = ceiling.get_Parameter(BuiltInParameter.CEILING_HEIGHTABOVELEVEL_PARAM)
            offset = param.AsDouble() if param else 0
            topo   = ceiling_level.Elevation + offset

            if topo > room_elev:
                if best_ceiling is None or topo < best_altura:
                    best_ceiling = ceiling
                    best_altura  = topo

    return best_ceiling, best_altura

# -------------------------------------------------------------
# ANALISE
# -------------------------------------------------------------
def analyze_rooms():
    rooms    = get_rooms()
    ceilings = get_ceilings()
    resultado = []

    for room in rooms:
        room_level = doc.GetElement(room.LevelId)
        room_elev  = room_level.Elevation if room_level else 0

        param_name   = room.get_Parameter(BuiltInParameter.ROOM_NAME)
        param_number = room.get_Parameter(BuiltInParameter.ROOM_NUMBER)
        param_height = room.get_Parameter(BuiltInParameter.ROOM_HEIGHT)

        name           = param_name.AsString()   if param_name   else "N/A"
        number         = param_number.AsString() if param_number else "N/A"
        current_height = param_height.AsDouble() if param_height else 0

        ceiling, ceiling_topo = find_ceiling_for_room(room, ceilings)

        if ceiling:
            new_height   = ceiling_topo - room_elev
            difference   = abs(new_height - current_height) * 304.8
            needs_adjust = difference > 1
        else:
            new_height   = current_height
            difference   = 0
            needs_adjust = False

        resultado.append({
            "room":           room,
            "name":           name,
            "number":         number,
            "current_height": current_height,
            "new_height":     new_height,
            "ceiling":        ceiling,
            "ceiling_topo":   ceiling_topo,
            "needs_adjust":   needs_adjust,
            "level":          room_level.Name if room_level else "N/A"
        })

    return resultado

# -------------------------------------------------------------
# APPLY
# -------------------------------------------------------------
def apply_adjustments(selected_items):
    adjusted = 0
    failed   = 0

    with Transaction(doc, "Adjust Room Heights") as tx:
        tx.Start()
        for item in selected_items:
            room = item["room"]
            room_level = doc.GetElement(room.LevelId)
            if not room_level:
                continue

            try:
                param_height = room.get_Parameter(BuiltInParameter.ROOM_HEIGHT)

                if param_height and not param_height.IsReadOnly:
                    param_height.Set(item["new_height"])
                    adjusted += 1

                else:
                    param_upper_level  = room.get_Parameter(BuiltInParameter.ROOM_UPPER_LEVEL)
                    param_limit_offset = room.get_Parameter(BuiltInParameter.ROOM_UPPER_OFFSET)

                    if param_limit_offset and not param_limit_offset.IsReadOnly:
                        if param_upper_level and param_upper_level.AsElementId():
                            upper_level = doc.GetElement(param_upper_level.AsElementId())
                            upper_elev  = upper_level.Elevation if upper_level else room_level.Elevation
                        else:
                            upper_elev = room_level.Elevation

                        new_offset = item["ceiling_topo"] - upper_elev
                        param_limit_offset.Set(new_offset)
                        adjusted += 1
                    else:
                        failed += 1

            except Exception as ex:
                failed += 1

        tx.Commit()

    return adjusted, failed

# -------------------------------------------------------------
# INTERFACE
# -------------------------------------------------------------
class AdjustRoomsForm(Form):
    def __init__(self):
        self.Text            = "Adjust Room Heights to Ceiling"
        self.Size            = Size(820, 640)
        self.StartPosition   = FormStartPosition.CenterScreen
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox     = False
        self.data            = []
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        # Checkbox
        self.chk_only_different = CheckBox(
            Text="Show only rooms that need adjustment",
            Location=Point(15, 15), Size=Size(350, 20),
            Font=Font("Segoe UI", 9),
            Checked=True, Parent=self)
        self.chk_only_different.CheckedChanged += self._on_filter

        # GroupBox filter by room name
        grp = GroupBox(
            Text="Filter by Room Name",
            Location=Point(15, 42), Size=Size(780, 55),
            Font=Font("Segoe UI", 9), Parent=self)

        self.rb_none = RadioButton(
            Text="No filter", Location=Point(10, 22),
            Size=Size(80, 20), Checked=True,
            Font=Font("Segoe UI", 9), Parent=grp)
        self.rb_none.CheckedChanged += self._on_filter

        self.rb_contains = RadioButton(
            Text="Contains:", Location=Point(100, 22),
            Size=Size(80, 20),
            Font=Font("Segoe UI", 9), Parent=grp)
        self.rb_contains.CheckedChanged += self._on_filter

        self.txt_contains = TextBox(
            Location=Point(185, 20), Size=Size(180, 22),
            Font=Font("Segoe UI", 9), Parent=grp)
        self.txt_contains.TextChanged += self._on_filter

        self.rb_not_contains = RadioButton(
            Text="Does Not Contain:", Location=Point(380, 22),
            Size=Size(145, 20),
            Font=Font("Segoe UI", 9), Parent=grp)
        self.rb_not_contains.CheckedChanged += self._on_filter

        self.txt_not_contains = TextBox(
            Location=Point(530, 20), Size=Size(180, 22),
            Font=Font("Segoe UI", 9), Parent=grp)
        self.txt_not_contains.TextChanged += self._on_filter

        # ListView
        self.lv = ListView(
            Location=Point(15, 108), Size=Size(780, 400),
            View=View.Details, FullRowSelect=True,
            GridLines=True, CheckBoxes=True,
            Font=Font("Segoe UI", 9), Parent=self)

        for col_text, col_width in [
            ("Number", 70), ("Name", 200), ("Level", 100),
            ("Current Height mm", 140), ("New Height mm", 130), ("Difference mm", 120)]:
            col       = ColumnHeader()
            col.Text  = col_text
            col.Width = col_width
            self.lv.Columns.Add(col)

        self.lv.ItemChecked += self._on_item_checked

        Label(
            Text="Red = needs adjustment",
            Location=Point(15, 515), Size=Size(300, 18),
            Font=Font("Segoe UI", 8), Parent=self)

        Button(
            Text="Select All", Location=Point(15, 538),
            Size=Size(100, 28), Font=Font("Segoe UI", 9),
            Parent=self).Click += self._sel_all

        Button(
            Text="Deselect All", Location=Point(125, 538),
            Size=Size(100, 28), Font=Font("Segoe UI", 9),
            Parent=self).Click += self._sel_none

        self.lbl_status = Label(
            Text="", Location=Point(235, 543),
            Size=Size(300, 20), Font=Font("Segoe UI", 9),
            Parent=self)

        btn_apply = Button(
            Text="Apply Adjustments", Location=Point(660, 538),
            Size=Size(135, 28),
            Font=Font("Segoe UI", 10, FontStyle.Bold),
            Parent=self)
        btn_apply.BackColor = Color.FromArgb(0, 120, 215)
        btn_apply.ForeColor = Color.White
        btn_apply.Click    += self._on_apply

    def _load_data(self):
        self.data = analyze_rooms()
        self._refresh_list()

    def _refresh_list(self):
        self.lv.Items.Clear()
        only_different    = self.chk_only_different.Checked
        usar_contains     = self.rb_contains.Checked
        usar_not_contains = self.rb_not_contains.Checked
        txt_contains      = self.txt_contains.Text.strip().lower()
        txt_not_contains  = self.txt_not_contains.Text.strip().lower()

        for item in self.data:
            if only_different and not item["needs_adjust"]:
                continue

            name_lower = item["name"].lower()

            if usar_contains and txt_contains:
                if txt_contains not in name_lower:
                    continue

            if usar_not_contains and txt_not_contains:
                if txt_not_contains in name_lower:
                    continue

            current_mm = int(round(item["current_height"] * 304.8))
            new_mm     = int(round(item["new_height"]     * 304.8))
            diff_mm    = int(round(abs(new_mm - current_mm)))

            lvi = ListViewItem(item["number"])
            lvi.SubItems.Add(item["name"])
            lvi.SubItems.Add(item["level"])
            lvi.SubItems.Add(str(current_mm))
            lvi.SubItems.Add(str(new_mm))
            lvi.SubItems.Add(str(diff_mm))
            lvi.Tag     = item
            lvi.Checked = item["needs_adjust"]

            if item["needs_adjust"]:
                lvi.BackColor = Color.FromArgb(255, 180, 180)

            self.lv.Items.Add(lvi)

        self._update_status()

    def _update_status(self):
        total   = self.lv.Items.Count
        checked = sum(1 for i in range(total) if self.lv.Items[i].Checked)
        self.lbl_status.Text = "Selected: {} / {}".format(checked, total)

    def _on_filter(self, s, e):
        self._refresh_list()

    def _on_item_checked(self, s, e):
        self._update_status()

    def _sel_all(self, s, e):
        for i in range(self.lv.Items.Count):
            self.lv.Items[i].Checked = True
        self._update_status()

    def _sel_none(self, s, e):
        for i in range(self.lv.Items.Count):
            self.lv.Items[i].Checked = False
        self._update_status()

    def _on_apply(self, s, e):
        selected = [self.lv.Items[i].Tag
                    for i in range(self.lv.Items.Count)
                    if self.lv.Items[i].Checked]

        if not selected:
            MessageBox.Show("No rooms selected.", "Warning",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return

        result = MessageBox.Show(
            "Adjust {} rooms?".format(len(selected)),
            "Confirm", MessageBoxButtons.YesNo, MessageBoxIcon.Question)

        if str(result) != "Yes":
            return

        adjusted, failed = apply_adjustments(selected)

        MessageBox.Show(
            "Done!\n\nAdjusted: {}\nFailed: {}".format(adjusted, failed),
            "Result", MessageBoxButtons.OK, MessageBoxIcon.Information)

        self._load_data()

# -------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------
if __name__ == "__main__":
    AdjustRoomsForm().ShowDialog()
