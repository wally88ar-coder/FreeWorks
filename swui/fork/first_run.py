# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Instalación de cero (18/11): FreeWorks como corresponde desde el PRIMER arranque.

Con una configuración de FreeCAD nueva (instalación nueva, o se borró la carpeta de configuración), FreeWorks
recién se ponía como banco de arranque la primera vez que alguien lo elegía (always_swui.install corre en
Initialize), y el asistente de primer arranque de FreeCAD ("Welcome to FreeCAD") grababa el idioma "English"
porque el parámetro estaba vacío: el primer arranque quedaba en Part Design, en inglés y con las barras de
FreeCAD (lo vio el usuario el 17/11 al reinstalar). Se arreglaba solo reiniciando.

Esto corre desde InitGui.py al arrancar FreeCAD (antes de que FreeCAD active el banco de arranque y muestre el
asistente) y, solo si "Usar siempre FreeWorks" está activo:
  - pone FreeWorks como banco de arranque (lo mismo que always_swui.set_autoload, con su respaldo);
  - anota ocultas las barras generales de FreeCAD que todavía no tienen nada anotado;
  - si el idioma de FreeCAD no está elegido, lo pone en castellano (el asistente lo muestra elegido), una sola vez
    por configuración. Un idioma ya elegido no se toca nunca.
"""

import FreeCAD

GENERAL = "User parameter:BaseApp/Preferences/General"
LANGUAGE_KEY = "Language"
LANGUAGE = "Spanish (Argentina)"  # nombre que usa FreeCAD 1.1.4 (el que eligió el usuario)
OWN = "User parameter:BaseApp/Preferences/Mod/SWUI"
LANGUAGE_DONE = "FirstRunLanguage"  # el idioma se revisa UNA vez por configuración (revisión del 18/11, hallazgo 10)
TOOLBARS = "User parameter:BaseApp/MainWindow/Toolbars"
# barras generales de FreeCAD (nombres internos de 1.1.4) que FreeWorks no muestra; "Workbench" es el selector
HIDDEN_TOOLBARS = ("File", "Edit", "Clipboard", "Workbench", "Macro", "View", "Individual Views", "Structure", "Help")


def apply():
    """Lo del primer arranque. Devuelve qué cambió (lista de textos), para el registro y las pruebas."""
    from swui.fork import always_swui

    changed = []
    if not always_swui.enabled():
        return changed
    general = FreeCAD.ParamGet(GENERAL)
    if general.GetString(always_swui.AUTOLOAD, "") != always_swui.WB_NAME:
        always_swui.set_autoload(True)
        changed.append("banco de arranque")
    # barras: FreeCAD recuerda en la configuración cuáles se ven; con una nueva no hay nada y muestra todas (layout
    # las oculta al entrar, pero en el primer arranque FreeCAD las vuelve a mostrar después: medido el 18/11, #101).
    # Se anotan ocultas solo las que no tienen nada anotado: lo que eligió el usuario no se toca.
    bars = FreeCAD.ParamGet(TOOLBARS)
    known = set(bars.GetBools())
    for name in HIDDEN_TOOLBARS:
        if name not in known:
            bars.SetBool(name, False)
            changed.append("barra " + name)
    own = FreeCAD.ParamGet(OWN)
    if not own.GetBool(LANGUAGE_DONE, False):
        # una sola vez: si después alguien vacía el idioma a propósito (FreeCAD toma el del sistema), no se insiste
        own.SetBool(LANGUAGE_DONE, True)
        if not general.GetString(LANGUAGE_KEY, ""):
            general.SetString(LANGUAGE_KEY, LANGUAGE)
            changed.append("idioma")
    return changed


def release_toolbars():
    """Al dejar de usar siempre FreeWorks: las barras generales de FreeCAD vuelven a estar a la vista en los otros
    bancos (en FreeWorks las sigue ocultando layout.enter)."""
    bars = FreeCAD.ParamGet(TOOLBARS)
    for name in HIDDEN_TOOLBARS:
        bars.SetBool(name, True)
