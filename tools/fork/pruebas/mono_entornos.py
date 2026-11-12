# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Entornos del fuzzing de secuencias ("el mono", `mono_comun.py`): la pieza de arranque, los paneles
que se pueden abrir y las acciones propias de cada parte de FreeWorks. Cada prueba
`prueba_ventana_mono*.py` corre uno; la corrida de noche, todos.
"""

import os

import FreeCAD

from azar_comun import bombear
from mono_comun import Entorno, correr, diferencias, solo_lo_de_antes

def _centro(shape):
    """Centro de masa de los sólidos (un Compound no tiene CenterOfMass en 1.1.4: Issue #67, era de
    la prueba); sin sólidos, el centro de la caja."""
    vol = sum(abs(s.Volume) for s in shape.Solids)
    if not shape.Solids or vol <= 0:
        return shape.BoundBox.Center
    c = FreeCAD.Vector()
    for s in shape.Solids:
        c = c + s.CenterOfMass * (abs(s.Volume) / vol)
    return c


class Pieza(Entorno):
    nombre = "pieza"
    vinculos = ("body", "hueco")
    acciones = ("medida_base",)

    def medida_base(self):
        caja = self.doc.getObject("Caja")
        return (caja, "Length") if caja is not None else None

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
    # el DXF también despliega por dentro: mismo #59 (noche/batería del 10/11)
    deuda_pasos = (("#59", "Ctrl+Z después de suprimir no volvió", "suprimir", "aplanar"),
                   ("#59", "Ctrl+Z después de suprimir no volvió", "suprimir", "dxf"))

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
    # el resolvedor de FreeCAD con Matriz + Taladro/Corte + Relaciones (también sin Ecuaciones)
    deuda = (("#76", "Solve failed: invalid vector subscript", None),
             # la relación pierde su cara tras un corte: FreeCAD avisa antes de que se repare (#80)
             ("#80", ("Broken link in: Reference", 'errStr + "Reference'), None),
             # el resolvedor no converge al aceptar una relación tras guardar y abrir (#76, otro aviso)
             ("#76", "Solve failed: iterNo > iterMax", None))
    deuda_pasos = ()

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


class Soldada(Entorno):
    nombre = "soldadas"
    vinculos = ("esqueleto", "cuerpos")
    acciones = ("esqueleto", "esqueleto")
    # error ya registrado: #40 (el reabierto se cierra solo)
    deuda = ()
    deuda_pasos = (("~#40", "se cerró solo", "guardar"),)

    def armar(self):
        from casos_soldadas import _anotar_paneles
        from comun import marco
        _anotar_paneles()
        self.esqueleto, self._cota, self.cuerpos = marco(self.doc, esquina="inglete")

    def crear_casos(self):
        from casos_soldadas import Cartela, Esquinas, Miembro, Tapa
        return [Miembro(), Esquinas(), Esquinas(), Cartela(), Tapa()]

    def cuerpo(self):
        return None  # cada caño es un Cuerpo: se prueba con el esqueleto y las esquinas

    def accion_esqueleto(self, rng, que, f0):
        """Cambiar el ancho y el alto del esqueleto (sus cotas, como el usuario): los caños lo siguen
        sin superponerse ni dejar huecos, la lista de cortes da el largo real y cada caño queda igual
        que en un marco armado de cero con las medidas nuevas; volver las cotas: como antes."""
        ancho, alto = round(rng.uniform(450.0, 800.0), 1), round(rng.uniform(300.0, 550.0), 1)
        que = "%s (esqueleto %s x %s)" % (que, ancho, alto)
        self._cotas(ancho, alto)
        try:
            self._chequear_marco(que, ancho, alto)
        finally:
            self._cotas(600.0, 400.0)  # siempre de vuelta, aunque falle (el paso siguiente arranca sano)
        d = diferencias(f0, self.foto(), visibilidad=False)
        assert not d, "%s: al volver las cotas del esqueleto, no quedó como estaba: %s" % (que, d[:3])

    def _chequear_marco(self, que, ancho, alto):
        from comun import marco
        from swui.fork import weldments as w
        cuerpos = [b for b in self.cuerpos if b is not None]
        malos = [b.Label for b in cuerpos if b.Shape.isNull() or not b.Shape.isValid()]
        assert not malos, "%s: caños con error al cambiar el esqueleto: %s" % (que, malos)
        for a in range(len(cuerpos)):
            for b in range(a + 1, len(cuerpos)):
                comun = cuerpos[a].Shape.common(cuerpos[b].Shape).Volume
                assert comun < 0.01, "%s: los caños no siguen al esqueleto: %s y %s se superponen %.3f mm³" % (
                    que, cuerpos[a].Label, cuerpos[b].Label, comun)
        for c in w.find_corners(cuerpos):
            d = c["a"].Shape.distToShape(c["b"].Shape)[0]
            assert d < 1e-3, "%s: los caños no siguen al esqueleto: hueco de %.2f mm" % (que, d)
        largos = {}
        for f in w.cut_list(self.doc):
            for etiqueta in f["members"]:
                largos[etiqueta] = f["length"]
        for b in cuerpos:
            _p0, _p1, u = w.axis(b)
            proy = [v.Point.dot(u) for v in b.Shape.Vertexes]
            real = max(proy) - min(proy)
            assert b.Label in largos and abs(largos[b.Label] - real) <= 0.1,                 "%s: la lista de cortes no da el largo de %s (%s, mide %.2f)" % (que, b.Label, largos.get(b.Label), real)
        # el control fuerte: igual que un marco armado de cero con el esqueleto nuevo
        activo = FreeCAD.ActiveDocument
        otro = FreeCAD.newDocument("MonoDeCero")
        try:
            _sk2, _c2, cuerpos2 = marco(otro, ancho=ancho, alto=alto, esquina="inglete")
            for a, b in zip(self.cuerpos[:4], cuerpos2):
                ca, cb = _centro(a.Shape), _centro(b.Shape)
                assert abs(a.Shape.Volume - b.Shape.Volume) < 0.5 and (ca - cb).Length < 0.01,                     "%s: los caños no siguen al esqueleto: %s no quedó como armado de cero (volumen %.1f vs %.1f)" % (
                        que, a.Label, a.Shape.Volume, b.Shape.Volume)
        finally:
            FreeCAD.closeDocument(otro.Name)
            if activo is not None:
                FreeCAD.setActiveDocument(activo.Name)

    def _cotas(self, ancho, alto):
        sk = self.esqueleto
        sk.setDatum(self._cota, FreeCAD.Units.Quantity("%s mm" % ancho))
        sk.setDatum(self._cota + 1, FreeCAD.Units.Quantity("%s mm" % alto))
        self.doc.recompute()
        bombear(600)


class Croquis(Entorno):
    nombre = "croquis"
    vinculos = ("body", "croquis")
    deuda = ()

    def armar(self):
        from casos_croquis import Simetria
        h = Simetria()
        h.preparar(self.doc)  # rectángulo de 30 x 20 y un eje constructivo
        self.body, self.croquis = self.doc.getObject("Cuerpo"), h.croquis

    def crear_casos(self):
        from casos_croquis import CASOS
        return [c() for c in CASOS]

    def cuerpo(self):
        return None  # el Cuerpo solo tiene el croquis


class Multicuerpo(Entorno):
    nombre = "multicuerpo"
    vinculos = ("body", "hueco", "otro_body")
    acciones = ("medida_base",)
    # suprimir Combinar con un Redondeo encima: el hijo suprimido igual se recalcula y avisa que su
    # arista ya no existe (#44); "Invalid edge link" solo se perdona si viene con ese aviso
    deuda = (("#44", ("Failed to recompute suppressed feature", "Invalid edge link"), None),
             ("#44", "Failed to recompute suppressed feature", None))
    # editar Combinar le cambia el tipo (sumar / restar / común): el sólido es otro y la arista de
    # un Redondeo de encima puede dejar de existir; en SW también queda con error (no es falla, #65)
    deuda = deuda + (("esperado, como SW (no es falla)", "Invalid edge link", "Fillet", "editar Combinar"),)

    def medida_base(self):
        caja = self.doc.getObject("Caja")
        return (caja, "Length") if caja is not None else None

    def armar(self):
        from casos_pieza2 import Combinar
        h = Combinar()
        h.preparar(self.doc)  # la pieza con agujero y un segundo Cuerpo que la toca
        self.body, self.hueco, self.otro_body = h.body, h.hueco, h.otro_body

    def crear_casos(self):
        from casos_grupo3 import EliminarConservar, MoverCopiarSolidos
        from casos_pieza import Chaflan, Redondeo
        from casos_pieza2 import Combinar
        return [Combinar(), Combinar(), MoverCopiarSolidos(), EliminarConservar(), Redondeo(), Chaflan()]


class Configuraciones(Entorno):
    """Pieza con configuraciones: además de los paneles, agregar configuraciones con otro largo y
    pasar de una a otra en cualquier orden (cada una con SU largo)."""
    nombre = "configuraciones"
    vinculos = ("body", "hueco")
    acciones = ("config_nueva", "config_ir", "config_ir")
    # suprimir el Agujero con un Redondeo sobre su arista: el redondeo se suprime con él (como SW)
    # pero FreeCAD igual lo recalcula y avisa (#44; reproducido sin ventana el 10/11)
    deuda = (("#44", ("Failed to recompute suppressed feature", "Invalid edge link"), None, "suprimir"),
             ("#44", "Failed to recompute suppressed feature", None, "suprimir"))

    def armar(self):
        from casos_otros import anotar
        from casos_pieza import armar_pieza
        from swui.fork import config_tab
        from swui.fork import configurations as cf
        anotar(config_tab._AddPanel)
        self.body, self.hueco = armar_pieza(self.doc)
        cf.ensure(self.doc)
        self.largos = {cf.active(self.doc) or cf.names(self.doc)[0]: 40.0}

    def crear_casos(self):
        from casos_otros import AgregarConfiguracion
        from casos_pieza import Chaflan, Redondeo
        return [Redondeo(), Chaflan(), AgregarConfiguracion()]

    def _caja(self):
        return self.doc.getObject("Caja")

    def accion_config_nueva(self, rng, que, f0):
        from swui.fork import configurations as cf
        if len(self.largos) >= 4:
            return
        try:
            nombre = cf.add(self.doc, "Mono%d" % rng.randint(1, 9999))
        except ValueError as e:  # #75: con una operación en error
            raise AssertionError("%s: %s" % (que, e))
        # desde 40: más corta, la pared derecha (x = largo - 20) llega al Agujero (borde en x = 13) y
        # a los redondeos/chaflanes de hasta 4 que lo rodean; la pieza se rompe de verdad (también
        # sin configuraciones y en SW). Era la variante de #74 que quedaba (12/11, 300 casos sin
        # ventana: 0 rotos de 38 a 70; con el agujero lejos de la pared, 0 rotos de 25 a 70)
        largo = round(rng.uniform(40.0, 70.0), 1)
        cf.configure(self.doc, ("prop", self._caja(), "Length"), largo, scope="this")
        self.doc.recompute()
        bombear(400)
        self.largos[nombre] = largo
        assert abs(self._caja().Length.Value - largo) < 1e-6, "%s: la configuración nueva no tomó su largo" % que

    def accion_config_ir(self, rng, que, f0):
        from swui.fork import configurations as cf
        conocidas = [n for n in sorted(self.largos) if n in cf.names(self.doc)]
        if not conocidas:
            return
        nombre = rng.choice(conocidas)
        cf.activate(self.doc, nombre)
        self.doc.recompute()
        bombear(400)
        largo = self._caja().Length.Value
        assert abs(largo - self.largos[nombre]) < 1e-6, \
            "%s: en la configuración %s el largo es %s, debería ser %s" % (que, nombre, largo, self.largos[nombre])
        malos = self.malos()
        assert not malos, "%s: al pasar a %s quedaron con error: %s" % (que, nombre, sorted(malos))

    def reabierto(self):
        from swui.fork import configurations as cf
        self.largos = {n: v for n, v in self.largos.items() if n in cf.names(self.doc)}
