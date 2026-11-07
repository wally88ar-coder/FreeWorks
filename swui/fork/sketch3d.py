# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Croquis 3D como en SW 2018, armado con objetos nativos de FreeCAD (sin motor propio).

FreeCAD 1.1.4 no tiene croquis 3D (el Sketcher resuelve solo en un plano). Acá cada línea es una
Línea nativa del banco Part (Part::Line) cuyos extremos son fórmulas:

  - punto compartido      X1 = Linea3D001.X2 (y lo mismo en Y y Z)
  - "A lo largo de X"     X2 = X1 + D1, Y2 = Y1, Z2 = Z1
  - cota                  propiedad de longitud de un VarSet del croquis ("D1@Croquis3D1" en Ecuaciones)
  - Igual / Paralela      el largo o la dirección salen de la otra línea

No hay resolvedor: cada línea depende de las anteriores (orden de dibujo). El archivo abre en
cualquier FreeCAD sin FreeWorks y las cotas se cambian igual; FreeWorks agrega dibujar y editar.

Regla "panel = cara de una función": todo lo que hace el panel (sketch3d_panel.py) está acá, en
funciones públicas que se pueden llamar por guion o desde la IA:

  new_sketch(doc)                        croquis 3D vacío ("Croquis3D1")
  add_line(sk, start, end)               línea; start/end con origin(), free(v), on_point(línea, 1|2),
                                         on_vertex(obj, "VertexN") y, para el final, along(eje, largo)
                                         o direction(vector, largo)
  set_length(línea, valor)               cota del largo (crea D1, D2...)
  set_dim(sk, "D1", valor)               cambiar una cota
  set_axis(línea, "X"|"Y"|"Z")           relación A lo largo de
  set_equal(línea, otra), set_parallel(línea, otra), fix(línea)
  delete_lines([líneas])                 las que dependían quedan donde estaban (sueltas)
  lines(sk), dims(sk), points(sk), is_defined(línea), update_colors(sk)

Nombres internos que quedan guardados en los archivos (estables para siempre):
  grupo  SWUI_Sketch3D (link al VarSet de cotas)
  VarSet cotas D1, D2... en el grupo de propiedades "Cotas"
  línea  SWUI_Sketch3DDef (definición JSON de sus puntas)
