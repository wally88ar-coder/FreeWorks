# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Aristas y vértices del modelo dentro del croquis, como en SOLIDWORKS.

En SW, con un croquis abierto, al pasar el mouse cerca de una arista o vértice
de la pieza se resalta, y la cota inteligente o la línea se enganchan ahí. En
FreeCAD 1.1.4 el croquis solo ve lo suyo: primero hay que traer la arista con
"Convertir entidades" (Sketcher_Projection). Acá:

- Con una herramienta del croquis activa (cota, relación, línea, círculo...;
  FreeCAD les pone un cursor dibujado: BitmapCursor) o sin herramienta
  (flecha: seleccionando, p. ej. un punto del croquis + una arista del sólido
  para hacerlos coincidentes), al pasar el mouse a menos de SNAP_PX píxeles de
  una arista o vértice del sólido, se resalta en naranja (primero vértices,
  como SW). Arrastrando con un botón apretado no se resalta nada.
- Al hacer clic con algo resaltado: si el croquis no la tiene, se agrega como
  referencia (lo mismo que Convertir entidades: nada propio del addon queda en
  el archivo) y el clic se manda justo sobre ella, así la herramienta la toma
  aunque no se haya apuntado exacto.
- Si hay algo del propio croquis a menos del radio de selección de FreeCAD
  (View/PickRadius, 5 px), manda el croquis (no se resalta nada). Se mide en
  pantalla: la preselección de FreeCAD sin herramienta no siempre está al día.
  Los ejes del croquis no cuentan: una arista del sólido encima de un eje se
  resalta igual (y una vez traída, FreeCAD también la prefiere al eje).
- Candidatas: las aristas de las operaciones visibles del cuerpo del croquis
  y del objeto donde está apoyado. No se traen las de operaciones que dependen
  del croquis (sería una dependencia circular). Entre aristas superpuestas en
  la pantalla gana la que está sobre el plano del croquis.

Las posiciones en pantalla se calculan una vez por posición de cámara.
FreeCAD 26.3 ya permite acotar directo a las aristas del modelo: desde esa
versión esto no se instala (queda lo nativo).
"""

import math
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets
from swui.fork import safe_ops  # noqa: E402  (#60: cerrar pasos con end_step)

VIEW_CLASS = "Gui::View3DInventor"
WB_NAME = "LikeSolidWorksUIWorkbench"
SKETCH = "Sketcher::SketchObject"
NATIVE_FROM = 26
SNAP_PX = 10  # distancia de enganche en píxeles
MAX_HIDDEN_TRIES = 6  # #102: candidatas tapadas que se saltean por movimiento del mouse (después, como antes)
POINTS_PER_EDGE = 16
HIGHLIGHT = (1.0, 0.55, 0.0)  # naranja (resaltado de look_sw)
LINE_WIDTH = 4

_filter = None
_state = {"sketch": None, "cands": None, "camera": None, "screen": None, "hot": None, "node": None}


def native():
    try:
        return int(FreeCAD.Version()[0]) >= NATIVE_FROM
    except Exception:
        return False


# --- Cuentas (sin FreeCAD, probables en el test) ---------------------


def coin_point(x, y, height, ratio=1.0):
    """Punto del mouse (Qt: y hacia abajo) -> punto de la vista 3D (Coin: y hacia arriba, en píxeles reales)."""
    return (int(round(x * ratio)), int(round((height - y) * ratio)))


def qt_point(cx, cy, height, ratio=1.0):
    """Al revés que coin_point."""
    return (cx / ratio, height - cy / ratio)


def closest_on_segment(p, a, b):
    """(distancia, punto) más cercano a p sobre el segmento a-b (2D)."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
    q = (ax + t * dx, ay + t * dy)
    return math.hypot(p[0] - q[0], p[1] - q[1]), q


