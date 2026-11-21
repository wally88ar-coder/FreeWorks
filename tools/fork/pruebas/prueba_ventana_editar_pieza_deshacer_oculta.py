# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#108 (visto con el mouse el 18/11): editando una pieza dentro del ensamblaje, después de un croquis top-down (en
la cara de otro componente, con una arista de ese otro traída) y de Extruir sobre esa cara con un círculo, apretar
Ctrl+Z hasta que no quede nada por deshacer NUNCA oculta un componente (ni el editado ni los otros): deshacer no
cambia lo que se ve. Ctrl+Y de todo vuelve a la extrusión, también a la vista."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _visibles(asm):
    return {o.Name: bool(o.Visibility) for o in asm.Group if o.TypeId in ("App::Link", "Assembly::AssemblyLink")}


def prueba():
    import FreeCADGui
    import Part
    import piezas_editar as pe
    from reglas_paneles import ctrl_y, ctrl_z
    from swui import ribbon
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, (uno, dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    uno.Placement.Base = V(30, 20, 10)
    doc.recompute()
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    assert ep.start(uno, warn=False)
    bombear(500)
    pdoc = uno.LinkedObject.Document
    antes = _visibles(asm)
    pasos0 = pdoc.UndoCount
    traza("visibles al empezar: %s" % antes)
    yield 100

    traza("croquis top-down con una arista traída del otro")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % dos.Name)
    ribbon._run("PartDesign_NewSketch")
    bombear(2000)
    sk = getattr(gdoc.getInEdit(), "Object", None)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject"
    # como con el mouse: clic en una arista del otro (se trae sola), Línea que empieza en un vértice del otro, y
    # salir del croquis con Esc
    from croquis_esc_comun import clic, esc
    vista = gdoc.activeView()
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    vpw = vista.graphicsView().viewport()
    clic(vista, dos.Placement.multVec(V(0, 20, 20)))
    traza("  externas: %s" % (sk.ExternalGeometry,))
    FreeCADGui.runCommand("Sketcher_CreateLine")
    bombear(400)
    clic(vista, dos.Placement.multVec(V(60, 40, 20)))  # trae el vértice
    # la línea que quedó SIN relación con el vértice (con el mouse de Claude no hubo preselección)
    sk.addGeometry(Part.LineSegment(V(-20, -20, 0), V(-5, -10, 0)))
    bombear(200)
    esc(vpw)  # corta la Línea
    FreeCADGui.Selection.clearSelection()
    esc(vpw)  # sale del croquis
    bombear(1000)
    traza("  en edición: %s; geometrías %d" % (getattr(gdoc.getInEdit(), "Object", None), sk.GeometryCount))
    if gdoc.getInEdit() is not None:
        ec.reset_edit(pdoc)
        bombear(800)
    traza("  visibles: %s" % _visibles(asm))
    yield 100

    traza("Extruir sobre la cara del otro con un círculo")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % dos.Name)
    ribbon._run("PartDesign_Pad")
    bombear(2000)
    sk2 = getattr(gdoc.getInEdit(), "Object", None)
    assert sk2 is not None and sk2.TypeId == "Sketcher::SketchObject", "Extruir no abrió el croquis: %s" % sk2
    sk2.addGeometry(Part.Circle(V(10, 10, 0), V(0, 0, 1), 5))
    pdoc.recompute()
    ec.reset_edit(pdoc)
    bombear(2000)
    if FreeCADGui.Control.activeDialog():  # el panel de la extrusión: Aceptar
        from swui.compat import QtWidgets
        for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
            b = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
            if b is not None and b.isVisible():
                b.click()
                break
        bombear(1500)
    traza("  pasos de la pieza: %s; visibles: %s" % (pdoc.UndoNames[:8], _visibles(asm)))
    assert _visibles(asm) == antes, "algo quedó oculto antes de deshacer: %s" % _visibles(asm)
    yield 100

    traza("Ctrl+Z hasta el principio")
    n = 0
    while pdoc.UndoCount > pasos0 and n < 15:
        FreeCAD.setActiveDocument(doc.Name)
        ctrl_z(pdoc)
        bombear(600)
        n += 1
        vis = _visibles(asm)
        traza("  Ctrl+Z %d: %s -> visibles %s" % (n, pdoc.UndoNames[:2], vis))
        assert vis == antes, "#108: el Ctrl+Z %d ocultó un componente: %s" % (n, vis)
    yield 100

    traza("Ctrl+Y de todo")
    for i in range(n):
        ctrl_y(pdoc)
        bombear(600)
        assert _visibles(asm) == antes, "Ctrl+Y %d ocultó un componente: %s" % (i + 1, _visibles(asm))
    ep.stop(doc)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
