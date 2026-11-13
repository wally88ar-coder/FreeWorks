# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#60: en FreeCAD 1.1.4, doc.abortTransaction() / commitTransaction() sin cambios dejan abierta la
transacción de la aplicación, y lo próximo que hace el usuario se suma a ese paso. Todo el código
propio (swui/fork, salvo la IA, que es aparte, y safe_ops mismo) cierra los pasos con
safe_ops.end_step: esta prueba avisa si vuelve a aparecer una llamada cruda (con archivo y renglón)."""

import glob  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(AQUI, "..", "..", ".."))
CRUDA = re.compile(r"\b(?!FreeCAD\.|App\.)[\w.]+\.(abortTransaction|commitTransaction)\(\)")


def prueba():
    malos = []
    for ruta in sorted(glob.glob(os.path.join(RAIZ, "swui", "fork", "**", "*.py"), recursive=True)):
        rel = os.path.relpath(ruta, RAIZ).replace("\\", "/")
        if "/ia/" in rel or rel.endswith("safe_ops.py"):
            continue
        with open(ruta, encoding="utf-8") as fh:
            for n, linea in enumerate(fh, 1):
                codigo = linea.split("#", 1)[0]
                if CRUDA.search(codigo):
                    malos.append("%s:%d: %s" % (rel, n, linea.strip()))
    assert not malos, "cerrar con safe_ops.end_step (#60):\n" + "\n".join(malos)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
