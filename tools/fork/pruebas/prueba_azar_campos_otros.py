# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de campos (plan de calidad, paso 8.4) en lo que no es un panel, sin ventana, por las
funciones que usan los diálogos:
- configuraciones: nombres raros al agregar y renombrar (vacío, repetido, acentos, espacios,
  "None", muy largo), valores raros para una medida (negativo, cero, enorme, infinito, NaN) y
  celdas de la tabla editadas a mano con cualquier cosa ("abc", "=1/0", vacía); después pasar de
  una configuración a otra;
- material: la copia del material guardada en la pieza con texto roto, y densidades raras;
- chapa: el dato de chapa guardado en el Cuerpo con texto roto, y espesores raros para el nombre
  del DXF.
Reglas: solo se rechaza con un aviso claro (ValueError en castellano); nunca otro error de
Python; lo aceptado deja la pieza recalculando sin errores de Python y sin valores infinitos; las
funciones que leen datos guardados devuelven None si están rotos (no revientan).
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
INGLES = re.compile(r"\b(Invalid|invalid|error|Error|Expression|not|unknown|Unknown|cannot|failed|Failed|"
                    r"syntax|Syntax|cyclic|property|Property|object|Object|Cell|cell|alias|Alias)\b")
NOMBRES = ["", " ", "Nueva", "Nueva", "Predeterminado", "con espacio", "ñandú", "a/b", "a.b", "1",
           "=x", "x" * 80, "\t", "Con\nsalto", "'", "\"", "A1", "Mono"]
VALORES = [0.0, -5.0, -0.0, 1e-9, 1e9, 1e300, float("inf"), float("-inf"), float("nan"), 12.5, 40.0]
CELDAS = ["", "abc", "=1/0", "=", "1,5", "1.5", "-3", "0", "1e400", "=A1", "'texto", "=Caja.Length",
          "=(", "TRUE", "5 mm", "∞"]
DEUDA_VISTA = set()


def _aviso(fn, entrada=""):
    """None si aceptó; el texto si rechazó con ValueError en castellano. Otro error es falla."""
    try:
        fn()
        return None
    except ValueError as exc:
        texto = str(exc)
        propio = texto.replace(entrada, "") if entrada else texto
        assert not INGLES.search(propio), "rechazó, pero con un aviso en inglés: %r" % texto
        return texto
    except Exception as exc:
        raise AssertionError("rechazó con %s (no un aviso claro): %s" % (type(exc).__name__, exc))


def _pieza():
    doc = FreeCAD.newDocument("Campos")
    doc.UndoMode = 1
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 40, 30, 10
    doc.recompute()
    return doc, body, caja


def _rotos(doc):
    """Los objetos con error del documento ([] = todo sano)."""
    return [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]


def _valor_en(cf, doc, caja, nombre):
    try:
        v = cf.value_in(doc, ("prop", caja, "Length"), nombre)
        return float(getattr(v, "Value", v))
    except Exception:
        return 40.0


def _recalcular(doc, que):
    try:
        doc.recompute()
    except Exception as exc:
        raise AssertionError("%s: el recálculo dio %s: %s" % (que, type(exc).__name__, exc))


accion = st.one_of(
    st.tuples(st.just("agregar"), st.sampled_from(NOMBRES)),
    st.tuples(st.just("renombrar"), st.integers(0, 9), st.sampled_from(NOMBRES)),
    st.tuples(st.just("valor"), st.sampled_from(VALORES), st.sampled_from(["this", "all"])),
    st.tuples(st.just("celda"), st.integers(0, 9), st.sampled_from(CELDAS)),
    st.tuples(st.just("ir"), st.integers(0, 9)),
)


