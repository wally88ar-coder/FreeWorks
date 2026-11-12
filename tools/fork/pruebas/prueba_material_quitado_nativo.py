# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#21: una pieza con material asignado por FreeWorks (queda también su copia de respaldo) a la
que después se le saca el material con la herramienta nativa (ShapeMaterial = "Default"): pasa a
"sin material" (densidad 0 para la masa), no sigue contando el material viejo. Y si el material
FALTA en la biblioteca (la copia es de un material que no está), se sigue usando la copia."""

import json  # noqa: E402

import FreeCAD  # noqa: E402

from comun import caja  # noqa: E402


def prueba():
    from swui.fork import material
    doc = FreeCAD.newDocument("MaterialQuitado")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja(body, "Caja", 10, 10, 10)
    doc.recompute()
    con = [m for m in material.all_materials() if (material.density_from(m) or 0) > 0]
    assert con, "no hay materiales con densidad en la biblioteca"
    info = con[0]
    material.assign([body], info)
    rho, origen = material.density(body)
    assert origen == "material" and rho > 0, (rho, origen)

    # sacarlo con la herramienta nativa: "Default", y la copia de FreeWorks queda
    body.ShapeMaterial = material.get_material(material.DEFAULT_UUID)
    assert getattr(body, material.COPY_PROP, ""), "la prueba necesita la copia vieja en la pieza"
    rho, origen = material.density(body)
    assert origen is None, "material sacado a mano sigue contando (#21): %s, %r" % (origen, rho)

    # material que FALTA en la biblioteca: la copia sí vale
    copia = json.loads(getattr(body, material.COPY_PROP))
    copia["uuid"] = "00000000-0000-0000-0000-00000000f00d"
    setattr(body, material.COPY_PROP, json.dumps(copia))
    rho, origen = material.density(body)
    assert origen == "copia" and rho > 0, "material que falta en la biblioteca: %s, %r" % (origen, rho)
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
