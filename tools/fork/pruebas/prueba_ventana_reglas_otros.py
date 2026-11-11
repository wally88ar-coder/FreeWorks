# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Los paneles SW Convertir a chapa, Vista de sección, Agregar configuración, Croquis (elegir plano) y
Croquis 3D cumplen las reglas comunes de reglas_paneles.py con elecciones y valores al
azar: Cancelar deja todo igual; algo inválido no se acepta y se avisa; otro comando cancela de
verdad; Aceptar deja una operación válida y un paso de deshacer (Deshacer y Rehacer exactos);
editar y aceptar sin tocar no cambia nada; guardar y abrir deja la pieza igual; nunca errores en
el informe de FreeCAD. Incumplimientos ya registrados: DEUDA (cada uno con su Issue)."""
TIPO = "completa"

from casos_otros import CASOS  # noqa: E402
from reglas_paneles import correr  # noqa: E402

_NO_CANCELA = ("no se canceló", "siguió abierto", "cambió", "pasos de deshacer", "diálogo", "sobra",
               "transacción")
DEUDA = {
}


def prueba():
    return correr([c() for c in CASOS], DEUDA)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
