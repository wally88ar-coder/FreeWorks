# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#25): una operación cambia muchas propiedades seguidas (nombres, punta del Cuerpo,
grupo) y cada cambio pedía recorrer todo el árbol de nuevo; una selección de muchos elementos
pedía marcar en el árbol una vez por elemento. Ahora es UN redibujado por tanda, y el árbol queda
al día igual (el último cambio se ve)."""
TIPO = "completa"
import FreeCAD  # noqa: E402

from azar_comun import bombear  # noqa: E402


def prueba():
    import FreeCADGui
    from swui.fork import safe_ops, tree_overlay
    doc = FreeCAD.newDocument("Arbol")
    body = doc.addObject("PartDesign::Body", "Body")
    cajas = []
    for i in range(10):
        c = body.newObject("PartDesign::AdditiveBox", "Caja%d" % i)
        c.Length, c.Width, c.Height = 10 + i, 10, 10
        cajas.append(c)
    doc.recompute()
    yield 1000
    assert tree_overlay._overlays, "el árbol de FreeWorks no está activo (la prueba no prueba nada)"
    antes = safe_ops.once_stats.get("tree_overlay.refresh", 0)
    for i, c in enumerate(cajas):  # 30 cambios seguidos, como una operación que renombra todo
        c.Label = "Renombrada %d" % i
        c.Label = "Otra %d" % i
        body.Tip = c
    bombear(500)
    hechos = safe_ops.once_stats.get("tree_overlay.refresh", 0) - antes
    assert hechos == 1, "30 cambios seguidos dieron %d redibujados del árbol (uno por tanda, #25)" % hechos
    assert body.Tip is cajas[-1] and cajas[-1].Label == "Otra 9", "el último cambio no quedó"
    # seleccionar muchas caras de una: una sola marca en el árbol
    antes = safe_ops.once_stats.get("tree_overlay.mark", 0)
    FreeCADGui.Selection.clearSelection()
    for n in range(1, 7):
        FreeCADGui.Selection.addSelection(doc.Name, body.Name, "Face%d" % n)
    bombear(500)
    hechos = safe_ops.once_stats.get("tree_overlay.mark", 0) - antes
    assert hechos <= 2, "7 cambios de selección seguidos dieron %d marcas del árbol (#25)" % hechos
    FreeCADGui.Selection.clearSelection()
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
