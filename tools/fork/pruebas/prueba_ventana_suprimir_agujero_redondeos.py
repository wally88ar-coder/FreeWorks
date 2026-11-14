# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (la seguidilla del mono de piezas del 14/11): guardar, cuatro Redondeos aceptados
y después Suprimir el Agujero (#87). Como SW: se suprimen también las operaciones que dependen de él
(los redondeos sobre sus aristas) y los redondeos que quedan activos siguen sobre sus aristas, sin
error (uno quedaba con "Invalid edge link": FreeCAD nombraba su arista a través del agujero)."""
TIPO = "completa"

from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

PASOS = [("guardar", 323), ("aceptar", 0), ("aceptar", 0), ("aceptar", 0), ("aceptar", 0)]


def prueba():
    from mono_comun import paso
    from mono_entornos import Pieza
    from swui.fork import feature_tree as ft
    m = Pieza()
    historia = []
    for accion, semilla in PASOS:
        body = m.cuerpo()
        if accion == "suprimir" and body is not None:
            for f in ft.features(body):
                traza("  %s: padres %s" % (f.Label, [p.Label for p in ft.parents(f)]))
        paso(m, accion, semilla, historia)
        bombear(300)
    # suprimido el Agujero (y sus hijos), los redondeos que siguen activos quedan bien y sobre
    # aristas que existen (#87: uno quedaba con "Invalid edge link")
    m.doc.openTransaction("Suprimir")
    agujero = m.doc.getObject("Agujero") or [f for f in ft.features(m.cuerpo()) if f.Label == "Agujero"][0]
    ft.suppress(agujero)
    m.doc.commitTransaction()
    m.doc.recompute()
    bombear(300)
    activos = [f for f in ft.features(m.cuerpo()) if f.isDerivedFrom("PartDesign::DressUp") and not f.Suppressed]
    assert activos, "no quedó ningún redondeo activo: la prueba no prueba nada"
    for f in activos:
        assert f.isValid(), "%s quedó con error después de suprimir el Agujero (#87)" % f.Label
        forma = f.Base[0].Shape
        for sub in f.Base[1]:
            assert not forma.getElement(sub).isNull(), "%s apunta a %s, que no existe (#87)" % (f.Label, sub)
    yield 300


from _base import ejecutar  # noqa: E402
ejecutar(globals())
