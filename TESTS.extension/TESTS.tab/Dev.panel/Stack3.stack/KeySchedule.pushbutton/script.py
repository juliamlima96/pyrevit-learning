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
#key schedule parameters extraction

#key parameter
key_parameter = selected_schedule.KeyScheduleParameterName

#all parameters
key_sch_list = []
schedule_definition = selected_schedule.Definition
for index in range(schedule_definition.GetFieldCount()):
    field = schedule_definition.GetField(index)
    revit_param = doc.GetElement(field.ParameterId)
    if revit_param:
        key_sch_list.append(revit_param)

#==================================================
#Excel Worksheets
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
#parameters in excel
#cells with information in worksheet
used_range = selected_worksheet.UsedRange

#find key parameter in excel
key_column = None
for column in range(1, used_range.Columns.Count + 1):
    cell_value = selected_worksheet.Cells(1, column).Value2

    if cell_value == key_parameter:
        key_column = column
        break
if key_column is None:
    forms.alert("Key Parameter not found on Excel File")
    script.exit()

#Excel Parameters List
excel_param_list = []
for column in range(1, used_range.Columns.Count +1):
    excel_param_list.append(selected_worksheet.Cells(1,column).Value2)

#==================================================
#matching parameters in Excel and Revit
param_match_list = []
list_unmatched =[]

for e_param in excel_param_list:
    for r_param in key_sch_list:
        if r_param.Name.lower() == e_param.lower():
            param_match_list.append(e_param)
            break
    else:
        list_unmatched.append(e_param)

#Add key parameter to the list
param_match_list.append(key_parameter)
#==================================================
#dictionary for values
excel_data ={}

for row in range(2, used_range.Rows.Count +1):
    row_data = {}
    for column in range(1, used_range.Columns.Count +1):
        excel_param = selected_worksheet.Cells(1,column).Value2
        value = selected_worksheet.Cells(row,column).Value2

        if excel_param in param_match_list:
            row_data[excel_param] = value

    excel_data [selected_worksheet.Cells(row,key_column).Value2] = row_data

print(selected_schedule.GetType())
print(selected_schedule.Name)




