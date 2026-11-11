# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles (reglas_paneles.py) para las operaciones de pieza con panel SW
del fork: Redondeo, Chaflán, Ángulo de salida, Matriz lineal, Matriz circular, Simetría.

Pieza: un Cuerpo con un cubo de 40 x 30 x 20 centrado en el origen (en X e Y) y un agujero
pasante de Ø6 en (10, 5) que las matrices y la simetría repiten.
"""

import FreeCAD

from reglas_paneles import Caso, esperar_panel

V = FreeCAD.Vector


def armar_pieza(doc):
    import FreeCADGui
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 40, 30, 20
    caja.Placement.Base = V(-20, -15, 0)
    hueco = body.newObject("PartDesign::SubtractiveCylinder", "Agujero")
    hueco.Radius, hueco.Height = 3, 20
    hueco.Placement.Base = V(10, 5, 0)
    doc.recompute()
    return body, hueco


def eje(body, rol):
    return [f for f in body.Origin.OriginFeatures if f.Role == rol][0]


def aristas_rectas(obj, largo_min=15):
    out = []
    for i, e in enumerate(obj.Shape.Edges):
        try:
            curva = e.Curve.__class__.__name__
        except TypeError:  # "undefined curve type": curvas que FreeCAD no expone (tras redondeos)
            continue
        if curva == "Line" and e.Length >= largo_min:
            out.append("Edge%d" % (i + 1))
    return out


def caras_planas(obj, normal_z=None):
    out = []
    for i, f in enumerate(obj.Shape.Faces):
        if f.Surface.__class__.__name__ != "Plane":
            continue
        n = f.normalAt(*f.ParameterRange[0:3:2])
        if normal_z is None or abs(n.z - normal_z) < 1e-6:
            out.append("Face%d" % (i + 1))
    return out


def correr_cinta(comando):
    from swui import ribbon
    ribbon._run(comando)


class _ConPieza(Caso):
    def preparar(self, doc):
        self.doc = doc
        self.body, self.hueco = armar_pieza(doc)

    @property
    def punta(self):
        return self.body.Tip


class Redondeo(_ConPieza):
    nombre = "Redondeo"
    tipo = "PartDesign::Fillet"
    otro = "PartDesign_Chamfer"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        lista = aristas_rectas(self.punta)
        for sub in rng.sample(lista, min(len(lista), rng.randint(1, 3))):
            FreeCADGui.Selection.addSelection(self.punta, sub)
        correr_cinta("PartDesign_Fillet")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.radius.setValue(round(rng.uniform(0.5, 4.0), 2))
        p.preview()
        yield 400

    def invalido(self):
        def gen():
            p = self.panel()
            p.radius.setValue(25.0)  # más que la altura del cubo: no hay redondeo posible
            p.preview()
            yield 400
        return gen()


class Chaflan(_ConPieza):
    nombre = "Chaflán"
    tipo = "PartDesign::Chamfer"
    otro = "PartDesign_Fillet"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        lista = aristas_rectas(self.punta)
        for sub in rng.sample(lista, min(len(lista), rng.randint(1, 3))):
            FreeCADGui.Selection.addSelection(self.punta, sub)
        correr_cinta("PartDesign_Chamfer")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.size.setValue(round(rng.uniform(0.5, 4.0), 2))
        p.preview()
        yield 400

    def invalido(self):
        def gen():
            p = self.panel()
            p.size.setValue(25.0)
            p.preview()
            yield 400
        return gen()


class AnguloSalida(_ConPieza):
    nombre = "Ángulo de salida"
    tipo = "PartDesign::Draft"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        lados = caras_planas(self.punta, normal_z=0.0)
        FreeCADGui.Selection.addSelection(self.punta, rng.choice(lados))
        correr_cinta("PartDesign_Draft")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        p = self.panel()
        p._activate(p.neutral)
        yield 200
        FreeCADGui.Selection.addSelection(self.punta, caras_planas(self.punta, normal_z=1.0)[0])
        yield 600
        p.angle.setValue(round(rng.uniform(1.0, 10.0), 1))
        p.preview()
        yield 400

    def invalido(self):
        # sin plano neutro (SW tampoco deja aceptar)
        def gen():
            yield 200
        return gen()


class MatrizLineal(_ConPieza):
    nombre = "Matriz lineal"
    tipo = "PartDesign::LinearPattern"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.hueco)
        correr_cinta("PartDesign_LinearPattern")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        p = self.panel()
        p._activate(p.ref_boxes["Direction"])
        yield 200
        FreeCADGui.Selection.addSelection(eje(self.body, "Y_Axis"))
        yield 600
        p.count1.setValue(rng.randint(2, 3))
        p.dist1.setValue(round(rng.uniform(7.0, 9.0), 1))
        p.preview()
        yield 400


class MatrizCircular(_ConPieza):
    nombre = "Matriz circular"
    tipo = "PartDesign::PolarPattern"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.hueco)
        correr_cinta("PartDesign_PolarPattern")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        p = self.panel()
        p._activate(p.ref_boxes["Axis"])
        yield 200
        FreeCADGui.Selection.addSelection(eje(self.body, "Z_Axis"))
        yield 600
        p.count.setValue(rng.randint(2, 4))
        p.preview()
        yield 400


class Simetria(_ConPieza):
    nombre = "Simetría"
    tipo = "PartDesign::Mirrored"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.hueco)
        correr_cinta("PartDesign_Mirrored")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        p = self.panel()
        p._activate(p.ref_boxes["MirrorPlane"])
        yield 200
        FreeCADGui.Selection.addSelection(eje(self.body, rng.choice(["YZ_Plane", "XZ_Plane"])))
        yield 600
        p.preview()
        yield 400


CASOS = [Redondeo, Chaflan, AnguloSalida, MatrizLineal, MatrizCircular, Simetria]


# --- Editar cambiando un valor (reglas editar_cancelar y editar_cambiar) ---
from reglas_paneles import cambia_numero  # noqa: E402

Redondeo.cambiar = cambia_numero("radius", 0.5, 4.0)
Chaflan.cambiar = cambia_numero("size", 0.5, 4.0)
AnguloSalida.cambiar = cambia_numero("angle", 1.0, 10.0)
MatrizLineal.cambiar = cambia_numero("dist1", 3.0, 4.5)  # que las copias queden dentro del cubo
MatrizCircular.cambiar = cambia_numero("count", 2, 5, entero=True)
