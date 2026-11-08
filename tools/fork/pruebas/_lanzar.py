# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Lo que abre FreeCAD (o FreeCADCmd) para correr UNA prueba: deja a mano la carpeta de pruebas y el
addon (FreeCAD con ventana no hace caso de PYTHONPATH) y corre la prueba que dice FW_PRUEBA. Si
la prueba ni siquiera carga (error de escritura), lo anota como resultado y cierra FreeCAD: si
no, la ventana quedaba abierta hasta que correr.py la cortaba por tiempo.
"""

import json
import os
import runpy
import sys
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(os.path.dirname(os.path.dirname(AQUI)))
for carpeta in (ADDON, AQUI):
    if carpeta not in sys.path:
        sys.path.insert(0, carpeta)
try:
    import _base  # adentro del try: un error de escritura en _base también se anota y cierra
    if os.environ.get("FW_COBERTURA"):
        # medir desde ANTES de cargar la prueba: así cuentan también las líneas de nivel de
        # módulo (def, class, import) de lo que la prueba carga por primera vez
        _base.COV = _base._cobertura()
    runpy.run_path(os.environ["FW_PRUEBA"], run_name="__main__")
except Exception:
    salida = os.environ.get("FW_RESULTADO")
    if salida:
        with open(salida, "w", encoding="utf-8") as fh:
            json.dump({"que": "", "conocido": "", "ok": False,
                       "error": "la prueba no cargó:\n" + traceback.format_exc(limit=6)}, fh, ensure_ascii=False)
    import FreeCAD
    if FreeCAD.GuiUp:
        import FreeCADGui
        from PySide import QtCore
        QtCore.QTimer.singleShot(300, FreeCADGui.getMainWindow().close)
