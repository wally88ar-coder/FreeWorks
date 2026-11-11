# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Miembro estructural sobre un esqueleto con una línea, un arco y un círculo (Issue #8): sobre el
arco o el círculo da un error en castellano que nombra la línea y NO crea nada (ni Cuerpos ni la
carpeta); con el arco mezclado entre líneas tampoco crea nada; sobre la línea sola sale el caño
de siempre (largo de la línea)."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from comun import V, cerca  # noqa: E402


def prueba():
    from swui.fork import weldments as w
    doc = FreeCAD.newDocument("SoloRectas")
    sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
    sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(300, 0, 0)))  # Edge1
    sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(300, 100, 0), V(0, 0, 1), 100), -1.5708, 0))  # Edge2
    sk.addGeometry(Part.Circle(V(0, 400, 0), V(0, 0, 1), 80))  # Edge3
    doc.recompute()
    arista = {}
    for i, e in enumerate(sk.Shape.Edges):
        tipo = e.Curve.__class__.__name__
        arista[tipo] = "Edge%d" % (i + 1)
    assert set(arista) >= {"Line", "Circle"}, arista
    linea = arista["Line"]
    curvas = ["Edge%d" % (i + 1) for i, e in enumerate(sk.Shape.Edges) if e.Curve.__class__.__name__ != "Line"]
    assert len(curvas) == 2, curvas
    antes = len(doc.Objects)
    tipo, medida = "Caño cuadrado", w.sizes("Caño cuadrado")[0][0]
    for elegidas in ([(sk, curvas[0])], [(sk, curvas[1])], [(sk, linea), (sk, curvas[0])]):
        try:
            w.create_members(doc, elegidas, tipo, medida)
            raise AssertionError("aceptó %s sin dar error" % [s for _o, s in elegidas])
        except ValueError as e:
            assert "no es una línea recta" in str(e) and "Esqueleto" in str(e), str(e)
        assert len(doc.Objects) == antes, "dejó objetos a medias: %s" % [o.Label for o in doc.Objects[antes:]]
    cuerpos = w.create_members(doc, [(sk, linea)], tipo, medida)
    doc.recompute()
    assert len(cuerpos) == 1 and cuerpos[0].Shape.isValid(), cuerpos
    assert cerca(cuerpos[0].Shape.BoundBox.XLength, 300, 0.01), cuerpos[0].Shape.BoundBox


from _base import ejecutar  # noqa: E402
ejecutar(globals())
