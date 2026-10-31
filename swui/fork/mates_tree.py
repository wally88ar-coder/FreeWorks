# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Relaciones de posición debajo de cada componente, como el FeatureManager de SOLIDWORKS.

Al abrir un componente del ensamblaje en el árbol aparece primero la carpeta
"Relaciones de posición en <Conjunto>" con las relaciones que lo tocan (las dos piezas de
una relación la muestran). La carpeta general de relaciones sigue estando, como en SW.

Es SOLO un dibujo en el árbol: no crea objetos ni guarda nada en el archivo (decisión del
usuario, 2026-10-31). Cada renglón señala a la relación verdadera de FreeCAD:
- clic: la elige (Ctrl+clic suma); se resalta en la vista y en la carpeta general;
- doble clic: la edita (el mismo panel que el doble clic en la carpeta general);
- clic derecho: el menú de siempre de esa relación (FreeCAD lo arma con lo elegido);
- pasar el mouse: la preselecciona;
- suprimida: en gris. "Fijo" no entra (en SW no es una relación).

Cómo (análisis en docs/NOTAS_TECNICAS.md, "Renglones propios dentro del árbol"):
renglones QTreeWidgetItem de un tipo propio dentro del Gui::TreeWidget. FreeCAD 1.1.4 deja
tranquilos los renglones que no son suyos, salvo que BORRA los de un componente cuando
cambian sus hijos (operación nueva en la pieza): el fork se entera (rowsAboutToBeRemoved) y
los vuelve a poner. Los renglones no se pueden elegir con Qt (elegirlos vaciaría la
selección de FreeCAD): los clics los atiende un filtro de eventos. Nunca se guardan
QTreeWidgetItem para después (PySide los invalida): se buscan cada vez, recorriendo el árbol de
arriba hacia abajo; nunca con parent() desde un renglón (PySide da "already deleted"): los
renglones propios llevan adentro el documento, el componente y la relación.
Si algo falla varias veces seguidas, se apaga solo y lo avisa (versión nueva de FreeCAD).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

TREE_CLASS = "Gui::TreeWidget"
DOCUMENT_TYPE = 1000  # TreeWidget::DocumentType en FreeCAD 1.1.4 (QTreeWidgetItem::UserType)
OBJECT_TYPE = 1001  # TreeWidget::ObjectType
USER_TYPE = 1000  # QTreeWidgetItem::UserType (valor fijo de Qt)
FOLDER_TYPE = USER_TYPE + 2701  # propios: lejos de los de FreeCAD
MATE_TYPE = USER_TYPE + 2702
NAME_ROLE = 0x0100 + 27  # Qt::UserRole + 27: nombre interno de la relación / firma de la carpeta
DOC_ROLE = 0x0100 + 28  # documento del ensamblaje
OWNER_ROLE = 0x0100 + 29  # componente dueño de la carpeta
TITLE = "Relaciones de posición en %s"
SUPPRESSED_COLOR = (150, 150, 150)
MARK_FILL = "#a6c8e3"  # celeste de lo elegido (como tree_overlay)
MAX_ERRORS = 3
QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction  # Qt6 / Qt5

_state = {"installed": False, "disabled": False, "errors": 0, "busy": False, "pending": False,
          "hover": None, "retry": 0}
_expanded = set()  # (documento, componente) con la carpeta abierta
_watched = set()  # id de los árboles ya conectados
_filter = None
_timer = None


# --- Cuentas (sin Qt, probables en el test) ---------------------------


def folder_title(assembly_doc_label):
    return TITLE % assembly_doc_label


def signature(rows):
    """Firma de la carpeta: si no cambió, no se rehace (evita parpadeos)."""
    return "|".join("%s:%s:%d" % (name, label, int(off)) for name, label, off in rows)


def is_label_click(x, label_left):
    """El clic cae sobre el ícono/nombre (no sobre la flechita de abrir): lo atiende el fork."""
    return x >= label_left


