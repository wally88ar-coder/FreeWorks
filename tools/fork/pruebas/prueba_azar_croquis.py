# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Herramientas de entidades del croquis con figuras al azar (plan de calidad, paso 8.2, grupo 5),
sin ventana, por sus funciones públicas (el panel solo junta los datos y las llama). Figura al
azar: un polígono cerrado (3 a 6 lados, unido con coincidencias) y un círculo, más una línea
constructiva como eje. Entidades elegidas al azar:
- Mover +d y después −d: todo vuelve a donde estaba (con y sin conservar relaciones);
- Girar a° y después −a° alrededor de un punto: vuelve; y un giro deja cada punta donde dice la
  cuenta (error conocido #41: con el centro fuera del origen gira mal);
- Escalar ×f y después ×1/f desde un punto: vuelve;
- Simetría sin copiar dos veces por el mismo eje: vuelve;
- Copiar con d: aparece una copia de cada entidad, corrida exactamente d;
- Matriz lineal n × m: aparecen las copias que corresponden, cada una corrida su paso;
- después de cada una: ninguna relación redundante, en conflicto ni mal armada.
Casos por regla: FW_CASOS_AZAR (6 por omisión)."""
TIPO = "azar"

import math  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402

from azar_comun import Fallas, comprobado, hypothesis_listo  # noqa: E402

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector


@st.composite
def figuras(draw):
    """Puntos de un polígono simple (radios al azar alrededor de un centro, ángulos ordenados)."""
    n = draw(st.integers(3, 6))
    angs = sorted(draw(st.lists(st.floats(0, 2 * math.pi), min_size=n, max_size=n, unique=True)))
    if min(b - a for a, b in zip(angs, angs[1:] + [angs[0] + 2 * math.pi])) < 0.2:
        angs = [2 * math.pi * i / n for i in range(n)]
    pts = []
    for a in angs:
        r = draw(st.floats(10, 60))
        pts.append(V(round(r * math.cos(a), 3), round(r * math.sin(a), 3), 0))
    circ = (V(draw(st.floats(-80, 80)), draw(st.floats(-80, 80)), 0), draw(st.floats(2, 15)))
    return pts, circ


def croquis(pts, circ):
    import Part
    import Sketcher
    doc = FreeCAD.newDocument("Croquis")
    sk = doc.addObject("Sketcher::SketchObject", "Croquis")
    n = len(pts)
    for i in range(n):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % n]))
    for i in range(n):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % n, 1))
    sk.addGeometry(Part.Circle(circ[0], V(0, 0, 1), circ[1]))
    eje = sk.addGeometry(Part.LineSegment(V(100, -100, 0), V(100, 100, 0)), True)  # constructiva
    doc.recompute()
    return doc, sk, n + 1, eje  # geometrías elegibles: 0..n (lados + círculo)


def firma(sk, ids=None):
    """Dónde está cada geometría (puntas, centro, radio), redondeado a 1e-5."""
    out = []
    for i, g in enumerate(sk.Geometry):
        if ids is not None and i not in ids:
            continue
        pts = [getattr(g, a) for a in ("StartPoint", "EndPoint", "Center") if hasattr(g, a)]
        out.append((type(g).__name__,) + tuple(round(c, 5) for p in pts for c in (p.x, p.y))
                   + (round(getattr(g, "Radius", 0.0), 5),))
    return out


def sano(sk, que):
    sk.solve()
    malas = (list(sk.RedundantConstraints), list(sk.ConflictingConstraints), list(sk.MalformedConstraints))
    assert not any(malas), "%s: relaciones redundantes %s, en conflicto %s, mal armadas %s" % ((que,) + malas)


def mismo(a, b, que):
    """Mismas entidades en el mismo lugar (a 1 µm: girar y volver pasa por el resolvedor del
    croquis, que deja diferencias de décimas de µm); el orden puede cambiar."""
    assert len(a) == len(b), "%s: había %d geometrías y quedaron %d" % (que, len(a), len(b))
    libres = list(b)
    for x in a:
        par = [y for y in libres if y[0] == x[0] and all(abs(p - q) < 1e-3 for p, q in zip(x[1:], y[1:]))]
        assert par, "%s: una entidad no volvió a su lugar: %s" % (que, x)
        libres.remove(par[0])


elegidas = st.data()


def _elegir(data, total):
    return sorted(data.draw(st.lists(st.integers(0, total - 1), min_size=1, max_size=total, unique=True)))


@cfg
@given(fig=figuras(), data=elegidas, dx=st.floats(-50, 50), dy=st.floats(-50, 50), conservar=st.booleans())
def mover_ida_vuelta(fig, data, dx, dy, conservar):
    from swui.fork import sketch_transform as stt
    doc, sk, total, _eje = croquis(*fig)
    try:
        ids = _elegir(data, total)
        antes = firma(sk)
        stt.move_entities(sk, ids, V(dx, dy, 0), keep_relations=conservar)
        sano(sk, "mover")
        stt.move_entities(sk, ids, V(-dx, -dy, 0), keep_relations=conservar)
        sk.solve()
        comprobado()
        sano(sk, "mover y volver")
        if conservar:  # sin conservar, las unidas a lo no elegido se separan (como SW): no vuelve exacto
            mismo(antes, firma(sk), "mover %s y volver" % ids)
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(fig=figuras(), data=elegidas, ang=st.floats(1, 359), cx=st.floats(-50, 50), cy=st.floats(-50, 50))
def girar_ida_vuelta(fig, data, ang, cx, cy):
    from swui.fork import sketch_transform as stt
    doc, sk, total, _eje = croquis(*fig)
    try:
        antes = firma(sk)
        ids = list(range(total))  # todo: así ninguna unión con lo no elegido lo frena
        stt.rotate_entities(sk, ids, V(cx, cy, 0), ang, keep_relations=True)
        sano(sk, "girar")
        stt.rotate_entities(sk, ids, V(cx, cy, 0), -ang, keep_relations=True)
        sk.solve()
        comprobado()
        sano(sk, "girar y volver")
        mismo(antes, firma(sk), "girar %.2f° y volver" % ang)
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(fig=figuras(), f=st.floats(0.3, 3.0), cx=st.floats(-50, 50), cy=st.floats(-50, 50))
def escalar_ida_vuelta(fig, f, cx, cy):
    from swui.fork import sketch_transform as stt
    doc, sk, total, _eje = croquis(*fig)
    try:
        antes = firma(sk)
        ids = list(range(total))
        stt.scale_entities(sk, ids, V(cx, cy, 0), f)
        sano(sk, "escalar")
        stt.scale_entities(sk, ids, V(cx, cy, 0), 1.0 / f)
        sk.solve()
        comprobado()
        sano(sk, "escalar y volver")
        mismo(antes, firma(sk), "escalar ×%.3f y volver" % f)
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(fig=figuras())
def simetria_dos_veces(fig):
    from swui.fork import sketch_entities as se
    doc, sk, total, eje = croquis(*fig)
    try:
        antes = firma(sk)
        ids = list(range(total))
        se.mirror_entities(sk, ids, eje, copy=False)
        sano(sk, "simetría")
        # sin copiar, la simetría reemplaza las entidades: los números cambian (el eje también)
        eje = [i for i in range(sk.GeometryCount) if sk.getConstruction(i)][0]
        ids = [i for i in range(sk.GeometryCount) if not sk.getConstruction(i)]
        se.mirror_entities(sk, ids, eje, copy=False)
        sk.solve()
        comprobado()
        sano(sk, "simetría dos veces")
        mismo(antes, firma(sk), "simetría dos veces")
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(fig=figuras(), data=elegidas, dx=st.floats(-80, 80), dy=st.floats(-80, 80))
def copiar(fig, data, dx, dy):
    from swui.fork import sketch_transform as stt
    doc, sk, total, _eje = croquis(*fig)
    try:
        ids = _elegir(data, total)
        originales = firma(sk, set(ids))
        n0 = sk.GeometryCount
        nuevas = stt.copy_entities(sk, ids, V(dx, dy, 0))
        sk.solve()
        comprobado()
        sano(sk, "copiar")
        assert sk.GeometryCount == n0 + len(ids), "copió %d, se eligieron %d" % (sk.GeometryCount - n0, len(ids))
        copias = firma(sk, set(nuevas) if nuevas else set(range(n0, sk.GeometryCount)))
        for o, c in zip(originales, copias):
            pares = list(zip(o[1:-1], c[1:-1]))
            corr = [(q - p) for p, q in pares]
            assert all(abs(corr[k] - (dx if k % 2 == 0 else dy)) < 1e-4 for k in range(len(corr))), \
                "una copia no quedó corrida (%.3f, %.3f): %s -> %s" % (dx, dy, o, c)
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(fig=figuras(), data=elegidas, n=st.integers(2, 4), m=st.integers(1, 3), paso1=st.floats(150, 300),
       paso2=st.floats(150, 300), ang=st.floats(0, 360))
def matriz(fig, data, n, m, paso1, paso2, ang):
    from swui.fork import sketch_transform as stt
    doc, sk, total, _eje = croquis(*fig)
    try:
        ids = _elegir(data, total)
        n0 = sk.GeometryCount
        stt.linear_pattern(sk, ids, count1=n, spacing1=paso1, angle1=ang, count2=m, spacing2=paso2, angle2=ang + 90)
        sk.solve()
        comprobado()
        sano(sk, "matriz")
        # las constructivas que agrega la matriz de FreeCAD (dirección) no cuentan
        normales = sum(1 for k in range(sk.GeometryCount) if not sk.getConstruction(k))
        esperado = (n0 - 1) + len(ids) * (n * m - 1)
        assert normales == esperado, "matriz %d×%d de %d entidades: %d entidades, se esperaban %d" % (
            n, m, len(ids), normales, esperado)
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(fig=figuras(), ang=st.floats(1, 359), cx=st.floats(-50, 50), cy=st.floats(-50, 50))
def girar_cuenta(fig, ang, cx, cy):
    """Un giro: cada punta queda donde dice la cuenta (rotación alrededor del centro elegido)."""
    from swui.fork import sketch_transform as stt
    doc, sk, total, _eje = croquis(*fig)
    try:
        a = math.radians(ang)
        c = V(cx, cy, 0)
        antes = [sk.Geometry[i].StartPoint for i in range(total - 1)]
        stt.rotate_entities(sk, list(range(total)), c, ang, keep_relations=True)
        sk.solve()
        comprobado()
        for i, p in enumerate(antes):
            d = p - c
            quiero = c + V(d.x * math.cos(a) - d.y * math.sin(a), d.x * math.sin(a) + d.y * math.cos(a), 0)
            q = sk.Geometry[i].StartPoint
            assert (q - quiero).Length < 1e-3, \
                "girar %.2f° alrededor de (%.2f, %.2f): la punta quedó en (%.3f, %.3f) y la cuenta da (%.3f, %.3f)" % (
                    ang, cx, cy, q.x, q.y, quiero.x, quiero.y)
    finally:
        FreeCAD.closeDocument(doc.Name)


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn, conocido in (("mover y volver", mover_ida_vuelta, ""), ("girar y volver", girar_ida_vuelta, "#41"),
                                 ("girar: donde dice la cuenta", girar_cuenta, "#41"),
                                 ("escalar y volver", escalar_ida_vuelta, ""),
                                 ("simetría dos veces", simetria_dos_veces, ""), ("copiar", copiar, ""),
                                 ("matriz", matriz, "")):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn, conocido)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
