# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana: pieza con dos configuraciones; una operación nueva (Redondeo con el panel del
fork y Vaciado con el panel nativo) queda suprimida en la otra configuración, como SW, y esa
supresión va en el MISMO paso de deshacer que la operación: un solo Ctrl+Z saca la operación y su
columna de la tabla (la tabla queda como antes), y Ctrl+Y trae las dos (suprimida en la otra
configuración). Cancelar el panel (también después de abrir y cerrar Ecuaciones) deja la tabla
como estaba. Issue #47, decisión del usuario 11/11 ("igual que SW")."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from comun import caja  # noqa: E402

E = {}


def contenido(doc):
    from swui.fork import configurations as cf
    t = cf.table(doc)
    return {c: t.getContents(c) for c in t.getUsedCells()} if t is not None else {}


def caras_arriba(obj):
    out = []
    for i, f in enumerate(obj.Shape.Faces):
        if f.Surface.__class__.__name__ == "Plane":
            n = f.normalAt(*f.ParameterRange[0:3:2])
            if abs(n.z - 1.0) < 1e-6:
                out.append("Face%d" % (i + 1))
    return out


def prueba():
    import FreeCADGui
    from swui.fork import configurations as cf
    doc = FreeCAD.newDocument("ConfigNueva")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    E["caja"] = caja(body, "Caja", 40, 30, 20)
    doc.recompute()
    cf.ensure(doc)
    E["primera"] = cf.active(doc)
    E["otra"] = cf.add(doc, "Otra")  # queda activa: la operación nueva vive en "Otra"
    doc.recompute()
    E["doc"] = doc

    # primero con Ctrl+Z / Ctrl+Y (el error), después uno sin deshacer y el panel nativo (Vaciado al
    # final: después de vaciar, las aristas cambian y el chaflán de prueba no entra)
    pasos = cancelar_con_ecuaciones(False) + cancelar_con_ecuaciones()
    pasos += caso("PartDesign::Fillet", "PartDesign_Fillet", "edge")
    pasos += caso("PartDesign::Chamfer", "PartDesign_Chamfer", "edge", deshacer=False)
    pasos += caso("PartDesign::Thickness", "PartDesign_Thickness", "cara")
    return pasos


def cancelar_con_ecuaciones(con_ecuaciones=True):
    """Panel de Redondeo abierto, abrir y cerrar Ecuaciones, Cancelar el panel: la tabla queda
    como estaba (lo encontró el mono el 11/11 con el arreglo de #47)."""
    import FreeCADGui
    from reglas_paneles import tocar

    def abrir():
        doc = E["doc"]
        E["antes"] = contenido(doc)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(doc.getObject("Cuerpo").Tip, "Edge1")
        from swui import ribbon
        ribbon._run("PartDesign_Fillet")

    def ecuaciones():
        from _base import traza
        from swui.fork import equations
        dlg = equations.show_dialog(E["doc"])
        traza("    con Ecuaciones abierto: %s" % ("tabla igual" if contenido(E["doc"]) == E["antes"] else "TABLA CAMBIÓ"))
        dlg.reject()
        traza("    tras cerrar Ecuaciones: %s" % ("tabla igual" if contenido(E["doc"]) == E["antes"] else "TABLA CAMBIÓ"))

    def cancelar():
        assert tocar(rechazar=True), "no encontré Cancelar"

    def comprobar():
        doc = E["doc"]
        assert not FreeCADGui.Control.activeDialog(), "el panel quedó abierto"
        assert not [o for o in doc.Objects if o.TypeId == "PartDesign::Fillet"], "quedó el redondeo"
        d = contenido(doc)
        assert d == E["antes"], "Cancelar con Ecuaciones dejó la tabla distinta: %s" % (
            sorted(set(d.items()) ^ set(E["antes"].items()))[:4])

    return [(800, abrir), (2500, ecuaciones), (1500, cancelar), (2000, comprobar)]


