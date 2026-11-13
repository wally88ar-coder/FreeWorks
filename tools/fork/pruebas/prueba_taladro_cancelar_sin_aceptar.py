# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Como SW 2018 (probado con el mouse el 12/11): un taladro NUEVO que pasó por "Editar
posiciones" y después se cancela no deja nada. Sin ventana se prueba lo de abajo del panel:
- drop_unconfirmed borra el taladro y su copia en otro sólido (la de verdad, hecha por el Alcance,
  con su vínculo al croquis: no queda ningún vínculo suelto) sin dejar al Cuerpo sin lo anterior;
  el croquis de los centros queda, a la vista; es un solo paso de deshacer (Ctrl+Z lo devuelve);
- solo cuenta como nuevo un taladro recién creado por el comando (transacción abierta y sin norma
  todavía): una transacción que quedó abierta por otra cosa no alcanza (revisión del 12/11);
- la marca "vuelve de Editar posiciones" sirve una sola vez, solo para ese taladro, y vence sola
  (una marca colgada haría que Cancelar en una edición común borrara un taladro que ya existía)."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402

V = FreeCAD.Vector


def _pieza(doc, nombre, x):
    body = doc.addObject("PartDesign::Body", nombre)
    caja = body.newObject("PartDesign::AdditiveBox", "Caja" + nombre)
    caja.Length, caja.Width, caja.Height = 40, 30, 20
    caja.Placement.Base = V(x, 0, 0)
    return body, caja


class _Muerto:
    Document = None
    Name = "Nada"


def _tipos(doc, tipo):
    return [o.Name for o in doc.Objects if o.TypeId == tipo]


def prueba():
    from swui.fork import hole_panel as hp
    from swui.fork import multibody as mb
    doc = FreeCAD.newDocument("TaladroCancelar")
    doc.UndoMode = 1
    try:
        body, caja = _pieza(doc, "Cuerpo", 0)
        otro, _caja2 = _pieza(doc, "Otro", 0)  # encimado: el taladro lo atraviesa también
        sk = body.newObject("Sketcher::SketchObject", "Posiciones")
        sk.AttachmentSupport = [(caja, "Face6")]
        sk.MapMode = "FlatFace"
        sk.addGeometry(Part.Point(V(10, 10, 0)))
        doc.recompute()
        doc.openTransaction("Taladro")
        hole = body.newObject("PartDesign::Hole", "Taladro")
        assert hp.just_created(hole), "un taladro recién creado no cuenta como nuevo"
        hole.Profile = (sk, ["Vertex1"])
        hole.Diameter, hole.Depth = 6, 10
        doc.recompute()
        creadas, _b, problemas = mb.apply_scope(hole, [body, otro])  # Alcance: también en "Otro"
        doc.commitTransaction()
        doc.recompute()
        assert creadas and not problemas, "el Alcance no hizo la copia: %s" % (problemas,)
        assert mb.copies_of(hole), "la copia no quedó marcada como copia del taladro"
        assert _tipos(doc, "PartDesign::SubShapeBinder"), "la copia no tiene vínculo: no prueba la revisión"
        vol = caja.Shape.Volume
        assert hole.isValid() and body.Shape.Volume < vol - 1, "el taladro de la prueba no agujerea"
        sk.Visibility = False  # como lo deja PartDesign al usarlo el taladro

        pasos = doc.UndoCount
        assert hp.drop_unconfirmed(hole), "no borró el taladro sin aceptar"
        assert not _tipos(doc, "PartDesign::Hole"), "quedó el taladro o su copia: %s" % _tipos(doc, "PartDesign::Hole")
        sueltos = _tipos(doc, "PartDesign::SubShapeBinder")
        assert not sueltos, "quedó el vínculo de la copia suelto: %s" % sueltos
        assert doc.getObject("Posiciones") is not None, "se llevó el croquis de los centros"
        assert sk.Visibility, "el croquis de los centros quedó oculto"
        assert abs(body.Shape.Volume - vol) < 1e-6, "el Cuerpo no volvió a la caja sin agujero"
        assert doc.UndoCount == pasos + 1, "el borrado no es un solo paso (%d)" % (doc.UndoCount - pasos)
        assert not FreeCAD.getActiveTransaction(), "quedó una transacción abierta"
        doc.undo()
        doc.recompute()
        h = doc.getObject("Taladro")
        assert h is not None, "Ctrl+Z no devolvió el taladro"

        # "nuevo" = recién creado: una transacción ajena abierta con un taladro que ya tiene norma, no
        h.ThreadType = "ISOMetricProfile"
        doc.openTransaction("Otra cosa")
        h.Label = h.Label + " "
        assert doc.HasPendingTransaction, "la transacción de la prueba no quedó abierta"
        assert not hp.just_created(h), "un taladro con norma y una transacción ajena cuenta como nuevo"
        doc.abortTransaction()

        # la marca
        hp.set_reopen_mark(h)
        assert not hp._take_reopen_mark(caja), "la marca sirvió para otro objeto"
        hp.set_reopen_mark(h)
        assert hp._take_reopen_mark(h), "no reconoció el taladro que vuelve de Editar posiciones"
        assert not hp._take_reopen_mark(h), "la marca sirvió dos veces"
        hp.set_reopen_mark(h)
        hp._reopen_mark["until"] -= hp.REOPEN_MARK_S + 1
        assert not hp._take_reopen_mark(h), "una marca vencida sigue valiendo"
        assert not hp.drop_unconfirmed(_Muerto()), "borró algo sin taladro"
    finally:
        FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
