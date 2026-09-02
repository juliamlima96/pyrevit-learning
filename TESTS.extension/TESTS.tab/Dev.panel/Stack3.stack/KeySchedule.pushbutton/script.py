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
from Autodesk.Revit.UI import TaskDialog


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
key_sch_param_list = [] #lista de parametros da key schedule
schedule_definition = selected_schedule.Definition
for index in range(schedule_definition.GetFieldCount()):
    field = schedule_definition.GetField(index)
    if field.ParameterId:
        revit_param = doc.GetElement(field.ParameterId) #Garante que estamos pegando apenas parametros
        if revit_param:
            key_sch_param_list.append(revit_param)

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
excel_param_list = [] #lista de strings com os headres do Exel, deve corresponder aos parametros do Revit
for column in range(1, used_range.Columns.Count +1):
    excel_param_list.append(selected_worksheet.Cells(1,column).Value2)

#==================================================
#matching parameters in Excel and Revit
param_match_list = [] #lista de strings com parametros que existem dos dois lados
list_unmatched =[] #lista de strings que estão no excel, mas não estão no Revit

for e_param in excel_param_list:
    for r_param in key_sch_param_list:
        if r_param.Name.lower() == e_param.lower():
            param_match_list.append(e_param)
            break
    else:
        list_unmatched.append(e_param)

#Add key parameter to the list
param_match_list.append(key_parameter)

#==================================================
#dictionary for values
excel_data ={} #dicionário com os dados do excel
excel_key_elem =[] #lista com keys existentes no excel
for row in range(2, used_range.Rows.Count +1):
    row_data = {} #dicionário com valores decada linha de cada room do excel
    for column in range(1, used_range.Columns.Count +1):
        excel_param = selected_worksheet.Cells(1,column).Value2
        value = selected_worksheet.Cells(row,column).Value2

        if excel_param in param_match_list:
            row_data[excel_param] = value

    excel_data [selected_worksheet.Cells(row,key_column).Value2] = row_data
    excel_key_elem.append(selected_worksheet.Cells(row,key_column).Value2)
#==================================================
#find key values in key schedule in Revit
rev_key_elem = FilteredElementCollector(
    doc,
    selected_schedule.Id
).WhereElementIsNotElementType().ToElements() #lista de keys existentes no key parameter

#==================================================
#Matches between keys in excel and revit
key_matches = [] #lista de keys que existem no excel e no revit
key_unmatches = [] #lista de keys que existem no excel, mas não no revit

for k in excel_key_elem:
    for key in rev_key_elem:
        if k == key.Name:
            key_matches.append(k)
            break
    else:
        key_unmatches.append(k)

#==================================================


# ╔╦╗╦═╗╔═╗╔╗╔╔═╗╔═╗╔═╗╔╦╗╦╔═╗╔╗╔
#  ║ ╠╦╝╠═╣║║║╚═╗╠═╣║   ║ ║║ ║║║║
#  ╩ ╩╚═╩ ╩╝╚╝╚═╝╩ ╩╚═╝ ╩ ╩╚═╝╝╚╝
#====================================================================================================

t = Transaction(doc, "Update Parameters")
t.Start()
try:
    st1 = SubTransaction(doc) #change text parameters
    st1.Start()
    for key in rev_key_elem:

        #check if key exists in Excel
        if key.Name in key_matches:

            #find parameter in key
            for param in key.Parameters:

                #text param filter
                if param.StorageType == StorageType.String:
                    param_name = param.Definition.Name

                    #check if exists in excel
                    if param_name in excel_data[key.Name]:
                        excel_value = excel_data[key.Name][param_name]

                        #set parameter
                        param.Set(excel_value)
    st1.Commit()

    st2 =SubTransaction(doc) #change yes/no parameters
    st2.Start()
    for key in rev_key_elem:

        #check if key exists in Excel
        if key.Name in key_matches:

            #find parameter in key
            for param in key.Parameters:

                #yes/no param filter
                if param.Definition.GetDataType() == SpecTypeId.Boolean.YesNo:
                    param_name = param.Definition.Name

                    #check for excel
                    if param_name in excel_data[key.Name]:
                        excel_value = excel_data[key.Name][param_name]
                        #check yes/no:
                        if str(excel_value).lower() in ["yes","true"]:
                            excel_value = 1
                        elif str(excel_value).lower() in ["no","false"]:
                            excel_value = 0
                        else:
                            continue

                        #set parameter
                        param.Set(excel_value)

    st2.Commit()
    t.Commit()
except:
    t.RollBack()
#====================================================================================================
#final print
msg = "Parameters Updated"
if key_unmatches:
    msg += "\n\nThe following worksets were not found:\n- "
    msg += "\n- ".join(key_unmatches)

TaskDialog.Show("Task Completed", msg)


