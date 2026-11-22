# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Hallado por la regla de campos el 22/11 (batería completa): en el croquis, Equidistanciar entidades dejaba
escribir 0 en la distancia y al Aceptar salía un error en el informe ("La distancia tiene que ser mayor que cero").
Causa: el campo tiene mínimo 0,001 pero muestra 2 decimales, y Qt redondea el mínimo a 0. Lo mismo la separación
de la Matriz lineal del croquis.
Tiene que pasar: escribir 0 en esos campos deja el valor más chico que se ve (0,01 mm), no 0; Equidistanciar con 0
escrito acepta sin error en el informe y agrega la equidistancia."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from reglas_paneles import informe_largo, mensajes_nuevos  # noqa: E402


def _escribir(spin, texto):
    le = spin.lineEdit()
    le.selectAll()
    le.setText(texto)
    spin.interpretText()
    bombear(200)


def prueba():
    import random

    import FreeCADGui
    import casos_croquis as cc
    from swui.fork import sketch_transform

    # el campo solo: el mínimo que se ve, nunca 0
    for dec in (2, 3):
        s = sketch_transform._spin(10.0, " mm", 0.0001, 1e6, decimals=dec)
        _escribir(s, "0")
        assert s.minimum() > 0 and abs(s.value() - 10 ** -dec) < 1e-9, (
            "con %d decimales, 0 escrito queda en %r (mínimo %r; tiene que quedar el mínimo visible)" % (
                dec, s.value(), s.minimum()))

    doc = FreeCAD.newDocument("DistanciaCero")
    caso = cc.Equidistanciar()
    caso.preparar(doc)
    for ms in caso.abrir(random.Random(1)):
        yield ms
    p = caso.panel()
    assert p is not None, "no abrió Equidistanciar"
    p.set_active("entities")
    FreeCADGui.Selection.addSelection(caso.croquis, "Edge1")
    yield 400
    _escribir(p.distance, "0")
    assert abs(p.distance.value() - 0.01) < 1e-9, "la distancia quedó en %r, no 0,01" % p.distance.value()
    p.hover = FreeCAD.Vector(15, -5, 0)
    p.update()
    yield 300
    antes = caso.croquis.GeometryCount
    desde = informe_largo()
    ok = p.accept()
    yield 600
    errores = mensajes_nuevos(desde)
    traza("  aceptó: %s, geometrías %d -> %d, errores %s" % (ok, antes, caso.croquis.GeometryCount, errores))
    assert ok, "Equidistanciar con 0 escrito no aceptó"
    assert not errores, "error en el informe: %s" % errores
    assert caso.croquis.GeometryCount > antes, "no agregó la equidistancia"

    p2 = None
    cc.correr_cinta("SWUI_SketchLinearPattern")
    for _ in range(30):
        yield 250
        p2 = caso.panel()
        if p2 is not None and hasattr(p2, "spacing1"):
            break
    assert p2 is not None and hasattr(p2, "spacing1"), "no abrió la Matriz lineal del croquis"
    _escribir(p2.spacing1, "0")
    assert abs(p2.spacing1.value() - 0.01) < 1e-9, "la separación quedó en %r, no 0,01" % p2.spacing1.value()
    p2.reject()
    yield 300
    FreeCADGui.ActiveDocument.resetEdit()
    yield 500
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