# --- Qué mostrar ---------------------------------------------------------


def _mates_sw():
    from swui.fork import mates_sw

    return mates_sw


def _assembly_of(comp):
    for parent in getattr(comp, "InList", []) or []:
        if parent.TypeId == "Assembly::AssemblyObject" and comp in (parent.Group or []):
            return parent
    return None


def rows_for(comp):
    """[(nombre, etiqueta, suprimida)] de las relaciones que tocan al componente, o None."""
    if comp is None or comp.TypeId not in ("App::Link", "Assembly::AssemblyLink"):
        return None
    asm = _assembly_of(comp)
    if asm is None:
        return None
    rows = []
    for j in _mates_sw().mates_of(asm, comp):
        if getattr(j, "ObjectToGround", None) is not None:
            continue
        rows.append((j.Name, j.Label, bool(getattr(j, "Suppressed", False))))
    return asm, rows


# --- Árbol ------------------------------------------------------------------


def _trees():
    try:
        return [t for t in FreeCADGui.getMainWindow().findChildren(QtWidgets.QTreeWidget)
                if t.metaObject().className() == TREE_CLASS]
    except Exception:
        return []


def _doc_by_label(label):
    for doc in FreeCAD.listDocuments().values():
        if doc.Label == label:
            return doc
    return None


def _object_of(item, doc):
    if doc is None or item.type() != OBJECT_TYPE:
        return None
    try:
        found = doc.getObjectsByLabel(item.text(0))
    except Exception:
        return None
    return found[0] if found else None


def _object_items(tree):
    """
    [(renglón, documento)] de los objetos. El iterador de Qt recorre en orden (cada documento y
    después sus objetos): el documento se lleva al pasar, sin parent() ni child() a mano (con
    esos, PySide da "already deleted" en el árbol de FreeCAD; el iterador anda, probado).
    """
    out = []
    doc = None
    it = QtWidgets.QTreeWidgetItemIterator(tree)
    while it.value():
        item = it.value()
        kind = item.type()
        if kind == DOCUMENT_TYPE:
            doc = _doc_by_label(item.text(0))
        elif kind == OBJECT_TYPE:
            out.append((item, doc))
        it += 1
    return out


def _our_folder(item):
    for i in range(item.childCount()):
        child = item.child(i)
        if child.type() == FOLDER_TYPE:
            return i, child
    return -1, None


def _selected_names():
    try:
        return {(s.Document.Name, s.Name) for s in FreeCADGui.Selection.getSelection("", 0)}
    except Exception:
        return set()


def _paint_mate(child, doc_name, selected):
    name = child.data(0, NAME_ROLE)
    on = (doc_name, name) in selected
    child.setBackground(0, QtGui.QBrush(QtGui.QColor(MARK_FILL)) if on else QtGui.QBrush())


def _make_folder(doc, asm, comp, rows, selected):
    folder = QtWidgets.QTreeWidgetItem(FOLDER_TYPE)
    folder.setText(0, folder_title(doc.Label))
    folder.setData(0, NAME_ROLE, signature(rows))
    folder.setData(0, DOC_ROLE, doc.Name)
    folder.setData(0, OWNER_ROLE, comp.Name)
    folder.setFlags(QtCore.Qt.ItemIsEnabled)
    try:
        jg = _mates_sw()._assembly_modules()[1].getJointGroup(asm)
        folder.setIcon(0, jg.ViewObject.Icon)
    except Exception:
        pass
    grey = QtGui.QBrush(QtGui.QColor(*SUPPRESSED_COLOR))
    for name, label, off in rows:
        child = QtWidgets.QTreeWidgetItem(MATE_TYPE)
        child.setText(0, label)
        child.setData(0, NAME_ROLE, name)
        child.setData(0, DOC_ROLE, doc.Name)
        child.setFlags(QtCore.Qt.ItemIsEnabled)
        joint = doc.getObject(name)
        try:
            child.setIcon(0, joint.ViewObject.Icon)
        except Exception:
            pass
        if off:
            child.setForeground(0, grey)
            child.setToolTip(0, "%s (suprimida)" % label)
        _paint_mate(child, doc.Name, selected)
        folder.addChild(child)
    return folder