El VarSet y las líneas encuentran su croquis por el grupo que las contiene (InList): un link de
vuelta al grupo haría un ciclo (el grupo ya las tiene en Group) y FreeCAD no recalcula.
"""

import json
import math
import re

import FreeCAD

V = FreeCAD.Vector
AXES = {"X": V(1, 0, 0), "Y": V(0, 1, 0), "Z": V(0, 0, 1)}
MARK = "SWUI_Sketch3D"
DEF = "SWUI_Sketch3DDef"
DIM_GROUP = "Cotas"
DEFINED_COLOR = (0.0, 0.0, 0.0)  # negro: totalmente definida, como SW
UNDER_COLOR = (0.0, 0.0, 1.0)  # azul: insuficientemente definida
EPS = 1e-7


# --- Puntas (especificaciones) ------------------------------------------------------------------


def origin():
    return {"k": "origin"}


def free(v):
    """Punto suelto en el espacio (queda donde está; insuficientemente definido)."""
    return {"k": "free", "p": [float(v.x), float(v.y), float(v.z)]}


def fixed(v):
    """Punto fijo (relación Fijar)."""
    return {"k": "fix", "p": [float(v.x), float(v.y), float(v.z)]}


def on_point(line, end):
    """Coincidente con la punta 1 (inicio) o 2 (final) de otra línea del croquis."""
    return {"k": "pt", "o": line.Name, "e": int(end)}


def on_vertex(obj, sub):
    """Coincidente con un vértice del modelo ("Vertex3" de una pieza)."""
    v = obj.getSubObject(sub).Point if sub else V()
    return {"k": "vtx", "o": obj.Name, "s": sub, "p": [v.x, v.y, v.z]}


def along(axis, length, sign=1):
    """Final a lo largo de X, Y o Z. length: número (cota nueva), "D1" (cota existente) o None
    (largo suelto, sin cota). sign: +1 o -1 (sentido del eje)."""
    return {"k": "dir", "ax": axis.upper(), "s": 1 if sign >= 0 else -1, "len": _len_spec(length)}


def direction(vec, length=None):
    """Final en una dirección cualquiera (diagonal en el espacio). length como en along()."""
    vec = V(vec)
    if length is None:
        length = vec.Length
        spec = {"val": float(length)}
    else:
        spec = _len_spec(length)
    u = vec.normalize() if vec.Length > EPS else V(1, 0, 0)
    return {"k": "dir", "ax": None, "u": [u.x, u.y, u.z], "s": 1, "len": spec}


def _len_spec(length):
    if length is None:
        return None
    if isinstance(length, str):
        return {"dim": length}
    return {"new": float(length)}


# --- Objetos -------------------------------------------------------------------------------------


def is_sketch3d(obj):
    return obj is not None and obj.TypeId == "App::DocumentObjectGroup" and MARK in obj.PropertiesList


def is_line(obj):
    return obj is not None and obj.TypeId == "Part::Line" and DEF in obj.PropertiesList


def sketch_of(obj):
    """El croquis 3D de una línea, de su VarSet de cotas o el croquis mismo; si no, None."""
    if obj is None:
        return None
    if is_sketch3d(obj):
        return obj
    for parent in getattr(obj, "InList", []):
        if is_sketch3d(parent):
            return parent
    return None


def varset(sk):
    return getattr(sk, MARK, None)


def sketches(doc):
    return [o for o in doc.Objects if is_sketch3d(o)]


def lines(sk):
    return [o for o in sk.Group if is_line(o)]


def _next_label(doc, base):
    used = {o.Label for o in doc.Objects}
    n = 1
    while "%s%d" % (base, n) in used:
        n += 1
    return "%s%d" % (base, n)


def new_sketch(doc=None, label=None):
    """Crea un croquis 3D vacío: grupo "Croquis3D1" con su VarSet de cotas adentro."""
    doc = doc or FreeCAD.ActiveDocument
    sk = doc.addObject("App::DocumentObjectGroup", "Croquis3D")
    sk.Label = label or _next_label(doc, "Croquis3D")
    sk.addProperty("App::PropertyLink", MARK, "SWUI", "Cotas del croquis 3D (FreeWorks)")
    sk.setEditorMode(MARK, 2)
    vs = doc.addObject("App::VarSet", "Croquis3DCotas")
    vs.Label = "Cotas de " + sk.Label
    setattr(sk, MARK, vs)
    sk.addObject(vs)
    _hide_in_gui(vs)
    return sk


def _hide_in_gui(obj):
    try:
        if obj.ViewObject is not None:
            obj.ViewObject.ShowInTree = False
    except Exception:
        pass


def _definition(line):
    try:
        return json.loads(getattr(line, DEF) or "{}")
    except ValueError:
        return {}


def _save(line, d):
    setattr(line, DEF, json.dumps(d, sort_keys=True))


def add_line(sk, start, end, label=None):
    """Agrega una línea al croquis 3D. start: origin(), free(v), fixed(v), on_point(...), on_vertex(...).
    end: lo mismo, o along(...) / direction(...). Devuelve la línea (Part::Line)."""
    doc = sk.Document
    line = doc.addObject("Part::Line", "Linea3D")
    line.Label = label or _next_label(doc, "Línea3D")
    line.addProperty("App::PropertyString", DEF, "SWUI", "Definición de las puntas (FreeWorks)")
    line.setEditorMode(DEF, 2)
    sk.addObject(line)
    end = dict(end)
    if end.get("k") == "dir" and end.get("len") and "new" in end["len"]:
        end["len"] = {"dim": _new_dim(sk, end["len"]["new"])}
    _save(line, {"a": dict(start), "b": end})
    _apply(line)
    _style(line)
    return line


def _style(line):
    try:
        vo = line.ViewObject
        if vo is not None:
            vo.LineWidth = 2.0
            vo.PointSize = 5.0
    except Exception:
        pass


# --- Cotas -------------------------------------------------------------------------------------


def dims(sk):
    """[(nombre, valor en mm, línea que la usa o None)] en orden D1, D2..."""
    vs = varset(sk)
    if vs is None:
        return []
    users = {}
    for line in lines(sk):
        ln = _definition(line).get("b", {}).get("len") or {}
        if "dim" in ln:
            users[ln["dim"]] = line
    out = []
    for prop in vs.PropertiesList:
        if vs.getGroupOfProperty(prop) == DIM_GROUP and re.match(r"^D\d+$", prop):
            out.append((prop, getattr(vs, prop).getValueAs("mm").Value, users.get(prop)))
    return sorted(out, key=lambda t: int(t[0][1:]))


def _new_dim(sk, value):
    vs = varset(sk)
    n = max([int(d[0][1:]) for d in dims(sk)] + [0]) + 1
    name = "D%d" % n
    vs.addProperty("App::PropertyLength", name, DIM_GROUP, "Cota del croquis 3D")
    setattr(vs, name, abs(float(value)))
    return name


def _remove_dim(sk, name):
    vs = varset(sk)
    if vs is None or name not in vs.PropertiesList:
        return
    still = any((_definition(l).get("b", {}).get("len") or {}).get("dim") == name for l in lines(sk))
    if still:
        return
    try:
        vs.setExpression(name, None)
    except Exception:
        pass
    vs.removeProperty(name)


def set_dim(sk, name, value):
    """Cambia el valor de una cota (mm)."""
    setattr(varset(sk), name, abs(float(value)))
    sk.Document.recompute()


def dim_of(line):
    """Nombre de la cota del largo de la línea, o None."""
    ln = _definition(line).get("b", {}).get("len") or {}
    return ln.get("dim")


def set_length(line, value):
    """Cota del largo: si la línea va en una dirección, crea su cota (o la cambia); si termina en
    otro punto, no se puede (el largo lo da ese punto). Devuelve el nombre de la cota."""
    sk = sketch_of(line)
    d = _definition(line)
    b = d.get("b", {})
    if b.get("k") != "dir":
        _to_direction(line, d)
        b = d["b"]
    ln = b.get("len") or {}
    if "dim" in ln:
        set_dim(sk, ln["dim"], value)
        return ln["dim"]
    b["len"] = {"dim": _new_dim(sk, value)}
    _save(line, d)
    _apply(line)
    sk.Document.recompute()
    return b["len"]["dim"]


# --- Relaciones -----------------------------------------------------------------------------------


def _to_direction(line, d):
    """Pasa el final de la línea a "dirección + largo" con lo que mide ahora (para poder ponerle
    relaciones). Si el final estaba en otro punto, deja de estarlo."""
    a, b = point(line, 1), point(line, 2)
    vec = b - a
    u = V(vec).normalize() if vec.Length > EPS else V(1, 0, 0)
    d["b"] = {"k": "dir", "ax": None, "u": [u.x, u.y, u.z], "s": 1, "len": {"val": vec.Length}}


def set_axis(line, axis):
    """Relación A lo largo de X/Y/Z (el sentido sale de cómo está dibujada)."""
    axis = axis.upper()
    d = _definition(line)
    if d.get("b", {}).get("k") != "dir":
        _to_direction(line, d)
    b = d["b"]
    vec = point(line, 2) - point(line, 1)
    comp = getattr(vec, axis.lower())
    b["ax"], b["s"] = axis, (1 if comp >= 0 else -1)
    b.pop("u", None)
    b.pop("par", None)
    if not b.get("len"):
        b["len"] = {"val": abs(comp) or vec.Length or 10.0}
    elif "val" in b["len"]:
        b["len"]["val"] = abs(comp) or b["len"]["val"]
    _save(line, d)
    _apply(line)
    line.Document.recompute()


def set_parallel(line, other):
    """Relación Paralela: la dirección sale de la otra línea."""
    d = _definition(line)
    if d.get("b", {}).get("k") != "dir":
        _to_direction(line, d)
    b = d["b"]
    mine = point(line, 2) - point(line, 1)
    theirs = point(other, 2) - point(other, 1)
    b["ax"], b["par"] = None, other.Name
    b["s"] = 1 if mine.dot(theirs) >= 0 else -1
    b.pop("u", None)
    _save(line, d)
    _apply(line)
    line.Document.recompute()


def set_equal(line, other):
    """Relación Igual: el largo de la línea sale del de la otra (si tenía cota propia, se borra)."""
    d = _definition(line)
    if d.get("b", {}).get("k") != "dir":
        _to_direction(line, d)
    old = (d["b"].get("len") or {}).get("dim")
    other_dim = dim_of(other)
    d["b"]["len"] = {"dim": other_dim} if other_dim else {"same": other.Name}
    _save(line, d)
    if old and old != other_dim:
        _remove_dim(sketch_of(line), old)
    _apply(line)
    line.Document.recompute()


def fix(line):
    """Relación Fijar: las dos puntas quedan fijas donde están (deja de depender de otras)."""
    d = _definition(line)
    old = dim_of(line)
    d["a"], d["b"] = fixed(point(line, 1)), fixed(point(line, 2))
    _save(line, d)
    if old:
        _remove_dim(sketch_of(line), old)
    _apply(line)
    line.Document.recompute()


def relations(line):
    """Textos de las relaciones de la línea, como el cuadro Relaciones existentes de SW."""
    d = _definition(line)
    out = []
    tips = {1: "el inicio", 2: "el final"}
    for key, mine in (("a", "Inicio"), ("b", "Final")):
        s = d.get(key, {})
        k = s.get("k")
        if k == "origin":
            out.append("%s coincidente con el origen" % mine)
        elif k == "pt":
            other = line.Document.getObject(s["o"])
            out.append("%s coincidente con %s de %s" % (mine, tips.get(s["e"], ""), other.Label if other else s["o"]))
        elif k == "vtx":
            other = line.Document.getObject(s["o"])
            out.append("%s coincidente con %s de %s" % (mine, s.get("s"), other.Label if other else s["o"]))
        elif k == "fix":
            out.append("%s fijo" % mine)
    b = d.get("b", {})
    if b.get("k") == "dir":
        if b.get("ax"):
            out.append("A lo largo de %s" % b["ax"])
        if b.get("par"):
            other = line.Document.getObject(b["par"])
            out.append("Paralela a %s" % (other.Label if other else b["par"]))
        ln = b.get("len") or {}
        if "same" in ln:
            other = line.Document.getObject(ln["same"])
            out.append("Igual a %s" % (other.Label if other else ln["same"]))
        if "dim" in ln:
            sharing = [l for l in lines(sketch_of(line)) if l is not line and dim_of(l) == ln["dim"]]
            if sharing:
                out.append("Igual a %s" % ", ".join(l.Label for l in sharing))
            out.append("Cota %s" % ln["dim"])
    return out


# --- Borrar ------------------------------------------------------------------------------------------


def dependents(line):
    """Líneas del mismo croquis que usan esta (punto compartido, paralela, igual)."""
    out = []
    for other in lines(sketch_of(line)):
        if other is line:
            continue
        d = _definition(other)
        b = d.get("b", {})
        refs = {d.get("a", {}).get("o"), b.get("o"), b.get("par"), (b.get("len") or {}).get("same")}
        if line.Name in refs:
            out.append(other)
    return out


def delete_lines(to_delete):
    """Borra líneas. Las que dependían de ellas quedan donde estaban (punta suelta, dirección y
    largo fijos en el valor de ahora): no se acomodan, como avisa el plan."""
    to_delete = [l for l in to_delete if is_line(l)]
    if not to_delete:
        return []
    sk = sketch_of(to_delete[0])
    doc = sk.Document
    names = {l.Name for l in to_delete}
    touched = []
    for other in lines(sk):
        if other.Name in names:
            continue
        d = _definition(other)
        changed = False
        a, b = d.get("a", {}), d.get("b", {})
        if a.get("o") in names:
            d["a"] = free(point(other, 1))
            changed = True
        if b.get("o") in names:
            d["b"] = free(point(other, 2))
            changed = True
        if b.get("par") in names:
            vec = point(other, 2) - point(other, 1)
            u = V(vec).normalize() if vec.Length > EPS else V(1, 0, 0)
            b.pop("par", None)
            b["u"], b["s"] = [u.x, u.y, u.z], 1
            changed = True
        if (b.get("len") or {}).get("same") in names:
            b["len"] = {"val": (point(other, 2) - point(other, 1)).Length}
            changed = True
        if changed:
            _save(other, d)
            touched.append(other)
    old_dims = [dim_of(l) for l in to_delete]
    for l in to_delete:
        for p in ("X1", "Y1", "Z1", "X2", "Y2", "Z2"):
            try:
                l.setExpression(p, None)
            except Exception:
                pass
    for other in touched:
        _apply(other)
    for l in to_delete:
        doc.removeObject(l.Name)
    for name in old_dims:
        if name:
            _remove_dim(sk, name)
    doc.recompute()
    return touched


# --- Fórmulas ----------------------------------------------------------------------------------------


def _num(value):
    return "%.6f" % float(value)


def _mm(value):
    return "%s mm" % _num(value)


def _point_exprs(line, spec, end):
    """Fórmulas (x, y, z) de una punta, o None si va con valores fijos."""
    k = spec.get("k")
    if k == "origin":
        return ("0 mm", "0 mm", "0 mm")
    if k == "pt":
        o, e = spec["o"], spec["e"]
        if line.Document.getObject(o) is None:
            return None
        return tuple("%s.%s%d" % (o, c, e) for c in "XYZ")
    if k == "vtx":
        if line.Document.getObject(spec["o"]) is None:
            return None
        i = int(spec["s"][6:]) - 1
        return tuple("%s.Shape.Vertexes[%d].Point.%s * 1 mm" % (spec["o"], i, c) for c in "xyz")
    return None


def _length_expr(line, b):
    sk = sketch_of(line)
    ln = b.get("len") or {}
    if "dim" in ln and varset(sk) is not None and ln["dim"] in varset(sk).PropertiesList:
        return "%s.%s" % (varset(sk).Name, ln["dim"])
    if "same" in ln and line.Document.getObject(ln["same"]) is not None:
        return "%s.Shape.Length * 1 mm" % ln["same"]
    return _mm(ln.get("val", 10.0))


def _apply(line):
    """Escribe las fórmulas de la línea según su definición."""
    d = _definition(line)
    a, b = d.get("a", {}), d.get("b", {})
    exprs = {}
    pa = _point_exprs(line, a, 1)
    if pa is None:
        p = a.get("p", [line.X1.Value, line.Y1.Value, line.Z1.Value])
        for c, v in zip("XYZ", p):
            exprs[c + "1"] = None
            setattr(line, c + "1", v)
    else:
        for c, e in zip("XYZ", pa):
            exprs[c + "1"] = e
    if b.get("k") == "dir":
        length = _length_expr(line, b)
        s = "+" if b.get("s", 1) >= 0 else "-"
        if b.get("ax"):
            for c in "XYZ":
                exprs[c + "2"] = ("%s1 %s %s" % (c, s, length)) if c == b["ax"] else "%s1" % c
        elif b.get("par") and line.Document.getObject(b["par"]) is not None:
            o = b["par"]
            for c in "XYZ":
                exprs[c + "2"] = "%s1 %s %s * (%s.%s2 - %s.%s1) / (%s.Shape.Length * 1 mm)" % (
                    c, s, length, o, c, o, c, o)
        else:
            u = b.get("u", [1, 0, 0])
            for c, uc in zip("XYZ", u):
                exprs[c + "2"] = "%s1 %s %s * %s" % (c, s, length, _num(uc))
    else:
        pb = _point_exprs(line, b, 2)
        if pb is None:
            p = b.get("p", [line.X2.Value, line.Y2.Value, line.Z2.Value])
            for c, v in zip("XYZ", p):
                exprs[c + "2"] = None
                setattr(line, c + "2", v)
        else:
            for c, e in zip("XYZ", pb):
                exprs[c + "2"] = e
    for prop, e in exprs.items():
        try:
            line.setExpression(prop, e)
        except Exception:
            pass


# --- Lectura ------------------------------------------------------------------------------------------


def point(line, end):
    """Punta 1 o 2 de la línea (Vector, en mm), con lo último calculado."""
    if end == 1:
        return V(line.X1.Value, line.Y1.Value, line.Z1.Value)
    return V(line.X2.Value, line.Y2.Value, line.Z2.Value)


def points(sk):
    """[(línea, punta, Vector)] de todas las puntas del croquis (para enganchar)."""
    out = []
    for line in lines(sk):
        out.append((line, 1, point(line, 1)))
        out.append((line, 2, point(line, 2)))
    return out


def find_point(sk, v, tol=1e-4):
    """La punta del croquis que está en v (línea, punta) o None."""
    for line, e, p in points(sk):
        if (p - v).Length <= tol:
            return line, e
    return None


def _point_defined(line, key, seen):
    d = _definition(line)
    spec = d.get(key, {})
    k = spec.get("k")
    if k in ("origin", "fix", "vtx"):
        return True
    if k == "pt":
        other = line.Document.getObject(spec["o"])
        if other is None or (other.Name, spec["e"]) in seen:
            return False
        seen.add((other.Name, spec["e"]))
        return _point_defined(other, "a" if spec["e"] == 1 else "b", seen)
    if k == "dir" and key == "b":
        if not _point_defined(line, "a", seen):
            return False
        ln = spec.get("len") or {}
        if "dim" not in ln and "same" not in ln:
            return False
        if "same" in ln:
            other = line.Document.getObject(ln["same"])
            if other is None or not is_defined(other, seen):
                return False
        if spec.get("ax"):
            return True
        if spec.get("par"):
            other = line.Document.getObject(spec["par"])
            return other is not None and is_defined(other, seen)
        return False  # dirección libre: puede girar (SW la muestra azul)
    return False


def is_defined(line, seen=None):
    """¿Totalmente definida? (negro en SW). Las puntas sueltas o largos sin cota: no."""
    seen = set() if seen is None else seen
    if line.Name in seen:
        return False
    seen = set(seen) | {line.Name}
    return _point_defined(line, "a", set(seen)) and _point_defined(line, "b", set(seen))


def update_colors(sk):
    """Negro las definidas y azul las demás, como SW."""
    for line in lines(sk):
        try:
            color = DEFINED_COLOR if is_defined(line) else UNDER_COLOR
            vo = line.ViewObject
            if vo is not None:
                vo.LineColor = color
                vo.PointColor = color
        except Exception:
            pass


def state(sk):
    """"Totalmente definido" / "Insuficientemente definido" (como la barra de estado de SW)."""
    ls = lines(sk)
    if ls and all(is_defined(l) for l in ls):
        return "Totalmente definido"
    return "Insuficientemente definido"


def length(line):
    return (point(line, 2) - point(line, 1)).Length


def angle_deg(u, v):
    if u.Length < EPS or v.Length < EPS:
        return 0.0
    return math.degrees(u.getAngle(v))
