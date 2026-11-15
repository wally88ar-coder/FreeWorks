# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#93, la función sola (sin herramienta abierta): en un croquis con un oblongo cuyo largo ya
está fijado, una cota de longitud conducente sobre su recta lo deja redundante y
make_driven_if_redundant la pasa a conducida (el croquis queda sin redundantes y la medida es la
real). Una cota que NO sobra no se toca; una relación que sobra pero no es cota (Horizontal) no se
toca; una cota ya conducida no se toca; un número fuera de rango no rompe nada."""

import math  # noqa: E402

import FreeCAD  # noqa: E402

V = FreeCAD.Vector


def _oblongo(doc):
    import Part
    import Sketcher
    sk = doc.addObject("Sketcher::SketchObject", "Croquis")
    a0 = sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(0, 0, 0), V(0, 0, 1), 3), math.pi / 2, 3 * math.pi / 2))
    a1 = sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(10, 0, 0), V(0, 0, 1), 3), -math.pi / 2, math.pi / 2))
    l0 = sk.addGeometry(Part.LineSegment(V(0, 3, 0), V(10, 3, 0)))
    l1 = sk.addGeometry(Part.LineSegment(V(0, -3, 0), V(10, -3, 0)))
    for c in (Sketcher.Constraint("Tangent", a0, 1, l0, 1), Sketcher.Constraint("Tangent", a1, 2, l0, 2),
              Sketcher.Constraint("Tangent", a0, 2, l1, 1), Sketcher.Constraint("Tangent", a1, 1, l1, 2),
              Sketcher.Constraint("Horizontal", l0), Sketcher.Constraint("Equal", a0, a1),
              Sketcher.Constraint("Radius", a0, 3), Sketcher.Constraint("DistanceX", a0, 3, a1, 3, 10)):
        sk.addConstraint(c)
    return sk, l0, l1


def prueba():
    import Sketcher
    from swui.fork import driven_dims as dd
    doc = FreeCAD.newDocument("CotaSobra")
    sk, l0, l1 = _oblongo(doc)
    doc.recompute()
    assert not sk.RedundantConstraints, "el oblongo de partida ya es redundante"

    # cota que sobra: largo de la recta de arriba
    # sin recalcular a mano: la función recalcula sola (la lista de redundantes de FreeCAD solo se
    # actualiza al recalcular; dentro del aviso de cambio llega vieja)
    i = sk.addConstraint(Sketcher.Constraint("Distance", l0, 10))
    assert dd.make_driven_if_redundant(sk) is True
    assert not sk.Constraints[i].Driving, "no quedó conducida"
    assert not sk.RedundantConstraints, "sigue redundante: %s" % list(sk.RedundantConstraints)
    assert abs(sk.Constraints[i].Value - 10) < 1e-6, sk.Constraints[i].Value
    assert dd.make_driven_if_redundant(sk) is False, "una cota ya conducida no se toca"

    # cambiar la medida de la que manda (distancia entre centros) y recalcular: la conducida la sigue
    centros = [n for n, c in enumerate(sk.Constraints) if c.Type == "DistanceX"][0]
    sk.setDatum(centros, FreeCAD.Units.Quantity("12 mm"))
    doc.recompute()
    assert abs(sk.Constraints[i].Value - 12) < 1e-6, "la conducida no siguió el cambio: %s" % sk.Constraints[i].Value
    assert not sk.RedundantConstraints and not sk.ConflictingConstraints

    # cota que no sobra: posición del centro izquierdo respecto del origen
    j = sk.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 3, 0))
    sk.solve()
    assert not sk.RedundantConstraints, list(sk.RedundantConstraints)
    assert dd.make_driven_if_redundant(sk) is False
    assert sk.Constraints[j].Driving, "una cota que no sobra quedó conducida"

    # relación que sobra pero no es cota: no se toca
    k = sk.addConstraint(Sketcher.Constraint("Horizontal", l1))
    sk.solve()
    assert sk.RedundantConstraints, "la Horizontal de abajo debería sobrar"
    assert dd.make_driven_if_redundant(sk) is False
    assert sk.ConstraintCount == k + 1

    # croquis que ya venía con otro problema (esa Horizontal de más) + una cota que no sobra: no se
    # toca (pasarla a conducida no arregla nada)
    m = sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 3, 0))
    assert dd.make_driven_if_redundant(sk) is False
    assert sk.Constraints[m].Driving, "se tocó una cota que no sobraba en un croquis que ya tenía error"
    sk.delConstraint(m)
    sk.delConstraint(k)

    # lista vieja: una cota que sobraba se borra y en el mismo número entra una que no sobra, sin
    # recalcular entre medio (como hace Cota inteligente al cambiar de entidad)
    n = sk.addConstraint(Sketcher.Constraint("Distance", l1, 12))  # largo actual (centros a 12)
    sk.solve()
    assert list(sk.RedundantConstraints), "la cota de abajo debería sobrar"
    sk.delConstraint(n)
    n2 = sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 3, 0))
    assert n2 == n
    assert dd.make_driven_if_redundant(sk) is False
    assert sk.Constraints[n2].Driving, "con la lista vieja quedó conducida una cota que no sobra"
    sk.delConstraint(n2)

    # índices raros
    assert dd.make_driven_if_redundant(sk, 999) is False
    assert dd.make_driven_if_redundant(sk, -5) is False
    vacio = doc.addObject("Sketcher::SketchObject", "Vacio")
    assert dd.make_driven_if_redundant(vacio) is False
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
