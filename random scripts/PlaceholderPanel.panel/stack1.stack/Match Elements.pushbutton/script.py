# -*- coding: utf-8 -*-
"""
Match Names Tool for Revit
- Compares Wall, Floor and Ceiling types between source and target models
- Identifies types with identical structure (layers, materials, widths, functions)
  but different names
- Allows renaming target types to match source names
"""

import clr
import sys

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("RevitServices")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
clr.AddReference("System")

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, BuiltInParameter,
    ElementId, Transaction, TransactionGroup,
    WallType, FloorType, CeilingType, RoofType,
    Material, CompoundStructure, StorageType
)
from System.Windows.Forms import (
    Application, Form, Label, ComboBox, CheckedListBox, Button,
    FormStartPosition, ComboBoxStyle, MessageBox, MessageBoxButtons,
    MessageBoxIcon, DialogResult, TextBox, ProgressBar, ListView,
    ListViewItem, View, ColumnHeader, SortOrder,
    FormBorderStyle, ProgressBarStyle, ToolTip, CheckState,
    CheckBox, HorizontalAlignment, Padding, Panel, ListBox
)
from System.Drawing import Point, Size, Font, FontStyle, ContentAlignment, Color
from System import Action, EventHandler

import System.Windows.Forms

uidoc = __revit__.ActiveUIDocument
doc   = __revit__.ActiveUIDocument.Document

# ─────────────────────────────────────────────────────────────
# OPEN DOCUMENTS
# ─────────────────────────────────────────────────────────────
app = doc.Application
doc_opt = [d for d in app.Documents if not d.IsFamilyDocument]
doc_names = sorted([d.Title for d in doc_opt])

if len(doc_opt) < 2:
    MessageBox.Show(
        "Please open at least 2 projects to compare.",
        "Match Names Tool", MessageBoxButtons.OK, MessageBoxIcon.Warning)
    sys.exit()

# ─────────────────────────────────────────────────────────────
# CATEGORY MAP
# ─────────────────────────────────────────────────────────────
CATEGORY_MAP = {
    "Wall Types":    lambda d: FilteredElementCollector(d).OfClass(WallType).ToElements(),
    "Floor Types":   lambda d: FilteredElementCollector(d).OfClass(FloorType).ToElements(),
    "Ceiling Types": lambda d: FilteredElementCollector(d).OfClass(CeilingType).ToElements(),
}

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def get_name(e):
    try:
        p = e.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
        if p and p.HasValue:
            return p.AsString()
        return e.Name
    except:
        try:
            return e.Name
        except:
            return ""


def get_structure_fingerprint(elem_type, doc_ref):
    try:
        cs = elem_type.GetCompoundStructure()
        if not cs:
            return None
        parts = []
        for i in range(cs.LayerCount):
            try:
                width = round(cs.GetLayerWidth(i), 6)
                func  = str(cs.GetLayerFunction(i))
                mat_id = cs.GetMaterialId(i)
                mat_name = ""
                if mat_id and mat_id != ElementId.InvalidElementId:
                    mat_elem = doc_ref.GetElement(mat_id)
                    if mat_elem:
                        mat_name = mat_elem.Name or ""
                parts.append("{}|{}|{}".format(func, width, mat_name))
            except:
                parts.append("ERROR")
        return "::".join(parts)
    except:
        return None


def find_matches(src_doc, tgt_doc, cat_key):
    """
    Returns list of tuples: (src_name, tgt_name, src_type, tgt_type, fingerprint, is_dup)
    is_dup = True when multiple source types share the same fingerprint.
    All combinations are included so the user can choose.
    """
    collector_func = CATEGORY_MAP[cat_key]
    src_types = collector_func(src_doc)
    tgt_types = collector_func(tgt_doc)

    # fingerprint -> [(name, type)]  — keep ALL source types
    src_fps = {}
    for t in src_types:
        name = get_name(t)
        if not name:
            continue
        fp = get_structure_fingerprint(t, src_doc)
        if not fp:
            continue
        src_fps.setdefault(fp, []).append((name, t))

    # fingerprint -> [(name, type)]  — target
    tgt_fps = {}
    for t in tgt_types:
        name = get_name(t)
        if not name:
            continue
        fp = get_structure_fingerprint(t, tgt_doc)
        if not fp:
            continue
        tgt_fps.setdefault(fp, []).append((name, t))

    matches = []
    for fp, src_list in src_fps.items():
        if fp not in tgt_fps:
            continue
        is_dup = len(src_list) > 1
        tgt_list = tgt_fps[fp]
        for src_name, src_type in src_list:
            for tgt_name, tgt_type in tgt_list:
                if src_name != tgt_name:
                    matches.append((src_name, tgt_name, src_type, tgt_type, fp, is_dup))

    matches.sort(key=lambda x: (x[4], x[0], x[1]))  # sort by fingerprint, then src, then tgt
    return matches


