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
# Casilla activa: celeste en los paneles de croquis de SW 2018 (visto en Simetría, 02/11;
# los paneles de operaciones del fork usan el rosado de dress_up_panel)
ACTIVE_QSS = "background: #CCE4F7;"
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


def delete_constraints(sketch, indices):
    """
    Borrar relaciones / cotas del croquis sin dejar fórmulas colgadas (#66): las que leen una cota
    con nombre que se borra (en el croquis o en otro objeto, como Ecuaciones) se quedan con su valor
    de ahora, sin la fórmula. Antes quedaban apuntando a una cota que ya no existe y el croquis se
    rompía.
    """
    import re

    names = [sketch.Constraints[i].Name for i in set(indices)
             if 0 <= i < len(sketch.Constraints) and sketch.Constraints[i].Name]
    if names:
        # quién nombra al croquis: su nombre interno o <<etiqueta>> (o la etiqueta si es un nombre
        # válido); sin nada adelante solo vale dentro del mismo croquis. El "no pegado a" de adelante
        # evita tomar Sketch001.Constraints.X por Sketch.Constraints.X (revisión del 12/11)
        refs = [re.escape(sketch.Name), "<<%s>>" % re.escape(sketch.Label)]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", sketch.Label or ""):
            refs.append(re.escape(sketch.Label))
        pattern = re.compile(r"(?<![A-Za-z0-9_.<>])(?:(%s)\.|\.)?Constraints\.(?:%s)(?![A-Za-z0-9_])"
                             % ("|".join(refs), "|".join(re.escape(n) for n in names)))
        for obj in [o for o in sketch.Document.Objects if getattr(o, "ExpressionEngine", None)]:
            for path, expr in list(obj.ExpressionEngine):
                hit = any(m.group(1) or obj is sketch for m in pattern.finditer(expr))
                if hit:
                    obj.setExpression(path, None)  # queda el valor de ahora
    for index in sorted(set(indices), reverse=True):
        sketch.delConstraint(index)


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


def _merge_end(sketch, geo, axis_geo, axis):
    """
    Posición del extremo de una línea perpendicular al eje que cae sobre él, si nada más
    que el eje lo toca; si no, None. SW une esa línea con su copia en una sola (comparado
    en SW 2018, 02/11): queda una línea con el punto medio sobre el eje.
    """
    line = sketch.Geometry[geo]
    if _geo_type(line) != "LineSegment":
        return None
    d = line.EndPoint - line.StartPoint
    if d.Length < TOL or abs(d.normalize().dot(axis[1])) > 1e-7:
        return None
    for pos in (1, 2):
        p = sketch.getPoint(geo, pos)
        if (reflect(p, axis) - p).Length >= 1e-4:
            continue
        for c in sketch.Constraints:
            refs = [(getattr(c, "First", -2000), getattr(c, "FirstPos", 0)),
                    (getattr(c, "Second", -2000), getattr(c, "SecondPos", 0)),
                    (getattr(c, "Third", -2000), getattr(c, "ThirdPos", 0))]
            if (geo, pos) in refs and any(g not in (geo, axis_geo, -2000) for g, _p in refs):
                return None  # unido a otra entidad: no se puede estirar
        return pos
    return None


