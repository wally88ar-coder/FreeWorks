# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Giro de la vista con la ruedita del mouse, como en SOLIDWORKS.

Dos maneras (menú FreeWorks -> "Velocidad de giro..."):

- "Como SolidWorks" (de fábrica, 14/11): FreeWorks gira la cámara él mismo
  mientras se arrastra con la ruedita SIN teclas, con lo medido en SW 2018
  (docs/NOTAS_TECNICAS.md, "Giro de la vista"):
    * ejes de la pantalla: a los costados gira alrededor del eje vertical de
      la pantalla, arriba/abajo alrededor del horizontal; nunca se tuerce;
    * velocidad pareja y proporcional al recorrido: SW_GRADOS por cada alto de
      la vista (horizontal) y por cada ancho + SW_ARBOL_PX (vertical);
    * centro de giro: el centro de la pieza (caja de lo visible) mientras la
      pieza no pase ZOOM_LIMITE veces la vista y su centro esté a la vista; si
      no, el punto de la pieza en el centro de la pantalla, PROF_PX por detrás
      de la superficie; sin pieza en el centro, el medio de lo que se ve.
  Un clic suelto con la ruedita (sin mover) no hace nada, como en SW (FreeCAD
  hacía saltar la vista para centrarla en el punto clicado).
- "x1 (como FreeCAD)", "x1,5"...: FreeCAD gira solo; cada movimiento se
  agranda FACTOR veces respecto del punto donde se apretó la ruedita.

Ctrl/Mayús + ruedita, el zoom y las hojas de dibujo no se tocan. Solo actúa
dentro de LikeSolidWorks UI y con el estilo de navegación SolidWorks.

Las cuentas son funciones sin FreeCAD (sw_angles, pivot_rule, orbit_step),
para probarlas solas y desde guiones.
"""

import math

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
KEY = "OrbitSpeed"
SW_KEY = "OrbitLikeSW"  # True = "Como SolidWorks"
DEFAULT = 1.5
CHOICES = (1.0, 1.5, 2.0, 2.5)
SW_TEXT = "Como SolidWorks"
NAV_STYLES = ("Gui::SolidWorksNavigationStyle",)  # estilos donde ruedita sin teclas = girar
VIEW_CLASS = "Gui::View3DInventor"
WB_NAME = "LikeSolidWorksUIWorkbench"
COMMAND = "SWUI_OrbitSpeed"

# Medido en SW 2018 con tres tamaños de ventana (14/11): 377° por alto de vista
# (horizontal) y por ancho de vista + árbol de operaciones (vertical).
SW_GRADOS = 377.0
SW_ARBOL_PX = 236.0
ZOOM_LIMITE = 1.3  # SW: con 1,19 veces el alto de la vista gira en el centro de la pieza; con 1,44 ya no
PROF_PX = 115.0  # SW: el centro va ~95-134 px (de pantalla) por detrás de la superficie
MOVER_MIN_PX = 2.0  # menos que esto, al soltar, es un clic

_filter = None


# --- Preferencia -----------------------------------------------------------


def factor():
    try:
        value = FreeCAD.ParamGet(PARAMS).GetFloat(KEY, DEFAULT)
    except Exception:
        value = DEFAULT
    return value if value > 0 else DEFAULT


def set_factor(value):
    FreeCAD.ParamGet(PARAMS).SetFloat(KEY, float(value))


def like_sw():
    """True si el giro es "Como SolidWorks" (de fábrica)."""
    try:
        return FreeCAD.ParamGet(PARAMS).GetBool(SW_KEY, True)
    except Exception:
        return True


def set_like_sw(value):
    FreeCAD.ParamGet(PARAMS).SetBool(SW_KEY, bool(value))


def choice_text(value):
    """1.5 -> 'x1,5'; 1.0 -> 'x1 (como FreeCAD)'."""
    text = ("x%g" % value).replace(".", ",")
    return text + " (como FreeCAD)" if value == 1.0 else text


def scaled(start, pos, k):
    """Punto agrandado k veces desde start (x, y)."""
    return (start[0] + (pos[0] - start[0]) * k, start[1] + (pos[1] - start[1]) * k)


# --- Cuentas del giro como SW (sin FreeCAD) --------------------------------


def sw_angles(dx, dy, width, height):
    """Ángulos (radianes) para un movimiento de dx, dy px en una vista de width x height px.

    Horizontal: SW_GRADOS por cada alto de vista; vertical: por cada ancho + árbol.
    """
    h = math.radians(SW_GRADOS * dx / max(float(height), 1.0))
    v = math.radians(SW_GRADOS * dy / (max(float(width), 1.0) + SW_ARBOL_PX))
    return h, v


def pivot_rule(corners, center, width, height):
    """Dónde gira SW, en píxeles de la vista (origen en una esquina, cualquier sentido de y).

    corners: las 8 esquinas de la caja de la pieza proyectadas; center: su centro proyectado.
    Devuelve ("pieza", center) o ("pantalla", (x, y)) con el medio de lo que se ve de la caja
    (el que llama prueba antes la superficie en el centro de la pantalla).
    """
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    w, h = max(float(width), 1.0), max(float(height), 1.0)
    size = max((max(xs) - min(xs)) / w, (max(ys) - min(ys)) / h)
    inside = 0.0 <= center[0] <= w and 0.0 <= center[1] <= h
    if inside and size <= ZOOM_LIMITE:
        return "pieza", (center[0], center[1])
    x0, x1 = max(min(xs), 0.0), min(max(xs), w)
    y0, y1 = max(min(ys), 0.0), min(max(ys), h)
    if x0 > x1 or y0 > y1:  # la pieza no se ve: como SW con la pieza entera
        return "pieza", (center[0], center[1])
    return "pantalla", ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def q_mul(a, b):
    """Producto de cuaterniones (x, y, z, w): primero b, después a."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def q_rotate(q, v):
    """Vector v girado por el cuaternión q."""
    x, y, z, w = q
    p = q_mul(q_mul(q, (v[0], v[1], v[2], 0.0)), (-x, -y, -z, w))
    return (p[0], p[1], p[2])


