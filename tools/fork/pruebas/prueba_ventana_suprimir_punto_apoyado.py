# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (la seguidilla del mono de piezas del 14/11, #87): un Punto de referencia en el
centro de curvatura de una arista de un Redondeo, y después Suprimir el Agujero (en una pieza con
configuraciones: la supresión va por la tabla). FreeCAD renumera las aristas del redondeo; como SW,
el punto sigue a SU arista (antes quedaba sobre una recta: "Null path" / "infinite radius of
curvature" en el informe). El mono además hace Ctrl+Z y compara: todo como antes."""
TIPO = "completa"

from azar_comun import bombear  # noqa: E402

PASOS = [("guardar", 0), ("aceptar", 470890), ("aceptar", 2188), ("aceptar", 0), ("aceptar", 0), ("suprimir", 0)]


def prueba():
    from mono_comun import paso
    from mono_entornos import Pieza
    m = Pieza()
    historia = []
    for accion, semilla in PASOS:
        paso(m, accion, semilla, historia)  # cada paso mira el informe, Ctrl+Z y Ctrl+Y
        bombear(300)
    puntos = [o for o in m.doc.Objects if o.TypeId == "PartDesign::Point"]
    assert puntos, "la seguidilla no armó el Punto: la prueba no prueba nada"
    yield 300


from _base import ejecutar  # noqa: E402
ejecutar(globals())
