# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Configurar operación, como SW: clic derecho en una operación del árbol (con más de una
configuración) > "Configurar operación". Una tabla con una fila por configuración y una columna
por cada cota de la operación (las mismas que se ven con doble clic) más "Suprimir": se cambian
todas de una vez, sin ir mostrando cada configuración.

Por debajo es la misma tabla de diseño (configurations.set_values): lo que se cambia acá queda
atado a la planilla, igual que con Modificar > Esta configuración. Suprimir en una configuración
suprime también lo que depende de la operación (como el Suprimir del árbol).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.fork import configurations as cf

COMMAND = "SWUI_ConfigureFeature"
TITLE = "Configurar operación"
SUPPRESS = "Suprimir"


def columns(feature):
    """[(título, target, tipo)]: Suprimir y las cotas de la operación (las del doble clic)."""
    from swui.fork import instant_dims as idm

    out = [(SUPPRESS, ("sup", feature), "sup")]
    seen = set()
    for dim in idm.dims_of(feature):
        if not dim.setter:
            continue
        kind, obj, which = dim.setter
        target = (kind, obj, which)
        if dim.locked and not cf.is_bound(target):  # atada a una ecuación: se cambia en Ecuaciones
            continue
        try:
            _obj, path, _alias, title, _value = cf.target_info(target)
        except Exception:
            continue
        if (obj.Name, path) in seen:
            continue
        seen.add((obj.Name, path))
        out.append((title, target, dim.kind))
    return out


def table_values(doc, feature):
    """{(configuración, columna): valor} para llenar la tabla."""
    names = cf.names(doc)
    out = {}
    for c, (_title, target, _kind) in enumerate(columns(feature)):
        for name in names:
            out[(name, c)] = cf.value_in(doc, target, name)
    return out


def apply(doc, feature, changes):
    """changes: {(configuración, columna): valor nuevo}. Devuelve cuántos cambió."""
    from swui.fork import feature_tree as ft

    cols = columns(feature)
    by_col = {}
    for (name, c), value in changes.items():
        by_col.setdefault(c, {})[name] = value
    done = 0
    for c, values in sorted(by_col.items()):
        _title, target, kind = cols[c]
        if kind == "sup":
            on = {n: v for n, v in values.items() if v}
            off = {n: v for n, v in values.items() if not v}
            if on:  # con lo que depende de ella, como el Suprimir del árbol
                for feat in cf._features([feature] + ft.dependents(feature)):
                    cf.set_values(doc, ("sup", feat), {n: 1 for n in on})
            if off:
                cf.set_values(doc, ("sup", feature), {n: 0 for n in off})
        else:
            cf.set_values(doc, target, values)
        done += len(values)
    if done:
        cf.sync_attachments(doc)
        doc.recompute()
        cf.activate(doc, cf.active(doc))  # chapa y Mover cara se ponen al día con la activa
    return done


class Dialog(QtWidgets.QDialog):
    def __init__(self, feature, parent=None):
        from swui.fork import instant_dims as idm

        super().__init__(parent or FreeCADGui.getMainWindow())
        self.feature, self.doc = feature, feature.Document
        self.setWindowTitle("%s: %s" % (TITLE, feature.Label))
        self.cols = columns(feature)
        self.names = cf.names(self.doc)
        self.before = table_values(self.doc, feature)
        lay = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget(len(self.names), len(self.cols), self)
        self.table.setObjectName("SWUI_ConfigureFeatureTable")
        self.table.setHorizontalHeaderLabels([t for t, _x, _k in self.cols])
        self.table.setVerticalHeaderLabels(self.names)
        active = cf.active(self.doc)
        for r, name in enumerate(self.names):
            for c, (_t, _target, kind) in enumerate(self.cols):
                value = self.before[(name, c)]
                if kind == "sup":
                    item = QtWidgets.QTableWidgetItem()
                    item.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
                    item.setCheckState(QtCore.Qt.CheckState.Checked if value else QtCore.Qt.CheckState.Unchecked)
                else:
                    item = QtWidgets.QTableWidgetItem(idm.fmt(value, kind))
                    item.setTextAlignment(int(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter))
                if name == active:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        lay.addWidget(self.table)
        note = QtWidgets.QLabel("La configuración activa va en negrita. Los cambios quedan en la tabla de diseño.")
        note.setWordWrap(True)
        lay.addWidget(note)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("Aceptar")
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.resize(min(900, 160 + 110 * len(self.cols)), min(500, 140 + 30 * len(self.names)))

    def changes(self):
        """{(configuración, columna): valor} de lo que se cambió en la tabla (o ValueError)."""
        from swui.fork import instant_dims as idm

        out = {}
        for r, name in enumerate(self.names):
            for c, (title, _target, kind) in enumerate(self.cols):
                item = self.table.item(r, c)
                if kind == "sup":
                    value = 1 if item.checkState() == QtCore.Qt.CheckState.Checked else 0
                else:
                    value = idm.parse(item.text(), kind)
                    if value is None:
                        raise ValueError("«%s» no es un valor válido (%s, %s)." % (item.text(), title, name))
                if abs(float(value) - float(self.before[(name, c)])) > 1e-9:
                    out[(name, c)] = value
        return out

    def _accept(self):
        try:
            changes = self.changes()
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, TITLE, str(e))
            return
        if changes:
            self.doc.openTransaction(TITLE)
            try:
                apply(self.doc, self.feature, changes)
            except Exception:
                self.doc.abortTransaction()
                FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (TITLE, traceback.format_exc()))
                QtWidgets.QMessageBox.warning(self, TITLE, "No se pudo aplicar (detalle en la vista de informe).")
                return
            self.doc.commitTransaction()
        self.accept()


def _target():
    from swui.fork import feature_tree as ft

    try:
        sel = FreeCADGui.Selection.getSelection()
    except Exception:
        return None
    if len(sel) != 1 or not ft.is_feature(sel[0]) or ft.body_of(sel[0]) is None:
        return None
    return sel[0] if cf.configured(sel[0].Document) else None


class _Command:
    def GetResources(self):
        return {"MenuText": TITLE + "...", "ToolTip": "Valores y supresión de esta operación en cada configuración"}

    def IsActive(self):
        return _target() is not None

    def Activated(self):
        feature = _target()
        if feature is not None:
            Dialog(feature).exec()


def _hook_menu():
    """En el clic derecho de una operación, después de Padre/Hijo... (solo con configuraciones)."""
    from swui.fork import feature_tree as ft

    if getattr(ft.menu_commands, "_swui_conf", False):
        return
    original = ft.menu_commands

    def menu_commands(objs, _original=original):
        out = _original(objs)
        try:
            feats = [o for o in objs if ft.is_feature(o) and ft.body_of(o) is not None]
            if out and len(feats) == 1 and cf.configured(feats[0].Document):
                at = out.index(ft.PARENT_CHILD) + 1 if ft.PARENT_CHILD in out else len(out)
                out.insert(at, COMMAND)
        except Exception:
            pass
        return out

    menu_commands._swui_conf = True
    ft.menu_commands = menu_commands
    if COMMAND not in [n for n, _c in ft.COMMANDS]:
        ft.COMMANDS = ft.COMMANDS + ((COMMAND, _Command),)  # lo nuestro sube arriba del menú


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _Command())
    except Exception:
        pass
    _hook_menu()
