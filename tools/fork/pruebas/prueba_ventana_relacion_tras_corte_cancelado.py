# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#85, hallado por el mono de ensamblaje): una relación de posición entre una cara
de costado de la placa y el bloque; después se abre Extruir corte de ensamblaje sobre la cara de
arriba de la placa (la vista previa le cambia la numeración de caras), se abre y cierra Ecuaciones,
y se Cancela el corte. Como SW: la relación sigue con LA MISMA cara (no salta a otra) y todo queda
como estaba antes de abrir el corte. Se prueba con varias semillas (caras y rectángulos al azar)."""
TIPO = "completa"
import random  # noqa: E402

import FreeCAD  # noqa: E402

from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

SEMILLAS = ((3511, 42371), (1, 2), (7, 9), (11, 13), (21, 34))


def _estado(joint):
    from swui.fork import mate_refs
    return (tuple(joint.Reference1[1]), tuple(joint.Reference2[1]), getattr(joint, mate_refs.PROP, ""))


def _correr(gen):
    for ms in gen or ():
        bombear(int(ms or 0))


def prueba():
    from casos_ensamblaje import Relacion
    from casos_ensamblaje2 import CorteEnsamblaje
    from swui.fork import equations, mates_sw
    for s_rel, s_corte in SEMILLAS:
        doc = FreeCAD.newDocument("Conjunto")
        doc.UndoMode = 1
        rel = Relacion()
        yield from rel.preparar(doc)
        rng = random.Random(s_rel)
        yield from rel.abrir(rng)
        yield from rel.elegir(rng)
        yield from rel.aceptar()
        yield 800
        joints = [o for o in mates_sw._assembly_modules()[1].getJointGroup(rel.asm).Group
                  if getattr(o, mates_sw.PROP, "") not in ("", "tangent_axis")]
        assert joints, "semilla %s: no quedó la relación" % s_rel
        joint = joints[-1]
        antes = _estado(joint)
        traza("  semilla %s: relación %s" % (s_rel, antes[:2]))
        corte = CorteEnsamblaje()
        corte.doc, corte.asm, corte.comps = rel.doc, rel.asm, rel.comps
        rng = random.Random(s_corte)
        yield from corte.abrir(rng)
        yield from corte.elegir(rng)
        traza("    con el corte abierto: %s" % (_estado(joint)[:2],))
        dlg = equations.show_dialog(doc)
        yield 800
        dlg.reject()
        yield 500
        yield from corte.cancelar()
        yield 800
        despues = _estado(joint)
        traza("    después de cancelar: %s" % (despues[:2],))
        assert despues[:2] == antes[:2], "semilla %s: la relación cambió de cara al cancelar el corte: %s -> %s (#85)" % (
            s_rel, antes[:2], despues[:2])
        assert despues[2] == antes[2], "semilla %s: la geometría guardada de la relación cambió: %s -> %s (#85)" % (
            s_rel, antes[2][:400], despues[2][:400])
        for d in list(FreeCAD.listDocuments().values()):
            FreeCAD.closeDocument(d.Name)
        yield 300


from _base import ejecutar  # noqa: E402
ejecutar(globals())
