# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Agente atacante, Chapa sin interfaz (escrito sin mirar el código, desde lo que promete cada
función y lo que hace SW 2018 con los desarrollos):
- el nombre del DXF tiene pieza + espesor + material, termina en .dxf y es un nombre de archivo
  válido en Windows para cualquier texto; dos espesores distintos dan nombres distintos; fmt_mm
  vuelve a leerse como el espesor (a 3 decimales) y nunca da "-0";
- next_label da un nombre que no está usado;
- merge_lines: un rectángulo con los lados cortados en pedazos (en cualquier orden, sentido y giro)
  queda en 4 rectas con el mismo perímetro; donde llega otra entidad (recta o arco de la misma
  capa) no se une; rectas de capas distintas no se unen;
- shift corre la caja de extent exactamente (dx, dy);
- dxf_text: el archivo se lee de vuelta con las mismas entidades, en su capa, con las coordenadas
  exactas (al 0,0001 mm: un DXF de taller con medidas de hasta 3 m), PLEGADO con línea de trazos;
- detect_thickness / detect_radius sobre una chapa en L hecha a mano (sin historia, como un STEP)
  dan el espesor y el radio interior con que se armó; con dos pliegues de radios distintos
  (empate), el mayor.
"""
TIPO = "azar"

import math  # noqa: E402
import re  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

V = FreeCAD.Vector
PROHIBIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _leer_dxf(texto):
    """Lector mínimo de DXF R12: [(tipo, {código: [valores]})] de la sección ENTITIES, y las capas."""
    lineas = texto.splitlines()
    assert len(lineas) % 2 == 0, "el DXF no tiene pares código/valor"
    pares = [(int(lineas[i].strip()), lineas[i + 1].strip()) for i in range(0, len(lineas), 2)]
    ents, capas, actual, seccion = [], {}, None, None
    for i, (cod, val) in enumerate(pares):
        if cod == 2 and i > 0 and pares[i - 1] == (0, "SECTION"):
            seccion = val
            continue
        if cod == 0:
            if actual is not None:
                if seccion == "ENTITIES":
                    ents.append(actual)
                elif actual[0] == "LAYER":
                    capas[actual[1].get(2, [""])[0]] = actual[1]
            actual = (val, {}) if val in ("LINE", "ARC", "CIRCLE", "LAYER", "POLYLINE", "LWPOLYLINE") else None
            continue
        if actual is not None:
            actual[1].setdefault(cod, []).append(val)
    return ents, capas


def _num(d, cod):
    return float(d[cod][0])


def _rect_partido(st):
    """Rectángulo con cada lado cortado en pedazos: (entidades, ancho, alto)."""
    def armar(t):
        w, h, cortes, giro, cx, cy, sentidos, orden = t
        esquinas = [(0, 0), (w, 0), (w, h), (0, h)]
        ents = []
        k = 0
        for lado in range(4):
            p, q = esquinas[lado], esquinas[(lado + 1) % 4]
            fr = [0.0]
            for c in sorted(cortes[lado]):  # cortes muy juntos = uno solo (sin dejar huecos)
                if c - fr[-1] >= 1e-3 and 1.0 - c >= 1e-3:
                    fr.append(c)
            fr.append(1.0)
            for a, b in zip(fr, fr[1:]):
                x1, y1 = p[0] + (q[0] - p[0]) * a, p[1] + (q[1] - p[1]) * a
                x2, y2 = p[0] + (q[0] - p[0]) * b, p[1] + (q[1] - p[1]) * b
                ents.append([x1, y1, x2, y2])
                k += 1
        c, s = math.cos(math.radians(giro)), math.sin(math.radians(giro))
        out = []
        for i, (x1, y1, x2, y2) in enumerate(ents):
            X1, Y1 = cx + c * x1 - s * y1, cy + s * x1 + c * y1
            X2, Y2 = cx + c * x2 - s * y2, cy + s * x2 + c * y2
            if sentidos[i % len(sentidos)]:
                X1, Y1, X2, Y2 = X2, Y2, X1, Y1
            out.append(("LINE", "CONTORNO", X1, Y1, X2, Y2))
        orden = [o % len(out) for o in orden]
        mezclado = []
        for o in orden:
            if out[o] not in mezclado:
                mezclado.append(out[o])
        mezclado += [e for e in out if e not in mezclado]
        return mezclado, w, h
    corte = st.lists(st.floats(0.05, 0.95), max_size=4)
    return st.tuples(st.floats(5, 3000), st.floats(5, 3000), st.tuples(corte, corte, corte, corte),
                     st.sampled_from([0.0, 90.0, 30.0, 45.0, 17.3]), st.floats(-1000, 1000), st.floats(-1000, 1000),
                     st.lists(st.booleans(), min_size=1, max_size=8),
                     st.lists(st.integers(0, 40), max_size=20)).map(armar)


def _largo(e):
    return math.hypot(e[4] - e[2], e[5] - e[3])


def _chapa_L(t, r, l1, l2, ancho):
    """Chapa en L sin historia: ala horizontal, pliegue de radio interior r, ala vertical."""
    a1 = Part.makeBox(l1, ancho, t, V(-l1, 0, 0))
    c = V(0, 0, r + t)
    ext = Part.makeCylinder(r + t, ancho, c, V(0, 1, 0))
    inte = Part.makeCylinder(r, ancho, c, V(0, 1, 0))
    cuarto = Part.makeBox(r + t, ancho, r + t, V(0, 0, 0))
    curva = ext.cut(inte).common(cuarto)
    a2 = Part.makeBox(t, ancho, l2, V(r, 0, r + t))
    s = a1.fuse([curva, a2]).removeSplitter()
    return s


def _chapa_Z(t, r, r2, l1, l2, l3, ancho):
    """La L de arriba con un segundo pliegue (radio interior r2) arriba del ala vertical, hacia +X."""
    s = _chapa_L(t, r, l1, l2, ancho)
    zt = r + t + l2
    c = V(r + t + r2, 0, zt)
    ext = Part.makeCylinder(r2 + t, ancho, c, V(0, 1, 0))
    inte = Part.makeCylinder(r2, ancho, c, V(0, 1, 0))
    cuarto = Part.makeBox(r2 + t, ancho, r2 + t, V(r, 0, zt))
    curva = ext.cut(inte).common(cuarto)
    a3 = Part.makeBox(l3, ancho, t, V(r + t + r2, 0, zt + r2))
    return s.fuse([curva, a3]).removeSplitter()


def prueba():
    given, cfg, st = hypothesis_listo()
    from swui.fork import sheet_metal as sm
    f = Fallas()

    espesor = st.integers(1, 20000).map(lambda n: n / 1000.0)
    # sin caracteres de control: un Label de FreeCAD no los trae en la práctica (y dxf_filename no
    # promete limpiarlos; con '' en el nombre el archivo no se puede crear: anotado como DUDOSO)
    texto = st.one_of(st.text(st.characters(blacklist_categories=("Cc", "Cs")), max_size=25), st.sampled_from(["Soporte", "Ménsula ñ", "CON", "a/b:c", " punto. ",
                                                             "SAE 1010", "AISI 304 \"2B\"", ""]))

    @cfg
    @given(pieza=texto, t=espesor, t2=espesor, material=st.one_of(st.none(), texto))
    def nombre_dxf(pieza, t, t2, material):
        n = sm.dxf_filename(pieza, t, material)
        assert n.lower().endswith(".dxf"), "%r no termina en .dxf" % n
        base = n[:-4]
        assert base and not PROHIBIDOS.search(n), "dxf_filename(%r, %r, %r) = %r no es válido en Windows" % (pieza, t, material, n)
        assert not base.endswith((" ", ".")), "%r termina en punto o espacio antes de .dxf" % n
        assert (sm.fmt_mm(t) + "mm") in n, "dxf_filename(%r, %r, %r) = %r no tiene el espesor %r" % (pieza, t, material, n, sm.fmt_mm(t))
        if material and sm.clean_name(material).strip():
            assert sm.clean_name(material).strip() in n, "%r no tiene el material %r" % (n, material)
        if sm.clean_name(pieza).strip():
            assert sm.clean_name(pieza).strip() in n, "%r no tiene la pieza %r" % (n, pieza)
        if abs(t - t2) >= 0.001:
            assert sm.dxf_filename(pieza, t2, material) != n, ("espesores %r y %r dan el mismo archivo %r: el "
                                                               "segundo pisa al primero" % (t, t2, n))
        fm = sm.fmt_mm(t)
        assert not fm.startswith("-0") or float(fm.replace(",", ".")) != 0, fm
        assert cerca(float(fm.replace(",", ".")), t, rel=0, absoluto=0.0005), "fmt_mm(%r) = %r" % (t, fm)
        comprobado()
    f.correr("nombre_dxf", nombre_dxf)

    @cfg
    @given(pref=st.sampled_from(["Brida base", "Brida de arista", "Chapa desplegada"]),
           usados=st.sets(st.integers(0, 30), max_size=12), basura=st.sets(st.text(max_size=5), max_size=3))
    def etiqueta_libre(pref, usados, basura):
        used = {"%s%d" % (pref, n) for n in usados} | set(basura)
        n = sm.next_label(pref, used)
        assert n not in used, "next_label(%r, %r) = %r ya está usado" % (pref, used, n)
        assert n.startswith(pref) and n[len(pref):].isdigit(), "next_label dio %r" % n
        comprobado()
    f.correr("etiqueta_libre", etiqueta_libre)

    @cfg
    @given(r=_rect_partido(st))
    def rectangulo_partido(r):
        ents, w, h = r
        m = sm.merge_lines(ents)
        lineas = [e for e in m if e[0] == "LINE"]
        per = sum(_largo(e) for e in lineas)
        assert cerca(per, 2 * (w + h), rel=1e-9, absoluto=1e-6), "perímetro %r, debería %r" % (per, 2 * (w + h))
        assert len(lineas) == 4, ("un rectángulo de %d pedazos quedó en %d rectas (debería 4): %r"
                                  % (len(ents), len(lineas), lineas))
        comprobado()
    f.correr("rectangulo_partido", rectangulo_partido)

    @cfg
    @given(x=st.floats(1, 500), resto=st.floats(1, 500), y=st.floats(-100, 100), que=st.sampled_from(["recta", "arco", "otra_capa"]))
    def no_une_donde_llega_otra(x, resto, y, que):
        a = ("LINE", "CONTORNO", 0.0, y, x, y)
        b = ("LINE", "CONTORNO", x, y, x + resto, y)
        if que == "recta":
            extra = ("LINE", "CONTORNO", x, y, x, y + 10.0)
        elif que == "arco":
            extra = ("ARC", "CONTORNO", x, y + 5.0, 5.0, 270.0, 0.0)  # empieza justo en (x, y)
        else:
            extra = ("LINE", "PLEGADO", 0.0, y, x, y)  # otra capa encima: no se une con nada
            m = sm.merge_lines([a, extra])
            assert len([e for e in m if e[0] == "LINE"]) == 2, "unió rectas de capas distintas: %r" % m
        m = sm.merge_lines([a, b, extra])
        cont = [e for e in m if e[0] == "LINE" and e[1] == "CONTORNO" and abs(e[3] - e[5]) < 1e-9 and abs(e[3] - y) < 1e-9]
        if que in ("recta", "arco"):
            assert len(cont) == 2, ("unió dos rectas en un punto al que llega una %s: %r" % (que, m))
        comprobado()
    f.correr("no_une_donde_llega_otra", no_une_donde_llega_otra)

    ent = st.one_of(
        st.tuples(st.just("LINE"), st.sampled_from(["CONTORNO", "PLEGADO"]), *[st.floats(-3000, 3000)] * 4),
        st.tuples(st.just("ARC"), st.just("CONTORNO"), st.floats(-3000, 3000), st.floats(-3000, 3000),
                  st.floats(0.1, 500), st.floats(0, 359), st.floats(0, 359)),
        st.tuples(st.just("CIRCLE"), st.just("CONTORNO"), st.floats(-3000, 3000), st.floats(-3000, 3000), st.floats(0.1, 500)),
    ).map(lambda e: tuple(round(v, 4) if isinstance(v, float) else v for v in e))

    @cfg
    @given(ents=st.lists(ent, min_size=1, max_size=12), dx=st.floats(-1000, 1000), dy=st.floats(-1000, 1000))
    def correr_y_caja(ents, dx, dy):
        e0 = sm.extent(ents)
        e1 = sm.extent(sm.shift(ents, dx, dy))
        esperado = (e0[0] + dx, e0[1] + dy, e0[2] + dx, e0[3] + dy)
        assert all(abs(a - b) < 1e-6 for a, b in zip(e1, esperado)), "extent(shift) %r, esperado %r" % (e1, esperado)
        comprobado()
    f.correr("correr_y_caja", correr_y_caja)

    @cfg
    @given(ents=st.lists(ent, min_size=1, max_size=12))
    def dxf_ida_y_vuelta(ents):
        txt = sm.dxf_text(ents)
        leidas, capas = _leer_dxf(txt)
        assert "CONTORNO" in capas and "PLEGADO" in capas, "faltan capas: %r" % list(capas)
        assert "DASH" in capas["PLEGADO"].get(6, [""])[0].upper(), "PLEGADO sin trazos: %r" % capas["PLEGADO"]
        assert len(leidas) == len(ents), "%d entidades escritas, %d leídas" % (len(ents), len(leidas))
        for e, (tipo, d) in zip(ents, leidas):
            assert tipo == e[0] and d[8][0] == e[1], "%r se leyó como %s en %s" % (e, tipo, d.get(8))
            if tipo == "LINE":
                got = (_num(d, 10), _num(d, 20), _num(d, 11), _num(d, 21))
                want = e[2:6]
            elif tipo == "ARC":
                got = (_num(d, 10), _num(d, 20), _num(d, 40), _num(d, 50), _num(d, 51))
                want = e[2:7]
            else:
                got = (_num(d, 10), _num(d, 20), _num(d, 40))
                want = e[2:5]
            assert all(abs(a - b) <= 1e-4 for a, b in zip(got, want)), ("%s escrita %r, leída %r: el DXF pierde "
                                                                       "precisión" % (tipo, want, got))
        comprobado()
    f.correr("dxf_ida_y_vuelta", dxf_ida_y_vuelta)

    @cfg
    @given(t=st.integers(5, 100).map(lambda n: n / 10.0), rel=st.sampled_from([0.5, 1.0, 1.5, 2.0, 3.0]),
           l1=st.floats(20, 200), l2=st.floats(20, 200), ancho=st.floats(10, 300))
    def detectar_espesor_y_radio(t, rel, l1, l2, ancho):
        r = round(t * rel, 3)
        s = _chapa_L(t, r, l1, l2, ancho)
        assert s.isValid() and len(s.Solids) == 1
        # la cara de abajo del ala horizontal (z = 0, la más grande plana con normal -Z)
        caras = [(i, fc) for i, fc in enumerate(s.Faces) if fc.Surface.__class__.__name__ == "Plane"
                 and abs(fc.CenterOfMass.z) < 1e-6]
        assert caras
        nombre = "Face%d" % (caras[0][0] + 1)
        dt = sm.detect_thickness(s, nombre)
        assert dt is not None and cerca(dt, t, rel=1e-6, absoluto=1e-6), \
            "detect_thickness dio %r, la chapa tiene %r (r=%r)" % (dt, t, r)
        dr = sm.detect_radius(s, t)
        assert dr is not None and cerca(dr, r, rel=1e-6, absoluto=1e-6), \
            "detect_radius dio %r, el radio interior es %r (t=%r)" % (dr, r, t)
        comprobado()
    f.correr("detectar_espesor_y_radio", detectar_espesor_y_radio)

    @cfg
    @given(t=st.integers(5, 60).map(lambda n: n / 10.0), r1=st.sampled_from([0.5, 1.0, 2.0, 3.0]),
           r2=st.sampled_from([0.5, 1.0, 2.0, 3.0]), l1=st.floats(20, 150), l2=st.floats(20, 150),
           l3=st.floats(20, 150), ancho=st.floats(10, 200))
    def dos_pliegues(t, r1, r2, l1, l2, l3, ancho):
        a, b = round(t * r1, 3), round(t * r2, 3)
        s = _chapa_Z(t, a, b, l1, l2, l3, ancho)
        assert s.isValid() and len(s.Solids) == 1
        # empate (un pliegue de cada radio): manda el mayor, como dice detect_radius
        esperado = max(a, b)
        dr = sm.detect_radius(s, t)
        assert dr is not None and cerca(dr, esperado, rel=1e-6, absoluto=1e-6),             "dos pliegues de radio %r y %r (t=%r): detect_radius dio %r, esperado %r" % (a, b, t, dr, esperado)
        comprobado()
    f.correr("dos_pliegues", dos_pliegues)

    f.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
