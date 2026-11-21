# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Visto con el mouse el 21/11 (paso 16): editando una pieza dentro del ensamblaje, después de abrir y cerrar un
croquis de la pieza (queda la pieza como documento activo), el DOBLE CLIC de verdad en una cara de la pieza muestra
sus cotas sobre la pieza, como SW. Antes buscaba en la vista del documento activo (la de la pieza, apartada) y no
mostraba nada. También sin el croquis antes."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _doble_clic(vista, punto_3d):
    from swui.compat import QtCore, QtGui, QtWidgets
    vp = vista.graphicsView().viewport()
    cx, cy = vista.getPointOnViewport(punto_3d)
    r = vp.devicePixelRatioF()
    p = QtCore.QPointF(cx / r, vp.height() - cy / r)
    g = vp.mapToGlobal(p.toPoint())
    izq, nada = QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton
    sin = QtCore.Qt.KeyboardModifier.NoModifier
    E = QtCore.QEvent.Type
    QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(E.MouseMove, p, g, nada, nada, sin))
    for t, b in ((E.MouseButtonPress, izq), (E.MouseButtonRelease, nada), (E.MouseButtonDblClick, izq),
                 (E.MouseButtonRelease, nada)):
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(t, p, g, izq, b, sin))
        bombear(40)
    bombear(800)


def prueba():
    import FreeCADGui
    import Part
    import piezas_editar as pe
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    from swui.fork import instant_dims as idm
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
    assert ep.start(uno, warn=False)
    bombear(500)
    pdoc = uno.LinkedObject.Document
    cara = uno.Placement.multVec(V(30, 0, 10))  # el frente del bloque editado

    traza("doble clic en la pieza editada")
    vpw = vista.graphicsView().viewport()
    cx, cy = vista.getPointOnViewport(cara)
    traza("  filtro puesto: %s; bajo el punto: %s" % (vpw.property("swui_dims"), vista.getObjectInfo((int(cx), int(cy)))))
    traza("  show directo: %s" % idm.show(pdoc.getObject("Extruir")))
    ge = FreeCADGui.ActiveDocument.getInEdit()
    traza("  activo %s; en edición: %s %s" % (FreeCADGui.ActiveDocument.Document.Name, ge, getattr(ge, "TypeId", None)))
    idm.hide()
    orig = idm._ViewFilter.eventFilter

    def espia(self, viewport, event):
        r = orig(self, viewport, event)
        if event.type() in (2, 3, 4):
            traza("    evento %s -> %s; editando %s; banco %s; cotas %s" % (int(event.type()), r, idm._editing(),
                                                                         idm._in_workbench(), idm.shown()))
        return r
    idm._ViewFilter.eventFilter = espia
    _doble_clic(vista, cara)
    idm._ViewFilter.eventFilter = orig
    traza("  cotas: %s" % idm.shown())
    assert idm.shown(), "el doble clic no mostró las cotas de la pieza editada"
    idm.hide()
    bombear(300)
    yield 100

    traza("después de abrir y cerrar un croquis de la pieza (la pieza queda como documento activo)")
    sk = ec.new_sketch(pdoc.getObject("Extruir"), "Face6")
    bombear(1500)
    sk.addGeometry(Part.LineSegment(V(5, 5, 0), V(15, 10, 0)))
    pdoc.recompute()
    ec.reset_edit(pdoc)
    bombear(3000)
    FreeCAD.setActiveDocument(pdoc.Name)  # como lo deja FreeCAD (título "Taco *" con el mouse)
    bombear(300)
    _doble_clic(vista, cara)
    traza("  activo %s; cotas: %s" % (FreeCAD.ActiveDocument.Name, idm.shown()))
    assert idm.shown(), "con la pieza como documento activo el doble clic no mostró las cotas"
    idm.hide()
    ep.stop(doc)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
