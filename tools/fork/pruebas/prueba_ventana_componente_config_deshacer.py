# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#11, segunda parte): un componente pasado a otra configuración de su pieza
(Placa "Larga", 120 mm en vez de 80) y Ctrl+Z en el ensamblaje: vuelve a la configuración de antes
y SE QUEDA ahí (antes FreeWorks lo volvía a pasar solo a la otra, porque su escucha actuaba
mientras FreeCAD deshacía)."""
TIPO = "completa"

import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from comun import caja, cerca  # noqa: E402


def prueba():
    from reglas_paneles import ctrl_z
    from swui import assembly_drop
    from swui.fork import config_asm as ca
    from swui.fork import configurations as cf
    carpeta = carpeta_temporal()
    pdoc = FreeCAD.newDocument("Placa")
    body = pdoc.addObject("PartDesign::Body", "Body")
    c = caja(body, "Caja", 80, 40, 10)
    pdoc.recompute()
    cf.ensure(pdoc)
    primera = cf.active(pdoc)
    cf.add(pdoc, "Larga")
    cf.configure(pdoc, ("prop", c, "Length"), 120, "this")
    cf.activate(pdoc, primera)
    pdoc.recompute()
    ruta = os.path.join(carpeta, "Placa.FCStd")
    pdoc.saveAs(ruta)
    FreeCAD.closeDocument(pdoc.Name)

    doc = FreeCAD.newDocument("Conjunto")
    FreeCAD.setActiveDocument(doc.Name)
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    asm.Type = "Assembly"
    asm.newObject("Assembly::JointGroup", "Joints")
    doc.recompute()
    doc.saveAs(os.path.join(carpeta, "Conjunto.FCStd"))
    (link,) = assembly_drop.insert_files(asm, [ruta])
    doc.recompute()
    yield 800
    largo0 = link.LinkedObject.Shape.BoundBox.XLength
    assert cerca(largo0, 80), largo0
    doc.openTransaction("Configuración del componente")
    ca.set_config(link, "Larga")
    doc.recompute()
    doc.commitTransaction()
    yield 2000
    assert cerca(link.LinkedObject.Shape.BoundBox.XLength, 120), "no pasó a «Larga»"
    ctrl_z(doc)
    doc.recompute()
    yield 3000  # que las escuchas tengan tiempo de actuar
    largo = link.LinkedObject.Shape.BoundBox.XLength
    assert cerca(largo, 80), "después de Ctrl+Z el componente mide %.1f (volvió solo a «Larga», #11)" % largo
    assert ca.current(link) in (primera, None, ""), "quedó en «%s»" % ca.current(link)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
