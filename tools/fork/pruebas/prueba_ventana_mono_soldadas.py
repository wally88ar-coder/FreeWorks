# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de secuencias ("el mono", paso 8.3) en PIEZAS SOLDADAS, con la ventana (motor en
`mono_comun.py`, entorno en `mono_entornos.py`). Arranque: marco de 4 caños cuadrados con inglete
sobre un esqueleto rectangular. Seguidillas al azar de:
- Miembro estructural, Esquinas, Cartela y Tapa de extremo (Aceptar / Cancelar; Ctrl+Z y Ctrl+Y
  exactos); editar un miembro cambiando la medida;
- mover un vértice del esqueleto: los caños lo siguen sin superponerse ni dejar huecos y la lista
  de cortes da el largo real; al volverlo, todo como estaba;
- Deshacer / Rehacer, guardar y abrir.
Errores ya registrados que el mono anota sin frenarse: #2, #6, #40.
Seguidillas por regla: FW_CASOS_AZAR (6); largo: 3 a FW_LARGO_MONO (8)."""
TIPO = "completa"

from mono_comun import correr_reglas  # noqa: E402
from mono_entornos import Soldada  # noqa: E402


def prueba():
    correr_reglas(Soldada)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
