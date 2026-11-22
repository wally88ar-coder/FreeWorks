# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#113, el mecanismo: editando una pieza, la pieza y el ensamblaje comparten los pasos de deshacer ("-> paso" en
el ensamblaje). Si uno de los dos tiene un paso propio más nuevo (un cambio solo en la pieza, o solo en el
ensamblaje, como mover un componente), Ctrl+Z / Ctrl+Y con el teclado, desde la vista del ensamblaje o desde la de la
pieza, deshace y rehace de a un paso, del más nuevo al más viejo, SIN el cartel de FreeCAD "Hay transacciones de
grupo... Sí/No/Abort" (SW nunca pregunta), y al final la pieza y el ensamblaje quedan como al principio."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from deshacer_comun import al_frente, atajo, visibles  # noqa: E402

V = FreeCAD.Vector


def _foto(pdoc, asm, uno):
    """Lo que cambia en esta prueba: el largo del Extruir de la pieza, el nombre visible de la pieza y la ubicación
    del componente."""
    pad = pdoc.getObject("Extruir")
    return (round(float(pad.Length), 6), pad.Label, tuple(round(x, 6) for x in uno.Placement.Base))


def _paso_pieza(pdoc, valor):
    pdoc.openTransaction("Solo pieza %s" % valor)
    pdoc.getObject("Extruir").Label = "Extruir %s" % valor
    pdoc.commitTransaction()


def _paso_ensamblaje(doc, uno, dx):
    doc.openTransaction("Mover componente")
    uno.Placement.Base = uno.Placement.Base + V(dx, 0, 0)
    doc.commitTransaction()


def _compartido(pdoc, valor):
    """Un cambio en la pieza que también llega al ensamblaje ("-> ..."), como Modificar cota."""
    pdoc.openTransaction("Compartido %s" % valor)
    pdoc.getObject("Extruir").Length = valor
    pdoc.recompute()
    pdoc.commitTransaction()


def _vista_pieza(pdoc):
    """Una vista de la pieza al frente (como cuando FreeCAD trae la ventana de la pieza)."""
    import FreeCADGui
    g = FreeCADGui.getDocument(pdoc.Name)
    vs = g.mdiViewsOfType("Gui::View3DInventor")
    if not vs:
        g.createView("Gui::View3DInventor")
        bombear(500)
    return al_frente(pdoc)


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from swui.compat import QtCore
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, (uno, dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    doc.recompute()
    FreeCAD.setActiveDocument(doc.Name)
    bombear(500)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % uno.Name)
    FreeCADGui.runCommand("SWUI_EditPart")
    bombear(800)
    assert ep.editing(doc) is uno, "no entró a Editar pieza"
    pdoc = uno.LinkedObject.Document
    yield 100

    for desde in ("ensamblaje", "pieza"):
        for orden in ("pieza", "ensamblaje"):
            traza("== paso propio de la %s más nuevo; Ctrl+Z desde la vista de la %s" % (orden, desde))
            vista = al_frente(doc)
            inicio = _foto(pdoc, asm, uno)
            vis = visibles(asm)
            n_p, n_a = pdoc.UndoCount, doc.UndoCount
            _compartido(pdoc, 22)
            if orden == "pieza":
                _paso_ensamblaje(doc, uno, 5)
                _compartido(pdoc, 24)
                _paso_pieza(pdoc, "x")
            else:
                _paso_pieza(pdoc, "x")
                _compartido(pdoc, 24)
                _paso_ensamblaje(doc, uno, 5)
            bombear(300)
            hecho = _foto(pdoc, asm, uno)
            traza("  pasos pieza %s / ensamblaje %s" % (pdoc.UndoNames[:5], doc.UndoNames[:5]))
            if desde == "pieza":
                vista = _vista_pieza(pdoc)
            carteles = []
            for n in range(12):
                if pdoc.UndoCount <= n_p and doc.UndoCount <= n_a:
                    break
                carteles += atajo(vista, QtCore.Qt.Key.Key_Z)
                traza("  Ctrl+Z: pieza %s / ensamblaje %s -> %s" % (pdoc.UndoNames[:2], doc.UndoNames[:2],
                                                                   _foto(pdoc, asm, uno)))
            for t in carteles:
                traza("    cartel: %s" % t[:200].replace("\n", " "))
            assert not carteles, "#113 (%s más nuevo, desde la %s): Ctrl+Z mostró el cartel: %s" % (
                orden, desde, carteles[0][:150])
            assert _foto(pdoc, asm, uno) == inicio, "Ctrl+Z no volvió al principio: %s en vez de %s" % (
                _foto(pdoc, asm, uno), inicio)
            assert visibles(asm) == vis, "Ctrl+Z ocultó un componente"
            for n in range(12):
                if not pdoc.RedoCount and not doc.RedoCount:
                    break
                if not pdoc.RedoCount:
                    # desde la ventana de la pieza solo se rehace lo de la pieza (como una ventana de pieza en SW);
                    # lo propio del ensamblaje, desde su vista (la que se ve mientras se edita)
                    vista = al_frente(doc)
                carteles += atajo(vista, QtCore.Qt.Key.Key_Y)
            assert not carteles, "#113 (%s más nuevo, desde la %s): Ctrl+Y mostró el cartel: %s" % (
                orden, desde, carteles[0][:150])
            assert _foto(pdoc, asm, uno) == hecho, "Ctrl+Y no rehízo todo: %s en vez de %s" % (
                _foto(pdoc, asm, uno), hecho)
            # dejar todo como al principio para la vuelta siguiente (sin pasos de rehacer)
            for n in range(12):
                if pdoc.UndoCount <= n_p and doc.UndoCount <= n_a:
                    break
                atajo(al_frente(doc), QtCore.Qt.Key.Key_Z)
            pdoc.clearUndos()
            doc.clearUndos()
            yield 100
    ep.stop(doc)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
