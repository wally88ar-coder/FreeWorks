# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (caso del azar de ensamblaje, 14/11): placa 10x10x10 fija con agujero de radio 2,5
y perno de radio 2 y alto 10, en (0; 1; 0) girado 1° alrededor de Y; Tangente entre la Face3 de la
placa y el cilindro del perno. Como SW: la pieza fija no se mueve, el eje del perno queda paralelo
a la cara y a la distancia de su radio."""
TIPO = "completa"
import FreeCAD  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402

V = FreeCAD.Vector


def prueba():
    import casos_relacion as base
    carpeta = carpeta_temporal()
    doc, asm, (placa, perno) = base._ensamblaje([base._pieza(carpeta, "Placa", 10, 10, 10, agujero=2.5),
                                                  base._pieza(carpeta, "Perno", 0, 0, 0, cilindro=(2, 10))])
    perno.Placement = FreeCAD.Placement(V(0, 1, 0), FreeCAD.Rotation(V(0, 1, 0), 1))
    doc.recompute()
    fijo0 = placa.Placement
    cil = ["Face%d" % (i + 1) for i, f in enumerate(perno.LinkedObject.Shape.Faces) if f.Surface.__class__.__name__ == "Cylinder"]
    r, _joint = base._relacionar(doc, asm, "tangent", [(placa, "Face3"), (perno, cil[0])])
    traza("  resultado %s; fija %s" % (r, placa.Placement))
    assert placa.Placement.isSame(fijo0, 1e-6), "la pieza fija se movió: %s" % placa.Placement
    assert r == 0, "no se resolvió (%s)" % r
    cara = base._cara_global(placa, "Face3")
    n1 = base._normal(cara)
    s = base._cara_global(perno, cil[0]).Surface
    assert abs(s.Axis.dot(n1)) < 1e-3, "el eje del perno no quedó paralelo a la cara"
    d = abs((s.Center - cara.CenterOfMass).dot(n1))
    assert abs(d - 2) < 1e-2, "el eje quedó a %.4f de la cara (radio 2)" % d
    yield 300
    base._cerrar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
