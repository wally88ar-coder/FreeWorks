# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Agente atacante, cota que sobra -> conducida (escrito sin mirar el código, desde lo que promete
driven_dims.make_driven_if_redundant(sketch, index=None) -> bool):
- la última relación (o la `index`), si es una cota conducente (Distance, DistanceX, DistanceY,
  Radius, Diameter, Angle) que deja el croquis con relaciones redundantes, pasa a conducida y
  devuelve True; el croquis queda sin redundantes ni conflictos y la cota conserva su valor;
- en cualquier otro caso (cota que no sobra, cota en CONFLICTO, relación que no es cota, cota ya
  conducida, croquis vacío, índice fuera de rango) devuelve False y no toca nada;
- nunca cambia otra relación (tipo, referencias, valor, nombre, conducente, activa, fórmula) ni
  mueve la geometría (constructiva y externa incluidas);
- no abre ni cierra pasos de deshacer: con una transacción abierta sigue abierta y la cantidad de
  pasos no cambia; al cerrarla, Deshacer vuelve la cota a conducente;
- croquis al azar (semilla fija): rectángulos con Igual, círculos con radio y diámetro, ángulos.
"""

import math  # noqa: E402
import random  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

from _base import traza  # noqa: E402

V = FreeCAD.Vector
COTAS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")
FALLAS = []


def _falla(caso, texto):
    traza("FALLA %s: %s" % (caso, texto))
    FALLAS.append("%s: %s" % (caso, texto))


# --- Fotos ---------------------------------------------------------------------------------------


def _foto_rel(sk):
    out = []
    for i, c in enumerate(sk.Constraints):
        out.append((c.Type, c.First, c.FirstPos, c.Second, c.SecondPos, c.Third,
                    round(float(c.Value), 6), c.Name, bool(c.Driving), bool(c.IsActive),
                    _expr(sk, i, c)))
    return out


def _expr(sk, i, c):
    claves = [".Constraints." + c.Name] if c.Name else []
    claves.append(".Constraints[%d]" % i)
    for camino, expr in sk.ExpressionEngine:
        if camino in claves:
            return expr
    return None


def _foto_geo(sk):
    out = []
    for g in sk.Geometry:
        pts = []
        if hasattr(g, "StartPoint"):
            pts += [g.StartPoint, g.EndPoint]
        if hasattr(g, "Center"):
            pts.append(g.Center)
        if hasattr(g, "Radius"):
            pts.append(V(g.Radius, 0, 0))
        out.append((type(g).__name__, [(round(p.x, 5), round(p.y, 5)) for p in pts]))
    ext = []
    for g in getattr(sk, "ExternalGeo", []) or []:
        if hasattr(g, "StartPoint"):
            ext.append((round(g.StartPoint.x, 5), round(g.StartPoint.y, 5),
                        round(g.EndPoint.x, 5), round(g.EndPoint.y, 5)))
    constr = [sk.getConstruction(i) for i in range(len(sk.Geometry))]
    return out, ext, constr


def _iguales_geo(a, b, tol=1e-4):
    if a[1] != b[1] or a[2] != b[2] or len(a[0]) != len(b[0]):
        return False
    for (ta, pa), (tb, pb) in zip(a[0], b[0]):
        if ta != tb or len(pa) != len(pb):
            return False
        for (x1, y1), (x2, y2) in zip(pa, pb):
            if abs(x1 - x2) > tol or abs(y1 - y2) > tol:
                return False
    return True


def _llamar(sk, index="omision"):
    from swui.fork import driven_dims
    if index == "omision":
        return driven_dims.make_driven_if_redundant(sk)
    return driven_dims.make_driven_if_redundant(sk, index)


def _comprobar(caso, sk, espera, index="omision", cambia=None, excepcion_ok=False):
    """Llama a la función y compara. `cambia` = índice de la relación que tiene que pasar a
    conducida si espera True (por omisión, la última)."""
    doc = sk.Document
    sk.solve()
    rel0, geo0 = _foto_rel(sk), _foto_geo(sk)
    pasos0, pend0 = doc.UndoCount, doc.HasPendingTransaction
    try:
        r = _llamar(sk, index)
    except Exception as e:  # noqa: BLE001
        if excepcion_ok and isinstance(e, (IndexError, ValueError)):
            r = False
        else:
            _falla(caso, "excepción %s: %s" % (type(e).__name__, e))
            return None
    if r is not True and r is not False:
        _falla(caso, "no devuelve bool sino %r" % (r,))
    if bool(r) != espera:
        _falla(caso, "devolvió %r, se esperaba %r (redundantes %r, conflicto %r)"
               % (r, espera, sk.RedundantConstraints, sk.ConflictingConstraints))
    if doc.UndoCount != pasos0 or doc.HasPendingTransaction != pend0:
        _falla(caso, "tocó el deshacer: pasos %d->%d, transacción abierta %r->%r"
               % (pasos0, doc.UndoCount, pend0, doc.HasPendingTransaction))
    sk.solve()
    rel1, geo1 = _foto_rel(sk), _foto_geo(sk)
    if len(rel1) != len(rel0):
        _falla(caso, "cambió la cantidad de relaciones %d->%d" % (len(rel0), len(rel1)))
        return r
    if cambia is None:
        cambia = len(rel0) - 1 if index in ("omision", None) else index
        if isinstance(cambia, int) and cambia < 0:
            cambia += len(rel0)
    for i, (a, b) in enumerate(zip(rel0, rel1)):
        if r and i == cambia:
            if b[8]:
                _falla(caso, "devolvió True pero la relación %d sigue conducente" % i)
            if a[:6] != b[:6] or a[7] != b[7] or a[9] != b[9]:
                _falla(caso, "la cota %d cambió algo más que conducente: %r -> %r" % (i, a, b))
            if abs(a[6] - b[6]) > 1e-4:
                _falla(caso, "la cota %d cambió de valor %r -> %r" % (i, a[6], b[6]))
            continue
        if a != b:
            _falla(caso, "cambió otra relación (%d): %r -> %r" % (i, a, b))
    if not _iguales_geo(geo0, geo1):
        _falla(caso, "se movió la geometría: %r -> %r" % (geo0, geo1))
    if r:
        if sk.RedundantConstraints or sk.ConflictingConstraints or sk.MalformedConstraints:
            _falla(caso, "quedó con redundantes %r / conflicto %r / mal formadas %r"
                   % (sk.RedundantConstraints, sk.ConflictingConstraints, sk.MalformedConstraints))
        doc.recompute()
        if "Invalid" in sk.State or "Error" in sk.State:
            _falla(caso, "el croquis quedó con error: %r" % (sk.State,))
    return r


# --- Croquis de partida ----------------------------------------------------------------------------


def _doc(nombre):
    doc = FreeCAD.newDocument(nombre)
    doc.UndoMode = 1
    return doc


def _rect(doc, w=10.0, h=6.0, x0=0.0, y0=0.0, igual=False, cotas=True, nombre="Croquis"):
    """Rectángulo 0..3 (abajo, der, arriba, izq), anclado en el origen con DistanceX/Y."""
    sk = doc.addObject("Sketcher::SketchObject", nombre)
    p = [V(x0, y0, 0), V(x0 + w, y0, 0), V(x0 + w, y0 + h, 0), V(x0, y0 + h, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(p[i], p[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 0))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sk.addConstraint(Sketcher.Constraint("Vertical", 1))
    sk.addConstraint(Sketcher.Constraint("Vertical", 3))
    sk.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 1, x0))
    sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 1, y0))
    if igual:
        sk.addConstraint(Sketcher.Constraint("Equal", 0, 1))
    if cotas:
        sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, w))
        if not igual:
            sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, h))
    sk.solve()
    return sk


def _add(sk, *args):
    return sk.addConstraint(Sketcher.Constraint(*args))


# --- Casos -----------------------------------------------------------------------------------------


def casos_fijos():
    doc = _doc("CotaSobra")

    # 1) Rectángulo con Igual y ancho: la altura sobra -> conducida
    sk = _rect(doc, 10, 10, igual=True)
    _add(sk, "DistanceY", 1, 1, 1, 2, 10.0)
    _comprobar("igual_altura_sobra", sk, True)

    # 2) Rectángulo libre en altura: la altura NO sobra -> False, nada cambia
    sk = _rect(doc, 10, 6, cotas=False)
    _add(sk, "DistanceX", 0, 1, 0, 2, 10.0)
    _add(sk, "DistanceY", 1, 1, 1, 2, 6.0)
    _comprobar("altura_no_sobra", sk, False)

    # 3) Círculo con radio y después diámetro (sobra el diámetro)
    sk = doc.addObject("Sketcher::SketchObject", "Circulo")
    c = sk.addGeometry(Part.Circle(V(3, 4, 0), V(0, 0, 1), 5))
    _add(sk, "Radius", c, 5.0)
    _add(sk, "Diameter", c, 10.0)
    _comprobar("radio_y_diametro", sk, True)
    # 3b) al revés: diámetro y después radio
    sk = doc.addObject("Sketcher::SketchObject", "Circulo2")
    c = sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 2.5))
    _add(sk, "Diameter", c, 5.0)
    _add(sk, "Radius", c, 2.5)
    _comprobar("diametro_y_radio", sk, True)

    # 4) Conflicto (diámetro que NO coincide): no es redundante -> False y nada cambia
    sk = doc.addObject("Sketcher::SketchObject", "Conflicto")
    c = sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 5))
    _add(sk, "Radius", c, 5.0)
    _add(sk, "Diameter", c, 12.0)
    _comprobar("diametro_en_conflicto", sk, False)
    # 4b) rectángulo cuadrado (Igual) con altura distinta del ancho
    sk = _rect(doc, 10, 10, igual=True, nombre="Conflicto2")
    _add(sk, "DistanceY", 1, 1, 1, 2, 20.0)
    _comprobar("igual_altura_en_conflicto", sk, False)

    # 5) Ángulos: recta horizontal + ángulo entre rectas; un ángulo absoluto de la segunda sobra
    sk = doc.addObject("Sketcher::SketchObject", "Angulos")
    a = sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)))
    b = sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(5, 5 * math.tan(math.radians(30)), 0)))
    _add(sk, "Coincident", a, 1, b, 1)
    _add(sk, "Horizontal", a)
    _add(sk, "Angle", a, b, math.radians(30))
    _add(sk, "Angle", b, math.radians(30))
    _comprobar("angulo_sobra", sk, True)
    # 5b) un tercer ángulo, en conflicto
    _add(sk, "Angle", b, math.radians(45))
    _comprobar("angulo_en_conflicto", sk, False)

    # 6) Relación que no es cota y sobra (Horizontal de más) -> False
    sk = _rect(doc, 8, 4, nombre="NoCota")
    _add(sk, "Horizontal", 0)
    _comprobar("horizontal_sobra_no_es_cota", sk, False)
    # 6b) Igual que sobra (rectángulo con ancho y alto iguales ya acotados)
    sk = _rect(doc, 7, 7, nombre="IgualSobra")
    _add(sk, "Equal", 0, 1)
    _comprobar("igual_sobra_no_es_cota", sk, False)

    # 7) Cota ya conducida que "sobra" -> False (ya es conducida)
    sk = _rect(doc, 10, 10, igual=True, nombre="YaConducida")
    n = _add(sk, "DistanceY", 1, 1, 1, 2, 10.0)
    sk.setDriving(n, False)
    _comprobar("ya_conducida", sk, False)

    # 8) Croquis vacío / sin relaciones
    sk = doc.addObject("Sketcher::SketchObject", "Vacio")
    _comprobar("vacio", sk, False, excepcion_ok=True)
    sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(3, 0, 0)))
    _comprobar("sin_relaciones", sk, False, excepcion_ok=True)

    # 9) index explícito: la redundante no es la última (después se agregó otra que no sobra)
    sk = _rect(doc, 10, 10, igual=True, nombre="Indice")
    i_sobra = _add(sk, "DistanceY", 1, 1, 1, 2, 10.0)
    ci = sk.addGeometry(Part.Circle(V(30, 0, 0), V(0, 0, 1), 2))
    _add(sk, "Radius", ci, 2.0)
    _comprobar("ultima_no_sobra_aunque_otra_si", sk, False)
    _comprobar("index_a_la_que_sobra", sk, True, index=i_sobra)

    # 10) índices negativos y fuera de rango
    sk = _rect(doc, 10, 10, igual=True, nombre="Negativo")
    _add(sk, "DistanceY", 1, 1, 1, 2, 10.0)
    k = len(sk.Constraints)
    # -1 a la Python = la última; si la función no lo acepta, que diga False sin tocar nada
    try:
        r = _llamar(sk, -1)
    except (IndexError, ValueError):
        r = False
    if r:
        if sk.Constraints[k - 1].Driving:
            _falla("index_-1", "devolvió True pero la última sigue conducente")
    sk2 = _rect(doc, 10, 10, igual=True, nombre="Negativo2")
    _add(sk2, "DistanceY", 1, 1, 1, 2, 10.0)
    # -k-5 no existe: False o excepción limpia, y nada cambia
    _comprobar("index_muy_negativo", sk2, False, index=-k - 5, excepcion_ok=True)
    _comprobar("index_fuera_de_rango", sk2, False, index=k + 3, excepcion_ok=True)
    _comprobar("index_None_es_la_ultima", sk2, True, index=None)
    # -2 apunta a una relación que no es la última: si devuelve True, tuvo que cambiar ESA
    sk3 = _rect(doc, 10, 10, igual=True, nombre="Negativo3")
    _add(sk3, "DistanceY", 1, 1, 1, 2, 10.0)
    ci = sk3.addGeometry(Part.Circle(V(30, 0, 0), V(0, 0, 1), 2))
    _add(sk3, "Radius", ci, 2.0)
    m = len(sk3.Constraints)
    antes = _foto_rel(sk3)
    try:
        r = _llamar(sk3, -2)
    except (IndexError, ValueError):
        r = False
    despues = _foto_rel(sk3)
    for i, (a_, b_) in enumerate(zip(antes, despues)):
        if a_ != b_ and not (r and i == m - 2):
            _falla("index_-2", "con index=-2 cambió la relación %d: %r -> %r" % (i, a_, b_))

    # 11) Geometría constructiva: diagonal de construcción acotada en un rectángulo definido
    sk = _rect(doc, 6, 8, nombre="Constructiva")
    d = sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(6, 8, 0)), True)
    _add(sk, "Coincident", d, 1, 0, 1)
    _add(sk, "Coincident", d, 2, 2, 1)
    _add(sk, "Distance", d, 10.0)
    _comprobar("diagonal_constructiva_sobra", sk, True)

    # 12) Geometría externa: recta pegada a las puntas de una arista de una caja; su largo sobra
    box = doc.addObject("Part::Box", "Caja")
    doc.recompute()
    sk = doc.addObject("Sketcher::SketchObject", "Externa")
    sk.addExternal("Caja", "Edge9")  # en ExternalGeo queda (0,0,0)-(10,0,0)
    doc.recompute()
    ln = sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)))
    _add(sk, "Coincident", ln, 1, -3, 1)
    _add(sk, "Coincident", ln, 2, -3, 2)
    sk.solve()
    _comprobar("recta_a_externa_no_sobra_aun", sk, False)
    _add(sk, "DistanceX", ln, 1, ln, 2, 10.0)
    _comprobar("largo_sobre_externa_sobra", sk, True)
    del box

    # 13) Fórmulas: la que sobra tiene fórmula; otra cota con fórmula no se toca
    sk = _rect(doc, 10, 10, igual=True, nombre="Formula")
    i_ancho = len(sk.Constraints) - 1
    sk.renameConstraint(i_ancho, "Ancho")
    ci = sk.addGeometry(Part.Circle(V(30, 0, 0), V(0, 0, 1), 2))
    ir = _add(sk, "Radius", ci, 2.0)
    sk.setExpression(".Constraints[%d]" % ir, "Constraints.Ancho / 5")
    doc.recompute()
    i_h = _add(sk, "DistanceY", 1, 1, 1, 2, 10.0)
    sk.renameConstraint(i_h, "Alto")
    sk.setExpression(".Constraints.Alto", "Constraints.Ancho")
    doc.recompute()
    _comprobar_formula = _comprobar("cota_con_formula_sobra", sk, True)
    if _comprobar_formula:
        doc.recompute()
        if "Invalid" in sk.State or "Error" in sk.State:
            _falla("cota_con_formula_sobra", "recompute con error después: %r" % (sk.State,))
        if abs(sk.Geometry[ci].Radius - 2.0) > 1e-6:
            _falla("cota_con_formula_sobra", "el radio con fórmula cambió: %r" % sk.Geometry[ci].Radius)
    FreeCAD.closeDocument(doc.Name)


def caso_deshacer():
    doc = _doc("CotaSobraDeshacer")
    sk = _rect(doc, 10, 10, igual=True)
    doc.recompute()
    pasos = doc.UndoCount  # antes de abrir: FreeCAD cuenta el paso con el primer cambio
    doc.openTransaction("Cota")
    n = _add(sk, "DistanceY", 1, 1, 1, 2, 10.0)
    r = _comprobar("con_transaccion_abierta", sk, True)
    if not doc.HasPendingTransaction:
        _falla("con_transaccion_abierta", "cerró la transacción abierta")
    doc.commitTransaction()
    doc.recompute()
    if doc.UndoCount != pasos + 1:
        _falla("con_transaccion_abierta", "pasos de deshacer %d (se esperaba %d)" % (doc.UndoCount, pasos + 1))
    if r:
        doc.undo()
        doc.recompute()
        if len(sk.Constraints) != n:
            _falla("deshacer", "Deshacer no sacó la cota agregada: %d relaciones" % len(sk.Constraints))
        doc.redo()
        doc.recompute()
        if len(sk.Constraints) != n + 1 or sk.Constraints[n].Driving:
            _falla("rehacer", "Rehacer no trajo la cota conducida")
    # sin transacción: no tiene que crear un paso
    sk2 = _rect(doc, 4, 4, igual=True, nombre="SinTransaccion")
    doc.recompute()
    _add(sk2, "DistanceY", 1, 1, 1, 2, 4.0)
    _comprobar("sin_transaccion", sk2, True)
    # dos veces seguidas: la primera conducida no vuelve a conducente
    i1 = len(sk2.Constraints) - 1
    _add(sk2, "Distance", 2, 4.0)
    _comprobar("segunda_que_sobra", sk2, True)
    if sk2.Constraints[i1].Driving:
        _falla("segunda_que_sobra", "la primera conducida volvió a conducente")
    # llamarla de nuevo sobre una ya conducida -> False
    _comprobar("repetir_sobre_conducida", sk2, False)
    FreeCAD.closeDocument(doc.Name)


def caso_azar(semilla=20261115, vueltas=40):
    rnd = random.Random(semilla)
    doc = _doc("CotaSobraAzar")
    for k in range(vueltas):
        tipo = rnd.choice(["rect", "rect_igual", "circulo", "angulo"])
        sobra = rnd.random() < 0.6
        conflicto = not sobra and rnd.random() < 0.5
        nombre = "Az%d" % k
        caso = "azar%d_%s_%s" % (k, tipo, "sobra" if sobra else ("conflicto" if conflicto else "libre"))
        if tipo in ("rect", "rect_igual"):
            w = round(rnd.uniform(0.5, 300), 3)
            h = w if tipo == "rect_igual" else round(rnd.uniform(0.5, 300), 3)
            x0, y0 = round(rnd.uniform(-100, 100), 3), round(rnd.uniform(-100, 100), 3)
            if sobra or conflicto:
                sk = _rect(doc, w, h, x0, y0, igual=(tipo == "rect_igual"), nombre=nombre)
                f = 1.0 if sobra else rnd.choice([0.5, 1.5, 2.0])
                op = rnd.choice(["alto", "diag", "ancho_arriba"])
                if op == "alto":
                    _add(sk, "DistanceY", 3, 2, 3, 1, h * f)
                elif op == "diag":
                    _add(sk, "Distance", 0, 1, 2, 1, math.hypot(w, h) * f)
                else:
                    _add(sk, "DistanceX", 2, 2, 2, 1, w * f)
            else:
                sk = _rect(doc, w, h, x0, y0, cotas=False, nombre=nombre)
                _add(sk, "DistanceX", 0, 1, 0, 2, w)
            _comprobar(caso, sk, sobra)
        elif tipo == "circulo":
            r = round(rnd.uniform(0.1, 200), 4)
            sk = doc.addObject("Sketcher::SketchObject", nombre)
            c = sk.addGeometry(Part.Circle(V(rnd.uniform(-50, 50), rnd.uniform(-50, 50), 0), V(0, 0, 1), r))
            primero = rnd.choice(["Radius", "Diameter"])
            _add(sk, primero, c, r if primero == "Radius" else 2 * r)
            if sobra or conflicto:
                f = 1.0 if sobra else rnd.choice([0.7, 1.3])
                segundo = rnd.choice(["Radius", "Diameter"])
                if segundo == primero:
                    segundo = "Diameter" if primero == "Radius" else "Radius"
                _add(sk, segundo, c, (r if segundo == "Radius" else 2 * r) * f)
            else:
                _add(sk, "DistanceX", -1, 1, c, 3, sk.Geometry[c].Center.x)
            _comprobar(caso, sk, sobra)
        else:
            ang = rnd.uniform(10, 80)
            sk = doc.addObject("Sketcher::SketchObject", nombre)
            a = sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)))
            b = sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(5 * math.cos(math.radians(ang)),
                                                               5 * math.sin(math.radians(ang)), 0)))
            _add(sk, "Coincident", a, 1, b, 1)
            _add(sk, "Horizontal", a)
            _add(sk, "Angle", a, b, math.radians(ang))
            if sobra or conflicto:
                f = 1.0 if sobra else 0.5
                _add(sk, "Angle", b, math.radians(ang) * f)
            else:
                _add(sk, "Distance", b, 5.0)
            _comprobar(caso, sk, sobra)
        if len(doc.Objects) > 20:
            FreeCAD.closeDocument(doc.Name)
            doc = _doc("CotaSobraAzar%d" % k)
    FreeCAD.closeDocument(doc.Name)


def prueba():
    del FALLAS[:]
    casos_fijos()
    caso_deshacer()
    caso_azar()
    assert not FALLAS, "%d fallas:\n" % len(FALLAS) + "\n".join(FALLAS)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
