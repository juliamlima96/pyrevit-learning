# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")

from Autodesk.Revit.DB import *
from System.Collections.Generic import List


app = __revit__.Application


total_families = 0
total_renamed = 0

for fam_doc in app.Documents:

    if not fam_doc.IsFamilyDocument:
        continue

    total_families += 1

    patterns = FilteredElementCollector(fam_doc)\
        .OfClass(LinePatternElement)\
        .ToElements()

    t = Transaction(fam_doc, "Remove H+A_ from Line Patterns")
    t.Start()

    alterou = False

    for pattern in patterns:

        nome = pattern.Name

        if nome.startswith("H+A_"):

            novo_nome = nome[4:]

            # Evita conflito caso já exista um pattern com esse nome
            existe = False

            for p in patterns:
                if p.Id != pattern.Id and p.Name == novo_nome:
                    existe = True
                    break

            if existe:
                print("[" + fam_doc.Title + "] Não foi possível renomear '" +
                      nome + "' -> '" + novo_nome +
                      "' (já existe)")
                continue

            try:
                pattern.Name = novo_nome
                total_renamed += 1
                alterou = True

                print("[" + fam_doc.Title + "] " +
                      nome + " -> " + novo_nome)

            except Exception as ex:
                print("Erro em " + fam_doc.Title + ": " + str(ex))

    if alterou:
        t.Commit()
    else:
        t.RollBack()

print("")
print("===================================")
print("Famílias verificadas: " + str(total_families))
print("Line Patterns renomeados: " + str(total_renamed))