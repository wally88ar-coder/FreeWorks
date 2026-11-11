# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles: piezas soldadas (Miembro estructural, Esquinas, Cartela, Tapa
de extremo). Esqueleto: rectángulo de 600 x 400 sin cotas.

Los paneles de soldadas no se anotan en el guardia de paneles (Issue #6): para manejarlos, la
prueba guarda el último que se creó (envuelve `_Base.__init__`, solo en esta prueba).
"""

import FreeCAD

from comun import croquis_rectangulo
from reglas_paneles import Caso, esperar_panel

_ULTIMO = {}


def _anotar_paneles():
    from swui.fork import weld_panels as wp
    if getattr(wp._Base.__init__, "_prueba", False):
        return
    original = wp._Base.__init__

    def init(self, *a, **k):
        _ULTIMO["p"] = self
        original(self, *a, **k)
    init._prueba = True
    wp._Base.__init__ = init


def correr_cinta(comando):
    from swui import ribbon
    ribbon._run(comando)


class _Soldada(Caso):
    otro = "SWUI_WeldMember"
    cuantos = None

    def panel(self):
        # el panel abierto de verdad, según el guardia (estos paneles se anotan ahí desde el 11/11):
        # "el último creado + hay algún panel" daba por abierto el primero cuando el comando nuevo
        # ya había abierto el suyo
        from swui.fork import panel_guard
        p = _ULTIMO.get("p")
        return p if p is not None and p is panel_guard.open_panel() else None

    def mensaje(self):
        texto = super().mensaje()
        if texto:
            return texto
        return ""

    def preparar(self, doc):
        _anotar_paneles()
        self.doc = doc
        self.esqueleto, _c = croquis_rectangulo(doc, 600, 400)

    def miembros(self, n=4, kind="Caño cuadrado"):
        from swui.fork import weldments as w
        size = w.sizes(kind)[10][0]
        bodies = w.create_members(self.doc, [(self.esqueleto, "Edge%d" % (i + 1)) for i in range(n)], kind, size)
        self.doc.recompute()
        return bodies


class Miembro(_Soldada):
    nombre = "Miembro estructural"
    tipo = "PartDesign::Body"
    ayudantes = ("App::Origin", "App::Line", "App::Plane", "App::Point", "App::DocumentObjectGroup",
                 "Sketcher::SketchObject", "PartDesign::Pad", "PartDesign::SubShapeBinder",
                 "PartDesign::Pocket", "PartDesign::SubtractiveBox", "App::VarSet")
    otro = "SWUI_WeldCorners"

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_WeldMember")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        p = self.panel()
        for i in sorted(rng.sample(range(4), rng.randint(1, 4))):
            FreeCADGui.Selection.addSelection(self.esqueleto, "Edge%d" % (i + 1))
            yield 400
        if p.size.count():
            p.size.setCurrentIndex(rng.randrange(p.size.count()))
        yield 900

    def invalido(self):
        def gen():  # sin ninguna línea del esqueleto
            yield 300
        return gen()

    def editar(self, obj):
        from swui.fork import weld_panels as wp
        grupo = [g for g in obj.InList if g.TypeId == "App::DocumentObjectGroup"]
        wp.open_edit_member(grupo[0] if grupo else obj)
        yield from esperar_panel()


class Esquinas(_Soldada):
    nombre = "Esquinas"
    tipo = ("PartDesign::Pocket", "PartDesign::SubtractiveBox", "PartDesign::Pad",
            "PartDesign::SubShapeBinder")
    ayudantes = ("Sketcher::SketchObject",)
    reglas = ("cancelar", "otro_comando", "aceptar", "guardar")

    def preparar(self, doc):
        super().preparar(doc)
        self.cuerpos = self.miembros()

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_WeldCorners")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        for _c, treat, _passing in p.rows:
            treat.setCurrentIndex(rng.randrange(treat.count()))
        yield 1200


class Cartela(_Soldada):
    nombre = "Cartela"
    tipo = "PartDesign::Body"
    ayudantes = ("App::Origin", "App::Line", "App::Plane", "App::Point", "Sketcher::SketchObject",
                 "PartDesign::Pad", "PartDesign::SubShapeBinder", "App::DocumentObjectGroup")
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "guardar")

    def preparar(self, doc):
        super().preparar(doc)
        self.cuerpos = self.miembros()

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_WeldGusset")
        yield from esperar_panel()

    def elegir(self, rng):
        import FreeCADGui
        i = rng.randrange(4)
        for b in (self.cuerpos[i], self.cuerpos[(i + 1) % 4]):  # dos que forman esquina
            FreeCADGui.Selection.addSelection(b.Tip, "Face1")
            yield 500
        p = self.panel()
        p.size.setValue(round(rng.uniform(50.0, 120.0), 0))
        yield 600

    def invalido(self):
        def gen():  # un solo miembro
            import FreeCADGui
            FreeCADGui.Selection.addSelection(self.cuerpos[0].Tip, "Face1")
            yield 500
        return gen()


class Tapa(_Soldada):
    nombre = "Tapa de extremo"
    tipo = "PartDesign::Body"
    ayudantes = Cartela.ayudantes
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "guardar")

    def preparar(self, doc):
        super().preparar(doc)
        self.cuerpos = self.miembros(n=1)  # un caño suelto: sus dos puntas libres

    def abrir(self, rng):
        import FreeCADGui
        FreeCADGui.Selection.clearSelection()
        correr_cinta("SWUI_WeldEndCap")
        yield from esperar_panel()

    def elegir(self, rng):
        p = self.panel()
        p.pick = (self.cuerpos[0], rng.randrange(2))
        p.thick.setValue(round(rng.uniform(2.0, 6.0), 1))
        p._changed()
        yield 900

    def invalido(self):
        def gen():  # sin elegir la punta
            yield 300
        return gen()


CASOS = [Miembro, Esquinas, Cartela, Tapa]


# --- Editar cambiando un valor (reglas editar_cancelar y editar_cambiar) ---
from reglas_paneles import cambia_lista  # noqa: E402

Miembro.cambiar = cambia_lista("size")
