# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Equidistanciar entidades del croquis como en SW 2018 (relevado con el mouse el 02/11).

SW: el panel solo tiene Parámetros (distancia 10 mm, Agregar cotas, Invertir dirección,
Seleccionar cadena, Bidireccional, Tapas en extremos Arcos/Líneas, Geometría base /
de equidistancia constructivas). Un clic en una entidad toma toda la cadena unida; la
vista previa amarilla sigue al mouse (de qué lado) y otro clic la ubica y termina.
Esquinas en punta (las líneas se prolongan) y una sola cota.

Por debajo, la equidistancia 2D de FreeCAD (Part.Wire.makeOffset2D, esquinas por
intersección); el resultado se agrega como líneas y arcos del croquis, unidos entre sí,
paralelos / concéntricos a los originales y, con Agregar cotas, una cota de distancia
(las demás atadas a esa con una expresión: se cambia en un solo lugar).
Función pública: offset_entities(...).
"""

import math

import FreeCAD

from swui.compat import QtWidgets
from swui.fork import sketch_entities as se
from swui.fork import safe_ops  # noqa: E402  (#60: cerrar pasos con end_step)

V = FreeCAD.Vector
TOL = 1e-5


# --- Cuentas -----------------------------------------------------------------


def _ends(sketch, g):
    geo = sketch.Geometry[g]
    if se._geo_type(geo) in ("Circle", "Ellipse", "Point"):
        return []
    return [sketch.getPoint(g, 1), sketch.getPoint(g, 2)]


def chain_of(sketch, geo):
    """Las entidades unidas punta con punta a geo (Seleccionar cadena de SW)."""
    construction = sketch.getConstruction(geo)
    out, todo = [geo], [geo]
    while todo:
        g = todo.pop()
        ends = _ends(sketch, g)
        for other in range(sketch.GeometryCount):
            if other in out or sketch.getConstruction(other) != construction:
                continue
            if any((p - q).Length < TOL for p in ends for q in _ends(sketch, other)):
                out.append(other)
                todo.append(other)
    return out


def _arc3(center, radius, a, m, b):
    """Arco del croquis (antihorario) de a a b que pasa por m."""
    import Part

    def ang(p):
        return math.atan2(p.y - center.y, p.x - center.x)

    ta, tm, tb = ang(a), ang(m), ang(b)
    two = 2 * math.pi

    def ccw(t0, t1):
        return (t1 - t0) % two

    if ccw(ta, tm) <= ccw(ta, tb):
        start, end = ta, ta + ccw(ta, tb)
    else:
        start, end = tb, tb + ccw(tb, ta)
    return Part.ArcOfCircle(Part.Circle(V(center.x, center.y, 0), V(0, 0, 1), radius), start, end)


def edge_geometry(edge):
    """Arista (resultado de la equidistancia) -> geometría del croquis."""
    import Part

    curve = edge.Curve
    kind = type(curve).__name__
    if kind in ("Line", "LineSegment"):
        return Part.LineSegment(edge.Vertexes[0].Point, edge.Vertexes[-1].Point)
    if kind == "Circle":
        if edge.isClosed():
            return Part.Circle(V(curve.Center.x, curve.Center.y, 0), V(0, 0, 1), curve.Radius)
        mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
        return _arc3(curve.Center, curve.Radius, edge.Vertexes[0].Point, mid, edge.Vertexes[-1].Point)
    return curve.toBSpline(edge.FirstParameter, edge.LastParameter)


def _merge_lines(geos):
    """Une líneas seguidas y alineadas (la equidistancia a veces parte un lado en dos)."""
    out = []
    for g in geos:
        if out and se._geo_type(g) == "LineSegment" and se._geo_type(out[-1]) == "LineSegment":
            prev = out[-1]
            for a, b in ((prev.EndPoint, g.StartPoint), (prev.EndPoint, g.EndPoint),
                         (prev.StartPoint, g.StartPoint), (prev.StartPoint, g.EndPoint)):
                if (a - b).Length < TOL:
                    d1 = prev.EndPoint - prev.StartPoint
                    d2 = g.EndPoint - g.StartPoint
                    if d1.Length > TOL and d2.Length > TOL and d1.cross(d2).Length / (d1.Length * d2.Length) < 1e-7:
                        pts = [prev.StartPoint, prev.EndPoint, g.StartPoint, g.EndPoint]
                        far = max(((p, q) for p in pts for q in pts), key=lambda pq: (pq[0] - pq[1]).Length)
                        import Part

                        out[-1] = Part.LineSegment(far[0], far[1])
                        break
            else:
                out.append(g)
            continue
        out.append(g)
    return out


def _wires(sketch, geo_ids):
    import Part

    edges = [sketch.Geometry[g].toShape() for g in geo_ids]
    return [Part.Wire(group) for group in Part.sortEdges(edges)]


def _straight(wire):
    """Dirección (unitaria) si la cadena es una recta (una línea o varias alineadas); si no, None.
    En una recta el plano no queda definido y makeOffset2D falla con 'wires are nonplanar or
    noncoplanar' (#63): la equidistancia se arma a mano en el plano del croquis."""
    pts = [v.Point for v in wire.Vertexes]
    if any(type(e.Curve).__name__ != "Line" for e in wire.Edges) or len(pts) < 2:
        return None
    d = max((p - pts[0] for p in pts), key=lambda v: v.Length)
    if d.Length < TOL:
        return None
    d.normalize()
    if any(abs((p - pts[0]).cross(d).Length) > TOL for p in pts):
        return None
    return d


