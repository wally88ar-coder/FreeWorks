# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Rodeo a FreeCAD 1.1.4 (redo_links, #47): un objeto creado con una fórmula en el mismo paso,
después de Deshacer y Rehacer, sigue a la planilla que lee (cambio la planilla y cambia). Igual
con un objeto borrado y traído de vuelta con Deshacer. Sin pasos de deshacer nuevos. Además se
comprueba que FreeCAD solo (sin el rodeo) todavía tiene el error: el día que lo arreglen, esta
prueba avisa para sacar el rodeo."""

import FreeCAD  # noqa: E402

from comun import cerca  # noqa: E402


def armar(nombre):
    doc = FreeCAD.newDocument(nombre)
    doc.UndoMode = 1
    sh = doc.addObject("Spreadsheet::Sheet", "Hoja")
    sh.set("A1", "5")
    sh.setAlias("A1", "a")
    doc.recompute()
    doc.openTransaction("crear")
    caja = doc.addObject("Part::Box", "Caja")
    caja.setExpression("Length", "Hoja.a")
    doc.recompute()
    doc.commitTransaction()
    return doc, sh


def sigue(doc, sh, valor):
    sh.set("A1", str(valor))
    doc.recompute()
    return cerca(doc.getObject("Caja").Length.Value, valor)


def prueba():
    from swui.fork import redo_links

    # FreeCAD solo: el error sigue (si no, sacar el rodeo y esta parte); el entorno de pruebas
    # puede haberlo enganchado ya al cargar FreeWorks
    obs = redo_links._state.pop("obs", None)
    if obs is not None:
        FreeCAD.removeDocumentObserver(obs)
    doc, sh = armar("SinRodeo")
    doc.undo()
    doc.redo()
    doc.recompute()  # como Ctrl+Y en la ventana (sin esto, la caja todavía está para recalcular)
    assert not sigue(doc, sh, 8), "FreeCAD ya no pierde la dependencia al rehacer: sacar redo_links"
    FreeCAD.closeDocument(doc.Name)

    redo_links.install()
    # rehacer la creación
    doc, sh = armar("Rehacer")
    doc.undo()
    doc.redo()
    doc.recompute()  # como Ctrl+Y en la ventana (sin esto, la caja todavía está para recalcular)
    pasos = doc.UndoCount
    assert sigue(doc, sh, 8), "tras Rehacer, la caja no sigue a la planilla"
    assert doc.UndoCount == pasos, "el rodeo dejó pasos de deshacer"
    # deshacer un borrado
    doc.openTransaction("borrar")
    doc.removeObject("Caja")
    doc.commitTransaction()
    doc.undo()
    doc.recompute()
    assert sigue(doc, sh, 11), "tras deshacer el borrado, la caja no sigue a la planilla"
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
