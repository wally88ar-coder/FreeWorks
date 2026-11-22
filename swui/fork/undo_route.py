# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Deshacer / Rehacer editando una pieza dentro del ensamblaje, sin preguntar (#113, como SW).

Editando una pieza, cada paso de la pieza queda también en el ensamblaje ("-> paso"; FreeCAD los agrupa con
el mismo número de transacción). Si uno de los dos documentos tiene además un paso propio más nuevo (por
ejemplo, mover un componente) y se deshace desde el otro, FreeCAD 1.1.4 (Gui::Document::checkTransactionID)
pregunta "Hay transacciones de grupo en los siguientes documentos con otras transacciones anteriores...
Sí / No / Abort". SW nunca pregunta: deshace lo último que se hizo.

Lo que hace FreeWorks, solo mientras se edita una pieza: cuando FreeCAD va a hacer esa pregunta, la contesta
"Abort" (FreeCAD no deshace nada) y deshace (o rehace) en el documento que FreeCAD nombra, que es el que
tiene el paso más nuevo: un solo paso, el que haría SW. El Ctrl+Z siguiente sigue normal. Si al hacerlo
FreeCAD volviera a preguntar (los dos documentos con pasos propios encima del grupo), se contesta "Sí":
FreeCAD deshace el grupo entero en los dos y quedan parejos.

Lógica en funciones (`is_grouped_question`, `listed_documents`, `route`); el filtro de Qt solo las llama.
"""

import traceback

import FreeCAD
import FreeCADGui

_filter = None
_state = {"routing": False}


def _editing_any():
    try:
        from swui.fork import edit_part as ep

        return bool(ep._editing)
    except Exception:
        return False


def is_grouped_question(box):
    """True si el cartel es la pregunta de FreeCAD por transacciones de grupo (Deshacer o Rehacer)."""
    from swui.compat import QtWidgets

    if not isinstance(box, QtWidgets.QMessageBox):
        return False
    B = QtWidgets.QMessageBox.StandardButton
    want = B.Yes | B.No | B.Abort
    try:
        if box.standardButtons() != want:
            return False
    except Exception:
        return False
    text = box.text() or ""
    return ("transacciones de grupo" in text or "grouped transactions" in text) and bool(listed_documents(text))


def is_undo(box):
    """La pregunta viene de Deshacer (True) o de Rehacer (False): FreeCAD pone el título."""
    title = (box.windowTitle() or "").strip().lower()
    return not (title.startswith("rehacer") or title.startswith("redo"))


def listed_documents(text):
    """Los documentos (nombre interno) que FreeCAD lista en la pregunta, en orden."""
    out = []
    for line in (text or "").splitlines():
        if not line.startswith("    "):
            continue
        name = line.strip()
        if name and name != "..." and name in FreeCAD.listDocuments():
            out.append(name)
    return out


def _gui_step(doc_name, undo):
    """Deshace (o rehace) un paso desde el documento doc_name, como si su vista estuviera al frente (con su
    vista: FreeCAD agrupa los otros documentos); sin vista, en ese documento solo."""
    gdoc = FreeCADGui.getDocument(doc_name)
    views = gdoc.mdiViewsOfType("Gui::View3DInventor") if gdoc is not None else []
    if len(views) == 1:
        gdoc.sendMsgToViews("Undo" if undo else "Redo")
        return "vista"
    doc = FreeCAD.getDocument(doc_name)
    if undo:
        doc.undo()
    else:
        doc.redo()
    return "documento"


def route(names, undo):
    """Deshacer (undo=True) o rehacer un paso en el primero de los documentos nombrados (el que tiene el paso
    más nuevo). Devuelve cómo lo hizo, o None si no había a dónde."""
    for name in names:
        if name not in FreeCAD.listDocuments():
            continue
        _state["routing"] = True
        try:
            return _gui_step(name, undo)
        finally:
            _state["routing"] = False
    return None


def answer(box):
    """Contesta la pregunta: "Abort" y después el paso en el documento que corresponde; "Sí" si ya se estaba
    desviando (para no preguntar en ronda)."""
    from swui.compat import QtCore, QtWidgets

    B = QtWidgets.QMessageBox.StandardButton
    if _state["routing"]:
        box.button(B.Yes).click()
        return
    names = listed_documents(box.text())
    undo = is_undo(box)
    box.button(B.Abort).click()

    def later():
        try:
            how = route(names, undo)
            FreeCAD.Console.PrintLog("[SWUI fork] %s sin preguntar en %s (%s)\n" % (
                "Deshacer" if undo else "Rehacer", names, how))
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Deshacer editando una pieza:\n%s\n" % traceback.format_exc())

    QtCore.QTimer.singleShot(0, later)


def _make_filter():
    from swui.compat import QtCore, QtWidgets

    class _Filter(QtCore.QObject):
        def eventFilter(self, obj, ev):
            try:
                if (ev.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QMessageBox)
                        and _editing_any() and is_grouped_question(obj)):
                    box = obj
                    QtCore.QTimer.singleShot(0, lambda: answer(box))
            except Exception:
                pass
            return False

    return _Filter()


def install():
    global _filter
    if _filter is not None:
        return
    from swui.compat import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    _filter = _make_filter()
    app.installEventFilter(_filter)
