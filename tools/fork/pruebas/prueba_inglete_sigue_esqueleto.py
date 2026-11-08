# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Marco de 4 caños 40x40 con esquinas a inglete sobre un esqueleto de 600 x 400. Si el
ancho del esqueleto pasa a 800 y se recalcula, el marco entero ocupa -20..820 x -20..420: los
caños horizontales llegan a la esquina nueva y ningún caño sobresale ni deja hueco."""
CONOCIDO = "#2"
ESPERA = "sobresale"  # el caño vertical pasa la esquina nueva

import FreeCAD  # noqa: E402

from comun import cerca, marco  # noqa: E402


def prueba():
    doc = FreeCAD.newDocument("Inglete")
    sk, cota, cuerpos = marco(doc, esquina="inglete")
    sk.setDatum(cota, FreeCAD.Units.Quantity("800 mm"))
    doc.recompute()
    for b in cuerpos:
        assert b.Shape.isValid(), "%s no es válido" % b.Label
        bb = b.Shape.BoundBox
        assert bb.XMin > -20.1 and bb.XMax < 820.1 and bb.YMin > -20.1 and bb.YMax < 420.1, \
            "%s sobresale: %s" % (b.Label, bb)
    abajo = [b for b in cuerpos if cerca(b.Shape.BoundBox.YMin, -20) and cerca(b.Shape.BoundBox.YMax, 20)]
    assert abajo, "no está el caño de abajo"
    assert cerca(abajo[0].Shape.BoundBox.XMax, 820), \
        "el caño de abajo termina en %.1f, no en 820 (hueco)" % abajo[0].Shape.BoundBox.XMax


from _base import ejecutar  # noqa: E402
ejecutar(globals())
