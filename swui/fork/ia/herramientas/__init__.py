# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Herramientas que el puente le ofrece a la IA, un archivo por área. Etapa 0: ver (estado y
captura) y Python seguro. Etapa 1a: pieza_ver (geometría, elegir, cotas, medir, verificar...);
1b: pieza_cambiar (cotas, árbol, configuraciones, material, comandos). Las de pieza, chapa, ensamblaje y planos van en archivos propios y
entran por la "ventanilla" de cada módulo (comandos SWUI_ o una función pública), nunca por sus
funciones internas.
"""


def register_all(registry):
    """Cargar todas las herramientas en el registro (lo llama la puerta que prende el puente)."""
    from swui.fork.ia.herramientas import pedido, pieza_cambiar, pieza_ver, python, ver

    ver.register(registry)
    python.register(registry)
    pieza_ver.register(registry)  # etapa 1a: mirar y elegir
    pieza_cambiar.register(registry)  # etapa 1b: cambiar valores
    pedido.register(registry)  # deshacer un pedido entero
    return registry
