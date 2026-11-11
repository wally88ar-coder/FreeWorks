# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Vista de sección como SW 2018 (pedido del usuario, 07/11; botón de la barrita de la vista).

Relevado en SW con el mouse (07/11): el botón abre el panel "Vista de sección"; Sección 1 con
Alzado / Planta / Vista lateral (o una cara o plano elegido), invertir lado, distancia, giro en X y
en Y, color de la tapa y "Mostrar tapa de sección"; se ve en vivo. Con Alzado saca la mitad que mira
hacia el que está enfrente (queda la de atrás). Al aceptar la pieza queda cortada y el botón queda
hundido; otro clic en el botón saca el corte. Solo cambia lo que se ve: no toca el documento.

Cómo: un SoClipPlane al principio del dibujo del documento en la vista (FreeCAD hace lo mismo con su
"Plano de recorte", Std_ToggleClipPlane, que no tiene tapa). La tapa (la cara cortada, pintada) se
calcula con Shape.slice de cada sólido visible y se dibuja antes del plano de corte, así no se
recorta. Se recalcula al reconstruir.

Funciones públicas (regla "panel = cara de una función"):
  section_on(view, normal, point, cap=True, color=CAP_COLOR)  -> corta la vista
  section_off(view)                                           -> la deja entera
  is_on(view)
  plane_frame(doc, name, offset, flip, rot_x, rot_y)          -> (normal, punto) del corte
