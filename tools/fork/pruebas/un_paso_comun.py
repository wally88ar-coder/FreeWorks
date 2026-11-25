# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""Ayudantes de las pruebas de #119 (una herramienta que crea Cuerpos editando una pieza con contenedor deja UN
paso de deshacer y lo nuevo dentro de la pieza): prueba_ventana_conservar_solido_un_paso,
prueba_ventana_reabrir_eliminar_solido_un_paso, prueba_ventana_mover_cara_suelto_un_paso."""
import os

import FreeCAD
from _base import carpeta_temporal, traza
from azar_comun import bombear

V = FreeCAD.Vector


class Pieza:
    """Ensamblaje con un bloque y otra pieza, editando el bloque, ya con su contenedor Parte."""

    def __init__(self, adoc, comp, pdoc, part, view):
        self.adoc, self.comp, self.pdoc, self.part, self.view = adoc, comp, pdoc, part, view

    # --- estado

    def cuerpos(self):
        return set(o.Name for o in self.pdoc.Objects if o.TypeId == "PartDesign::Body")

    def afuera(self):
        """Cuerpos y grupos de la pieza que no están dentro del contenedor (todos, no solo los nuevos)."""
        return sorted(o.Name for o in self.pdoc.Objects
                      if o.TypeId in ("PartDesign::Body", "App::DocumentObjectGroup")
                      and not self.part.hasObject(o, True))

    def foto(self):
        """Qué hay y dónde está, para comparar después de Cancelar."""
        out = []
        for o in self.pdoc.Objects:
            padre, geo = o.getParentGroup(), o.getParentGeoFeatureGroup()
            out.append((o.Name, o.TypeId, getattr(padre, "Name", None), getattr(geo, "Name", None),
                        bool(o.Visibility)))
        return sorted(out)

    def activo(self):
        act = self.view.getActiveObject("pdbody", False)
        return getattr(act[0], "Name", None) if act else None

    def sigue(self, que, espera=1200):
        from swui.fork import edit_part as ep
        bombear(espera)
        assert ep.editing(self.adoc) is self.comp, "%s: salió de Editar pieza" % que
        traza("  %s: sigue editando, Cuerpo activo %s" % (que, self.activo()))

    # --- comprobaciones

    def un_paso(self, que, nombre, antes, nuevos=True):
        """Después de Aceptar: un solo paso nuevo, con su nombre; todo dentro del contenedor; Ctrl+Z / Ctrl+Y."""
        from reglas_paneles import ctrl_y, ctrl_z
        pdoc = self.pdoc
        bombear(1500)  # que corra también el temporizador del contenedor (antes armaba ahí su paso aparte)
        import FreeCADGui
        from swui.fork import panel_guard
        abierto = panel_guard.open_panel()
        if abierto is not None or FreeCADGui.Control.activeDialog():
            aviso = getattr(getattr(abierto, "message", None), "text", lambda: "")()
            raise AssertionError("%s: Aceptar no cerró el panel (%s)" % (que, aviso))
        self.sigue(que)
        creados = self.cuerpos() - antes
        traza("  %s: pasos %s, Cuerpos nuevos %s, fuera de la pieza %s"
              % (que, list(pdoc.UndoNames[:3]), sorted(creados), self.afuera()))
        if nuevos:
            assert creados, "%s: no creó un Cuerpo" % que
        assert pdoc.UndoCount == 1 and pdoc.UndoNames[0] == nombre, (
            "#119: %s dejó %d pasos de deshacer: %s" % (que, pdoc.UndoCount, list(pdoc.UndoNames[:3])))
        assert not self.afuera(), "%s: quedó fuera de la pieza: %s" % (que, self.afuera())
        despues = self.foto()
        ctrl_z(self.adoc)
        self.sigue("%s, Ctrl+Z" % que)
        assert not (self.cuerpos() - antes), "%s: Ctrl+Z no sacó todo: %s" % (que, sorted(self.cuerpos() - antes))
        assert not self.afuera(), "%s: después de Ctrl+Z, fuera de la pieza: %s" % (que, self.afuera())
        ctrl_y(self.adoc)
        self.sigue("%s, Ctrl+Y" % que)
        assert self.cuerpos() - antes == creados, "%s: Ctrl+Y no volvió los Cuerpos" % que
        assert not self.afuera(), "%s: después de Ctrl+Y, fuera de la pieza: %s" % (que, self.afuera())
        assert self.foto() == despues, "%s: Ctrl+Y no dejó todo como después de Aceptar" % que

    def cancelado(self, que, foto, pasos=0):
        """Después de Cancelar: nada nuevo, todo como estaba y sin pasos de deshacer nuevos."""
        bombear(1500)
        self.sigue(que)
        assert self.pdoc.UndoCount == pasos, "%s: Cancelar dejó pasos de deshacer: %s" % (
            que, list(self.pdoc.UndoNames[:3]))
        cambios = sorted(set(self.foto()) ^ set(foto))
        assert not cambios, "%s: Cancelar no dejó todo como estaba: %s" % (que, cambios[:6])
        assert not self.afuera(), "%s: después de Cancelar, fuera de la pieza: %s" % (que, self.afuera())


def informe():
    """Texto de la vista de Informe de FreeCAD (ahí quedan los avisos de C++, p. ej. "go out of the allowed
    scope", que no pasan por FreeCAD.Console de Python)."""
    import FreeCADGui
    from swui.compat import QtWidgets
    rv = FreeCADGui.getMainWindow().findChild(QtWidgets.QTextEdit, "Report view")  # como reglas_paneles
    assert rv is not None, "no encontré la vista de Informe"
    return rv.toPlainText()


def errores_a_la_traza():
    """Lo que el fork escribe con PrintError (p. ej. el detalle de "FreeCAD no pudo armar la operación") va
    también al registro de la prueba."""
    original = FreeCAD.Console.PrintError
    if getattr(original, "_a_la_traza", False):
        return

    def escribir(texto):
        traza("  ERROR en la consola: " + str(texto).strip())
        original(texto)

    escribir._a_la_traza = True
    try:
        FreeCAD.Console.PrintError = escribir
    except Exception:
        pass


def preparar():
    """Generador: arma el ensamblaje, entra a Editar pieza en el bloque y arma su contenedor. Devuelve una Pieza."""
    import piezas_editar as pe
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    from swui.fork import part_container as pc
    errores_a_la_traza()
    c = carpeta_temporal()
    for sub in ("b", "o"):
        os.makedirs(os.path.join(c, sub), exist_ok=True)
    adoc, _asm, (comp, _o) = pe.ensamblaje([pe.bloque(os.path.join(c, "b")), pe.bloque(os.path.join(c, "o"), "Otro")])
    assert ep.start(comp, warn=False), "no entró a Editar pieza"
    yield 800
    pdoc = comp.LinkedObject.Document
    ep.prepare_container(ec.current(adoc))
    yield 800
    part = pc.container(pdoc)
    assert part is not None and hasattr(part, pc.MARK), "no se armó el contenedor de la pieza"
    return Pieza(adoc, comp, pdoc, part, ep._view(adoc))


def partir(p):
    """El Cuerpo del bloque queda en dos pedazos (un corte de 4 mm en el medio), en un paso nativo."""
    pdoc = p.pdoc
    body = pdoc.getObject("Body")
    bb = body.Shape.BoundBox
    pdoc.openTransaction("Partir")
    corte = body.newObject("PartDesign::SubtractiveBox", "Partir")
    corte.Length, corte.Width, corte.Height = 4, bb.YLength + 20, bb.ZLength + 20
    corte.Placement.Base = body.Placement.inverse().multVec(V(bb.Center.x - 2, bb.YMin - 10, bb.ZMin - 10))
    pdoc.commitTransaction()
    pdoc.recompute()
    assert len(body.Shape.Solids) == 2, "el bloque no quedó en dos pedazos: %d" % len(body.Shape.Solids)
    return body


def segundo(p):
    """Otro Cuerpo (una caja aparte) dentro del contenedor, en un paso nativo."""
    pdoc = p.pdoc
    pdoc.openTransaction("Segundo")
    seg = pdoc.addObject("PartDesign::Body", "Segundo")
    p.part.addObject(seg)
    caja = seg.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length = caja.Width = caja.Height = 15
    caja.Placement.Base = V(0, 0, 60)
    pdoc.commitTransaction()
    pdoc.recompute()
    assert seg.Shape.Solids, "el segundo Cuerpo no tiene sólido"
    return seg


def pedazo(body, i):
    """Un punto dentro del pedazo i del Cuerpo (como el que guarda Eliminar/Conservar al elegir una cara)."""
    from swui.fork import delete_bodies as db
    q = db.inner_point(body.Shape.Solids[i])
    return [q.x, q.y, q.z]


def abrir_eliminar():
    """Generador: abre Eliminar/Conservar sólido (sin nada elegido) y devuelve el panel."""
    import FreeCADGui
    from reglas_paneles import esperar_panel
    from swui import ribbon
    from swui.fork import panel_guard
    FreeCADGui.Selection.clearSelection()
    ribbon._run("SWUI_DeleteBodies")
    yield from esperar_panel()
    panel = panel_guard.open_panel()
    assert type(panel).__name__ == "DeleteBodiesPanel", "no abrió Eliminar/Conservar sólido: %s" % type(panel).__name__
    return panel
