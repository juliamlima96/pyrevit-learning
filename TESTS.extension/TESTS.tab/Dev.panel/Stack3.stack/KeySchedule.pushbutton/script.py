  # -*- coding: utf-8 -*-

# ╦╔╦╗╔═╗╔═╗╦═╗╔╦╗╔═╗
# ║║║║╠═╝║ ║╠╦╝ ║ ╚═╗
# ╩╩ ╩╩  ╚═╝╩╚═ ╩ ╚═╝
#==================================================
#.NET Imports
import clr
clr.AddReference('System')
clr.AddReference('Microsoft.Office.Interop.Excel')

from Autodesk.Revit.DB import *
from pyrevit import forms, script
from Microsoft.Office.Interop import Excel


# ╦  ╦╔═╗╦═╗╦╔═╗╔╗ ╦  ╔═╗╔═╗
# ╚╗╔╝╠═╣╠╦╝║╠═╣╠╩╗║  ║╣ ╚═╗
#  ╚╝ ╩ ╩╩╚═╩╩ ╩╚═╝╩═╝╚═╝╚═╝
#==================================================
app    = __revit__.Application
uidoc  = __revit__.ActiveUIDocument
doc    = __revit__.ActiveUIDocument.Document #type:Document
excel_app = Excel.ApplicationClass()

# ╔╦╗╔═╗╦╔╗╔
# ║║║╠═╣║║║║
# ╩ ╩╩ ╩╩╝╚╝
#==================================================

#select schedule
selected_schedule = forms.select_schedules(multiple=False)
if not selected_schedule:
    script.exit()

if not selected_schedule.Definition.IsKeySchedule:
    forms.alert("Schedule not Key Schedule")
    script.exit()

#==================================================
#select excel file
excel_file = forms.pick_file(
    file_ext='xlsx',
)
if not excel_file:
    script.exit()

#==================================================
#key parameter
key_parameter = selected_schedule.KeyScheduleParameterName

#==================================================
#Worksheets
#list worksheets
workbook = excel_app.Workbooks.Open(excel_file)

#worksheet names
worksheet_list = []
for worksheet in workbook.Worksheets:
    worksheet_list.append(worksheet.Name)

selected_worksheet_name = forms.SelectFromList.show(
    sorted(worksheet_list),
    title="Choose Sheet",
    multiselect=False
)
if not selected_worksheet_name:
    script.exit()

#selected worksheet (object)
selected_worksheet = workbook.Worksheets[selected_worksheet_name]

#==================================================
#cells with information in worksheet
used_range = selected_worksheet.UsedRange

#find key parameter in excel
for column in range(1, used_range.Columns.Count + 1):
    cell_value = selected_worksheet.Cells(1, column).Value2

    if cell_value == key_parameter:
        key_column = column
        break
    else:
        forms.alert("Key Parameter not found on Excel File")
        script.exit()

#list with key parameter values
for row in range (2, used_range.Rows.Count + 1):
    key_value = selected_worksheet.Cells(row, key_column).Value2
    print(row, key_value)

print(column, cell_value)








