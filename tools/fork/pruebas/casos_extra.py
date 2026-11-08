# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles, segunda tanda (08/11): Eje y Punto de ensamblaje, Recortar
miembro, Barrido / Hélice / Recubrir (paneles nativos que FreeWorks traduce) y variantes que la
primera tanda no ejercitaba: Mover sin copiar, Mover cara trasladando y girando, Tapa de extremo
elegida con un clic (no por código).
"""

import FreeCAD

from casos_ensamblaje import _Ensamblaje, correr_cinta
from casos_grupo3 import ORIGEN, MoverCopiarSolidos, _croquis
from casos_pieza import _ConPieza, armar_pieza, caras_planas
from casos_pieza2 import _Nativa
from casos_soldadas import Tapa, _Soldada
from reglas_paneles import esperar_panel

V = FreeCAD.Vector


# --- Ensamblaje ----------------------------------------------------------------------------------


class EjeEnsamblaje(_Ensamblaje):
    nombre = "Eje de ensamblaje"
    tipo = "Part::DatumLine"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_AssemblyAxis")
        yield from esperar_panel()

    def elegir(self, rng):
        placa = self.comps[0]
        rectas = [i for i, e in enumerate(placa.LinkedObject.Shape.Edges) if e.Curve.__class__.__name__ == "Line"]
        self.elegir_en(placa, "Edge%d" % (rng.choice(rectas) + 1))
        yield 900

    def invalido(self):
        def gen():
            yield 200
        return gen()


class PuntoEnsamblaje(_Ensamblaje):
    nombre = "Punto de ensamblaje"
    tipo = "Part::DatumPoint"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_AssemblyPoint")
        yield from esperar_panel()

    def elegir(self, rng):
        self.elegir_en(self.comps[0], rng.choice(self.caras(self.comps[0])))  # centro de cara
        yield 900

    def invalido(self):
        def gen():
            yield 200
        return gen()


# --- Piezas soldadas -----------------------------------------------------------------------------


class Recortar(_Soldada):
    nombre = "Recortar miembro"
    tipo = ("PartDesign::Pocket", "PartDesign::SubtractiveBox", "PartDesign::Boolean",
            "PartDesign::SubShapeBinder", "PartDesign::Pad")
    ayudantes = ("Sketcher::SketchObject",)
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "guardar")

    def preparar(self, doc):
        import Part
        from swui.fork import weldments as w
        super().preparar(doc)
        doc.removeObject(self.esqueleto.Name)
        sk = doc.addObject("Sketcher::SketchObject", "Esqueleto")
        sk.addGeometry(Part.LineSegment(V(0, 0, 0), V(600, 0, 0)))     # el que se recorta
        sk.addGeometry(Part.LineSegment(V(400, -200, 0), V(400, 200, 0)))  # el límite
        doc.recompute()
        self.esqueleto = sk
        size = w.sizes("Caño cuadrado")[10][0]
        self.cuerpos = w.create_members(doc, [(sk, "Edge1"), (sk, "Edge2")], "Caño cuadrado", size)
        doc.recompute()

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_WeldTrim")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        p = self.panel()
        p._activate("targets")
        yield 200
        FreeCADGui.Selection.addSelection(self.cuerpos[0].Tip, "Face1")
        yield 500
        p._activate("boundary")
        yield 200
        FreeCADGui.Selection.addSelection(self.cuerpos[1].Tip, "Face1")
        yield 900

    def invalido(self):
        def gen():  # sin límite
            import FreeCADGui
            p = self.panel()
            p._activate("targets")
            yield 200
            FreeCADGui.Selection.addSelection(self.cuerpos[0].Tip, "Face1")
            yield 600
        return gen()


class TapaPorClic(Tapa):
    """La tapa elegida como el usuario: un clic en la cara de la punta (no `panel.pick`)."""
    nombre = "Tapa de extremo (clic)"

    def elegir(self, rng):
        import FreeCADGui
        cuerpo = self.cuerpos[0]
        tip = cuerpo.Tip
        # la cara plana de una punta: perpendicular al caño (normal en X; el caño va de 0 a 600)
        puntas = []
        for i, f in enumerate(tip.Shape.Faces):
            if f.Surface.__class__.__name__ == "Plane":
                n = f.normalAt(*f.ParameterRange[0:3:2])
                if abs(abs(n.x) - 1.0) < 1e-6:
                    puntas.append(("Face%d" % (i + 1), f.CenterOfMass))
        sub, centro = rng.choice(puntas)
        FreeCADGui.Selection.addSelection(tip.Document.Name, tip.Name, sub, centro.x, centro.y, centro.z)
        yield 900
        p = self.panel()
        p.thick.setValue(round(rng.uniform(2.0, 6.0), 1))
        p._changed()
        yield 900


# --- Variantes de pieza y sólidos ----------------------------------------------------------------


class MoverSinCopiar(MoverCopiarSolidos):
    nombre = "Mover sólido (sin copiar)"
    comprobar_copia = None
    ayudantes = ORIGEN + ("PartDesign::SubShapeBinder", "Part::DatumPoint", "PartDesign::FeatureBase")

    def elegir(self, rng):
        p = self.panel()
        p.copy.setChecked(False)
        for spin in p.deltas:
            spin.setValue(round(rng.uniform(-60.0, 60.0), 1))
        p.preview()
        yield 800

    def comprobar_aceptado(self, doc):
        # mover (sin copiar): el sólido original queda oculto; solo se ve el movido
        return ["sin copiar, el original sigue a la vista"] if self.body.Visibility else []


class MoverCaraTrasladar(_ConPieza):
    nombre = "Mover cara (trasladar)"
    tipo = ("PartDesign::Pad", "PartDesign::Pocket")

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.punta, caras_planas(self.punta, normal_z=1.0)[0])
        correr_cinta("SWUI_MoveFace")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.radios["translate"].setChecked(True)
        yield 300
        # sin dirección elegida: ΔX ΔY ΔZ (los tres, para que no sea lo mismo que Equidistanciar)
        p.deltas[0].setValue(round(rng.uniform(1.0, 5.0), 1))
        p.deltas[1].setValue(round(rng.uniform(-5.0, -1.0), 1))
        p.deltas[2].setValue(round(rng.choice([-1, 1]) * rng.uniform(1.0, 4.0), 1))
        p.preview()
        yield 700


class MoverCaraGirar(_ConPieza):
    nombre = "Mover cara (girar)"
    tipo = "PartDesign::Draft"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        self.base_obj = self.punta  # al abrir, la punta pasa a ser la operación nueva
        lados = caras_planas(self.base_obj, normal_z=0.0)
        self.cara = rng.choice(lados)
        FreeCADGui.Selection.addSelection(self.base_obj, self.cara)
        correr_cinta("SWUI_MoveFace")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        p = self.panel()
        p.radios["rotate"].setChecked(True)
        yield 300
        p._activate(p.hinge_box)
        yield 200
        cara = self.base_obj.Shape.getElement(self.cara)
        abajo = [e for e in cara.Edges if abs(e.Vertexes[0].Point.z) < 1e-6 and abs(e.Vertexes[-1].Point.z) < 1e-6]
        for i, e in enumerate(self.base_obj.Shape.Edges):
            if abajo and e.isSame(abajo[0]):
                FreeCADGui.Selection.addSelection(self.base_obj, "Edge%d" % (i + 1))
                break
        yield 600
        p.angle.setValue(round(rng.uniform(2.0, 10.0), 1))
        p.preview()
        yield 700


# --- Nativas con traducción ----------------------------------------------------------------------


class Helice(_Nativa):
    nombre = "Hélice"
    tipo = "PartDesign::AdditiveHelix"
    comando = "PartDesign_AdditiveHelix"
    plano = "XZ_Plane"
    alto = 0

    def dibujar(self, sk, Part):
        sk.addGeometry(Part.Circle(V(30, 5, 0), V(0, 0, 1), 2))  # lejos del eje vertical del croquis


class Barrido(_Nativa):
    nombre = "Barrido"
    tipo = "PartDesign::AdditivePipe"
    comando = "PartDesign_AdditivePipe"
    plano = "XY_Plane"
    alto = 20

    def preparar(self, doc):
        import Part
        super().preparar(doc)
        # perfil: círculo en la cara de arriba (z = 20) centrado en el origen; trayecto: recta
        # vertical desde ahí (croquis en YZ: x del croquis = Y, y del croquis = Z)
        self.trayecto = _croquis(self.body, "YZ_Plane", 0, [])
        self.trayecto.addGeometry(Part.LineSegment(V(0, 20, 0), V(0, 40, 0)))
        doc.recompute()

    def dibujar(self, sk, Part):
        sk.addGeometry(Part.Circle(V(0, 0, 0), V(0, 0, 1), 2))

    def elegir(self, rng):
        import FreeCADGui
        # FreeWorks deja prendido "Elegir trayecto": el clic en la recta la toma
        FreeCADGui.Selection.addSelection(self.trayecto, "Edge1")
        yield 1200


class Recubrir(_Nativa):
    nombre = "Recubrir"
    tipo = "PartDesign::AdditiveLoft"
    comando = "PartDesign_AdditiveLoft"

    def preparar(self, doc):
        import Part
        super().preparar(doc)
        self.seccion = _croquis(self.body, "XY_Plane", 35, [("circulo", -8, 0, 2)])
        doc.recompute()

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.croquis)
        FreeCADGui.Selection.addSelection(self.seccion)  # perfil y sección elegidos antes
        correr_cinta(self.comando)
        yield from esperar_panel()


CASOS = [EjeEnsamblaje, PuntoEnsamblaje, Recortar, TapaPorClic, MoverSinCopiar, MoverCaraTrasladar,
         MoverCaraGirar, Helice, Barrido, Recubrir]
