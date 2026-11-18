# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#99: con la ventana de Ecuaciones abierta, se cierra su archivo; Ecuaciones en otro archivo abre sin error y
la ventana vieja se va."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from azar_comun import bombear  # noqa: E402


def prueba():
    from swui.fork import equations as eq
    a = FreeCAD.newDocument("EcA")
    a.addObject("PartDesign::Body", "Body")
    b = FreeCAD.newDocument("EcB")
    b.addObject("PartDesign::Body", "Body")
    vieja = eq.show_dialog(a)
    bombear(300)
    FreeCAD.closeDocument(a.Name)
    bombear(300)
    nueva = eq.show_dialog(b)
    bombear(300)
    assert nueva is not None and nueva.isVisible(), "Ecuaciones no abrió en el otro archivo"
    assert vieja not in eq._open and not vieja.isVisible(), "quedó la ventana del archivo cerrado"
    nueva.reject()
    bombear(200)
    FreeCAD.closeDocument(b.Name)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
