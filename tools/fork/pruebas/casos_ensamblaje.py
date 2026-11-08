# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles: ensamblaje (Relación de posición, Matriz lineal de componentes,
Plano de ensamblaje). Ensamblaje con dos piezas guardadas aparte: Placa (100 x 60 x 10, fija) y
Bloque (20 x 20 x 20). Las elecciones van con el camino dentro del ensamblaje, como un clic.
"""

import os

import FreeCAD

from _base import carpeta_temporal
from _base import traza
from reglas_paneles import Caso, _report_view, esperar_panel, informe_largo

V = FreeCAD.Vector


def _pieza(carpeta, nombre, l, a, h):
    doc = FreeCAD.newDocument(nombre)
    body = doc.addObject("PartDesign::Body", "Body")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = l, a, h
    doc.recompute()
    ruta = os.path.join(carpeta, nombre + ".FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)  # que el documento de la prueba vuelva a ser el activo
    return ruta


def correr_cinta(comando):
    from swui import ribbon
    ribbon._run(comando)


class _Ensamblaje(Caso):
    otro = "SWUI_Mate"
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "guardar")

    def preparar(self, doc):
        import FreeCADGui
        from swui import assembly_drop
        carpeta = carpeta_temporal()
        rutas = [_pieza(carpeta, "Placa", 100, 60, 10), _pieza(carpeta, "Bloque", 20, 20, 20)]
        FreeCAD.setActiveDocument(doc.Name)
        yield 500
        self.doc = doc
        # como el comando "Crear ensamblaje" de FreeCAD 1.1
        self.asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
        self.asm.Type = "Assembly"
        self.asm.newObject("Assembly::JointGroup", "Joints")
        doc.recompute()
        doc.saveAs(os.path.join(carpeta, "Conjunto.FCStd"))
        desde = informe_largo()
        self.comps = assembly_drop.insert_files(self.asm, rutas)
        traza("  componentes: %s %s" % ([c.Name for c in self.comps], _report_view().toPlainText()[desde:][-600:]))
        doc.recompute()
        yield 800
        FreeCAD.setActiveDocument(doc.Name)

    def elegir_en(self, comp, sub):
        """Clic en `sub` (FaceN, EdgeN) de un componente, como en la pantalla."""
        import FreeCADGui
        linked = comp.LinkedObject
        camino = "%s.%s.%s" % (comp.Name, linked.Name, sub)
        FreeCADGui.Selection.addSelection(self.doc.Name, self.asm.Name, camino)

    def caras(self, comp):
        return ["Face%d" % (i + 1) for i in range(len(comp.LinkedObject.Shape.Faces))]


class Relacion(_Ensamblaje):
    nombre = "Relación de posición"
    tipo = "App::FeaturePython"
    otro = "SWUI_ComponentLinearPattern"
    # sin "invalido": con una sola referencia, Aceptar cierra sin agregar nada (como SW, que
    # cierra el panel de relaciones sin crear la que quedó incompleta); la regla lo daría por falla
    reglas = ("cancelar", "otro_comando", "aceptar", "guardar")

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_Mate")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.set_key(rng.choice(["coincident", "parallel", "distance"]))
        yield 300
        placa, bloque = self.comps[0], self.comps[1]
        self.elegir_en(placa, rng.choice(self.caras(placa)))
        yield 500
        self.elegir_en(bloque, rng.choice(self.caras(bloque)))
        yield 1200

    def invalido(self):
        def gen():  # una sola referencia
            self.panel().set_key("coincident")
            yield 300
            self.elegir_en(self.comps[0], "Face1")
            yield 600
        return gen()


class MatrizComponentes(_Ensamblaje):
    nombre = "Matriz de componentes"
    tipo = "App::VarSet"
    ayudantes = ("App::Link", "App::LinkElement", "App::LinkGroup", "App::DocumentObjectGroup",
                 "Part::DatumLine")  # la dirección se guarda como eje propio

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_ComponentLinearPattern")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p._activate("seeds")
        yield 200
        self.elegir_en(self.comps[1], "Face1")
        yield 500
        p._activate("dir1")
        yield 200
        aristas = [i for i, e in enumerate(self.comps[0].LinkedObject.Shape.Edges) if e.Length > 50]
        self.elegir_en(self.comps[0], "Edge%d" % (rng.choice(aristas) + 1))
        yield 500
        p.count1.setValue(rng.randint(2, 4))
        p.spacing1.setValue(round(rng.uniform(25.0, 40.0), 1))
        yield 1200

    def invalido(self):
        def gen():  # sin dirección
            p = self.panel()
            p._activate("seeds")
            yield 200
            self.elegir_en(self.comps[1], "Face1")
            yield 600
        return gen()


class PlanoEnsamblaje(_Ensamblaje):
    nombre = "Plano de ensamblaje"
    tipo = "Part::DatumPlane"
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "guardar")

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_AssemblyPlane")
        yield from esperar_panel()

    def elegir(self, rng):
        from swui.fork import ref_plane_panel as rp
        p = self.panel()
        self.elegir_en(self.comps[0], rng.choice(self.caras(self.comps[0])))
        yield 800
        g = p.groups[0]
        g.choose(rp.DISTANCE)
        g.value.setValue(round(rng.uniform(5.0, 30.0), 1))
        p.preview()
        yield 500

    def invalido(self):
        def gen():  # nada elegido
            yield 200
        return gen()


CASOS = [Relacion, MatrizComponentes, PlanoEnsamblaje]