def refresh():
    """Pone, corrige o saca las carpetas de todos los árboles. Barato si nada cambió."""
    _state["pending"] = False
    if _state["disabled"]:
        return
    _state["busy"] = True
    try:
        show = _mates_sw()._in_swui()
        selected = _selected_names()
        for tree in _trees():
            _watch(tree)
            for item, item_doc in _object_items(tree):
                try:
                    _refresh_item(item, item_doc, show, selected)
                except RuntimeError:  # renglón que FreeCAD acaba de rehacer: va en la próxima vuelta
                    _state["retry"] += 1
        if _state["retry"] and _state["retry"] < 20:
            QtCore.QTimer.singleShot(200, schedule)
        else:
            _state["retry"] = 0
        _state["errors"] = 0
    except Exception:
        _failed("refresh")
    finally:
        _state["busy"] = False


def _refresh_item(item, item_doc, show, selected):
    """Carpeta de un renglón: ponerla, corregirla o sacarla."""
    obj = _object_of(item, item_doc) if show else None
    found = rows_for(obj) if obj is not None else None
    index, folder = _our_folder(item)
    if not found or not found[1]:
        if folder is not None:
            item.takeChild(index)
        return
    asm, rows = found
    doc = obj.Document
    if folder is not None and folder.data(0, NAME_ROLE) == signature(rows):
        if index != 0:  # FreeCAD acomodó sus hijos adelante: volver arriba, como SW
            item.takeChild(index)
            item.insertChild(0, folder)
            folder.setExpanded((doc.Name, obj.Name) in _expanded)
        for i in range(folder.childCount()):
            _paint_mate(folder.child(i), doc.Name, selected)
        return
    if folder is not None:
        item.takeChild(index)
    folder = _make_folder(doc, asm, obj, rows, selected)
    item.insertChild(0, folder)
    folder.setExpanded((doc.Name, obj.Name) in _expanded)


def _failed(where):
    _state["errors"] += 1
    FreeCAD.Console.PrintLog("[SWUI fork] Relaciones bajo componentes (%s):\n%s\n" % (where, traceback.format_exc()))
    if _state["errors"] >= MAX_ERRORS:
        _state["disabled"] = True
        FreeCAD.Console.PrintWarning(
            "[SWUI] Las relaciones de posición debajo de cada componente se apagaron: esta versión de "
            "FreeCAD cambió su árbol. Siguen todas en la carpeta general de relaciones.\n")
        remove_all()


def remove_all():
    _state["busy"] = True
    try:
        for tree in _trees():
            for item, _doc in _object_items(tree):
                index, folder = _our_folder(item)
                if folder is not None:
                    item.takeChild(index)
    except Exception:
        pass
    finally:
        _state["busy"] = False


def schedule(delay=0):
    """Rehacer en la próxima vuelta del programa (junta muchos avisos en uno)."""
    global _timer
    if _state["disabled"] or _state["pending"]:
        return
    _state["pending"] = True
    if _timer is None:
        _timer = QtCore.QTimer()
        _timer.setSingleShot(True)
        _timer.timeout.connect(refresh)
    _timer.start(delay)


def _on_rows_removed(*_a):
    if not _state["busy"]:
        schedule()


def _owner_key(folder):
    return (folder.data(0, DOC_ROLE), folder.data(0, OWNER_ROLE))


def _on_expanded(item):
    try:
        if item.type() == FOLDER_TYPE:
            _expanded.add(_owner_key(item))
        elif item.type() == OBJECT_TYPE:
            schedule()
    except Exception:
        pass


def _on_collapsed(item):
    try:
        if item.type() == FOLDER_TYPE:
            _expanded.discard(_owner_key(item))
    except Exception:
        pass


