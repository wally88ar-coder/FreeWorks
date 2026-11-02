# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Cuentas sobre la lista de deshacer de FreeCAD (doc.UndoNames, el paso más nuevo primero).

Se compara la lista entera y no el nombre del último paso: dos pasos pueden llamarse igual (visto
el 01/11: una consulta "IA: eje" repetida se confundió con un cambio y deshizo lo de un panel).
"""


def new_steps(current, snap):
    """Cuántos pasos de arriba de `current` son nuevos respecto de `snap` (lista de deshacer de antes,
    el más nuevo primero). Aguanta que FreeCAD haya tirado los más viejos (tope de pasos). None si
    el historial ya no coincide (p. ej. alguien deshizo cosas)."""
    if not snap:
        return len(current)
    for k in range(len(current)):
        rest = current[k:]
        if rest == snap[:len(rest)]:
            return k
    return None