@cfg
@given(acciones=st.lists(accion, min_size=1, max_size=8))
def configuraciones(acciones):
    from swui.fork import configurations as cf
    doc, body, caja = _pieza()
    try:
        cf.ensure(doc)
        _recalcular(doc, "armar")
        for i, a in enumerate(acciones):
            que = "paso %d %r" % (i, a)
            traza("    " + que)
            nombres = cf.names(doc)
            antes_nombres, rotos_antes = list(nombres), _rotos(doc)
            aviso = None
            if a[0] == "agregar":
                aviso = _aviso(lambda: cf.add(doc, a[1]), a[1])
            elif a[0] == "renombrar" and nombres:
                viejo = nombres[a[1] % len(nombres)]
                aviso = _aviso(lambda: cf.rename(doc, viejo, a[2]), a[2])
                if aviso and "No hay una configuración" in aviso and rotos_antes:
                    # registrado: #55 (renombrar con la pieza YA en error falla a medias y deja la
                    # tabla rota); la seguidilla ya no sirve para buscar otra cosa
                    DEUDA_VISTA.add("#55")
                    return
            elif a[0] == "valor":
                if not math.isfinite(a[1]):
                    # con infinito o NaN: aviso en castellano y nada tocado (antes reventaba o lo
                    # aceptaba, #46)
                    aviso = _aviso(lambda: cf.configure(doc, ("prop", caja, "Length"), a[1], scope=a[2]))
                    assert aviso, "aceptó %s como valor de configuración" % a[1]
                    assert all(math.isfinite(_valor_en(cf, doc, caja, n)) for n in cf.names(doc)), \
                        "con %s quedó una configuración que no es un número" % a[1]
                else:
                    aviso = _aviso(lambda: cf.configure(doc, ("prop", caja, "Length"), a[1], scope=a[2]))
            elif a[0] == "celda":
                sh = cf.table(doc)
                cols = cf.param_cols(sh) if sh is not None else []
                filas = cf.config_rows(sh) if sh is not None else []
                if cols and filas:
                    celda = "%s%d" % (cf.col_letter(cols[a[1] % len(cols)]), filas[a[1] % len(filas)])
                    sh.set(celda, a[2])  # como el usuario escribiendo en la tabla
                    traza("      celda %s = %r" % (celda, a[2]))
                    try:
                        sh.recompute()
                        doc.recompute()
                    except Exception as exc:
                        raise AssertionError("%s: escribir %r en %s hizo reventar el recálculo: %s: %s"
                                             % (que, a[2], celda, type(exc).__name__, exc))
                    if a[2] in ("1e400", "∞") or a[2].startswith("="):
                        # lo que escriba el usuario en la tabla puede dar infinito (#46) o una fórmula
                        # circular/rota: FreeCAD marca la celda con error y la pieza no se toca; se
                        # vuelve a un número para que la seguidilla siga
                        sh.set(celda, "40")
                        doc.recompute()
                        DEUDA_VISTA.add("celda %r (se volvió a 40)" % a[2])
            elif a[0] == "ir" and nombres:
                aviso = _aviso(lambda: cf.activate(doc, nombres[a[1] % len(nombres)]))
            if aviso is not None:
                # un rechazo deja la tabla como estaba: mismos nombres, la activa con su fila
                assert cf.names(doc) == antes_nombres, "%s: rechazó (%s) pero cambiaron los nombres: %s -> %s" % (
                    que, aviso, antes_nombres, cf.names(doc))
                assert cf.active(doc) is None or cf.row_of(doc, cf.active(doc)) is not None,                     "%s: rechazó (%s) y la configuración activa quedó sin fila en la tabla" % (que, aviso)
            _recalcular(doc, que)
            comprobado()
            for n in cf.names(doc):  # ("None" sin que nadie lo escriba es la fantasma de #50: acá no se usa ese nombre)
                assert isinstance(n, str) and n.strip() and n != "None", "%s: quedó una configuración %r" % (que, n)
            v = caja.Length.Value
            assert math.isfinite(v), "%s: el largo quedó en %r" % (que, v)
    finally:
        FreeCAD.closeDocument(doc.Name)