def get_structure_description(elem_type, doc_ref):
    try:
        cs = elem_type.GetCompoundStructure()
        if not cs:
            return "No compound structure"
        lines = []
        total_width = 0.0
        for i in range(cs.LayerCount):
            try:
                width_ft = cs.GetLayerWidth(i)
                width_mm = round(width_ft * 304.8, 1)
                total_width += width_ft
                func = str(cs.GetLayerFunction(i)).replace("MaterialFunctionAssignment.", "")
                mat_id = cs.GetMaterialId(i)
                mat_name = "<none>"
                if mat_id and mat_id != ElementId.InvalidElementId:
                    mat_elem = doc_ref.GetElement(mat_id)
                    if mat_elem and mat_elem.Name:
                        mat_name = mat_elem.Name
                lines.append("  Layer {}: {} | {} mm | {}".format(i + 1, func, width_mm, mat_name))
            except:
                lines.append("  Layer {}: <error>".format(i + 1))
        total_mm = round(total_width * 304.8, 1)
        return "Total: {} mm | {} layers\n{}".format(total_mm, cs.LayerCount, "\n".join(lines))
    except:
        return "Error reading structure"


# ─────────────────────────────────────────────────────────────
# PROJECT SELECTOR FORM
# ─────────────────────────────────────────────────────────────
class ProjectSelectorForm(Form):
    def __init__(self):
        self.Text = "Match Names Tool"
        self.Size = Size(580, 220)
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimumSize = Size(580, 220)
        self.Padding = Padding(20)

        Label(Text="Source Project",
              Location=Point(30, 40), Size=Size(250, 20), Parent=self,
              Font=Font("Segoe UI", 9))

        self.cmb_src = ComboBox(
            Location=Point(30, 62), Size=Size(510, 23),
            DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for n in doc_names:
            self.cmb_src.Items.Add(n)

        Label(Text="Target Project",
              Location=Point(30, 100), Size=Size(250, 20), Parent=self,
              Font=Font("Segoe UI", 9))

        self.cmb_tgt = ComboBox(
            Location=Point(30, 122), Size=Size(510, 23),
            DropDownStyle=ComboBoxStyle.DropDownList, Parent=self)
        for n in doc_names:
            self.cmb_tgt.Items.Add(n)

        btn = Button(Text="Next", Location=Point(450, 155), Size=Size(90, 28), Parent=self)
        btn.Click += self.on_next

    def on_next(self, s, e):
        if not self.cmb_src.SelectedItem or not self.cmb_tgt.SelectedItem:
            MessageBox.Show("Select source and target projects.", "Error",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return
        if self.cmb_src.SelectedItem == self.cmb_tgt.SelectedItem:
            MessageBox.Show("Source and target must be different projects.", "Error",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return

        src_doc = next(d for d in doc_opt if d.Title == self.cmb_src.SelectedItem)
        tgt_doc = next(d for d in doc_opt if d.Title == self.cmb_tgt.SelectedItem)

        self.Hide()
        MatchForm(src_doc, tgt_doc).ShowDialog()
        self.Close()


# ─────────────────────────────────────────────────────────────
# MATCH FORM
# ─────────────────────────────────────────────────────────────
ITEM_H    = 22   # row height in both lists

class MatchForm(Form):
    def __init__(self, src_doc, tgt_doc):
        self.src_doc = src_doc
        self.tgt_doc = tgt_doc
        self.matches  = []          # list of (src_name, tgt_name, src_type, tgt_type, fp, is_dup)
        self._rows    = []          # filtered rows currently displayed
        self._group_starts  = set() # indices where a new fingerprint group starts
        self._index_to_group = {}   # index -> fingerprint

        self.Text = "Match Names - Compare & Rename"
        self.Size = Size(1020, 720)
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimumSize   = Size(1020, 720)

        self._build_ui()

    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        y = 15

        # ── Category + Compare ──────────────────────────────
        Label(Text="Category:", Location=Point(15, y + 3), Size=Size(70, 20),
              Font=Font("Segoe UI", 9), Parent=self)
        self.cmb_cat = ComboBox(
            Location=Point(85, y), Size=Size(200, 23),
            DropDownStyle=ComboBoxStyle.DropDownList,
            Font=Font("Segoe UI", 9), Parent=self)
        for c in sorted(CATEGORY_MAP.keys()):
            self.cmb_cat.Items.Add(c)

        btn_compare = Button(
            Text="Compare", Location=Point(295, y), Size=Size(90, 25),
            Font=Font("Segoe UI", 9), Parent=self)
        btn_compare.Click += self.on_compare

        self.lbl_result = Label(
            Text="", Location=Point(395, y + 3), Size=Size(560, 20),
            Font=Font("Segoe UI", 9), Parent=self)
        y += 35

        # ── Filter ──────────────────────────────────────────
        Label(Text="Filter:", Location=Point(15, y + 3), Size=Size(45, 20),
              Font=Font("Segoe UI", 9), Parent=self)
        self.txt_search = TextBox(
            Location=Point(60, y), Size=Size(935, 23),
            Font=Font("Segoe UI", 9), Parent=self)
        self.txt_search.TextChanged += self.on_filter
        y += 32

        # ── Column headers ──────────────────────────────────
        list_w   = 460
        sep_x    = 15 + list_w
        sep_w    = 4
        tgt_x    = sep_x + sep_w + 1

        lbl_src = Label(Text="Source Name",
              Location=Point(15, y), Size=Size(list_w, 18),
              Font=Font("Segoe UI", 8), Parent=self)
        lbl_src.TextAlign = ContentAlignment.MiddleCenter

        lbl_tgt = Label(Text="Target Name",
              Location=Point(tgt_x, y), Size=Size(list_w, 18),
              Font=Font("Segoe UI", 8), Parent=self)
        lbl_tgt.TextAlign = ContentAlignment.MiddleCenter
        y += 20

        list_h = 400

        # ── Source panel (owner-drawn ListBox) ───────────────
        self.lst_src = ListBox(
            Location=Point(15, y), Size=Size(list_w, list_h),
            Font=Font("Segoe UI", 9),
            ScrollAlwaysVisible=True,
            Parent=self)
        self.lst_src.DrawMode = System.Windows.Forms.DrawMode.OwnerDrawFixed
        self.lst_src.ItemHeight = ITEM_H
        self.lst_src.DrawItem  += self._draw_src_item
        self.lst_src.MouseDown += self._on_src_mouse_down
        self.lst_src.MouseMove += self._on_src_mouse_move

        # ── Separator ────────────────────────────────────────
        Panel(Location=Point(sep_x, y), Size=Size(sep_w, list_h),
              BackColor=Color.FromArgb(200, 200, 200), Parent=self)

        # ── Target panel (plain ListBox, no checkboxes) ──────
        self.lst_tgt = ListBox(
            Location=Point(tgt_x, y), Size=Size(list_w, list_h),
            Font=Font("Segoe UI", 9),
            ScrollAlwaysVisible=True,
            Enabled=False,
            Parent=self)
        self.lst_tgt.DrawMode  = System.Windows.Forms.DrawMode.OwnerDrawFixed
        self.lst_tgt.ItemHeight = ITEM_H
        self.lst_tgt.DrawItem  += self._draw_tgt_item

        # Tooltip
        self.tip = ToolTip()
        self.tip.AutoPopDelay = 15000
        self.tip.InitialDelay = 400
        self._last_tip_idx = -1

        # Checked state: index in self._rows -> bool
        self._checked = {}

        y += list_h + 10

        # ── Footer ───────────────────────────────────────────
        Button(Text="All", Location=Point(15, y), Size=Size(70, 26),
               Font=Font("Segoe UI", 9), Parent=self).Click += self.sel_all
        Button(Text="None", Location=Point(93, y), Size=Size(70, 26),
               Font=Font("Segoe UI", 9), Parent=self).Click += self.sel_none

        self.lbl_selected = Label(
            Text="Selected: 0", Location=Point(172, y + 4), Size=Size(160, 20),
            Font=Font("Segoe UI", 9), Parent=self)

        btn_back = Button(
            Text="Back", Location=Point(790, y), Size=Size(90, 28),
            Font=Font("Segoe UI", 9), Parent=self)
        btn_back.Click += self.on_back

        btn_rename = Button(
            Text="Rename", Location=Point(890, y), Size=Size(110, 28),
            Font=Font("Segoe UI", 10, FontStyle.Bold), Parent=self)
        btn_rename.BackColor = Color.FromArgb(0, 100, 200)
        btn_rename.ForeColor = Color.White
        btn_rename.Click += self.on_rename

    # ─── Owner-draw: source list ─────────────────────────────
    def _draw_src_item(self, s, e):
        if e.Index < 0 or e.Index >= len(self._rows):
            return
        src_name, tgt_name, src_type, tgt_type, fp, is_dup = self._rows[e.Index]
        checked = self._checked.get(e.Index, False)

        g   = e.Graphics
        rc  = e.Bounds
        bg  = Color.FromArgb(220, 234, 255) if checked else Color.White
        g.FillRectangle(System.Drawing.SolidBrush(bg), rc)

        # Group separator line at top
        if e.Index in self._group_starts and e.Index > 0:
            g.DrawLine(System.Drawing.Pen(Color.FromArgb(180, 180, 180), 1),
                       rc.X, rc.Y, rc.Right, rc.Y)

        # Checkbox square
        cb_x = rc.X + 4
        cb_y = rc.Y + (rc.Height - 13) / 2
        cb_rc = System.Drawing.Rectangle(int(cb_x), int(cb_y), 13, 13)
        g.DrawRectangle(System.Drawing.Pen(Color.FromArgb(140, 140, 140)), cb_rc)
        if checked:
            g.FillRectangle(System.Drawing.SolidBrush(Color.FromArgb(0, 100, 200)),
                            System.Drawing.Rectangle(int(cb_x)+2, int(cb_y)+2, 9, 9))

        txt_x = rc.X + 24
        txt_w = rc.Width - 28
        sf  = System.Drawing.StringFormat()
        sf.Trimming = System.Drawing.StringTrimming.EllipsisCharacter
        sf.FormatFlags = System.Drawing.StringFormatFlags.NoWrap
        g.DrawString(src_name, e.Font,
                     System.Drawing.SolidBrush(Color.Black),
                     System.Drawing.RectangleF(float(txt_x), float(rc.Y + 3),
                                               float(txt_w), float(rc.Height - 4)),
                     sf)

    # ─── Owner-draw: target list ─────────────────────────────
    def _draw_tgt_item(self, s, e):
        if e.Index < 0 or e.Index >= len(self._rows):
            return
        src_name, tgt_name, src_type, tgt_type, fp, is_dup = self._rows[e.Index]
        checked = self._checked.get(e.Index, False)

        g  = e.Graphics
        rc = e.Bounds
        bg = Color.FromArgb(220, 234, 255) if checked else Color.White
        g.FillRectangle(System.Drawing.SolidBrush(bg), rc)

        # Group separator line at top
        if e.Index in self._group_starts and e.Index > 0:
            g.DrawLine(System.Drawing.Pen(Color.FromArgb(180, 180, 180), 1),
                       rc.X, rc.Y, rc.Right, rc.Y)

        sf  = System.Drawing.StringFormat()
        sf.Trimming = System.Drawing.StringTrimming.EllipsisCharacter
        sf.FormatFlags = System.Drawing.StringFormatFlags.NoWrap
        g.DrawString(tgt_name, e.Font,
                     System.Drawing.SolidBrush(Color.Black),
                     System.Drawing.RectangleF(float(rc.X + 6), float(rc.Y + 3),
                                               float(rc.Width - 10), float(rc.Height - 4)),
                     sf)

    # ─── Scroll sync (chamado após qualquer interação) ───────
    def _sync_scroll(self):
        try:
            self.lst_tgt.TopIndex = self.lst_src.TopIndex
        except:
            pass

    # ─── Toggle checkbox on click ────────────────────────────
    def _on_src_mouse_down(self, s, e):
        self._sync_scroll()
        idx = self.lst_src.IndexFromPoint(e.Location)
        if idx < 0 or idx >= len(self._rows):
            return

        new_state = not self._checked.get(idx, False)
        group_fp  = self._index_to_group.get(idx)

        # If marking as checked, uncheck all others in the same group
        if new_state and group_fp is not None:
            for i, fp in self._index_to_group.items():
                if fp == group_fp and i != idx and self._checked.get(i, False):
                    self._checked[i] = False
                    self.lst_src.Invalidate(self.lst_src.GetItemRectangle(i))
                    self.lst_tgt.Invalidate(self.lst_tgt.GetItemRectangle(i))

        self._checked[idx] = new_state
        self.lst_src.Invalidate(self.lst_src.GetItemRectangle(idx))
        self.lst_tgt.Invalidate(self.lst_tgt.GetItemRectangle(idx))
        self._update_count()

    # ─── Tooltip on hover + sync scroll ─────────────────────
    def _on_src_mouse_move(self, s, e):
        self._sync_scroll()
        idx = self.lst_src.IndexFromPoint(e.Location)
        if idx != self._last_tip_idx and 0 <= idx < len(self._rows):
            self._last_tip_idx = idx
            src_name, tgt_name, src_type, tgt_type, fp, is_dup = self._rows[idx]
            desc = get_structure_description(src_type, self.src_doc)
            self.tip.SetToolTip(self.lst_src, desc)
        elif idx < 0:
            self._last_tip_idx = -1

    # ─── Compare ─────────────────────────────────────────────
    def on_compare(self, s, e):
        key = self.cmb_cat.SelectedItem
        if not key:
            MessageBox.Show("Select a category first.", "Warning",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return

        self.matches = find_matches(self.src_doc, self.tgt_doc, key)
        self._checked = {}
        self._refresh_lists()

        if not self.matches:
            self.lbl_result.Text = "No matches found."
        else:
            n_dup = len(set(fp for _, _, _, _, fp, is_dup in self.matches if is_dup))
            self.lbl_result.Text = "{} rows found ({} unique structures{}).".format(
                len(self.matches),
                len(set(fp for _, _, _, _, fp, _ in self.matches)),
                ", {} with duplicates".format(n_dup) if n_dup else ""
            )

    # ─── List management ─────────────────────────────────────
    def _refresh_lists(self):
        search = self.txt_search.Text.strip().lower()
        self._rows = []
        self._checked = {}

        for row in self.matches:
            src_name, tgt_name = row[0], row[1]
            if search and search not in (src_name + tgt_name).lower():
                continue
            self._rows.append(row)

        # Build set of row indices where a new fingerprint group starts
        # and a map: index -> group_id (fp) for radio-select logic
        self._group_starts = set()
        self._index_to_group = {}
        last_fp = None
        for i, row in enumerate(self._rows):
            fp = row[4]
            if fp != last_fp:
                self._group_starts.add(i)
                last_fp = fp
            self._index_to_group[i] = fp

        # Populate both ListBoxes with placeholder strings (drawing is owner-draw)
        self.lst_src.BeginUpdate()
        self.lst_tgt.BeginUpdate()
        self.lst_src.Items.Clear()
        self.lst_tgt.Items.Clear()
        for row in self._rows:
            self.lst_src.Items.Add(row[0])
            self.lst_tgt.Items.Add(row[1])
        self.lst_src.EndUpdate()
        self.lst_tgt.EndUpdate()

        self._update_count()

    def on_filter(self, s, e):
        self._refresh_lists()

    def _update_count(self):
        count = sum(1 for v in self._checked.values() if v)
        self.lbl_selected.Text = "Selected: {}".format(count)

    def sel_all(self, s, e):
        for i in range(len(self._rows)):
            self._checked[i] = True
        self.lst_src.Invalidate()
        self.lst_tgt.Invalidate()
        self._update_count()

    def sel_none(self, s, e):
        self._checked = {}
        self.lst_src.Invalidate()
        self.lst_tgt.Invalidate()
        self._update_count()

    def on_back(self, s, e):
        self.Hide()
        ProjectSelectorForm().ShowDialog()
        self.Close()

    # ─── Rename ──────────────────────────────────────────────
    def on_rename(self, s, e):
        to_rename = []
        for i, row in enumerate(self._rows):
            if self._checked.get(i, False):
                src_name, tgt_name, src_type, tgt_type, fp, is_dup = row
                to_rename.append((src_name, tgt_name, tgt_type))

        if not to_rename:
            MessageBox.Show("No items selected.", "Warning",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return

        if MessageBox.Show(
            "Rename {} types in the target project?".format(len(to_rename)),
            "Confirm", MessageBoxButtons.YesNo, MessageBoxIcon.Question
        ) != DialogResult.Yes:
            return

        renamed = 0
        failed  = 0

        tg = TransactionGroup(self.tgt_doc, "Match Names - Rename Types")
        tg.Start()

        for src_name, tgt_name, tgt_type in to_rename:
            t = Transaction(self.tgt_doc, "Rename: {} -> {}".format(tgt_name, src_name))
            t.Start()
            try:
                tgt_type.Name = src_name
                t.Commit()
                renamed += 1
            except Exception as ex:
                t.RollBack()
                failed += 1

        tg.Assimilate()

        MessageBox.Show(
            "Rename completed!\n\nRenamed: {}\nFailed: {}".format(renamed, failed),
            "Result", MessageBoxButtons.OK, MessageBoxIcon.Information)

        self.on_compare(None, None)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ProjectSelectorForm().ShowDialog()
