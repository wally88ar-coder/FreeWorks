# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#11): una relación Tangente (placa y perno) lleva una unión acompañante oculta
(el eje). Borrarla como el usuario (Supr) se lleva las dos; Ctrl+Z trae LAS DOS de vuelta (antes
volvía la Tangente sin su eje y el perno se acostaba mal); Ctrl+Y las vuelve a sacar."""
TIPO = "completa"

import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402

V = FreeCAD.Vector


def _pieza(carpeta, nombre, cilindro=None):
    doc = FreeCAD.newDocument(nombre)
    body = doc.addObject("PartDesign::Body", "Body")
    if cilindro:
        c = body.newObject("PartDesign::AdditiveCylinder", "Perno")
        c.Radius, c.Height = cilindro
    else:
        c = body.newObject("PartDesign::AdditiveBox", "Caja")
        c.Length, c.Width, c.Height = 80, 60, 10
    doc.recompute()
    ruta = os.path.join(carpeta, nombre + ".FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    return ruta


def _contestar():
    """Contesta como el usuario las preguntas de FreeCAD al borrar (dependencias...)."""
    from PySide import QtWidgets
    w = QtWidgets.QApplication.activeModalWidget()
    if w is None:
        return
    si = [b for b in w.findChildren(QtWidgets.QAbstractButton)
          if b.text().replace("&", "") in ("Yes", "Sí", "Si", "OK", "Aceptar")]
    (si[0].click() if si else w.reject())


def prueba():
    import FreeCADGui
    from PySide import QtCore
    from reglas_paneles import ctrl_y, ctrl_z
    from swui import assembly_drop
    from swui.fork import mates_sw
    carpeta = carpeta_temporal()
    rutas = [_pieza(carpeta, "Placa"), _pieza(carpeta, "Perno", cilindro=(5, 40))]
    doc = FreeCAD.newDocument("Conjunto")
    FreeCAD.setActiveDocument(doc.Name)
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    asm.Type = "Assembly"
    asm.newObject("Assembly::JointGroup", "Joints")
    doc.recompute()
    doc.saveAs(os.path.join(carpeta, "Conjunto.FCStd"))
    placa, perno = assembly_drop.insert_files(asm, rutas)
    perno.Placement = FreeCAD.Placement(V(20, 15, 40), FreeCAD.Rotation(V(1, 1, 0), 30))
    doc.recompute()
    yield 500
    cara = [i for i, f in enumerate(placa.LinkedObject.Shape.Faces) if abs(f.CenterOfMass.z - 10) < 1e-6][0]
    cil = [i for i, f in enumerate(perno.LinkedObject.Shape.Faces) if f.Surface.__class__.__name__ == "Cylinder"][0]
    FreeCADGui.Selection.clearSelection()
    for comp, sub in ((placa, "Face%d" % (cara + 1)), (perno, "Face%d" % (cil + 1))):
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.%s" % (comp.Name, comp.LinkedObject.Name, sub))
    ents = mates_sw.entities_from_selection(asm)
    FreeCADGui.Selection.clearSelection()
    doc.openTransaction("Relación")
    mates_sw.create_joint(asm, "tangent", [(e[0], e[1]) for e in ents])
    mates_sw.solve(asm)
    doc.recompute()
    doc.commitTransaction()
    yield 500
    tang = [o for o in doc.Objects if getattr(o, mates_sw.PROP, "") == "tangent"]
    assert tang, "no se armó la Tangente"
    tang = tang[0]
    nombre = tang.Name
    assert mates_sw.companions(tang), "la Tangente no tiene su eje"

    vigia = QtCore.QTimer()
    vigia.timeout.connect(_contestar)
    vigia.start(500)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(tang)
    FreeCADGui.runCommand("Std_Delete")
    yield 1500
    assert doc.getObject(nombre) is None, "Supr no borró la Tangente"
    assert not [o for o in doc.Objects if getattr(o, mates_sw.TANGENT_OF, None) == nombre], "quedó el eje"

    ctrl_z(doc)
    doc.recompute()
    yield 1500
    tang = doc.getObject(nombre)
    assert tang is not None, "Ctrl+Z no trajo la Tangente"
    assert mates_sw.companions(tang), "Ctrl+Z trajo la Tangente sin su eje (#11)"

    ctrl_y(doc)
    doc.recompute()
    yield 1500
    assert doc.getObject(nombre) is None, "Ctrl+Y no volvió a sacar la Tangente"
    assert not [o for o in doc.Objects if getattr(o, mates_sw.TANGENT_OF, None) == nombre], \
        "Ctrl+Y dejó el eje sin su Tangente"
    vigia.stop()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
