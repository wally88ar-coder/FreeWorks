# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Un marco soldado guardado por FreeWorks no depende de FreeWorks para abrir: el archivo no
guarda objetos de Python propios (ninguna clase "swui." en Document.xml), se abre de nuevo y todos sus
sólidos son válidos con el mismo volumen."""

import os  # noqa: E402
import zipfile  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from comun import cerca, marco  # noqa: E402


def prueba():
    doc = FreeCAD.newDocument("Guardar")
    _sk, _c, cuerpos = marco(doc, esquina="inglete")
    vol = {b.Name: b.Shape.Volume for b in cuerpos}
    ruta = os.path.join(carpeta_temporal(), "marco.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("Document.xml").decode("utf-8", "replace")
    # las propiedades SWUI_ son nativas (se leen sin FreeWorks); lo que no debe haber es una clase
    # de Python de FreeWorks (módulo "swui.algo")
    assert "swui." not in xml, "el archivo guarda una clase de FreeWorks: no abriría sin FreeWorks"
    assert "FeaturePython" not in xml, "el archivo tiene objetos de Python"
    doc = FreeCAD.openDocument(ruta)
    doc.recompute()
    for nombre, v in vol.items():
        o = doc.getObject(nombre)
        assert o is not None and o.Shape.isValid() and cerca(o.Shape.Volume, v, 0.5), \
            "%s cambió al reabrir" % nombre


from _base import ejecutar  # noqa: E402
ejecutar(globals())
