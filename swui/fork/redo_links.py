# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Rodeo a un error de FreeCAD 1.1.4 (NOTAS_TECNICAS, "Errores de FreeCAD encontrados", 8; #47).

Un objeto que Deshacer o Rehacer vuelve a crear (creado con una fórmula en el mismo paso, o
borrado y traído de vuelta) recupera sus fórmulas pero NO la dependencia: su OutList queda sin
el objeto que la fórmula lee, y cuando ese cambia, el objeto no se recalcula. Con
configuraciones: Ctrl+Y de una operación nueva y la operación ya no se suprime al pasar a otra
configuración. Volver a poner la fórmula (sacarla y ponerla) rearma la dependencia, sin pasos de
deshacer nuevos y sin dejar la operación para recalcular (probado con FreeCADCmd).

Se anotan los objetos que aparecen mientras FreeCAD deshace o rehace y, al terminar, se les
reponen las fórmulas. Sin interfaz también anda (escucha de documento de FreeCAD).
"""

import traceback

import FreeCAD

_state = {}


def relink(obj):
    """Vuelve a poner las fórmulas de obj tal cual (rearma su dependencia). Si una no se puede volver
    a poner (lee algo que ya no está), se intenta dejarla como estaba: nunca se pierde una fórmula."""
    for path, expr in list(getattr(obj, "ExpressionEngine", []) or []):
        obj.setExpression(path, None)
        try:
            obj.setExpression(path, expr)
        except Exception:
            try:
                obj.setExpression(path, expr)
            except Exception:
                FreeCAD.Console.PrintWarning("[SWUI fork] No se pudo volver a poner la fórmula %s.%s = %s\n"
                                             % (obj.Label, path, expr))


class _Relink:
    def __init__(self):
        self.pending = {}  # documento -> nombres de objetos vueltos a crear por deshacer/rehacer

    def slotCreatedObject(self, obj):
        try:
            doc = obj.Document
            if getattr(doc, "Transacting", False):
                self.pending.setdefault(doc.Name, set()).add(obj.Name)
        except Exception:
            pass

    def _done(self, doc):
        names = self.pending.pop(doc.Name, set())
        for name in sorted(names):
            obj = doc.getObject(name)
            if obj is None:
                continue
            try:
                relink(obj)
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Fórmulas tras deshacer:\n%s\n" % traceback.format_exc())

    def slotUndoDocument(self, doc):
        self._done(doc)

    def slotRedoDocument(self, doc):
        self._done(doc)

    def slotAbortTransaction(self, doc):
        self._done(doc)  # Cancelar de un panel: lo que vuelve también se repara

    def slotDeletedDocument(self, doc):
        self.pending.pop(doc.Name, None)


def install():
    if _state.get("obs") is None:
        _state["obs"] = _Relink()
        FreeCAD.addDocumentObserver(_state["obs"])
