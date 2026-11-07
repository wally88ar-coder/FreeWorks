# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Cinta de alto fijo, el mínimo, sin la línea para estirarla (pedido del usuario, 07/11: "esa línea
azul que permite engrosar la ribbon no tiene sentido"). En SW 2018 el CommandManager tiene un alto
fijo y no se puede estirar.

La cinta del original es un QDockWidget arriba ("SWUI_Ribbon"); la línea es el separador de
QMainWindow entre el área de arriba y el resto, que se ponía azul al pasar el mouse y dejaba
arrastrar. Acá:
  - el dock queda con alto fijo = lo mínimo que piden las pestañas (botones + fila de pestañas); se
    vuelve a medir al cambiar de pestaña o de ancho (botones con o sin texto);
  - los separadores horizontales de la ventana (look_sw.EXTRA_QSS) tienen alto 0: no se ven ni se
    pueden agarrar. Los verticales (ancho del árbol) quedan como estaban.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

DOCK_NAME = "SWUI_Ribbon"

_state = {"hooked": False}


def ribbon_height(tabs):
    """Alto mínimo de la cinta: la página más alta + la fila de pestañas."""
    pages = 0
    for i in range(tabs.count()):
        w = tabs.widget(i)
        if w is not None:
            pages = max(pages, w.minimumSizeHint().height())
    return pages + tabs.tabBar().sizeHint().height()


def fix():
    """Dejar la cinta con su alto mínimo fijo (función pública, sin interfaz)."""
    try:
        mw = FreeCADGui.getMainWindow()
        dock = mw.findChild(QtWidgets.QDockWidget, DOCK_NAME)
        if dock is None:
            return False
        tabs = dock.widget()
        if tabs is None:
            return False
        h = ribbon_height(tabs)
        if h > 0 and (dock.minimumHeight() != h or dock.maximumHeight() != h):
            dock.setFixedHeight(h)
        if not _state["hooked"]:
            try:
                tabs.currentChanged.connect(lambda *_a: QtCore.QTimer.singleShot(0, fix))
                _state["hooked"] = True
            except Exception:
                pass
        return True
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cinta de alto fijo: %s\n" % traceback.format_exc())
        return False


def install():
    """Enganchar a layout.enter() del original: medir cuando la cinta ya está armada."""
    from swui import layout

    if getattr(layout.enter, "_swui_ribbon_fixed", False):
        return
    original_enter = layout.enter

    def enter(_original=original_enter):
        result = _original()
        for ms in (0, 500, 2000):  # los botones se acomodan al ancho un rato después
            QtCore.QTimer.singleShot(ms, fix)
        return result

    enter._swui_ribbon_fixed = True
    layout.enter = enter
