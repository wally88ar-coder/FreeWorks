# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Como SW 2018 (probado con el mouse el 12/11): Cancelar un taladro NUEVO no deja nada, ni el
taladro (aunque haya pasado por "Editar posiciones") ni el croquis de posiciones que armó el
asistente (pedido del usuario: "igual que SW"). Sin ventana se prueba lo de abajo del panel:
- drop_new_hole después de "Editar posiciones": se borran el taladro, su copia en otro sólido (la de
  verdad, hecha por el Alcance, sin dejar su vínculo suelto) y el croquis del asistente, sin dejar al
  Cuerpo sin lo anterior, en un solo paso de deshacer (Ctrl+Z devuelve todo); con un croquis del
  usuario, el croquis queda y a la vista;
- Cancelar sin pasar por Posiciones: se va el croquis del asistente; sin nada que borrar, ni un paso
  de deshacer vacío ni se toca la visibilidad de nada;
- un croquis del asistente que usa otra operación queda;
- las marcas van por objeto, no por nombre (revisión del 12/11): un croquis nuevo con el nombre de
  uno del asistente ya borrado no es del asistente; la marca se consume una vez, y si el asistente
  soltó el croquis sin taladro, a los pocos segundos deja de valer;
- "recién creado" = lo anotó el escucha de creación y su transacción sigue abierta: un taladro
  "Sin norma" que ya existía, editado con una transacción ajena abierta, NO es nuevo;
- la marca "vuelve de Editar posiciones" sirve una vez, para ese taladro, y vence sola."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402

V = FreeCAD.Vector


def _tipos(doc, tipo):
    return [o.Name for o in doc.Objects if o.TypeId == tipo]


def _armar(nombre):
    doc = FreeCAD.newDocument(nombre)
    doc.UndoMode = 1
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 40, 30, 20
    otro = doc.addObject("PartDesign::Body", "Otro")
    caja2 = otro.newObject("PartDesign::AdditiveBox", "Caja2")  # encimado: el taladro lo cruza
    caja2.Length, caja2.Width, caja2.Height = 40, 30, 20
    doc.recompute()
    doc.openTransaction("Croquis")
    sk = _croquis(body, caja, "Posiciones")
    doc.commitTransaction()
    doc.recompute()
    return doc, body, caja, otro, sk


def _croquis(body, caja, nombre):
    sk = body.newObject("Sketcher::SketchObject", nombre)
    sk.AttachmentSupport = [(caja, "Face6")]
    sk.MapMode = "FlatFace"
    sk.addGeometry(Part.Point(V(10, 10, 0)))
    return sk


def _taladro(doc, body, sk, nombre="Taladro"):
    from swui.fork import hole_panel as hp
    doc.openTransaction("Taladro")
    hole = body.newObject("PartDesign::Hole", nombre)
    hp.note_created(hole)  # lo que hace el escucha de creación con la ventana
    hole.Profile = (sk, ["Vertex1"])
    hole.Diameter, hole.Depth = 6, 10
    doc.recompute()
    return hole


