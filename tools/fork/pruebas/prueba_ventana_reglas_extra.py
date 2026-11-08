# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Los paneles SW de la segunda tanda (Eje y Punto de ensamblaje, Recortar miembro, Tapa por clic, Mover
sin copiar, Mover cara trasladar y girar, Hélice, Barrido, Recubrir) cumplen las reglas comunes de reglas_paneles.py que corresponden a cada uno (ver `reglas`), con elecciones y valores al
azar: Cancelar deja todo igual; algo inválido no se acepta y se avisa; otro comando cancela de
verdad; Aceptar deja una operación válida y un paso de deshacer (Deshacer y Rehacer exactos);
editar y aceptar sin tocar no cambia nada; guardar y abrir deja la pieza igual; nunca errores en
el informe de FreeCAD. Incumplimientos ya registrados: DEUDA (cada uno con su Issue)."""
TIPO = "completa"

from casos_extra import CASOS  # noqa: E402
from reglas_paneles import correr  # noqa: E402

_ESCUCHA = ("already deleted", "deleted object")
_ERROR = ("ValueError", "No se pudo", "QPushButton")
DEUDA = {
    ("Recortar miembro", "invalido"): ("#19",) + _ERROR,
    ("Recortar miembro", "aceptar"): ("#6",) + _ESCUCHA,
    ("Recortar miembro", "cancelar"): ("~#6",) + _ESCUCHA,
    ("Recortar miembro", "otro_comando"): ("~#6",) + _ESCUCHA,
    ("Tapa de extremo (clic)", "invalido"): ("#19",) + _ERROR,
    ("Tapa de extremo (clic)", "aceptar"): ("#6",) + _ESCUCHA,
    ("Tapa de extremo (clic)", "cancelar"): ("~#6",) + _ESCUCHA,
    ("Tapa de extremo (clic)", "otro_comando"): ("~#6",) + _ESCUCHA,
}


def prueba():
    return correr([c() for c in CASOS], DEUDA)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
