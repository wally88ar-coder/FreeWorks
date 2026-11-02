# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Etapa 1c, operaciones directas (camino mixto, decisión del usuario 01/11): las que dan el mismo
resultado sin panel, porque su panel SW es solo la interfaz. Se crea el objeto nativo de Part
Design, como lo deja el panel: croquis (totalmente definido, en negro), Extruir, Cortar,
Revolución, Redondeo, Chaflán, Matriz lineal y circular, Simetría y Taladro.

Reglas: coordenadas GLOBALES en mm (las mismas que da 'geometria'); la IA no pone nombres (los SW
los pone FreeWorks); si la operación queda con error se deshace sola y vuelve el aviso de FreeCAD;
nada si el usuario tiene un panel o croquis abierto. Un paso de Ctrl+Z por operación ("IA: ...").
"""

import FreeCAD

from swui.fork.ia.herramientas import comun as c
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult

FITS = {"ajustado": "Fine", "normal": "Medium", "holgado": "Coarse"}


# --- Ayudas -----------------------------------------------------------------------------


def _body_of(obj):
    from swui.fork import feature_tree as ft

    if obj.TypeId == "PartDesign::Body":
        return obj
    body = ft.body_of(obj)
    if body is None:
        raise c.Problema("%s no está en un Cuerpo." % c.label_of(obj))
    return body


def _origin(body, role):
    for f in body.Origin.OriginFeatures:
        if getattr(f, "Role", "") == role:
            return f
    raise c.Problema("El Cuerpo no tiene %s." % role)


def _split(doc, ref):
    name, _, sub = str(ref).partition(".")
    return c.find(doc, name), sub


def _feature_ref(doc, body, ref):
    """'XY' / 'X' / 'Body.FaceN' / 'Body.EdgeN' / 'Plano1' -> (objeto, [sub]) para un vínculo de Part Design."""
    key = str(ref).strip().upper()
    planes = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane"}
    axes = {"X": "X_Axis", "Y": "Y_Axis", "Z": "Z_Axis"}
    if key in planes:
        return _origin(body, planes[key]), [""]
    if key in axes:
        return _origin(body, axes[key]), [""]
    obj, sub = _split(doc, ref)
    if not sub:
        return obj, [""]
    if obj.TypeId == "PartDesign::Body":
        return obj.Tip, [sub]
    return obj, [sub]


def _ops(doc, names):
    from swui.fork import feature_tree as ft

    out = []
    for n in names or []:
        o = c.find(doc, n)
        if not ft.is_feature(o):
            raise c.Problema("%s no es una operación." % c.label_of(o))
        out.append(o)
    if not out:
        raise c.Problema("Faltan las operaciones.")
    return out


def _make(doc, title, fn):
    """Crear en un paso de deshacer; si la operación queda con error, deshacer y avisar."""
    c.require_free()
    from swui.fork import feature_tree as ft

    before = {o.Name for o in doc.Objects}
    doc.openTransaction("IA: %s" % title)
    try:
        obj = fn()
        # body.newObject no mueve la punta en las matrices y simetrías (sí en Extruir/Cortar): la
        # operación nueva quedaba debajo de la barra de retroceso (visto el 01/11). Como el comando.
        if ft.is_feature(obj):
            ft.set_tip(_body_of(obj), obj)
        doc.recompute()
    except c.Problema:
        doc.abortTransaction()
        doc.recompute()
        raise
    except Exception as exc:
        doc.abortTransaction()
        doc.recompute()
        raise c.Problema("FreeCAD no pudo hacer %s: %s" % (title, exc))
    bad = []
    for name in {o.Name for o in doc.Objects} - before:
        o = doc.getObject(name)
        state = getattr(o, "State", None) or []
        broken = "Invalid" in state
        try:
            if o.isDerivedFrom("PartDesign::Feature") and (o.Shape.isNull() or not o.Shape.isValid()):
                broken = True
        except Exception:
            pass
        if broken:
            msg = ""
            try:
                msg = o.getStatusString()
            except Exception:
                pass
            bad.append("%s: %s" % (o.Label, msg or "operación con error"))
    if bad:
        doc.abortTransaction()  # vuelve atrás todo lo de este paso
        doc.recompute()
        raise c.Problema("%s no se pudo hacer y se deshizo: %s" % (title, "; ".join(bad)))
    doc.commitTransaction()
    return obj


def _result(obj, extra=""):
    body = None
    try:
        body = _body_of(obj)
    except Exception:
        pass
    text = "Hecho: %s." % c.label_of(obj)
    data = {"objeto": obj.Name, "etiqueta": obj.Label}
    if body is not None and not body.Shape.isNull():
        data["volumen_cuerpo"] = c.r(body.Shape.Volume)
        text += " Volumen de %s: %s mm³." % (body.Label, data["volumen_cuerpo"])
    return ToolResult(success=True, output=text + extra, data=data)


# --- Croquis ----------------------------------------------------------------------------


def _local(sk, p):
    v = sk.getGlobalPlacement().inverse().multVec(FreeCAD.Vector(*[float(x) for x in p]))
    return FreeCAD.Vector(v.x, v.y, 0)


def _fix_point(sk, geo, pos, p):
    import Sketcher

    if abs(p.x) < 1e-9:
        sk.addConstraint(Sketcher.Constraint("PointOnObject", geo, pos, -2))
    else:
        sk.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, geo, pos, p.x))
    if abs(p.y) < 1e-9:
        sk.addConstraint(Sketcher.Constraint("PointOnObject", geo, pos, -1))
    else:
        sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, geo, pos, p.y))


def _polyline(sk, pts, rect=False):
    import Part
    import Sketcher

    n = len(pts)
    first = len(sk.Geometry)
    for i in range(n):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % n]))
    for i in range(n):
        sk.addConstraint(Sketcher.Constraint("Coincident", first + i, 2, first + (i + 1) % n, 1))
    if rect:
        sk.addConstraint(Sketcher.Constraint("Horizontal", first))
        sk.addConstraint(Sketcher.Constraint("Horizontal", first + 2))
        sk.addConstraint(Sketcher.Constraint("Vertical", first + 1))
        sk.addConstraint(Sketcher.Constraint("Vertical", first + 3))
        sk.addConstraint(Sketcher.Constraint("DistanceX", first, 1, first, 2, pts[1].x - pts[0].x))
        sk.addConstraint(Sketcher.Constraint("DistanceY", first + 1, 1, first + 1, 2, pts[2].y - pts[1].y))
        _fix_point(sk, first, 1, pts[0])
    else:
        for i in range(n):
            _fix_point(sk, first + i, 1, pts[i])


def _add_element(sk, el):
    import Part
    import Sketcher

    kind = el.get("tipo")
    if kind == "rectangulo":
        if "desde" in el and "hasta" in el:
            a, b = _local(sk, el["desde"]), _local(sk, el["hasta"])
        else:
            m = _local(sk, el["centro"])
            w, h = float(el["ancho"]) / 2.0, float(el["alto"]) / 2.0
            a, b = FreeCAD.Vector(m.x - w, m.y - h, 0), FreeCAD.Vector(m.x + w, m.y + h, 0)
        x0, x1, y0, y1 = min(a.x, b.x), max(a.x, b.x), min(a.y, b.y), max(a.y, b.y)
        if x1 - x0 < 1e-6 or y1 - y0 < 1e-6:
            raise c.Problema("Rectángulo sin ancho o sin alto.")
        _polyline(sk, [FreeCAD.Vector(x0, y0, 0), FreeCAD.Vector(x1, y0, 0), FreeCAD.Vector(x1, y1, 0),
                       FreeCAD.Vector(x0, y1, 0)], rect=True)
    elif kind == "circulo":
        m = _local(sk, el["centro"])
        d = float(el.get("diametro") or 2 * float(el["radio"]))
        g = sk.addGeometry(Part.Circle(m, FreeCAD.Vector(0, 0, 1), d / 2.0))
        sk.addConstraint(Sketcher.Constraint("Diameter", g, d))
        if m.Length < 1e-9:
            sk.addConstraint(Sketcher.Constraint("Coincident", g, 3, -1, 1))
        else:
            _fix_point(sk, g, 3, m)
    elif kind == "poligono":
        pts = [_local(sk, p) for p in el["puntos"]]
        if len(pts) < 3:
            raise c.Problema("Un polígono necesita al menos 3 puntos.")
        _polyline(sk, pts)
    else:
        raise c.Problema("Elemento \"%s\" desconocido (rectangulo, circulo, poligono)." % kind)


def croquis(sobre, elementos, cuerpo=None, documento=None):
    doc = c.document(documento)
    key = str(sobre).strip().upper()
    if key in ("XY", "XZ", "YZ"):
        bodies = [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]
        body = c.find(doc, cuerpo) if cuerpo else (bodies[0] if len(bodies) == 1 else None)
        if body is None:
            raise c.Problema("Decí en qué Cuerpo va el croquis (hay %d)." % len(bodies))
        support = [(_origin(body, key + "_Plane"), "")]
    else:
        obj, sub = _split(doc, sobre)
        body = _body_of(obj) if not cuerpo else c.find(doc, cuerpo)
        if sub:
            face = c.sub_shape(obj, sub)
            if type(face.Surface).__name__ != "Plane":
                raise c.Problema("%s no es una cara plana." % sobre)
            support = [(obj.Tip if obj.TypeId == "PartDesign::Body" else obj, sub)]
        else:
            support = [(obj, "")]  # un plano de referencia

    def work():
        sk = body.newObject("Sketcher::SketchObject", "Sketch")
        sk.AttachmentSupport = support
        sk.MapMode = "FlatFace"
        doc.recompute()
        for el in elementos:
            _add_element(sk, el)
        return sk
    sk = _make(doc, "croquis", work)
    plc = sk.getGlobalPlacement()
    rot = plc.Rotation
    data = {"objeto": sk.Name, "etiqueta": sk.Label, "en_negro": bool(getattr(sk, "FullyConstrained", False)),
            "origen_global": c.vec(plc.Base), "eje_x_local": c.vec(rot.multVec(FreeCAD.Vector(1, 0, 0))),
            "eje_y_local": c.vec(rot.multVec(FreeCAD.Vector(0, 1, 0))), "normal": c.vec(rot.multVec(FreeCAD.Vector(0, 0, 1)))}
    text = "Croquis %s%s." % (c.label_of(sk), " totalmente definido (en negro)" if data["en_negro"] else
                              " (OJO: no quedó totalmente definido)")
    return ToolResult(success=True, output=text, data=data)


# --- Extruir, cortar, revolución --------------------------------------------------------


def extruir(croquis, largo=10.0, invertir=False, simetrico=False, hasta=None, documento=None):
    doc = c.document(documento)
    sk = c.find(doc, croquis)
    body = _body_of(sk)

    def work():
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sk
        if hasta:
            pad.Type = "UpToFace"
            pad.UpToFace = _feature_ref(doc, body, hasta)
        else:
            pad.Length = float(largo)
        pad.Reversed = bool(invertir)
        if simetrico:
            pad.SideType = "Symmetric"
        return pad
    return _result(_make(doc, "extruir %s" % sk.Label, work))


def cortar(croquis, largo=None, invertir=False, simetrico=False, documento=None):
    doc = c.document(documento)
    sk = c.find(doc, croquis)
    body = _body_of(sk)

    def work():
        pk = body.newObject("PartDesign::Pocket", "Pocket")
        pk.Profile = sk
        if largo is None:
            pk.Type = "ThroughAll"
        else:
            pk.Length = float(largo)
        pk.Reversed = bool(invertir)
        if simetrico:
            pk.SideType = "Symmetric"
        return pk
    return _result(_make(doc, "cortar %s" % sk.Label, work))


def revolucion(croquis, eje="V", angulo=360.0, cortar=False, documento=None):
    doc = c.document(documento)
    sk = c.find(doc, croquis)
    body = _body_of(sk)

    def work():
        rev = body.newObject("PartDesign::Groove" if cortar else "PartDesign::Revolution",
                             "Groove" if cortar else "Revolution")
        rev.Profile = sk
        key = str(eje).strip().upper()
        if key in ("V", "H"):
            rev.ReferenceAxis = (sk, [key + "_Axis"])
        else:
            rev.ReferenceAxis = _feature_ref(doc, body, eje)
        rev.Angle = float(angulo)
        return rev
    return _result(_make(doc, "revolución %s" % sk.Label, work))


# --- Redondeo, chaflán ------------------------------------------------------------------


def _dress(doc, objeto, aristas, kind, title, setter):
    obj = c.find(doc, objeto)
    body = _body_of(obj)
    if not aristas:
        raise c.Problema("Faltan las aristas (EdgeN; ver 'geometria' o 'elegir').")

    def work():
        base = body.Tip  # ANTES de crear: body.newObject ya deja como punta al redondeo nuevo
        f = body.newObject(kind, kind.split(":")[-1])
        f.Base = (base, [str(a).split(".")[-1] for a in aristas])
        setter(f)
        return f
    return _result(_make(doc, title, work))


def redondeo(objeto, aristas, radio, documento=None):
    doc = c.document(documento)
    return _dress(doc, objeto, aristas, "PartDesign::Fillet", "redondeo R%s" % radio,
                  lambda f: setattr(f, "Radius", float(radio)))


def chaflan(objeto, aristas, distancia, documento=None):
    doc = c.document(documento)
    return _dress(doc, objeto, aristas, "PartDesign::Chamfer", "chaflán %s" % distancia,
                  lambda f: setattr(f, "Size", float(distancia)))


# --- Matrices y simetría ----------------------------------------------------------------


def matriz_lineal(operaciones, direccion, cantidad, espaciado, invertir=False, documento=None):
    doc = c.document(documento)
    ops = _ops(doc, operaciones)
    body = _body_of(ops[0])

    def work():
        p = body.newObject("PartDesign::LinearPattern", "LinearPattern")
        p.Originals = ops
        p.Direction = _feature_ref(doc, body, direccion)
        p.Mode = "Spacing"
        p.Offset = float(espaciado)
        p.Occurrences = int(cantidad)
        p.Reversed = bool(invertir)
        return p
    return _result(_make(doc, "matriz lineal", work))


def matriz_circular(operaciones, eje, cantidad, angulo=360.0, documento=None):
    doc = c.document(documento)
    ops = _ops(doc, operaciones)
    body = _body_of(ops[0])

    def work():
        p = body.newObject("PartDesign::PolarPattern", "PolarPattern")
        p.Originals = ops
        p.Axis = _feature_ref(doc, body, eje)
        p.Angle = float(angulo)
        p.Occurrences = int(cantidad)
        return p
    return _result(_make(doc, "matriz circular", work))


def simetria(operaciones, plano, documento=None):
    doc = c.document(documento)
    ops = _ops(doc, operaciones)
    body = _body_of(ops[0])

    def work():
        m = body.newObject("PartDesign::Mirrored", "Mirrored")
        m.Originals = ops
        m.MirrorPlane = _feature_ref(doc, body, plano)
        return m
    return _result(_make(doc, "simetría", work))


# --- Taladro (como el asistente: tornillo, ajuste, pasante) -----------------------------


def taladro(cara, posiciones, tamano="M6", roscado=False, ajuste="normal", profundidad=None, documento=None):
    doc = c.document(documento)
    obj, sub = _split(doc, cara)
    body = _body_of(obj)
    face = c.sub_shape(obj, sub)
    if type(face.Surface).__name__ != "Plane":
        raise c.Problema("%s no es una cara plana." % cara)
    size = str(tamano).upper().replace(" ", "")

    def work():
        import Part
        import Sketcher

        sk = body.newObject("Sketcher::SketchObject", "Sketch")
        sk.AttachmentSupport = [(body.Tip, sub)]
        sk.MapMode = "FlatFace"
        doc.recompute()
        nominal = float(size.lstrip("M").split("X")[0])
        for p in posiciones:
            m = _local(sk, p)
            g = sk.addGeometry(Part.Circle(m, FreeCAD.Vector(0, 0, 1), nominal / 2.0))
            sk.addConstraint(Sketcher.Constraint("Diameter", g, nominal))
            _fix_point(sk, g, 3, m)
        h = body.newObject("PartDesign::Hole", "Hole")
        h.Profile = sk
        h.ThreadType = "ISOMetricProfile"
        options = h.getEnumerationsOfProperty("ThreadSize")
        pick = [o for o in options if o.upper().split("X")[0] == size.split("X")[0]] or \
               [o for o in options if o.upper() == size]
        if not pick:
            raise c.Problema("No hay rosca métrica %s. Hay: %s" % (tamano, ", ".join(options[:40])))
        h.ThreadSize = pick[0]
        h.Threaded = bool(roscado)
        if not roscado:
            h.ThreadFit = FITS.get(str(ajuste).lower(), "Medium")
        if profundidad is None:
            h.DepthType = "ThroughAll"
        else:
            h.DepthType = "Dimension"
            h.Depth = float(profundidad)
        return h
    h = _make(doc, "taladro %s" % tamano, work)
    return _result(h, " Ø del agujero: %s mm (%s)." % (c.r(h.Diameter.Value), h.ThreadSize))


# --- Registro ---------------------------------------------------------------------------

_DOC = ToolParam("documento", "string", "Documento (por defecto el activo)", required=False)
_PT = {"type": "number"}


def register(registry):
    reg = registry.register
    reg(ToolDefinition(
        name="croquis",
        description=("Croquis nuevo TOTALMENTE DEFINIDO (en negro) sobre un plano del origen (XY, XZ, YZ), una cara "
                     "plana ('Body.FaceN') o un plano de referencia. Elementos con coordenadas GLOBALES (las de "
                     "'geometria'): {'tipo':'rectangulo','centro':[x,y,z],'ancho':a,'alto':b} (ancho sobre el eje X "
                     "local del croquis) o {'tipo':'rectangulo','desde':[x,y,z],'hasta':[x,y,z]}; "
                     "{'tipo':'circulo','centro':[x,y,z],'diametro':d}; {'tipo':'poligono','puntos':[[x,y,z],...]}. "
                     "Devuelve los ejes locales. Después: extruir / cortar / revolucion."),
        parameters=[ToolParam("sobre", "string", "XY, XZ, YZ, 'Body.FaceN' o un plano de referencia"),
                    ToolParam("elementos", "array", "Lista de elementos", items={"type": "object"}),
                    ToolParam("cuerpo", "string", "Cuerpo (si hay varios)", required=False), _DOC],
        handler=c.guarded(croquis), category="operar", timeout=60))
    reg(ToolDefinition(
        name="extruir",
        description=("Extruir saliente/base desde un croquis (como el panel SW, mismo resultado): largo en mm, "
                     "invertir, simetrico (plano medio) o hasta una cara ('Body.FaceN')."),
        parameters=[ToolParam("croquis", "string", "Croquis"),
                    ToolParam("largo", "number", "Largo en mm", required=False, default=10.0),
                    ToolParam("invertir", "boolean", "Invertir dirección", required=False, default=False),
                    ToolParam("simetrico", "boolean", "Plano medio", required=False, default=False),
                    ToolParam("hasta", "string", "Hasta esta cara en vez de un largo", required=False), _DOC],
        handler=c.guarded(extruir), category="operar", timeout=60))
    reg(ToolDefinition(
        name="cortar",
        description="Extruir corte desde un croquis: largo en mm, o sin largo = por todo (pasante).",
        parameters=[ToolParam("croquis", "string", "Croquis"),
                    ToolParam("largo", "number", "Profundidad en mm; sin esto, por todo", required=False),
                    ToolParam("invertir", "boolean", "Invertir dirección", required=False, default=False),
                    ToolParam("simetrico", "boolean", "Plano medio", required=False, default=False), _DOC],
        handler=c.guarded(cortar), category="operar", timeout=60))
    reg(ToolDefinition(
        name="revolucion",
        description=("Revolución (o revolución de corte con cortar=true) de un croquis alrededor de su eje V o H, "
                     "o de una arista ('Body.EdgeN') o eje del origen (X, Y, Z)."),
        parameters=[ToolParam("croquis", "string", "Croquis"),
                    ToolParam("eje", "string", "V, H, X, Y, Z o 'Body.EdgeN'", required=False, default="V"),
                    ToolParam("angulo", "number", "Grados", required=False, default=360.0),
                    ToolParam("cortar", "boolean", "Revolución de corte", required=False, default=False), _DOC],
        handler=c.guarded(revolucion), category="operar", timeout=60))
    reg(ToolDefinition(
        name="redondeo",
        description="Redondeo de aristas ('EdgeN' del Cuerpo, ver 'geometria' / 'elegir') con un radio en mm.",
        parameters=[ToolParam("objeto", "string", "Cuerpo"),
                    ToolParam("aristas", "array", "Aristas", items={"type": "string"}),
                    ToolParam("radio", "number", "Radio en mm"), _DOC],
        handler=c.guarded(redondeo), category="operar", timeout=60))
    reg(ToolDefinition(
        name="chaflan",
        description="Chaflán de distancias iguales en aristas ('EdgeN' del Cuerpo).",
        parameters=[ToolParam("objeto", "string", "Cuerpo"),
                    ToolParam("aristas", "array", "Aristas", items={"type": "string"}),
                    ToolParam("distancia", "number", "Distancia en mm"), _DOC],
        handler=c.guarded(chaflan), category="operar", timeout=60))
    reg(ToolDefinition(
        name="matriz_lineal",
        description=("Matriz lineal de operaciones: dirección X, Y, Z o una arista recta ('Body.EdgeN'); cantidad "
                     "total (incluida la original) y espaciado entre copias."),
        parameters=[ToolParam("operaciones", "array", "Operaciones a repetir", items={"type": "string"}),
                    ToolParam("direccion", "string", "X, Y, Z o 'Body.EdgeN'"),
                    ToolParam("cantidad", "integer", "Instancias en total"),
                    ToolParam("espaciado", "number", "Espaciado en mm"),
                    ToolParam("invertir", "boolean", "Invertir dirección", required=False, default=False), _DOC],
        handler=c.guarded(matriz_lineal), category="operar", timeout=120))
    reg(ToolDefinition(
        name="matriz_circular",
        description="Matriz circular de operaciones alrededor de X, Y, Z o una arista ('Body.EdgeN', p. ej. un borde circular).",
        parameters=[ToolParam("operaciones", "array", "Operaciones a repetir", items={"type": "string"}),
                    ToolParam("eje", "string", "X, Y, Z o 'Body.EdgeN'"),
                    ToolParam("cantidad", "integer", "Instancias en total"),
                    ToolParam("angulo", "number", "Ángulo total en grados", required=False, default=360.0), _DOC],
        handler=c.guarded(matriz_circular), category="operar", timeout=120))
    reg(ToolDefinition(
        name="simetria",
        description="Simetría de operaciones respecto de un plano del origen (XY, XZ, YZ) o una cara plana ('Body.FaceN').",
        parameters=[ToolParam("operaciones", "array", "Operaciones", items={"type": "string"}),
                    ToolParam("plano", "string", "XY, XZ, YZ o 'Body.FaceN'"), _DOC],
        handler=c.guarded(simetria), category="operar", timeout=120))
    reg(ToolDefinition(
        name="taladro",
        description=("Asistente para taladro (métrico ISO): en una cara plana ('Body.FaceN'), posiciones GLOBALES de "
                     "los centros, tamaño (M6...), roscado o de paso con ajuste (ajustado, normal, holgado), pasante "
                     "o con profundidad. El Ø de paso lo calcula FreeCAD según el ajuste, como el asistente."),
        parameters=[ToolParam("cara", "string", "Cara plana donde empieza el agujero"),
                    ToolParam("posiciones", "array", "Centros [[x,y,z], ...]", items={"type": "array", "items": _PT}),
                    ToolParam("tamano", "string", "M3, M4, M5, M6, M8, M10...", required=False, default="M6"),
                    ToolParam("roscado", "boolean", "Agujero roscado", required=False, default=False),
                    ToolParam("ajuste", "string", "ajustado, normal u holgado (de paso)", required=False,
                              default="normal"),
                    ToolParam("profundidad", "number", "Profundidad en mm; sin esto, pasante", required=False), _DOC],
        handler=c.guarded(taladro), category="operar", timeout=120))