def _watch(tree):
    if id(tree) in _watched:
        return
    _watched.add(id(tree))
    tree.model().rowsAboutToBeRemoved.connect(_on_rows_removed)
    tree.itemExpanded.connect(_on_expanded)
    tree.itemCollapsed.connect(_on_collapsed)
    tree.viewport().installEventFilter(_filter)
    tree.viewport().setMouseTracking(True)


# --- Clics -------------------------------------------------------------------


def _joint_of(item):
    if item is None or item.type() != MATE_TYPE:
        return None
    try:
        doc = FreeCAD.getDocument(item.data(0, DOC_ROLE))
    except Exception:
        return None
    return doc.getObject(item.data(0, NAME_ROLE))


def select(joint, add=False):
    if not add:
        FreeCADGui.Selection.clearSelection()
    elif FreeCADGui.Selection.isSelected(joint):
        FreeCADGui.Selection.removeSelection(joint)
        return
    FreeCADGui.Selection.addSelection(joint)


def edit(joint):
    """Lo mismo que el doble clic sobre la relación en la carpeta general."""
    vobj = joint.ViewObject
    try:
        if vobj.Proxy.doubleClicked(vobj):
            return
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Editar relación:\n%s\n" % traceback.format_exc())
    vobj.Document.setEdit(joint)


def _preselect(tree, item):
    joint = _joint_of(item)
    key = (joint.Document.Name, joint.Name) if joint is not None else None
    if key == _state["hover"]:
        return
    _state["hover"] = key
    try:
        FreeCADGui.Selection.removePreselection()
    except Exception:
        pass
    if joint is not None:
        # un instante después: al entrar a un renglón que no es suyo, FreeCAD borra la preselección
        # (TreeWidget::onItemEntered) justo después de este filtro
        QtCore.QTimer.singleShot(0, lambda k=key: _set_preselection(k))


def _set_preselection(key):
    if key != _state["hover"]:
        return
    try:
        FreeCADGui.Selection.setPreselection(FreeCAD.getDocument(key[0]).getObject(key[1]))
    except Exception:
        pass


def toggle_suppressed(joint):
    doc = joint.Document
    doc.openTransaction("Suprimir relación")
    try:
        joint.Suppressed = not bool(joint.Suppressed)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise
    doc.recompute()


class _MenuAddition(QtCore.QObject):
    """
    Clic derecho en una relación de la carpeta: FreeCAD arma su menú con lo elegido, pero la
    casilla "Suprimido" solo la pone en sus propios renglones. Se agrega arriba, como en la
    carpeta general. El filtro se pone al apretar el botón y se saca al mostrarse el menú.
    """

    def __init__(self):
        super().__init__()
        self.joint = None

    def arm(self, joint):
        self.joint = (joint.Document.Name, joint.Name)
        QtWidgets.QApplication.instance().installEventFilter(self)
        QtCore.QTimer.singleShot(3000, self.disarm)

    def disarm(self):
        self.joint = None
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        try:
            if (self.joint is not None and event.type() == QtCore.QEvent.Show
                    and isinstance(obj, QtWidgets.QMenu) and not isinstance(obj.parent(), QtWidgets.QMenu)):
                key = self.joint
                self.disarm()
                joint = FreeCAD.getDocument(key[0]).getObject(key[1])
                if joint is not None and hasattr(joint, "Suppressed"):
                    first = obj.actions()[0] if obj.actions() else None
                    action = QAction("Suprimido", obj)
                    action.setCheckable(True)
                    action.setChecked(bool(joint.Suppressed))
                    action.triggered.connect(lambda *_a, j=joint: toggle_suppressed(j))
                    obj.insertAction(first, action)
                    obj.insertSeparator(first)
                    obj.adjustSize()
        except Exception:
            self.disarm()
        return False


_menu_addition = None


