# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Ventana sin la barra de título de Windows, como SW 2018 (pedido del usuario, 06/11: "para ganar
unos mm de pantalla"; sin interruptor en el menú, decisión del usuario).

SW 2018 pone todo en una sola franja: logo, menús, acceso rápido, nombre del documento y a la
derecha minimizar / restaurar-maximizar / cerrar. Relevado en SW (06/11): doble clic en la franja
vacía restaura / maximiza, como la barra de título de Windows.

Cómo (desde afuera, sin tocar FreeCAD):
  - a la ventana principal se le sacan las pistas de título (Qt.CustomizeWindowHint solo): queda
    el borde de Windows, sin la barra de título (se vuelve a mostrar como estaba: maximizada o
    no). Qt.FramelessWindowHint NO: con eso Windows la vuelve a maximizar al restaurarla (06/11);
  - en el área derecha de la barra de menús (la misma de acceso rápido) van el nombre del documento
    (del documento activo, con " *" si tiene cambios) y los tres botones;
  - arrastrar la parte vacía de la barra de menús mueve la ventana con `startSystemMove` (lo hace
    Windows: sigue andando el "pegado" a los bordes); doble clic ahí maximiza / restaura;
  - los bordes, el pegado y Win + flechas los sigue manejando Windows;
  - al restaurar una ventana que arrancó maximizada, queda al 80 % y centrada (si no, su "tamaño
    normal" es la pantalla entera).
Se pone al entrar al banco y se saca al salir (vuelve la ventana normal de Windows).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

OBJECT_NAME = "SWUI_WindowButtons"
BUTTON_W = 40

_state = {"on": False, "box": None, "title": None, "max_btn": None, "bar_filter": None}


def _mw():
    return FreeCADGui.getMainWindow()


def doc_title(window_title):
    """'test planos - FreeCAD 1.1.4' -> 'test planos'; '[*]' de FreeCAD se vuelve '*' como SW."""
    text = (window_title or "").replace("[*]", "")
    for sep in (" - FreeCAD", " — FreeCAD"):
        if sep in text:
            text = text.split(sep)[0]
    return text.strip()


# --- Botones y nombre -----------------------------------------------------------------------


def current_title():
    """Nombre del documento activo, con " *" si tiene cambios sin guardar (como SW)."""
    try:
        gd = FreeCADGui.ActiveDocument
        if gd is not None:
            text = gd.Document.Label
            if getattr(gd, "Modified", False):
                text += " *"
            return text
    except Exception:
        pass
    return doc_title(_mw().windowTitle())


def _update_title(*_a):
    lab = _state["title"]
    if lab is None:
        return
    lab.setText(current_title())
    _relayout_title()
    # al arrancar la barra todavía se está armando: volver a acomodar el ancho un momento después
    QtCore.QTimer.singleShot(300, _relayout_title)


def _relayout_title():
    lab = _state["title"]
    if lab is None:
        return
    try:
        area = lab.parentWidget().parentWidget()
        _relayout(_mw().menuBar(), area)
    except Exception:
        pass


def _update_max(*_a):
    btn = _state["max_btn"]
    if btn is None:
        return
    mw = _mw()
    style = mw.style()
    if mw.isMaximized():
        btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_TitleBarNormalButton))
        btn.setToolTip("Restaurar")
    else:
        btn.setIcon(style.standardIcon(QtWidgets.QStyle.SP_TitleBarMaxButton))
        btn.setToolTip("Maximizar")


def _fix_normal():
    """Arrancó maximizada: su "tamaño normal" es la pantalla entera y restaurar no cambiaría nada."""
    mw = _mw()
    if mw.isMaximized() or mw.isMinimized():
        return
    avail = mw.screen().availableGeometry()
    g = mw.geometry()
    if g.width() >= avail.width() * 0.95 and g.height() >= avail.height() * 0.95:
        w, h = int(avail.width() * 0.8), int(avail.height() * 0.8)
        mw.setGeometry(avail.x() + (avail.width() - w) // 2, avail.y() + (avail.height() - h) // 2, w, h)


def toggle_max():
    mw = _mw()
    if mw.isMaximized():
        mw.showNormal()
        QtCore.QTimer.singleShot(100, _fix_normal)  # después de que Windows termine de restaurar
    else:
        mw.showMaximized()
    QtCore.QTimer.singleShot(150, _update_max)


def _button(parent, icon, tip, slot, name):
    b = QtWidgets.QToolButton(parent)
    b.setObjectName(name)
    b.setAutoRaise(True)
    b.setIcon(icon)
    b.setToolTip(tip)
    b.setFixedWidth(BUTTON_W)
    b.setFocusPolicy(QtCore.Qt.NoFocus)
    b.clicked.connect(slot)
    return b


def _relayout(bar, area):
    """La barra de menús le da al área derecha el ancho que pedía al ponerla: volver a pedirlo."""
    lay = area.layout()
    if lay is not None:
        lay.invalidate()
        area.setMinimumWidth(lay.sizeHint().width())
    area.adjustSize()
    bar.setCornerWidget(area, QtCore.Qt.Corner.TopRightCorner)
    area.show()


def _add_buttons():
    mw = _mw()
    bar = mw.menuBar()
    area = bar.cornerWidget(QtCore.Qt.Corner.TopRightCorner)
    if area is None:
        area = QtWidgets.QWidget(bar)
        area.setLayout(QtWidgets.QHBoxLayout())
        bar.setCornerWidget(area, QtCore.Qt.Corner.TopRightCorner)
    lay = area.layout()
    if lay is None:
        lay = QtWidgets.QHBoxLayout(area)
    box = QtWidgets.QWidget(area)
    box.setObjectName(OBJECT_NAME)
    row = QtWidgets.QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    title = QtWidgets.QLabel(box)
    title.setObjectName("SWUI_WindowTitle")
    title.setContentsMargins(12, 0, 24, 0)
    row.addWidget(title)
    style = mw.style()
    row.addWidget(_button(box, style.standardIcon(QtWidgets.QStyle.SP_TitleBarMinButton), "Minimizar",
                          mw.showMinimized, "SWUI_WinMin"))
    mx = _button(box, style.standardIcon(QtWidgets.QStyle.SP_TitleBarMaxButton), "Maximizar", toggle_max,
                 "SWUI_WinMax")
    row.addWidget(mx)
    close = _button(box, style.standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton), "Cerrar", mw.close,
                    "SWUI_WinClose")
    close.setStyleSheet("QToolButton#SWUI_WinClose:hover { background: #e81123; }")
    row.addWidget(close)
    lay.addWidget(box)
    box.show()
    _state.update(box=box, title=title, max_btn=mx)
    try:
        mw.windowTitleChanged.connect(_update_title)
    except Exception:
        pass
    _update_title()
    _update_max()
    _relayout(bar, area)


