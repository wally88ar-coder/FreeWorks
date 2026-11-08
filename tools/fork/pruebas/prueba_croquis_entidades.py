# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Las herramientas de entidades del croquis (Simetría, Mover, Copiar, Girar, Escalar, Matriz
lineal, Equidistanciar) corren todos los casos de `tools/fork/test_sketch_entities.py` sin error
y ningún croquis queda con relaciones redundantes ni en conflicto."""

import contextlib  # noqa: E402
import io  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import runpy  # noqa: E402

from _base import AQUI  # noqa: E402


def prueba():
    viejo = os.path.join(os.path.dirname(AQUI), "test_sketch_entities.py")
    texto = io.StringIO()
    with contextlib.redirect_stdout(texto):
        runpy.run_path(viejo, run_name="__main__")
    salida = texto.getvalue()
    casos = [l for l in salida.splitlines() if " red " in l and " conf " in l]
    assert len(casos) >= 15, "corrieron solo %d casos:\n%s" % (len(casos), salida[-1500:])
    malos = [l for l in casos if re.search(r"red \[[^\]]", l) or re.search(r"conf \[[^\]]", l)]
    assert not malos, "con redundantes o en conflicto:\n" + "\n".join(malos)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
