# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Piezas soldadas como SW 2018: la lógica, sin interfaz (regla "panel = cara de una función").
Plan aprobado por el usuario el 07/11 (documento "Plan: piezas soldadas en FreeWorks").

Todo se arma con objetos NATIVOS de FreeCAD (decisión del usuario 01/11; FreeWorks es asistente, no
motor): cada miembro es un PartDesign::Body con
    Ruta     SubShapeBinder de la línea del croquis esqueleto (sigue al esqueleto)
    Perfil   croquis de la sección, acoplado "NormalToEdge" al principio de la Ruta
    Miembro  Pad a dos lados: largo = fórmula "<Ruta>.Shape.Length + alargue final", el otro lado =
             alargue inicial (las esquinas alargan el miembro que pasa)
y los recortes son operaciones nativas dentro del Cuerpo:
    a tope / T / ajuste a otro miembro: Pocket con la ENVOLVENTE (contorno exterior lleno) del otro
             miembro, barrida por su misma Ruta y con sus mismos largos (fórmulas): sigue sola;
    inglete y recorte contra una cara: SubtractiveBox del lado a sacar (inglete: acoplado al vértice
             de la esquina; cara: a la cara). El ángulo del inglete se calcula al crearlo.

Nombres guardados en los archivos (estables, no cambiar): propiedades SWUI_WeldMember,
SWUI_WeldKind, SWUI_WeldSize, SWUI_WeldDims, SWUI_WeldRotation, SWUI_WeldAnchor, SWUI_WeldMirror,
SWUI_WeldCorner, SWUI_WeldPart ("tapa", "cartela").

Funciones públicas:
    profile_names(), sizes(kind), profile_loops(kind, dims), area(kind, dims)
    create_members(doc, edges, kind, size, rotation=0, anchor="Centro", mirror=False) -> [Cuerpo]
    find_corners(members), apply_corner(corner, treatment, passing=None), remove_corner(...)
    corner_state(corner), set_profile(bodies, rotation=None, anchor=None)
    edit_members(group, edges, kind, size, rotation, anchor, mirror, treatment=None), route_edge(body)
    trim_to_member(member, tool), trim_to_face(member, (obj, "FaceN")), extend_to_face(...)
    cut_list(doc) -> filas, cut_list_csv(rows), cut_list_sheet(doc, rows)
    end_cap(member, end, thickness, inset), gusset(a, b, size, thickness)
