# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Pestaña "Configuraciones" del panel izquierdo, como el ConfigurationManager de SOLIDWORKS.

- Tercera pestaña junto a Modelo y Tareas (panel_sw.py). Lista las configuraciones de la
  pieza; la activa con ✓ y en negrita. Doble clic = mostrar configuración.
- Clic derecho: Mostrar configuración, Agregar configuración..., Cambiar nombre,
  Eliminar, Editar tabla de diseño (la planilla propia de FreeCAD; decidido 01/11: sin Excel).
- Una pieza sin configuraciones muestra "Predeterminado" (como SW); al agregar la segunda se
  arma la tabla de diseño (configurations.ensure).
- Con más de una configuración:
    * la cajita "Modificar" de las cotas (instant_dims) suma "Esta configuración / Todas las
      configuraciones" (por omisión Esta, como SW);
    * Suprimir / Desactivar supresión del árbol (feature_tree) valen para la configuración
      activa, como SW;
    * las cotas atadas a la tabla no se muestran como ecuaciones (Σ) ni en la ventana Ecuaciones.
El núcleo (sin interfaz) está en configurations.py.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets
from swui.fork import configurations as cf

DOCK_NAME = "SWUI_Configurations"
TITLE = "Configuraciones"
POLL_MS = 500
SCOPES = (("this", "Esta configuración"), ("all", "Todas las configuraciones"))

_state = {"dock": None, "tree": None, "sig": None, "timer": None, "scope": "this"}


def _doc():
    try:
        return FreeCAD.ActiveDocument
    except Exception:
        return None


def _is_part(doc):
    """¿Pieza (algún Cuerpo) o ensamblaje? (las dos pueden tener configuraciones)"""
    return doc is not None and any(getattr(o, "TypeId", "") in ("PartDesign::Body", cf.ASSEMBLY)
                                   for o in doc.Objects)


def _status(text, ms=5000):
    try:
        FreeCADGui.getMainWindow().statusBar().showMessage(text, ms)
    except Exception:
        pass


def _run(doc, name, fn):
    """fn dentro de una transacción (se puede deshacer); los errores se avisan en castellano."""
    doc.openTransaction(name)
    try:
        result = fn()
        doc.recompute()
    except ValueError as e:
        doc.abortTransaction()
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), name, str(e))
        return None
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (name, traceback.format_exc()))
        return None
    doc.commitTransaction()
    refresh(force=True)
    return result


# --- Acciones ----------------------------------------------------------------


def show_config(name):
    doc = _doc()
    if doc is None or name == cf.active(doc):
        return
    if not cf.configured(doc):
        return
    _run(doc, "Mostrar configuración", lambda: cf.activate(doc, name))
    _status("Configuración activa: %s" % name)


def add_config():
    doc = _doc()
    if not _is_part(doc):
        return
    name, ok = QtWidgets.QInputDialog.getText(FreeCADGui.getMainWindow(), "Agregar configuración",
                                              "Nombre de la configuración:", text=cf.next_name(doc))
    if ok and name.strip():
        _run(doc, "Agregar configuración", lambda: cf.add(doc, name.strip()))


def rename_config(name):
    doc = _doc()
    if doc is None:
        return
    new, ok = QtWidgets.QInputDialog.getText(FreeCADGui.getMainWindow(), "Cambiar nombre",
                                             "Nombre nuevo:", text=name)
    if ok and new.strip() and new.strip() != name:
        _run(doc, "Cambiar nombre de configuración", lambda: cf.rename(doc, name, new.strip()))


def delete_config(name):
    doc = _doc()
    if doc is None:
        return
    answer = QtWidgets.QMessageBox.question(FreeCADGui.getMainWindow(), "Eliminar",
                                            "¿Eliminar la configuración \"%s\"?" % name)
    if answer == QtWidgets.QMessageBox.StandardButton.Yes:
        _run(doc, "Eliminar configuración", lambda: cf.delete(doc, name))


def edit_table():
    """Abrir la tabla de diseño (la arma si todavía no existe)."""
    doc = _doc()
    if not _is_part(doc):
        return
    sheet = cf.table(doc)
    if sheet is None:
        sheet = _run(doc, "Tabla de diseño", lambda: cf.ensure(doc))
    if sheet is not None:
        try:
            FreeCADGui.getDocument(doc.Name).setEdit(sheet.Name)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Tabla de diseño:\n%s\n" % traceback.format_exc())


# --- Panel -------------------------------------------------------------------------


