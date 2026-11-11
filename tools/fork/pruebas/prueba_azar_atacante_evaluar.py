# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Agente atacante, Evaluar: propiedades físicas y material (escrito sin mirar el código, desde
lo que promete cada función y cómo da SW 2018 el informe):
- partir un sólido en dos (caja girada y corrida al azar, corte en cualquier lugar) no cambia la
  masa, el volumen, el centro de masa ni las inercias (en el centro y en el origen) de combine;
- los momentos principales son los de libro de la caja (en cualquier giro), sus ejes son unitarios
  y perpendiculares, y con ellos se rearma el tensor; shift (Steiner) lleva el tensor del centro
  al del origen;
- con dos piezas de materiales distintos (compute sobre el documento), la masa es la suma de
  densidad x volumen y el centro el promedio pesado; sin material la masa es 0 y el centro sale
  del volumen; guardar, cerrar y abrir (documento con acentos y espacios) da lo mismo;
- fmt escribe el número redondeado a esos decimales con punto de miles y coma decimal;
- parse_number lee un número escrito como en Argentina (punto de miles, coma decimal) y lo que
  escribe fmt_number;
- copy_text / read_copy guardan y devuelven el material igual (nombres con acentos);
- safe_file_name da siempre un nombre de archivo válido en Windows (sin caracteres prohibidos,
  sin terminar en punto o espacio, y que no sea un nombre reservado como CON o NUL).
