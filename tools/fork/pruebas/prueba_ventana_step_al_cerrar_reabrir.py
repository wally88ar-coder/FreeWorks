# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#40): con "Guardar también STEP" encendido, guardar y cerrar un archivo hace
que FreeWorks lo abra oculto para escribir el STEP y después lo cierre. Si mientras tanto el
usuario abre ese mismo archivo, FreeCAD le da el documento oculto, y al terminar el STEP FreeWorks
se lo cerraba: el documento recién abierto "se cerraba solo" (visto en la prueba de reglas de
soldadas). Como SW: el documento que abrió el usuario queda abierto y el STEP se escribe igual."""
TIPO = "completa"
import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _archivo(carpeta, nombre):
    doc = FreeCAD.newDocument(nombre)
    body = doc.addObject("PartDesign::Body", "Body")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 40, 30, 10
    doc.recompute()
    ruta = os.path.join(carpeta, nombre + ".FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    bombear(300)
    return ruta


def _abierto(ruta):
    norm = os.path.normcase(os.path.abspath(ruta))
    return [d for d in FreeCAD.listDocuments().values()
            if d.FileName and os.path.normcase(os.path.abspath(d.FileName)) == norm]


def prueba():
    from swui.fork import step_copy
    antes = step_copy.enabled()
    step_copy.set_enabled(True) if hasattr(step_copy, "set_enabled") else \
        FreeCAD.ParamGet(step_copy.PARAMS).SetBool(step_copy.KEY, True)
    original = step_copy.export
    try:
        carpeta = carpeta_temporal()
        ruta = _archivo(carpeta, "Soldada")
        # el usuario abre el archivo justo mientras se escribe el STEP (en el medio de `export`)
        usuario = {}

        def export_con_usuario(doc, filename=None):
            usuario["doc"] = FreeCAD.openDocument(ruta)
            usuario["nombre"] = usuario["doc"].Name
            return original(doc, filename)

        step_copy.export = export_con_usuario
        step_copy.after_save("Soldada", ruta)
        step_copy.export = original
        bombear(1500)
        assert "doc" in usuario, "la prueba no pasó por la exportación con el archivo cerrado"
        abiertos = _abierto(ruta)
        traza("  abiertos con ese archivo: %s" % [d.Name for d in abiertos])
        assert abiertos, "el documento que abrió el usuario se cerró solo al terminar el STEP (#40)"
        assert usuario["nombre"] in FreeCAD.listDocuments(), "el documento del usuario dejó de existir (#40)"
        assert os.path.isfile(step_copy.step_path(ruta)), "no se escribió el STEP"
        import FreeCADGui
        g = FreeCADGui.getDocument(usuario["nombre"])
        assert g is not None and g.mdiViewsOfType("Gui::View3DInventor"), \
            "el documento que abrió el usuario quedó oculto, sin ventana"
        for d in list(FreeCAD.listDocuments().values()):
            FreeCAD.closeDocument(d.Name)
        yield 300
        # sin nadie que lo abra: el oculto que abrió FreeWorks se cierra (no queda en memoria)
        ruta2 = _archivo(carpeta, "Otra")
        step_copy.after_save("Otra", ruta2)
        bombear(800)
        assert not _abierto(ruta2), "quedó abierto (oculto) el archivo que se abrió solo para el STEP"
        sobras = [f for f in os.listdir(carpeta) if f.startswith("~fw_step")]
        assert not sobras, "quedaron archivos de trabajo del STEP en la carpeta: %s" % sobras
        assert os.path.isfile(step_copy.step_path(ruta2)), "no se escribió el STEP del segundo"
    finally:
        step_copy.export = original
        FreeCAD.ParamGet(step_copy.PARAMS).SetBool(step_copy.KEY, antes)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
