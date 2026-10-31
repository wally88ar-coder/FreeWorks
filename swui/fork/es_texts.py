# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Textos de FreeCAD 1.1.4 que quedan en inglés con el idioma en castellano (vistos con el mouse,
2026-10-31): "Save As..." en el menú Archivo y la pregunta al cerrar un documento con cambios
("Save all changes to document ... before closing?", botón "Discard").

Solo cambia textos al mostrarse el menú o la ventana (filtro de eventos de Qt sobre la
aplicación, que mira únicamente QMenu y QMessageBox); lo que no está en las tablas queda igual.

Además, en el cuadro de una cota nueva del croquis ("Insertar longitud", "Insertar ángulo"...),
Escape la deja con el valor medido, como el cuadro Modificar de SW; en FreeCAD cancelar la
borraba (visto con el mouse, 2026-10-31).
"""

import re

from swui.compat import QtCore, QtWidgets

MENU = {
    "Save &As...": "Guardar &como...",
    "Save As...": "Guardar como...",
    "Save &As…": "Guardar &como…",
    "Save As…": "Guardar como…",
}

BUTTONS = {
    "Discard": "Descartar",
    "&Discard": "&Descartar",
    "Cancel": "Cancelar",
    "&Cancel": "&Cancelar",
}

MESSAGES = [
    (re.compile(r"^Save all changes to document '(.*)' before closing\?$"),
     r"¿Guardar los cambios del documento '\1' antes de cerrar?"),
    (re.compile(r"^Save changes to document '(.*)' before closing\?$"),
     r"¿Guardar los cambios del documento '\1' antes de cerrar?"),
]

# botones y títulos de paneles de tareas (QToolButton/QPushButton) que FreeCAD deja en inglés
WIDGETS = {
    "Close": "Cerrar",
    "Sketch Edit": "Edición de croquis",
}

_filter = None


def menu_text(text):
    return MENU.get(text)


def message_text(text):
    for rx, repl in MESSAGES:
        if rx.match(text or ""):
            return rx.sub(repl, text)
    return None


def _fix_menu(menu):
    for action in menu.actions():
        new = menu_text(action.text())
        if new:
            action.setText(new)


def _fix_box(box):
    new = message_text(box.text())
    if new:
        box.setText(new)
    for button in box.buttons():
        new = BUTTONS.get(button.text())
        if new:
            button.setText(new)


def is_new_datum_title(title):
    """¿Título del cuadro de FreeCAD para el valor de una cota recién puesta?"""
    return (title or "").startswith(("Insertar ", "Insert "))


def _datum_dialog(widget):
    """El cuadro de cota nueva al que pertenece widget (o None)."""
    w = widget
    while w is not None:
        if isinstance(w, QtWidgets.QDialog) and not isinstance(w, QtWidgets.QMessageBox):
            if is_new_datum_title(w.windowTitle()) and any(
                    c.text() in ("Referencia", "Reference") for c in w.findChildren(QtWidgets.QCheckBox)):
                return w
            return None
        w = w.parentWidget()
    return None


class _Filter(QtCore.QObject):
    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            if kind == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape \
                    and isinstance(obj, QtWidgets.QWidget):
                dialog = _datum_dialog(obj)
                if dialog is not None:
                    dialog.accept()  # queda la cota con el valor medido
                    return True
            if kind == QtCore.QEvent.Show:
                if isinstance(obj, QtWidgets.QMessageBox):
                    _fix_box(obj)
                elif isinstance(obj, QtWidgets.QMenu):
                    _fix_menu(obj)
                elif isinstance(obj, QtWidgets.QAbstractButton):
                    new = WIDGETS.get(obj.text())
                    if new:
                        obj.setText(new)
        except Exception:
            pass
        return False


def inserted_text(text, delta):
    """
    Contador del panel Insertar de FreeCAD en castellano: "Placa : 1 insertado", "2 insertados".
    delta +1 / -1; acepta también el texto en inglés de FreeCAD ("... : 1 inserted").
    """
    m = re.search(r" : (\d+) (inserted|insertados?)$", text)
    base = text[:m.start()] if m else text
    n = (int(m.group(1)) if m else 0) + delta
    if n <= 0:
        return base
    return "%s : %d %s" % (base, n, "insertado" if n == 1 else "insertados")


def _patch_insert_panel():
    """FreeCAD cuenta los insertados leyendo "N inserted" del texto: se cambia el contador entero."""
    try:
        import CommandInsertLink
    except Exception:
        return
    cls = CommandInsertLink.TaskAssemblyInsertLink
    if getattr(cls.increment_counter, "_swui", False):
        return

    def increment_counter(self, item):
        item.setText(0, inserted_text(item.text(0), +1))

    def decrement_counter(self, item):
        item.setText(0, inserted_text(item.text(0), -1))

    increment_counter._swui = decrement_counter._swui = True
    cls.increment_counter = increment_counter
    cls.decrement_counter = decrement_counter


def install():
    global _filter
    _patch_insert_panel()
    if _filter is not None:
        return
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    _filter = _Filter()
    app.installEventFilter(_filter)
