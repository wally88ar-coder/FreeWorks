# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Piezas de prueba para "Editar pieza = pieza" (plan del 16/11): un bloque, una chapa (Brida base, Brida de
arista y un corte), una soldadura (esqueleto, cuatro miembros y esquinas) y una pieza con ecuaciones y
material. Cada una se guarda en su archivo y se puede poner en un ensamblaje junto a otra.
"""

import os

import FreeCAD

V = FreeCAD.Vector


def bloque(carpeta, nombre="Bloque"):
    """Croquis + Extruir 60 x 40 x 20 (como menu_comun.pieza)."""
    from menu_comun import pieza
    doc, body, sk, pad = pieza()
    return _guardar(doc, carpeta, nombre)


def chapa(carpeta, nombre="Chapa"):
    """Brida base 100 x 40 x 2 mm (radio = espesor), una Brida de arista de 20 y un corte redondo."""
    import Part
    import SheetMetalBaseCmd
    import SheetMetalCmd
    from swui.fork import sheet_metal as sm
    doc = FreeCAD.newDocument(nombre)
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(100, 0, 0), V(100, 40, 0), V(0, 40, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    doc.recompute()
    base = doc.addObject("PartDesign::FeaturePython", "BridaBase")
    SheetMetalBaseCmd.SMBaseBend(base, sk)
    body.addObject(base)
    sm.ensure_k(base)
    base.Thickness = 2
    base.setExpression("Radius", "Thickness")
    doc.recompute()
    larga = max(range(len(base.Shape.Edges)), key=lambda i: (base.Shape.Edges[i].Length,
                                                              -base.Shape.Edges[i].BoundBox.ZMax))
    brida = doc.addObject("PartDesign::FeaturePython", "BridaArista")
    SheetMetalCmd.SMBendWall(brida, base, ["Edge%d" % (larga + 1)])
    body.addObject(brida)
    brida.setExpression("radius", "%s.Radius" % base.Name)
    brida.length = 20
    doc.recompute()
    arriba = max(range(len(brida.Shape.Faces)), key=lambda i: (round(brida.Shape.Faces[i].Area, 3)
                                                               if abs(brida.Shape.Faces[i].normalAt(0, 0).z) > 0.99
                                                               else -1))
    sc = body.newObject("Sketcher::SketchObject", "CroquisCorte")
    sc.AttachmentSupport = [(brida, ["Face%d" % (arriba + 1)])]
    sc.MapMode = "FlatFace"
    doc.recompute()
    centro = brida.Shape.Faces[arriba].CenterOfMass
    local = sc.Placement.inverse().multVec(centro)
    sc.addGeometry(Part.Circle(V(local.x, local.y, 0), V(0, 0, 1), 5))
    corte = body.newObject("PartDesign::Pocket", "Corte")
    corte.Profile = sc
    corte.Type = "ThroughAll"
    doc.recompute()
    assert body.Shape.isValid() and corte.isValid(), "la chapa de prueba no salió"
    return _guardar(doc, carpeta, nombre)


def soldadura(carpeta, nombre="Marco"):
    """Esqueleto 600 x 400, cuatro caños 40x40x2 y esquinas a inglete (comun.marco)."""
    from comun import marco
    doc = FreeCAD.newDocument(nombre)
    marco(doc)
    doc.recompute()
    return _guardar(doc, carpeta, nombre)


def ecuaciones(carpeta, nombre="ConEcuaciones"):
    """Bloque con una variable global Largo = 60 que manda el largo, y material Acero."""
    from menu_comun import pieza
    from swui.fork import equations as eq
    from swui.fork import material as mt
    doc, body, sk, pad = pieza()
    vs = doc.addObject("App::VarSet", eq.VARSET_NAME)
    vs.addProperty("App::PropertyLength", "Largo", "Variables")
    vs.Largo = 30
    pad.setExpression("Length", "%s.Largo" % eq.VARSET_NAME)
    doc.recompute()
    acero = [m for m in mt.all_materials() if "steel" in m["name"].lower() or "acero" in m["name"].lower()]
    if acero:
        mt.assign([body], acero[0])
    doc.recompute()
    return _guardar(doc, carpeta, nombre)


def _guardar(doc, carpeta, nombre):
    ruta = os.path.join(carpeta, nombre + ".FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    return ruta


def ensamblaje(rutas):
    """Ensamblaje con cada archivo como componente (casos_relacion._ensamblaje), corridos para no superponerse."""
    import casos_relacion as cr
    doc, asm, comps = cr._ensamblaje(rutas)
    x = 0.0
    for c in comps:
        c.Placement.Base = V(x, 0, 0)
        try:
            x += c.Shape.BoundBox.XLength + 50
        except Exception:  # noqa: BLE001
            x += 200
    doc.recompute()
    return doc, asm, comps