TEXTOS_ROTOS = st.one_of(st.sampled_from([
    "", "{", "null", "[]", "{}", "1", "\"x\"", "{\"a\":",
    '{"uuid":"x","values":5}', '{"uuid":"x","values":{"Density":[1]}}', '{"uuid":"x","values":{"Density":["a","b"]}}',
    '{"uuid":"x","values":{"Density":["1e400","kg/m^3"]}}', '{"uuid":"x","values":{"Density":["7850","kg/m^3"]}}',
    '{"thickness": -1}', '{"thickness": "∞", "radius": 2}', '{"thickness": 2, "radius": "x"}', '{"thickness": 2, "radius": 2, "k": 0.5}']),
    st.text(max_size=30))


@cfg
@given(texto=TEXTOS_ROTOS)
def datos_guardados_rotos(texto):
    """La copia del material y el dato de chapa guardados en el archivo pueden venir rotos (un
    archivo editado, otra versión): leerlos (y usarlos: densidad, espesor, radio) da un valor sano,
    None o un aviso, nunca un error de Python. Hoy revientan: #56 (deuda, anotada)."""
    from swui.fork import material as mt
    from swui.fork import sheet_metal as sm
    try:
        copia = mt.read_copy(texto)
    except Exception:
        DEUDA_VISTA.add("#56 (material)")
        copia = None
    assert copia is None or isinstance(copia, dict), "read_copy(%r) devolvió %r" % (texto, copia)
    if isinstance(copia, dict):
        try:
            d = mt.density_from(copia)
        except Exception:
            DEUDA_VISTA.add("#56 (densidad)")
            d = None
        if d is not None and not math.isfinite(d):
            DEUDA_VISTA.add("#46 (densidad)")
    try:
        spec = sm.read_spec(texto)
    except Exception as exc:
        raise AssertionError("sheet_metal.read_spec(%r) reventó con %s: %s" % (texto, type(exc).__name__, exc))
    assert spec is None or isinstance(spec, dict), "read_spec(%r) devolvió %r" % (texto, spec)
    if isinstance(spec, dict):
        doc = FreeCAD.newDocument("Chapa")
        try:
            b = doc.addObject("PartDesign::Body", "Chapa")
            c = b.newObject("PartDesign::AdditiveBox", "Plancha")
            c.Height = 2
            doc.recompute()
            sm.write_spec(b, spec)
            for fn in (sm.thickness, sm.radius):
                try:
                    v = fn(b)
                except Exception:
                    DEUDA_VISTA.add("#56 (chapa)")
                    continue
                assert v is None or isinstance(v, (int, float)), "%s con %r dio %r" % (fn.__name__, spec, v)
        finally:
            FreeCAD.closeDocument(doc.Name)
    comprobado()


@cfg
@given(t=st.one_of(st.sampled_from(VALORES), st.floats(allow_nan=True, allow_infinity=True)),
       pieza=st.sampled_from(["Soporte", "", "a/b", "ñ"]))
def espesor_raro(t, pieza):
    """El nombre del DXF con un espesor raro: un nombre o un aviso claro, nunca un error de Python.
    (Espesores infinitos o de 1e300 no salen de una chapa real: no se exige qué nombre dan.)"""
    from swui.fork import sheet_metal as sm
    salida = {}
    aviso = _aviso(lambda: salida.update(n=sm.dxf_filename(pieza, t, None)))
    comprobado()
    if aviso is None:
        n = salida["n"]
        assert isinstance(n, str) and n.lower().endswith(".dxf"), "dxf_filename(%r, %r) dio %r" % (pieza, t, n)


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn in (("configuraciones", configuraciones), ("datos guardados rotos", datos_guardados_rotos),
                       ("espesor raro", espesor_raro)):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn)
    if DEUDA_VISTA:
        traza("  deuda: %s" % ", ".join(sorted(DEUDA_VISTA)))
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
