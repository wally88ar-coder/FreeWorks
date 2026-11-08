# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles: Convertir a chapa, Vista de sección, Agregar configuración,
Croquis (elegir plano) y Croquis 3D.

Vista de sección y Agregar configuración no se anotan en el guardia de paneles (#29, #30): la
prueba guarda la última instancia de su clase para manejarlas.
"""

import FreeCAD

from casos_pieza import _ConPieza, caras_planas
from reglas_paneles import ESPERA_CORTA, Caso, esperar_panel

V = FreeCAD.Vector
_ULTIMO = {}


def anotar(cls):
    """Guarda en _ULTIMO[cls.__name__] la última instancia que se crea (solo para la prueba)."""
    if getattr(cls.__init__, "_prueba", False):
        return
    original = cls.__init__

    def init(self, *a, **k):
        _ULTIMO[cls.__name__] = self
        original(self, *a, **k)
    init._prueba = True
    cls.__init__ = init


def correr_cinta(comando):
    from swui import ribbon
    ribbon._run(comando)


class ConvertirChapa(_ConPieza):
    nombre = "Convertir a chapa"
    tipo = None  # marca el Cuerpo como chapa (SWUI_Sheet)
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "guardar")

    def preparar(self, doc):
        import FreeCADGui
        self.doc = doc
        body = doc.addObject("PartDesign::Body", "Cuerpo")
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        c = body.newObject("PartDesign::AdditiveBox", "Placa")
        c.Length, c.Width, c.Height = 60, 40, 2
        doc.recompute()
        self.body = body

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_SMConvert")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.addSelection(self.punta, caras_planas(self.punta, normal_z=1.0)[0])
        yield 800
        p = self.panel()
        p.radius.setValue(round(rng.uniform(1.0, 4.0), 1))
        yield 300

    def invalido(self):
        def gen():  # sin la cara fija
            yield 200
        return gen()


class VistaSeccion(Caso):
    nombre = "Vista de sección"
    tipo = None
    reglas = ("cancelar", "otro_comando")  # Aceptar no cambia el documento (solo la vista)

    def preparar(self, doc):
        from swui.fork import section_view
        from casos_pieza import armar_pieza
        anotar(section_view.SectionPanel)
        self.doc = doc
        self.body, _h = armar_pieza(doc)

    def panel(self):
        import FreeCADGui
        p = _ULTIMO.get("SectionPanel")
        return p if p is not None and FreeCADGui.Control.activeDialog() else None

    def abrir(self, rng):
        from swui.fork import section_view
        section_view.toggle()
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.offset.setValue(round(rng.uniform(-10, 10), 1))
        yield 500


class AgregarConfiguracion(Caso):
    nombre = "Agregar configuración"
    tipo = None
    ayudantes = ("Spreadsheet::Sheet",)  # la tabla de configuraciones (la primera vez)
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "guardar")

    def preparar(self, doc):
        from swui.fork import config_tab
        from casos_pieza import armar_pieza
        anotar(config_tab._AddPanel)
        self.doc = doc
        self.body, _h = armar_pieza(doc)

    def panel(self):
        import FreeCADGui
        p = _ULTIMO.get("_AddPanel")
        return p if p is not None and FreeCADGui.Control.activeDialog() else None

    def abrir(self, rng):
        from swui.fork import config_tab
        config_tab.add_config()
        yield from esperar_panel()

    def elegir(self, rng):
        self.panel().name.setText("Prueba%d" % rng.randint(1, 999))
        yield 300

    def invalido(self):
        def gen():  # nombre vacío
            self.panel().name.setText("")
            yield 300
        return gen()


class ElegirPlano(Caso):
    nombre = "Croquis: elegir plano"
    tipo = None
    reglas = ("cancelar", "otro_comando")  # se acepta eligiendo el plano (abre el croquis)

    def preparar(self, doc):
        import FreeCADGui
        self.doc = doc
        body = doc.addObject("PartDesign::Body", "Cuerpo")
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("PartDesign_NewSketch")
        yield from esperar_panel()


class Croquis3D(Caso):
    nombre = "Croquis 3D"
    # sin "otro_comando": en SW, otro comando con un croquis abierto lo cierra CONSERVANDO lo
    # dibujado (no es cancelar); FreeWorks hace lo mismo
    tipo = "App::DocumentObjectGroup"
    ayudantes = ("App::VarSet", "Part::Line")
    otro = "SWUI_Sketch3D"  # (sin Cuerpo, Chaflán pide uno: no sirve para esta regla)
    reglas = ("cancelar", "invalido", "aceptar", "guardar")

    def preparar(self, doc):
        self.doc = doc

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_Sketch3D")
        yield from esperar_panel()

    def elegir(self, rng):
        from swui.fork import sketch3d as s3
        p = self.panel()
        a = V(0, 0, 0)
        for _i in range(rng.randint(1, 3)):
            b = a + V(rng.uniform(10, 50), rng.uniform(-30, 30), rng.uniform(0, 40))
            s3.add_line(p.sk, s3.free(a), s3.free(b))  # puntas libres, como dibujar con el mouse
            a = b
        p.refresh()
        yield 600

    def invalido(self):
        return None  # vacío se acepta y se borra solo (como SW): no hay inválido


CASOS = [ConvertirChapa, VistaSeccion, AgregarConfiguracion, ElegirPlano, Croquis3D]
