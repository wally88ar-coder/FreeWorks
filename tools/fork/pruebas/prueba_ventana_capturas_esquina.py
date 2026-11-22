# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Capturas de referencia de la esquina de confirmación (22/11; plan de calidad, paso 9): una foto del cuadro
de botones de la esquina en cada caso: panel abierto (✓ ✗), croquis (Salir del croquis / Cancelar croquis), chapa
aplanada (Salir de aplanar) y Editar pieza (Volver al ensamblaje). Se fotografía el cuadro solo (no el dibujo 3D de
atrás, que se corre un píxel de una corrida a otra) y se compara con la aprobada (`capturas/aprobadas/`), como
`prueba_ventana_capturas`.
Mientras el usuario no las apruebe, cada foto queda en `capturas/nuevas/` y la prueba lo anota sin fallar (son de
esta entrega; aprobarlas = copiarlas a `aprobadas/`; desde ahí se comparan). Además deja en `nuevas/` una foto
"_contexto" de la esquina sobre la vista, para mirarla: esa no se compara nunca.
Lo que esto controla: que un cambio no desarme la esquina (íconos, orden, tamaño). Lo que no: si se parece a SW."""
TIPO = "completa"

import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from deshacer_comun import al_frente  # noqa: E402
from esquina_comun import claves  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
APROBADAS = os.path.join(AQUI, "capturas", "aprobadas")
NUEVAS = os.path.join(AQUI, "capturas", "nuevas")
TOLERANCIA = 0.0002  # como prueba_ventana_capturas
DIFERENTE = 40


def _comparar(nombre, img, problemas, pendientes):
    from PySide import QtGui
    img = img.convertToFormat(QtGui.QImage.Format.Format_RGB32)
    os.makedirs(NUEVAS, exist_ok=True)
    ruta_ref = os.path.join(APROBADAS, nombre + ".png")
    if not os.path.exists(ruta_ref):
        img.save(os.path.join(NUEVAS, nombre + ".png"))
        pendientes.append(nombre)
        return
    ref = QtGui.QImage(ruta_ref).convertToFormat(QtGui.QImage.Format.Format_RGB32)
    if ref.size() != img.size():
        img.save(os.path.join(NUEVAS, nombre + ".png"))
        problemas.append("%s: cambió el tamaño (%sx%s, aprobada %sx%s)" % (
            nombre, img.width(), img.height(), ref.width(), ref.height()))
        return
    distintos = comparados = 0
    marca = QtGui.QImage(img)
    for y in range(img.height()):
        for x in range(img.width()):
            comparados += 1
            a, b = img.pixel(x, y), ref.pixel(x, y)
            if a != b and max(abs(((a >> s) & 255) - ((b >> s) & 255)) for s in (0, 8, 16)) > DIFERENTE:
                distintos += 1
                marca.setPixel(x, y, 0xFFFF0000)
    fraccion = distintos / float(max(1, comparados))
    traza("  %s: %.2f %% distinto" % (nombre, 100 * fraccion))
    if fraccion > TOLERANCIA:
        img.save(os.path.join(NUEVAS, nombre + ".png"))
        marca.save(os.path.join(NUEVAS, nombre + "_diferencias.png"))
        problemas.append("%s: cambió el %.2f %% (ver capturas/nuevas)" % (nombre, 100 * fraccion))


def _foto(nombre, quiero, problemas, pendientes):
    """La foto del cuadro de la esquina (comparada) y una de contexto (para mirar, no se compara)."""
    import FreeCADGui
    from swui.compat import QtCore
    from swui.fork import confirm_corner as cc
    bombear(800)
    assert claves() == quiero, "%s: la esquina tiene %s, quiero %s" % (nombre, claves(), quiero)
    box = cc.widget()
    _comparar(nombre, box.grab().toImage(), problemas, pendientes)
    mw = FreeCADGui.getMainWindow()
    g = box.geometry()
    zona = QtCore.QRect(max(0, g.x() - 260), max(0, g.y() - 10), g.width() + 260 + 140, g.height() + 120)
    os.makedirs(NUEVAS, exist_ok=True)
    mw.grab(zona).save(os.path.join(NUEVAS, nombre + "_contexto.png"))


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from menu_comun import pieza
    from swui import ribbon
    from swui.fork import confirm_corner as cc
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    from swui.fork import sheet_panels
    problemas, pendientes = [], []
    assert cc.enabled(), "la esquina viene apagada de fábrica"
    c = carpeta_temporal()

    traza("panel abierto (Redondeo)")
    doc, body, _sk, pad = pieza()
    al_frente(doc).viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(800)
    FreeCADGui.Selection.clearSelection()
    ec.select(pad, "Edge1")
    ribbon._run("PartDesign_Fillet")
    bombear(1500)
    _foto("esquina_panel", ["ok", "cancel"], problemas, pendientes)
    FreeCADGui.Control.closeDialog()
    bombear(800)
    yield 100

    traza("croquis")
    tope = body.Tip
    arriba = [i for i, f in enumerate(tope.Shape.Faces)
              if f.normalAt(0, 0).z > 0.99 and abs(f.BoundBox.ZMax - tope.Shape.BoundBox.ZMax) < 1e-6]
    FreeCADGui.Selection.clearSelection()
    ec.select(tope, "Face%d" % (arriba[0] + 1))
    ribbon._run("PartDesign_NewSketch")
    bombear(2500)
    _foto("esquina_croquis", ["exit_sketch", "cancel_sketch"], problemas, pendientes)
    FreeCADGui.runCommand("Sketcher_LeaveSketch")
    bombear(1500)
    yield 100

    traza("chapa aplanada")
    cdoc = FreeCAD.openDocument(pe.chapa(c))
    bombear(1500)
    al_frente(cdoc)
    FreeCADGui.SendMsgToActiveView("ViewFit")
    cuerpo = [o for o in cdoc.Objects if o.TypeId == "PartDesign::Body"][0]
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(cuerpo)
    sheet_panels.toggle_flat()
    bombear(2500)
    _foto("esquina_aplanado", ["exit_flat"], problemas, pendientes)
    sheet_panels.exit_flat(sheet_panels.flattened(cdoc))
    bombear(1000)
    yield 100

    traza("Editar pieza")
    adoc, asm, (uno, _dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    uno.Placement.Base = FreeCAD.Vector(30, 20, 10)
    adoc.recompute()
    al_frente(adoc).viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(adoc.Name, asm.Name, "%s.Extruir.Face6" % uno.Name)
    FreeCADGui.runCommand("SWUI_EditPart")
    bombear(1500)
    assert ep.editing(adoc) is uno, "no entró a Editar pieza"
    _foto("esquina_editar_pieza", ["back_assembly"], problemas, pendientes)
    ep.stop(adoc)
    bombear(1000)

    assert not problemas, "\n".join(problemas)
    if pendientes:
        traza("  sin aprobada todavía (quedan en capturas/nuevas, no frena): %s" % ", ".join(pendientes))


from _base import ejecutar  # noqa: E402
ejecutar(globals())
