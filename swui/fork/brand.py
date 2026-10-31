# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Nombre propio del fork: FreeWorks (decisión del usuario, 2026-10-31; no lleva "SolidWorks", que
es marca de Dassault, ni "FreeCAD", marca de la FPA).

Solo cambia lo que se ve: el título del menú del banco y el nombre en la lista de bancos. Lo
interno queda igual para que abran los archivos y la configuración de siempre: la clave del banco
("LikeSolidWorksUIWorkbench", la guarda FreeCAD como banco de arranque), los comandos SWUI_ y las
propiedades guardadas en las piezas. El menú lo arma FreeCAD con el texto del original al activar
el banco: se le cambia el título después (señal workbenchActivated), sin tocar InitGui.py.
Pendiente aparte (consultar antes): package.xml y el nombre del repositorio, para el Addon Manager.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

BRAND = "FreeWorks"
ORIGINAL = "LikeSolidWorks UI"
WB_NAME = "LikeSolidWorksUIWorkbench"

_connected = False


def menu_title(text):
    """'LikeSolidWorks UI' (o con &) -> 'FreeWorks'; lo demás queda igual."""
    return BRAND if (text or "").replace("&", "") == ORIGINAL else text


def rename_menu():
    try:
        bar = FreeCADGui.getMainWindow().menuBar()
    except Exception:
        return
    for action in bar.actions():
        new = menu_title(action.text())
        if new != action.text():
            action.setText(new)


def _on_workbench(name):
    if name == WB_NAME:
        QtCore.QTimer.singleShot(0, rename_menu)


def install():
    global _connected
    try:
        wb = FreeCADGui.listWorkbenches().get(WB_NAME)
        if wb is not None:
            wb.MenuText = BRAND
    except Exception:
        pass
    if not _connected:
        try:
            FreeCADGui.getMainWindow().workbenchActivated.connect(_on_workbench)
            _connected = True
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Nombre FreeWorks: señal no disponible.\n")
    QtCore.QTimer.singleShot(0, rename_menu)
