# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#15 (lentitud en piezas con muchos sólidos y ensamblajes grandes):
- Alcance automático: con 60 sólidos (caños), saber qué sólidos atraviesa un corte pasante tarda
  menos de 0,1 s (antes 0,17: un booleano contra cada sólido; ahora solo contra los que tocan su
  caja) y da lo mismo: encuentra el sólido que cruza aunque esté lejos del suyo.
- Ensamblaje con 500 componentes: cada cambio de ubicación de un componente revisa las operaciones
  de ensamblaje en menos de 0,2 ms (antes 1,2 ms: recorría todos los objetos)."""

import os  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

V = FreeCAD.Vector


def _alcance():
    from swui.fork import multibody as mb
    doc = FreeCAD.newDocument("MuchosSolidos")
    cuerpos = []
    for i in range(60):
        b = doc.addObject("PartDesign::Body", "B%d" % i)
        c = b.newObject("PartDesign::AdditiveCylinder", "Tubo%d" % i)
        c.Radius, c.Height = 20, 1000
        c.Placement.Base = V(100 * (i % 10), 100 * (i // 10), 0)
        cuerpos.append(b)
    # uno lejos en x/y del primero pero cruzado por el corte pasante (que va en z)
    lejos = doc.addObject("PartDesign::Body", "Lejos")
    caja = lejos.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length = caja.Width = caja.Height = 20
    caja.Placement.Base = V(-10, -10, 3000)
    doc.recompute()
    a = cuerpos[0]
    sk = a.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(a.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 5))
    doc.recompute()
    pk = a.newObject("PartDesign::Pocket", "Agujero")
    pk.Profile = sk
    pk.Type = "ThroughAll"
    pk.Midplane = True
    doc.recompute()
    mb.touched_bodies(pk)  # la primera vez arma cachés de FreeCAD
    t = time.perf_counter()
    for _ in range(5):
        tocados = mb.touched_bodies(pk)
    dt = (time.perf_counter() - t) / 5
    nombres = sorted(b.Name for b in tocados)
    assert nombres == ["B0", "Lejos"], "atraviesa %s (esperado B0 y Lejos)" % nombres
    assert dt < 0.1, "tardó %.3f s con 60 sólidos (máximo 0,1)" % dt
    FreeCAD.closeDocument(doc.Name)


def _ensamblaje():
    from swui.fork import assembly_features as af
    carpeta = tempfile.mkdtemp()
    pieza = FreeCAD.newDocument("Pieza")
    caja = pieza.addObject("Part::Box", "Caja")
    pieza.recompute()
    pieza.saveAs(os.path.join(carpeta, "pieza.FCStd"))
    asm = FreeCAD.newDocument("Conjunto")
    asm.saveAs(os.path.join(carpeta, "conjunto.FCStd"))
    links = []
    for i in range(500):
        link = asm.addObject("App::Link", "L%d" % i)
        link.LinkedObject = caja
        links.append(link)
    otro = asm.addObject("App::VarSet", "NoEsOperacion")
    asm.recompute()
    assert af.operations(asm) == [], "un VarSet común no es una operación de ensamblaje"
    obs = af._Observer()
    t = time.perf_counter()
    for link in links[:100]:
        obs.slotChangedObject(link, "Placement")
    dt = (time.perf_counter() - t) / 100
    assert dt < 2e-4, "cada cambio de ubicación tardó %.2f ms con 500 componentes (máximo 0,2)" % (dt * 1000)
    otro.addProperty("App::PropertyString", af.KIND, "SW", "prueba")
    assert af.operations(asm) == [otro], "no encontró la operación de ensamblaje"
    FreeCAD.closeDocument(asm.Name)
    FreeCAD.closeDocument(pieza.Name)


def prueba():
    _alcance()
    _ensamblaje()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
