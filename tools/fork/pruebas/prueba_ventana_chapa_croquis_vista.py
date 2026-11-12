# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#20): Desdoblar (croquis sobre el desarrollo) y "Editar croquis sobre el
desarrollo" de un Corte desdoblado apagan, mientras el croquis está abierto, "mostrar apoyo" y
"ocultar dependientes"; al salir del croquis vuelven a como estaban (antes quedaban apagadas para
siempre en ese croquis)."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from casos_chapa2 import CorteDesdoblado  # noqa: E402

PROPS = ("ShowSupport", "HideDependent")


def prueba():
    import FreeCADGui
    from swui.fork import sheet_panels
    doc = FreeCAD.newDocument("CroquisVista")
    caso = CorteDesdoblado()
    yield from caso.preparar(doc)
    doc = caso.doc
    corte = doc.getObject(caso.hecho_inicial)
    sk = corte.Sketch
    vo = sk.ViewObject
    assert all(getattr(vo, p) for p in PROPS), "después de Desdoblar + Doblar: %s" % {p: getattr(vo, p) for p in PROPS}
    from PySide import QtCore
    QtCore.QTimer.singleShot(0, lambda: sheet_panels.edit_cut_sketch(corte))
    yield 2500
    vp = FreeCADGui.ActiveDocument.getInEdit()
    assert vp is not None and vp.Object is sk, "no se abrió el croquis del corte"
    assert not any(getattr(vo, p) for p in PROPS), "con el croquis abierto deberían estar apagadas"
    FreeCADGui.ActiveDocument.resetEdit()
    yield 3000
    if FreeCADGui.Control.activeDialog():
        FreeCADGui.Control.closeDialog()
    yield 500
    assert all(getattr(vo, p) for p in PROPS), "al salir no volvieron: %s (#20)" % {p: getattr(vo, p) for p in PROPS}


from _base import ejecutar  # noqa: E402
ejecutar(globals())
