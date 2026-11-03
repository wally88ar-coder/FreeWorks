# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Herramientas de entidades del croquis como en SOLIDWORKS (Simetría de entidades...).

En FreeCAD 1.1.4 los botones nativos (Sketcher_Symmetry, Sketcher_Offset...) están
en gris si no hay nada elegido: toman la selección al hacer clic. En SW el botón
siempre anda: abre su panel con un cuadro "Entidades a ..." y se marcan en pantalla,
con vista previa al momento.

Acá cada herramienta es:
- una función pública que hace el trabajo sin panel (para la IA y las pruebas):
  mirror_entities(...). Por debajo usa las funciones del croquis de FreeCAD
  (addSymmetric) y relaciones nativas: nada propio queda en el archivo.
- un panel SW que se mete arriba en el panel del croquis (como el panel de
  relaciones del original), junta las entidades con clics y llama a la función.

Simetría (como SW 2018): copia simétrica unida al original con relaciones
"Simétrico" (un punto por lugar; si el punto cae sobre la línea, queda coincidente
y sobre la línea), círculos iguales; sin Copiar, las entidades pasan al otro lado.
Las relaciones que sobran (las que FreeCAD marcaría como redundantes) no se ponen.
"""

import math
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

WB_NAME = "LikeSolidWorksUIWorkbench"
SKETCH = "Sketcher::SketchObject"
MIRROR = "SWUI_SketchMirror"
TOL = 1e-6
PICKED_COLOR = (0.26, 0.53, 0.71)  # celeste SW (igual que look_sw / dress_up_panel)
AXIS_COLOR = (0.85, 0.2, 0.6)  # la línea de simetría elegida
PREVIEW_COLOR = (1.0, 0.86, 0.0)  # amarillo de la vista previa de SW
PICKED_WIDTH = 4
PREVIEW_WIDTH = 2

_state = {"panel": None}


# --- Cuentas (sin interfaz) ---------------------------------------------


def _geo_type(geo):
    return type(geo).__name__


def point_positions(geo):
    """Posiciones de punto de una geometría del croquis (1 inicio, 2 fin, 3 centro)."""
    kind = _geo_type(geo)
    if kind == "Point":
        return [1]
    if kind in ("Circle", "Ellipse"):
        return [3]
    if kind == "LineSegment":
        return [1, 2]
    if kind in ("BSplineCurve",):
        return [1, 2]
    return [1, 2, 3]  # arcos (de círculo, elipse, parábola, hipérbola)


def axis_line(sketch, geo):
    """(punto, dirección unitaria) de la línea geo del croquis (-1 eje H, -2 eje V, <=-3 referencias)."""
    if geo >= 0:
        line = sketch.Geometry[geo]
    else:
        line = sketch.ExternalGeo[-geo - 1]
    if _geo_type(line) != "LineSegment":
        return None
    a, b = line.StartPoint, line.EndPoint
    d = b - a
    if d.Length < TOL:
        return None
    d.normalize()
    return a, d


def reflect(p, axis):
    """Punto p reflejado respecto de la línea axis = (punto, dirección unitaria), en el plano XY."""
    a, d = axis
    v = p - a
    along = d * v.dot(d)
    perp = v - along
    return a + along - perp


def is_line(sketch, geo):
    try:
        return axis_line(sketch, geo) is not None
    except Exception:
        return False


def _issues(sketch):
    out = set()
    for name in ("RedundantConstraints", "ConflictingConstraints", "PartiallyRedundantConstraints",
                 "MalformedConstraints"):
        try:
            out |= set(getattr(sketch, name))
        except Exception:
            pass
    return out


def _try_add(sketch, constraint):
    """Agregar la relación si no deja el croquis redundante ni en conflicto. True si quedó."""
    before = _issues(sketch)
    try:
        index = sketch.addConstraint(constraint)
    except Exception:
        return False
    sketch.solve()
    if _issues(sketch) - before:
        sketch.delConstraint(index)
        sketch.solve()
        return False
    return True


def _coincident_groups(sketch, geo_ids, constraints):
    """Puntos de las entidades unidos por relaciones (coincidente, tangente en extremos...)."""
    parent = {}

    def find(k):
        while parent.setdefault(k, k) != k:
            k = parent[k]
        return k

    chosen = set(geo_ids)
    for c in constraints:
        first, fpos = getattr(c, "First", -2000), getattr(c, "FirstPos", 0)
        second, spos = getattr(c, "Second", -2000), getattr(c, "SecondPos", 0)
        if c.Type not in ("Coincident", "Tangent", "Perpendicular") or not fpos or not spos:
            continue
        if first in chosen and second in chosen:
            parent[find((first, fpos))] = find((second, spos))
    return find


def mirror_entities(sketch, geo_ids, axis_geo, copy=True):
    """
    Simetría de entidades (SW). sketch: croquis; geo_ids: números de geometría (desde 0);
    axis_geo: la línea de simetría (número de una línea del croquis, -1 eje horizontal,
    -2 eje vertical, -3 en adelante referencias externas); copy: True deja el original
    (como la casilla Copiar de SW). Devuelve la lista de números de las entidades nuevas.
    Abre su propia transacción si no hay una abierta.
    """
    geo_ids = sorted(set(int(g) for g in geo_ids if 0 <= int(g) < sketch.GeometryCount and g != axis_geo))
    if not geo_ids:
        raise ValueError("No hay entidades para la simetría.")
    axis = axis_line(sketch, axis_geo)
    if axis is None:
        raise ValueError("La simetría necesita una línea.")
    doc = sketch.Document
    own = not doc.HasPendingTransaction
    if own:
        doc.openTransaction("Simetría de entidades")
    try:
        new = _mirror(sketch, geo_ids, axis_geo, axis, copy)
    except Exception:
        if own:
            doc.abortTransaction()
        raise
    if own:
        doc.commitTransaction()
    return new


def _mirror(sketch, geo_ids, axis_geo, axis, copy):
    old_constraints = list(sketch.Constraints)
    count = len(old_constraints)
    new = list(sketch.addSymmetric(geo_ids, axis_geo, 0) or [])
    if len(new) != len(geo_ids):
        raise RuntimeError("FreeCAD no hizo la simetría.")
    if not copy:
        # Las entidades pasan al otro lado con sus relaciones propias (copiadas por FreeCAD)
        sketch.delGeometries(geo_ids)
        sketch.solve()
        shift = lambda g: g - sum(1 for o in geo_ids if o < g)  # noqa: E731
        return [shift(g) for g in new]
    # Relaciones copiadas por FreeCAD: se sacan (copian cotas sueltas y se pisan con la
    # simetría) y se vuelven a probar al final, por si alguna hace falta.
    copied = []
    for index in range(len(sketch.Constraints) - 1, count - 1, -1):
        c = sketch.Constraints[index]
        if c.Type != "InternalAlignment":
            copied.insert(0, c)
            sketch.delConstraint(index)
    sketch.solve()
    import Sketcher

    find = _coincident_groups(sketch, geo_ids, old_constraints)
    done = set()
    for orig, twin in zip(geo_ids, new):
        geo = sketch.Geometry[orig]
        twin_pos = point_positions(sketch.Geometry[twin])
        for pos in point_positions(geo):
            key = find((orig, pos))
            if key in done:
                continue
            done.add(key)
            p = sketch.getPoint(orig, pos)
            m = reflect(p, axis)
            match = None
            for tpos in twin_pos:
                if (sketch.getPoint(twin, tpos) - m).Length < 1e-4:
                    match = tpos
                    break
            if match is None:
                continue
            if (p - m).Length < 1e-4:
                # Sobre la línea: el punto y su copia quedan unidos y sobre la línea
                _try_add(sketch, Sketcher.Constraint("Coincident", orig, pos, twin, match))
                _try_add(sketch, Sketcher.Constraint("PointOnObject", orig, pos, axis_geo))
            else:
                _try_add(sketch, Sketcher.Constraint("Symmetric", orig, pos, twin, match, axis_geo))
        if _geo_type(geo) in ("Circle", "Ellipse", "ArcOfCircle"):
            _try_add(sketch, Sketcher.Constraint("Equal", orig, twin))
    for c in copied:
        _try_add(sketch, c)
    sketch.solve()
    return new


def mirror_preview(sketch, geo_ids, axis_geo, number=48):
    """Listas de puntos GLOBALES de las entidades reflejadas (vista previa)."""
    axis = axis_line(sketch, axis_geo)
    if axis is None:
        return []
    plc = sketch.getGlobalPlacement()
    out = []
    for g in geo_ids:
        try:
            pts = _discretize(sketch.Geometry[g], number)
        except Exception:
            continue
        out.append([plc.multVec(reflect(p, axis)) for p in pts])
    return out


def _discretize(geo, number=48):
    if _geo_type(geo) == "Point":
        return [FreeCAD.Vector(geo.X, geo.Y, geo.Z)]
    return geo.toShape().discretize(Number=number)


def entity_lines(sketch, geo_ids, number=48):
    """Listas de puntos GLOBALES de entidades del croquis (geo < 0: ejes y referencias)."""
    plc = sketch.getGlobalPlacement()
    out = []
    for g in geo_ids:
        try:
            geo = sketch.Geometry[g] if g >= 0 else sketch.ExternalGeo[-g - 1]
            pts = _discretize(geo, number)
            if g == -1 or g == -2:
                # los ejes del croquis no tienen largo: un tramo visible
                a, d = axis_line(sketch, g)
                pts = [a - d * 1e4, a + d * 1e4]
        except Exception:
            continue
        out.append([plc.multVec(p) for p in pts])
    return out


# --- Selección del croquis ----------------------------------------------


def parse_sub(sketch, sub):
    """Nombre de selección del croquis -> número de geometría, o None (Edge3 -> 2, H_Axis -> -1...)."""
    sub = sub.split(".")[-1]
    try:
        if sub.startswith("Edge"):
            return int(sub[4:]) - 1
        if sub.startswith("ExternalEdge"):
            return -2 - int(sub[12:])
        if sub == "H_Axis":
            return -1
        if sub == "V_Axis":
            return -2
        if sub.startswith("Vertex"):
            geo, _pos = sketch.getGeoVertexIndex(int(sub[6:]) - 1)
            if geo >= 0 and _geo_type(sketch.Geometry[geo]) == "Point":
                return geo  # un punto suelto es una entidad
    except Exception:
        pass
    return None


def sw_name(sketch, geo):
    """Nombre como en la lista de SW (Línea3, Arco1, Punto2...), contando por tipo."""
    if geo == -1:
        return "Eje horizontal"
    if geo == -2:
        return "Eje vertical"
    if geo <= -3:
        return "Referencia%d" % (-geo - 2)
    names = {"LineSegment": "Línea", "Circle": "Círculo", "ArcOfCircle": "Arco", "Point": "Punto",
             "Ellipse": "Elipse", "ArcOfEllipse": "Arco de elipse", "BSplineCurve": "Spline"}
    kind = _geo_type(sketch.Geometry[geo])
    n = sum(1 for g in sketch.Geometry[:geo + 1] if _geo_type(g) == kind)
    return "%s%d" % (names.get(kind, "Entidad"), n)


def editing_sketch():
    try:
        vp = FreeCADGui.ActiveDocument.getInEdit()
        obj = vp.Object if vp is not None else None
    except Exception:
        return None
    return obj if obj is not None and getattr(obj, "TypeId", "") == SKETCH else None


# --- Dibujo sobre la vista ----------------------------------------------


def _lines_node(lines, color, width, dashed=False):
    from pivy import coin

    sep = coin.SoAnnotation()
    base = coin.SoBaseColor()
    base.rgb = color
    style = coin.SoDrawStyle()
    style.lineWidth = width
    style.pointSize = width * 2 + 1
    if dashed:
        style.linePattern = 0x0F0F
    sep.addChild(base)
    sep.addChild(style)
    for pts in lines:
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
        sep.addChild(coords)
        sep.addChild(coin.SoLineSet() if len(pts) > 1 else coin.SoPointSet())
    return sep


# --- Panel ----------------------------------------------------------------


class _Observer:
    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, *_a):
        if not self.panel.busy:
            QtCore.QTimer.singleShot(0, self.panel.take_selection)


class _AppKeys(QtCore.QObject):
    """
    Con el panel abierto, Esc lo cancela y Enter lo acepta (como SW), en la vista o en el
    panel. Sin esto, Esc de FreeCAD borra la selección y el segundo cierra el croquis.
    """

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    def eventFilter(self, _watched, event):
        kind = event.type()
        if kind not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
            return False
        key = event.key()
        if key not in (QtCore.Qt.Key_Escape, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            return False
        try:
            if QtWidgets.QApplication.activeWindow() is not FreeCADGui.getMainWindow():
                return False  # un diálogo aparte (p. ej. una cota) se maneja solo
        except Exception:
            return False
        event.accept()
        if kind == QtCore.QEvent.KeyPress:
            action = self.panel.reject if key == QtCore.Qt.Key_Escape else self.panel.accept
            QtCore.QTimer.singleShot(0, action)  # después de que una casilla numérica tome el valor
        return True


class _Keys(QtCore.QObject):
    """Supr en la lista borra el renglón (le gana al Supr de FreeCAD, que borraría entidades)."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
            return False
        key = event.key()
        if key in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace) and watched is self.panel.entities:
            event.accept()
            if kind == QtCore.QEvent.KeyPress:
                self.panel.remove_current()
            return True
        return False


