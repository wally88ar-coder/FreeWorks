# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Entornos del fuzzing de secuencias ("el mono", `mono_comun.py`): la pieza de arranque, los paneles
que se pueden abrir y las acciones propias de cada parte de FreeWorks. Cada prueba
`prueba_ventana_mono*.py` corre uno; la corrida de noche, todos.
"""

import os

from azar_comun import bombear
from mono_comun import Entorno, correr, diferencias, solo_lo_de_antes

class Pieza(Entorno):
    nombre = "pieza"
    vinculos = ("body", "hueco")

    def armar(self):
        from casos_pieza import armar_pieza
        self.body, self.hueco = armar_pieza(self.doc)

    def crear_casos(self):
        from casos_pieza import AnguloSalida, Chaflan, MatrizCircular, MatrizLineal, Redondeo, Simetria
        from casos_pieza2 import Eje, MoverCara, Plano, Punto
        return [c() for c in (Redondeo, Chaflan, AnguloSalida, MatrizLineal, MatrizCircular, Simetria,
                              Plano, Eje, Punto, MoverCara)]


def _diferido(fn):
    """Corre `fn` desde la ventana (si muestra un aviso en ventanita, la prueba no queda trabada)."""
    from PySide import QtCore
    hecho = {}
    QtCore.QTimer.singleShot(0, lambda: hecho.update(r=fn()))
    for _i in range(40):
        bombear(250)
        if "r" in hecho:
            break
    bombear(500)
    return hecho.get("r")


class Chapa(Entorno):
    nombre = "chapa"
    vinculos = ("body", "croquis")
    acciones = ("aplanar", "dxf")
    deuda = (("#43", "Invalid shape name ?Face", "Unfold"),
             ("#44", "Failed to recompute suppressed feature", None))

    def armar(self):
        from casos_grupo3 import BridaArista, BridaBase
        h = BridaArista()
        correr(h.preparar(self.doc))  # cuerpo, croquis y brida base por su panel
        self.body, self.croquis = h.body, h.croquis
        base = [o for o in self.body.Group if o.TypeId == "PartDesign::FeaturePython"]
        assert base, "no se armó la Brida base de arranque"
        bb = BridaBase()
        bb.croquis = self.croquis
        self.hechos.append((base[0].Name, bb))
        self._bb = bb

    def crear_casos(self):
        from casos_grupo3 import BridaArista, Dobladillo
        return [BridaArista(), Dobladillo(), BridaArista()]  # más bridas que dobladillos, como en el taller

    def atar(self):
        super().atar()
        self._bb.doc, self._bb.body, self._bb.croquis = self.doc, self.body, self.croquis

    def accion_aplanar(self, rng, que, f0):
        from swui.fork import sheet_metal as sm
        from swui.fork import sheet_panels
        flat = _diferido(sheet_panels.toggle_flat)
        assert flat is not None, "%s: no se pudo desplegar" % que
        assert flat.Visibility and not self.body.Visibility, "%s: desplegado, la chapa debería ocultarse" % que
        assert flat.Shape.isValid() and flat.Shape.Area > 0, "%s: el desarrollo no es válido" % que
        _diferido(sheet_panels.toggle_flat)
        assert self.body.Visibility and not sm.flat_of(self.body).Visibility, "%s: al plegar no volvió la chapa" % que
        d = diferencias(f0, solo_lo_de_antes(f0, self.foto()))
        assert not d, "%s: desplegar y plegar cambió la chapa: %s" % (que, d[:3])

    def accion_dxf(self, rng, que, f0):
        from _base import carpeta_temporal
        from swui.fork import sheet_metal as sm
        from swui.fork import sheet_panels
        if not self.doc.FileName:
            self.doc.saveAs(os.path.join(carpeta_temporal(), "mono_chapa.FCStd"))
            f0 = self.foto()
        nombre = sm.dxf_filename(sm.part_name(self.body), sm.thickness(self.body), sm.material_name(self.body))
        ruta = os.path.join(os.path.dirname(self.doc.FileName), nombre)
        if os.path.exists(ruta):
            os.remove(ruta)  # si no, pregunta si reemplazar (eso lo prueba otra cosa)
        hecho = _diferido(sheet_panels.export_dxf)
        assert hecho == ruta and os.path.exists(ruta), "%s: no salió el DXF %s (dio %r)" % (que, ruta, hecho)
        texto = open(ruta, encoding="utf-8", errors="replace").read()
        assert "ENTITIES" in texto and ("LINE" in texto or "LWPOLYLINE" in texto), \
            "%s: el DXF no tiene el contorno" % que
        d = diferencias(f0, solo_lo_de_antes(f0, self.foto()), visibilidad=False)
        assert not d, "%s: exportar el DXF cambió la chapa: %s" % (que, d[:3])


class Ensamblaje(Entorno):
    nombre = "ensamblaje"
    vinculos = ("asm", "comps")
    acciones = ("suprimir_componente", "cambiar_pieza")
    deuda = (("#38", "The graph must be a DAG", None),)
    deuda_pasos = (("#37", "Ctrl+Z no volvió", "aceptar Taladro de ensamblaje"),
                   ("#38", "al abrir quedó modificado", "guardar"))

    def armar(self):
        from casos_ensamblaje import Relacion
        h = Relacion()
        correr(h.preparar(self.doc))  # piezas guardadas, conjunto guardado e insertadas
        self.asm, self.comps = h.asm, h.comps
        assert len(self.comps) == 2, "no se insertaron las dos piezas"

    def crear_casos(self):
        from casos_ensamblaje import MatrizComponentes, PlanoEnsamblaje, Relacion
        from casos_ensamblaje2 import CorteEnsamblaje, TaladroEnsamblaje
        return [Relacion(), Relacion(), MatrizComponentes(), PlanoEnsamblaje(), TaladroEnsamblaje(),
                CorteEnsamblaje()]

    def cuerpo(self):
        return None  # en el conjunto se suprimen componentes (acción propia)

    def otros_documentos(self):
        out = []
        for c in getattr(self, "comps", None) or []:
            try:
                d = c.LinkedObject.Document
            except Exception:
                continue
            if d is not self.doc and d not in out:
                out.append(d)
        return out

    def accion_suprimir_componente(self, rng, que, f0):
        import FreeCADGui
        from reglas_paneles import ctrl_z
        from swui.fork import config_asm
        bloque = self.comps[1]
        if config_asm.is_suppressed(bloque):
            return
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, bloque.Name)
        FreeCADGui.runCommand("SWUI_ComponentSuppress")
        bombear(800)
        FreeCADGui.Selection.clearSelection()
        assert config_asm.is_suppressed(bloque), "%s: el Bloque no quedó suprimido" % que
        ctrl_z(self.doc)
        self.doc.recompute()
        bombear(600)
        d = diferencias(f0, self.foto(), visibilidad=False)
        assert not d, "%s: Ctrl+Z después de suprimir el componente no volvió: %s" % (que, d[:3])
        assert not config_asm.is_suppressed(bloque), "%s: Ctrl+Z no volvió a mostrar el Bloque" % que

    def accion_cambiar_pieza(self, rng, que, f0):
        pieza = self.comps[1].LinkedObject.Document
        caja = pieza.getObject("Caja")
        antes = float(caja.Length.Value)
        caja.Length = round(rng.uniform(12.0, 35.0), 1)
        pieza.recompute()
        self.doc.recompute()
        bombear(800)
        malos = self.malos()
        assert not malos, "%s: con el Bloque de largo %s quedaron con error: %s" % (que, caja.Length, sorted(malos))
        caja.Length = antes
        pieza.recompute()
        self.doc.recompute()
        bombear(800)
        d = diferencias(f0, self.foto(), visibilidad=False)
        assert not d, "%s: al volver el largo del Bloque, el conjunto no quedó como estaba: %s" % (que, d[:3])
