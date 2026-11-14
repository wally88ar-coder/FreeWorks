# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Un ensamblaje recién abierto sin cambios no queda "modificado" (#79).

FreeCAD 1.1.4 con el banco Ensamblaje cargado deja tocados los vínculos de los componentes al abrir
el archivo (del lado de C++, pasa también sin FreeWorks) y el documento queda como modificado: al
cerrarlo pregunta si guardar aunque no se haya tocado nada. SW no pregunta, salvo que una pieza haya
cambiado con el ensamblaje cerrado (ahí sí lo actualiza y queda para guardar).

`settle_after_open(doc)` borra esa marca solo si no cambió nada de verdad:
- ninguna pieza que usa se guardó después que el ensamblaje (con 2 s de margen por "guardar todo");
- ninguna pieza que usa está abierta con cambios sin guardar;
- al abrir no se reparó ninguna relación (eso lo dice quien llama: `repaired`).
Si algo de eso pasó, la marca queda (como SW, queda para guardar).
"""

import os

import FreeCAD

MARGIN_S = 2.0
last = {"reason": ""}  # por qué quedó (o no) la marca la última vez: para las pruebas y el registro


LINKS = ("App::Link", "Assembly::AssemblyLink")


def is_touched(obj):
    """¿Quedó por recalcular? (no todos los objetos tienen isTouched, p. ej. el ensamblaje)"""
    try:
        return "Touched" in obj.State
    except Exception:
        return False


def _linked_docs(doc, seen=None):
    """Los documentos que usa `doc`, también los de sus subensamblajes (revisión del 14/11)."""
    seen = {doc.Name: doc} if seen is None else seen
    for o in doc.Objects:
        if o.TypeId not in LINKS:
            continue
        found = []
        for get in (lambda: o.getLinkedObject(True), lambda: getattr(o, "LinkedObject", None)):
            try:
                found.append(get())
            except Exception:
                pass
        for linked in found:
            d = getattr(linked, "Document", None)
            if d is not None and d.Name not in seen:
                seen[d.Name] = d
                _linked_docs(d, seen)
    return [d for n, d in seen.items() if d is not doc]


def unchanged_since_save(doc):
    """True si ninguna pieza que usa `doc` cambió después de guardarlo (ver el módulo)."""
    try:
        saved = os.path.getmtime(doc.FileName)
    except Exception:
        return False
    for d in _linked_docs(doc):
        if not d.FileName:
            return False  # una pieza sin guardar nunca: es un cambio
        try:
            if os.path.getmtime(d.FileName) > saved + MARGIN_S:
                return False
        except Exception:
            return False
        if getattr(FreeCAD, "GuiUp", False):
            import FreeCADGui

            g = FreeCADGui.getDocument(d.Name)
            if g is not None and g.Modified:
                return False
    return True


def settle_after_open(doc, repaired=False, touched=None):
    """Borrar la marca de "modificado" que deja FreeCAD al abrir un ensamblaje sin cambios (#79).
    `touched`: los objetos que dejó tocados la carga (si no se da, los de ahora). Solo se borra si
    son todos componentes (vínculos): si el archivo se guardó con algo por recalcular, eso queda
    (revisión del 14/11). Devuelve True si la borró."""
    def no(reason):
        last["reason"] = reason
        FreeCAD.Console.PrintLog("[SWUI fork] Marca de modificado al abrir %s: queda (%s)\n" % (doc.Label, reason))
        return False

    if repaired or not getattr(FreeCAD, "GuiUp", False) or not doc.FileName:
        return no("se reparó una relación" if repaired else "sin archivo")
    import FreeCADGui

    g = FreeCADGui.getDocument(doc.Name)
    if g is None or not g.Modified:
        return no("no estaba modificado")
    if not unchanged_since_save(doc):
        return no("una pieza cambió después de guardar el ensamblaje")
    if touched is None:
        touched = {o.Name for o in doc.Objects if is_touched(o)}
    objs = [doc.getObject(n) for n in touched]
    otros = [n for n, o in zip(touched, objs) if o is None or o.TypeId not in LINKS]
    if otros:  # algo más que los componentes quedó por recalcular: no es la marca de FreeCAD
        return no("por recalcular al abrir: %s" % ", ".join(sorted(otros)))
    now = [o for o in doc.Objects if is_touched(o)]
    otros = [o.Name for o in now if o.Name not in touched and o.TypeId not in LINKS]
    if otros:
        return no("quedaron por recalcular: %s" % ", ".join(sorted(otros)))
    last["reason"] = "borrada"
    for o in now:
        try:
            o.purgeTouched()
        except Exception:
            pass
    g.Modified = False
    return True


# --- Abrir una pieza en su ventana con el ensamblaje abierto (#79) ----------------------------

_bursts = {}  # documento -> {"clean", "other": [cambios que no son la marca de vínculo], "links": set()}
_timers = {}
_opening = set()  # ensamblajes recién abiertos: los mira `settle_after_open`, no este escucha
_cleared = {}  # documento -> cuándo se borró la marca (dos borrados seguidos no: revisión del 14/11)
QUIET_MS = 250
AGAIN_S = 1.0  # una carga partida en dos tandas (más de QUIET_MS entre una y otra) no borra dos veces


def _gui_modified(doc):
    try:
        import FreeCADGui

        g = FreeCADGui.getDocument(doc.Name)
        return bool(g is not None and g.Modified)
    except Exception:
        return True


def _settle_links(doc_name):
    """Fin de una tanda de cambios: si fueron solo los `_LinkTouched` que pone FreeCAD al abrir en
    su ventana una pieza que el ensamblaje ya tenía cargada (sin cambios), se saca la marca."""
    import time

    _timers.pop(doc_name, None)
    burst = _bursts.pop(doc_name, None)
    if not burst or doc_name in _opening:
        return False

    def no(reason):
        last["reason"] = reason
        return False

    if not burst["clean"]:
        return no("ya estaba modificado")
    if burst["other"]:
        return no("cambió además: %s" % ", ".join(sorted(set(burst["other"]))[:8]))
    if not burst["links"]:
        return False
    if time.time() - _cleared.get(doc_name, 0) < AGAIN_S:
        return no("se borró hace un momento")
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        return False
    if not _gui_modified(doc):
        return False
    if not unchanged_since_save(doc):
        return no("una pieza en disco es más nueva que el ensamblaje")
    for name in burst["links"]:
        o = doc.getObject(name)
        if o is None:
            return False
        try:
            d = o.getLinkedObject(True).Document
        except Exception:
            return False
        if d is not doc and _gui_modified(d):
            return no("la pieza tiene cambios")  # el ensamblaje cambió de verdad (SW lo actualiza)
    for name in burst["links"]:
        try:
            doc.getObject(name).purgeTouched()
        except Exception:
            pass
    import FreeCADGui

    FreeCADGui.getDocument(doc.Name).Modified = False
    _cleared[doc_name] = time.time()
    last["reason"] = "borrada (pieza abierta en su ventana)"
    return True


def _restart(doc_name):
    """La tanda termina cuando no llegan cambios por QUIET_MS (una carga larga no la parte en dos)."""
    from swui.compat import QtCore

    t = _timers.get(doc_name)
    if t is None:
        t = QtCore.QTimer()
        t.setSingleShot(True)
        t.timeout.connect(lambda n=doc_name: _settle_links(n))
        _timers[doc_name] = t
    t.start(QUIET_MS)


class _Observer:
    def slotChangedObject(self, obj, prop):
        try:
            doc = obj.Document
        except Exception:
            return
        if doc.Name not in _bursts:
            if prop != "_LinkTouched":
                return  # solo interesa una tanda que empieza con la marca de vínculo
            if not any(o.TypeId == "Assembly::AssemblyObject" for o in doc.Objects):
                return
            _bursts[doc.Name] = {"clean": not _gui_modified(doc), "other": [], "links": set()}
        burst = _bursts[doc.Name]
        if prop == "_LinkTouched" and obj.TypeId in LINKS:
            burst["links"].add(obj.Name)
        else:
            burst["other"].append("%s.%s" % (obj.Name, prop))
        _restart(doc.Name)

    def slotDeletedDocument(self, doc):
        for d in (_bursts, _timers, _cleared):
            d.pop(doc.Name, None)
        _opening.discard(doc.Name)


_installed = {"done": False}


def install():
    if not _installed["done"] and getattr(FreeCAD, "GuiUp", False):
        _installed["done"] = True
        FreeCAD.addDocumentObserver(_Observer())
