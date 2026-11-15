# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""Ayudas comunes de las pruebas con ventana del croquis: un croquis de partida como el del
usuario (oblongo + una "L" arriba a la derecha + un círculo definido) y clics de mouse sobre la
vista en coordenadas del croquis."""

import math

import FreeCAD

V = FreeCAD.Vector
# Números de geometría del croquis de partida
L_ARRIBA, L_DERECHA, ARCO_IZQ, ARCO_DER, RECTA_SUP, RECTA_INF, CIRCULO = range(7)


def croquis_oblongo(doc, circulo=True):
    """
    Horizontal de arriba (y=20) y vertical de la derecha (x=25) totalmente definidas; oblongo de
    centros (0,0)-(10,0), R3, armado como lo arma FreeCAD (tangentes en las puntas, horizontal,
    iguales), con la distancia entre centros y 15 mm hasta la vertical: le queda 1 grado de
    libertad (la altura), como el del usuario del 14/11. Con `circulo`, un círculo R4 en
    (-10,-10) totalmente definido.
    """
    import Part
    import Sketcher
    sk = doc.addObject("Sketcher::SketchObject", "Croquis")
    g0 = sk.addGeometry(Part.LineSegment(V(-20, 20, 0), V(25, 20, 0)))
    g1 = sk.addGeometry(Part.LineSegment(V(25, 20, 0), V(25, -20, 0)))
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
    if circulo:
        ci = sk.addGeometry(Part.Circle(V(-10, -10, 0), V(0, 0, 1), 4))
        for c in (Sketcher.Constraint("Radius", ci, 4), Sketcher.Constraint("DistanceX", -1, 1, ci, 3, -10),
                  Sketcher.Constraint("DistanceY", -1, 1, ci, 3, -10)):
            sk.addConstraint(c)
    return sk


def vp():
    import FreeCADGui
    return FreeCADGui.ActiveDocument.ActiveView.graphicsView().viewport()


def px(p):
    """Punto del croquis (vista de arriba) -> píxel del viewport de Qt (y hacia abajo)."""
    import FreeCADGui
    x, y = FreeCADGui.ActiveDocument.ActiveView.getPointOnViewport(p)[:2]
    return x, vp().height() - y


def _ev(t, x, y, b, bs):
    from PySide import QtCore, QtGui, QtWidgets
    w = vp()
    q = QtCore.QPointF(x, y)
    QtWidgets.QApplication.sendEvent(w, QtGui.QMouseEvent(t, q, QtCore.QPointF(w.mapToGlobal(q)), b, bs,
                                                          QtCore.Qt.KeyboardModifier.NoModifier))
    QtWidgets.QApplication.processEvents()


def mover(p, pasos=6):
    """Lleva el mouse hasta p en varios pasos (las herramientas reaccionan al movimiento)."""
    from PySide import QtCore
    x, y = px(p)
    N = QtCore.Qt.MouseButton.NoButton
    for i in range(pasos):
        _ev(QtCore.QEvent.Type.MouseMove, x + pasos - i, y, N, N)
    _ev(QtCore.QEvent.Type.MouseMove, x, y, N, N)


def clic(p):
    from PySide import QtCore
    mover(p)
    x, y = px(p)
    L, N = QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton
    _ev(QtCore.QEvent.Type.MouseButtonPress, x, y, L, L)
    _ev(QtCore.QEvent.Type.MouseButtonRelease, x, y, L, N)


def tecla(key):
    from PySide import QtCore, QtGui, QtWidgets
    for t in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
        QtWidgets.QApplication.sendEvent(vp(), QtGui.QKeyEvent(t, key, QtCore.Qt.KeyboardModifier.NoModifier))
    QtWidgets.QApplication.processEvents()


def esc():
    from PySide import QtCore
    tecla(QtCore.Qt.Key.Key_Escape)


def hay_rojo(p):
    """¿Hay algún píxel rojo puro cerca del punto p del croquis (captura de la ventana)?"""
    import FreeCADGui
    from PySide import QtCore
    mw = FreeCADGui.getMainWindow()
    img = mw.grab().toImage()
    x, y = px(p)
    c = vp().mapTo(mw, QtCore.QPoint(int(x), int(y)))
    vistos = []
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            col = img.pixelColor(c.x() + dx, c.y() + dy)
            vistos.append(col.name())
            if col.red() > 200 and col.green() < 60 and col.blue() < 60:
                return True, None
    return False, sorted(set(vistos))
