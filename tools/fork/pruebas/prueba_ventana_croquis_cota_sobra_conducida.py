# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#93, como el SW 2018 del usuario ("Configurar como conducida de forma predeterminada"): con
Cota inteligente sobre la recta de un oblongo cuyo largo ya está fijado, la cota provisoria
queda conducida (el croquis no se pone redundante ni rojo) mientras se mueve; al ubicarla queda
conducida, sin el cuadro "Insertar longitud", en un solo paso de deshacer (Deshacer la saca,
Rehacer la devuelve conducida). Sobre un círculo que ya tiene radio, igual; Esc a mitad de camino
no deja nada. Si después del primer clic se elige otra entidad (la horizontal de arriba), la cota
pasa a ser la distancia entre las dos, que no sobra: queda conducente y pide su valor como
siempre. Guardar, cerrar y abrir: las dos cotas siguen igual y el archivo no queda modificado."""
TIPO = "completa"

import os  # noqa: E402

import FreeCAD  # noqa: E402

import croquis_comun as cc  # noqa: E402
from _base import carpeta_temporal  # noqa: E402

E = {"modales": [], "todos": []}
V = FreeCAD.Vector
DIMS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter")


def _vigilar():
    """Cada 200 ms: anota y acepta cualquier cuadro modal (el de 'Insertar longitud')."""
    from PySide import QtCore, QtWidgets

    def mirar():
        m = QtWidgets.QApplication.activeModalWidget()
        if m is None:
            return
        E["modales"].append(m.windowTitle())
        E["todos"].append(m.windowTitle())
        cajas = m.findChildren(QtWidgets.QDialogButtonBox)
        boton = cajas[0].button(QtWidgets.QDialogButtonBox.StandardButton.Ok) if cajas else None
        if boton is not None:
            boton.click()
        else:
            m.accept()

    t = QtCore.QTimer()
    t.timeout.connect(mirar)
    t.start(200)
    E["timer"] = t


def _pendiente(doc):
    return bool(getattr(doc, "HasPendingTransaction", False))


def prueba():
    import FreeCADGui
    doc = FreeCAD.newDocument("CotaSobra")
    sk = cc.croquis_oblongo(doc)
    doc.recompute()
    E.update(doc=doc, sk=sk, n=sk.ConstraintCount)
    assert not sk.RedundantConstraints and not sk.ConflictingConstraints, "el croquis de partida ya tiene errores"
    _vigilar()

    def ultima():
        return sk.Constraints[-1]

    def abrir():
        FreeCADGui.ActiveDocument.setEdit(sk.Name)

    def encuadrar():
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewTop()
        view.fitAll()

    def primer_clic():
        FreeCADGui.runCommand("Sketcher_Dimension")
        cc.clic(V(5, 3, 0))  # recta de arriba del oblongo
        cc.mover(V(5, 8, 0))

    def provisoria():
        assert sk.ConstraintCount == E["n"] + 1, "no hay cota provisoria (¿cambió FreeCAD?)"
        assert ultima().Type in DIMS and not ultima().Driving, "la provisoria no quedó conducida: %s %s" % (
            ultima().Type, ultima().Driving)
        assert not sk.RedundantConstraints, "croquis redundante con la provisoria: %s" % list(sk.RedundantConstraints)

    def ubicar():
        E["modales"].clear()
        cc.clic(V(5, 12, 0))

    def ubicada():
        assert not E["modales"], "una cota conducida no debería pedir valor: %s" % E["modales"]
        assert sk.ConstraintCount == E["n"] + 1, "FreeCAD borró la cota ubicada (%d)" % sk.ConstraintCount
        assert ultima().Type in DIMS and not ultima().Driving, (ultima().Type, ultima().Driving)
        assert abs(ultima().Value - 10) < 1e-6, ultima().Value
        assert not sk.RedundantConstraints, list(sk.RedundantConstraints)
        assert not _pendiente(doc), "quedó un paso abierto"
        cc.esc()  # sale de la herramienta (continua)

    def deshacer():
        assert FreeCADGui.ActiveDocument.getInEdit() is not None, "Esc cerró el croquis"
        FreeCADGui.runCommand("Std_Undo")

    def rehacer():
        assert sk.ConstraintCount == E["n"], "Deshacer no sacó la cota en un paso (%d)" % sk.ConstraintCount
        FreeCADGui.runCommand("Std_Redo")

    def circulo():
        assert sk.ConstraintCount == E["n"] + 1 and not ultima().Driving, "Rehacer no la devolvió conducida"
        FreeCADGui.runCommand("Sketcher_Dimension")
        cc.clic(V(-6, -10, 0))  # borde del círculo que ya tiene radio
        cc.mover(V(-2, -4, 0))

    def circulo_provisoria():
        assert sk.ConstraintCount == E["n"] + 2, "no hay cota provisoria en el círculo"
        assert ultima().Type in ("Radius", "Diameter") and not ultima().Driving, (ultima().Type, ultima().Driving)
        assert not sk.RedundantConstraints, list(sk.RedundantConstraints)
        cc.esc()  # cancela la cota a mitad de camino

    def cancelada():
        assert sk.ConstraintCount == E["n"] + 1, "Esc dejó la cota del círculo (%d)" % sk.ConstraintCount
        assert not _pendiente(doc), "Esc dejó un paso abierto"
        cc.esc()  # sale de la herramienta

    def dos_entidades():
        assert FreeCADGui.ActiveDocument.getInEdit() is not None, "Esc cerró el croquis"
        FreeCADGui.runCommand("Sketcher_Dimension")
        cc.clic(V(5, 3, 0))
        cc.clic(V(-10, 20, 0))  # horizontal de arriba

    def distancia():
        assert ultima().Type == "Distance" and abs(ultima().Value - 17) < 1e-6, (ultima().Type, ultima().Value)
        assert ultima().Driving, "la distancia entre las rectas no sobra: tiene que quedar conducente"
        E["modales"].clear()
        cc.clic(V(-15, 12, 0))

    def distancia_ubicada():
        assert sk.ConstraintCount == E["n"] + 2, sk.ConstraintCount
        assert ultima().Driving and abs(ultima().Value - 17) < 1e-6, (ultima().Driving, ultima().Value)
        assert not sk.RedundantConstraints and not sk.ConflictingConstraints
        assert E["modales"] == ["Insertar longitud"], "la cota conducente tiene que pedir su valor: %s" % E["modales"]
        cc.esc()

    def separada():
        # herramienta de cota separada (Radio), con el círculo ya elegido: crea la cota de una
        assert FreeCADGui.ActiveDocument.getInEdit() is not None, "Esc cerró el croquis"
        E["modales"].clear()
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(sk, "Edge%d" % (cc.CIRCULO + 1))
        FreeCADGui.runCommand("Sketcher_ConstrainRadius")

    def separada_conducida():
        assert sk.ConstraintCount == E["n"] + 3, "la herramienta de Radio no agregó la cota (%d)" % sk.ConstraintCount
        assert ultima().Type == "Radius" and not ultima().Driving, (ultima().Type, ultima().Driving)
        assert not sk.RedundantConstraints, list(sk.RedundantConstraints)
        # FreeCAD pide el valor igual ("Insertar radio", con el valor actual): se acepta y la cota
        # tiene que seguir conducida (en SW esa herramienta separada no existe)
        assert E["modales"] in ([], ["Insertar radio"]), E["modales"]
        FreeCADGui.Selection.clearSelection()

    def guardar_y_abrir():
        FreeCADGui.ActiveDocument.resetEdit()
        ruta = os.path.join(carpeta_temporal(), "cota_sobra.FCStd")
        doc.saveAs(ruta)
        FreeCAD.closeDocument(doc.Name)
        E["doc2"] = FreeCAD.openDocument(ruta)

    def abierto():
        d = E["doc2"]
        s = d.getObject("Croquis")
        a, b = s.Constraints[E["n"]], s.Constraints[E["n"] + 1]
        assert not a.Driving and abs(a.Value - 10) < 1e-6, (a.Type, a.Driving, a.Value)
        assert b.Driving and abs(b.Value - 17) < 1e-6, (b.Type, b.Driving, b.Value)
        r = s.Constraints[E["n"] + 2]
        assert r.Type == "Radius" and not r.Driving and abs(r.Value - 4) < 1e-6, (r.Type, r.Driving, r.Value)
        assert set(E["todos"]) <= {"Insertar longitud", "Insertar radio"}, "aparecieron otros cuadros: %s" % E["todos"]
        import FreeCADGui
        assert not FreeCADGui.getDocument(d.Name).Modified, "el archivo quedó modificado al abrirlo"
        E["timer"].stop()

    return [(800, abrir), (1500, encuadrar), (800, primer_clic), (1000, provisoria), (300, ubicar),
            (2000, ubicada), (800, deshacer), (800, rehacer), (800, circulo), (1000, circulo_provisoria),
            (800, cancelada), (800, dos_entidades), (1200, distancia), (2500, distancia_ubicada),
            (800, separada), (1500, separada_conducida), (800, guardar_y_abrir), (2000, abierto)]


from _base import ejecutar  # noqa: E402
ejecutar(globals())