def _remove_buttons():
    box = _state["box"]
    try:
        _mw().windowTitleChanged.disconnect(_update_title)
    except Exception:
        pass
    if box is not None:
        try:
            area = box.parentWidget()
            box.hide()
            box.setParent(None)
            box.deleteLater()
            if area is not None:
                area.setMinimumWidth(0)
                _relayout(_mw().menuBar(), area)
        except Exception:
            pass
    _state.update(box=None, title=None, max_btn=None)


# --- Mover (barra de menús) y cambiar el tamaño (bordes) ----------------------------------


class _BarFilter(QtCore.QObject):
    """Barra de menús: arrastrar la parte vacía mueve la ventana; doble clic maximiza / restaura.

    El movimiento arranca recién cuando el mouse se mueve con el botón apretado: si arrancara al
    apretar, Windows se queda con el mouse y el doble clic no llega.
    """

    press = None

    def eventFilter(self, bar, event):
        try:
            t = event.type()
            if t == QtCore.QEvent.MouseButtonRelease:
                self.press = None
                return False
            if t == QtCore.QEvent.MouseMove:
                if self.press is None or not (event.buttons() & QtCore.Qt.LeftButton):
                    return False
                gpos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                if (gpos - self.press).manhattanLength() < QtWidgets.QApplication.startDragDistance():
                    return True
                self.press = None
                handle = _mw().windowHandle()
                if handle is not None:
                    handle.startSystemMove()
                    QtCore.QTimer.singleShot(300, _update_max)
                return True
            if t not in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonDblClick):
                return False
            if event.button() != QtCore.Qt.LeftButton:
                return False
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if bar.actionAt(pos) is not None:
                return False  # un menú
            if t == QtCore.QEvent.MouseButtonDblClick:
                self.press = None
                toggle_max()
                return True
            self.press = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            return True
        except Exception:
            self.press = None
            FreeCAD.Console.PrintLog("[SWUI fork] Ventana sin marco: %s\n" % traceback.format_exc())
        return False


_SAVED = {"flags": None}


def _reshow(mw, frameless):
    """Sacar / devolver la barra de título.

    No se usa Qt.FramelessWindowHint: con eso Windows vuelve a maximizar la ventana apenas se la
    restaura (medido 06/11). Qt.CustomizeWindowHint sin las pistas de título deja el borde de
    Windows (cambiar tamaño, pegado a los bordes, maximizar de verdad) sin la barra de título.
    """
    maximized = mw.isMaximized()
    if frameless:
        if _SAVED["flags"] is not None:
            return
        _SAVED["flags"] = mw.windowFlags()
        flags = QtCore.Qt.Window | QtCore.Qt.CustomizeWindowHint
    else:
        if _SAVED["flags"] is None:
            return
        flags = _SAVED["flags"]
        _SAVED["flags"] = None
    mw.setWindowFlags(flags)
    if maximized:
        mw.showMaximized()
    else:
        mw.show()


def apply():
    """Ventana sin marco con los botones al lado de los menús (función pública, sin interfaz)."""
    if _state["on"]:
        return
    mw = _mw()
    try:
        _reshow(mw, True)
        _add_buttons()
        try:
            # maximizar / restaurar con Win + flechas o el pegado: cambiar el ícono del botón
            mw.windowHandle().windowStateChanged.connect(lambda *_a: QtCore.QTimer.singleShot(0, _update_max))
        except Exception:
            pass
        bar = mw.menuBar()
        if _state["bar_filter"] is None:
            _state["bar_filter"] = _BarFilter()
        bar.installEventFilter(_state["bar_filter"])
        _state["on"] = True
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Ventana sin marco:\n%s\n" % traceback.format_exc())
        restore()


def restore():
    """Volver a la ventana normal de Windows."""
    if not _state["on"] and _SAVED["flags"] is None and _state["box"] is None:
        return  # nunca se puso (p. ej. se salió del banco antes de que corriera apply)
    mw = _mw()
    try:
        if _state["bar_filter"] is not None:
            mw.menuBar().removeEventFilter(_state["bar_filter"])
        _remove_buttons()
        _reshow(mw, False)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Ventana sin marco:\n%s\n" % traceback.format_exc())
    _state["on"] = False


def install():
    """Enganchar a layout.enter() / layout.leave() del original (como acceso rápido)."""
    from swui import layout

    if getattr(layout.enter, "_swui_frameless", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        QtCore.QTimer.singleShot(0, apply)  # después de acceso rápido, que va primero en la barra
        return result

    def leave(_original=original_leave):
        restore()
        return _original()

    enter._swui_frameless = leave._swui_frameless = True
    layout.enter, layout.leave = enter, leave
