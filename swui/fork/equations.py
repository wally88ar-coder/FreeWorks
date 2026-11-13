# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Ecuaciones como en SOLIDWORKS: "Ecuaciones, variables globales y cotas" (fase 3).

Una tabla con dos partes, como SW:
- Variables globales: "Largo" = 100, "Ala" = "Largo" / 4 ... (con comentario).
- Ecuaciones: "D1@Croquis1" = "Largo" * 2, "D1@Extruir1" = "Espesor" ...
Columnas Nombre / Valor o ecuación / Se evalúa en / Comentarios. A la derecha, las
cotas del modelo: doble clic las inserta en la celda (o arma una ecuación nueva).
No modal (decisión del usuario, 2026-10-31): con la ventana abierta se puede girar la
vista, mostrar las cotas con doble clic y un clic en una cota la inserta, como en SW.
Aceptar guarda todo como un solo paso de deshacer; Cancelar deja todo como estaba
(si mientras tanto se hizo otra operación, FreeCAD ya cerró ese paso: Cancelar no la toca).

Por debajo, todo es nativo de FreeCAD (abre sin el addon):
- las variables globales son propiedades de un VarSet (App::VarSet) llamado
  "Variables globales" (nombre interno VARSET_NAME, estable); el comentario es la
  documentación de la propiedad. Se muestran también las de otros VarSet del documento.
- cada ecuación es una expresión de FreeCAD (la f(x) de la casilla). FreeCAD no les
  guarda comentario: los comentarios de las ecuaciones van en ese mismo VarSet, en la
  propiedad oculta NOTES_PROP (JSON {"Objeto|ruta": texto}, nombre estable).
- nombres de cotas como SW: "D1@Croquis1" (D1, D2... en el orden de las cotas del
  croquis; una cota con nombre propio se llama así). Al usar una cota sin nombre en
  una ecuación se le pone ese nombre (renameConstraint), así la ecuación no se corre
  si se borran cotas. Cotas de operaciones: D1@Extruir1 = profundidad, etc. (FEATURE_DIMS).
- funciones de SW: sqr -> sqrt, atn -> atan, arcsin/arccos, int -> trunc,
  iif(cond; sí; no) -> (cond ? sí : no). Coma decimal como en Argentina.
