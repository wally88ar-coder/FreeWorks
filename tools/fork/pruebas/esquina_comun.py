# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""Ayudas de las pruebas de la esquina de confirmación (21/11): sus botones, clics de verdad, dónde está."""
from _base import traza
from azar_comun import bombear


def boton(clave):
    from swui.compat import QtWidgets
    from swui.fork import confirm_corner as cc
    box = cc.widget()
    if box is None:
        return None
    return box.findChild(QtWidgets.QToolButton, "SWUI_corner_" + clave)


def clic_boton(clave):
    from PySide6.QtTest import QTest
    from swui.compat import QtCore
    bombear(400)  # el reloj de la esquina (250 ms) la pone al día
    b = boton(clave)
    assert b is not None, "no está el botón %s en la esquina (hay %s)" % (clave, claves())
    QTest.mouseClick(b, QtCore.Qt.MouseButton.LeftButton)
    bombear(1500)


def claves():
    from swui.fork import confirm_corner as cc
    bombear(400)
    return cc.visible_keys()


def lugar_ok(vista):
    """La esquina está arriba a la derecha de la vista, a la izquierda del cubo, adentro y por encima de la vista."""
    import FreeCADGui
    from swui.compat import QtCore, QtWidgets
    from swui.fork import confirm_corner as cc
    box = cc.widget()
    assert box is not None, "la esquina no se ve"
    mw = FreeCADGui.getMainWindow()
    vp = vista.graphicsView().viewport()
    tl = vp.mapTo(mw, QtCore.QPoint(0, 0))
    g = box.geometry()
    derecha_vista = tl.x() + vp.width()
    traza("  esquina %s; vista x %d..%d, y %d; cubo %d" % (
        (g.x(), g.y(), g.width(), g.height()), tl.x(), derecha_vista, tl.y(), cc.cube_offset()))
    assert g.right() <= derecha_vista - cc.cube_offset(), "tapa el cubo de navegación"
    assert g.right() >= derecha_vista - cc.cube_offset() - 30, "no está pegada a la derecha"
    assert tl.y() <= g.top() <= tl.y() + 20, "no está arriba de la vista"
    hijos = [c for c in mw.children() if isinstance(c, QtWidgets.QWidget)]
    central = mw.centralWidget()
    assert hijos.index(box) > hijos.index(central), "la esquina quedó debajo de la vista (#105)"
