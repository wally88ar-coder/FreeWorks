# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Croquis nuevo que se cierra vacío: se borra, como SW (pedido del usuario, 01/11, comparado con el
mouse en SW 2018: Insertar > Croquis sobre una cara y Salir del croquis sin dibujar no deja nada
en el árbol; FreeCAD dejaba "Croquis5" vacío).

Solo croquis creados en esta sesión que todavía no tuvieron nada: sin geometría, sin referencias
externas y sin relaciones al cerrarlos, y que nadie usa (fuera de su Cuerpo). Un croquis que ya
tenía algo y queda vacío se respeta. Los que arma el fork por dentro (Desdoblar, croquis de hoja,
taladro de ensamblaje...) llevan propiedades SWUI_ o los usa otro objeto: no se tocan.
Un solo paso de deshacer ("Croquis vacío") lo devuelve.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

WB_NAME = "LikeSolidWorksUIWorkbench"
SKETCH_TYPE = "Sketcher::SketchObject"

_new = set()  # (documento, nombre) de croquis creados en esta sesión y todavía sin nada
_state = {"installed": False}


def is_empty(sketch):
    try:
        return (not sketch.Geometry and not sketch.Constraints
                and not list(getattr(sketch, "ExternalGeometry", []) or []))
    except Exception:
        return False


def _own_property(obj):
    try:
        return any(p.startswith("SWUI_") for p in obj.PropertiesList)
    except Exception:
        return True


def _used(sketch):
    """¿Lo usa algo que no sea su Cuerpo? (una operación, un VarSet del fork...)"""
    try:
        return any(not o.isDerivedFrom("PartDesign::Body") for o in sketch.InList)
    except Exception:
        return True


def should_remove(sketch):
    return (sketch is not None and sketch.TypeId == SKETCH_TYPE and is_empty(sketch)
            and not _own_property(sketch) and not _used(sketch))


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


class _DocObserver:
    def slotCreatedObject(self, obj):
        try:
            doc = obj.Document
            if obj.TypeId != SKETCH_TYPE or doc.Restoring or getattr(doc, "Transacting", False):
                return
            _new.add((doc.Name, obj.Name))
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        for key in [k for k in _new if k[0] == doc.Name]:
            _new.discard(key)


class _GuiObserver:
    def slotResetEdit(self, vp):
        try:
            obj = vp.Object
            key = (obj.Document.Name, obj.Name)
        except Exception:
            return
        if key in _new:
            QtCore.QTimer.singleShot(0, lambda: _closed(key))


def _closed(key):
    """Después de cerrar el croquis (fuera del aviso de FreeCAD)."""
    doc = FreeCAD.listDocuments().get(key[0])
    sketch = doc.getObject(key[1]) if doc is not None else None
    if sketch is None:
        _new.discard(key)
        return
    try:
        gdoc = FreeCADGui.getDocument(doc.Name)
        if gdoc is not None and gdoc.getInEdit() is not None:
            return  # se volvió a abrir enseguida: se mira al cerrarlo
    except Exception:
        pass
    if not is_empty(sketch):
        _new.discard(key)  # ya tuvo algo: de ahora en más es un croquis como cualquier otro
        return
    if not _in_workbench() or not should_remove(sketch):
        return
    _new.discard(key)
    doc.openTransaction("Croquis vacío")
    try:
        doc.removeObject(sketch.Name)
        doc.commitTransaction()
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintLog("[SWUI fork] Croquis vacío:\n%s\n" % traceback.format_exc())


def install():
    if _state["installed"]:
        return
    FreeCAD.addDocumentObserver(_DocObserver())
    FreeCADGui.addDocumentObserver(_GuiObserver())
    _state["installed"] = True
