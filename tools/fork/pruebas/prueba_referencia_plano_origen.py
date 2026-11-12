# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#73: un croquis apoyado en un plano del origen como lo anota FreeCAD 1.1 (el Origen con
"XZ_Plane." de subelemento) NO se informa como referencia perdida (Reparar referencias y el
'verificar' de la IA). Uno apoyado en una cara que ya no existe sí."""

import FreeCAD  # noqa: E402

from comun import caja  # noqa: E402


def prueba():
    from swui.fork import repair_refs as rr
    doc = FreeCAD.newDocument("RefOrigen")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    box = caja(body, "Caja", 20, 20, 10)
    doc.recompute()
    bien = body.newObject("Sketcher::SketchObject", "Alzado")
    bien.AttachmentSupport = [(body.Origin, ("XZ_Plane.",))]
    bien.MapMode = "FlatFace"
    mal = body.newObject("Sketcher::SketchObject", "Perdido")
    mal.AttachmentSupport = [(box, ("Face99",))]
    mal.MapMode = "FlatFace"
    doc.recompute()
    malos = {o.Name: t for o, _k, t in rr.problems(doc)}
    assert bien.Name not in malos, "falso aviso en el croquis sobre el plano del origen (#73): %s" % malos[bien.Name]
    assert mal.Name in malos, "no avisó el croquis apoyado en una cara que no existe"
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