"""

import math

import FreeCAD

V = FreeCAD.Vector
TOL = 1e-4
STEEL = 7.85e-6  # kg/mm³: si la pieza no tiene material, se pesa como acero (decisión 07/11)

# --- Tabla de perfiles (mercado argentino; decisión de Claude 07/11, ajustable) -------------------

INCH = 25.4
SQUARE = (15, 20, 25, 30, 40, 50, 60, 70, 80, 100)
RECT = ((20, 10), (30, 20), (40, 20), (50, 30), (60, 40), (80, 40), (100, 50))
WALLS = (0.9, 1.25, 1.6, 2.0, 2.5, 3.2)
ROUND = (("1/2\"", 12.7), ("5/8\"", 15.875), ("3/4\"", 19.05), ("7/8\"", 22.225), ("1\"", 25.4),
         ("1 1/4\"", 31.75), ("1 1/2\"", 38.1), ("2\"", 50.8), ("2 1/2\"", 63.5), ("3\"", 76.2))
ROUND_WALLS = (1.25, 1.6, 2.0, 2.5, 3.2)
ANGLES = (("3/4\"", 0.75), ("7/8\"", 0.875), ("1\"", 1.0), ("1 1/4\"", 1.25), ("1 1/2\"", 1.5),
          ("2\"", 2.0), ("2 1/2\"", 2.5), ("3\"", 3.0))
THICK = (("1/8\"", 0.125), ("3/16\"", 0.1875), ("1/4\"", 0.25))
FLATS = (("3/4\"", 0.75), ("1\"", 1.0), ("1 1/4\"", 1.25), ("1 1/2\"", 1.5), ("2\"", 2.0),
         ("2 1/2\"", 2.5), ("3\"", 3.0), ("4\"", 4.0))
FLAT_THICK = THICK + (("5/16\"", 0.3125),)
UPN = ((80, 45, 6.0, 8.0), (100, 50, 6.0, 8.5), (120, 55, 7.0, 9.0), (140, 60, 7.0, 10.0),
       (160, 65, 7.5, 10.5), (200, 75, 8.5, 11.5))  # h, b, alma, ala (DIN 1026, sin radios)

KINDS = ("Caño cuadrado", "Caño rectangular", "Caño redondo", "Ángulo", "Planchuela", "UPN")


def _fmt(x):
    s = ("%.2f" % x).rstrip("0").rstrip(".")
    return s.replace(".", ",")


def profile_names():
    return KINDS


def sizes(kind):
    """[(nombre, dims)] de un tipo de perfil. dims en mm."""
    out = []
    if kind == "Caño cuadrado":
        for a in SQUARE:
            for t in WALLS:
                if t < a / 4:
                    out.append(("%dx%dx%s" % (a, a, _fmt(t)), [a, a, t]))
    elif kind == "Caño rectangular":
        for b, h in RECT:
            for t in WALLS:
                if t < h / 4:
                    out.append(("%dx%dx%s" % (b, h, _fmt(t)), [b, h, t]))
    elif kind == "Caño redondo":
        for name, d in ROUND:
            for t in ROUND_WALLS:
                if t < d / 4:
                    out.append(("%s (%s mm) x %s" % (name, _fmt(d), _fmt(t)), [d, t]))
    elif kind == "Ángulo":
        for name, a in ANGLES:
            for tn, t in THICK:
                if t < a / 3:
                    out.append(("%s x %s" % (name, tn), [a * INCH, t * INCH]))
    elif kind == "Planchuela":
        for name, b in FLATS:
            for tn, t in FLAT_THICK:
                if t < b / 2:
                    out.append(("%s x %s" % (name, tn), [b * INCH, t * INCH]))
    elif kind == "UPN":
        for h, b, tw, tf in UPN:
            out.append(("UPN %d" % h, [h, b, tw, tf]))
    return out


def dims_of(kind, size):
    for name, d in sizes(kind):
        if name == size:
            return list(d)
    raise ValueError("Perfil desconocido: %s %s" % (kind, size))


def _rect(x0, y0, x1, y1):
    return [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]


def profile_loops(kind, dims, outer_only=False):
    """Contornos de la sección centrados en su rectángulo envolvente: [("poly", [puntos]) |
    ("circle", radio)]. outer_only: solo el contorno de afuera (la envolvente llena)."""
    if kind in ("Caño cuadrado", "Caño rectangular"):
        b, h, t = dims
        loops = [("poly", _rect(-b / 2, -h / 2, b / 2, h / 2))]
        if not outer_only:
            loops.append(("poly", _rect(-b / 2 + t, -h / 2 + t, b / 2 - t, h / 2 - t)))
        return loops
    if kind == "Caño redondo":
        d, t = dims
        loops = [("circle", d / 2)]
        if not outer_only:
            loops.append(("circle", d / 2 - t))
        return loops
    if kind == "Ángulo":
        a, t = dims
        h = a / 2
        if outer_only:
            return [("poly", _rect(-h, -h, h, h))]
        return [("poly", [V(-h, -h, 0), V(h, -h, 0), V(h, -h + t, 0), V(-h + t, -h + t, 0),
                          V(-h + t, h, 0), V(-h, h, 0)])]
    if kind == "Planchuela":
        b, t = dims
        return [("poly", _rect(-b / 2, -t / 2, b / 2, t / 2))]
    if kind == "UPN":
        h, b, tw, tf = dims
        x0, x1, y0, y1 = -b / 2, b / 2, -h / 2, h / 2
        if outer_only:
            return [("poly", _rect(x0, y0, x1, y1))]
        return [("poly", [V(x0, y0, 0), V(x1, y0, 0), V(x1, y0 + tf, 0), V(x0 + tw, y0 + tf, 0),
                          V(x0 + tw, y1 - tf, 0), V(x1, y1 - tf, 0), V(x1, y1, 0), V(x0, y1, 0)])]
    raise ValueError(kind)


def extent(kind, dims):
    """(ancho en X, alto en Y) del perfil."""
    if kind in ("Caño cuadrado", "Caño rectangular"):
        return dims[0], dims[1]
    if kind == "Caño redondo":
        return dims[0], dims[0]
    if kind == "Ángulo":
        return dims[0], dims[0]
    if kind == "Planchuela":
        return dims[0], dims[1]
    if kind == "UPN":
        return dims[1], dims[0]
    return 0, 0


def area(kind, dims):
    """Área de la sección (mm²), para el peso por metro."""
    import Part

    faces = []
    for typ, data in profile_loops(kind, dims):
        if typ == "circle":
            faces.append(Part.Face(Part.Wire(Part.makeCircle(data))))
        else:
            faces.append(Part.Face(Part.makePolygon(data + [data[0]])))
    a = faces[0].Area
    for f in faces[1:]:
        a -= f.Area
    return a


ANCHORS = ("Centro", "Arriba", "Abajo", "Izquierda", "Derecha",
           "Arriba izquierda", "Arriba derecha", "Abajo izquierda", "Abajo derecha")


def _anchor_point(anchor, w, h):
    x = -w / 2 if "izquierda" in anchor.lower() else (w / 2 if "derecha" in anchor.lower() else 0)
    y = h / 2 if anchor.startswith("Arriba") else (-h / 2 if anchor.startswith("Abajo") else 0)
    return V(x, y, 0)


# --- Miembros -------------------------------------------------------------------------------------


def _add_prop(obj, name, typ, value, group="Pieza soldada", doc=""):
    if not hasattr(obj, name):
        obj.addProperty(typ, name, group, doc)
        try:
            obj.setEditorMode(name, 2)
        except Exception:
            pass
    setattr(obj, name, value)


def _fill_sketch(sk, loops, mirror=False):
    import Part

    for typ, data in loops:
        if typ == "circle":
            sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), data))
            continue
        pts = [V(-p.x, p.y, 0) if mirror else p for p in data]
        n = len(pts)
        first = sk.GeometryCount
        for i in range(n):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % n]))
        import Sketcher

        for i in range(n):
            sk.addConstraint(Sketcher.Constraint("Coincident", first + i, 2, first + (i + 1) % n, 1))


def _edge_of(obj, sub):
    return obj.getSubObject(sub)


def frame_normal(obj, sub):
    """Normal del plano del esqueleto (croquis) donde está la línea."""
    try:
        if obj.isDerivedFrom("Sketcher::SketchObject"):
            return obj.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
    except Exception:
        pass
    return V(0, 0, 1)


def _profile_rotation(sketch_pl, normal, edge_dir):
    """Ángulo (grados) alrededor del eje del miembro para que el "arriba" del perfil quede hacia la
    normal del esqueleto (como SW: el perfil apoyado en el plano del croquis)."""
    n = V(normal)
    n = n - edge_dir * n.dot(edge_dir)
    if n.Length < 1e-6:
        n = V(0, 0, 1) - edge_dir * edge_dir.z
        if n.Length < 1e-6:
            n = V(0, 1, 0) - edge_dir * edge_dir.y
    n.normalize()
    xl = sketch_pl.Rotation.multVec(V(1, 0, 0))
    yl = sketch_pl.Rotation.multVec(V(0, 1, 0))
    return math.degrees(math.atan2(-n.dot(xl), n.dot(yl)))


def _route_of(body):
    """La Ruta del miembro: el primer SubShapeBinder del Cuerpo (se busca por cómo está armado, no
    por el nombre: FreeWorks les cambia el nombre a los croquis y operaciones nuevos, como SW)."""
    for o in body.Group:
        if o.TypeId == "PartDesign::SubShapeBinder":
            return o
    return None


def _profile_of(body):
    """El croquis del perfil: acoplado a la Ruta y usado por la extrusión del miembro."""
    pad = _pad_of(body)
    if pad is not None and pad.Profile:
        prof = pad.Profile[0] if isinstance(pad.Profile, tuple) else pad.Profile
        return prof
    return None


def _pad_of(body):
    """La extrusión del miembro: el primer Pad del Cuerpo."""
    for o in body.Group:
        if o.TypeId == "PartDesign::Pad":
            return o
    return None


def is_member(obj):
    return bool(getattr(obj, "SWUI_WeldMember", False))


def members(doc):
    return [o for o in doc.Objects if is_member(o)]


def set_extension(body, start=None, end=None):
    """Alargue (mm) del miembro en su punta inicial y/o final."""
    pad, route = _pad_of(body), _route_of(body)
    if start is not None:
        pad.Length2 = max(0.0, float(start))
    if end is not None:
        pad.setExpression("Length", "%s.Shape.Length + %s" % (route.Name, repr(round(float(end), 6))))


def extension(body):
    """(alargue inicial, alargue final)."""
    pad, route = _pad_of(body), _route_of(body)
    e1 = 0.0
    for prop, expr in pad.ExpressionEngine:
        if prop == "Length" and "+" in expr:
            try:
                e1 = float(expr.split("+")[-1])
            except ValueError:
                pass
    return float(pad.Length2), e1


def create_member(doc, edge, kind, size, rotation=0.0, anchor="Centro", mirror=False, label=None):
    """Un miembro estructural sobre una línea del esqueleto. edge = (objeto, "EdgeN")."""
    obj, sub = edge
    dims = dims_of(kind, size)
    body = doc.addObject("PartDesign::Body", "Miembro")
    body.Label = label or "%s %s" % (kind, size)
    route = body.newObject("PartDesign::SubShapeBinder", "Ruta")
    route.Label = "Ruta"
    route.Support = [(obj, (sub,))]
    try:
        route.ViewObject.Visibility = False
    except Exception:
        pass
    sk = body.newObject("Sketcher::SketchObject", "Perfil")
    sk.Label = "Perfil"
    sk.AttachmentSupport = [(route, "Edge1")]
    sk.MapMode = "NormalToEdge"
    sk.MapPathParameter = 0.0
    _fill_sketch(sk, profile_loops(kind, dims), mirror)
    doc.recompute()
    e = route.Shape.Edges[0]
    d = e.Vertexes[-1].Point - e.Vertexes[0].Point
    d.normalize()
    auto = _profile_rotation(sk.Placement, frame_normal(obj, sub), d)
    w, h = extent(kind, dims)
    rot = FreeCAD.Rotation(V(0, 0, 1), auto + float(rotation))
    base = rot.multVec(_anchor_point(anchor, w, h)) * -1
    sk.AttachmentOffset = FreeCAD.Placement(base, rot)
    pad = body.newObject("PartDesign::Pad", "Miembro")
    pad.Label = "Miembro"
    pad.Profile = sk
    pad.SideType = "Two sides"
    pad.Type = "Length"
    pad.Type2 = "Length"
    pad.Reversed = True
    pad.Length2 = 0.0
    pad.setExpression("Length", "%s.Shape.Length + 0.0" % route.Name)
    try:
        sk.ViewObject.Visibility = False
    except Exception:
        pass
    _add_prop(body, "SWUI_WeldMember", "App::PropertyBool", True)
    _add_prop(body, "SWUI_WeldKind", "App::PropertyString", kind)
    _add_prop(body, "SWUI_WeldSize", "App::PropertyString", size)
    _add_prop(body, "SWUI_WeldDims", "App::PropertyFloatList", [float(x) for x in dims])
    _add_prop(body, "SWUI_WeldRotation", "App::PropertyFloat", float(rotation))
    _add_prop(body, "SWUI_WeldAnchor", "App::PropertyString", anchor)
    _add_prop(body, "SWUI_WeldMirror", "App::PropertyBool", bool(mirror))
    doc.recompute()
    return body


def create_members(doc, edges, kind, size, rotation=0.0, anchor="Centro", mirror=False, group_label=None):
    """Miembro estructural (como SW): un Cuerpo por línea, todos en una carpeta "Miembro
    estructuralN". Devuelve los Cuerpos."""
    n = 1 + sum(1 for o in doc.Objects if o.TypeId == "App::DocumentObjectGroup"
                and o.Label.startswith("Miembro estructural"))
    group = doc.addObject("App::DocumentObjectGroup", "MiembroEstructural")
    group.Label = group_label or "Miembro estructural%d" % n
    bodies = []
    for i, edge in enumerate(edges):
        b = create_member(doc, edge, kind, size, rotation, anchor, mirror,
                          label="%s %s (%d)" % (kind, size, i + 1))
        group.addObject(b)
        bodies.append(b)
    doc.recompute()
    return bodies


