# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de secuencias ("el mono", paso 8.3) en ENSAMBLAJE, con la ventana (motor en
`mono_comun.py`). Arranque: conjunto guardado con dos piezas guardadas aparte, Placa (fija) y
Bloque. Seguidillas al azar de:
- Relación de posición, Matriz de componentes, Plano de ensamblaje, Taladro y Extruir corte de
  ensamblaje (Aceptar / Cancelar; Ctrl+Z y Ctrl+Y exactos, también en las piezas que cambian);
- suprimir el Bloque (como SW: se oculta) y Ctrl+Z;
- cambiar el largo del Bloque en su archivo y volver a ponerlo: el conjunto sin errores y, al
  volver la medida, como estaba;
- Deshacer / Rehacer, guardar y abrir (el conjunto y sus piezas).
Después de CADA paso: sin errores, nada colgado, sin objetos con error (en el conjunto y en las piezas).
Seguidillas por regla: FW_CASOS_AZAR (6); largo: 3 a FW_LARGO_MONO (8)."""
TIPO = "completa"

from mono_comun import correr_reglas  # noqa: E402
from mono_entornos import Ensamblaje  # noqa: E402


def prueba():
    correr_reglas(Ensamblaje, conocido_otra="#76")  # detrás de #3 (arreglado) apareció #76


from _base import ejecutar  # noqa: E402
ejecutar(globals())
