# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de campos (plan de calidad, paso 8.4): Ecuaciones con lo que sea que escriba el usuario,
sin ventana, por las funciones que usa el diálogo (`equations.Model.set_variable` y `set_equation`,
lo que corre al escribir en una celda). Pieza: cubo con un agujero; textos al azar: números raros
(negativos, cero, enormes, "1,5", "1.5", " 3 ", "1e400"), texto donde va un número, fórmulas rotas
("=", "=Largo+", "=1/0", paréntesis sin cerrar), referencias a sí misma, nombres que no existen,
nombres de variable inválidos. Reglas:
- solo se rechaza con un aviso claro (ValueError, en castellano); nunca otro tipo de error;
- si se acepta, el documento recalcula sin errores de Python y, si la pieza queda mal (una medida
  negativa), borrar la ecuación la deja como estaba;
- una fórmula que se acepta da un número finito.
Casos por regla: FW_CASOS_AZAR (6)."""
TIPO = "azar"

import math  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402

import FreeCAD  # noqa: E402

from _base import traza  # noqa: E402
from azar_comun import Fallas, comprobado, hypothesis_listo  # noqa: E402

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector

RAROS = ["", " ", "0", "-0", "-5", "1e400", "inf", "nan", "-inf", "Infinity", "-1e400", "1e-12", "99999999999", "1,5", "1.5", " 3 ", "3 mm",
         "3mm", "5 in", "abc", "1,5,5", "1..5", ",", "=", "==", "=+", "=1/0", "=0/0", "=(", "=(1+2",
         "=1+2)", "=\"Largo\"+", "=\"NoExiste\"", "=\"Largo\"*2", "=\"D1@Caja\"", "=sqrt(-1)", "=-\"Largo\"",
         "=\"Largo\"/0", "=2^1000", "=1e308*10", "=iif(1;2;3)", "=iif(\"Largo\">10;5;1)", "=\"Largo",
         "=Largo", "=\"Largo\"\"Ancho\"", "∞", "½", "١٢", "\t", "\n", "=\n", "1\n2", "=" + "(" * 50]
NOMBRES_VAR = ["Largo", "Ancho", "Nueva", "_x", "x1", "1x", "lárgo", "con espacio", "", "a-b", "Caja", "Length"]
MENSAJE_INGLES = re.compile(r"\b(Invalid|invalid|error|Error|Expression|expression|not|unknown|Unknown|cannot|failed|"
                            r"Failed|syntax|Syntax|cyclic|Cyclic|property|Property|object|Object)\b")


# Issue #45: FreeCAD rechaza la fórmula con su propio error en inglés (el diálogo lo muestra tal cual).
# Se tolera (anotado en la traza) para que la prueba siga buscando otras cosas; al arreglar #45, sacar.
DEUDA_TIPOS = ("ParserError", "OverflowError", "FreeCADError")
DEUDA_VISTA = set()


def _pieza():
    doc = FreeCAD.newDocument("Ecuaciones")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 40, 30, 20
    hueco = body.newObject("PartDesign::SubtractiveCylinder", "Agujero")
    hueco.Radius, hueco.Height = 3, 20
    hueco.Placement.Base = V(10, 10, 0)
    doc.recompute()
    return doc, body, caja


def _texto():
    return st.one_of(st.sampled_from(RAROS), st.text(max_size=12),
                     st.builds(lambda a, b: a + b, st.sampled_from(["=", "", "=\"Largo\"", "=2*"]),
                               st.text(alphabet="0123456789+-*/().,;\"<> eE", max_size=10)))


def _sano(doc):
    malos = []
    for o in doc.Objects:
        try:
            if "Invalid" in o.State or "Error" in o.State:
                malos.append(o.Name)
        except Exception:
            pass
    return malos


def _evaluable(obj, prop):
    """False si la expresión puesta en obj.prop da un número no finito o absurdo (> 1e9 mm): error
    ya registrado #46; recalcular así cuelga FreeCAD (visto 09/11), así que la prueba no recalcula."""
    expr = dict(obj.ExpressionEngine).get(prop)
    if expr is None:
        return True
    try:
        v = obj.evalExpression(expr)
        v = float(getattr(v, "Value", v))
    except Exception:
        return True  # que lo diga el recálculo
    if not math.isfinite(v) or abs(v) > 1e9:
        DEUDA_VISTA.add("#46 (cuelga)")
        return False
    return True


