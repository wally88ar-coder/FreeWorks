# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#84): desde algunos giros de arranque de la pieza que se mueve, el solver de
FreeCAD 1.1 no resuelve un Ángulo ni una Tangente que sí tienen solución (da -1). Como SW: se
resuelve desde cualquier arranque y la pieza fija no se mueve; con un valor imposible (la pieza
fija que la otra no puede alcanzar) no cambia nada de lugar; Ctrl+Z deshace todo en un paso; y
cambiar el valor del Ángulo después (como en el panel) también resuelve.
Casos (los de la ficha): bloque 10x10x10 girado 84° alrededor de (0; 0,5; 0,5), Ángulo entre la
Face3 de la placa y la Face1 del bloque con 87°, 90° y 135°; perno Ø4x10 girado 121° alrededor de
(0,125; -0,0625; 0,5), Tangente con la Face2 de una placa 10x10x10 con agujero Ø5."""
TIPO = "completa"
import math  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402

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
    doc.openTransaction("Relación")
    joint = mates_sw.create_joint(asm, key, [(e[0], e[1]) for e in ents], value=valor)
    r = mates_sw.solve(asm)
    doc.recompute()
    doc.commitTransaction()
    bombear(200)
    return r, joint


def _cara_global(comp, sub):
    import Part
    return Part.getShape(comp).getElement(sub)


def _normal(cara):
    return cara.normalAt(*cara.ParameterRange[0:3:2])


def _angulo(placa, c1, bloque, c2):
    n1, n2 = _normal(_cara_global(placa, c1)), _normal(_cara_global(bloque, c2))
    return math.degrees(math.acos(max(-1.0, min(1.0, n1.dot(n2)))))


def _cerrar():
    for x in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(x.Name)


def _cumple(placa, bloque, valor):
    ang = _angulo(placa, "Face3", bloque, "Face1")
    return min(abs(ang - valor), abs(ang - (180 - valor))) < 0.05, ang


def prueba():
    from swui.fork import mates_sw
    giro = FreeCAD.Rotation(V(0, 0.5, 0.5), 84)
    for valor in (87.0, 90.0, 135.0):
        carpeta = carpeta_temporal()
        doc, asm, (placa, bloque) = _ensamblaje([_pieza(carpeta, "Placa", 10, 10, 10), _pieza(carpeta, "Bloque", 10, 10, 10)])
        bloque.Placement = FreeCAD.Placement(V(), giro)
        doc.recompute()
        fijo0, libre0 = placa.Placement, bloque.Placement
        pasos = doc.UndoCount
        r, joint = _relacionar(doc, asm, "angle", [(placa, "Face3"), (bloque, "Face1")], valor)
        assert r == 0, "Ángulo %s° desde el giro de 84°: no se resolvió (%s) (#84)" % (valor, r)
        assert placa.Placement.isSame(fijo0, 1e-6), "Ángulo %s°: la pieza fija se movió" % valor
        ok, ang = _cumple(placa, bloque, valor)
        assert ok, "Ángulo %s°: las caras forman %.3f°" % (valor, ang)
        assert doc.UndoCount == pasos + 1, "Ángulo %s°: no es un solo paso de deshacer" % valor
        # cambiar el valor después, como en el panel (pasa por la misma ayuda)
        nuevo = 30.0 if valor != 30.0 else 60.0
        doc.openTransaction("Valor")
        joint.Angle = nuevo
        r2 = mates_sw.solve_joint(asm, joint)
        doc.recompute()
        doc.commitTransaction()
        assert r2 == 0, "Ángulo %s° → %s°: no se resolvió (%s)" % (valor, nuevo, r2)
        ok, ang = _cumple(placa, bloque, nuevo)
        assert ok, "Ángulo %s° → %s°: las caras forman %.3f°" % (valor, nuevo, ang)
        assert placa.Placement.isSame(fijo0, 1e-6), "Ángulo %s° → %s°: la pieza fija se movió" % (valor, nuevo)
        doc.undo()
        doc.undo()  # Ctrl+Z dos veces: sin la relación y el bloque donde arrancó
        doc.recompute()
        assert not [o for o in mates_sw._assembly_modules()[1].getJointGroup(asm).Group if getattr(o, mates_sw.PROP, "") == "angle"], \
            "Ángulo %s°: Ctrl+Z no sacó la relación" % valor
        assert bloque.Placement.isSame(libre0, 1e-6), "Ángulo %s°: después de Ctrl+Z el bloque no volvió" % valor
        assert placa.Placement.isSame(fijo0, 1e-6), "Ángulo %s°: después de Ctrl+Z la fija se movió" % valor
        _cerrar()
        yield 300

    # Tangente: perno girado 121° (el caso de la ficha)
    carpeta = carpeta_temporal()
    doc, asm, (placa, perno) = _ensamblaje([_pieza(carpeta, "Placa", 10, 10, 10, agujero=2.5),
                                            _pieza(carpeta, "Perno", 0, 0, 0, cilindro=(2, 10))])
    perno.Placement = FreeCAD.Placement(V(), FreeCAD.Rotation(V(0.125, -0.0625, 0.5), 121))
    doc.recompute()
    fijo0 = placa.Placement
    cil = ["Face%d" % (i + 1) for i, f in enumerate(perno.LinkedObject.Shape.Faces) if f.Surface.__class__.__name__ == "Cylinder"]
    r, _joint = _relacionar(doc, asm, "tangent", [(placa, "Face2"), (perno, cil[0])])
    assert r == 0, "Tangente desde el giro de 121°: no se resolvió (%s) (#84)" % r
    assert placa.Placement.isSame(fijo0, 1e-6), "Tangente: la pieza fija se movió"
    cara = _cara_global(placa, "Face2")
    n1 = _normal(cara)
    s = _cara_global(perno, cil[0]).Surface
    assert abs(s.Axis.dot(n1)) < 1e-3, "Tangente: el eje del perno no quedó paralelo a la cara"
    d = abs((s.Center - cara.CenterOfMass).dot(n1))
    assert abs(d - 2) < 1e-2, "Tangente: el eje quedó a %.4f de la cara (radio 2)" % d
    _cerrar()
    yield 300

    # las dos piezas fijas (la del bloque también): la ayuda no mueve ninguna (FreeCAD además dice
    # que resolvió sin cumplir la relación: eso es otra ficha)
    carpeta = carpeta_temporal()
    doc, asm, (placa, bloque) = _ensamblaje([_pieza(carpeta, "Placa", 10, 10, 10), _pieza(carpeta, "Bloque", 10, 10, 10)])
    bloque.Placement = FreeCAD.Placement(V(30, 0, 0), giro)
    doc.recompute()
    from swui.fork import mates_sw as ms
    jo, ua = ms._assembly_modules()
    g = ua.getJointGroup(asm).newObject("App::FeaturePython", "GroundedJoint")
    jo.GroundedJoint(g, bloque)
    doc.recompute()
    antes = {c.Name: c.Placement for c in (placa, bloque)}
    r, _joint = _relacionar(doc, asm, "angle", [(placa, "Face3"), (bloque, "Face1")], 87.0)
    for c in (placa, bloque):
        assert c.Placement.isSame(antes[c.Name], 1e-6), "con las dos fijas, %s se movió" % c.Name
    _cerrar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
