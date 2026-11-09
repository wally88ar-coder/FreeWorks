# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de secuencias ("el mono", paso 8.3) en CHAPA, con la ventana (motor en `mono_comun.py`).
Arranque: una Brida base (por su panel) de un rectángulo. Seguidillas al azar de:
- Brida de arista y Dobladillo (Aceptar / Cancelar; Ctrl+Z y Ctrl+Y exactos);
- editar lo hecho (espesor de la brida base, largo de una brida o dobladillo) y Aceptar;
- desplegar y volver a plegar (Aplanar ida y vuelta): la chapa queda igual que antes;
- exportar el DXF: sale el archivo con contorno, y la chapa queda igual;
- suprimir, Deshacer / Rehacer, guardar y abrir.
Después de CADA paso: sin errores, nada colgado, sin objetos con error.
Seguidillas por regla: FW_CASOS_AZAR (6); largo: 3 a FW_LARGO_MONO (8)."""
TIPO = "completa"

import os  # noqa: E402

from azar_comun import bombear  # noqa: E402
from mono_comun import Entorno, correr, correr_reglas, diferencias, solo_lo_de_antes  # noqa: E402


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


def prueba():
    correr_reglas(Chapa)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
