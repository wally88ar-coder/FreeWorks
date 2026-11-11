# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Motor del fuzzing de secuencias ("el mono", plan de calidad, paso 8.3), común a todos los entornos
(pieza, chapa, ensamblaje, soldadas...). Cada prueba `prueba_ventana_mono*.py` define un Entorno:
cómo se arma la pieza de arranque, qué paneles se pueden abrir (los "casos" de las reglas de
paneles) y acciones propias (desplegar la chapa, exportar el DXF, cambiar de configuración...).

Acciones comunes:
- aceptar: abrir un panel, elegir al azar, Aceptar; Ctrl+Z vuelve exacto, Ctrl+Y lo trae igual (si
  el panel no acepta lo elegido, Cancelar deja todo igual);
- cancelar: abrir, elegir, Cancelar: todo igual;
- editar: abrir una operación ya hecha en esta seguidilla, cambiarle un valor, Aceptar; Ctrl+Z y
  Ctrl+Y exactos;
- suprimir: una operación desde el árbol; Ctrl+Z la vuelve;
- deshacer / rehacer sueltos;
- guardar: guardar, cerrar y abrir: todo igual y sin quedar "modificado";
- ecuaciones / material (regla aparte; era el error #3, arreglado): con un panel abierto, abrir Ecuaciones
  o Material, cerrarlos y Cancelar el panel: todo igual.
Después de CADA paso: sin errores en el informe, nada colgado, sin objetos con error nuevos.

No cuentan (ya los miden otras pruebas): la visibilidad después de Ctrl+Z / Ctrl+Y (error #36) y el
aviso propio de FreeCAD "... not possible ..." cuando lo elegido al azar no sirve.
"""

import os
import random
import re

import FreeCAD

from _base import carpeta_temporal, traza
from azar_comun import Fallas, bombear, comprobado, hypothesis_listo

LARGO = int(os.environ.get("FW_LARGO_MONO", "8"))
BASE = ["aceptar", "aceptar", "cancelar", "editar", "suprimir", "deshacer", "rehacer", "guardar", "otro_archivo"]
OTRA_HERRAMIENTA = ["ecuaciones", "material", "aceptar"]


def correr(gen):
    """Corre un generador de los casos (`yield ms`) de corrido, bombeando la ventana."""
    if gen is None:
        return
    for ms in gen:
        bombear(int(ms or 0))


class NadaQueElegir(Exception):
    """La pieza ya no tiene dónde abrir ese panel (p. ej. no quedan aristas libres): el paso se saltea."""


def abrir(caso, rng):
    """Abre el panel del caso. Si falla ANTES de abrirlo porque no hay qué elegir (lista vacía), el
    paso se saltea: es un límite de la prueba, no de FreeWorks."""
    import FreeCADGui
    from PySide import QtCore, QtWidgets
    # Si la herramienta contesta con un aviso en ventanita ("Hacen falta al menos dos sólidos"), la
    # llamada queda adentro de esa ventanita hasta que alguien toque OK: un reloj la lee y la cierra.
    avisos = []

    def mirar():
        d = QtWidgets.QApplication.activeModalWidget()
        if isinstance(d, QtWidgets.QMessageBox):
            avisos.append(d.text())
            d.accept()
    reloj = QtCore.QTimer()
    reloj.timeout.connect(lambda: mirar())
    reloj.start(300)
    try:
        correr(caso.abrir(rng))
    except IndexError:
        if FreeCADGui.Control.activeDialog():
            raise
        raise NadaQueElegir()
    finally:
        reloj.stop()
    if avisos and not FreeCADGui.Control.activeDialog():
        traza("    (%s no se abrió, avisó: %s)" % (caso.nombre, avisos[0][:120]))
        raise NadaQueElegir()


def _tipos(caso):
    t = caso.tipo
    return t if isinstance(t, tuple) else (t,)


class Entorno:
    """La pieza de arranque y lo que el mono puede hacer con ella. Las subclases completan."""

    nombre = "pieza"
    vinculos = ("body",)  # atributos que son objetos del documento (se vuelven a buscar al reabrir)
    acciones = ()         # acciones propias del entorno (métodos accion_<nombre>)
    # errores ya registrados que el mono no frena (para que siga buscando otros): ("#N", texto que
    # aparece en el informe, parte del nombre del objeto que queda con error o None). Se anotan en
    # la traza. El texto puede ser una tupla: cuenta solo si aparecen TODOS en el informe del paso
    # (así un aviso que suele acompañar al error conocido no se perdona cuando sale solo).
    deuda = ()
    # comprobaciones que fallan por un error ya registrado: ("#N", texto del aviso, parte del paso,
    # p. ej. "aceptar Taladro de ensamblaje"), y opcional un cuarto: un paso que tiene que haber
    # pasado antes en la seguidilla (p. ej. "aplanar"). El paso se anota en la traza y el mono sigue.
    deuda_pasos = ()

    def __init__(self):
        from azar_comun import limpiar
        limpiar()  # cada seguidilla, de cero y con un solo archivo abierto (memoria de la PC)
        self.doc = FreeCAD.newDocument("Mono")
        self.doc.UndoMode = 1
        self.hechos = []  # (nombre del objeto, caso) que se pueden editar (aceptados o de arranque)
        self.armar()
        self.doc.recompute()
        # la pieza de arranque es "la que se abrió": Deshacer no la desarma (si no, el mono pierde lo
        # que necesita y falla la prueba, no FreeWorks)
        self.doc.clearUndos()
        for o in self.otros_documentos():
            o.clearUndos()
        self.casos = self.crear_casos()
        self.atar()
        bombear(1000)  # que la ventana termine de mostrar la pieza nueva antes de la primera foto

    # --- a completar ---
    def armar(self):
        raise NotImplementedError

    def crear_casos(self):
        return []

    def otros_documentos(self):
        """Otros documentos que el mono cambia (las piezas de un ensamblaje)."""
        return []

    def atar(self):
        """Pasa a cada caso lo que necesita (documento, cuerpo, pieza...)."""
        for c in self.casos:
            c.doc = self.doc
            for v in self.vinculos:
                setattr(c, v, getattr(self, v))

    def cuerpo(self):
        """El Cuerpo cuyas operaciones se pueden suprimir (None: no se suprime)."""
        return getattr(self, "body", None)

    # --- medir ---
    def foto(self):
        from reglas_paneles import foto_varios
        return foto_varios(self.doc, self.otros_documentos())

    def malos(self):
        from reglas_paneles import invalidos
        out = set(invalidos(self.doc))
        for o in self.otros_documentos():
            try:
                out |= {"%s:%s" % (o.Label, n) for n in invalidos(o)}
            except Exception:
                pass
        return out

    # --- guardar y abrir ---
    def guardar_y_abrir(self):
        import FreeCADGui
        nombres = {}
        for v in self.vinculos:
            x = getattr(self, v, None)
            if isinstance(x, (list, tuple)):
                nombres[v] = [o.Name for o in x]
            elif x is not None:
                nombres[v] = x.Name
        hechos = [(n, c) for n, c in self.hechos]
        for o in self.otros_documentos():  # las piezas de un ensamblaje, junto a él
            if getattr(o, "FileName", ""):
                o.save()
        ruta = self.doc.FileName or os.path.join(carpeta_temporal(), "mono.FCStd")
        self.doc.saveAs(ruta)
        FreeCAD.closeDocument(self.doc.Name)
        bombear(400)
        self.doc = FreeCAD.openDocument(ruta)
        bombear(1200)
        for v, n in nombres.items():
            setattr(self, v, [self.doc.getObject(x) for x in n] if isinstance(n, list) else self.doc.getObject(n))
        self.hechos = hechos
        self.reabierto()
        self.atar()
        if getattr(self, "body", None) is not None:
            FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", self.body)

    def reabierto(self):
        """Después de abrir de nuevo: volver a buscar lo que haga falta (otros documentos...)."""

    # --- pregunta 6 de las 7: dos archivos abiertos ---
    otro = None
    otro_foto = None

    def accion_otro_archivo(self, rng, que, f0):
        """Abrir (crear) otro archivo con una pieza, y volver al de trabajo como el usuario (su
        pestaña). Desde acá, después de cada paso se controla que el otro archivo no cambie."""
        import FreeCADGui
        from reglas_paneles import foto
        try:
            vivo = self.otro is not None and self.otro.Name in FreeCAD.listDocuments()
        except ReferenceError:  # se cerró por otro lado
            vivo = False
        if not vivo:
            self.otro = FreeCAD.newDocument("OtroArchivo")
            b = self.otro.addObject("PartDesign::Body", "Cuerpo")
            c = b.newObject("PartDesign::AdditiveBox", "Caja")
            c.Length, c.Width, c.Height = 25, 15, 5
            self.otro.recompute()
            bombear(600)
            self.otro_foto = foto(self.otro)
        FreeCAD.setActiveDocument(self.doc.Name)
        FreeCADGui.setActiveDocument(self.doc.Name)
        bombear(600)
        if getattr(self, "body", None) is not None:
            FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", self.body)
        # abrir otro archivo y volver no cambia nada del de trabajo
        d = diferencias(f0, self.foto(), visibilidad=False)
        assert not d, "%s: abrir otro archivo y volver cambió el de trabajo: %s" % (que, d[:3])

    def otro_igual(self, que):
        from reglas_paneles import foto
        if self.otro is None:
            return
        try:
            ahora = foto(self.otro)
        except Exception:  # también ReferenceError: el documento se cerró
            raise AssertionError("%s: el otro archivo abierto se cerró o se rompió" % que)
        d = diferencias(self.otro_foto, ahora)
        assert not d, "%s: cambió el OTRO archivo abierto (no el de trabajo): %s" % (que, d[:3])

    # --- pregunta 3 de las 7: cambiar una medida de algo anterior y recalcular ---
    def medida_base(self):
        """(objeto, propiedad) de una medida del principio de la pieza, o None."""
        return None

    def accion_medida_base(self, rng, que, f0):
        """Cambiar una medida de la base (el largo del cubo), recalcular sin errores de Python, y al
        volverla, todo exactamente como estaba."""
        mb = self.medida_base()
        if mb is None:
            return
        obj, prop = mb
        antes = getattr(obj, prop)
        malos0 = self.malos()
        # 0,9 a 1,3: achicar más puede hacer que el agujero (borde a 7 mm del borde de la caja de 40)
        # corte la cara y cambie la topología: las operaciones atadas a "Edge3"/"Face6" fallarían
        # por los nombres topológicos de FreeCAD, no por FreeWorks
        setattr(obj, prop, round(float(getattr(antes, "Value", antes)) * rng.uniform(0.9, 1.3), 1))
        try:
            self.doc.recompute()
            bombear(600)
            nuevos = self.malos() - malos0
            assert not nuevos, "%s: con el %s de %s cambiado quedaron con error: %s" % (que, prop, obj.Label, sorted(nuevos))
        finally:
            setattr(obj, prop, antes)
            self.doc.recompute()
            bombear(600)
        d = diferencias(f0, self.foto(), visibilidad=False)
        assert not d, "%s: cambiar el %s de %s y volverlo no dejó todo como estaba: %s" % (que, prop, obj.Label, d[:3])


def solo_lo_de_antes(f0, f1):
    """f1 recortado a los objetos que ya estaban en f0 (para acciones que agregan algo a propósito,
    como el desarrollo de la chapa): lo de antes no tiene que cambiar."""
    return {"objs": {n: v for n, v in f1["objs"].items() if n in f0["objs"]}, "undo": f0["undo"], "abierta": f1["abierta"]}


def diferencias(a, b, visibilidad=True):
    """visibilidad=False (después de Ctrl+Z / Ctrl+Y): no cuentan los cambios SOLO de visibilidad
    (error conocido #36; lo controla prueba_ventana_reglas_*). Si no, el mono se frenaría siempre ahí."""
    from reglas_paneles import diferencias as dif
    out = dif(a, b, con_undo=False)
    if not visibilidad:
        out = [d for d in out if " cambió (visible): " not in d]
    return out


ADDONS_AJENOS = ("\\sheetmetal\\", "/sheetmetal/")


def _errores_ajenos(desde):
    """Mensajes finales ("<class 'X'>: texto") de los errores del informe que vienen enteros de
    otro addon (ninguna línea del rastro pasa por FreeWorks)."""
    from reglas_paneles import _report_view
    rv = _report_view()
    if rv is None:
        return set()
    out = set()
    for bloque in rv.toPlainText()[desde:].split("Traceback (most recent call last):")[1:]:
        lineas = bloque.splitlines()
        rastro = [l for l in lineas if l.strip().startswith("File ")]
        if rastro and all(any(a in l.lower() for a in ADDONS_AJENOS) for l in rastro):
            for l in lineas:
                if l.strip().startswith("<class "):
                    out.add(l.strip().split(": ", 1)[-1])
                    break
    return {t for t in out if t}


def _sin_los_ya_rotos(m, errores, malos0, desde):
    """Saca del informe lo que repite un objeto que YA estaba con error antes del paso (un Redondeo
    que perdió su arista con razón vuelve a avisar en cada recálculo: no es un error nuevo; que no
    se arregle solo lo sigue viendo `malos`). Se sacan su renglón ("Redondeo4: ...") y el renglón
    gemelo de FreeCAD que termina igual ("<Exception> ...: Invalid edge link: ...")."""
    nombres = set()
    for n in malos0:
        if ":" in n:
            continue  # de otro documento
        o = m.doc.getObject(n)
        if o is not None and o.TypeId in _CONTENEDORES:
            continue  # con error por un hijo: sus avisos taparían los de otros
        nombres |= {n, o.Label} if o is not None else {n}
    if not nombres:
        return errores
    from reglas_paneles import _report_view
    rv = _report_view()
    todo = rv.toPlainText()[desde:].splitlines() if rv is not None else []
    colas = set()
    for l in todo:  # el renglón con el nombre no es de los que cuentan como error: todo el informe
        for x in nombres:
            mm = re.search(r"(?:^|\s)%s: (.+)$" % re.escape(x), l)
            if mm and mm.group(1).strip():
                colas.add(mm.group(1).strip())
    if not colas:
        return errores
    return [l for l in errores if not any(l.rstrip().endswith(c) for c in colas)]


_CONTENEDORES = ("PartDesign::Body", "App::Part", "Assembly::AssemblyObject", "App::Link")


def chequear_ventana(m, que, desde, malos0):
    """Después de cada paso: nada colgado, sin errores en el informe, sin objetos con error nuevos."""
    from reglas_paneles import limpiar_ventana, mensajes_nuevos
    restos = limpiar_ventana()
    assert not restos, "%s: quedó %s" % (que, restos)
    # "... not possible ...": aviso propio de FreeCAD cuando lo elegido al azar no sirve (radio que
    # no entra, arista de costura...); ahí lo que importa es que el panel no acepte y avise, y eso
    # ya se mide. Si el aviso viene de código de FreeWorks ("[swui..."), cuenta igual.
    errores = [l for l in mensajes_nuevos(desde) if not l.lstrip().startswith("Traceback")
               and not ("not possible" in l and "[swui" not in l)]
    # Errores de adentro de otro addon (SheetMetal) con lo elegido al azar (una brida sobre una
    # arista donde no entra): son de ese addon. Lo que mide el mono es que FreeWorks no deje una
    # operación con error (eso lo ve `malos`, que sigue contando).
    ajenos = _errores_ajenos(desde)
    if ajenos:
        errores = [l for l in errores if "pyException" not in l and not any(a in l for a in ajenos)]
    errores = _sin_los_ya_rotos(m, errores, malos0, desde)
    nuevos = m.malos() - malos0
    paso_ahora = que.split(" → ")[-1]
    for d in m.deuda:
        issue, texto, objeto = d[:3]
        accion = d[3] if len(d) > 3 else None  # solo en ese paso (y sin tapar errores de Python)
        if accion is not None and accion not in paso_ahora:
            continue
        textos = texto if isinstance(texto, tuple) else (texto,)
        if all(any(x in l for l in errores) for x in textos):
            traza("    (deuda %s en: %s)" % (issue, que))
            errores = [l for l in errores if not any(x in l for x in textos)
                       and (accion is not None or "pyException" not in l)]
            if objeto:
                nuevos = {n for n in nuevos if objeto not in n}
    if errores:  # el informe entero de este paso a la traza: de dónde viene el error
        from reglas_paneles import _report_view
        rv = _report_view()
        if rv is not None:
            traza("    informe del paso: " + rv.toPlainText()[desde:][-4000:])
    assert not errores, "%s: informe de FreeCAD: %s" % (que, errores[:3])
    assert not nuevos, "%s: quedaron con error: %s" % (que, sorted(nuevos))
    if hasattr(m, "otro_igual"):
        m.otro_igual(que)


def sin_lo_previo(caso, f, f0):
    """La foto sin lo que el caso arma ANTES del panel en su propio paso de deshacer (el croquis
    de un taladro de ensamblaje): Cancelar o Ctrl+Z del panel no lo sacan, y está bien."""
    previos = {n for n, _t in getattr(caso, "antes_del_panel", ())} - set(f0["objs"])
    if not previos:
        return f
    return {"objs": {n: v for n, v in f["objs"].items() if n not in previos}, "undo": f["undo"], "abierta": f["abierta"]}


def deshacer_y_rehacer(m, que, f0, f1, caso=None):
    from reglas_paneles import ctrl_y, ctrl_z
    ctrl_z(m.doc)
    m.doc.recompute()
    bombear(400)
    d = diferencias(f0, sin_lo_previo(caso, m.foto(), f0), visibilidad=False)
    assert not d, "%s: Ctrl+Z no volvió a como estaba: %s" % (que, d[:3])
    ctrl_y(m.doc)
    m.doc.recompute()
    bombear(400)
    d = diferencias(f1, m.foto(), visibilidad=False)
    assert not d, "%s: Ctrl+Y no lo trajo igual: %s" % (que, d[:3])


def paso(m, accion, semilla, historia):
    from reglas_paneles import ctrl_y, ctrl_z, informe_largo
    rng = random.Random(semilla)
    caso = m.casos[semilla % len(m.casos)] if m.casos else None
    nombre = caso.nombre if caso is not None and accion in ("aceptar", "cancelar", "ecuaciones", "material") else ""
    que = " → ".join(historia + [("%s %s" % (accion, nombre)).strip()])
    desde = informe_largo()
    malos0 = m.malos()
    f0 = m.foto()
    if accion in ("aceptar", "cancelar", "ecuaciones", "material") and caso is None:
        accion = "deshacer"
    if accion == "aceptar":
        abrir(caso, rng)
        correr(caso.elegir(rng))
        bombear(800)
        correr(caso.aceptar())
        bombear(800)
        if caso.ok:
            m.doc.recompute()
            f1 = m.foto()
            nuevos = [n for n in f1["objs"] if n not in f0["objs"] and ":" not in n
                      and m.doc.getObject(n) is not None and m.doc.getObject(n).TypeId in _tipos(caso)]
            if nuevos and getattr(caso, "cambiar", None) is not None:
                m.hechos.append((nuevos[-1], caso))
            deshacer_y_rehacer(m, que, f0, f1, caso)
            correr(caso.despues_de_aceptar())  # p. ej. salir del croquis
        else:
            correr(caso.cancelar())
            bombear(800)
            d = diferencias(f0, sin_lo_previo(caso, m.foto(), f0))
            assert not d, "%s: no aceptó y quedó algo: %s" % (que, d[:3])
    elif accion == "cancelar":
        abrir(caso, rng)
        correr(caso.elegir(rng))
        bombear(800)
        correr(caso.cancelar())
        bombear(800)
        d = diferencias(f0, sin_lo_previo(caso, m.foto(), f0))
        assert not d, "%s: Cancelar dejó algo: %s" % (que, d[:3])
    elif accion == "editar":
        vivos = [(n, c) for n, c in m.hechos if m.doc.getObject(n) is not None
                 and not getattr(m.doc.getObject(n), "Suppressed", False)]
        if vivos:
            n, c = vivos[semilla % len(vivos)]
            gen = c.cambiar(rng)
            if gen is not None:
                que = " → ".join(historia + ["editar %s (%s)" % (c.nombre, n)])
                correr(c.editar(m.doc.getObject(n)))
                correr(gen)
                bombear(800)
                correr(c.aceptar())
                bombear(800)
                if c.ok:
                    m.doc.recompute()
                    deshacer_y_rehacer(m, que, f0, m.foto())
                else:
                    correr(c.cancelar())
                    bombear(800)
                    d = diferencias(f0, m.foto())
                    assert not d, "%s: no aceptó el cambio y quedó algo: %s" % (que, d[:3])
    elif accion in ("ecuaciones", "material"):
        abrir(caso, rng)
        correr(caso.elegir(rng))
        bombear(800)
        if accion == "ecuaciones":
            from swui.fork import equations
            dlg = equations.show_dialog(m.doc)
        else:
            from swui.fork import material
            dlg = material.show_dialog(m.doc)
        bombear(800)
        dlg.reject()
        bombear(500)
        correr(caso.cancelar())
        bombear(800)
        d = diferencias(f0, sin_lo_previo(caso, m.foto(), f0))
        assert not d, "%s: con %s abierto, el Cancelar del panel no deshizo: %s" % (que, accion, d[:3])
    elif accion == "suprimir":
        import FreeCADGui
        from swui.fork import feature_tree as ft
        body = m.cuerpo()
        feats = [o for o in ft.features(body) if not getattr(o, "Suppressed", False)] if body is not None else []
        if len(feats) > 1:
            obj = feats[1 + semilla % (len(feats) - 1)]  # no la primera (la base)
            que = " → ".join(historia + ["suprimir %s" % obj.Label])
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(obj)
            FreeCADGui.runCommand("SWUI_Suppress")
            bombear(600)
            FreeCADGui.Selection.clearSelection()
            assert obj.Suppressed, "%s: %s no quedó suprimida" % (que, obj.Label)
            ctrl_z(m.doc)
            m.doc.recompute()
            bombear(400)
            d = diferencias(f0, m.foto(), visibilidad=False)
            assert not d, "%s: Ctrl+Z después de suprimir no volvió: %s" % (que, d[:3])
    elif accion == "deshacer":
        ctrl_z(m.doc)
        m.doc.recompute()
        bombear(400)
    elif accion == "rehacer":
        ctrl_y(m.doc)
        m.doc.recompute()
        bombear(400)
    elif accion == "guardar":
        import FreeCADGui
        m.guardar_y_abrir()
        d = diferencias(f0, m.foto())
        assert not d, "%s: guardar y abrir cambió: %s" % (que, d[:3])
        assert not getattr(FreeCADGui.getDocument(m.doc.Name), "Modified", False), "%s: al abrir quedó modificado" % que
        malos0 = m.malos()
    else:  # acción propia del entorno
        getattr(m, "accion_" + accion)(rng, que, f0)
    chequear_ventana(m, que, desde, malos0)
    historia.append(("%s %s" % (accion, nombre)).strip())


def regla_mono(entorno, acciones):
    given, cfg, st = hypothesis_listo()

    @cfg
    @given(pasos=st.lists(st.tuples(st.sampled_from(acciones), st.integers(0, 10 ** 6)), min_size=3, max_size=LARGO))
    def regla(pasos):
        m = entorno()
        historia = []
        traza("  seguidilla: %s" % [a for a, _s in pasos])
        for accion, semilla in pasos:
            try:
                paso(m, accion, semilla, historia)
            except NadaQueElegir:
                traza("    (%s: no queda dónde; se saltea)" % accion)
            except AssertionError as e:
                texto = str(e)
                ultimo = texto.split(": ", 1)[0].split(" → ")[-1]
                antes = texto.split(": ", 1)[0].split(" → ")[:-1]
                cual = [d[0] for d in m.deuda_pasos if d[1] in texto and d[2] in ultimo
                        and (len(d) < 4 or any(d[3] in h for h in antes))]
                if not cual:
                    raise
                traza("    (deuda %s en: %s)" % (cual[0], texto.split(": ", 1)[0]))
                from reglas_paneles import limpiar_ventana
                limpiar_ventana()
                historia.append(ultimo)
        comprobado()
    # memoria de Hypothesis propia de cada entorno y lista de acciones (el código de la regla es el
    # mismo para todos: sin esto, la seguidilla que falló en un entorno se repite en los otros)
    try:
        clave = "%s|%s|%s" % (entorno.__name__, ",".join(acciones), LARGO)
        regla.hypothesis.inner_test._hypothesis_internal_add_digest = clave.encode("utf-8")
    except Exception:
        pass
    return regla


def correr_reglas(entorno, conocido_otra="", extra=()):
    """Las dos reglas del mono para un entorno: la seguidilla común (+ las acciones propias) y la de
    otra herramienta abierta con el panel abierto (era el #3, arreglado el 11/11)."""
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "").lower()
    reglas = [("mono", BASE + list(entorno.acciones) + list(extra), ""),
              ("mono con otra herramienta abierta", OTRA_HERRAMIENTA, conocido_otra)]
    for nombre, acciones, conocido in reglas:
        if not solo or solo in nombre:
            fallas.correr(nombre, regla_mono(entorno, acciones), conocido)
    fallas.terminar()