def _offset2d(wire, distance, closed_caps=False):
    """wire.makeOffset2D en el plano del croquis (Z = 0), también para una recta (#63). Cadena
    abierta: el resultado es la cadena corrida (o, con closed_caps, el contorno cerrado con arcos
    en las puntas)."""
    import Part

    d = _straight(wire)
    if d is None:
        if closed_caps:
            return wire.makeOffset2D(distance, 2, False, False)
        return wire.makeOffset2D(distance, 2, False, not wire.isClosed())
    n = V(-d.y, d.x, 0) * distance
    # las puntas de la recta: el menor y el mayor a lo largo de d (el orden de Vertexes no es el
    # de la cadena si una línea se dibujó al revés; revisión del 12/11)
    pts = sorted((v.Point for v in wire.Vertexes), key=lambda p: p.dot(d))
    a, b = pts[0], pts[-1]
    if not closed_caps:
        return Part.Wire(Part.LineSegment(a + n, b + n).toShape())
    r = abs(distance)
    m = V(-d.y, d.x, 0) * r
    edges = [Part.LineSegment(a + m, b + m).toShape(),
             Part.Arc(b + m, b + d * r, b - m).toShape(),
             Part.LineSegment(b - m, a - m).toShape(),
             Part.Arc(a - m, a - d * r, a + m).toShape()]
    return Part.Wire(edges)


def offset_shapes(sketch, geo_ids, distance, side=None, reverse=False, both=False, caps=None):
    """
    Resultado de la equidistancia (formas del plano del croquis, sin tocarlo): lista de
    formas, una por cadena y lado. side: punto del croquis que dice de qué lado (SW: el
    mouse); caps "arcs" / "lines" con both en cadenas abiertas.
    """
    import Part

    out = []
    for wire in _wires(sketch, geo_ids):
        closed = wire.isClosed()
        if both and not closed and caps == "arcs":
            out.append(_offset2d(wire, distance, closed_caps=True))
            continue
        options = [_offset2d(wire, sign * distance) for sign in (1, -1)]
        if both:
            out += options
            if not closed and caps == "lines":
                ends = []
                for res in options:
                    pts = [v.Point for v in res.Vertexes]
                    near = [min(pts, key=lambda p, q=q: (p - q).Length)
                            for q in (wire.Vertexes[0].Point, wire.Vertexes[-1].Point)]
                    ends.append(near)
                for k in (0, 1):
                    if (ends[0][k] - ends[1][k]).Length > TOL:
                        out.append(Part.LineSegment(ends[0][k], ends[1][k]).toShape())
            continue
        pick = 0
        if side is not None:
            vertex = Part.Vertex(V(side.x, side.y, 0))
            dist = [res.distToShape(vertex)[0] if res.Edges else 1e99 for res in options]
            pick = 0 if dist[0] <= dist[1] else 1
        if reverse:
            pick = 1 - pick
        out.append(options[pick])
    return out


def _geometries(shapes):
    geos = []
    for shape in shapes:
        geos += _merge_lines([edge_geometry(e) for e in shape.Edges])
    return geos