"""
TIPO = "azar"

import os  # noqa: E402
import re  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

V = FreeCAD.Vector


def _tensor(shape):
    M = shape.MatrixOfInertia
    return [[M.A11, M.A12, M.A13], [M.A21, M.A22, M.A23], [M.A31, M.A32, M.A33]]


def _item(shape, rho):
    c = shape.CenterOfMass
    return (shape.Volume, shape.Area, (c.x, c.y, c.z), _tensor(shape), rho)


def _igual_tensor(a, b, escala):
    return all(abs(a[i][j] - b[i][j]) <= 1e-6 * max(escala, 1e-12) + 1e-12 for i in range(3) for j in range(3))


def _rot(st):
    return st.tuples(st.floats(-1, 1), st.floats(-1, 1), st.floats(-1, 1), st.floats(0, 360)).filter(
        lambda t: abs(t[0]) + abs(t[1]) + abs(t[2]) > 0.05).map(
        lambda t: FreeCAD.Rotation(V(t[0], t[1], t[2]), t[3]))


def _leer_ar(texto):
    """'1.234,567' -> 1234.567 (lector propio, para no depender de parse_number)."""
    return float(texto.replace(".", "").replace(",", "."))


def prueba():
    given, cfg, st = hypothesis_listo()
    from swui.fork import mass_props as mp
    from swui.fork import material as mat
    f = Fallas()
    medida = st.floats(1, 100)

    @cfg
    @given(dx=medida, dy=medida, dz=medida, frac=st.floats(0.05, 0.95), eje=st.integers(0, 2),
           rot=_rot(st), pos=st.tuples(st.floats(-200, 200), st.floats(-200, 200), st.floats(-200, 200)),
           rho=st.floats(1e-7, 2e-5))
    def partir_en_dos(dx, dy, dz, frac, eje, rot, pos, rho):
        dims = [dx, dy, dz]
        pl = FreeCAD.Placement(V(*pos), rot)
        entera = Part.makeBox(dx, dy, dz)
        corte = dims[eje] * frac
        d1, d2 = list(dims), list(dims)
        d1[eje], d2[eje] = corte, dims[eje] - corte
        base2 = [0.0, 0.0, 0.0]
        base2[eje] = corte
        p1 = Part.makeBox(*d1)
        p2 = Part.makeBox(d2[0], d2[1], d2[2], V(*base2))
        for s in (entera, p1, p2):
            s.Placement = pl
        r0 = mp.combine([_item(entera, rho)])
        r2 = mp.combine([_item(p1, rho), _item(p2, rho)])
        assert cerca(r0["mass"], r2["mass"], rel=1e-9, absoluto=0), (r0["mass"], r2["mass"])
        assert cerca(r0["volume"], r2["volume"], rel=1e-9), (r0["volume"], r2["volume"])
        for i in range(3):
            assert abs(r0["center"][i] - r2["center"][i]) < 1e-7 * (1 + max(dims) + 200), (r0["center"], r2["center"])
        esc = max(abs(x) for fila in r0["inertia_origin"] for x in fila)
        assert _igual_tensor(r0["inertia_cm"], r2["inertia_cm"], esc), \
            "inercia en el centro: entera %r, en dos %r" % (r0["inertia_cm"], r2["inertia_cm"])
        assert _igual_tensor(r0["inertia_origin"], r2["inertia_origin"], esc), \
            "inercia en el origen: entera %r, en dos %r" % (r0["inertia_origin"], r2["inertia_origin"])
        comprobado()
    f.correr("partir_en_dos", partir_en_dos)

    @cfg
    @given(dx=medida, dy=medida, dz=medida, rot=_rot(st),
           pos=st.tuples(st.floats(-100, 100), st.floats(-100, 100), st.floats(-100, 100)))
    def principales_y_steiner(dx, dy, dz, rot, pos):
        rho = 7.85e-6
        s = Part.makeBox(dx, dy, dz)
        s.Placement = FreeCAD.Placement(V(*pos), rot)
        r = mp.combine([_item(s, rho)])
        m = rho * dx * dy * dz
        libro = sorted([m * (dy * dy + dz * dz) / 12, m * (dx * dx + dz * dz) / 12, m * (dx * dx + dy * dy) / 12])
        pr = mp.principal(r["inertia_cm"])
        momentos = [p[0] for p in pr]
        assert momentos == sorted(momentos), "no van de menor a mayor: %r" % momentos
        for a, b in zip(momentos, libro):
            assert cerca(a, b, rel=1e-6, absoluto=1e-12), "momentos %r, de libro %r" % (momentos, libro)
        ejes = [p[1] for p in pr]
        for i in range(3):
            assert cerca(sum(x * x for x in ejes[i]), 1.0, rel=1e-6), "eje %d no unitario: %r" % (i, ejes[i])
            for j in range(i + 1, 3):
                assert abs(sum(a * b for a, b in zip(ejes[i], ejes[j]))) < 1e-5, "ejes no perpendiculares %r" % ejes
        # rearmar el tensor (solo si los momentos son distintos; si se repiten, los ejes no son únicos
        # pero la suma igual tiene que dar el tensor)
        T = [[sum(pr[k][0] * ejes[k][i] * ejes[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        esc = max(libro)
        assert _igual_tensor(T, r["inertia_cm"], esc), "con los principales no se rearma el tensor:\n%r\n%r" % (T, r["inertia_cm"])
        orig = mp.shift(r["inertia_cm"], r["mass"], r["center"])
        esc2 = max(abs(x) for fila in r["inertia_origin"] for x in fila)
        assert _igual_tensor(orig, r["inertia_origin"], esc2), \
            "Steiner hasta el origen %r, combine da %r" % (orig, r["inertia_origin"])
        comprobado()
    f.correr("principales_y_steiner", principales_y_steiner)

    mats = [x for x in mat.all_materials() if x.get("library") == "System"]
    acero = [x for x in mats if x["name"] == "Steel-Generic"][0]
    alu = [x for x in mats if x["name"] == "Aluminum-Generic"][0]

    @cfg
    @given(a=st.tuples(medida, medida, medida), b=st.tuples(medida, medida, medida),
           gap=st.floats(0, 50), cual=st.sampled_from(["acero+alu", "acero+nada", "nada+nada", "alu+alu"]),
           nombre=st.sampled_from(["Masa", "Pieza con ñ y espacio", "Ácido-1"]),
           pd=st.booleans())
    def dos_materiales(a, b, gap, cual, nombre, pd):
        carpeta = carpeta_temporal()
        doc = FreeCAD.newDocument(nombre)
        try:
            sa = doc.addObject("Part::Feature", "A")
            sa.Shape = Part.makeBox(*a)
            if pd:  # la segunda como Cuerpo de Part Design
                sb = doc.addObject("PartDesign::Body", "B")
                bx = sb.newObject("PartDesign::AdditiveBox", "Caja")
                bx.Length, bx.Width, bx.Height = b
                bx.Placement.Base = V(a[0] + gap, 0, 0)
            else:
                sb = doc.addObject("Part::Feature", "B")
                sb.Shape = Part.makeBox(b[0], b[1], b[2], V(a[0] + gap, 0, 0))
            doc.recompute()
            ma, mb = cual.split("+")
            info = {"acero": acero, "alu": alu, "nada": None}
            if info[ma]:
                mat.assign([sa], info[ma])
            if info[mb]:
                mat.assign([sb], info[mb])
            doc.recompute()

            def rho(x):
                return 0.0 if info[x] is None else info[x]["values"]["Density"][0] * 1e-9
            va, vb = a[0] * a[1] * a[2], b[0] * b[1] * b[2]
            ca = (a[0] / 2, a[1] / 2, a[2] / 2)
            cb = (a[0] + gap + b[0] / 2, b[1] / 2, b[2] / 2)
            masa = rho(ma) * va + rho(mb) * vb
            if masa > 0:
                centro = [(rho(ma) * va * ca[i] + rho(mb) * vb * cb[i]) / masa for i in range(3)]
            else:
                centro = [(va * ca[i] + vb * cb[i]) / (va + vb) for i in range(3)]

            def mirar(d, cuando):
                res = mp.compute(mp.components(d))[0]
                assert cerca(res["mass"], masa, rel=1e-6, absoluto=1e-12), \
                    "%s: masa %r, esperada %r (%s)" % (cuando, res["mass"], masa, cual)
                assert cerca(res["volume"], va + vb, rel=1e-6), "%s: volumen %r" % (cuando, res["volume"])
                for i in range(3):
                    assert abs(res["center"][i] - centro[i]) < 1e-6 * (1 + abs(centro[i])), \
                        "%s: centro %r, esperado %r (%s)" % (cuando, res["center"], centro, cual)
            mirar(doc, "recién hecho")
            ruta = os.path.join(carpeta, "masa.FCStd")
            doc.saveAs(ruta)
            FreeCAD.closeDocument(doc.Name)
            doc = FreeCAD.openDocument(ruta)
            doc.recompute()
            mirar(doc, "al abrir")
            comprobado()
        finally:
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
    f.correr("dos_materiales", dos_materiales)

    @cfg
    @given(x=st.floats(-1e9, 1e9, allow_nan=False), dec=st.integers(0, 6))
    def fmt_redondea(x, dec):
        t = mp.fmt(x, dec)
        assert re.fullmatch(r"-?\d{1,3}(\.\d{3})*(,\d+)?", t), "fmt(%r, %d) = %r no tiene el formato 1.234,5" % (x, dec, t)
        if dec == 0:
            assert "," not in t, "fmt(%r, 0) = %r con decimales" % (x, t)
        else:
            assert len(t.split(",")[1]) == dec, "fmt(%r, %d) = %r" % (x, dec, t)
        # redondeo: a lo sumo media unidad del último decimal (vale el redondeo al par)
        assert abs(_leer_ar(t) - x) <= 0.5 * 10 ** -dec + 1e-9 * max(1, abs(x)), "fmt(%r, %d) = %r" % (x, dec, t)
        comprobado()
    f.correr("fmt_redondea", fmt_redondea)

    @cfg
    @given(entero=st.integers(0, 10 ** 12), decs=st.one_of(st.just(""), st.integers(0, 999).map(lambda n: "%d" % n)))
    def parse_argentino(entero, decs):
        miles = "{:,}".format(entero).replace(",", ".")
        texto = miles + ("," + decs if decs else "")
        esperado = float(str(entero) + ("." + decs if decs else ""))
        # "12.345" solo es ambiguo (podría ser 12,345 escrito en inglés): se prueba desde dos puntos
        if decs == "" and miles.count(".") == 1:
            return
        v = mat.parse_number(texto)
        assert v is not None and cerca(v, esperado, rel=1e-12, absoluto=1e-9), \
            "parse_number(%r) = %r, y en Argentina es %r" % (texto, v, esperado)
        comprobado()
    f.correr("parse_argentino", parse_argentino)

    @cfg
    @given(x=st.floats(-1e12, 1e12, allow_nan=False))
    def parse_de_fmt_number(x):
        t = mat.fmt_number(x)
        v = mat.parse_number(t)
        # fmt_number es para mostrar: la promesa no dice cuántas cifras guarda (con 1966019661 da
        # '1,966e+09', 4 cifras). Se exige solo que lo que muestra se pueda volver a leer y sea ese
        # número a 4 cifras significativas (DUDOSO anotado en el informe del atacante).
        assert v is not None and cerca(v, x, rel=5e-4, absoluto=1e-12), "fmt_number(%r) = %r -> %r" % (x, t, v)
        comprobado()
    f.correr("parse_de_fmt_number", parse_de_fmt_number)

    @cfg
    @given(nombre=st.text(min_size=1, max_size=30), cat=st.text(max_size=20), dens=st.floats(1, 30000),
           otros=st.dictionaries(st.sampled_from(["YoungsModulus", "PoissonRatio", "YieldStrength"]),
                                 st.tuples(st.floats(0, 1e6), st.sampled_from(["MPa", "", "1/K"]))))
    def copia_ida_y_vuelta(nombre, cat, dens, otros):
        valores = dict(otros)
        valores["Density"] = (dens, "kg/m^3")
        info = {"uuid": "1234-abcd", "name": nombre, "category": cat, "description": "",
                "values": valores}
        back = mat.read_copy(mat.copy_text(info))
        assert back is not None, "read_copy(copy_text(...)) dio None para %r" % info
        assert back["name"] == nombre and back["uuid"] == "1234-abcd", (nombre, back)
        for k, v in valores.items():
            assert tuple(back["values"][k]) == tuple(v), "%s: %r -> %r" % (k, v, back["values"].get(k))
        assert cerca(mat.density_from(back), dens * 1e-9, rel=1e-9, absoluto=0), (dens, mat.density_from(back))
        comprobado()
    f.correr("copia_ida_y_vuelta", copia_ida_y_vuelta)

    reservados = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1", "con", "Nul", "CON.txt", "aux "]

    @cfg
    @given(nombre=st.one_of(st.sampled_from(reservados), st.text(max_size=30)))
    def nombre_de_archivo(nombre):
        t = mat.safe_file_name(nombre)
        assert t, "safe_file_name(%r) vacío" % nombre
        assert not re.search(r'[<>:"/\\|?*\x00-\x1f]', t), "safe_file_name(%r) = %r con caracteres prohibidos" % (nombre, t)
        assert not t.endswith((".", " ")), "safe_file_name(%r) = %r termina en punto o espacio" % (nombre, t)
        base = t.split(".")[0].strip().upper()
        assert base not in {"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)} | \
            {"LPT%d" % i for i in range(1, 10)}, \
            "safe_file_name(%r) = %r es un nombre reservado de Windows (no se puede crear %s.FCMat)" % (nombre, t, t)
        comprobado()
    f.correr("nombre_de_archivo", nombre_de_archivo)

    f.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
