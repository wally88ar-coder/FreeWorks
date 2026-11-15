# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Croquis con un oblongo cuyo largo ya está fijado (distancia entre centros + tangencias) y una
recta horizontal arriba. Con Cota inteligente, un clic en la recta del oblongo: FreeCAD agrega una
cota provisoria que sobra (redundante) y pinta el croquis con el color de croquis con error. Ese
color tiene que ser ROJO (como lo sobredefinido de SW) y distinto del naranja del resaltado, para
que se vea qué se está por elegir (pedido del usuario, 14/11). El segundo clic, en la recta de
arriba, cambia la cota provisoria por la distancia entre las dos rectas y el croquis vuelve a no
tener redundantes."""
TIPO = "completa"

import math  # noqa: E402

import FreeCAD  # noqa: E402

E = {}
V = FreeCAD.Vector
ROJO = 0xFF0000FF


def _croquis(doc):
    import Part
    import Sketcher
    sk = doc.addObject("Sketcher::SketchObject", "Croquis")
    g0 = sk.addGeometry(Part.LineSegment(V(-20, 20, 0), V(25, 20, 0)))  # horizontal de arriba
    g1 = sk.addGeometry(Part.LineSegment(V(25, 20, 0), V(25, -20, 0)))  # vertical de la derecha
    for c in (Sketcher.Constraint("Coincident", g0, 2, g1, 1), Sketcher.Constraint("Horizontal", g0),
              Sketcher.Constraint("Vertical", g1), Sketcher.Constraint("DistanceX", g0, 1, g0, 2, 45),
              Sketcher.Constraint("DistanceY", g1, 2, g1, 1, 40),
              Sketcher.Constraint("DistanceX", -1, 1, g0, 1, -20), Sketcher.Constraint("DistanceY", -1, 1, g0, 1, 20)):
        sk.addConstraint(c)
    a0 = sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(0, 0, 0), V(0, 0, 1), 3), math.pi / 2, 3 * math.pi / 2))
    a1 = sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(10, 0, 0), V(0, 0, 1), 3), -math.pi / 2, math.pi / 2))
    l0 = sk.addGeometry(Part.LineSegment(V(0, 3, 0), V(10, 3, 0)))
    l1 = sk.addGeometry(Part.LineSegment(V(0, -3, 0), V(10, -3, 0)))
    for c in (Sketcher.Constraint("Tangent", a0, 1, l0, 1), Sketcher.Constraint("Tangent", a1, 2, l0, 2),
              Sketcher.Constraint("Tangent", a0, 2, l1, 1), Sketcher.Constraint("Tangent", a1, 1, l1, 2),
              Sketcher.Constraint("Horizontal", l0), Sketcher.Constraint("Equal", a0, a1),
              Sketcher.Constraint("Radius", a0, 3), Sketcher.Constraint("DistanceX", a0, 3, a1, 3, 10),
              Sketcher.Constraint("DistanceX", a1, 3, g1, 1, 15)):
        sk.addConstraint(c)
    return sk


def _vp():
    import FreeCADGui
    return FreeCADGui.ActiveDocument.ActiveView.graphicsView().viewport()


def _px(p):
    import FreeCADGui
    x, y = FreeCADGui.ActiveDocument.ActiveView.getPointOnViewport(p)[:2]
    return x, _vp().height() - y


def _clic(p):
    from PySide import QtCore, QtGui, QtWidgets
    w = _vp()
    x, y = _px(p)
    L, N = QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton

    def ev(t, xx, yy, b, bs):
        q = QtCore.QPointF(xx, yy)
        QtWidgets.QApplication.sendEvent(w, QtGui.QMouseEvent(t, q, QtCore.QPointF(w.mapToGlobal(q)), b, bs,
                                                              QtCore.Qt.KeyboardModifier.NoModifier))
        QtWidgets.QApplication.processEvents()

    for i in range(6):
        ev(QtCore.QEvent.Type.MouseMove, x + 6 - i, y, N, N)
    ev(QtCore.QEvent.Type.MouseButtonPress, x, y, L, L)
    ev(QtCore.QEvent.Type.MouseButtonRelease, x, y, L, N)


def _hay_rojo(p):
    """¿Hay algún píxel rojo puro cerca del punto p del croquis (captura de la ventana)?"""
    import FreeCADGui
    from PySide import QtCore
    mw = FreeCADGui.getMainWindow()
    img = mw.grab().toImage()
    x, y = _px(p)
    c = _vp().mapTo(mw, QtCore.QPoint(int(x), int(y)))
    vistos = []
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            col = img.pixelColor(c.x() + dx, c.y() + dy)
            vistos.append(col.name())
            if col.red() > 200 and col.green() < 60 and col.blue() < 60:
                return True, None
    return False, sorted(set(vistos))


def prueba():
    import FreeCADGui
    doc = FreeCAD.newDocument("CotaRoja")
    sk = _croquis(doc)
    doc.recompute()
    E.update(doc=doc, sk=sk, n=sk.ConstraintCount)
    assert not sk.RedundantConstraints and not sk.ConflictingConstraints, "el croquis de partida ya tiene errores"

    def abrir():
        FreeCADGui.ActiveDocument.setEdit(sk.Name)

    def encuadrar():
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewTop()
        view.fitAll()

    def cota_y_primer_clic():
        vista = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
        assert vista.GetUnsigned("InvalidSketchColor") == ROJO, hex(vista.GetUnsigned("InvalidSketchColor"))
        assert vista.GetUnsigned("HighlightColor") != ROJO, "el resaltado es del mismo color que el error"
        FreeCADGui.runCommand("Sketcher_Dimension")
        _clic(V(5, 3, 0))  # recta de arriba del oblongo

    def mirar_rojo():
        assert sk.ConstraintCount == E["n"] + 1, "Cota inteligente no agregó la cota provisoria (¿cambió FreeCAD?)"
        assert sk.RedundantConstraints, "la cota provisoria no quedó redundante (¿cambió FreeCAD?)"
        ok, vistos = _hay_rojo(V(25, -10, 0))  # la vertical de la derecha, lejos del mouse
        assert ok, "el croquis con error no se ve rojo; colores cerca de la vertical: %s" % vistos

    def segundo_clic():
        _clic(V(-10, 20, 0))  # horizontal de arriba

    def comprobar():
        assert not sk.RedundantConstraints, "sigue redundante después del segundo clic: %s" % sk.RedundantConstraints
        ultima = sk.Constraints[-1]
        assert ultima.Type == "Distance" and abs(ultima.Value - 17) < 1e-6, (ultima.Type, ultima.Value)

    def esc():
        from PySide import QtCore, QtGui, QtWidgets
        for t in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
            QtWidgets.QApplication.sendEvent(_vp(), QtGui.QKeyEvent(t, QtCore.Qt.Key.Key_Escape,
                                                                    QtCore.Qt.KeyboardModifier.NoModifier))

    def salir():  # con la herramienta de cota todavía activa, resetEdit da "Access violation"
        FreeCADGui.ActiveDocument.resetEdit()

    return [(800, abrir), (1500, encuadrar), (800, cota_y_primer_clic), (1200, mirar_rojo),
            (500, segundo_clic), (1200, comprobar), (300, esc), (500, esc), (800, salir)]


from _base import ejecutar  # noqa: E402
ejecutar(globals())
