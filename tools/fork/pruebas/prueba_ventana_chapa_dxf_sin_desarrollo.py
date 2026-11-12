# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#43, como SW): Exportar DXF de una chapa sin desarrollo escribe el archivo y NO
cambia la pieza: no queda un desarrollo oculto en el árbol ni un paso de deshacer. Después, una
Brida de arista nueva se acepta sin errores en el informe (antes el desarrollo oculto se
recalculaba con la pieza y fallaba con "?Face6")."""
TIPO = "completa"

import os  # noqa: E402
import tempfile  # noqa: E402

import FreeCAD  # noqa: E402

from casos_grupo3 import BridaArista, correr_cinta  # noqa: E402
from reglas_paneles import esperar_panel, informe_largo, mensajes_nuevos, tocar  # noqa: E402


def prueba():
    import FreeCADGui
    from swui.fork import sheet_metal as sm
    from swui.fork import sheet_panels
    doc = FreeCAD.newDocument("ChapaDxf")
    caso = BridaArista()
    yield from caso.preparar(doc)
    doc = caso.doc
    carpeta = tempfile.mkdtemp()
    doc.saveAs(os.path.join(carpeta, "chapa.FCStd"))
    yield 500
    assert sm.flat_of(caso.body) is None, "la prueba necesita una chapa sin desarrollo"
    pasos = doc.UndoCount
    FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", caso.body)
    ruta = sheet_panels.export_dxf()
    yield 1000
    assert ruta and os.path.exists(ruta), "no escribió el DXF: %r" % (ruta,)
    assert sm.flat_of(caso.body) is None, "quedó un desarrollo en el árbol (#43)"
    assert doc.UndoCount == pasos, "exportar dejó pasos de deshacer: %s" % (doc.UndoNames[:3],)
    assert not FreeCAD.getActiveTransaction(), "quedó abierto un paso: %s" % (FreeCAD.getActiveTransaction(),)
    desde = informe_largo()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(caso.body.Tip, caso.aristas()[0])
    correr_cinta("SWUI_SMEdgeFlange")
    yield from esperar_panel()
    yield 800
    assert tocar(), "no encontré Aceptar"
    yield 2000
    malos = [m for m in mensajes_nuevos(desde) if "Face" in m and ("Invalid" in m or "?" in m)]
    assert not malos, "errores en el informe: %s" % malos[:3]
    assert not [o.Label for o in doc.Objects if "Invalid" in str(o.State)], "quedaron operaciones con error"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
