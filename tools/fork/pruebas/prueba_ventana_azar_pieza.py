# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Operaciones de pieza con medidas al azar, por el panel, como el usuario (plan de calidad,
paso 8.2, grupo 1). Lo que se elige en el panel es lo que sale, y la pieza cumple la fórmula:
- Extruir (una dirección, plano medio, invertida, dos direcciones): volumen = área × largo total;
  la pieza va de 0 a L, de −L/2 a L/2, de −L a 0, o de −L2 a L; Length del objeto = lo escrito.
- Extruir corte: saca área × profundidad; con "Por todo", área × alto de la pieza.
- Revolución: volumen = π·(r2² − r1²)·h·ángulo/360 (Pappus para un rectángulo).
- Redondeo de una arista recta: saca (1 − π/4)·r²·largo; Radius del objeto = lo puesto.
- Chaflán de una arista recta: saca d²/2·largo; Size del objeto = lo puesto.
- Taladro pasante: el Ø es el de la tabla ISO 273 para la medida y el ajuste elegidos, y saca
  π·(Ø/2)²·alto.
- Matriz lineal: n agujeros a paso p (centros en x0 + k·p); Matriz circular: n agujeros.
- Simetría por el plano YZ: un agujero más, en −x.
- Ángulo de salida: la cara queda inclinada exactamente el ángulo puesto.
Casos por regla: FW_CASOS_AZAR (6 por omisión)."""
TIPO = "completa"

from azar_comun import (PI, Fallas, aceptar, bombear, caja, campo, cerca, cinta, comprobado, croquis,  # noqa: E402
                        documento, elegir_opcion, escribir, esperar_panel, hypothesis_listo,
                        tildar, volumen)

given, cfg, st = hypothesis_listo()
medida = st.floats(min_value=2.0, max_value=80.0, allow_nan=False).map(lambda x: round(x, 2))


@cfg
@given(w=medida, h=medida, largo=medida, largo2=medida,
       modo=st.sampled_from(["una", "plano medio", "invertida", "dos"]))
def extruir(w, h, largo, largo2, modo):
    import FreeCADGui
    doc, body = documento()
    sk = croquis(body, rects=[(0, 0, w, h)])
    FreeCADGui.Selection.addSelection(sk)
    cinta("PartDesign_Pad")
    assert esperar_panel(), "no se abrió el panel de Extruir"
    lados = {"una": "Una dirección", "plano medio": "Plano medio", "invertida": "Una dirección",
             "dos": "Dos direcciones"}[modo]
    elegir_opcion("sidesMode", lados)
    tildar("checkBoxReversed", modo == "invertida")
    escribir(campo("lengthEdit"), largo)
    if modo == "dos":
        escribir(campo("lengthEdit2"), largo2)
    assert aceptar(), "Extruir no aceptó"
    doc.recompute()
    pad = [o for o in doc.Objects if o.TypeId == "PartDesign::Pad"][0]
    comprobado()
    assert cerca(pad.Length.Value, largo), "Length = %s, se escribió %s" % (pad.Length, largo)
    total = largo + (largo2 if modo == "dos" else 0)
    assert cerca(volumen(body), w * h * total), "volumen %.3f, esperado %.3f" % (volumen(body), w * h * total)
    bb = body.Shape.BoundBox
    zz = {"una": (0, largo), "plano medio": (-largo / 2, largo / 2), "invertida": (-largo, 0),
          "dos": (-largo2, largo)}[modo]
    assert cerca(bb.ZMin, zz[0], absoluto=1e-3) and cerca(bb.ZMax, zz[1], absoluto=1e-3), \
        "%s: alto de %.3f a %.3f, esperado de %.3f a %.3f" % (modo, bb.ZMin, bb.ZMax, zz[0], zz[1])


@cfg
@given(W=medida, D=medida, H=medida, fx=st.floats(0.1, 0.8), fy=st.floats(0.1, 0.8),
       fw=st.floats(0.05, 0.4), fh=st.floats(0.05, 0.4), fd=st.floats(0.1, 0.9),
       por_todo=st.booleans())
def corte(W, D, H, fx, fy, fw, fh, fd, por_todo):
    import FreeCADGui
    doc, body = documento()
    caja(body, W, D, H)
    x0, y0 = W * fx, D * fy
    w, h = min(W * fw, W - x0 - 0.5), min(D * fh, D - y0 - 0.5)
    if w < 0.5 or h < 0.5:
        return
    sk = croquis(body, z=H, rects=[(x0, y0, x0 + w, y0 + h)])
    antes = volumen(body)
    FreeCADGui.Selection.addSelection(sk)
    cinta("PartDesign_Pocket")
    assert esperar_panel(), "no se abrió el panel de Extruir corte"
    prof = round(H * fd, 2)
    if por_todo:
        elegir_opcion("changeMode", "Por todo")
    else:
        elegir_opcion("changeMode", "Hasta profundidad")
        escribir(campo("lengthEdit"), prof)
    assert aceptar(), "Extruir corte no aceptó"
    doc.recompute()
    comprobado()
    sacado = antes - volumen(body)
    esperado = w * h * (H if por_todo else prof)
    assert cerca(sacado, esperado), "sacó %.3f, esperado %.3f (por todo=%s)" % (sacado, esperado, por_todo)


@cfg
@given(r1=st.floats(1.0, 40.0), ancho=st.floats(1.0, 30.0), h=st.floats(1.0, 40.0),
       angulo=st.floats(5.0, 360.0))
def revolucion(r1, ancho, h, angulo):
    import FreeCADGui
    r1, ancho, h, angulo = round(r1, 2), round(ancho, 2), round(h, 2), round(angulo, 1)
    doc, body = documento()
    sk = croquis(body, rol="XZ_Plane", rects=[(r1, 0, r1 + ancho, h)])  # gira en el eje vertical
    FreeCADGui.Selection.addSelection(sk)
    cinta("PartDesign_Revolution")
    assert esperar_panel(), "no se abrió el panel de Revolución"
    escribir(campo("revolveAngle"), angulo)
    assert aceptar(), "Revolución no aceptó"
    doc.recompute()
    comprobado()
    r2 = r1 + ancho
    esperado = PI * (r2 ** 2 - r1 ** 2) * h * angulo / 360.0
    assert cerca(volumen(body), esperado, rel=1e-3), "volumen %.3f, esperado %.3f" % (volumen(body), esperado)


def _arista_recta(obj, rng_indice):
    rectas = [i for i, e in enumerate(obj.Shape.Edges) if e.Curve.__class__.__name__ == "Line"]
    i = rectas[rng_indice % len(rectas)]
    return "Edge%d" % (i + 1), obj.Shape.Edges[i].Length


@cfg
@given(L=medida, A=medida, H=medida, indice=st.integers(0, 11), f=st.floats(0.05, 0.45))
def redondeo(L, A, H, indice, f):
    import FreeCADGui
    doc, body = documento()
    base = caja(body, L, A, H)
    sub, largo = _arista_recta(base, indice)
    r = round(min(L, A, H) * f, 2)
    if r < 0.1:
        return
    antes = volumen(body)
    FreeCADGui.Selection.addSelection(base, sub)
    cinta("PartDesign_Fillet")
    assert esperar_panel(), "no se abrió el panel de Redondeo"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p.radius.setValue(r)
    p.preview()
    bombear(600)
    assert aceptar(), "Redondeo no aceptó: %s" % (p.message.text() if p.message.isVisible() else "")
    doc.recompute()
    comprobado()
    fil = [o for o in doc.Objects if o.TypeId == "PartDesign::Fillet"][0]
    assert cerca(fil.Radius.Value, r), "Radius = %s, se puso %s" % (fil.Radius, r)
    sacado = antes - volumen(body)
    esperado = (1 - PI / 4) * r * r * largo
    assert cerca(sacado, esperado, rel=1e-3), "sacó %.4f, esperado %.4f" % (sacado, esperado)


@cfg
@given(L=medida, A=medida, H=medida, indice=st.integers(0, 11), f=st.floats(0.05, 0.45))
def chaflan(L, A, H, indice, f):
    import FreeCADGui
    doc, body = documento()
    base = caja(body, L, A, H)
    sub, largo = _arista_recta(base, indice)
    d = round(min(L, A, H) * f, 2)
    if d < 0.1:
        return
    antes = volumen(body)
    FreeCADGui.Selection.addSelection(base, sub)
    cinta("PartDesign_Chamfer")
    assert esperar_panel(), "no se abrió el panel de Chaflán"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p.size.setValue(d)
    p.preview()
    bombear(600)
    assert aceptar(), "Chaflán no aceptó"
    doc.recompute()
    comprobado()
    ch = [o for o in doc.Objects if o.TypeId == "PartDesign::Chamfer"][0]
    assert cerca(ch.Size.Value, d), "Size = %s, se puso %s" % (ch.Size, d)
    sacado = antes - volumen(body)
    esperado = d * d / 2 * largo
    assert cerca(sacado, esperado, rel=1e-3), "sacó %.4f, esperado %.4f" % (sacado, esperado)


# ISO 273, agujeros pasantes para tornillos (ajustado / normal / holgado), mm
ISO273 = {"M3": (3.2, 3.4, 3.6), "M4": (4.3, 4.5, 4.8), "M5": (5.3, 5.5, 5.8), "M6": (6.4, 6.6, 7.0),
          "M8": (8.4, 9.0, 10.0), "M10": (10.5, 11.0, 12.0), "M12": (13.0, 13.5, 14.5),
          "M14": (15.0, 15.5, 16.5), "M16": (17.0, 17.5, 18.5), "M20": (21.0, 22.0, 24.0),
          "M24": (25.0, 26.0, 28.0)}
AJUSTES = ["Ajustado", "Normal", "Holgado"]


@cfg
@given(medida_m=st.sampled_from(sorted(ISO273)), ajuste=st.integers(0, 2), H=st.floats(3.0, 40.0),
       fx=st.floats(0.3, 0.7), fy=st.floats(0.3, 0.7))
def taladro(medida_m, ajuste, H, fx, fy):
    import FreeCADGui
    H = round(H, 2)
    doc, body = documento()
    caja(body, 80, 60, H)
    sk = croquis(body, z=H, circulos=[(round(80 * fx, 2), round(60 * fy, 2), 1.0)])
    antes = volumen(body)
    FreeCADGui.Selection.addSelection(sk)
    cinta("PartDesign_Hole")
    assert esperar_panel(), "no se abrió el Asistente para taladro"
    from swui.fork import hole_panel, panel_guard
    p = panel_guard.open_panel()
    p.kind.setCurrentIndex(p.kind.findData(hole_panel.PLAIN))
    bombear(500)
    textos = [p.size.itemText(i) for i in range(p.size.count())]
    assert medida_m in textos, "el panel no ofrece %s: %s" % (medida_m, textos)
    p.size.setCurrentIndex(textos.index(medida_m))
    p.fit.setCurrentIndex(ajuste)
    p.end.setCurrentIndex(p.end.findData("ThroughAll"))
    p.preview()
    bombear(800)
    assert aceptar(), "el taladro no aceptó"
    doc.recompute()
    hole = [o for o in doc.Objects if o.TypeId == "PartDesign::Hole"][0]
    comprobado()
    d = ISO273[medida_m][ajuste]
    assert cerca(hole.Diameter.Value, d, absoluto=0.01), \
        "%s %s: Ø %s, la tabla ISO 273 dice %s" % (medida_m, AJUSTES[ajuste], hole.Diameter, d)
    sacado = antes - volumen(body)
    esperado = PI * (d / 2) ** 2 * H
    assert cerca(sacado, esperado, rel=1e-3), "sacó %.3f, esperado %.3f (Ø %s pasante)" % (sacado, esperado, d)


def _pieza_con_agujero(doc, body, L, A, H, x, y, r):
    import FreeCAD as App
    caja(body, L, A, H, App.Vector(-L / 2, -A / 2, 0))
    c = body.newObject("PartDesign::SubtractiveCylinder", "Agujero")
    c.Radius, c.Height = r, H
    c.Placement.Base = App.Vector(x, y, 0)
    doc.recompute()
    return c


def _centros(body, r):
    """Centros (x, y) de los agujeros de radio r: círculos de la cara de arriba."""
    zmax = body.Shape.BoundBox.ZMax
    out = []
    for e in body.Shape.Edges:
        if e.Curve.__class__.__name__ == "Circle" and abs(e.Curve.Radius - r) < 1e-6 \
                and abs(e.Curve.Center.z - zmax) < 1e-6:
            out.append((round(e.Curve.Center.x, 3), round(e.Curve.Center.y, 3)))
    return sorted(set(out))


@cfg
@given(n=st.integers(2, 5), paso=st.floats(4.0, 15.0), r=st.floats(0.5, 1.8), H=st.floats(3.0, 30.0))
def matriz_lineal(n, paso, r, H):
    import FreeCADGui
    paso, r, H = round(paso, 2), round(r, 2), round(H, 2)
    L = n * paso + 20
    doc, body = documento()
    x0 = -L / 2 + 10
    hueco = _pieza_con_agujero(doc, body, L, 30, H, x0, 0, r)
    antes = volumen(body)
    FreeCADGui.Selection.addSelection(hueco)
    cinta("PartDesign_LinearPattern")
    assert esperar_panel(), "no se abrió la Matriz lineal"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p._activate(p.ref_boxes["Direction"])
    bombear(200)
    FreeCADGui.Selection.addSelection([f for f in body.Origin.OriginFeatures if f.Role == "X_Axis"][0])
    bombear(600)
    p.count1.setValue(n)
    p.dist1.setValue(paso)
    p.preview()
    bombear(800)
    assert aceptar(), "la Matriz lineal no aceptó"
    doc.recompute()
    comprobado()
    sacado = antes - volumen(body)
    uno = PI * r * r * H
    assert cerca(sacado, (n - 1) * uno, rel=1e-3), "sacó %.3f de más, esperado %d agujeros más (%.3f)" % (sacado, n - 1, (n - 1) * uno)
    xs = sorted(c[0] for c in _centros(body, r))
    esperados = [round(x0 + k * paso, 3) for k in range(n)]
    assert len(xs) == n and all(abs(a - b) < 1e-2 for a, b in zip(xs, esperados)), \
        "centros %s, esperados %s (cantidad %d, paso %s)" % (xs, esperados, n, paso)


@cfg
@given(n=st.integers(2, 8), R=st.floats(6.0, 20.0), r=st.floats(0.5, 1.5), H=st.floats(3.0, 30.0))
def matriz_circular(n, R, r, H):
    import FreeCADGui
    R, r, H = round(R, 2), round(r, 2), round(H, 2)
    doc, body = documento()
    hueco = _pieza_con_agujero(doc, body, 2 * R + 10, 2 * R + 10, H, R, 0, r)
    antes = volumen(body)
    FreeCADGui.Selection.addSelection(hueco)
    cinta("PartDesign_PolarPattern")
    assert esperar_panel(), "no se abrió la Matriz circular"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p._activate(p.ref_boxes["Axis"])
    bombear(200)
    FreeCADGui.Selection.addSelection([f for f in body.Origin.OriginFeatures if f.Role == "Z_Axis"][0])
    bombear(600)
    p.count.setValue(n)
    p.preview()
    bombear(800)
    assert aceptar(), "la Matriz circular no aceptó"
    doc.recompute()
    comprobado()
    sacado = antes - volumen(body)
    uno = PI * r * r * H
    assert cerca(sacado, (n - 1) * uno, rel=1e-3), "sacó %.3f de más, esperado %d agujeros más" % (sacado, n - 1)
    assert len(_centros(body, r)) == n, "hay %d agujeros, esperado %d" % (len(_centros(body, r)), n)


@cfg
@given(x=st.floats(3.0, 15.0), r=st.floats(0.5, 2.0), H=st.floats(3.0, 30.0))
def simetria(x, r, H):
    import FreeCADGui
    x, r, H = round(x, 2), round(r, 2), round(H, 2)
    doc, body = documento()
    hueco = _pieza_con_agujero(doc, body, 2 * x + 10, 20, H, x, 0, r)
    antes = volumen(body)
    FreeCADGui.Selection.addSelection(hueco)
    cinta("PartDesign_Mirrored")
    assert esperar_panel(), "no se abrió la Simetría"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p._activate(p.ref_boxes["MirrorPlane"])
    bombear(200)
    FreeCADGui.Selection.addSelection([f for f in body.Origin.OriginFeatures if f.Role == "YZ_Plane"][0])
    bombear(800)
    assert aceptar(), "la Simetría no aceptó"
    doc.recompute()
    comprobado()
    sacado = antes - volumen(body)
    assert cerca(sacado, PI * r * r * H, rel=1e-3), "sacó %.3f de más, esperado un agujero más" % sacado
    assert _centros(body, r) == sorted([(-x, 0.0), (x, 0.0)]), "centros %s, esperados ±%s" % (_centros(body, r), x)


@cfg
@given(angulo=st.floats(1.0, 15.0), L=st.floats(10.0, 60.0), H=st.floats(5.0, 40.0))
def angulo_salida(angulo, L, H):
    import math
    import FreeCADGui
    angulo, L, H = round(angulo, 1), round(L, 2), round(H, 2)
    doc, body = documento()
    base = caja(body, L, 30, H)
    # la cara del costado x = L y la de abajo (plano neutro)
    lado = abajo = None
    for i, f in enumerate(base.Shape.Faces):
        c = f.CenterOfMass
        if abs(c.x - L) < 1e-6:
            lado = "Face%d" % (i + 1)
        if abs(c.z) < 1e-6:
            abajo = "Face%d" % (i + 1)
    FreeCADGui.Selection.addSelection(base, lado)
    cinta("PartDesign_Draft")
    assert esperar_panel(), "no se abrió el Ángulo de salida"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p._activate(p.neutral)
    bombear(200)
    FreeCADGui.Selection.addSelection(base, abajo)
    bombear(600)
    p.angle.setValue(angulo)
    p.preview()
    bombear(800)
    assert aceptar(), "el Ángulo de salida no aceptó"
    doc.recompute()
    dr = [o for o in doc.Objects if o.TypeId == "PartDesign::Draft"][0]
    comprobado()
    assert cerca(dr.Angle.Value, angulo), "Angle = %s, se puso %s" % (dr.Angle, angulo)
    inclinadas = []
    for f in body.Shape.Faces:
        if f.Surface.__class__.__name__ == "Plane":
            n = f.normalAt(*f.ParameterRange[0:3:2])
            if n.x > 0.5:
                inclinadas.append(math.degrees(math.asin(min(1.0, abs(n.z)))))
    assert inclinadas and abs(inclinadas[0] - angulo) < 0.01, \
        "la cara quedó inclinada %s°, se pidió %s°" % (inclinadas, angulo)


def prueba():
    fallas = Fallas()
    import os
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn in (("extruir", extruir), ("corte", corte), ("revolución", revolucion),
                       ("redondeo", redondeo), ("chaflán", chaflan), ("taladro", taladro),
                       ("matriz lineal", matriz_lineal), ("matriz circular", matriz_circular),
                       ("simetría", simetria), ("ángulo de salida", angulo_salida)):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
