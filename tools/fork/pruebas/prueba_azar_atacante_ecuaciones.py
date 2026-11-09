# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Agente atacante, Ecuaciones (escrito sin mirar el código, desde lo que promete cada función):
- una fórmula de SW al azar (números con coma decimal, + - * / ^, paréntesis, sqr, abs, int, iif y
  referencias a otra variable) puesta en una variable global da el MISMO número que la cuenta hecha
  a mano;
- un nombre que cumple la regla del propio FreeWorks (letras sin acento, números y _, empezando con
  letra: "h", "t", "A", "m"... son nombres típicos de SW) se acepta con su valor, o se rechaza con un
  ValueError en castellano SIN dejar una variable a medias;
- lo aceptado recalcula sin objetos con error (una fórmula válida en SW como 1 + atn(1) no puede
  quedar aceptada y rota);
- ecuación sobre una cota: la pieza toma el valor; guardar, cerrar y abrir deja las mismas
  ecuaciones (en forma SW) y la misma pieza; Deshacer vuelve exacto y Rehacer lo trae igual;
  borrar la ecuación deja la cota con su último valor (como SW);
- dos documentos abiertos (uno con acentos y espacios en el nombre) con la misma variable no se
  pisan;
- sketch_dim_names: nombres únicos, los con nombre propio lo conservan, solo cotas.
"""
TIPO = "azar"

import math  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

V = FreeCAD.Vector


def _pieza(nombre="Ecu", ancho=10.0, alto=5.0, largo=7.0):
    doc = FreeCAD.newDocument(nombre)
    doc.UndoMode = 1
    b = doc.addObject("PartDesign::Body", "Body")
    sk = b.newObject("Sketcher::SketchObject", "Sketch")
    xy = [f for f in b.Origin.OriginFeatures if f.Role == "XY_Plane"][0]
    sk.AttachmentSupport = [(xy, "")]
    sk.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(ancho, 0, 0), V(ancho, alto, 0), V(0, alto, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 0))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sk.addConstraint(Sketcher.Constraint("Vertical", 1))
    sk.addConstraint(Sketcher.Constraint("Vertical", 3))
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, ancho))
    sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, alto))
    pad = b.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = largo
    doc.recompute()
    return doc, b, sk, pad


def _con_error(doc):
    return [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]


# --- Fórmulas al azar: (texto SW, valor esperado) --------------------------------------------------


def _num_sw(v):
    """Número escrito como en SW en Argentina (coma decimal)."""
    texto = ("%.3f" % v).rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def _estrategias(st):
    hoja = st.one_of(
        st.integers(0, 500).map(lambda n: (str(n), float(n))),
        st.floats(0.001, 500, allow_nan=False).map(lambda x: round(x, 3)).map(lambda x: (_num_sw(x), x)),
        st.just(('"Base"', None)),  # referencia a otra variable (se reemplaza por su valor)
    )

    def ramas(hijos):
        def bin_(op):
            return st.tuples(hijos, hijos).map(lambda ab: ("(%s %s %s)" % (ab[0][0], op, ab[1][0]),
                                                           ("bin", op, ab[0][1], ab[1][1])))
        div = st.tuples(hijos, st.integers(1, 50)).map(
            lambda ab: ("(%s / %d)" % (ab[0][0], ab[1]), ("bin", "/", ab[0][1], float(ab[1]))))
        pot = st.tuples(hijos, st.integers(0, 3)).map(
            lambda ab: ("(%s ^ %d)" % (ab[0][0], ab[1]), ("pow", ab[0][1], ab[1])))
        sqr = st.integers(0, 400).map(lambda n: ("sqr(%d)" % n, math.sqrt(n)))
        absf = hijos.map(lambda a: ("abs(%s)" % a[0], ("abs", a[1])))
        intf = hijos.map(lambda a: ("int(%s)" % a[0], ("int", a[1])))
        iif = st.tuples(hijos, hijos, hijos, hijos).map(
            lambda t: ("iif(%s > %s; %s; %s)" % (t[0][0], t[1][0], t[2][0], t[3][0]),
                       ("iif", t[0][1], t[1][1], t[2][1], t[3][1])))
        return st.one_of(bin_("+"), bin_("-"), bin_("*"), div, pot, sqr, absf, intf, iif)

    return st.recursive(hoja, ramas, max_leaves=6)


def _valor(nodo, base):
    if nodo is None:
        return base
    if isinstance(nodo, float):
        return nodo
    k = nodo[0]
    if k == "bin":
        a, b = _valor(nodo[2], base), _valor(nodo[3], base)
        op = nodo[1]
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        return a / b
    if k == "pow":
        return _valor(nodo[1], base) ** nodo[2]
    if k == "abs":
        return abs(_valor(nodo[1], base))
    if k == "int":
        return float(math.trunc(_valor(nodo[1], base)))
    if k == "iif":
        return _valor(nodo[3], base) if _valor(nodo[1], base) > _valor(nodo[2], base) else _valor(nodo[4], base)
    raise ValueError(nodo)


def prueba():
    given, cfg, st = hypothesis_listo()
    from swui.fork import equations as eq
    f = Fallas()

    # 1) fórmula al azar = cuenta a mano
    @cfg
    @given(formula=_estrategias(st), base=st.integers(1, 300))
    def formula_al_azar(formula, base):
        texto, arbol = formula
        esperado = _valor(arbol, float(base))
        if not math.isfinite(esperado) or abs(esperado) > 1e12:
            return
        doc = FreeCAD.newDocument("Formula")
        try:
            m = eq.Model(doc)
            m.set_variable("Base", str(base))
            vs, prop = m.set_variable("Resultado", "= " + texto)
            doc.recompute()
            valor, _u = m.value(vs, prop)
            traza("  %s (Base=%d) -> %r, esperado %r" % (texto, base, valor, esperado))
            assert cerca(float(valor), esperado, rel=1e-7, absoluto=1e-6), \
                "%s con Base=%d dio %r y la cuenta da %r" % (texto, base, valor, esperado)
            assert not _con_error(doc), "quedó con error: %s" % _con_error(doc)
            comprobado()
        finally:
            FreeCAD.closeDocument(doc.Name)
    f.correr("formula_al_azar", formula_al_azar)

    # 2) nombres que cumplen la regla de FreeWorks: se aceptan, o se rechazan limpio
    nombres = ["h", "t", "A", "m", "s", "g", "N", "mm", "kg", "e", "pi", "Largo", "Ala", "x1", "Espesor"]

    @cfg
    @given(nombre=st.sampled_from(nombres), valor=st.integers(1, 999))
    def nombre_valido(nombre, valor):
        doc = FreeCAD.newDocument("Nombres")
        try:
            m = eq.Model(doc)
            m.set_variable("Otra", "1")
            antes = eq.count(doc)
            try:
                vs, prop = m.set_variable(nombre, str(valor))
            except ValueError as ex:
                # rechazo válido: con aviso propio y sin dejar nada a medias
                assert eq.count(doc) == antes, ("%r rechazado (%s) pero quedó la variable a medias: "
                                                "%d variables/ecuaciones en vez de %d"
                                                % (nombre, ex, eq.count(doc), antes))
                comprobado()
                return
            except Exception as ex:
                raise AssertionError("el nombre %r cumple la regla (letras, números y _, empezando con "
                                     "letra) y falla con un error de FreeCAD %s: %s; quedaron %d "
                                     "variables/ecuaciones (antes %d)"
                                     % (nombre, type(ex).__name__, ex, eq.count(doc), antes))
            doc.recompute()
            assert cerca(float(m.value(vs, prop)[0]), float(valor)), "%r quedó en %r" % (nombre, m.value(vs, prop))
            otra = m.set_variable("Doble", '= "%s" * 2' % nombre)
            doc.recompute()
            assert cerca(float(m.value(*otra)[0]), 2.0 * valor), "\"%s\" * 2 dio %r" % (nombre, m.value(*otra))
            comprobado()
        finally:
            FreeCAD.closeDocument(doc.Name)
    f.correr("nombre_valido", nombre_valido, "#48")  # error registrado: Issue #48

    # 3) una fórmula válida en SW no queda aceptada y rota
    @cfg
    @given(n=st.integers(1, 50), fn=st.sampled_from(["atn(1)", "arcsin(0,5)", "arccos(0,5)"]))
    def trig_mezclada(n, fn):
        doc = FreeCAD.newDocument("Trig")
        try:
            m = eq.Model(doc)
            try:
                vs, prop = m.set_variable("Ang", "= %d + %s" % (n, fn))
            except ValueError:
                comprobado()  # rechazada con aviso: vale
                return
            except Exception as ex:
                raise AssertionError("%d + %s: error de FreeCAD %s: %s" % (n, fn, type(ex).__name__, ex))
            doc.recompute()
            malos = _con_error(doc)
            assert not malos, ("'= %d + %s' (válida en SW) quedó aceptada, con %s en error y valor %r"
                               % (n, fn, malos, m.value(vs, prop)))
            comprobado()
        finally:
            FreeCAD.closeDocument(doc.Name)
    f.correr("trig_mezclada", trig_mezclada, "#49")  # error registrado: Issue #49

    # 4) ecuación sobre cota: guardar/abrir, deshacer/rehacer, borrar
    @cfg
    @given(largo=st.integers(1, 200), k=st.integers(1, 9), dec=st.integers(0, 9),
           prof=st.integers(1, 50), nombre=st.sampled_from(["Pieza", "Pieza ñandú 2", "Soporte-á b"]))
    def cota_guardar_deshacer(largo, k, dec, prof, nombre):
        doc, body, sk, pad = _pieza(nombre)
        carpeta = carpeta_temporal()
        try:
            m = eq.Model(doc)
            factor = "%d,%d" % (k, dec)
            fv = k + dec / 10.0
            v0 = body.Shape.Volume
            doc.openTransaction("Ecuaciones")
            m.set_variable("Largo", str(largo), "comentario con ñ y acento: á")
            m.set_equation("D1@Sketch", '"Largo" * %s' % factor)
            m.set_equation("D1@Pad", str(prof))
            doc.recompute()  # dentro del paso, como el Aceptar del diálogo
            doc.commitTransaction()
            esperado = largo * fv * 5.0 * prof
            assert cerca(body.Shape.Volume, esperado), "volumen %r, esperado %r" % (body.Shape.Volume, esperado)
            n = eq.count(doc)
            exprs = sorted((o.Name, p, m.sw_expr(o, x)) for o, p, x in m.expressions())
            # deshacer / rehacer
            doc.undo()
            doc.recompute()
            assert cerca(body.Shape.Volume, v0), "Deshacer: volumen %r, antes %r" % (body.Shape.Volume, v0)
            assert eq.count(doc) == 0, "Deshacer dejó %d variables/ecuaciones" % eq.count(doc)
            doc.redo()
            doc.recompute()
            assert cerca(body.Shape.Volume, esperado), "Rehacer: volumen %r, esperado %r" % (body.Shape.Volume, esperado)
            assert eq.count(doc) == n, "Rehacer: %d en vez de %d" % (eq.count(doc), n)
            # guardar, cerrar y abrir
            ruta = os.path.join(carpeta, "pieza.FCStd")
            doc.saveAs(ruta)
            FreeCAD.closeDocument(doc.Name)
            doc = FreeCAD.openDocument(ruta)
            doc.recompute()
            body = doc.getObject("Body")
            m = eq.Model(doc)
            assert cerca(body.Shape.Volume, esperado), "al abrir: volumen %r" % body.Shape.Volume
            assert eq.count(doc) == n, "al abrir: %d en vez de %d" % (eq.count(doc), n)
            exprs2 = sorted((o.Name, p, m.sw_expr(o, x)) for o, p, x in m.expressions())
            assert exprs2 == exprs, "al abrir cambiaron las ecuaciones:\n%r\n%r" % (exprs, exprs2)
            vs, prop = [v for v in m.variables() if v[1] == "Largo"][0]
            assert cerca(float(m.value(vs, prop)[0]), float(largo))
            # borrar la ecuación de la cota: queda el último valor (SW)
            m.set_equation("D1@Sketch", "")
            doc.recompute()
            assert cerca(body.Shape.Volume, esperado), ("borrar la ecuación cambió la pieza: %r, esperado %r"
                                                        % (body.Shape.Volume, esperado))
            assert eq.count(doc) == n - 1, "borrar la ecuación: %d en vez de %d" % (eq.count(doc), n - 1)
            assert not _con_error(doc), _con_error(doc)
            comprobado()
        finally:
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
    f.correr("cota_guardar_deshacer", cota_guardar_deshacer)

    # 5) dos documentos con la misma variable
    @cfg
    @given(a=st.integers(1, 100), b=st.integers(1, 100))
    def dos_documentos(a, b):
        d1, b1, _s1, _p1 = _pieza("Pieza uno")
        d2, b2, _s2, _p2 = _pieza("Pieza dós ñ")
        try:
            m1, m2 = eq.Model(d1), eq.Model(d2)
            m1.set_variable("Largo", str(a))
            m2.set_variable("Largo", str(b))
            m1.set_equation("D1@Sketch", '"Largo"')
            m2.set_equation("D1@Sketch", '"Largo" * 2')
            d1.recompute()
            d2.recompute()
            assert cerca(b1.Shape.Volume, a * 5.0 * 7.0), "doc 1: %r" % b1.Shape.Volume
            assert cerca(b2.Shape.Volume, 2 * b * 5.0 * 7.0), "doc 2: %r" % b2.Shape.Volume
            m1.set_variable("Largo", str(a + 1))
            d1.recompute()
            d2.recompute()
            assert cerca(b2.Shape.Volume, 2 * b * 5.0 * 7.0), "cambiar el doc 1 tocó el doc 2"
            assert eq.count(d1) == 2 and eq.count(d2) == 2, (eq.count(d1), eq.count(d2))
            comprobado()
        finally:
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
    f.correr("dos_documentos", dos_documentos)

    # 6) sketch_dim_names
    tipos = ["Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle",
             "Coincident", "Horizontal", "Vertical", "Tangent", "Equal", "PointOnObject"]
    cotas = {"Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"}

    @cfg
    @given(lista=st.lists(st.tuples(st.sampled_from(tipos),
                                    st.sampled_from(["", "", "", "D1", "D2", "D3", "Ancho", "D10"])),
                          max_size=14))
    def nombres_de_cotas(lista):
        # FreeCAD no deja dos restricciones con el mismo nombre: el caso válido no repite nombres
        vistos, limpio = set(), []
        for t, n in lista:
            if n and (n in vistos or t not in cotas):
                n = ""
            vistos.add(n)
            limpio.append((t, n))
        r = eq.sketch_dim_names(limpio)
        indices_cota = {i for i, (t, _n) in enumerate(limpio) if t in cotas}
        assert set(r) == indices_cota, "%r -> %r: no son exactamente las cotas" % (limpio, r)
        assert len(set(r.values())) == len(r), "%r -> nombres repetidos %r" % (limpio, r)
        for i, (_t, n) in enumerate(limpio):
            if n and i in r:
                assert r[i] == n, "%r: la cota %d tenía nombre %r y quedó %r" % (limpio, i, n, r[i])
        sin = [r[i] for i in sorted(indices_cota) if not limpio[i][1]]
        nums = [int(x[1:]) for x in sin]
        assert all(x.startswith("D") for x in sin) and nums == sorted(nums), \
            "%r -> las sin nombre no van D1, D2... en orden: %r" % (limpio, sin)
        comprobado()
    f.correr("nombres_de_cotas", nombres_de_cotas)

    f.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
