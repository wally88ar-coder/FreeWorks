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

Lógica en funciones (`is_grouped_question`, `listed_documents`, `route`, `step`); el filtro de Qt solo las llama.
`step` también la usa la esquina de confirmación (Cancelar croquis).
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


def step(doc_name, undo=True):
    """Deshace (o rehace) UN paso desde el documento doc_name, como Ctrl+Z con su vista 3D al frente (FreeCAD agrupa
    los otros documentos del mismo paso). El mensaje va solo a una vista: a todas, una planilla o un plano del mismo
    documento deshacían otro paso cada uno (revisión del 21/11). Sin vista 3D, en ese documento solo."""
    msg = "Undo" if undo else "Redo"
    gdoc = FreeCADGui.getDocument(doc_name)
    views = gdoc.mdiViewsOfType("Gui::View3DInventor") if gdoc is not None else []
    if views:
        view = views[0]
        if hasattr(view, "sendMessage"):
            view.sendMessage(msg)
            return "vista"
        if len(gdoc.mdiViewsOfType("Gui::MDIView")) == 1:
            gdoc.sendMsgToViews(msg)
            return "vista"
        return _step_active(view, msg)
    doc = FreeCAD.getDocument(doc_name)
    if undo:
        doc.undo()
    else:
        doc.redo()
    return "documento"


def _step_active(view, msg):
    """Varias vistas en el documento: se pone al frente un momento la 3D y se le manda el mensaje a ella sola."""
    from swui.compat import QtWidgets

    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    before = area.activeSubWindow() if area is not None else None
    target = None
    for sub in area.subWindowList() if area is not None else []:
        if sub.isAncestorOf(view.graphicsView()):
            target = sub
    if target is None:
        return None
    area.setActiveSubWindow(target)
    FreeCADGui.SendMsgToActiveView(msg)
    if before is not None and before is not target:
        area.setActiveSubWindow(before)
    return "vista activada"


def route(names, undo):
    """Deshacer (undo=True) o rehacer un paso en el primero de los documentos nombrados (el que tiene el paso
    más nuevo). Devuelve cómo lo hizo, o None si no había a dónde."""
    for name in names:
        if name not in FreeCAD.listDocuments():
            continue
        _state["routing"] = True
        try:
            return step(name, undo)
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

                    def later_answer():
                        try:
                            answer(box)
                        except RuntimeError:
                            pass  # el cartel ya no está

                    QtCore.QTimer.singleShot(0, later_answer)
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
