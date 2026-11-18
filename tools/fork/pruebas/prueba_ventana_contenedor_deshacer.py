# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Revisión del 17/11 (hallazgo 12) y del 18/11 (hallazgo 2 y segunda pasada): en una pieza con el contenedor de
FreeWorks (varios Cuerpos), un Cuerpo nuevo del botón Cuerpo entra al contenedor en el MISMO paso de deshacer que lo
crea: un solo Ctrl+Z lo borra (como SW) y Ctrl+Y lo trae ya adentro del contenedor, sin abrir un paso nuevo (con
otro paso más por rehacer detrás, que no se pierde). Un Cuerpo que el código pone en una carpeta al crearlo (miembros
de soldadas) queda en la carpeta y la carpeta en el contenedor (como lo arma FreeCAD). Pegar una pieza con su
Cuerpo deja el Cuerpo dentro de la pieza pegada. Un Cuerpo creado sin paso abierto entra en un paso propio."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402


def _cuerpos(doc):
    return set(o.Name for o in doc.Objects if o.TypeId == "PartDesign::Body")


def prueba():
    import FreeCADGui
    from reglas_paneles import ctrl_y, ctrl_z
    from swui.fork import part_container as pc
    doc = FreeCAD.newDocument("Contenedor")
    for nombre in ("Uno", "Dos"):
        b = doc.addObject("PartDesign::Body", nombre)
        caja = b.newObject("PartDesign::AdditiveBox", "Caja" + nombre)
        caja.Length = 10
    doc.recompute()
    parte = pc.wrap(doc, save=False)
    bombear(500)
    FreeCADGui.getDocument(doc.Name).activeView()
    yield 100

    traza("Cuerpo nuevo (botón) y una operación después")
    antes = _cuerpos(doc)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.runCommand("PartDesign_Body")
    bombear(1500)
    nuevos = _cuerpos(doc) - antes
    assert len(nuevos) == 1, "no se creó el Cuerpo: %s" % nuevos
    cuerpo = nuevos.pop()
    assert doc.getObject(cuerpo) in parte.Group, "el Cuerpo nuevo no entró al contenedor"
    traza("  pasos de deshacer: %s" % doc.UndoNames[:3])
    # otro paso detrás, para que al rehacer quede algo más por rehacer
    doc.openTransaction("Largo")
    doc.getObject("CajaUno").Length = 15
    doc.commitTransaction()
    doc.recompute()
    pasos = doc.UndoCount
    yield 100

    traza("deshacer y rehacer")
    ctrl_z(doc)
    bombear(600)
    ctrl_z(doc)
    bombear(600)
    assert doc.getObject(cuerpo) is None, "dos Ctrl+Z (largo y Cuerpo) no borraron el Cuerpo: %s" % doc.UndoNames[:3]
    assert doc.RedoCount >= 2, "no quedaron los dos pasos para rehacer: %s" % doc.RedoNames[:3]
    rehacer = doc.RedoCount
    ctrl_y(doc)
    bombear(1200)  # el temporizador del contenedor tiene que haber corrido
    traza("  rehacer: %s -> %s, %s" % (rehacer, doc.RedoCount, doc.RedoNames[:3]))
    assert doc.getObject(cuerpo) is not None, "Ctrl+Y no trajo el Cuerpo"
    assert doc.getObject(cuerpo) in parte.Group, "Ctrl+Y trajo el Cuerpo fuera del contenedor"
    assert doc.RedoCount == rehacer - 1, "Rehacer abrió un paso nuevo y se perdió lo que quedaba por rehacer: %s" % (
        doc.RedoNames[:3],)
    ctrl_y(doc)
    bombear(600)
    assert doc.getObject("CajaUno").Length.Value == 15, "se perdió el paso de después"
    assert doc.UndoCount == pasos, "rehacer todo no volvió a los mismos pasos: %s vs %s" % (doc.UndoCount, pasos)
    yield 100

    traza("Cuerpo puesto en una carpeta por el código (como los miembros de soldadas)")
    doc.openTransaction("Miembro")
    m = doc.addObject("PartDesign::Body", "Miembro")
    carpeta = doc.addObject("App::DocumentObjectGroup", "Miembros")
    carpeta.addObject(m)
    doc.commitTransaction()
    bombear(800)
    doc.recompute()
    # lo nativo de FreeCAD: el Cuerpo en la carpeta, y la pieza lista la carpeta Y lo que tiene adentro
    assert m.getParentGroup() is carpeta, "el miembro no quedó en la carpeta"
    assert m.getParentGeoFeatureGroup() is parte and carpeta.getParentGeoFeatureGroup() is parte,         "la carpeta no entró al contenedor"
    assert [o.Name for o in m.InList if o.hasExtension("App::GroupExtension")].count("Miembros") == 1
    yield 100

    traza("pegar una pieza con su Cuerpo")
    otra = doc.addObject("App::Part", "Otra")
    adentro = doc.addObject("PartDesign::Body", "Adentro")
    otra.addObject(adentro)
    doc.recompute()
    bombear(600)
    antes = set(o.Name for o in doc.Objects)
    doc.openTransaction("Pegar")
    doc.copyObject(otra, True)
    doc.commitTransaction()
    bombear(800)
    copia = [doc.getObject(n) for n in set(o.Name for o in doc.Objects) - antes]
    partes = [o for o in copia if o.TypeId == "App::Part"]
    cuerpos = [o for o in copia if o.TypeId == "PartDesign::Body"]
    assert len(partes) == 1 and len(cuerpos) == 1, "la copia: %s" % [o.Name for o in copia]
    assert cuerpos[0] in partes[0].Group, "el Cuerpo pegado no quedó en su pieza: %s" % [
        o.Name for o in cuerpos[0].InList]
    yield 100

    traza("Cuerpo sin paso abierto: entra en un paso propio")
    undo = doc.UndoCount
    suelto = doc.addObject("PartDesign::Body", "Suelto")
    bombear(800)
    assert suelto in parte.Group, "el Cuerpo sin paso no entró al contenedor"
    assert doc.UndoCount == undo + 1, "no quedó en un paso propio: %s" % doc.UndoNames[:3]
    FreeCAD.closeDocument(doc.Name)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