# --- Geometría de un miembro ----------------------------------------------------------------------


def axis(body):
    """(inicio, fin, dirección unitaria) de la línea del miembro, en coordenadas del documento."""
    e = _route_of(body).Shape.Edges[0]
    pl = body.getGlobalPlacement() if hasattr(body, "getGlobalPlacement") else body.Placement
    a, b = pl.multVec(e.Vertexes[0].Point), pl.multVec(e.Vertexes[-1].Point)
    d = b - a
    d.normalize()
    return a, b, d


def profile_axes(body):
    """(X, Y) del perfil en coordenadas del documento."""
    sk = _profile_of(body)
    r = sk.getGlobalPlacement().Rotation
    return r.multVec(V(1, 0, 0)), r.multVec(V(0, 1, 0))


def half_extent(body, direction):
    """Media medida del perfil del miembro a lo largo de una dirección perpendicular a él."""
    w, h = extent(body.SWUI_WeldKind, list(body.SWUI_WeldDims))
    xl, yl = profile_axes(body)
    d = V(direction)
    if d.Length < 1e-9:
        return 0.0
    d.normalize()
    return abs(d.dot(xl)) * w / 2 + abs(d.dot(yl)) * h / 2


# --- Esquinas ---------------------------------------------------------------------------------------


def find_corners(bodies, tol=0.01):
    """Esquinas entre miembros: [{"a", "b", "kind": "L"|"T", "point", "end_a", "end_b"}].
    L: dos puntas que se tocan; T: la punta de b sobre el medio de a (end_a None)."""
    out = []
    data = [(b,) + axis(b) for b in bodies]
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            A, a0, a1, da = data[i]
            B, b0, b1, db = data[j]
            if abs(abs(da.dot(db)) - 1) < 1e-6:
                continue  # paralelos (en línea): no es esquina
            done = False
            for ea, pa in ((0, a0), (1, a1)):
                for eb, pb in ((0, b0), (1, b1)):
                    if (pa - pb).Length < tol:
                        out.append({"a": A, "b": B, "kind": "L", "point": V(pa), "end_a": ea, "end_b": eb})
                        done = True
            if done:
                continue
            for (P, p0, p1, dp), (Q, q0, q1, dq) in (((A, a0, a1, da), (B, b0, b1, db)),
                                                     ((B, b0, b1, db), (A, a0, a1, da))):
                for eq, pq in ((0, q0), (1, q1)):
                    t = (pq - p0).dot(dp)
                    off = (pq - (p0 + dp * t)).Length
                    if off < tol and tol < t < (p1 - p0).Length - tol:
                        out.append({"a": P, "b": Q, "kind": "T", "point": V(pq), "end_a": None, "end_b": eq})
    return out


def _away(body, end):
    """Dirección desde la punta `end` hacia el resto del miembro."""
    a, b, d = axis(body)
    return d if end == 0 else d * -1