def q_axis_angle(axis, angle):
    n = math.sqrt(sum(a * a for a in axis)) or 1.0
    s = math.sin(angle / 2.0) / n
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2.0))


def orbit_step(q, pos, pivot, dx, dy, width, height):
    """Cámara (orientación q, posición pos) después de mover el mouse dx, dy px (y hacia abajo).

    Gira alrededor de pivot: a la derecha, alrededor del eje vertical de la pantalla; hacia
    abajo, alrededor del horizontal (mismo sentido que FreeCAD). Devuelve (q, pos) nuevos.
    """
    h, v = sw_angles(dx, dy, width, height)
    angle = math.hypot(h, v)
    if angle < 1e-12:
        return tuple(q), tuple(pos)
    local = q_axis_angle((-v, -h, 0.0), angle)  # en ejes de la cámara
    q2 = q_mul(q, local)
    n = math.sqrt(sum(c * c for c in q2))
    q2 = tuple(c / n for c in q2)
    world = q_mul(q2, (-q[0], -q[1], -q[2], q[3]))  # giro en ejes del mundo
    rel = q_rotate(world, (pos[0] - pivot[0], pos[1] - pivot[1], pos[2] - pivot[2]))
    return q2, (pivot[0] + rel[0], pivot[1] + rel[1], pivot[2] + rel[2])


# --- Vista 3D de FreeCAD ---------------------------------------------------


def _wanted():
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return False
        style = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View").GetString("NavigationStyle", "")
        return style in NAV_STYLES
    except Exception:
        return False


def _xy(event):
    p = event.position() if hasattr(event, "position") else event.localPos()  # Qt6 / Qt5
    return p.x(), p.y()


def _view_of(widget):
    """La vista 3D de FreeCAD (Python) cuyo área de dibujo es widget."""
    for name in FreeCAD.listDocuments():
        gdoc = FreeCADGui.getDocument(name)
        for view in gdoc.mdiViewsOfType(VIEW_CLASS) if gdoc else []:
            try:
                if view.graphicsView().viewport() == widget:
                    return view
            except Exception:
                continue
    return None


