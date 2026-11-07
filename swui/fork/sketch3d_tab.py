# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Botón Croquis 3D en la pestaña Croquis de la cinta, al lado de Croquis (en SW está en el
desplegable del mismo botón). Se suma a la tabla del original (ribbon_layout.SKIZZE) desde afuera.
"""

ENTRY = ("SWUI_Sketch3D", "Croquis 3D", {"svg": "fork/sketch3d"})


def install():
    from swui import ribbon_layout

    groups = ribbon_layout.SKIZZE[1]
    if any(isinstance(e, tuple) and e[0] == ENTRY[0] for g in groups for e in g):
        return
    first = groups[0]
    at = next((i for i, e in enumerate(first) if isinstance(e, dict) and "toggle" in e), -1)
    first.insert(at + 1, ENTRY)
