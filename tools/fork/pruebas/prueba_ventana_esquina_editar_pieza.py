# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Esquina de confirmación editando una pieza dentro del ensamblaje (21/11, partes D y F), con clics de verdad:
D) Volver al ensamblaje en la esquina (la barra vieja no aparece); el clic sale de Editar pieza.
F) Anidados (decidido: se ve solo lo de más adentro): croquis dentro de Editar pieza -> Salir/Cancelar croquis;
   panel (Extruir, Editar operación) -> ✓/✗; al cerrarlos vuelve Volver al ensamblaje.
   Cancelar croquis de un croquis nuevo en la cara de OTRO componente no deja nada en la pieza (ni el croquis ni la
   referencia a la cara) y Ctrl+Z después no lo trae; ✗ en Editar operación no deja nada modificado.
Con la esquina apagada vuelve la barra "Editando pieza — Salir"; prendida, se va."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from deshacer_comun import al_frente, atajo, cancelar_panel, con_menu, visibles  # noqa: E402
from esquina_comun import claves, clic_boton  # noqa: E402

V = FreeCAD.Vector


def _barra():
    import FreeCADGui
    from swui.compat import QtWidgets
    return [w for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QFrame, "SWUI_edit_part_bar") if w.isVisible()]


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from croquis_esc_comun import clic, esc
    from menu_comun import derecho_vista
    from swui import ribbon
    from swui.compat import QtCore
    from swui.fork import confirm_corner as cc
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, (uno, dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    uno.Placement.Base = V(30, 20, 10)
    doc.recompute()
    vista = al_frente(doc)
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    assert claves() == [], "sin editar, la esquina tiene %s" % claves()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % uno.Name)
    FreeCADGui.runCommand("SWUI_EditPart")
    bombear(800)
    assert ep.editing(doc) is uno, "no entró a Editar pieza"
    pdoc = uno.LinkedObject.Document
    gdoc = FreeCADGui.getDocument(doc.Name)
    assert claves() == ["back_assembly"], "editando, la esquina tiene %s" % claves()
    assert not _barra(), "con la esquina, igual aparece la barra vieja"
    vis = visibles(asm)
    yield 100

    traza("F) croquis nuevo en la cara del otro, línea desde su vértice, Cancelar croquis: no queda nada")
    objetos = set(o.Name for o in pdoc.Objects)
    doc.clearUndos()  # lo armado por la prueba (Insertar componente) no es del usuario: Ctrl+Z no tiene que llegar ahí
    pdoc.clearUndos()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % dos.Name)
    ribbon._run("PartDesign_NewSketch")
    bombear(3000)
    sk = getattr(gdoc.getInEdit(), "Object", None)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "no abrió el croquis"
    assert claves() == ["exit_sketch", "cancel_sketch"], "croquis dentro de Editar pieza: %s" % claves()
    FreeCADGui.runCommand("Sketcher_CreateLine")
    bombear(300)
    vpw = vista.graphicsView().viewport()
    clic(vista, dos.Placement.multVec(V(0, 0, 20)))
    clic(vista, dos.Placement.multVec(V(12, 30, 20)))
    esc(vpw)
    traza("  pasos pieza %s" % pdoc.UndoNames[:5])
    clic_boton("cancel_sketch")
    sobran = [o.Label for o in pdoc.Objects if o.Name not in objetos]
    traza("  quedaron %s; pasos pieza %s / ensamblaje %s" % (sobran, pdoc.UndoNames[:3], doc.UndoNames[:3]))
    assert not sobran, "Cancelar croquis dejó en la pieza: %s" % sobran
    assert not pdoc.UndoNames and not doc.UndoNames, "la pila no volvió a vacía: %s / %s" % (pdoc.UndoNames, doc.UndoNames)
    assert ep.editing(doc) is uno, "Cancelar croquis sacó de Editar pieza"
    assert claves() == ["back_assembly"], "después de Cancelar croquis la esquina tiene %s" % claves()
    atajo(vista, QtCore.Qt.Key.Key_Z)
    traza("  después de Ctrl+Z: pasos pieza %s / ensamblaje %s" % (pdoc.UndoNames[:3], doc.UndoNames[:3]))
    assert not [o.Label for o in pdoc.Objects if o.Name not in objetos], "Ctrl+Z trajo el croquis cancelado"
    assert visibles(asm) == vis, "Ctrl+Z ocultó un componente"
    yield 100

    traza("F) Extruir en la cara del otro: Salir del croquis y ✓ en la esquina")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % dos.Name)
    ribbon._run("PartDesign_Pad")
    bombear(3000)
    sk2 = getattr(gdoc.getInEdit(), "Object", None)
    assert sk2 is not None and sk2.TypeId == "Sketcher::SketchObject", "Extruir no abrió el croquis"
    FreeCADGui.runCommand("Sketcher_CreateCircle")
    bombear(300)
    clic(vista, dos.Placement.multVec(V(45, 10, 20)))
    clic(vista, dos.Placement.multVec(V(50, 10, 20)))
    esc(vpw)
    clic_boton("exit_sketch")
    bombear(1500)
    assert claves() == ["ok", "cancel"], "con el panel de Extruir la esquina tiene %s" % claves()
    clic_boton("ok")
    pads = [o for o in pdoc.Objects if o.TypeId == "PartDesign::Pad" and o.Name != "Extruir"]
    assert len(pads) == 1 and pads[0].isValid(), "✓ no hizo la extrusión: %s" % [o.Name for o in pads]
    assert claves() == ["back_assembly"], "después de ✓ la esquina tiene %s" % claves()
    yield 100

    traza("F) Editar operación y ✗: nada modificado")
    gpdoc = FreeCADGui.getDocument(pdoc.Name)
    mod = (gdoc.Modified, gpdoc.Modified, pdoc.UndoCount, doc.UndoCount)
    FreeCADGui.Selection.clearSelection()
    vistos, ok = con_menu(derecho_vista(uno.Placement.multVec(V(50, 30, 20))), "Editar operación")
    bombear(1500)
    if not ok:  # por si el menú no la trae (otra cara bajo el mouse): con la función
        ep.open_in_assembly(asm, "%s.Extruir.Face6" % uno.Name)
        bombear(1500)
    assert claves() == ["ok", "cancel"], "Editar operación: la esquina tiene %s" % claves()
    clic_boton("cancel")
    ahora = (gdoc.Modified, gpdoc.Modified, pdoc.UndoCount, doc.UndoCount)
    traza("  antes %s, después %s" % (mod, ahora))
    assert ahora == mod, "✗ en Editar operación cambió algo: %s -> %s" % (mod, ahora)
    if FreeCADGui.Control.activeDialog():
        cancelar_panel()
    yield 100

    traza("opción apagada: vuelve la barra; prendida: se va")
    try:
        FreeCADGui.runCommand(cc.COMMAND, 0)
        bombear(600)
        assert _barra(), "con la esquina apagada no volvió la barra"
        assert claves() == [], "apagada, la esquina se ve"
    finally:
        FreeCADGui.runCommand(cc.COMMAND, 1)
    bombear(600)
    assert not _barra(), "prendida la esquina, quedó la barra"
    assert claves() == ["back_assembly"], "prendida otra vez: %s" % claves()
    yield 100

    traza("D) Volver al ensamblaje")
    clic_boton("back_assembly")
    assert ep.editing(doc) is None, "Volver al ensamblaje no salió de Editar pieza"
    assert claves() == [], "fuera de Editar pieza la esquina tiene %s" % claves()
    assert visibles(asm) == vis, "al volver quedó algo oculto"
    yield 100

    traza("taladro de ensamblaje: Cancelar croquis no deja el croquis ni abre el panel")
    from swui.fork import assembly_features as af
    antes_asm = set(o.Name for o in doc.Objects)
    pila_asm = list(doc.UndoNames)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % dos.Name)
    af.start("hole")
    bombear(2500)
    skh = getattr(gdoc.getInEdit(), "Object", None)
    assert skh is not None and skh.TypeId == "Sketcher::SketchObject", "el taladro de ensamblaje no abrió su croquis"
    assert claves() == ["exit_sketch", "cancel_sketch"], "croquis del taladro de ensamblaje: %s" % claves()
    clic_boton("cancel_sketch")
    bombear(1500)
    sobran = [o.Name for o in doc.Objects if o.Name not in antes_asm]
    traza("  quedaron %s; pendiente %s; panel %s; pasos %s / antes %s" % (
        sobran, af._state.get("pending"), bool(FreeCADGui.Control.activeDialog()), doc.UndoNames[:3], pila_asm[:3]))
    assert not sobran, "Cancelar croquis (taladro de ensamblaje) dejó %s" % sobran
    assert af._state.get("pending") is None and not FreeCADGui.Control.activeDialog(), "el taladro siguió igual"
    assert list(doc.UndoNames) == pila_asm, "la pila del ensamblaje no volvió: %s / %s" % (doc.UndoNames, pila_asm)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
