# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#38, decisión del usuario 11/11): el Taladro de ensamblaje deja en la pieza una
COPIA CONGELADA del croquis (sin vínculo al ensamblaje): la operación de la pieza se llama
"... -> Conjunto" y dice de dónde viene y cuándo se copió. Guardar, cerrar y abrir el ensamblaje:
sin "The graph must be a DAG" y sin quedar modificado. Si el croquis del ensamblaje cambia sin
editar la operación (como con una ecuación), la pieza pasa a "->?" y la operación del ensamblaje
dice "(desactualizada)"; editarla desde el ensamblaje y Aceptar vuelve a copiar: "->", el agujero
en el lugar nuevo y sin "(desactualizada)"."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from casos_ensamblaje2 import TaladroEnsamblaje  # noqa: E402
from reglas_paneles import esperar_panel, informe_largo, tocar  # noqa: E402

V = FreeCAD.Vector


def _op(doc):
    from swui.fork import assembly_features as af
    ops = [o for o in doc.Objects if hasattr(o, af.KIND)]
    assert len(ops) == 1, [o.Label for o in ops]
    return ops[0]


def _centro_agujero(feat):
    """Centro (x, y) del agujero en la pieza: la cara cilíndrica del taladro."""
    caras = [f for f in feat.Shape.Faces if f.Surface.__class__.__name__ == "Cylinder"]
    assert caras, "la pieza no tiene agujero"
    c = caras[0].Surface.Center
    return round(c.x, 3), round(c.y, 3)


def prueba():
    from reglas_paneles import _report_view
    from swui.fork import assembly_features as af
    doc = FreeCAD.newDocument("Conjunto")
    caso = TaladroEnsamblaje()
    yield from caso.preparar(doc)
    doc, asm, placa = caso.doc, caso.asm, caso.comps[0]
    # croquis con un punto en la placa y el panel; Aceptar con lo que propone
    doc.openTransaction("Croquis de ensamblaje")
    sk = af.make_sketch(asm, placa, "%s.%s" % (placa.LinkedObject.Name, caso.cara_arriba(placa)))
    import Part
    sk.addGeometry(Part.Point(caso.local(sk, 30, 30)))
    sk.recompute()
    doc.commitTransaction()
    af.open_panel_new(asm, "hole", sk)
    yield from esperar_panel()
    yield 1000
    assert tocar(), "no encontré Aceptar"
    yield 2500
    v = _op(doc)
    ((_link, binder, feat),) = af.entries_of(v)
    assert not binder.Support, "la copia sigue enlazada al ensamblaje (#38)"
    assert getattr(binder, af.ORIGIN, "") and getattr(binder, af.COPIED, ""), "sin origen ni fecha"
    assert " -> " in feat.Label and "->?" not in feat.Label, "nombre en la pieza: %r" % feat.Label
    c0 = _centro_agujero(feat)

    # guardar, cerrar y abrir: sin el aviso del círculo y sin quedar modificado
    pdoc = feat.Document
    ruta = doc.FileName
    doc.save()
    pdoc.save()
    yield 1500
    # solo el ensamblaje, como el mono (abrirlo con las piezas cerradas lo deja modificado aunque no
    # tenga taladro: es otra cosa, ver ESTADO)
    FreeCAD.closeDocument(doc.Name)
    yield 800
    desde = informe_largo()
    doc = FreeCAD.openDocument(ruta)
    yield 3000
    texto = _report_view().toPlainText()[desde:]
    assert "DAG" not in texto, "al abrir: %s" % texto[-400:]
    # "modificado al abrir" pasa igual sin taladro: lo cubre prueba_ventana_ensamblaje_abrir_modificado (#79)

    # el croquis cambia sin editar la operación: '->?' y '(desactualizada)'
    v = _op(doc)
    sk = getattr(v, af.SKETCH)
    g = sk.Geometry
    pt = g[0]
    pt.X, pt.Y = pt.X + 15, pt.Y + 5
    sk.Geometry = [pt] + list(g[1:])
    doc.recompute()
    yield 2000
    ((_link, binder, feat),) = af.entries_of(v)
    assert "->?" in feat.Label, "la pieza no avisa que quedó desactualizada: %r" % feat.Label
    assert "(desactualizada)" in v.Label, "el ensamblaje no marca la operación: %r" % v.Label

    # editar desde el ensamblaje y Aceptar: vuelve a copiar
    af.open_panel(v)
    yield from esperar_panel()
    yield 1000
    assert tocar(), "no encontré Aceptar al editar"
    yield 2500
    ((_link, binder, feat),) = af.entries_of(v)
    feat.Document.recompute()
    assert " -> " in feat.Label and "->?" not in feat.Label, "después de editar: %r" % feat.Label
    assert "(desactualizada)" not in v.Label, v.Label
    assert not binder.Support, "al editar quedó enlazada otra vez"
    c1 = _centro_agujero(feat)
    assert c1 != c0, "el agujero no se movió al lugar nuevo (%s)" % (c1,)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
