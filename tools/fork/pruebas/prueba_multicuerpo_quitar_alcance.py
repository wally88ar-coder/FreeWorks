# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Dos sólidos apilados (cubos de 10). Un taladro pasante del primero, con Alcance, se lleva
también al segundo; después el segundo recibe otra operación (un cubo más al costado). Si se
quita el segundo sólido del Alcance, el segundo vuelve a ser cubo + cubo sin agujero (2000 mm³):
no pierde nada de lo anterior a la copia borrada (Issue #1, arreglado)."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from comun import V, caja, cerca  # noqa: E402


def prueba():
    from swui.fork import multibody as mb
    doc = FreeCAD.newDocument("Alcance")
    a = doc.addObject("PartDesign::Body", "A")
    caja(a, "CajaA", 10, 10, 10)
    b = doc.addObject("PartDesign::Body", "B")
    caja(b, "CajaB", 10, 10, 10, V(0, 0, 20))
    doc.recompute()
    sk = a.newObject("Sketcher::SketchObject", "CroquisAgujero")
    sk.AttachmentSupport = [(a.Origin.OriginFeatures[3], "")]  # plano XY
    sk.MapMode = "FlatFace"
    sk.addGeometry(Part.Circle(V(5, 5, 0), V(0, 0, 1), 2))
    doc.recompute()
    pk = a.newObject("PartDesign::Pocket", "Agujero")
    pk.Profile = sk
    pk.Type = "ThroughAll"
    pk.Midplane = True
    doc.recompute()
    creadas, _borradas, problemas = mb.apply_scope(pk, [a, b])
    doc.recompute()
    assert creadas and not problemas, (creadas, problemas)
    assert b.Shape.Volume < 999, "la copia no agujereó el segundo sólido: %.1f" % b.Shape.Volume
    caja(b, "CajaB2", 10, 10, 10, V(10, 0, 20))  # operación DESPUÉS de la copia
    doc.recompute()
    _c, borradas, _p = mb.apply_scope(pk, [a])
    doc.recompute()
    assert borradas, "no borró la copia"
    assert cerca(b.Shape.Volume, 2000, 0.5), \
        "el segundo sólido quedó con %.1f mm³ (esperado 2000)" % b.Shape.Volume


from _base import ejecutar  # noqa: E402
ejecutar(globals())
