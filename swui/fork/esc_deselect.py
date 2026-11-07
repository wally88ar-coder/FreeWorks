# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Esc deselecciona, como en SW 2018 (pedido del usuario, 06/11).

Relevado en SW con el mouse (06/11): Alzado elegido en el árbol, Esc -> queda sin nada elegido. En
SW vale para cualquier cosa elegida (caras, aristas, planos, operaciones). FreeCAD 1.1.4 no hace
nada con Esc fuera de un panel o de un croquis.

Cómo: un filtro de eventos de la aplicación mira solo la tecla Esc (no la come: los demás la siguen
recibiendo) cuando el foco está en la vista 3D o en el árbol. Limpia la selección solo si nada más
usa ese Esc:
  - banco LikeSolidWorks UI;
  - sin panel de tareas abierto (ahí Esc cierra el panel) ni objeto en edición (croquis...);
  - sin arrastre de agarraderas de plano ni cotas del doble clic a la vista (ahí Esc las cancela
    primero; un segundo Esc deselecciona);
  - el foco no está en un campo de texto (renombrar en el árbol, etc.).
El borrado va con un QTimer de 0 ms y vuelve a mirar las condiciones, por si el mismo Esc abrió o
cerró algo.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

WB_NAME = "LikeSolidWorksUIWorkbench"
_ZONES = ("Gui::View3DInventor", "Gui::TreeWidget", "Gui::TreePanel", "Gui::DocumentObjectTreeView")

_state = {"filter": None}


def deselect():
    """Lo que hace Esc: dejar sin nada elegido (función pública, sin interfaz)."""
    FreeCADGui.Selection.clearSelection()


def _in_zone(widget):
    w = widget
    while w is not None:
        try:
            if w.metaObject().className() in _ZONES:
                return True
        except Exception:
            return False
        w = w.parentWidget()
    return False


def _busy():
    """True si este Esc es de otro (panel, croquis, arrastre, cotas, campo de texto)."""
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return True
    except Exception:
        return True
    try:
        if FreeCADGui.Control.activeDialog():
            return True
    except Exception:
        pass
    try:
        gd = FreeCADGui.ActiveDocument
        if gd is None or gd.getInEdit() is not None:
            return True
    except Exception:
        return True
    try:
        from swui.fork import plane_handles

        if plane_handles._state.get("drag") is not None:
            return True
    except Exception:
        pass
    try:
        from swui.fork import instant_dims

        if instant_dims.shown():
            return True
    except Exception:
        pass
    focus = QtWidgets.QApplication.focusWidget()
    if isinstance(focus, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QTextEdit,
                          QtWidgets.QPlainTextEdit)):
        return True
    if QtWidgets.QApplication.activePopupWidget() is not None or QtWidgets.QApplication.activeModalWidget():
        return True
    return False


def _later():
    try:
        if not _busy() and FreeCADGui.Selection.getSelectionEx("*"):
            deselect()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Esc: %s\n" % traceback.format_exc())


class _EscFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        try:
            if event.type() != QtCore.QEvent.KeyPress or event.key() != QtCore.Qt.Key_Escape:
                return False
            if event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier):
                return False
            if not isinstance(obj, QtWidgets.QWidget) or not _in_zone(QtWidgets.QApplication.focusWidget()):
                return False
            # el mismo Esc llega a varios objetos (widget y sus padres): mirar solo el primero
            if obj is not QtWidgets.QApplication.focusWidget():
                return False
            if _busy():
                return False
            QtCore.QTimer.singleShot(0, _later)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Esc: %s\n" % traceback.format_exc())
        return False


def install():
    if _state["filter"] is None:
        _state["filter"] = _EscFilter()
        QtWidgets.QApplication.instance().installEventFilter(_state["filter"])