def closest_on_polyline(p, pts):
    best = None
    for a, b in zip(pts, pts[1:]):
        found = closest_on_segment(p, a, b)
        if best is None or found[0] < best[0]:
            best = found
    return best


def choose(p, vertices, edges, snap=SNAP_PX):
    """
    Lo que se engancha cerca de p (pantalla). vertices = [(clave, (x, y), lejanía_al_plano)],
    edges = [(clave, [(x, y)...], lejanía_al_plano)]. Primero vértices; entre empatados
    (1 px) gana el más cercano al plano del croquis. Devuelve (clave, punto en pantalla) o None.
    """
    for group in ("v", "e"):
        found = []
        if group == "v":
            for key, q, depth in vertices:
                d = math.hypot(p[0] - q[0], p[1] - q[1])
                if d <= snap:
                    found.append((d, depth, key, q))
        else:
            for key, pts, depth in edges:
                hit = closest_on_polyline(p, pts) if len(pts) > 1 else None
                if hit is not None and hit[0] <= snap:
                    found.append((hit[0], depth, key, hit[1]))
        if found:
            best = min(d for d, *_r in found)
            near = [f for f in found if f[0] <= best + 1.0]
            _d, _depth, key, q = min(near, key=lambda f: (f[1], f[0]))
            return key, q
    return None


def already(sketch, obj, sub):
    """¿El croquis ya tiene esa referencia?"""
    for target, subs in getattr(sketch, "ExternalGeometry", []) or []:
        if getattr(target, "Name", target) == obj and sub in subs:
            return True
    return False


def external_index(sketch, obj, sub):
    """Número de la referencia en el croquis (ExternalEdgeN, desde 1), o None."""
    n = 0
    for target, subs in getattr(sketch, "ExternalGeometry", []) or []:
        for s in subs:
            n += 1
            if getattr(target, "Name", target) == obj and s == sub:
                return n
    return None


def depends_on(obj, sketch):
    """¿obj depende del croquis? (traerlo armaría una dependencia circular)"""
    try:
        return sketch in obj.OutListRecursive
    except Exception:
        return True


# --- Candidatas y pantalla --------------------------------------------


def _editing_sketch():
    try:
        vp = FreeCADGui.ActiveDocument.getInEdit()
        obj = vp.Object if vp is not None else None
    except Exception:
        return None
    return obj if obj is not None and getattr(obj, "TypeId", "") == SKETCH else None


OUTSIDE = "<otro>"  # prefijo de las candidatas de OTRO componente (editando la pieza en un ensamblaje)


class _Outside:
    """Candidata de otro componente: se nombra como el componente, con el prefijo OUTSIDE."""

    def __init__(self, link):
        self.link = link
        self.Name = OUTSIDE + link.Name


def _context(sketch):
    """Contexto de Editar pieza del croquis (la pieza editada dentro de un ensamblaje), o None."""
    try:
        from swui.fork import edit_context as ec

        return ec.for_document(sketch.Document)
    except Exception:
        return None


def _global_shape(obj, ctx=None):
    """
    Forma del objeto en coordenadas de la vista (mismo orden de aristas/vértices): las del documento, o las del
    ensamblaje si la pieza se edita dentro de uno. (Antes se usaba obj.getParents(), que FreeCAD 1.1.4 no tiene:
    editando una pieza movida, las aristas quedaban corridas.)
    """
    import Part

    if ctx is not None:
        from swui.fork import edit_context as ec

        return ec.global_shape(obj, ctx)
    return Part.getShape(obj)


def _sketch_placement(sketch, ctx=None):
    """Ubicación del croquis en la vista (en el ensamblaje, si la pieza se edita dentro de uno)."""
    plc = sketch.getGlobalPlacement()
    if ctx is None:
        return plc
    from swui.fork import edit_context as ec

    return ec.part_placement(ctx).multiply(plc)


