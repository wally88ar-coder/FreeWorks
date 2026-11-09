# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de secuencias ("el mono", paso 8.3) en CONFIGURACIONES DE PIEZA (agregar configuraciones con otro largo, pasar de una a otra, paneles), con la ventana (motor en
`mono_comun.py`, entorno en `mono_entornos.py`): seguidillas al azar de Aceptar / Cancelar /
editar, Deshacer / Rehacer, guardar y abrir, más las acciones propias. Después de CADA paso:
Ctrl+Z / Ctrl+Y exactos, sin errores, nada colgado, sin objetos con error.
Seguidillas por regla: FW_CASOS_AZAR (6); largo: 3 a FW_LARGO_MONO (8)."""
TIPO = "completa"

from mono_comun import correr_reglas  # noqa: E402
from mono_entornos import Configuraciones  # noqa: E402


def prueba():
    correr_reglas(Configuraciones)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
