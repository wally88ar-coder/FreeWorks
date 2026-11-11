# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Miembro estructural (Issue #7): con dos líneas elegidas y la vista previa hecha, cambiar la
medida del perfil y apretar Aceptar ENSEGUIDA (antes de los 0,35 s de la vista previa): los
caños que quedan son de la medida nueva, no de la vieja. Y con el panel vacío, Aceptar no lo
cierra: queda abierto con un aviso adentro y sin errores de Python en el informe (Issue #19).
Las dos líneas se eligen de una (como con un recuadro): se suman las dos (antes el segundo aviso de
selección sacaba las del primero)."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from comun import croquis_rectangulo  # noqa: E402

E = {}


def prueba():
    import FreeCADGui
    from swui import ribbon
    from swui.fork import panel_guard
    from swui.fork import weldments as w

    from reglas_paneles import informe_largo, mensajes_nuevos

    doc = FreeCAD.newDocument("AceptarRapido")
    E["doc"] = doc
    E["informe"] = informe_largo()
    E["sk"], _c = croquis_rectangulo(doc, 600, 400)
    doc.recompute()

    def abrir_vacio():
        FreeCADGui.Selection.clearSelection()
        ribbon._run("SWUI_WeldMember")

    def aceptar_vacio():
        p = panel_guard.open_panel()
        assert p is not None, "no se abrió el panel de Miembro estructural"
        E["p"] = p
        assert p.accept() is False, "con el panel vacío, Aceptar lo cerró (tiene que quedar abierto)"
        msg = getattr(p, "message", None)
        assert msg is not None and msg.isVisible() and msg.text(), "no hay aviso adentro del panel"
        assert panel_guard.open_panel() is p, "el panel no siguió abierto"

    def elegir():
        FreeCADGui.Selection.addSelection(E["sk"], "Edge1")
        FreeCADGui.Selection.addSelection(E["sk"], "Edge2")

    def cambiar_y_aceptar_ya():
        p = E["p"]
        from swui.fork import panel_guard as _pg
        assert p.bodies, "no hubo vista previa: edges=%s done=%s alive=%s orphan=%s sel=%s" % (p.edges, getattr(p, "_done", None), _pg.alive(p), getattr(p._sel, "_swui_orphan", None), [(s.ObjectName, s.SubElementNames) for s in FreeCADGui.Selection.getSelectionEx()])
        nueva = p.size.count() - 1 if p.size.currentIndex() != p.size.count() - 1 else 0
        p.size.setCurrentIndex(nueva)
        E["medida"] = p.size.currentText()
        assert p.accept() is not False, "no aceptó"  # sin esperar la vista previa

    def comprobar():
        doc = E["doc"]
        miembros = w.members(doc)
        assert len(miembros) == 2, [m.Label for m in miembros]
        malas = [(m.Label, m.SWUI_WeldSize) for m in miembros if m.SWUI_WeldSize != E["medida"]]
        assert not malas, "quedaron caños de la medida vieja: %s (se eligió %s)" % (malas, E["medida"])
        assert all(m.Shape.isValid() for m in miembros)
        assert not FreeCADGui.Control.activeDialog(), "quedó un panel abierto"
        malos = mensajes_nuevos(E["informe"])
        assert not malos, "errores en el informe: %s" % malos[:5]

    return [(500, abrir_vacio), (1800, aceptar_vacio), (300, elegir), (1500, cambiar_y_aceptar_ya),
            (1500, comprobar)]


from _base import ejecutar  # noqa: E402
ejecutar(globals())