"""

import re

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

COMMAND = "SWUI_Equations"
VARSET_NAME = "VariablesGlobales"  # nombre interno del VarSet que crea el addon (estable)
VARSET_LABEL = "Variables globales"
VAR_GROUP = "Variables"
# VarSets donde FreeWorks guarda datos propios (no son variables): matrices de componentes
# (component_patterns.KIND) y taladro / corte de ensamblaje (assembly_features.KIND)
INTERNAL_VARSET_MARKS = ("SWUI_Pattern", "SWUI_AsmFeature")
NOTES_PROP = "SWUI_EquationNotes"  # comentarios de las ecuaciones, en el VarSet (nombre estable)
SKETCH_DIMS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")
VARSET_BASE = ("ExpressionEngine", "Label", "Label2", "Visibility", "Placement")

# Cotas de operaciones en el orden D1, D2... como las numera SW (propiedades de FreeCAD 1.1.4)
FEATURE_DIMS = {
    "PartDesign::Pad": ("Length", "Length2", "TaperAngle", "TaperAngle2", "Offset"),
    "PartDesign::Pocket": ("Length", "Length2", "TaperAngle", "TaperAngle2", "Offset"),
    "PartDesign::Revolution": ("Angle", "Angle2"),
    "PartDesign::Groove": ("Angle", "Angle2"),
    "PartDesign::Fillet": ("Radius",),
    "PartDesign::Chamfer": ("Size", "Size2", "Angle"),
    "PartDesign::Draft": ("Angle",),
    "PartDesign::Thickness": ("Value",),
    "PartDesign::Hole": ("Diameter", "Depth", "CounterboreDiameter", "CounterboreDepth",
                         "CountersinkAngle", "DrillPointAngle"),
    "PartDesign::LinearPattern": ("Length", "Occurrences", "Offset", "Length2", "Occurrences2", "Offset2"),
    "PartDesign::PolarPattern": ("Angle", "Occurrences", "Offset"),
    "PartDesign::Helix": ("Pitch", "Height", "Turns", "Angle"),
    "PartDesign::AdditiveHelix": ("Pitch", "Height", "Turns", "Angle"),
    "PartDesign::SubtractiveHelix": ("Pitch", "Height", "Turns", "Angle"),
    "PartDesign::AdditiveBox": ("Length", "Width", "Height"),
    "PartDesign::AdditiveCylinder": ("Radius", "Height"),
    "Part::Box": ("Length", "Width", "Height"),
    "Part::Cylinder": ("Radius", "Height"),
}
ANGLE_PROPS = ("Angle", "Angle2", "TaperAngle", "TaperAngle2", "CountersinkAngle", "DrillPointAngle")
COUNT_PROPS = ("Occurrences", "Occurrences2", "Turns")

SW_FUNCTIONS = {"sqr": "sqrt", "atn": "atan", "arcsin": "asin", "arccos": "acos", "int": "trunc"}

# Referencia de FreeCAD: Objeto.prop / <<Etiqueta>>.prop / Objeto.Constraints.D1 / ...[3]
REF_RE = re.compile(r"(<<[^>]+>>|[A-Za-z_][A-Za-z0-9_]*)((?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])+)")
QUOTED_RE = re.compile(r'"([^"]+)"')

_open = []


# --- Nombres de cotas como SW ---------------------------------------------


def sketch_dim_names(constraints):
    """
    {índice: nombre SW} de las cotas de un croquis. constraints = [(Tipo, Nombre)].
    Las cotas con nombre lo conservan; las otras son D1, D2... en orden, sin repetir nombres.
    """
    used = set(n for t, n in constraints if n)
    out, k = {}, 0
    for i, (kind, name) in enumerate(constraints):
        if kind not in SKETCH_DIMS:
            continue
        if name:
            out[i] = name
            continue
        k += 1
        while "D%d" % k in used:
            k += 1
        out[i] = "D%d" % k
        used.add(out[i])
    return out


def feature_dim_names(type_id, props):
    """{propiedad: 'D1'...} de una operación (solo las propiedades que tiene)."""
    names = [p for p in FEATURE_DIMS.get(type_id, ()) if p in props]
    return {p: "D%d" % (i + 1) for i, p in enumerate(names)}


def sw_function_names(text):
    """sqr( -> sqrt( etc. (palabras enteras)."""
    def repl(m):
        return SW_FUNCTIONS[m.group(1).lower()] + "("
    return re.sub(r"\b(sqr|atn|arcsin|arccos|int)\s*\(", repl, text, flags=re.IGNORECASE)


def _split_args(inner):
    """Argumentos de iif separados por ';' (o ',' si no hay ';'), respetando paréntesis."""
    sep = ";" if ";" in inner else ","
    out, depth, cur = [], 0, ""
    for ch in inner:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [a.strip() for a in out]


def convert_iif(text):
    """iif(cond; a; b) de SW -> ((cond) ? (a) : (b)) de FreeCAD (también anidados)."""
    while True:
        m = re.search(r"\biif\s*\(", text, flags=re.IGNORECASE)
        if not m:
            return text
        start, i, depth = m.start(), m.end(), 1
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        if depth:
            return text  # paréntesis sin cerrar: que lo diga FreeCAD
        args = _split_args(text[m.end():i - 1])
        if len(args) != 3:
            return text
        args = [convert_iif(a) for a in args]
        text = text[:start] + "((%s) ? (%s) : (%s))" % tuple(args) + text[i:]


def decimal_points(text):
    """'2,5' -> '2.5' (coma decimal entre dígitos; fuera de comillas)."""
    parts = re.split(r'("[^"]*")', text)
    return "".join(p if p.startswith('"') else re.sub(r"(\d),(\d)", r"\1.\2", p) for p in parts)


def to_freecad(text, resolve):
    """
    Ecuación como en SW -> expresión de FreeCAD. resolve(nombre) -> referencia de FreeCAD
    o None. Devuelve (expresión, [nombres que no existen]).
    """
    unknown = []
    body = decimal_points(text.strip().lstrip("="))

    def repl(m):
        ref = resolve(m.group(1).strip())
        if ref is None:
            unknown.append(m.group(1))
            return m.group(0)
        return ref

    body = QUOTED_RE.sub(repl, body)
    body = convert_iif(sw_function_names(body))
    return body.strip(), unknown


def to_sw(expr, name_of, local=None):
    """
    Expresión de FreeCAD -> como en SW. name_of(objeto, ruta) -> nombre SW o None.
    local = {propiedad: nombre SW} para las referencias sin objeto (FreeCAD escribe "Largo"
    en vez de "VariablesGlobales.Largo" dentro del mismo VarSet).
    """
    def repl(m):
        name = name_of(m.group(1), m.group(2))
        return '"%s"' % name if name else m.group(0)

    text = REF_RE.sub(repl, expr or "")
    if local:
        parts = re.split(r'("[^"]*")', text)
        word = re.compile(r"(?<![\w.])([A-Za-z_][A-Za-z0-9_]*)(?![\w(.])")
        parts = [p if p.startswith('"') else word.sub(lambda m: '"%s"' % local[m.group(1)]
                                                       if m.group(1) in local else m.group(0), p)
                 for p in parts]
        text = "".join(parts)
    # 2.5 -> 2,5 fuera de las comillas
    parts = re.split(r'("[^"]*")', text)
    return "".join(p if p.startswith('"') else re.sub(r"(\d)\.(\d)", r"\1,\2", p) for p in parts)


# --- Fórmulas que FreeCAD no puede calcular (Issues #45, #48, #49) ---------------------------


def is_freecad_word(name):
    """¿FreeCAD lee este nombre como unidad o constante (h, m, s, mm, kg, N, pi, e...)? Una
    variable con ese nombre no se puede usar en fórmulas (#48)."""
    if name in ("pi", "e"):
        return True
    try:
        FreeCAD.Units.Quantity(name)
        return True
    except Exception:
        return False


class Rejected(ValueError):
    """Rechazo propio, ya escrito en castellano para el usuario."""


def spanish_error(exc):
    """Lo que dice FreeCAD (en inglés) cuando no puede con una fórmula -> aviso en castellano.
    Los rechazos propios (Rejected) pasan tal cual."""
    if isinstance(exc, Rejected):
        return str(exc)
    # el error de verdad puede venir "debajo": '=2^1000' hace que recompute() devuelva un SystemError
    # ("returned a result with an exception set") con el OverflowError como causa (hallado 12/11)
    chain, seen = [], exc
    while seen is not None and len(chain) < 5:
        chain.append(seen)
        seen = seen.__cause__ or seen.__context__
    if any(isinstance(e, OverflowError) for e in chain):
        return "El resultado es demasiado grande (o no es un número)."
    inner = [e for e in chain[1:] if not isinstance(e, SystemError)]
    if isinstance(exc, SystemError) and inner:
        exc = inner[0]
    text = str(exc)
    low = text.lower()
    if "exception set" in low:
        return "FreeCAD no pudo calcular la fórmula."
    if "parse" in low or "syntax" in low or "unexpected" in low:
        return "La fórmula está mal escrita (revise paréntesis, signos y comas)."
    if "overflow" in low or "infinit" in low or "too large" in low:
        return "El resultado es demasiado grande (o no es un número)."
    if "unit" in low:
        return ("Las unidades no cierran (por ejemplo, un ángulo de atn() sumado a un número): "
                "FreeCAD no puede calcularla.")
    if "not found" in low:
        return "La fórmula usa algo que no existe (revise los nombres entre comillas)."
    if "can not evaluate" in low or "cannot evaluate" in low:
        return "La fórmula no da un número."
    if "division by zero" in low:
        return "La fórmula divide por cero."
    if "cyclic" in low or "circular" in low:
        return "La fórmula depende de sí misma (referencia circular)."
    return "FreeCAD no pudo calcular la fórmula (%s)." % text


def is_invalid(obj):
    return "Invalid" in list(getattr(obj, "State", []) or [])


def check_result(obj, prop=None, was_invalid=False):
    """Recalcula obj y comprueba que la fórmula dio algo usable (sin error, y finito si se da la
    propiedad). Si no, lanza la excepción con lo que dijo FreeCAD. Si obj YA estaba con error antes
    del cambio, ese error no es de la fórmula: no se rechaza (si no, una pieza rota no se podía
    arreglar cambiando medidas de a una; revisión del 11/11)."""
    import math

    obj.recompute()
    if is_invalid(obj) and not was_invalid:
        try:
            why = obj.getStatusString()
        except Exception:
            why = "Invalid"
        expression_words = ("parse", "syntax", "unexpected", "unit", "cyclic", "circular", "overflow",
                            "expression", "property binding", "not found", "division")
        if obj.TypeId not in ("App::VarSet", "Spreadsheet::Sheet") and not any(
                k in (why or "").lower() for k in expression_words):
            # la fórmula se calculó, pero con ese valor la OPERACIÓN no se puede construir (un
            # corte que sale del sólido...): como SW, se acepta y la operación queda con error en
            # el árbol (decisión del usuario, 11/11); `Model.warning` lo dice
            return
        raise RuntimeError(why or "Invalid")
    if prop is not None:
        value = getattr(obj, prop)
        value = getattr(value, "Value", value)
        if isinstance(value, (int, float)) and not math.isfinite(float(value)):
            raise OverflowError("not finite (infinite or nan)")


def check_finite(obj, expr):
    """La fórmula de una cota tiene que dar un número: '=sqrt(-1)', '=acos(2)' o '=1e308*10' dan
    "no es un número" o infinito y FreeCAD los acepta sin error (hallado por el fuzzing el 12/11,
    después de cerrar la Issue 46). Si FreeCAD no la puede evaluar sola, decide el recálculo."""
    import math

    try:
        value = obj.evalExpression(expr)
        value = float(getattr(value, "Value", value))
    except Exception:
        return
    if not math.isfinite(value):
        raise OverflowError("not finite (infinite or nan)")


def invalid_names(doc):
    """Nombres de los objetos del documento que hoy están con error."""
    return {o.Name for o in doc.Objects if is_invalid(o)}


def broken_warning(doc, before):
    """Después de un cambio aceptado: aviso con las operaciones que quedaron con error y antes no
    lo estaban (como SW, que acepta el valor y marca el error en el árbol), o "" si no hay."""
    doc.recompute()
    labels = sorted(o.Label for o in doc.Objects if is_invalid(o) and o.Name not in before)
    if not labels:
        return ""
    return ("Aplicado, pero con ese valor no se puede construir: %s (marcado con error en el árbol)."
            % ", ".join("«%s»" % lb for lb in labels))


def raw_value(obj, path):
    """El valor crudo de una cota o propiedad, para devolverlo tal cual (ver `restore`)."""
    try:
        if obj.TypeId == "Sketcher::SketchObject":
            p = path if path.startswith(".") else "." + path
            m = re.match(r"^\.Constraints(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\])$", p)
            if m is None:
                return None
            if m.group(2) is not None:
                index = int(m.group(2))
            else:
                index = [c.Name for c in obj.Constraints].index(m.group(1))
            return ("datum", index, obj.Constraints[index].Value)
        return ("prop", path.lstrip("."), getattr(obj, path.lstrip(".")))
    except Exception:
        return None


def restore(obj, path, expr, value=None):
    """Vuelve una propiedad a su fórmula de antes y, si no tenía, a su VALOR de antes (`raw_value`):
    una fórmula rechazada ya dejó su resultado escrito y quedaba la cota cambiada (revisión 11/11)."""
    try:
        obj.setExpression(path, expr)
        if expr is None and value is not None:
            if isinstance(value, tuple) and value and value[0] == "datum":
                obj.setDatum(value[1], value[2])
            elif isinstance(value, tuple) and value and value[0] == "prop":
                try:
                    setattr(obj, value[1], value[2])
                except Exception:
                    # '=acos(2)' en un largo dejó "nan deg": FreeCAD no acepta volver a "40 mm" sobre
                    # esas unidades, sí el número solo (fuzzing del 12/11)
                    setattr(obj, value[1], float(getattr(value[2], "Value", value[2])))
            else:
                setattr(obj, path.lstrip("."), value)
        obj.recompute()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Ecuaciones, volver atrás:\n%s\n" % __import__("traceback").format_exc())


def fmt(value, unit=""):
    if value is None:
        return ""
    text = ("%.6f" % value).rstrip("0").rstrip(".").replace(".", ",")
    if text == "-0":
        text = "0"
    return text + (" " + unit if unit else "")


# --- Documento ----------------------------------------------------------


class Model:
    """Variables globales, cotas y ecuaciones de un documento, con nombres SW."""

    def __init__(self, doc):
        self.doc = doc
        self.warning = ""  # lo deja el último cambio aceptado (operación que quedó con error, como SW)

    # objetos y nombres

    def varsets(self):
        return [o for o in self.doc.Objects if o.TypeId == "App::VarSet"]


    def main_varset(self, create=False):
        for vs in self.varsets():
            if vs.Name == VARSET_NAME or vs.Label == VARSET_LABEL:
                return vs
        if not create:
            # el primero del usuario; nunca uno de datos de FreeWorks (matriz de componentes...):
            # sus valores se mostraban como variables "sueltas" y una variable con ese nombre le
            # pisaba el espaciado (Issue #4). Esos siguen a la vista como "Espaciado@MatrizLineal1"
            own = [v for v in self.varsets() if not any(m in v.PropertiesList for m in INTERNAL_VARSET_MARKS)]
            return own[0] if own else None
        vs = self.doc.addObject("App::VarSet", VARSET_NAME)
        vs.Label = VARSET_LABEL
        return vs

    def variables(self):
        """[(varset, propiedad)] de todas las variables globales."""
        out = []
        for vs in self.varsets():
            if _sketch3d_of(vs) is not None:
                continue  # cotas de un croquis 3D: van como cotas (D1@Croquis3D1), no como variables
            for prop in vs.PropertiesList:
                if prop in VARSET_BASE or prop.startswith("SWUI_") or vs.getGroupOfProperty(prop) == "Base":
                    continue
                out.append((vs, prop))
        return out

    def var_display(self, vs, prop):
        sk = _sketch3d_of(vs)
        if sk is not None:
            return "%s@%s" % (prop, sk.Label)
        main = self.main_varset()
        return prop if vs is main else "%s@%s" % (prop, vs.Label)

    def _object(self, token, owner=None):
        if token.startswith("<<") and token.endswith(">>"):
            found = self.doc.getObjectsByLabel(token[2:-2])
            return found[0] if found else None
        return self.doc.getObject(token)

    def name_of(self, obj, path):
        """(objeto, ruta de FreeCAD) -> nombre SW ('D1@Croquis1', 'Largo') o None."""
        path = path if path.startswith((".", "[")) else "." + path
        if obj.TypeId == "App::VarSet":
            prop = path.lstrip(".")
            return self.var_display(obj, prop) if prop in obj.PropertiesList else None
        if obj.TypeId == "Sketcher::SketchObject":
            index = self._constraint_index(obj, path)
            if index is None:
                return None
            names = sketch_dim_names([(c.Type, c.Name) for c in obj.Constraints])
            name = names.get(index)
            return "%s@%s" % (name, obj.Label) if name else None
        prop = path.lstrip(".")
        names = feature_dim_names(obj.TypeId, obj.PropertiesList)
        if prop in names:
            return "%s@%s" % (names[prop], obj.Label)
        return "%s@%s" % (prop, obj.Label) if prop in obj.PropertiesList else None

    def _constraint_index(self, sketch, path):
        m = re.match(r"^\.Constraints(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\])$", path)
        if not m:
            return None
        if m.group(2) is not None:
            i = int(m.group(2))
            return i if i < len(sketch.Constraints) else None
        for i, c in enumerate(sketch.Constraints):
            if c.Name == m.group(1):
                return i
        return None

    def name_of_ref(self, token, path, owner=None):
        obj = self._object(token)
        if obj is None and owner is not None:  # referencia local: Constraints.D1 del mismo objeto
            obj, path = owner, "." + token + path
        return self.name_of(obj, path) if obj is not None else None

    def resolve(self, name, rename=True):
        """Nombre SW -> referencia de FreeCAD ('Sketch.Constraints.D1', 'VariablesGlobales.Largo')."""
        target = self.target(name, rename)
        if target is None:
            return None
        obj, path = target
        return obj.Name + (path if path.startswith((".", "[")) else "." + path)

    def target(self, name, rename=False):
        """Nombre SW -> (objeto, ruta de FreeCAD) o None. Con rename, pone nombre a la cota."""
        if "@" not in name:
            for vs, prop in self.variables():
                if self.var_display(vs, prop) == name:
                    return vs, prop
            return None
        short, label = name.split("@", 1)
        found = self.doc.getObjectsByLabel(label)
        if not found:
            return None
        obj = found[0]
        if obj.TypeId == "App::DocumentObjectGroup" and _sketch3d_of(obj) is not None:  # croquis 3D: sus cotas viven en su VarSet
            vs = getattr(obj, "SWUI_Sketch3D", None)
            return (vs, short) if vs is not None and short in vs.PropertiesList else None
        if obj.TypeId == "App::VarSet":
            return (obj, short) if short in obj.PropertiesList else None
        if obj.TypeId == "Sketcher::SketchObject":
            names = sketch_dim_names([(c.Type, c.Name) for c in obj.Constraints])
            for index, n in names.items():
                if n == short:
                    if not obj.Constraints[index].Name:
                        if not rename:
                            return obj, ".Constraints[%d]" % index
                        obj.renameConstraint(index, short)
                    return obj, ".Constraints." + short
            return None
        names = feature_dim_names(obj.TypeId, obj.PropertiesList)
        for prop, n in names.items():
            if n == short:
                return obj, prop
        return (obj, short) if short in obj.PropertiesList else None

    # valores

    def value(self, obj, path):
        """(valor, unidad) actual de una cota o variable."""
        try:
            if obj.TypeId == "Sketcher::SketchObject":
                index = self._constraint_index(obj, path if path.startswith(".") else "." + path)
                c = obj.Constraints[index]
                if c.Type == "Angle":
                    import math

                    return math.degrees(c.Value), "°"
                return c.Value, "mm"
            prop = path.lstrip(".")
            v = getattr(obj, prop)
        except Exception:
            return None, ""
        if hasattr(v, "Value") and hasattr(v, "Unit"):
            text = str(v.Unit)
            if prop in ANGLE_PROPS or "Angle" in text:
                return v.getValueAs("deg").Value, "°"
            if "Length" in text:
                return v.getValueAs("mm").Value, "mm"
            return v.Value, ""
        if isinstance(v, (int, float)):
            return float(v), ""
        return None, ""

    def expressions(self):
        """[(objeto, ruta, expresión)] de todo el documento, salvo las de las variables globales."""
        out = []
        for obj in self.doc.Objects:
            if (obj.TypeId == "App::VarSet" and _sketch3d_of(obj) is None) or hasattr(obj, "SWUI_ScopeOf"):
                continue  # las copias de un corte en otro sólido (multibody.py) siguen al original solas
            if "SWUI_Sketch3DDef" in obj.PropertiesList:
                continue  # fórmulas internas de las líneas de un croquis 3D (no son ecuaciones del usuario)
            for path, expr in getattr(obj, "ExpressionEngine", []):
                out.append((obj, path, expr))
        return out

    def expression_of(self, obj, path):
        for p, e in getattr(obj, "ExpressionEngine", []):
            if p == path or p == "." + path.lstrip(".") or p.lstrip(".") == path.lstrip("."):
                return e
        return None

    def sw_expr(self, obj, expr):
        local = None
        if obj.TypeId == "App::VarSet":
            local = {p: self.var_display(obj, p) for p in obj.PropertiesList if p not in VARSET_BASE}
        return to_sw(expr, lambda tok, path: self.name_of_ref(tok, path, obj), local)

    def all_dims(self):
        """[(nombre SW, objeto, ruta, valor, unidad)] de las cotas del modelo (para insertar)."""
        out = []
        for obj in self.doc.Objects:
            if obj.TypeId == "App::DocumentObjectGroup" and _sketch3d_of(obj) is not None:
                vs = getattr(obj, "SWUI_Sketch3D", None)
                from swui.fork import sketch3d

                for n, value, _line in sketch3d.dims(obj):
                    out.append(("%s@%s" % (n, obj.Label), vs, n, value, "mm"))
                continue
            if obj.TypeId == "Sketcher::SketchObject":
                names = sketch_dim_names([(c.Type, c.Name) for c in obj.Constraints])
                for index, n in names.items():
                    path = ".Constraints[%d]" % index
                    value, unit = self.value(obj, path)
                    out.append(("%s@%s" % (n, obj.Label), obj, path, value, unit))
            elif hasattr(obj, "SWUI_MoveFace") and obj.TypeId in ("PartDesign::Groove", "PartDesign::Revolution"):
                continue  # Mover cara de un agujero: su 360° es de adentro, no una cota de SW
            else:
                names = feature_dim_names(obj.TypeId, obj.PropertiesList)
                for prop, n in sorted(names.items(), key=lambda p: int(p[1][1:])):
                    value, unit = self.value(obj, prop)
                    if value is not None and self._relevant(obj, prop, value, n):
                        out.append(("%s@%s" % (n, obj.Label), obj, prop, value, unit))
        return out

    def _relevant(self, obj, prop, value, name):
        """¿Mostrar esta cota de operación? (los números D1, D2... no cambian aunque no se muestre)."""
        if self.expression_of(obj, prop):
            return True
        if prop == "Length" and getattr(obj, "Type", "Length") not in ("Length", "TwoLengths"):
            return False  # "Por todo", "Hasta cara"...: el largo no se usa (visto con el mouse, 31/10)
        if name == "D1":
            return True
        if prop in ("Length2", "Angle2"):
            return getattr(obj, "Type", "") in ("TwoLengths", "TwoAngles")
        return bool(value)

    # cambios

    def set_variable(self, name, text, comment=None):
        """
        Crea o cambia una variable global. text: '100', '2,5' o '= "Largo" / 2'. Todo o nada: si
        FreeCAD no puede calcularla (fórmula mal escrita, unidades que no cierran, resultado
        infinito) se deja todo como estaba, sin variable a medias, y se avisa en castellano
        (ValueError). Issues #45, #48, #49.
        """
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValueError("El nombre «%s» no sirve: solo letras sin acento, números y _, "
                             "empezando con letra." % name)
        target = self.target(name)
        created = target is None
        if created and is_freecad_word(name):
            raise ValueError("«%s» no se puede usar de nombre: FreeCAD lo toma como unidad o constante "
                             "(h = hora, m = metro, pi...). Use otro, por ejemplo «%s1» o «Alto»." % (name, name))
        text = (text or "").strip()
        new_set = False
        if created:
            # ¿hay que crear "Variables globales" para esta variable? (si se rechaza, se va también)
            new_set = not any(v.Name == VARSET_NAME or v.Label == VARSET_LABEL for v in self.varsets())
            vs = self.main_varset(create=True)
            vs.addProperty("App::PropertyFloat", name, VAR_GROUP, comment or "")
            prop, before = name, None
        else:
            vs, prop = target
            before = (self.expression_of(vs, prop), getattr(vs, prop))
        was_invalid = is_invalid(vs)
        self.warning = ""
        broken_before = invalid_names(self.doc)
        try:
            if text.startswith("="):
                expr, unknown = to_freecad(text, lambda n: self.resolve(n))
                if unknown:
                    raise Rejected("No existe: %s" % ", ".join('"%s"' % u for u in unknown))
                vs.setExpression(prop, expr)
            else:
                from swui.fork.material import parse_number

                number = parse_number(text)
                if number is None:
                    raise Rejected("«%s» no es un número (para una fórmula, empiece con =)." % text)
                vs.setExpression(prop, None)
                setattr(vs, prop, number)
            check_result(vs, prop, was_invalid=was_invalid)
        except Exception as exc:
            if created:
                vs.setExpression(prop, None)
                vs.removeProperty(prop)
                if new_set:  # "Variables globales" recién creado para esta variable: se va también
                    self.doc.removeObject(vs.Name)
            else:
                restore(vs, prop, *before)
            raise ValueError(spanish_error(exc)) from exc
        if comment is not None:
            vs.setDocumentationOfProperty(prop, comment)
        self.warning = broken_warning(self.doc, broken_before)
        return vs, prop

    def set_equation(self, name, text):
        """Ecuación sobre una cota: '"D1@Croquis1"' = text. text vacío la borra. Todo o nada, como
        `set_variable`: si FreeCAD no la puede calcular, la cota queda como estaba."""
        target = self.target(name, rename=True)
        if target is None:
            raise ValueError("No existe la cota «%s»." % name)
        obj, path = target
        if not (text or "").strip().lstrip("="):
            obj.setExpression(path, None)
            return obj, path
        expr, unknown = to_freecad(text, lambda n: self.resolve(n))
        if unknown:
            raise ValueError("No existe: %s" % ", ".join('"%s"' % u for u in unknown))
        before = self.expression_of(obj, path)
        old_value = raw_value(obj, path)
        was_invalid = is_invalid(obj)
        self.warning = ""
        broken_before = invalid_names(self.doc)
        try:
            check_finite(obj, expr)  # antes de ponerla: un "nan" escrito cambia hasta la unidad de la cota
            obj.setExpression(path, expr)
            plain = path.lstrip(".")  # una propiedad simple (no la cota de un croquis): también su resultado
            check_result(obj, plain if plain in obj.PropertiesList else None, was_invalid=was_invalid)
        except Exception as exc:
            restore(obj, path, before, old_value)
            raise ValueError(spanish_error(exc)) from exc
        self.warning = broken_warning(self.doc, broken_before)
        return obj, path

    def _notes(self):
        import json

        vs = self.main_varset()
        try:
            return json.loads(getattr(vs, NOTES_PROP, "") or "{}") if vs is not None else {}
        except ValueError:
            return {}

    def equation_comment(self, obj, path):
        return self._notes().get(note_key(obj, path), "")

    def set_equation_comment(self, obj, path, text):
        import json

        notes = self._notes()
        key = note_key(obj, path)
        if (text or "").strip():
            notes[key] = text
        elif key in notes:
            del notes[key]
        else:
            return
        vs = self.main_varset(create=True)
        if NOTES_PROP not in vs.PropertiesList:
            vs.addProperty("App::PropertyString", NOTES_PROP, "SWUI",
                           "Comentarios de las ecuaciones (fork de LikeSolidWorks UI)")
            vs.setEditorMode(NOTES_PROP, 2)
        setattr(vs, NOTES_PROP, json.dumps(notes, ensure_ascii=False, sort_keys=True))

    def remove_variable(self, vs, prop):
        users = [o.Label for o in self.doc.Objects for _p, e in getattr(o, "ExpressionEngine", [])
                 if re.search(r"\b%s\.%s\b" % (re.escape(vs.Name), re.escape(prop)), e)
                 or ("<<%s>>.%s" % (vs.Label, prop)) in e]
        if users:
            raise ValueError("La usan: %s. Quítela primero de esas ecuaciones." % ", ".join(sorted(set(users))))
        vs.removeProperty(prop)


def _sketch3d_of(obj):
    """Croquis 3D (sketch3d.py) del objeto si es el croquis o su VarSet de cotas; si no, None."""
    if obj is None:
        return None
    if obj.TypeId == "App::DocumentObjectGroup" and "SWUI_Sketch3D" in obj.PropertiesList:
        return obj
    if obj.TypeId == "App::VarSet":
        for parent in obj.InList:
            if "SWUI_Sketch3D" in parent.PropertiesList and getattr(getattr(parent, "SWUI_Sketch3D", None), "Name", None) == obj.Name:
                return parent
    return None


def note_key(obj, path):
    """Clave del comentario de una ecuación: 'Sketch|Constraints.D1' (Name: sigue aunque cambie el nombre)."""
    return "%s|%s" % (obj.Name, path.lstrip("."))


def count(doc):
    """Cantidad de variables globales + ecuaciones (para la franja del árbol)."""
    model = Model(doc)
    return len(model.variables()) + len(model.expressions())


# --- Ventana ------------------------------------------------------------

HEAD, VAR, NEW_VAR, EQ, NEW_EQ = "head", "var", "new_var", "eq", "new_eq"


def show_dialog(doc=None):
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    for d in list(_open):
        d.reject()
    dialog = _EquationsDialog(doc)
    _open.append(dialog)
    dialog.finished.connect(lambda *_a: _open.remove(dialog) if dialog in _open else None)
    dialog.show()
    dialog.raise_()
    return dialog


class _EquationsDialog(QtWidgets.QDialog):
    def __init__(self, doc):
        super().__init__(FreeCADGui.getMainWindow())
        self.doc = doc
        self.model = Model(doc)
        self.rows = []  # [(tipo, datos)] por renglón de la tabla
        self.filling = False
        self.setWindowTitle("Ecuaciones, variables globales y cotas")
        self.setModal(False)  # se puede tocar el modelo (clic en una cota la inserta), como pidió el usuario
        self.resize(900, 460)
        from swui.fork import safe_ops

        # paso propio, o sumado al de un panel abierto (abrir uno nuevo confirmaría el del panel
        # y su Cancelar ya no desharía: Issue #3)
        self.own_step = safe_ops.begin_step(doc, "Ecuaciones")
        # se tocó algo desde esta ventana: sin esto, con un panel abierto y sin cambios, Aceptar o
        # Cancelar recalculaban igual el documento a medio armar del panel (en ensamblaje, una
        # relación a medias hacía fallar el resolvedor: "Solve failed", 11/11)
        self.touched = False
        box = QtWidgets.QVBoxLayout(self)
        split = QtWidgets.QHBoxLayout()
        box.addLayout(split, 1)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nombre", "Valor / Ecuación", "Se evalúa en", "Comentarios"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 260)
        self.table.setColumnWidth(2, 110)
        self.table.itemChanged.connect(self._edited)
        self.table.installEventFilter(self)
        split.addWidget(self.table, 3)
        right = QtWidgets.QVBoxLayout()
        right.addWidget(QtWidgets.QLabel("Cotas del modelo (doble clic: insertar)"))
        self.dims = QtWidgets.QListWidget()
        self.dims.itemDoubleClicked.connect(self._insert_dim)
        right.addWidget(self.dims, 1)
        split.addLayout(right, 1)
        self.msg = QtWidgets.QLabel("Valor: un número (100 o 2,5). Ecuación: empieza con =, por ejemplo "
                                    '= "Largo" / 2. Supr borra el renglón elegido. Con la ventana abierta, '
                                    "doble clic en una cara muestra sus cotas y un clic en una cota la inserta.")
        self.msg.setWordWrap(True)
        box.addWidget(self.msg)
        row = QtWidgets.QHBoxLayout()
        b_del = QtWidgets.QPushButton("Eliminar renglón")
        b_del.clicked.connect(lambda *_a: self._delete_row())
        b_ok = QtWidgets.QPushButton("Aceptar")
        b_cancel = QtWidgets.QPushButton("Cancelar")
        b_ok.clicked.connect(self.accept)
        b_cancel.clicked.connect(self.reject)
        row.addWidget(b_del)
        row.addStretch(1)
        row.addWidget(b_ok)
        row.addWidget(b_cancel)
        box.addLayout(row)
        self._fill()
        try:
            from swui.fork import instant_dims

            instant_dims.set_pick(self._picked)
        except Exception:
            pass

    # --- tabla

    def _item(self, text, editable=False, bold=False, grey=False):
        item = QtWidgets.QTableWidgetItem(text)
        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        if bold:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        if grey:
            item.setForeground(QtGui.QBrush(QtGui.QColor("#808080")))
        return item

    def _add_row(self, kind, data, cells):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for col, item in enumerate(cells):
            self.table.setItem(r, col, item)
        self.rows.append((kind, data))

    def _fill(self):
        self.filling = True
        self.table.setRowCount(0)
        self.rows = []
        m = self.model
        self._add_row(HEAD, None, [self._item("Variables globales", bold=True)] + [self._item("") for _ in range(3)])
        for vs, prop in m.variables():
            expr = m.expression_of(vs, prop)
            value, _u = m.value(vs, prop)
            shown = "= " + m.sw_expr(vs, expr) if expr else fmt(value)
            self._add_row(VAR, (vs, prop), [
                self._item('"%s"' % m.var_display(vs, prop)), self._item(shown, editable=True),
                self._item(fmt(value)), self._item(vs.getDocumentationOfProperty(prop) or "", editable=True)])
        self._add_row(NEW_VAR, None, [self._item("Agregar variable global", editable=True, grey=True),
                                      self._item("", editable=True), self._item(""), self._item("", editable=True)])
        self._add_row(HEAD, None, [self._item("Ecuaciones", bold=True)] + [self._item("") for _ in range(3)])
        for obj, path, expr in m.expressions():
            name = m.name_of(obj, path) or "%s@%s" % (path.lstrip("."), obj.Label)
            value, unit = m.value(obj, path)
            state = "Error" if "Invalid" in getattr(obj, "State", []) else fmt(value, unit)
            self._add_row(EQ, (obj, path), [self._item('"%s"' % name), self._item("= " + m.sw_expr(obj, expr), editable=True),
                                           self._item(state), self._item(m.equation_comment(obj, path), editable=True)])
        self._add_row(NEW_EQ, None, [self._item("Agregar ecuación", editable=True, grey=True),
                                     self._item("", editable=True), self._item(""), self._item("", editable=True)])
        self.filling = False
        self._fill_dims()

    def _fill_dims(self):
        self.dims.clear()
        locked = set((o.Name, p.lstrip(".")) for o, p, _e in self.model.expressions())
        for name, obj, path, value, unit in self.model.all_dims():
            mark = "Σ " if (obj.Name, path.lstrip(".")) in locked or self.model.expression_of(obj, path) else ""
            item = QtWidgets.QListWidgetItem("%s%s = %s" % (mark, name, fmt(value, unit)))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, name)
            self.dims.addItem(item)

    # --- edición

    def _edited(self, item):
        if self.filling:
            return
        r, col = item.row(), item.column()
        kind, data = self.rows[r]
        name_cell = self.table.item(r, 0).text().strip().strip('"')
        value_text = self.table.item(r, 1).text().strip()
        self.touched = True
        try:
            if kind == VAR and col == 3:
                data[0].setDocumentationOfProperty(data[1], item.text())
                return
            if kind == EQ and col == 3:
                self.model.set_equation_comment(data[0], data[1], item.text())
                return
            if kind == VAR and col == 1:
                self.model.set_variable(self.model.var_display(*data), value_text)
            elif kind == NEW_VAR:
                if not value_text or name_cell == "Agregar variable global":
                    return
                comment = self.table.item(r, 3).text()
                self.model.set_variable(name_cell, value_text, comment)
            elif kind == EQ and col == 1:
                name = self.model.name_of(*data)
                self.model.set_equation(name, value_text)
            elif kind == NEW_EQ:
                if not value_text or name_cell == "Agregar ecuación":
                    return
                obj, path = self.model.set_equation(name_cell, value_text)
                comment = self.table.item(r, 3).text()
                if comment.strip():
                    found = [p for o, p, _e in self.model.expressions()
                             if o is obj and p.lstrip(".") == path.lstrip(".")]
                    self.model.set_equation_comment(obj, found[0] if found else path, comment)
            else:
                return
        except Exception as exc:
            self.msg.setText("No se aplicó: %s" % exc)
            self.msg.setStyleSheet("color: #c00000;")
            return
        warning = getattr(self.model, "warning", "")
        self.msg.setText(warning or "Aplicado.")
        self.msg.setStyleSheet("color: #b05a00;" if warning else "")
        self.doc.recompute()
        _refresh_dims()
        QtCore.QTimer.singleShot(0, self._fill)

    def _insert_dim(self, item):
        self._insert_name(item.data(QtCore.Qt.ItemDataRole.UserRole))

    def _picked(self, dim):
        """Clic en una cota del modelo (instant_dims) con la ventana abierta: como SW, va a la tabla."""
        kind, obj, which = dim.setter
        path = ".Constraints[%d]" % which if kind == "sketch" else which
        name = self.model.name_of(obj, path)
        if not name:
            return
        self._insert_name(name)
        self.raise_()
        self.activateWindow()

    def _insert_name(self, name):
        r = self.table.currentRow()
        kind = self.rows[r][0] if 0 <= r < len(self.rows) else None
        editor_text = '"%s"' % name
        if kind == NEW_EQ and self.table.item(r, 0).text().strip() in ("", "Agregar ecuación"):
            self.table.item(r, 0).setText(editor_text)  # cota a la que se le pone la ecuación
            self.table.setCurrentCell(r, 1)
            self.table.editItem(self.table.item(r, 1))
            return
        if kind in (VAR, NEW_VAR, EQ, NEW_EQ):
            cell = self.table.item(r, 1)
            text = cell.text() or "= "
            if not text.strip().startswith("="):
                text = "= " + text
            cell.setText(text.rstrip() + " " + editor_text)
            return
        # sin renglón elegido: ecuación nueva sobre esa cota
        last = len(self.rows) - 1
        self.filling = True
        self.table.item(last, 0).setText(editor_text)
        self.filling = False
        self.table.setCurrentCell(last, 1)
        self.table.editItem(self.table.item(last, 1))

    def _delete_row(self):
        r = self.table.currentRow()
        if not 0 <= r < len(self.rows):
            return
        kind, data = self.rows[r]
        self.touched = True
        try:
            if kind == VAR:
                self.model.remove_variable(*data)
            elif kind == EQ:
                data[0].setExpression(data[1], None)
                self.model.set_equation_comment(data[0], data[1], "")
            else:
                return
        except Exception as exc:
            self.msg.setText("No se borró: %s" % exc)
            self.msg.setStyleSheet("color: #c00000;")
            return
        self.doc.recompute()
        _refresh_dims()
        self._fill()

    def eventFilter(self, obj, event):
        if (obj is self.table and event.type() == QtCore.QEvent.Type.KeyPress
                and event.key() == QtCore.Qt.Key.Key_Delete and self.table.state() != QtWidgets.QAbstractItemView.State.EditingState):
            self._delete_row()
            return True
        return False

    # --- cerrar

    def _unpick(self):
        try:
            from swui.fork import instant_dims

            instant_dims.set_pick(None)
        except Exception:
            pass

    def _own_step_alive(self):
        """
        ¿El paso abierto sigue siendo el de Ecuaciones? Si mientras tanto se abrió un panel (otra
        operación, editar con doble clic), FreeCAD ya confirmó el de Ecuaciones y el abierto es el
        del panel: cerrarlo desde acá anulaba o confirmaba lo del panel (revisión del 11/11).
        """
        from swui.fork import safe_ops

        if not self.own_step:
            return False
        try:
            if safe_ops.task_open(self.doc):
                safe_ops.forget_step(self.doc)
                return False
        except Exception:  # el documento se cerró con la ventana abierta
            safe_ops.forget_step(self.doc)
            return False
        return True

    def accept(self):
        from swui.fork import safe_ops

        self._unpick()
        if self._own_step_alive():
            safe_ops.end_step(self.doc)
        if self.own_step or self.touched:
            self.doc.recompute()
        _refresh_dims()
        _changed()
        super().accept()

    def reject(self):
        self._unpick()
        from swui.fork import safe_ops

        # paso propio: se anula. Sumado al de un panel abierto: lo deshace el Cancelar del panel
        if self._own_step_alive():
            safe_ops.end_step(self.doc, abort=True)
        else:
            FreeCAD.Console.PrintWarning("[SWUI] Ecuaciones: hay un panel abierto; lo cambiado acá lo "
                                         "deshace el Cancelar del panel.\n")
        if self.own_step or self.touched:  # paso propio: lo anulado (también cotas cambiadas) se recalcula
            self.doc.recompute()
        _refresh_dims()  # Cancelar deshace: las cotas a la vista vuelven a los valores de antes
        _changed()
        super().reject()


def _refresh_dims():
    """Las cotas a la vista (instant_dims) con los valores nuevos; antes quedaban las viejas (31/10)."""
    try:
        from swui.fork import instant_dims

        instant_dims.refresh()
    except Exception:
        pass


_listeners = []


def add_listener(fn):
    if fn not in _listeners:
        _listeners.append(fn)


def _changed():
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            pass


class _EquationsCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": "Ecuaciones...", "ToolTip": "Ecuaciones, variables globales y cotas (como SW)",
                "Pixmap": paths.icon("fork/equations") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        show_dialog()


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _EquationsCommand())
    except Exception:
        pass  # ya registrado
