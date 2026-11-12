# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#66 (revisión del 12/11): al borrar una cota con nombre de un croquis, se sueltan SOLO las
fórmulas que la leen: por nombre interno, por <<etiqueta>> o sin nombre dentro del mismo croquis.
Una fórmula que lee la cota del mismo nombre de OTRO croquis (Sketch001.Constraints.Ancho) queda."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

V = FreeCAD.Vector


def _croquis(doc, nombre, etiqueta):
    sk = doc.addObject("Sketcher::SketchObject", nombre)
    sk.Label = etiqueta
    sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(30, 0, 0)))
    i = sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 30))
    sk.renameConstraint(i, "Ancho")
    return sk


def prueba():
    from swui.fork import sketch_entities as se
    doc = FreeCAD.newDocument("BorrarCota")
    a = _croquis(doc, "Sketch", "Croquis base")
    b = _croquis(doc, "Sketch001", "Otro")
    caja = doc.addObject("Part::Box", "Caja")
    caja.setExpression("Length", "Sketch001.Constraints.Ancho")
    caja.setExpression("Width", "<<Croquis base>>.Constraints.Ancho")
    caja.setExpression("Height", "Sketch.Constraints.Ancho / 3")
    doc.recompute()
    se.delete_constraints(a, [0])
    doc.recompute()
    expr = dict(caja.ExpressionEngine)
    assert "Length" in expr, "soltó una fórmula de OTRO croquis: %s" % expr
    assert "Width" not in expr, "quedó la fórmula por etiqueta a la cota borrada: %s" % expr
    assert "Height" not in expr, "quedó la fórmula por nombre a la cota borrada: %s" % expr
    assert "Invalid" not in str(caja.State) and "Invalid" not in str(b.State), (caja.State, b.State)
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
