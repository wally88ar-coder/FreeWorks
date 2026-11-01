# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
IA en FreeWorks (plan en el documento "IA en FreeWorks: análisis y plan", enlace en
docs/ESTADO.md). Etapa 0: el puente.

Regla (decisión del usuario, 01/11): la IA usa a FreeWorks, pero FreeWorks no sabe que la IA
existe. El único enganche es la llamada a install() desde swui/fork/__init__.py; ningún otro
módulo importa nada de acá (el test lo verifica). Capas, cada una usa solo las de abajo:

- terceros/     código copiado de neka-nat/freecad-mcp y ghbalf/freecad-ai, con su aviso
- nucleo/       clave y puerto, prender/apagar el puente, Python seguro
- herramientas/ lo que la IA puede hacer, un archivo por área
- puertas/      menú FreeWorks > IA (y más adelante la pestaña Asistente)

Nada de la IA queda guardado en los archivos del usuario.
"""

COMMANDS = ("SWUI_IABridge", "SWUI_IAConnect")


def install():
    """Solo registra los comandos del menú; el puente arranca apagado y lo pesado se carga al
    prenderlo."""
    from swui.fork.ia.puertas import menu

    menu.install()
