# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Cerrar un paso de deshacer que no cambió nada (un panel que se cancela o se acepta sin tocar
nada) no deja abierta la transacción de la aplicación (Issue #60): FreeCAD 1.1.4 la deja abierta si
solo se llama doc.abortTransaction() / commitTransaction(), y lo próximo que haga el usuario, en
cualquier documento, se suma a ese paso. Se prueba:
- que FreeCAD sigue haciendo eso (si un día lo arregla, avisa: se puede simplificar end_step);
- safe_ops.end_step, anulando y confirmando, sin cambios y con cambios;
- safe_ops.undo_step sin cambios;
- que después, un cambio en OTRO documento no queda en un paso abierto."""

import FreeCAD  # noqa: E402

from _base import traza  # noqa: E402


def _activa():
    return FreeCAD.getActiveTransaction()


def prueba():
    from swui.fork import safe_ops
    doc = FreeCAD.newDocument("TransVacia")
    otro = FreeCAD.newDocument("TransOtro")
    try:
        for d in (doc, otro):
            d.UndoMode = 1
        # lo que hace FreeCAD solo
        doc.openTransaction("Nativo")
        doc.abortTransaction()
        nativo = _activa()
        FreeCAD.closeActiveTransaction(True)
        if nativo:
            traza("  FreeCAD 1.1.4 deja abierta la transacción vacía (%s): end_step hace falta" % (nativo,))
        else:
            traza("  AVISO: esta versión de FreeCAD ya cierra la transacción vacía (end_step sobra)")
        assert _activa() is None, "no se pudo limpiar la transacción de la prueba"

        problemas = []
        for abort in (True, False):
            for con_cambios in (False, True):
                doc.openTransaction("Panel")
                if con_cambios:
                    doc.addObject("App::FeaturePython", "Cosa")
                safe_ops.end_step(doc, abort=abort)
                quedo = _activa()
                if quedo:
                    problemas.append("end_step(abort=%s, %s cambios) dejó abierta %s"
                                     % (abort, "con" if con_cambios else "sin", quedo))
                    FreeCAD.closeActiveTransaction(True)
        n = len(doc.Objects)
        assert n == 1, "end_step: anular no deshizo o confirmar no dejó el objeto (%d objetos)" % n

        with safe_ops.undo_step(doc, "Nada") as propio:
            assert propio, "undo_step no abrió un paso propio (quedó algo abierto antes)"
        if _activa():
            problemas.append("undo_step sin cambios dejó abierta %s" % (_activa(),))
            FreeCAD.closeActiveTransaction(True)

        # lo que ve el usuario: un panel cancelado sin cambios y después un cambio en otro archivo
        doc.openTransaction("Cartela")
        safe_ops.end_step(doc, abort=True)
        antes = otro.UndoCount
        otro.addObject("App::FeaturePython", "Suelto")
        if otro.HasPendingTransaction:
            problemas.append("un cambio en otro documento quedó en un paso abierto (%s)" % (_activa(),))
        if otro.UndoCount != antes:
            problemas.append("un cambio sin paso propio se sumó a un paso de deshacer (%d -> %d)"
                             % (antes, otro.UndoCount))
        # un panel en un documento, sin cambios, mientras se cambia algo en otro: Cancelar no
        # tiene que deshacer lo del otro
        FreeCAD.closeActiveTransaction(False)
        doc.openTransaction("Panel en el primero")
        otro.addObject("App::FeaturePython", "DelOtro")
        safe_ops.end_step(doc, abort=True)
        if otro.getObject("DelOtro") is None:
            problemas.append("Cancelar un panel sin cambios deshizo un cambio hecho en otro documento")
        if _activa():
            problemas.append("con un cambio en otro documento, quedó abierta %s" % (_activa(),))
        assert not problemas, "\n".join(problemas)
        traza("  sin transacciones colgadas")
    finally:
        try:
            FreeCAD.closeActiveTransaction(True)
        except Exception:
            pass
        for d in (doc, otro):
            FreeCAD.closeDocument(d.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
