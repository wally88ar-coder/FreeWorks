# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#14: un croquis apoyado en una cara de una operación, con el apoyo DESACTIVADO a propósito
(MapMode "Deactivated"), sigue desactivado en todas las configuraciones cuando esa operación se
suprime por configuración (antes volvía pegado a la cara en las otras). Y uno apoyado de verdad
se apaga en la configuración donde la operación está suprimida y vuelve en las otras."""

import FreeCAD  # noqa: E402

from comun import caja  # noqa: E402


def prueba():
    from swui.fork import configurations as cf
    doc = FreeCAD.newDocument("CroquisDesactivado")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    base = caja(body, "Caja", 20, 20, 10)
    tope = caja(body, "Tope", 10, 10, 5, base=FreeCAD.Vector(0, 0, 10))
    doc.recompute()
    arriba = [i for i, f in enumerate(tope.Shape.Faces) if abs(f.CenterOfMass.z - 15) < 1e-6][0]
    suelto = body.newObject("Sketcher::SketchObject", "Suelto")
    suelto.AttachmentSupport = [(tope, "Face%d" % (arriba + 1))]
    suelto.MapMode = "FlatFace"
    doc.recompute()
    pl = suelto.Placement
    suelto.MapMode = "Deactivated"  # el usuario lo desactivó a propósito
    suelto.Placement = pl
    apoyado = body.newObject("Sketcher::SketchObject", "Apoyado")
    apoyado.AttachmentSupport = [(tope, "Face%d" % (arriba + 1))]
    apoyado.MapMode = "FlatFace"
    doc.recompute()
    cf.ensure(doc)
    primera = cf.active(doc)
    otra = cf.add(doc, "Otra")
    cf.configure(doc, ("sup", tope), 1, "this")  # suprimido solo en "Otra"
    cf.sync_attachments(doc)
    doc.recompute()
    for conf in (otra, primera, otra):
        cf.activate(doc, conf)
        doc.recompute()
        assert suelto.MapMode == "Deactivated", \
            "en «%s» el croquis desactivado a propósito quedó «%s» (#14)" % (conf, suelto.MapMode)
        esperado = "Deactivated" if conf == otra else "FlatFace"
        assert apoyado.MapMode == esperado, "en «%s» el croquis apoyado quedó «%s»" % (conf, apoyado.MapMode)
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
