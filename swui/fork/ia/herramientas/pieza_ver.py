# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Etapa 1a: mirar y elegir, sin cambiar nada. Entran por funciones públicas de FreeWorks (las
"ventanillas"): feature_tree.creator / features / body_of, instant_dims.dims_of, equations
(nombres D1@Croquis1), configurations, measure_sw.measure, mass_props, repair_refs.problems,
move_face.stale_in / lost_in.

Elegir por descripción (decisión del usuario, 01/11): si la descripción encaja con más de una cara
o arista, no se elige al azar: vuelven las candidatas y la IA le pregunta al usuario cuál.
"""

import FreeCAD

from swui.fork.ia.herramientas import comun as c
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult

MAX_ITEMS = 200


# --- geometria ------------------------------------------------------------------------


def _tip_faces(obj):
    """Caras de la punta del Cuerpo en sus coordenadas, para saber qué operación creó cada una."""
    tip = getattr(obj, "Tip", None)
    try:
        return tip, tip.Shape.Faces if tip is not None else []
    except Exception:
        return None, []


def _creator_label(tip, tip_faces, i):
    from swui.fork import feature_tree as ft

    try:
        f = ft.creator(tip, tip_faces[i])
        return f.Label if f is not None else None
    except Exception:
        return None


def geometria(objeto, documento=None, que="caras", tipo=None, con_creador=True):
    doc = c.document(documento)
    obj = c.find(doc, objeto)
    shape = c.solid_shape(obj)
    items = []
    if que in ("caras", "todo"):
        tip, tip_faces = _tip_faces(obj) if con_creador else (None, [])
        for i, face in enumerate(shape.Faces):
            info = c.face_info(face, "Face%d" % (i + 1))
            if tipo and not info["tipo"].startswith(tipo):
                continue
            if tip is not None and len(tip_faces) == len(shape.Faces):
                info["creada_por"] = _creator_label(tip, tip_faces, i)
            items.append(info)
    if que in ("aristas", "todo"):
        seams = _seams(shape)
        for i, edge in enumerate(shape.Edges):
            info = c.edge_info(edge, "Edge%d" % (i + 1))
            if tipo and not info["tipo"].startswith(tipo):
                continue
            if i in seams:
                info["costura"] = True  # línea de unión de un cilindro: no es una arista de verdad
            items.append(info)
    bb = shape.BoundBox
    data = {"objeto": c.label_of(obj), "volumen": c.r(shape.Volume),
            "caja": {"min": [c.r(bb.XMin), c.r(bb.YMin), c.r(bb.ZMin)],
                     "max": [c.r(bb.XMax), c.r(bb.YMax), c.r(bb.ZMax)]},
            "elementos": items[:MAX_ITEMS]}
    if len(items) > MAX_ITEMS:
        data["recortado"] = "se muestran %d de %d: filtrá por tipo" % (MAX_ITEMS, len(items))
    return ToolResult(success=True, output="%s: %d caras, %d aristas (coordenadas globales, mm)."
                      % (c.label_of(obj), len(shape.Faces), len(shape.Edges)), data=data)


def _seams(shape):
    """Índices de las aristas que son costura de una cara curva (la recta de un agujero)."""
    out = set()
    for face in shape.Faces:
        if type(face.Surface).__name__ == "Plane":
            continue
        for e in face.Edges:
            try:
                if e.isSeam(face):
                    for i, g in enumerate(shape.Edges):
                        if g.isSame(e):
                            out.add(i)
            except Exception:
                pass
    return out


# --- elegir -----------------------------------------------------------------------------


def _matches(info, shape_el, kind, tipo, normal, radio, diametro, largo, cerca_de, creada_por, agujero):
    if tipo and not info["tipo"].startswith(tipo):
        return False
    if normal is not None:
        if kind == "cara":
            if info.get("tipo") != "plana" or not c.same_dir(FreeCAD.Vector(*info["normal"]), normal, 1e-2):
                return False
        else:  # arista recta paralela a la dirección
            if info.get("tipo") != "recta":
                return False
            d = FreeCAD.Vector(*info["hasta"]) - FreeCAD.Vector(*info["desde"])
            if not c.parallel(d.normalize(), normal, 1e-2):
                return False
    want_r = radio if radio is not None else (diametro / 2.0 if diametro is not None else None)
    if want_r is not None and not (info.get("radio") is not None and c.close(info["radio"], want_r)):
        return False
    if largo is not None and not c.close(info.get("largo", -1), largo):
        return False
    if agujero is not None and info.get("agujero") is not None and info["agujero"] != agujero:
        return False
    if creada_por and (info.get("creada_por") or "") not in (creada_por,):
        return False
    return True


def elegir(objeto, documento=None, elemento="cara", tipo=None, normal=None, radio=None, diametro=None,
           largo=None, agujero=None, creada_por=None, extremo=None, cerca_de=None, seleccionar=True):
    import FreeCADGui

    doc = c.document(documento)
    obj = c.find(doc, objeto)
    shape = c.solid_shape(obj)
    kind = "cara" if elemento.startswith("cara") else "arista"
    nvec = c.direction(normal) if normal is not None else None
    tip, tip_faces = _tip_faces(obj) if (kind == "cara" and creada_por) else (None, [])
    elems = shape.Faces if kind == "cara" else shape.Edges
    seams = _seams(shape) if kind == "arista" else set()
    found = []
    for i, el in enumerate(elems):
        if i in seams:
            continue  # las costuras de los cilindros no se eligen
        name = ("Face%d" if kind == "cara" else "Edge%d") % (i + 1)
        info = c.face_info(el, name) if kind == "cara" else c.edge_info(el, name)
        if creada_por and tip is not None and len(tip_faces) == len(elems):
            info["creada_por"] = _creator_label(tip, tip_faces, i)
        if _matches(info, el, kind, tipo, nvec, radio, diametro, largo, cerca_de, creada_por, agujero):
            found.append((info, el))
    if extremo and found:
        d = c.direction(extremo)
        key = lambda pair: pair[1].CenterOfMass.dot(d)  # noqa: E731
        best = max(key(p) for p in found)
        found = [p for p in found if abs(key(p) - best) < 1e-3]
    if cerca_de is not None and found:
        p = FreeCAD.Vector(*[float(x) for x in cerca_de])
        dist = lambda pair: pair[1].distToShape(__import__("Part").Vertex(p))[0]  # noqa: E731
        best = min(dist(q) for q in found)
        found = [q for q in found if dist(q) - best < 1e-3]
    if not found:
        return c.fail("Ninguna %s de %s encaja con esa descripción. Mirá la lista con 'geometria'."
                      % (kind, obj.Label))
    if len(found) > 1:
        return ToolResult(success=False, output="", error=(
            "La descripción encaja con %d %ss: hay que preguntarle al usuario cuál (o precisar con "
            "extremo / cerca_de). Candidatas: %s" % (len(found), kind,
                                                   [info for info, _el in found][:20])))
    info = found[0][0]
    if seleccionar:
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(doc.Name, obj.Name, info["nombre"])
    return ToolResult(success=True, output="%s.%s%s" % (obj.Name, info["nombre"],
                                                       " (quedó elegida)" if seleccionar else ""),
                      data=info)


# --- cotas ------------------------------------------------------------------------------


def _dims_with_names(obj):
    """[(nombre SW, Dim)] de un croquis u operación (las del doble clic)."""
    from swui.fork import equations, instant_dims

    out = []
    for dim in instant_dims.dims_of(obj):
        kind, owner, which = dim.setter
        if kind == "sketch":
            names = equations.sketch_dim_names([(k.Type, k.Name) for k in owner.Constraints])
            name = names.get(which, "C%d" % which)
        else:
            name = equations.feature_dim_names(owner.TypeId, owner.PropertiesList).get(which, which)
        out.append(("%s@%s" % (name, owner.Label), dim))
    return out


def all_dims(obj):
    """Cotas de un croquis, de una operación (con su croquis) o de todo un Cuerpo."""
    from swui.fork import feature_tree as ft

    if getattr(obj, "TypeId", "") == "PartDesign::Body":
        out, seen = [], set()
        for f in ft.features(obj):
            for name, dim in _dims_with_names(f):
                if name not in seen:
                    seen.add(name)
                    out.append((name, dim))
        return out
    return _dims_with_names(obj)


def cotas(objeto, documento=None):
    from swui.fork import configurations as cf

    doc = c.document(documento)
    obj = c.find(doc, objeto)
    rows = []
    configured = cf.configured(doc)
    for name, dim in all_dims(obj):
        row = {"nombre": name, "valor": c.r(dim.value), "tipo": "angulo" if dim.kind == "angle" else "largo",
               "texto": dim.text}
        if dim.locked:
            row["atada_a_ecuacion"] = True
        if configured:
            try:
                row["por_configuracion"] = {n: cf.value_in(doc, dim.setter, n) for n in cf.names(doc)}
            except Exception:
                pass
        rows.append(row)
    text = "%d cotas de %s" % (len(rows), obj.Label)
    if configured:
        text += " (configuración activa: %s)" % cf.active(doc)
    return ToolResult(success=True, output=text + ".", data={"cotas": rows})


# --- configuraciones --------------------------------------------------------------------


def configuraciones(documento=None):
    from swui.fork import configurations as cf

    doc = c.document(documento)
    names = cf.names(doc)
    if not names:
        return ToolResult(success=True, output="%s no tiene configuraciones (una sola, como siempre)." % doc.Label,
                          data={"configuraciones": []})
    return ToolResult(success=True, output="Activa: %s." % cf.active(doc),
                      data={"configuraciones": names, "activa": cf.active(doc)})


# --- medir ------------------------------------------------------------------------------


def medir(referencias, documento=None, modo="center"):
    from swui.fork import measure_sw

    doc = c.document(documento)
    shapes = []
    for ref in referencias:
        name, _, sub = str(ref).partition(".")
        obj = c.find(doc, name)
        shapes.append(c.sub_shape(obj, sub) if sub else c.solid_shape(obj))
    rows, _line = measure_sw.measure(shapes, mode=modo)
    data = {"medidas": [{"que": t, "valor": v} for t, v in rows]}
    return ToolResult(success=True, output="; ".join("%s %s" % (t, v) for t, v in rows) or "Nada para medir.",
                      data=data)


# --- propiedades físicas ----------------------------------------------------------------


def propiedades(documento=None, incluir_ocultos=False):
    from swui.fork import mass_props

    doc = c.document(documento)
    parts = mass_props.components(doc, hidden=bool(incluir_ocultos))
    result, rhos, names, notes = mass_props.compute(parts)
    text = mass_props.report(result, rhos, names, notes)
    return ToolResult(success=result is not None, output=text, error="" if result is not None else text)


# --- verificar --------------------------------------------------------------------------


def verificar(documento=None, objeto=None, volumen=None, caja=None, tolerancia=0.01):
    from swui.fork import feature_tree as ft
    from swui.fork import move_face, repair_refs

    doc = c.document(documento)
    problems = []
    for o in doc.Objects:
        st = getattr(o, "State", None) or []
        if "Invalid" in st or "Error" in st:
            problems.append("con error: %s" % c.label_of(o))
        if o.TypeId == "Sketcher::SketchObject" and ft.body_of(o) is not None:
            if not getattr(o, "FullyConstrained", True) and not getattr(o, "Suppressed", False):
                problems.append("croquis sin definir del todo (no está en negro): %s" % o.Label)
    try:
        for o, _kind, text in repair_refs.problems(doc):
            problems.append("referencia perdida en %s: %s" % (o.Label, text))
    except Exception:
        pass
    try:
        for o in move_face.stale_in(doc):
            problems.append("desactualizado (Ctrl+Q): %s" % o.Label)
    except Exception:
        pass
    data = {"problemas": problems}
    checks = []
    if objeto:
        obj = c.find(doc, objeto)
        shape = c.solid_shape(obj)
        bb = shape.BoundBox
        data["volumen"] = c.r(shape.Volume)
        data["caja"] = [c.r(bb.XLength), c.r(bb.YLength), c.r(bb.ZLength)]
        data["valido"] = shape.isValid()
        if not shape.isValid():
            problems.append("el sólido de %s no es válido" % obj.Label)
        if volumen is not None:
            ok = abs(shape.Volume - float(volumen)) <= max(float(tolerancia), 1e-6 * float(volumen))
            checks.append("volumen %s (esperado %s): %s" % (c.r(shape.Volume), volumen, "bien" if ok else "MAL"))
            if not ok:
                problems.append("volumen distinto del esperado")
        if caja is not None:
            got = sorted([bb.XLength, bb.YLength, bb.ZLength])
            want = sorted(float(x) for x in caja)
            ok = all(abs(a - b) <= float(tolerancia) for a, b in zip(got, want))
            checks.append("caja %s (esperada %s): %s" % (data["caja"], list(caja), "bien" if ok else "MAL"))
            if not ok:
                problems.append("caja distinta de la esperada")
    data["chequeos"] = checks
    ok = not problems
    text = "Todo bien." if ok else "Hay %d problema(s): %s" % (len(problems), "; ".join(problems))
    if checks:
        text += " " + "; ".join(checks)
    return ToolResult(success=True, output=text, data=data)


# --- Registro ---------------------------------------------------------------------------

_OBJ = ToolParam("objeto", "string", "Nombre interno o etiqueta del objeto (un Cuerpo, una operación o un croquis)")
_DOC = ToolParam("documento", "string", "Documento (por defecto el activo)", required=False)


def register(registry):
    registry.register(ToolDefinition(
        name="geometria",
        description=("Lista las caras (y/o aristas) de un sólido con números: tipo (plana, cilindrica...), "
                     "normal, centro, área, radio, si un cilindro es agujero, y qué operación creó cada cara. "
                     "Coordenadas globales en mm. Los nombres FaceN/EdgeN cambian cuando cambia la pieza: "
                     "no los guardes de un pedido al siguiente, volvé a mirar."),
        parameters=[_OBJ, _DOC,
                    ToolParam("que", "string", "caras, aristas o todo", required=False,
                              enum=["caras", "aristas", "todo"], default="caras"),
                    ToolParam("tipo", "string", "Filtrar por tipo: plana, cilindrica, recta, circulo, arco...",
                              required=False),
                    ToolParam("con_creador", "boolean", "Decir qué operación creó cada cara", required=False,
                              default=True)],
        handler=c.guarded(geometria), category="ver", timeout=60))
    registry.register(ToolDefinition(
        name="elegir",
        description=("Encuentra UNA cara o arista por descripción geométrica y la deja elegida en pantalla. "
                     "Ej.: cara plana con normal +Z más alta (normal='+Z', extremo='+Z'); el agujero de "
                     "Ø10 (tipo='cilindrica', diametro=10, agujero=true); arista recta de 100 paralela a X "
                     "(elemento='arista', tipo='recta', largo=100, normal='X'). Si encaja con más de una, NO "
                     "elige: devuelve las candidatas y hay que preguntarle al usuario cuál (decisión del "
                     "usuario)."),
        parameters=[_OBJ, _DOC,
                    ToolParam("elemento", "string", "cara o arista", required=False, enum=["cara", "arista"],
                              default="cara"),
                    ToolParam("tipo", "string", "plana, cilindrica, conica, recta, circulo, arco", required=False),
                    ToolParam("normal", "string", "Cara plana: su normal (+Z, -X...). Arista recta: paralela a",
                              required=False),
                    ToolParam("radio", "number", "Radio en mm", required=False),
                    ToolParam("diametro", "number", "Diámetro en mm", required=False),
                    ToolParam("largo", "number", "Largo de la arista en mm", required=False),
                    ToolParam("agujero", "boolean", "Cilindro hueco (true) o macizo (false)", required=False),
                    ToolParam("creada_por", "string", "Etiqueta de la operación que creó la cara", required=False),
                    ToolParam("extremo", "string", "Quedarse con la(s) más lejana(s) en esa dirección (+Z = la más alta)",
                              required=False),
                    ToolParam("cerca_de", "array", "Punto [x, y, z]: quedarse con la más cercana", required=False,
                              items={"type": "number"}),
                    ToolParam("seleccionar", "boolean", "Dejarla elegida en pantalla", required=False, default=True)],
        handler=c.guarded(elegir), category="ver", timeout=60))
    registry.register(ToolDefinition(
        name="cotas",
        description=("Las cotas de un croquis, de una operación (con su croquis) o de un Cuerpo entero: las "
                     "mismas del doble clic, con su nombre SW (D1@Croquis1), valor, y valor por configuración "
                     "si hay. Para cambiarlas: cambiar_cota."),
        parameters=[_OBJ, _DOC], handler=c.guarded(cotas), category="ver", timeout=60))
    registry.register(ToolDefinition(
        name="configuraciones",
        description="Las configuraciones del documento y cuál está activa.",
        parameters=[_DOC], handler=c.guarded(configuraciones), category="ver", timeout=30))
    registry.register(ToolDefinition(
        name="medir",
        description=("Mide entre referencias como el Medir de FreeWorks: distancia, ángulo, centro a centro "
                     "en círculos (modo center, como SW), mínima (min) o máxima (max). Referencias: "
                     "'Objeto.FaceN', 'Objeto.EdgeN', 'Objeto.VertexN' u 'Objeto' entero."),
        parameters=[ToolParam("referencias", "array", "Lista de referencias", items={"type": "string"}), _DOC,
                    ToolParam("modo", "string", "center, min o max", required=False,
                              enum=["center", "min", "max"], default="center")],
        handler=c.guarded(medir), category="ver", timeout=60))
    registry.register(ToolDefinition(
        name="propiedades_fisicas",
        description=("Propiedades físicas como el informe de SW: masa, volumen, área, centro de gravedad e "
                     "inercia, con la densidad del material asignado (sin material: densidad 0)."),
        parameters=[_DOC, ToolParam("incluir_ocultos", "boolean", "Incluir sólidos ocultos", required=False,
                                    default=False)],
        handler=c.guarded(propiedades), category="ver", timeout=60))
    registry.register(ToolDefinition(
        name="verificar",
        description=("Revisa el documento: operaciones con error, croquis que no están en negro, referencias "
                     "perdidas, Mover cara desactualizados. Con objeto: su volumen, caja y si el sólido es "
                     "válido; con volumen y/o caja esperados, dice si dan. Usala después de cada cambio."),
        parameters=[_DOC, ToolParam("objeto", "string", "Cuerpo a medir", required=False),
                    ToolParam("volumen", "number", "Volumen esperado en mm³", required=False),
                    ToolParam("caja", "array", "Medidas esperadas de la caja [a, b, c] en mm (cualquier orden)",
                              required=False, items={"type": "number"}),
                    ToolParam("tolerancia", "number", "Tolerancia en mm / mm³", required=False, default=0.01)],
        handler=c.guarded(verificar), category="ver", timeout=60))
