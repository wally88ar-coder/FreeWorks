# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Ecuaciones no toma como suyos los VarSets donde FreeWorks guarda datos (Issue #4): con solo el
VarSet de una matriz de componentes en el documento (marca SWUI_Pattern, con su Espaciado), crear
una variable global la pone en "Variables globales" (nuevo) y el Espaciado de la matriz no cambia;
ese Espaciado se sigue viendo, pero como "Espaciado@<la matriz>", no como una variable suelta. Lo
mismo con el de un taladro de ensamblaje (SWUI_AsmFeature)."""

import FreeCAD  # noqa: E402

from comun import cerca  # noqa: E402


def prueba():
    from swui.fork import equations as eq
    doc = FreeCAD.newDocument("VarSetInterno")
    for marca in ("SWUI_Pattern", "SWUI_AsmFeature"):
        v = doc.addObject("App::VarSet", "Datos")
        v.addProperty("App::PropertyString", marca, "SW", "")
        v.addProperty("App::PropertyFloat", "Espaciado", "SW", "")
        v.Espaciado = 50.0
    doc.recompute()
    m = eq.Model(doc)
    nombres = [m.var_display(v, p) for v, p in m.variables()]
    assert "Espaciado" not in nombres and any(n.startswith("Espaciado@") for n in nombres), \
        "los datos de FreeWorks salen como variables sueltas (o no salen): %s" % nombres
    vs, prop = m.set_variable("Espaciado", "7")
    doc.recompute()
    assert vs.Name == eq.VARSET_NAME, "la variable fue a %s (%s), no a Variables globales" % (vs.Name, vs.Label)
    for o in doc.Objects:
        if o.TypeId == "App::VarSet" and o is not vs:
            assert cerca(o.Espaciado, 50.0), "pisó el Espaciado de %s: %s" % (o.Name, o.Espaciado)
    assert cerca(vs.Espaciado, 7.0)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
