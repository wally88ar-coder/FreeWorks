# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Ecuaciones: una fórmula que desborda ('=2^1000') se rechaza con un aviso en castellano ("El
resultado es demasiado grande") y la variable o la cota quedan como estaban. FreeCAD no avisa con
un OverflowError sino con un SystemError en inglés ("returned a result with an exception set") que
lleva el desborde como causa: el aviso salía con ese texto (hallado por el fuzzing el 12/11, después
de cerrar la Issue 45). Y una ecuación sobre una cota que no da un número ('=sqrt(-1)', '=acos(2)',
'=1e308*10') también se rechaza, como la de una variable (fuzzing del 12/11, después de la 46)."""

import FreeCAD  # noqa: E402

INGLES = ("returned", "exception", "object", "method", "built-in")


def prueba():
    from swui.fork import equations as eq
    doc = FreeCAD.newDocument("Desborde")
    try:
        body = doc.addObject("PartDesign::Body", "Cuerpo")
        caja = body.newObject("PartDesign::AdditiveBox", "Caja")
        caja.Length, caja.Width, caja.Height = 40, 30, 20
        doc.recompute()
        m = eq.Model(doc)
        m.set_variable("Largo", "40")
        doc.recompute()
        # ("Largo" = "Largo"^1000 sería circular: ese aviso es otro)
        for nombre, texto in (("Largo", "=2^1000"), ("Nueva", "=2^1000"), ("Nueva", "=\"Largo\"^1000")):
            try:
                m.set_variable(nombre, texto)
            except ValueError as exc:
                aviso = str(exc)
            else:
                raise AssertionError("aceptó %s = %s" % (nombre, texto))
            assert "demasiado grande" in aviso, "%s = %s: aviso %r" % (nombre, texto, aviso)
            assert not any(p in aviso for p in INGLES), "aviso en inglés: %r" % aviso
            vs, prop = [(v, p) for v, p in m.variables() if p == "Largo"][0]
            assert getattr(vs, prop) == 40.0, "la variable Largo quedó en %r" % getattr(vs, prop)
            assert not [p for _v, p in m.variables() if p == "Nueva"], "quedó la variable rechazada"
        nombres = eq.feature_dim_names(caja.TypeId, caja.PropertiesList)
        cota = "%s@%s" % (nombres.get("Length", "Length"), caja.Label)
        try:
            m.set_equation(cota, "=2^1000")
        except ValueError as exc:
            aviso = str(exc)
        else:
            raise AssertionError("aceptó la ecuación =2^1000")
        assert not any(p in aviso for p in INGLES), "aviso en inglés: %r" % aviso
        doc.recompute()
        assert caja.Length.Value == 40, "la cota quedó en %r" % caja.Length.Value
        # fórmulas que FreeCAD calcula sin error pero no dan un número (fuzzing del 12/11)
        for texto in ("=sqrt(-1)", "=acos(2)", "=log(0)", "=1e308*10", "=sqrt(-\"Largo\")"):
            try:
                m.set_equation(cota, texto)
            except ValueError as exc:
                assert "demasiado grande" in str(exc), "%s: aviso %r" % (texto, str(exc))
            else:
                raise AssertionError("aceptó la ecuación %s (no da un número)" % texto)
            assert not dict(caja.ExpressionEngine).get("Length"), "%s: quedó la fórmula puesta" % texto
            doc.recompute()
            assert caja.Length.Value == 40 and str(caja.Length.Unit) == str(FreeCAD.Units.Length),                 "%s: la cota quedó en %s" % (texto, caja.Length)
        # la cota de un croquis (otra forma de volver atrás: setDatum)
        import Part
        sk = body.newObject("Sketcher::SketchObject", "Croquis")
        sk.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(10, 0, 0)))
        import Sketcher
        sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 10))
        sk.renameConstraint(0, "D1")
        doc.recompute()
        for texto in ("=acos(2)", "=sqrt(-1)"):
            try:
                m.set_equation("D1@%s" % sk.Label, texto)
            except ValueError as exc:
                assert not any(p in str(exc) for p in INGLES), "aviso en inglés: %r" % str(exc)
            else:
                raise AssertionError("aceptó %s en la cota del croquis" % texto)
            doc.recompute()
            v = sk.Constraints[0].Value
            assert abs(v - 10) < 1e-9, "%s: la cota del croquis quedó en %r" % (texto, v)
    finally:
        FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
