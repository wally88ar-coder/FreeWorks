# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Herramientas que el puente le ofrece a la IA, un archivo por área. Etapa 0: ver (estado y
captura) y Python seguro. Las de pieza, chapa, ensamblaje y planos van en archivos propios y
entran por la "ventanilla" de cada módulo (comandos SWUI_ o una función pública), nunca por sus
funciones internas.
"""


def register_all(registry):
    """Cargar todas las herramientas en el registro (lo llama la puerta que prende el puente)."""
    from swui.fork.ia.herramientas import python, ver

    ver.register(registry)
    python.register(registry)
    return registry
