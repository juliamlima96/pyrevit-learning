# -*- coding: utf-8 -*-
from Autodesk.Revit.UI import TaskDialog
doc   = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app   = __revit__.Application
# imprimir nome de ficheiro 
nome= doc. Title
caminho= doc.PathName
TaskDialog.Show ("informação", "o nome do ficheiro é: "+ nome + "\n" + "o caminho do ficheiro é: " + caminho)
# teste oeiwtoiweijweotjwojtropw
# teste 1236546946
# teste 1236546946ertetet