# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Marco de 4 caños 40x40 a tope a 90° sobre un esqueleto de 600 x 400. Si el ancho pasa a
800 y se recalcula, los horizontales van de -20 a 820, los verticales quedan entre ellos
(20..380 en Y) y nada se superpone (la suma de volúmenes es la del sólido unido)."""

import FreeCAD  # noqa: E402

from comun import cerca, marco  # noqa: E402


def prueba():
    doc = FreeCAD.newDocument("Tope")
    sk, cota, cuerpos = marco(doc, esquina="tope")
    sk.setDatum(cota, FreeCAD.Units.Quantity("800 mm"))
    doc.recompute()
    horiz = [b for b in cuerpos if b.Shape.BoundBox.XLength > 500]
    vert = [b for b in cuerpos if b not in horiz]
    assert len(horiz) == 2 and len(vert) == 2, [b.Shape.BoundBox for b in cuerpos]
    for b in horiz:
        bb = b.Shape.BoundBox
        assert cerca(bb.XMin, -20) and cerca(bb.XMax, 820), "%s: %s" % (b.Label, bb)
    for b in vert:
        bb = b.Shape.BoundBox
        assert cerca(bb.YMin, 20) and cerca(bb.YMax, 380), "%s: %s" % (b.Label, bb)
    suma = sum(b.Shape.Volume for b in cuerpos)
    union = cuerpos[0].Shape.fuse([b.Shape for b in cuerpos[1:]]).Volume
    assert cerca(suma, union, 1.0), "se superponen: suma %.1f, unidos %.1f" % (suma, union)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