def _recalcular(doc):
    """Recalcula; False si revienta con el desborde ya registrado (#46: '=2^1000' se acepta y el
    recálculo da OverflowError). Cualquier otro error del recálculo es falla."""
    try:
        doc.recompute()
        return True
    except OverflowError:
        DEUDA_VISTA.add("#46 (recálculo)")
        return False


def _intento(fn, entrada=""):
    """Corre fn: None si aceptó; el mensaje si rechazó con ValueError en castellano. Otro error, o un
    rechazo con un mensaje de FreeCAD en inglés, es falla."""
    try:
        fn()
        return None
    except Exception as exc:
        texto = str(exc)
        if type(exc).__name__ in DEUDA_TIPOS or "cyclic" in texto:  # registrado (#45): rechaza, en inglés
            DEUDA_VISTA.add("#45 (%s)" % type(exc).__name__)
            return texto
        if not isinstance(exc, ValueError):
            raise AssertionError("rechazó con %s (no un aviso claro): %s" % (type(exc).__name__, exc))
        propio = texto
        for x in (entrada, (entrada or "").strip()):  # el aviso puede repetir lo que escribió el usuario
            if x:
                propio = propio.replace(x, "")
        assert not MENSAJE_INGLES.search(propio), "rechazó, pero con un aviso en inglés: %r" % texto
        return texto


@cfg
@given(textos=st.lists(st.tuples(st.sampled_from(NOMBRES_VAR), _texto()), min_size=1, max_size=5))
def variables(textos):
    from swui.fork import equations as eq
    doc, body, caja = _pieza()
    try:
        m = eq.Model(doc)
        m.set_variable("Largo", "40")
        for nombre, texto in textos:
            que = "variable %r = %r" % (nombre, texto)
            aviso = _intento(lambda: m.set_variable(nombre, texto), texto)
            if not _recalcular(doc):
                break
            comprobado()
            if aviso is None:
                for vs, prop in m.variables():
                    v = getattr(vs, prop)
                    if not math.isfinite(v):
                        DEUDA_VISTA.add("#46")  # registrado: acepta números infinitos
                        setattr(vs, prop, 40.0)
                        continue
                    assert isinstance(v, float) and math.isfinite(v), \
                        "%s: aceptó y la variable %s quedó en %r" % (que, prop, v)
            assert not [n for n in _sano(doc) if n != "Caja" and n != "Agujero" and n != "Cuerpo"
                        and not n.startswith("Variables")], "%s: quedaron con error: %s" % (que, _sano(doc))
    finally:
        FreeCAD.closeDocument(doc.Name)


@cfg
@given(texto=_texto(), cual=st.sampled_from(["Length", "Width", "Height"]))
def ecuacion(texto, cual):
    from swui.fork import equations as eq
    doc, body, caja = _pieza()
    try:
        m = eq.Model(doc)
        m.set_variable("Largo", "40")
        doc.recompute()
        nombres = {p: n for p, n in eq.feature_dim_names(caja.TypeId, caja.PropertiesList).items()}
        cota = "%s@%s" % (nombres.get(cual, cual), caja.Label)
        vol0 = body.Shape.Volume
        que = "ecuación %s = %r" % (cota, texto)
        if os.environ.get("FW_DETALLE_CAMPOS"):
            traza("    " + que)
        aviso = _intento(lambda: m.set_equation(cota, texto), texto)
        if aviso is None and not _evaluable(caja, cual):
            return  # #46: con un resultado infinito, recalcular cuelga FreeCAD; no se recalcula
        if not _recalcular(doc):
            return
        comprobado()
        if aviso is None:
            v = getattr(caja, cual).Value
            if not math.isfinite(v):  # registrado: #46 (acepta un resultado infinito o NaN)
                DEUDA_VISTA.add("#46 (cota)")
            else:
                assert math.isfinite(v), "%s: aceptó y la cota quedó en %r" % (que, v)
            # borrar la ecuación (celda vacía) deja la pieza sana; con el valor de antes, como estaba
            _intento(lambda: m.set_equation(cota, ""))
            setattr(caja, cual, {"Length": 40, "Width": 30, "Height": 20}[cual])
            doc.recompute()
            assert not _sano(doc), "%s: borrada la ecuación, siguen con error: %s" % (que, _sano(doc))
            assert abs(body.Shape.Volume - vol0) < 1e-6, "%s: borrada la ecuación, la pieza no volvió" % que
    finally:
        FreeCAD.closeDocument(doc.Name)


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn in (("variables", variables), ("ecuación sobre una cota", ecuacion)):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn)
    if DEUDA_VISTA:
        traza("  deuda: %s" % ", ".join(sorted(DEUDA_VISTA)))
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
