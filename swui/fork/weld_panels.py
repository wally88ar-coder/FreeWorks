# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Paneles de la pestaña Piezas soldadas (como SW 2018). Solo juntan los datos y llaman a las
funciones de weldments.py (regla "panel = cara de una función").

  Miembro estructural  tipo y tamaño, líneas del esqueleto (clic en la vista), girar, ubicar perfil,
                       simetría y tratamiento de esquinas; vista previa en vivo
  Esquinas             cada esquina entre miembros: a tope (cuál pasa), inglete o ninguno; en vivo
  Recortar/Alargar     miembros a recortar + límite (otro miembro = ajuste exacto, cara plana = plano)
  Lista de cortes      tabla agrupada; exportar CSV (Excel) o insertarla como planilla
  Tapa de extremo      cara de la punta de un miembro, espesor y separación del borde
  Cartela              dos miembros en esquina, tamaño y espesor
  Editar miembro       clic derecho > Editar operación sobre la carpeta "Miembro estructuralN" (o un
                       caño): el mismo panel con los valores actuales, todo editable; los caños se
                       cambian en su lugar (no se pierden tapas, cartelas ni recortes apoyados en ellos)

Las cajitas numéricas y las listas desplegables de estos paneles no toman la ruedita del mouse si no
se hizo clic en ellas: la ruedita baja el panel (un -2° puesto sin querer torcía todos los caños,
visto por el usuario 07/11).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.fork import weldments as w

TITLE = "Piezas soldadas"
CORNER_TEXTS = (("A tope (pasa el más largo)", "tope"), ("Inglete", "inglete"), ("Ninguno", "ninguno"))


def _mw():
    return FreeCADGui.getMainWindow()


def _info(text):
    QtWidgets.QMessageBox.information(_mw(), TITLE, text)


def _doc():
    return FreeCAD.ActiveDocument


def _close():
    try:
        FreeCADGui.Control.closeDialog()
    except Exception:
        pass


def _owner_member(obj, sub=""):
    """El miembro (Cuerpo) al que pertenece lo elegido, o None."""
    try:
        if w.is_member(obj):
            return obj
        for parent in obj.InList:
            if w.is_member(parent):
                return parent
        if sub:
            leaf = obj.getSubObject(sub.rsplit(".", 1)[0] + "." if "." in sub else "", retType=1)
            if leaf is not None and w.is_member(leaf):
                return leaf
    except Exception:
        pass
    return None


def _remove_bodies(doc, bodies, group=None):
    for b in bodies:
        try:
            if doc.getObject(b.Name) is None:
                continue
            b.removeObjectsFromDocument()
            doc.removeObject(b.Name)
        except Exception:
            pass
    if group is not None:
        try:
            doc.removeObject(group.Name)
        except Exception:
            pass


def _group_of(body):
    for p in body.InList:
        if p.TypeId == "App::DocumentObjectGroup":
            return p
    return None


class _Sel:
    def __init__(self, fn):
        self.fn = fn

    def addSelection(self, *_a):
        QtCore.QTimer.singleShot(0, self.fn)

    def removeSelection(self, *_a):
        QtCore.QTimer.singleShot(0, self.fn)

    def clearSelection(self, *_a):
        QtCore.QTimer.singleShot(0, self.fn)

    def setSelection(self, *_a):
        QtCore.QTimer.singleShot(0, self.fn)


class _Base:
    title = TITLE

    def __init__(self):
        self.doc = _doc()
        self.doc.openTransaction(self.title)
        self._sel = _Sel(self._selection_changed)
        FreeCADGui.Selection.addObserver(self._sel)
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._preview)

    def _selection_changed(self):
        pass

    def _preview(self):
        pass

    def _changed(self, *_a):
        self._timer.start()

    def _finish(self):
        try:
            FreeCADGui.Selection.removeObserver(self._sel)
        except Exception:
            pass
        self._timer.stop()

    def accept(self):
        try:
            self._timer.stop()
            self._apply_final()
            self.doc.commitTransaction()
        except Exception as e:
            self.doc.abortTransaction()
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (self.title, traceback.format_exc()))
            _info("No se pudo: %s" % e)
        self._finish()
        _close()
        FreeCADGui.Selection.clearSelection()
        self.doc.recompute()
        return True

    def _apply_final(self):
        self._preview()

    def reject(self):
        self._finish()
        self.doc.abortTransaction()
        _close()
        self.doc.recompute()
        return True

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel


