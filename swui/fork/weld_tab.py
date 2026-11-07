# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Pestaña Piezas soldadas de la cinta (como la de SW 2018), después de Chapa: Miembro estructural,
Esquinas, Recortar/Alargar, Lista de cortes, Tapa de extremo y Cartela. Se suma a la tabla del
original (ribbon_layout.TABS) desde afuera, como sheet_tab.py.
"""

TITLE = "Piezas soldadas"

GROUPS = [
    [
        ("SWUI_WeldMember", "Miembro\nestructural", {"svg": "fork/weld_member"}),
        ("SWUI_WeldCorners", "Esquinas", {"svg": "fork/weld_corners"}),
        ("SWUI_WeldTrim", "Recortar/\nAlargar", {"svg": "fork/weld_trim"}),
    ],
    [
        ("SWUI_WeldEndCap", "Tapa de\nextremo", {"svg": "fork/weld_endcap"}),
        ("SWUI_WeldGusset", "Cartela", {"svg": "fork/weld_gusset"}),
    ],
    [
        ("SWUI_WeldCutList", "Lista de\ncortes", {"svg": "fork/weld_cutlist"}),
    ],
]


def install():
    from swui import ribbon_layout

    if any(title == TITLE for title, _g in ribbon_layout.TABS):
        return
    after = next((i for i, (title, _g) in enumerate(ribbon_layout.TABS) if title == "Chapa"),
                 len(ribbon_layout.TABS) - 1)
    ribbon_layout.TABS.insert(after + 1, (TITLE, [list(g) for g in GROUPS]))
