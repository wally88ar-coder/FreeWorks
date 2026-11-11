# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Todo módulo del fork que abre un panel en Tareas lo anota en el guardia de paneles
(`safe_ops.show_panel`, `panel_guard.track` o las escuchas comunes que lo hacen solas), para que
otro comando lo cancele de verdad y una escucha no quede colgada si FreeCAD lo cierra. Los que
todavía no lo hacen están en DEUDA, cada uno con su Issue: uno nuevo sin anotar hace fallar la
prueba, y uno de la lista que ya se arregló también (para sacarlo de la lista)."""

import glob  # noqa: E402
import os  # noqa: E402

from _base import ADDON  # noqa: E402

REGISTRA = ("panel_guard.track", "show_panel(", "_PickObserver", "_SelObserver")
DEUDA = {
}


def prueba():
    fork = os.path.join(ADDON, "swui", "fork")
    sin = set()
    for ruta in glob.glob(os.path.join(fork, "**", "*.py"), recursive=True):
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        if "Control.showDialog(" in texto and not any(r in texto for r in REGISTRA):
            sin.add(os.path.relpath(ruta, fork).replace("\\", "/"))
    nuevos = sorted(sin - set(DEUDA))
    arreglados = sorted(set(DEUDA) - sin)
    assert not nuevos, "abren un panel sin anotarlo en el guardia (usar safe_ops.show_panel): %s" % nuevos
    assert not arreglados, "ya se anotan, sacarlos de DEUDA y cerrar su Issue: %s" % [
        "%s %s" % (a, DEUDA[a]) for a in arreglados]


from _base import ejecutar  # noqa: E402
ejecutar(globals())
