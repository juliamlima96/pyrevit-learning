# -*- coding: utf-8 -*-
"""
Join / Unjoin Geometry Tool for Revit
- Pre-select elements in Revit before running the script
- Shows selected elements in a window with search filter
- Persistent checkbox selection
- Join all checked elements (all pairs)
- Unjoin all checked elements (all pairs)
- Progress bar during bulk join/unjoin
"""

import clr

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("RevitServices")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")
clr.AddReference("System")

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory,
    ElementId, JoinGeometryUtils, Transaction,
    Element, BuiltInParameter
)
from System.Windows.Forms import (
    Application, Form, Label, CheckedListBox, Button,
    FormStartPosition, MessageBox, MessageBoxButtons,
    MessageBoxIcon, DialogResult, TextBox, ProgressBar,
    FormBorderStyle, ProgressBarStyle, ToolTip, CheckState
)
from System.Drawing import Point, Size, Font, FontStyle, ContentAlignment, Color
from System import Action

uidoc = __revit__.ActiveUIDocument
doc   = __revit__.ActiveUIDocument.Document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_element_label(elem):
    """Returns a readable label for a Revit element: Category: TypeName [ID: xxxxx]"""
    type_name = None
    cat_name = None

    # Category name
    try:
        if elem.Category and elem.Category.Name:
            cat_name = elem.Category.Name
    except:
        pass

    # Type name - multiple fallback approaches for IronPython compatibility
    try:
        type_id = elem.GetTypeId()
        if type_id and type_id != ElementId.InvalidElementId:
            type_elem = doc.GetElement(type_id)
            if type_elem is not None:
                # Approach 1: .NET property accessor
                try:
                    type_name = Element.Name.__get__(type_elem)
                except:
                    pass

                # Approach 2: SYMBOL_NAME_PARAM
                if not type_name:
                    try:
                        p = type_elem.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
                        if p and p.HasValue:
                            type_name = p.AsString()
                    except:
                        pass

                # Approach 3: ALL_MODEL_TYPE_NAME
                if not type_name:
                    try:
                        p = type_elem.get_Parameter(BuiltInParameter.ALL_MODEL_TYPE_NAME)
                        if p and p.HasValue:
                            type_name = p.AsString()
                    except:
                        pass

                # Approach 4: str() on the type element
                if not type_name:
                    try:
                        type_name = str(type_elem.Name)
                    except:
                        pass
    except:
        pass

    if not type_name:
        type_name = "Unknown"
    if not cat_name:
        cat_name = "Element"

    return "{}: {} [ID: {}]".format(cat_name, type_name, elem.Id.IntegerValue)


def get_selected_elements():
    """Gets the currently selected elements in Revit."""
    selection = uidoc.Selection.GetElementIds()
    elements = []
    for eid in selection:
        elem = doc.GetElement(eid)
        if elem is not None:
            elements.append(elem)
    return elements


