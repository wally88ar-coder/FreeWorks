# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""Abrir el clic derecho del árbol o de la vista en una prueba con ventana y leer el menú (15/11)."""
import FreeCAD
import Part
import Sketcher
from azar_comun import bombear

V = FreeCAD.Vector


def abrir_menu(abrir, cerrar=True, foto=None):
    """Abre un clic derecho con abrir() y devuelve (visibles, con lo de atrás, desplegado) del menú."""
    from swui.compat import QtCore, QtWidgets
    from swui.fork import context_menus as cm

    visto = {}

    class F(QtCore.QObject):
        def eventFilter(self, obj, ev):
            if (ev.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QMenu)
                    and not isinstance(obj.parent(), QtWidgets.QMenu) and "menu" not in visto):
                visto["menu"] = obj

                def leer():
                    try:
                        if foto is not None:  # como se abre, antes de desplegar la »
                            visto["foto"] = obj.grab().toImage()
                        visto["vis"] = cm.visible_texts(obj)
                        visto["todo"] = cm.visible_texts(obj, with_hidden=True)
                        visto["acciones"] = {a.text().replace("&", ""): a for a in obj.actions()}
                        visto["bandeja"] = [(b.property("swui_text"), not b.icon().isNull(), b.isEnabled())
                                            for a in obj.actions() if a.objectName() == "SWUI_cm_tray"
                                            for b in cm.tray_buttons(a)]
                        if cm.expand(obj):
                            bombear(150)
                        visto["desplegado"] = cm.visible_texts(obj)

                    finally:
                        if cerrar:
                            obj.close()
                QtCore.QTimer.singleShot(350, leer)
            return False

    f = F()
    app = QtWidgets.QApplication.instance()
    app.installEventFilter(f)
    try:
        abrir()
        bombear(900)
    finally:
        app.removeEventFilter(f)
    return visto


def arbol():
    import FreeCADGui
    from swui.compat import QtWidgets
    for t in FreeCADGui.getMainWindow().findChildren(QtWidgets.QTreeWidget):
        if t.metaObject().className() == "Gui::TreeWidget" and t.isVisible():
            return t


def item(label):
    from swui.compat import QtWidgets
    tree = arbol()
    it = QtWidgets.QTreeWidgetItemIterator(tree)
    while it.value():
        if it.value().text(0) == label:
            return it.value()
        it += 1


def derecho_arbol(label):
    from swui.compat import QtCore, QtGui, QtWidgets
    tree = arbol()
    it_ = item(label)
    assert it_ is not None, "no está %s en el árbol" % label
    tree.scrollToItem(it_)
    r = tree.visualItemRect(it_)
    p = QtCore.QPoint(r.left() + 30, r.center().y())
    vp = tree.viewport()

    def abrir():
        ev = QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, p, vp.mapToGlobal(p))
        QtWidgets.QApplication.sendEvent(vp, ev)
    return abrir


def px(view, vp, p):
    s = view.getSize()
    x, y = view.getPointOnViewport(p)[:2]
    return x * vp.width() / s[0], vp.height() - y * vp.height() / s[1]


def derecho_vista(punto):
    import FreeCADGui
    from swui.compat import QtCore, QtGui, QtWidgets
    view = FreeCADGui.ActiveDocument.ActiveView
    vp = view.graphicsView().viewport()
    x, y = px(view, vp, punto)
    R, N = QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.NoButton

    def ev(t, b, bs, dx=0):
        p = QtCore.QPointF(x + dx, y)
        return QtGui.QMouseEvent(t, p, QtCore.QPointF(vp.mapToGlobal(p)), b, bs,
                                 QtCore.Qt.KeyboardModifier.NoModifier)

    def abrir():
        for dx in (3, 1, 0):  # que FreeCAD preseleccione lo de abajo
            QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseMove, N, N, dx))
            bombear(80)
        QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseButtonPress, R, R))
        bombear(30)
        QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseButtonRelease, R, N))
    return abrir


def pieza():
    doc = FreeCAD.newDocument("Taco")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(60, 0, 0), V(60, 40, 0), V(0, 40, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    pad = body.newObject("PartDesign::Pad", "Extruir")
    pad.Profile = sk
    pad.Length = 20
    doc.recompute()
    return doc, body, sk, pad


