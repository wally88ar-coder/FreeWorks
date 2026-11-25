# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#119, Mover cara sobre un sólido suelto (no tenía prueba propia): editando una pieza con el contenedor Parte de
FreeWorks que tiene, además del bloque, un sólido suelto (como uno importado de un STEP), Mover cara sobre una
cara del sólido suelto le arma un Cuerpo que arranca de él.
Tiene que pasar (como SW: una operación = un paso):
1) Cancelar: no queda nada (ni el Cuerpo armado), todo como estaba, sin pasos de deshacer, se sigue editando;
2) Equidistanciar 5 mm y Aceptar: UN paso de deshacer, "Mover cara"; el Cuerpo nuevo dentro del contenedor, con
   el volumen de la caja más área × 5; se sigue editando; Ctrl+Z saca todo y Ctrl+Y lo vuelve, dentro."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def prueba():
    import FreeCADGui
    import Part
    from reglas_paneles import esperar_panel, tocar
    from swui import ribbon
    from swui.fork import edit_context as ec
    from swui.fork import move_face as mf
    from swui.fork import panel_guard
    from un_paso_comun import preparar
    p = yield from preparar()
    pdoc = p.pdoc
    pdoc.openTransaction("Importado")
    suelto = pdoc.addObject("Part::Feature", "Importado")
    suelto.Shape = Part.makeBox(20, 20, 20, V(120, 0, 0))
    p.part.addObject(suelto)
    pdoc.commitTransaction()
    pdoc.recompute()
    yield 500
    pdoc.clearUndos()
    cara = [i for i, f in enumerate(suelto.Shape.Faces) if abs(f.CenterOfMass.z - 20) < 1e-6][0]
    sub = "Face%d" % (cara + 1)
    area = suelto.Shape.Faces[cara].Area

    def abrir():
        """Elegir la cara del sólido suelto y abrir Mover cara (si la selección llega tarde, el panel que espera
        una cara la recibe, como en prueba_ventana_azar_mover_cara)."""
        for _i in range(20):
            FreeCADGui.Selection.clearSelection()
            assert ec.select(suelto, sub, clear=False), "no se pudo elegir la cara del sólido suelto"
            if panel_guard.open_panel() is None and not FreeCADGui.Control.activeDialog():
                ribbon._run(mf.COMMAND)
                yield from esperar_panel()
            cual = type(panel_guard.open_panel()).__name__
            if cual == "MoveFacePanel":
                return panel_guard.open_panel()
            assert cual == "_WaitFacePanel", "no abrió Mover cara: %s" % cual
            bombear(300)
        raise AssertionError("Mover cara no tomó la cara del sólido suelto")

    traza("1) Mover cara en el sólido suelto y Cancelar")
    foto = p.foto()
    yield from abrir()
    yield 500
    assert tocar(rechazar=True), "no encontré Cancelar"
    p.cancelado("Cancelar", foto)
    yield 100

    traza("2) Equidistanciar 5 mm y Aceptar")
    antes = p.cuerpos()
    panel = yield from abrir()
    panel.radios["offset"].setChecked(True)
    bombear(300)
    panel.distance.setValue(5.0)
    panel.flip.setChecked(False)
    panel.preview()
    yield 1000
    assert tocar(rechazar=False), "no encontré Aceptar"
    p.un_paso("Mover cara", mf.LABEL, antes)
    nuevo = pdoc.getObject(sorted(p.cuerpos() - antes)[0])
    esperado = 20 ** 3 + area * 5
    traza("  volumen %.3f (esperado %.3f)" % (nuevo.Shape.Volume, esperado))
    assert abs(nuevo.Shape.Volume - esperado) < 1e-3, "el Cuerpo nuevo no tiene la cara movida 5 mm: %.3f" % (
        nuevo.Shape.Volume)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
