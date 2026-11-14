# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Croquis 3D: dibujar y editar con el mouse, como SW 2018 (la lógica está en sketch3d.py).

Dibujar (botón Línea, prendido al abrir un croquis nuevo):
  clic, clic, clic...      líneas en cadena (también arrastrando); clic sobre un punto existente
                           termina la cadena; doble clic o clic derecho también
  terna de ejes            en el último punto; la línea engancha a X, Y o Z ("A lo largo de X")
                           cuando el mouse va en esa dirección en la pantalla
  Tab                      cambia el plano de dibujo: Alzado -> Vista lateral -> Planta (el
                           orden XY -> YZ -> ZX de SW; en FreeCAD Z es la vertical)
  Ctrl + clic              en una cara plana o un plano: se dibuja en ese plano
  números + Enter          largo de la línea (queda como cota D1, D2... como en SW)
  Esc                      borra el número escrito; si no hay, corta la cadena; si no, deja de dibujar
Editar (Línea apagado): clic en líneas para elegirlas y relaciones del panel; doble clic en una
línea cambia su largo; Supr borra. Aceptar = salir del croquis; Cancelar deshace todo.
Abrir para editar: doble clic en el croquis 3D (árbol) o en una de sus líneas (vista), o elegirlo
y apretar Croquis 3D.