def _candidates(sketch):
    """[(objeto, forma global)] cuyas aristas se pueden enganchar."""
    from swui.fork import feature_tree as ft

    objs = []
    body = ft.body_of(sketch)
    if body is not None:
        for f in ft.features(body):
            try:
                if f.ViewObject.Visibility and not depends_on(f, sketch):
                    objs.append(f)
            except Exception:
                pass
    try:
        for target, _subs in sketch.AttachmentSupport:
            if hasattr(target, "Shape") and target not in objs and not depends_on(target, sketch):
                objs.append(target)
    except Exception:
        pass
    ctx = _context(sketch)
    out = []
    for obj in objs:
        try:
            shape = _global_shape(obj, ctx)
            if shape is not None and not shape.isNull() and shape.Edges:
                out.append((obj, shape))
        except Exception:
            pass
    from swui.fork import feature_tree as ft

    if ctx is not None and ft.body_of(sketch) is not None:
        # top-down (18/11): las aristas y vértices de los otros componentes también (como referencia externa; solo
        # con el croquis en un Cuerpo, que es donde va la copia)
        from swui.fork import edit_context as ec

        for link, shape in ec.other_components(ctx):
            out.append((_Outside(link), shape))
    return out


def _camera_key(view):
    try:
        cam = view.getCameraNode()
        size = tuple(view.getSize())
        fields = [cam.position.getValue().getValue(), cam.orientation.getValue().getValue()]
        for name in ("height", "heightAngle"):
            if hasattr(cam, name):
                fields.append(getattr(cam, name).getValue())
        return (str(fields), size)
    except Exception:
        return None


def _screen(view, sketch, cands):
    """Vértices y aristas en pantalla (Coin), con su lejanía al plano del croquis."""
    plc = _sketch_placement(sketch, _context(sketch))
    normal = plc.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
    origin = plc.Base

    def depth(pt):
        return abs((pt - origin).dot(normal))

    vertices, edges = [], []
    for obj, shape in cands:
        for i, v in enumerate(shape.Vertexes):
            vertices.append(((obj.Name, "Vertex%d" % (i + 1)), tuple(view.getPointOnViewport(v.Point)),
                             depth(v.Point)))
        for i, e in enumerate(shape.Edges):
            try:
                pts = e.discretize(Number=POINTS_PER_EDGE)
            except Exception:
                continue
            screen = [tuple(view.getPointOnViewport(pt)) for pt in pts]
            edges.append(((obj.Name, "Edge%d" % (i + 1)), screen, max(depth(pt) for pt in pts), pts))
    return vertices, edges


def _find(view, sketch, coin, ratio=1.0):
    """(objeto, sub, punto Coin) enganchable cerca de coin, o None."""
    st = _state
    if st["sketch"] is not sketch:
        st.update(sketch=sketch, cands=_candidates(sketch), camera=None, elements={})
    key = _camera_key(view)
    if key is None or key != st["camera"]:
        st["screen"] = _screen(view, sketch, st["cands"])
        st["camera"] = key
    vertices, edges = st["screen"]
    snap = SNAP_PX * ratio
    # #102: las candidatas cerca del mouse se juntan una vez (pocas) y se prueban en el orden de choose; la
    # primera que no está tapada por el sólido es la que se engancha (como SW)
    verts = [v for v in vertices if math.hypot(coin[0] - v[1][0], coin[1] - v[1][1]) <= snap]
    lines = []
    for k, s, d, _pts in edges:
        hit = closest_on_polyline(coin, s) if len(s) > 1 else None
        if hit is not None and hit[0] <= snap:
            lines.append((k, s, d))
    for tries in range(MAX_HIDDEN_TRIES + 1):
        found = choose(coin, verts, lines, snap)
        if found is None:
            return None
        key, q = found
        if tries == MAX_HIDDEN_TRIES or not _hidden(view, q, _element(key)):
            obj, sub = key  # (al llegar al tope, como antes: la que elige choose)
            return obj, sub, q
        verts = [v for v in verts if v[0] != key]
        lines = [e for e in lines if e[0] != key]
    return None


