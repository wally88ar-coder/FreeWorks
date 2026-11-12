# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Un marco soldado guardado con el FreeWorks anterior al 11/11 (marcas de esquina con NOMBRES y
alargues guardados en el Cuerpo: datos/marco_tope_anterior_11-11.FCStd, 600 x 400, caño 40x40, a
tope) se sigue entendiendo con las marcas nuevas (#2, #22): reconoce sus 4 esquinas a tope; sacar
una deja a 0 el alargue de esa punta y no toca el de la otra punta; pasar todo a inglete deja cada
caño con sus operaciones justas, sin la marca vieja, y después el marco sigue al esqueleto (ancho
800: ocupa -20..820)."""

import os  # noqa: E402
import shutil  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from comun import cerca  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
MUESTRA = os.path.join(AQUI, "datos", "marco_tope_anterior_11-11.FCStd")


def abrir():
    ruta = os.path.join(carpeta_temporal(), "marco_anterior.FCStd")
    shutil.copy(MUESTRA, ruta)  # la muestra no se toca
    doc = FreeCAD.openDocument(ruta)
    doc.recompute()
    return doc


def prueba():
    from swui.fork import weldments as w
    doc = abrir()
    cuerpos = w.members(doc)
    esquinas = w.find_corners(cuerpos)
    assert len(esquinas) == 4, len(esquinas)
    estados = [w.corner_state(c) for c in esquinas]
    assert all(e is not None and e[0] == "tope" and e[1] is not None for e in estados), estados

    # sacar una esquina: el que pasaba vuelve a 0 en esa punta y conserva el alargue de la otra
    c = esquinas[0]
    pasa = w.corner_state(c)[1]
    punta = c["end_a"] if pasa is c["a"] else c["end_b"]
    otra_antes = w.extension(pasa)[1 - punta]
    w.remove_corner(c["a"], c["b"])
    doc.recompute()
    assert w.corner_state(c) is None, "quedó algo de la esquina sacada"
    assert cerca(w.extension(pasa)[punta], 0.0), "el alargue de la esquina sacada quedó: %r" % (w.extension(pasa),)
    assert cerca(w.extension(pasa)[1 - punta], otra_antes), "sacar una esquina tocó la otra punta"
    FreeCAD.closeDocument(doc.Name)

    # todo a inglete y después cambiar el esqueleto
    doc = abrir()
    cuerpos = w.members(doc)
    w.apply_corners(cuerpos, "inglete")
    doc.recompute()
    for b in cuerpos:
        assert "SWUI_WeldExtTags" not in b.PropertiesList, "quedó la marca vieja en %s" % b.Label
        n = len([o for o in b.Group if w._role(o) is not None])
        assert n == 4, "%s quedó con %d operaciones de esquina (esperadas 4)" % (b.Label, n)
    sk = doc.getObject("Esqueleto")
    sk.setDatum(9, FreeCAD.Units.Quantity("800 mm"))
    doc.recompute()
    for b in cuerpos:
        bb = b.Shape.BoundBox
        assert b.Shape.isValid(), b.Label
        assert bb.XMin > -20.1 and bb.XMax < 820.1 and bb.YMin > -20.1 and bb.YMax < 420.1, \
            "%s sobresale: %s" % (b.Label, bb)
    assert max(b.Shape.BoundBox.XMax for b in cuerpos) > 819.9, "el marco no llega a 820"
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