Detalles de la vista: filtro de eventos de la aplicación mientras el panel está abierto (los clics
izquierdos de dibujo no le llegan a FreeCAD: no elige ni gira); los demás botones siguen moviendo
la vista. Posiciones con getCursorPos/getPointOnFocalPlane/getPointOnViewport (todas en píxeles
Coin, y hacia arriba).
"""

import math
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets
from swui.fork import sketch3d as s3
from swui.fork import safe_ops  # noqa: E402  (#60: cerrar pasos con end_step)

V = FreeCAD.Vector
TITLE = "Croquis 3D"
SNAP_PX = 16.0  # pedido del usuario (07/11): con 10 tomaba antes la línea que el punto
AXIS_DEG = 7.0
MOVE_PX = 5
PLANES = (("Alzado", V(0, 1, 0)), ("Vista lateral", V(1, 0, 0)), ("Planta", V(0, 0, 1)))
AXIS_COLOR = {"X": (0.85, 0.1, 0.1), "Y": (0.1, 0.65, 0.1), "Z": (0.1, 0.2, 0.9)}

_state = {"panel": None, "watch": None}


def _fmt(v):
    return ("%.2f" % v).rstrip("0").rstrip(".").replace(".", ",")


def _view():
    try:
        return FreeCADGui.ActiveDocument.ActiveView
    except Exception:
        return None


def _is_viewport(widget):
    try:
        parent = widget.parentWidget()
        return parent is not None and parent.metaObject().className() == "Gui::View3DInventorViewer"
    except Exception:
        return False


def _screen(view, p):
    fn = getattr(view, "getPointOnViewport", None) or getattr(view, "getPointOnScreen")
    x, y = fn(p)
    return float(x), float(y)


def _focal(view, pos):
    fn = getattr(view, "getPointOnFocalPlane", None) or getattr(view, "getPoint")
    return fn(int(pos[0]), int(pos[1]))


def _ray(view, pos):
    """(punto, dirección) del rayo del mouse."""
    p = _focal(view, pos)
    d = view.getViewDirection()
    try:
        cam = view.getCameraNode()
        if cam.getTypeId().getName() == "PerspectiveCamera":
            c = cam.position.getValue()
            o = V(c[0], c[1], c[2])
            return o, (p - o).normalize()
    except Exception:
        pass
    return p, V(d).normalize()


def _hit_plane(view, pos, base, normal):
    o, d = _ray(view, pos)
    den = d.dot(normal)
    if abs(den) < 1e-9:
        return None
    t = (base - o).dot(normal) / den
    return o + d * t


def _dist2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


# --- Dibujo sobre la vista (Coin) ---------------------------------------------------------------


class _Overlay:
    """Vista previa: línea, terna en el punto de partida, marca de enganche, texto y cotas."""

    def __init__(self, view):
        from pivy import coin

        self.coin = coin
        self.view = view
        self.root = coin.SoAnnotation()
        self.sep = coin.SoSeparator()
        self.root.addChild(self.sep)
        self.dims_sep = coin.SoSeparator()
        self.root.addChild(self.dims_sep)
        try:
            view.getSceneGraph().addChild(self.root)
        except Exception:
            self.root = None

    def clear(self):
        if self.root is not None:
            self.sep.removeAllChildren()

    def remove(self):
        try:
            if self.root is not None:
                self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        self.root = None

    def _line(self, a, b, color, width=2.0, dashed=False, parent=None):
        coin = self.coin
        g = coin.SoSeparator()
        st = coin.SoDrawStyle()
        st.lineWidth = width
        if dashed:
            st.linePattern = 0x0F0F
        col = coin.SoBaseColor()
        col.rgb = color
        co = coin.SoCoordinate3()
        co.point.setValues(0, 2, [[a.x, a.y, a.z], [b.x, b.y, b.z]])
        ls = coin.SoLineSet()
        ls.numVertices.setValue(2)
        for n in (st, col, co, ls):
            g.addChild(n)
        (parent or self.sep).addChild(g)

    def _text(self, p, text, color=(0.1, 0.1, 0.1), parent=None):
        coin = self.coin
        g = coin.SoSeparator()
        tr = coin.SoTranslation()
        tr.translation = (p.x, p.y, p.z)
        col = coin.SoBaseColor()
        col.rgb = color
        font = coin.SoFont()
        font.size = 13
        font.name = "Arial"
        tx = coin.SoText2()
        tx.string = text
        for n in (tr, col, font, tx):
            g.addChild(n)
        (parent or self.sep).addChild(g)

    def _marker(self, p, color=(1.0, 0.5, 0.0)):
        coin = self.coin
        g = coin.SoSeparator()
        col = coin.SoBaseColor()
        col.rgb = color
        co = coin.SoCoordinate3()
        co.point.setValue(p.x, p.y, p.z)
        mk = coin.SoMarkerSet()
        mk.markerIndex = coin.SoMarkerSet.CIRCLE_FILLED_9_9
        for n in (col, co, mk):
            g.addChild(n)
        self.sep.addChild(g)

    def draw(self, anchor, end, snap_point, text, text_at, scale, axis=None):
        self.clear()
        if self.root is None:
            return
        # terna en el punto de partida (sin cadena empezada: en el origen, para engancharlo como en SW)
        base = anchor if anchor is not None else V()
        size = scale * 60.0
        for ax, vec in s3.AXES.items():
            self._line(base - vec * size * 0.15, base + vec * size, AXIS_COLOR[ax], 1.5)
        if anchor is not None and end is not None:
            self._line(anchor, end, AXIS_COLOR.get(axis, (1.0, 0.45, 0.0)) if axis else (1.0, 0.45, 0.0), 2.5)
        if snap_point is not None:
            self._marker(snap_point)
        if text and text_at is not None:
            self._text(text_at, text)

    def draw_dim(self, a, b, off, arrow):
        """Cota gris paralela a la línea a-b, corrida `off`, con líneas de referencia y flechas."""
        gray = (0.45, 0.45, 0.45)
        if self.root is None or (b - a).Length < 1e-9:
            return
        u = (b - a).normalize()
        n = V(off).normalize() if off.Length > 1e-12 else V()
        self._line(a, a + off * 1.15, gray, 1.0)
        self._line(b, b + off * 1.15, gray, 1.0)
        pa, pb = a + off, b + off
        self._line(pa, pb, gray, 1.0)
        for tip, d in ((pa, u), (pb, -u)):
            self._line(tip, tip + d * arrow + n * arrow * 0.35, gray, 1.0)
            self._line(tip, tip + d * arrow - n * arrow * 0.35, gray, 1.0)

    def draw_dims(self, sk):
        if self.root is None:
            return
        self.dims_sep.removeAllChildren()
        for name, value, line in s3.dims(sk):
            if line is None:
                continue
            mid = (s3.point(line, 1) + s3.point(line, 2)) * 0.5
            self._text(mid, _fmt(value), (0.0, 0.0, 0.0), parent=self.dims_sep)


# --- Caja del largo (como las del croquis 2D) ----------------------------------------------------------


class _LengthBox:
    """Caja editable con el largo, sobre la cota, como en el croquis 2D de FreeWorks (On-View
    Parameters de FreeCAD): la misma clase de caja (Gui::QuantitySpinBox), con el número elegido
    para escribir encima; Enter fija el largo. Pedido del usuario (07/11): misma interfaz en todo."""

    OFFSET_PX = 30.0

    def __init__(self, panel):
        self.panel = panel
        self.box = None
        self.edit = None
        self.viewer = None
        self.fresh = True  # primera vez que aparece en este tramo: tomar el foco y elegir el número

    def _make(self):
        if self.box is not None:
            return self.box
        viewer = None
        for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QWidget):
            if _is_viewport(w) and w.isVisible():
                viewer = w.parentWidget()
                break
        if viewer is None:
            return None
        try:
            box = FreeCADGui.UiLoader().createWidget("Gui::QuantitySpinBox", viewer)
        except Exception:
            box = None
        if box is None:
            box = QtWidgets.QLineEdit(viewer)
        box.setObjectName("SWUI_Sketch3DLength")
        box.setFixedWidth(86)
        if hasattr(box, "setButtonSymbols"):
            box.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        edit = box.lineEdit() if hasattr(box, "lineEdit") else box
        edit.textEdited.connect(self._edited)
        self.box, self.edit, self.viewer = box, edit, viewer
        return box

    def _edited(self, text):
        import re

        m = re.match(r"\s*([0-9]+(?:[.,][0-9]*)?)", text)
        self.panel.draw.typed = m.group(1).replace(".", ",") if m else ""
        safe_ops.later_once("sketch3d.mouse", self.panel.mouse_moved)  # una vez por tanda (#25)

    def has_focus(self):
        try:
            fw = QtWidgets.QApplication.focusWidget()
            return self.box is not None and fw is not None and (fw == self.box or fw == self.edit
                                                                 or self.box.isAncestorOf(fw))
        except Exception:
            return False

    def show(self, view, a, b, scale, typed):
        box = self._make()
        if box is None:
            return
        sa, sb = _screen(view, a), _screen(view, b)
        dx, dy = sb[0] - sa[0], sb[1] - sa[1]
        dl = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / dl, dx / dl
        if ny < 0:
            nx, ny = -nx, -ny  # la cota del lado de arriba de la línea en la pantalla
        mid = ((sa[0] + sb[0]) / 2.0, (sa[1] + sb[1]) / 2.0)
        try:
            p0 = _focal(view, (int(mid[0]), int(mid[1])))
            p1 = _focal(view, (int(mid[0] + nx * self.OFFSET_PX), int(mid[1] + ny * self.OFFSET_PX)))
            off = p1 - p0
        except Exception:
            off = V()
        self.panel.overlay.draw_dim(a, b, off, scale * 9.0)
        if not typed:
            text = "%s mm" % _fmt((b - a).Length)
            if self.edit.text() != text:
                self.edit.setText(text)
                if not self.fresh and self.has_focus():
                    self.edit.setSelection(0, len(text.split(" ")[0]))  # sigue lista para escribir encima
        elif not self.has_focus() and not self.edit.text().startswith(typed):
            self.edit.setText("%s mm" % typed)  # escrito con el foco en la vista
        h = self.viewer.height()
        cx, cy = mid[0] + nx * self.OFFSET_PX, mid[1] + ny * self.OFFSET_PX
        box.move(int(cx - box.width() / 2), int(h - cy - box.height() / 2))
        if not box.isVisible():
            box.show()
            box.raise_()
        if self.fresh:
            self.fresh = False
            box.setFocus()
            number = self.edit.text().split(" ")[0]
            self.edit.setSelection(0, len(number))

    def hide(self):
        self.fresh = True
        if self.box is not None:
            try:
                self.box.hide()
            except Exception:
                self.box = None

    def remove(self):
        if self.box is not None:
            try:
                self.box.deleteLater()
            except Exception:
                pass
        self.box = None


# --- Herramienta Línea --------------------------------------------------------------------------------


class _Snap:
    def __init__(self, point, spec, text=""):
        self.point, self.spec, self.text = point, spec, text


class _Draw:
    """Estado del dibujo de líneas en cadena."""

    def __init__(self, panel):
        self.panel = panel
        self.anchor = None  # (Vector, spec del punto)
        self.plane = 0  # índice de PLANES; -1 = plano de una cara (custom)
        self.custom = None  # (base, normal, nombre)
        self.typed = ""
        self.preview = None  # (end Vector, end spec, axis, sign)
        self.press = None
        self.right_used = False

    # plano
    def plane_name(self):
        if self.plane < 0 and self.custom:
            return self.custom[2]
        return PLANES[self.plane][0]

    def plane_normal(self):
        if self.plane < 0 and self.custom:
            return self.custom[1]
        return PLANES[self.plane][1]

    def plane_base(self):
        if self.anchor is not None:
            return self.anchor[0]
        if self.plane < 0 and self.custom:
            return self.custom[0]
        return V()

    def next_plane(self):
        self.plane = 0 if self.plane < 0 else (self.plane + 1) % len(PLANES)
        self.panel.show_plane()

    # enganches
    def snap(self, view, pos, skip_line=None):
        sk = self.panel.sk
        best, best_d = None, SNAP_PX
        try:
            for line, e, p in s3.points(sk):
                d = _dist2(_screen(view, p), pos)
                if d < best_d:
                    best, best_d = _Snap(p, s3.on_point(line, e), "Punto de %s" % line.Label), d
            d = _dist2(_screen(view, V()), pos)
            if d < best_d:
                best, best_d = _Snap(V(), s3.origin(), "Origen"), d
        except Exception:
            pass
        if best is not None:
            return best
        try:
            info = view.getObjectInfo((int(pos[0]), int(pos[1])))
        except Exception:
            info = None
        obj = FreeCAD.ActiveDocument.getObject(info.get("Object")) if info else None
        if obj is not None and not s3.is_line(obj):
            # vértices de la pieza bajo el mouse, por cercanía en la pantalla (como los demás puntos)
            try:
                for i, vx in enumerate(obj.Shape.Vertexes):
                    d = _dist2(_screen(view, vx.Point), pos)
                    if d < best_d:
                        best, best_d = _Snap(vx.Point, s3.on_vertex(obj, "Vertex%d" % (i + 1)),
                                             "Vértice de %s" % obj.Label), d
            except Exception:
                pass
        return best

    def _axis(self, view, pos):
        """(eje, signo, punto 3D) si el mouse va según un eje desde el ancla, en la pantalla."""
        a = self.anchor[0]
        sa = _screen(view, a)
        mv = (pos[0] - sa[0], pos[1] - sa[1])
        ml = math.hypot(*mv)
        if ml < 6:
            return None
        best = None
        for ax, vec in s3.AXES.items():
            sb = _screen(view, a + vec * 100.0)
            dv = (sb[0] - sa[0], sb[1] - sa[1])
            dl = math.hypot(*dv)
            if dl < 1e-6:
                continue
            cos = (mv[0] * dv[0] + mv[1] * dv[1]) / (ml * dl)
            ang = math.degrees(math.acos(max(-1.0, min(1.0, abs(cos)))))
            if ang <= AXIS_DEG and (best is None or ang < best[0]):
                t = 100.0 * (mv[0] * dv[0] + mv[1] * dv[1]) / (dl * dl)
                best = (ang, ax, 1 if t >= 0 else -1, a + vec * t)
        return best[1:] if best else None

    def point_at(self, view, pos):
        """(Vector, spec, eje, signo, texto) del punto bajo el mouse."""
        sn = self.snap(view, pos)
        if sn is not None:
            return sn.point, sn.spec, None, 1, sn.text
        if self.anchor is not None:
            ax = self._axis(view, pos)
            if ax is not None:
                axis, sign, p = ax
                return p, None, axis, sign, "A lo largo de %s" % axis
        p = _hit_plane(view, pos, self.plane_base(), self.plane_normal())
        if p is None:
            return None, None, None, 1, ""
        return p, None, None, 1, ""

    def _scale(self, view, pos):
        try:
            a = _focal(view, pos)
            b = _focal(view, (pos[0] + 1, pos[1]))
            return (a - b).Length
        except Exception:
            return 1.0

    # eventos
    def typed_length(self):
        try:
            value = float(self.typed.replace(",", "."))
            return value if value > 0 else None
        except ValueError:
            return None

    def move(self, view, pos):
        p, spec, axis, sign, text = self.point_at(view, pos)
        self.preview = None
        info = []
        scale = self._scale(view, pos)
        if self.anchor is not None and p is not None:
            length = self.typed_length()
            if length is not None and (p - self.anchor[0]).Length > 1e-9:
                # con el largo escrito, la vista previa lo respeta (como la caja del croquis 2D)
                p = self.anchor[0] + (p - self.anchor[0]).normalize() * length
                spec = None
            self.preview = (p, spec, axis, sign)
        if text:
            info.insert(0, text)
        info.append("Plano: %s (Tab)" % self.plane_name())
        self.panel.overlay.draw(self.anchor[0] if self.anchor else None, p if self.anchor else None,
                                p if spec is not None else None, "  " + " · ".join(info), p,
                                scale, axis)
        if self.preview is not None and (p - self.anchor[0]).Length > 1e-6:
            self.panel.length_box.show(view, self.anchor[0], p, scale, self.typed)
        else:
            self.panel.length_box.hide()

    def click(self, view, pos, ctrl=False):
        if ctrl:
            self.pick_plane(view, pos)
            return
        p, spec, axis, sign, _t = self.point_at(view, pos)
        if p is None:
            return
        if self.anchor is None:
            self.anchor = (p, spec or s3.free(p))
            self.move(view, pos)
            return
        if (p - self.anchor[0]).Length < 1e-6:
            self.end_chain()  # doble clic o clic en el mismo punto: fin de la cadena
            return
        line = self.make(p, spec, axis, sign, None)
        if spec is not None and spec.get("k") in ("pt", "origin", "vtx"):
            self.end_chain()  # cerró sobre un punto existente
        else:
            self.anchor = (s3.point(line, 2), s3.on_point(line, 2))
        self.move(view, pos)

    def drag(self, view, pos0, pos1):
        """Arrastrar: línea del punto donde se apretó al punto donde se soltó."""
        if self.anchor is None:
            p, spec, _a, _s, _t = self.point_at(view, pos0)
            if p is None:
                return
            self.anchor = (p, spec or s3.free(p))
        self.click(view, pos1)

    def make(self, p, spec, axis, sign, length):
        a_point, a_spec = self.anchor
        vec = p - a_point
        if spec is not None and length is None:
            end = spec
        elif axis:
            dist = abs(getattr(vec, axis.lower())) if length is None else length
            end = s3.along(axis, length, sign)
            if length is None:
                end["len"] = {"val": dist}
        else:
            end = s3.direction(vec, length)
        line = self.panel.add_line(a_spec, end)
        return line

    def enter(self, view):
        if not self.typed or self.anchor is None or self.preview is None:
            return
        length = self.typed_length()
        self.typed = ""
        self.panel.length_box.hide()
        if length is None:
            return
        p, _spec, axis, sign = self.preview
        if not axis and (p - self.anchor[0]).Length < 1e-6:
            return
        line = self.make(p, None, axis, sign, length)
        self.anchor = (s3.point(line, 2), s3.on_point(line, 2))
        self.move(view, view.getCursorPos())

    def end_chain(self):
        self.anchor = None
        self.preview = None
        self.typed = ""
        self.panel.overlay.clear()
        self.panel.length_box.hide()

    def pick_plane(self, view, pos):
        """Ctrl + clic en una cara plana o un plano: dibujar en ese plano."""
        try:
            info = view.getObjectInfo((int(pos[0]), int(pos[1])))
        except Exception:
            info = None
        if not info:
            return
        obj = FreeCAD.ActiveDocument.getObject(info.get("Object"))
        comp = str(info.get("Component", ""))
        base = V(info.get("x", 0), info.get("y", 0), info.get("z", 0))
        normal, name = None, None
        try:
            if comp.startswith("Face"):
                face = obj.getSubObject(comp)
                if face.Surface.TypeId == "Part::GeomPlane":
                    normal, name = face.normalAt(0, 0), "%s de %s" % (comp, obj.Label)
            elif obj is not None and obj.TypeId == "App::Plane":
                normal = obj.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
                name = obj.Label
        except Exception:
            normal = None
        if normal is None:
            self.panel.message("Ctrl + clic: elija una cara plana o un plano.")
            return
        self.custom, self.plane = (base, normal, name), -1
        self.panel.show_plane()


# --- Filtro de eventos -------------------------------------------------------------------------------


def _typing_widget():
    w = QtWidgets.QApplication.focusWidget()
    return isinstance(w, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox, QtWidgets.QTextEdit,
                          QtWidgets.QPlainTextEdit))


KEYS = {QtCore.Qt.Key_Tab, QtCore.Qt.Key_Escape, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter,
        QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete, QtCore.Qt.Key_Comma, QtCore.Qt.Key_Period}


class _Filter(QtCore.QObject):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    def eventFilter(self, obj, event):
        try:
            return self._handle(obj, event)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Croquis 3D (eventos):\n%s\n" % traceback.format_exc())
            return False

    def _handle(self, obj, event):
        t = event.type()
        p = self.panel
        if p.done:
            return False
        if t in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.KeyPress):
            from swui.fork import panel_guard

            if not panel_guard.alive(p):  # FreeCAD lo cerró sin avisar: apagarse
                QtCore.QTimer.singleShot(0, p._orphaned)
                return False
        if t in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
            if p.length_box.has_focus():
                key = event.key()
                if key not in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Escape, QtCore.Qt.Key_Return,
                               QtCore.Qt.Key_Enter):
                    return False  # números, coma, borrar: los escribe la caja
                if t == QtCore.QEvent.ShortcutOverride:
                    event.accept()
                    return True
                p.key(key, "")
                return True
            if _typing_widget():
                return False
            key = event.key()
            digit = QtCore.Qt.Key_0 <= key <= QtCore.Qt.Key_9
            if not (digit or key in KEYS):
                return False
            if key == QtCore.Qt.Key_Delete:
                if p.drawing():
                    return False
            elif key == QtCore.Qt.Key_Tab:
                if not p.drawing():
                    return False
            elif key != QtCore.Qt.Key_Escape and not (p.drawing() and p.draw.anchor is not None):
                return False  # números y Enter: solo con una línea empezada (si no, siguen las vistas 0..6)
            if t == QtCore.QEvent.ShortcutOverride:
                event.accept()
                return True
            p.key(key, event.text())
            return True
        if not isinstance(obj, QtWidgets.QWidget) or not _is_viewport(obj):
            return False
        if t == QtCore.QEvent.MouseButtonDblClick and event.button() == QtCore.Qt.LeftButton:
            if p.drawing():
                p.draw.end_chain()
                return True
            return p.double_click()
        if not p.drawing():
            return False
        if t == QtCore.QEvent.MouseMove:
            if not (event.buttons() & (QtCore.Qt.MiddleButton | QtCore.Qt.RightButton)):
                safe_ops.later_once("sketch3d.mouse", p.mouse_moved)  # una vez por tanda (#25)
            return False
        if t == QtCore.QEvent.ContextMenu and p.draw.right_used:
            p.draw.right_used = False
            return True
        if t == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.RightButton and p.draw.anchor is not None:
                p.draw.end_chain()
                p.draw.right_used = True  # que al soltar no salga el menú de FreeCAD
                return True
            if event.button() != QtCore.Qt.LeftButton:
                return False
            view = _view()
            p.draw.press = (view.getCursorPos(), bool(event.modifiers() & QtCore.Qt.ControlModifier))
            return True
        if t == QtCore.QEvent.MouseButtonRelease:
            if event.button() == QtCore.Qt.RightButton and p.draw.anchor is None and not p.draw.right_used:
                return False
            if event.button() != QtCore.Qt.LeftButton:
                if event.button() == QtCore.Qt.RightButton:
                    QtCore.QTimer.singleShot(400, lambda: setattr(p.draw, "right_used", False))
                    return True
                return False
            press, p.draw.press = p.draw.press, None
            if press is None:
                return True
            view = _view()
            pos = view.getCursorPos()
            p.run(lambda: p.draw.click(view, pos, press[1]) if _dist2(press[0], pos) <= MOVE_PX
                  else p.draw.drag(view, press[0], pos))
            return True
        return False


# --- Panel ---------------------------------------------------------------------------------------------


class Sketch3DPanel:
    def __init__(self, sk=None, draw=True):
        self.doc = FreeCAD.ActiveDocument
        self.doc.openTransaction(TITLE)
        self.new = sk is None
        self.sk = sk or s3.new_sketch(self.doc)
        view = _view()
        self.overlay = _Overlay(view)
        self.draw = _Draw(self)
        self.length_box = _LengthBox(self)
        self._build()
        self.filter = _Filter(self)
        QtWidgets.QApplication.instance().installEventFilter(self.filter)
        self.done = False
        self._sel = _SelObserver(self._selection_changed, self)
        FreeCADGui.Selection.addObserver(self._sel)
        self.tool.setChecked(bool(draw))
        self._tool_toggled(bool(draw))
        self.refresh()
        _state["panel"] = self
        try:
            FreeCADGui.Selection.clearSelection()
        except Exception:
            pass

    # interfaz
    def _build(self):
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(TITLE)
        lay = QtWidgets.QVBoxLayout(self.form)
        self.msg = QtWidgets.QLabel()
        self.msg.setWordWrap(True)
        self.msg.setStyleSheet("background:#ffffcc; padding:4px;")
        lay.addWidget(self.msg)
        box = QtWidgets.QGroupBox("Dibujar")
        bl = QtWidgets.QVBoxLayout(box)
        self.tool = QtWidgets.QPushButton("Línea")
        self.tool.setCheckable(True)
        self.tool.setStyleSheet("QPushButton:checked { background:#cfe3f7; border:1px solid #5b9bd5; font-weight:bold; }")
        self.tool.toggled.connect(self._tool_toggled)
        bl.addWidget(self.tool)
        self.plane_lbl = QtWidgets.QLabel()
        self.plane_lbl.setWordWrap(True)
        bl.addWidget(self.plane_lbl)
        lay.addWidget(box)
        box = QtWidgets.QGroupBox("Relaciones existentes")
        bl = QtWidgets.QVBoxLayout(box)
        self.rel_list = QtWidgets.QListWidget()
        self.rel_list.setMaximumHeight(90)
        bl.addWidget(self.rel_list)
        self.state_lbl = QtWidgets.QLabel()
        bl.addWidget(self.state_lbl)
        lay.addWidget(box)
        box = QtWidgets.QGroupBox("Agregar relaciones")
        grid = QtWidgets.QGridLayout(box)
        self.rel_buttons = {}
        for i, (key, text) in enumerate((("X", "A lo largo de X"), ("Y", "A lo largo de Y"), ("Z", "A lo largo de Z"),
                                         ("par", "Paralela"), ("eq", "Igual"), ("fix", "Fijar"))):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(lambda *_a, k=key: self.relation(k))
            grid.addWidget(b, i // 2, i % 2)
            self.rel_buttons[key] = b
        lay.addWidget(box)
        box = QtWidgets.QGroupBox("Cotas")
        bl = QtWidgets.QVBoxLayout(box)
        row = QtWidgets.QHBoxLayout()
        self.dim_btn = QtWidgets.QPushButton("Acotar largo")
        self.dim_btn.clicked.connect(lambda *_a: self.dimension())
        row.addWidget(self.dim_btn)
        self.del_btn = QtWidgets.QPushButton("Borrar")
        self.del_btn.clicked.connect(lambda *_a: self.delete_selected())
        row.addWidget(self.del_btn)
        bl.addLayout(row)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Cota", "Valor (mm)", "Línea"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 80)
        self.table.itemChanged.connect(self._dim_edited)
        bl.addWidget(self.table)
        lay.addWidget(box)
        lay.addStretch(1)
        self._filling = False

    def message(self, text):
        self.msg.setText(text)

    def show_plane(self):
        self.plane_lbl.setText("Plano de dibujo: <b>%s</b>. Tab cambia el plano; Ctrl + clic en una cara o "
                               "un plano lo toma." % self.draw.plane_name())
        self.mouse_moved()

    def drawing(self):
        return self.tool.isChecked()

    def _tool_toggled(self, on):
        if on:
            self.message("Clic para empezar y clic en cada punto (o arrastrar). Escriba el largo y Enter "
                         "para fijarlo. Doble clic, clic derecho o Esc cortan la cadena.")
            FreeCADGui.Selection.clearSelection()
        else:
            self.draw.end_chain()
            self.message("Elija líneas con el mouse para ver y agregar relaciones. Doble clic en una línea "
                         "cambia su largo. Supr borra.")
        self.show_plane()

    def run(self, fn):
        try:
            fn()
        except Exception as e:
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (TITLE, traceback.format_exc()))
            self.message("No se pudo: %s" % e)
        self.refresh()

    def mouse_moved(self):
        view = _view()
        if view is None or not self.drawing():
            return
        try:
            self.draw.move(view, view.getCursorPos())
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Croquis 3D (mover):\n%s\n" % traceback.format_exc())

    def key(self, key, text):
        view = _view()
        if key == QtCore.Qt.Key_Escape:
            if self.draw.typed:
                self.draw.typed = ""
            elif self.draw.anchor is not None:
                self.draw.end_chain()
            elif self.drawing():
                self.tool.setChecked(False)
            else:
                FreeCADGui.Selection.clearSelection()
        elif key == QtCore.Qt.Key_Tab:
            if self.drawing():
                self.draw.next_plane()
        elif key == QtCore.Qt.Key_Delete:
            self.delete_selected()
        elif key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if self.drawing():
                self.run(lambda: self.draw.enter(view))
        elif key == QtCore.Qt.Key_Backspace:
            self.draw.typed = self.draw.typed[:-1]
        elif self.drawing() and self.draw.anchor is not None:
            ch = "," if key in (QtCore.Qt.Key_Comma, QtCore.Qt.Key_Period) else (text or "")
            if ch and (ch.isdigit() or (ch == "," and "," not in self.draw.typed)):
                self.draw.typed += ch
        self.mouse_moved()

    # cambios en el modelo
    def add_line(self, start, end):
        line = s3.add_line(self.sk, start, end)
        self.doc.recompute()
        return line

    def selected_lines(self):
        out = []
        for s in FreeCADGui.Selection.getSelectionEx("", 0):
            for name in [s.ObjectName] + [x.split(".")[0] for x in (s.SubElementNames or []) if x]:
                o = self.doc.getObject(name)
                if s3.is_line(o) and s3.sketch_of(o) is not None and s3.sketch_of(o).Name == self.sk.Name \
                        and o not in out:
                    out.append(o)
                    break
        return out

    def relation(self, key):
        sel = self.selected_lines()
        if key in ("X", "Y", "Z", "fix"):
            if not sel:
                self.message("Elija una o más líneas del croquis.")
                return
            for line in sel:
                self.run(lambda l=line: s3.fix(l) if key == "fix" else s3.set_axis(l, key))
        else:
            if len(sel) != 2:
                self.message("Elija dos líneas: la segunda toma la dirección (Paralela) o el largo (Igual) "
                             "de la primera.")
                return
            ref, line = sel
            self.run(lambda: s3.set_parallel(line, ref) if key == "par" else s3.set_equal(line, ref))

    def dimension(self):
        sel = self.selected_lines()
        if len(sel) != 1:
            self.message("Elija una línea para acotar su largo.")
            return
        self.edit_length(sel[0])

    def edit_length(self, line):
        value, ok = QtWidgets.QInputDialog.getDouble(FreeCADGui.getMainWindow(), TITLE,
                                                     "Largo de %s (mm):" % line.Label, s3.length(line),
                                                     0.001, 1e7, 2)
        if ok:
            self.run(lambda: s3.set_length(line, value))

    def delete_selected(self):
        sel = self.selected_lines()
        if not sel:
            return
        FreeCADGui.Selection.clearSelection()

        def go():
            touched = s3.delete_lines(sel)
            if touched:
                self.message("Quedaron sueltas donde estaban: %s." % ", ".join(l.Label for l in touched))
        self.run(go)

    def double_click(self):
        obj = _line_under_mouse()
        if s3.is_line(obj) and s3.sketch_of(obj) is not None and s3.sketch_of(obj).Name == self.sk.Name:
            QtCore.QTimer.singleShot(0, lambda: self.edit_length(obj))
            return True
        return False

    def _selection_changed(self):
        if not self.done:
            self.refresh(False)

    def refresh(self, recompute=True):
        try:
            if recompute:
                self.doc.recompute()
            s3.update_colors(self.sk)
            self.overlay.draw_dims(self.sk)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Croquis 3D:\n%s\n" % traceback.format_exc())
        sel = self.selected_lines()
        self.rel_list.clear()
        if len(sel) == 1:
            for text in s3.relations(sel[0]):
                self.rel_list.addItem(text)
            self.state_lbl.setText("%s: %s" % (sel[0].Label, "totalmente definida" if s3.is_defined(sel[0])
                                                else "insuficientemente definida"))
        else:
            self.state_lbl.setText("Croquis: %s" % s3.state(self.sk).lower())
        self._filling = True
        dims = s3.dims(self.sk)
        self.table.setRowCount(len(dims))
        for r, (name, value, line) in enumerate(dims):
            for c, text in enumerate((name, _fmt(value), line.Label if line else "")):
                item = QtWidgets.QTableWidgetItem(text)
                flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
                if c == 1:
                    flags |= QtCore.Qt.ItemIsEditable
                item.setFlags(flags)
                self.table.setItem(r, c, item)
        self._filling = False

    def _dim_edited(self, item):
        if self._filling or item.column() != 1:
            return
        name = self.table.item(item.row(), 0).text()
        try:
            value = float(item.text().replace(",", "."))
        except ValueError:
            self.refresh(False)
            return
        if value <= 0:
            self.refresh(False)
            return
        self.run(lambda: s3.set_dim(self.sk, name, value))

    # cierre
    def _finish(self):
        if self.done:
            return
        self.done = True
        try:
            QtWidgets.QApplication.instance().removeEventFilter(self.filter)
        except Exception:
            pass
        try:
            FreeCADGui.Selection.removeObserver(self._sel)
        except Exception:
            pass
        self.overlay.remove()
        self.length_box.remove()
        _state["panel"] = None

    def _orphaned(self):
        """FreeCAD cerró el panel por su cuenta (otro comando con "Sí" a "Un diálogo ya está
        abierto"): se apaga todo lo nuestro y lo dibujado queda (como Aceptar)."""
        was_done = self.done
        self._finish()
        if not was_done:
            try:
                # solo si el paso abierto sigue siendo el nuestro: si ya es el del comando que
                # cerró el panel, cerrarlo le rompería su Cancelar (revisión de #60, 13/11)
                active = FreeCAD.getActiveTransaction()
                if active and active[0] == TITLE:
                    safe_ops.end_step(self.doc)
                s3.update_colors(self.sk)
            except Exception:
                pass

    def accept(self):
        self._finish()
        try:
            if self.new and not s3.lines(self.sk):
                vs = s3.varset(self.sk)
                self.doc.removeObject(self.sk.Name)
                if vs is not None:
                    self.doc.removeObject(vs.Name)
            else:
                s3.update_colors(self.sk)
            safe_ops.end_step(self.doc)
        except Exception:
            safe_ops.end_step(self.doc, abort=True)
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (TITLE, traceback.format_exc()))
        FreeCADGui.Control.closeDialog()
        self.doc.recompute()
        return True

    def reject(self):
        self._finish()
        safe_ops.end_step(self.doc, abort=True)
        FreeCADGui.Control.closeDialog()
        self.doc.recompute()
        return True

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel


class _SelObserver:
    def __init__(self, fn, panel):
        self.fn = fn
        self.panel = panel  # panel_guard.orphaned lo mira

    def _later(self, *_a):
        from swui.fork import panel_guard

        if self.panel.done or panel_guard.orphaned(self):
            return
        QtCore.QTimer.singleShot(0, self.fn)

    addSelection = removeSelection = clearSelection = setSelection = _later


# --- Comando y aperturas -------------------------------------------------------------------------------


def _selected_sketch():
    for s in FreeCADGui.Selection.getSelectionEx("", 0):
        for name in [s.ObjectName] + [x.split(".")[0] for x in (s.SubElementNames or []) if x]:
            sk = s3.sketch_of(FreeCAD.ActiveDocument.getObject(name))
            if sk is not None:
                return sk
    return None


def _empty_view(doc):
    """Documento sin nada a la vista: isométrica de ~1 m alrededor del origen (FreeCAD arranca con
    un zoom de pocos milímetros y lo que se dibuja no se ve)."""
    for o in doc.Objects:
        try:
            if o.ViewObject.Visibility and hasattr(o, "Shape") and not o.Shape.isNull() \
                    and o.Shape.BoundBox.DiagonalLength > 1e-6:
                return
        except Exception:
            pass
    view = _view()
    try:
        view.viewIsometric()
        cam = view.getCameraNode()
        d = view.getViewDirection()
        dist = 3000.0
        cam.position.setValue(-d.x * dist + 250, -d.y * dist + 150, -d.z * dist + 250)
        cam.focalDistance.setValue(dist)
        if cam.getTypeId().getName() == "OrthographicCamera":
            cam.height.setValue(1400.0)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Croquis 3D (vista):\n%s\n" % traceback.format_exc())