class _Clicks(QtCore.QObject):
    def eventFilter(self, viewport, event):
        try:
            return self._handle(viewport, event)
        except Exception:
            _failed("clic")
            return False

    def _handle(self, viewport, event):
        etype = event.type()
        if etype not in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease,
                         QtCore.QEvent.MouseButtonDblClick, QtCore.QEvent.MouseMove, QtCore.QEvent.Leave):
            return False
        tree = viewport.parent()
        if etype == QtCore.QEvent.Leave:
            if _state["hover"] is not None:
                _preselect(tree, None)
            return False
        pos = event.pos()
        item = tree.itemAt(pos)
        ours = item is not None and item.type() in (FOLDER_TYPE, MATE_TYPE)
        if etype == QtCore.QEvent.MouseMove:
            if not (event.buttons() & QtCore.Qt.LeftButton):
                _preselect(tree, item if ours else None)
            return False
        if not ours or not is_label_click(pos.x(), tree.visualItemRect(item).left()):
            return False
        button = event.button()
        if etype == QtCore.QEvent.MouseButtonDblClick and button == QtCore.Qt.LeftButton:
            if item.type() == FOLDER_TYPE:
                item.setExpanded(not item.isExpanded())
            else:
                joint = _joint_of(item)
                if joint is not None:
                    QtCore.QTimer.singleShot(0, lambda j=joint: edit(j))
            return True
        if etype == QtCore.QEvent.MouseButtonPress and button in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton):
            joint = _joint_of(item)
            if joint is not None:
                add = bool(event.modifiers() & QtCore.Qt.ControlModifier) and button == QtCore.Qt.LeftButton
                if button == QtCore.Qt.LeftButton or not FreeCADGui.Selection.isSelected(joint):
                    select(joint, add)
                if button == QtCore.Qt.RightButton and _menu_addition is not None:
                    _menu_addition.arm(joint)
            return True  # que Qt no "elija" el renglón: FreeCAD vaciaría la selección
        if etype == QtCore.QEvent.MouseButtonRelease and button == QtCore.Qt.LeftButton:
            return True
        return False  # soltar el derecho: Qt arma el menú de FreeCAD con la relación elegida


# --- Avisos de FreeCAD ---------------------------------------------------------


class _DocObserver:
    PROPS = ("Label", "Suppressed", "Reference1", "Reference2", "Group", "ObjectToGround")

    def slotCreatedObject(self, obj):
        schedule()

    def slotDeletedObject(self, obj):
        schedule()

    def slotChangedObject(self, obj, prop):
        if prop in self.PROPS:
            schedule()

    def slotFinishRestoreDocument(self, doc):
        schedule(300)

    def slotRelabelDocument(self, doc):
        schedule()

    def slotDeletedDocument(self, doc):
        schedule()

    def slotActivateDocument(self, doc):
        schedule()


class _SelObserver:
    def addSelection(self, *_a):
        schedule()

    def removeSelection(self, *_a):
        schedule()

    def setSelection(self, *_a):
        schedule()

    def clearSelection(self, *_a):
        schedule()


def self_check():
    """(ok, motivo) de lo que esta función necesita de FreeCAD (para el chequeo de compatibilidad)."""
    if not _trees():
        return False, "no se encontró el árbol de FreeCAD (%s)" % TREE_CLASS
    for tree in _trees():
        if tree.topLevelItemCount() and tree.topLevelItem(0).type() not in (DOCUMENT_TYPE, OBJECT_TYPE):
            return False, "el árbol de FreeCAD usa otros tipos de renglón"
    if _state["disabled"]:
        return False, "se apagó por errores"
    return True, ""


def install():
    global _filter, _menu_addition
    if _state["installed"]:
        return
    _filter = _Clicks()
    _menu_addition = _MenuAddition()
    FreeCAD.addDocumentObserver(_DocObserver())
    FreeCADGui.Selection.addObserver(_SelObserver())
    try:
        FreeCADGui.getMainWindow().workbenchActivated.connect(lambda *_a: schedule())
    except Exception:
        pass
    _state["installed"] = True
    schedule(500)