def _corner_id(a, b):
    return "%s|%s" % tuple(sorted((a.Name, b.Name)))


def _tag(obj, cid):
    _add_prop(obj, "SWUI_WeldCorner", "App::PropertyString", cid)


def remove_corner(a, b):
    """Sacar el tratamiento de esquina entre dos miembros (operaciones y alargues)."""
    cid = _corner_id(a, b)
    doc = a.Document
    for body in (a, b):
        for o in list(body.Group):
            if getattr(o, "SWUI_WeldCorner", "") == cid:
                body.removeObject(o)
                doc.removeObject(o.Name)
        tags = _ext_tags(body)
        if cid in tags:
            end = tags.pop(cid)[0]
            _set_ext_tags(body, tags)
            _apply_ext(body, end, tags)
    doc.recompute()


def _ext_tags(body):
    """{esquina: (punta, alargue)} de SWUI_WeldExtTags ("esquina=punta@alargue;..."). Los archivos
    anteriores al 07/11 guardaban solo "esquina=punta": alargue None (desconocido)."""
    raw = getattr(body, "SWUI_WeldExtTags", "") or ""
    out = {}
    for item in raw.split(";"):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        end, _sep, val = v.partition("@")
        try:
            out[k] = (int(end), float(val) if val else None)
        except ValueError:
            continue
    return out


def _set_ext_tags(body, tags):
    items = []
    for k, (end, val) in tags.items():
        items.append("%s=%d" % (k, end) if val is None else "%s=%d@%s" % (k, end, repr(round(val, 6))))
    _add_prop(body, "SWUI_WeldExtTags", "App::PropertyString", ";".join(items))


def _apply_ext(body, end, tags):
    """Alargue de una punta = el MAYOR de los que piden sus esquinas: en una esquina de tres caños
    (dos largueros y la pata) la misma punta la usan dos esquinas, y cambiar una no debe acortar la
    otra (arreglado 07/11). Con alargues viejos sin valor guardado, la punta queda como está."""
    vals = [v for e, v in tags.values() if e == end]
    if any(v is None for v in vals):
        return
    value = max(vals) if vals else 0.0
    if end == 0:
        set_extension(body, start=value)
    else:
        set_extension(body, end=value)


def _extend_for(body, end, value, cid):
    tags = _ext_tags(body)
    tags[cid] = (end, float(value))
    _set_ext_tags(body, tags)
    vals = [v for e, v in tags.values() if e == end]
    if any(v is None for v in vals):
        # archivo viejo: no se sabe cuánto pedía la otra esquina; nunca acortar
        current = extension(body)[0 if end == 0 else 1]
        value = max(float(value), current)
        if end == 0:
            set_extension(body, start=value)
        else:
            set_extension(body, end=value)
        return
    _apply_ext(body, end, tags)


def _envelope_cut(target, tool, cid):
    """En `target`, sacar la envolvente llena del miembro `tool` (barrida por su Ruta, con sus largos)."""
    doc = target.Document
    troute, tpad, tsk = _route_of(tool), _pad_of(tool), _profile_of(tool)
    b = target.newObject("PartDesign::SubShapeBinder", "RutaRecorte")
    b.Label = "Ruta de " + tool.Label
    b.Support = [(troute, ("Edge1",))]
    try:
        b.ViewObject.Visibility = False
    except Exception:
        pass
    sk = target.newObject("Sketcher::SketchObject", "Envolvente")
    sk.Label = "Envolvente de " + tool.Label
    sk.AttachmentSupport = [(b, "Edge1")]
    sk.MapMode = "NormalToEdge"
    sk.MapPathParameter = 0.0
    sk.AttachmentOffset = tsk.AttachmentOffset
    _fill_sketch(sk, profile_loops(tool.SWUI_WeldKind, list(tool.SWUI_WeldDims), outer_only=True),
                 bool(getattr(tool, "SWUI_WeldMirror", False)))
    pk = target.newObject("PartDesign::Pocket", "Recorte")
    pk.Label = "Recorte contra " + tool.Label
    pk.Profile = sk
    pk.SideType = "Two sides"
    pk.Type = "Length"
    pk.Type2 = "Length"
    pk.setExpression("Length", "%s.Length" % tpad.Name)
    pk.setExpression("Length2", "%s.Length2" % tpad.Name)
    for o in (b, sk, pk):
        _tag(o, cid)
    try:
        sk.ViewObject.Visibility = False
    except Exception:
        pass
    return pk


def _box_cut(target, vertex_end, normal_out, size, cid, label):
    """En `target`, una caja que saca todo lo que está del lado `normal_out` del plano que pasa por
    la punta `vertex_end` de su Ruta (inglete)."""
    # ubicada al crearla (en modo "Translate" FreeCAD descarta el giro de la caja, medido 07/11)
    a0, a1, _d = axis(target)
    corner = a0 if vertex_end == 0 else a1
    box = target.newObject("PartDesign::SubtractiveBox", "Inglete")
    box.Label = label
    box.Length = box.Width = box.Height = size
    rot = FreeCAD.Rotation(V(0, 0, 1), normal_out)
    inv = target.getGlobalPlacement().inverse() if hasattr(target, "getGlobalPlacement") else FreeCAD.Placement()
    box.Placement = inv.multiply(FreeCAD.Placement(corner + rot.multVec(V(-size / 2, -size / 2, 0)), rot))
    _tag(box, cid)
    return box


def butt_extension(passing, end_p, other, end_o=None):
    """Alargue del miembro que pasa para llegar a la cara de afuera del otro (a tope)."""
    u = _away(passing, end_p)
    if end_o is None:
        a, b, v = axis(other)
    else:
        v = _away(other, end_o)
    cos = max(-1.0, min(1.0, u.dot(v)))
    theta = math.acos(cos)
    s = math.sin(theta)
    if s < 1e-6:
        return 0.0
    d_o = u - v * u.dot(v)  # perpendicular al otro, del lado del que pasa
    d_p = v - u * u.dot(v)
    half_o = half_extent(other, d_o)
    half_p = half_extent(passing, d_p)
    return half_o / s + half_p * abs(cos) / s


