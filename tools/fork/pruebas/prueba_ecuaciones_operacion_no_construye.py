# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Ecuaciones: una fórmula que se calcula bien pero con la que la OPERACIÓN no se puede construir
(profundidad 0 en un Extruir) se rechaza con un aviso que dice eso ("no se puede construir"), no
"FreeCAD no pudo calcular la fórmula", y la cota queda como estaba (revisión del 11/11)."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

from comun import cerca  # noqa: E402

V = FreeCAD.Vector


def prueba():
    from swui.fork import equations as eq
    doc = FreeCAD.newDocument("NoConstruye")
    b = doc.addObject("PartDesign::Body", "Body")
    sk = b.newObject("Sketcher::SketchObject", "Sketch")
    xy = [f for f in b.Origin.OriginFeatures if f.Role == "XY_Plane"][0]
    sk.AttachmentSupport = [(xy, "")]
    sk.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(10, 0, 0), V(10, 5, 0), V(0, 5, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    pad = b.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = 7
    doc.recompute()
    assert cerca(b.Shape.Volume, 350.0)
    m = eq.Model(doc)
    m.set_variable("Cero", "0")
    try:
        m.set_equation("D1@Pad", '"Cero"')
    except ValueError as exc:
        texto = str(exc)
    else:
        raise AssertionError("aceptó una profundidad 0")
    assert "no se puede construir" in texto, "aviso engañoso: %r" % texto
    doc.recompute()
    assert not pad.ExpressionEngine, "quedó la fórmula: %s" % pad.ExpressionEngine
    assert cerca(pad.Length.Value, 7.0) and cerca(b.Shape.Volume, 350.0), pad.Length
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
