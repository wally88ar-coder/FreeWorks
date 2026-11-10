# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Piezas comunes: cada tarea delicada escrita UNA sola vez (plan de calidad del 08/11/2026,
`docs/PLAN_CALIDAD.md`). La auditoría del 08/11 mostró que varios errores eran la misma tarea
hecha distinto en módulos distintos (borrar una operación, abrir algo deshacible con un panel
abierto, escuchas que actúan al abrir un archivo, paneles que el guardia no conoce, el nombre
interno de un documento guardado en un archivo). Los módulos nuevos usan estas funciones; los
viejos se pasan a ellas al tocarlos.

Sin interfaz se pueden usar todas (las pruebas corren con FreeCADCmd); lo de paneles no hace
nada si no hay ventana.
"""

import contextlib
import os

import FreeCAD

BODY = "PartDesign::Body"


# --- Borrar una operación -----------------------------------------------------------------


def body_of(obj):
    """El Cuerpo que contiene a obj (o obj mismo si es un Cuerpo); None si no hay."""
    seen = 0
    while obj is not None and seen < 20:
        if obj.TypeId == BODY:
            return obj
        try:
            obj = obj.getParentGeoFeatureGroup()
        except Exception:
            return None
        seen += 1
    return None


def remove_feature(feature, show_tip=True):
    """
    Borra una operación de su Cuerpo sin dejar a la siguiente sin base.

    FreeCAD: `doc.removeObject` solo, sobre una operación del medio, deja la siguiente con
    BaseFeature vacía y el Cuerpo pierde todo lo anterior (Issue #1: volumen de 1968 a 1000).
    `body.removeObject` primero reengancha la siguiente a la anterior y, si era la punta, pasa
    la punta a la anterior (comprobado en 1.1.4). Con ventana, deja a la vista la nueva punta
    (PartDesign oculta las anteriores; sin esto el sólido "desaparece", visto el 07/11).
    Devuelve el Cuerpo (o None si la operación no estaba en uno). No sirve para un Cuerpo entero
    (sus operaciones y su origen quedarían sueltos): eso da ValueError.
    """
    if feature.TypeId == BODY:
        raise ValueError("remove_feature no borra Cuerpos enteros: %s" % feature.Label)
    doc = feature.Document
    body = body_of(feature)
    if body is not None:
        body.removeObject(feature)
    doc.removeObject(feature.Name)
    if body is not None and show_tip:
        show_body_tip(body)
    return body


def show_body_tip(body):
    """Con ventana: la punta del Cuerpo a la vista y las operaciones anteriores ocultas."""
    if not FreeCAD.GuiUp:
        return
    try:
        tip = body.Tip
        if tip is None:
            return
        if not tip.ViewObject.Visibility:
            for o in body.Group:
                if o is not tip and o.isDerivedFrom("PartDesign::Feature"):
                    o.ViewObject.Visibility = False
            tip.ViewObject.Visibility = True
    except Exception:
        pass


# --- Algo que se pueda deshacer -------------------------------------------------------------


def task_open(doc=None):
    """
    Hay un panel abierto en Tareas (del fork o nativo). Con `doc`: y ese documento es el activo
    (los paneles trabajan sobre el documento activo; un panel sobre otro documento no cuenta).
    """
    if not FreeCAD.GuiUp:
        return False
    try:
        import FreeCADGui
        if not FreeCADGui.Control.activeDialog():
            return False
        return doc is None or FreeCAD.ActiveDocument is doc
    except Exception:
        return False


_open_steps = set()  # documentos con un undo_step propio abierto (para anidarlos)


@contextlib.contextmanager
def undo_step(doc, name):
    """
    Un paso de deshacer con nombre, sin romper el Cancelar de un panel abierto:

        with safe_ops.undo_step(doc, "Material"):
            ...cambios...

    FreeCAD no anida transacciones: abrir una nueva CONFIRMA la que esté abierta (la de un panel,
    la de un comando o la de otro undo_step), y después su Cancelar ya no deshace (Issue #3). Por
    eso, si ya hay una transacción abierta, o un panel abierto sobre este documento, los cambios
    se suman a esa (el Cancelar del panel los deshace también) y no se abre ni se confirma nada:
    devuelve False. Si no, abre un paso propio (devuelve True); si algo falla adentro, se anula y
    se relanza.

    Cómo se ve una transacción abierta en 1.1.4 (comprobado): `doc.HasPendingTransaction` recién
    se prende con el primer cambio; `FreeCAD.getActiveTransaction()` ya da algo apenas se abre
    (también con `doc.openTransaction`). Límite: un panel que no abre transacción (solo muestra
    datos) también hace que se sume: ese cambio queda sin paso de deshacer propio.
    """
    join = (doc.Name in _open_steps or bool(getattr(doc, "HasPendingTransaction", False))
            or bool(_active_transaction()) or task_open(doc))
    if join:
        yield False
        return
    doc.openTransaction(name)
    _open_steps.add(doc.Name)
    try:
        yield True
    except BaseException:
        _open_steps.discard(doc.Name)
        doc.abortTransaction()
        raise
    _open_steps.discard(doc.Name)
    end_step(doc)


def end_step(doc, abort=False):
    """
    Cierra la transacción de un panel o comando (abort=True la anula, como Cancelar). En 1.1.4
    (probado con FreeCADCmd): si no hubo cambios, `doc.abortTransaction()` / `commitTransaction()`
    dejan abierta la de la aplicación (`FreeCAD.getActiveTransaction()` la sigue dando), y lo
    próximo que haga el usuario, en cualquier documento, se suma a ese paso (Issue #60). Acá se
    cierra también esa.
    """
    if abort:
        doc.abortTransaction()
    else:
        doc.commitTransaction()
    try:
        if _active_transaction() and not getattr(doc, "HasPendingTransaction", False):
            # la de la aplicación es una sola para todos los documentos: si mientras tanto se
            # cambió algo en OTRO (quedó en este mismo paso), anularla lo desharía sin avisar;
            # entonces se confirma (queda como un paso de deshacer en ese documento)
            otros = any(getattr(d, "HasPendingTransaction", False)
                        for d in FreeCAD.listDocuments().values() if d is not doc)
            FreeCAD.closeActiveTransaction(bool(abort) and not otros)
    except Exception:
        pass


def _active_transaction():
    try:
        return FreeCAD.getActiveTransaction()
    except Exception:
        return None


# --- Escuchas de documento -------------------------------------------------------------------


def doc_busy(doc):
    """
    FreeCAD está abriendo el archivo o deshaciendo/rehaciendo: una escucha no debe cambiar nada
    (si cambia algo al abrir, el archivo queda "modificado" sin que el usuario toque nada: Issue
    #28; si cambia al deshacer, el deshacer queda a medias). En 1.1.4 los avisos de "empieza a
    abrir" no llegan a Python (slotStartRestoreDocument no se llama nunca); `Restoring` y
    `Transacting` sí. Cerrar un documento no se puede detectar (no hay `Closing` en 1.1.4).
    """
    try:
        return bool(getattr(doc, "Restoring", False) or getattr(doc, "Transacting", False))
    except Exception:
        return True


class QuietObserver:
    """
    Base para escuchas de documento (FreeCAD.addDocumentObserver). Las subclases empiezan cada
    aviso con `if self.busy(doc): return`. (No necesita __init__: se puede heredar sin llamar a
    super().)
    """

    def busy(self, doc):
        return doc_busy(doc)


# --- Paneles ---------------------------------------------------------------------------------


def show_panel(panel):
    """
    Abre un panel del fork en Tareas y lo anota en el guardia de paneles (`panel_guard`): otro
    comando de la cinta lo cancela de verdad y, si FreeCAD lo cierra por su cuenta, su escucha se
    apaga y se llama a su `panel._orphaned()` (si lo tiene) para limpiar lo que dibujó (Issues #6
    y #12). Todo panel nuevo debe abrirse con esto y tener `_orphaned` si dibuja algo.
    """
    if not FreeCAD.GuiUp:
        return False
    import FreeCADGui
    from swui.fork import panel_guard
    panel_guard.track(panel)
    FreeCADGui.Control.showDialog(panel)
    return True


# --- Referencias a otro documento ------------------------------------------------------------


UNSAVED = "sin_guardar:"


def doc_key(doc):
    """
    Cómo guardar en un archivo a qué documento apunta algo: la ruta del archivo (estable), no
    `doc.Name` (cambia: dos "Placa.FCStd" de carpetas distintas son "Placa" y "Placa1";
    Issue #5). Un documento sin guardar da "sin_guardar:<nombre interno>", que solo vale mientras
    siga sin guardar (quien la use tiene que volver a pedir la clave después de guardar).
    Límite: la ruta es absoluta; para una copia del proyecto en otra carpeta, el que la use tiene
    que resolverla relativa a su propio archivo (eso va en el arreglo de #5).
    """
    path = getattr(doc, "FileName", "") or ""
    return os.path.normcase(os.path.abspath(path)) if path else UNSAVED + doc.Name


def find_doc(key):
    """El documento abierto que corresponde a `doc_key`, o None."""
    if not key:
        return None
    docs = FreeCAD.listDocuments()
    if key.startswith(UNSAVED):
        doc = docs.get(key[len(UNSAVED):])
        # solo si sigue sin guardar: otro documento con el mismo nombre interno no es el mismo
        return doc if doc is not None and not (getattr(doc, "FileName", "") or "") else None
    norm = os.path.normcase(os.path.abspath(key))
    for doc in docs.values():
        path = getattr(doc, "FileName", "") or ""
        if path and os.path.normcase(os.path.abspath(path)) == norm:
            return doc
    return None
