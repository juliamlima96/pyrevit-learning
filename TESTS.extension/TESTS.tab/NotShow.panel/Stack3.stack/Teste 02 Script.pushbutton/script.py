# -*- coding: utf-8 -*-
from Autodesk.Revit.UI import TaskDialog
from pyrevit import script 
from Autodesk.Revit.DB import FilteredElementCollector, Wall, Floor
from Autodesk.Revit.DB import BuiltInCategory

doc   = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app   = __revit__.Application


# listar familias no modelo walls e floors 

"""
walls=FilteredElementCollector (doc)\
    .OfClass(Wall)\
    .ToElements()
floors=FilteredElementCollector (doc)\
    .OfClass(Floor)\
    .ToElements()
"""

"""walls=FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Walls).ToElements()
floors=FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Floors).ToElements()
doors=FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Doors).ToElements()
TaskDialog.Show("Elementos no Modelo",
    "Walls: "  + str(len(walls))  + "\n" +
    "Floors: " + str(len(floors)) + "\n" +
    "Doors: "  + str(len(doors)))"""

#abre a janela 
"""output=script.get_output()
#imprime o titulo
output.print_md("Elementos no Modelo")
output.print_md("Walls:" + str(len(walls)))
output.print_md("Floors: " + str(len(floors)))
output.print_md("Doors: " + str(len(doors)))"""

# Listar familias nomes da familias 

#walls=FilteredElementCollector(doc).OfClass(Wall).ToElements()
#floors=FilteredElementCollector(doc).OfClass(Floor).ToElements()
#lista=""
# Adiciona walls
#lista=lista +"Walls Count:\n"
"""for w in walls:
    lista=lista + w.Name + "\n"
#TaskDialog.Show("Lista de Elementos",(lista))
#Adiciona floors
lista=lista +"Floors Count:\n"
for f in floors:
    lista=lista + f.Name + "\n"""
# pegar paredes   
"""nome_walls=[]
for w in walls:
    if w.Name not in nome_walls:
        nome_walls.append(w.Name)
#pegar floors
nome_floors=[]
for f in floors: 
    if f.Name not in nome_floors:
        nome_floors.append(f.Name)
# montar lista
lista=""
lista= "Walls:\n"
for n in nome_walls:
    lista=lista + n + "\n"
lista= lista + "Floors:\n"
for n in nome_floors:  
    lista=lista + n + "\n"
TaskDialog.Show("Lista de Elementos",(lista))"""


#Scope Box

#Sb=FilteredElementCollector(doc).OfClass(ScopeBox).ToElements()
scopebox=FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_VolumeOfInterest).ToElements()

#Montars a lista
lista="Scope Boxes:\n"
for sb in scopebox:
    lista= lista + sb.Name + "\n"
TaskDialog.Show("Lista de Elementos",(lista))