def offset_entities(sketch, geo_ids, distance=10.0, side=None, reverse=False, chain=True, both=False,
                    caps=None, add_dims=True, base_construction=False, offset_construction=False):
    """
    Equidistanciar entidades (SW). geo_ids: entidades (con chain se suma su cadena);
    distance en mm; side: punto del croquis del lado buscado; reverse: Invertir dirección;
    both: Bidireccional; caps None / "arcs" / "lines": Tapas en extremos; add_dims: una cota
    (las demás atadas a ella); base_construction / offset_construction: Geometría constructiva.
    Devuelve los números de las entidades nuevas.
    """
    geos = sorted(set(int(g) for g in geo_ids if 0 <= int(g) < sketch.GeometryCount))
    if chain:
        full = []
        for g in geos:
            for c in chain_of(sketch, g):
                if c not in full:
                    full.append(c)
        geos = full
    if not geos:
        raise ValueError("No hay entidades para equidistanciar.")
    if distance <= 0:
        raise ValueError("La distancia tiene que ser mayor que cero.")
    shapes = offset_shapes(sketch, geos, distance, side, reverse, both, caps)
    new_geos = _geometries(shapes)
    if not new_geos:
        raise RuntimeError("FreeCAD no pudo equidistanciar esas entidades.")
    doc = sketch.Document
    own = not doc.HasPendingTransaction
    if own:
        doc.openTransaction("Equidistanciar entidades")
    try:
        new = _add(sketch, geos, new_geos, distance, add_dims, base_construction, offset_construction)
    except Exception:
        if own:
            safe_ops.end_step(doc, abort=True)
        raise
    if own:
        safe_ops.end_step(doc)
    return new


def _add(sketch, originals, new_geos, distance, add_dims, base_construction, offset_construction):
    import Sketcher

    start = sketch.GeometryCount
    sketch.addGeometry(new_geos, offset_construction)
    new = list(range(start, sketch.GeometryCount))
    try_add = se._try_add
    # Unidas entre sí donde se tocan
    for i, a in enumerate(new):
        for b in new[i + 1:]:
            for pa in (1, 2):
                for pb in (1, 2):
                    try:
                        if not _ends(sketch, a) or not _ends(sketch, b):
                            continue
                        if (sketch.getPoint(a, pa) - sketch.getPoint(b, pb)).Length < 1e-4:
                            try_add(sketch, Sketcher.Constraint("Coincident", a, pa, b, pb))
                    except Exception:
                        pass
    # Paralelas a sus líneas originales, concéntricas a sus arcos
    pairs = []
    for n in new:
        g = sketch.Geometry[n]
        kind = se._geo_type(g)
        for o in originals:
            og = sketch.Geometry[o]
            okind = se._geo_type(og)
            if kind == "LineSegment" and okind == "LineSegment":
                d1 = g.EndPoint - g.StartPoint
                d2 = og.EndPoint - og.StartPoint
                if d1.cross(d2).Length / max(d1.Length * d2.Length, 1e-12) < 1e-7:
                    if abs(_line_gap(og, g.StartPoint) - distance) < 1e-4:
                        try_add(sketch, Sketcher.Constraint("Parallel", o, n))
                        pairs.append((o, n))
                        break
            elif kind in ("ArcOfCircle", "Circle") and okind in ("ArcOfCircle", "Circle"):
                if (g.Center - og.Center).Length < 1e-4:
                    try_add(sketch, Sketcher.Constraint("Coincident", o, 3, n, 3))
                    pairs.append((o, n))
                    break
    if add_dims:
        first = None
        for o, n in pairs:
            kind = se._geo_type(sketch.Geometry[o])
            if kind == "LineSegment":
                c = Sketcher.Constraint("Distance", o, 1, n, distance)
            else:
                continue
            before = len(sketch.Constraints)
            if not try_add(sketch, c):
                continue
            index = before
            if first is None:
                name = _free_name(sketch, "Equidistancia")
                sketch.renameConstraint(index, name)
                first = name
            else:
                try:
                    sketch.setExpression("Constraints[%d]" % index, "Constraints.%s" % first)
                except Exception:
                    pass
        if first is None:
            for o, n in pairs:  # solo círculos y arcos: la distancia entre los dos (FreeCAD 1.x)
                if try_add(sketch, Sketcher.Constraint("Distance", o, n, distance)):
                    sketch.renameConstraint(len(sketch.Constraints) - 1, _free_name(sketch, "Equidistancia"))
                    break
    if base_construction:
        for o in originals:
            if not sketch.getConstruction(o):
                sketch.toggleConstruction(o)
    sketch.solve()
    return new


def _line_gap(line, p):
    """Distancia de p a la recta de la línea."""
    a, b = line.StartPoint, line.EndPoint
    d = b - a
    return (p - a).cross(d).Length / d.Length


def _free_name(sketch, base):
    names = {c.Name for c in sketch.Constraints}
    n = 1
    while "%s%d" % (base, n) in names:
        n += 1
    return "%s%d" % (base, n)


