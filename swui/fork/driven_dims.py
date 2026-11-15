# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Cota que sobra -> conducida, como SOLIDWORKS 2018 (pedido del usuario, 15/11; ficha #93).

SW 2018 del usuario (comparado con el mouse el 15/11, Opciones > Croquis > "Cotas que definen en
exceso": "Configurar como conducida de forma predeterminada", sin "Avisar"): con Cota inteligente
sobre algo que ya está definido (la recta de un oblongo), la cota se ve mientras se mueve, el
croquis no cambia de estado, y al ubicarla queda conducida (gris), sin preguntar.

FreeCAD 1.1.4 en cambio agrega la cota (conducente) ya en el primer clic: el croquis queda con
"Restricciones redundantes" mientras se mueve la cota, la vuelve a crear con cada movimiento del
mouse (longitud, horizontal, vertical) y, si se ubica así, pide el valor y la borra sin avisar.
Ninguna preferencia lo cambia (revisado).

Acá: mientras una herramienta de cota de FreeCAD tiene su paso abierto ("Add ... constraint"),
cada cota nueva que deja el croquis redundante se pasa a conducida (setDriving). Así la vista
previa no pone el croquis en rojo, el segundo clic en otra entidad sigue funcionando igual (la
herramienta la cambia por la cota nueva, que no sobra y queda conducente) y al ubicarla queda
conducida sin el cuadro de valor, en el mismo paso de deshacer. Solo API pública: escucha de
documento, RedundantConstraints, setDriving. Si FreeCAD algún día trae esto, la escucha no hace
nada (la cota ya llega sin redundancia).

Lógica en `make_driven_if_redundant` (se puede llamar sola, sin herramienta abierta).
"""

import re
import traceback

import FreeCAD

WB_NAME = "LikeSolidWorksUIWorkbench"
SKETCH_TYPE = "Sketcher::SketchObject"
DIM_TYPES = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")
# Pasos que abren las herramientas de cota de FreeCAD 1.1.4 (Cota inteligente y las separadas):
# "Add length constraint", "Add DistanceX constraint", "Add radius constraint"... Los guarda en
# inglés aunque la interfaz esté en castellano. Las herramientas de FreeWorks usan nombres propios.
TOOL_STEP = re.compile(r"^Add .*constraint$", re.IGNORECASE)

_state = {"installed": False, "busy": False}


def make_driven_if_redundant(sketch, index=None):
    """
    Si la relación `index` del croquis (por omisión, la última) es una cota conducente y el croquis
    tiene relaciones redundantes que desaparecen al pasarla a conducida, la deja conducida (como SW
    con "Configurar como conducida de forma predeterminada") y devuelve True. Si conducida no
    arregla nada (el croquis ya venía con otro problema), la devuelve como estaba y da False.
    Recalcula el croquis (solve) antes y después: la lista de redundantes de FreeCAD solo se
    actualiza al recalcular. No abre ni cierra pasos de deshacer: el cambio va en el paso abierto.
    """
    try:
        count = sketch.ConstraintCount
        if not count:
            return False
        if index is None:
            index = count - 1
        if index < 0 or index >= count:
            return False
        c = sketch.Constraints[index]
        if c.Type not in DIM_TYPES or not c.Driving:
            return False
        sketch.solve()
        if not list(sketch.RedundantConstraints):
            return False
        sketch.setDriving(index, False)
        sketch.solve()
        if list(sketch.RedundantConstraints) or list(sketch.ConflictingConstraints):
            sketch.setDriving(index, True)  # no era esta la que sobraba: como estaba
            sketch.solve()
            return False
        return True
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cota conducida:\n%s\n" % traceback.format_exc())
        return False


def tool_step_open():
    """¿Hay abierto un paso de una herramienta de cota de FreeCAD?"""
    try:
        active = FreeCAD.getActiveTransaction()
    except Exception:
        return False
    name = active[0] if isinstance(active, tuple) and active else active
    return bool(name) and bool(TOOL_STEP.match(str(name)))


def _in_workbench():
    try:
        import FreeCADGui
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _in_edit(sketch):
    try:
        import FreeCADGui
        gdoc = FreeCADGui.getDocument(sketch.Document.Name)
        vp = gdoc.getInEdit() if gdoc is not None else None
        return vp is not None and vp.Object is sketch
    except Exception:
        return False


class _Observer:
    def slotChangedObject(self, obj, prop):
        if prop != "Constraints" or _state["busy"]:
            return
        try:
            if obj.TypeId != SKETCH_TYPE:
                return
            from swui.fork import safe_ops
            if safe_ops.doc_busy(obj.Document) or not tool_step_open():
                return
            if not _in_workbench() or not _in_edit(obj):
                return
        except Exception:
            return
        _state["busy"] = True  # setDriving vuelve a avisar "Constraints"
        try:
            make_driven_if_redundant(obj)
        finally:
            _state["busy"] = False


def install():
    if _state["installed"]:
        return
    FreeCAD.addDocumentObserver(_Observer())
    _state["installed"] = True
