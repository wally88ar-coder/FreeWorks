# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (mono de piezas del 14/11, #89): un Redondeo aceptado y después Ángulo de salida
sobre una cara de costado que quedó junto al redondeo. OpenCASCADE no la puede inclinar y FreeCAD lo
decía en inglés en el informe ("Failed to add some face for drafting, skip") sin que el panel avisara
nada. Como SW: el panel avisa en castellano que esa cara quedó sin ángulo y no deja aceptar; el
informe queda limpio y el Cancelar deja todo como estaba (lo mira el mono en cada paso)."""
TIPO = "completa"

from azar_comun import bombear  # noqa: E402

# dos seguidillas del mono (otro redondeo antes): en la segunda la queja salía del recálculo que hace
# Ecuaciones con el panel abierto, no de la vista previa
SEGUIDILLAS = [[("ecuaciones", 0), ("ecuaciones", 0), ("ecuaciones", 0), ("aceptar", 0), ("ecuaciones", 292)],
               [("ecuaciones", 0), ("ecuaciones", 0), ("ecuaciones", 0), ("aceptar", 150), ("ecuaciones", 292)]]


def prueba():
    from mono_comun import paso
    from mono_entornos import Pieza
    for pasos in SEGUIDILLAS:
        m = Pieza()
        historia = []
        for accion, semilla in pasos:
            paso(m, accion, semilla, historia)
            bombear(300)
        yield 300
    # y el panel: el aviso en castellano y Aceptar no acepta
    import FreeCAD
    import FreeCADGui
    from casos_pieza import caras_planas, correr_cinta
    from swui.fork import panel_guard
    doc = FreeCAD.newDocument("Salida")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 40, 30, 20
    doc.recompute()
    vertical = [i + 1 for i, e in enumerate(caja.Shape.Edges)
                if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 19][0]
    red = body.newObject("PartDesign::Fillet", "Redondeo")
    red.Base = (caja, ["Edge%d" % vertical])
    red.Radius = 5
    doc.recompute()
    arista = red.Shape.Edges  # una cara de costado que toca la cara curva del redondeo
    curva = [f for f in red.Shape.Faces if type(f.Surface).__name__ == "Cylinder"][0]
    lados = [n for n in caras_planas(red, normal_z=0.0)
             if red.Shape.getElement(n).distToShape(curva)[0] < 1e-6]
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(red, lados[0])
    correr_cinta("PartDesign_Draft")
    for _ in range(40):
        bombear(250)
        if panel_guard.open_panel() is not None:
            break
    p = panel_guard.open_panel()
    assert p is not None, "no se abrió el panel del Ángulo de salida"
    p._activate(p.neutral)
    bombear(200)
    FreeCADGui.Selection.addSelection(red, caras_planas(red, normal_z=1.0)[0])
    bombear(600)
    p.angle.setValue(5.0)
    p.preview()
    bombear(400)
    texto = p.message.text() if p.message.isVisible() else ""
    if "sin ángulo" in texto:
        assert p.accept() is False, "aceptó una salida con una cara que quedó sin ángulo"
    else:
        # si OpenCASCADE sí pudo con esa cara, que la vista previa sea válida (y no hay nada que avisar)
        assert p.valid, "la vista previa quedó mal sin avisar por qué: %r" % texto
    p.reject()
    bombear(400)
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
