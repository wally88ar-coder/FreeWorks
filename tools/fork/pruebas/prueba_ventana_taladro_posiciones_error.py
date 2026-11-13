# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#17): Taladro nuevo cuya posición queda fuera de la pieza (vista previa en
error) y "Editar posiciones": el taladro NO se borra, se abre el croquis de las posiciones y al
salir del croquis vuelve el panel del taladro (antes se cancelaba: el taladro se borraba y el
panel no volvía). Y como SW 2018 (probado con el mouse el 12/11): si después se Cancela, el
taladro nuevo no queda (acá el croquis de los centros queda: es del usuario, elegido antes; el que
arma el asistente se va con el taladro, ver prueba_taladro_cancelar_sin_aceptar); un taladro que ya
estaba aceptado, editado, pasado por "Editar posiciones" y cancelado, queda. Y el croquis que arma
el asistente ("Asistente para taladro" sin nada elegido) queda marcado como del taladro."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from casos_grupo3 import _croquis  # noqa: E402
from casos_pieza import armar_pieza  # noqa: E402
from reglas_paneles import esperar_panel  # noqa: E402


def prueba():
    import FreeCADGui
    from swui import ribbon
    from swui.fork import hole_panel
    from swui.fork import panel_guard
    doc = FreeCAD.newDocument("TaladroError")
    body, _hueco = armar_pieza(doc)
    sk = _croquis(body, "XY_Plane", 20, [("circulo", -10, -5, 1)])
    doc.recompute()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(sk)
    ribbon._run("PartDesign_Hole")
    yield from esperar_panel()
    yield 800
    p = panel_guard.open_panel()
    assert isinstance(p, hole_panel.HolePanel), "no se abrió el panel SW del taladro: %s" % type(p).__name__
    assert p.created and not p.wizard, "el taladro nuevo no cuenta como recién creado (o el croquis del usuario como del asistente)"
    # vista previa en error: profundidad 0 ("Invalid hole depth"; el campo no la deja escribir, se
    # fuerza para armar el caso: un taladro lejos de la pieza NO queda en error en FreeCAD 1.1.4)
    p.depth.setMinimum(0.0)
    p.depth.setValue(0.0)
    p.preview()
    yield 300
    assert not p.valid, "la vista previa no quedó en error: la prueba no prueba #17"
    hole = p.obj.Name
    p.edit_positions()
    yield 1500
    assert doc.getObject(hole) is not None, "Editar posiciones con error borró el taladro (#17)"
    vp = FreeCADGui.ActiveDocument.getInEdit()
    assert vp is not None and vp.Object is sk, "no se abrió el croquis de las posiciones"
    FreeCADGui.ActiveDocument.resetEdit()
    yield 1500
    assert FreeCADGui.Control.activeDialog(), "al salir del croquis no volvió el panel del taladro (#17)"
    p2 = panel_guard.open_panel()
    assert p2 is not None and p2.obj.Name == hole, "volvió otro panel: %r" % (p2,)
    p2.reject()
    FreeCADGui.Control.closeDialog()
    yield 500
    assert doc.getObject(hole) is None, "Cancelar dejó el taladro nuevo después de Editar posiciones (SW lo borra)"
    assert doc.getObject(sk.Name) is not None, "Cancelar se llevó el croquis de los centros"
    assert not FreeCADGui.Control.activeDialog(), "quedó un panel abierto"

    # taladro ya aceptado: editarlo, Editar posiciones, volver y Cancelar -> queda
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(sk)
    ribbon._run("PartDesign_Hole")
    yield from esperar_panel()
    yield 800
    p = panel_guard.open_panel()
    assert isinstance(p, hole_panel.HolePanel), "no se abrió el panel del segundo taladro"
    assert p.accept(), "no se pudo aceptar el taladro bueno"
    FreeCADGui.Control.closeDialog()
    yield 800
    hole = p.obj.Name
    FreeCADGui.ActiveDocument.setEdit(doc.getObject(hole))
    yield from esperar_panel()
    yield 800
    p = panel_guard.open_panel()
    assert isinstance(p, hole_panel.HolePanel) and not p.is_new, "editar el taladro no abrió su panel"
    p.edit_positions()
    yield 1500
    FreeCADGui.ActiveDocument.resetEdit()
    yield 1500
    p2 = panel_guard.open_panel()
    assert p2 is not None and p2.obj.Name == hole, "no volvió el panel del taladro existente"
    assert not p2.unconfirmed, "un taladro ya aceptado quedó como sin aceptar"
    p2.reject()
    FreeCADGui.Control.closeDialog()
    yield 500
    assert doc.getObject(hole) is not None, "Cancelar borró un taladro que ya estaba aceptado"

    # el croquis que arma el asistente (pick_plane lo arma para el comando del taladro) es del taladro
    from swui import pick_plane
    sk2 = _croquis(body, "XY_Plane", 20, [])
    doc.recompute()
    assert not hole_panel.is_hole_sketch(sk2), "un croquis cualquiera quedó como del taladro"
    pick_plane.arm("PartDesign_Hole", sk2)
    pick_plane._disarm()
    assert hole_panel.is_hole_sketch(sk2), "el croquis del asistente no quedó marcado como del taladro"
    assert not hole_panel.is_hole_sketch(sk), "el croquis elegido por el usuario quedó como del taladro"
    hole_panel.take_hole_sketch(sk2)
    # el escucha de creación anota los taladros que crea el comando (el primero de esta prueba)
    assert hole_panel._created_observer is not None, "no está el escucha de creación de taladros"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
