# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#22, soldadas (decisión del usuario 11/11: "como SW", la copia queda independiente): copiar un
marco soldado (con lo que depende, como Ctrl+C / Ctrl+V) da caños cuyas esquinas son con los caños
COPIADOS, no con los originales. Cambiar las esquinas de la copia (a inglete) no toca el original,
y borrar un caño del original no le saca nada a la copia. Las marcas viejas (nombres) se siguen
leyendo."""

import FreeCAD  # noqa: E402

from comun import cerca, marco  # noqa: E402


def prueba():
    from swui.fork import weldments as w
    doc = FreeCAD.newDocument("CopiarMarco")
    _sk, _cota, cuerpos = marco(doc, esquina="tope")
    vol = {b.Name: b.Shape.Volume for b in cuerpos}
    antes = set(o.Name for o in doc.Objects)
    doc.copyObject(cuerpos, True)  # con lo que depende: como Ctrl+C / Ctrl+V con dependencias
    doc.recompute()
    copias = [o for o in doc.Objects if o.Name not in antes and w.is_member(o)]
    assert len(copias) == 4, "no se copiaron los 4 caños: %s" % [o.Name for o in copias]
    rutas_copia = set(w._route_of(c).Name for c in copias)
    for c in copias:
        for o in c.Group:
            if w._role(o) is not None:
                ref = w._with(o)
                assert ref is not None and ref.Name in rutas_copia, \
                    "%s de %s es con %s (del original, #22)" % (o.Label, c.Label, getattr(ref, "Name", None))
    estados = sorted(str(w.corner_state(x)[0]) for x in w.find_corners(copias))
    assert estados == ["tope"] * 4, "la copia no reconoce sus esquinas: %s" % estados

    # cambiar las esquinas de la copia no toca el original
    w.apply_corners(copias, "inglete")
    doc.recompute()
    for b in cuerpos:
        assert cerca(b.Shape.Volume, vol[b.Name], 0.5), "cambiar la copia cambió el original %s" % b.Label
    assert sorted(str(w.corner_state(x)[0]) for x in w.find_corners(cuerpos)) == ["tope"] * 4
    assert sorted(str(w.corner_state(x)[0]) for x in w.find_corners(copias)) == ["inglete"] * 4
    # sin operaciones de más: por esquina a inglete, una ruta y una caja en cada caño
    for c in copias:
        n = len([o for o in c.Group if w._role(o) is not None])
        assert n == 4, "%s quedó con %d operaciones de esquina (esperadas 4)" % (c.Label, n)

    # borrar un caño del original no le saca nada a la copia
    ops = {c.Name: len([o for o in c.Group if w._role(o) is not None]) for c in copias}
    vol_c = {c.Name: c.Shape.Volume for c in copias}
    w._forget(cuerpos[0])
    doc.recompute()
    for c in copias:
        assert len([o for o in c.Group if w._role(o) is not None]) == ops[c.Name], \
            "borrar un caño del original le sacó operaciones a la copia %s" % c.Label
        assert cerca(c.Shape.Volume, vol_c[c.Name], 0.5), "borrar en el original cambió la copia %s" % c.Label
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
