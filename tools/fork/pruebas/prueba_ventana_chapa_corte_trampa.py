# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#9): Extruir corte de la pestaña Chapa deja el corte "hasta el espesor" (atado
al espesor de la chapa) SOLO para el corte que pide. Si se cancela antes de que exista el corte
(Cancelar en "elegir plano"), no queda nada armado: el próximo Vaciado que aparezca (otro comando,
abrir un archivo, deshacer) queda como lo hizo FreeCAD, sin fórmula. Y el corte pedido sí queda
atado al espesor."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from casos_grupo3 import _croquis, _SobreBrida  # noqa: E402
from reglas_paneles import esperar_panel, tocar  # noqa: E402


def prueba():
    import FreeCADGui
    from swui.fork import sheet_metal as sm
    from swui.fork import sheet_panels as sp
    doc = FreeCAD.newDocument("CorteChapa")
    chapa = _SobreBrida()
    yield from chapa.preparar(doc)
    body = chapa.body
    assert sm.sheet_base(body) is not None, "no se armó la chapa"

    # 1) pedir el corte y Cancelar en "elegir plano": nada queda armado
    FreeCADGui.Selection.clearSelection()
    sp.start_cut()
    yield from esperar_panel()
    assert FreeCADGui.Control.activeDialog(), "no se abrió el panel de elegir plano"
    tocar(rechazar=True)
    yield 4000
    assert not FreeCADGui.Control.activeDialog(), "el panel quedó abierto"
    assert sp._cut_watch["observer"] is None, "Cancelar dejó la trampa armada (#9)"

    # 2) un Vaciado que aparece después (otro comando, deshacer...): sin fórmula
    otro = body.newObject("PartDesign::Pocket", "OtroCorte")
    yield 800
    assert not otro.ExpressionEngine, "un Vaciado ajeno quedó atado al espesor (#9): %s" % otro.ExpressionEngine
    body.removeObject(otro)
    doc.removeObject(otro.Name)
    doc.recompute()

    # 3) el corte pedido sí queda atado al espesor
    sk = _croquis(body, "XY_Plane", 0, [("circulo", 40, 25, 5)])
    doc.recompute()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(sk)
    sp.start_cut()
    yield from esperar_panel()
    yield 1000
    cortes = [o for o in doc.Objects if o.TypeId == "PartDesign::Pocket"]
    assert cortes, "no se creó el corte"
    expr = dict(cortes[-1].ExpressionEngine)
    assert "Thickness" in expr.get("Length", ""), "el corte pedido no quedó atado al espesor: %s" % expr
    tocar()
    yield 1500
    assert sp._cut_watch["observer"] is None, "quedó armada después del corte"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
