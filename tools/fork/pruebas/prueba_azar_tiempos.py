# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Tiempos máximos (plan de calidad, paso 9), sin ventana: con piezas GRANDES, lo que hace FreeWorks
tiene que terminar en un tiempo razonable. Cada tope es ~4 veces lo medido el 09/11 (mínimo 3 s) en la PC del
usuario (FreeCAD 1.1.4): si algo pasa a tardar mucho más, es que un cambio lo empeoró.
- Soldada: escalera de 2 largueros y 20 travesaños (22 miembros): crear los miembros, poner las
  esquinas a tope, la lista de cortes, y estirar un larguero y recalcular todo (cada tiempo
  vale solo si todo quedó sin errores).
- Configuraciones: pieza con 12 configuraciones de largo distinto: pasar por todas.
- Propiedades físicas: 60 sólidos en una pieza, la cuenta completa (`mass_props.compute`).
- Ecuaciones: 100 variables encadenadas (cada una depende de la anterior) y recalcular.
Los tiempos medidos quedan en la traza de la prueba (para ajustar los topes si cambia la PC)."""
TIPO = "azar"

import time  # noqa: E402

import FreeCAD  # noqa: E402

from _base import traza  # noqa: E402

V = FreeCAD.Vector

TOPES = {  # segundos
    "soldada: crear 22 miembros": 6.0,
    "soldada: esquinas a tope": 10.0,
    "soldada: lista de cortes": 8.0,
    "soldada: estirar un larguero y recalcular todo": 10.0,
    "configuraciones: pasar por 12": 6.0,
    "propiedades físicas de 60 sólidos": 3.0,
    "ecuaciones: 100 variables encadenadas": 3.0,
}
MEDIDO = {}


def _sanos(doc, que):
    """Un recálculo que falla suele ser MÁS rápido: el tiempo solo vale si quedó todo bien."""
    malos = [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
    assert not malos, "%s: quedaron con error: %s" % (que, malos[:5])


class _Reloj:
    def __init__(self, nombre):
        self.nombre = nombre

    def __enter__(self):
        self.t0 = time.time()

    def __exit__(self, tipo, *_x):
        if tipo is None:
            MEDIDO[self.nombre] = time.time() - self.t0
            traza("  %-42s %6.1f s (tope %.0f s)" % (self.nombre, MEDIDO[self.nombre], TOPES[self.nombre]))
        return False


def soldada():
    import Part
    import Sketcher
    from swui.fork import weldments as w
    doc = FreeCAD.newDocument("TiempoSoldada")
    try:
        sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
        largo, ancho, n = 3000.0, 500.0, 20
        sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(largo, 0, 0)))
        sk.addGeometry(Part.LineSegment(V(0, ancho, 0), V(largo, ancho, 0)))
        for i in range(n):
            x = largo * (i + 0.5) / n
            sk.addGeometry(Part.LineSegment(V(x, 0, 0), V(x, ancho, 0)))
        cota = sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, largo))
        doc.recompute()
        size = w.sizes("Caño cuadrado")[10][0]
        with _Reloj("soldada: crear 22 miembros"):
            cuerpos = w.create_members(doc, [(sk, "Edge%d" % (i + 1)) for i in range(n + 2)], "Caño cuadrado", size)
            doc.recompute()
        _sanos(doc, "crear miembros")
        assert len(cuerpos) == n + 2, "se crearon %d miembros, no %d" % (len(cuerpos), n + 2)
        with _Reloj("soldada: esquinas a tope"):
            w.apply_corners(cuerpos, "tope")
            doc.recompute()
        _sanos(doc, "esquinas")
        with _Reloj("soldada: lista de cortes"):
            filas = w.cut_list(doc)
        assert sum(f["qty"] for f in filas) == n + 2, "la lista de cortes no tiene los %d miembros" % (n + 2)
        with _Reloj("soldada: estirar un larguero y recalcular todo"):
            sk.setDatum(cota, FreeCAD.Units.Quantity("3200 mm"))
            for o in doc.Objects:
                o.touch()
            doc.recompute()
        _sanos(doc, "estirar")
    finally:
        FreeCAD.closeDocument(doc.Name)


def configuraciones():
    from swui.fork import configurations as cf
    doc = FreeCAD.newDocument("TiempoConfig")
    try:
        body = doc.addObject("PartDesign::Body", "Cuerpo")
        caja = body.newObject("PartDesign::AdditiveBox", "Caja")
        caja.Length, caja.Width, caja.Height = 50, 30, 10
        for i in range(8):  # algo de historial
            h = body.newObject("PartDesign::SubtractiveCylinder", "Agujero%d" % i)
            h.Radius, h.Height = 1.5, 10
            h.Placement.Base = V(5 + 5 * i, 15, 0)
        doc.recompute()
        cf.ensure(doc)
        largos = {}
        for i in range(12):
            nombre = cf.add(doc, "C%02d" % i)
            largos[nombre] = 50.0 + 5 * i
            cf.configure(doc, ("prop", caja, "Length"), largos[nombre], scope="this")
        doc.recompute()
        with _Reloj("configuraciones: pasar por 12"):
            for nombre, largo in largos.items():
                cf.activate(doc, nombre)
                doc.recompute()
                assert abs(caja.Length.Value - largo) < 1e-6, "en %s el largo es %s" % (nombre, caja.Length)
    finally:
        FreeCAD.closeDocument(doc.Name)


def propiedades():
    from swui.fork import mass_props as mp
    doc = FreeCAD.newDocument("TiempoMasa")
    try:
        for i in range(60):
            b = doc.addObject("PartDesign::Body", "Cuerpo%d" % i)
            c = b.newObject("PartDesign::AdditiveBox", "Caja%d" % i)
            c.Length, c.Width, c.Height = 10 + i % 7, 10, 10
            c.Placement.Base = V(30 * (i % 10), 30 * (i // 10), 0)
        doc.recompute()
        with _Reloj("propiedades físicas de 60 sólidos"):
            partes = mp.components(doc)
            resultado, _rhos, _nombres, _notas = mp.compute(partes)
        assert resultado is not None, "compute no devolvió resultado"
    finally:
        FreeCAD.closeDocument(doc.Name)


def ecuaciones():
    from swui.fork import equations as eq
    doc = FreeCAD.newDocument("TiempoEcuaciones")
    try:
        body = doc.addObject("PartDesign::Body", "Cuerpo")
        body.newObject("PartDesign::AdditiveBox", "Caja")
        doc.recompute()
        m = eq.Model(doc)
        with _Reloj("ecuaciones: 100 variables encadenadas"):
            m.set_variable("V0", "10")
            for i in range(1, 100):
                m.set_variable("V%d" % i, '= "V%d" + 1' % (i - 1))
            doc.recompute()
        valores = {p: getattr(vs, p) for vs, p in m.variables()}
        assert abs(valores.get("V99", -1) - 109) < 1e-9, "V99 debería dar 109 y da %s" % valores.get("V99")
    finally:
        FreeCAD.closeDocument(doc.Name)


def prueba():
    errores = []
    for fn in (soldada, configuraciones, propiedades, ecuaciones):
        try:
            fn()
        except Exception as exc:
            errores.append("%s: %s: %s" % (fn.__name__, type(exc).__name__, exc))
    lentos = ["%s tardó %.1f s (tope %.0f s)" % (n, s, TOPES[n]) for n, s in MEDIDO.items() if s > TOPES[n]]
    assert not errores and not lentos, "\n".join(errores + lentos)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
