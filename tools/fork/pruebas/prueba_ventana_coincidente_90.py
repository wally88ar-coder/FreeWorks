# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Error #58: relación Coincidente / Distancia / Paralela entre dos caras planas que están a 90°
justos (dos cajas sin girar, una cara de costado contra una de frente). El solver de FreeCAD 1.1 no
movía la pieza y decía que había resuelto. Ahora, como SW, la gira: las caras quedan paralelas
(coincidente: pegadas y cara contra cara; distancia: a la distancia pedida). Ctrl+Z deja la pieza
donde estaba y sin la relación; Ctrl+Y la vuelve a armar igual. Con caras ya paralelas no cambia
nada (la pieza no se da vuelta). Incluye una cara de adentro de una ranura (cara "dada vuelta":
el eje de su superficie apunta para adentro) y elegir primero la pieza que se mueve."""
TIPO = "completa"

import io  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import traza  # noqa: E402

# las piezas y el ensamblaje se arman igual que en la prueba al azar de ensamblaje
_src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "prueba_ventana_azar_ensamblaje.py"),
               encoding="utf-8").read()
_ns = {"__file__": __file__, "__name__": "aux_ensamblaje"}
exec(compile(_src[:_src.rindex("from _base import ejecutar")], "prueba_ventana_azar_ensamblaje.py", "exec"), _ns)
V = FreeCAD.Vector


def _ranura(carpeta):
    """Placa 60x40x10 con una ranura pasante de 20x20 (sus caras de adentro)."""
    doc = FreeCAD.newDocument("Placa")
    body = doc.addObject("PartDesign::Body", "Body")
    c = body.newObject("PartDesign::AdditiveBox", "Caja")
    c.Length, c.Width, c.Height = 60, 40, 10
    r = body.newObject("PartDesign::SubtractiveBox", "Ranura")
    r.Length, r.Width, r.Height = 20, 20, 10
    r.Placement.Base = V(20, 10, 0)
    doc.recompute()
    ruta = os.path.join(carpeta, "Placa.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    return ruta


def _cara_dada_vuelta(comp):
    """Una cara plana de adentro de la ranura cuya superficie apunta al revés que la cara."""
    shape = comp.LinkedObject.Shape
    for i, f in enumerate(shape.Faces):
        if f.Surface.__class__.__name__ != "Plane":
            continue
        u0, u1, v0, v1 = f.ParameterRange
        n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        if n.dot(f.Surface.Axis) < 0 and abs(n.z) < 1e-6:
            return "Face%d" % (i + 1)
    return None


def _caso(c1, c2, key, valor, rot, problemas, ranura=False, al_reves=False):
    from azar_comun import limpiar
    from swui.fork import mates_sw
    limpiar()
    carpeta = _ns["carpeta_temporal"]()
    rutas = [_ranura(carpeta) if ranura else _ns["_pieza"](carpeta, "Placa", 15.3, 11.0, 100.0),
             _ns["_pieza"](carpeta, "Bloque", 76.5, 69.1, 44.3)]
    doc, asm, (placa, bloque) = _ns["_ensamblaje"](rutas)
    if ranura:
        c1 = _cara_dada_vuelta(placa)
        if c1 is None:
            problemas.append("ranura: no encontré una cara dada vuelta (la prueba no prueba lo que dice)")
            return
        traza("  cara de la ranura dada vuelta: %s" % c1)
    bloque.Placement = FreeCAD.Placement(V(0, 53.8, -89.2), FreeCAD.Rotation(V(*rot[:3]), rot[3]))
    doc.recompute()
    antes = bloque.Placement
    _p, m1 = _ns["_plano"](_ns["_cara_global"](placa, c1))
    _p, m2 = _ns["_plano"](_ns["_cara_global"](bloque, c2))
    signo0 = m1.dot(m2)
    refs = [(placa, c1), (bloque, c2)]
    r = _ns["_relacionar"](doc, asm, key, refs[::-1] if al_reves else refs, valor)
    p1, n1 = _ns["_plano"](_ns["_cara_global"](placa, c1))
    p2, n2 = _ns["_plano"](_ns["_cara_global"](bloque, c2))
    que = "%s %s-%s giro %s%s%s" % (key, c1, c2, rot, " ranura" if ranura else "", " al revés" if al_reves else "")
    signo, d = n1.dot(n2), abs((p2 - p1).dot(n1))
    traza("  %s: r=%s signo=%.5f distancia=%.4f" % (que, r, signo, d))
    if r not in (0, None):
        problemas.append("%s: no se resolvió (%s)" % (que, r))
    if abs(abs(signo) - 1) > 1e-6:
        problemas.append("%s: las caras no quedaron paralelas (coseno %.5f)" % (que, signo))
    elif abs(signo0) < 1e-9 and key in ("coincident", "distance") and signo > 0:
        problemas.append("%s: quedaron paralelas pero no cara contra cara" % que)
    elif abs(signo0) > 1 - 1e-9 and signo * signo0 < 0:
        problemas.append("%s: ya eran paralelas y la pieza se dio vuelta" % que)
    if key in ("coincident", "distance") and abs(d - (valor or 0.0)) > 1e-2:
        problemas.append("%s: distancia entre caras %.4f, se pidió %s" % (que, d, valor or 0.0))
    despues = bloque.Placement
    juntas = len(mates_sw.joints_of(asm))
    doc.undo()
    doc.recompute()
    if not bloque.Placement.isSame(antes, 1e-6):
        problemas.append("%s: Ctrl+Z no dejó la pieza donde estaba" % que)
    if len(mates_sw.joints_of(asm)) != juntas - 1:
        problemas.append("%s: Ctrl+Z no sacó la relación" % que)
    doc.redo()
    doc.recompute()
    if not bloque.Placement.isSame(despues, 1e-4):
        problemas.append("%s: Ctrl+Y no la dejó igual que antes" % que)


def prueba():
    from azar_comun import comprobado, limpiar
    problemas = []
    sin_giro, en_y, en_z = (0, 0, 1, 0), (0, -1, 0, 2.0), (0, 0, 1, 1.0)
    for c1, c2, key, valor, rot, *extra in (
            ("Face1", "Face3", "coincident", None, sin_giro),   # costado contra frente, sin girar
            ("Face1", "Face3", "coincident", None, en_y),       # el caso que encontró el azar
            ("Face5", "Face1", "coincident", None, sin_giro),   # abajo contra costado
            ("Face5", "Face1", "coincident", None, en_z),
            ("Face1", "Face3", "distance", 12.5, sin_giro),
            ("Face1", "Face3", "parallel", None, sin_giro),
            ("Face1", "Face1", "coincident", None, sin_giro),   # ya paralelas: no se da vuelta
            ("Face1", "Face2", "coincident", None, en_y),
            ("Face1", "Face3", "coincident", None, sin_giro, False, True),  # primero la que se mueve
            (None, "Face5", "coincident", None, sin_giro, True),            # cara de la ranura
            (None, "Face1", "coincident", None, sin_giro, True),
            (None, "Face5", "distance", 3.0, sin_giro, True, True),
            # una cara dada vuelta contra una que no (en una caja, Face2, Face4 y Face6 no lo están):
            # si las dos lo están, un error al elegir el lado se anula y no se ve
            (None, "Face6", "coincident", None, sin_giro, True),
            (None, "Face4", "coincident", None, sin_giro, True, True),
            ("Face1", "Face6", "coincident", None, sin_giro)):
        _caso(c1, c2, key, valor, rot, problemas, *extra)
        comprobado()
    limpiar()
    assert not problemas, "\n".join(problemas)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
