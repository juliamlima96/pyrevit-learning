# -*- coding: utf-8 -*-
"""
Interactive Tag Placement
- Choose leader option
- Choose tag family
- Select elements and pick tag positions
- Click Finish to place all tags at once
"""

import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, Transaction,
    IndependentTag, TagOrientation, FamilySymbol,
    ElementId, BuiltInParameter
)
from Autodesk.Revit.UI.Selection import ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException
from System.Windows.Forms import (
    Form, Label, Button, RadioButton, GroupBox, ListBox,
    FormStartPosition, MessageBox, MessageBoxButtons,
    MessageBoxIcon, FormBorderStyle, DialogResult,
    Application, SelectionMode
)
from System.Drawing import Point, Size, Font, FontStyle, Color

uidoc = __revit__.ActiveUIDocument
doc   = uidoc.Document
view  = uidoc.ActiveView

# -------------------------------------------------------------
# GET TAG FAMILIES
# -------------------------------------------------------------
def get_tag_families():
    tag_categories = [
        BuiltInCategory.OST_RoomTags,
        BuiltInCategory.OST_DoorTags,
        BuiltInCategory.OST_WindowTags,
        BuiltInCategory.OST_WallTags,
        BuiltInCategory.OST_GenericAnnotation,
    ]

    tags = {}

    for cat in tag_categories:
        symbols = FilteredElementCollector(doc)\
            .OfCategory(cat)\
            .WhereElementIsElementType()\
            .ToElements()

        for symbol in symbols:
            try:
                family_name = symbol.FamilyName
                type_name   = symbol.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
                type_str    = type_name.AsString() if type_name else ""
                full_name   = "{} : {}".format(family_name, type_str)
                tags[full_name] = symbol
            except:
                continue

    return tags

# -------------------------------------------------------------
# SETTINGS FORM
# -------------------------------------------------------------
class SettingsForm(Form):
    def __init__(self):
        self.Text            = "Tag Placement Settings"
        self.Size            = Size(420, 460)
        self.StartPosition   = FormStartPosition.CenterScreen
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox     = False
        self.use_leader      = True
        self.selected_tag    = None
        self.tag_families    = {}
        self._build_ui()
        self._load_tags()

    def _build_ui(self):
        grp_leader = GroupBox(
            Text="Leader",
            Location=Point(15, 10), Size=Size(380, 60),
            Font=Font("Segoe UI", 9), Parent=self)

        self.rb_with_leader = RadioButton(
            Text="With Leader", Location=Point(15, 25),
            Size=Size(150, 20), Checked=True,
            Font=Font("Segoe UI", 9), Parent=grp_leader)

        self.rb_no_leader = RadioButton(
            Text="Without Leader", Location=Point(175, 25),
            Size=Size(150, 20),
            Font=Font("Segoe UI", 9), Parent=grp_leader)

        grp_tags = GroupBox(
            Text="Tag Family",
            Location=Point(15, 78), Size=Size(380, 320),
            Font=Font("Segoe UI", 9), Parent=self)

        Label(
            Text="Select the tag family to use:",
            Location=Point(10, 22), Size=Size(350, 18),
            Font=Font("Segoe UI", 9), Parent=grp_tags)

        self.lst_tags = ListBox(
            Location=Point(10, 45), Size=Size(358, 260),
            Font=Font("Segoe UI", 9),
            SelectionMode=SelectionMode.One,
            Parent=grp_tags)

        btn_ok = Button(
            Text="Start", Location=Point(155, 408),
            Size=Size(100, 30),
            Font=Font("Segoe UI", 10, FontStyle.Bold),
            Parent=self)
        btn_ok.BackColor = Color.FromArgb(0, 120, 215)
        btn_ok.ForeColor = Color.White
        btn_ok.Click    += self._on_ok

    def _load_tags(self):
        self.tag_families = get_tag_families()
        self.lst_tags.Items.Clear()
        for name in sorted(self.tag_families.keys()):
            self.lst_tags.Items.Add(name)
        if self.lst_tags.Items.Count > 0:
            self.lst_tags.SelectedIndex = 0

    def _on_ok(self, s, e):
        if self.lst_tags.SelectedItem is None:
            MessageBox.Show("Please select a tag family.", "Warning",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning)
            return

        self.use_leader   = self.rb_with_leader.Checked
        self.selected_tag = self.tag_families[self.lst_tags.SelectedItem.ToString()]
        self.DialogResult = DialogResult.OK
        self.Close()