def _selected_edges():
    out = []
    for s in FreeCADGui.Selection.getSelectionEx():
        if _owner_member(s.Object) is not None:
            continue
        for sub in s.SubElementNames:
            if sub.startswith("Edge"):
                out.append((s.Object, sub))
    return out


# --- Miembro estructural -------------------------------------------------------------------------


class MemberPanel(_Base):
    title = "Miembro estructural"

    KEEP = "Como están"

    def __init__(self, group=None):
        """Sin `group`: Miembro estructural nuevo. Con `group` (carpeta "Miembro estructuralN"):
        Editar operación, como SW: el mismo panel con los valores actuales; los caños se cambian en
        su lugar (weldments.edit_members)."""
        super().__init__()
        self.edit = group
        self.bodies = []
        self.group = None
        self.edges = []
        self.form = self._build()
        if group is not None:
            self._load(group)
        self._selection_changed()

    def _load(self, group):
        self.bodies = [m for m in group.Group if w.is_member(m)]
        self.group = group
        self.edges = [w.route_edge(m) for m in self.bodies]
        first = self.bodies[0]
        for wdg in (self.kind, self.size, self.rot, self.anchor, self.mirror, self.corner):
            wdg.blockSignals(True)
        names = [self.kind.itemText(i) for i in range(self.kind.count())]
        if first.SWUI_WeldKind in names:
            self.kind.setCurrentIndex(names.index(first.SWUI_WeldKind))
        self.kind.blockSignals(False)
        self._fill_sizes()
        self.size.blockSignals(True)
        sizes = [self.size.itemText(i) for i in range(self.size.count())]
        if first.SWUI_WeldSize not in sizes:  # medida vieja, de antes de las tablas CIRSOC: se ofrece igual
            self.size.insertItem(0, first.SWUI_WeldSize)
            sizes.insert(0, first.SWUI_WeldSize)
        self.size.setCurrentIndex(sizes.index(first.SWUI_WeldSize))
        self.rot.setValue(float(getattr(first, "SWUI_WeldRotation", 0.0)))
        anchors = list(w.ANCHORS)
        if getattr(first, "SWUI_WeldAnchor", "Centro") in anchors:
            self.anchor.setCurrentIndex(anchors.index(first.SWUI_WeldAnchor))
        self.mirror.setChecked(bool(getattr(first, "SWUI_WeldMirror", False)))
        self.corner.insertItem(0, self.KEEP)
        self.corner.setCurrentIndex(0)
        for wdg in (self.kind, self.size, self.rot, self.anchor, self.mirror, self.corner):
            wdg.blockSignals(False)
        self._timer.stop()
        self._refresh_list()

    def _build(self):
        f = QtWidgets.QWidget()
        f.setWindowTitle(self.title)
        lay = QtWidgets.QVBoxLayout(f)
        box = QtWidgets.QGroupBox("Selecciones")
        g = QtWidgets.QFormLayout(box)
        self.kind = QtWidgets.QComboBox()
        self.kind.addItems(list(w.profile_names()))
        self.size = QtWidgets.QComboBox()
        self.kind.currentIndexChanged.connect(self._fill_sizes)
        self.size.currentIndexChanged.connect(self._changed)
        g.addRow("Tipo", self.kind)
        g.addRow("Tamaño", self.size)
        lay.addWidget(box)
        seg = QtWidgets.QGroupBox("Segmentos del recorrido")
        v = QtWidgets.QVBoxLayout(seg)
        self.list = QtWidgets.QListWidget()
        self.list.setMaximumHeight(110)
        v.addWidget(self.list)
        hint = QtWidgets.QLabel("Hacé clic en las líneas del croquis esqueleto: cada clic suma una línea; "
                                "un clic en un caño ya puesto lo saca.")
        hint.setWordWrap(True)
        v.addWidget(hint)
        rm = QtWidgets.QPushButton("Quitar la línea marcada de la lista")
        rm.clicked.connect(self._remove_current)
        v.addWidget(rm)
        lay.addWidget(seg)
        conf = QtWidgets.QGroupBox("Configuración")
        c = QtWidgets.QFormLayout(conf)
        self.rot = QtWidgets.QDoubleSpinBox()
        self.rot.setRange(-360, 360)
        self.rot.setSuffix(" °")
        self.rot.valueChanged.connect(self._changed)
        self.anchor = QtWidgets.QComboBox()
        self.anchor.addItems(list(w.ANCHORS))
        self.anchor.currentIndexChanged.connect(self._changed)
        self.mirror = QtWidgets.QCheckBox("Simetría de perfil")
        self.mirror.toggled.connect(self._changed)
        c.addRow("Girar ángulo", self.rot)
        c.addRow("Ubicar perfil", self.anchor)
        c.addRow(self.mirror)
        self.corner = QtWidgets.QComboBox()
        for text, _v in CORNER_TEXTS:
            self.corner.addItem(text)
        self.corner.currentIndexChanged.connect(self._changed)
        c.addRow("Tratamiento de esquinas", self.corner)
        lay.addWidget(conf)
        lay.addStretch(1)
        self._fill_sizes()
        return f

    def _fill_sizes(self, *_a):
        self.size.blockSignals(True)
        self.size.clear()
        names = [n for n, _d in w.sizes(self.kind.currentText())]
        self.size.addItems(names)
        default = {"Caño cuadrado": "40x40x2", "Caño rectangular": "20x40x1,6"}.get(self.kind.currentText())
        if default in names:
            self.size.setCurrentIndex(names.index(default))
        self.size.blockSignals(False)
        self._changed()

    def _selection_changed(self):
        # como SW: cada clic SUMA la línea (FreeCAD reemplaza la selección en cada clic común);
        # otro clic en una línea que ya está la saca. Las caras de los miembros de la vista previa
        # no cuentan.
        picked = _selected_edges()
        # clic sobre un caño de la vista previa = clic en su línea (la tapa): la saca de la lista
        hit = None
        names = [b.Name for b in self.bodies]
        for sel in FreeCADGui.Selection.getSelectionEx("", 0):
            for sub in (sel.SubElementNames or [""]):
                for part in [sel.Object.Name] + sub.split("."):
                    if part in names:
                        hit = names.index(part)
        if hit is not None and hit < len(self.edges) and not picked:
            self.edges.pop(hit)
            QtCore.QTimer.singleShot(0, FreeCADGui.Selection.clearSelection)
            self._refresh_list()
            self._changed()
            return
        if not picked:
            return
        for o, sub in picked:
            keys = [(e[0].Name, e[1]) for e in self.edges]
            key = (o.Name, sub)
            if key in keys:
                self.edges.pop(keys.index(key))
            else:
                self.edges.append((o, sub))
        # la selección de FreeCAD se vacía: así el próximo clic en la misma línea la vuelve a elegir
        # (y la saca de la lista), como SW
        QtCore.QTimer.singleShot(0, FreeCADGui.Selection.clearSelection)
        self._refresh_list()
        self._changed()

    def _refresh_list(self):
        self.list.clear()
        for o, sub in self.edges:
            parent = None
            try:
                from swui.fork import sketch3d

                parent = sketch3d.sketch_of(o) if sketch3d.is_line(o) else None
            except Exception:
                pass
            if parent is not None:  # línea de un Croquis 3D: "Línea3D2@Croquis3D1", como SW
                self.list.addItem("%s@%s" % (o.Label, parent.Label))
            else:
                self.list.addItem("%s@%s" % (sub.replace("Edge", "Línea"), o.Label))

    def _remove_current(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.edges):
            self.edges.pop(i)
            self._refresh_list()
            self._changed()

    def _clear_preview(self):
        if self.edit is not None:
            return  # editando: los caños se cambian en su lugar, no se borran
        _remove_bodies(self.doc, self.bodies, self.group)
        self.bodies, self.group = [], None

    def _treatment(self):
        text = self.corner.currentText()
        if text == self.KEEP:
            return None
        return dict(CORNER_TEXTS)[text]

    def _preview_edit(self):
        if not self.edges or not self.size.currentText():
            return  # sin líneas no se borra la operación entera: Aceptar avisa
        try:
            self.bodies = w.edit_members(self.edit, self.edges, self.kind.currentText(), self.size.currentText(),
                                         self.rot.value(), self.anchor.currentText(), self.mirror.isChecked(),
                                         self._treatment())
            self.doc.recompute()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Editar miembro estructural:\n%s\n" % traceback.format_exc())

    def _preview(self):
        if self.edit is not None:
            self._preview_edit()
            return
        self._clear_preview()
        if not self.edges or not self.size.currentText():
            self.doc.recompute()
            return
        try:
            self.bodies = w.create_members(self.doc, self.edges, self.kind.currentText(), self.size.currentText(),
                                           self.rot.value(), self.anchor.currentText(), self.mirror.isChecked())
            self.group = _group_of(self.bodies[0]) if self.bodies else None
            treat = CORNER_TEXTS[self.corner.currentIndex()][1]
            if treat != "ninguno" and len(self.bodies) > 1:
                w.apply_corners(self.bodies, treat)
            self.doc.recompute()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Miembro estructural:\n%s\n" % traceback.format_exc())

    def _apply_final(self):
        if self.edit is not None:
            if not self.edges:
                raise ValueError("dejá al menos una línea (para sacar el miembro entero, borralo del árbol)")
            self._preview()
            return
        if not self.bodies:
            self._preview()
        if not self.bodies:
            raise ValueError("elegí al menos una línea del esqueleto")


