# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Ecuaciones: una fórmula que se calcula bien pero con la que la OPERACIÓN no se puede construir
(profundidad 0 en un Extruir) se ACEPTA, como SW: la operación queda con error en el árbol y el aviso
dice cuál ("no se puede construir: «Pad»"). Cambiar la variable a un valor bueno la arregla, y una
fórmula mal escrita se sigue rechazando (decisión del usuario, 11/11)."""

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
    assert m.warning == "", "aviso sin motivo: %r" % m.warning
    m.set_equation("D1@Pad", '"Cero"')
    assert "no se puede construir" in m.warning and "Pad" in m.warning, "sin aviso: %r" % m.warning
    assert pad.ExpressionEngine, "no quedó la fórmula"
    assert eq.is_invalid(pad), "la operación no quedó marcada con error"
    # arreglarla cambiando la variable: vuelve a construir y el aviso se va
    m.set_variable("Cero", "3")
    assert m.warning == "", "aviso de más: %r" % m.warning
    doc.recompute()
    assert not eq.is_invalid(pad) and cerca(b.Shape.Volume, 150.0), b.Shape.Volume
    # un error de la FÓRMULA (no de la operación) se sigue rechazando y queda como estaba
    try:
        m.set_equation("D1@Pad", '"Cero" +* 2')
    except ValueError:
        pass
    else:
        raise AssertionError("aceptó una fórmula mal escrita")
    doc.recompute()
    assert cerca(b.Shape.Volume, 150.0), b.Shape.Volume
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