def _element(key):
    """La arista o el vértice (forma global) de la candidata key = (nombre, "EdgeN"/"VertexN"), o None."""
    cache = _state.setdefault("elements", {})
    if key in cache:
        return cache[key]
    elem = None
    for obj, shape in _state.get("cands") or []:
        if obj.Name == key[0]:
            try:
                n = int(key[1][4:] if key[1].startswith("Edge") else key[1][6:])
                elem = (shape.Edges if key[1].startswith("Edge") else shape.Vertexes)[n - 1]
            except Exception:
                elem = None
            break
    cache[key] = elem
    return elem


def _see_through(info, obj=None):
    """¿Lo que tocó el rayo se ve a través? Componentes transparentes (los de Editar pieza: SW elige a través de
    ellos) y objetos o Cuerpos transparentes (30 % o más). obj: el objeto tocado (también si no vino ParentObject)."""
    objs = [obj] if obj is not None else []
    parent = info.get("ParentObject")
    if parent is not None:
        objs.append(parent)
        doc = parent.Document
        for name in (info.get("SubName") or "").split(".")[:-1]:
            obj = doc.getObject(name) if name and doc is not None else None
            if obj is None:
                break
            objs.append(obj)
            linked = getattr(obj, "LinkedObject", None)
            doc = linked.Document if linked is not None and linked is not obj else obj.Document
    for obj in objs:
        vo = getattr(obj, "ViewObject", None)
        if vo is None:
            continue
        try:
            if getattr(vo, "OverrideMaterial", False) and vo.ShapeMaterial.Transparency >= 0.3:
                return True
        except Exception:
            pass
        if getattr(vo, "Transparency", 0) >= 30:
            return True
    return False


def _hidden(view, q, elem):
    """
    #102: ¿la arista o vértice elem (forma global), que en pantalla cae en q (Coin), está tapado por el sólido? Se
    miran los toques del rayo de ese píxel (getObjectsInfo de FreeCAD, de adelante hacia atrás). Tapa solo una CARA de
    un objeto con sólido que no se ve a través (no los planos, ejes ni croquis, ni los componentes transparentes de
    Editar pieza) y que está más cerca de la cámara que el punto de elem más cercano al rayo (el de la curva, no el
    de su cuerda), en más de 1,5 píxeles. Las caras pegadas a la propia arista (a menos de 3 píxeles: sus vecinas,
    aunque se vean de canto) no tapan. En SW las aristas tapadas no se enganchan. Ante cualquier duda (la vista no
    responde), no se considera tapado: queda como antes.
    """
    if elem is None:
        return False
    try:
        import Part

        x, y = int(round(q[0])), int(round(q[1]))
        hits = view.getObjectsInfo((x, y), 2.0) or []
        direction = view.getViewDirection()  # de la cámara hacia la escena
        direction = FreeCAD.Vector(direction[0], direction[1], direction[2])
        if not hits or direction.Length == 0:
            return False
        direction.normalize()
        # el punto de elem más cercano al rayo del píxel
        base = view.getPoint((x, y))
        size = max(elem.BoundBox.DiagonalLength, 1.0) * 10 + (base - elem.BoundBox.Center).Length * 2
        ray = Part.LineSegment(base - direction * size, base + direction * size).toShape()
        point = elem.distToShape(ray)[1][0][0]
        # milímetros por píxel a esa profundidad (proyectando 100 mm: getPointOnViewport da píxeles enteros)
        up = view.getCameraOrientation().multVec(FreeCAD.Vector(0, 1, 0))
        a, b = view.getPointOnViewport(point), view.getPointOnViewport(point + up * 100)
        per_px = 100.0 / max(math.hypot(b[0] - a[0], b[1] - a[1]), 1e-6)
        tol, near = max(1.5 * per_px, 1e-3), max(3 * per_px, 1e-3)
        for info in hits:
            if "x" not in info or not str(info.get("Component", "")).startswith("Face"):
                continue  # aristas y vértices no tapan
            doc = FreeCAD.listDocuments().get(info.get("Document", ""))
            obj = doc.getObject(info.get("Object", "")) if doc is not None else None
            shape = Part.getShape(obj) if obj is not None else None
            if shape is None or shape.isNull() or not shape.Solids or _see_through(info, obj):
                continue
            hit = FreeCAD.Vector(info["x"], info["y"], info["z"])
            if elem.distToShape(Part.Vertex(hit))[0] <= near:
                return False  # una cara pegada a la propia arista: se ve
            return (point - hit).dot(direction) > tol
        return False
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Arista tapada:\n%s\n" % traceback.format_exc())
        return False