# --- Esquinas ---------------------------------------------------------------------------------------


class CornersPanel(_Base):
    title = "Tratamiento de esquinas"

    def __init__(self, bodies):
        super().__init__()
        self.bodies = bodies
        self.corners = w.find_corners(bodies)
        self.form = self._build()
        self._changed()

    def _build(self):
        f = QtWidgets.QWidget()
        f.setWindowTitle(self.title)
        lay = QtWidgets.QVBoxLayout(f)
        if not self.corners:
            lay.addWidget(QtWidgets.QLabel("No hay esquinas entre los miembros elegidos."))
        self.rows = []
        for i, c in enumerate(self.corners):
            box = QtWidgets.QGroupBox("Esquina %d (%s)" % (i + 1, "T" if c["kind"] == "T" else "L"))
            g = QtWidgets.QFormLayout(box)
            g.addRow(QtWidgets.QLabel("%s\n%s" % (c["a"].Label, c["b"].Label)))
            treat = QtWidgets.QComboBox()
            passing = QtWidgets.QComboBox()
            if c["kind"] == "T":
                treat.addItems(["A tope", "Ninguno"])
                passing.addItem(c["a"].Label)
                passing.setEnabled(False)
            else:
                treat.addItems(["A tope", "Inglete", "Ninguno"])
                la = (w.axis(c["a"])[1] - w.axis(c["a"])[0]).Length
                lb = (w.axis(c["b"])[1] - w.axis(c["b"])[0]).Length
                passing.addItems([c["a"].Label, c["b"].Label])
                passing.setCurrentIndex(0 if la >= lb else 1)
            treat.currentIndexChanged.connect(self._changed)
            passing.currentIndexChanged.connect(self._changed)
            g.addRow("Tratamiento", treat)
            g.addRow("Pasa", passing)
            lay.addWidget(box)
            self.rows.append((c, treat, passing))
        lay.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(f)
        scroll.setWindowTitle(self.title)
        return scroll

    def _preview(self):
        try:
            for c, treat, passing in self.rows:
                t = {"A tope": "tope", "Inglete": "inglete", "Ninguno": "ninguno"}[treat.currentText()]
                p = c["a"] if passing.currentIndex() == 0 else c["b"]
                w.apply_corner(c, t, p)
            self.doc.recompute()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Esquinas:\n%s\n" % traceback.format_exc())


