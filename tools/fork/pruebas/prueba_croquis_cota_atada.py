# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Equidistanciar deja una cota con nombre ("Equidistancia1") y las demás atadas a ella con una
fórmula. Si después Mover o Girar (sin conservar relaciones) borra esa cota, las atadas no pueden
quedar apuntando a una cota que ya no existe: el croquis no queda con error (Issue #66, lo encontró
el mono de croquis la noche del 10/11). Se prueba con un rectángulo equidistanciado y moviendo, o
girando, la línea nueva que tiene la cota con nombre."""
CONOCIDO = "#66"
ESPERA = "fórmulas a una cota borrada"

import re  # noqa: E402

import FreeCAD  # noqa: E402

from _base import traza  # noqa: E402

V = FreeCAD.Vector


def _rectangulo(doc):
    import Part
    import Sketcher
    sk = doc.addObject("Sketcher::SketchObject", "Sk")
    p = [V(0, 0, 0), V(40, 0, 0), V(40, 30, 0), V(0, 30, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(p[i], p[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    doc.recompute()
    return sk


def prueba():
    from swui.fork import sketch_offset as so
    from swui.fork import sketch_transform as st
    problemas = []
    for herramienta in ("Mover", "Girar"):
        doc = FreeCAD.newDocument("CotaAtada")
        try:
            sk = _rectangulo(doc)
            so.offset_entities(sk, [0], 5.0, side=V(20, 15, 0))
            doc.recompute()
            nombrada = [c for c in sk.Constraints if c.Name == "Equidistancia1"]
            assert nombrada, "Equidistanciar no dejó la cota 'Equidistancia1'"
            atadas = [e for _p, e in sk.ExpressionEngine if "Equidistancia1" in e]
            assert atadas, "Equidistanciar no ató las demás cotas a 'Equidistancia1'"
            linea = nombrada[0].Second
            if herramienta == "Mover":
                st.move_entities(sk, [linea], V(1, 1, 0))
            else:
                st.rotate_entities(sk, [linea], V(0, 0, 0), 10.0)
            doc.recompute()
            nombres = {c.Name for c in sk.Constraints if c.Name}
            colgadas = [e for _p, e in sk.ExpressionEngine
                        if any(n not in nombres for n in re.findall(r"Constraints\.([A-Za-z_]\w*)", e))]
            if colgadas or "Invalid" in sk.State:
                problemas.append("%s la línea con la cota: quedan %d fórmulas a una cota borrada (%s), croquis %s"
                                 % (herramienta, len(colgadas), colgadas[:1], sk.State))
            else:
                traza("  %s: sin fórmulas colgadas" % herramienta)
        finally:
            FreeCAD.closeDocument(doc.Name)
    assert not problemas, "\n".join(problemas)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
