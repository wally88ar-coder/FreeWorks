# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Caso de las reglas de paneles: Corte desdoblado de chapa. Su panel solo existe al EDITAR un corte
ya hecho, así que la pieza se arma como el usuario: Brida base, Brida de arista, Desdoblar,
dibujar un círculo sobre el desarrollo, Doblar. Después se prueban las reglas de edición
(editar_cancelar, editar_cambiar, editar) y guardar.
"""

import FreeCAD

from casos_grupo3 import _SobreBrida, correr_cinta
from reglas_paneles import esperar_panel, tocar

V = FreeCAD.Vector


class CorteDesdoblado(_SobreBrida):
    nombre = "Corte desdoblado"
    tipo = "PartDesign::FeaturePython"
    reglas = ("editar", "guardar")
    cambio_visible = False  # el factor K mueve el corte décimas: no siempre cambia la foto

    def preparar(self, doc):
        import FreeCADGui
        from swui.fork import sheet_panels
        yield from super().preparar(doc)  # brida base
        # una brida de arista: que haya un pliegue que el corte atraviese al doblar
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.body.Tip, self.aristas()[0])
        correr_cinta("SWUI_SMEdgeFlange")
        yield from esperar_panel()
        tocar()
        yield 2500
        assert not FreeCADGui.Control.activeDialog(), "la Brida de arista no se aceptó"
        antes = {o.Name for o in doc.Objects}
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", self.body)
        # fuera del generador: si Desdoblar o Doblar muestran un aviso (ventanita modal), la prueba
        # no queda trabada adentro de la llamada
        from PySide import QtCore
        hecho = {}
        QtCore.QTimer.singleShot(0, lambda: hecho.update(sk=sheet_panels.start_unfold()))
        yield 2500
        sk = hecho.get("sk")
        assert sk is not None, "Desdoblar no abrió el croquis"
        import Part
        sk.addGeometry(Part.Circle(V(40, 25, 0), V(0, 0, 1), 4))
        sk.recompute()
        for _i in range(3):  # Doblar (si el croquis está abierto, lo cierra y vuelve a llamar)
            QtCore.QTimer.singleShot(0, sheet_panels.start_fold)
            yield 2500
            if [o for o in doc.Objects if o.Name not in antes and o.TypeId == self.tipo]:
                break
        doc.recompute()
        nuevos = [o for o in doc.Objects if o.Name not in antes and o.TypeId == self.tipo]
        assert nuevos, "no se pudo armar el Corte desdoblado (Desdoblar + círculo + Doblar)"
        self.hecho_inicial = nuevos[-1].Name

    def abrir(self, rng):
        return iter(())

    def cambiar(self, rng):
        def gen():
            p = self.panel()
            p.tied.setChecked(False)
            yield 200
            self.k_puesto = round(rng.uniform(0.3, 0.48), 3)
            p.k.setValue(self.k_puesto)
            p.preview()
            yield 1200
        return gen()

    def verificar_cambio(self, obj):
        # el círculo no cruza el pliegue: el factor K no cambia la forma; se mira el valor guardado
        k = float(getattr(obj, "kfactor", -1))
        return "" if abs(k - self.k_puesto) < 1e-3 else "el factor K quedó en %s (se puso %s)" % (k, self.k_puesto)


CASOS = [CorteDesdoblado]
