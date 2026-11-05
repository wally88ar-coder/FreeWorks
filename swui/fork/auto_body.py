# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Sin "Cuerpo activo" a la vista, como SW. En Part Design cada sólido es un Cuerpo y las
operaciones van al Cuerpo activo: con dos sólidos y ninguno activo (por ejemplo al abrir
el archivo), Extruir pedía en inglés "Cuerpo Activo Requerido"; con un croquis de otro
sólido daba error ("debe pertenecer al cuerpo activo"). SW no tiene ese concepto: se elige
el croquis o la cara y listo.

Acá, al elegir algo que está dentro de un Cuerpo (en la vista o en el árbol, sin ningún
panel abierto), ese Cuerpo pasa a ser el activo. Es lo mismo que el doble clic de FreeCAD
sobre el Cuerpo, hecho solo; no guarda nada propio en el archivo.

Además (pedido del usuario, 04/11): una pieza nueva arrancaba con el Cuerpo elegido y
Extruir daba el error de FreeCAD "El objeto seleccionado debe pertenecer al cuerpo
activo" (FreeCAD tomaba el Cuerpo como si fuera el croquis). Como en SW, con la pieza
entera elegida Extruir / Cortar / Revolución / Croquis piden el plano o la cara
(`pick_plane` no cuenta un Cuerpo entero como selección), y el Cuerpo recién creado no
queda elegido.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

WB_NAME = "LikeSolidWorksUIWorkbench"
BODY = "PartDesign::Body"

_state = {"observer": None}


def body_of(obj):
    """El Cuerpo que contiene a obj (o obj mismo si es un Cuerpo); None si no hay."""
    seen = 0
    while obj is not None and seen < 20:
        if obj.TypeId == BODY:
            return obj
        try:
            obj = obj.getParentGeoFeatureGroup()
        except Exception:
            return None
        seen += 1
    return None


def _busy(gdoc):
    try:
        if FreeCADGui.Control.activeDialog():
            return True
        return gdoc.getInEdit() is not None
    except Exception:
        return True


def _activate(doc_name, obj_name):
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return
        doc = FreeCAD.getDocument(doc_name)
        gdoc = FreeCADGui.getDocument(doc_name)
        obj = doc.getObject(obj_name)
        body = body_of(obj)
        if body is None or _busy(gdoc):
            return
        from swui.fork import configurations as cf

        if cf.is_copy(body):
            return  # la copia de un componente configurado (ensamblaje): no es para trabajar adentro
        view = gdoc.ActiveView
        if view is None or view.getActiveObject("pdbody") is body:
            return
        view.setActiveObject("pdbody", body)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Cuerpo activo:\n%s\n" % traceback.format_exc())


class _Observer:
    def addSelection(self, doc, obj, sub, pnt):
        # después de la selección (cambiar el Cuerpo activo adentro del aviso confunde a FreeCAD)
        QtCore.QTimer.singleShot(0, lambda: _activate(doc, obj))


# --- Cuerpo entero elegido = nada elegido (como SW) ---------------------------------

DESELECT_MS = (0, 300, 1000)  # FreeCAD elige el Cuerpo nuevo un rato después de crearlo


def without_whole_bodies(sel):
    """sel = [(objeto, [subelementos])]: saca los Cuerpos elegidos enteros (sin cara ni arista)."""
    return [(o, s) for o, s in sel if s or getattr(o, "TypeId", "") != BODY]


def _hook_pick_plane():
    from swui import pick_plane

    original = pick_plane._selection
    if getattr(original, "_swui_auto_body", False):
        return

    def wrapped():
        return without_whole_bodies(original())

    wrapped._swui_auto_body = True
    pick_plane._selection = wrapped


def _deselect_new_body(doc_name, body_name):
    """Si lo único elegido es el Cuerpo recién creado, entero: no dejar nada elegido."""
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return
        sels = FreeCADGui.Selection.getSelectionEx(doc_name)
        if len(sels) == 1 and sels[0].Object.Name == body_name and not sels[0].SubElementNames:
            FreeCADGui.Selection.clearSelection(doc_name)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cuerpo nuevo sin elegir:\n%s\n" % traceback.format_exc())


class _DocObserver:
    def slotCreatedObject(self, obj):
        try:
            if obj.TypeId != BODY:
                return
            doc_name, name = obj.Document.Name, obj.Name
        except Exception:
            return
        for ms in DESELECT_MS:
            QtCore.QTimer.singleShot(ms, lambda: _deselect_new_body(doc_name, name))


def install():
    if _state["observer"] is None:
        _state["observer"] = _Observer()
        FreeCADGui.Selection.addObserver(_state["observer"])
    if _state.get("doc_observer") is None:
        _state["doc_observer"] = _DocObserver()
        FreeCAD.addDocumentObserver(_state["doc_observer"])
    try:
        _hook_pick_plane()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Cuerpo entero = sin selección:\n%s\n" % traceback.format_exc())
