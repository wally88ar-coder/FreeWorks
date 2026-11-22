# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#113 sobre archivos ABIERTOS DEL DISCO (una copia de las piezas de paso6: Conjunto con Placa, Taco fuera del
origen y Marco): Editar pieza en el Taco, Editar operación > Cancelar, croquis en la cara de arriba de la Placa con
una línea desde su vértice (se cierra), Extruir con croquis en esa cara (círculo, Salir, Aceptar) y Ctrl+Z con el
TECLADO hasta el principio: nunca aparece el cartel "Hay transacciones de grupo..." y ningún componente se oculta."""
TIPO = "completa"
import os  # noqa: E402
import shutil  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from deshacer_comun import atajo, cancelar_panel, con_menu, doble_clic, modificar, ventana_activa, visibles  # noqa: E402
from deshacer_comun import vista_activa_doc  # noqa: E402

V = FreeCAD.Vector
ORIGEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "piezas", "paso6")


def _prefijo(comp):
    """Camino desde el ensamblaje hasta el Cuerpo del componente ("Comp." o "Comp.Body.")."""
    lo = comp.LinkedObject
    if lo.TypeId == "PartDesign::Body":
        return comp.Name + ".", lo
    for o in lo.Group:
        if o.TypeId == "PartDesign::Body":
            return "%s.%s." % (comp.Name, o.Name), o
    raise AssertionError("sin Cuerpo en %s" % comp.Label)


def _cara_arriba(asm, comp):
    """(camino de la cara de arriba de la punta del Cuerpo, la cara en coordenadas del ensamblaje)."""
    import Part
    pre, body = _prefijo(comp)
    tip = body.Tip
    mejor = None
    for i in range(len(tip.Shape.Faces)):
        sub = "%s%s.Face%d" % (pre, tip.Name, i + 1)
        f = Part.getShape(asm, sub, needSubElement=True)
        if f.Surface.__class__.__name__ != "Plane":
            continue
        n = f.normalAt(0, 0)
        if n.z > 0.99 and (mejor is None or f.BoundBox.ZMax > mejor[1].BoundBox.ZMax):
            mejor = (sub, f)
    assert mejor is not None, "sin cara de arriba en %s" % comp.Label
    return mejor


def prueba():
    import FreeCADGui
    from croquis_esc_comun import clic, esc
    from menu_comun import derecho_vista
    from swui import ribbon
    from swui.compat import QtCore, QtWidgets
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    for n in os.listdir(ORIGEN):
        shutil.copy(os.path.join(ORIGEN, n), c)
    doc = FreeCAD.openDocument(os.path.join(c, "Conjunto.FCStd"))
    bombear(1500)
    asm = [o for o in doc.Objects if o.TypeId == "Assembly::AssemblyObject"][0]
    comps = {o.LinkedObject.Document.Name: o for o in asm.Group if o.TypeId == "App::Link"}
    traza("componentes: %s; documentos %s" % (sorted(comps), sorted(FreeCAD.listDocuments())))
    taco = [o for k, o in comps.items() if k.startswith("Taco")][0]
    placa = [o for k, o in comps.items() if k.startswith("Placa")][0]
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.activeView()
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(800)
    sub_taco, cara_taco = _cara_arriba(asm, taco)
    sub_placa, cara_placa = _cara_arriba(asm, placa)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub_taco)
    FreeCADGui.runCommand("SWUI_EditPart")
    bombear(1000)
    assert ep.editing(doc) is taco, "no entró a Editar pieza"
    pdoc = taco.LinkedObject.Document
    antes = visibles(asm)
    traza("  ventanas %s; pasos pieza %s / ensamblaje %s" % (ventana_activa(), pdoc.UndoNames[:3], doc.UndoNames[:3]))
    yield 100

    traza("Editar operación > Cancelar")
    FreeCADGui.Selection.clearSelection()
    centro = cara_taco.CenterOfMass
    vis, ok = con_menu(derecho_vista(centro), "Editar operación")
    bombear(1500)
    assert ok, "no estaba Editar operación: %s" % vis
    assert cancelar_panel(), "no encontré Cancelar"
    bombear(1500)
    traza("  pasos pieza %s / ensamblaje %s" % (pdoc.UndoNames[:4], doc.UndoNames[:4]))
    yield 100

    traza("croquis en la cara de arriba de la Placa, línea desde su vértice, cerrar")
    bb = cara_placa.BoundBox
    esquina = V(bb.XMin, bb.YMin, bb.ZMax)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub_placa)
    ribbon._run("PartDesign_NewSketch")
    bombear(3000)
    sk = getattr(gdoc.getInEdit(), "Object", None)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "no abrió el croquis"
    FreeCADGui.runCommand("Sketcher_CreateLine")
    bombear(400)
    clic(vista, esquina)
    clic(vista, esquina + V(12, 8, 0))
    vpw = vista.graphicsView().viewport()
    esc(vpw)
    traza("  geometrías %d; pasos pieza %s / ensamblaje %s" % (sk.GeometryCount, pdoc.UndoNames[:4], doc.UndoNames[:4]))
    if os.environ.get("FW_CIERRE", "esc") == "esc":
        FreeCADGui.Selection.clearSelection()
        esc(vpw)  # como el usuario (#111): Esc sin nada elegido cierra el croquis
        bombear(2500)
        if getattr(gdoc.getInEdit(), "Object", None) is sk:
            FreeCADGui.runCommand("Sketcher_LeaveSketch")
    else:
        FreeCADGui.runCommand("Sketcher_LeaveSketch")
    bombear(2500)
    traza("  cerrado; pasos pieza %s / ensamblaje %s; ventana %s" % (pdoc.UndoNames[:5], doc.UndoNames[:5],
                                                                     ventana_activa()))
    yield 100

    traza("Extruir sobre la cara de la Placa, círculo, Salir del croquis, Aceptar")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub_placa)
    ribbon._run("PartDesign_Pad")
    bombear(3000)
    sk2 = getattr(gdoc.getInEdit(), "Object", None)
    assert sk2 is not None and sk2.TypeId == "Sketcher::SketchObject", "Extruir no abrió el croquis"
    centro_c = V(bb.XMax - 10, bb.YMin + 10, bb.ZMax)
    FreeCADGui.runCommand("Sketcher_CreateCircle")
    bombear(400)
    clic(vista, centro_c)
    clic(vista, centro_c + V(4, 0, 0))
    esc(vpw)
    FreeCADGui.runCommand("Sketcher_LeaveSketch")
    bombear(2500)
    for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        b = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if b is not None and b.isVisible():
            b.click()
            break
    bombear(2500)
    otros = {n: FreeCAD.getDocument(n).UndoNames[:4] for n in FreeCAD.listDocuments() if n not in (doc.Name, pdoc.Name)}
    traza("  pasos pieza %s / ensamblaje %s / otros %s; ventana %s; activo %s" % (
        pdoc.UndoNames[:8], doc.UndoNames[:8], otros, ventana_activa(), FreeCAD.ActiveDocument.Name))
    yield 100

    if os.environ.get("FW_MODIFICAR", "1") == "1":
        from swui.fork import instant_dims as idm
        traza("doble clic en el Taco y Modificar la primera cota")
        doble_clic(vista, cara_taco.CenterOfMass)
        assert idm.shown(), "el doble clic no mostró cotas"
        boton, cota = idm._state["labels"][0]
        traza("  cota '%s'" % boton.text())
        modificar(idm, str(float(boton.text().replace(",", ".").split()[0].lstrip("Ø")) + 5))
        idm.hide()
        bombear(500)
        traza("  pasos pieza %s / ensamblaje %s; vista activa %s" % (pdoc.UndoNames[:4], doc.UndoNames[:4],
                                                                     vista_activa_doc()))
        yield 100

    traza("Ctrl+Z con el teclado hasta el principio (sin elegir ventana)")
    todos = []
    for n in range(1, 20):
        if not pdoc.UndoCount:
            break
        cart = atajo(vista, QtCore.Qt.Key.Key_Z)
        todos += cart
        traza("  Ctrl+Z %d: carteles %d; pasos pieza %s / ensamblaje %s; ventana %s / %s" % (
            n, len(cart), pdoc.UndoNames[:3], doc.UndoNames[:3], ventana_activa(), vista_activa_doc()))
        for t in cart:
            traza("    cartel: %s" % t[:250].replace("\n", " "))
        assert visibles(asm) == antes, "#108: Ctrl+Z %d ocultó un componente: %s" % (n, visibles(asm))
    assert not todos, "#113: Ctrl+Z mostró el cartel de FreeCAD: %s" % todos[0][:200]
    ep.stop(doc)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