# --- Editar miembro estructural --------------------------------------------------------------------


def _member_group(obj):
    """Carpeta "Miembro estructuralN" de lo elegido (la carpeta, un caño o su extrusión), o None."""
    if obj is None:
        return None
    if obj.TypeId == "App::DocumentObjectGroup":
        return obj if any(w.is_member(m) for m in obj.Group) else None
    body = obj if w.is_member(obj) else None
    if body is None and obj.TypeId == "PartDesign::Pad":
        body = next((p for p in obj.InList if w.is_member(p) and w._pad_of(p) == obj), None)
    return _group_of(body) if body is not None else None


def open_edit_member(group):
    if any(w.is_member(m) for m in group.Group):
        _open(MemberPanel, group)


# --- Recortar / Alargar ------------------------------------------------------------------------------


class TrimPanel(_Base):
    title = "Recortar/Alargar"

    def __init__(self):
        super().__init__()
        self.targets = []
        self.boundary = None  # ("member", cuerpo) | ("face", (obj, "FaceN"))
        self.active = "targets"
        self.form = self._build()

    def _build(self):
        f = QtWidgets.QWidget()
        f.setWindowTitle(self.title)
        lay = QtWidgets.QVBoxLayout(f)
        self.t_box = QtWidgets.QGroupBox("Cuerpos a recortar")
        v = QtWidgets.QVBoxLayout(self.t_box)
        self.t_list = QtWidgets.QListWidget()
        self.t_list.setMaximumHeight(90)
        v.addWidget(self.t_list)
        b1 = QtWidgets.QPushButton("Elegir cuerpos a recortar")
        b1.clicked.connect(lambda: self._activate("targets"))
        v.addWidget(b1)
        lay.addWidget(self.t_box)
        self.b_box = QtWidgets.QGroupBox("Límite de recorte")
        v2 = QtWidgets.QVBoxLayout(self.b_box)
        self.b_text = QtWidgets.QLineEdit()
        self.b_text.setReadOnly(True)
        v2.addWidget(self.b_text)
        b2 = QtWidgets.QPushButton("Elegir el límite (otro miembro o una cara plana)")
        b2.clicked.connect(lambda: self._activate("boundary"))
        v2.addWidget(b2)
        self.as_body = QtWidgets.QRadioButton("Cuerpo (ajuste exacto contra el miembro)")
        self.as_face = QtWidgets.QRadioButton("Cara plana (corte recto en el plano de la cara)")
        self.as_body.setChecked(True)
        v2.addWidget(self.as_body)
        v2.addWidget(self.as_face)
        self.kind_lbl = QtWidgets.QLabel("")
        v2.addWidget(self.kind_lbl)
        lay.addWidget(self.b_box)
        self.extend = QtWidgets.QCheckBox("Permitir alargar")
        self.extend.setChecked(True)
        lay.addWidget(self.extend)
        lay.addStretch(1)
        self._activate("targets")
        return f

    def _activate(self, which):
        self.active = which
        self.t_box.setStyleSheet("QGroupBox { font-weight: %s; }" % ("bold" if which == "targets" else "normal"))
        self.b_box.setStyleSheet("QGroupBox { font-weight: %s; }" % ("bold" if which == "boundary" else "normal"))
        FreeCADGui.Selection.clearSelection()

    def _selection_changed(self):
        sel = FreeCADGui.Selection.getSelectionEx("", 0)
        if not sel:
            return
        s = sel[-1]
        subs = [x for x in s.SubElementNames if x] or [""]
        sub = subs[-1]
        leaf = s.Object.getSubObject(sub, retType=1) if sub else s.Object
        member = _owner_member(leaf) if leaf is not None else None
        if member is None and sub:
            # cuerpo dentro de la carpeta: el primer objeto del camino que sea miembro
            parts = sub.split(".")
            obj = s.Object
            for name in parts[:-1]:
                obj = s.Object.Document.getObject(name) or obj
                if w.is_member(obj):
                    member = obj
                    break
        if self.active == "targets":
            if member is not None and member not in self.targets:
                self.targets.append(member)
                self.t_list.addItem(member.Label)
        else:
            el = sub.split(".")[-1] if sub else ""
            if member is not None and self.as_body.isChecked():
                # como SW: si el límite es otro miembro, por defecto es el cuerpo (ajuste exacto)
                self.boundary = ("member", member)
                self.b_text.setText(member.Label)
                self.kind_lbl.setText("Ajuste exacto contra el miembro (cuerpo)")
                self._face_pick = (leaf, el) if el.startswith("Face") else None
            elif member is not None and not el.startswith("Face"):
                self.boundary = ("member", member)
                self.b_text.setText(member.Label)
                self.kind_lbl.setText("Ajuste exacto contra el miembro (cuerpo)")
            elif member is not None and el.startswith("Face"):
                face = leaf.Shape.getElement(el) if leaf is not None else None
                if face is not None and face.Surface.__class__.__name__ != "Plane":
                    self.boundary = ("member", member)
                    self.b_text.setText(member.Label)
                    self.kind_lbl.setText("Ajuste exacto contra el miembro (cuerpo)")
                else:
                    self.boundary = ("face", (leaf, el))
                    self.b_text.setText("%s - %s" % (leaf.Label, el))
                    self.kind_lbl.setText("Corte recto en el plano de la cara")
            elif el.startswith("Face") and leaf is not None:
                self.boundary = ("face", (leaf, el))
                self.b_text.setText("%s - %s" % (leaf.Label, el))
                self.kind_lbl.setText("Corte recto en el plano de la cara")

    def _apply_final(self):
        if not self.targets or self.boundary is None:
            raise ValueError("elegí los cuerpos a recortar y el límite")
        for m in self.targets:
            if self.boundary[0] == "member":
                if self.boundary[1] == m:
                    continue
                w.trim_to_member(m, self.boundary[1], self.extend.isChecked())
            else:
                w.trim_to_face(m, self.boundary[1], self.extend.isChecked())


