# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Reordenar operaciones arrastrándolas en el árbol, como SW (decisión del usuario, 15/11: "Mover arriba /
Mover abajo" salen del clic derecho).

Medido en FreeCAD 1.1.4 (sondeo del 15/11): soltar una operación sobre otra del mismo Cuerpo NO la
reordena; FreeCAD la convierte en "BaseFeature" del Cuerpo y la saca del orden. Por eso, dentro de
LikeSolidWorks UI, el arrastre de UNA operación sobre otra operación del mismo Cuerpo lo atiende
FreeWorks: la mitad de arriba del renglón de destino = antes de esa operación; la de abajo = después.
Por debajo es el mismo "mover" del árbol (feature_tree.move), un lugar por vez, en un solo paso de
deshacer, con su croquis y volviendo a buscar las aristas de los redondeos.

No se puede dejar una operación arriba de algo de lo que depende, ni abajo de algo que depende de
ella (como SW: el cursor muestra que no se puede soltar). Todo lo demás (arrastrar croquis, cuerpos,
componentes, a otro Cuerpo...) sigue siendo de FreeCAD.
"""

import traceback

import FreeCAD
import FreeCADGui


ITEM_DATA = "application/x-qabstractitemmodeldatalist"  # lo que arrastra el árbol (no un archivo)


def drop_index(feats, feature, target, before):
    """Lugar final de feature en feats si se suelta antes/después de target. None si no se mueve."""
    if feature is target or feature not in feats or target not in feats:
        return None
    i, j = feats.index(feature), feats.index(target)
    if j > i:  # bajando: target sube un lugar al sacar feature
        dest = j - 1 if before else j
    else:
        dest = j if before else j + 1
    return None if dest == i else dest


def blocker(feats, feature, dest, ancestors):
    """Por qué no se puede llevar feature al lugar dest (None = se puede). ancestors(obj) -> set/list."""
    i = feats.index(feature)
    if dest < i:
        for other in feats[dest:i]:
            if other in ancestors(feature):
                return "%s depende de %s (usa su geometría)." % (feature.Label, other.Label)
    else:
        for other in feats[i + 1:dest + 1]:
            if feature in ancestors(other):
                return "%s depende de %s (usa su geometría)." % (other.Label, feature.Label)
    return None


def reorder(feature, target, before):
    """
    Lleva feature antes (before=True) o después de target, en el mismo Cuerpo, en un solo paso de
    deshacer. Devuelve (perdidas, motivo): perdidas = [(operación, aristas que no se encontraron)] como
    feature_tree.move; motivo = por qué no se pudo (y entonces no cambia nada).
    """
    from swui.fork import feature_tree as ft

    body = ft.body_of(feature)
    if body is None or ft.body_of(target) is not body:
        return [], "Solo se puede reordenar dentro de la misma pieza."
    feats = ft.features(body)
    dest = drop_index(feats, feature, target, before)
    if dest is None:
        return [], None
    why = blocker(feats, feature, dest, ft.ancestors)
    if why:
        return [], why
    steps = dest - feats.index(feature)
    direction = "down" if steps > 0 else "up"

    def run():
        lost = []
        for _k in range(abs(steps)):
            lost += ft.move(feature, direction) or []
        return lost

    return ft._transaction(feature.Document, "Mover", run) or [], None


# --- Interfaz -----------------------------------------------------------------------------------------


def _tree_of(viewport):
    try:
        tree = viewport.parent()
        return tree if tree is not None and tree.metaObject().className() == "Gui::TreeWidget" else None
    except Exception:
        return None


def _pos(event):
    try:
        return event.position().toPoint()  # Qt6
    except Exception:
        return event.pos()


def _dragged():
    """La operación que se arrastra: el árbol de FreeCAD arrastra lo elegido. Una sola, en un Cuerpo."""
    from swui.fork import feature_tree as ft

    try:
        sel = FreeCADGui.Selection.getSelection()
    except Exception:
        return None
    if len(sel) != 1 or not ft.is_feature(sel[0]) or ft.body_of(sel[0]) is None:
        return None
    return sel[0]


def target_at(tree, pos, feature):
    """(operación de destino, antes) para el renglón bajo pos, o (None, None) si no es del mismo Cuerpo."""
    from swui.fork import feature_tree as ft

    item = tree.itemAt(pos)
    if item is None:
        return None, None
    body = ft.body_of(feature)
    # el renglón tiene que ser del mismo documento y del mismo Cuerpo (puede haber otro documento
    # abierto con una operación del mismo nombre; revisión del 15/11)
    chain, up = [], item.parent()
    while up is not None:
        chain.append(up)
        up = up.parent()
    texts = [i.text(0) for i in chain]
    if body.Label not in texts or (texts and texts[-1] != feature.Document.Label):
        return None, None
    label = item.text(0)
    target = None
    for obj in body.Group:
        if obj.Label == label:
            target = obj
            break
    if target is not None and ft.is_sketch(target):
        # un croquis cuenta como la operación que lo usa (en SW van juntos)
        users = [f for f in ft.features(body) if ft._profile_sketch(f) is target]
        target = users[0] if users else None
    if target is None or not ft.is_feature(target):
        return None, None
    rect = tree.visualItemRect(item)
    return target, pos.y() < rect.center().y()


_line = {}  # la línea que muestra dónde va a quedar (como la flecha de SW)


def _show_line(tree, target, before):
    from swui.compat import QtWidgets

    vp = tree.viewport()
    line = _line.get("w")
    try:
        if line is None or line.parent() is not vp:
            line = QtWidgets.QFrame(vp)
            line.setObjectName("SWUI_drop_line")
            line.setStyleSheet("background: #1f6fd0;")
            _line["w"] = line
    except RuntimeError:  # el árbol se volvió a crear
        line = QtWidgets.QFrame(vp)
        line.setStyleSheet("background: #1f6fd0;")
        _line["w"] = line
    rect = None
    from swui.compat import QtWidgets as W
    it = W.QTreeWidgetItemIterator(tree)
    while it.value():
        if it.value().text(0) == target.Label:
            rect = tree.visualItemRect(it.value())
            break
        it += 1
    if rect is None:
        hide_line()
        return
    y = rect.top() if before else rect.bottom()
    line.setGeometry(rect.left(), max(0, y - 1), vp.width() - rect.left(), 2)
    line.show()
    line.raise_()


def hide_line():
    line = _line.get("w")
    try:
        if line is not None:
            line.hide()
    except RuntimeError:
        _line.pop("w", None)


def on_event(obj, event):
    """
    Desde el filtro de la aplicación: DragMove / Drop / DragLeave sobre el árbol. True = lo atiende
    FreeWorks (no llega a FreeCAD); False = sigue como siempre.
    """
    from swui.compat import QtCore
    from swui.fork import context_menus as cm
    from swui.fork import feature_tree as ft

    tree = _tree_of(obj)
    if tree is None or not ft._in_workbench():
        return False
    if event.type() == QtCore.QEvent.Type.DragLeave:
        hide_line()
        return False
    # solo el arrastre que sale del mismo árbol, sin Ctrl/Alt (copiar / vincular son de FreeCAD)
    try:
        src = event.source()
        own = src is tree or (src is None and event.mimeData() is not None
                              and event.mimeData().hasFormat(ITEM_DATA) and not event.mimeData().hasUrls())
        if not own:
            return False
        mods = event.modifiers()
        if mods & (QtCore.Qt.KeyboardModifier.ControlModifier | QtCore.Qt.KeyboardModifier.AltModifier):
            return False
    except Exception:
        return False
    feature = _dragged()
    if feature is None:
        return False
    try:
        target, before = target_at(tree, _pos(event), feature)
    except Exception:
        return False
    if target is None:
        hide_line()
        return False
    feats = ft.features(ft.body_of(feature))
    dest = drop_index(feats, feature, target, before)
    # con un panel abierto o un croquis en edición no se reordena (ni lo hace FreeCAD a su manera)
    ok = dest is not None and blocker(feats, feature, dest, ft.ancestors) is None and not cm._busy()
    if event.type() == QtCore.QEvent.Type.DragMove:
        if ok:
            event.setDropAction(QtCore.Qt.DropAction.MoveAction)
            event.accept()
            _show_line(tree, target, before)
        else:
            event.ignore()
            hide_line()
        return True
    hide_line()
    # Drop: después de que termine el arrastre de Qt
    event.setDropAction(QtCore.Qt.DropAction.IgnoreAction)
    event.accept()
    if ok:  # donde no se puede soltar (dependencia) no pasa nada, como SW (el cursor ya lo decía)
        QtCore.QTimer.singleShot(0, lambda: run(feature, target, before))
    return True


def run(feature, target, before):
    """Reordenar con avisos (lo que muestra al soltar)."""
    from swui.compat import QtWidgets
    from swui.fork import feature_tree as ft

    mw = FreeCADGui.getMainWindow()
    doc = feature.Document
    try:
        broken_before = set(ft._broken(doc))
        lost, why = reorder(feature, target, before)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Reordenar:\n%s\n" % traceback.format_exc())
        return
    if why:
        QtWidgets.QMessageBox.information(mw, "No se puede mover", why)
        return
    broken = [doc.getObject(n).Label for n in ft._broken(doc) if n not in broken_before]
    seen, lines = set(), []
    for f, _s in lost:  # un aviso por operación aunque se haya movido varios lugares
        if f.Name not in seen:
            seen.add(f.Name)
            lines.append("%s perdió las aristas o caras que tenía elegidas." % f.Label)
    lines += ["%s quedó con error." % label for label in broken if label not in [f.Label for f, _s in lost]]
    if lines:
        answer = QtWidgets.QMessageBox.question(
            mw, "Mover", "\n".join(lines) + "\n\n¿Deshacer el cambio de orden?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            doc.undo()
            doc.recompute()