# --- Resaltado (Coin) ---------------------------------------------------


def _show(view, obj, sub):
    """Resaltar la arista/vértice en naranja, encima de todo."""
    from pivy import coin

    _hide(view)
    shape = None
    for o, s in _state["cands"] or []:
        if o.Name == obj:
            shape = s
    if shape is None:
        return
    sep = coin.SoAnnotation()
    color = coin.SoBaseColor()
    color.rgb = HIGHLIGHT
    style = coin.SoDrawStyle()
    style.lineWidth = LINE_WIDTH
    style.pointSize = 9
    coords = coin.SoCoordinate3()
    if sub.startswith("Vertex"):
        p = shape.Vertexes[int(sub[6:]) - 1].Point
        coords.point.setValues(0, 1, [(p.x, p.y, p.z)])
        mark = coin.SoMarkerSet()
        mark.markerIndex = coin.SoMarkerSet.CIRCLE_FILLED_9_9
    else:
        pts = shape.Edges[int(sub[4:]) - 1].discretize(Number=48)
        coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
        mark = coin.SoLineSet()
    for node in (color, style, coords, mark):
        sep.addChild(node)
    view.getSceneGraph().addChild(sep)
    _state["node"] = sep


def _hide(view=None):
    node = _state.get("node")
    if node is None:
        return
    try:
        (view or FreeCADGui.ActiveDocument.ActiveView).getSceneGraph().removeChild(node)
    except Exception:
        pass
    _state["node"] = None


def bring(sketch, obj_name, sub):
    """
    Agregar la referencia (como Convertir entidades). Devuelve (objeto, elemento) de la referencia como la tiene
    el croquis (para elegirla), o None si no se pudo. Lo de otro componente (OUTSIDE) entra por una referencia
    externa (edit_context.outside_element_in_sketch).
    """
    if obj_name.startswith(OUTSIDE):
        from swui.fork import edit_context as ec

        found = ec.outside_element_in_sketch(sketch, obj_name[len(OUTSIDE):] + "." + sub)
        _state["sketch"] = None  # el croquis cambió: recalcular candidatas
        return found
    doc = sketch.Document
    obj = doc.getObject(obj_name)
    if obj is not None and already(sketch, obj_name, sub):
        return obj_name, sub
    if obj is None or depends_on(obj, sketch):
        return None
    doc.openTransaction("Referencia del modelo")
    try:
        sketch.addExternal(obj_name, sub)
        sketch.recompute()
    except Exception:
        safe_ops.end_step(doc, abort=True)
        FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())
        return None
    safe_ops.end_step(doc)
    _state["sketch"] = None  # el croquis cambió: recalcular candidatas
    return obj_name, sub


# --- Lo de otro componente traído con una herramienta y no usado ---------------------
#
# Revisión del 18/11 (hallazgo 4): con Línea, el clic sobre un vértice de otro componente trae la referencia (copia
# oculta + geometría externa) ANTES de que la herramienta use el clic. Si después se cancela (Esc) sin usarla, no
# tiene que quedar nada: cuando la herramienta termina o se cierra el croquis, lo traído que ninguna relación usa
# se saca (con Ctrl+Z de su paso si es el último; si no, en un paso propio).

