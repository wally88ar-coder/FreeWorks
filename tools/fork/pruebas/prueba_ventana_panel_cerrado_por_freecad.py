# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#12): si FreeCAD cierra por su cuenta un panel de Mover/Copiar sólidos,
Eliminar/Conservar sólidos o Mover cara (como con "Sí" a "ya hay un diálogo abierto", sin su
Cancelar), el Redondeo siguiente abre igual el panel SW (no el nativo en inglés)."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from comun import caja  # noqa: E402
from reglas_paneles import esperar_panel  # noqa: E402


def prueba():
    import FreeCADGui
    from swui import ribbon
    from swui.fork import dress_up_panel as dp
    from swui.fork import panel_guard
    doc = FreeCAD.newDocument("PanelCerrado")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    box = caja(body, "Caja", 20, 20, 20)
    doc.recompute()
    for comando in ("SWUI_MoveBodies", "SWUI_DeleteBodies", "SWUI_MoveFace"):
        FreeCADGui.Selection.clearSelection()
        ribbon._run(comando)
        yield from esperar_panel()
        assert FreeCADGui.Control.activeDialog(), "%s no abrió su panel" % comando
        FreeCADGui.Control.closeDialog()  # como FreeCAD con "Sí": sin el Cancelar del panel
        yield 800
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(box, "Edge1")
        ribbon._run("PartDesign_Fillet")
        yield from esperar_panel()
        yield 600
        p = panel_guard.open_panel()
        assert isinstance(p, dp.FilletPanel), \
            "después de cerrar %s por FreeCAD, Redondeo abrió %s (panel nativo, #12)" % (comando, type(p).__name__)
        p.reject()
        FreeCADGui.Control.closeDialog()
        yield 800
        assert not [o for o in doc.Objects if o.TypeId == "PartDesign::Fillet"], "quedó un redondeo"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
