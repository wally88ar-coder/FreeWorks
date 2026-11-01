# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Código ajeno copiado adentro de FreeWorks (decisión del usuario, 2026-11-01: copiar los pedazos
útiles, no instalar los complementos). No sabe nada de FreeWorks; lo usa `swui/fork/ia/nucleo`.

Origen de cada archivo (para traer sus arreglos a mano, como con el original de upstream):

- `gui_dispatch.py`, `dispatch_health.py`: neka-nat/freecad-mcp
  (https://github.com/neka-nat/freecad-mcp, carpeta addon/FreeCADMCP/rpc_server/), commit 8babe99
  del 2026-10-25. Licencia MIT, Copyright (c) 2025 Shirokuma (k tanaka): texto completo en
  `LICENCIA-MIT-neka-nat.txt`.
- `mcp_protocol.py`, `mcp_http.py`, `mcp_server.py`, `registry.py`: ghbalf/freecad-ai
  (https://github.com/ghbalf/freecad-ai, carpeta freecad_ai/), commit 08d637d del 2026-10-16.
  Licencia LGPL-2.1-or-later (la misma de FreeWorks), autor Alfred Mickautsch.

Cada cambio nuestro va marcado en el código con un comentario "FreeWorks:". Los comentarios del
código original quedan en inglés, como estaban.
"""
