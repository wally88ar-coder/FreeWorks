# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Configuraciones de pieza con medidas al azar (plan de calidad, paso 8.2, grupo 8), sin
ventana, por las funciones públicas de `configurations` (add, configure, suppress, activate).
Pieza: cubo L × A × H con un agujero. Se agregan de 1 a 3 configuraciones (como SW, cada nueva
copia la activa); en cada una se cambia el largo (solo en esa) y a veces se suprime el agujero
(solo en esa):
- en cada configuración la pieza tiene SU largo y SU agujero (volumen = L·A·H − agujero si está);
- ir y venir entre configuraciones en cualquier orden da siempre lo mismo para cada una;
- la primera configuración no cambia nunca;
- guardar con una configuración activa y abrir: sigue esa, con sus valores.
Casos por regla: FW_CASOS_AZAR (6 por omisión)."""
TIPO = "azar"

import math  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector
R = 2.0


def pieza(L, A, H):
    doc = FreeCAD.newDocument("Config")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = L, A, H
    hueco = body.newObject("PartDesign::SubtractiveCylinder", "Agujero")
    hueco.Radius, hueco.Height = R, H
    hueco.Placement.Base = V(5, 5, 0)
    doc.recompute()
    return doc, body, caja, hueco


def volumen_esperado(L, A, H, con_agujero):
    return L * A * H - (math.pi * R * R * H if con_agujero else 0.0)


configs = st.lists(st.tuples(st.floats(12, 200), st.booleans()), min_size=1, max_size=3)


@cfg
@given(L=st.floats(12, 200), A=st.floats(12, 100), H=st.floats(2, 50), otras=configs, data=st.data())
def ir_y_venir(L, A, H, otras, data):
    from swui.fork import configurations as cf
    doc, body, caja, hueco = pieza(L, A, H)
    try:
        cf.ensure(doc)
        primera = cf.active(doc) or cf.names(doc)[0]
        quiero = {primera: (L, True)}
        anterior = True  # como SW: la configuración nueva copia la activa (la que se acaba de hacer)
        for k, (largo, sin_agujero) in enumerate(otras):
            nombre = cf.add(doc, "Prueba%d" % k)
            cf.configure(doc, ("prop", caja, "Length"), round(largo, 2), scope="this")
            if sin_agujero:
                cf.suppress(hueco, scope="this")
            doc.recompute()
            anterior = anterior and not sin_agujero
            quiero[nombre] = (round(largo, 2), anterior)
        orden = data.draw(st.lists(st.sampled_from(sorted(quiero)), min_size=3, max_size=8))
        for nombre in orden:
            cf.activate(doc, nombre)
            doc.recompute()
            comprobado()
            largo, con_agujero = quiero[nombre]
            assert cerca(caja.Length.Value, largo, absoluto=1e-6), \
                "en %s el largo es %s, debería ser %s (orden %s)" % (nombre, caja.Length, largo, orden)
            assert bool(hueco.Suppressed) == (not con_agujero), \
                "en %s el agujero %s (orden %s)" % (nombre, "está suprimido" if hueco.Suppressed else "está", orden)
            v = volumen_esperado(largo, A, H, con_agujero)
            assert cerca(body.Shape.Volume, v, rel=1e-6), \
                "en %s el volumen es %.3f, debería ser %.3f (orden %s)" % (nombre, body.Shape.Volume, v, orden)
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(L=st.floats(12, 200), A=st.floats(12, 100), H=st.floats(2, 50), largo=st.floats(12, 200),
       sin_agujero=st.booleans())
def guardar(L, A, H, largo, sin_agujero):
    from swui.fork import configurations as cf
    doc, body, caja, hueco = pieza(L, A, H)
    largo = round(largo, 2)
    cf.ensure(doc)
    nombre = cf.add(doc, "Guardada")
    cf.configure(doc, ("prop", caja, "Length"), largo, scope="this")
    if sin_agujero:
        cf.suppress(hueco, scope="this")
    doc.recompute()
    ruta = os.path.join(carpeta_temporal(), "config.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    doc = FreeCAD.openDocument(ruta)
    try:
        doc.recompute()
        comprobado()
        caja, hueco, body = doc.getObject("Caja"), doc.getObject("Agujero"), doc.getObject("Cuerpo")
        assert cf.active(doc) == nombre, "al abrir quedó activa %s, se guardó con %s" % (cf.active(doc), nombre)
        assert cerca(caja.Length.Value, largo, absoluto=1e-6), "al abrir el largo es %s, debería ser %s" % (caja.Length, largo)
        assert bool(hueco.Suppressed) == sin_agujero, "al abrir el agujero no quedó como se guardó"
        v = volumen_esperado(largo, A, H, not sin_agujero)
        assert cerca(body.Shape.Volume, v, rel=1e-6), "al abrir el volumen es %.3f, debería ser %.3f" % (body.Shape.Volume, v)
    finally:
        FreeCAD.closeDocument(doc.Name)


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn in (("ir y venir", ir_y_venir), ("guardar y abrir", guardar)):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