# --- Tapa de extremo y cartela ------------------------------------------------------------------------


class EndCapPanel(_Base):
    title = "Tapa de extremo"

    def __init__(self):
        super().__init__()
        self.pick = None  # (miembro, punta)
        self.form = self._build()
        self._selection_changed()

    def _build(self):
        f = QtWidgets.QWidget()
        f.setWindowTitle(self.title)
        g = QtWidgets.QFormLayout(f)
        self.face = QtWidgets.QLineEdit()
        self.face.setReadOnly(True)
        g.addRow("Punta", self.face)
        self.thick = QtWidgets.QDoubleSpinBox()
        self.thick.setRange(0.5, 100)
        self.thick.setValue(3.0)
        self.thick.setSuffix(" mm")
        self.inset = QtWidgets.QDoubleSpinBox()
        self.inset.setRange(0, 50)
        self.inset.setSuffix(" mm")
        g.addRow("Espesor", self.thick)
        g.addRow("Distancia al borde", self.inset)
        hint = QtWidgets.QLabel("Hacé clic en el miembro cerca de la punta que querés tapar.")
        hint.setWordWrap(True)
        g.addRow(hint)
        return f

    def _selection_changed(self):
        for s in FreeCADGui.Selection.getSelectionEx("", 0):
            picked = list(getattr(s, "PickedPoints", []) or [])
            for k, sub in enumerate(s.SubElementNames):
                leaf = s.Object.getSubObject(sub, retType=1)
                member = _owner_member(leaf) if leaf is not None else None
                if member is None:
                    for name in sub.split(".")[:-1]:
                        o = s.Object.Document.getObject(name)
                        if o is not None and w.is_member(o):
                            member = o
                if member is None or not sub.split(".")[-1].startswith("Face"):
                    continue
                # cualquier cara del miembro: la tapa va a la punta más cercana al clic (la cara de la
                # punta de un caño es un anillo finito, difícil de acertar)
                face = s.Object.getSubObject(sub)
                a0, a1, d = w.axis(member)
                c = picked[k] if k < len(picked) else face.CenterOfMass
                end = 0 if (c - a0).Length < (c - a1).Length else 1
                self.pick = (member, end)
                self.face.setText("%s (punta %d)" % (member.Label, end + 1))

    def _apply_final(self):
        if self.pick is None:
            raise ValueError("elegí la cara de la punta de un miembro")
        w.end_cap(self.pick[0], self.pick[1], self.thick.value(), self.inset.value())


