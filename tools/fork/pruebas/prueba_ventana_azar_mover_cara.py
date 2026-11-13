# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Mover cara con medidas al azar (plan de calidad, paso 8.2, grupo 9), por el panel (su lógica
está adentro del panel: hace falta la ventana). Cubo de medida al azar, cara plana al azar:
- Equidistanciar d hacia afuera: el volumen crece exactamente área de la cara × d; hacia adentro
  (Invertir): decrece área × d; la cara queda corrida d sobre su normal;
- Girar a° alrededor de una arista de la cara: la cara queda inclinada exactamente a°;
- lo puesto en el panel queda en la operación (distancia, ángulo).
Casos por regla: FW_CASOS_AZAR (6 por omisión)."""
TIPO = "completa"

import math  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402

from azar_comun import (Fallas, aceptar, bombear, caja, cerca, cinta, comprobado, documento,  # noqa: E402
                        esperar_panel, hypothesis_listo)

given, cfg, st = hypothesis_listo()
V = FreeCAD.Vector


def _abrir(base, sub):
    """Elegir la cara y abrir Mover cara. Si la selección todavía no llegó cuando corre el comando,
    se abre el panel que espera una cara (Issue #69, de la prueba): se le da la cara ahí, como el
    usuario, y se espera el panel de siempre."""
    import FreeCADGui
    from swui.fork import panel_guard
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(base, sub)
    bombear(200)
    cinta("SWUI_MoveFace")
    if not esperar_panel():
        return False
    for _i in range(20):
        cual = type(panel_guard.open_panel()).__name__
        if cual == "MoveFacePanel":
            return True
        if cual != "_WaitFacePanel":
            return False  # otro panel o ninguno: que lo diga el assert, no un AttributeError
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(base, sub)
        bombear(300)
    return False


def _caras(obj):
    out = []
    for i, f in enumerate(obj.Shape.Faces):
        if f.Surface.__class__.__name__ == "Plane":
            out.append(("Face%d" % (i + 1), f))
    return out


@cfg
@given(L=st.floats(10, 120), A=st.floats(10, 120), H=st.floats(10, 120), cual=st.integers(0, 5),
       d=st.floats(0.5, 8), afuera=st.booleans())
def equidistanciar(L, A, H, cual, d, afuera):
    import FreeCADGui
    L, A, H, d = round(L, 1), round(A, 1), round(H, 1), round(d, 2)
    doc, body = documento()
    base = caja(body, L, A, H)
    sub, cara = _caras(base)[cual % 6]
    area = cara.Area
    n = cara.normalAt(*cara.ParameterRange[0:3:2])
    centro = cara.CenterOfMass
    if not afuera and d >= min(L, A, H) - 0.5:
        return
    antes = body.Shape.Volume
    assert _abrir(base, sub), "no se abrió Mover cara con la cara elegida"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p.radios["offset"].setChecked(True)
    bombear(300)
    p.distance.setValue(d)
    p.flip.setChecked(not afuera)
    p.preview()
    bombear(1000)
    assert aceptar(), "Mover cara no aceptó: %s" % (p.message.text() if p.message.isVisible() else "")
    doc.recompute()
    comprobado()
    cambio = body.Shape.Volume - antes
    quiero = area * d * (1 if afuera else -1)
    assert cerca(cambio, quiero, rel=1e-6, absoluto=1e-3), \
        "%s %s %s mm: el volumen cambió %.4f, área × d = %.4f" % (sub, "afuera" if afuera else "adentro", d, cambio, quiero)
    destino = centro + n * (d if afuera else -d)
    caras_ahora = [f for _s, f in _caras(body.Tip)]
    assert any(abs((f.CenterOfMass - destino).dot(n)) < 1e-4 and abs(abs(f.normalAt(*f.ParameterRange[0:3:2]).dot(n)) - 1) < 1e-6
               for f in caras_ahora), "la cara no quedó corrida %s mm sobre su normal" % d


@cfg
@given(L=st.floats(20, 120), A=st.floats(20, 120), H=st.floats(20, 120), lado=st.integers(0, 3),
       ang=st.floats(1, 20))
def girar(L, A, H, lado, ang):
    import FreeCADGui
    L, A, H, ang = round(L, 1), round(A, 1), round(H, 1), round(ang, 1)
    doc, body = documento()
    base = caja(body, L, A, H)
    laterales = [(s, f) for s, f in _caras(base) if abs(f.normalAt(*f.ParameterRange[0:3:2]).z) < 1e-6]
    sub, cara = laterales[lado % len(laterales)]
    n0 = cara.normalAt(*cara.ParameterRange[0:3:2])
    assert _abrir(base, sub), "no se abrió Mover cara con la cara elegida"
    from swui.fork import panel_guard
    p = panel_guard.open_panel()
    p.radios["rotate"].setChecked(True)
    bombear(300)
    p._activate(p.hinge_box)
    bombear(200)
    abajo = [e for e in cara.Edges if all(abs(v.Point.z) < 1e-6 for v in e.Vertexes)][0]
    for i, e in enumerate(base.Shape.Edges):
        if e.isSame(abajo):
            FreeCADGui.Selection.addSelection(base, "Edge%d" % (i + 1))
            break
    bombear(600)
    p.angle.setValue(ang)
    p.preview()
    bombear(1000)
    if not aceptar():
        aviso = p.message.text() if p.message.isVisible() else ""
        # girada hacia adentro, la arista de arriba se corre H·tan(ángulo): si eso pasa el ancho
        # de la pieza, la cara la atraviesa y el panel lo rechaza con su aviso (bien; 13/11)
        ancho = L if abs(n0.x) > 0.5 else A
        assert "atraviesa" in aviso and H * math.tan(math.radians(ang)) >= ancho - 1e-6,             "Mover cara (girar) no aceptó: %s" % aviso
        from reglas_paneles import tocar
        tocar(rechazar=True)
        bombear(500)
        comprobado()
        return
    doc.recompute()
    comprobado()
    inclinadas = []
    for _s, f in _caras(body.Tip):
        n = f.normalAt(*f.ParameterRange[0:3:2])
        horiz = V(n.x, n.y, 0)
        if horiz.Length > 0.5 and horiz.normalize().dot(V(n0.x, n0.y, 0)) > 0.9:
            inclinadas.append(math.degrees(math.asin(min(1.0, abs(n.z)))))
    assert inclinadas and min(abs(x - ang) for x in inclinadas) < 0.01, \
        "la cara quedó inclinada %s°, se pidió %s°" % ([round(x, 3) for x in inclinadas], ang)


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    for nombre, fn in (("equidistanciar", equidistanciar), ("girar", girar)):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, fn)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