def apply_corner(corner, treatment="tope", passing=None):
    """Tratamiento de una esquina (como SW): "tope" (el que pasa se alarga hasta la cara de afuera
    y el otro se corta contra él), "inglete" (los dos a 45° o a la bisectriz) o "ninguno".
    En una T siempre es a tope con el que pasa por el medio."""
    a, b = corner["a"], corner["b"]
    remove_corner(a, b)
    cid = _corner_id(a, b)
    doc = a.Document
    if treatment == "ninguno":
        return
    if corner["kind"] == "T":
        _envelope_cut(b, a, cid)
        doc.recompute()
        return
    if treatment == "inglete":
        ua, ub = _away(a, corner["end_a"]), _away(b, corner["end_b"])
        big = 2 * max(extent(a.SWUI_WeldKind, list(a.SWUI_WeldDims)) + extent(b.SWUI_WeldKind,
                                                                              list(b.SWUI_WeldDims)))
        theta = math.acos(max(-1.0, min(1.0, ua.dot(ub))))
        ext = big / max(0.2, math.sin(theta / 2))
        m = ua - ub
        m.normalize()
        _extend_for(a, corner["end_a"], ext, cid)
        _extend_for(b, corner["end_b"], ext, cid)
        size = 4 * ext + 200
        _box_cut(a, corner["end_a"], m * -1, size, cid, "Inglete con " + b.Label)
        _box_cut(b, corner["end_b"], m, size, cid, "Inglete con " + a.Label)
        doc.recompute()
        return
    # a tope: pasa el más largo salvo que se diga otro
    if passing is None:
        la = (axis(a)[1] - axis(a)[0]).Length
        lb = (axis(b)[1] - axis(b)[0]).Length
        passing = a if la >= lb else b
    other = b if passing == a else a
    end_p = corner["end_a"] if passing == a else corner["end_b"]
    end_o = corner["end_b"] if passing == a else corner["end_a"]
    _extend_for(passing, end_p, butt_extension(passing, end_p, other, end_o), cid)
    doc.recompute()
    _envelope_cut(other, passing, cid)
    doc.recompute()


def corner_state(corner):
    """(tratamiento, el que pasa) que tiene hoy una esquina, leído de sus operaciones; None si no
    tiene ninguno."""
    a, b = corner["a"], corner["b"]
    cid = _corner_id(a, b)
    feats = [(body, o) for body in (a, b) for o in body.Group if getattr(o, "SWUI_WeldCorner", "") == cid]
    if not feats:
        return None
    if any(o.TypeId == "PartDesign::SubtractiveBox" for _b, o in feats):
        return "inglete", None
    if corner["kind"] == "T":
        return "tope", a
    cut_in = [body for body, o in feats if o.TypeId == "PartDesign::Pocket"]
    if not cut_in:
        return None
    return "tope", (b if cut_in[0] == a else a)


def _envelopes_of(body):
    """Croquis de envolvente que OTROS miembros usan para recortarse contra `body`."""
    route = _route_of(body)
    sk = _profile_of(body)
    out = []
    for o in body.Document.Objects:
        if o is sk or o.TypeId != "Sketcher::SketchObject" or not o.AttachmentSupport:
            continue
        binder = o.AttachmentSupport[0][0]
        if binder.TypeId == "PartDesign::SubShapeBinder" and binder.Support and binder.Support[0][0] == route:
            out.append(o)
    return out


def _refill(sk, loops, mirror):
    try:
        sk.deleteAllGeometry()
    except Exception:
        for i in reversed(range(sk.GeometryCount)):
            sk.delGeometry(i)
    _fill_sketch(sk, loops, mirror)


def _reshape(body, kind=None, size=None, rotation=None, anchor=None, mirror=None):
    """Cambiar en su lugar el perfil de un miembro (tipo, tamaño, giro, ubicación, simetría) y las
    envolventes que otros usan para recortarse contra él. Sin tocar las esquinas."""
    sk = _profile_of(body)
    old_kind, old_size = body.SWUI_WeldKind, body.SWUI_WeldSize
    old_rot = float(getattr(body, "SWUI_WeldRotation", 0.0))
    old_mirror = bool(getattr(body, "SWUI_WeldMirror", False))
    kind = kind or old_kind
    size = size or old_size
    new_rot = old_rot if rotation is None else float(rotation)
    new_anchor = anchor or getattr(body, "SWUI_WeldAnchor", "Centro")
    new_mirror = old_mirror if mirror is None else bool(mirror)
    dims = list(body.SWUI_WeldDims) if (kind, size) == (old_kind, old_size) else [float(x) for x in dims_of(kind, size)]
    envelopes = _envelopes_of(body)
    if (kind, size, new_mirror) != (old_kind, old_size, old_mirror):
        _refill(sk, profile_loops(kind, dims), new_mirror)
        for env in envelopes:
            _refill(env, profile_loops(kind, dims, outer_only=True), new_mirror)
        old_name = "%s %s" % (old_kind, old_size)
        if body.Label.startswith(old_name):
            body.Label = "%s %s%s" % (kind, size, body.Label[len(old_name):])
        for env in envelopes:  # "Envolvente de <miembro>" y su recorte siguen el nombre nuevo
            env.Label = "Envolvente de " + body.Label
    yaw = sk.AttachmentOffset.Rotation.toEuler()[0]
    auto = yaw - old_rot  # el giro que el perfil necesita para apoyarse en el esqueleto
    w, h = extent(kind, dims)
    rot = FreeCAD.Rotation(V(0, 0, 1), auto + new_rot)
    sk.AttachmentOffset = FreeCAD.Placement(rot.multVec(_anchor_point(new_anchor, w, h)) * -1, rot)
    for env in envelopes:
        env.AttachmentOffset = sk.AttachmentOffset
    _add_prop(body, "SWUI_WeldKind", "App::PropertyString", kind)
    _add_prop(body, "SWUI_WeldSize", "App::PropertyString", size)
    _add_prop(body, "SWUI_WeldDims", "App::PropertyFloatList", [float(x) for x in dims])
    _add_prop(body, "SWUI_WeldRotation", "App::PropertyFloat", new_rot)
    _add_prop(body, "SWUI_WeldAnchor", "App::PropertyString", new_anchor)
    _add_prop(body, "SWUI_WeldMirror", "App::PropertyBool", new_mirror)


def _redo_corners(doc, bodies, treatment=None, new=()):
    """Rehacer las esquinas de esos miembros: con `treatment` todas iguales; sin él, cada una con el
    que tenía; las de un miembro recién agregado (nombres en `new`), a tope como SW.
    Primero se sacan todas y después se rehacen: así una punta compartida por dos esquinas vuelve a
    cero antes de medirla de nuevo (también en archivos viejos sin el alargue guardado)."""
    names = set(b.Name for b in bodies)
    todo = []
    for c in find_corners(members(doc)):
        if c["a"].Name not in names and c["b"].Name not in names:
            continue
        state = corner_state(c)
        if treatment is not None and c["a"].Name in names and c["b"].Name in names:
            state = (treatment, None)
        elif state is None and (c["a"].Name in new or c["b"].Name in new):
            state = ("tope", None)
        if state is not None:
            todo.append((c, state))
    for c, _state in todo:
        remove_corner(c["a"], c["b"])
    for c, (treat, passing) in todo:
        apply_corner(c, treat, passing)
    doc.recompute()


