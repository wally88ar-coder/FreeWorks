# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Multicuerpo con medidas al azar (plan de calidad, paso 8.2, grupo 6), sin ventana, por las
funciones públicas de `multibody`. De 2 a 4 sólidos (cubos de medida al azar, apilados con
separaciones al azar) y un agujero pasante del primero que los atraviesa a todos:
- Alcance con un subconjunto al azar: cada sólido elegido pierde exactamente su cilindro
  (π·r²·alto) y los no elegidos quedan iguales;
- `touched_bodies` (selección automática): los sólidos que el corte Por todo atraviesa son todos
  (error conocido #42: solo ve los que entran en el alto del sólido propio);
- sacar sólidos del Alcance: vuelven a su volumen original; si después de la copia el sólido tenía
  otra operación, no pierde nada de lo anterior (error conocido #1).
Casos por regla: FW_CASOS_AZAR (6 por omisión)."""
TIPO = "azar"

import math  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402

from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector


def armar(datos):
    import Part
    doc = FreeCAD.newDocument("Multi")
    cuerpos, altos = [], []
    z = 0.0
    for i, (lado, alto, sep) in enumerate(datos):
        b = doc.addObject("PartDesign::Body", "Solido%d" % i)
        c = b.newObject("PartDesign::AdditiveBox", "Caja%d" % i)
        c.Length = c.Width = lado
        c.Height = alto
        c.Placement.Base = V(-lado / 2, -lado / 2, z)
        cuerpos.append(b)
        altos.append(alto)
        z += alto + sep
    doc.recompute()
    a = cuerpos[0]
    sk = a.newObject("Sketcher::SketchObject", "CroquisAgujero")
    sk.AttachmentSupport = [([f for f in a.Origin.OriginFeatures if f.Role == "XY_Plane"][0], "")]
    sk.MapMode = "FlatFace"
    r = 1.0
    sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), r))
    doc.recompute()
    pk = a.newObject("PartDesign::Pocket", "Agujero")
    pk.Profile = sk
    pk.Type = "ThroughAll"
    pk.Midplane = True
    doc.recompute()
    return doc, cuerpos, altos, pk, r


pila = st.lists(st.tuples(st.floats(10, 60), st.floats(2, 30), st.floats(1, 20)), min_size=2, max_size=4)


@cfg
@given(datos=pila, data=st.data())
def alcance(datos, data):
    from swui.fork import multibody as mb
    doc, cuerpos, altos, pk, r = armar(datos)
    try:
        llenos = {b.Name: b.Shape.Volume + (math.pi * r * r * altos[0] if b is cuerpos[0] else 0) for b in cuerpos}
        comprobado()
        otros = data.draw(st.lists(st.sampled_from(cuerpos[1:]), unique=True))
        elegidos = [cuerpos[0]] + otros
        _c, _b, problemas = mb.apply_scope(pk, elegidos)
        doc.recompute()
        assert not problemas, problemas
        for b, h in zip(cuerpos, altos):
            quiero = llenos[b.Name] - (math.pi * r * r * h if b in elegidos else 0)
            assert cerca(b.Shape.Volume, quiero, rel=1e-6, absoluto=1e-3), \
                "%s %s: volumen %.3f, esperado %.3f" % (b.Label, "elegido" if b in elegidos else "no elegido",
                                                      b.Shape.Volume, quiero)
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(datos=pila)
def detecta(datos):
    """`touched_bodies` (la selección automática del Alcance): todos los sólidos que el corte
    Por todo atraviesa."""
    from swui.fork import multibody as mb
    doc, cuerpos, _altos, pk, _r = armar(datos)
    try:
        tocados = mb.touched_bodies(pk)
        comprobado()
        assert {b.Name for b in tocados} >= {b.Name for b in cuerpos}, \
            "el corte Por todo toca %s y atraviesa %s" % ([b.Label for b in tocados], [b.Label for b in cuerpos])
    finally:
        FreeCAD.closeDocument(doc.Name)


def _sacar(con_operacion_despues):
    @cfg
    @given(datos=pila)
    def regla(datos):
        from swui.fork import multibody as mb
        doc, cuerpos, altos, pk, r = armar(datos)
        try:
            originales = {b.Name: b.Shape.Volume for b in cuerpos[1:]}
            mb.apply_scope(pk, cuerpos)
            doc.recompute()
            extra = {}
            if con_operacion_despues:
                for b in cuerpos[1:]:  # una operación DESPUÉS de la copia
                    lado = b.Shape.BoundBox.XLength
                    c = b.newObject("PartDesign::AdditiveBox", "Extra")
                    c.Length = c.Width = c.Height = 3
                    c.Placement.Base = V(lado / 2, -1.5, b.Shape.BoundBox.ZMin)
                    extra[b.Name] = 27.0
                doc.recompute()
            mb.apply_scope(pk, [cuerpos[0]])
            doc.recompute()
            comprobado()
            for b in cuerpos[1:]:
                quiero = originales[b.Name] + extra.get(b.Name, 0.0)
                assert cerca(b.Shape.Volume, quiero, rel=1e-6, absoluto=1e-3), \
                    "%s, sacado del Alcance: volumen %.3f, esperado %.3f" % (b.Label, b.Shape.Volume, quiero)
        finally:
            FreeCAD.closeDocument(doc.Name)
    return regla


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn, conocido in (("alcance", alcance, ""), ("detecta los sólidos que atraviesa", detecta, "#42"),
                                 ("sacar del alcance", _sacar(False), ""),
                                 ("sacar del alcance con operación después", _sacar(True), "#1")):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn, conocido)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
