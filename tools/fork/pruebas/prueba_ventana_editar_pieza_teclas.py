# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Editar pieza = pieza, teclas (18/11): la barra espaciadora (Medir) y Esc hacen lo mismo en la pieza sola que
editándola dentro de un ensamblaje. Espacio abre Medir y otro Espacio lo cierra; Esc con el panel de Redondeo abierto
lo cancela sin dejar nada; Esc con un croquis abierto sin herramienta hace lo mismo en los dos modos. Editando, nada
de esto saca de Editar pieza."""
TIPO = "completa"
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
    return vista


def _tecla(vista, key):
    from swui.compat import QtCore, QtGui, QtWidgets
    vp = vista.graphicsView().viewport()
    vp.setFocus()
    for t in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
        QtWidgets.QApplication.sendEvent(vp, QtGui.QKeyEvent(t, key, QtCore.Qt.KeyboardModifier.NoModifier))
        bombear(100)
    bombear(500)


def _medir_abierto():
    from swui.fork import measure_sw
    w = measure_sw._window
    return bool(w is not None and w.isVisible())


def _secuencia(vista, pdoc, pad, gdoc):
    """Lo que pasa con cada tecla; el mismo dict en los dos modos."""
    import FreeCADGui
    from swui import ribbon
    from swui.compat import QtCore
    from swui.fork import edit_context as ec
    r = {}
    # Espacio: Medir
    _tecla(vista, QtCore.Qt.Key.Key_Space)
    r["espacio abre medir"] = _medir_abierto()
    _tecla(vista, QtCore.Qt.Key.Key_Space)
    r["espacio cierra medir"] = not _medir_abierto()
    # Esc con Redondeo abierto
    antes = set(o.Name for o in pdoc.Objects)
    FreeCADGui.Selection.clearSelection()
    ec.select(pad, "Edge1")
    ribbon._run("PartDesign_Fillet")
    bombear(1200)
    r["redondeo abre panel"] = bool(FreeCADGui.Control.activeDialog())
    _tecla(vista, QtCore.Qt.Key.Key_Escape)
    bombear(800)
    r["esc cierra el panel"] = not FreeCADGui.Control.activeDialog()
    r["esc no deja nada"] = sorted(o.TypeId for o in pdoc.Objects if o.Name not in antes)
    # Esc con un croquis abierto, sin herramienta
    FreeCADGui.Selection.clearSelection()
    ec.select(pad, "Face6")
    ribbon._run("PartDesign_NewSketch")
    bombear(1200)
    sk = getattr(ec.in_edit(pdoc), "Object", None) if hasattr(ec, "in_edit") else None
    vp_edit = gdoc.getInEdit()
    sk = getattr(vp_edit, "Object", sk)
    r["croquis abierto"] = getattr(sk, "TypeId", "") == "Sketcher::SketchObject"
    _tecla(vista, QtCore.Qt.Key.Key_Escape)
    bombear(800)
    r["esc en el croquis: sigue abierto"] = getattr(getattr(gdoc.getInEdit(), "Object", None), "TypeId", "") \
        == "Sketcher::SketchObject"
    if gdoc.getInEdit() is not None:
        ec.reset_edit(pdoc)
        bombear(600)
    return r


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    ruta = pe.bloque(c)
    otra = pe.bloque(c, "Otro")

    traza("pieza sola")
    pdoc = FreeCAD.openDocument(ruta)
    bombear(800)
    vista = _al_frente(pdoc)
    gdoc = FreeCADGui.getDocument(pdoc.Name)
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    sola = _secuencia(vista, pdoc, pdoc.getObject("Extruir"), gdoc)
    traza("  %s" % sola)
    FreeCAD.closeDocument(pdoc.Name)
    bombear(500)
    yield 100

    traza("editando")
    doc, asm, (uno, _dos) = pe.ensamblaje([ruta, otra])
    uno.Placement.Base = FreeCAD.Vector(0, -30, 15)  # fuera del origen
    doc.recompute()
    vista = _al_frente(doc)
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    gdoc = FreeCADGui.getDocument(doc.Name)
    assert ep.start(uno, warn=False)
    bombear(400)
    pdoc = uno.LinkedObject.Document
    editando = _secuencia(vista, pdoc, pdoc.getObject("Extruir"), ec.gui_for(pdoc))
    traza("  %s" % editando)
    assert ep.editing(doc) is uno, "las teclas sacaron de Editar pieza"
    # lo esperado, en sí (revisión del 18/11: si las dos daban mal igual, la prueba pasaba)
    esperado = {"espacio abre medir": True, "espacio cierra medir": True, "redondeo abre panel": True,
                "esc cierra el panel": True, "esc no deja nada": [], "croquis abierto": True}
    for nombre, r in (("pieza sola", sola), ("editando", editando)):
        mal = {k: r.get(k) for k, v in esperado.items() if r.get(k) != v}
        assert not mal, "%s: %s" % (nombre, mal)
    distintas = {k: (sola[k], editando.get(k)) for k in sola if sola[k] != editando.get(k)}
    assert not distintas, "las teclas hacen distinto editando: %s" % distintas
    ep.stop(doc)
    for d in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(d.Name)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
