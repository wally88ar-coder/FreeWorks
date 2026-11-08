# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles, grupo 3: Asistente para taladro, Mover/Copiar sólidos,
Eliminar/Conservar sólidos y chapa (Brida base, Brida de arista, Dobladillo).
"""

import FreeCAD

from casos_pieza import _ConPieza, armar_pieza, eje
from reglas_paneles import Caso, esperar_panel, tocar

V = FreeCAD.Vector
ORIGEN = ("App::Origin", "App::Line", "App::Plane", "App::Point")  # lo que trae un Cuerpo nuevo


def correr_cinta(comando):
    from swui import ribbon
    ribbon._run(comando)


def _croquis(body, plano, z, figuras):
    import Part
    sk = body.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(eje(body, plano), "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = FreeCAD.Placement(V(0, 0, z), FreeCAD.Rotation())
    for f in figuras:
        if f[0] == "circulo":
            sk.addGeometry(Part.Circle(V(f[1], f[2], 0), V(0, 0, 1), f[3]))
        elif f[0] == "rect":
            x0, y0, x1, y1 = f[1:]
            pts = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
            for i in range(4):
                sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    return sk


class Taladro(_ConPieza):
    nombre = "Taladro"
    tipo = "PartDesign::Hole"

    def preparar(self, doc):
        super().preparar(doc)
        self.croquis = _croquis(self.body, "XY_Plane", 20, [("circulo", -10, -5, 1)])
        doc.recompute()

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.croquis)
        correr_cinta("PartDesign_Hole")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        n = p.size.count()
        if n:
            p.size.setCurrentIndex(rng.randrange(min(n, 6)))  # medidas chicas: que entren
        yield 300
        p.preview()
        yield 500


class MoverCopiarSolidos(_ConPieza):
    nombre = "Mover/Copiar sólidos"
    tipo = "PartDesign::Body"
    ayudantes = ORIGEN + ("PartDesign::SubShapeBinder", "Part::DatumPoint", "PartDesign::FeatureBase")

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.punta, "Face1")
        correr_cinta("SWUI_MoveBodies")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.copy.setChecked(True)
        for spin in p.deltas:
            spin.setValue(round(rng.uniform(-60.0, 60.0), 1))
        p.preview()
        yield 800

    def editar(self, obj):
        from swui.fork import move_bodies
        # el Cuerpo copiado arranca de un FeatureBase que apunta a la copia vinculada (binder)
        base = [o for o in obj.Group if o.TypeId == "PartDesign::FeatureBase"][0]
        move_bodies.open_panel(base.BaseFeature)
        yield from esperar_panel()

    def invalido(self):
        # sin sólidos en la lista
        def gen():
            p = self.panel()
            p.clear()
            yield 400
        return gen()


class EliminarConservar(_ConPieza):
    nombre = "Eliminar/Conservar sólidos"
    tipo = "App::DocumentObjectGroup"
    ayudantes = ORIGEN + ("Part::CompoundFilter", "Part::Vertex", "PartDesign::Body",
                          "PartDesign::SubShapeBinder")

    def preparar(self, doc):
        import FreeCADGui
        self.doc = doc
        self.body, self.hueco = armar_pieza(doc)
        otro = doc.addObject("PartDesign::Body", "Cuerpo2")
        c = otro.newObject("PartDesign::AdditiveBox", "Caja2")
        c.Length, c.Width, c.Height = 10, 10, 10
        c.Placement.Base = V(40, 0, 0)
        doc.recompute()
        self.otro_body = otro
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", self.body)

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        cual = rng.choice([self.body, self.otro_body])
        FreeCADGui.Selection.addSelection(cual.Tip, "Face1")
        correr_cinta("SWUI_DeleteBodies")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.radios[rng.choice(["delete", "keep"])].setChecked(True)
        yield 600

    def editar(self, obj):
        from swui.fork import delete_bodies
        delete_bodies.open_panel(obj)
        yield from esperar_panel()

    def invalido(self):
        def gen():
            p = self.panel()
            p.clear()
            yield 400
        return gen()


# --- Chapa ------------------------------------------------------------------------------------


class _Chapa(Caso):
    otro = "PartDesign_Fillet"

    def _cuerpo_con_croquis(self, doc):
        import FreeCADGui
        self.doc = doc
        self.body = doc.addObject("PartDesign::Body", "Chapa")
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", self.body)
        self.croquis = _croquis(self.body, "XY_Plane", 0, [("rect", 0, 0, 80, 50)])
        doc.recompute()


class BridaBase(_Chapa):
    nombre = "Brida base"
    tipo = "PartDesign::FeaturePython"

    def preparar(self, doc):
        self._cuerpo_con_croquis(doc)

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.croquis)
        correr_cinta("SWUI_SMBaseFlange")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.thick.setValue(round(rng.uniform(1.0, 3.0), 1))
        p.preview()
        yield 600


class _SobreBrida(_Chapa):
    """Arma una brida base (por su panel) y trabaja sobre sus aristas de arriba."""
    comando = ""

    def preparar(self, doc):
        import FreeCADGui
        self._cuerpo_con_croquis(doc)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.croquis)
        correr_cinta("SWUI_SMBaseFlange")
        yield from esperar_panel()
        tocar()
        yield 1500
        doc.recompute()

    def aristas(self):
        tip = self.body.Tip
        zmax = tip.Shape.BoundBox.ZMax
        out = []
        for i, e in enumerate(tip.Shape.Edges):
            if e.Curve.__class__.__name__ == "Line" and e.Length >= 40 \
                    and abs(e.Vertexes[0].Point.z - zmax) < 1e-6 and abs(e.Vertexes[-1].Point.z - zmax) < 1e-6:
                out.append("Edge%d" % (i + 1))
        return out

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.body.Tip, rng.choice(self.aristas()))
        correr_cinta(self.comando)
        yield from esperar_panel()


class BridaArista(_SobreBrida):
    nombre = "Brida de arista"
    tipo = "PartDesign::FeaturePython"
    comando = "SWUI_SMEdgeFlange"

    def elegir(self, rng):
        p = self.panel()
        p.length.setValue(round(rng.uniform(10.0, 25.0), 1))
        p.preview()
        yield 800


class Dobladillo(_SobreBrida):
    nombre = "Dobladillo"
    tipo = "PartDesign::FeaturePython"
    comando = "SWUI_SMHem"

    def elegir(self, rng):
        p = self.panel()
        p.length.setValue(round(rng.uniform(5.0, 12.0), 1))
        p.preview()
        yield 800


CASOS = [Taladro, MoverCopiarSolidos, EliminarConservar, BridaBase, BridaArista, Dobladillo]
