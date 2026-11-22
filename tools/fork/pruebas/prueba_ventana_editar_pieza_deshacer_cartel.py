# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#113 (visto por el usuario el 21/11): editando una pieza dentro del ensamblaje, Extruir con croquis en la
cara de OTRO componente (círculo con la herramienta, Salir del croquis, Aceptar) y Ctrl+Z / Ctrl+Y con el TECLADO
y la ventana del ensamblaje al frente: deshace y rehace sin el cartel de FreeCAD "Hay transacciones de grupo...
Sí/No/Abort" (SW nunca pregunta), la extrusión se va y vuelve, y ningún componente se oculta (#108)."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from deshacer_comun import al_frente as _al_frente, atajo as _atajo, visibles as _visibles  # noqa: E402

V = FreeCAD.Vector





def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from croquis_esc_comun import clic, esc
    from swui import ribbon
    from swui.compat import QtCore, QtWidgets
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, (uno, dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    uno.Placement.Base = V(30, 20, 10)
    doc.recompute()
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.activeView()
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % uno.Name)
    FreeCADGui.runCommand("SWUI_EditPart")
    bombear(800)
    assert ep.editing(doc) is uno, "no entró a Editar pieza"
    pdoc = uno.LinkedObject.Document
    antes = _visibles(asm)
    yield 100

    traza("Extruir sobre la cara del otro, círculo, Salir del croquis, Aceptar")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % dos.Name)
    ribbon._run("PartDesign_Pad")
    bombear(3000)
    sk = getattr(gdoc.getInEdit(), "Object", None)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "Extruir no abrió el croquis"
    FreeCADGui.runCommand("Sketcher_CreateCircle")
    bombear(400)
    clic(vista, dos.Placement.multVec(V(30, 20, 20)))
    clic(vista, dos.Placement.multVec(V(36, 20, 20)))
    esc(vista.graphicsView().viewport())
    FreeCADGui.runCommand("Sketcher_LeaveSketch")
    bombear(2500)
    for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        b = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if b is not None and b.isVisible():
            b.click()
            break
    bombear(2000)
    pads = [o.Name for o in pdoc.Objects if o.TypeId == "PartDesign::Pad"]
    traza("  extrusiones en la pieza: %s; pasos pieza %s; ensamblaje %s" % (pads, pdoc.UndoNames[:6], doc.UndoNames[:6]))
    assert len(pads) == 2, "no quedó la extrusión nueva: %s" % pads
    yield 100

    traza("Ctrl+Z con el teclado, ensamblaje al frente")
    vista = _al_frente(doc)
    todos = []
    for n in range(1, 15):
        if not pdoc.UndoCount and not doc.UndoCount:
            break
        FreeCADGui.Selection.clearSelection()
        cart = _atajo(vista, QtCore.Qt.Key.Key_Z)
        todos += cart
        pads = [o.Name for o in pdoc.Objects if o.TypeId == "PartDesign::Pad"]
        traza("  Ctrl+Z %d: carteles %d; extrusiones %s; pasos pieza %s / ensamblaje %s; visibles %s"
              % (n, len(cart), pads, pdoc.UndoNames[:3], doc.UndoNames[:3], _visibles(asm)))
        for t in cart:
            traza("    cartel: %s" % t[:200].replace("\n", " "))
        assert _visibles(asm) == antes, "#108: Ctrl+Z %d ocultó un componente" % n
    assert len([o for o in pdoc.Objects if o.TypeId == "PartDesign::Pad"]) == 1, "Ctrl+Z no sacó la extrusión"
    assert not todos, "#113: Ctrl+Z mostró el cartel de FreeCAD: %s" % todos[0][:200]
    yield 100

    traza("Ctrl+Y con el teclado")
    todos = []
    for n in range(1, 8):
        cart = _atajo(vista, QtCore.Qt.Key.Key_Y)
        todos += cart
        pads = [o.Name for o in pdoc.Objects if o.TypeId == "PartDesign::Pad"]
        traza("  Ctrl+Y %d: carteles %d; extrusiones %s" % (n, len(cart), pads))
        if len(pads) == 2:
            break
    assert len([o for o in pdoc.Objects if o.TypeId == "PartDesign::Pad"]) == 2, "Ctrl+Y no trajo la extrusión"
    assert not todos, "#113: Ctrl+Y mostró el cartel de FreeCAD: %s" % todos[0][:200]
    assert _visibles(asm) == antes, "Ctrl+Y ocultó un componente"
    ep.stop(doc)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