# --- Panel ---------------------------------------------------------------------


class OffsetPanel(se.EntityPanel):
    TITLE = "Equidistanciar entidades"
    NOTHING = "Haga clic en las entidades a equidistanciar."
    _last = 10.0  # SW recuerda la última distancia

    def _build_body(self, box):
        from swui.fork.sketch_transform import _row, _spin

        params = QtWidgets.QGroupBox("Parámetros")
        lay = QtWidgets.QVBoxLayout(params)
        self.distance = _spin(OffsetPanel._last, " mm", 0.001, 1e6)
        lay.addWidget(_row("↔", self.distance))
        self.dims = QtWidgets.QCheckBox("Agregar cotas")
        self.dims.setChecked(True)
        self.reverse = QtWidgets.QCheckBox("Invertir dirección")
        self.chain = QtWidgets.QCheckBox("Seleccionar cadena")
        self.chain.setChecked(True)
        self.both = QtWidgets.QCheckBox("Bidireccional")
        self.caps = QtWidgets.QCheckBox("Tapas en extremos")
        self.arcs = QtWidgets.QRadioButton("Arcos")
        self.lines = QtWidgets.QRadioButton("Líneas")
        self.arcs.setChecked(True)
        for w in (self.dims, self.reverse, self.chain, self.both, self.caps):
            lay.addWidget(w)
        caps_box = QtWidgets.QWidget()
        cl = QtWidgets.QVBoxLayout(caps_box)
        cl.setContentsMargins(20, 0, 0, 0)
        cl.addWidget(self.arcs)
        cl.addWidget(self.lines)
        lay.addWidget(caps_box)
        lay.addWidget(QtWidgets.QLabel("Geometría constructiva:"))
        self.base_c = QtWidgets.QCheckBox("Geometría base")
        self.offset_c = QtWidgets.QCheckBox("Geometría de equidistancia")
        lay.addWidget(self.base_c)
        lay.addWidget(self.offset_c)
        box.addWidget(params)
        self.both.toggled.connect(self._options)
        self.caps.toggled.connect(self._options)
        for w in (self.reverse, self.both, self.caps, self.arcs):
            w.toggled.connect(lambda *_a: self._draw())
        self.distance.valueChanged.connect(lambda *_a: self._draw())
        self.chain.toggled.connect(lambda *_a: self._rechain())
        self._options()
        self.picked = []  # lo que se clickeó (sin la cadena)

    def _options(self, *_a):
        # Como SW: Tapas en extremos solo con Bidireccional
        self.caps.setEnabled(self.both.isChecked())
        on = self.both.isChecked() and self.caps.isChecked()
        self.arcs.setEnabled(on)
        self.lines.setEnabled(on)
        self._draw()

    def _rechain(self):
        self.geos = self._expand(self.picked)
        self._draw()

    def _expand(self, picked):
        if not self.chain.isChecked():
            return list(picked)
        out = []
        for g in picked:
            for c in chain_of(self.sketch, g):
                if c not in out:
                    out.append(c)
        return out

    def _pick(self, geo):
        if geo < 0:
            return False
        if geo in self.geos:
            self.picked = [g for g in self.picked if g not in self._expand([geo])]
        else:
            self.picked.append(geo)
        self.geos = self._expand(self.picked)
        return True

    def start(self, picked):
        self.picked = [g for g in picked if g >= 0]
        self.geos = self._expand(self.picked)
        self.update()

    def _follows_mouse(self):
        return bool(self.geos)

    def _caps(self):
        if not (self.both.isChecked() and self.caps.isChecked()):
            return None
        return "arcs" if self.arcs.isChecked() else "lines"

    def _preview_lines(self):
        if not self.geos:
            return []
        try:
            shapes = offset_shapes(self.sketch, self.geos, self.distance.value(), self.hover,
                                   self.reverse.isChecked(), self.both.isChecked(), self._caps())
        except Exception:
            return []
        plc = self.sketch.getGlobalPlacement()
        out = []
        for shape in shapes:
            for e in shape.Edges:
                try:
                    out.append([plc.multVec(p) for p in e.discretize(Number=32)])
                except Exception:
                    pass
        return out

    def _run(self):
        OffsetPanel._last = self.distance.value()
        offset_entities(self.sketch, self.geos, self.distance.value(), self.hover,
                        self.reverse.isChecked(), False, self.both.isChecked(), self._caps(),
                        self.dims.isChecked(), self.base_c.isChecked(), self.offset_c.isChecked())