class GussetPanel(_Base):
    title = "Cartela"

    def __init__(self):
        super().__init__()
        self.members = []
        self.form = self._build()
        self._selection_changed()

    def _build(self):
        f = QtWidgets.QWidget()
        f.setWindowTitle(self.title)
        g = QtWidgets.QFormLayout(f)
        self.which = QtWidgets.QLineEdit()
        self.which.setReadOnly(True)
        g.addRow("Miembros", self.which)
        self.size = QtWidgets.QDoubleSpinBox()
        self.size.setRange(5, 2000)
        self.size.setValue(80)
        self.size.setSuffix(" mm")
        self.thick = QtWidgets.QDoubleSpinBox()
        self.thick.setRange(0.5, 100)
        self.thick.setValue(6)
        self.thick.setSuffix(" mm")
        g.addRow("Largo de los lados", self.size)
        g.addRow("Espesor", self.thick)
        hint = QtWidgets.QLabel("Hacé clic en cada uno de los dos miembros que forman la esquina.")
        hint.setWordWrap(True)
        g.addRow(hint)
        return f

    def _selection_changed(self):
        found = []
        for s in FreeCADGui.Selection.getSelectionEx("", 0):
            for sub in (s.SubElementNames or [""]):
                leaf = s.Object.getSubObject(sub, retType=1) if sub else s.Object
                member = _owner_member(leaf) if leaf is not None else None
                if member is None:
                    for name in sub.split(".")[:-1]:
                        o = s.Object.Document.getObject(name)
                        if o is not None and w.is_member(o):
                            member = o
                if member is not None and member not in found:
                    found.append(member)
        # cada clic suma un miembro (FreeCAD reemplaza la selección); quedan los dos últimos
        for m in found:
            if m in self.members:
                continue
            self.members.append(m)
        self.members = self.members[-2:]
        self.which.setText(" / ".join(m.Label for m in self.members))

    def _apply_final(self):
        if len(self.members) != 2:
            raise ValueError("elegí dos miembros que formen una esquina")
        w.gusset(self.members[0], self.members[1], self.size.value(), self.thick.value())