"""

import math
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

CAP_COLOR = (0.0, 0.0, 1.0)  # azul, como el color de tapa de SW
PLANES = (("Alzado", "XZ_Plane"), ("Planta", "XY_Plane"), ("Vista lateral", "YZ_Plane"))
WB_NAME = "LikeSolidWorksUIWorkbench"

_state = {"views": {}, "observer": None, "panel": None}


# --- Lógica (sin interfaz) ---------------------------------------------------------------


def is_on(view):
    try:
        return _view_key(view) in _state["views"]
    except Exception:
        return False


def _view_key(view):
    """Clave estable de la vista: la dirección del nodo raíz. No sirve id() (pivy da un objeto nuevo
    por cada pedido) ni getNodeId() (Coin lo cambia con cada cambio de la escena: al reconstruir
    quedaba un corte "huérfano" que el botón ya no sacaba; reporte del usuario, 07/11)."""
    try:
        return int(view.getSceneGraph().this)
    except Exception:
        return id(view)


def _origin_plane(doc, role):
    from swui.fork import origin_planes as op

    for p in op.primary_planes(doc):
        if getattr(p, "Role", "") == role:
            return p
    return None


def plane_frame(doc, name, offset=0.0, flip=False, rot_x=0.0, rot_y=0.0):
    """(normal, punto) del plano de corte. `name`: Alzado / Planta / Vista lateral, o un plano o cara
    como (normal, punto). Se ve el lado contrario a la normal (como SW); flip lo invierte."""
    if isinstance(name, tuple):
        n, p = FreeCAD.Vector(name[0]), FreeCAD.Vector(name[1])
        xdir = n.cross(FreeCAD.Vector(0, 0, 1))
        if xdir.Length < 1e-9:
            xdir = FreeCAD.Vector(1, 0, 0)
        xdir.normalize()
        ydir = n.cross(xdir)
    else:
        role = dict(PLANES).get(name, name)
        plane = _origin_plane(doc, role)
        if plane is not None:
            pl = plane.getGlobalPlacement() if hasattr(plane, "getGlobalPlacement") else plane.Placement
        else:  # sin Cuerpo: los planos del documento en el origen
            rots = {"XY_Plane": FreeCAD.Rotation(),
                    "XZ_Plane": FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90),
                    "YZ_Plane": FreeCAD.Rotation(0.5, 0.5, 0.5, 0.5)}
            pl = FreeCAD.Placement(FreeCAD.Vector(), rots.get(role, FreeCAD.Rotation()))
        r = pl.Rotation
        n = r.multVec(FreeCAD.Vector(0, 0, 1))
        xdir = r.multVec(FreeCAD.Vector(1, 0, 0))
        ydir = r.multVec(FreeCAD.Vector(0, 1, 0))
        p = pl.Base
    n = FreeCAD.Vector(n)
    n.normalize()
    if rot_x:
        n = FreeCAD.Rotation(xdir, rot_x).multVec(n)
    if rot_y:
        n = FreeCAD.Rotation(ydir, rot_y).multVec(n)
    p = p + n * float(offset)
    keep = n * (1 if flip else -1)  # sin invertir: queda el lado de atrás (contrario a la normal)
    return keep, p


def _solids(doc):
    """Formas visibles con sólidos, en coordenadas globales: cada Cuerpo entero (no sus operaciones)
    y los objetos Part sueltos."""
    out = []
    for o in doc.Objects:
        try:
            if not o.ViewObject or not o.ViewObject.Visibility:
                continue
            if o.TypeId.startswith("App::") or "Sketch" in o.TypeId:
                continue
            parent = o.getParentGeoFeatureGroup()
            if parent is not None and parent.TypeId == "PartDesign::Body":
                continue  # se corta el Cuerpo entero
            sh = getattr(o, "Shape", None)
            if sh is None or sh.isNull() or not sh.Solids:
                continue
            sh = sh.copy()
            sh.Placement = o.getGlobalPlacement()
            out.append((o, sh))
        except Exception:
            continue
    return out


def cap_shapes(doc, keep, point):
    """Caras de la tapa: el corte de cada sólido visible con el plano."""
    import Part

    n = FreeCAD.Vector(keep)
    d = n.dot(point)
    faces = []
    for o, sh in _solids(doc):
        try:
            wires = sh.slice(n, d)
            if not wires:
                continue
            faces.append(Part.makeFace(wires, "Part::FaceMakerBullseye"))
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Tapa de sección de %s: %s\n" % (o.Name, traceback.format_exc()))
    return faces


def _cap_node(faces, color):
    from pivy import coin

    sep = coin.SoSeparator()
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE
    mat = coin.SoMaterial()
    mat.diffuseColor = color
    mat.emissiveColor = tuple(0.3 * c for c in color)
    hints = coin.SoShapeHints()
    hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
    for n in (pick, mat, hints):
        sep.addChild(n)
    for f in faces:
        try:
            pts, tris = f.tessellate(0.05)
        except Exception:
            continue
        if not tris:
            continue
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
        fs = coin.SoIndexedFaceSet()
        idx = []
        for t in tris:
            idx.extend([t[0], t[1], t[2], -1])
        fs.coordIndex.setValues(0, len(idx), idx)
        sep.addChild(coords)
        sep.addChild(fs)
    return sep


def section_on(view, normal, point, cap=True, color=CAP_COLOR):
    """Cortar la vista con el plano (se ve el lado hacia `normal`). Si ya estaba cortada, lo cambia."""
    from pivy import coin

    section_off(view)
    root = view.getSceneGraph()
    n = FreeCAD.Vector(normal)
    n.normalize()
    clip = coin.SoClipPlane()
    clip.plane.setValue(coin.SbPlane(coin.SbVec3f(n.x, n.y, n.z), n.dot(point)))
    cap_sep = None
    doc = FreeCADGui.ActiveDocument.Document if FreeCADGui.ActiveDocument else None
    if cap and doc is not None:
        cap_sep = _cap_node(cap_shapes(doc, n, point), color)
        root.insertChild(cap_sep, 0)
    root.insertChild(clip, 1 if cap_sep is not None else 0)
    _state["views"][_view_key(view)] = {"view": view, "root": root, "clip": clip, "cap": cap_sep,
                                        "normal": n, "point": FreeCAD.Vector(point), "show_cap": cap,
                                        "color": color}
    _watch()
    try:
        view.redraw()
    except Exception:
        pass


def section_off(view):
    """Volver a ver la pieza entera."""
    st = _state["views"].pop(_view_key(view), None)
    if st is None:
        return
    for node in (st["clip"], st["cap"]):
        if node is None:
            continue
        try:
            i = st["root"].findChild(node)
            if i >= 0:
                st["root"].removeChild(i)
        except Exception:
            pass
    try:
        view.redraw()
    except Exception:
        pass


def _refresh_caps(doc):
    for st in list(_state["views"].values()):
        try:
            if st["cap"] is None:
                continue
            gd = FreeCADGui.getDocument(doc.Name)
            if gd is None:
                continue
            section_on(st["view"], st["normal"], st["point"], st["show_cap"], st["color"])
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Vista de sección: %s\n" % traceback.format_exc())


class _DocObserver:
    def slotRecomputedDocument(self, doc):
        QtCore.QTimer.singleShot(0, lambda: _refresh_caps(doc))

    def slotDeletedDocument(self, doc):
        for k, st in list(_state["views"].items()):
            try:
                st["view"].getSceneGraph()
            except Exception:
                _state["views"].pop(k, None)


def _watch():
    if _state["observer"] is None:
        _state["observer"] = _DocObserver()
        FreeCAD.addDocumentObserver(_state["observer"])


# --- Panel estilo SW ---------------------------------------------------------------------------


def _selected_frame():
    """(normal, punto) de la cara plana o plano elegido, o None."""
    try:
        for s in FreeCADGui.Selection.getSelectionEx("", 0):
            obj = s.Object
            for sub in (s.SubElementNames or []):
                if not sub:
                    continue
                el = obj.getSubObject(sub)
                if el is not None and el.ShapeType == "Face" and el.Surface.__class__.__name__ == "Plane":
                    u0, u1, v0, v1 = el.ParameterRange
                    n = el.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
                    return (n, el.CenterOfMass), s.Object.Label + "." + sub.split(".")[-1]
                sub_obj = obj.getSubObject(sub, retType=1)
                if sub_obj is not None and getattr(sub_obj, "TypeId", "") in ("App::Plane", "PartDesign::Plane"):
                    pl = obj.getSubObject(sub, retType=3)
                    n = pl.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
                    return (n, pl.Base), sub_obj.Label
            if getattr(obj, "TypeId", "") in ("App::Plane", "PartDesign::Plane"):
                pl = obj.getGlobalPlacement()
                return (pl.Rotation.multVec(FreeCAD.Vector(0, 0, 1)), pl.Base), obj.Label
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Vista de sección: %s\n" % traceback.format_exc())
    return None


class SectionPanel:
    """Panel "Vista de sección" (lado izquierdo, Tareas)."""

    def __init__(self, view):
        self.view = view
        self.doc = FreeCADGui.ActiveDocument.Document
        self.ref = "Alzado"  # o (normal, punto) de una cara / plano elegido
        self.color = CAP_COLOR
        self.form = self._build()
        sel = _selected_frame()
        if sel is not None:
            self.ref = sel[0]
            self.ref_edit.setText(sel[1])
        self._update()

    def _build(self):
        w = QtWidgets.QWidget()
        w.setWindowTitle("Vista de sección")
        lay = QtWidgets.QVBoxLayout(w)
        box = QtWidgets.QGroupBox("Sección 1")
        g = QtWidgets.QGridLayout(box)
        row = QtWidgets.QHBoxLayout()
        self.plane_buttons = []
        for name, _role in PLANES:
            b = QtWidgets.QToolButton()
            b.setText(name)
            b.setCheckable(True)
            b.setAutoExclusive(False)
            b.clicked.connect(lambda _c=False, nm=name: self._pick_plane(nm))
            row.addWidget(b)
            self.plane_buttons.append((name, b))
        g.addLayout(row, 0, 0, 1, 3)
        self.flip = QtWidgets.QToolButton()
        self.flip.setText("⇅")
        self.flip.setToolTip("Invertir el lado que se ve")
        self.flip.setCheckable(True)
        self.flip.toggled.connect(lambda *_a: self._update())
        self.ref_edit = QtWidgets.QLineEdit("Alzado")
        self.ref_edit.setReadOnly(True)
        self.ref_edit.setToolTip("Plano de corte: Alzado, Planta, Vista lateral, o elija una cara plana o un plano")
        g.addWidget(self.flip, 1, 0)
        g.addWidget(self.ref_edit, 1, 1, 1, 2)
        self.offset = self._spin(g, 2, "Distancia", "mm", -1e6, 1e6, 0.0)
        self.rot_x = self._spin(g, 3, "Girar en X", "°", -180, 180, 0.0)
        self.rot_y = self._spin(g, 4, "Girar en Y", "°", -180, 180, 0.0)
        self.cap = QtWidgets.QCheckBox("Mostrar tapa de sección")
        self.cap.setChecked(True)
        self.cap.toggled.connect(lambda *_a: self._update())
        g.addWidget(self.cap, 5, 0, 1, 2)
        self.color_btn = QtWidgets.QPushButton("Editar color")
        self.color_btn.clicked.connect(self._pick_color)
        g.addWidget(self.color_btn, 5, 2)
        lay.addWidget(box)
        hint = QtWidgets.QLabel("Elija una cara plana o un plano en la vista para cortar por ahí.")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addStretch(1)
        self._sel_obs = _PanelSel(self)
        FreeCADGui.Selection.addObserver(self._sel_obs)
        return w

    def _spin(self, grid, row, label, unit, lo, hi, val):
        grid.addWidget(QtWidgets.QLabel(label), row, 0)
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(2)
        s.setSuffix(" " + unit)
        s.setValue(val)
        s.valueChanged.connect(lambda *_a: self._update())
        grid.addWidget(s, row, 1, 1, 2)
        return s

    def _pick_plane(self, name):
        self.ref = name
        self.ref_edit.setText(name)
        self._update()

    def picked(self):
        sel = _selected_frame()
        if sel is None:
            return
        self.ref = sel[0]
        self.ref_edit.setText(sel[1])
        self._update()

    def _pick_color(self):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor.fromRgbF(*self.color), self.form, "Color de la tapa")
        if c.isValid():
            self.color = (c.redF(), c.greenF(), c.blueF())
            self._update()

    def _update(self):
        for name, b in self.plane_buttons:
            b.setChecked(self.ref == name)
        try:
            keep, point = plane_frame(self.doc, self.ref, self.offset.value(), self.flip.isChecked(),
                                      self.rot_x.value(), self.rot_y.value())
            section_on(self.view, keep, point, self.cap.isChecked(), self.color)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Vista de sección:\n%s\n" % traceback.format_exc())
        _sync_buttons()

    def _close(self):
        try:
            FreeCADGui.Selection.removeObserver(self._sel_obs)
        except Exception:
            pass
        _state["panel"] = None
        FreeCADGui.Control.closeDialog()
        _sync_buttons()

    def accept(self):
        self._close()  # el corte queda
        return True

    def reject(self):
        section_off(self.view)
        self._close()
        return True

    def _orphaned(self):
        """FreeCAD cerró el panel sin Cancelar: como Cancelar (sin corte a medias)."""
        try:
            section_off(self.view)
        except Exception:
            pass
        _state["panel"] = None
        _sync_buttons()

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel


class _PanelSel:
    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, *_a):
        from swui.fork import panel_guard

        if panel_guard.orphaned(self):  # FreeCAD cerró el panel: la escucha se apaga (#29)
            return
        QtCore.QTimer.singleShot(0, self.panel.picked)


# --- Botón (lo usa la barrita de la vista) -----------------------------------------------------

_buttons = []


def register_button(button):
    _buttons.append(button)
    _sync_buttons()


def _sync_buttons():
    try:
        view = FreeCADGui.ActiveDocument.ActiveView if FreeCADGui.ActiveDocument else None
        on = (view is not None and is_on(view)) or _state["panel"] is not None
    except Exception:
        on = False
    for b in list(_buttons):
        try:
            b.blockSignals(True)
            b.setChecked(on)
            b.blockSignals(False)
        except Exception:
            _buttons.remove(b)


def toggle():
    """Lo que hace el botón: abre el panel, o saca el corte si ya estaba (como SW)."""
    gd = FreeCADGui.ActiveDocument
    if gd is None:
        _sync_buttons()
        return
    view = gd.ActiveView
    if _state["panel"] is not None:
        _state["panel"].reject()
        return
    if is_on(view):
        section_off(view)
        _sync_buttons()
        return
    if FreeCADGui.Control.activeDialog():
        FreeCADGui.Control.closeDialog()
    panel = SectionPanel(view)
    _state["panel"] = panel
    from swui.fork import safe_ops

    safe_ops.show_panel(panel)  # anotado en el guardia: otro comando lo cancela de verdad (#29)
    _sync_buttons()
