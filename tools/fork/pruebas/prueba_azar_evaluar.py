# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Evaluar (Propiedades físicas) con medidas al azar (plan de calidad, paso 8.2, grupo 7), sin
ventana, por las funciones públicas (`material.assign`, `mass_props.components` y `compute`).
Cubos y cilindros de medida, posición y giro al azar, con un material al azar de la biblioteca:
- masa = densidad del material × volumen;
- centro de masa = el del sólido (o el promedio por masa de varios);
- inercia en el centro de masa: los momentos principales son los de libro (cubo: m(b²+c²)/12;
  cilindro: m·r²/2 y m(3r²+h²)/12), giren como giren;
- varios sólidos: el tensor total es la suma de cada uno trasladado (Steiner) al centro común.
Casos por regla: FW_CASOS_AZAR (6 por omisión)."""
TIPO = "azar"

import os  # noqa: E402

import FreeCAD  # noqa: E402

from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector

medida = st.floats(1.0, 200.0)
posicion = st.tuples(st.floats(-300, 300), st.floats(-300, 300), st.floats(-300, 300))
giro = st.tuples(st.floats(-1, 1), st.floats(-1, 1), st.floats(-1, 1), st.floats(0, 360))


def _material(data):
    from swui.fork import material
    todos = [m for m in material.all_materials() if (material.density_from(m) or 0) > 0]
    assert todos, "la biblioteca no tiene materiales con densidad"
    return data.draw(st.sampled_from(todos))


def _cuerpo(doc, nombre, forma, dims, pos, rot):
    b = doc.addObject("PartDesign::Body", nombre)
    if forma == "cubo":
        c = b.newObject("PartDesign::AdditiveBox", "Caja")
        c.Length, c.Width, c.Height = dims
    else:
        c = b.newObject("PartDesign::AdditiveCylinder", "Cilindro")
        c.Radius, c.Height = dims
    eje = V(*rot[:3])
    if eje.Length < 1e-6:
        eje = V(0, 0, 1)
    b.Placement = FreeCAD.Placement(V(*pos), FreeCAD.Rotation(eje, rot[3]))
    return b


def _principales_libro(forma, dims, masa):
    if forma == "cubo":
        a, b, c = dims
        return sorted([masa * (b * b + c * c) / 12, masa * (a * a + c * c) / 12, masa * (a * a + b * b) / 12])
    r, h = dims
    return sorted([masa * r * r / 2, masa * (3 * r * r + h * h) / 12, masa * (3 * r * r + h * h) / 12])


@cfg
@given(data=st.data(), forma=st.sampled_from(["cubo", "cilindro"]), pos=posicion, rot=giro)
def un_solido(data, forma, pos, rot):
    from swui.fork import mass_props as mp
    from swui.fork import material
    dims = (data.draw(medida), data.draw(medida), data.draw(medida)) if forma == "cubo" else \
        (data.draw(st.floats(0.5, 100)), data.draw(medida))
    doc = FreeCAD.newDocument("Masa")
    try:
        b = _cuerpo(doc, "Pieza", forma, dims, pos, rot)
        doc.recompute()
        info = _material(data)
        material.assign([b], info)
        doc.recompute()
        rho = material.density_from(info)
        res, _rhos, _n, _notas = mp.compute(mp.components(doc))
        comprobado()
        vol = b.Shape.Volume
        assert cerca(res["mass"], rho * vol, rel=1e-9), "masa %.6g, densidad × volumen = %.6g (%s)" % (
            res["mass"], rho * vol, info["name"])
        c = b.Shape.Solids[0].CenterOfMass
        assert all(abs(res["center"][k] - (c.x, c.y, c.z)[k]) < 1e-6 for k in range(3)), \
            "centro de masa %s, el del sólido es %s" % (res["center"], c)
        principales = [v for v, _a in mp.principal(res["inertia_cm"])]
        libro = _principales_libro(forma, dims, res["mass"])
        assert all(cerca(x, y, rel=1e-6) for x, y in zip(principales, libro)), \
            "%s %s: momentos principales %s, de libro %s" % (forma, dims, principales, libro)
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(data=st.data(), n=st.integers(2, 4))
def varios_solidos(data, n):
    """Varios cubos separados: masa total, centro por masa y tensor por Steiner (cuenta propia)."""
    from swui.fork import mass_props as mp
    from swui.fork import material
    doc = FreeCAD.newDocument("Masa")
    try:
        cuerpos = []
        for i in range(n):
            dims = (data.draw(medida), data.draw(medida), data.draw(medida))
            pos = (i * 500.0, data.draw(st.floats(-100, 100)), data.draw(st.floats(-100, 100)))  # separados
            cuerpos.append((_cuerpo(doc, "Pieza%d" % i, "cubo", dims, pos, (0, 0, 1, 0)), dims))
        doc.recompute()
        infos = []
        for b, _d in cuerpos:
            info = _material(data)
            material.assign([b], info)
            infos.append(info)
        doc.recompute()
        res, _rhos, _n, _notas = mp.compute(mp.components(doc))
        comprobado()
        masas, centros = [], []
        for (b, dims), info in zip(cuerpos, infos):
            masas.append(material.density_from(info) * b.Shape.Volume)
            c = b.Shape.Solids[0].CenterOfMass
            centros.append((c.x, c.y, c.z))
        M = sum(masas)
        cg = [sum(m * c[k] for m, c in zip(masas, centros)) / M for k in range(3)]
        assert cerca(res["mass"], M, rel=1e-9), "masa %.6g, suma %.6g" % (res["mass"], M)
        assert all(abs(res["center"][k] - cg[k]) < 1e-6 for k in range(3)), "centro %s, esperado %s" % (res["center"], cg)
        # tensor de libro (cubos sin girar) llevado al centro común con Steiner, hecho aparte
        esperado = [[0.0] * 3 for _i in range(3)]
        for (b, (a, bb, cc)), m, c in zip(cuerpos, masas, centros):
            propio = [m * (bb * bb + cc * cc) / 12, m * (a * a + cc * cc) / 12, m * (a * a + bb * bb) / 12]
            d = [c[k] - cg[k] for k in range(3)]
            dd = sum(x * x for x in d)
            for i in range(3):
                for j in range(3):
                    esperado[i][j] += (propio[i] if i == j else 0.0) + m * ((dd if i == j else 0.0) - d[i] * d[j])
        for i in range(3):
            for j in range(3):
                got = res["inertia_cm"][i][j]
                assert abs(got - esperado[i][j]) <= 1e-6 * max(1.0, abs(esperado[i][j])) + 1e-9 * max(abs(x) for r in esperado for x in r), \
                    "inercia [%d][%d] = %.6g, esperado %.6g" % (i, j, got, esperado[i][j])
    finally:
        FreeCAD.closeDocument(doc.Name)


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn in (("un sólido", un_solido), ("varios sólidos", varios_solidos)):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
