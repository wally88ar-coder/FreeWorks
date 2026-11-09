# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Ensamblajes con medidas al azar (plan de calidad, paso 8.2, grupo 4), con la ventana y por las
funciones del panel de relaciones (elegir como un clic, `entities_from_selection`, `create_joint`,
resolver). Piezas de medida al azar; la que se mueve arranca en una posición y un giro al azar:
- Coincidente entre dos caras planas: quedan en el mismo plano (paralelas y a distancia 0);
- Distancia d: paralelas y a distancia d;
- Ángulo a: las caras forman a (o 180 − a);
- Paralela / Perpendicular: normales paralelas / a 90°;
- Concéntrica entre el agujero de la placa y un perno: ejes en la misma recta;
- la pieza fija (la primera) no se mueve nunca;
- cambiar la medida de la pieza que se mueve y volver a resolver: la relación se sigue cumpliendo;
- guardar y abrir: cada componente queda donde estaba;
- Matriz de componentes: n instancias a paso p sobre la dirección elegida, sin corrimientos;
- Taladro de ensamblaje sobre una pieza movida y girada al azar: el agujero (Ø ISO 273) queda en
  la pieza con su eje en el punto marcado y perpendicular a la cara.
Casos por regla: FW_CASOS_AZAR (6 por omisión)."""
TIPO = "completa"

import math  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from azar_comun import Fallas, bombear, comprobado, hypothesis_listo  # noqa: E402

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector
TOL = 1e-3


def _pieza(carpeta, nombre, l, a, h, agujero=0.0, cilindro=None):
    doc = FreeCAD.newDocument(nombre)
    body = doc.addObject("PartDesign::Body", "Body")
    if cilindro:
        c = body.newObject("PartDesign::AdditiveCylinder", "Perno")
        c.Radius, c.Height = cilindro
    else:
        c = body.newObject("PartDesign::AdditiveBox", "Caja")
        c.Length, c.Width, c.Height = l, a, h
        if agujero:
            hueco = body.newObject("PartDesign::SubtractiveCylinder", "Agujero")
            hueco.Radius, hueco.Height = agujero, h
            hueco.Placement.Base = V(l / 2, a / 2, 0)
    doc.recompute()
    ruta = os.path.join(carpeta, nombre + ".FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    return ruta


def _ensamblaje(rutas):
    from swui import assembly_drop
    carpeta = os.path.dirname(rutas[0])
    doc = FreeCAD.newDocument("Conjunto")
    FreeCAD.setActiveDocument(doc.Name)
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    asm.Type = "Assembly"
    asm.newObject("Assembly::JointGroup", "Joints")
    doc.recompute()
    doc.saveAs(os.path.join(carpeta, "Conjunto.FCStd"))
    comps = assembly_drop.insert_files(asm, rutas)
    doc.recompute()
    FreeCAD.setActiveDocument(doc.Name)
    bombear(300)
    return doc, asm, comps


def _ubicar(comp, rng_pos, rng_rot):
    """Posición y giro al azar de un componente (antes de relacionarlo)."""
    eje = V(*rng_rot[:3])
    if eje.Length < 1e-6:
        eje = V(0, 0, 1)
    comp.Placement = FreeCAD.Placement(V(*rng_pos), FreeCAD.Rotation(eje, rng_rot[3]))


def _caras_planas(comp):
    return ["Face%d" % (i + 1) for i, f in enumerate(comp.LinkedObject.Shape.Faces)
            if f.Surface.__class__.__name__ == "Plane"]


def _cara_global(comp, sub):
    import Part
    return Part.getShape(comp).getElement(sub)


def _plano(cara):
    n = cara.normalAt(*cara.ParameterRange[0:3:2])
    return cara.CenterOfMass, n


def _relacionar(doc, asm, key, refs, valor=None):
    """Como el panel: elegir con el camino del ensamblaje, armar la relación y resolver."""
    import FreeCADGui
    from swui.fork import mates_sw
    FreeCADGui.Selection.clearSelection()
    for comp, sub in refs:
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.%s" % (comp.Name, comp.LinkedObject.Name, sub))
    ents = mates_sw.entities_from_selection(asm)
    FreeCADGui.Selection.clearSelection()
    assert len(ents) == 2, "se eligieron %d referencias" % len(ents)
    assert key in mates_sw.applicable([e[2] for e in ents]), "%s no se ofrece para %s" % (key, [e[2] for e in ents])
    doc.openTransaction("Relación")
    mates_sw.create_joint(asm, key, [(e[0], e[1]) for e in ents], value=valor)
    r = mates_sw.solve(asm)
    doc.recompute()
    doc.commitTransaction()
    bombear(200)
    return r


medida = st.floats(min_value=10.0, max_value=120.0).map(lambda x: round(x, 1))
posicion = st.tuples(st.floats(-200, 200), st.floats(-200, 200), st.floats(-200, 200))
giro = st.tuples(st.floats(-1, 1), st.floats(-1, 1), st.floats(-1, 1), st.floats(0, 360))


def _armar(data, agujero=0.0, perno=None):
    carpeta = carpeta_temporal()
    W, D, H = data.draw(medida), data.draw(medida), data.draw(medida)
    if perno:
        rutas = [_pieza(carpeta, "Placa", W, D, H, agujero=agujero), _pieza(carpeta, "Perno", 0, 0, 0, cilindro=perno)]
    else:
        a, b, c = data.draw(medida), data.draw(medida), data.draw(medida)
        rutas = [_pieza(carpeta, "Placa", W, D, H), _pieza(carpeta, "Bloque", a, b, c)]
    doc, asm, comps = _ensamblaje(rutas)
    _ubicar(comps[1], data.draw(posicion), data.draw(giro))
    doc.recompute()
    return doc, asm, comps


def _fijo_quieto(comp, antes, que):
    assert comp.Placement.isSame(antes, 1e-6), "%s: la pieza fija se movió" % que


def _caras(data, key):
    doc, asm, (placa, bloque) = _armar(data)
    fijo0 = placa.Placement
    c1 = data.draw(st.sampled_from(_caras_planas(placa)))
    c2 = data.draw(st.sampled_from(_caras_planas(bloque)))
    valor = None
    if key == "distance":
        valor = round(data.draw(st.floats(0.5, 80)), 2)
    if key == "angle":
        valor = round(data.draw(st.floats(10, 170)), 1)
    r = _relacionar(doc, asm, key, [(placa, c1), (bloque, c2)], valor)
    assert r in (0, None), "%s: el ensamblaje no se resolvió (%s)" % (key, r)
    comprobado()
    _fijo_quieto(placa, fijo0, key)
    p1, n1 = _plano(_cara_global(placa, c1))
    p2, n2 = _plano(_cara_global(bloque, c2))
    coseno = abs(n1.dot(n2))
    que = "%s entre %s y %s" % (key, c1, c2)
    if key in ("coincident", "distance", "parallel"):
        assert abs(coseno - 1) < TOL, "%s: las caras no quedaron paralelas (coseno %.5f)" % (que, coseno)
    if key in ("coincident", "distance"):
        d = abs((p2 - p1).dot(n1))
        quiero = 0.0 if key == "coincident" else valor
        assert abs(d - quiero) < 1e-2, "%s: distancia entre caras %.4f, se pidió %s" % (que, d, quiero)
    if key == "perpendicular":
        assert coseno < TOL, "%s: no quedaron a 90° (coseno %.5f)" % (que, coseno)
    if key == "angle":
        ang = math.degrees(math.acos(max(-1.0, min(1.0, n1.dot(n2)))))
        assert min(abs(ang - valor), abs(ang - (180 - valor))) < 0.05, "%s: forman %.3f°, se pidió %s°" % (que, ang, valor)
    return doc, asm, placa, bloque, c1, c2, key, valor


@cfg
@given(data=st.data(), key=st.sampled_from(["coincident", "distance", "angle", "parallel", "perpendicular"]))
def caras(data, key):
    _caras(data, key)


@cfg
@given(data=st.data())
def concentrica(data):
    r = round(data.draw(st.floats(2, 10)), 2)
    doc, asm, (placa, perno) = _armar(data, agujero=r + 0.5, perno=(r, round(data.draw(st.floats(10, 60)), 1)))
    fijo0 = placa.Placement
    cil_p = ["Face%d" % (i + 1) for i, f in enumerate(placa.LinkedObject.Shape.Faces) if f.Surface.__class__.__name__ == "Cylinder"]
    cil_n = ["Face%d" % (i + 1) for i, f in enumerate(perno.LinkedObject.Shape.Faces) if f.Surface.__class__.__name__ == "Cylinder"]
    res = _relacionar(doc, asm, "concentric", [(placa, cil_p[0]), (perno, cil_n[0])])
    assert res in (0, None), "concéntrica: el ensamblaje no se resolvió (%s)" % res
    comprobado()
    _fijo_quieto(placa, fijo0, "concéntrica")
    a = _cara_global(placa, cil_p[0]).Surface
    b = _cara_global(perno, cil_n[0]).Surface
    assert abs(abs(a.Axis.dot(b.Axis)) - 1) < TOL, "concéntrica: ejes no paralelos"
    dif = b.Center - a.Center
    lejos = (dif - a.Axis * dif.dot(a.Axis)).Length
    assert lejos < 1e-2, "concéntrica: los ejes quedaron a %.4f mm" % lejos


@cfg
@given(data=st.data(), key=st.sampled_from(["coincident", "distance"]), nuevo=medida)
def cambiar_pieza(data, key, nuevo):
    doc, asm, placa, bloque, c1, c2, key, valor = _caras(data, key)
    # cambiar la medida del bloque (en su archivo), recalcular y volver a resolver, como el usuario
    pdoc = bloque.LinkedObject.Document
    caja = [o for o in pdoc.Objects if o.TypeId == "PartDesign::AdditiveBox"][0]
    caja.Length = nuevo
    pdoc.recompute()
    doc.recompute()
    from swui.fork import mates_sw
    r = mates_sw.solve(asm)
    doc.recompute()
    assert r in (0, None), "después de cambiar la pieza el ensamblaje no se resuelve (%s)" % r
    p1, n1 = _plano(_cara_global(placa, c1))
    p2, n2 = _plano(_cara_global(bloque, c2))
    assert abs(abs(n1.dot(n2)) - 1) < TOL, "después de cambiar la pieza las caras no son paralelas"
    d = abs((p2 - p1).dot(n1))
    quiero = 0.0 if key == "coincident" else valor
    assert abs(d - quiero) < 1e-2, "después de cambiar la pieza la distancia es %.4f, se pidió %s" % (d, quiero)


@cfg
@given(data=st.data())
def guardar(data):
    doc, asm, placa, bloque, c1, c2, key, valor = _caras(data, "coincident")
    pos = {c.Name: c.Placement for c in (placa, bloque)}
    ruta = doc.FileName
    doc.save()
    for n in list(FreeCAD.listDocuments()):
        FreeCAD.closeDocument(n)
    doc = FreeCAD.openDocument(ruta)
    bombear(500)
    for n, plc in pos.items():
        o = doc.getObject(n)
        assert o is not None and o.Placement.isSame(plc, 1e-6), "%s no quedó donde estaba al reabrir" % n


def _cdm(forma):
    vol = sum(s.Volume for s in forma.Solids) or 1.0
    c = V()
    for s in forma.Solids:
        c = c + s.CenterOfMass * (s.Volume / vol)
    return c


@cfg
@given(data=st.data(), n=st.integers(2, 5), paso=st.floats(20, 150))
def matriz_componentes(data, n, paso):
    """Matriz lineal de componentes por el panel: n copias (con la original) a paso p sobre la
    dirección de una arista recta de la placa."""
    import Part
    import FreeCADGui
    from azar_comun import aceptar, cinta, esperar_panel
    paso = round(paso, 1)
    doc, asm, (placa, bloque) = _armar(data)
    rectas = [i for i, e in enumerate(placa.LinkedObject.Shape.Edges) if e.Curve.__class__.__name__ == "Line"]
    arista = "Edge%d" % (data.draw(st.sampled_from(rectas)) + 1)
    cinta("SWUI_ComponentLinearPattern")
    assert esperar_panel(), "no se abrió la Matriz de componentes"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p._activate("seeds")
    bombear(200)
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.Face1" % (bloque.Name, bloque.LinkedObject.Name))
    bombear(500)
    p._activate("dir1")
    bombear(200)
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.%s" % (placa.Name, placa.LinkedObject.Name, arista))
    bombear(500)
    p.count1.setValue(n)
    p.spacing1.setValue(paso)
    bombear(1200)
    assert aceptar(), "la Matriz de componentes no aceptó"
    doc.recompute()
    from swui.fork import component_patterns as cp
    vs = [o for o in doc.Objects if o.TypeId == "App::VarSet" and getattr(o, cp.COPIES, None)]
    assert vs, "no quedó la matriz"
    comprobado()
    direc = Part.getShape(placa).getElement(arista)
    u = direc.Vertexes[-1].Point - direc.Vertexes[0].Point
    u.normalize()
    centros = [_cdm(Part.getShape(bloque))]
    for arr in cp.copies_of(vs[0]):
        for el in (arr.ElementList or [arr]):
            centros.append(_cdm(Part.getShape(el)))
    assert len(centros) == n, "hay %d instancias (con la original), se pidieron %d" % (len(centros), n)
    proy = sorted(c.dot(u) for c in centros)
    pasos = [round(b - a, 3) for a, b in zip(proy, proy[1:])]
    assert all(abs(x - paso) < 1e-2 for x in pasos), "pasos entre instancias %s, se pidió %s" % (pasos, paso)
    base = centros[0]
    for c in centros[1:]:
        dif = c - base
        lateral = (dif - u * dif.dot(u)).Length
        assert lateral < 1e-2, "una copia quedó corrida %.4f mm de la dirección" % lateral


ISO273_NORMAL = {"M3": 3.4, "M4": 4.5, "M5": 5.5, "M6": 6.6, "M8": 9.0, "M10": 11.0, "M12": 13.5}


@cfg
@given(data=st.data(), medida_m=st.sampled_from(sorted(ISO273_NORMAL)), fu=st.floats(0.3, 0.7), fv=st.floats(0.3, 0.7))
def taladro_girado(data, medida_m, fu, fv):
    """Taladro de ensamblaje sobre la cara de arriba de una pieza que está movida y GIRADA al azar:
    el agujero queda en la pieza donde se lo marcó (su eje pasa por el punto elegido)."""
    import Part
    from azar_comun import aceptar, esperar_panel
    doc, asm, (placa, bloque) = _armar(data)
    caja = bloque.LinkedObject.Shape
    arriba = None
    for i, f in enumerate(caja.Faces):
        n = f.normalAt(*f.ParameterRange[0:3:2])
        if f.Surface.__class__.__name__ == "Plane" and n.z > 0.99:
            arriba = "Face%d" % (i + 1)
    cara = Part.getShape(bloque).getElement(arriba)
    u0, u1, v0, v1 = cara.ParameterRange
    punto = cara.valueAt(u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv)
    normal = cara.normalAt(u0, v0)
    from swui.fork import assembly_features as af
    doc.openTransaction("Croquis de ensamblaje")
    sk = af.make_sketch(asm, bloque, "%s.%s" % (bloque.LinkedObject.Name, arriba))
    loc = sk.Placement.inverse().multVec(punto)
    sk.addGeometry(Part.Point(V(loc.x, loc.y, 0)))
    sk.recompute()
    doc.commitTransaction()
    af.open_panel_new(asm, "hole", sk)
    assert esperar_panel(), "no se abrió el panel del taladro de ensamblaje"
    from swui.fork import hole_panel, panel_guard
    p = panel_guard.open_panel()
    p.kind.setCurrentIndex(p.kind.findData(hole_panel.PLAIN))
    bombear(400)
    textos = [p.size.itemText(i) for i in range(p.size.count())]
    p.size.setCurrentIndex(textos.index(medida_m))
    p.fit.setCurrentIndex(1)
    p.end.setCurrentIndex(p.end.findData("ThroughAll"))
    p.preview()
    bombear(1000)
    assert aceptar(), "el taladro de ensamblaje no aceptó"
    doc.recompute()
    bloque.LinkedObject.Document.recompute()
    doc.recompute()
    comprobado()
    r = ISO273_NORMAL[medida_m] / 2
    cil = [f for f in Part.getShape(bloque).Faces
           if f.Surface.__class__.__name__ == "Cylinder" and abs(f.Surface.Radius - r) < 1e-3]
    assert cil, "la pieza no tiene un agujero de Ø %s" % (2 * r)
    s = cil[0].Surface
    assert abs(abs(s.Axis.dot(normal)) - 1) < 1e-3, "el agujero no quedó perpendicular a la cara"
    dif = punto - s.Center
    lejos = (dif - s.Axis * dif.dot(s.Axis)).Length
    assert lejos < 1e-2, "el agujero quedó a %.4f mm del punto marcado (pieza girada)" % lejos


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn in (("relaciones entre caras", caras), ("concéntrica", concentrica),
                       ("cambiar una pieza", cambiar_pieza), ("guardar y abrir", guardar),
                       ("matriz de componentes", matriz_componentes), ("taladro en pieza girada", taladro_girado)):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