class EntityPanel:
    """
    Lo común a las herramientas de entidades: recuadro arriba del panel del croquis con
    ✓ / ✗, mensaje, cuadro de entidades (rosado si está activo, como SW), selección por
    clic en el croquis, resaltado y vista previa. Cada herramienta define TITLE, MESSAGE,
    _build_options(layout), _preview_lines(), _run() y, si usa otra casilla, _pick_other.
    """

    TITLE = ""
    MESSAGE = ""
    ENTITIES_LABEL = "Entidades"
    NOTHING = "Elija las entidades."

    def __init__(self, sketch):
        self.sketch = sketch
        self.doc = sketch.Document
        self.busy = False
        self.geos = []  # entidades elegidas, en orden
        self.nodes = []
        self.active = "entities"
        self._build()
        self.observer = _Observer(self)
        FreeCADGui.Selection.addObserver(self.observer)
        self.watch = QtCore.QTimer()
        self.watch.setInterval(400)
        self.watch.timeout.connect(self._check_alive)
        self.watch.start()
        self.app_keys = _AppKeys(self)
        QtWidgets.QApplication.instance().installEventFilter(self.app_keys)

    # --- interfaz

    def _build(self):
        from swui.fork.dress_up_panel import ACTIVE_QSS, MISSING_COLOR

        self.active_qss = ACTIVE_QSS
        w = QtWidgets.QFrame()
        w.setObjectName("SWUI_SketchEntities")
        w.setFrameShape(QtWidgets.QFrame.StyledPanel)
        box = QtWidgets.QVBoxLayout(w)
        box.setContentsMargins(6, 6, 6, 6)
        head = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("<b>%s</b>" % self.TITLE)
        head.addWidget(title, 1)
        self.ok = QtWidgets.QToolButton()
        self.ok.setText("✓")
        self.ok.setToolTip("Aceptar (Enter)")
        self.ok.setStyleSheet("QToolButton { color: #1E8C2E; font-size: 16px; font-weight: bold; }")
        self.ok.clicked.connect(self.accept)
        self.cancel = QtWidgets.QToolButton()
        self.cancel.setText("✗")
        self.cancel.setToolTip("Cancelar (Esc)")
        self.cancel.setStyleSheet("QToolButton { color: #C00000; font-size: 16px; font-weight: bold; }")
        self.cancel.clicked.connect(self.reject)
        head.addWidget(self.ok)
        head.addWidget(self.cancel)
        box.addLayout(head)
        msg = QtWidgets.QLabel(self.MESSAGE)
        msg.setWordWrap(True)
        msg.setStyleSheet("background: #FFFBE0; border: 1px solid #E0D890; padding: 4px;")
        box.addWidget(msg)
        group = QtWidgets.QGroupBox("Opciones")
        self.options = QtWidgets.QVBoxLayout(group)
        self.options.addWidget(QtWidgets.QLabel(self.ENTITIES_LABEL))
        self.entities = QtWidgets.QListWidget()
        self.entities.setMinimumHeight(70)
        self.entities.setMaximumHeight(110)
        self.entities.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        from swui.fork.dress_up_panel import QAction

        act = QAction("Borrar", self.entities)
        act.triggered.connect(lambda *_a: self.remove_current())
        self.entities.addAction(act)
        act = QAction("Borrar selecciones", self.entities)
        act.triggered.connect(lambda *_a: self.clear_entities())
        self.entities.addAction(act)
        self.keys = _Keys(self)
        self.entities.installEventFilter(self.keys)
        self.activators = [_Activate(self, "entities")]  # guardados: si no, Python los borra
        self.entities.viewport().installEventFilter(self.activators[0])
        self.options.addWidget(self.entities)
        self._build_options(self.options)
        box.addWidget(group)
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: %s;" % MISSING_COLOR)
        self.message.hide()
        box.addWidget(self.message)
        self.widget = w
        self._paint_active()

    def _build_options(self, layout):
        pass

    def set_active(self, which):
        self.active = which
        self._paint_active()

    def _paint_active(self):
        self.entities.setStyleSheet(self.active_qss if self.active == "entities" else "")

    def _refresh_list(self):
        self.entities.clear()
        for g in self.geos:
            self.entities.addItem(sw_name(self.sketch, g))

    # --- selección

    def take_selection(self):
        if _state["panel"] is not self:
            return
        try:
            sels = FreeCADGui.Selection.getSelectionEx()
        except Exception:
            sels = []
        changed = False
        for sel in sels:
            if sel.Object is not self.sketch:
                continue
            for sub in sel.SubElementNames:
                geo = parse_sub(self.sketch, sub)
                if geo is None:
                    continue
                try:
                    changed = self._pick(geo) or changed
                except Exception:
                    FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (self.TITLE, traceback.format_exc()))
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        if changed:
            self.update()

    def _pick(self, geo):
        """Clic en una entidad: a la casilla activa. True si cambió algo."""
        if self.active == "entities":
            if geo < 0:
                return False
            if geo in self.geos:
                self.geos.remove(geo)  # segundo clic la saca, como SW
            else:
                self.geos.append(geo)
            return True
        return self._pick_other(geo)

    def _pick_other(self, geo):
        return False

    def start(self, picked):
        """Entidades elegidas antes de abrir (como SW): a la lista."""
        self.geos = [g for g in picked if g >= 0]
        self.update()

    def remove_current(self):
        row = self.entities.currentRow()
        if 0 <= row < len(self.geos):
            del self.geos[row]
            self.update()

    def clear_entities(self):
        self.geos = []
        self.update()

    # --- dibujo

    def update(self):
        self._refresh_list()
        self._refresh_other()
        self.message.hide()
        self._draw()

    def _refresh_other(self):
        pass

    def _overlays(self):
        nodes = []
        if self.geos:
            nodes.append(_lines_node(entity_lines(self.sketch, self.geos), PICKED_COLOR, PICKED_WIDTH))
        preview = self._preview_lines()
        if preview:
            nodes.append(_lines_node(preview, PREVIEW_COLOR, PREVIEW_WIDTH))
        return nodes

    def _preview_lines(self):
        return []

    def _graph(self):
        try:
            return FreeCADGui.getDocument(self.doc.Name).ActiveView.getSceneGraph()
        except Exception:
            return None

    def _undraw(self):
        graph = self._graph()
        for node in self.nodes:
            try:
                graph.removeChild(node)
            except Exception:
                pass
        self.nodes = []

    def _draw(self):
        self._undraw()
        graph = self._graph()
        if graph is None:
            return
        try:
            for node in self._overlays():
                graph.addChild(node)
                self.nodes.append(node)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Vista previa:\n%s\n" % traceback.format_exc())

    # --- cerrar

    def _check_alive(self):
        if editing_sketch() is not self.sketch:
            self.close()

    def _show_problem(self, text):
        self.message.setText(text)
        self.message.show()

    def _ready(self):
        return "" if self.geos else self.NOTHING

    def _run(self):
        pass

    def accept(self):
        if _state["panel"] is not self:
            return False  # ya cerrado (p. ej. Enter y clic en ✓ seguidos)
        problem = self._ready()
        if problem:
            self._show_problem(problem)
            return False
        try:
            self._run()
        except Exception as exc:
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (self.TITLE, traceback.format_exc()))
            self._show_problem("No se pudo: %s" % exc)
            return False
        try:
            self.sketch.recompute()
        except Exception:
            pass
        self.close()
        return True

    def reject(self):
        if _state["panel"] is self:
            self.close()
        return True

    def close(self):
        if _state["panel"] is self:
            _state["panel"] = None
        self.watch.stop()
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self.app_keys)
        except Exception:
            pass
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        self._undraw()
        try:
            self.widget.hide()
            self.widget.setParent(None)
            self.widget.deleteLater()
        except Exception:
            pass
        try:
            from swui import sketch_relations

            sketch_relations.refresh()
        except Exception:
            pass


