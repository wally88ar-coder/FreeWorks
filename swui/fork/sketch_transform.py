# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Mover, Copiar, Girar, Escalar entidades y Matriz lineal de croquis, como en SW 2018.

Cada herramienta es una función pública (sin panel; para la IA y las pruebas) y un
panel SW sobre la base de sketch_entities (relevados en SW 2018 el 02/11):
- Mover / Copiar: "Entidades a mover/copiar", "Conservar relaciones"; Parámetros
  Desde/Hasta ("Punto inicial", después el clic de destino termina) o X/Y (ΔX, ΔY,
  Repetir). SW recuerda el último modo.
- Girar: "Entidades a girar", "Conservar relaciones"; "Centro de rotación" y ángulo.
- Escala: "Entidades a ajustar la escala"; "Ajustar escala con" (punto), factor, Copiar
  y número de copias.
- Matriz lineal: Dirección 1 y 2 (eje, espaciado, Acotar espacio, cantidad, ángulo),
  "Entidades para la matriz".

Por debajo, funciones del croquis de FreeCAD: addCopy (copias con sus relaciones
internas), addRectangularArray (matriz con sus relaciones) y la geometría de cada
entidad (translate / rotate / scale) cambiada en la lista del croquis, sin el
resolvedor (moveGeometry arrastra todo el croquis).
Sin "Conservar relaciones" (como SW) se sacan las relaciones con lo que no se mueve.
"""

import math
import traceback

import FreeCAD

from swui.compat import QtCore, QtWidgets
from swui.fork import sketch_entities as se

V = FreeCAD.Vector
ORIENTATION = ("Horizontal", "Vertical", "Angle", "DistanceX", "DistanceY")
LENGTHS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter")


# --- Cuentas -----------------------------------------------------------------


def _refs(c):
    out = []
    for g, p in ((getattr(c, "First", -2000), getattr(c, "FirstPos", 0)),
                 (getattr(c, "Second", -2000), getattr(c, "SecondPos", 0)),
                 (getattr(c, "Third", -2000), getattr(c, "ThirdPos", 0))):
        if g != -2000:
            out.append((g, p))
    return out


def _touches(c, chosen):
    return any(g in chosen for g, _p in _refs(c))


def _external(c, chosen):
    """¿Ata una entidad elegida con algo que no se mueve (otra entidad, ejes, origen)?"""
    refs = _refs(c)
    if not any(g in chosen for g, _p in refs) or c.Type == "InternalAlignment":
        return False
    if any(g not in chosen for g, _p in refs):
        return True
    # Una sola entidad con su punto medido desde el origen (DistanceX/Y de un punto)
    return c.Type in ("DistanceX", "DistanceY") and len(refs) == 1 and refs[0][1] != 0


def _delete(sketch, indices):
    for index in sorted(set(indices), reverse=True):
        sketch.delConstraint(index)


def _transform(sketch, geo_ids, change, keep=False, angle=None, factor=None):
    """
    Cambiar las entidades en su lugar. change(geo) modifica una copia de la geometría.
    keep: conservar las relaciones con lo que no se mueve. angle (grados): se sacan las
    relaciones de orientación que dejan de valer. factor: las cotas de largo se escalan.
    """
    chosen = set(geo_ids)
    drop = []
    for index, c in enumerate(sketch.Constraints):
        if not _touches(c, chosen):
            continue
        if not keep and _external(c, chosen):
            drop.append(index)
        elif angle is not None and c.Type in ORIENTATION:
            turn = angle % 360.0
            if turn > 1e-9 and (c.Type not in ("Horizontal", "Vertical") or abs(turn - 180.0) > 1e-9):
                drop.append(index)
    _delete(sketch, drop)
    datums = []
    if factor is not None:
        for index, c in enumerate(sketch.Constraints):
            if c.Type in LENGTHS and all(g in chosen for g, _p in _refs(c)) and not _external(c, chosen):
                datums.append((index, c.Value * factor))
    geos = list(sketch.Geometry)
    for g in geo_ids:
        geo = geos[g]
        change(geo)
        geos[g] = geo
    sketch.Geometry = geos
    for index, value in datums:
        try:
            sketch.setDatum(index, value)  # mm; DistanceX/Y conservan el signo
        except Exception:
            pass
    sketch.solve()


def _translate(delta):
    def change(geo):
        geo.translate(delta)
    return change


def _rotate(center, angle):
    # giro alrededor de `center` como transformación completa. Geometry.rotate(placement) NO sirve:
    # en 1.1.4 descarta el centro (90° de (10, 0) alrededor de (0, 2) daba (4, 10) y no (2, 12):
    # Issue #41, medido con FreeCADCmd)
    matrix = FreeCAD.Placement(V(0, 0, 0), FreeCAD.Rotation(V(0, 0, 1), angle), center).toMatrix()

    def change(geo):
        geo.transform(matrix)
    return change


def _scale(center, factor):
    def change(geo):
        geo.scale(center, factor)
    return change


def _clean(geo_ids, sketch):
    return sorted(set(int(g) for g in geo_ids if 0 <= int(g) < sketch.GeometryCount))


def _transaction(sketch, name, work):
    doc = sketch.Document
    own = not doc.HasPendingTransaction
    if own:
        doc.openTransaction(name)
    try:
        out = work()
    except Exception:
        if own:
            doc.abortTransaction()
        raise
    if own:
        doc.commitTransaction()
    return out


def move_entities(sketch, geo_ids, delta, keep_relations=False):
    """Mover entidades (SW Mover entidades). delta: Vector del croquis (mm)."""
    geos = _clean(geo_ids, sketch)
    if not geos:
        raise ValueError("No hay entidades para mover.")
    return _transaction(sketch, "Mover entidades",
                        lambda: _transform(sketch, geos, _translate(V(delta.x, delta.y, 0)), keep_relations))


def copy_entities(sketch, geo_ids, delta):
    """Copiar entidades (SW Copiar entidades), con sus relaciones internas. Devuelve las nuevas."""
    geos = _clean(geo_ids, sketch)
    if not geos:
        raise ValueError("No hay entidades para copiar.")

    def work():
        new = list(sketch.addCopy(geos, V(delta.x, delta.y, 0), False) or [])
        sketch.solve()
        return new
    return _transaction(sketch, "Copiar entidades", work)


def rotate_entities(sketch, geo_ids, center, angle, keep_relations=False):
    """Girar entidades (SW Girar entidades) alrededor de center (Vector), angle en grados (antihorario)."""
    geos = _clean(geo_ids, sketch)
    if not geos:
        raise ValueError("No hay entidades para girar.")
    return _transaction(sketch, "Girar entidades",
                        lambda: _transform(sketch, geos, _rotate(center, angle), keep_relations, angle=angle))


def scale_entities(sketch, geo_ids, center, factor, copies=0):
    """
    Escalar entidades (SW Escala). copies=0: en su lugar; si no, esa cantidad de copias,
    cada una escalada factor veces respecto de la anterior. Devuelve las entidades nuevas.
    """
    geos = _clean(geo_ids, sketch)
    if not geos:
        raise ValueError("No hay entidades para escalar.")
    if factor <= 0:
        raise ValueError("El factor de escala tiene que ser mayor que cero.")

    def work():
        if not copies:
            # Las relaciones con lo que no se escala se sacan (si no, el resolvedor las vuelve atrás)
            _transform(sketch, geos, _scale(center, factor), False, factor=factor)
            return []
        out = []
        last = geos
        for _i in range(int(copies)):
            new = list(sketch.addCopy(last, V(0, 0, 0), False) or [])
            _transform(sketch, new, _scale(center, factor), True, factor=factor)
            out += new
            last = new
        return out
    return _transaction(sketch, "Escalar entidades", work)


def linear_pattern(sketch, geo_ids, count1=2, spacing1=10.0, angle1=0.0, count2=1, spacing2=10.0,
                   angle2=90.0, dim1=False, dim2=False):
    """
    Matriz lineal de croquis (SW). Dirección 1: count1 instancias a spacing1 (mm) con ángulo
    angle1 (grados desde X); dirección 2 igual. Con la segunda a 90° de la primera usa la
    matriz de FreeCAD (addRectangularArray, queda unida por relaciones); si no, copias sueltas.
    dim1 / dim2: dejar acotado el espaciado (si no, la cota queda como conducida).
    """
    geos = _clean(geo_ids, sketch)
    if not geos:
        raise ValueError("No hay entidades para la matriz.")
    count1, count2 = max(1, int(count1)), max(1, int(count2))
    if count1 * count2 < 2:
        raise ValueError("La matriz necesita al menos dos instancias.")
    a1, a2 = math.radians(angle1), math.radians(angle2)
    v1 = V(spacing1 * math.cos(a1), spacing1 * math.sin(a1), 0)
    v2 = V(spacing2 * math.cos(a2), spacing2 * math.sin(a2), 0)
    turn = (angle2 - angle1) % 360.0

    def work():
        start_geo = sketch.GeometryCount
        start = len(sketch.Constraints)
        if count1 > 1 and (count2 == 1 or abs(turn - 90.0) < 1e-6 or abs(turn - 270.0) < 1e-6):
            perp = 1.0 if count2 == 1 else (-1.0 if abs(turn - 90.0) < 1e-6 else 1.0) * spacing2 / spacing1
            sketch.addRectangularArray(geos, v1, False, count1, count2, True, perp)
            sketch.solve()
            _follow_original(sketch, geos, start_geo, start)
            spacing = [i for i in range(start, len(sketch.Constraints))
                       if sketch.Constraints[i].Type == "Distance"]
            # La primera cota es el espaciado de la dirección 1; la segunda, el de la 2
            for k, index in enumerate(spacing[:2]):
                if not (dim1 if k == 0 else dim2):
                    sketch.setDriving(index, False)
        else:
            for i in range(count1):
                for j in range(count2):
                    if i or j:
                        sketch.addCopy(geos, v1 * i + v2 * j, False)
        sketch.solve()
        return list(range(start_geo, sketch.GeometryCount))
    return _transaction(sketch, "Matriz lineal de croquis", work)


def _follow_original(sketch, geos, start_geo, start):
    """
    FreeCAD copia las cotas en cada instancia (cada copia con su largo propio): se cambian
    por Igual al original, así la matriz sigue al original como en SW. Cada instancia son
    las entidades en orden y una línea constructiva de la matriz.
    """
    import Sketcher

    block = len(geos) + 1
    twin = {}
    for g in range(start_geo, sketch.GeometryCount):
        k = (g - start_geo) % block
        if k < len(geos):
            twin[g] = geos[k]
    drop = []
    for index in range(start, len(sketch.Constraints)):
        c = sketch.Constraints[index]
        refs = _refs(c)
        if c.Type in LENGTHS and len({g for g, _p in refs}) == 1 and refs[0][0] in twin:
            drop.append((index, refs[0][0]))
    _delete(sketch, [i for i, _g in drop])
    sketch.solve()
    for _i, g in drop:
        se._try_add(sketch, Sketcher.Constraint("Equal", twin[g], g))


def _state_closed(panel):
    return se.active_panel() is not panel


def moved_lines(sketch, geo_ids, change, number=48):
    """Vista previa: puntos GLOBALES de las entidades cambiadas (sin tocar el croquis)."""
    plc = sketch.getGlobalPlacement()
    out = []
    for g in geo_ids:
        try:
            geo = sketch.Geometry[g]
            change(geo)
            pts = se._discretize(geo, number)
        except Exception:
            continue
        out.append([plc.multVec(p) for p in pts])
    return out


# --- Paneles -------------------------------------------------------------------


def _spin(value, suffix, low, high, decimals=2, step=1.0):
    box = QtWidgets.QDoubleSpinBox()
    box.setDecimals(decimals)
    box.setRange(low, high)
    box.setSuffix(suffix)
    box.setSingleStep(step)
    box.setValue(value)
    return box


def _count(value, low=1, high=1000):
    box = QtWidgets.QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    return box


def _row(label, widget):
    w = QtWidgets.QWidget()
    lay = QtWidgets.QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lab = QtWidgets.QLabel(label)
    lab.setMinimumWidth(24)
    lay.addWidget(lab)
    lay.addWidget(widget, 1)
    return w


class _MovePanel(se.EntityPanel):
    """Mover y Copiar (mismo panel en SW)."""

    TITLE = "Mover"
    GROUP = "Entidades a mover"
    NOTHING = "Elija las entidades a mover."
    KEEP = True  # Copiar en SW también tiene "Conservar relaciones"
    SNAP_TARGET = True
    _mode = "dh"  # SW recuerda el último modo usado (Desde/Hasta o X/Y), compartido con Copiar

    def _build_body(self, box):
        group = QtWidgets.QGroupBox(self.GROUP)
        lay = QtWidgets.QVBoxLayout(group)
        lay.addWidget(self._make_list())
        self.keep = QtWidgets.QCheckBox("Conservar relaciones")
        lay.addWidget(self.keep)
        box.addWidget(group)
        params = QtWidgets.QGroupBox("Parámetros")
        lay = QtWidgets.QVBoxLayout(params)
        self.dh = QtWidgets.QRadioButton("Desde/Hasta")
        self.xy = QtWidgets.QRadioButton("X/Y")
        lay.addWidget(self.dh)
        lay.addWidget(self.xy)
        self.dh_part = QtWidgets.QWidget()
        dl = QtWidgets.QVBoxLayout(self.dh_part)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(QtWidgets.QLabel("Punto inicial:"))
        dl.addWidget(self._point_box("base"))
        lay.addWidget(self.dh_part)
        self.xy_part = QtWidgets.QWidget()
        xl = QtWidgets.QVBoxLayout(self.xy_part)
        xl.setContentsMargins(0, 0, 0, 0)
        self.dx = _spin(0.0, " mm", -1e6, 1e6)
        self.dy = _spin(0.0, " mm", -1e6, 1e6)
        for b in (self.dx, self.dy):
            b.valueChanged.connect(lambda *_a: self._draw())
        xl.addWidget(_row("ΔX", self.dx))
        xl.addWidget(_row("ΔY", self.dy))
        lay.addWidget(self.xy_part)
        self.repeat = QtWidgets.QPushButton("Repetir")
        self.repeat.clicked.connect(self._repeat)
        lay.addWidget(self.repeat)
        box.addWidget(params)
        (self.dh if _MovePanel._mode == "dh" else self.xy).setChecked(True)
        self.dh.toggled.connect(self._mode_changed)
        self._mode_changed()

    def _mode_changed(self, *_a):
        _MovePanel._mode = "dh" if self.dh.isChecked() else "xy"
        self.dh_part.setVisible(self.dh.isChecked())
        self.xy_part.setVisible(not self.dh.isChecked())
        self._repeat_state()
        if not self.dh.isChecked() and self.active == "base":
            self.set_active("entities")
        self._draw()

    def _repeat_state(self):
        # SW: en X/Y siempre; en Desde/Hasta después del primer movimiento
        self.repeat.setEnabled(not self.dh.isChecked() or getattr(self, "last", None) is not None)

    def _delta(self):
        if self.dh.isChecked():
            base = self.points.get("base")
            if base is None or self.hover is None:
                return None
            return self.hover - base
        return V(self.dx.value(), self.dy.value(), 0)

    def _follows_mouse(self):
        return self.dh.isChecked() and self.points.get("base") is not None and bool(self.geos) \
            and self.active != "base" and not getattr(self, "placed", False)

    def _point_picked(self, name):
        # Elegido el punto inicial ("Desde punto definido", como SW), el mouse lleva la vista
        # previa y el próximo clic la ubica
        self.placed = False
        self.set_active("entities")

    def _refresh_list(self):
        super()._refresh_list()
        if self.points.get("base") is not None:
            self.boxes["base"].setText("Desde punto definido")

    def _click_follow(self):
        """Como SW: el clic en el destino mueve y el panel queda abierto (Repetir, ✓)."""
        delta = self._delta()
        if delta is None or _state_closed(self):
            return
        if self._do(delta):
            self.last = delta
            self.placed = True
            self._repeat_state()
        self.update()

    def _preview_lines(self):
        delta = self._delta()
        if not self.geos or delta is None or (self.dh.isChecked() and getattr(self, "placed", False)):
            return []
        return moved_lines(self.sketch, self.geos, _translate(delta))

    def _ready(self):
        if not self.geos:
            return self.NOTHING
        if self.dh.isChecked() and getattr(self, "placed", False):
            return ""
        if self.dh.isChecked() and self.points.get("base") is None:
            return "Elija el punto inicial (y después haga clic en el destino)."
        if self._delta() is None:
            return "Haga clic en el destino."
        return ""

    def _apply(self, delta):
        move_entities(self.sketch, self.geos, delta, self.keep.isChecked())

    def _run(self):
        if self.dh.isChecked() and getattr(self, "placed", False):
            return  # ya se movió con el clic: ✓ solo cierra
        self._apply(self._delta())

    def _do(self, delta):
        try:
            self._apply(delta)
            self.sketch.recompute()
            return True
        except Exception as exc:
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (self.TITLE, traceback.format_exc()))
            self._show_problem("No se pudo: %s" % exc)
            return False

    def _repeat(self):
        delta = getattr(self, "last", None) if self.dh.isChecked() else self._delta()
        if not self.geos or delta is None:
            self._show_problem(self._ready() or self.NOTHING)
            return
        self._do(delta)
        self.update()


class MovePanel(_MovePanel):
    pass


class CopyPanel(_MovePanel):
    TITLE = "Copiar"
    GROUP = "Entidades a copiar"
    NOTHING = "Elija las entidades a copiar."

    def _apply(self, delta):
        copy_entities(self.sketch, self.geos, delta)


class RotatePanel(se.EntityPanel):
    TITLE = "Girar"
    NOTHING = "Elija las entidades a girar."

    def _build_body(self, box):
        group = QtWidgets.QGroupBox("Entidades a girar")
        lay = QtWidgets.QVBoxLayout(group)
        lay.addWidget(self._make_list())
        self.keep = QtWidgets.QCheckBox("Conservar relaciones")
        lay.addWidget(self.keep)
        box.addWidget(group)
        params = QtWidgets.QGroupBox("Parámetros")
        lay = QtWidgets.QVBoxLayout(params)
        lay.addWidget(QtWidgets.QLabel("Centro de rotación:"))
        lay.addWidget(self._point_box("center"))
        self.angle = _spin(0.0, "°", -360.0, 360.0)
        self.angle.valueChanged.connect(lambda *_a: self._draw())
        lay.addWidget(_row("∠", self.angle))
        box.addWidget(params)

    def _point_picked(self, name):
        self.angle.setFocus()
        self.angle.selectAll()

    def _preview_lines(self):
        center = self.points.get("center")
        if not self.geos or center is None or abs(self.angle.value()) < 1e-9:
            return []
        return moved_lines(self.sketch, self.geos, _rotate(center, self.angle.value()))

    def _ready(self):
        if not self.geos:
            return self.NOTHING
        if self.points.get("center") is None:
            return "Elija el centro de rotación."
        return ""

    def _run(self):
        rotate_entities(self.sketch, self.geos, self.points["center"], self.angle.value(),
                        self.keep.isChecked())


class ScalePanel(se.EntityPanel):
    TITLE = "Escala"
    NOTHING = "Elija las entidades a ajustar la escala."

    def _build_body(self, box):
        group = QtWidgets.QGroupBox("Entidades a ajustar la escala")
        lay = QtWidgets.QVBoxLayout(group)
        lay.addWidget(self._make_list())
        box.addWidget(group)
        params = QtWidgets.QGroupBox("Parámetros")
        lay = QtWidgets.QVBoxLayout(params)
        lay.addWidget(QtWidgets.QLabel("Ajustar escala con"))
        lay.addWidget(self._point_box("center"))
        self.factor = _spin(1.0, "", 0.0001, 1e6, decimals=4, step=0.1)
        self.factor.valueChanged.connect(lambda *_a: self._draw())
        lay.addWidget(_row("×", self.factor))
        self.copy = QtWidgets.QCheckBox("Copiar")
        lay.addWidget(self.copy)
        self.copies = _count(1)
        self.copies_row = _row("#", self.copies)
        self.copies_row.setVisible(False)
        self.copy.toggled.connect(self.copies_row.setVisible)
        self.copy.toggled.connect(lambda *_a: self._draw())
        self.copies.valueChanged.connect(lambda *_a: self._draw())
        lay.addWidget(self.copies_row)
        box.addWidget(params)

    def _point_picked(self, name):
        self.factor.setFocus()
        self.factor.selectAll()

    def _preview_lines(self):
        center = self.points.get("center")
        if not self.geos or center is None or abs(self.factor.value() - 1.0) < 1e-9:
            return []
        out = []
        n = self.copies.value() if self.copy.isChecked() else 1
        for k in range(1, n + 1):
            out += moved_lines(self.sketch, self.geos, _scale(center, self.factor.value() ** k))
        return out

    def _ready(self):
        if not self.geos:
            return self.NOTHING
        if self.points.get("center") is None:
            return "Elija el punto con el que ajustar la escala."
        return ""

    def _run(self):
        scale_entities(self.sketch, self.geos, self.points["center"], self.factor.value(),
                       self.copies.value() if self.copy.isChecked() else 0)


class PatternPanel(se.EntityPanel):
    TITLE = "Matriz lineal"
    NOTHING = "Elija las entidades para la matriz."

    def _direction(self, box, n, axis, angle, count):
        group = QtWidgets.QGroupBox("Dirección %d" % n)
        lay = QtWidgets.QVBoxLayout(group)
        ref = self._ref_box("dir%d" % n)
        ref.setText(axis)
        lay.addWidget(ref)
        spacing = _spin(10.0, " mm", 0.001, 1e6)
        lay.addWidget(_row("↔", spacing))
        dim = QtWidgets.QCheckBox("Acotar espacio de %s" % axis[-1])
        lay.addWidget(dim)
        number = _count(count)
        lay.addWidget(_row("#", number))
        ang = _spin(angle, "°", -360.0, 360.0)
        lay.addWidget(_row("∠", ang))
        for w in (spacing, number, ang):
            w.valueChanged.connect(lambda *_a: self._changed())
        box.addWidget(group)
        return ref, spacing, dim, number, ang

    def _build_body(self, box):
        (self.ref1, self.spacing1, self.dim1, self.count1, self.angle1) = \
            self._direction(box, 1, "Eje X", 0.0, 2)
        (self.ref2, self.spacing2, self.dim2, self.count2, self.angle2) = \
            self._direction(box, 2, "Eje Y", 90.0, 1)
        group = QtWidgets.QGroupBox("Entidades para la matriz")
        lay = QtWidgets.QVBoxLayout(group)
        lay.addWidget(self._make_list())
        box.addWidget(group)
        self._changed()

    def _changed(self):
        # Como SW: la dirección 2 se habilita al poner más de una instancia
        two = self.count2.value() > 1
        for w in (self.spacing2, self.dim2, self.angle2):
            w.setEnabled(two)
        self._draw()

    def _pick(self, geo):
        if self.active in ("dir1", "dir2"):
            line = se.axis_line(self.sketch, geo) if se.is_line(self.sketch, geo) else None
            if line is None:
                return False
            _a, d = line
            angle = math.degrees(math.atan2(d.y, d.x))
            box, spin = (self.ref1, self.angle1) if self.active == "dir1" else (self.ref2, self.angle2)
            box.setText(se.sw_name(self.sketch, geo))
            spin.setValue(round(angle, 6))
            return True
        return super()._pick(geo)

    def _vectors(self):
        a1, a2 = math.radians(self.angle1.value()), math.radians(self.angle2.value())
        s1, s2 = self.spacing1.value(), self.spacing2.value()
        return (V(s1 * math.cos(a1), s1 * math.sin(a1), 0), V(s2 * math.cos(a2), s2 * math.sin(a2), 0))

    def _preview_lines(self):
        if not self.geos:
            return []
        v1, v2 = self._vectors()
        out = []
        for i in range(self.count1.value()):
            for j in range(self.count2.value()):
                if i or j:
                    out += moved_lines(self.sketch, self.geos, _translate(v1 * i + v2 * j))
        return out

    def _ready(self):
        if not self.geos:
            return self.NOTHING
        if self.count1.value() * self.count2.value() < 2:
            return "Ponga más de una instancia."
        return ""

    def _run(self):
        linear_pattern(self.sketch, self.geos, self.count1.value(), self.spacing1.value(),
                       self.angle1.value(), self.count2.value(), self.spacing2.value(),
                       self.angle2.value(), self.dim1.isChecked(), self.dim2.isChecked())
