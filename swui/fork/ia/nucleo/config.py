# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Puerto y clave del puente IA, guardados en las preferencias de FreeCAD
(BaseApp/Preferences/Mod/SWUI/IA). La clave se crea sola la primera vez y se puede cambiar
desde FreeWorks > IA > Conectar la IA (la vieja deja de servir).
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


def token():
    """La clave actual; si no hay, crea una."""
    value = _params().GetString("Token", "")
    if not value:
        value = new_token()
    return value


def new_token():
    value = secrets.token_urlsafe(24)
    _params().SetString("Token", value)
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
