# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Mover cara como en SOLIDWORKS (fase 4): Equidistanciar / Trasladar / Girar.

Panel como el PropertyManager de SW (captura del usuario, 2026-10-26): tipo, caras, y en
Parámetros la condición final y la dirección (Trasladar), el eje de giro (Girar), Invertir
dirección, distancia, ΔX ΔY ΔZ o ángulo. Sirve en piezas propias y en sólidos importados
(STEP): a un sólido suelto se le arma un Cuerpo que arranca de él.

Todo nativo (el addon es un asistente, docs/ESTADO.md "Análisis: ..."), verificado en 1.1.4:
- Equidistanciar / Trasladar una cara plana = moverla según su normal: Extruir
  (PartDesign::Pad) con la cara misma como perfil si sale, Cortar (PartDesign::Pocket) si
  entra. De Trasladar cuenta solo la componente normal (correr una cara plana dentro de su
  plano no la cambia). Con caras vecinas inclinadas queda un escalón en vez de prolongarlas
  (límite conocido).
- Condición final de Trasladar, como SW (2026-10-31): Hasta la superficie = Pad/Pocket "Hasta
  cara"; Equidistante de la superficie = lo mismo con Offset; Hasta el vértice = "Hasta cara"
  contra un plano de referencia oculto que pasa por el vértice, paralelo a la cara (OXY sobre
  vértice, arista de la cara y cara: sigue a la pieza); Hasta el sólido = hasta la primera
  cara de ese sólido que encuentra la cara al avanzar (elegida al aplicar; "Hasta forma" de
  FreeCAD no llega a un sólido entero, probado).
- Girar alrededor de una arista recta de la cara = Ángulo de salida (PartDesign::Draft): plano
  neutro = una cara plana que contiene la arista; dirección de tiro = una arista recta (o la
  normal de una cara plana) perpendicular a la arista dentro de la cara. Prolonga bien las
  vecinas, también inclinadas.
- Girar alrededor de otro eje paralelo a la cara (arista de otra cara, eje de referencia...):
  girar la cara alrededor de ese eje es lo mismo que girarla el mismo ángulo alrededor de la
  recta donde la cara girada corta a la original (corrida tan(ángulo/2) por la altura del
  eje). Ángulo de salida con un plano neutro y una línea de tiro ocultos ubicados en esa recta
  (el Draft no acepta un plano como tiro, sí una línea: probado). Quedan fijos: si la pieza
  cambia, avisa (check) y Ctrl+Q los reubica (update_stale), como editar el Mover cara.
- Equidistanciar una cara cilíndrica entera (agujero o eje, 2026-10-31) = Ranura
  (PartDesign::Groove) si quita material o Revolución si agrega, de un anillo (croquis oculto
  en un plano que contiene el eje) entre el radio de la cara y el nuevo, a lo largo de la cara.
  Agujero de Ø10 a Ø14: saca exactamente π·(7²-5²)·largo (probado). El croquis queda fijo: si
  después cambia el agujero, avisa y Ctrl+Q lo reubica (lo mismo que editar el Mover cara).
Si cambia el sentido (agregar <-> quitar material) o el tipo, la operación se cambia por la
otra (mientras nada más use sus caras). La distancia o el ángulo se pueden atar a ecuaciones.
Los objetos auxiliares (planos, líneas, croquis) se nombran en "aux" de la marca.

