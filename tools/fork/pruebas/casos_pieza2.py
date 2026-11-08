# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles, grupo 2: geometría de referencia (Plano, Eje, Punto), Combinar,
Mover cara y las operaciones nativas que FreeWorks traduce (Extruir, Extruir corte,
Revolución). Misma pieza que casos_pieza.py.
"""

import FreeCAD

from casos_pieza import _ConPieza, armar_pieza, aristas_rectas, caras_planas, correr_cinta, eje
from reglas_paneles import esperar_panel

V = FreeCAD.Vector


def _nada():
    """Inválido de los paneles de referencia: Aceptar sin haber elegido nada."""
    def gen():
        yield 200
    return gen()


class Plano(_ConPieza):
    nombre = "Plano"
    tipo = "PartDesign::Plane"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("PartDesign_Plane")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        from swui.fork import ref_plane_panel as rp
        p = self.panel()
        FreeCADGui.Selection.addSelection(self.punta, rng.choice(caras_planas(self.punta)))
        yield 700
        g = p.groups[0]
        g.choose(rp.DISTANCE)
        g.value.setValue(round(rng.uniform(2.0, 15.0), 1))
        p.preview()
        yield 400

    invalido = staticmethod(_nada)


class Eje(_ConPieza):
    nombre = "Eje"
    tipo = "PartDesign::Line"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("PartDesign_Line")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.addSelection(self.punta, rng.choice(aristas_rectas(self.punta)))
        yield 700

    invalido = staticmethod(_nada)


class Punto(_ConPieza):
    nombre = "Punto"
    tipo = "PartDesign::Point"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("PartDesign_Point")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        circulos = ["Edge%d" % (i + 1) for i, e in enumerate(self.punta.Shape.Edges)
                    if e.Curve.__class__.__name__ == "Circle"]
        FreeCADGui.Selection.addSelection(self.punta, rng.choice(circulos))  # centro del arco
        yield 700

    invalido = staticmethod(_nada)


class Combinar(_ConPieza):
    nombre = "Combinar"
    tipo = "PartDesign::Boolean"
    reglas = ("cancelar", "otro_comando", "aceptar", "editar", "guardar")

    def preparar(self, doc):
        import FreeCADGui
        self.doc = doc
        self.body, self.hueco = armar_pieza(doc)
        otro = doc.addObject("PartDesign::Body", "Cuerpo2")
        c = otro.newObject("PartDesign::AdditiveBox", "Caja2")
        c.Length, c.Width, c.Height = 20, 20, 30
        c.Placement.Base = V(-30, -10, 5)
        doc.recompute()
        self.otro_body = otro
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", self.body)

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.body.Tip, "Face1")
        FreeCADGui.Selection.addSelection(self.otro_body.Tip, "Face1")
        correr_cinta("SWUI_Combine")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.radios[rng.choice(["Fuse", "Cut", "Common"])].setChecked(True)
        p.preview()
        yield 600


class MoverCara(_ConPieza):
    nombre = "Mover cara"
    tipo = ("PartDesign::Pad", "PartDesign::Pocket")

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.punta, caras_planas(self.punta, normal_z=1.0)[0])
        correr_cinta("SWUI_MoveFace")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.radios["offset"].setChecked(True)
        yield 300
        p.distance.setValue(round(rng.uniform(1.0, 5.0), 1))
        p.flip.setChecked(rng.random() < 0.5)  # hacia afuera (Extruir) o hacia adentro (Cortar)
        p.preview()
        yield 600

    def invalido(self):
        # Girar sin elegir la bisagra
        def gen():
            p = self.panel()
            p.radios["rotate"].setChecked(True)
            yield 300
            p.preview()
            yield 400
        return gen()


class _Nativa(_ConPieza):
    """Operaciones nativas con croquis: FreeWorks solo traduce el panel (y agrega Alcance)."""
    reglas = ("cancelar", "otro_comando", "aceptar", "editar", "guardar")
    comando = ""
    plano = "XY_Plane"
    alto = 20

    def preparar(self, doc):
        import Part
        super().preparar(doc)
        sk = self.body.newObject("Sketcher::SketchObject", "CroquisPrueba")
        sk.AttachmentSupport = [(eje(self.body, self.plano), "")]
        sk.MapMode = "FlatFace"
        sk.AttachmentOffset = FreeCAD.Placement(V(0, 0, self.alto), FreeCAD.Rotation())
        self.dibujar(sk, Part)
        doc.recompute()
        self.croquis = sk

    def dibujar(self, sk, Part):
        sk.addGeometry(Part.Circle(V(-8, 0, 0), V(0, 0, 1), 4))

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.croquis)
        correr_cinta(self.comando)
        yield from esperar_panel()

    def panel(self):
        return None  # panel nativo: se maneja con los botones

    def mensaje(self):
        return ""


class Extruir(_Nativa):
    nombre = "Extruir"
    tipo = "PartDesign::Pad"
    comando = "PartDesign_Pad"


class ExtruirCorte(_Nativa):
    nombre = "Extruir corte"
    tipo = "PartDesign::Pocket"
    comando = "PartDesign_Pocket"


class Revolucion(_Nativa):
    nombre = "Revolución"
    tipo = "PartDesign::Revolution"
    comando = "PartDesign_Revolution"
    plano = "XZ_Plane"
    alto = 0

    def dibujar(self, sk, Part):
        # rectángulo de 25..30 en X y 20..25 en Z: un anillo arriba del cubo al girarlo en Z
        pts = [V(25, 20, 0), V(30, 20, 0), V(30, 25, 0), V(25, 25, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))


CASOS = [Plano, Eje, Punto, Combinar, MoverCara, Extruir, ExtruirCorte, Revolucion]
