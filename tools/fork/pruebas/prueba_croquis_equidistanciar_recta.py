# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#63: Equidistanciar entidades sobre una recta (una línea sola, o dos líneas alineadas unidas)
anda como en SW: la copia queda paralela a la distancia pedida, del lado del mouse, y con
Bidireccional + tapas en arco queda el contorno cerrado (dos rectas y dos medias vueltas). Antes:
'makeOffset2D: wires are nonplanar or noncoplanar'. Una cadena con curva sigue igual."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

V = FreeCAD.Vector


def _croquis(doc, lineas):
    sk = doc.addObject("Sketcher::SketchObject", "Croquis")
    for a, b in lineas:
        sk.addGeometry(Part.LineSegment(V(*a), V(*b)))
    for i in range(len(lineas) - 1):  # unir las puntas que coinciden (estén como estén dibujadas)
        for pi, p in ((1, lineas[i][0]), (2, lineas[i][1])):
            for qi, q in ((1, lineas[i + 1][0]), (2, lineas[i + 1][1])):
                if p == q:
                    sk.addConstraint(Sketcher.Constraint("Coincident", i, pi, i + 1, qi))
    doc.recompute()
    return sk


def _dist_a_recta(p, a, b):
    d = (b - a)
    d.normalize()
    return (p - a).cross(d).Length


def prueba():
    from swui.fork import sketch_offset as so
    doc = FreeCAD.newDocument("EquidRecta")
    for lineas in ([((0, 0, 0), (50, 0, 0))],
                   [((0, 0, 0), (20, 20, 0)), ((20, 20, 0), (40, 40, 0))],
                   [((20, 20, 0), (0, 0, 0)), ((20, 20, 0), (40, 40, 0))]):  # la primera al revés
        sk = _croquis(doc, lineas)
        n0 = sk.GeometryCount
        a, b = V(*lineas[0][0]), V(*lineas[-1][1])
        lado = V(-30, 30, 0) if lineas[0][1][1] else V(25, 10, 0)
        nuevos = so.offset_entities(sk, [0], 5.0, side=lado)
        doc.recompute()
        assert nuevos and sk.GeometryCount > n0, "no agregó nada"
        for g in nuevos:
            e = sk.Geometry[g].toShape()
            for v in e.Vertexes:
                assert abs(_dist_a_recta(v.Point, a, b) - 5.0) < 1e-6, "no quedó a 5 mm: %s" % v.Point
            mitad = e.valueAt((e.FirstParameter + e.LastParameter) / 2)
            assert (mitad - a).cross(b - a).z * (lado - a).cross(b - a).z > 0, "quedó del otro lado"
        largo = sum(sk.Geometry[g].toShape().Length for g in nuevos)
        total = sum((V(*q) - V(*p)).Length for p, q in lineas)
        assert abs(largo - total) < 1e-6, "la copia mide %.3f y la cadena %.3f" % (largo, total)
        assert "Invalid" not in str(sk.State), sk.State
        doc.removeObject(sk.Name)
    # bidireccional con tapas en arco: contorno cerrado
    sk = _croquis(doc, [((0, 0, 0), (50, 0, 0))])
    nuevos = so.offset_entities(sk, [0], 4.0, both=True, caps="arcs")
    doc.recompute()
    tipos = sorted(type(sk.Geometry[g]).__name__ for g in nuevos)
    assert tipos.count("ArcOfCircle") == 2 and tipos.count("LineSegment") == 2, tipos
    w = Part.Wire(Part.sortEdges([sk.Geometry[g].toShape() for g in nuevos])[0])
    assert w.isClosed(), "el contorno no quedó cerrado"
    # una cadena con curva sigue por el camino de FreeCAD
    sk2 = doc.addObject("Sketcher::SketchObject", "Curva")
    sk2.addGeometry(Part.ArcOfCircle(Part.Circle(V(0, 0, 0), V(0, 0, 1), 20), 0, 1.5))
    doc.recompute()
    assert so.offset_entities(sk2, [0], 3.0), "el arco dejó de andar"
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