class _Tree(QtWidgets.QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setObjectName("SWUI_ConfigTree")
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.itemDoubleClicked.connect(self._double)

    def _name(self, item):
        return item.data(0, QtCore.Qt.ItemDataRole.UserRole) if item is not None else None

    def _double(self, item, _col):
        name = self._name(item)
        if name:
            show_config(name)

    def _menu(self, pos):
        item = self.itemAt(pos)
        name = self._name(item)
        doc = _doc()
        menu = QtWidgets.QMenu(self)
        if name and doc is not None and cf.configured(doc):
            act = menu.addAction("Mostrar configuración", lambda: show_config(name))
            act.setEnabled(name != cf.active(doc))
            menu.addAction("Cambiar nombre", lambda: rename_config(name))
            act = menu.addAction("Eliminar", lambda: delete_config(name))
            act.setEnabled(name != cf.active(doc))
            menu.addSeparator()
        menu.addAction("Agregar configuración...", add_config)
        menu.addAction("Editar tabla de diseño", edit_table)
        menu.exec(self.viewport().mapToGlobal(pos))

    def keyPressEvent(self, event):
        name = self._name(self.currentItem())
        if event.key() == QtCore.Qt.Key.Key_F2 and name and cf.configured(_doc()):
            rename_config(name)
            return
        if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter) and name:
            show_config(name)
            return
        super().keyPressEvent(event)


def _signature(doc):
    if not _is_part(doc):
        return (None,)
    return (doc.Name, doc.Label, tuple(cf.names(doc)), cf.active(doc))


def refresh(force=False):
    tree = _state.get("tree")
    if tree is None:
        return
    try:
        doc = _doc()
        sig = _signature(doc)
        if not force and sig == _state["sig"]:
            return
        _state["sig"] = sig
        tree.clear()
        if sig == (None,):
            item = QtWidgets.QTreeWidgetItem(["(abrí una pieza o un ensamblaje)"])
            item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            tree.addTopLevelItem(item)
            return
        names = cf.names(doc) or [cf.FIRST]
        act = cf.active(doc) or cf.FIRST
        # Como SW: "Pieza Configuraciones (Activa)"
        top = QtWidgets.QTreeWidgetItem(["%s Configuraciones (%s)" % (doc.Label or doc.Name, act)])
        tree.addTopLevelItem(top)
        for name in names:
            item = QtWidgets.QTreeWidgetItem([("✓ " if name == act else "    ") + name])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, name)
            if name == act:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)
            top.addChild(item)
        top.setExpanded(True)
    except RuntimeError:
        _state["tree"] = None  # el panel se borró
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Configuraciones:\n%s\n" % traceback.format_exc())


def _make_dock(mw):
    dock = mw.findChild(QtWidgets.QDockWidget, DOCK_NAME)
    if dock is None:
        dock = QtWidgets.QDockWidget(TITLE, mw)
        dock.setObjectName(DOCK_NAME)
        box = QtWidgets.QWidget(dock)
        lay = QtWidgets.QVBoxLayout(box)
        lay.setContentsMargins(2, 2, 2, 2)
        tree = _Tree(box)
        lay.addWidget(tree)
        dock.setWidget(box)
        _state["tree"] = tree
    _state["dock"] = dock
    return dock


def attach(mw=None):
    """Poner la pestaña junto a Modelo y Tareas (llamado después de panel_sw.dock_left)."""
    mw = mw or FreeCADGui.getMainWindow()
    if not hasattr(mw, "findChild"):
        return  # sin ventana de verdad (test_load)
    try:
        from swui import layout
        from swui.fork import panel_sw

        docks = {d.objectName(): d for d in mw.findChildren(QtWidgets.QDockWidget)}
        model, tasks = docks.get(panel_sw.MODEL_NAME), docks.get(layout.TASK_NAME)
        dock = _make_dock(mw)
        left = QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
        if mw.dockWidgetArea(dock) != left:
            mw.addDockWidget(left, dock)
        anchor = tasks or model
        if anchor is not None:
            mw.tabifyDockWidget(anchor, dock)
        dock.show()
        panel_sw._hide_titles((dock,))
        if model is not None:
            QtCore.QTimer.singleShot(0, model.raise_)
        _start_timer(mw)
        refresh(force=True)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Pestaña Configuraciones:\n%s\n" % traceback.format_exc())


def detach():
    dock = _state.get("dock")
    if dock is not None:
        try:
            dock.hide()
        except RuntimeError:
            pass
    if _state.get("timer") is not None:
        _state["timer"].stop()


def _start_timer(mw):
    if _state.get("timer") is None:
        t = QtCore.QTimer(mw)
        t.setInterval(POLL_MS)
        t.timeout.connect(lambda: refresh())
        _state["timer"] = t
    _state["timer"].start()


# --- Enganches: Modificar, Suprimir, Ecuaciones -------------------------------------------


