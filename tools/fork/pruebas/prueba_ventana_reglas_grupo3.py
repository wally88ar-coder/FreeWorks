# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Los paneles SW de pieza, grupo 3 (Asistente para taladro, Mover/Copiar y Eliminar/Conservar sólidos,
chapa: Brida base, Brida de arista, Dobladillo) cumplen las reglas comunes de reglas_paneles.py con elecciones y valores al
azar: Cancelar deja todo igual; algo inválido no se acepta y se avisa; otro comando cancela de
verdad; Aceptar deja una operación válida y un paso de deshacer (Deshacer y Rehacer exactos);
editar y aceptar sin tocar no cambia nada; guardar y abrir deja la pieza igual; nunca errores en
el informe de FreeCAD. Incumplimientos ya registrados: DEUDA (cada uno con su Issue)."""
TIPO = "completa"

from casos_grupo3 import CASOS  # noqa: E402
from reglas_paneles import correr  # noqa: E402

DEUDA = {
    ("Brida base", "editar"): "#31",
}


def prueba():
    return correr([c() for c in CASOS], DEUDA)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