class _Camera:
    """Cámara de una vista: leer y escribir orientación y posición, proyectar, elegir el centro."""

    def __init__(self, view, widget):
        self.view = view
        self.cam = view.getCameraNode()
        self.w, self.h = widget.width(), widget.height()

    def get(self):
        return tuple(self.cam.orientation.getValue().getValue()), tuple(self.cam.position.getValue().getValue())

    def set(self, q, pos):
        from pivy import coin
        self.cam.orientation.setValue(coin.SbRotation(*q))
        self.cam.position.setValue(coin.SbVec3f(*pos))

    def mm_per_px(self):
        if hasattr(self.cam, "height"):  # ortográfica
            return self.cam.height.getValue() / max(self.h, 1)
        angle = getattr(self.cam, "heightAngle", None)  # perspectiva
        dist = self.cam.focalDistance.getValue()
        return 2.0 * dist * math.tan(angle.getValue() / 2.0) / max(self.h, 1) if angle else 0.0

    def to_px(self, p):
        """Punto del mundo -> píxeles de la vista (x a la derecha, y hacia arriba)."""
        s = self.view.getSize()
        x, y = self.view.getPointOnViewport(FreeCAD.Vector(*p))[:2]
        return x * self.w / max(s[0], 1), y * self.h / max(s[1], 1)

    def scene_box(self):
        """Caja de lo que se dibuja (objetos visibles), o None si no hay nada."""
        from pivy import coin
        action = coin.SoGetBoundingBoxAction(coin.SbViewportRegion(max(self.w, 1), max(self.h, 1)))
        action.apply(self.view.getSceneGraph())
        box = action.getBoundingBox()
        if box.isEmpty():
            return None
        return tuple(box.getMin().getValue()), tuple(box.getMax().getValue())

    def surface_at_center(self):
        s = self.view.getSize()
        info = self.view.getObjectInfo((int(s[0] / 2), int(s[1] / 2)))
        if info and all(k in info for k in ("x", "y", "z")):
            return info["x"], info["y"], info["z"]
        return None

    def pivot(self):
        """Centro de giro como SW (ver pivot_rule)."""
        box = self.scene_box()
        q, pos = self.get()
        if box is None:
            return _focal_point(q, pos, self.cam.focalDistance.getValue())
        lo, hi = box
        center = tuple((a + b) / 2.0 for a, b in zip(lo, hi))
        corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        kind, target = pivot_rule([self.to_px(c) for c in corners], self.to_px(center), self.w, self.h)
        if kind == "pieza":
            return center
        into = q_rotate(q, (0.0, 0.0, -1.0))  # hacia adentro de la pantalla
        hit = self.surface_at_center()
        if hit is not None:
            behind = sum((c - s) * d for c, s, d in zip(center, hit, into))  # hasta el centro de la caja
            depth = min(PROF_PX * self.mm_per_px(), max(behind, 0.0))
            return tuple(s + d * depth for s, d in zip(hit, into))
        # nada en el centro de la pantalla: el medio de lo que se ve, a la profundidad del centro
        cx, cy = self.to_px(center)
        k = self.mm_per_px()
        right, up = q_rotate(q, (1.0, 0.0, 0.0)), q_rotate(q, (0.0, 1.0, 0.0))
        return tuple(c + r * (target[0] - cx) * k + u * (target[1] - cy) * k
                     for c, r, u in zip(center, right, up))


def _focal_point(q, pos, dist):
    into = q_rotate(q, (0.0, 0.0, -1.0))
    return tuple(p + d * dist for p, d in zip(pos, into))


