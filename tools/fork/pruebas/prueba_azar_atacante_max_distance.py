# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Agente atacante, distancia máxima (Medir) (escrito sin mirar el código, desde lo que promete):
- dos cajas giradas y corridas al azar: el máximo es el de los vértices (todos contra todos);
- dos esferas: |c1 - c2| + r1 + r2; esfera y punto: |c - p| + r;
- punto contra cilindro: el mayor de sus dos bordes (cuenta propia sqrt(a² + (ρ + r)²));
- un punto sobre el eje de un círculo (el centro de un agujero, corrido del origen) está a
  sqrt(r² + h²) de todo el borde: max_point_circle y max_distance tienen que dar eso;
- dos cilindros cualesquiera: igual a los bordes contra bordes (cada punto de uno contra el círculo
  del otro, con la fórmula), a la milésima del tamaño;
- da lo mismo pedir (a, b) que (b, a), y corrido todo junto da lo mismo;
- los dos puntos que devuelve están sobre las formas y a esa distancia.
"""
TIPO = "azar"

import math  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

V = FreeCAD.Vector


def _rot(st):
    return st.tuples(st.floats(-1, 1), st.floats(-1, 1), st.floats(-1, 1), st.floats(0, 360)).filter(
        lambda t: abs(t[0]) + abs(t[1]) + abs(t[2]) > 0.05).map(
        lambda t: FreeCAD.Rotation(V(t[0], t[1], t[2]), t[3]))


def _pos(st, m=200):
    return st.tuples(st.floats(-m, m), st.floats(-m, m), st.floats(-m, m)).map(lambda t: V(*t))


def _dir(st):
    return st.tuples(st.floats(-1, 1), st.floats(-1, 1), st.floats(-1, 1)).filter(
        lambda t: math.sqrt(t[0] ** 2 + t[1] ** 2 + t[2] ** 2) > 0.1).map(lambda t: V(*t).normalize())


def _pv(p):
    return V(p[0], p[1], p[2]) if not isinstance(p, FreeCAD.Vector) else p


def _sobre(shape, p, tam):
    d = shape.distToShape(Part.Vertex(_pv(p)))[0]
    return d <= 1e-5 * max(tam, 1.0)


def _revisar(md, a, b, esperado, tam, que, tol=1e-6):
    d, pa, pb = md.max_distance(a, b)
    assert cerca(d, esperado, rel=tol, absoluto=tol * tam), "%s: dio %r, esperado %r" % (que, d, esperado)
    assert _sobre(a, pa, tam) and _sobre(b, pb, tam), "%s: los puntos %r %r no están sobre las formas" % (que, pa, pb)
    assert cerca((_pv(pa) - _pv(pb)).Length, d, rel=1e-6, absoluto=1e-6 * tam), "%s: los puntos no están a %r" % (que, d)
    d2 = md.max_distance(b, a)[0]
    assert cerca(d2, d, rel=1e-6, absoluto=1e-6 * tam), "%s: (a, b) da %r y (b, a) da %r" % (que, d, d2)


def _circulo(c, n, r, k):
    """k puntos de un círculo (centro c, normal n, radio r)."""
    u = n.cross(V(1, 0, 0))
    if u.Length < 1e-6:
        u = n.cross(V(0, 1, 0))
    u.normalize()
    w = n.cross(u)
    return [c + u * (r * math.cos(2 * math.pi * i / k)) + w * (r * math.sin(2 * math.pi * i / k)) for i in range(k)]


def _max_pc(p, c, n, r):
    """Distancia máxima de un punto a un círculo, cuenta propia: sqrt(a² + (ρ + r)²)."""
    v = p - c
    a = v.dot(n)
    rho = (v - n * a).Length
    return math.sqrt(a * a + (rho + r) ** 2)


def prueba():
    given, cfg, st = hypothesis_listo()
    from swui.fork import max_distance as md
    f = Fallas()
    med = st.floats(0.5, 100)

    @cfg
    @given(d1=st.tuples(med, med, med), d2=st.tuples(med, med, med), r1=_rot(st), r2=_rot(st),
           p1=_pos(st), p2=_pos(st), forma=st.sampled_from(["solido", "caras", "aristas"]))
    def dos_cajas(d1, d2, r1, r2, p1, p2, forma):
        a, b = Part.makeBox(*d1), Part.makeBox(*d2)
        a.Placement = FreeCAD.Placement(p1, r1)
        b.Placement = FreeCAD.Placement(p2, r2)
        if forma == "caras":
            a, b = a.Faces[0], b.Faces[3]
        elif forma == "aristas":
            a, b = a.Edges[2], b.Edges[7]
        esperado = max((va.Point - vb.Point).Length for va in a.Vertexes for vb in b.Vertexes)
        tam = max(max(d1), max(d2)) + 400
        _revisar(md, a, b, esperado, tam, "cajas (%s)" % forma)
        # corrido todo junto: lo mismo
        mov = V(37.5, -12.25, 101.0)
        a2, b2 = a.copy(), b.copy()
        a2.translate(mov)
        b2.translate(mov)
        assert cerca(md.max_distance(a2, b2)[0], esperado, rel=1e-6, absoluto=1e-6 * tam), "corrido cambia"
        comprobado()
    f.correr("dos_cajas", dos_cajas)

    @cfg
    @given(c1=_pos(st), c2=_pos(st), ra=med, rb=med, que=st.sampled_from(["solido", "cara", "punto"]))
    def esferas(c1, c2, ra, rb, que):
        a = Part.makeSphere(ra, c1)
        if que == "punto":
            b = Part.Vertex(c2)
            esperado = (c1 - c2).Length + ra
        else:
            b = Part.makeSphere(rb, c2)
            if que == "cara":
                a, b = a.Faces[0], b.Faces[0]
            esperado = (c1 - c2).Length + ra + rb
        tam = ra + rb + 400
        _revisar(md, a, b, esperado, tam, "esferas (%s) c1=%r r=%r c2=%r r=%r" % (que, c1, ra, c2, rb))
        comprobado()
    f.correr("esferas", esferas, "#52")  # error registrado: Issue #52

    @cfg
    @given(c=_pos(st), n=_dir(st), r=med, h=med, p=_pos(st, 300))
    def punto_cilindro(c, n, r, h, p):
        cil = Part.makeCylinder(r, h, c, n)
        esperado = max(_max_pc(p, q, n, r) for q in (c, c + n * h))
        tam = r + h + 600
        _revisar(md, cil, Part.Vertex(p), esperado, tam, "punto %r contra cilindro c=%r n=%r r=%r h=%r" % (p, c, n, r, h))
        comprobado()
    f.correr("punto_cilindro", punto_cilindro)

    @cfg
    @given(c=_pos(st), n=_dir(st), r=med, h=st.floats(-100, 100))
    def punto_en_el_eje(c, n, r, h):
        # medir desde el centro de un agujero (o un punto sobre su eje) hasta su borde: todos los
        # puntos del borde están a sqrt(r² + h²)
        p = c + n * h
        esperado = math.sqrt(r * r + h * h)
        d, q = md.max_point_circle((p.x, p.y, p.z), (c.x, c.y, c.z), (n.x, n.y, n.z), r)
        q = V(*q)
        assert cerca(d, esperado, rel=1e-7, absoluto=1e-7), ("max_point_circle desde el eje (p=%r, c=%r, n=%r, "
                                                            "r=%r) dio %r, y es %r" % (p, c, n, r, d, esperado))
        assert abs((q - c).dot(n)) < 1e-6 * (1 + r), "el punto %r no está en el plano del círculo" % q
        comprobado()
    f.correr("punto_en_el_eje_formula", punto_en_el_eje)

    @cfg
    @given(c=_pos(st), n=_dir(st), r=med, h=st.floats(-100, 100))
    def punto_en_el_eje_medir(c, n, r, h):
        p = c + n * h
        borde = Part.makeCircle(r, c, n)
        _revisar(md, Part.Vertex(p), borde, math.sqrt(r * r + h * h), r + abs(h) + 400, "punto del eje contra el borde")
        comprobado()
    f.correr("punto_en_el_eje_medir", punto_en_el_eje_medir)

    @cfg
    @given(c1=_pos(st, 100), n1=_dir(st), r1=med, h1=med, c2=_pos(st, 100), n2=_dir(st), r2=med, h2=med)
    def dos_cilindros(c1, n1, r1, h1, c2, n2, r2, h2):
        a = Part.makeCylinder(r1, h1, c1, n1)
        b = Part.makeCylinder(r2, h2, c2, n2)
        # cuerpos convexos: el máximo está en sus bordes; cada punto de un borde contra el otro círculo
        # con la fórmula, y ese lado muy denso (1440 puntos) + afinado simple alrededor del mejor
        mejor = 0.0
        for ca in (c1, c1 + n1 * h1):
            for cb in (c2, c2 + n2 * h2):
                pts = _circulo(ca, n1, r1, 1440)
                for q in pts:
                    d = md.max_point_circle((q.x, q.y, q.z), (cb.x, cb.y, cb.z), (n2.x, n2.y, n2.z), r2)[0]
                    mejor = max(mejor, d)
        tam = r1 + h1 + r2 + h2 + 400
        d = md.max_distance(a, b)[0]
        # muestreo: el verdadero está entre `mejor` y mejor + r1·(1 - cos(π/1440))·2 (casi nada)
        holgura = 2 * r1 * (1 - math.cos(math.pi / 1440)) + 1e-6 * tam
        assert d >= mejor - 1e-6 * tam, ("cilindros: dio %r y hay dos puntos de los bordes a %r (se quedó en un "
                                         "máximo local)" % (d, mejor))
        assert d <= mejor + holgura + 1e-3, "cilindros: dio %r, más que lo posible %r" % (d, mejor + holgura)
        comprobado()
    f.correr("dos_cilindros", dos_cilindros, "#52")  # error registrado: Issue #52

    @cfg
    @given(c1=_pos(st), c2=_pos(st), r1=med, r2=med, n=_dir(st))
    def dos_circulos_mismo_plano(c1, c2, r1, r2, n):
        # c2 llevado al plano de c1
        c2p = c2 - n * ((c2 - c1).dot(n))
        a = Part.makeCircle(r1, c1, n)
        b = Part.makeCircle(r2, c2p, n)
        esperado = (c1 - c2p).Length + r1 + r2
        r = md.max_coplanar_circles((c1.x, c1.y, c1.z), r1, (c2p.x, c2p.y, c2p.z), r2, (n.x, n.y, n.z))
        assert cerca(r[0], esperado, rel=1e-9, absoluto=1e-9), "fórmula %r, esperado %r" % (r[0], esperado)
        _revisar(md, a, b, esperado, r1 + r2 + 800, "círculos en el mismo plano")
        comprobado()
    f.correr("dos_circulos_mismo_plano", dos_circulos_mismo_plano)

    f.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
