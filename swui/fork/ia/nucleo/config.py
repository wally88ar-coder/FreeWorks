# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Puerto y clave del puente IA. El puerto va en las preferencias de FreeCAD
(BaseApp/Preferences/Mod/SWUI/IA, Port). La clave va en un archivo propio
(<datos de usuario>/FreeWorks-IA/clave.txt) y no en user.cfg: FreeCAD reescribe user.cfg al
cerrarse, y así la clave se puede crear o leer con FreeCAD abierto o cerrado (por ejemplo al
conectar Claude Code). Se crea sola la primera vez y se puede cambiar desde
FreeWorks > IA > Conectar la IA (la vieja deja de servir).
"""

import os
import secrets

import FreeCAD

PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI/IA"
HOST = "127.0.0.1"  # solo en esta PC
DEFAULT_PORT = 47115
NAME = "freeworks"  # nombre del servidor para Claude Code y los demás programas


def _params():
    return FreeCAD.ParamGet(PARAMS)


def port():
    value = _params().GetInt("Port", DEFAULT_PORT)
    return value if 1024 < value < 65536 else DEFAULT_PORT


def _token_file():
    return os.path.join(data_dir(), "clave.txt")


def token():
    """La clave actual; si no hay, crea una."""
    try:
        with open(_token_file(), encoding="ascii") as fh:
            value = fh.read().strip()
    except OSError:
        value = ""
    return value or new_token()


def new_token():
    value = secrets.token_urlsafe(24)
    with open(_token_file(), "w", encoding="ascii") as fh:
        fh.write(value)
    return value


def url():
    return "http://%s:%d/mcp" % (HOST, port())


def claude_command():
    """La línea para conectar Claude Code (una sola vez por PC)."""
    return ('claude mcp add --scope user --transport http %s %s --header "Authorization: Bearer %s"'
            % (NAME, url(), token()))


def data_dir():
    """Carpeta propia de la IA dentro de la de usuario de FreeCAD (respaldos, pruebas)."""
    path = os.path.join(FreeCAD.getUserAppDataDir(), "FreeWorks-IA")
    os.makedirs(path, exist_ok=True)
    return path
