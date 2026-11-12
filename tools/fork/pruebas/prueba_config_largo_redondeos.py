# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#74 (la variante que quedaba): con Redondeos y Chaflanes encima, agregar configuraciones con
otro largo e ir y venir entre ellas no deja nada con error, mientras la pieza sea posible (la pared
no llega al agujero). Lo que veía el mono era la pieza imposible: con la caja más corta, la pared
corta el agujero y el chaflán se rompe IGUAL sin configuraciones (eso lo comprueba también)."""

import random  # noqa: E402

import FreeCAD  # noqa: E402

V = FreeCAD.Vector


def _rectas(obj, minimo=15):
    out = []
    for i, e in enumerate(obj.Shape.Edges):
        try:
            curva = e.Curve.__class__.__name__
        except TypeError:  # curvas que FreeCAD no expone (tras redondeos)
            continue
        if curva == "Line" and e.Length >= minimo:
            out.append("Edge%d" % (i + 1))
    return out


def _pieza():
    doc = FreeCAD.newDocument("LargoRedondeos")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 40, 30, 20
    caja.Placement.Base = V(-20, -15, 0)
    hueco = body.newObject("PartDesign::SubtractiveCylinder", "Agujero")
    hueco.Radius, hueco.Height = 3, 20
    hueco.Placement.Base = V(10, 5, 0)
    doc.recompute()
    return doc, body, caja


def _operacion(doc, body, rng):
    tip = body.Tip
    lista = _rectas(tip)
    if not lista:
        return
    tipo = rng.choice(["PartDesign::Fillet", "PartDesign::Chamfer"])
    o = body.newObject(tipo, "Op")
    o.Base = (tip, rng.sample(lista, min(len(lista), rng.randint(1, 3))))
    if tipo.endswith("Fillet"):
        o.Radius = round(rng.uniform(0.5, 4.0), 2)
    else:
        o.Size = round(rng.uniform(0.5, 4.0), 2)
    doc.recompute()
    if not o.isValid():  # como cancelar el panel: no queda
        body.removeObject(o)
        doc.removeObject(o.Name)
        body.Tip = tip
        doc.recompute()


def _rotos(body):
    return [o.Name for o in body.Group if "Invalid" in str(o.State)]


def prueba():
    from swui.fork import configurations as cf
    for semilla in range(10):
        rng = random.Random(semilla)
        doc, body, caja = _pieza()
        cf.ensure(doc)
        largos = {cf.active(doc): 40.0}
        for paso in range(7):
            accion = rng.choice(["op", "op", "nueva", "ir"])
            if accion == "op":
                _operacion(doc, body, rng)
            elif accion == "nueva" and len(largos) < 4:
                nombre = cf.add(doc, "C%d" % paso)
                largos[nombre] = round(rng.uniform(40.0, 70.0), 1)
                cf.configure(doc, ("prop", caja, "Length"), largos[nombre], scope="this")
                doc.recompute()
            else:
                nombre = rng.choice(sorted(largos))
                cf.activate(doc, nombre)
                doc.recompute()
                assert abs(caja.Length.Value - largos[nombre]) < 1e-6, (semilla, nombre, caja.Length)
            assert not _rotos(body), "semilla %d, paso %d (%s): con error %s" % (semilla, paso, accion, _rotos(body))
        FreeCAD.closeDocument(doc.Name)
    # la causa de lo que veía el mono: caja corta = pared contra el agujero, sin configuraciones
    rotas = 0
    for semilla in range(16):
        rng = random.Random(semilla)
        doc, body, caja = _pieza()
        for _ in range(rng.randint(1, 3)):
            _operacion(doc, body, rng)
        caja.Length = 30  # pared en x = 10: corta el agujero por el medio
        doc.recompute()
        rotas += bool(_rotos(body))
        FreeCAD.closeDocument(doc.Name)
    assert rotas, "con la pared cortando el agujero alguna pieza tendría que romperse (sin configuraciones)"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