def _merge(sketch, geo, pos, axis_geo, axis):
    """Estirar la línea hasta su reflejo (una sola línea, punto medio sobre el eje)."""
    import Sketcher

    for index in range(len(sketch.Constraints) - 1, -1, -1):
        c = sketch.Constraints[index]
        if (getattr(c, "First", None), getattr(c, "FirstPos", None)) == (geo, pos) or \
                (getattr(c, "Second", None), getattr(c, "SecondPos", None)) == (geo, pos):
            sketch.delConstraint(index)  # lo que lo ataba al eje
    far = sketch.getPoint(geo, 3 - pos)
    # Sin el resolvedor (moveGeometry arrastra todo el croquis): la línea, cambiada en la lista
    geos = list(sketch.Geometry)
    line = geos[geo]
    if pos == 1:
        line.StartPoint = reflect(far, axis)
    else:
        line.EndPoint = reflect(far, axis)
    geos[geo] = line
    sketch.Geometry = geos
    sketch.solve()
    sym = Sketcher.Constraint("Symmetric", geo, 1, geo, 2, axis_geo)
    if _try_add(sketch, sym):
        return
    # La simetría de los extremos ya fija la dirección: la horizontal/vertical de la línea sobra
    for index in range(len(sketch.Constraints) - 1, -1, -1):
        c = sketch.Constraints[index]
        if c.Type in ("Horizontal", "Vertical", "Perpendicular") and geo in (c.First, getattr(c, "Second", -2000)):
            sketch.delConstraint(index)
    _try_add(sketch, sym)


