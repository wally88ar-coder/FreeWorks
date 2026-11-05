# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Agarraderas para cambiar el tamaño de un plano, como en SW 2018 (pedido del usuario, 04/11).

Relevado en SW con el mouse (04/11): al elegir un plano aparecen 8 agarraderas (4 esquinas y el
medio de cada lado); arrastrando una, el plano cambia de tamaño y desde ahí conserva ese tamaño (no
sigue más a la pieza; los otros planos sí). SW no vuelve solo al tamaño automático (dato del
usuario), así que acá tampoco.

Cómo:
  - plano elegido entero (del origen o de referencia, en la vista o en el árbol): 8 puntos celestes
    en una capa encima de todo (SoAnnotation en la raíz de la vista, sin elegirse);
  - filtro del mouse en la vista SOLO mientras hay un plano elegido: un clic sobre una agarradera
    (a menos de PICK_PX) la toma y FreeCAD no recibe ese clic; al mover, el rectángulo sigue al
    punto del plano bajo el mouse (`sketch_entities.sketch_point`); al soltar se guarda;
  - el tamaño se guarda en la propiedad oculta `SWUI_PlaneRect` del plano (plane_look.RECT_PROP,
    nombre estable) en un paso de deshacer "Tamaño del plano" (Ctrl+Z lo devuelve).

Función pública (regla "panel = cara de una función"): `set_plane_rect(plane, rect)`.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

HANDLE_COLOR = (0.35, 0.65, 1.0)  # celeste de las agarraderas de SW
PICK_PX = 9
MIN_SIZE = 1.0  # mm
WB_NAME = "LikeSolidWorksUIWorkbench"

_state = {"sel_obs": None, "target": None, "overlay": None, "filter": None, "viewports": [],
          "drag": None, "hover": False}


# --- Lógica (sin interfaz) ---------------------------------------------------------------


def handle_points(rect):
    """Las 8 agarraderas en coordenadas del plano: 4 esquinas y el medio de cada lado."""
    x0, y0, x1, y1 = rect
    xm, ym = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (xm, y0), (x1, ym), (xm, y1), (x0, ym)]


def drag_rect(rect, index, x, y):
    """Rectángulo nuevo al llevar la agarradera `index` al punto (x, y) del plano."""
    x0, y0, x1, y1 = rect
    moves_x = {0: "x0", 3: "x0", 7: "x0", 1: "x1", 2: "x1", 5: "x1"}
    moves_y = {0: "y0", 1: "y0", 4: "y0", 2: "y1", 3: "y1", 6: "y1"}
    if moves_x.get(index) == "x0":
        x0 = min(x, x1 - MIN_SIZE)
    elif moves_x.get(index) == "x1":
        x1 = max(x, x0 + MIN_SIZE)
    if moves_y.get(index) == "y0":
        y0 = min(y, y1 - MIN_SIZE)
    elif moves_y.get(index) == "y1":
        y1 = max(y, y0 + MIN_SIZE)
    return x0, y0, x1, y1


def set_plane_rect(plane, rect):
    """Fijar el tamaño del plano (como las agarraderas de SW), en un paso de deshacer."""
    from swui.fork import plane_look as pl

    doc = plane.Document
    doc.openTransaction("Tamaño del plano")
    try:
        if not hasattr(plane, pl.RECT_PROP):
            plane.addProperty("App::PropertyFloatList", pl.RECT_PROP, "SWUI",
                              "Tamaño del plano puesto con las agarraderas (x0, y0, x1, y1)")
            plane.setEditorMode(pl.RECT_PROP, 2)  # oculta
            try:
                plane.setPropertyStatus(pl.RECT_PROP, ["Output", "NoRecompute"])
            except Exception:
                pass
        setattr(plane, pl.RECT_PROP, [float(v) for v in rect])
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    pl.refresh(doc)


# --- Dibujo de las agarraderas -----------------------------------------------------------


def _target():
    t = _state["target"]
    if t is None:
        return None
    try:
        return FreeCAD.getDocument(t[0]).getObject(t[1])
    except Exception:
        return None


def _hide_overlay():
    ov = _state["overlay"]
    _state["overlay"] = None
    if ov is None:
        return
    try:
        ov["parent"].removeChild(ov["root"])
    except Exception:
        pass


def _draw(plane, rect):
    from pivy import coin

    from swui.fork import plane_look as pl

    ov = _state["overlay"]
    if ov is None or ov.get("doc") != plane.Document.Name:
        _hide_overlay()
        try:
            parent = FreeCADGui.getDocument(plane.Document.Name).ActiveView.getSceneGraph()
        except Exception:
            return
        root = coin.SoAnnotation()
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        color = coin.SoBaseColor()
        color.rgb = HANDLE_COLOR
        xf = coin.SoTransform()
        coords = coin.SoCoordinate3()
        marks = coin.SoMarkerSet()
        marks.markerIndex = coin.SoMarkerSet.CIRCLE_FILLED_9_9
        for n in (pick, color, xf, coords, marks):
            root.addChild(n)
        parent.addChild(root)
        ov = {"doc": plane.Document.Name, "parent": parent, "root": root, "xf": xf, "coords": coords}
        _state["overlay"] = ov
    try:
        m = plane.getGlobalPlacement().toMatrix()
    except Exception:
        m = plane.Placement.toMatrix()
    ov["xf"].setMatrix(pl._coin_matrix(m))
    pts = [(x, y, 0) for x, y in handle_points(rect)]
    ov["coords"].point.setValues(0, len(pts), pts)
    ov["coords"].point.setNum(len(pts))


