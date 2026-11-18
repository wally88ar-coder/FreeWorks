# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#98: Taladro con una arista elegida (FreeCAD arma el taladro con la arista de perfil, no un croquis):
el panel cuenta 0 posiciones sin error (antes: AttributeError 'Geometry'). Con un croquis de perfil, cuenta
sus puntos y círculos que no son de construcción."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402

V = FreeCAD.Vector


def prueba():
    from swui.fork import hole_panel as hp
    doc = FreeCAD.newDocument("TaladroArista")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    doc.recompute()

    class Falso:
        pass
    p = Falso()
    p.obj = Falso()
    p.obj.Profile = [caja, ["Edge1"]]  # la arista: el perfil es la caja, no un croquis
    p._sketch = lambda: hp.HolePanel._sketch(p)
    assert hp.HolePanel.centers(p) == 0
    sk = body.newObject("Sketcher::SketchObject", "Posiciones")
    sk.addGeometry(Part.Point(V(1, 1, 0)))
    sk.addGeometry(Part.Circle(V(5, 5, 0), V(0, 0, 1), 2))
    sk.addGeometry(Part.Circle(V(9, 9, 0), V(0, 0, 1), 2), True)  # de construcción: no cuenta
    p.obj.Profile = [sk, [""]]
    assert hp.HolePanel.centers(p) == 2, hp.HolePanel.centers(p)
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
