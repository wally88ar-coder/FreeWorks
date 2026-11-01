# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Campos numéricos como en SOLIDWORKS: al hacer clic en un valor (distancia, ángulo, espesor...)
queda todo marcado y lo que se escribe lo reemplaza. En Qt el clic deja el cursor donde cayó y
el triple clic no marca todo con la unidad al lado ("10,00 mm"): el número escrito se agregaba
al viejo (visto con el mouse, 2026-10-31).

Un filtro de eventos en la aplicación mira solo el foco que llega con un clic a un campo
numérico (QAbstractSpinBox: los de los paneles del fork y los de FreeCAD); el foco que pone el
programa (p. ej. los números junto al mouse del croquis) no se toca. Solo dentro de
LikeSolidWorks UI.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

WB_NAME = "LikeSolidWorksUIWorkbench"

_filter = None


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _spin_of(widget):
    """El campo numérico de un widget (el campo mismo o su línea de texto)."""
    for w in (widget, widget.parent() if widget is not None else None):
        if isinstance(w, QtWidgets.QAbstractSpinBox):
            return w
    return None


class _Filter(QtCore.QObject):
    def eventFilter(self, obj, event):
        try:
            if event.type() != QtCore.QEvent.Type.FocusIn:
                return False
            if event.reason() != QtCore.Qt.FocusReason.MouseFocusReason:
                return False
            spin = _spin_of(obj)
            if spin is None or not spin.isEnabled() or spin.isReadOnly() or not _in_workbench():
                return False
            # después de que el clic ubique el cursor: marcar todo
            QtCore.QTimer.singleShot(0, spin.selectAll)
        except Exception:
            pass
        return False


def install():
    global _filter
    if _filter is not None:
        return
    try:
        _filter = _Filter()
        QtWidgets.QApplication.instance().installEventFilter(_filter)
    except Exception:
        _filter = None
        FreeCAD.Console.PrintLog("[SWUI fork] Campos numéricos: filtro no disponible.\n")
