# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Chapa con medidas al azar (plan de calidad, paso 8.2, grupo 3), por el panel de Brida base,
como el usuario. Perfil abierto al azar (1 a 3 pliegues de 30° a 150°, tramos de 15 a 120 mm),
largo, espesor (0,5 a 4 mm), radio (= espesor, la regla del taller, o al azar) y factor K al azar:
- lo puesto en el panel queda en la chapa (espesor, radio, K);
- el desarrollo tiene la superficie que da SW con el factor K (definición de SW: la fibra neutra
  está a K·espesor de la cara interior del pliegue). Fórmula sin depender de qué lado del perfil
  se dibujó: superficie = volumen/espesor − Σ pliegues (ángulo·ancho)·(0,5 − K)·espesor, con
  ángulo·ancho = superficie interior del pliegue / radio interior;
- en el DXF: el contorno queda cerrado y hay una línea de plegado por pliegue;
- el nombre del archivo lleva el espesor con coma (p. ej. "_1,5mm").
Referencia: SW (el usuario siempre sacó los desarrollos de SW). La comparación contra SW mismo
(la misma chapa en SW 2018) queda pendiente: el puente con SW todavía no mide desarrollos."""
TIPO = "completa"

import math  # noqa: E402

import FreeCAD  # noqa: E402

from azar_comun import (Fallas, aceptar, bombear, cerca, cinta, comprobado, documento,  # noqa: E402
                        esperar_panel, hypothesis_listo)

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector


@st.composite
def perfiles(draw):
    """Polilínea abierta en el plano XY: tramos y giros (siempre para el mismo lado: no se cruza)."""
    n = draw(st.integers(1, 3))
    lados = [round(draw(st.floats(15, 120)), 1) for _i in range(n + 1)]
    giros = [round(draw(st.floats(30, 150)), 1) for _i in range(n)]
    pts = [V(0, 0, 0)]
    rumbo = 0.0
    for i, largo in enumerate(lados):
        pts.append(pts[-1] + V(math.cos(math.radians(rumbo)), math.sin(math.radians(rumbo)), 0) * largo)
        if i < n:
            rumbo += 180 - giros[i]  # giro de la chapa: el ángulo entre tramos es giros[i]
    return [V(round(p.x, 3), round(p.y, 3), 0) for p in pts]


def _cilindros(forma):
    return [f for f in forma.Faces if f.Surface.__class__.__name__ == "Cylinder"]


@cfg
@given(pts=perfiles(), largo=st.floats(20, 150), espesor=st.floats(0.5, 4.0),
       radio_igual=st.booleans(), f_radio=st.floats(0.5, 3.0), k=st.floats(0.25, 0.5))
def brida_base(pts, largo, espesor, radio_igual, f_radio, k):
    import Part
    import FreeCADGui
    largo, espesor, k = round(largo, 1), round(espesor, 2), round(k, 3)
    radio = espesor if radio_igual else round(espesor * f_radio, 2)
    # solo chapas posibles: tramos más largos que lo que se comen los pliegues, y que no se toquen
    # entre sí (con dos pliegues agudos para el mismo lado el perfil se cruza: eso no es una chapa)
    if min((pts[i] - pts[i + 1]).Length for i in range(len(pts) - 1)) < 4 * (radio + espesor):
        return
    import Part
    tramos = [Part.LineSegment(a, b).toShape() for a, b in zip(pts, pts[1:])]
    for i in range(len(tramos)):
        for j in range(i + 2, len(tramos)):
            if tramos[i].distToShape(tramos[j])[0] < 3 * (radio + espesor):
                return
    doc, body = documento("Chapa")
    sk = body.newObject("Sketcher::SketchObject", "Perfil")
    sk.AttachmentSupport = [([f for f in body.Origin.OriginFeatures if f.Role == "XY_Plane"][0], "")]
    sk.MapMode = "FlatFace"
    for a, b in zip(pts, pts[1:]):
        sk.addGeometry(Part.LineSegment(a, b))
    doc.recompute()
    FreeCADGui.Selection.addSelection(sk)
    cinta("SWUI_SMBaseFlange")
    assert esperar_panel(), "no se abrió el panel de Brida base"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p.length.setValue(largo)
    p.thick.setValue(espesor)
    p.tied.setChecked(radio_igual)
    bombear(200)
    if not radio_igual:
        p.radius.setValue(radio)
    p.k.setValue(k)
    p.preview()
    bombear(1200)
    assert aceptar(), "la Brida base no aceptó: %s" % (p.message.text() if p.message.isVisible() else "")
    doc.recompute()
    from swui.fork import sheet_metal as sm
    comprobado()
    # lo puesto en el panel
    assert cerca(sm.thickness(body), espesor), "espesor %s, se puso %s" % (sm.thickness(body), espesor)
    assert cerca(sm.radius(body), radio, absoluto=1e-3), "radio %s, se puso %s" % (sm.radius(body), radio)
    assert cerca(sm.body_k(body), k, absoluto=1e-4), "K %s, se puso %s" % (sm.body_k(body), k)
    forma = body.Shape
    assert forma.isValid(), "la chapa quedó con error"
    # pliegues: caras cilíndricas interiores (radio R) con su par exterior (R + espesor)
    cil = _cilindros(forma)
    radios = [round(f.Surface.Radius, 4) for f in cil]
    interiores = [f for f in cil if any(abs(r - (f.Surface.Radius + espesor)) < 1e-3 for r in radios)]
    pliegues = len(pts) - 2
    assert len(interiores) == pliegues, "hay %d pliegues, se dibujaron %d" % (len(interiores), pliegues)
    for f in interiores:
        assert cerca(f.Surface.Radius, radio, absoluto=1e-3), "radio interior %s, se puso %s" % (f.Surface.Radius, radio)
    esperado = forma.Volume / espesor - sum(f.Area / f.Surface.Radius for f in interiores) * (0.5 - k) * espesor
    # el desarrollo
    flat = sm.ensure_flat(body, sketches=True)
    doc.recompute()
    fs = flat.Shape
    area = fs.Volume / espesor if fs.Solids else sum(f.Area for f in fs.Faces)
    from _base import traza
    traza("  K=%s (%s %s) R=%s T=%s pliegues=%d: desarrollo %.3f, esperado %.3f, sólidos=%d caras=%d" % (
        k, getattr(flat, "KFactor", "?"), getattr(flat, "KFactorStandard", "?"), radio, espesor, pliegues,
        area, esperado, len(fs.Solids), len(fs.Faces)))
    assert cerca(area, esperado, rel=1e-4, absoluto=0.05), \
        "desarrollo de %.3f mm², según SW con K=%s debería ser %.3f mm² (diferencia %.3f)" % (
            area, k, esperado, area - esperado)
    # el DXF
    ents = sm.flat_entities(flat)
    plegado = [e for e in ents if e[1] == sm.BEND_LAYER]
    assert len(plegado) == pliegues, "%d líneas de plegado en el DXF, hay %d pliegues" % (len(plegado), pliegues)
    puntas = {}
    for e in ents:
        if e[1] == sm.OUTLINE_LAYER and e[0] == "LINE":
            for q in ((round(e[2], 2), round(e[3], 2)), (round(e[4], 2), round(e[5], 2))):
                puntas[q] = puntas.get(q, 0) + 1
    sueltas = [q for q, n in puntas.items() if n % 2]
    assert not sueltas, "el contorno del DXF no cierra en %s" % sueltas[:4]
    nombre = sm.dxf_filename("Pieza", espesor, "SAE 1010")
    assert ("_%smm" % sm.fmt_mm(espesor)) in nombre and "," not in sm.fmt_mm(float(int(espesor))) \
        and nombre.endswith("_SAE 1010.dxf"), "nombre del DXF: %s" % nombre


def _desarrollo_vs_sw(body, espesor, k, pliegues, que):
    """Compara el desarrollo con la superficie que da SW con el factor K, y revisa el DXF."""
    from swui.fork import sheet_metal as sm
    forma = body.Shape
    assert forma.isValid(), "%s: la chapa quedó con error" % que
    cil = _cilindros(forma)
    radios = [round(f.Surface.Radius, 4) for f in cil]
    interiores = [f for f in cil if any(abs(r - (f.Surface.Radius + espesor)) < 1e-3 for r in radios)]
    assert len(interiores) == pliegues, "%s: hay %d pliegues, se esperaban %d" % (que, len(interiores), pliegues)
    esperado = forma.Volume / espesor - sum(f.Area / f.Surface.Radius for f in interiores) * (0.5 - k) * espesor
    flat = sm.ensure_flat(body, sketches=True)
    body.Document.recompute()
    fs = flat.Shape
    area = fs.Volume / espesor if fs.Solids else sum(f.Area for f in fs.Faces)
    assert cerca(area, esperado, rel=1e-4, absoluto=0.05),         "%s: desarrollo de %.3f mm², según SW con K=%s debería ser %.3f mm²" % (que, area, k, esperado)
    ents = sm.flat_entities(flat)
    plegado = [e for e in ents if e[1] == sm.BEND_LAYER]
    assert len(plegado) == pliegues, "%s: %d líneas de plegado en el DXF, hay %d pliegues" % (que, len(plegado), pliegues)


@cfg
@given(W=st.floats(40, 200), D=st.floats(30, 150), espesor=st.floats(0.5, 4.0), largo=st.floats(8, 60),
       angulo=st.floats(30, 150), spec=st.integers(0, 2), pos=st.integers(0, 2), cual=st.integers(0, 3))
def brida_arista(W, D, espesor, largo, angulo, spec, pos, cual):
    import FreeCADGui
    W, D, espesor, largo, angulo = round(W, 1), round(D, 1), round(espesor, 2), round(largo, 1), round(angulo, 1)
    if largo < 3 * espesor + 2:
        return
    doc, body = documento("Chapa")
    from azar_comun import croquis
    sk = croquis(body, rects=[(0, 0, W, D)])
    FreeCADGui.Selection.addSelection(sk)
    cinta("SWUI_SMBaseFlange")
    assert esperar_panel(), "no se abrió la Brida base"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p.thick.setValue(espesor)
    p.preview()
    bombear(800)
    assert aceptar(), "la Brida base no aceptó"
    doc.recompute()
    tip = body.Tip
    zmax = tip.Shape.BoundBox.ZMax
    arriba = [i for i, e in enumerate(tip.Shape.Edges) if e.Curve.__class__.__name__ == "Line"
              and all(abs(v.Point.z - zmax) < 1e-6 for v in e.Vertexes)]
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(tip, "Edge%d" % (arriba[cual % len(arriba)] + 1))
    cinta("SWUI_SMEdgeFlange")
    assert esperar_panel(), "no se abrió la Brida de arista"
    p = panel_guard.open_panel()
    p.spec_box.setCurrentIndex(spec)
    p.pos_box.setCurrentIndex(pos)
    p.angle.setValue(angulo)
    p.length.setValue(largo)
    p.preview()
    bombear(1200)
    assert aceptar(), "la Brida de arista no aceptó: %s" % (p.message.text() if p.message.isVisible() else "")
    doc.recompute()
    pared = [o for o in doc.Objects if o.TypeId == "PartDesign::FeaturePython" and hasattr(o, "angle")][-1]
    comprobado()
    assert cerca(pared.length.Value, largo), "largo %s, se puso %s" % (pared.length, largo)
    assert cerca(pared.angle.Value, angulo), "ángulo %s, se puso %s" % (pared.angle, angulo)
    from swui.fork import sheet_metal as sm
    _desarrollo_vs_sw(body, espesor, sm.body_k(body), 1, "brida de %s mm a %s°" % (largo, angulo))


def prueba():
    fallas = Fallas()
    fallas.correr("brida base y desarrollo", brida_base)
    fallas.correr("brida de arista y desarrollo", brida_arista)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
