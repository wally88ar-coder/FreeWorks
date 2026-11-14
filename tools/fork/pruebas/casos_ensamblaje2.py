# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Casos de las reglas de paneles: Taladro y Extruir corte de ensamblaje. Cambian las PIEZAS (otros
documentos): la foto incluye esos documentos (`documentos`). El croquis se arma por código sobre
la cara de arriba de la Placa (como lo deja el paso "elegí una cara" + dibujar) y el panel se abre
con la función pública `assembly_features.open_panel_new`.
"""

import FreeCAD

from casos_ensamblaje import _Ensamblaje
from reglas_paneles import esperar_panel

V = FreeCAD.Vector


class _AsmCorte(_Ensamblaje):
    kind = ""
    otro = "SWUI_Mate"
    # el croquis lo arma la prueba en su propio paso de deshacer (en el uso real también es un
    # paso aparte: elegir la cara y dibujar): los pasos de deshacer no se cuentan
    contar_deshacer = False
    reglas = ("cancelar", "otro_comando", "aceptar", "editar", "guardar")

    def documentos(self, doc):
        out = []
        for c in getattr(self, "comps", []):
            try:
                out.append(c.LinkedObject.Document)
            except Exception:
                pass
        return out

    def cara_arriba(self, comp):
        for i, f in enumerate(comp.LinkedObject.Shape.Faces):
            n = f.normalAt(*f.ParameterRange[0:3:2])
            if f.Surface.__class__.__name__ == "Plane" and n.z > 0.99:
                return "Face%d" % (i + 1)

    def dibujar(self, sk, rng):
        raise NotImplementedError

    def editar(self, obj):
        from swui.fork import assembly_features as af
        af.open_panel(obj)  # como el doble clic en el árbol
        yield from esperar_panel()

    def abrir(self, rng):
        import FreeCADGui
        from swui.fork import assembly_features as af
        FreeCADGui.Selection.clearSelection()
        placa = self.comps[0]
        self.doc.openTransaction("Croquis de ensamblaje")
        sk = af.make_sketch(self.asm, placa, "%s.%s" % (placa.LinkedObject.Name, self.cara_arriba(placa)))
        self.dibujar(sk, rng)
        sk.recompute()
        self.doc.commitTransaction()
        self.antes_del_panel = tuple(self.antes_del_panel) + ((sk.Name, sk.TypeId),)
        af.open_panel_new(self.asm, self.kind, sk)
        yield from esperar_panel()

    def local(self, sk, x, y):
        """Punto (x, y) de la cara de arriba de la placa, en coordenadas del croquis."""
        v = sk.Placement.inverse().multVec(V(x, y, 10))
        return V(v.x, v.y, 0)


class TaladroEnsamblaje(_AsmCorte):
    nombre = "Taladro de ensamblaje"
    kind = "hole"
    tipo = "App::VarSet"
    ayudantes = ("Sketcher::SketchObject", "PartDesign::SubShapeBinder", "PartDesign::Hole")

    def dibujar(self, sk, rng):
        import Part
        sk.addGeometry(Part.Point(self.local(sk, rng.uniform(15, 85), rng.uniform(15, 45))))

    def elegir(self, rng):
        p = self.panel()
        if not hasattr(p, "size"):
            # el punto cayó donde no hay pieza (p. ej. adentro de otro taladro): el panel pide elegir
            # las piezas; con la placa elegida pasa al panel del taladro (#68)
            assert not p.direction.isVisibleTo(p.form), \
                "Taladro de ensamblaje sin piezas: muestra Dirección/Profundidad de un corte (#68)"
            assert p.message.isVisibleTo(p.form) and "ninguna pieza" in p.message.text(), \
                "Taladro de ensamblaje sin piezas: no avisa que no toca ninguna pieza (#68)"
            self.elegir_en(self.comps[0], self.cara_arriba(self.comps[0]))
            yield 1500
            p = self.panel()
            if not hasattr(p, "size"):
                raise AssertionError("Taladro de ensamblaje: elegida la pieza, no pasó al panel del "
                                     "taladro (%s, #68)" % type(p).__name__)
        if p.size.count():
            p.size.setCurrentIndex(rng.randrange(min(p.size.count(), 6)))
        p.preview()
        yield 1200


class CorteEnsamblaje(_AsmCorte):
    nombre = "Extruir corte de ensamblaje"
    kind = "cut"
    tipo = "App::VarSet"
    ayudantes = ("Sketcher::SketchObject", "PartDesign::SubShapeBinder", "PartDesign::Pocket")

    def dibujar(self, sk, rng):
        import Part
        x0, y0 = rng.uniform(10, 40), rng.uniform(10, 25)
        pts = [self.local(sk, x, y) for x, y in ((x0, y0), (x0 + 20, y0), (x0 + 20, y0 + 15), (x0, y0 + 15))]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))

    def elegir(self, rng):
        yield 1200

    # inválido: sin ninguna pieza afectada, Aceptar avisa y no cierra (#10: antes guardaba igual)
    reglas = _AsmCorte.reglas + ("invalido",)

    def invalido(self):
        def gen():
            self.panel()._clear_parts()
            yield 600
        return gen()


CASOS = [TaladroEnsamblaje, CorteEnsamblaje]
