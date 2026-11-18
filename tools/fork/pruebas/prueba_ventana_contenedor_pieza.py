# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#97 y Editar pieza = pieza (17/11): una pieza de varios Cuerpos (soldadura) con solo ABRIRLA no cambia ni se
guarda (antes: Plano nuevo consultaba pick_objects todo el tiempo y la pasaba a contenedor y la guardaba);
al INSERTARLA en un ensamblaje entra entera por su contenedor Parte. Editando una pieza de UN Cuerpo, Croquis 3D
pasa la pieza a contenedor ANTES (paso de deshacer propio): cancelado, el componente sigue sano (antes apuntaba a
algo borrado) y se puede seguir eligiendo en la pieza; Cuerpo nuevo va dentro del contenedor, en la pieza, y se
ve en el componente; Ctrl+Z en el ensamblaje lo deshace y se sigue editando."""
TIPO = "completa"
import os  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402


def _al_frente(doc):
    import FreeCADGui
    from swui.compat import QtWidgets
    FreeCAD.setActiveDocument(doc.Name)
    vista = FreeCADGui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor")[0]
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in area.subWindowList():
        if sub.isAncestorOf(vista.graphicsView()):
            area.setActiveSubWindow(sub)
    bombear(500)


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from reglas_paneles import tocar
    from swui import ribbon
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    from swui.fork import part_container as pc
    c = carpeta_temporal()

    traza("paso 1")
    # 1) abrir una soldadura (varios Cuerpos) no la cambia ni la guarda
    marco = pe.soldadura(c)
    hora = os.path.getmtime(marco)
    d = FreeCAD.openDocument(marco)
    _al_frente(d)
    bombear(2500)  # tiempo para que la cinta y los menús consulten si sus botones están activos
    assert pc.container(d) is None, "abrir la soldadura la pasó a contenedor"
    assert os.path.getmtime(marco) == hora, "abrir la soldadura la guardó"
    FreeCAD.closeDocument(d.Name)
    yield 100

    traza("paso 2")
    # 2) insertarla en un ensamblaje: entra entera por su contenedor
    bloque = pe.bloque(c)
    doc, asm, comps = pe.ensamblaje([bloque, marco])
    assert len(comps) == 2, "la soldadura entró en %d componentes" % (len(comps) - 1)
    pm = comps[1].LinkedObject
    assert pm.TypeId == "App::Part" and hasattr(pm, pc.MARK), "la soldadura no entró por su contenedor: %s" % pm.TypeId
    assert len([o for o in pm.Document.Objects if o.TypeId == "PartDesign::Body"]) >= 2
    yield 100

    traza("paso 3")
    # 3) editando el bloque (un Cuerpo): Croquis 3D y cancelar -> componente sano, se sigue eligiendo
    uno = comps[0]
    _al_frente(doc)
    assert ep.start(uno, warn=False)
    bombear(400)
    pdoc = uno.LinkedObject.Document
    FreeCADGui.Selection.clearSelection()
    ribbon._run("SWUI_Sketch3D")
    bombear(1300)
    tocar(rechazar=True)
    bombear(600)
    assert uno.LinkedObject is not None and uno.LinkedObject.isValid(), "el componente quedó apuntando a algo roto"
    assert uno.LinkedObject.TypeId == "App::Part", "no pasó a contenedor: %s" % uno.LinkedObject.TypeId
    assert ep.editing(doc) is uno, "Croquis 3D sacó de Editar pieza"
    assert ec.select(pdoc.getObject("Extruir"), "Face6"), "después de pasar a contenedor no se puede elegir la cara"
    assert not [o for o in pdoc.Objects if o.TypeId == "App::DocumentObjectGroup"], "quedó el grupo del croquis 3D"
    yield 100

    traza("paso 4")
    # 4) Cuerpo nuevo: en la pieza, dentro del contenedor, visible en el componente; Ctrl+Z lo deshace
    FreeCADGui.Selection.clearSelection()
    antes = len([o for o in pdoc.Objects if o.TypeId == "PartDesign::Body"])
    ribbon._run("PartDesign_Body")
    bombear(1300)
    nuevos = [o for o in pdoc.Objects if o.TypeId == "PartDesign::Body"]
    assert len(nuevos) == antes + 1, "Cuerpo no creó un Cuerpo en la pieza"
    nuevo = nuevos[-1]
    assert nuevo.getParentGeoFeatureGroup() is uno.LinkedObject, "el Cuerpo nuevo quedó fuera del contenedor"
    assert not [o for o in doc.Objects if o.TypeId == "PartDesign::Body"], "el Cuerpo nuevo fue al ensamblaje"
    assert ep.editing(doc) is uno, "Cuerpo nuevo sacó de Editar pieza"
    traza("  pasos: pieza %s, ensamblaje %s" % (pdoc.UndoNames[:3], doc.UndoNames[:3]))
    FreeCADGui.runCommand("Std_Undo")
    bombear(800)
    assert len([o for o in pdoc.Objects if o.TypeId == "PartDesign::Body"]) == antes, "Ctrl+Z no deshizo el Cuerpo"
    assert uno.LinkedObject is not None and uno.LinkedObject.isValid()
    ep.stop(doc)
    bombear(300)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