def set_profile(bodies, rotation=None, anchor=None):
    """Cambiar "Girar ángulo" (grados) y/o "Ubicar perfil" de miembros ya hechos. Gira el perfil en
    su lugar (y las envolventes que otros miembros usan para recortarse contra él) y rehace las
    esquinas de esos miembros con el mismo tratamiento que tenían."""
    if not bodies:
        return
    doc = bodies[0].Document
    for body in bodies:
        _reshape(body, rotation=rotation, anchor=anchor)
    doc.recompute()
    _redo_corners(doc, bodies)


def route_edge(body):
    """(objeto, "EdgeN") de la línea del esqueleto sobre la que está el miembro."""
    sup = _route_of(body).Support
    obj, subs = sup[0]
    return obj, (subs[0] if isinstance(subs, (tuple, list)) else subs)


def _forget(body):
    """Sacar de los otros miembros todo lo que depende de `body` (esquinas, recortes contra él)."""
    doc = body.Document
    for c in find_corners(members(doc)):
        if body in (c["a"], c["b"]):
            remove_corner(c["a"], c["b"])
    for other in members(doc):
        if other is body:
            continue
        for o in list(other.Group):
            cid = getattr(o, "SWUI_WeldCorner", "")
            if cid.startswith("trim|") and body.Name in cid.split("|"):
                other.removeObject(o)
                doc.removeObject(o.Name)
        tags = _ext_tags(other)
        gone = [k for k in tags if k.startswith("trim|") and body.Name in k.split("|")]
        for k in gone:
            end = tags.pop(k)[0]
            _set_ext_tags(other, tags)
            _apply_ext(other, end, tags)
    doc.recompute()


def edit_members(group, edges, kind, size, rotation=0.0, anchor="Centro", mirror=False, treatment=None):
    """Editar operación de un Miembro estructural ya hecho, como SW: mismas opciones que al crearlo.
    `group` = la carpeta "Miembro estructuralN"; `edges` = las líneas del esqueleto que quedan (las
    que se sacan borran su caño, las nuevas lo agregan); los caños que siguen se cambian EN SU LUGAR
    (no se borran: las tapas, cartelas y recortes apoyados en ellos no se pierden). `treatment`:
    "tope", "inglete", "ninguno" o None (cada esquina como estaba; las nuevas, a tope).
    Devuelve los miembros de la carpeta."""
    doc = group.Document
    current = [m for m in group.Group if is_member(m)]
    keys = [(o.Name, sub) for o, sub in edges]
    keep, drop = [], []
    for m in current:
        try:
            obj, sub = route_edge(m)
            key = (obj.Name, sub)
        except Exception:
            key = None
        (keep if key in keys else drop).append(m)
    for m in drop:
        _forget(m)
        group.removeObject(m)
        m.removeObjectsFromDocument()
        doc.removeObject(m.Name)
    have = []
    for m in keep:
        obj, sub = route_edge(m)
        have.append((obj.Name, sub))
    for m in keep:
        _reshape(m, kind, size, rotation, anchor, mirror)
    doc.recompute()
    n = len(current)
    new = set()
    for o, sub in edges:
        if (o.Name, sub) in have:
            continue
        n += 1
        b = create_member(doc, (o, sub), kind, size, rotation, anchor, mirror,
                          label="%s %s (%d)" % (kind, size, n))
        group.addObject(b)
        new.add(b.Name)
    bodies = [m for m in group.Group if is_member(m)]
    _redo_corners(doc, bodies, treatment, new)
    return bodies


def apply_corners(bodies, treatment="tope"):
    """Todas las esquinas entre esos miembros con el mismo tratamiento."""
    corners = find_corners(bodies)
    for c in corners:
        apply_corner(c, treatment)
    return corners


# --- Recortar / Alargar ---------------------------------------------------------------------------


def _near_end(body, point):
    a, b, d = axis(body)
    return 0 if (point - a).Length <= (point - b).Length else 1


def trim_to_member(member, tool, extend=True):
    """Recortar (y alargar si no llega) `member` contra el miembro `tool`: ajuste exacto (cuerpo)."""
    a0, a1, da = axis(member)
    b0, b1, db = axis(tool)
    # punto de la línea de `member` más cercano a la línea de `tool`
    w0 = a0 - b0
    aa, bb, cc = da.dot(da), da.dot(db), db.dot(db)
    dd, ee = da.dot(w0), db.dot(w0)
    den = aa * cc - bb * bb
    cid = "trim|%s|%s" % (member.Name, tool.Name)
    if abs(den) > 1e-9:
        s = (bb * ee - cc * dd) / den
        hit = a0 + da * s
        length = (a1 - a0).Length
        end = 0 if s < length / 2 else 1
        need = -s if end == 0 else s - length
        # solo si no llega: hasta el eje del otro (la envolvente saca lo que sobra). Más allá dejaba un
        # pedacito suelto del otro lado del caño (visto con guion, 07/11)
        if extend and need > 1e-6:
            _extend_for(member, end, need, cid)
    _envelope_cut(member, tool, cid)
    member.Document.recompute()


def _face_plane(obj, sub):
    f = obj.getSubObject(sub)
    if f is None or f.ShapeType != "Face" or f.Surface.__class__.__name__ != "Plane":
        raise ValueError("Elegí una cara plana")
    u0, u1, v0, v1 = f.ParameterRange
    return f.CenterOfMass, f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)


