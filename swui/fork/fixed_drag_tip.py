# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Aviso al arrastrar una pieza fija en un ensamblaje, como en SOLIDWORKS.

Medido en SW 2018 con el mouse (15/11): arrastrar un componente fijo no lo mueve y muestra junto
al cursor "El componente seleccionado está fijo. No se puede mover."; uno totalmente definido
tampoco se mueve, pero sin mensaje; uno suelto se mueve. FreeCAD no mueve la pieza fija pero no
avisa nada: este filtro solo agrega el globito; no come eventos ni cambia lo que hace FreeCAD.

Solo actúa con un ensamblaje en edición (el que se arrastra) y el botón izquierdo sin teclas.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

TEXT = "El componente seleccionado está fijo. No se puede mover."
VIEW_CLASS = "Gui::View3DInventor"
ASSEMBLY_VP = "AssemblyGui::ViewProviderAssembly"
MOVE_MIN_PX = 4.0  # menos que esto es un clic, no un arrastre

_filter = None


def component_name(subname):
    """Primer tramo del camino elegido ("Body001.Caja.Face6" -> "Body001"): el componente."""
    if not subname:
        return None
    first = subname.split(".", 1)[0]
    return first or None


def is_grounded(doc, name):
    """True si el objeto `name` del documento es un componente fijo (lo fija una unión Fijar)."""
    if doc is None or not name:
        return False
    comp = doc.getObject(name)
    if comp is None:
        return False
    return any(getattr(o, "ObjectToGround", None) is comp for o in comp.InList)


def grounded_at(gdoc, view, x, y, width, height):
    """
    Nombre del componente fijo bajo el punto (x, y) del área de dibujo de `view` (píxeles de Qt,
    y hacia abajo), o None. Solo con el ensamblaje de ESE documento (`gdoc`) en edición.
    """
    try:
        edit = gdoc.getInEdit() if gdoc else None
        if edit is None or getattr(edit, "TypeId", "") != ASSEMBLY_VP:
            return None
        size = view.getSize()
        vx = int(x * size[0] / max(width, 1))
        vy = int((height - y) * size[1] / max(height, 1))  # FreeCAD cuenta y hacia arriba
        info = view.getObjectInfo((vx, vy))
        if not info:
            return None
        # el camino arranca en el componente del ensamblaje ("Body001.Caja.Face6"); el documento
        # es el del ensamblaje en edición (info["Document"] es el de la pieza, el del objeto final)
        name = component_name(info.get("SubName"))
        return name if is_grounded(gdoc.Document, name) else None
    except Exception:
        return None


def _view_of(widget):
    """(documento de la interfaz, vista 3D) cuyo área de dibujo es widget, o (None, None)."""
    for name in FreeCAD.listDocuments():
        gdoc = FreeCADGui.getDocument(name)
        for view in gdoc.mdiViewsOfType(VIEW_CLASS) if gdoc else []:
            try:
                if view.graphicsView().viewport() == widget:
                    return gdoc, view
            except Exception:
                continue
    return None, None


def _xy(event):
    p = event.position() if hasattr(event, "position") else event.localPos()  # Qt6 / Qt5
    return p.x(), p.y()


class _TipFilter(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.press = None  # (widget, x, y) del apretar con el botón izquierdo
        self.grounded = None  # None = todavía no se miró qué hay bajo el mouse
        self.shown = False

    def eventFilter(self, obj, event):
        try:
            t = event.type()
            if t == QtCore.QEvent.Type.MouseButtonPress:
                self.press, self.grounded, self.shown = None, None, False
                if (event.button() == QtCore.Qt.MouseButton.LeftButton
                        and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier):
                    x, y = _xy(event)
                    self.press = (obj, x, y)
            elif t == QtCore.QEvent.Type.MouseMove and self.press is not None:
                if not (event.buttons() & QtCore.Qt.MouseButton.LeftButton) or obj is not self.press[0]:
                    self.press = None
                    return False
                x, y = _xy(event)
                dx, dy = x - self.press[1], y - self.press[2]
                if not self.shown and dx * dx + dy * dy < MOVE_MIN_PX * MOVE_MIN_PX:
                    return False
                if self.grounded is None:
                    # se mira una sola vez, recién al arrastrar (un clic no paga la búsqueda), en el
                    # punto donde se apretó: la pieza fija no se movió
                    gdoc, view = _view_of(obj)
                    self.grounded = bool(view is not None and grounded_at(
                        gdoc, view, self.press[1], self.press[2], obj.width(), obj.height()))
                if self.grounded:
                    self.shown = True
                    gp = obj.mapToGlobal(QtCore.QPoint(int(x), int(y)))
                    QtWidgets.QToolTip.showText(gp + QtCore.QPoint(16, 16), TEXT, obj)
                else:
                    self.press = None
            elif t == QtCore.QEvent.Type.MouseButtonRelease:
                self.press = None
        except Exception:
            self.press = None
        return False  # nunca come el evento: FreeCAD sigue haciendo lo suyo


def install():
    """Filtro en el área de dibujo de cada vista 3D (las abiertas y las que se abran)."""
    global _filter
    if _filter is not None:
        return
    _filter = _TipFilter()
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        mdi.subWindowActivated.connect(lambda *_a: _attach_all())
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Aviso de pieza fija: no se encontró el área de ventanas.\n")
    _attach_all()


def _attach_all():
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != VIEW_CLASS:
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if not vp.property("swui_fixed_tip"):
                    vp.setProperty("swui_fixed_tip", True)
                    vp.installEventFilter(_filter)
    except Exception:
        pass
