# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de secuencias ("el mono", paso 8.3) en CHAPA, con la ventana (motor en `mono_comun.py`).
Arranque: una Brida base (por su panel) de un rectángulo. Seguidillas al azar de:
- Brida de arista y Dobladillo (Aceptar / Cancelar; Ctrl+Z y Ctrl+Y exactos);
- editar lo hecho (espesor de la brida base, largo de una brida o dobladillo) y Aceptar;
- desplegar y volver a plegar (Aplanar ida y vuelta): la chapa queda igual que antes;
- exportar el DXF: sale el archivo con contorno, y la chapa queda igual;
- suprimir, Deshacer / Rehacer, guardar y abrir.
Después de CADA paso: sin errores, nada colgado, sin objetos con error.
Seguidillas por regla: FW_CASOS_AZAR (6); largo: 3 a FW_LARGO_MONO (8)."""
TIPO = "completa"

from mono_comun import correr_reglas  # noqa: E402
from mono_entornos import Chapa  # noqa: E402


def prueba():
    correr_reglas(Chapa)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