class _OrbitFilter(QtCore.QObject):
    """Filtro de eventos en el área de dibujo de cada vista 3D."""

    def __init__(self):
        super().__init__()
        self.start = None  # modo factor: punto donde se apretó
        self.drag = None   # modo SW: datos del arrastre en curso
        self.busy = False

    def eventFilter(self, obj, event):
        if self.busy:
            return False
        try:
            t = event.type()
            press = t in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonDblClick)
            if self.drag is not None:
                if not press:
                    return self._sw_event(obj, event)
                self._sw_end()  # otro botón, o un arrastre que perdió su "soltar": empieza de nuevo
            if press:  # el doble clic de Qt también es un apretar
                middle = event.button() == QtCore.Qt.MouseButton.MiddleButton
                only = event.buttons() == QtCore.Qt.MouseButton.MiddleButton
                plain = event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier
                ok = middle and only and plain and _wanted()
                self.start = None
                if ok and like_sw():
                    return self._sw_begin(obj, event)
                self.start = _xy(event) if ok else None
                return False
            if t == QtCore.QEvent.Type.MouseButtonRelease:
                self.start = None
                return False
            if t != QtCore.QEvent.Type.MouseMove or self.start is None:
                return False
            k = factor()
            if k == 1.0 or not (event.buttons() & QtCore.Qt.MouseButton.MiddleButton):
                return False
            x, y = scaled(self.start, _xy(event), k)
            point = QtCore.QPointF(x, y)
            moved = QtGui.QMouseEvent(event.type(), point, QtCore.QPointF(obj.mapToGlobal(point)),
                                      event.button(), event.buttons(), event.modifiers())
            self._send(obj, moved)
            return True  # el movimiento original no llega a FreeCAD
        except Exception:
            self.start = None
            self._sw_end()
            return False

    def _send(self, obj, event):
        self.busy = True
        try:
            QtWidgets.QApplication.sendEvent(obj, event)
        finally:
            self.busy = False

    # --- modo SW ---

    def _sw_begin(self, obj, event):
        view = _view_of(obj)
        if view is None:
            return False  # que gire FreeCAD
        try:
            view.stopAnimating()  # una animación de FreeCAD en curso pisaría el giro
        except Exception:
            pass
        cam = _Camera(view, obj)
        pivot = cam.pivot()
        # el cursor que había (p. ej. el de una herramienta del croquis) vuelve al terminar
        old = obj.cursor() if obj.testAttribute(QtCore.Qt.WidgetAttribute.WA_SetCursor) else None
        self.drag = {"cam": cam, "pivot": pivot, "first": _xy(event), "last": _xy(event), "moved": False,
                     "widget": obj, "cursor": old}
        obj.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        return True

    def _sw_end(self):
        d, self.drag = self.drag, None
        if d is None:
            return
        try:
            if d["cursor"] is None:
                d["widget"].unsetCursor()
            else:
                d["widget"].setCursor(d["cursor"])
        except Exception:
            pass  # la vista ya no existe

    def _sw_event(self, obj, event):
        d = self.drag
        t = event.type()
        if obj is not d["widget"] and obj != d["widget"]:
            return False  # eventos de otra vista: no son de este giro
        if t == QtCore.QEvent.Type.MouseMove:
            if not (event.buttons() & QtCore.Qt.MouseButton.MiddleButton):
                self._sw_end()  # se soltó afuera sin que llegara el aviso
                return False
            x, y = _xy(event)
            if not d["moved"] and math.hypot(x - d["first"][0], y - d["first"][1]) < MOVER_MIN_PX:
                return True
            d["moved"] = True
            cam = d["cam"]
            q, pos = cam.get()
            q2, pos2 = orbit_step(q, pos, d["pivot"], x - d["last"][0], y - d["last"][1], cam.w, cam.h)
            cam.set(q2, pos2)
            d["last"] = (x, y)
            return True
        if t == QtCore.QEvent.Type.MouseButtonRelease and event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self._sw_end()  # un clic suelto no hace nada, como en SW (FreeCAD centraba la vista)
            return True
        return False


def install():
    """Comando del menú y filtro en las vistas 3D (las abiertas y las que se abran)."""
    global _filter
    try:
        FreeCADGui.addCommand(COMMAND, _OrbitSpeedCommand())
    except Exception:
        pass  # ya registrado
    if _filter is not None:
        return
    _filter = _OrbitFilter()
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        mdi.subWindowActivated.connect(lambda *_a: _attach_all())
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Velocidad de giro: no se encontró el área de ventanas.\n")
    _attach_all()


def _attach_all():
    """Poner el filtro en el área de dibujo de cada vista 3D abierta (una sola vez por vista)."""
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != VIEW_CLASS:
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if not vp.property("swui_orbit"):
                    vp.setProperty("swui_orbit", True)
                    vp.installEventFilter(_filter)
    except Exception:
        pass


def choices():
    """Textos del menú, en orden: "Como SolidWorks" primero."""
    return [SW_TEXT] + [choice_text(v) for v in CHOICES]


def current_choice():
    if like_sw():
        return 0
    return 1 + min(range(len(CHOICES)), key=lambda i: abs(CHOICES[i] - factor()))


def apply_choice(index):
    """Guardar la elección index de choices()."""
    if index == 0:
        set_like_sw(True)
    else:
        set_like_sw(False)
        set_factor(CHOICES[index - 1])


class _OrbitSpeedCommand:
    """Menú FreeWorks -> Velocidad de giro..."""

    def GetResources(self):
        return {
            "MenuText": "Velocidad de giro...",
            "ToolTip": "Cómo gira el modelo al arrastrar con la ruedita del mouse",
        }

    def IsActive(self):
        return True

    def Activated(self):
        items = choices()
        text, ok = QtWidgets.QInputDialog.getItem(
            FreeCADGui.getMainWindow(), "Velocidad de giro",
            "Giro con la ruedita del mouse\n(\"Como SolidWorks\": velocidad, ejes y centro de giro de SW;"
            "\n x1 = como FreeCAD):",
            items, current_choice(), False)
        if ok and text in items:
            apply_choice(items.index(text))