def do_join_all(elements, progress_cb=None):
    """Attempts JoinGeometry on all pairs. Returns (joined, skipped, errors)."""
    joined = skipped = errors = 0
    total = len(elements)
    total_pairs = max(total * (total - 1) // 2, 1)
    done = 0

    for i in range(total):
        for j in range(i + 1, total):
            done += 1
            if progress_cb:
                progress_cb(int(done * 100 / total_pairs))
            try:
                a, b = elements[i], elements[j]
                if JoinGeometryUtils.AreElementsJoined(doc, a, b):
                    skipped += 1
                else:
                    JoinGeometryUtils.JoinGeometry(doc, a, b)
                    joined += 1
            except:
                errors += 1

    return joined, skipped, errors


def do_unjoin_all(elements, progress_cb=None):
    """Attempts UnjoinGeometry on all pairs. Returns (unjoined, skipped, errors)."""
    unjoined = skipped = errors = 0
    total = len(elements)
    total_pairs = max(total * (total - 1) // 2, 1)
    done = 0

    for i in range(total):
        for j in range(i + 1, total):
            done += 1
            if progress_cb:
                progress_cb(int(done * 100 / total_pairs))
            try:
                a, b = elements[i], elements[j]
                if JoinGeometryUtils.AreElementsJoined(doc, a, b):
                    JoinGeometryUtils.UnjoinGeometry(doc, a, b)
                    unjoined += 1
                else:
                    skipped += 1
            except:
                errors += 1

    return unjoined, skipped, errors


# ---------------------------------------------------------------------------
# Progress Form
# ---------------------------------------------------------------------------
class ProgressForm(Form):
    def __init__(self):
        self.Text            = "Processing..."
        self.Size            = Size(400, 110)
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.StartPosition   = FormStartPosition.CenterScreen
        self.ControlBox      = False

        self.lbl = Label(
            Text="Please wait...", Location=Point(12, 12),
            Size=Size(370, 20), Font=Font("Segoe UI", 9), Parent=self
        )
        self.bar = ProgressBar(
            Location=Point(12, 38), Size=Size(370, 20),
            Minimum=0, Maximum=100,
            Style=ProgressBarStyle.Continuous, Parent=self
        )

    def update(self, pct, msg=None):
        try:
            self.bar.Value = max(0, min(100, pct))
            if msg:
                self.lbl.Text = msg
            Application.DoEvents()
        except:
            pass


# ---------------------------------------------------------------------------
# Main Form
# ---------------------------------------------------------------------------
class JoinGeometryForm(Form):

    def __init__(self, elements):
        self.Text            = "Join / Unjoin Geometry Tool"
        self.Size            = Size(660, 640)
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.StartPosition   = FormStartPosition.CenterScreen
        self.MaximizeBox     = False

        # label -> element
        self.all_elements        = {}
        self.all_items           = []
        self._checked_items      = set()
        self._show_selected_only = False

        self._build_ui()
        self._load_elements(elements)

    # ---------------------------------------------------------------
    def _build_ui(self):
        y = 12

        # Title
        lbl_title = Label(
            Text="Join / Unjoin Geometry Tool",
            Location=Point(12, y), Size=Size(630, 30),
            Font=Font("Segoe UI", 14, FontStyle.Bold), Parent=self
        )
        lbl_title.TextAlign = ContentAlignment.MiddleLeft
        y += 32

        # Subtitle - info
        self.lbl_info = Label(
            Text="Elements from Revit selection:",
            Location=Point(12, y), Size=Size(630, 20),
            Font=Font("Segoe UI", 9), Parent=self
        )
        y += 28

        # ── Search filter ───────────────────────────────────────────
        Label(
            Text="Filter:",
            Location=Point(12, y + 4), Size=Size(44, 20),
            Font=Font("Segoe UI", 9), Parent=self
        )
        self.txt_search = TextBox(
            Location=Point(58, y), Size=Size(582, 24),
            Font=Font("Segoe UI", 9), Parent=self
        )
        self.txt_search.TextChanged += self.on_filter
        y += 34

        # ── Selection buttons ────────────────────────────────────────
        btn_all = Button(
            Text="Select All", Location=Point(12, y), Size=Size(90, 26),
            Font=Font("Segoe UI", 9), Parent=self
        )
        btn_all.Click += self.on_select_all

        btn_none = Button(
            Text="Clear Selection", Location=Point(110, y), Size=Size(110, 26),
            Font=Font("Segoe UI", 9), Parent=self
        )
        btn_none.Click += self.on_select_none

        self.btn_show_sel = Button(
            Text="Show Selected", Location=Point(228, y), Size=Size(115, 26),
            Font=Font("Segoe UI", 9), Parent=self
        )
        self.btn_show_sel.Click += self.on_toggle_show_selected

        self.lbl_count = Label(
            Text="0 selected / 0 total",
            Location=Point(352, y + 5), Size=Size(280, 18),
            Font=Font("Segoe UI", 9), Parent=self
        )
        y += 36

        # ── Element list ─────────────────────────────────────────────
        self.chk_items = CheckedListBox(
            Location=Point(12, y), Size=Size(628, 360),
            Font=Font("Segoe UI", 9),
            CheckOnClick=True,
            ScrollAlwaysVisible=True,
            Parent=self
        )
        self.chk_items.ItemCheck += self.on_item_check
        y += 370

        # ── Action buttons ───────────────────────────────────────────
        btn_cancel = Button(
            Text="Cancel", Location=Point(12, y), Size=Size(90, 34),
            Font=Font("Segoe UI", 9), Parent=self
        )
        btn_cancel.Click += lambda s, e: self.Close()

        btn_unjoin = Button(
            Text="Unjoin Geometry",
            Location=Point(288, y), Size=Size(170, 34),
            Font=Font("Segoe UI", 10, FontStyle.Bold), Parent=self
        )
        btn_unjoin.BackColor = Color.FromArgb(200, 80, 0)
        btn_unjoin.ForeColor = Color.White
        btn_unjoin.Click += self.on_unjoin_all

        btn_join = Button(
            Text="Join Geometry",
            Location=Point(470, y), Size=Size(170, 34),
            Font=Font("Segoe UI", 10, FontStyle.Bold), Parent=self
        )
        btn_join.BackColor = Color.FromArgb(0, 100, 200)
        btn_join.ForeColor = Color.White
        btn_join.Click += self.on_join_all

        tip = ToolTip()
        tip.SetToolTip(btn_join, "Attempts Join Geometry on all pairs of checked elements.")
        tip.SetToolTip(btn_unjoin, "Attempts Unjoin Geometry on all pairs of checked elements.")

    # ---------------------------------------------------------------
    # Load pre-selected elements
    # ---------------------------------------------------------------
    def _load_elements(self, elements):
        """Populates the list with the pre-selected Revit elements."""
        self.all_elements = {}
        self.all_items    = []

        for elem in elements:
            label = get_element_label(elem)
            # Ensure unique labels (in case of duplicates)
            if label in self.all_elements:
                label = "{} #{}".format(label, elem.Id.IntegerValue)
            self.all_elements[label] = elem
            self.all_items.append(label)

        self.all_items.sort()

        self.chk_items.Items.Clear()
        for lbl in self.all_items:
            self.chk_items.Items.Add(lbl)

        self.lbl_info.Text = "Elements from Revit selection: {} found".format(
            len(self.all_items))
        self._update_count()

    # ---------------------------------------------------------------
    # Filter & selection
    # ---------------------------------------------------------------
    def on_filter(self, s, e):
        self._sync_checked()
        self._refresh_list()

    def _sync_checked(self):
        """Syncs _checked_items with the visible list."""
        for i in range(self.chk_items.Items.Count):
            display = self.chk_items.Items[i]
            if self.chk_items.GetItemChecked(i):
                self._checked_items.add(display)
            else:
                self._checked_items.discard(display)

    def _refresh_list(self):
        """Re-renders the list respecting the search filter and show-selected mode."""
        search = self.txt_search.Text.strip().lower()
        self.chk_items.Items.Clear()
        for key in self.all_items:
            if self._show_selected_only and key not in self._checked_items:
                continue
            if search and search not in key.lower():
                continue
            idx = self.chk_items.Items.Add(key)
            if key in self._checked_items:
                self.chk_items.SetItemChecked(idx, True)
        self._update_count()

    def on_select_all(self, s, e):
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, True)
            self._checked_items.add(self.chk_items.Items[i])
        self._update_count()

    def on_select_none(self, s, e):
        for i in range(self.chk_items.Items.Count):
            self.chk_items.SetItemChecked(i, False)
        self._checked_items.clear()
        if self._show_selected_only:
            self._show_selected_only = False
            self.btn_show_sel.Text      = "Show Selected"
            self.btn_show_sel.BackColor = self.BackColor
            self.btn_show_sel.ForeColor = Color.Black
            self._refresh_list()
        self._update_count()

    def on_item_check(self, s, e):
        try:
            display = self.chk_items.Items[e.Index]
            if e.NewValue == CheckState.Checked:
                self._checked_items.add(display)
            else:
                self._checked_items.discard(display)
            self.BeginInvoke(Action(self._update_count))
        except:
            pass

    def on_toggle_show_selected(self, s, e):
        self._sync_checked()
        if not self._show_selected_only:
            if not self._checked_items:
                MessageBox.Show("No items selected.", "Warning",
                                MessageBoxButtons.OK, MessageBoxIcon.Warning)
                return
            self._show_selected_only = True
            self.btn_show_sel.Text      = "Show All"
            self.btn_show_sel.BackColor = Color.FromArgb(255, 180, 0)
            self.btn_show_sel.ForeColor = Color.Black
        else:
            self._show_selected_only = False
            self.btn_show_sel.Text      = "Show Selected"
            self.btn_show_sel.BackColor = self.BackColor
            self.btn_show_sel.ForeColor = Color.Black
        self._refresh_list()

    def _update_count(self):
        checked = sum(1 for i in range(self.chk_items.Items.Count)
                      if self.chk_items.GetItemChecked(i))
        total = self.chk_items.Items.Count
        self.lbl_count.Text = "{} selected / {} total".format(checked, total)

    def _get_checked_elements(self):
        elements = []
        for i in range(self.chk_items.Items.Count):
            if self.chk_items.GetItemChecked(i):
                key = self.chk_items.Items[i]
                if key in self.all_elements:
                    elements.append(self.all_elements[key])
        return elements

    # ---------------------------------------------------------------
    # Join all checked elements
    # ---------------------------------------------------------------
    def on_join_all(self, s, e):
        elements = self._get_checked_elements()

        if len(elements) < 2:
            MessageBox.Show(
                "Please check at least 2 elements.",
                "Warning", MessageBoxButtons.OK, MessageBoxIcon.Warning
            )
            return

        if MessageBox.Show(
            "Apply Join Geometry?",
            "Confirm", MessageBoxButtons.YesNo, MessageBoxIcon.Question
        ) != DialogResult.Yes:
            return

        pf = ProgressForm()
        pf.Show()
        Application.DoEvents()

        t = Transaction(doc, "Join Geometry - Bulk")
        t.Start()
        try:
            joined, skipped, errors = do_join_all(
                elements,
                lambda pct: pf.update(pct, "Processing pairs... {}%".format(pct))
            )
            t.Commit()
        except Exception as ex:
            t.RollBack()
            pf.Close()
            MessageBox.Show(
                "Error during Join Geometry:\n{}".format(ex),
                "Error", MessageBoxButtons.OK, MessageBoxIcon.Error
            )
            return

        pf.update(100, "Done!")
        Application.DoEvents()
        pf.Close()

        MessageBox.Show(
            "Join Geometry completed!\n\n"
            "Joined: {}\nAlready joined (skipped): {}\nErrors: {}".format(
                joined, skipped, errors),
            "Result", MessageBoxButtons.OK, MessageBoxIcon.Information
        )

    # ---------------------------------------------------------------
    # Unjoin all checked elements
    # ---------------------------------------------------------------
    def on_unjoin_all(self, s, e):
        elements = self._get_checked_elements()

        if len(elements) < 2:
            MessageBox.Show(
                "Please check at least 2 elements.",
                "Warning", MessageBoxButtons.OK, MessageBoxIcon.Warning
            )
            return

        if MessageBox.Show(
            "Apply Unjoin Geometry?",
            "Confirm", MessageBoxButtons.YesNo, MessageBoxIcon.Question
        ) != DialogResult.Yes:
            return

        pf = ProgressForm()
        pf.Show()
        Application.DoEvents()

        t = Transaction(doc, "Unjoin Geometry - Bulk")
        t.Start()
        try:
            unjoined, skipped, errors = do_unjoin_all(
                elements,
                lambda pct: pf.update(pct, "Processing pairs... {}%".format(pct))
            )
            t.Commit()
        except Exception as ex:
            t.RollBack()
            pf.Close()
            MessageBox.Show(
                "Error during Unjoin Geometry:\n{}".format(ex),
                "Error", MessageBoxButtons.OK, MessageBoxIcon.Error
            )
            return

        pf.update(100, "Done!")
        Application.DoEvents()
        pf.Close()

        MessageBox.Show(
            "Unjoin Geometry completed!\n\n"
            "Unjoined: {}\nAlready not joined (skipped): {}\nErrors: {}".format(
                unjoined, skipped, errors),
            "Result", MessageBoxButtons.OK, MessageBoxIcon.Information
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    selected = get_selected_elements()

    if not selected:
        MessageBox.Show(
            "No elements selected in Revit.\n\n"
            "Please select the elements you want to join\n"
            "before running this script.",
            "Join Geometry Tool",
            MessageBoxButtons.OK, MessageBoxIcon.Warning
        )
    else:
        JoinGeometryForm(selected).ShowDialog()