_pending = []  # [(documento, croquis, copia, elemento, UndoCount después de traerla, geometrías en ese momento)]
_pending_timer = [None]
_pending_viewport = [None]  # la vista donde se hizo el clic (editando, la del ensamblaje: la pieza no tiene vista)


def _remember(sketch, brought, viewport):
    doc = sketch.Document
    _pending_viewport[0] = viewport
    _pending.append((doc.Name, sketch.Name, brought[0], brought[1], doc.UndoCount, sketch.GeometryCount))
    timer = _pending_timer[0]
    if timer is None:
        timer = QtCore.QTimer()
        timer.setInterval(400)
        timer.timeout.connect(_check_pending)
        _pending_timer[0] = timer
    timer.start()


def _tool_active():
    try:
        vp = _pending_viewport[0]
        return vp is not None and vp.cursor().shape() == QtCore.Qt.CursorShape.BitmapCursor
    except Exception:
        return False


def _used(sketch, binder, element):
    index = external_index(sketch, binder, element)
    if index is None:
        return None  # ya no está (deshecho o borrado)
    geo = -2 - index  # la primera externa es -3
    for c in sketch.Constraints:
        if geo in (c.First, c.Second, c.Third):
            return True
    return False


def _check_pending():
    try:
        if not _pending:
            if _pending_timer[0] is not None:
                _pending_timer[0].stop()
            return
        editing = _editing_sketch()
        for item in list(_pending):
            doc_name, sketch_name, binder, element, undo_count, geo_count = item
            try:
                doc = FreeCAD.getDocument(doc_name)
                sketch = doc.getObject(sketch_name)
            except Exception:
                sketch = None
            if sketch is None:
                _pending.remove(item)
                continue
            if editing is sketch and _tool_active():
                continue  # la herramienta sigue: todavía la puede usar
            _pending.remove(item)
            used = _used(sketch, binder, element)
            if used is None or used:
                continue
            # #107 (18/11): si la herramienta dibujó algo después de traerla (la línea que empezó ahí, aunque no quedó
            # pegada por una relación), deshacer el paso se llevaba también la línea: se saca solo la referencia, en
            # un paso propio (abajo)
            if (sketch.GeometryCount == geo_count and doc.UndoCount == undo_count and doc.UndoNames
                    and doc.UndoNames[0] == OUTSIDE_STEP):
                doc.undo()  # nada después: como si no se hubiera traído
                continue
            own = safe_ops.begin_step(doc, "Quitar referencia sin usar")
            try:
                index = external_index(sketch, binder, element)
                sketch.delExternal(index - 1)
                if doc.getObject(binder) is not None and not doc.getObject(binder).InList:
                    doc.removeObject(binder)
                sketch.recompute()
            except Exception:
                if own:
                    safe_ops.end_step(doc, abort=True)
                raise
            if own:
                safe_ops.end_step(doc)
            _state["sketch"] = None
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Referencia de otro componente sin usar:\n%s\n" % traceback.format_exc())


OUTSIDE_STEP = "Referencia de otro componente"  # nombre del paso de deshacer (edit_context)


# --- Filtro de eventos ---------------------------------------------------


def _active(viewport):
    """
    Croquis en edición, con una herramienta activa (cursor dibujado) o seleccionando
    (flecha: para elegir la arista y relacionarla con algo del croquis, como en SW).
    """
    if viewport.cursor().shape() not in (QtCore.Qt.CursorShape.BitmapCursor, QtCore.Qt.CursorShape.ArrowCursor):
        return None
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return None
    except Exception:
        return None
    return _editing_sketch()