def trim_to_face(member, face, extend=True):
    """Recortar (y alargar si no llega) `member` contra una cara plana: corte recto en el plano."""
    obj, sub = face
    p, n = _face_plane(obj, sub)
    a0, a1, d = axis(member)
    cid = "trim|%s|%s.%s" % (member.Name, obj.Name, sub)
    den = d.dot(n)
    end = None
    if abs(den) > 1e-9:
        t = (p - a0).dot(n) / den
        length = (a1 - a0).Length
        end = 0 if t < length / 2 else 1
        need = -t if end == 0 else t - length
        if extend and need > 0:
            # más el pedazo del perfil inclinado que todavía no llega al plano
            w, h = extent(member.SWUI_WeldKind, list(member.SWUI_WeldDims))
            _extend_for(member, end, need + max(w, h) * 2, cid)
    # lado a sacar: el que no tiene el medio del miembro
    mid = (a0 + a1) * 0.5
    out = n if (mid - p).dot(n) < 0 else n * -1
    b = member.newObject("PartDesign::SubShapeBinder", "CaraRecorte")
    b.Label = "Cara de recorte"
    b.Support = [(obj, (sub,))]
    try:
        b.ViewObject.Visibility = False
    except Exception:
        pass
    w, h = extent(member.SWUI_WeldKind, list(member.SWUI_WeldDims))
    size = 4 * (max(w, h) + 100)
    box = member.newObject("PartDesign::SubtractiveBox", "Recorte")
    box.Label = "Recorte contra cara"
    box.Length = box.Width = box.Height = size
    box.AttachmentSupport = [(b, "Face1")]
    box.MapMode = "FlatFace"
    member.Document.recompute()
    # FlatFace pone Z según la normal de la cara: girar si el lado a sacar es el otro
    z = box.Placement.Rotation.multVec(V(0, 0, 1))
    flip = FreeCAD.Rotation(V(1, 0, 0), 180) if z.dot(out) < 0 else FreeCAD.Rotation()
    box.AttachmentOffset = FreeCAD.Placement(flip.multVec(V(-size / 2, -size / 2, 0)), flip)
    for o in (b, box):
        _tag(o, cid)
    member.Document.recompute()


# --- Lista de cortes ------------------------------------------------------------------------------


def _density(body):
    try:
        from swui.fork import material as mt

        rho, source = mt.density(body)
        if rho and source:
            return rho, False
    except Exception:
        pass
    return STEEL, True


def _end_angles(body):
    """(largo, ángulo punta 1, ángulo punta 2) como la lista de cortes de SW: 0 = corte recto,
    45 = inglete; None si la punta no es plana (ajuste a medida)."""
    a0, a1, d = axis(body)
    sh = body.Shape
    # puntos de la superficie (no solo los vértices: la boca de pescado no tiene vértice en su punta)
    pts = [v.Point for v in sh.Vertexes]
    try:
        pts += list(sh.tessellate(0.05)[0])
    except Exception:
        pass
    ts = [(p - a0).dot(d) for p in pts]
    lo, hi = min(ts), max(ts)
    length = hi - lo
    angles = []
    for target in (lo, hi):
        best = None
        curved = False
        for f in sh.Faces:
            fpts = [v.Point for v in f.Vertexes]
            try:
                fpts += list(f.tessellate(0.05)[0])
            except Exception:
                pass
            vs = [(q - a0).dot(d) for q in fpts]
            if not vs or abs(min(vs, key=lambda x: abs(x - target)) - target) > 0.5:
                continue
            surf = f.Surface.__class__.__name__
            if surf != "Plane":
                along = False
                if surf == "Cylinder":  # la pared del caño (eje a lo largo) no es la punta
                    along = abs(abs(f.Surface.Axis.dot(d)) - 1) < 1e-3
                if not along and any(abs(x - target) < 0.5 for x in vs):
                    curved = True
                continue
            u0, u1, v0, v1 = f.ParameterRange
            n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            c = abs(n.dot(d))
            if c < 0.05:
                continue  # cara a lo largo
            ang = math.degrees(math.acos(min(1.0, c)))
            if best is None or ang > best:
                best = ang
        angles.append(None if curved else round(best or 0.0, 2))
    return length, angles[0], angles[1]


def cut_list(doc):
    """Lista de cortes agrupada (como SW): [{"n", "qty", "profile", "length", "angle1", "angle2",
    "unit_kg", "total_kg", "assumed_steel", "members"}]."""
    groups = {}
    for b in members(doc):
        try:
            length, a1, a2 = _end_angles(b)
        except Exception:
            continue
        rho, assumed = _density(b)
        kg = b.Shape.Volume * rho
        angs = tuple(sorted([x if x is not None else -1 for x in (a1, a2)]))
        key = (b.SWUI_WeldKind, b.SWUI_WeldSize, round(length, 1), angs)
        g = groups.setdefault(key, {"qty": 0, "profile": "%s %s" % (b.SWUI_WeldKind, b.SWUI_WeldSize),
                                    "length": round(length, 1), "angle1": a1, "angle2": a2,
                                    "unit_kg": kg, "assumed_steel": assumed, "members": []})
        g["qty"] += 1
        g["members"].append(b.Label)
    # tapas y cartelas (como SW: van en la lista como chapas, sin largo ni ángulos)
    for b in doc.Objects:
        desc = getattr(b, "SWUI_WeldPlate", "")
        if not desc:
            continue
        try:
            rho, assumed = _density(b)
            kg = b.Shape.Volume * rho
        except Exception:
            continue
        g = groups.setdefault(("chapa", desc), {"qty": 0, "profile": desc, "length": None, "angle1": "",
                                                "angle2": "", "unit_kg": kg, "assumed_steel": assumed,
                                                "members": []})
        g["qty"] += 1
        g["members"].append(b.Label)
    rows = sorted(groups.values(), key=lambda g: (g["length"] is None, g["profile"], -(g["length"] or 0)))
    for i, r in enumerate(rows):
        r["n"] = i + 1
        r["total_kg"] = r["unit_kg"] * r["qty"]
    return rows


def _angle_text(a):
    if a == "":
        return ""
    return "a medida" if a is None else _fmt(a)


def _length_text(x):
    return "" if x is None else _fmt(x)


def cut_list_csv(rows):
    """Texto CSV para Excel en castellano (punto y coma, coma decimal)."""
    lines = ["Nº;Cant.;Perfil;Largo (mm);Ángulo 1;Ángulo 2;Peso unit. (kg);Peso total (kg)"]
    for r in rows:
        lines.append(";".join([str(r["n"]), str(r["qty"]), r["profile"], _length_text(r["length"]),
                               _angle_text(r["angle1"]), _angle_text(r["angle2"]),
                               _fmt(round(r["unit_kg"], 2)), _fmt(round(r["total_kg"], 2))]))
    total = sum(r["total_kg"] for r in rows)
    lines.append(";;;;;;Total;%s" % _fmt(round(total, 2)))
    return "\r\n".join(lines) + "\r\n"


