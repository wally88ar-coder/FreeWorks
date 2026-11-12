# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#72): la herramienta 'estado' del puente IA con un ensamblaje recién creado y
activo (en edición, vacío) responde bien y dice que se está editando el ensamblaje (antes fallaba:
la vista del ensamblaje no tiene .Object)."""
TIPO = "completa"

import FreeCAD  # noqa: E402


def prueba():
    import FreeCADGui
    from swui.fork.ia.herramientas import ver
    doc = FreeCAD.newDocument("Conjunto")
    FreeCAD.setActiveDocument(doc.Name)
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    asm.Type = "Assembly"
    asm.newObject("Assembly::JointGroup", "Joints")
    doc.recompute()
    FreeCADGui.getDocument(doc.Name).setEdit(asm)
    yield 1500
    res = ver.estado()
    assert res.success, "estado falló con el ensamblaje activo (#72): %s" % (res.output,)
    assert res.data.get("editando") == asm.Name, "editando: %r" % res.data.get("editando")
    FreeCADGui.getDocument(doc.Name).resetEdit()
    yield 500


from _base import ejecutar  # noqa: E402
ejecutar(globals())
