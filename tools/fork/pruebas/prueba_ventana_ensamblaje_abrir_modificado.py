# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#79): un ensamblaje con dos piezas, guardado, cerrado y abierto de nuevo sin
tocar nada, NO queda como modificado (no pregunta si guardar al cerrarlo)."""
TIPO = "completa"
CONOCIDO = "#79"
ESPERA = "modificado al abrirlo (#79)"

import os  # noqa: E402
import tempfile  # noqa: E402

import FreeCAD  # noqa: E402

from casos_ensamblaje2 import TaladroEnsamblaje  # noqa: E402


def prueba():
    import FreeCADGui
    doc = FreeCAD.newDocument("Conjunto")
    caso = TaladroEnsamblaje()
    yield from caso.preparar(doc)
    doc = caso.doc
    ruta = doc.FileName
    if not ruta:
        ruta = os.path.join(tempfile.mkdtemp(), "conj.FCStd")
        doc.saveAs(ruta)
    for d in FreeCAD.listDocuments().values():
        if d.FileName:
            d.save()
    yield 1000
    FreeCAD.closeDocument(doc.Name)
    yield 800
    doc = FreeCAD.openDocument(ruta)
    yield 3000
    assert not FreeCADGui.getDocument(doc.Name).Modified, "el ensamblaje quedó modificado al abrirlo (#79)"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