# --- Selección -----------------------------------------------------------------------------


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _update_target():
    from swui.fork import plane_look as pl

    if _state["drag"] is not None:
        return
    target = None
    try:
        if _in_workbench():
            sels = FreeCADGui.Selection.getSelectionEx("*")
            if len(sels) == 1:
                s = sels[0]
                subs = [x for x in (s.SubElementNames or []) if x]
                if not subs and getattr(s.Object, "TypeId", "") in pl.PLANES:
                    target = s.Object
    except Exception:
        target = None
    if target is None:
        _state["target"] = None
        _hide_overlay()
        _filters(False)
        return
    _state["target"] = (target.Document.Name, target.Name)
    try:
        _draw(target, pl.plane_rect(target))
        _filters(True)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Agarraderas: %s\n" % traceback.format_exc())


class _SelObserver:
    def addSelection(self, *_a):
        QtCore.QTimer.singleShot(0, _update_target)

    def removeSelection(self, *_a):
        QtCore.QTimer.singleShot(0, _update_target)

    def setSelection(self, *_a):
        QtCore.QTimer.singleShot(0, _update_target)

    def clearSelection(self, *_a):
        QtCore.QTimer.singleShot(0, _update_target)


# --- Mouse ----------------------------------------------------------------------------------


def _hit(plane, rect, vp, event):
    """Número de la agarradera bajo el mouse, o None."""
    from swui.fork import sketch_entities as se

    try:
        view = FreeCADGui.getDocument(plane.Document.Name).ActiveView
        gp = plane.getGlobalPlacement()
        cx, cy = se._event_coin(vp, event)
        limit = PICK_PX * vp.devicePixelRatioF()
        best, best_d = None, None
        for i, (x, y) in enumerate(handle_points(rect)):
            sx, sy = view.getPointOnViewport(gp.multVec(FreeCAD.Vector(x, y, 0)))
            d = ((sx - cx) ** 2 + (sy - cy) ** 2) ** 0.5
            if d <= limit and (best_d is None or d < best_d):
                best, best_d = i, d
        return best
    except Exception:
        return None


class _Mouse(QtCore.QObject):
    def eventFilter(self, vp, event):
        try:
            t = event.type()
            plane = _target()
            if plane is None:
                return False
            from swui.fork import plane_look as pl

            drag = _state["drag"]
            if t == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                rect = pl.plane_rect(plane)
                idx = _hit(plane, rect, vp, event)
                if idx is None:
                    return False
                _state["drag"] = {"index": idx, "rect": rect, "start": rect}
                return True
            if t == QtCore.QEvent.MouseMove:
                if drag is not None:
                    from swui.fork import sketch_entities as se

                    p = se.sketch_point(plane, vp, event)
                    if p is not None:
                        drag["rect"] = drag_rect(drag["start"], drag["index"], p.x, p.y)
                        pl.show_rect(plane, drag["rect"])
                        _draw(plane, drag["rect"])
                    return True
                near = _hit(plane, pl.plane_rect(plane), vp, event) is not None
                if near != _state["hover"]:
                    _state["hover"] = near
                    if near:
                        vp.setCursor(QtGui.QCursor(QtCore.Qt.SizeAllCursor))
                    else:
                        vp.unsetCursor()
                return False
            if t == QtCore.QEvent.MouseButtonRelease and drag is not None:
                _state["drag"] = None
                if drag["rect"] != drag["start"]:
                    set_plane_rect(plane, drag["rect"])
                QtCore.QTimer.singleShot(0, _update_target)
                return True
            if t == QtCore.QEvent.KeyPress and drag is not None and event.key() == QtCore.Qt.Key_Escape:
                _state["drag"] = None
                pl.show_rect(plane, drag["start"])
                _draw(plane, drag["start"])
                return True
        except Exception:
            _state["drag"] = None
            FreeCAD.Console.PrintError("[SWUI fork] Agarraderas del plano:\n%s\n" % traceback.format_exc())
        return False


def _filters(on):
    from swui.fork import sketch_entities as se

    if _state["filter"] is None:
        _state["filter"] = _Mouse()
    for vp in list(_state["viewports"]):
        try:
            vp.removeEventFilter(_state["filter"])
            if _state["hover"]:
                vp.unsetCursor()
        except Exception:
            pass
    _state["viewports"] = []
    _state["hover"] = False
    if not on:
        return
    for vp in se._viewports():
        try:
            vp.installEventFilter(_state["filter"])
            vp.setMouseTracking(True)
            _state["viewports"].append(vp)
        except Exception:
            pass


def install():
    if _state["sel_obs"] is None:
        _state["sel_obs"] = _SelObserver()
        FreeCADGui.Selection.addObserver(_state["sel_obs"])
