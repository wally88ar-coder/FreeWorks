# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
"Deshacer el último pedido" (decisión del usuario, 01/11: un solo Ctrl+Z por pedido; plan B).

FreeCAD 1.1.4 no anida los pasos de deshacer: abrir uno con otro abierto cierra el de afuera, y lo
que se hace después del interno queda SIN paso (probado en freecadcmd, 01/11). Como los paneles y
las funciones de FreeWorks abren el suyo, un pedido con varias operaciones deja varios pasos. Por
eso: la IA marca el comienzo del pedido y, si hay que volver atrás, se deshacen de una vez todos
los pasos que aparecieron desde entonces.
"""

from swui.fork.ia.herramientas import comun as c
from swui.fork.ia.nucleo.deshacer import new_steps  # noqa: F401  (también lo usan paneles y el test)
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult


def pedido(accion, titulo="", documento=None):
    doc = c.document(documento)
    state = c._state
    if accion == "empezar":
        state["pedido"] = {"doc": doc.Name, "snap": list(doc.UndoNames), "titulo": titulo or "pedido"}
        return ToolResult(success=True, output="Pedido \"%s\" empezado." % (titulo or "pedido"))
    info = state.get("pedido")
    if not info or info["doc"] != doc.Name:
        return c.fail("No hay un pedido empezado en %s (usá pedido con accion='empezar' al comenzar)." % doc.Label)
    k = new_steps(list(doc.UndoNames), info["snap"])
    if accion == "ver":
        return ToolResult(success=True, output="Pedido \"%s\": %s pasos de deshacer desde que empezó."
                          % (info["titulo"], "?" if k is None else k),
                          data={"pasos": list(doc.UndoNames)[:k or 0]})
    if accion == "deshacer":
        c.require_free()
        if k is None:
            return c.fail("El historial de deshacer cambió desde que empezó el pedido (¿deshizo algo a mano?). "
                          "Deshaga con Ctrl+Z mirando la lista.")
        names = list(doc.UndoNames)[:k]
        for _ in range(k):
            doc.undo()
        doc.recompute()
        state.pop("pedido", None)
        return ToolResult(success=True, output="Deshecho el pedido \"%s\": %d pasos (%s)."
                          % (info["titulo"], k, ", ".join(names)))
    if accion == "terminar":
        state.pop("pedido", None)
        return ToolResult(success=True, output="Pedido \"%s\" terminado: dejó %s pasos de deshacer."
                          % (info["titulo"], "?" if k is None else k))
    return c.fail("Acción \"%s\" desconocida." % accion)


def register(registry):
    registry.register(ToolDefinition(
        name="pedido",
        description=("Agrupa un pedido del usuario para poder deshacerlo entero. Al empezar un pedido que "
                     "cambia la pieza: accion='empezar' con un título. Si el usuario quiere volver atrás todo "
                     "el pedido: accion='deshacer' (deshace de una vez todos los pasos que dejó, también los "
                     "de paneles). 'ver' dice cuántos pasos lleva; 'terminar' lo cierra."),
        parameters=[ToolParam("accion", "string", "empezar, ver, deshacer o terminar",
                              enum=["empezar", "ver", "deshacer", "terminar"]),
                    ToolParam("titulo", "string", "Qué pidió el usuario, en pocas palabras", required=False),
                    ToolParam("documento", "string", "Documento (por defecto el activo)", required=False)],
        handler=c.guarded(pedido), category="cambiar", timeout=120))
