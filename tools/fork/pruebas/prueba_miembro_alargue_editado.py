# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """El alargue final de un miembro estructural se lee bien aunque su fórmula esté escrita a mano
de otra forma (Issue #23): "Ruta.Shape.Length + 15 * 2" da 30, un número solo (330 sobre una
línea de 300) da 30, y la forma que escribe FreeWorks da lo que se puso con set_extension. Antes
se leía el texto después del "+" y daba 0."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from comun import V, cerca  # noqa: E402


def prueba():
    from swui.fork import weldments as w
    doc = FreeCAD.newDocument("Alargue")
    sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
    sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(300, 0, 0)))
    doc.recompute()
    tipo = "Caño cuadrado"
    m = w.create_members(doc, [(sk, "Edge1")], tipo, w.sizes(tipo)[0][0])[0]
    pad, ruta = w._pad_of(m), w._route_of(m)
    w.set_extension(m, start=5, end=12.5)
    assert cerca(w.extension(m)[0], 5) and cerca(w.extension(m)[1], 12.5), w.extension(m)
    pad.setExpression("Length", "%s.Shape.Length + 15 * 2" % ruta.Name)
    doc.recompute()
    assert cerca(w.extension(m)[1], 30), "fórmula a mano: alargue %r (esperado 30)" % (w.extension(m),)
    pad.setExpression("Length", None)
    pad.Length = 330
    doc.recompute()
    assert cerca(w.extension(m)[1], 30), "número solo: alargue %r (esperado 30)" % (w.extension(m),)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
