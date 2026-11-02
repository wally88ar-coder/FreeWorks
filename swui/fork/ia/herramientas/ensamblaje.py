# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Etapa 1d: ensamblaje sin panel, por las ventanillas de FreeWorks: insertar componentes
(`assembly_drop.insert_files`), relaciones de posición SW (`mates_sw.create_joint`, `applicable`,
`entities_from_selection`, `solve`), fijar / flotar, matriz y simetría de componentes
(`component_patterns.pick_from_selection`, `direction_object`, `make_linear`, `make_circular`,
`make_mirror`). El taladro y el corte de ensamblaje son de los "delicados": van por 'panel'.

Las referencias se arman eligiendo en FreeCAD (como un clic) y leyendo lo elegido con las mismas
funciones que usa el panel: así salen igual que hechas a mano. Formato para la IA:
'Componente.FaceN' (etiqueta o nombre del componente + cara/arista de la pieza), 'Componente' (la
pieza entera), un plano o eje del ensamblaje por su nombre, o XY / XZ / YZ / X / Y / Z del origen.
"""

import FreeCAD

from swui.fork.ia.herramientas import comun as c
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult

ALIASES = {"coincidente": "coincident", "paralela": "parallel", "perpendicular": "perpendicular",
           "tangente": "tangent", "concentrica": "concentric", "concéntrica": "concentric", "bloquear": "lock",
           "distancia": "distance", "angulo": "angle", "ángulo": "angle"}
ORIGIN = {"XY": "XY_Plane", "XZ": "XZ_Plane", "YZ": "YZ_Plane", "X": "X_Axis", "Y": "Y_Axis", "Z": "Z_Axis"}


def _asm(doc):
    from swui.fork import mates_sw

    FreeCAD.setActiveDocument(doc.Name)
    asm = mates_sw.ensure_active()
    if asm is None:
        raise c.Problema("%s no tiene un ensamblaje (o tiene varios: activá uno)." % doc.Label)
    return asm


def _component(doc, asm, name):
    obj = c.find(doc, name)
    if obj not in asm.Group or not obj.TypeId.startswith(("App::Link", "Assembly::AssemblyLink")):
        raise c.Problema("%s no es un componente del ensamblaje." % c.label_of(obj))
    return obj


def _path(doc, asm, text):
    """Ruta de selección dentro del ensamblaje para 'Componente.FaceN', un plano o el origen."""
    key = str(text).strip()
    if key.upper() in ORIGIN:
        for f in asm.Origin.OriginFeatures:
            if getattr(f, "Role", "") == ORIGIN[key.upper()]:
                return "%s.%s." % (asm.Origin.Name, f.Name)
        raise c.Problema("El ensamblaje no tiene %s." % key)
    name, _, sub = key.partition(".")
    obj = c.find(doc, name)
    if obj.TypeId.startswith(("Part::Datum", "App::Plane", "App::Line")):
        return "%s." % obj.Name
    comp = _component(doc, asm, name)
    if not sub:
        return "%s." % comp.Name
    linked = comp.LinkedObject
    inner = linked.Name if linked is not None and linked.TypeId != "App::Part" else ""
    return "%s.%s%s" % (comp.Name, inner + "." if inner else "", sub)


def _select(doc, asm, refs):
    import FreeCADGui

    FreeCADGui.Selection.clearSelection()
    for ref in refs:
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, _path(doc, asm, ref))


def componentes(documento=None):
    from swui.fork import mates_sw

    doc = c.document(documento)
    asm = _asm(doc)
    comps = []
    for o in asm.Group:
        if not o.TypeId.startswith(("App::Link", "Assembly::AssemblyLink")):
            continue
        linked = o.getLinkedObject(True)
        row = {"nombre": o.Name, "etiqueta": o.Label, "pieza": linked.Label if linked else None,
               "archivo": linked.Document.FileName if linked else None,
               "posicion": c.vec(o.Placement.Base), "fijo": mates_sw.grounded_joint(asm, o) is not None,
               "visible": bool(o.Visibility)}
        if hasattr(o, "Configuracion"):
            row["configuracion"] = o.Configuracion
        comps.append(row)
    mates = []
    for j in mates_sw.joints_of(asm):
        mates.append({"nombre": j.Name, "etiqueta": j.Label, "tipo": mates_sw.key_of(j),
                      "estado": [s for s in (getattr(j, "State", None) or []) if s in ("Invalid", "Touched")]})
    return ToolResult(success=True, output="%s: %d componentes, %d relaciones." % (asm.Label, len(comps), len(mates)),
                      data={"ensamblaje": asm.Name, "componentes": comps, "relaciones": mates})


def insertar_componente(archivos, documento=None):
    import os

    from swui import assembly_drop

    doc = c.document(documento)
    c.require_free()
    asm = _asm(doc)
    missing = [p for p in archivos if not os.path.isfile(p)]
    if missing:
        raise c.Problema("No existen: %s" % missing)
    added = assembly_drop.insert_files(asm, list(archivos))
    if not added:
        raise c.Problema("No se insertó nada (¿el archivo no tiene una pieza?).")
    return ToolResult(success=True, output="Insertado: %s." % ", ".join(c.label_of(o) for o in added),
                      data={"componentes": [o.Name for o in added]})


def relacion(tipo, referencia1, referencia2, valor=None, documento=None):
    import FreeCADGui

    from swui.fork import mates_sw

    doc = c.document(documento)
    c.require_free()
    asm = _asm(doc)
    key = ALIASES.get(str(tipo).lower(), str(tipo).lower())
    if key not in mates_sw.MATES:
        raise c.Problema("Relación \"%s\" desconocida: %s" % (tipo, ", ".join(ALIASES)))
    _select(doc, asm, [referencia1, referencia2])
    ents = mates_sw.entities_from_selection(asm)
    FreeCADGui.Selection.clearSelection()
    if len(ents) != 2:
        raise c.Problema("No pude armar las dos referencias (salieron %d)." % len(ents))
    kinds = [e[2] for e in ents]
    ok = mates_sw.applicable(kinds)
    if key not in ok:
        raise c.Problema("%s no se puede entre %s y %s. Se puede: %s" % (mates_sw.MATES[key][0], kinds[0], kinds[1],
                                                                       [mates_sw.MATES[k][0] for k in ok]))
    doc.openTransaction("IA: relación %s" % mates_sw.MATES[key][0])
    try:
        joint = mates_sw.create_joint(asm, key, [(e[0], e[1]) for e in ents], value=valor)
        result = mates_sw.solve(asm)
        doc.recompute()
    except Exception as exc:
        doc.abortTransaction()
        doc.recompute()
        raise c.Problema("No se pudo crear la relación: %s" % exc)
    miss = "" if result not in (0, None) else _unmet(doc, asm, key, [referencia1, referencia2], valor)
    if result not in (0, None) or miss:
        doc.abortTransaction()
        doc.recompute()
        raise c.Problema("La relación no se puede cumplir con las que ya hay (%s): no la dejé."
                         % (miss or "el ensamblaje no se resuelve"))
    doc.commitTransaction()
    return ToolResult(success=True, output="Relación %s entre %s y %s." % (joint.Label, referencia1, referencia2),
                      data={"relacion": joint.Name, "etiqueta": joint.Label})


def _unmet(doc, asm, key, refs, value):
    """Qué no se cumple después de resolver ("" si está bien). FreeCAD 1.1.4 no avisa una relación
    que choca con otras (resuelve 0 y la deja sin cumplir, visto el 01/11): se mide como en SW."""
    import FreeCADGui

    from swui.fork import mates_sw

    _select(doc, asm, refs)
    ents = mates_sw.entities_from_selection(asm)
    FreeCADGui.Selection.clearSelection()
    if len(ents) != 2 or any(e[3] is None for e in ents):
        return ""
    (k1, s1), (k2, s2) = [(e[2], e[3]) for e in ents]
    if k1 == k2 == "plane":
        n1, n2 = c.face_normal(s1.Faces[0]), c.face_normal(s2.Faces[0])
        gap = abs((s2.Faces[0].CenterOfMass - s1.Faces[0].CenterOfMass).dot(n1))
        if key in ("coincident", "distance", "parallel") and not c.parallel(n1, n2):
            return "las caras no quedaron paralelas"
        if key == "coincident" and gap > 0.01:
            return "las caras quedaron a %.3f mm" % gap
        if key == "distance" and value is not None and not c.close(gap, float(value)):
            return "las caras quedaron a %.3f mm, no a %s" % (gap, value)
        if key == "perpendicular" and abs(n1.dot(n2)) > 1e-3:
            return "las caras no quedaron perpendiculares"
        if key == "angle" and value is not None:
            ang = c.angle_deg(n1, n2)
            if not (c.close(ang, float(value), 0.05) or c.close(180 - ang, float(value), 0.05)):
                return "el ángulo quedó en %.2f°" % ang
    if key == "concentric" and k1 == k2 == "cylinder":
        a1, a2 = s1.Faces[0].Surface, s2.Faces[0].Surface
        off = (a2.Center - a1.Center)
        off = off - a1.Axis * off.dot(a1.Axis)
        if not c.parallel(a1.Axis, a2.Axis) or off.Length > 0.01:
            return "los ejes no quedaron alineados"
    return ""


def fijar(componente, fijo=True, documento=None):
    from swui.fork import mates_sw

    doc = c.document(documento)
    c.require_free()
    asm = _asm(doc)
    comp = _component(doc, asm, componente)
    current = mates_sw.grounded_joint(asm, comp)
    if bool(fijo) == (current is not None):
        return ToolResult(success=True, output="%s ya estaba %s." % (comp.Label, "fijo" if fijo else "flotante"))
    doc.openTransaction("IA: %s %s" % ("fijar" if fijo else "flotar", comp.Label))
    try:
        if fijo:
            import CommandCreateJoint

            CommandCreateJoint.createGroundedJoint(comp)
        else:
            doc.removeObject(current.Name)
        mates_sw.solve(asm)
        doc.recompute()
    except Exception as exc:
        doc.abortTransaction()
        raise c.Problema("No se pudo: %s" % exc)
    doc.commitTransaction()
    return ToolResult(success=True, output="%s quedó %s." % (comp.Label, "fijo" if fijo else "flotante"))


def _reference(doc, asm, ref, name, axis):
    import FreeCADGui

    from swui.fork import component_patterns as cp

    _select(doc, asm, [ref])
    picked = cp.pick_from_selection(asm)
    FreeCADGui.Selection.clearSelection()
    if len(picked) != 1:
        raise c.Problema("No pude usar \"%s\" como referencia." % ref)
    d, own = cp.direction_object(asm, picked[0], name, axis)
    if d is None:
        raise c.Problema("\"%s\" no sirve como %s." % (ref, "eje" if axis else "dirección o plano"))
    if own:
        cp.mark_own(d)
    return d


def matriz_componentes(tipo, componentes, referencia, cantidad, espaciado=None, angulo_total=360.0,
                       invertir=False, documento=None):
    from swui.fork import component_patterns as cp
    from swui.fork import mates_sw

    doc = c.document(documento)
    c.require_free()
    asm = _asm(doc)
    seeds = [_component(doc, asm, n) for n in componentes]
    doc.openTransaction("IA: matriz de componentes")
    try:
        if tipo == "lineal":
            if espaciado is None:
                raise c.Problema("Falta el espaciado.")
            d = _reference(doc, asm, referencia, "DireccionMatriz", False)
            v = cp.make_linear(asm, seeds, d, int(cantidad), float(espaciado), bool(invertir))
        elif tipo == "circular":
            d = _reference(doc, asm, referencia, "EjeMatriz", True)
            v = cp.make_circular(asm, seeds, d, int(cantidad), float(angulo_total), True, bool(invertir))
        else:
            raise c.Problema("Tipo \"%s\": lineal o circular." % tipo)
        doc.recompute()
        mates_sw.solve(asm)
    except c.Problema:
        doc.abortTransaction()
        raise
    except Exception as exc:
        doc.abortTransaction()
        raise c.Problema("No se pudo hacer la matriz: %s" % exc)
    doc.commitTransaction()
    return ToolResult(success=True, output="Matriz %s: %d instancias." % (v.Label, int(cantidad)),
                      data={"datos": v.Name})


def simetria_componentes(componentes, plano, documento=None):
    from swui.fork import component_patterns as cp

    doc = c.document(documento)
    c.require_free()
    asm = _asm(doc)
    seeds = [_component(doc, asm, n) for n in componentes]
    doc.openTransaction("IA: simetría de componentes")
    try:
        p = _reference(doc, asm, plano, "PlanoSimetria", False)
        v, warn = cp.make_mirror(asm, seeds, p, (), None)
        doc.recompute()
    except c.Problema:
        doc.abortTransaction()
        raise
    except Exception as exc:
        doc.abortTransaction()
        raise c.Problema("No se pudo hacer la simetría: %s" % exc)
    doc.commitTransaction()
    text = "Simetría %s." % v.Label
    if warn:
        text += (" OJO: no son simétricas en sí (%s); quedan copias de la misma pieza. Para la versión simétrica "
                 "(archivo nuevo) usá el panel." % ", ".join(warn))
    return ToolResult(success=True, output=text, data={"datos": v.Name})


_DOC = ToolParam("documento", "string", "Documento del ensamblaje (por defecto el activo)", required=False)


def register(registry):
    reg = registry.register
    reg(ToolDefinition(
        name="componentes",
        description="Componentes del ensamblaje (pieza, archivo, posición, fijo, configuración) y sus relaciones.",
        parameters=[_DOC], handler=c.guarded(componentes), category="ensamblaje", timeout=60))
    reg(ToolDefinition(
        name="insertar_componente",
        description="Inserta piezas guardadas (.FCStd) como componentes; el primero queda fijo, como en SW.",
        parameters=[ToolParam("archivos", "array", "Rutas de los archivos", items={"type": "string"}), _DOC],
        handler=c.guarded(insertar_componente), category="ensamblaje", timeout=180))
    reg(ToolDefinition(
        name="relacion",
        description=("Relación de posición SW entre dos referencias: coincidente, paralela, perpendicular, tangente, "
                     "concentrica, distancia (valor en mm), angulo (valor en grados) o bloquear. Referencias: "
                     "'Componente.FaceN' / 'Componente.EdgeN' (nombres de la pieza; ver 'geometria' sobre la pieza), "
                     "'Componente', un plano/eje del ensamblaje, o XY/XZ/YZ/X/Y/Z. Si no se puede resolver, no queda."),
        parameters=[ToolParam("tipo", "string", "Tipo de relación"),
                    ToolParam("referencia1", "string", "Primera referencia"),
                    ToolParam("referencia2", "string", "Segunda referencia"),
                    ToolParam("valor", "number", "Distancia (mm) o ángulo (°)", required=False), _DOC],
        handler=c.guarded(relacion), category="ensamblaje", timeout=120))
    reg(ToolDefinition(
        name="fijar",
        description="Fijar (fijo=true) o flotar (fijo=false) un componente, como Fijar / Flotar de SW.",
        parameters=[ToolParam("componente", "string", "Componente"),
                    ToolParam("fijo", "boolean", "true = fijar, false = flotar", required=False, default=True), _DOC],
        handler=c.guarded(fijar), category="ensamblaje", timeout=60))
    reg(ToolDefinition(
        name="matriz_componentes",
        description=("Matriz de componentes como SW: lineal (referencia = arista recta, cara plana (su normal), eje o "
                     "X/Y/Z; espaciado en mm) o circular (referencia = eje, arista circular o cara cilíndrica; "
                     "angulo_total). Cantidad = instancias en total."),
        parameters=[ToolParam("tipo", "string", "lineal o circular", enum=["lineal", "circular"]),
                    ToolParam("componentes", "array", "Componentes a repetir", items={"type": "string"}),
                    ToolParam("referencia", "string", "Dirección o eje"),
                    ToolParam("cantidad", "integer", "Instancias en total"),
                    ToolParam("espaciado", "number", "Espaciado en mm (lineal)", required=False),
                    ToolParam("angulo_total", "number", "Grados (circular)", required=False, default=360.0),
                    ToolParam("invertir", "boolean", "Invertir dirección", required=False, default=False), _DOC],
        handler=c.guarded(matriz_componentes), category="ensamblaje", timeout=180))
    reg(ToolDefinition(
        name="simetria_componentes",
        description=("Simetría de componentes respecto de un plano (cara plana de un componente, plano del ensamblaje "
                     "o XY/XZ/YZ): copias de la misma pieza. La versión simétrica (archivo nuevo) va por el panel."),
        parameters=[ToolParam("componentes", "array", "Componentes", items={"type": "string"}),
                    ToolParam("plano", "string", "Plano de simetría"), _DOC],
        handler=c.guarded(simetria_componentes), category="ensamblaje", timeout=180))
