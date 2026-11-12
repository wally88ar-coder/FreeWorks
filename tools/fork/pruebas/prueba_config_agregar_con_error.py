# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#75: con una operación en error en la pieza (un Chaflán sobre una arista que ya no existe, como
dejó #74), Agregar configuración funciona igual (como SW): dos seguidas, cada una queda activa y en
la lista; antes daba "No hay una configuración ..."."""

import FreeCAD  # noqa: E402

from comun import caja  # noqa: E402


def prueba():
    from swui.fork import configurations as cf
    doc = FreeCAD.newDocument("AgregarConError")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    box = caja(body, "Caja", 20, 20, 10)
    doc.recompute()
    ch = body.newObject("PartDesign::Chamfer", "Chamfer")
    ch.Base = (box, ["Edge99"])  # arista que no existe: queda en error
    ch.Size = 1
    doc.recompute()
    assert "Invalid" in str(ch.State) or not ch.isValid(), "la prueba necesita una operación en error"
    cf.ensure(doc)
    for nombre in ("Otra", "Tercera"):
        hecho = cf.add(doc, nombre)
        assert hecho == nombre and nombre in cf.names(doc), "no quedó «%s»: %s" % (nombre, cf.names(doc))
        assert cf.active(doc) == nombre, "activa: %s" % cf.active(doc)
    cf.configure(doc, ("prop", box, "Length"), 30, "this")
    cf.activate(doc, cf.names(doc)[0])
    doc.recompute()
    assert abs(box.Length.Value - 20) < 1e-6, box.Length
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
