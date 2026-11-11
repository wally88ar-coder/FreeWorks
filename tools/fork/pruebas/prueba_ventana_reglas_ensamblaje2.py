# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Los paneles SW Taladro y Extruir corte de ensamblaje (cambian las piezas, otros documentos)
cumplen las reglas comunes de reglas_paneles.py que corresponden a cada uno (ver `reglas`), con elecciones y valores al
azar: Cancelar deja todo igual; algo inválido no se acepta y se avisa; otro comando cancela de
verdad; Aceptar deja una operación válida y un paso de deshacer (Deshacer y Rehacer exactos);
editar y aceptar sin tocar no cambia nada; guardar y abrir deja la pieza igual; nunca errores en
el informe de FreeCAD. Incumplimientos ya registrados: DEUDA (cada uno con su Issue)."""
TIPO = "completa"

from casos_ensamblaje2 import CASOS  # noqa: E402
from reglas_paneles import correr  # noqa: E402

DEUDA = {
    ("Taladro de ensamblaje", "aceptar"): ("#37", "después de Deshacer"),
    ("Taladro de ensamblaje", "guardar"): ("#38", "DAG", "modificado", "Failed to get subshape"),
    ("Extruir corte de ensamblaje", "guardar"): ("#38", "DAG", "modificado", "Failed to get subshape"),
}


def prueba():
    return correr([c() for c in CASOS], DEUDA)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
