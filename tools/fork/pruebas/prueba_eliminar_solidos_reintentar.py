# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#18: Eliminar/Conservar sólidos arma todo o nada. Un Cuerpo partido en tres pedazos; se elimina
uno (quedan dos para armar). Si el segundo pedazo no se puede ubicar, no queda NADA creado; al
reintentar (ya sin la falla) se crean justo un punto, un filtro y un Cuerpo por pedazo, sin
duplicados."""

import FreeCAD  # noqa: E402

from comun import caja  # noqa: E402

V = FreeCAD.Vector


def prueba():
    from swui.fork import delete_bodies as db
    doc = FreeCAD.newDocument("Reintentar")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja(body, "Caja", 50, 10, 10)
    for x in (15, 30):
        hueco = body.newObject("PartDesign::SubtractiveBox", "Corte")
        hueco.Length, hueco.Width, hueco.Height = 5, 20, 20
        hueco.Placement.Base = V(x, -5, -5)
    doc.recompute()
    assert len(body.Shape.Solids) == 3, "la pieza de prueba no quedó en tres pedazos: %d" % len(body.Shape.Solids)
    group = doc.addObject("App::DocumentObjectGroup", "Group")
    spec = {"mode": "delete", "items": [{"body": body.Name, "point": [5, 5, 5]}]}
    antes = len(doc.Objects)

    original = db.inner_point
    llamadas = []

    def falla_al_segundo(solid, face=None):
        llamadas.append(1)
        return None if len(llamadas) == 2 else original(solid, face)

    db.inner_point = falla_al_segundo
    try:
        problema = db.build(doc, group, spec)
    finally:
        db.inner_point = original
    assert problema, "la falla del segundo pedazo no se avisó"
    assert len(doc.Objects) == antes, "la falla dejó %d objetos creados (#18)" % (len(doc.Objects) - antes)

    problema = db.build(doc, group, spec)
    doc.recompute()
    assert not problema, problema
    nuevos = len(doc.Objects) - antes
    tipos = sorted(o.TypeId for o in doc.Objects[antes:])
    assert [t for t in tipos if t == "PartDesign::Body"] == ["PartDesign::Body"] * 2, \
        "al reintentar quedaron %d Cuerpos nuevos (se esperan 2): %s" % (tipos.count("PartDesign::Body"), tipos)
    assert tipos.count("Part::Vertex") == 2, tipos
    assert nuevos >= 6, nuevos
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