def _despues_de_posiciones(hp, mb, croquis_del_asistente):
    """Taladro nuevo con copia por Alcance, que pasó por Editar posiciones (ya guardado) y se cancela."""
    doc, body, caja, otro, sk = _armar("TaladroPos")
    try:
        hole = _taladro(doc, body, sk)
        assert hp.just_created(hole), "un taladro recién creado no cuenta como nuevo"
        creadas, _b, problemas = mb.apply_scope(hole, [body, otro])
        doc.commitTransaction()
        doc.recompute()
        assert creadas and not problemas, "el Alcance no hizo la copia: %s" % (problemas,)
        assert _tipos(doc, "PartDesign::SubShapeBinder"), "la copia no tiene vínculo: no prueba la revisión"
        vol = caja.Shape.Volume
        assert hole.isValid() and body.Shape.Volume < vol - 1, "el taladro de la prueba no agujerea"
        sk.Visibility = False  # como lo deja PartDesign al usarlo el taladro
        pasos = doc.UndoCount
        borrar_croquis = "Posiciones" if croquis_del_asistente else None
        assert hp.drop_new_hole(doc, "Taladro", borrar_croquis), "no borró el taladro sin aceptar"
        assert not _tipos(doc, "PartDesign::Hole"), "quedó el taladro o su copia: %s" % _tipos(doc, "PartDesign::Hole")
        assert not _tipos(doc, "PartDesign::SubShapeBinder"), "quedó suelto el vínculo de la copia"
        assert abs(body.Shape.Volume - vol) < 1e-6, "el Cuerpo no volvió a la caja sin agujero"
        assert body.Tip is caja, "la punta del Cuerpo quedó en %s" % (body.Tip.Name if body.Tip else None)
        assert doc.UndoCount == pasos + 1, "no es un solo paso de deshacer (%d)" % (doc.UndoCount - pasos)
        assert not FreeCAD.getActiveTransaction(), "quedó una transacción abierta"
        if croquis_del_asistente:
            assert doc.getObject("Posiciones") is None, "quedó el croquis de posiciones del asistente (SW no lo deja)"
        else:
            assert doc.getObject("Posiciones") is not None, "se llevó un croquis que el usuario ya tenía"
            assert sk.Visibility, "el croquis del usuario quedó oculto"
        doc.undo()
        doc.recompute()
        assert doc.getObject("Taladro") is not None and doc.getObject("Posiciones") is not None, \
            "Ctrl+Z no devolvió el taladro y su croquis"
    finally:
        FreeCAD.closeDocument(doc.Name)


def _marcas(hp):
    doc, body, caja, _otro, sk = _armar("TaladroMarcas")
    try:
        # croquis del asistente: por objeto; uno nuevo con el mismo nombre no hereda la marca
        hp.mark_hole_sketch(sk)
        assert hp.is_hole_sketch(sk), "no quedó marcado el croquis del asistente"
        nombre = sk.Name
        body.removeObject(sk)
        doc.removeObject(nombre)  # el usuario sale del croquis sin dibujar: FreeWorks lo borra
        nuevo = _croquis(body, caja, "Posiciones")
        doc.recompute()
        assert nuevo.Name == nombre, "FreeCAD no repitió el nombre (%s): la prueba no prueba la revisión" % nuevo.Name
        assert not hp.is_hole_sketch(nuevo), "un croquis del usuario heredó la marca de uno borrado con su nombre"
        hp.mark_hole_sketch(nuevo)
        assert hp.take_hole_sketch(nuevo), "no tomó la marca del croquis del asistente"
        assert not hp.take_hole_sketch(nuevo), "la marca del croquis sirvió dos veces"
        # el asistente lo soltó sin taladro (p. ej. Extruir desde el croquis): un rato después ya no es suyo
        hp.mark_hole_sketch(nuevo)
        hp.release_hole_sketch(nuevo)
        assert hp.is_hole_sketch(nuevo), "recién soltado (el taladro arranca enseguida) dejó de ser del asistente"
        hp._wizard_sketches[-1][1] -= hp.WIZARD_RELEASE_S + 1
        assert not hp.take_hole_sketch(nuevo), "un croquis soltado hace rato sigue siendo del asistente"

        # recién creado: escucha + transacción abierta; un "Sin norma" que ya existía, no
        h = _taladro(doc, body, nuevo)
        doc.commitTransaction()
        doc.recompute()
        hp._new_holes.clear()  # pasó el tiempo / es de antes (se abrió de un archivo)
        h.ThreadType = "None"  # "Sin norma (diámetro a mano)"
        doc.openTransaction("Otra cosa")
        h.Label = h.Label + " "
        assert doc.HasPendingTransaction, "la transacción de la prueba no quedó abierta"
        assert not hp.just_created(h), "un taladro Sin norma que ya existía cuenta como nuevo"
        doc.abortTransaction()
        hp.note_created(h)
        hp._new_holes[-1] = (h, hp._new_holes[-1][1] - hp.NEW_HOLE_S - 1)
        doc.openTransaction("Otra cosa")
        h.Label = h.Label + " "
        assert not hp.just_created(h), "un taladro creado hace rato cuenta como nuevo"
        doc.abortTransaction()

        # la marca de vuelta de Editar posiciones
        hp.set_reopen_mark(h, True)
        assert hp._take_reopen_mark(caja) == (False, False), "la marca sirvió para otro objeto"
        hp.set_reopen_mark(h, True)
        assert hp._take_reopen_mark(h) == (True, True), "no reconoció el taladro que vuelve de Editar posiciones"
        assert hp._take_reopen_mark(h) == (False, False), "la marca sirvió dos veces"
        hp.set_reopen_mark(h)
        hp._reopen_mark["until"] -= hp.REOPEN_MARK_S + 1
        assert hp._take_reopen_mark(h) == (False, False), "una marca vencida sigue valiendo"
        assert not hp.drop_new_hole(None, "Taladro"), "borró algo sin documento"
    finally:
        FreeCAD.closeDocument(doc.Name)


