# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de campos (paso 8.4) en los paneles de PIEZA, con la ventana (motor en `campos_comun.py`):
en cada panel (redondeo, chaflán, ángulo de salida, matrices, simetría, plano, eje, punto, combinar,
mover cara, extruir, corte, revolución, taladro, mover/copiar y eliminar/conservar sólidos, chapa),
escribir lo que sea en un campo al azar y Aceptar o Cancelar: sin errores de Python ni ventanas
colgadas; lo aceptado es válido y se deshace exacto; Cancelar deja todo igual.
Casos por panel: FW_CASOS_CAMPOS (2; de noche 6)."""
TIPO = "completa"
TIEMPO_MAXIMO = 2400  # ~25 paneles: no entra en los 10 min de las demás

from campos_comun import correr_campos  # noqa: E402


def prueba():
    import casos_grupo3
    import casos_pieza
    import casos_pieza2
    correr_campos(casos_pieza.CASOS + casos_pieza2.CASOS + casos_grupo3.CASOS)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