# -------------------------------------------------------------
# FINISH FORM
# -------------------------------------------------------------
class FinishForm(Form):
    def __init__(self):
        self.Text            = "Tag Placement"
        self.Size            = Size(260, 100)
        self.StartPosition   = FormStartPosition.Manual
        self.Location        = Point(100, 100)
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MaximizeBox     = False
        self.TopMost         = True
        self.finished        = False
        self._build_ui()

    def _build_ui(self):
        self.lbl = Label(
            Text="Elements queued: 0",
            Location=Point(15, 12), Size=Size(220, 20),
            Font=Font("Segoe UI", 9), Parent=self)

        btn_finish = Button(
            Text="Finish - Place All Tags",
            Location=Point(15, 36), Size=Size(220, 28),
            Font=Font("Segoe UI", 10, FontStyle.Bold),
            Parent=self)
        btn_finish.BackColor = Color.FromArgb(0, 120, 215)
        btn_finish.ForeColor = Color.White
        btn_finish.Click    += self._on_finish

    def update_count(self, count):
        self.lbl.Text = "Elements queued: {}".format(count)
        self.Refresh()

    def _on_finish(self, s, e):
        self.finished = True
        self.Close()

# -------------------------------------------------------------
# PLACE TAGS
# -------------------------------------------------------------
def place_tags(tag_data, use_leader, tag_symbol):
    placed = 0
    failed = 0
    errors = []

    with Transaction(doc, "Place Tags") as tx:
        tx.Start()

        if not tag_symbol.IsActive:
            tag_symbol.Activate()
            doc.Regenerate()

        for data in tag_data:
            try:
                tag = IndependentTag.Create(
                    doc,
                    view.Id,
                    data["reference"],
                    use_leader,
                    TagOrientation.Horizontal,
                    data["tag_point"]
                )

                tag.ChangeTypeId(tag_symbol.Id)
                placed += 1

            except Exception as ex:
                failed += 1
                errors.append(str(ex))

        tx.Commit()

    error_msg = ""
    if errors:
        error_msg = "\n\nErrors:\n" + "\n".join(errors[:3])

    MessageBox.Show(
        "Done!\n\nPlaced: {}\nFailed: {}{}".format(placed, failed, error_msg),
        "Result",
        MessageBoxButtons.OK,
        MessageBoxIcon.Information)

    return placed, failed

# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
def main():
    # Step 1 - Settings and tag family selection
    settings_form = SettingsForm()
    result = settings_form.ShowDialog()
    if str(result) != "OK":
        return

    use_leader = settings_form.use_leader
    tag_symbol = settings_form.selected_tag

    # Step 2 - Interactive loop
    tag_data    = []
    finish_form = FinishForm()
    finish_form.Show()

    MessageBox.Show(
        "Click an element, then click where you want the tag.\nRepeat for all elements.\nClick 'Finish - Place All Tags' when done.",
        "Instructions",
        MessageBoxButtons.OK,
        MessageBoxIcon.Information)

    while not finish_form.finished:
        try:
            ref = uidoc.Selection.PickObject(
                ObjectType.Element,
                "Select element")

            if ref is None:
                break

            tag_point = uidoc.Selection.PickPoint(
                "Click where you want the tag")

            if tag_point is None:
                break

            tag_data.append({
                "reference": ref,
                "tag_point": tag_point
            })

            finish_form.update_count(len(tag_data))
            Application.DoEvents()

        except OperationCanceledException:
            break
        except Exception as ex:
            break

    finish_form.Close()

    if not tag_data:
        MessageBox.Show("No elements selected.", "Warning",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning)
        return

    # Step 3 - Place all tags
    place_tags(tag_data, use_leader, tag_symbol)

main()
