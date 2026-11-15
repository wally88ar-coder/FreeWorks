# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#92: un croquis abierto que queda con una relación de más (una cota conducente de largo sobre
la recta de un oblongo cuyo largo ya está fijado) se pinta ROJO, como lo sobredefinido de SW, y no
del naranja de FreeCAD, casi igual al resaltado de FreeWorks (no se veía qué se estaba por
elegir). El resaltado al pasar el mouse no es rojo. Al sacar la relación de más vuelve a estar
bien."""
TIPO = "completa"

import FreeCAD  # noqa: E402

import croquis_comun as cc  # noqa: E402

E = {}
V = FreeCAD.Vector
ROJO = 0xFF0000FF


def prueba():
    import FreeCADGui
    doc = FreeCAD.newDocument("CotaRoja")
    sk = cc.croquis_oblongo(doc, circulo=False)
    doc.recompute()
    E.update(doc=doc, sk=sk, n=sk.ConstraintCount)
    assert not sk.RedundantConstraints and not sk.ConflictingConstraints, "el croquis de partida ya tiene errores"

    def abrir():
        FreeCADGui.ActiveDocument.setEdit(sk.Name)

    def encuadrar():
        view = FreeCADGui.ActiveDocument.ActiveView
        view.viewTop()
        view.fitAll()

    def sobrar():
        import Sketcher
        vista = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
        assert vista.GetUnsigned("InvalidSketchColor") == ROJO, hex(vista.GetUnsigned("InvalidSketchColor"))
        assert vista.GetUnsigned("HighlightColor") != ROJO, "el resaltado es del mismo color que el error"
        sk.addConstraint(Sketcher.Constraint("Distance", cc.RECTA_SUP, 10))
        sk.solve()
        FreeCADGui.updateGui()

    def mirar_rojo():
        assert sk.RedundantConstraints, "la cota de largo no quedó redundante"
        ok, vistos = cc.hay_rojo(V(25, -10, 0))  # la vertical de la derecha
        assert ok, "el croquis con error no se ve rojo; colores cerca de la vertical: %s" % vistos
        sk.delConstraint(sk.ConstraintCount - 1)
        sk.solve()

    def salir():
        assert not sk.RedundantConstraints, list(sk.RedundantConstraints)
        FreeCADGui.ActiveDocument.resetEdit()

    return [(800, abrir), (1500, encuadrar), (500, sobrar), (1200, mirar_rojo), (500, salir)]


from _base import ejecutar  # noqa: E402
ejecutar(globals())
