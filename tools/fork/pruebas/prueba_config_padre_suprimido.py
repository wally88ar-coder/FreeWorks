# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#74 (como SW): en una configuración donde una operación está suprimida, las que dependen de ella
(un Redondeo sobre una arista suya) también quedan suprimidas al mostrarla, y la configuración nueva
copiada de ahí también; ninguna operación queda con error. En las otras configuraciones, todo activo."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from comun import caja  # noqa: E402

V = FreeCAD.Vector


def prueba():
    from swui.fork import configurations as cf
    doc = FreeCAD.newDocument("PadreSuprimido")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja(body, "Caja", 40, 40, 10)
    doc.recompute()
    sk = body.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = FreeCAD.Placement(V(0, 0, 10), FreeCAD.Rotation())
    sk.addGeometry(Part.Circle(V(20, 20, 0), V(0, 0, 1), 6))
    hueco = body.newObject("PartDesign::Pocket", "Hueco")
    hueco.Profile = sk
    hueco.Length = 5
    doc.recompute()
    arista = next("Edge%d" % (i + 1) for i, e in enumerate(hueco.Shape.Edges)
                  if e.Curve.__class__.__name__ == "Circle" and abs(e.Curve.Radius - 6) < 1e-6
                  and abs(e.Curve.Center.z - 5) < 1e-6)
    red = body.newObject("PartDesign::Fillet", "Redondeo")
    red.Base = (hueco, [arista])
    red.Radius = 1
    doc.recompute()
    assert red.isValid(), "la prueba necesita un redondeo válido"
    cf.ensure(doc)
    primera = cf.names(doc)[0]
    cf.add(doc, "Sin hueco")
    # solo el Hueco suprimido en esta configuración (como queda después de ciertas seguidillas: #74)
    cf.configure(doc, ("sup", hueco), 1, "this")
    cf.activate(doc, primera)
    cf.activate(doc, "Sin hueco")
    assert hueco.Suppressed and red.Suppressed, "Hueco %s, Redondeo %s" % (hueco.Suppressed, red.Suppressed)
    malos = [o.Label for o in body.Group if "Invalid" in str(o.State)]
    assert not malos, "con error: %s" % malos
    cf.add(doc, "Copia")
    assert cf.active(doc) == "Copia" and hueco.Suppressed and red.Suppressed, "la copia: %s %s" % (
        hueco.Suppressed, red.Suppressed)
    cf.activate(doc, primera)
    assert not hueco.Suppressed and not red.Suppressed, "en la primera quedó algo suprimido"
    malos = [o.Label for o in body.Group if "Invalid" in str(o.State)]
    assert not malos, "con error en la primera: %s" % malos
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
