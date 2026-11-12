# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#2: tapas de extremo y cartelas siguen a sus miembros. Una L abierta de caño 40x40 (500 y 300 mm,
a tope) con una cartela en la esquina y una tapa en cada punta libre (una con alargue). Se cambian
los dos largos del esqueleto (700 y 450) y se recalcula: cada tapa sigue apoyada en su punta (toca
el caño y no se superpone) y la cartela sigue tocando los dos caños en la esquina, sin superponerse."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

V = FreeCAD.Vector


def toca(a, b, que):
    d = a.Shape.distToShape(b.Shape)[0]
    comun = a.Shape.common(b.Shape).Volume
    assert d < 1e-3, "%s: hay %.2f mm entre %s y %s (no la siguió)" % (que, d, a.Label, b.Label)
    assert comun < 0.01, "%s: %s y %s se superponen %.2f mm³" % (que, a.Label, b.Label, comun)


def prueba():
    from swui.fork import weldments as w
    doc = FreeCAD.newDocument("TapaCartela")
    sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
    sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(500, 0, 0)))
    sk.addGeometry(Part.LineSegment(V(500, 0, 0), V(500, 300, 0)))
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 2, 1, 1))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 0))
    sk.addConstraint(Sketcher.Constraint("Vertical", 1))
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
    c_x = sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 500))
    c_y = sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 300))
    doc.recompute()
    size = [s for s, _d in w.sizes("Caño cuadrado") if s.startswith("40x40x2")][0]
    a, b = w.create_members(doc, [(sk, "Edge1"), (sk, "Edge2")], "Caño cuadrado", size)
    w.apply_corners([a, b], "tope")
    w.set_extension(a, start=15)  # la punta libre de `a` con alargue: la tapa tiene que seguirlo
    doc.recompute()
    tapa_a = w.end_cap(a, 0, thickness=5)
    tapa_b = w.end_cap(b, 1, thickness=5)
    cartela = w.gusset(a, b, size=80, thickness=6)
    doc.recompute()
    for que in ("armado", "después de cambiar el esqueleto"):
        for t in (tapa_a, tapa_b, cartela):
            assert t.Shape.isValid() and not t.Shape.isNull(), "%s: %s con error" % (que, t.Label)
        toca(tapa_a, a, que)
        toca(tapa_b, b, que)
        toca(cartela, a, que)
        toca(cartela, b, que)
        bb_a, bb_t = a.Shape.BoundBox, tapa_a.Shape.BoundBox
        assert abs(bb_t.XMax - bb_a.XMin) < 1e-3, "%s: la tapa de la punta inicial no está en la punta" % que
        bb_b, bb_tb = b.Shape.BoundBox, tapa_b.Shape.BoundBox
        assert abs(bb_tb.YMin - bb_b.YMax) < 1e-3, "%s: la tapa de la punta final no está en la punta" % que
        if que == "armado":
            sk.setDatum(c_x, FreeCAD.Units.Quantity("700 mm"))
            sk.setDatum(c_y, FreeCAD.Units.Quantity("450 mm"))
            doc.recompute()
    assert abs(b.Shape.BoundBox.XMin - 680) < 1e-3, "la L no se movió (la prueba no cambió nada)"
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
