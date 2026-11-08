# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana de FreeCAD y el banco FreeWorks: un cubo, una arista elegida, Redondeo desde
la cinta abre el panel SW del fork; Cancelar lo cierra, no queda ningún redondeo en el documento,
el cubo sigue con su volumen, no queda ningún diálogo abierto y Deshacer no tiene un paso nuevo."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from _base import modal_abierto  # noqa: E402
from comun import caja, cerca  # noqa: E402

E = {}


def prueba():
    import FreeCADGui
    doc = FreeCAD.newDocument("Redondeo")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    E["caja"] = caja(body, "Caja", 20, 20, 20)
    doc.recompute()
    E["doc"], E["undo"] = doc, doc.UndoCount

    def abrir():
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(E["caja"], "Edge1")
        from swui import ribbon
        ribbon._run("PartDesign_Fillet")

    def mirar_y_cancelar():
        from swui.fork import panel_guard
        panel = panel_guard.open_panel()
        assert panel is not None, "no se abrió el panel del fork (¿panel nativo?)"
        assert [o for o in E["doc"].Objects if o.TypeId == "PartDesign::Fillet"], "no hay redondeo en vista previa"
        panel.reject()

    def comprobar():
        doc = E["doc"]
        assert not FreeCADGui.Control.activeDialog(), "quedó un panel abierto"
        assert modal_abierto() is None, "quedó un diálogo abierto"
        assert not [o for o in doc.Objects if o.TypeId == "PartDesign::Fillet"], "Cancelar dejó el redondeo"
        assert cerca(E["caja"].Shape.Volume, 8000, 0.5), E["caja"].Shape.Volume
        assert doc.UndoCount == E["undo"], "Cancelar dejó un paso de deshacer: %s" % doc.UndoNames

    return [(800, abrir), (2500, mirar_y_cancelar), (1500, comprobar)]


from _base import ejecutar  # noqa: E402
ejecutar(globals())
