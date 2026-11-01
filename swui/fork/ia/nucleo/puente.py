# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Prender y apagar el puente IA: servidor MCP por HTTP en 127.0.0.1 (con clave), en un hilo
aparte. Cada herramienta corre en el hilo principal de FreeCAD a través de la cola copiada de
neka-nat (`terceros/gui_dispatch.py`): espera si el usuario está girando la pieza o tiene un menú
o una ventana abierta, y avisa si algo quedó trabado.

Las herramientas las arma quien prende el puente (`puertas/`) y se pasan en un ToolRegistry:
el núcleo no sabe cuáles son.
"""

import threading

import FreeCAD

from swui.compat import QtCore
from swui.fork.ia.nucleo import config
from swui.fork.ia.terceros import gui_dispatch, mcp_http, mcp_server
from swui.fork.ia.terceros.registry import ToolResult

_state = {"transport": None, "thread": None, "registry": None}


class _GuiExecutor:
    """Corre cada herramienta en el hilo principal (salvo las que manejan sus propios pasos)."""

    def __init__(self, registry):
        self.registry = registry

    def execute(self, name, args):
        args = args if isinstance(args, dict) else {}
        tool = self.registry.get(name)
        if tool is None or not tool.main_thread:
            return self.registry.execute(name, args)
        res = gui_dispatch.dispatch_to_gui(lambda: self.registry.execute(name, args),
                                           timeout=tool.timeout, operation_name=name)
        return as_result(res)


def as_result(res):
    """Lo que devuelve la cola (resultado, texto de error o dict de trabado) como ToolResult."""
    if isinstance(res, ToolResult):
        return res
    if isinstance(res, dict):
        return ToolResult(success=False, output="", error=str(res.get("error") or res))
    return ToolResult(success=False, output="", error=str(res))


def on_gui(task, timeout=60, name="FreeWorks"):
    """Correr task() en el hilo principal desde el hilo del servidor. task() devuelve un dict;
    si falla o se traba, el resultado es un dict con "error"."""
    res = gui_dispatch.dispatch_to_gui(task, timeout=timeout, operation_name=name)
    if isinstance(res, dict) and res.get("success") is False:
        return {"error": res.get("error")}
    if not isinstance(res, dict):
        # la cola devuelve el error como texto "Tipo: mensaje" cuando task() lanza una excepción
        return {"error": str(res)}
    return res


def running():
    return _state["transport"] is not None


def start(registry):
    """Prender el puente. Lanza OSError si el puerto está ocupado (lo avisa quien llama)."""
    if running():
        return config.url()
    transport = mcp_http.HTTPServerTransport(host=config.HOST, port=config.port(),
                                             auth_token=config.token())
    transport.bind()  # acá salta el error de puerto ocupado, antes de dar nada por prendido
    server = mcp_server.MCPServer(registry, executor=_GuiExecutor(registry))
    gui_dispatch.init_waker()
    QtCore.QTimer.singleShot(500, gui_dispatch.process_gui_tasks)  # latido de respaldo
    thread = threading.Thread(target=transport.serve, args=(server.handle,), daemon=True,
                              name="FreeWorks-IA")
    thread.start()
    _state.update(transport=transport, thread=thread, registry=registry)
    FreeCAD.Console.PrintMessage("FreeWorks: puente IA prendido en %s (%d herramientas).\n"
                                 % (config.url(), len(registry.list_tools())))
    return config.url()


def stop():
    transport = _state["transport"]
    if transport is None:
        return
    _state.update(transport=None, thread=None, registry=None)
    try:
        transport.stop()
    finally:
        gui_dispatch.request_shutdown()
        gui_dispatch.cleanup_waker()
    FreeCAD.Console.PrintMessage("FreeWorks: puente IA apagado.\n")