def _sketch_near(view, sketch, coin, radius):
    """
    ¿Hay algo del croquis (líneas, puntos, referencias ya traídas; no los ejes) a menos
    de radius del mouse? Se mide en pantalla en vez de mirar la preselección de FreeCAD,
    que sin herramienta no siempre está al día.
    """
    plc = _sketch_placement(sketch, _context(sketch))
    shapes = []
    for geo in list(sketch.Geometry) + list(getattr(sketch, "ExternalGeo", [])[2:]):
        try:
            shapes.append(geo.toShape())
        except Exception:
            pass
    for shape in shapes:
        for v in shape.Vertexes:
            q = view.getPointOnViewport(plc.multVec(v.Point))
            if math.hypot(coin[0] - q[0], coin[1] - q[1]) <= radius:
                return True
        for e in shape.Edges:
            try:
                pts = [tuple(view.getPointOnViewport(plc.multVec(p))) for p in e.discretize(Number=POINTS_PER_EDGE)]
            except Exception:
                continue
            hit = closest_on_polyline(coin, pts)
            if hit is not None and hit[0] <= radius:
                return True
    return False


def _snap_screen(view, sketch, brought, q):
    """
    Punto de pantalla (Coin) donde la herramienta tiene que recibir el clic para engancharse a la referencia recién
    traída: su lugar PROYECTADO en el plano del croquis (ahí la dibuja el croquis). Con el vértice o la arista
    fuera del plano, el punto de pantalla del original cae en otro lugar del plano en una vista inclinada y la línea
    quedaba suelta (18/11). None si no se puede saber (queda el punto de siempre).
    """
    try:
        index = external_index(sketch, *brought)
        if not index:
            return None
        shape = sketch.ExternalGeo[1 + index].toShape()
        plc = _sketch_placement(sketch, _context(sketch))
        if shape.ShapeType == "Vertex" or not shape.Edges:
            return tuple(view.getPointOnViewport(plc.multVec(shape.Vertexes[0].Point)))
        pts = [tuple(view.getPointOnViewport(plc.multVec(p))) for p in shape.Edges[0].discretize(Number=POINTS_PER_EDGE)]
        hit = closest_on_polyline(q, pts)
        return tuple(hit[1]) if hit is not None else None
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())
        return None


def _pick_radius():
    try:
        return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View").GetFloat("PickRadius", 5.0)
    except Exception:
        return 5.0


def _hot_at(viewport, pos):
    """Arista/vértice del modelo enganchable en pos (Qt) del viewport, o None."""
    sketch = _active(viewport)
    if sketch is None:
        _state["sketch"] = None  # al volver al croquis se recalculan las candidatas
        return None
    ratio = viewport.devicePixelRatioF()
    view = FreeCADGui.ActiveDocument.ActiveView
    coin = coin_point(pos.x(), pos.y(), viewport.height(), ratio)
    if _sketch_near(view, sketch, coin, _pick_radius() * ratio):
        return None  # manda el croquis
    return _find(view, sketch, coin, ratio)


def _hover(viewport, pos, dragging):
    """Resaltar (o dejar de resaltar) lo que está cerca del mouse."""
    try:
        hot = None if dragging else _hot_at(viewport, pos)
        old = _state["hot"]
        if (hot and hot[:2]) != (old and old[:2]):
            view = FreeCADGui.ActiveDocument.ActiveView
            if hot is None:
                _hide(view)
            else:
                _show(view, hot[0], hot[1])
        _state["hot"] = hot
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())


def _send(viewport, kind, pos, button, buttons, modifiers):
    ev = QtGui.QMouseEvent(kind, pos, viewport.mapToGlobal(pos), button, buttons, modifiers)
    QtWidgets.QApplication.sendEvent(viewport, ev)


