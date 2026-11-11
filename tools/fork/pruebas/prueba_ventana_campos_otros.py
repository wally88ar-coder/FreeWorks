# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de campos (paso 8.4) en los paneles de SOLDADAS, ENSAMBLAJE, CROQUIS y otros, con la
ventana (motor en `campos_comun.py`): escribir lo que sea en un campo al azar y Aceptar o Cancelar:
sin errores de Python ni ventanas colgadas; lo aceptado es válido y se deshace exacto; Cancelar
deja todo igual. Casos por panel: FW_CASOS_CAMPOS (2; de noche 6)."""
TIPO = "completa"
TIEMPO_MAXIMO = 2400  # ~25 paneles: no entra en los 10 min de las demás

from campos_comun import correr_campos  # noqa: E402

# errores ya registrados que no frenan la búsqueda (como en las reglas de paneles)
DEUDA = {"Taladro de ensamblaje": (("#38", "The graph must be a DAG", None),),
         "Matriz de componentes": (("#32", "deleted object", None),)}
# los mismos errores cuando aparecen como una comprobación que falla (no en el informe)
DEUDA_PASOS = {"Taladro de ensamblaje": (("#37", "Ctrl+Z no volvió"), ("#37", "Ctrl+Y no lo trajo"))}


def prueba():
    import casos_croquis
    import casos_ensamblaje
    import casos_ensamblaje2
    import casos_otros
    import casos_soldadas
    correr_campos(casos_soldadas.CASOS + casos_ensamblaje.CASOS + casos_ensamblaje2.CASOS + casos_croquis.CASOS
                  + [c for c in casos_otros.CASOS if c.__name__ != "VistaSeccion"], DEUDA, DEUDA_PASOS)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
