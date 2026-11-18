# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Editar pieza = pieza (16/11), clic derecho y árbol: editando una pieza dentro del ensamblaje, el clic
derecho en una cara de esa pieza trae el menú de PIEZA (como en la pieza sola: "Operación (Extruir)", Croquis,
Editar operación), no el de componente. Croquis abre un croquis nuevo en la pieza, sobre esa cara (sin el error
del Croquis nativo, que abría otro). Editar operación abre la operación de la pieza sin salir de Editar pieza.
En la cara de OTRO componente sigue el menú de componente."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from menu_comun import abrir_menu, derecho_vista  # noqa: E402

V = FreeCAD.Vector


def _con_menu(abrir, que):
    """Abre el clic derecho, hace clic en `que` y lo cierra. Devuelve (visibles, si estaba)."""
    from swui.compat import QtCore, QtWidgets
    from swui.fork import context_menus as cm
    visto = {}

    class F(QtCore.QObject):
        def eventFilter(self, obj, ev):
            if (ev.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QMenu)
                    and not isinstance(obj.parent(), QtWidgets.QMenu) and "m" not in visto):
                visto["m"] = obj

                def hacer():
                    visto["vis"] = cm.visible_texts(obj)
                    visto["ok"] = cm.click_text(obj, que)
                    obj.close()
                QtCore.QTimer.singleShot(350, hacer)
            return False
    f = F()
    QtWidgets.QApplication.instance().installEventFilter(f)
    try:
        abrir()
        bombear(1500)
    finally:
        QtWidgets.QApplication.instance().removeEventFilter(f)
    return visto.get("vis"), visto.get("ok")


def _en_edicion(gdoc):
    vp = gdoc.getInEdit()
    return getattr(vp, "Object", None)


def prueba():
    import FreeCADGui
    import Part
    import piezas_editar as pe
    from swui.fork import edit_part as ep
    carpeta = carpeta_temporal()
    ruta = pe.bloque(carpeta)
    otra = pe.bloque(carpeta, "Otro")
    doc, asm, (uno, dos) = pe.ensamblaje([ruta, otra])
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    gdoc.activeView().viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    assert ep.start(uno, warn=False)
    bombear(500)
    pdoc = uno.LinkedObject.Document
    arriba = uno.Placement.multVec(V(30, 20, 20))

    traza("paso 1")
    # 1) clic derecho en la cara de la pieza editada: menú de pieza
    m = abrir_menu(derecho_vista(arriba))
    vis = " | ".join(m.get("vis") or [])
    traza("  menú: %s" % vis[:400])
    assert "Componente (" not in vis, "editando, la cara de la pieza trajo el menú de componente: %s" % vis
    assert "Operación (" in vis or "Cara" in vis, "no salió el menú de pieza: %s" % vis
    assert any(t == "Croquis" for t, _i, _e in m.get("bandeja", [])), "falta Croquis en la bandeja: %s" % m.get("bandeja")
    yield 100

    traza("paso 2")
    # 2) Croquis desde la bandeja: croquis nuevo en la pieza sobre la cara (con un croquis viejo ahí: no se mueve)
    viejo = uno.LinkedObject.newObject("Sketcher::SketchObject", "Sketch")
    viejo.AttachmentSupport = [(pdoc.getObject("Extruir"), ["Face6"])]
    viejo.MapMode = "FlatFace"
    viejo.addGeometry(Part.Circle(V(10, 10, 0), V(0, 0, 1), 3))
    pdoc.recompute()
    antes = [o.Name for o in pdoc.Objects]
    FreeCADGui.Selection.clearSelection()
    vis, ok = _con_menu(derecho_vista(arriba), "Croquis")
    bombear(1500)
    assert ok, "no estaba Croquis: %s" % vis
    nuevos = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "Sketcher::SketchObject"]
    assert nuevos and _en_edicion(gdoc) is nuevos[0], "Croquis no abrió un croquis nuevo en la pieza: %s / %s" % (
        [o.Name for o in nuevos], getattr(_en_edicion(gdoc), "Name", None))
    assert [o.Name for o in nuevos[0].AttachmentSupport[0][:1]] == ["Extruir"], "croquis mal apoyado"
    gdoc.resetEdit()
    bombear(600)
    assert ep.editing(doc) is uno, "Croquis sacó de Editar pieza"
    yield 100

    traza("paso 3")
    # 3) Editar operación desde la cara: abre la extrusión de la pieza (sin salir de Editar pieza)
    FreeCADGui.Selection.clearSelection()
    vis, ok = _con_menu(derecho_vista(uno.Placement.multVec(V(50, 30, 20))), "Editar operación")
    bombear(1500)
    assert ok, "no estaba Editar operación: %s" % vis
    assert getattr(_en_edicion(gdoc), "Name", None) == "Extruir", "Editar operación abrió %s" % _en_edicion(gdoc)
    FreeCADGui.Control.closeDialog()
    bombear(300)
    if _en_edicion(gdoc) is not None:
        gdoc.resetEdit()
    bombear(500)
    assert ep.editing(doc) is uno
    yield 100

    traza("paso 4")
    # 4) la cara del OTRO componente: menú de componente (como antes)
    FreeCADGui.Selection.clearSelection()
    m = abrir_menu(derecho_vista(dos.Placement.multVec(V(30, 20, 20))))
    vis = " | ".join(m.get("vis") or [])
    assert "Componente (" in vis, "la cara del otro componente no trajo el menú de componente: %s" % vis
    ep.stop(doc)
    bombear(300)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