def _hook_dims():
    from swui.fork import instant_dims as idm

    if getattr(idm._expressions, "_swui_conf", False):
        return
    orig_expr, orig_apply, orig_modify = idm._expressions, idm.apply_value, idm._modify

    def _expressions(obj, _orig=orig_expr):
        """Las cotas atadas a la tabla de diseño no son ecuaciones (se cambian con Modificar)."""
        out = []
        try:
            engine = dict(obj.ExpressionEngine)
        except Exception:
            return _orig(obj)
        for path in _orig(obj):
            try:
                if cf.is_config_expression(obj, path, engine.get(path, "")):
                    continue
            except Exception:
                pass
            out.append(path)
        return out

    def apply_value(dim, value, _orig=orig_apply):
        kind, obj, which = dim.setter
        doc = obj.Document
        if not cf.configured(doc):
            return _orig(dim, value)
        target = (kind, obj, which)
        scope = _state.get("scope", "this")
        doc.openTransaction("Modificar cota")
        try:
            cf.configure(doc, target, value, scope)
            doc.recompute()
        except Exception:
            doc.abortTransaction()
            FreeCAD.Console.PrintError("[SWUI fork] No se pudo cambiar la cota:\n%s\n" % traceback.format_exc())
            return False
        doc.commitTransaction()
        if scope == "this":
            _status("Cota cambiada solo en la configuración %s." % cf.active(doc))
        return True

    def _modify(dim, button, _orig=orig_modify):
        _orig(dim, button)
        try:
            doc = dim.setter[1].Document
            if dim.locked or not cf.configured(doc):
                return
            box = next((w for w in QtWidgets.QApplication.topLevelWidgets()
                        if w.objectName() == "SWUI_Modificar" and w.isVisible()), None)
            if box is None:
                return
            combo = QtWidgets.QComboBox(box)
            combo.setObjectName("SWUI_ModificarAlcance")
            for key, text in SCOPES:
                combo.addItem(text, key)
            _state["scope"] = "this"
            combo.currentIndexChanged.connect(lambda i: _state.__setitem__("scope", combo.itemData(i)))
            box.layout().insertWidget(2, combo)
            box.adjustSize()
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Modificar:\n%s\n" % traceback.format_exc())

    for fn in (_expressions, apply_value, _modify):
        fn._swui_conf = True
    idm._expressions, idm.apply_value, idm._modify = _expressions, apply_value, _modify


def _hook_suppress():
    from swui.fork import feature_tree as ft

    if getattr(ft.suppress, "_swui_conf", False):
        return
    orig_sup, orig_unsup = ft.suppress, ft.unsuppress

    def suppress(obj, _orig=orig_sup):
        if cf.configured(getattr(obj, "Document", None)):
            done = cf.suppress(obj, "this")
            _status("Suprimida solo en la configuración %s." % cf.active(obj.Document))
            return done
        return _orig(obj)

    def unsuppress(obj, with_children=False, _orig=orig_unsup):
        if cf.configured(getattr(obj, "Document", None)):
            done = cf.unsuppress(obj, with_children, "this")
            _status("Supresión desactivada solo en la configuración %s." % cf.active(obj.Document))
            return done
        return _orig(obj, with_children)

    suppress._swui_conf = unsuppress._swui_conf = True
    ft.suppress, ft.unsuppress = suppress, unsuppress


def _hook_equations():
    from swui.fork import equations as eq

    if getattr(eq.Model.expressions, "_swui_conf", False):
        return
    orig = eq.Model.expressions

    def expressions(self, _orig=orig):
        out = []
        for obj, path, expr in _orig(self):
            try:
                if cf.is_config_expression(obj, path, expr):
                    continue
            except Exception:
                pass
            out.append((obj, path, expr))
        return out

    expressions._swui_conf = True
    eq.Model.expressions = expressions


def install():
    _hook_dims()
    _hook_suppress()
    try:
        _hook_equations()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Configuraciones/Ecuaciones:\n%s\n" % traceback.format_exc())
    from swui import layout
    from swui.fork import panel_sw

    if not getattr(panel_sw.dock_left, "_swui_conf", False):
        original = panel_sw.dock_left

        def dock_left(mw, _original=original):
            result = _original(mw)
            attach(mw)
            return result

        dock_left._swui_conf = True
        panel_sw.dock_left = dock_left
        layout._dock_right = dock_left  # panel_sw.install ya lo había puesto: el nuevo lo reemplaza
    if not getattr(layout.leave, "_swui_conf", False):
        original_leave = layout.leave

        def leave(_original=original_leave):
            detach()
            return _original()

        leave._swui_conf = True
        layout.leave = leave
