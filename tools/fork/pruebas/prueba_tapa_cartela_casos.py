# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Tapas y cartelas que siguen a sus miembros (#2), casos que encontró la revisión del 11/11:
- cambiar la medida del perfil del miembro (40x40 -> 50x50) no toca el croquis de su tapa (antes se
  tomaba como envolvente y se rellenaba con el rectángulo lleno);
- una tapa en una punta CON esquina (el caño se alarga de más y una caja corta) queda apoyada en la
  punta real, no flotando;
- sacar el miembro (como al quitar su línea en Editar) se lleva sus tapas y cartelas (antes
  quedaban con error)."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

V = FreeCAD.Vector


def _l(doc):
    from swui.fork import weldments as w
    sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
    sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(500, 0, 0)))
    sk.addGeometry(Part.LineSegment(V(500, 0, 0), V(500, 300, 0)))
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 2, 1, 1))
    doc.recompute()
    size = [s for s, _d in w.sizes("Caño cuadrado") if s.startswith("40x40x2")][0]
    a, b = w.create_members(doc, [(sk, "Edge1"), (sk, "Edge2")], "Caño cuadrado", size)
    w.apply_corners([a, b], "tope")
    doc.recompute()
    return a, b


def prueba():
    from swui.fork import weldments as w
    doc = FreeCAD.newDocument("TapaCasos")
    a, b = _l(doc)
    tapa = w.end_cap(a, 0, thickness=5, inset=2)
    doc.recompute()
    sk_tapa = [o for o in tapa.Group if o.TypeId == "Sketcher::SketchObject"][0]
    n_geo, etiqueta = sk_tapa.GeometryCount, sk_tapa.Label
    grande = [s for s, _d in w.sizes("Caño cuadrado") if s.startswith("50x50")][0]
    w._reshape(a, size=grande)
    doc.recompute()
    assert sk_tapa.Label == etiqueta and sk_tapa.GeometryCount == n_geo, \
        "cambiar el perfil tocó el croquis de la tapa: %s, %d elementos" % (sk_tapa.Label, sk_tapa.GeometryCount)

    # tapa en la punta con esquina (la de `b` que toca a `a`): apoyada en la punta real
    esquina = 0  # b va de (500,0) a (500,300): su punta 0 es la esquina
    tapa_b = w.end_cap(b, esquina, thickness=5)
    doc.recompute()
    d = tapa_b.Shape.distToShape(b.Shape)[0]
    assert d < 1e-3, "la tapa en la punta con esquina quedó a %.1f mm del caño (flotando)" % d

    cartela = w.gusset(a, b, size=80, thickness=6)
    doc.recompute()
    nombres = (tapa.Name, cartela.Name)
    w._forget(a)
    doc.recompute()
    quedan = [n for n in nombres if doc.getObject(n) is not None]
    assert not quedan, "sacar el miembro dejó sus tapas o cartelas: %s" % quedan
    malos = [o.Label for o in doc.Objects if "Invalid" in str(o.State)]
    assert not malos, "quedaron objetos con error: %s" % malos
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
