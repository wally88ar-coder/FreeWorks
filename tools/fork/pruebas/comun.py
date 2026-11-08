# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""Piezas que arman varias pruebas (marcos, cuerpos simples)."""

import FreeCAD

V = FreeCAD.Vector


def cerca(a, b, tol=0.05):
    return abs(float(a) - float(b)) <= tol  # float: las Quantity de FreeCAD no restan con números


def croquis_rectangulo(doc, ancho, alto, nombre="Esqueleto"):
    """Croquis cerrado ancho x alto desde el origen, con cotas: devuelve (croquis, índice de la cota del ancho)."""
    import Part
    import Sketcher
    sk = doc.addObject("Sketcher::SketchObject", nombre)
    pts = [V(0, 0, 0), V(ancho, 0, 0), V(ancho, alto, 0), V(0, alto, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 0))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sk.addConstraint(Sketcher.Constraint("Vertical", 1))
    sk.addConstraint(Sketcher.Constraint("Vertical", 3))
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
    cota = sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, ancho))
    sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, alto))
    doc.recompute()
    return sk, cota


def marco(doc, ancho=600, alto=400, esquina="inglete", perfil="Caño cuadrado", medida="40x40x2"):
    """Marco de 4 caños sobre un esqueleto rectangular, con sus esquinas. Devuelve (croquis, cota, cuerpos)."""
    from swui.fork import weldments as w
    sk, cota = croquis_rectangulo(doc, ancho, alto)
    size = [s for s, _d in w.sizes(perfil) if s.startswith(medida)][0]
    cuerpos = w.create_members(doc, [(sk, "Edge%d" % (i + 1)) for i in range(4)], perfil, size)
    w.apply_corners(cuerpos, esquina)
    doc.recompute()
    return sk, cota, cuerpos


def caja(body, nombre, largo, ancho, alto, base=V(0, 0, 0)):
    b = body.newObject("PartDesign::AdditiveBox", nombre)
    b.Length, b.Width, b.Height = largo, ancho, alto
    b.Placement.Base = base
    return b
