# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Un archivo con un "Hasta la superficie" que apunta a una cara de OTRO sólido se guarda,
se cierra y se abre con la escucha de referencias de FreeWorks prendida: al abrirlo no se agrega
ninguna copia ("Referencia de...") y el Hasta la superficie sigue apuntando a lo mismo (Issue #28,
el archivo quedaba "modificado")."""

import os  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from comun import V  # noqa: E402


def _cuerpo_con_extruir(doc, nombre, z):
    b = doc.addObject("PartDesign::Body", nombre)
    sk = b.newObject("Sketcher::SketchObject", nombre + "Croquis")
    sk.AttachmentSupport = [(b.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = FreeCAD.Placement(V(0, 0, z), FreeCAD.Rotation())
    pts = [V(0, 0, 0), V(10, 0, 0), V(10, 10, 0), V(0, 10, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    pad = b.newObject("PartDesign::Pad", nombre + "Extruir")
    pad.Profile = sk
    pad.Length = 5
    return pad


def prueba():
    from swui.fork import cross_body
    ruta = os.path.join(carpeta_temporal(), "alcance.FCStd")
    doc = FreeCAD.newDocument("Abrir")
    p1 = _cuerpo_con_extruir(doc, "B1", 20)
    p2 = _cuerpo_con_extruir(doc, "B2", 0)
    doc.recompute()
    p2.Type = "UpToFace"
    p2.UpToFace = (p1, ["Face6"])
    doc.recompute()
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    antes = cross_body._in_workbench
    cross_body._in_workbench = lambda: True  # como si estuviera el banco (sin ventana no lo está)
    obs = cross_body._ScopeObserver()
    FreeCAD.addDocumentObserver(obs)
    try:
        doc = FreeCAD.openDocument(ruta)
        tipos = [o.TypeId for o in doc.Objects]
        assert "PartDesign::SubShapeBinder" not in tipos, "al abrir agregó una copia: %s" % tipos
        obj, subs = doc.getObject("B2Extruir").UpToFace
        assert obj.Name == "B1Extruir" and list(subs) == ["Face6"], (obj.Name, subs)
    finally:
        FreeCAD.removeDocumentObserver(obs)
        cross_body._in_workbench = antes


from _base import ejecutar  # noqa: E402
ejecutar(globals())
