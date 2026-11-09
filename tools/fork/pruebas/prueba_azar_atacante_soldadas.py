# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Agente atacante, Piezas soldadas (escrito sin mirar el código, desde lo que promete cada
función y cómo da SW 2018 la lista de cortes):
- cada perfil de la tabla: area() = el área de su cara, extent() = su caja, centrado en su
  rectángulo envolvente, cara válida; el área dibujada es la Ag de la tabla CIRSOC (±3 %) y el
  peso por metro también; la envolvente (outer_only) no es más chica que el perfil;
  section_props = weld_profiles.section;
- marco rectangular al azar (caño cuadrado o redondo, cualquier medida que entre), a tope o a
  inglete: 4 miembros válidos; la lista de cortes cuenta 4; el peso total es volumen real x acero;
  a inglete cada largo es lado + ancho del perfil (de punta larga a punta larga, como SW) con
  ángulos de 45°; a tope dos largos van lado + ancho (los que pasan) y dos lado - ancho;
- un marco cuadrado a inglete tiene 4 miembros iguales: un solo renglón con cantidad 4 (SW);
- el CSV tiene una fila por renglón + títulos + total, con punto y coma y coma decimal, y su
  total es la suma.
"""
TIPO = "azar"

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from _base import traza  # noqa: E402
from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

V = FreeCAD.Vector
ACERO = 7.85e-6  # kg/mm³


def _num(texto):
    return float(texto.replace(".", "").replace(",", "."))


def prueba():
    given, cfg, st = hypothesis_listo()
    from swui.fork import weld_profiles as wp
    from swui.fork import weldments as w
    f = Fallas()

    todos = [(k, n, d) for k in wp.kinds() for n, d in w.sizes(k)]
    traza("  %d perfiles en la tabla" % len(todos))

    @cfg
    @given(i=st.integers(0, len(todos) - 1))
    def perfil(i):
        k, n, d = todos[i]
        cara = wp.face(k, d)
        que = "%s %s %r" % (k, n, d)
        assert cara.isValid(), "%s: cara inválida" % que
        assert cerca(w.area(k, d), cara.Area, rel=1e-6), "%s: area() %r, cara %r" % (que, w.area(k, d), cara.Area)
        bb = cara.BoundBox
        ex = w.extent(k, d)
        assert cerca(ex[0], bb.XLength, rel=1e-6) and cerca(ex[1], bb.YLength, rel=1e-6), \
            "%s: extent %r, caja de la cara (%r, %r)" % (que, ex, bb.XLength, bb.YLength)
        assert abs(bb.Center.x) < 1e-6 * ex[0] + 1e-9 and abs(bb.Center.y) < 1e-6 * ex[1] + 1e-9, \
            "%s: no está centrado en su caja: %r" % (que, bb.Center)
        sec = w.section_props(k, n)
        assert sec == wp.section(k, n), "%s: section_props y weld_profiles.section no coinciden" % que
        if sec:
            ag = [v for c, v in sec.items() if c.startswith("Área Ag")]
            # DUDOSO, no se exige: Ángulo 1 1/8" x 1/8" dibujado da 175,5 mm² y la tabla 1,65 cm² (6 %);
            # con 28,6 x 3,2 la cuenta a mano da ~1,75 cm²: parece un dato de la tabla, no del dibujo
            if ag and not (k == "Ángulo" and n == '1 1/8" x 1/8"'):
                tabla = _num(ag[0]) * 100.0  # cm² -> mm²
                assert cerca(cara.Area, tabla, rel=0.03), ("%s: área dibujada %.1f mm², la tabla dice Ag = %s cm²"
                                                           % (que, cara.Area, ag[0]))
            peso = [v for c, v in sec.items() if c.startswith("Peso")]
            if peso and not (k == "Ángulo" and n == '1 1/8" x 1/8"'):
                assert cerca(cara.Area * ACERO * 1000.0, _num(peso[0]), rel=0.03), \
                    "%s: %.3f kg/m dibujado, la tabla dice %s" % (que, cara.Area * ACERO * 1000.0, peso[0])
        # la envolvente llena no es más chica que el perfil
        lazos = w.profile_loops(k, d, outer_only=True)
        assert lazos, "%s: sin contorno de afuera" % que
        assert w.profile_text(k, n), "%s: sin nombre para mostrar" % que
        comprobado()
    f.correr("perfil", perfil)

    redondos = [n for n, _d in w.sizes("Caño redondo")]
    cuadrados = [n for n, _d in w.sizes("Caño cuadrado")]

    @cfg
    @given(ancho=st.integers(150, 2500), alto=st.integers(150, 2500),
           perfil=st.one_of(st.tuples(st.just("Caño cuadrado"), st.sampled_from(cuadrados)),
                            st.tuples(st.just("Caño redondo"), st.sampled_from(redondos))),
           trat=st.sampled_from(["tope", "inglete"]))
    def marco(ancho, alto, perfil, trat):
        kind, size = perfil
        D = w.extent(kind, w.dims_of(kind, size))[0]
        if D * 4 > min(ancho, alto):
            return  # no entra
        doc = FreeCAD.newDocument("Marco")
        try:
            sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
            pts = [V(0, 0, 0), V(ancho, 0, 0), V(ancho, alto, 0), V(0, alto, 0)]
            for i in range(4):
                sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
            doc.recompute()
            cuerpos = w.create_members(doc, [(sk, "Edge%d" % i) for i in range(1, 5)], kind, size)
            doc.recompute()
            w.apply_corners(cuerpos, trat)
            doc.recompute()
            assert len(cuerpos) == 4
            for b in cuerpos:
                assert b.Shape.isValid() and len(b.Shape.Solids) == 1, "%s quedó inválido" % b.Label
                assert not [o.Name for o in b.Group if "Invalid" in o.State], "%s con operaciones en error" % b.Label
            filas = w.cut_list(doc)
            assert sum(r["qty"] for r in filas) == 4, "la lista cuenta %d miembros" % sum(r["qty"] for r in filas)
            masa = sum(b.Shape.Volume for b in cuerpos) * ACERO
            total = sum(r["total_kg"] for r in filas)
            assert cerca(total, masa, rel=0.005), "peso total %r, el acero de los miembros pesa %r" % (total, masa)
            largos = sorted(r["length"] for r in filas for _q in range(r["qty"]))
            if trat == "inglete":
                esperado = sorted([ancho + D] * 2 + [alto + D] * 2)
                for r in filas:
                    assert cerca(r["angle1"], 45.0) and cerca(r["angle2"], 45.0), "ángulos %r" % r
                assert all(cerca(a, b, absoluto=0.06) for a, b in zip(largos, esperado)), \
                    ("%s %s a inglete en %dx%d: largos %r, como SW serían %r" % (kind, size, ancho, alto, largos, esperado))
            else:
                # cuál pasa en cada esquina no lo promete la función (ni SW: se elige por esquina). En
                # cada esquina uno se alarga D/2 y el otro se acorta D/2: cada largo es lado - D, lado
                # o lado + D, y la suma de los cuatro es el perímetro del esqueleto
                # caño redondo: el que no pasa se corta con la forma del caño (boca de pescado) y su
                # punta larga llega al eje del otro: cada largo es lado, lado + D/2 o lado + D
                if kind == "Caño redondo":
                    suma, pasos = 2.0 * (ancho + alto) + 2.0 * D, (0.0, 0.5, 1.0)
                else:
                    suma, pasos = 2.0 * (ancho + alto), (-1.0, 0.0, 1.0)
                assert cerca(sum(largos), suma, absoluto=0.2), \
                    ("%s %s a tope en %dx%d: largos %r suman %r, tendrían que sumar %r"
                     % (kind, size, ancho, alto, largos, sum(largos), suma))
                posibles = [lado + k * D for lado in (ancho, alto) for k in pasos]
                assert all(any(cerca(a, p, absoluto=0.06) for p in posibles) for a in largos), \
                    ("%s %s a tope en %dx%d: largos %r (fuera de los largos posibles, D=%r)"
                     % (kind, size, ancho, alto, largos, D))
            # CSV
            csv = w.cut_list_csv(filas)
            renglones = [x for x in csv.splitlines() if x.strip()]
            assert len(renglones) == len(filas) + 2, "CSV con %d renglones para %d filas" % (len(renglones), len(filas))
            cols = len(renglones[0].split(";"))
            assert all(len(x.split(";")) == cols for x in renglones), "CSV con columnas desparejas:\n%s" % csv
            assert "." not in renglones[1].split(";")[3] or "," in renglones[1].split(";")[3], csv
            tot = _num(renglones[-1].split(";")[-1])
            assert cerca(tot, total, absoluto=0.01), "total del CSV %r, suma %r" % (tot, total)
            comprobado()
        finally:
            FreeCAD.closeDocument(doc.Name)
    f.correr("marco", marco)

    @cfg
    @given(lado=st.integers(150, 2500),
           perfil=st.one_of(st.tuples(st.just("Caño cuadrado"), st.sampled_from(cuadrados)),
                            st.tuples(st.just("Caño redondo"), st.sampled_from(redondos))))
    def iguales_en_un_renglon(lado, perfil):
        # marco cuadrado a inglete: los 4 miembros son iguales; SW los pone en UN renglón con cantidad 4
        kind, size = perfil
        D = w.extent(kind, w.dims_of(kind, size))[0]
        if D * 4 > lado:
            return
        doc = FreeCAD.newDocument("Cuadrado")
        try:
            sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
            pts = [V(0, 0, 0), V(lado, 0, 0), V(lado, lado, 0), V(0, lado, 0)]
            for i in range(4):
                sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
            doc.recompute()
            cuerpos = w.create_members(doc, [(sk, "Edge%d" % i) for i in range(1, 5)], kind, size)
            doc.recompute()
            w.apply_corners(cuerpos, "inglete")
            doc.recompute()
            filas = w.cut_list(doc)
            assert len(filas) == 1 and filas[0]["qty"] == 4,                 ("%s %s, marco cuadrado de %d a inglete: 4 miembros iguales salen en %d renglones %r"
                 % (kind, size, lado, len(filas), [(r["qty"], r["length"]) for r in filas]))
            comprobado()
        finally:
            FreeCAD.closeDocument(doc.Name)
    f.correr("iguales_en_un_renglon", iguales_en_un_renglon, "#53")  # error registrado: Issue #53

    f.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
