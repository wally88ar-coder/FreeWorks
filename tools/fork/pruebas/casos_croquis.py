# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles: herramientas de entidades del croquis (Simetría, Mover, Copiar,
Girar, Escalar, Matriz lineal, Equidistanciar). No son paneles de Tareas: van arriba del panel del
croquis, con el croquis en edición; se aceptan con su ✓ (accept) y se cancelan con su ✗.

Croquis: un rectángulo de 30 x 20 desde el origen (4 líneas unidas) y una línea constructiva
vertical en x = 50 (eje para la simetría). Las reglas miden el croquis por su cantidad de
geometrías y relaciones.
"""

import FreeCAD

from casos_pieza import eje
from reglas_paneles import ESPERA_CORTA, Caso

V = FreeCAD.Vector


def correr_cinta(comando):
    from swui import ribbon
    ribbon._run(comando)


class _Croquis(Caso):
    tipo = None   # no crea objetos: cambia el croquis
    contar_deshacer = False
    edicion_ok = "Sketcher::SketchObject"  # se sigue en el croquis para probar Ctrl+Z adentro
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "guardar")
    comando = ""
    otro = "SWUI_SketchMove"

    def preparar(self, doc):
        import FreeCADGui
        import Part
        import Sketcher
        self.doc = doc
        body = doc.addObject("PartDesign::Body", "Cuerpo")
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        sk = body.newObject("Sketcher::SketchObject", "Croquis")
        sk.AttachmentSupport = [(eje(body, "XY_Plane"), "")]
        sk.MapMode = "FlatFace"
        pts = [V(0, 0, 0), V(30, 0, 0), V(30, 20, 0), V(0, 20, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
        for i in range(4):
            sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
        sk.addGeometry(Part.LineSegment(V(50, -10, 0), V(50, 30, 0)), True)  # 4: eje constructivo
        doc.recompute()
        self.croquis = sk

    def panel(self):
        from swui.fork import sketch_entities
        return sketch_entities.active_panel()

    def abrir(self, rng):
        import FreeCADGui
        gdoc = FreeCADGui.ActiveDocument
        if gdoc.getInEdit() is None:
            gdoc.setEdit(self.croquis)
            yield 1500
        FreeCADGui.Selection.clearSelection()
        correr_cinta(self.comando)
        hecho = 0
        while self.panel() is None and hecho < 8000:
            yield 250
            hecho += 250
        yield 400

    def entidades(self, rng):
        """Elige al azar 1 a 4 lados del rectángulo en la casilla de entidades."""
        import FreeCADGui
        p = self.panel()
        p.set_active("entities")
        for g in sorted(rng.sample(range(4), rng.randint(1, 4))):
            FreeCADGui.Selection.addSelection(self.croquis, "Edge%d" % (g + 1))
            yield 300

    def punto(self, nombre, v):
        p = self.panel()
        p.points[nombre] = v
        p._point_picked(nombre)
        p.update()

    def _salir(self):
        import FreeCADGui
        gdoc = FreeCADGui.ActiveDocument
        if gdoc.getInEdit() is not None:
            gdoc.resetEdit()
        self.doc.recompute()

    def aceptar(self):
        p = self.panel()
        self.ok = bool(p.accept()) if p is not None else False
        self.aviso = ""
        if not self.ok and p is not None:
            try:
                self.aviso = p.message.text() if p.message.isVisible() else ""
            except Exception:
                pass
        yield ESPERA_CORTA

    def despues_de_aceptar(self):
        self._salir()
        yield ESPERA_CORTA

    def cancelar(self):
        p = self.panel()
        if p is not None:
            p.reject()
        yield ESPERA_CORTA
        self._salir()
        yield ESPERA_CORTA

    def invalido(self):
        def gen():  # nada elegido
            yield 200
        return gen()


class Simetria(_Croquis):
    nombre = "Croquis: Simetría"
    comando = "SWUI_SketchMirror"

    def elegir(self, rng):
        import FreeCADGui
        yield from self.entidades(rng)
        p = self.panel()
        p.set_active("axis")
        FreeCADGui.Selection.addSelection(self.croquis, "Edge5")
        yield 400
        p.copy.setChecked(rng.random() < 0.7)
        p.update()
        yield 300


class Mover(_Croquis):
    nombre = "Croquis: Mover"
    comando = "SWUI_SketchMove"
    otro = "SWUI_SketchRotate"

    def elegir(self, rng):
        yield from self.entidades(rng)
        p = self.panel()
        p.xy.setChecked(True)
        p.dx.setValue(round(rng.uniform(-20, 20), 1))
        p.dy.setValue(round(rng.uniform(5, 20), 1))
        p.update()
        yield 300


class Copiar(Mover):
    nombre = "Croquis: Copiar"
    comando = "SWUI_SketchCopy"


class Girar(_Croquis):
    nombre = "Croquis: Girar"
    comando = "SWUI_SketchRotate"

    def elegir(self, rng):
        yield from self.entidades(rng)
        self.panel().set_active("center")
        self.punto("center", V(rng.uniform(0, 30), rng.uniform(0, 20), 0))
        self.panel().angle.setValue(round(rng.uniform(10, 170), 1))
        self.panel().update()
        yield 300


class Escalar(_Croquis):
    nombre = "Croquis: Escalar"
    comando = "SWUI_SketchScale"

    def elegir(self, rng):
        yield from self.entidades(rng)
        self.panel().set_active("center")
        self.punto("center", V(0, 0, 0))
        self.panel().factor.setValue(round(rng.uniform(0.5, 2.0), 2))
        self.panel().update()
        yield 300


class MatrizLineal(_Croquis):
    nombre = "Croquis: Matriz lineal"
    comando = "SWUI_SketchLinearPattern"

    def elegir(self, rng):
        yield from self.entidades(rng)
        p = self.panel()
        p.count1.setValue(rng.randint(2, 4))
        p.spacing1.setValue(round(rng.uniform(35, 50), 1))
        p.update()
        yield 300


class Equidistanciar(_Croquis):
    nombre = "Croquis: Equidistanciar"
    comando = "SWUI_SketchOffset"

    def elegir(self, rng):
        yield from self.entidades(rng)
        p = self.panel()
        p.distance.setValue(round(rng.uniform(1, 5), 1))
        p.hover = V(15, -5, 0)  # el lado: como pasar el mouse por afuera del rectángulo
        p.update()
        yield 300


CASOS = [Simetria, Mover, Copiar, Girar, Escalar, MatrizLineal, Equidistanciar]
