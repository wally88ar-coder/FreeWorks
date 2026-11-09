# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Piezas soldadas con medidas al azar (plan de calidad, paso 8.2, grupo 2), sin ventana, por las
funciones públicas de `weldments` (el panel solo junta los datos y las llama). Marcos cerrados
(paralelogramos y triángulos: lados 100-2000 mm, ángulos de 30° a 150°), cualquier perfil del
catálogo que entre, esquinas a tope o a inglete:
- todos los caños quedan válidos;
- ningún caño se superpone con otro (suma de volúmenes = volumen de todos unidos);
- en cada esquina los dos caños se tocan (sin huecos);
- la lista de cortes da, para cada caño, su largo real (de punta a punta sobre su eje);
- guardar y abrir deja los mismos volúmenes;
- mover un vértice del esqueleto y recalcular: todo lo anterior se sigue cumpliendo, y cada caño
  queda igual que armando el marco de cero con el esqueleto nuevo (error conocido #2, a tope y a
  inglete).
Casos por regla: FW_CASOS_AZAR (6 por omisión)."""
TIPO = "azar"

import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector


def _w():
    from swui.fork import weldments as w
    return w


# --- Esqueletos y perfiles al azar -----------------------------------------------------------------


@st.composite
def esqueletos(draw):
    """Puntos de un marco cerrado: paralelogramo (4) o triángulo (3), en mm."""
    import math
    if draw(st.booleans()):
        a = draw(st.floats(100, 2000))
        b = draw(st.floats(100, 2000))
        ang = math.radians(draw(st.floats(30, 150)))
        p = [V(0, 0, 0), V(a, 0, 0), V(a + b * math.cos(ang), b * math.sin(ang), 0),
             V(b * math.cos(ang), b * math.sin(ang), 0)]
    else:
        a = draw(st.floats(150, 2000))
        ang1 = math.radians(draw(st.floats(30, 120)))
        ang2 = math.radians(draw(st.floats(30, min(120, 150 - math.degrees(ang1)))))
        # triángulo con base a y ángulos ang1, ang2 en sus puntas
        h_x = a * math.tan(ang2) / (math.tan(ang1) + math.tan(ang2))
        p = [V(0, 0, 0), V(a, 0, 0), V(h_x, h_x * math.tan(ang1), 0)]
    return [V(round(q.x, 2), round(q.y, 2), 0) for q in p]


@st.composite
def perfiles(draw, lado_min):
    w = _w()
    tipo = draw(st.sampled_from([k for k in w.profile_names() if k != "Planchuela"]))
    entran = [n for n, d in w.sizes(tipo) if max(w.extent(tipo, d)) < lado_min / 4.0]
    if not entran:
        tipo = "Caño cuadrado"
        entran = [n for n, d in w.sizes(tipo) if max(w.extent(tipo, d)) < lado_min / 4.0]
    return tipo, draw(st.sampled_from(entran))


def _lado_min(pts):
    return min((pts[i] - pts[(i + 1) % len(pts)]).Length for i in range(len(pts)))


def armar(pts, tipo, medida, esquina):
    import Part
    w = _w()
    doc = FreeCAD.newDocument("Soldada")
    sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
    for i in range(len(pts)):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % len(pts)]))
    doc.recompute()
    cuerpos = w.create_members(doc, [(sk, "Edge%d" % (i + 1)) for i in range(len(pts))], tipo, medida)
    w.apply_corners(cuerpos, esquina)
    doc.recompute()
    return doc, sk, cuerpos


def mover_vertice(doc, sk, i, nuevo):
    """Mueve el vértice i del esqueleto (las dos líneas que lo comparten) y recalcula todo."""
    g = sk.Geometry
    n = len(g)
    g[i].StartPoint = nuevo
    g[(i - 1) % n].EndPoint = nuevo
    sk.Geometry = g
    for o in doc.Objects:
        o.touch()
    doc.recompute()


# --- Las comprobaciones ---------------------------------------------------------------------------


def chequear(doc, cuerpos, que):
    w = _w()
    comprobado()
    malos = [b.Label for b in cuerpos if not b.Shape.isValid() or b.Shape.isNull()
             or "Invalid" in str(b.State)]
    assert not malos, "%s: caños con error: %s" % (que, malos)
    # superposición: lo que comparte cada par (exacto). Unir todo y comparar volúmenes no sirve:
    # con caños redondos la unión de FreeCAD da unos mm³ de diferencia sin superposición real
    for i in range(len(cuerpos)):
        for j in range(i + 1, len(cuerpos)):
            comun = cuerpos[i].Shape.common(cuerpos[j].Shape).Volume
            assert comun < 0.01, "%s: %s y %s se superponen %.3f mm³" % (
                que, cuerpos[i].Label, cuerpos[j].Label, comun)
    for c in w.find_corners(cuerpos):
        d = c["a"].Shape.distToShape(c["b"].Shape)[0]
        assert d < 1e-3, "%s: hueco de %.2f mm entre %s y %s" % (que, d, c["a"].Label, c["b"].Label)
    filas = w.cut_list(doc)
    por_caño = {}
    for f in filas:
        for etiqueta in f["members"]:
            por_caño[etiqueta] = f["length"]
    for b in cuerpos:
        _p0, _p1, u = w.axis(b)
        proy = [v.Point.dot(u) for v in b.Shape.Vertexes]
        real = max(proy) - min(proy)
        lista = por_caño.get(b.Label)
        assert lista is not None, "%s: %s no está en la lista de cortes" % (que, b.Label)
        assert abs(lista - real) <= 0.1, \
            "%s: la lista de cortes dice %.1f para %s y mide %.2f" % (que, lista, b.Label, real)


# --- Reglas ---------------------------------------------------------------------------------------


@cfg
@given(pts=esqueletos(), datos=st.data(), esquina=st.sampled_from(["tope", "inglete"]))
def marco(pts, datos, esquina):
    tipo, medida = datos.draw(perfiles(_lado_min(pts)))
    traza("  marco %d lados, %s %s, %s" % (len(pts), tipo, medida, esquina))
    doc, _sk, cuerpos = armar(pts, tipo, medida, esquina)
    try:
        chequear(doc, cuerpos, "%s %s a %s" % (tipo, medida, esquina))
    finally:
        FreeCAD.closeDocument(doc.Name)


def _cdm(forma):
    """Centro de masa (un compuesto no tiene uno propio: promedio por volumen de sus sólidos)."""
    vol = sum(s.Volume for s in forma.Solids) or 1.0
    c = V()
    for s in forma.Solids:
        c = c + s.CenterOfMass * (s.Volume / vol)
    return c


def _sigue(esquina):
    @cfg
    @given(pts=esqueletos(), datos=st.data(), f=st.floats(0.8, 1.25), cual=st.integers(0, 3))
    def regla(pts, datos, f, cual):
        tipo, medida = datos.draw(perfiles(_lado_min(pts) * 0.8))
        doc, sk, cuerpos = armar(pts, tipo, medida, esquina)
        try:
            i = cual % len(pts)
            # alejar o acercar un vértice desde el centro (el marco sigue convexo)
            c = sum(pts, V()) * (1.0 / len(pts))
            nuevo = c + (pts[i] - c) * f
            nuevo = V(round(nuevo.x, 2), round(nuevo.y, 2), 0)
            mover_vertice(doc, sk, i, nuevo)
            que = "%s %s a %s, después de mover el vértice %d" % (tipo, medida, esquina, i)
            chequear(doc, cuerpos, que)
            # el control fuerte: editar el esqueleto tiene que dar lo MISMO que armar el marco de
            # cero con el esqueleto nuevo (cada caño, mismo volumen y mismo centro de masa)
            pts2 = list(pts)
            pts2[i] = nuevo
            doc2, _sk2, cuerpos2 = armar(pts2, tipo, medida, esquina)
            try:
                for a, b in zip(cuerpos, cuerpos2):
                    va, vb = a.Shape.Volume, b.Shape.Volume
                    ca, cb = _cdm(a.Shape), _cdm(b.Shape)
                    assert cerca(va, vb, rel=1e-5, absoluto=0.5) and (ca - cb).Length < 0.01, \
                        "%s: %s no quedó como armado de cero (volumen %.1f vs %.1f, centro corrido %.2f mm)" % (
                            que, a.Label, va, vb, (ca - cb).Length)
            finally:
                FreeCAD.closeDocument(doc2.Name)
        finally:
            FreeCAD.closeDocument(doc.Name)
    return regla


@cfg
@given(pts=esqueletos(), datos=st.data(), esquina=st.sampled_from(["tope", "inglete"]))
def guardar(pts, datos, esquina):
    tipo, medida = datos.draw(perfiles(_lado_min(pts)))
    doc, _sk, cuerpos = armar(pts, tipo, medida, esquina)
    vol = {b.Name: b.Shape.Volume for b in cuerpos}
    ruta = os.path.join(carpeta_temporal(), "soldada.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    doc = FreeCAD.openDocument(ruta)
    try:
        doc.recompute()
        comprobado()
        for n, v in vol.items():
            o = doc.getObject(n)
            assert o is not None and o.Shape.isValid() and cerca(o.Shape.Volume, v, rel=1e-6, absoluto=0.5), \
                "%s cambió al reabrir (%s)" % (n, esquina)
    finally:
        FreeCAD.closeDocument(doc.Name)


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    reglas = [("marco", marco, ""), ("guardar y abrir", guardar, ""),
              ("sigue al esqueleto (tope)", _sigue("tope"), "#2"),
              ("sigue al esqueleto (inglete)", _sigue("inglete"), "#2")]
    for nombre, fn, conocido in reglas:
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn, conocido)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
