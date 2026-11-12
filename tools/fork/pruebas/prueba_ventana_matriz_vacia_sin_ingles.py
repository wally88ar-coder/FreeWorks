# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#26): abrir una Matriz lineal o circular sin nada elegido (la lista vacía, como
SW) no deja en el informe el aviso en inglés "One transformed shape does not intersect the support"."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from casos_pieza import armar_pieza, correr_cinta  # noqa: E402
from reglas_paneles import esperar_panel, informe_largo, _report_view  # noqa: E402


def prueba():
    import FreeCADGui
    doc = FreeCAD.newDocument("MatrizVacia")
    armar_pieza(doc)
    doc.recompute()
    vistos = []
    for comando in ("PartDesign_LinearPattern", "PartDesign_PolarPattern"):
        FreeCADGui.Selection.clearSelection()
        desde = informe_largo()
        correr_cinta(comando)
        yield from esperar_panel()
        yield 1500
        texto = _report_view().toPlainText()[desde:]
        vistos += [comando + ": " + l for l in texto.splitlines() if "does not intersect" in l]
        FreeCADGui.Control.closeDialog()
        yield 500
    assert not vistos, "aviso en inglés (#26): %s" % vistos


from _base import ejecutar  # noqa: E402
ejecutar(globals())