# --- Lista de cortes ---------------------------------------------------------------------------------


def show_cut_list(doc=None):
    doc = doc or _doc()
    if doc is None:
        return
    rows = w.cut_list(doc)
    dlg = QtWidgets.QDialog(_mw())
    dlg.setWindowTitle("Lista de cortes - " + doc.Label)
    lay = QtWidgets.QVBoxLayout(dlg)
    heads = ["Nº", "Cant.", "Perfil", "Largo (mm)", "Ángulo 1", "Ángulo 2", "Peso unit. (kg)", "Peso total (kg)"]
    table = QtWidgets.QTableWidget(len(rows), len(heads))
    table.setHorizontalHeaderLabels(heads)
    table.verticalHeader().setVisible(False)
    for i, r in enumerate(rows):
        vals = [str(r["n"]), str(r["qty"]), r["profile"], w._length_text(r["length"]), w._angle_text(r["angle1"]),
                w._angle_text(r["angle2"]), w._fmt(round(r["unit_kg"], 2)), w._fmt(round(r["total_kg"], 2))]
        for j, v in enumerate(vals):
            it = QtWidgets.QTableWidgetItem(v)
            it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
            if j not in (2,):
                it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            it.setToolTip("\n".join(r["members"]))
            table.setItem(i, j, it)
    table.resizeColumnsToContents()
    lay.addWidget(table)
    total = sum(r["total_kg"] for r in rows)
    note = "Peso total: %s kg." % w._fmt(round(total, 2))
    if any(r["assumed_steel"] for r in rows):
        note += "  Los miembros sin material se pesaron como acero (7850 kg/m³); asignale material en Evaluar."
    if not rows:
        note = "No hay miembros estructurales en este documento."
    lab = QtWidgets.QLabel(note)
    lab.setWordWrap(True)
    lay.addWidget(lab)
    buttons = QtWidgets.QHBoxLayout()
    b_csv = QtWidgets.QPushButton("Exportar CSV (Excel)...")
    b_sheet = QtWidgets.QPushButton("Insertar como planilla")
    b_close = QtWidgets.QPushButton("Cerrar")
    buttons.addWidget(b_csv)
    buttons.addWidget(b_sheet)
    buttons.addStretch(1)
    buttons.addWidget(b_close)
    lay.addLayout(buttons)

    def export():
        import os

        base = os.path.splitext(doc.FileName)[0] if doc.FileName else os.path.join(os.path.expanduser("~"), doc.Label)
        path, _f = QtWidgets.QFileDialog.getSaveFileName(dlg, "Exportar lista de cortes", base + " - lista de cortes.csv",
                                                         "CSV (*.csv)")
        if path:
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                fh.write(w.cut_list_csv(rows))
            _info("Lista de cortes guardada en:\n%s" % path)

    def sheet():
        doc.openTransaction("Lista de cortes")
        w.cut_list_sheet(doc, rows)
        doc.commitTransaction()
        _info("Se agregó la planilla \"Lista de cortes\" al documento (para ponerla en un plano).")

    b_csv.clicked.connect(export)
    b_sheet.clicked.connect(sheet)
    b_close.clicked.connect(dlg.accept)
    dlg.resize(min(900, table.horizontalHeader().length() + 60), 420)
    dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()


