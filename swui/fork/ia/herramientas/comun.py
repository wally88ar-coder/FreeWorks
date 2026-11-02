# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Lo que comparten las herramientas: encontrar documento y objeto por nombre o etiqueta, describir
caras y aristas con números (la IA no ve la pieza: la conoce por su geometría), y la regla del
usuario (01/11): si el usuario tiene un panel o un croquis abierto, la IA no cambia nada, espera y
avisa.
"""

import math

import FreeCAD

from swui.fork.ia.terceros.registry import ToolResult

ROUND = 3
AXES = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}

# Lo pone en True el conductor de paneles (paso 1c) mientras maneja un panel abierto por la IA.
_state = {"ia_panel": False}


class Problema(Exception):
    """Error para la IA, con un texto claro (no un traceback)."""


def fail(text):
    return ToolResult(success=False, output="", error=text)


def guarded(fn):
    """Convertir Problema en un error limpio para la IA."""

    def wrapper(**kw):
        try:
            return fn(**kw)
        except Problema as exc:
            return fail(str(exc))

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def r(x):
    return round(float(x), ROUND)


def vec(v):
    return [r(v.x), r(v.y), r(v.z)]


def document(name=None):
    if name:
        doc = FreeCAD.listDocuments().get(name)
        if doc is None:
            for d in FreeCAD.listDocuments().values():
                if d.Label == name:
                    return d
            raise Problema("No hay un documento \"%s\" abierto." % name)
        return doc
    doc = FreeCAD.ActiveDocument
    if doc is None:
        raise Problema("No hay un documento abierto.")
    return doc


def find(doc, name):
    """Objeto por nombre interno o por etiqueta (la del árbol)."""
    if not name:
        raise Problema("Falta decir qué objeto.")
    obj = doc.getObject(name)
    if obj is not None:
        return obj
    found = doc.getObjectsByLabel(name)
    if len(found) == 1:
        return found[0]
    if found:
        raise Problema("Hay %d objetos con la etiqueta \"%s\": usá el nombre interno (%s)."
                       % (len(found), name, ", ".join(o.Name for o in found)))
    raise Problema("No hay un objeto \"%s\" en %s." % (name, doc.Label))


def label_of(obj):
    return "%s (%s)" % (obj.Label, obj.Name) if obj.Label != obj.Name else obj.Name


def user_busy():
    """Texto si el usuario tiene algo abierto que la IA no debe pisar; "" si está libre."""
    if _state["ia_panel"]:
        return ""
    import FreeCADGui

    try:
        gdoc = FreeCADGui.ActiveDocument
        editing = gdoc.getInEdit() if gdoc is not None else None
    except Exception:
        editing = None
    if editing is not None:
        obj = editing.Object
        what = "el croquis" if obj.TypeId.startswith("Sketcher::") else "el panel de"
        return "Tenés abierto %s %s. Cerralo y sigo (no toqué nada)." % (what, obj.Label)
    try:
        if FreeCADGui.Control.activeDialog():
            return "Tenés un panel abierto. Cerralo (Aceptar o Cancelar) y sigo (no toqué nada)."
    except Exception:
        pass
    return ""


def require_free():
    busy = user_busy()
    if busy:
        raise Problema(busy)


def solid_shape(obj):
    """Forma del objeto en coordenadas globales (Cuerpo: su sólido final)."""
    import Part

    try:
        shape = Part.getShape(obj, "", needSubElement=False, transform=True)
    except Exception:
        shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        raise Problema("%s no tiene un sólido." % label_of(obj))
    return shape


def sub_shape(obj, sub):
    import Part

    try:
        shape = Part.getShape(obj, sub, needSubElement=True, transform=True)
    except Exception as exc:
        raise Problema("No encuentro %s.%s (%s)." % (obj.Label, sub, exc))
    if shape is None or shape.isNull():
        raise Problema("No encuentro %s.%s." % (obj.Label, sub))
    return shape


def face_normal(face):
    u0, u1, v0, v1 = face.ParameterRange
    return face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)


def face_info(face, name):
    surf = face.Surface
    kind = type(surf).__name__
    out = {"nombre": name, "area": r(face.Area), "centro": vec(face.CenterOfMass)}
    if kind == "Plane":
        out["tipo"] = "plana"
        out["normal"] = vec(face_normal(face))
    elif kind == "Cylinder":
        out["tipo"] = "cilindrica"
        out["radio"] = r(surf.Radius)
        out["eje"] = vec(surf.Axis)
        out["centro_eje"] = vec(surf.Center)
        out["agujero"] = _is_hole(face)
    elif kind == "Cone":
        out["tipo"] = "conica"
        out["eje"] = vec(surf.Axis)
    elif kind == "Sphere":
        out["tipo"] = "esferica"
        out["radio"] = r(surf.Radius)
    else:
        out["tipo"] = "otra (%s)" % kind
    return out


def _is_hole(face):
    """Cilindro hueco (agujero) o macizo (perno): la normal apunta al eje en un agujero."""
    try:
        n = face_normal(face)
        u0, u1, v0, v1 = face.ParameterRange
        p = face.valueAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
        axis = face.Surface.Axis
        c = face.Surface.Center
        radial = (p - c) - axis * ((p - c).dot(axis))
        return n.dot(radial) < 0
    except Exception:
        return None


def edge_info(edge, name):
    curve = edge.Curve
    kind = type(curve).__name__
    out = {"nombre": name, "largo": r(edge.Length)}
    if kind in ("Line", "LineSegment"):
        out["tipo"] = "recta"
        out["desde"] = vec(edge.Vertexes[0].Point)
        out["hasta"] = vec(edge.Vertexes[-1].Point)
    elif kind == "Circle":
        full = edge.isClosed()
        out["tipo"] = "circulo" if full else "arco"
        out["radio"] = r(curve.Radius)
        out["centro"] = vec(curve.Center)
        out["eje"] = vec(curve.Axis)
    else:
        out["tipo"] = "otra (%s)" % kind
        out["centro"] = vec(edge.CenterOfMass)
    return out


def direction(text):
    """'+Z', '-x', 'z' o [x, y, z] -> FreeCAD.Vector unitario."""
    if isinstance(text, (list, tuple)) and len(text) == 3:
        v = FreeCAD.Vector(*[float(x) for x in text])
    else:
        key = str(text).strip().lower()
        if key in ("x", "y", "z"):
            key = "+" + key
        if key not in AXES:
            raise Problema("Dirección \"%s\": usá +X, -X, +Y, -Y, +Z, -Z o [x, y, z]." % text)
        v = FreeCAD.Vector(*AXES[key])
    if v.Length < 1e-9:
        raise Problema("Dirección nula.")
    return v.normalize()


def parallel(a, b, tol=1e-3):
    return abs(abs(a.dot(b)) - a.Length * b.Length) < tol


def same_dir(a, b, tol=1e-3):
    return (a.normalize() - b.normalize()).Length < tol


def close(a, b, tol=0.01):
    return abs(float(a) - float(b)) <= tol


def angle_deg(a, b):
    return math.degrees(a.getAngle(b))