def _mirror(sketch, geo_ids, axis_geo, axis, copy):
    merged = {}
    if copy:
        for g in geo_ids:
            pos = _merge_end(sketch, g, axis_geo, axis)
            if pos:
                merged[g] = pos
    rest = [g for g in geo_ids if g not in merged]
    old_constraints = list(sketch.Constraints)
    count = len(old_constraints)
    new = list(sketch.addSymmetric(rest, axis_geo, 0) or []) if rest else []
    if len(new) != len(rest):
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
    for orig, twin in zip(rest, new):
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
    for g, pos in merged.items():
        _merge(sketch, g, pos, axis_geo, axis)
        end = sketch.getPoint(g, pos)
        for twin in new:  # el extremo nuevo, unido a las copias que llegan ahí
            for tpos in point_positions(sketch.Geometry[twin]):
                if (sketch.getPoint(twin, tpos) - end).Length < 1e-4:
                    _try_add(sketch, Sketcher.Constraint("Coincident", g, pos, twin, tpos))
    for c in copied:
        _try_add(sketch, c)
    sketch.solve()
    twins = dict(zip(rest, new))
    return [twins.get(g, g) for g in geo_ids]  # una línea unida es su propia copia


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
    """Nombre como en la lista de SW (Línea3, Arco1, Punto2...); SW llama Arco también al círculo."""
    if geo == -1:
        return "Eje horizontal"
    if geo == -2:
        return "Eje vertical"
    if geo <= -3:
        return "Referencia%d" % (-geo - 2)
    names = {"LineSegment": "Línea", "Circle": "Arco", "ArcOfCircle": "Arco", "Point": "Punto",
             "Ellipse": "Elipse", "ArcOfEllipse": "Elipse parcial", "BSplineCurve": "Spline"}

    def label(g):
        return names.get(_geo_type(g), "Entidad")

    name = label(sketch.Geometry[geo])
    n = sum(1 for g in sketch.Geometry[:geo + 1] if label(g) == name)
    return "%s%d" % (name, n)


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
        self.hover = None  # punto del croquis bajo el mouse (vistas previas que lo siguen)
        self.mouse = _ViewMouse(self)
        self.viewports = []
        for vp in _viewports():
            vp.installEventFilter(self.mouse)
            self.viewports.append(vp)

    # --- interfaz

    def _build(self):
        from swui.fork.dress_up_panel import MISSING_COLOR

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
        if self.MESSAGE:
            msg = QtWidgets.QLabel(self.MESSAGE)
            msg.setWordWrap(True)
            msg.setStyleSheet("background: #FFFBE0; border: 1px solid #E0D890; padding: 4px;")
            box.addWidget(msg)
        self.activators = []  # guardados: si no, Python los borra
        self.boxes = {}  # casillas de selección {nombre: widget}; la activa se pinta
        self.points = {}  # casillas de punto {nombre: Vector del croquis o None}
        self.entities = None
        self._build_body(box)
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: %s;" % MISSING_COLOR)
        self.message.hide()
        box.addWidget(self.message)
        self.widget = w
        self._paint_active()

    def _build_body(self, box):
        """Como el panel de Simetría de SW: grupo Opciones con la lista y lo propio."""
        group = QtWidgets.QGroupBox("Opciones")
        self.options = QtWidgets.QVBoxLayout(group)
        self.options.addWidget(QtWidgets.QLabel(self.ENTITIES_LABEL))
        self.options.addWidget(self._make_list())
        self._build_options(self.options)
        box.addWidget(group)

    def _make_list(self):
        """Lista de entidades (casilla "entities"), con Supr y clic derecho Borrar como SW."""
        from swui.fork.dress_up_panel import QAction

        self.entities = QtWidgets.QListWidget()
        self.entities.setMinimumHeight(70)
        self.entities.setMaximumHeight(110)
        self.entities.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        act = QAction("Borrar", self.entities)
        act.triggered.connect(lambda *_a: self.remove_current())
        self.entities.addAction(act)
        act = QAction("Borrar selecciones", self.entities)
        act.triggered.connect(lambda *_a: self.clear_entities())
        self.entities.addAction(act)
        self.keys = _Keys(self)
        self.entities.installEventFilter(self.keys)
        self.activators.append(_Activate(self, "entities"))
        self.entities.viewport().installEventFilter(self.activators[-1])
        self.boxes["entities"] = self.entities
        return self.entities

    def _ref_box(self, name):
        """Casilla de una sola referencia (línea, punto): un clic la activa."""
        edit = QtWidgets.QLineEdit()
        edit.setReadOnly(True)
        self.activators.append(_Activate(self, name))
        edit.installEventFilter(self.activators[-1])
        self.boxes[name] = edit
        return edit

    def _point_box(self, name):
        """Casilla de un punto: se elige con un clic en la vista (se engancha a los puntos)."""
        self.points[name] = None
        return self._ref_box(name)

    def _build_options(self, layout):
        pass

    def set_active(self, which):
        self.active = which
        self._paint_active()

    def _paint_active(self):
        for name, w in self.boxes.items():
            w.setStyleSheet(self.active_qss if self.active == name else "")

    def _refresh_list(self):
        if self.entities is not None:
            self.entities.clear()
            for g in self.geos:
                self.entities.addItem(sw_name(self.sketch, g))
        for name, p in self.points.items():
            self.boxes[name].setText("" if p is None else point_text(p))

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
        if self.entities is None:
            return
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

    # --- mouse en la vista

    def view_event(self, vp, event, kind):
        """
        Mouse en la vista 3D con el panel abierto. Con una casilla de punto activa, el clic
        elige el punto (enganchado a un punto del croquis cercano) y no le llega al croquis.
        Si la vista previa sigue al mouse, el clic termina (como SW). True: el evento no sigue.
        """
        if kind == "move":
            self.hover = sketch_point(self.sketch, vp, event)
            if self._follows_mouse():
                self._draw()
            return False
        if event.button() != QtCore.Qt.LeftButton:
            return False
        if self.active in self.points:
            p = snap_point(self.sketch, vp, event)
            if p is not None:
                self.points[self.active] = p
                self._point_picked(self.active)
                self.update()
            return True
        if self._follows_mouse():
            self.hover = snap_point(self.sketch, vp, event) if self.SNAP_TARGET else \
                sketch_point(self.sketch, vp, event)
            QtCore.QTimer.singleShot(0, self._click_follow)
            return True
        return False

    def _click_follow(self):
        """Clic con la vista previa siguiendo al mouse: por defecto termina (Equidistanciar)."""
        self.accept()

    SNAP_TARGET = False  # el clic que termina se engancha a los puntos (Mover: Hasta)

    def _follows_mouse(self):
        """¿La vista previa sigue al mouse ahora? (Desde/Hasta, lado de Equidistanciar)"""
        return False

    def _point_picked(self, name):
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
        for vp in self.viewports:
            try:
                vp.removeEventFilter(self.mouse)
            except Exception:
                pass
        self.viewports = []
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


