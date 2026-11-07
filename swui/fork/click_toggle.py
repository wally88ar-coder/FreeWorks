# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Clic sobre lo que ya está elegido lo deselecciona, como en SW 2018 (reporte del usuario, 06/11).

FreeCAD 1.1.4: un clic sobre algo ya elegido elige "lo que lo contiene" y va subiendo: Vista lateral
-> Origen -> Cuerpo -> otra vez Vista lateral. Relevado en SW con el mouse (06/11): Vista lateral
elegida, clic en su borde -> nada elegido; cara elegida, clic en la cara -> nada elegido. SW nunca
sube a Origen ni a la pieza.

Cómo: filtro de eventos de la aplicación, solo para clics izquierdos sin teclas en la vista 3D (Ctrl
+ clic sigue como en FreeCAD, que ya saca de la selección). Al apretar anota la selección; al
soltar (sin haber movido el mouse) mira qué quedó: si antes había UNA cosa elegida y ahora quedó
elegido algo que la contiene (mismo objeto de arriba, camino más corto), deselecciona en lugar de
subir. Solo en el banco LikeSolidWorks UI y fuera de la edición de un croquis u otro objeto.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

WB_NAME = "LikeSolidWorksUIWorkbench"
MOVE_PX = 4

_state = {"filter": None, "press": None}


def _selection():
    """[(documento, objeto de arriba, camino)] de lo elegido."""
    out = []
    for s in FreeCADGui.Selection.getSelectionEx("*", 0):
        subs = [x for x in (s.SubElementNames or []) if x] or [""]
        for sub in subs:
            out.append((s.DocumentName, s.ObjectName, sub))
    return out


def climbed(before, after):
    """True si `after` es lo que contiene a `before` (lo que FreeCAD elige al hacer clic otra vez)."""
    if len(before) != 1 or len(after) != 1:
        return False
    (d0, o0, s0), (d1, o1, s1) = before[0], after[0]
    if (d0, o0) != (d1, o1) or s1 == s0:
        return False
    if s1 == "":
        return True
    return s0.startswith(s1) and s1.endswith(".")


def _is_viewport(widget):
    """El widget de dibujo de la vista 3D (el clic sin aceptar sube a sus padres: mirar solo este)."""
    try:
        parent = widget.parentWidget()
        return parent is not None and parent.metaObject().className() == "Gui::View3DInventorViewer"
    except Exception:
        return False


def _in_view(widget):
    w = widget
    while w is not None:
        try:
            if w.metaObject().className() == "Gui::View3DInventor":
                return True
        except Exception:
            return False
        w = w.parentWidget()
    return False


def _active():
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return False
        gd = FreeCADGui.ActiveDocument
        return gd is not None and gd.getInEdit() is None
    except Exception:
        return False


def _after_release(before):
    try:
        if climbed(before, _selection()):
            FreeCADGui.Selection.clearSelection()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Clic otra vez: %s\n" % traceback.format_exc())


def _pos(event):
    p = event.position() if hasattr(event, "position") else QtCore.QPointF(event.pos())
    return p.x(), p.y()


class _ClickFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        try:
            t = event.type()
            if t not in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
                return False
            if event.button() != QtCore.Qt.LeftButton or not isinstance(obj, QtWidgets.QWidget):
                return False
            if not _is_viewport(obj):
                return False
            if t == QtCore.QEvent.MouseButtonPress:
                _state["press"] = None
                if event.modifiers() != QtCore.Qt.NoModifier or not _in_view(obj) or not _active():
                    return False
                before = _selection()
                if len(before) == 1:
                    _state["press"] = (obj, _pos(event), before)
                return False
            press = _state["press"]
            _state["press"] = None
            if press is None:
                return False
            (x0, y0), (x1, y1) = press[1], _pos(event)
            if abs(x1 - x0) > MOVE_PX or abs(y1 - y0) > MOVE_PX:
                return False
            before = press[2]
            QtCore.QTimer.singleShot(0, lambda: _after_release(before))
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Clic otra vez: %s\n" % traceback.format_exc())
        return False


def install():
    if _state["filter"] is None:
        _state["filter"] = _ClickFilter()
        QtWidgets.QApplication.instance().installEventFilter(_state["filter"])
