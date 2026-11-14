# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#80): una relación Coincidente entre la cara de arriba de una placa y un bloque;
después un corte en la placa que le cambia la numeración de caras, y se recalcula el ensamblaje
(un solo recálculo que pasa por la pieza y por el ensamblaje, como al aceptar un corte de
ensamblaje). Como SW: la relación sigue con su cara sin errores en el informe ("Broken link in"
salía antes de que FreeWorks la reparara) y el bloque queda apoyado sobre la placa."""
TIPO = "completa"
import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _pieza(carpeta, nombre, l, a, h):
    doc = FreeCAD.newDocument(nombre)
    body = doc.addObject("PartDesign::Body", "Body")
    c = body.newObject("PartDesign::AdditiveBox", "Caja")
    c.Length, c.Width, c.Height = l, a, h
    doc.recompute()
    ruta = os.path.join(carpeta, nombre + ".FCStd")
    doc.saveAs(ruta)
    return ruta


def _arriba(comp):
    import Part
    forma = Part.getShape(comp)
    best = None
    for i, f in enumerate(forma.Faces):
        if f.Surface.__class__.__name__ != "Plane":
            continue
        n = f.normalAt(*f.ParameterRange[0:3:2])
        if n.z > 0.99 and (best is None or f.CenterOfMass.z > best[1]):
            best = ("Face%d" % (i + 1), f.CenterOfMass.z)
    return best[0]


def prueba():
    import FreeCADGui
    from reglas_paneles import informe_largo, mensajes_nuevos
    from swui import assembly_drop
    from swui.fork import mates_sw
    carpeta = carpeta_temporal()
    rutas = [_pieza(carpeta, "Placa", 40, 30, 10), _pieza(carpeta, "Bloque", 10, 10, 10)]
    doc = FreeCAD.newDocument("Conjunto")
    FreeCAD.setActiveDocument(doc.Name)
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    asm.Type = "Assembly"
    asm.newObject("Assembly::JointGroup", "Joints")
    doc.recompute()
    doc.saveAs(os.path.join(carpeta, "Conjunto.FCStd"))
    placa, bloque = assembly_drop.insert_files(asm, rutas)
    bloque.Placement = FreeCAD.Placement(V(5, 5, 30), FreeCAD.Rotation())
    doc.recompute()
    bombear(300)
    arriba = _arriba(placa)
    FreeCADGui.Selection.clearSelection()
    for comp, sub in ((placa, arriba), (bloque, "Face5")):
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.%s" % (comp.Name, comp.LinkedObject.Name, sub))
    ents = mates_sw.entities_from_selection(asm)
    FreeCADGui.Selection.clearSelection()
    doc.openTransaction("Relación")
    joint = mates_sw.create_joint(asm, "coincident", [(e[0], e[1]) for e in ents])
    assert mates_sw.solve(asm) == 0, "no se resolvió la relación"
    doc.recompute()
    doc.commitTransaction()
    yield 500
    # un corte que renumera las caras de la placa (en su archivo), y UN recálculo desde el ensamblaje
    pdoc = placa.LinkedObject.Document
    body = pdoc.getObject("Body")
    for i, (x, y) in enumerate(((0, 0), (30, 20), (0, 20))):
        hueco = body.newObject("PartDesign::SubtractiveBox", "Muesca%d" % i)
        hueco.Length, hueco.Width, hueco.Height = 10, 10, 10
        hueco.Placement.Base = V(x, y, 0)
    desde = informe_largo()
    doc.recompute()
    bombear(800)
    malos = [m for m in mensajes_nuevos(desde) if "Broken link" in m or "Reference" in m]
    assert not malos, "el informe muestra errores de la relación (#80): %s" % malos
    ref = joint.Reference1 if joint.Reference1[0] is placa or getattr(joint.Reference1[0], "Name", "") == placa.Name else joint.Reference2
    assert not any("?" in s for s in ref[1]), "la relación quedó con la cara perdida: %s" % (ref,)
    fondo = min(v.Point.z for v in __import__("Part").getShape(bloque).Vertexes)
    assert abs(fondo - 10) < 1e-4, "el bloque no quedó apoyado sobre la placa (fondo en z=%.4f)" % fondo
    for d in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(d.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
