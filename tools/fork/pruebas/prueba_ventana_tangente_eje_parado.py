# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#64): Tangente entre la cara de arriba (o de abajo) de una placa fija y un
perno parado en su agujero (eje a 90° de la cara, lo más común). La unión Perpendicular que
acompaña a la Tangente arranca en su punto muerto: FreeCAD decía "resuelto" sin mover nada y el
perno quedaba parado atravesando la placa. Como SW: el perno queda acostado (eje paralelo a la cara)
y a la distancia de su radio. Con la cara de costado (eje ya paralelo) sigue como antes."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
import os  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _pieza(carpeta, nombre, l, a, h, agujero=0.0, cilindro=None):
    doc = FreeCAD.newDocument(nombre)
    body = doc.addObject("PartDesign::Body", "Body")
    if cilindro:
        c = body.newObject("PartDesign::AdditiveCylinder", "Perno")
        c.Radius, c.Height = cilindro
    else:
        c = body.newObject("PartDesign::AdditiveBox", "Caja")
        c.Length, c.Width, c.Height = l, a, h
        if agujero:
            hueco = body.newObject("PartDesign::SubtractiveCylinder", "Agujero")
            hueco.Radius, hueco.Height = agujero, h
            hueco.Placement.Base = V(l / 2, a / 2, 0)
    doc.recompute()
    ruta = os.path.join(carpeta, nombre + ".FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    return ruta



def _ensamblaje(rutas):
    from swui import assembly_drop
    carpeta = os.path.dirname(rutas[0])
    doc = FreeCAD.newDocument("Conjunto")
    FreeCAD.setActiveDocument(doc.Name)
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    asm.Type = "Assembly"
    asm.newObject("Assembly::JointGroup", "Joints")
    doc.recompute()
    doc.saveAs(os.path.join(carpeta, "Conjunto.FCStd"))
    comps = assembly_drop.insert_files(asm, rutas)
    doc.recompute()
    FreeCAD.setActiveDocument(doc.Name)
    bombear(300)
    return doc, asm, comps



def _relacionar(doc, asm, key, refs, valor=None):
    """Como el panel: elegir con el camino del ensamblaje, armar la relación y resolver."""
    import FreeCADGui
    from swui.fork import mates_sw
    FreeCADGui.Selection.clearSelection()
    for comp, sub in refs:
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.%s" % (comp.Name, comp.LinkedObject.Name, sub))
    ents = mates_sw.entities_from_selection(asm)
    FreeCADGui.Selection.clearSelection()
    assert len(ents) == 2, "se eligieron %d referencias" % len(ents)
    assert key in mates_sw.applicable([e[2] for e in ents]), "%s no se ofrece para %s" % (key, [e[2] for e in ents])
    doc.openTransaction("Relación")
    mates_sw.create_joint(asm, key, [(e[0], e[1]) for e in ents], value=valor)
    r = mates_sw.solve(asm)
    doc.recompute()
    doc.commitTransaction()
    bombear(200)
    return r



def _cara_global(comp, sub):
    import Part
    return Part.getShape(comp).getElement(sub)



def _plano(cara):
    n = cara.normalAt(*cara.ParameterRange[0:3:2])
    return cara.CenterOfMass, n





def _caso(cara, cilindro_primero=False, libres=False, antialineada=False):
    from swui.fork import mates_sw
    carpeta = carpeta_temporal()
    rutas = [_pieza(carpeta, "Placa", 15, 15, 10, agujero=2.5), _pieza(carpeta, "Perno", 0, 0, 0, cilindro=(2, 10))]
    if libres:  # la fija es otra pieza: la placa y el perno, los dos libres
        rutas.insert(0, _pieza(carpeta, "Base", 5, 5, 5))
    doc, asm, comps = _ensamblaje(rutas)
    placa, perno = comps[-2:]
    if libres:
        comps[0].Placement.Base = V(100, 100, 0)
    que = "%s%s%s%s" % (cara, " (cilindro primero)" if cilindro_primero else "", " (libres)" if libres else "",
                        " (antialineada)" if antialineada else "")
    cil = ["Face%d" % (i + 1) for i, f in enumerate(perno.LinkedObject.Shape.Faces) if f.Surface.__class__.__name__ == "Cylinder"]
    refs = [(placa, cara), (perno, cil[0])]
    res = _relacionar(doc, asm, "tangent", refs[::-1] if cilindro_primero else refs)
    assert res in (0, None), "%s: no se resolvió (%s)" % (que, res)
    tang = [j for j in mates_sw.joints_of(asm) if getattr(j, mates_sw.PROP, "") == "tangent"][0]
    assert len(mates_sw.companions(tang)) == 1, "%s: falta la unión del eje" % que
    if antialineada:
        doc.openTransaction("Alineación")
        mates_sw.flip_one_part(asm, tang)
        res = mates_sw.solve(asm)
        doc.commitTransaction()
        doc.recompute()
    p1, n1 = _plano(_cara_global(placa, cara))
    s = _cara_global(perno, cil[0]).Surface
    assert abs(s.Axis.dot(n1)) < 1e-3, "%s: el perno quedó parado (eje a %.3f de la cara) (#64)" % (que, s.Axis.dot(n1))
    # de qué lado queda depende de dónde arrancó (el perno empieza con el eje SOBRE la cara de
    # costado: cualquiera de los dos lados vale; el botón Alineación lo cambia, como en SW)
    d = (s.Center - p1).dot(n1)
    if libres:
        # dos piezas que no están atadas a la fija: el solver de FreeCAD 1.1 no les cumple la
        # distancia (con cualquier relación, no es de la Tangente); lo que se prueba es que la
        # placa no gire junto con el perno (antes de la revisión del 13/11 giraban las dos)
        assert comps[0].Placement.Base == V(100, 100, 0), "%s: se movió la pieza fija" % que
        assert placa.Placement.Rotation.isSame(FreeCAD.Rotation(), 1e-9), "%s: la placa giró con el perno" % que
    else:
        assert abs(abs(d) - 2) < 1e-2, "%s: el eje quedó a %.4f de la cara (radio 2)" % (que, d)
    pos = perno.Placement
    doc.undo()  # Ctrl+Z: la relación se va y el perno vuelve a donde estaba
    doc.recompute()
    doc.redo()
    doc.recompute()
    assert perno.Placement.isSame(pos, 1e-6), "%s: Ctrl+Z y Ctrl+Y no lo dejaron donde estaba" % que
    for x in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(x.Name)


def prueba():
    for cara in ("Face1", "Face3", "Face5"):  # costado, arriba y abajo (la caja con agujero)
        _caso(cara)
        yield 300
    _caso("Face3", cilindro_primero=True)
    yield 300
    _caso("Face3", libres=True)
    yield 300
    _caso("Face3", antialineada=True)
    yield 300


from _base import ejecutar  # noqa: E402
ejecutar(globals())
