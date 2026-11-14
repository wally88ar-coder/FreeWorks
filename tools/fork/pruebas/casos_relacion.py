# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Lo común de las pruebas de relaciones de posición con ventana: piezas guardadas aparte, un
ensamblaje con ellas y relacionar como el panel. Solo funciones (importar un archivo prueba_*
arranca esa prueba: por eso esto va aparte).
"""

import math  # noqa: F401
import os

import FreeCAD

from azar_comun import bombear

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
