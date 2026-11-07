# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Barrita sobre la vista, como la "barra Ver (transparente)" de SW 2018, solo con lo que pidió el
usuario (07/11): Vista de sección y Estilo de visualización.

Va flotando arriba al centro de cada ventana de dibujo (no le saca lugar), con fondo transparente.
  - Vista de sección: botón que queda hundido mientras la vista está cortada (section_view.toggle).
  - Estilo de visualización: menú con los estilos de SW que FreeCAD tiene (Std_DrawStyle):
      Sombreado con aristas -> "Como es" (cada objeto como se dibuja normalmente: con aristas)
      Sombreado             -> Sombreado
      Sin líneas ocultas    -> Línea oculta
      Estructura alámbrica  -> Estructura alámbrica
    "Líneas ocultas visibles" (punteadas) no existe en FreeCAD 1.1.4: no se ofrece.
Se pone al entrar al banco y en cada ventana nueva; se saca al salir.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

OBJECT_NAME = "SWUI_ViewBar"
TOP = 4  # px desde arriba de la vista
STYLES = (  # (texto SW, acción de Std_DrawStyle)
    ("Sombreado con aristas", "Std_DrawStyleAsIs"),
    ("Sombreado", "Std_DrawStyleShaded"),
    ("Sin líneas ocultas", "Std_DrawStyleHiddenLine"),
    ("Estructura alámbrica", "Std_DrawStyleWireframe"),
)

_state = {"on": False, "bars": [], "mdi": None}


def _style_actions():
    """{nombre de acción: QAction} del grupo Std_DrawStyle de FreeCAD."""
    try:
        return {a.objectName(): a for a in FreeCADGui.Command.get("Std_DrawStyle").getAction()}
    except Exception:
        return {}


def set_style(action_name):
    """Poner un estilo de visualización (función pública, sin interfaz)."""
    act = _style_actions().get(action_name)
    if act is not None:
        act.trigger()
    _refresh()


def _current_style():
    for name, act in _style_actions().items():
        try:
            if act.isChecked():
                return name
        except Exception:
            pass
    return None


# --- La barrita --------------------------------------------------------------------------------


class _Bar(QtWidgets.QFrame):
    def __init__(self, host):
        super().__init__(host)
        self.setObjectName(OBJECT_NAME)
        self.setStyleSheet(
            "QFrame#%s { background: transparent; border: none; }"
            "QToolButton { background: transparent; border: 1px solid transparent; border-radius: 2px;"
            " padding: 1px; }"
            "QToolButton:hover { background: rgba(255,255,255,170); border: 1px solid #9fc3e6; }"
            "QToolButton:checked { background: rgba(200,222,245,220); border: 1px solid #7aa7d6; }"
            % OBJECT_NAME)
        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(2)
        acts = _style_actions()
        # Vista de sección
        self.section = QtWidgets.QToolButton(self)
        self.section.setCheckable(True)
        self.section.setAutoRaise(True)
        self.section.setIconSize(QtCore.QSize(22, 22))
        self.section.setToolTip("Vista de sección")
        try:
            clip = FreeCADGui.Command.get("Std_ToggleClipPlane").getAction()
            if clip:
                self.section.setIcon(clip[0].icon())
        except Exception:
            pass
        self.section.clicked.connect(self._section)
        row.addWidget(self.section)
        # Estilo de visualización
        self.style_btn = QtWidgets.QToolButton(self)
        self.style_btn.setAutoRaise(True)
        self.style_btn.setIconSize(QtCore.QSize(22, 22))
        self.style_btn.setToolTip("Estilo de visualización")
        self.style_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu = QtWidgets.QMenu(self.style_btn)
        self.items = []
        for text, name in STYLES:
            a = menu.addAction(text)
            a.setCheckable(True)
            if name in acts:
                a.setIcon(acts[name].icon())
            a.triggered.connect(lambda _c=False, nm=name: set_style(nm))
            self.items.append((name, a))
        menu.aboutToShow.connect(self.refresh)
        self.style_btn.setMenu(menu)
        row.addWidget(self.style_btn)
        from swui.fork import section_view

        section_view.register_button(self.section)
        host.installEventFilter(self)
        self.refresh()
        self.place()
        self.show()
        self.raise_()

    def _section(self):
        from swui.fork import section_view

        try:
            section_view.toggle()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Vista de sección:\n%s\n" % traceback.format_exc())

    def refresh(self):
        cur = _current_style()
        acts = _style_actions()
        for name, a in self.items:
            a.setChecked(name == cur)
        icon_name = cur if cur in dict((n, 1) for _t, n in STYLES) else STYLES[0][1]
        if icon_name in acts:
            self.style_btn.setIcon(acts[icon_name].icon())

    def place(self):
        host = self.parentWidget()
        if host is None:
            return
        self.adjustSize()
        self.move(max(0, (host.width() - self.width()) // 2), TOP)
        self.raise_()

    def eventFilter(self, obj, event):
        if event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            QtCore.QTimer.singleShot(0, self.place)
        return False


def _hosts():
    """Widgets de las vistas 3D abiertas (donde va la barrita)."""
    out = []
    try:
        mw = FreeCADGui.getMainWindow()
        for w in mw.findChildren(QtWidgets.QWidget):
            if w.metaObject().className() == "Gui::View3DInventorViewer":
                out.append(w)
    except Exception:
        pass
    return out


def _ensure():
    if not _state["on"]:
        return
    have = []
    for bar in list(_state["bars"]):
        try:
            have.append(bar.parentWidget())
        except Exception:
            _state["bars"].remove(bar)
    for host in _hosts():
        if any(h == host for h in have):
            continue
        try:
            _state["bars"].append(_Bar(host))
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Barra de la vista:\n%s\n" % traceback.format_exc())


def _refresh():
    for bar in list(_state["bars"]):
        try:
            bar.refresh()
        except Exception:
            _state["bars"].remove(bar)


def apply():
    _state["on"] = True
    _ensure()
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        if mdi is not None and _state["mdi"] is None:
            mdi.subWindowActivated.connect(lambda *_a: QtCore.QTimer.singleShot(0, _activated))
            _state["mdi"] = mdi
    except Exception:
        pass


def _activated():
    _ensure()
    _refresh()
    try:
        from swui.fork import section_view

        section_view._sync_buttons()
    except Exception:
        pass


def remove():
    _state["on"] = False
    for bar in _state["bars"]:
        try:
            bar.hide()
            bar.setParent(None)
            bar.deleteLater()
        except Exception:
            pass
    _state["bars"] = []


def install():
    """Enganchar a layout.enter() / layout.leave() del original."""
    from swui import layout

    if getattr(layout.enter, "_swui_view_bar", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        QtCore.QTimer.singleShot(0, apply)
        return result

    def leave(_original=original_leave):
        remove()
        return _original()

    enter._swui_view_bar = leave._swui_view_bar = True
    layout.enter, layout.leave = enter, leave
