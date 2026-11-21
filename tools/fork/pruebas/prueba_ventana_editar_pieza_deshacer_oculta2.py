# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#108 (reproducido con el mouse el 21/11): Editar pieza con el comando, Extruir sobre la cara de OTRO componente
(croquis en esa cara), círculo con la herramienta (clics), "Salir del croquis" con el botón, Aceptar la extrusión y
Ctrl+Z varias veces: ningún Ctrl+Z oculta un componente."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _visibles(asm):
    return {o.Name: bool(o.Visibility) for o in asm.Group if o.TypeId in ("App::Link", "Assembly::AssemblyLink")}


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from croquis_esc_comun import clic
    from reglas_paneles import ctrl_z
    from swui import ribbon
    from swui.compat import QtWidgets
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
    FreeCADGui.runCommand("SWUI_EditPart")  # como el ícono de la bandeja
    bombear(800)
    assert ep.editing(doc) is uno, "no entró a Editar pieza"
    pdoc = uno.LinkedObject.Document
    antes = _visibles(asm)
    yield 100

    traza("Extruir sobre la cara del otro, círculo con la herramienta, Salir del croquis, Aceptar")
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
    from croquis_esc_comun import esc
    esc(vista.graphicsView().viewport())  # suelta la herramienta
    traza("  geometrías del croquis: %d" % sk.GeometryCount)
    FreeCADGui.runCommand("Sketcher_LeaveSketch")
    bombear(2500)
    for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        b = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if b is not None and b.isVisible():
            b.click()
            break
    bombear(2000)
    traza("  pasos: pieza %s; ensamblaje %s; visibles %s" % (pdoc.UndoNames[:8], doc.UndoNames[:5], _visibles(asm)))
    assert _visibles(asm) == antes, "algo quedó oculto antes de deshacer: %s" % _visibles(asm)
    yield 100

    traza("Ctrl+Z, con la ventana del ensamblaje al frente")
    for n in range(1, 10):
        if not pdoc.UndoCount and not doc.UndoCount:
            break
        FreeCADGui.Selection.clearSelection()
        ctrl_z(pdoc)
        bombear(800)
        vis = _visibles(asm)
        traza("  Ctrl+Z %d: pieza %s / ensamblaje %s -> visibles %s" % (n, pdoc.UndoNames[:2], doc.UndoNames[:2], vis))
        assert vis == antes, "#108: el Ctrl+Z %d ocultó un componente: %s" % (n, vis)
    ep.stop(doc)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
