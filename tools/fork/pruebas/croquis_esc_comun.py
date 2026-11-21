# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""Clic y Esc de verdad en la vista 3D (eventos Qt), para las pruebas del croquis editando una pieza (#107, #108)."""
from azar_comun import bombear


def clic(vista, punto_3d, mover=True):
    """Clic en el punto (del ensamblaje); mover=False: sin pasar antes el mouse por encima."""
    from swui.compat import QtCore, QtGui, QtWidgets
    vp = vista.graphicsView().viewport()
    cx, cy = vista.getPointOnViewport(punto_3d)
    r = vp.devicePixelRatioF()
    p = QtCore.QPointF(cx / r, vp.height() - cy / r)
    nada, izq = QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.LeftButton
    sin = QtCore.Qt.KeyboardModifier.NoModifier
    g = vp.mapToGlobal(p.toPoint())
    if mover:
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, p, g, nada, nada, sin))
        bombear(300)
    QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, p, g, izq, izq, sin))
    bombear(150)
    QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonRelease, p, g, izq, nada, sin))
    bombear(500)


def esc(widget):
    from swui.compat import QtCore, QtGui, QtWidgets
    widget.setFocus()
    for t in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
        QtWidgets.QApplication.sendEvent(widget, QtGui.QKeyEvent(t, QtCore.Qt.Key.Key_Escape,
                                                                 QtCore.Qt.KeyboardModifier.NoModifier))
    bombear(400)