class _Activate(QtCore.QObject):
    """Clic en una casilla de selección: pasa a ser la activa (rosada)."""

    def __init__(self, panel, which):
        super().__init__()
        self.panel = panel
        self.which = which

    def eventFilter(self, _watched, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.panel.set_active(self.which)
        return False


class MirrorPanel(EntityPanel):
    TITLE = "Simetría"
    MESSAGE = ("Seleccione las entidades a simetrizar y una línea de croquis o arista lineal "
               "respecto a la cual realizar la simetría.")
    ENTITIES_LABEL = "Entidades a simetrizar:"
    NOTHING = "Elija las entidades a simetrizar."

    def __init__(self, sketch):
        self.axis = None
        super().__init__(sketch)

    def _build_options(self, layout):
        self.copy = QtWidgets.QCheckBox("Copiar")
        self.copy.setChecked(True)
        self.copy.toggled.connect(lambda *_a: self._draw())
        layout.addWidget(self.copy)
        layout.addWidget(QtWidgets.QLabel("Respecto a:"))
        self.axis_box = QtWidgets.QLineEdit()
        self.axis_box.setReadOnly(True)
        self.activators.append(_Activate(self, "axis"))
        self.axis_box.installEventFilter(self.activators[-1])
        layout.addWidget(self.axis_box)

    def _paint_active(self):
        super()._paint_active()
        if hasattr(self, "axis_box"):
            self.axis_box.setStyleSheet(self.active_qss if self.active == "axis" else "")

    def _pick(self, geo):
        if self.active == "entities" and geo < 0 and is_line(self.sketch, geo):
            return self._pick_other(geo)  # un eje no se simetriza: es la línea
        return super()._pick(geo)

    def _pick_other(self, geo):
        if not is_line(self.sketch, geo):
            return False
        self.axis = geo
        if geo in self.geos:
            self.geos.remove(geo)
        return True

    def _refresh_other(self):
        self.axis_box.setText("" if self.axis is None else sw_name(self.sketch, self.axis))

    def _overlays(self):
        nodes = super()._overlays()
        if self.axis is not None:
            nodes.append(_lines_node(entity_lines(self.sketch, [self.axis]), AXIS_COLOR, PICKED_WIDTH))
        return nodes

    def _preview_lines(self):
        if self.axis is None or not self.geos:
            return []
        return mirror_preview(self.sketch, [g for g in self.geos if g != self.axis], self.axis)

    def _ready(self):
        if not self.geos:
            return self.NOTHING
        if self.axis is None:
            return "Elija la línea respecto a la cual hacer la simetría (Respecto a)."
        return ""

    def _run(self):
        mirror_entities(self.sketch, self.geos, self.axis, self.copy.isChecked())

    def start(self, picked):
        """Entidades elegidas antes de abrir (como SW): a la lista; la línea, a Respecto a."""
        for geo in picked:
            if geo < 0:
                if is_line(self.sketch, geo):
                    self.axis = geo
            elif geo not in self.geos:
                self.geos.append(geo)
        self.set_active("axis" if self.geos and self.axis is None else "entities")
        self.update()


# --- Mostrar el panel ------------------------------------------------------


def _host():
    """El panel del croquis (TaskPanel del panel Tareas), o None."""
    try:
        from swui import sketch_relations

        return sketch_relations._task_panel()
    except Exception:
        return None


def open_panel(cls):
    """Abrir el panel de una herramienta en el croquis en edición (con lo ya elegido)."""
    sketch = editing_sketch()
    if sketch is None:
        return None
    old = _state["panel"]
    if old is not None:
        old.close()
    picked = []
    try:
        for sel in FreeCADGui.Selection.getSelectionEx():
            if sel.Object is sketch:
                for sub in sel.SubElementNames:
                    geo = parse_sub(sketch, sub)
                    if geo is not None and geo not in picked:
                        picked.append(geo)
    except Exception:
        pass
    panel = cls(sketch)
    _state["panel"] = panel
    host = _host()
    if host is not None:
        layout = host.layout()
        if hasattr(layout, "insertWidget"):
            layout.insertWidget(0, panel.widget)
        else:
            layout.addWidget(panel.widget)
    else:
        panel.widget.setWindowFlags(QtCore.Qt.Tool)
        panel.widget.show()
    try:
        from swui import sketch_relations

        sketch_relations._hide()
        sketch_relations._raise_tasks()
    except Exception:
        pass
    panel.busy = True
    try:
        FreeCADGui.Selection.clearSelection()
    finally:
        panel.busy = False
    panel.start(picked)
    panel.widget.show()
    return panel


def active_panel():
    return _state["panel"]


# --- Comandos ---------------------------------------------------------------


class _MirrorCommand:
    def GetResources(self):
        return {
            "Pixmap": "Sketcher_Symmetry",
            "MenuText": "Simetría de entidades",
            "ToolTip": "Simetría de entidades del croquis respecto de una línea (como SW): "
                       "elegir antes o después de hacer clic.",
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return editing_sketch() is not None

    def Activated(self):
        try:
            open_panel(MirrorPanel)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Simetría de entidades:\n%s\n" % traceback.format_exc())


# --- Enganches ---------------------------------------------------------------


def _wrap_relations():
    """Mientras una herramienta de entidades está abierta, el panel de relaciones no aparece."""
    from swui import sketch_relations

    if getattr(sketch_relations.refresh, "_swui_entities", False):
        return
    original = sketch_relations.refresh

    def refresh():
        if _state["panel"] is not None:
            sketch_relations._hide()
            return
        original()

    refresh._swui_entities = True
    sketch_relations.refresh = refresh
    try:
        timer = sketch_relations._timer
        if timer is not None:
            timer.timeout.disconnect()
            timer.timeout.connect(lambda: sketch_relations.refresh())
    except Exception:
        pass


REPLACE = {"Sketcher_Symmetry": MIRROR}


def install_ribbon():
    """En la pestaña Croquis, los botones nativos cambiados por los nuestros (mismo texto e ícono)."""
    from swui import ribbon_layout

    def walk(items):
        for i, entry in enumerate(items):
            if isinstance(entry, tuple) and entry and entry[0] in REPLACE:
                items[i] = (REPLACE[entry[0]],) + tuple(entry[1:])
            elif isinstance(entry, dict):
                for key in ("flyout", "stack"):
                    if isinstance(entry.get(key), list):
                        walk(entry[key])
            elif isinstance(entry, list):
                walk(entry)

    walk(ribbon_layout.SKIZZE[1])


_installed = False


def install():
    global _installed
    if _installed:
        return
    try:
        FreeCADGui.addCommand(MIRROR, _MirrorCommand())
    except Exception:
        pass  # ya registrado
    install_ribbon()
    try:
        _wrap_relations()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Panel de relaciones:\n%s\n" % traceback.format_exc())
    _installed = True
