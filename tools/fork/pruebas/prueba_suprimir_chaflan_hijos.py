# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#81 (como SW): un Redondeo sobre CUALQUIER arista de un Chaflán (también las de al lado que el
chaflán acortó) es hijo del Chaflán: suprimir el Chaflán (en una configuración) lo suprime también y
nada queda con error. Un Redondeo sobre una arista que el chaflán no tocó no es su hijo."""

import FreeCAD  # noqa: E402


def prueba():
    from swui.fork import configurations as cf
    from swui.fork import feature_tree as ft
    doc = FreeCAD.newDocument("ChaflanHijos")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    box = body.newObject("PartDesign::AdditiveBox", "Caja")
    box.Length = box.Width = 40
    box.Height = 10
    doc.recompute()
    ch = body.newObject("PartDesign::Chamfer", "Chamfer")
    ch.Base = (box, ["Edge1"])
    ch.Size = 2
    doc.recompute()
    malos = []
    for i in range(len(ch.Shape.Edges)):
        fi = body.newObject("PartDesign::Fillet", "Fillet")
        fi.Base = (ch, ["Edge%d" % (i + 1)])
        fi.Radius = 0.3
        doc.recompute()
        hijo = fi in ft.dependents(ch)
        ch.Suppressed = True
        doc.recompute()
        rompe = not fi.isValid()
        ch.Suppressed = False
        doc.recompute()
        if rompe and not hijo:
            malos.append("Edge%d" % (i + 1))
        doc.removeObject(fi.Name)
        doc.recompute()
    assert not malos, "redondeos que se rompen al suprimir el chaflán y no cuentan como hijos: %s (#81)" % malos
    # con configuraciones: suprimir el chaflán en una suprime al redondeo de la arista acortada
    largo = max(ch.Shape.Edges, key=lambda e: e.Length).Length
    acortada = next("Edge%d" % (i + 1) for i, e in enumerate(ch.Shape.Edges)
                    if abs(e.Length - (largo - 2)) < 1e-6)
    fi = body.newObject("PartDesign::Fillet", "Fillet")
    fi.Base = (ch, [acortada])
    fi.Radius = 0.3
    doc.recompute()
    cf.ensure(doc)
    cf.add(doc, "Sin chaflan")
    cf.suppress(ch)
    doc.recompute()
    assert ch.Suppressed and fi.Suppressed, "Chaflán %s, Redondeo %s" % (ch.Suppressed, fi.Suppressed)
    assert not [o.Label for o in body.Group if "Invalid" in str(o.State)], "quedó algo con error"
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
