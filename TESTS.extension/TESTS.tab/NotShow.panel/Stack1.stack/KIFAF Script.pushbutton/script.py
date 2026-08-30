# -*- coding: utf-8 -*-
import wpf
import os
from System.Windows import Window
from Autodesk.Revit.UI import TaskDialog
from pyrevit import script
from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory
from Autodesk.Revit.DB import BoundingBoxIsInsideFilter, Outline
from Autodesk.Revit.DB import Wall, Floor, Ceiling, FamilyInstance
from Autodesk.Revit.DB import CopyPasteOptions, ElementTransformUtils
from Autodesk.Revit.DB import ElementId, Transaction
from System.Collections.Generic import List as CList

doc   = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app   = __revit__.Application

#----------------------------------------------------------------------

class ScopeBoxTransfer(Window):
    def __init__(self):
        wpf.LoadComponent(self, os.path.join(os.path.dirname(__file__), "ui.xaml"))
        
        self.docs = list(app.Documents)
        for d in self.docs:
            self.combo_origem.Items.Add(d.Title)
            self.combo_destino.Items.Add(d.Title)
        
        self.combo_origem.SelectedIndex  = 0
        self.combo_destino.SelectedIndex = 0
        
        self.btn_proximo.Click  += self.proximo_click
        self.btn_executar.Click += self.executar_click

    def proximo_click(self, sender, args):
        indice_origem = self.combo_origem.SelectedIndex
        doc_origem    = self.docs[indice_origem]
        
        scopeboxes = FilteredElementCollector(doc_origem)\
                     .OfCategory(BuiltInCategory.OST_VolumeOfInterest)\
                     .ToElements()
        
        self.scopeboxes = list(scopeboxes)
        for sb in self.scopeboxes:
            self.combo_scopebox.Items.Add(sb.Name)
        self.combo_scopebox.SelectedIndex = 0
        
        from System.Windows import Visibility
        self.etapa1.Visibility = Visibility.Collapsed
        self.etapa2.Visibility = Visibility.Visible

    def executar_click(self, sender, args):
        self.selected_origem   = self.docs[self.combo_origem.SelectedIndex]
        self.selected_destino  = self.docs[self.combo_destino.SelectedIndex]
        self.selected_scopebox = self.scopeboxes[self.combo_scopebox.SelectedIndex]
        self.Close()

#----------------------------------------------------------------------

# abre a janela
janela = ScopeBoxTransfer()
janela.ShowDialog()

# usa as escolhas
doc_origem   = janela.selected_origem
doc_destino  = janela.selected_destino
sb_escolhida = janela.selected_scopebox

# bounding box da scope box na origem
bb      = sb_escolhida.get_BoundingBox(None)
outline = Outline(bb.Min, bb.Max)
filtro  = BoundingBoxIsInsideFilter(outline)

# recolher elementos da origem
walls    = FilteredElementCollector(doc_origem).WherePasses(filtro).OfClass(Wall).ToElements()
floors   = FilteredElementCollector(doc_origem).WherePasses(filtro).OfClass(Floor).ToElements()
ceilings = FilteredElementCollector(doc_origem).WherePasses(filtro).OfClass(Ceiling).ToElements()
loadable = FilteredElementCollector(doc_origem).WherePasses(filtro).OfClass(FamilyInstance).ToElements()
genericlist = list(walls) + list(floors) + list(ceilings) + list(loadable)

# encontrar scope box no destino com o mesmo nome
nome_sb     = sb_escolhida.Name
sbs_destino = FilteredElementCollector(doc_destino)\
              .OfCategory(BuiltInCategory.OST_VolumeOfInterest)\
              .ToElements()

sb_destino = None
for sb in sbs_destino:
    if sb.Name == nome_sb:
        sb_destino = sb
        break

if sb_destino is None:
    TaskDialog.Show("Erro", "Scope Box nao encontrada no destino!")

else:
    # recolher elementos no destino dentro da scope box
    bb_d      = sb_destino.get_BoundingBox(None)
    outline_d = Outline(bb_d.Min, bb_d.Max)
    filtro_d  = BoundingBoxIsInsideFilter(outline_d)

    walls_d    = FilteredElementCollector(doc_destino).WherePasses(filtro_d).OfClass(Wall).ToElements()
    floors_d   = FilteredElementCollector(doc_destino).WherePasses(filtro_d).OfClass(Floor).ToElements()
    ceilings_d = FilteredElementCollector(doc_destino).WherePasses(filtro_d).OfClass(Ceiling).ToElements()
    loadable_d = FilteredElementCollector(doc_destino).WherePasses(filtro_d).OfClass(FamilyInstance).ToElements()
    elementos_destino = list(walls_d) + list(floors_d) + list(ceilings_d) + list(loadable_d)

    with Transaction(doc_destino, "Substituir elementos Scope Box") as t:
        t.Start()

        # 1. renomeia tipos no destino para _TMP_
        tipos_tmp = {}
        for e in elementos_destino:
            tipo = doc_destino.GetElement(e.GetTypeId())
            if tipo is None:
                continue
            try:
                nome_actual = tipo.Name
                if not nome_actual.startswith("_TMP_"):
                    tmp_nome = "_TMP_" + nome_actual
                    tipo.Name = tmp_nome
                    tipos_tmp[tmp_nome] = tipo
            except:
                pass

        # 2. copia elementos da origem para o destino
        ids = CList[ElementId]([e.Id for e in genericlist])
        ElementTransformUtils.CopyElements(
            doc_origem,
            ids,
            doc_destino,
            None,
            CopyPasteOptions()
        )

        # 3. apaga _TMP_ sem instâncias
        for tmp_nome, tipo in tipos_tmp.items():
            try:
                doc_destino.Delete(tipo.Id)
            except:
                pass

        t.Commit()

    TaskDialog.Show("Concluido", "Elementos actualizados com sucesso!")