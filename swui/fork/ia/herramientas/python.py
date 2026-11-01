# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Herramienta "ejecutar_python": scripts escritos en el momento para lo puntual o raro (decisión del
usuario, 01/11). Lo frecuente o delicado va en herramientas propias. La ejecución segura está en
`nucleo/ejecutar.py`; esta herramienta maneja sus propios pasos (main_thread=False) porque la
prueba aparte no debe frenar la ventana de FreeCAD.
"""

import json

from swui.fork.ia.nucleo import ejecutar
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult


def ejecutar_python(codigo, titulo="Script de la IA", probar=True):
    res = ejecutar.run_safe(codigo, titulo, bool(probar))
    detail = res.get("detalle") or {}
    if not res["ok"]:
        text = res["mensaje"]
        if detail:
            text += "\n" + json.dumps(detail, ensure_ascii=False, default=str)
        return ToolResult(success=False, output="", error=text)
    return ToolResult(success=True, output=res["mensaje"], data=detail)


def register(registry):
    registry.register(ToolDefinition(
        name="ejecutar_python",
        description=(
            "Corre un script de Python en el FreeWorks abierto (FreeCAD 1.1.4), para pedidos puntuales "
            "que no tienen herramienta propia. Antes hace una copia de respaldo y lo prueba en un "
            "FreeCAD aparte sin pantalla: si ahí falla, se cuelga o deja operaciones con error, no "
            "toca la pieza. Después lo corre como UN paso de Ctrl+Z. El script queda escrito en la "
            "consola de Python. Variables disponibles: App/FreeCAD, Gui/FreeCADGui, doc (documento "
            "activo o None), Part, PartDesign, Sketcher, math; print() vuelve como salida. Preferí "
            "objetos nativos de Part Design (Cuerpo, croquis, Pad, Pocket...) con nombres claros. "
            "probar=false solo para cambios visuales que la prueba aparte no puede ver."),
        parameters=[
            ToolParam("codigo", "string", "El script de Python"),
            ToolParam("titulo", "string", "Qué hace, en pocas palabras (nombre del paso de deshacer)",
                      required=False, default="Script de la IA"),
            ToolParam("probar", "boolean", "Probar antes en un FreeCAD aparte", required=False,
                      default=True),
        ],
        handler=ejecutar_python,
        category="python",
        main_thread=False,
    ))
