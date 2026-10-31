# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
La cinta pasa sola a la pestaña Ensamblaje al abrir o pasar a un ensamblaje, y vuelve a
Operaciones al pasar de un ensamblaje a una pieza, como SW 2018 (pendiente de la fase 5).

Como el original con los croquis y los planos (ribbon._check_context / _check_drawing): solo en el
cambio de documento, así una pestaña que el usuario elige a mano dentro del mismo documento queda.
Se suma desde afuera envolviendo ribbon._check_drawing, que el original llama en cada revisión.
"""

import FreeCAD

ASSEMBLY_TAB = "Baugruppe"  # clave del original (ribbon_layout.BAUGRUPPE)
PART_TAB = "Features"  # Operaciones

_state = {"key": None}


def kind_of(doc):
    """'assembly', 'part' u None (documento vacío o de planos) según lo que tiene el documento."""
    if doc is None:
        return None
    types = {o.TypeId for o in doc.Objects}
    if "Assembly::AssemblyObject" in types:
        return "assembly"
    if "PartDesign::Body" in types or any(t.startswith("Part::") for t in types):
        return "part"
    return None


def tab_for(before, now):
    """Pestaña a la que pasar al cambiar de (documento, tipo) `before` a `now`, o None."""
    if now is None or now == before:
        return None
    if now[1] == "assembly":
        return ASSEMBLY_TAB
    if now[1] == "part" and before is not None and before[1] == "assembly":
        return PART_TAB
    return None


def _check():
    from swui import ribbon

    tabs = ribbon._tabs
    if tabs is None or getattr(ribbon, "_on_drawing", False) or getattr(ribbon, "_in_sketch", False):
        return
    doc = FreeCAD.ActiveDocument
    seen = (doc.Name, len(doc.Objects)) if doc is not None else None
    if seen == _state.get("seen"):
        return  # corre cada pocos cientos de ms: sin recorrer los objetos si nada cambió
    _state["seen"] = seen
    now = (doc.Name, kind_of(doc)) if doc is not None else None
    before = _state["key"]
    _state["key"] = now
    tab = tab_for(before, now)
    if tab in ribbon._tab_titles:
        tabs.setCurrentIndex(ribbon._tab_titles.index(tab))


def install():
    from swui import ribbon

    original = ribbon._check_drawing
    if getattr(original, "_swui_asm_tab", False):
        return

    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            _check()
        except Exception:
            pass
        return result

    wrapped._swui_asm_tab = True
    ribbon._check_drawing = wrapped
