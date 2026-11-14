# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#90: una matriz de croquis con miles de copias dejaba al croquis calculando sin fin (la prueba de
campos escribía 999 en una cantidad y FreeCAD no respondía más). Ahora se rechaza con un aviso en
castellano, sin tocar el croquis; una cantidad normal sigue andando."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402

V = FreeCAD.Vector


def prueba():
    from swui.fork import sketch_transform as st
    doc = FreeCAD.newDocument("Matrices")
    sk = doc.addObject("Sketcher::SketchObject", "Croquis")
    for a, b in ((V(0, 0, 0), V(10, 0, 0)), (V(10, 0, 0), V(10, 5, 0)), (V(10, 5, 0), V(0, 5, 0)), (V(0, 5, 0), V(0, 0, 0))):
        sk.addGeometry(Part.LineSegment(a, b))
    doc.recompute()
    antes = sk.GeometryCount
    try:
        st.linear_pattern(sk, [0, 1, 2, 3], count1=999, spacing1=20, count2=999, spacing2=20)
        raise AssertionError("aceptó una matriz de 999 x 999 copias")
    except ValueError as exc:
        assert "demasiadas" in str(exc), "el aviso no dice qué pasa: %s" % exc
    assert sk.GeometryCount == antes, "con el aviso igual tocó el croquis"
    st.linear_pattern(sk, [0, 1, 2, 3], count1=3, spacing1=20)
    doc.recompute()
    assert sk.GeometryCount >= antes + 8, "una matriz normal de 3 no hizo las copias (%d)" % sk.GeometryCount
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