def open_sketch(sk=None, draw=None):
    """Abre el panel: croquis nuevo (sk None, dibujando) o editar uno existente."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None
    old = _state["panel"]
    if old is not None and not old.done:
        old.accept()  # otro croquis 3D abierto: se cierra guardando (como salir del croquis en SW)
    if FreeCADGui.Control.activeDialog():
        from swui.fork import panel_guard

        if not panel_guard.cancel_open():
            FreeCADGui.Control.closeDialog()
    if sk is None:
        _empty_view(doc)
    try:
        panel = Sketch3DPanel(sk, draw=(sk is None) if draw is None else draw)
        FreeCADGui.Control.showDialog(panel)
        from swui.fork import panel_guard

        panel_guard.track(panel)
        return panel
    except Exception as e:
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (TITLE, traceback.format_exc()))
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), TITLE, "No se pudo abrir: %s" % e)
        return None


class _Command:
    def GetResources(self):
        from swui import paths

        return {"MenuText": "Croquis 3D",
                "ToolTip": "Croquis en el espacio: líneas en cualquier dirección, atadas a X, Y o Z, con cotas "
                           "(como SW). Con un croquis 3D elegido, lo edita.",
                "Pixmap": paths.icon("fork/sketch3d") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        try:
            open_sketch(_selected_sketch())
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (TITLE, traceback.format_exc()))


COMMAND = "SWUI_Sketch3D"


class _Watch(QtCore.QObject):
    """Doble clic en un croquis 3D (árbol) o en una de sus líneas (vista) lo abre para editar."""

    def eventFilter(self, obj, event):
        try:
            if event.type() != QtCore.QEvent.MouseButtonDblClick or event.button() != QtCore.Qt.LeftButton:
                return False
            if _state["panel"] is not None or FreeCADGui.Control.activeDialog():
                return False
            if not isinstance(obj, QtWidgets.QWidget):
                return False
            if _is_viewport(obj):
                o = _line_under_mouse()
                if o is not None:
                    sk = s3.sketch_of(o)
                    QtCore.QTimer.singleShot(0, lambda: open_sketch(sk, draw=False))
                    return True
                return False
            parent = obj.parentWidget()
            if parent is not None and parent.metaObject().className() == "Gui::TreeWidget":
                QtCore.QTimer.singleShot(0, _tree_double)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Croquis 3D (doble clic):\n%s\n" % traceback.format_exc())
        return False


def _line_under_mouse():
    """Línea de croquis 3D bajo el mouse; si getObjectInfo no la toma (a veces por un píxel), la
    que dejó elegida el primer clic del doble clic."""
    doc = FreeCAD.ActiveDocument
    view = _view()
    names = []
    try:
        info = view.getObjectInfo(view.getCursorPos()) if view else None
        if info:
            names.append(info.get("Object"))
            names += [x for x in str(info.get("SubName", "")).split(".") if x]
    except Exception:
        pass
    for s in FreeCADGui.Selection.getSelectionEx("", 0):
        names.append(s.ObjectName)
        for sub in s.SubElementNames or []:
            names += [x for x in sub.split(".") if x]
    for name in names:
        o = doc.getObject(name) if name else None
        if s3.is_line(o) and s3.sketch_of(o) is not None:
            return o
    return None


def _tree_double():
    sel = FreeCADGui.Selection.getSelection()
    if len(sel) == 1 and s3.sketch_of(sel[0]) is not None and not FreeCADGui.Control.activeDialog():
        open_sketch(s3.sketch_of(sel[0]), draw=False)


def install():
    from swui.fork import sketch3d_tab

    try:
        FreeCADGui.addCommand(COMMAND, _Command())
    except Exception:
        pass
    sketch3d_tab.install()
    if _state["watch"] is None:
        _state["watch"] = _Watch()
        QtWidgets.QApplication.instance().installEventFilter(_state["watch"])