def prueba():
    from swui.fork import hole_panel as hp
    from swui.fork import multibody as mb
    _despues_de_posiciones(hp, mb, True)
    _despues_de_posiciones(hp, mb, False)
    _marcas(hp)

    # Cancelar sin pasar por Posiciones: el panel ya deshizo el taladro
    for del_asistente in (True, False):
        doc, body, caja, _otro, sk = _armar("TaladroCancelar")
        try:
            _taladro(doc, body, sk)
            doc.abortTransaction()  # lo que hace el Cancelar del panel
            doc.recompute()
            assert doc.getObject("Taladro") is None, "el taladro de la prueba no se deshizo"
            sk.Visibility = False  # el usuario lo tenía oculto: Cancelar no lo tiene que mostrar
            pasos = doc.UndoCount
            borro = hp.drop_new_hole(doc, None, "Posiciones" if del_asistente else None)
            if del_asistente:
                assert borro and doc.getObject("Posiciones") is None, "quedó el croquis del asistente"
                assert body.Tip is caja, "la punta del Cuerpo quedó en %s" % (body.Tip.Name if body.Tip else None)
                assert doc.UndoCount == pasos + 1, "no es un solo paso de deshacer"
            else:
                assert not borro and doc.getObject("Posiciones") is not None, "tocó el croquis del usuario"
                assert not sk.Visibility, "mostró un croquis que el usuario tenía oculto"
                assert doc.UndoCount == pasos, "dejó un paso de deshacer sin cambios"
            assert not FreeCAD.getActiveTransaction(), "quedó una transacción abierta"
        finally:
            FreeCAD.closeDocument(doc.Name)

    # croquis del asistente que ya usa otra operación (otro taladro aceptado): queda
    doc, body, caja, _otro, sk = _armar("TaladroCompartido")
    try:
        _taladro(doc, body, sk, "Aceptado")
        doc.commitTransaction()
        _taladro(doc, body, sk, "Taladro")
        doc.commitTransaction()  # pasó por Editar posiciones
        doc.recompute()
        assert hp.drop_new_hole(doc, "Taladro", "Posiciones"), "no borró el taladro sin aceptar"
        assert doc.getObject("Taladro") is None, "quedó el taladro sin aceptar"
        assert doc.getObject("Aceptado") is not None, "se llevó el otro taladro"
        assert doc.getObject("Posiciones") is not None, "se llevó un croquis que usa otro taladro"
    finally:
        FreeCAD.closeDocument(doc.Name)
    hp._new_holes.clear()
    hp._wizard_sketches.clear()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