# --- Comandos ----------------------------------------------------------------------------------------


class _NoWheel(QtCore.QObject):
    """La ruedita sobre una cajita o lista sin foco no cambia su valor: pasa al panel (que baja)."""

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.Wheel and not obj.hasFocus():
                parent = obj.parentWidget()
                if parent is not None:
                    QtWidgets.QApplication.sendEvent(parent, event)
                return True
        except Exception:
            pass
        return False


def guard_wheel(form):
    """Cajitas numéricas y listas desplegables del panel: solo con clic adentro toman la ruedita."""
    flt = _NoWheel(form)
    for cls in (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox):
        for wdg in form.findChildren(cls):
            wdg.setFocusPolicy(QtCore.Qt.StrongFocus)
            wdg.installEventFilter(flt)
    return flt


def _open(panel_cls, *args):
    if _doc() is None:
        return
    if FreeCADGui.Control.activeDialog():
        FreeCADGui.Control.closeDialog()
    try:
        panel = panel_cls(*args)
        panel._wheel = guard_wheel(panel.form)
        FreeCADGui.Control.showDialog(panel)
    except Exception as e:
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (TITLE, traceback.format_exc()))
        _info("No se pudo abrir: %s" % e)


def start_member():
    _open(MemberPanel)


def start_corners():
    doc = _doc()
    if doc is None:
        return
    chosen = []
    for s in FreeCADGui.Selection.getSelectionEx("", 0):
        for sub in (s.SubElementNames or [""]):
            for name in [s.Object.Name] + sub.split(".")[:-1]:
                o = doc.getObject(name)
                if o is not None and w.is_member(o) and o not in chosen:
                    chosen.append(o)
                if o is not None and o.TypeId == "App::DocumentObjectGroup":
                    for m in o.Group:
                        if w.is_member(m) and m not in chosen:
                            chosen.append(m)
    bodies = chosen if len(chosen) >= 2 else w.members(doc)
    if len(bodies) < 2:
        _info("Hacen falta al menos dos miembros estructurales.")
        return
    _open(CornersPanel, bodies)


def start_trim():
    _open(TrimPanel)


def start_end_cap():
    _open(EndCapPanel)


def start_gusset():
    _open(GussetPanel)


class _Command:
    def __init__(self, text, tip, icon, run):
        self.text, self.tip, self.icon, self.run = text, tip, icon, run

    def GetResources(self):
        from swui import paths

        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": paths.icon(self.icon) or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        try:
            self.run()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (self.text, traceback.format_exc()))


COMMANDS = {
    "SWUI_WeldMember": ("Miembro estructural", "Caños y perfiles sobre las líneas de un croquis esqueleto (como SW)",
                        "fork/weld_member", start_member),
    "SWUI_WeldCorners": ("Esquinas", "Tratamiento de las esquinas entre miembros: a tope o inglete (como SW)",
                         "fork/weld_corners", start_corners),
    "SWUI_WeldTrim": ("Recortar/Alargar", "Recortar o alargar miembros contra otro miembro o una cara plana (como SW)",
                      "fork/weld_trim", start_trim),
    "SWUI_WeldCutList": ("Lista de cortes", "Miembros agrupados con largo, ángulos y peso; exportar a Excel (como SW)",
                         "fork/weld_cutlist", lambda: show_cut_list()),
    "SWUI_WeldEndCap": ("Tapa de extremo", "Chapa que cierra la punta de un caño (como SW)",
                        "fork/weld_endcap", start_end_cap),
    "SWUI_WeldGusset": ("Cartela", "Chapa triangular en la esquina entre dos miembros (como SW)",
                        "fork/weld_gusset", start_gusset),
}


def install():
    from swui.fork import dress_up_panel as dp
    from swui.fork import weld_tab

    if (_member_group, open_edit_member) not in dp.OPENERS:
        dp.OPENERS.append((_member_group, open_edit_member))

    for name, (text, tip, icon, run) in COMMANDS.items():
        try:
            FreeCADGui.addCommand(name, _Command(text, tip, icon, run))
        except Exception:
            pass
    weld_tab.install()