class _ViewMouse(QtCore.QObject):
    """Filtro en las vistas 3D mientras el panel está abierto."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.swallow_release = False

    def eventFilter(self, vp, event):
        t = event.type()
        try:
            if t == QtCore.QEvent.MouseMove:
                return self.panel.view_event(vp, event, "move")
            if t == QtCore.QEvent.MouseButtonPress:
                if self.panel.view_event(vp, event, "press"):
                    self.swallow_release = True
                    return True
            elif t == QtCore.QEvent.MouseButtonRelease and self.swallow_release:
                self.swallow_release = False
                return True
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Mouse en la vista:\n%s\n" % traceback.format_exc())
        return False


def _viewports():
    out = []
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != "Gui::View3DInventor":
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                out.append(gv.viewport())
    except Exception:
        pass
    return out


def _event_coin(vp, event):
    """Posición del mouse en coordenadas de Coin (píxeles reales, y desde abajo)."""
    pos = event.position() if hasattr(event, "position") else QtCore.QPointF(event.pos())
    r = vp.devicePixelRatioF()
    return pos.x() * r, (vp.height() - pos.y()) * r


def sketch_point(sketch, vp, event):
    """Punto del plano del croquis (coordenadas del croquis) bajo el mouse."""
    try:
        view = FreeCADGui.ActiveDocument.ActiveView
        cx, cy = _event_coin(vp, event)
        get = getattr(view, "getPointOnFocalPlane", None) or view.getPoint
        p = get(int(cx), int(cy))
        d = view.getViewDirection()
        inv = sketch.getGlobalPlacement().inverse()
        pl = inv.multVec(p)
        dl = inv.Rotation.multVec(d)
        if abs(dl.z) > 1e-9:
            pl = pl + dl * (-pl.z / dl.z)
        return FreeCAD.Vector(pl.x, pl.y, 0)
    except Exception:
        return None


SNAP_PX = 8


def sketch_vertices(sketch):
    """Puntos del croquis para enganchar: extremos, centros, puntos sueltos y el origen."""
    out = [FreeCAD.Vector(0, 0, 0)]
    for g, geo in enumerate(sketch.Geometry):
        for pos in point_positions(geo):
            try:
                out.append(sketch.getPoint(g, pos))
            except Exception:
                pass
    return out


def snap_point(sketch, vp, event):
    """El punto del croquis cerca del mouse (SNAP_PX), o si no el punto del plano bajo el mouse."""
    try:
        view = FreeCADGui.ActiveDocument.ActiveView
        cx, cy = _event_coin(vp, event)
        plc = sketch.getGlobalPlacement()
        best = None
        for p in sketch_vertices(sketch):
            q = view.getPointOnViewport(plc.multVec(p))
            dist = math.hypot(q[0] - cx, q[1] - cy)
            if dist <= SNAP_PX * vp.devicePixelRatioF() and (best is None or dist < best[0]):
                best = (dist, p)
        if best is not None:
            return FreeCAD.Vector(best[1].x, best[1].y, 0)
    except Exception:
        pass
    return sketch_point(sketch, vp, event)


def point_text(p):
    """Cómo se ve un punto elegido en su casilla."""
    if p.Length < 1e-7:
        return "Origen"
    return "Punto (%s; %s)" % (mm_text(p.x), mm_text(p.y))


def mm_text(v):
    return ("%.2f" % v).replace(".", ",")


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
    MESSAGE = ("Seleccione las entidades para crear la simetría y una línea de croquis o una "
               "arista lineal del modelo con respecto a las que crear la simetría.")
    ENTITIES_LABEL = "Entidades para simetría:"
    NOTHING = "Elija las entidades a simetrizar."

    def __init__(self, sketch):
        self.axis = None
        super().__init__(sketch)

    def _build_options(self, layout):
        self.copy = QtWidgets.QCheckBox("Copiar")
        self.copy.setChecked(True)
        self.copy.toggled.connect(lambda *_a: self._draw())
        layout.addWidget(self.copy)
        layout.addWidget(QtWidgets.QLabel("Con respecto a:"))
        self.axis_box = self._ref_box("axis")
        layout.addWidget(self.axis_box)

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
            return "Elija la línea con respecto a la cual crear la simetría (Con respecto a)."
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


# (comando, botón nativo que reemplaza, ícono, texto, ayuda, "módulo:clase del panel")
TOOLS = [
    (MIRROR, "Sketcher_Symmetry", "Sketcher_Symmetry", "Simetría de entidades",
     "Simetría de entidades del croquis respecto de una línea (como SW).",
     "swui.fork.sketch_entities:MirrorPanel"),
    ("SWUI_SketchMove", "Sketcher_Translate", "Sketcher_Translate", "Mover entidades",
     "Mover entidades del croquis Desde/Hasta o por X/Y (como SW).",
     "swui.fork.sketch_transform:MovePanel"),
    ("SWUI_SketchCopy", None, "Sketcher_Copy", "Copiar entidades",
     "Copiar entidades del croquis Desde/Hasta o por X/Y (como SW).",
     "swui.fork.sketch_transform:CopyPanel"),
    ("SWUI_SketchRotate", "Sketcher_Rotate", "Sketcher_Rotate", "Girar entidades",
     "Girar entidades del croquis alrededor de un punto (como SW).",
     "swui.fork.sketch_transform:RotatePanel"),
    ("SWUI_SketchScale", "Sketcher_Scale", "Sketcher_Scale", "Escalar entidades",
     "Escalar entidades del croquis desde un punto, con o sin copias (como SW).",
     "swui.fork.sketch_transform:ScalePanel"),
    ("SWUI_SketchLinearPattern", "Sketcher_RectangularArray", "Sketcher_RectangularArray",
     "Matriz lineal de croquis", "Matriz lineal de entidades del croquis en una o dos direcciones (como SW).",
     "swui.fork.sketch_transform:PatternPanel"),
    ("SWUI_SketchOffset", "Sketcher_Offset", "Sketcher_Offset", "Equidistanciar entidades",
     "Equidistanciar entidades del croquis (como SW): clic en una entidad y otro del lado elegido.",
     "swui.fork.sketch_offset:OffsetPanel"),
]


def panel_class(spec):
    import importlib

    module, name = spec.split(":")
    return getattr(importlib.import_module(module), name)


class _ToolCommand:
    def __init__(self, icon, menu, tip, spec):
        self.icon, self.menu, self.tip, self.spec = icon, menu, tip, spec

    def GetResources(self):
        return {"Pixmap": self.icon, "MenuText": self.menu, "ToolTip": self.tip, "CmdType": "ForEdit"}

    def IsActive(self):
        return editing_sketch() is not None

    def Activated(self):
        try:
            open_panel(panel_class(self.spec))
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (self.menu, traceback.format_exc()))


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


REPLACE = {native: cmd for cmd, native, *_r in TOOLS if native}
COPY = "SWUI_SketchCopy"
# Copiar entidades va en el desplegable después de Mover, como en SW (el original no lo tenía)
COPY_ENTRY = (COPY, "Elemente kopieren", {})


def install_ribbon():
    """En la pestaña Croquis, los botones nativos cambiados por los nuestros (mismo texto e ícono)."""
    from swui import ribbon_layout

    def walk(items):
        for i, entry in enumerate(list(items)):
            if isinstance(entry, tuple) and entry and entry[0] in REPLACE:
                index = items.index(entry)
                items[index] = (REPLACE[entry[0]],) + tuple(entry[1:])
                if entry[0] == "Sketcher_Translate" and not any(
                        isinstance(e, tuple) and e[0] == COPY for e in items):
                    items.insert(index + 1, COPY_ENTRY)
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
    for cmd, _native, icon, menu, tip, spec in TOOLS:
        try:
            FreeCADGui.addCommand(cmd, _ToolCommand(icon, menu, tip, spec))
        except Exception:
            pass  # ya registrado
    install_ribbon()
    try:
        _wrap_relations()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Panel de relaciones:\n%s\n" % traceback.format_exc())
    _installed = True