def cut_list_sheet(doc, rows, name="ListaDeCortes"):
    """La lista como Planilla en el documento (para ponerla en un plano con TechDraw)."""
    sheet = doc.getObject(name)
    if sheet is None:
        sheet = doc.addObject("Spreadsheet::Sheet", name)
        sheet.Label = "Lista de cortes"
    else:
        sheet.clearAll()
    heads = ["Nº", "Cant.", "Perfil", "Largo (mm)", "Ángulo 1", "Ángulo 2", "Peso unit. (kg)", "Peso total (kg)"]
    cols = "ABCDEFGH"
    for c, h in zip(cols, heads):
        sheet.set("%s1" % c, h)
    for i, r in enumerate(rows):
        vals = [r["n"], r["qty"], r["profile"], "" if r["length"] is None else round(r["length"], 1),
                _angle_text(r["angle1"]),
                _angle_text(r["angle2"]), round(r["unit_kg"], 2), round(r["total_kg"], 2)]
        for c, v in zip(cols, vals):
            sheet.set("%s%d" % (c, i + 2), ("'" + v) if isinstance(v, str) else str(v))
    last = len(rows) + 2
    sheet.set("G%d" % last, "'Total")
    sheet.set("H%d" % last, str(round(sum(r["total_kg"] for r in rows), 2)))
    doc.recompute()
    return sheet


# --- Extras: tapa de extremo y cartela ---------------------------------------------------------------


def end_cap(member, end, thickness=3.0, inset=0.0):
    """Tapa de extremo (como SW): chapa con el contorno de afuera del perfil (menos `inset` por lado),
    apoyada en la punta del miembro, hacia afuera. Un Cuerpo aparte, ubicado al crearla."""
    doc = member.Document
    a0, a1, d = axis(member)
    sh = member.Shape
    ts = [(v.Point - a0).dot(d) for v in sh.Vertexes]
    t_end = min(ts) if end == 0 else max(ts)
    out = d * (-1 if end == 0 else 1)
    p = a0 + d * t_end
    sk_pl = _profile_of(member).getGlobalPlacement()
    rot = sk_pl.Rotation
    if rot.multVec(V(0, 0, 1)).dot(out) < 0:
        rot = rot.multiply(FreeCAD.Rotation(V(1, 0, 0), 180))
    center = sk_pl.Base + d * (t_end - (sk_pl.Base - a0).dot(d))
    body = doc.addObject("PartDesign::Body", "Tapa")
    body.Label = "Tapa de extremo"
    sk = body.newObject("Sketcher::SketchObject", "PerfilTapa")
    sk.Label = "Perfil de la tapa"
    sk.Placement = FreeCAD.Placement(center, rot)
    kind, dims = member.SWUI_WeldKind, list(member.SWUI_WeldDims)
    loops = profile_loops(kind, dims, outer_only=True)
    if inset:
        shrunk = []
        for typ, data in loops:
            if typ == "circle":
                shrunk.append((typ, data - inset))
            else:
                xs = [q.x for q in data]
                ys = [q.y for q in data]
                shrunk.append(("poly", _rect(min(xs) + inset, min(ys) + inset, max(xs) - inset, max(ys) - inset)))
        loops = shrunk
    _fill_sketch(sk, loops, bool(getattr(member, "SWUI_WeldMirror", False)))
    pad = body.newObject("PartDesign::Pad", "Tapa")
    pad.Profile = sk
    pad.Length = float(thickness)
    _add_prop(body, "SWUI_WeldPart", "App::PropertyString", "tapa")
    w_, h_ = extent(kind, dims)
    _add_prop(body, "SWUI_WeldPlate", "App::PropertyString", "Tapa de extremo %sx%s e=%s" % (
        _fmt(w_ - 2 * inset), _fmt(h_ - 2 * inset), _fmt(thickness)))
    doc.recompute()
    return body


def gusset(a, b, size=80.0, thickness=6.0):
    """Cartela triangular (como SW) en la esquina entre dos miembros, en el plano de los dos, centrada
    en su espesor. Un Cuerpo aparte, ubicado al crearla."""
    doc = a.Document
    # la esquina = el cruce de los ejes (no de las líneas del esqueleto: un miembro alargado con
    # Recortar/Alargar no llega en el esqueleto; visto con el mouse 07/11)
    a0, a1, da = axis(a)
    b0, b1, db = axis(b)
    w0 = a0 - b0
    aa, bb, cc, dd, ee = da.dot(da), da.dot(db), db.dot(db), da.dot(w0), db.dot(w0)
    den = aa * cc - bb * bb
    if abs(den) < 1e-9:
        raise ValueError("Los miembros están en línea")
    sa = (bb * ee - cc * dd) / den
    sb = (aa * ee - bb * dd) / den
    pa, pb = a0 + da * sa, b0 + db * sb
    if (pa - pb).Length > 1.0:
        raise ValueError("Los miembros no forman una esquina (sus ejes no se cruzan)")
    p = (pa + pb) * 0.5
    # cada lado de la cartela va hacia donde está la mayor parte del miembro
    ua = da if ((a0 + a1) * 0.5 - p).dot(da) >= 0 else da * -1
    ub = db if ((b0 + b1) * 0.5 - p).dot(db) >= 0 else db * -1
    n = ua.cross(ub)
    if n.Length < 1e-9:
        raise ValueError("Los miembros están en línea")
    n.normalize()
    # el triángulo arranca en las caras de los miembros (no en sus ejes)
    off_a = half_extent(b, ua) + 0.0
    off_b = half_extent(a, ub) + 0.0
    q0 = p + ua * off_a + ub * off_b
    q1 = q0 + ua * size
    q2 = q0 + ub * size
    x = ua
    y = n.cross(x)
    rot = FreeCAD.Rotation(x, y, n, "ZXY")
    pl = FreeCAD.Placement(q0, rot)
    inv = pl.inverse()
    body = doc.addObject("PartDesign::Body", "Cartela")
    body.Label = "Cartela"
    sk = body.newObject("Sketcher::SketchObject", "PerfilCartela")
    sk.Label = "Perfil de la cartela"
    sk.Placement = pl
    pts = [inv.multVec(q) for q in (q0, q1, q2)]
    pts = [V(q.x, q.y, 0) for q in pts]
    _fill_sketch(sk, [("poly", pts)])
    pad = body.newObject("PartDesign::Pad", "Cartela")
    pad.Profile = sk
    pad.SideType = "Symmetric"
    pad.Length = float(thickness)
    _add_prop(body, "SWUI_WeldPart", "App::PropertyString", "cartela")
    _add_prop(body, "SWUI_WeldPlate", "App::PropertyString", "Cartela %sx%s e=%s" % (
        _fmt(size), _fmt(size), _fmt(thickness)))
    doc.recompute()
    return body