def suprimida_solo_en_la_otra(doc, op, tipo, cuando, activar=False):
    """En la tabla: suprimida (1) en la primera configuración y no (0) en la otra. Con activar,
    además pasa de una a otra como el usuario (eso deja pasos de deshacer: solo al final)."""
    from swui.fork import configurations as cf
    valores = {n: cf.value_in(doc, ("sup", op), n) for n in (E["primera"], E["otra"])}
    assert valores[E["primera"]] and not valores[E["otra"]], "%s (%s): en la tabla: %s" % (tipo, cuando, valores)
    if not activar:
        return
    cf.activate(doc, E["primera"])
    doc.recompute()
    en_primera = op.Suppressed
    cf.activate(doc, E["otra"])
    doc.recompute()
    assert en_primera, "%s (%s): en «%s» no quedó suprimida" % (tipo, cuando, E["primera"])
    assert not op.Suppressed, "%s (%s): en «%s» quedó suprimida" % (tipo, cuando, E["otra"])


def caso(tipo, comando, sub, deshacer=True):
    import FreeCADGui
    from reglas_paneles import ctrl_y, ctrl_z, tocar
    from swui.fork import configurations as cf

    def abrir():
        doc = E["doc"]
        E["antes"] = contenido(doc)
        E["undo"] = doc.UndoCount
        punta = doc.getObject("Cuerpo").Tip
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(punta, "Edge1" if sub == "edge" else caras_arriba(punta)[0])
        from swui import ribbon
        ribbon._run(comando)

    def aceptar():
        assert FreeCADGui.Control.activeDialog(), "%s: no se abrió el panel" % tipo
        assert tocar(), "%s: no encontré Aceptar" % tipo

    def despues_de_aceptar():
        doc = E["doc"]
        assert not FreeCADGui.Control.activeDialog(), "%s: el panel quedó abierto" % tipo
        nuevas = [o for o in doc.Objects if o.TypeId == tipo]
        assert nuevas, "%s: no quedó la operación" % tipo
        E["op"] = nuevas[-1].Name
        assert cf.bound_alias(nuevas[-1], "Suppressed") is not None, \
            "%s: no quedó suprimida en la otra configuración" % tipo
        assert contenido(doc) != E["antes"], "%s: la tabla no cambió" % tipo
        assert doc.UndoCount == E["undo"] + 1, \
            "%s: la operación y su supresión no quedaron en un solo paso: %s" % (tipo, doc.UndoNames[:3])
        if not deshacer:
            suprimida_solo_en_la_otra(doc, nuevas[-1], tipo, "sin deshacer", activar=True)
            return
        suprimida_solo_en_la_otra(doc, nuevas[-1], tipo, "al aceptar")
        ctrl_z(doc)
        doc.recompute()

    def despues_de_deshacer():
        doc = E["doc"]
        assert doc.getObject(E["op"]) is None, "%s: Ctrl+Z no sacó la operación" % tipo
        d = contenido(doc)
        assert d == E["antes"], "%s: Ctrl+Z dejó la tabla distinta (#47): %s" % (
            tipo, sorted(set(d.items()) ^ set(E["antes"].items()))[:4])
        ctrl_y(doc)
        doc.recompute()

    def despues_de_rehacer():
        doc = E["doc"]
        op = doc.getObject(E["op"])
        assert op is not None, "%s: Ctrl+Y no trajo la operación" % tipo
        assert cf.bound_alias(op, "Suppressed") is not None, "%s: Ctrl+Y la trajo sin la supresión" % tipo
        suprimida_solo_en_la_otra(doc, op, tipo, "tras Ctrl+Y", activar=True)

    if not deshacer:
        return [(800, abrir), (2500, aceptar), (2000, despues_de_aceptar)]
    return [(800, abrir), (2500, aceptar), (2000, despues_de_aceptar), (1500, despues_de_deshacer),
            (1500, despues_de_rehacer)]


from _base import ejecutar  # noqa: E402
ejecutar(globals())
