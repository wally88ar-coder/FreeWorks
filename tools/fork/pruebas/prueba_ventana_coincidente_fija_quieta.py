# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#62): dos piezas iguales encimadas, la segunda apenas girada (1°), Coincidente
entre dos caras de costado. El solver de FreeCAD 1.1 al crear la unión giraba también la pieza FIJA;
como SW, la fija no se mueve nunca: queda donde estaba y la otra se apoya cara contra cara."""
TIPO = "completa"
import FreeCAD  # noqa: E402
import os  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
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







def prueba():
    for giro in (1.0, -1.0, 5.0):
        carpeta = carpeta_temporal()
        rutas = [_pieza(carpeta, "Placa", 10, 10, 10), _pieza(carpeta, "Bloque", 10, 10, 10)]
        doc, asm, (placa, bloque) = _ensamblaje(rutas)
        bloque.Placement = FreeCAD.Placement(V(), FreeCAD.Rotation(V(0, 0, 1), giro))
        doc.recompute()
        fijo0 = placa.Placement
        res = _relacionar(doc, asm, "coincident", [(placa, "Face3"), (bloque, "Face2")])
        assert res in (0, None), "giro %s: no se resolvió (%s)" % (giro, res)
        assert placa.Placement.isSame(fijo0, 1e-6), "giro %s: la pieza fija se movió a %s (#62)" % (giro, placa.Placement)
        p1, n1 = _plano(_cara_global(placa, "Face3"))
        p2, n2 = _plano(_cara_global(bloque, "Face2"))
        assert abs(abs(n1.dot(n2)) - 1) < 1e-6, "giro %s: las caras no quedaron paralelas" % giro
        assert abs((p2 - p1).dot(n1)) < 1e-4, "giro %s: las caras no quedaron en el mismo plano" % giro
        doc.undo()  # Ctrl+Z: la relación se va, la fija sigue donde estaba
        doc.recompute()
        assert placa.Placement.isSame(fijo0, 1e-6), "giro %s: después de Ctrl+Z la fija se movió" % giro
        for x in list(FreeCAD.listDocuments().values()):
            FreeCAD.closeDocument(x.Name)
        yield 300


from _base import ejecutar  # noqa: E402
ejecutar(globals())