Marca: propiedad oculta SWUI_MoveFace (texto JSON con lo elegido en el panel). Nombre estable
para siempre (docs/ESTADO.md, Decisiones): sin el addon el archivo abre y recalcula igual (es
un Pad / Pocket / Draft / Groove / Revolution común); con el addon, editar abre este panel.
"""

import json
import math
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.fork import dress_up_panel as dp

COMMAND = "SWUI_MoveFace"
MARK = "SWUI_MoveFace"
LABEL = "Mover cara"
PAD, POCKET, DRAFT = "PartDesign::Pad", "PartDesign::Pocket", "PartDesign::Draft"
GROOVE, REVOLUTION = "PartDesign::Groove", "PartDesign::Revolution"
NATIVE_NAMES = {PAD: "Pad", POCKET: "Pocket", DRAFT: "Draft", GROOVE: "Groove", REVOLUTION: "Revolution"}
OFFSET, TRANSLATE, ROTATE = "offset", "translate", "rotate"
MODES = (("Equidistanciar", OFFSET), ("Trasladar", TRANSLATE), ("Girar", ROTATE))
# Condición final de Trasladar, con los textos de SW 2018 (vistos en el SW del usuario, 2026-10-31)
END_DEPTH, END_VERTEX, END_SURFACE, END_OFFSET, END_BODY = "depth", "vertex", "surface", "offset_surface", "body"
ENDS = (("Hasta profundidad especificada", END_DEPTH), ("Hasta el vértice", END_VERTEX),
        ("Hasta la superficie", END_SURFACE), ("Equidistante de la superficie", END_OFFSET),
        ("Hasta el sólido", END_BODY))
TOL = 1e-6


# --- Cuentas sin FreeCAD (probables en el test) -------------------------------


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def normal_move(mode, normal, distance=0.0, flip=False, direction=None, delta=(0.0, 0.0, 0.0)):
    """
    Cuánto se corre la cara según su normal (positivo = hacia afuera, agrega material).
    Equidistanciar: la distancia (Invertir = hacia adentro). Trasladar: la componente normal
    de la distancia sobre la dirección elegida, o de ΔX ΔY ΔZ si no hay dirección.
    """
    sign = -1.0 if flip else 1.0
    if mode == OFFSET:
        return sign * distance
    if direction is not None:
        return sign * distance * dot(direction, normal)
    return dot(delta, normal)


def native_type(mode, move, curved=False):
    """Operación nativa que hace el trabajo."""
    if mode == ROTATE:
        return DRAFT
    if curved:
        return REVOLUTION if move > 0 else GROOVE
    return PAD if move > 0 else POCKET


def hinge_shift(height, angle):
    """
    Cara girada `angle` grados alrededor de un eje paralelo a ella, a `height` de su plano
    (positivo = del lado de la normal): dónde corta la cara girada al plano de la cara, medido
    desde el pie del eje sobre u×n (u = sentido del eje, giro positivo a la derecha de u).
    """
    return -height * math.tan(math.radians(angle) / 2.0)


def ring_radii(radius, move, away):
    """
    Cara cilíndrica corrida `move` según su normal (positivo = agrega material). away: la normal
    se aleja del eje (eje macizo) o va hacia él (agujero). -> (radio menor, radio mayor) del
    anillo que se agrega o se saca, o None si el radio nuevo no da.
    """
    new = radius + (move if away else -move)
    if new <= TOL:
        return None
    return min(radius, new), max(radius, new)


def next_label(used):
    n = 1
    while "%s%d" % (LABEL, n) in used:
        n += 1
    return "%s%d" % (LABEL, n)


MODE_PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI/MoveFace"


def last_mode():
    """El último modo usado (SW abre Mover cara en ese); la primera vez, Equidistanciar."""
    try:
        mode = FreeCAD.ParamGet(MODE_PARAMS).GetString("Mode", OFFSET)
    except Exception:
        return OFFSET
    return mode if mode in (OFFSET, TRANSLATE, ROTATE) else OFFSET


def remember_mode(mode):
    try:
        FreeCAD.ParamGet(MODE_PARAMS).SetString("Mode", mode)
    except Exception:
        pass


def read_spec(text):
    """Lo guardado en SWUI_MoveFace (JSON) con valores por omisión."""
    spec = {"mode": OFFSET, "flip": False, "distance": 10.0, "delta": [0.0, 0.0, 0.0],
            "dir": None, "hinge": "", "angle": 10.0, "end": END_DEPTH, "target": None, "gap": 10.0,
            "axis": None, "aux": {}, "faces": [], "plc": None}
    try:
        data = json.loads(text or "{}")
        if isinstance(data, dict):
            spec.update({k: v for k, v in data.items() if k in spec})
    except ValueError:
        pass
    if spec["mode"] not in (OFFSET, TRANSLATE, ROTATE):
        spec["mode"] = OFFSET
    if spec["end"] not in [v for _t, v in ENDS]:
        spec["end"] = END_DEPTH
    return spec


# --- Geometría ------------------------------------------------------------------


def is_planar(face):
    try:
        if type(face.Surface).__name__ == "Plane":
            return True
        return face.findPlane() is not None  # plano guardado como spline (STEP)
    except Exception:
        return False


def face_normal(face):
    """Normal hacia afuera del sólido (respeta la orientación de la cara)."""
    u0, u1, v0, v1 = face.ParameterRange
    n = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    return n.normalize()


def _is_line(edge):
    return type(getattr(edge, "Curve", None)).__name__ in ("Line", "LineSegment")


def _edge_dir(edge):
    d = edge.Vertexes[-1].Point - edge.Vertexes[0].Point
    return d.normalize() if d.Length > TOL else None


def _on_plane(point, origin, normal):
    return abs((point - origin).dot(normal)) < 1e-4


def is_full_cylinder(face):
    """Cara cilíndrica entera (agujero o eje de 360°)."""
    try:
        if type(face.Surface).__name__ != "Cylinder":
            return False
        u0, u1 = face.ParameterRange[:2]
        return abs(abs(u1 - u0) - 2 * math.pi) < 1e-6
    except Exception:
        return False


def cylinder_data(face):
    """(centro del anillo en el eje, sentido del eje, radio, largo, la normal se aleja del eje)."""
    surf = face.Surface
    axis = FreeCAD.Vector(surf.Axis).normalize()
    center = FreeCAD.Vector(surf.Center)
    s = [(v.Point - center).dot(axis) for v in face.Vertexes]
    if not s:  # sin vértices (cilindro de costura): los extremos por la caja
        s = [(p - center).dot(axis) for p in (face.BoundBox.getPoint(i) for i in range(8))]
    s0, s1 = min(s), max(s)
    u0, u1, v0, v1 = face.ParameterRange
    point = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    radial = point - (center + axis * (point - center).dot(axis))
    away = face_normal(face).dot(radial) > 0
    return center + axis * s0, axis, surf.Radius, s1 - s0, away


def faces_problem(shape, subs, same_plane=False, curved_ok=False):
    """
    Las caras elegidas sirven? (planas, mirando para el mismo lado; con curved_ok también UNA
    cara cilíndrica entera). "" si sí.
    """
    first = None
    for sub in subs:
        face = dp._element(shape, sub)
        if face is None:
            return "Hay caras que ya no existen (en rojo): borralas y elegí las nuevas."
        if not is_planar(face):
            if not curved_ok:
                return ("Solo se pueden trasladar o girar caras planas (las cilíndricas, con "
                        "Equidistanciar).")
            if not is_full_cylinder(face):
                return "De las caras curvas, por ahora solo cilíndricas enteras (agujeros y ejes)."
            if len(subs) > 1:
                return "Una cara cilíndrica va sola (para otra, otro Mover cara)."
            return ""
        n = face_normal(face)
        if first is None:
            first = (face, n)
            continue
        if n.dot(first[1]) < 1 - 1e-6:
            return "Las caras tienen que mirar para el mismo lado (para otras, otro Mover cara)."
        if same_plane and not _on_plane(face.Vertexes[0].Point, first[0].Vertexes[0].Point, first[1]):
            return "Para girar, las caras tienen que estar en el mismo plano."
    return ""


def hinge_refs(shape, subs, hinge):
    """
    Girar alrededor de la arista `hinge` (recta, en el plano de las caras): (plano neutro,
    dirección de tiro, problema). Plano neutro: una cara plana que contiene la arista (mejor la
    vecina). Tiro: una arista recta perpendicular a la arista dentro del plano de la cara, o una
    cara plana con esa normal.
    """
    face = dp._element(shape, subs[0])
    edge = dp._element(shape, hinge)
    if face is None or edge is None or not _is_line(edge):
        return None, None, "Elegí como eje una arista recta de la cara."
    n = face_normal(face)
    h = _edge_dir(edge)
    origin = face.Vertexes[0].Point
    if h is None or abs(h.dot(n)) > 1e-6 or not all(_on_plane(v.Point, origin, n) for v in edge.Vertexes):
        return None, None, "La arista del giro tiene que estar en el plano de la cara."
    chosen = [dp._element(shape, s) for s in subs]
    neutral, best = None, None
    for i, cand in enumerate(shape.Faces):
        if any(c is not None and cand.isSame(c) for c in chosen) or not is_planar(cand):
            continue
        m = face_normal(cand)
        if abs(m.dot(h)) > 1e-6 or abs(m.dot(n)) > 1 - 1e-6:
            continue
        p = cand.Vertexes[0].Point
        if not all(_on_plane(v.Point, p, m) for v in edge.Vertexes):
            continue
        shares = any(e.isSame(edge) for e in cand.Edges)
        if neutral is None or (shares and not best):
            neutral, best = "Face%d" % (i + 1), shares
    if neutral is None:
        return None, None, "No hay una cara plana que pase por esa arista para usar de bisagra."
    pull_dir = n.cross(h).normalize()
    pull = None
    face_edges = [e for c in chosen if c is not None for e in c.Edges]
    for i, cand in enumerate(shape.Edges):
        if not _is_line(cand):
            continue
        d = _edge_dir(cand)
        if d is not None and abs(d.dot(pull_dir)) > 1 - 1e-6:
            own = any(cand.isSame(e) for e in face_edges)
            if pull is None or own:
                pull = "Edge%d" % (i + 1)
                if own:
                    break
    if pull is None:
        for i, cand in enumerate(shape.Faces):
            if is_planar(cand) and abs(face_normal(cand).dot(pull_dir)) > 1 - 1e-6:
                pull = "Face%d" % (i + 1)
                break
    if pull is None:
        return None, None, "No encuentro una arista perpendicular al eje dentro de la cara para girarla."
    return neutral, pull, ""


def direction_of(obj, sub):
    """Dirección de una referencia: arista recta, cara plana, plano o recta de referencia."""
    try:
        if sub:
            el = obj.Shape.getElement(sub)
            if sub.startswith("Edge") and _is_line(el):
                return _edge_dir(el)
            if sub.startswith("Face") and is_planar(el):
                return face_normal(el)
            return None
        rot = obj.Placement.Rotation
        if obj.TypeId in ("App::Plane", "PartDesign::Plane"):
            return rot.multVec(FreeCAD.Vector(0, 0, 1))
        if obj.TypeId == "App::Line":
            return rot.multVec(FreeCAD.Vector(1, 0, 0))
        if obj.TypeId == "PartDesign::Line":
            return rot.multVec(FreeCAD.Vector(0, 0, 1))
    except Exception:
        pass
    return None


def _local(body, placement_or_vec):
    """Global -> coordenadas del Cuerpo (las de obj.Shape de sus operaciones)."""
    inv = body.getGlobalPlacement().inverse() if body is not None else FreeCAD.Placement()
    if isinstance(placement_or_vec, FreeCAD.Vector):
        return inv.multVec(placement_or_vec)
    return inv.multiply(placement_or_vec)


def axis_of(ref, base, body):
    """
    Eje de giro elegido: arista recta (de esta pieza o de otra), eje o recta de referencia.
    -> (punto, sentido) en coordenadas del Cuerpo, o None.
    """
    obj, sub = ref
    try:
        if sub:
            if obj is base:
                edge = base.Shape.getElement(sub)
                if not _is_line(edge):
                    return None
                return edge.Vertexes[0].Point, _edge_dir(edge)
            from swui.fork import sketch_model_edges as sme

            edge = sme._global_shape(obj).getElement(sub)
            if not _is_line(edge):
                return None
            a, b = _local(body, edge.Vertexes[0].Point), _local(body, edge.Vertexes[-1].Point)
            d = b - a
            return (a, d.normalize()) if d.Length > TOL else None
        plc = _local(body, obj.getGlobalPlacement())
        local = FreeCAD.Vector(1, 0, 0) if obj.TypeId == "App::Line" else FreeCAD.Vector(0, 0, 1)
        if obj.TypeId not in ("App::Line", "PartDesign::Line"):
            return None
        return plc.Base, plc.Rotation.multVec(local).normalize()
    except Exception:
        return None


def rotation_aux(face, point, u, angle):
    """
    Girar la cara plana `angle` grados (con signo) alrededor del eje (point, u), paralelo a ella:
    (Placement del plano neutro, Placement de la línea de tiro) para un Ángulo de salida de
    `abs(angle)` sin invertir, o un problema (texto).
    """
    n = face_normal(face)
    if abs(u.dot(n)) > 1e-6:
        return None, None, "El eje de giro tiene que ser paralelo a la cara."
    w = u.cross(n).normalize()
    height = (point - face.Vertexes[0].Point).dot(n)
    foot = point - n * height
    hinge = foot + w * hinge_shift(height, angle)
    # plano neutro: contiene la recta y la normal (su normal es w); tiro: w hacia donde sube la cara
    pull = w if angle > 0 else w * -1
    neutral = FreeCAD.Placement(hinge, FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), w))
    line = FreeCAD.Placement(hinge, FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), pull))
    return neutral, line, ""


def ring_geometry(face, distance, flip):
    """
    Equidistanciar una cara cilíndrica entera: (operación, Placement del croquis del anillo,
    sus 4 esquinas, "") o (None, None, None, problema). El croquis contiene el eje: X radial,
    Y = eje (su V_Axis es el eje de la revolución).
    """
    center, axis, radius, length, away = cylinder_data(face)
    move = normal_move(OFFSET, (0, 0, 0), distance, flip)
    radii = ring_radii(radius, move, away)
    if radii is None:
        return None, None, None, "Con esa distancia el agujero se cierra: probá con una menor."
    radial = axis.cross(FreeCAD.Vector(0, 0, 1))
    if radial.Length < 1e-6:
        radial = axis.cross(FreeCAD.Vector(1, 0, 0))
    radial.normalize()
    rot = FreeCAD.Rotation(radial, axis, radial.cross(axis), "ZXY")
    r0, r1 = radii
    pts = [FreeCAD.Vector(r0, 0, 0), FreeCAD.Vector(r1, 0, 0),
           FreeCAD.Vector(r1, length, 0), FreeCAD.Vector(r0, length, 0)]
    return native_type(OFFSET, move, curved=True), FreeCAD.Placement(center, rot), pts, ""


def _ring_global(plc, pts):
    return [plc.multVec(p) for p in pts]


def ring_matches(sketch, plc, pts, tol=1e-6):
    """¿El croquis del anillo ya dibuja ese anillo? (mismas esquinas en el espacio)."""
    try:
        have = [sketch.Placement.multVec(g.StartPoint) for g in sketch.Geometry]
    except Exception:
        return False
    want = _ring_global(plc, pts)
    return len(have) == 4 and all((a - b).Length < tol for a, b in zip(have, want))


def write_ring(sketch, plc, pts):
    import Part

    if sketch.MapMode != "Deactivated":
        sketch.MapMode = "Deactivated"
    if not sketch.Placement.isSame(plc, 1e-9):
        sketch.Placement = plc
    old = [(g.StartPoint, g.EndPoint) for g in sketch.Geometry]
    new = [(pts[i], pts[(i + 1) % 4]) for i in range(4)]
    if len(old) != 4 or any((a - c).Length > 1e-9 or (b - d).Length > 1e-9 for (a, b), (c, d) in zip(old, new)):
        sketch.deleteAllGeometry()
        for a, b in new:
            sketch.addGeometry(Part.LineSegment(a, b))
    sketch.recompute()


def place_aux(aux, plc):
    if aux.MapMode != "Deactivated":
        aux.MapMode = "Deactivated"
    if not aux.Placement.isSame(plc, 1e-9):
        aux.Placement = plc
    aux.recompute()


def face_rotated(before, faces, after, tol=1e-6):
    """
    ¿Las caras a girar ya no están donde estaban? El Ángulo de salida a veces no gira nada y no avisa:
    con Reversed, FreeCAD saca en silencio las caras que OpenCASCADE no acepta (makeElementDraft,
    1.1.4).
    """
    for name in faces:
        face = before.getElement(name)
        n, p = face_normal(face), face.CenterOfMass
        for f in after.Faces:
            if not is_planar(f) or abs(abs(face_normal(f).dot(n)) - 1) > 1e-9:
                continue
            if abs((f.CenterOfMass - p).dot(n)) < tol and abs(f.Area - face.Area) <= tol * max(1.0, face.Area):
                return False
    return True


def same_plane(a, b, tol=1e-6):
    """Dos Placement de plano (normal = Z local): ¿el mismo plano?"""
    z = FreeCAD.Vector(0, 0, 1)
    na, nb = a.Rotation.multVec(z), b.Rotation.multVec(z)
    return abs(abs(na.dot(nb)) - 1) < 1e-9 and abs(na.dot(b.Base - a.Base)) < tol


def same_line(a, b, tol=1e-6):
    """Dos Placement de línea (sentido = Z local): ¿la misma recta, con el mismo sentido?"""
    z = FreeCAD.Vector(0, 0, 1)
    da, db = a.Rotation.multVec(z), b.Rotation.multVec(z)
    return da.dot(db) > 1 - 1e-9 and (b.Base - a.Base).cross(da).Length < tol


# --- Auxiliares fijos: aviso y Ctrl+Q ------------------------------------------
# El giro con eje fuera de la cara y el anillo de una cara cilíndrica usan auxiliares con ubicación
# fija (calculada al aceptar). Si la pieza cambia, quedan atrasados: se avisa (cartelito y texto en
# el árbol) y Ctrl+Q los reubica, igual que abrir el Mover cara y aceptar. Sin cálculo propio en
# el recálculo de FreeCAD (el archivo abre y recalcula sin el addon).


def _spec_aux(obj):
    spec = read_spec(getattr(obj, MARK, ""))
    aux = spec.get("aux") if isinstance(spec.get("aux"), dict) else {}
    return spec, aux


def wanted_aux(obj):
    """
    Dónde deberían estar los auxiliares fijos de este Mover cara con la pieza como está ahora:
    {"plane": Placement, "line": Placement} o {"sketch": (Placement, esquinas)}. None si no tiene
    auxiliares fijos o no se puede calcular (cara que ya no existe, operación con error...).
    """
    from swui.fork import feature_tree as ft

    spec, aux = _spec_aux(obj)
    if "sketch" not in aux and not ("plane" in aux and "line" in aux):
        return None
    base = getattr(obj, "BaseFeature", None)
    faces = MoveFacePanel._initial_faces(obj)
    try:
        face = base.Shape.getElement(faces[0]) if base is not None and faces else None
    except Exception:
        face = None
    if face is None:
        return None
    if "sketch" in aux:
        type_id, plc, pts, problem = ring_geometry(face, float(spec["distance"]), bool(spec["flip"]))
        if problem or type_id != obj.TypeId:
            return None
        return {"sketch": (plc, pts)}
    ref = MoveFacePanel._ref(obj.Document, spec.get("axis"))
    if ref is None and spec.get("hinge"):
        ref = (base, spec["hinge"])
    if ref is None:
        return None
    axis = axis_of(ref, base, ft.body_of(obj))
    if axis is None:
        return None
    angle = obj.Angle.Value * (-1.0 if spec["flip"] else 1.0)
    neutral, line, problem = rotation_aux(face, axis[0], axis[1], angle)
    if problem:
        return None
    return {"plane": neutral, "line": line}


# --- Ángulo de salida con la bisagra corrida (error de FreeCAD 1.1.4, sigue en 26.3) ---------
# PartDesign::Draft pasa el plano neutro y el tiro a las coordenadas de su propio Placement ANTES de
# copiar el de la operación anterior (FeatureDraft.cpp, execute: invObjLoc y recién después
# positionByBaseFeature). Si la operación anterior no está en el origen (un croquis fuera del
# origen, un agujero...), ese cálculo gira la cara alrededor de una bisagra corrida: sale mal sin
# aviso o falla (visto 2026-10-31; recalculado otra vez da bien). Al aceptar se le copia la
# ubicación antes de calcular y se anota en "plc"; si después cambia la de la operación anterior,
# queda atrasado: aviso + Ctrl+Q, que lo recalcula (ya con la ubicación nueva).


def _plc(data):
    return FreeCAD.Placement(FreeCAD.Vector(*data[:3]), FreeCAD.Rotation(*data[3:]))


def plc_data(plc):
    return list(plc.Base) + list(plc.Rotation.Q)


def place_draft(obj, base):
    """Darle al Ángulo de salida la ubicación de la operación anterior antes de calcular."""
    if base is not None and not obj.Placement.isSame(base.Placement, 1e-9):
        obj.Placement = base.Placement


def draft_misplaced(obj):
    """¿Este Mover cara (Ángulo de salida) se calculó con la ubicación vieja de la operación anterior?"""
    if obj.TypeId != DRAFT:
        return False
    base = getattr(obj, "BaseFeature", None)
    if base is None:
        return False
    used = read_spec(getattr(obj, MARK, "")).get("plc")
    if not used:  # de antes de este arreglo: solo pudo salir mal si la anterior no está en el origen
        return not base.Placement.isIdentity()
    try:
        return not base.Placement.isSame(_plc(used), 1e-7)
    except Exception:
        return False


def stale(obj):
    """¿Los auxiliares fijos de este Mover cara quedaron atrasados respecto de la pieza?"""
    if draft_misplaced(obj):
        return True
    want = wanted_aux(obj)
    if not want:
        return False
    _spec, aux = _spec_aux(obj)
    doc = obj.Document
    for key, value in want.items():
        have = doc.getObject(aux.get(key, ""))
        if have is None:
            return False
        if key == "sketch" and not ring_matches(have, *value):
            return True
        if key == "plane" and not same_plane(have.Placement, value):
            return True
        if key == "line" and not same_line(have.Placement, value):
            return True
    return False


def update(obj):
    """Reubicar los auxiliares fijos (lo mismo que abrir el Mover cara y aceptar). True si cambió algo."""
    if not stale(obj):
        return False
    if draft_misplaced(obj):
        spec = read_spec(getattr(obj, MARK, ""))
        spec["plc"] = plc_data(obj.BaseFeature.Placement)
        setattr(obj, MARK, json.dumps(spec, sort_keys=True))
        place_draft(obj, obj.BaseFeature)
    want = wanted_aux(obj) or {}
    _spec, aux = _spec_aux(obj)
    doc = obj.Document
    for key, value in want.items():
        target = doc.getObject(aux[key])
        if key == "sketch":
            write_ring(target, *value)
        else:
            place_aux(target, value)
    obj.touch()
    return True


def marked(doc, every=False):
    """Los Mover cara del documento (every=False: solo los que pueden tener auxiliares fijos)."""
    return [o for o in doc.Objects if hasattr(o, MARK) and (every or o.TypeId in (DRAFT, GROOVE, REVOLUTION))]


def lost(obj):
    """
    ¿Perdió la cara que mueve? FreeCAD renumera las caras cuando cambia la forma de antes (p. ej. un
    agujero que deja de atravesar) y la referencia queda "?Face3": la operación sigue "válida" pero
    no hace nada (visto con el mouse, 2026-10-31). Hay que abrirlo y elegir la cara de nuevo.
    """
    base = getattr(obj, "BaseFeature", None)
    faces = MoveFacePanel._initial_faces(obj)
    if base is None or not faces:
        return False
    for name in faces:
        if name.startswith("?"):
            return True
        try:
            base.Shape.getElement(name)
        except Exception:
            return True
    return False


def lost_in(doc):
    out = []
    for obj in marked(doc, every=True):
        try:
            if lost(obj):
                out.append(obj)
        except Exception:
            pass
    return out


def stale_in(doc):
    out = []
    for obj in marked(doc):
        try:
            if stale(obj):
                out.append(obj)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Mover cara atrasado:\n%s\n" % traceback.format_exc())
    return out


def update_stale(doc, passes=5):
    """
    Ctrl+Q: reubicar los auxiliares de todos los Mover cara atrasados. -> cuántos. Puede hacer falta
    más de una vuelta: al poner al día uno (el agujero), otro de después recupera su cara y recién
    entonces se ve que también quedó atrasado (visto con el mouse, 2026-10-31).
    """
    done = 0
    for _i in range(passes):
        now = 0
        for obj in stale_in(doc):
            try:
                if update(obj):
                    now += 1
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] Actualizar %s:\n%s\n" % (obj.Label, traceback.format_exc()))
        if not now:
            break
        done += now
        doc.recompute()
    return done


STALE_TEXT = "⚠ desactualizado: Ctrl+Q"
LOST_TEXT = "⚠ perdió la cara: Ctrl+Q o abrilo"
_stale = {}  # Name del documento -> {Name de los Mover cara atrasados}
_lost = {}  # Name del documento -> {Name de los Mover cara que perdieron la cara}


def _warn(doc, text):
    try:
        FreeCAD.Console.PrintTranslatedUserWarning(doc.Label, text)  # cartelito de FreeCAD
    except Exception:
        FreeCAD.Console.PrintWarning("[SWUI] " + text)


def check(doc):
    """Mirar (sin cambiar nada) qué Mover cara quedaron atrasados o sin cara; avisar los nuevos."""
    if doc is None:
        return
    try:
        lost_now = set(o.Name for o in lost_in(doc))
        now = set(o.Name for o in stale_in(doc)) - lost_now
    except Exception:
        return
    before, lost_before = _stale.get(doc.Name, set()), _lost.get(doc.Name, set())
    _stale[doc.Name], _lost[doc.Name] = now, lost_now
    new = [doc.getObject(n) for n in sorted(now - before)]
    if new:
        _warn(doc, "%s quedó desactualizado porque cambió la pieza: apretá Ctrl+Q para actualizarlo.\n"
              % ", ".join(o.Label for o in new if o is not None))
    gone = [doc.getObject(n) for n in sorted(lost_now - lost_before)]
    if gone:
        hint = (" Si otro Mover cara de antes quedó desactualizado, apretá primero Ctrl+Q: al ponerlo al día "
                "suele volver la cara." if now else "")
        _warn(doc, "%s perdió la cara que movía porque cambió la pieza (FreeCAD renumeró las caras): "
                   "abrilo (clic derecho > Editar operación) y elegí la cara de nuevo.%s\n"
              % (", ".join(o.Label for o in gone if o is not None), hint))
    if now != before or lost_now != lost_before:
        try:
            from swui.fork import tree_overlay

            tree_overlay.refresh()
        except Exception:
            pass


def tree_text(tree):
    """Texto al lado del renglón de cada Mover cara atrasado (tree_overlay.EXTRA_TEXT)."""
    from swui.fork import tree_overlay

    out = []
    for _body, rows in tree_overlay.body_rows(tree):
        for obj, (x, y0, w, h, _row_x), _top, _bottom, _f in rows:
            try:
                if obj.Name in _lost.get(obj.Document.Name, ()):
                    out.append((x + w + 6, y0, h, LOST_TEXT))
                elif obj.Name in _stale.get(obj.Document.Name, ()):
                    out.append((x + w + 6, y0, h, STALE_TEXT))
            except Exception:
                pass
    return out


class _DocObserver:
    def slotRecomputedDocument(self, doc):
        try:
            name = doc.Name
        except Exception:
            return
        QtCore.QTimer.singleShot(0, lambda: check(FreeCAD.listDocuments().get(name)))

    def slotCreatedDocument(self, doc):  # también al abrir un archivo (ya cargado cuando corre)
        try:
            name = doc.Name
        except Exception:
            return
        QtCore.QTimer.singleShot(800, lambda: check(FreeCAD.listDocuments().get(name)))

    def slotUndoDocument(self, doc):  # deshacer no recalcula: mirar igual (visto con el mouse, 2026-10-31)
        self.slotRecomputedDocument(doc)

    def slotRedoDocument(self, doc):
        self.slotRecomputedDocument(doc)

    def slotDeletedDocument(self, doc):
        try:
            _stale.pop(doc.Name, None)
            _lost.pop(doc.Name, None)
        except Exception:
            pass


_observer = None


def first_face_hit(face, normal, target):
    """
    Hasta el sólido: la primera cara de `target` (forma, en coordenadas del Cuerpo) que encuentra
    la cara al avanzar según `normal` (desde su centro). -> ("FaceN", distancia con signo) o None.
    """
    import Part

    start = face.CenterOfMass
    best = None
    for sign in (1.0, -1.0):
        ray = Part.LineSegment(start, start + normal * sign * 1e5).toShape()
        for i, cand in enumerate(target.Faces):
            try:
                dist, pts, _info = ray.distToShape(cand)
            except Exception:
                continue
            if dist > 1e-6 or not pts:
                continue
            s = (pts[0][0] - start).dot(normal)
            if abs(s) < 1e-6:
                continue
            if best is None or abs(s) < abs(best[1]):
                best = ("Face%d" % (i + 1), s)
        if best is not None:
            return best
    return None


def _links_to(user, obj):
    """¿user usa a obj en algo más que su BaseFeature (caras, aristas, croquis apoyados...)?"""
    for prop in user.PropertiesList:
        if prop in ("BaseFeature", "_Body"):
            continue
        try:
            if "Link" not in user.getTypeIdOfProperty(prop):
                continue
            value = getattr(user, prop)
        except Exception:
            continue
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            if item is obj or (isinstance(item, tuple) and item and item[0] is obj):
                return True
    return False


# --- Panel -------------------------------------------------------------------


class MoveFacePanel(dp.SwPanel):
    TRANSACTION = "Mover cara"
    NOTHING = "Elegí al menos una cara."

    @property
    def FAIL(self):
        if self.spec["mode"] == ROTATE:
            # con la ubicación ya corregida (place_draft), falla cuando la cara girada atravesaría
            # la de enfrente o chocaría con otra
            return "Con ese ángulo la cara atraviesa la pieza: probá un ángulo menor o el otro sentido."
        if self.spec["mode"] == TRANSLATE and self.spec["end"] != END_DEPTH:
            return "FreeCAD no pudo llevar la cara hasta ahí: probá con otra referencia."
        return "FreeCAD no pudo mover la cara así: probá con una distancia menor."

    def __init__(self, obj, faces=None):
        self.spec = read_spec(getattr(obj, MARK, ""))
        if not isinstance(self.spec.get("aux"), dict):
            self.spec["aux"] = {}
        self.faces = list(faces) if faces is not None else self._initial_faces(obj)
        self.direction = self._ref(obj.Document, self.spec.get("dir"))
        self.target = self._ref(obj.Document, self.spec.get("target"))
        self.axis = self._ref(obj.Document, self.spec.get("axis"))
        self.hinge = self.spec.get("hinge") or ""
        gdoc = FreeCADGui.getDocument(obj.Document.Name)
        if gdoc.getInEdit() is not None and not obj.Document.HasPendingTransaction:
            # Editar una existente: sin modo edición de FreeCAD, así se puede cambiar Pad <-> Pocket
            gdoc.resetEdit()
        super().__init__(obj)

    @staticmethod
    def _ref(doc, data):
        if not data:
            return None
        found = doc.getObject(data[0])
        return (found, data[1]) if found is not None else None

    @staticmethod
    def _initial_faces(obj):
        if obj.TypeId in (GROOVE, REVOLUTION):
            return list(read_spec(getattr(obj, MARK, "")).get("faces") or [])
        try:
            ref = obj.Base if obj.TypeId == DRAFT else obj.Profile
            return list(ref[1]) if ref and ref[0] is not None else []
        except Exception:
            return []

    # --- interfaz

    def _build(self):
        from swui import paths
        from swui.compat import QtGui

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.obj.Label)
        icon = paths.icon("fork/move_face")
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        box = QtWidgets.QVBoxLayout(self.form)

        top = QtWidgets.QGroupBox("Mover cara")
        tl = QtWidgets.QVBoxLayout(top)
        self.group = QtWidgets.QButtonGroup(self.form)
        self.radios = {}
        for text, mode in MODES:
            radio = QtWidgets.QRadioButton(text, top)
            radio.setChecked(mode == self.spec["mode"])
            radio.toggled.connect(lambda on, m=mode: self._mode(m) if on else None)
            self.group.addButton(radio)
            tl.addWidget(radio)
            self.radios[mode] = radio
        tl.addWidget(QtWidgets.QLabel("Caras (clic en la pieza):"))
        self.list = dp.pick_list(self.remove_current, self.clear, height=70)
        self.list.setMaximumHeight(110)  # que entren los parámetros en una pantalla de 768
        self.list.itemClicked.connect(lambda *_a: self._activate(self.list))
        self.list.currentRowChanged.connect(lambda *_a: self._draw())
        tl.addWidget(self.list)
        box.addWidget(top)

        params = QtWidgets.QGroupBox("Parámetros")
        self.params = QtWidgets.QFormLayout(params)
        self.end = QtWidgets.QComboBox()
        for text, value in ENDS:
            self.end.addItem(text, value)
        self.end.setCurrentIndex(max(0, [v for _t, v in ENDS].index(self.spec["end"])))
        self.end.currentIndexChanged.connect(self._end_changed)
        self.target_box = dp.RefBox(self._activate)
        self.dir_box = dp.RefBox(self._activate)
        self.dir_box.setPlaceholderText("Arista, cara plana o plano")
        self.dir_box.setToolTip("Vacía: se usan ΔX ΔY ΔZ")
        self.hinge_box = dp.RefBox(self._activate)
        self.hinge_box.setPlaceholderText("Arista recta o eje")
        self.hinge_box.setToolTip("Una arista de la cara, u otra recta paralela a la cara")
        self.flip = QtWidgets.QCheckBox("Invertir dirección")
        self.flip.setChecked(bool(self.spec["flip"]))
        self.flip.toggled.connect(self._changed)
        locked = self._locked()
        self.distance = dp._spin(float(self.spec["distance"]), " mm", 0.001, 100000.0)
        self.distance.valueChanged.connect(self._changed)
        self.gap = dp._spin(float(self.spec["gap"]), " mm", 0.0, 100000.0)
        self.gap.valueChanged.connect(self._changed)
        self.deltas = []
        for value in self.spec["delta"]:
            spin = dp._spin(float(value), " mm", -100000.0, 100000.0)
            spin.valueChanged.connect(self._changed)
            self.deltas.append(spin)
        self.angle = dp._spin(float(self.spec["angle"]), "°", 0.01, 89.99)
        self.angle.valueChanged.connect(self._changed)
        if locked:
            for spin in (self.distance, self.angle):
                spin.setEnabled(False)
                spin.setToolTip("Controlado por una ecuación")
        self.rows = {}
        for key, text, widget in (("end", "", self.end), ("target", "Hasta:", self.target_box),
                                  ("dir", "Dirección:", self.dir_box), ("hinge", "Eje de giro:", self.hinge_box),
                                  ("flip", "", self.flip), ("distance", "Distancia:", self.distance),
                                  ("gap", "Distancia:", self.gap),
                                  ("dx", "ΔX:", self.deltas[0]), ("dy", "ΔY:", self.deltas[1]),
                                  ("dz", "ΔZ:", self.deltas[2]), ("angle", "Ángulo:", self.angle)):
            label = QtWidgets.QLabel(text)
            self.params.addRow(label, widget)
            self.rows[key] = (label, widget)
        box.addWidget(params)
        box.addWidget(self._message_label())
        box.addStretch(1)
        self.active = self.list
        self._refresh()

    def _locked(self):
        """La distancia o el ángulo atados a una ecuación (en la operación nativa)."""
        prop = {DRAFT: "Angle", GROOVE: "", REVOLUTION: ""}.get(self.obj.TypeId, "Length")
        return bool(prop) and self._has_expression(prop)

    def _mode(self, mode):
        if mode == self.spec["mode"]:
            return
        self.spec["mode"] = mode
        remember_mode(mode)
        self.active = self.list
        self._refresh()
        self._changed()

    def _end_changed(self, *_a):
        self.spec["end"] = self.end.currentData()
        self.target = None
        self.active = self.target_box if self.spec["end"] != END_DEPTH else self.list
        self._refresh()
        self._changed()

    def _activate(self, widget):
        self.active = widget
        self._paint_active()

    def _paint_active(self):
        for w in (self.list, self.target_box, self.dir_box, self.hinge_box):
            qss = dp.ACTIVE_QSS if w is self.active else ""
            w.setStyleSheet(("QListWidget { %s }" % qss) if (w is self.list and qss) else qss)

    def _refresh(self):
        mode, end = self.spec["mode"], self.spec["end"]
        has_dir = self.direction is not None
        depth = mode == TRANSLATE and end == END_DEPTH
        show = {"end": mode == TRANSLATE, "target": mode == TRANSLATE and end != END_DEPTH,
                "dir": depth, "hinge": mode == ROTATE, "flip": mode != TRANSLATE or end in (END_DEPTH, END_OFFSET),
                "distance": mode == OFFSET or (depth and has_dir),
                "gap": mode == TRANSLATE and end == END_OFFSET,
                "dx": depth and not has_dir, "dy": depth and not has_dir,
                "dz": depth and not has_dir, "angle": mode == ROTATE}
        for key, (label, widget) in self.rows.items():
            label.setVisible(show[key])
            widget.setVisible(show[key])
        self.target_box.setPlaceholderText({END_VERTEX: "Vértice", END_SURFACE: "Cara o plano",
                                            END_OFFSET: "Cara o plano", END_BODY: "Sólido"}.get(end, ""))
        self.target_box.setText(self._ref_text(self.target))
        self.dir_box.setText(self._ref_text(self.direction))
        self.hinge_box.setText(self._ref_text(self.axis) if self.axis else ("Arista<1>" if self.hinge else ""))
        row = self.list.currentRow()
        self.list.clear()
        for sub, text in zip(self.faces, dp.sw_names(self.faces)):
            item = QtWidgets.QListWidgetItem(text)
            if self.base is None or dp._element(self.base.Shape, sub) is None:
                from swui.compat import QtGui

                item.setText(text + "  (no se encuentra: borrala y elegí otra)")
                item.setForeground(QtGui.QBrush(QtGui.QColor(dp.MISSING_COLOR)))
            self.list.addItem(item)
        if 0 <= row < len(self.faces):
            self.list.setCurrentRow(row)
        self._paint_active()

    @staticmethod
    def _ref_text(ref):
        if not ref:
            return ""
        obj, sub = ref
        if sub.startswith("Edge"):
            return "Arista<1> (%s)" % obj.Label
        if sub.startswith("Face"):
            return "Cara<1> (%s)" % obj.Label
        if sub.startswith("Vertex"):
            return "Vértice<1> (%s)" % obj.Label
        return obj.Label

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.faces):
            self.faces = self.faces[:row] + self.faces[row + 1:]
            self._refresh()
            self.preview()

    def clear(self, *_a):
        self.faces = []
        self._refresh()
        self.preview()

    # --- selección

    def _to_base(self, obj, sub):
        """Arista/cara tocada (en el sólido anterior o en la vista previa) -> nombre en el anterior."""
        if self.base is None:
            return None
        if obj == self.base:
            return sub
        if obj == self.obj and self.valid:
            return dp.to_base(self.obj.Shape, sub, self.base.Shape)
        return None

    def _own(self, obj):
        """¿obj es este Cuerpo (el sólido anterior, la vista previa o el Cuerpo mismo)?"""
        from swui.fork import feature_tree as ft

        return obj in (self.base, self.obj) or ft.body_of(obj) is ft.body_of(self.obj)

    def _pick_target(self, obj, sub):
        end = self.spec["end"]
        ref = None
        if end == END_BODY:
            from swui.fork import feature_tree as ft

            if self._own(obj):
                return False  # hasta OTRO sólido
            body = ft.body_of(obj)
            target = body if body is not None else obj
            try:
                if not target.Shape.Solids:
                    return False
            except Exception:
                return False
            ref = (target, "")
        elif end == END_VERTEX:
            if obj == self.obj:
                return False  # el vértice de la vista previa se mueve con la cara
            if sub.startswith("Edge"):
                # un vértice es difícil de acertar (FreeCAD no le da prioridad, SW sí): un clic en
                # una arista toma la punta más cercana al clic (visto con el mouse, 2026-10-31)
                sub = self._edge_end(obj, sub) or ""
            if not sub.startswith("Vertex"):
                return False
            ref = (obj, sub)
        else:
            if sub.startswith("Face"):
                if obj in (self.base, self.obj):
                    name = self._to_base(obj, sub)
                    ref = (self.base, name) if name else None
                else:
                    ref = (obj, sub)
            elif not sub and obj.TypeId in ("App::Plane", "PartDesign::Plane"):
                ref = (obj, "")
        if ref is None:
            return False
        self.target = ref
        self.active = self.list
        return True

    @staticmethod
    def _picked_point(obj, sub):
        """Punto donde se hizo clic (global) sobre obj/sub, de la selección actual, o None."""
        try:
            for sel in FreeCADGui.Selection.getSelectionEx():
                if sel.Object is not obj:
                    continue
                for name, point in zip(sel.SubElementNames, sel.PickedPoints):
                    if name.split(".")[-1] == sub:
                        return point
        except Exception:
            pass
        return None

    def _edge_end(self, obj, sub):
        """'EdgeN' tocada -> 'VertexM' de su punta más cercana al clic (en la forma de obj)."""
        from swui.fork import sketch_model_edges as sme

        point = self._picked_point(obj, sub)
        try:
            shape = sme._global_shape(obj)
            edge = shape.getElement(sub)
        except Exception:
            return None
        if point is None or not edge.Vertexes:
            return None
        best = min(edge.Vertexes, key=lambda v: (v.Point - point).Length)
        for i, v in enumerate(shape.Vertexes):
            if v.isSame(best) or (v.Point - best.Point).Length < 1e-7:
                return "Vertex%d" % (i + 1)
        return None

    def _pick(self, obj, sub):
        if self.active is self.target_box:
            return self._pick_target(obj, sub)
        if self.active is self.dir_box:
            ref = None
            if sub and obj in (self.base, self.obj):
                name = self._to_base(obj, sub)
                ref = (self.base, name) if name else None
            elif sub:
                ref = (obj, sub)
            elif obj.TypeId in ("App::Plane", "PartDesign::Plane", "App::Line", "PartDesign::Line"):
                ref = (obj, "")
            if ref is None or direction_of(*ref) is None:
                return False
            self.direction = ref
            self.active = self.list
            return True
        if self.spec["mode"] == ROTATE and not sub and obj.TypeId in ("App::Line", "PartDesign::Line"):
            self.axis, self.hinge = (obj, ""), ""  # eje de referencia
            self.active = self.list
            return True
        if sub.startswith("Edge"):
            if self.spec["mode"] != ROTATE:
                return False
            name = self._to_base(obj, sub) if obj in (self.base, self.obj) else None
            if name is not None:
                edge = dp._element(self.base.Shape, name)
                if edge is None or not _is_line(edge):
                    return False
                if self._in_face_plane(edge):
                    self.hinge, self.axis = name, None  # arista en el plano de la cara: bisagra
                else:
                    self.hinge, self.axis = "", (self.base, name)
            elif obj == self.obj:
                return False
            else:
                self.hinge, self.axis = "", (obj, sub)  # arista de otra pieza o croquis
            self.active = self.list
            return True
        if not sub.startswith("Face"):
            return False
        if obj == self.obj and self.valid and int(sub[4:]) - 1 in self.yellow:
            geo = dp._element(self.obj.Shape, sub)  # cara amarilla: sacar la cara movida más cercana
            gone = dp.nearest(geo, self.base.Shape, self.faces) if geo is not None else None
            if gone is None:
                return False
            self.faces = [f for f in self.faces if f != gone]
            return True
        name = self._to_base(obj, sub)
        if name is None:
            return False
        if self.active is self.hinge_box:
            self.active = self.list
        self.faces = dp.toggle(self.faces, name)
        return True

    def _in_face_plane(self, edge):
        if not self.faces:
            return True
        face = dp._element(self.base.Shape, self.faces[0])
        if face is None or not is_planar(face):
            return True
        n = face_normal(face)
        origin = face.Vertexes[0].Point
        return all(_on_plane(v.Point, origin, n) for v in edge.Vertexes)

    # --- auxiliares (planos, líneas y croquis ocultos de la operación)

    def _body(self):
        from swui.fork import feature_tree as ft

        return ft.body_of(self.obj)

    def _aux(self, key, type_id, name):
        """El auxiliar `key` de esta operación (lo crea antes de ella en el Cuerpo, oculto)."""
        aux = self.spec["aux"]
        found = self.doc.getObject(aux.get(key, "")) if aux.get(key) else None
        if found is not None and found.TypeId == type_id:
            return found
        body = self._body()
        new = self.doc.addObject(type_id, name)
        body.insertObject(new, self.obj, False)
        new.Visibility = False
        try:
            new.ViewObject.ShowInTree = False  # como SW: no se ven en el árbol
        except Exception:
            pass
        new.Label = "%s-%s" % (self.obj.Label, name)
        aux[key] = new.Name
        return new

    def _drop_aux(self, keep=()):
        aux = self.spec["aux"]
        for key in [k for k in aux if k not in keep]:
            name = aux.pop(key)
            obj = self.doc.getObject(name)
            if obj is None:
                continue
            try:
                body = self._body()
                if body is not None and obj in body.Group:
                    body.removeObject(obj)
                self.doc.removeObject(name)
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] Mover cara, auxiliar:\n%s\n" % traceback.format_exc())

    # --- operación nativa

    def _normal(self):
        face = dp._element(self.base.Shape, self.faces[0])
        return face_normal(face)

    def _swap(self, type_id):
        """Cambiar la operación por otra (Pad <-> Pocket <-> Draft...), en el mismo lugar del Cuerpo."""
        from swui.fork import multibody

        old = self.obj
        body = self._body()
        if body is None:
            return "La operación no está en un Cuerpo."
        aux_names = set(self.spec["aux"].values())
        if any(u is not body and u.Name not in aux_names and _links_to(u, old) for u in old.InList):
            return ("Otras operaciones usan esta cara movida: para pasar de agregar a quitar material "
                    "(o a girar) hay que hacer otro Mover cara.")
        new = self.doc.addObject(type_id, NATIVE_NAMES[type_id])
        body.insertObject(new, old, True)
        new.addProperty("App::PropertyString", MARK, "SWUI", "Mover cara (fork de LikeSolidWorks UI)")
        new.setEditorMode(MARK, 2)
        for path, expr in old.ExpressionEngine:
            if path in new.PropertiesList:
                try:
                    new.setExpression(path, expr)
                except Exception:
                    pass
        label, old_name = old.Label, old.Name
        was_tip = body.Tip is old
        body.removeObject(old)
        self.doc.removeObject(old_name)
        if was_tip:
            multibody._set_tip(body, new)
        multibody._keep_label(new, label)
        self.visible.pop(old_name, None)
        self.visible[new.Name] = False
        self.obj = new
        self.base = new.BaseFeature
        return ""

    def _ensure(self, type_id):
        return self._swap(type_id) if self.obj.TypeId != type_id else ""

    def _apply(self):
        mode = self.spec["mode"]
        self.spec.update({"flip": self.flip.isChecked(), "distance": self.distance.value(),
                          "delta": [s.value() for s in self.deltas], "angle": self.angle.value(),
                          "hinge": self.hinge, "end": self.end.currentData(), "gap": self.gap.value(),
                          "faces": list(self.faces),
                          "dir": [self.direction[0].Name, self.direction[1]] if self.direction else None,
                          "target": [self.target[0].Name, self.target[1]] if self.target else None,
                          "axis": [self.axis[0].Name, self.axis[1]] if self.axis else None})
        if self.base is None:
            return "No hay sólido antes de esta operación."
        if not self.faces:
            return ""
        problem = faces_problem(self.base.Shape, self.faces, same_plane=(mode == ROTATE),
                                curved_ok=(mode == OFFSET))
        if problem:
            return problem
        if mode == ROTATE:
            return self._apply_rotate()
        face = dp._element(self.base.Shape, self.faces[0])
        if not is_planar(face):
            return self._apply_cylinder(face)
        if mode == TRANSLATE and self.spec["end"] != END_DEPTH:
            return self._apply_up_to(face)
        direction = direction_of(*self.direction) if (mode == TRANSLATE and self.direction) else None
        n = self._normal()
        move = normal_move(mode, (n.x, n.y, n.z), self.distance.value(), self.flip.isChecked(),
                           (direction.x, direction.y, direction.z) if direction is not None else None,
                           [s.value() for s in self.deltas])
        if abs(move) < TOL:
            return "Ese desplazamiento no mueve la cara (es paralelo a ella o vale cero)."
        problem = self._ensure(native_type(mode, move))
        if problem:
            return problem
        self._drop_aux()
        self._write_spec()
        if self.obj.Profile != (self.base, self.faces):
            self.obj.Profile = (self.base, self.faces)
        self._set("Type", "Length")
        self._set("Length", abs(move))
        return ""

    def _apply_up_to(self, face):
        """Trasladar con condición final (Hasta el vértice / la superficie / el sólido)."""
        from swui.fork import sketch_model_edges as sme

        end = self.spec["end"]
        if self.target is None:
            return {END_VERTEX: "Elegí el vértice hasta donde llega la cara.",
                    END_BODY: "Elegí el sólido hasta donde llega la cara."}.get(
                        end, "Elegí la cara o el plano hasta donde llega la cara.")
        n = face_normal(face)
        origin = face.CenterOfMass
        tobj, tsub = self.target
        to_local = _local(self._body(), FreeCAD.Placement()).toMatrix()
        if end == END_BODY:
            try:
                shape = sme._global_shape(tobj).transformed(to_local)
            except Exception:
                return "Ese sólido no tiene forma."
            hit = first_face_hit(face, n, shape)
            if hit is None:
                return "La cara no encuentra ese sólido al avanzar ni al retroceder."
            tsub, side = hit
        else:
            try:
                if tobj is self.base:
                    geo = self.base.Shape.getElement(tsub)
                elif tsub:
                    geo = sme._global_shape(tobj).getElement(tsub).transformed(to_local)
                else:
                    geo = None
                point = geo.Point if end == END_VERTEX else (
                    geo.CenterOfMass if geo is not None else _local(self._body(), tobj.getGlobalPlacement()).Base)
            except Exception:
                return "Esa referencia ya no existe: elegí otra."
            side = (point - origin).dot(n)
        if abs(side) < TOL:
            return "La cara ya está ahí: no hay nada que mover."
        problem = self._ensure(PAD if side > 0 else POCKET)
        if problem:
            return problem
        keep = []
        ref = self._bound((tobj, tsub), keep)
        if end == END_VERTEX:
            plane = self._aux("vertex_plane", "PartDesign::Plane", "PlanoVertice")
            keep.append("vertex_plane")
            refs = [(ref[0], ref[1][0]), (self.base, self._face_edge_name()), (self.base, self.faces[0])]
            if [(o, s) for o, s in plane.AttachmentSupport] != refs:
                plane.AttachmentSupport = refs
            if plane.MapMode != "OXY":
                plane.MapMode = "OXY"  # por el vértice, paralelo a la cara (probado en 1.1.4)
            plane.recompute()
            ref = (plane, [""])
        offset = 0.0
        if end == END_OFFSET:
            # Un plano oculto apoyado en la superficie y corrido la distancia hacia la cara (Invertir:
            # del otro lado), y "Hasta cara" contra él. El Offset de FreeCAD no sirve: su signo
            # depende de cómo está orientada la cara y de si la superficie la tapa o no (con la cara
            # +X de un tope que no la tapaba quedaba del otro lado: visto con el mouse, 2026-10-31).
            plane = self._aux("offset_plane", "PartDesign::Plane", "PlanoEquidistante")
            keep.append("offset_plane")
            problem = self._offset_plane(plane, ref, n if side > 0 else n * -1)
            if problem:
                return problem
            ref = (plane, [""])
        self._drop_aux(keep)
        self._write_spec()
        if self.obj.Profile != (self.base, self.faces):
            self.obj.Profile = (self.base, self.faces)
        self._set("Type", "UpToFace")
        if self.obj.UpToFace != ref:
            self.obj.UpToFace = ref
        self._set("Offset", offset)
        return ""

    def _offset_plane(self, plane, ref, travel):
        """
        Ubicar el plano equidistante: apoyado en la superficie (cara plana o plano de referencia),
        corrido `gap` hacia donde viene la cara (`travel` = sentido en que avanza la cara).
        """
        obj, subs = ref
        sub = subs[0] if subs else ""
        support = [(obj, sub)]
        mode = "FlatFace" if sub.startswith("Face") else "ObjectXY"
        if [(o, s) for o, s in plane.AttachmentSupport] != support:
            plane.AttachmentSupport = support
        if plane.MapMode != mode:
            plane.MapMode = mode
        plane.AttachmentOffset = FreeCAD.Placement()
        plane.recompute()
        if "Invalid" in getattr(plane, "State", []):
            return "Para Equidistante, la superficie tiene que ser plana (o un plano)."
        z = plane.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        toward = z.dot(travel)
        if abs(toward) < 1e-9:
            return "La superficie es paralela al movimiento: la cara nunca llega."
        # antes de la superficie = correrla en contra del avance; Invertir: a favor
        step = self.gap.value() * (1.0 if self.flip.isChecked() else -1.0)
        shift = step if toward > 0 else -step
        plane.AttachmentOffset = FreeCAD.Placement(FreeCAD.Vector(0, 0, shift), FreeCAD.Rotation())
        plane.recompute()
        return ""

    def _bound(self, ref, keep):
        """
        Una referencia usable desde este Cuerpo: lo de otro Cuerpo o suelto queda fuera de alcance
        para una operación de PartDesign, así que pasa por un enlace nativo (SubShapeBinder oculto).
        -> (objeto, [sub]).
        """
        from swui.fork import feature_tree as ft

        obj, sub = ref
        body = self._body()
        if obj is self.base or ft.body_of(obj) is body or obj in getattr(body.Origin, "OriginFeatures", []):
            return (obj, [sub])
        binder = self._aux("binder", "PartDesign::SubShapeBinder", "Enlace")
        keep.append("binder")
        support = [(obj, (sub,) if sub else ())]
        if [(o, tuple(s)) for o, s in binder.Support] != support:
            # Lo apoyado en el enlace (el plano del vértice) se suelta antes: si no, al cambiar el
            # enlace FreeCAD marca su referencia "?Vertex1" y avisa en inglés "subshape not found"
            # (visto con el mouse, 2026-10-31). _apply_translate lo vuelve a apoyar enseguida.
            for dep in binder.InList:
                if any(o is binder for o, _ in getattr(dep, "AttachmentSupport", [])):
                    dep.MapMode = "Deactivated"
                    dep.AttachmentSupport = []
            binder.Support = support
        binder.recompute()
        if sub.startswith("Vertex"):
            return (binder, ["Vertex1"])
        if sub.startswith("Face"):
            return (binder, ["Face1"])
        return (binder, [""])

    def _face_edge_name(self):
        face = dp._element(self.base.Shape, self.faces[0])
        for i, e in enumerate(self.base.Shape.Edges):
            if any(e.isSame(fe) for fe in face.Edges):
                return "Edge%d" % (i + 1)
        return ""

    def _apply_rotate(self):
        hinge_problem = ""
        if self.hinge and not self.axis:
            neutral, pull, hinge_problem = hinge_refs(self.base.Shape, self.faces, self.hinge)
            if not hinge_problem:
                problem = self._ensure(DRAFT)
                if problem:
                    return problem
                self._drop_aux()
                self.spec["plc"] = plc_data(self.base.Placement)
                self._write_spec()
                place_draft(self.obj, self.base)  # error de FreeCAD: ver draft_misplaced
                self.obj.Base = (self.base, self.faces)
                if self.obj.NeutralPlane != (self.base, [neutral]):
                    self.obj.NeutralPlane = (self.base, [neutral])
                if self.obj.PullDirection != (self.base, [pull]):
                    self.obj.PullDirection = (self.base, [pull])
                self._set("Angle", self.angle.value())
                self._set("Reversed", self.flip.isChecked())
                return ""
            axis_ref = (self.base, self.hinge)  # sin cara bisagra: como cualquier eje
        elif self.axis:
            axis_ref = self.axis
        else:
            return "Elegí el eje de giro: una arista recta o un eje."
        axis = axis_of(axis_ref, self.base, self._body())
        if axis is None:
            return hinge_problem or "El eje de giro tiene que ser una recta."
        face = dp._element(self.base.Shape, self.faces[0])
        angle = self.angle.value() * (-1.0 if self.flip.isChecked() else 1.0)
        neutral, line, problem = rotation_aux(face, axis[0], axis[1], angle)
        if problem:
            return problem
        problem = self._ensure(DRAFT)
        if problem:
            return problem
        plane = self._aux("plane", "PartDesign::Plane", "PlanoGiro")
        pull = self._aux("line", "PartDesign::Line", "TiroGiro")
        place_aux(plane, neutral)
        place_aux(pull, line)
        self._drop_aux(("plane", "line"))
        self.spec["plc"] = plc_data(self.base.Placement)
        self._write_spec()
        place_draft(self.obj, self.base)  # error de FreeCAD: ver draft_misplaced
        self.obj.Base = (self.base, self.faces)
        if self.obj.NeutralPlane != (plane, [""]):
            self.obj.NeutralPlane = (plane, [""])
        if self.obj.PullDirection != (pull, [""]):
            self.obj.PullDirection = (pull, [""])
        self._set("Angle", abs(angle))
        self._set("Reversed", False)
        return ""

    def _apply_cylinder(self, face):
        """Equidistanciar una cara cilíndrica entera: anillo revolucionado (Groove / Revolution)."""
        type_id, plc, pts, problem = ring_geometry(face, self.distance.value(), self.flip.isChecked())
        if problem:
            return problem
        problem = self._ensure(type_id)
        if problem:
            return problem
        sketch = self._aux("sketch", "Sketcher::SketchObject", "Anillo")
        write_ring(sketch, plc, pts)
        self._drop_aux(("sketch",))
        self._write_spec()
        if self.obj.Profile != (sketch, [""]):
            self.obj.Profile = (sketch, [""])
        if self.obj.ReferenceAxis != (sketch, ["V_Axis"]):
            self.obj.ReferenceAxis = (sketch, ["V_Axis"])
        self._set("Angle", 360.0)
        return ""

    def _result_problem(self):
        if self.spec["mode"] != ROTATE or self.obj.TypeId != DRAFT or not self.faces:
            return ""
        try:
            if face_rotated(self.base.Shape, self.faces, self.obj.Shape):
                return ""
        except Exception:
            return ""
        return "FreeCAD dejó la cara sin girar: probá un ángulo menor o el otro sentido."

    def _write_spec(self):
        text = json.dumps(self.spec, sort_keys=True)
        if getattr(self.obj, MARK, None) != text:
            setattr(self.obj, MARK, text)
        remember_mode(self.spec["mode"])

    def _ready(self):
        if not self.faces:
            return False
        if self.spec["mode"] == ROTATE:
            return bool(self.hinge or self.axis)
        if self.spec["mode"] == TRANSLATE and self.spec["end"] != END_DEPTH:
            return self.target is not None
        return True

    def _nothing(self):
        return not self.faces

    def _overlays(self, base, result):
        nodes = super()._overlays(base, result)
        if base is None:
            return nodes
        if result is None:
            picked = [dp._element(base, s) for s in self.faces]
            nodes.append(dp._faces_node([p for p in picked if p is not None], dp.PICKED_COLOR))
        if self.hinge and self.spec["mode"] == ROTATE:
            el = dp._element(base, self.hinge)
            if el is not None:
                nodes.append(dp._lines_node([el], dp.CURRENT_COLOR, dp.LINE_WIDTH + 1))
        row = self.list.currentRow()
        if 0 <= row < len(self.faces):
            el = dp._element(base, self.faces[row])
            if el is not None:
                nodes.append(dp._lines_node([el], dp.CURRENT_COLOR, dp.LINE_WIDTH + 1))
        return nodes


def _choose(obj):
    return MoveFacePanel if hasattr(obj, MARK) else None


# --- Comando -------------------------------------------------------------------


def _body_for(doc, obj):
    """Cuerpo de lo elegido; a un sólido suelto (STEP) se le arma un Cuerpo que arranca de él."""
    from swui.fork import multibody

    body = obj if obj.TypeId == "PartDesign::Body" else multibody.body_of(obj)
    if body is not None:
        return body
    try:
        solid = obj.isDerivedFrom("Part::Feature") and bool(obj.Shape.Solids)
    except Exception:
        solid = False
    if not solid:
        return None
    body = doc.addObject("PartDesign::Body", "Body")
    used = set(o.Label for o in doc.Objects)
    multibody._keep_label(body, multibody.BODY_LABEL if multibody.BODY_LABEL not in used
                          else multibody.next_body_label(used))
    body.BaseFeature = obj
    body.Placement = obj.Placement  # el Cuerpo toma la forma SIN la ubicación del sólido (1.1.4)
    obj.Visibility = False
    doc.recompute()  # que el sólido de arranque (BaseFeature del Cuerpo) tenga su forma
    return body


def _active_body(doc):
    try:
        body = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody")
        if body is not None:
            return body
    except Exception:
        pass
    from swui.fork import multibody

    bodies = multibody.solid_bodies(doc)
    return bodies[0] if len(bodies) == 1 else None


def start(doc=None, preset=None):
    """Crear el Mover cara (con las caras ya elegidas, si hay) y abrir el panel."""
    from swui.fork import multibody

    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    if FreeCADGui.Control.activeDialog():
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), LABEL,
                                          "Cerrá primero el panel que está abierto.")
        return None
    sels = FreeCADGui.Selection.getSelectionEx(doc.Name)
    if not sels and _active_body(doc) is None:
        # como SW: el panel se abre y espera la cara (hay varios sólidos, o un sólido suelto)
        panel = _WaitFacePanel(doc)
        dp._state["panel"] = panel
        FreeCADGui.Control.showDialog(panel)
        return None
    doc.openTransaction(LABEL)
    try:
        body = _body_for(doc, sels[0].Object) if sels else _active_body(doc)
        if body is None or (body.Tip is None and body.BaseFeature is None):
            doc.abortTransaction()
            QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), LABEL,
                                              "Elegí una cara plana de la pieza (o activá un Cuerpo con sólido).")
            return None
        obj = body.newObject(PAD, "Pad")
        obj.addProperty("App::PropertyString", MARK, "SWUI", "Mover cara (fork de LikeSolidWorks UI)")
        obj.setEditorMode(MARK, 2)
        start = read_spec("")
        start["mode"] = last_mode()  # como SW: abre en el último modo usado
        start.update(preset or {})  # lo elegido en el panel que esperaba la cara
        setattr(obj, MARK, json.dumps(start, sort_keys=True))
        multibody._keep_label(obj, next_label(set(o.Label for o in doc.Objects)))
        multibody._set_tip(body, obj)
        base = obj.BaseFeature
        faces = []
        for sel in sels:
            for sub in sel.SubElementNames:
                sub = sub.split(".")[-1]
                if not sub.startswith("Face") or base is None:
                    continue
                if sel.Object in (base, body.BaseFeature) or multibody.body_of(sel.Object) is None:
                    name = sub
                else:
                    name = dp.to_base(sel.Object.Shape, sub, base.Shape)
                if name and name not in faces:
                    faces.append(name)
        FreeCADGui.Selection.clearSelection()
        panel = MoveFacePanel(obj, faces)
        dp._state["panel"] = panel
        FreeCADGui.Control.showDialog(panel)
        return obj
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Mover cara:\n%s\n" % traceback.format_exc())
        dp._state["panel"] = None
        if doc.HasPendingTransaction:
            doc.abortTransaction()
        return None


class _WaitFacePanel:
    """
    Mover cara abierto sin cara elegida: como SW, ya muestra los modos y los parámetros (lo que se
    elija acá pasa al panel de siempre), y espera la primera cara plana.
    """

    def __init__(self, doc):
        from swui import paths
        from swui.compat import QtGui

        self.doc = doc
        self.busy = False
        self.spec = read_spec("")
        self.spec["mode"] = last_mode()
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(LABEL)
        icon = paths.icon("fork/move_face")
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        box = QtWidgets.QVBoxLayout(self.form)
        top = QtWidgets.QGroupBox("Mover cara")
        tl = QtWidgets.QVBoxLayout(top)
        self.group = QtWidgets.QButtonGroup(self.form)
        for text, mode in MODES:
            radio = QtWidgets.QRadioButton(text, top)
            radio.setChecked(mode == self.spec["mode"])
            radio.toggled.connect(lambda on, m=mode: self._mode(m) if on else None)
            self.group.addButton(radio)
            tl.addWidget(radio)
        tl.addWidget(QtWidgets.QLabel("Caras (clic en la pieza):"))
        self.faces = QtWidgets.QListWidget()
        self.faces.setMaximumHeight(110)
        self.faces.setStyleSheet("QListWidget { %s }" % dp.ACTIVE_QSS)
        tl.addWidget(self.faces)
        box.addWidget(top)
        params = QtWidgets.QGroupBox("Parámetros")
        form = QtWidgets.QFormLayout(params)
        self.flip = QtWidgets.QCheckBox("Invertir dirección")
        self.distance = dp._spin(float(self.spec["distance"]), " mm", 0.001, 100000.0)
        self.deltas = [dp._spin(float(v), " mm", -100000.0, 100000.0) for v in self.spec["delta"]]
        self.angle = dp._spin(float(self.spec["angle"]), "°", 0.01, 89.99)
        self.rows = {}
        for key, text, widget in (("flip", "", self.flip), ("distance", "Distancia:", self.distance),
                                  ("dx", "ΔX:", self.deltas[0]), ("dy", "ΔY:", self.deltas[1]),
                                  ("dz", "ΔZ:", self.deltas[2]), ("angle", "Ángulo:", self.angle)):
            label = QtWidgets.QLabel(text)
            form.addRow(label, widget)
            self.rows[key] = (label, widget)
        box.addWidget(params)
        self._show_rows()
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: %s;" % dp.MISSING_COLOR)
        self.message.hide()
        box.addWidget(self.message)
        box.addStretch(1)
        self.observer = dp._PickObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Cancel

    def _mode(self, mode):
        self.spec["mode"] = mode
        remember_mode(mode)
        self._show_rows()

    def _show_rows(self):
        mode = self.spec["mode"]
        show = {"flip": True, "distance": mode == OFFSET, "dx": mode == TRANSLATE, "dy": mode == TRANSLATE,
                "dz": mode == TRANSLATE, "angle": mode == ROTATE}
        for key, (label, widget) in self.rows.items():
            label.setVisible(show[key])
            widget.setVisible(show[key])

    def preset(self):
        """Lo elegido en este panel, para el Mover cara que se arma con la primera cara."""
        return {"mode": self.spec["mode"], "flip": self.flip.isChecked(), "distance": self.distance.value(),
                "delta": [s.value() for s in self.deltas], "angle": self.angle.value()}

    def take_selection(self):
        sels = FreeCADGui.Selection.getSelectionEx(self.doc.Name)
        faces = [s for s in sels if any(n.split(".")[-1].startswith("Face") for n in s.SubElementNames)]
        if not faces:
            self.message.setText("Elegí una cara (no una arista ni un vértice).")
            self.message.show()
            self.busy = True
            try:
                FreeCADGui.Selection.clearSelection()
            finally:
                self.busy = False
            return
        preset = self.preset()
        self._close()
        FreeCADGui.Control.closeDialog()
        QtCore.QTimer.singleShot(0, lambda: start(self.doc, preset))  # la cara sigue elegida: abre el panel

    def _close(self):
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        dp._state["panel"] = None

    def reject(self):
        self._close()
        return True


class _MoveFaceCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": LABEL, "ToolTip": "Equidistanciar, trasladar o girar caras planas (como SW)",
                "Pixmap": paths.icon("fork/move_face") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        start()


def install():
    global _observer
    if _choose not in dp.CHOOSERS:
        dp.CHOOSERS.append(_choose)
    if _observer is None:
        try:
            _observer = _DocObserver()
            FreeCAD.addDocumentObserver(_observer)
        except Exception:
            _observer = None
            FreeCAD.Console.PrintLog("[SWUI fork] Mover cara, aviso de atrasados:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import tree_overlay

        if tree_text not in tree_overlay.EXTRA_TEXT:
            tree_overlay.EXTRA_TEXT.append(tree_text)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Mover cara, texto en el árbol:\n%s\n" % traceback.format_exc())
    try:
        FreeCADGui.addCommand(COMMAND, _MoveFaceCommand())
    except Exception:
        pass  # ya registrado