class _Filter(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.busy = False  # mientras se reenvía el clic
        self.swallow_release = False  # el soltar del clic que ya se atendió

    def eventFilter(self, viewport, event):
        if self.busy:
            return False
        t = event.type()
        if t == QtCore.QEvent.Type.MouseButtonRelease and self.swallow_release:
            self.swallow_release = False
            return True
        if t not in (QtCore.QEvent.Type.MouseMove, QtCore.QEvent.Type.MouseButtonPress):
            if t == QtCore.QEvent.Type.Leave:
                _hide()
                _state["hot"] = None
            return False
        try:
            pos = event.position() if hasattr(event, "position") else QtCore.QPointF(event.pos())
            if t == QtCore.QEvent.Type.MouseMove:
                # Después de que el croquis vea el movimiento (su preselección queda al día)
                dragging = event.buttons() != QtCore.Qt.MouseButton.NoButton
                # una vez por tanda, con la última posición (#25)
                safe_ops.later_once("model_edges.hover", _hover, viewport, QtCore.QPointF(pos), dragging)
                return False
            # Clic
            if event.button() != QtCore.Qt.MouseButton.LeftButton:
                return False
            hot = _hot_at(viewport, pos)
            if hot is None:
                return False
            view = FreeCADGui.ActiveDocument.ActiveView
            sketch = _editing_sketch()
            ratio = viewport.devicePixelRatioF()
            obj, sub, q = hot
            before = set(o.Name for o in sketch.Document.Objects)
            brought = bring(sketch, obj, sub)
            new_outside = bool(brought) and obj.startswith(OUTSIDE) and brought[0] not in before
            _hide(view)
            _state["hot"] = None
            if viewport.cursor().shape() == QtCore.Qt.CursorShape.ArrowCursor:
                # Sin herramienta (seleccionando): se suma a la selección, como en SW, para
                # relacionarla con lo ya elegido. El croquis elegiría al soltar el botón lo
                # que tenía bajo el mouse (desactualizado): ese soltar no le llega.
                index = external_index(sketch, *brought) if brought else None
                if index:
                    from swui.fork import edit_context as ec

                    # editando la pieza dentro de un ensamblaje, por el camino del componente (18/11: si no, no
                    # quedaba elegida); en la pieza sola, igual que antes
                    ec.select(sketch, "ExternalEdge%d" % index, clear=False)
                self.swallow_release = True
                return True
            if new_outside:
                _remember(sketch, brought, viewport)  # con herramienta: si no se usa, no queda (hallazgo 4)
            if brought:
                # que la herramienta vea la referencia recién traída al recibir el clic (si no, el croquis todavía
                # no la dibujó y la línea no queda pegada: medido el 18/11)
                try:
                    view.redraw()
                    FreeCADGui.updateGui()
                except Exception:
                    pass
            on_plane = _snap_screen(view, sketch, brought, q) if brought else None
            if on_plane is not None:
                q = on_plane
            x, y = qt_point(q[0], q[1], viewport.height(), ratio)
            snapped = QtCore.QPointF(x, y)
            self.busy = True
            try:
                _send(viewport, QtCore.QEvent.Type.MouseMove, snapped, QtCore.Qt.MouseButton.NoButton,
                      QtCore.Qt.MouseButton.NoButton, event.modifiers())
                _send(viewport, QtCore.QEvent.Type.MouseButtonPress, snapped, event.button(),
                      event.buttons(), event.modifiers())
            finally:
                self.busy = False
            return True  # el clic original no sigue: ya se mandó sobre la arista
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())
            return False


def _attach_all():
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != VIEW_CLASS:
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if not vp.property("swui_model_edges"):
                    vp.setProperty("swui_model_edges", True)
                    vp.installEventFilter(_filter)
    except Exception:
        pass


def install():
    """Filtro en las vistas 3D (las abiertas y las que se abran). Nada desde FreeCAD 26.3."""
    global _filter
    if _filter is not None or native():
        return
    _filter = _Filter()
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        mdi.subWindowActivated.connect(lambda *_a: _attach_all())
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Aristas del modelo: no se encontró el área de ventanas.\n")
    _attach_all()
