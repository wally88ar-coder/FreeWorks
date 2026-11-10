# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Reglas comunes de los paneles (plan de calidad, paso 8.1): lo que TODO panel de FreeWorks tiene
que cumplir, con elecciones y valores al azar. Las usan las pruebas `prueba_ventana_reglas_*.py`.

Cada panel se describe con un "caso" (subclase de `Caso`) que sabe armar una pieza, abrir el
panel, elegir algo válido al azar, meter algo inválido y apretar Aceptar / Cancelar. Las reglas
son generadores (`yield ms` = esperar con la ventana viva) y anotan cada incumplimiento en
`Informe` en vez de cortar: así una corrida muestra todo lo que está mal.

Reglas:
  cancelar      abrir, elegir, Cancelar: el documento queda idéntico (objetos, volúmenes,
                visibilidad, pasos de deshacer) y no queda ningún panel ni diálogo abierto.
  invalido      abrir, meter algo inválido, Aceptar: no acepta (o avisa) y no queda nada a
                medio hacer después de Cancelar.
  otro_comando  abrir, elegir, otro comando de la cinta: el panel se cancela de verdad.
  aceptar       abrir, elegir, Aceptar: una operación nueva del tipo esperado, válida, y un solo
                paso de deshacer; Deshacer vuelve al estado anterior y Rehacer la trae igual.
                Si los valores al azar no sirven (p. ej. un redondeo demasiado grande), el panel
                tiene que no aceptar y avisar; eso no es falla.
  editar        abrir la operación aceptada y Aceptar sin tocar nada: la pieza no cambia.
  guardar       guardar, cerrar y abrir: misma pieza y el archivo no queda "modificado".
En todas: sin errores de Python ni avisos de error en el informe de FreeCAD.
"""

import os
import re
import random

import FreeCAD

from _base import carpeta_temporal, traza

ESPERA_PANEL = 1800   # ms para que un panel se abra y haga su vista previa
ESPERA_CORTA = 700


# --- Lo que se compara ----------------------------------------------------------------------


def _r(v):
    return round(float(v), 2)


def _vol(o):
    try:
        s = o.Shape
        if s.isNull() or not s.Solids:
            return None
        # al mm³: barridos y hélices dan centésimas distintas en cada recálculo
        return round(float(s.Volume))
    except Exception:
        return None


def _caja(o):
    """Dónde está (también vínculos, planos y ejes). Con sólido, su centro de masa (exacto y
    estable); sin sólido, la caja envolvente redondeada a 0,1 mm. La caja de un sólido no sirve:
    varía unas centésimas (y en superficies curvas hasta 0,1 mm) entre recálculos y al reabrir."""
    try:
        import Part
        s = Part.getShape(o)
        if s.isNull():
            return None
        if s.Solids:  # promedio por volumen (un compuesto no tiene CenterOfMass propio)
            vol = sum(x.Volume for x in s.Solids) or 1.0
            c = FreeCAD.Vector()
            for x in s.Solids:
                c = c + x.CenterOfMass * (x.Volume / vol)
            return ("cdm",) + tuple(_r(v) for v in (c.x, c.y, c.z))
        b = s.BoundBox
        return tuple(round(float(x), 1) for x in (b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax))
    except Exception:
        return None


def _ubicacion(o):
    try:
        p = o.Placement
        q = p.Rotation.Q
        # q y -q son el mismo giro (FreeCAD da uno u otro según cómo se llegó, p. ej. al rehacer):
        # se escribe siempre el que tiene la primera componente no nula positiva
        primera = next((x for x in (q[3], q[0], q[1], q[2]) if abs(x) > 5e-3), 1.0)  # (lo que el redondeo no borra)
        if primera < 0:
            q = tuple(-x for x in q)
        return tuple(_r(x) for x in (p.Base.x, p.Base.y, p.Base.z)) + tuple(_r(x) + 0.0 for x in q)
    except Exception:
        return None


def _valor(v):
    """Un valor de propiedad comparable: los vínculos por el nombre del objeto apuntado."""
    if hasattr(v, "Name") and hasattr(v, "TypeId"):
        return "->" + v.Name
    if isinstance(v, (list, tuple)):
        return tuple(_valor(x) for x in v)
    return str(v)


def _firma(sk):
    """Resumen de qué hay en el croquis y dónde (puntas, centros, puntos; constructivas aparte)."""
    out = []
    for i, g in enumerate(sk.Geometry):
        pts = []
        for nombre in ("StartPoint", "EndPoint", "Center"):
            p = getattr(g, nombre, None)
            if p is not None:
                pts.append(p)
        if not pts and hasattr(g, "X"):  # Part.Point
            pts.append(FreeCAD.Vector(g.X, g.Y, g.Z))
        try:
            constr = bool(sk.getConstruction(i))
        except Exception:
            constr = None
        out.append((type(g).__name__, constr, tuple(_r(c) for p in pts for c in (p.x, p.y)),
                    _r(getattr(g, "Radius", 0))))
    return hash(tuple(out))


def sin_freeworks(ruta):
    """Módulos de FreeWorks que el archivo guarda como objetos de Python ([] = abre sin FreeWorks):
    los objetos van en Document.xml y su aspecto (proveedores de vista) en GuiDocument.xml."""
    import zipfile
    try:
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("Document.xml").decode("utf-8", "replace")
            if "GuiDocument.xml" in z.namelist():
                xml += z.read("GuiDocument.xml").decode("utf-8", "replace")
    except Exception as exc:
        return ["(no se pudo leer el archivo guardado: %s)" % exc]
    return sorted(set(re.findall(r'module="(swui[^"]*)"', xml)))


def foto_varios(doc, otros):
    """foto(doc) más los objetos de otros documentos (las piezas de un ensamblaje), con el nombre
    del documento adelante. Los pasos de deshacer son los del documento principal; "abierta" si
    cualquiera tiene una transacción abierta."""
    f = foto(doc)
    for o in otros:
        if o is None or o is doc:
            continue
        try:
            g = foto(o)
        except Exception:
            continue
        for n, v in g["objs"].items():  # por Label: al reabrir, el nombre interno puede cambiar
            f["objs"]["%s:%s" % (o.Label, n)] = v
        f["abierta"] = f["abierta"] or g["abierta"]
    return f


def foto(doc):
    """Estado comparable del documento: por objeto, tipo, medida (volumen y caja; en un croquis,
    lo dibujado), ubicación, visibilidad y marcas SWUI_; y los pasos de deshacer."""
    objs = {}
    en_edicion = None
    try:
        import FreeCADGui
        vp = FreeCADGui.getDocument(doc.Name).getInEdit()
        en_edicion = vp.Object.Name if vp is not None else None
    except Exception:
        pass
    for o in doc.Objects:
        vis = None
        try:
            vis = bool(o.Visibility)
        except Exception:
            pass
        medida = (_vol(o), _caja(o))
        if o.TypeId == "Sketcher::SketchObject":
            medida = (o.GeometryCount, o.ConstraintCount, _firma(o))
            if o.Name == en_edicion:
                vis = None  # mientras se edita, FreeCAD le cambia la visibilidad
        try:  # las marcas propias de FreeWorks (SWUI_...): chapa, alcance, configuraciones...
            marcas = hash(tuple(sorted((p, _valor(getattr(o, p))) for p in o.PropertiesList
                                       if p.startswith("SWUI_"))))
        except Exception:
            marcas = None
        extra = None
        if o.TypeId == "Spreadsheet::Sheet":  # la tabla de configuraciones: su contenido
            try:
                extra = hash(tuple((c, str(o.get(c))) for c in sorted(o.getNonEmptyCells())))
            except Exception:
                pass
        objs[o.Name] = (o.TypeId, medida, _ubicacion(o), vis, marcas, extra)
    return {"objs": objs, "undo": doc.UndoCount, "abierta": bool(doc.HasPendingTransaction)}


def diferencias(a, b, con_undo=True):
    out = []
    for n in sorted(set(a["objs"]) | set(b["objs"])):
        if n not in b["objs"]:
            out.append("falta %s" % n)
        elif n not in a["objs"]:
            out.append("sobra %s (%s)" % (n, b["objs"][n][0]))
        else:
            # visible None = no se sabe (croquis en edición): no se compara
            que = [k for k, x, y in zip(("tipo", "medida", "ubicación", "visible", "marcas", "contenido"),
                                        a["objs"][n], b["objs"][n])
                   if x != y and not (k == "visible" and (x is None or y is None))]
            if que:
                out.append("%s cambió (%s): %s -> %s" % (n, ", ".join(que), a["objs"][n], b["objs"][n]))
    if con_undo and a["undo"] != b["undo"]:
        out.append("pasos de deshacer: %d -> %d" % (a["undo"], b["undo"]))
    if b.get("abierta") and not a.get("abierta"):
        out.append("quedó una transacción abierta (lo próximo que haga el usuario se suma a ese paso)")
    return out


def invalidos(doc):
    """Objetos con error (y croquis con relaciones en conflicto o redundantes)."""
    out = set()
    for o in doc.Objects:
        try:
            if "Invalid" in str(o.State) or (hasattr(o, "isValid") and not o.isValid()):
                out.add(o.Name)
            if o.TypeId == "Sketcher::SketchObject" and (list(o.ConflictingConstraints)
                                                         or list(o.RedundantConstraints)):
                out.add(o.Name + " (relaciones en conflicto/redundantes)")
        except Exception:
            pass
    return out


# --- Informe ---------------------------------------------------------------------------------


class Informe:
    def __init__(self, deuda=None):
        self.fallas = []          # (caso, regla, detalle)
        self.notas = []
        # (caso, regla) -> "#N" o ("#N", "pedazo del texto que da ese error"): con texto, la
        # deuda tapa solo las fallas que lo contienen (otra falla en la misma regla sí se ve)
        self.deuda = deuda or {}

    def falla(self, caso, regla, detalle):
        traza("FALLA %s/%s: %s" % (caso, regla, detalle))
        self.fallas.append((caso, regla, detalle))

    def nota(self, texto):
        traza(texto)
        self.notas.append(texto)

    def _cubre(self, f):
        d = self.deuda.get((f[0], f[1]))
        if d is None:
            return False
        if isinstance(d, tuple):
            return any(t in f[2] for t in d[1:])
        return True

    def _a_veces(self, k):
        """Deuda que no aparece en todas las corridas ("~#N"): que no esté no es "ya no falla"."""
        d = self.deuda.get(k)
        return str(d[0] if isinstance(d, tuple) else d).startswith("~")

    def resumen(self):
        nuevas = [f for f in self.fallas if not self._cubre(f)]
        viejas = [f for f in self.fallas if self._cubre(f)]
        arregladas = sorted(k for k in self.deuda if not self._a_veces(k)
                            and not any(self._cubre(f) for f in self.fallas if (f[0], f[1]) == k))
        return nuevas, viejas, arregladas


# --- Ventana ---------------------------------------------------------------------------------


def _report_view():
    import FreeCADGui
    from PySide import QtWidgets
    return FreeCADGui.getMainWindow().findChild(QtWidgets.QTextEdit, "Report view")


def informe_largo():
    rv = _report_view()
    return len(rv.toPlainText()) if rv is not None else 0


MALAS = ("Traceback", "Exception", "Error", "error:", "failed", "Failed", "not possible",
         "<class ")


def mensajes_nuevos(desde):
    rv = _report_view()
    if rv is None:
        return []
    texto = rv.toPlainText()[desde:]
    out, donde = [], ""
    for l in texto.splitlines():
        if "File \"" in l and "swui" in l:  # de qué parte de FreeWorks viene el error
            donde = l.strip().split("swui", 1)[1][:90]
        elif any(m in l for m in MALAS):
            out.append(l + ("   [swui%s]" % donde if donde and not l.lstrip().startswith(("Traceback", "raise")) else ""))
            donde = ""
    return out


def limpiar_ventana(edicion_ok=""):
    """Cierra diálogos y paneles que hayan quedado (después de anotarlos). `edicion_ok`: tipo de
    objeto que puede quedar en edición a propósito (el croquis, para las herramientas del croquis)."""
    import FreeCADGui
    from PySide import QtWidgets
    restos = []
    d = QtWidgets.QApplication.activeModalWidget()
    if d is not None:
        restos.append("diálogo abierto: %s %r" % (d.objectName(), d.windowTitle()))
        d.reject()
    vp0 = FreeCADGui.ActiveDocument.getInEdit() if FreeCADGui.ActiveDocument is not None else None
    try:  # un panel de herramienta del croquis que quedó abierto
        from swui.fork import sketch_entities
        if sketch_entities.active_panel() is not None:
            restos.append("panel de herramienta del croquis abierto")
            sketch_entities.active_panel().reject()
    except Exception:
        pass
    if edicion_ok and vp0 is not None and getattr(vp0.Object, "TypeId", "") == edicion_ok:
        FreeCADGui.Selection.clearSelection()
        return restos
    if FreeCADGui.Control.activeDialog():
        restos.append("panel abierto")
        try:
            tocar(rechazar=True)
            if FreeCADGui.Control.activeDialog():
                FreeCADGui.Control.closeDialog()
        except Exception:
            pass
    try:
        gdoc = FreeCADGui.ActiveDocument
        vp = gdoc.getInEdit() if gdoc is not None else None
        # un ensamblaje activo está "en edición" a propósito (así se mueven sus piezas)
        if vp is not None and getattr(vp.Object, "TypeId", "") != "Assembly::AssemblyObject":
            restos.append("algo en edición")
            gdoc.resetEdit()
    except Exception:
        pass
    FreeCADGui.Selection.clearSelection()
    return restos


def esperar_panel(maximo_ms=15000):
    """Generador: espera a que haya un panel abierto (los del fork se abren con QTimer)."""
    import FreeCADGui
    from swui.fork import panel_guard
    hecho = 0
    while hecho < maximo_ms:
        yield 250
        hecho += 250
        if panel_guard.open_panel() is not None or FreeCADGui.Control.activeDialog():
            yield 600  # que termine de armarse y haga la primera vista previa
            return


def ctrl_z(doc):
    """Deshacer como el usuario (Edición > Deshacer, Std_Undo, sobre el documento activo): puede
    deshacer también en otros documentos de la misma transacción, cosa que doc.undo() no hace."""
    import FreeCADGui
    FreeCAD.setActiveDocument(doc.Name)
    FreeCADGui.runCommand("Std_Undo")


def ctrl_y(doc):
    """Rehacer como el usuario (Std_Redo)."""
    import FreeCADGui
    FreeCAD.setActiveDocument(doc.Name)
    FreeCADGui.runCommand("Std_Redo")


def tocar(rechazar=False):
    """Clic en el botón Aceptar o Cancelar del panel de Tareas (como el usuario: FreeCAD llama a
    accept/reject y cierra el panel si corresponde). True si encontró el botón."""
    import FreeCADGui
    from PySide import QtWidgets
    caja = QtWidgets.QDialogButtonBox
    rol = caja.ButtonRole.RejectRole if rechazar else caja.ButtonRole.AcceptRole
    for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QWidget):
        if w.metaObject().className() != "Gui::TaskView::TaskView" or not w.isVisible():
            continue
        for box in w.findChildren(caja):
            if not box.isVisible():
                continue
            for b in box.buttons():
                if box.buttonRole(b) == rol and b.isEnabled():
                    # fuera del generador: si Aceptar abre un aviso modal (exec), el generador
                    # no puede quedar trabado adentro del clic
                    from PySide import QtCore
                    QtCore.QTimer.singleShot(0, b.click)
                    return True
    return False


# --- Caso: un panel --------------------------------------------------------------------------


class Caso:
    """Cómo manejar un panel. Las subclases completan lo marcado."""

    nombre = ""
    tipo = ""            # TypeId de la operación que crea (None: no crea, cambia algo que existe)
    ayudantes = ()       # TypeId de objetos auxiliares que también puede crear al aceptar
    otro = "PartDesign_Chamfer"  # comando de la cinta para la regla otro_comando
    cuantos = 1          # cuántas del tipo crea al aceptar (None: una o más, p. ej. miembros)
    # False en el croquis: entrar y salir de la edición ya deja pasos de deshacer (FreeCAD); ahí
    # Deshacer/Rehacer se prueban adentro del croquis, como Ctrl+Z del usuario
    contar_deshacer = True
    edicion_ok = ""      # tipo que puede seguir en edición después de Aceptar (el croquis)
    cambio_visible = True  # False si lo que cambia `cambiar` no se ve en la pieza (p. ej. factor K)
    # (nombre, tipo) que `abrir` crea ANTES del panel en su propio paso de deshacer (el croquis de un
    # taladro de ensamblaje): un Ctrl+Z después de Aceptar no los saca, y está bien
    antes_del_panel = ()
    reglas = ("cancelar", "invalido", "otro_comando", "aceptar", "editar", "guardar")

    def preparar(self, doc):
        """Arma la pieza; deja activo el Cuerpo. Guarda lo que necesite en self."""
        raise NotImplementedError

    def abrir(self, rng):
        """Abre el panel (con la selección que haga falta). Generador."""
        raise NotImplementedError

    def elegir(self, rng):
        """Con el panel abierto: elecciones y valores válidos al azar. Generador."""
        return iter(())

    def invalido(self):
        """Con el panel abierto: algo inválido. Generador. Sin nada, la regla se saltea."""
        return None

    def panel(self):
        from swui.fork import panel_guard
        return panel_guard.open_panel()

    def aceptar(self):
        """Toca Aceptar del panel, como el usuario. Generador; deja self.ok."""
        import FreeCADGui
        self.ok = tocar(rechazar=False)
        espera = 0
        while True:  # hasta 3 s para que el panel se cierre (algunos tardan en recalcular)
            yield 300
            espera += 300
            if not FreeCADGui.Control.activeDialog() or espera >= 3000:
                break
        self.ok = self.ok and not FreeCADGui.Control.activeDialog()
        self.aviso = self.mensaje()  # una vez: un aviso en ventanita se lee y se cierra

    def cancelar(self):
        """Toca Cancelar del panel. Generador."""
        tocar(rechazar=True)
        yield ESPERA_CORTA

    def mensaje(self):
        """Texto del aviso del panel (para ver que avisa en castellano), o ''. Un aviso en una
        ventanita aparte (QMessageBox) también cuenta: se lee y se cierra."""
        from PySide import QtWidgets
        d = QtWidgets.QApplication.activeModalWidget()
        if isinstance(d, QtWidgets.QMessageBox):
            texto = d.text()
            d.accept()
            return texto
        p = self.panel()
        try:
            m = p.message
            return m.text() if m.isVisible() else ""
        except Exception:
            return ""

    def documentos(self, doc):
        """Otros documentos que el panel cambia (las piezas de un ensamblaje): entran en la foto."""
        return []

    def verificar_cambio(self, obj):
        """Con cambio_visible=False: '' si el cambio de `cambiar` quedó aplicado en `obj`, o el
        problema."""
        return ""

    def comprobar_aceptado(self, doc):
        """Comprobaciones propias del caso después de Aceptar (lista de problemas)."""
        return []

    def cerrar(self):
        """Al terminar el caso: cerrar lo que el caso abrió (p. ej. las piezas de un ensamblaje)."""

    def cambiar(self, rng):
        """Con el panel de EDICIÓN abierto: cambiar un valor (otro radio, otra cantidad...).
        Generador. Sin esto (None), las reglas editar_cancelar y editar_cambiar se saltean."""
        return None

    def despues_de_aceptar(self):
        """Generador: lo que hace falta al terminar cada vuelta de aceptar (p. ej. salir del croquis)."""
        return iter(())

    def editar(self, obj):
        """Abre el panel sobre una operación ya hecha (como doble clic en el árbol). Generador."""
        import FreeCADGui
        FreeCADGui.ActiveDocument.setEdit(obj)
        yield ESPERA_PANEL


# --- Reglas ----------------------------------------------------------------------------------


def _nuevos(antes, despues):
    return [n for n in despues["objs"] if n not in antes["objs"]]


def correr_caso(caso, inf, semillas=(1,)):
    """Generador: todas las reglas del caso, una semilla por vuelta de aceptar/cancelar."""
    import FreeCADGui
    doc = FreeCAD.newDocument("Reglas_" + caso.nombre.replace(" ", "_"))
    doc.UndoMode = 1

    def fotodoc():
        return foto_varios(doc, caso.documentos(doc))
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    desde_preparar = informe_largo()
    armado = caso.preparar(doc)
    if hasattr(armado, "send"):  # un caso puede armar su pieza con otro panel (chapa)
        yield from armado
    doc.recompute()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    yield ESPERA_CORTA
    base = fotodoc()

    def invalidos_todos():
        out = set(invalidos(doc))
        for o in caso.documentos(doc):
            try:
                out |= {"%s:%s" % (o.Label, n) for n in invalidos(o)}
            except Exception:
                pass
        return out


    def medir(regla, base):
        """Compara con `base`, anota las diferencias y devuelve el estado nuevo: lo que quedó
        mal ya se anotó y las reglas siguientes miden desde acá."""
        ahora = fotodoc()
        for d in diferencias(base, ahora, con_undo=caso.contar_deshacer):
            inf.falla(caso.nombre, regla, d)
        return ahora

    def chequear_ventana(regla, desde):
        for r in limpiar_ventana(caso.edicion_ok if regla == "aceptar" else ""):
            inf.falla(caso.nombre, regla, "quedó " + r)
        vistos = []
        for l in mensajes_nuevos(desde):
            l = re.sub(r"^\d\d:\d\d:\d\d\s+", "", l.strip())[:200]  # sin la hora: una vez cada uno
            if l not in vistos and not l.startswith("Traceback"):
                vistos.append(l)
        for l in vistos[:6]:
            inf.falla(caso.nombre, regla, "informe de FreeCAD: " + l)

    malos0 = invalidos_todos()
    for n in sorted(malos0):  # la pieza de prueba tiene que arrancar sana
        inf.falla(caso.nombre, "preparar", "la pieza de prueba quedó con error: %s" % n)
    chequear_ventana("preparar", desde_preparar)

    for semilla in semillas:
        rng = random.Random(semilla)
        if "cancelar" in caso.reglas:
            desde = informe_largo()
            yield from caso.abrir(rng)
            if caso.panel() is None and not FreeCADGui.Control.activeDialog():
                inf.falla(caso.nombre, "cancelar", "no se abrió el panel")
            yield from caso.elegir(rng)
            yield ESPERA_PANEL
            yield from caso.cancelar()
            chequear_ventana("cancelar", desde)
            base = medir("cancelar", base)

    if "invalido" in caso.reglas:
        desde = informe_largo()
        yield from caso.abrir(random.Random(0))
        gen = caso.invalido()
        if gen is not None:
            yield from gen
            yield ESPERA_PANEL
            yield from caso.aceptar()
            traza("  %s inválido: %s, aviso %r" % (caso.nombre, "aceptó" if caso.ok else "no aceptó",
                                                   caso.aviso))
            if caso.ok:
                inf.falla(caso.nombre, "invalido", "aceptó algo inválido")
            elif not caso.aviso:
                inf.falla(caso.nombre, "invalido", "no aceptó pero no dijo por qué")
            elif caso.aviso.startswith("No se pudo"):
                inf.falla(caso.nombre, "invalido", "el aviso es un error de Python: %r" % caso.aviso)
        yield from caso.cancelar()
        chequear_ventana("invalido", desde)
        base = medir("invalido", base)

    if "otro_comando" in caso.reglas:
        desde = informe_largo()
        yield from caso.abrir(random.Random(1))
        yield from caso.elegir(random.Random(1))
        yield ESPERA_PANEL
        primero = caso.panel()
        abierto = fotodoc()
        FreeCADGui.Selection.clearSelection()
        from swui import ribbon
        # fuera del generador: si FreeCAD pregunta "Un diálogo ya está abierto" (ventanita modal),
        # la prueba sigue y la anota en vez de quedar trabada adentro
        from PySide import QtCore
        QtCore.QTimer.singleShot(0, lambda: ribbon._run(caso.otro))
        yield ESPERA_PANEL
        yield ESPERA_CORTA
        # ANTES de cancelar el panel nuevo (su Cancelar podría borrar lo que dejó el primero):
        # lo que agregó el primer panel ya no tiene que estar, y lo de antes, igual que antes
        ahora = fotodoc()
        for n in abierto["objs"]:
            if n not in base["objs"] and n in ahora["objs"]:
                inf.falla(caso.nombre, "otro_comando", "el primer panel no se canceló: sigue %s (%s)"
                          % (n, ahora["objs"][n][0]))
        solo_base = {"objs": {n: v for n, v in ahora["objs"].items() if n in base["objs"]},
                     "undo": base["undo"], "abierta": False}
        for d in diferencias(base, solo_base, con_undo=False):
            inf.falla(caso.nombre, "otro_comando", d)
        if primero is not None and caso.panel() is primero:
            inf.falla(caso.nombre, "otro_comando", "el primer panel siguió abierto")
        tocar(rechazar=True)
        yield ESPERA_CORTA
        chequear_ventana("otro_comando", desde)
        ahora = fotodoc()
        problemas = diferencias(base, ahora, con_undo=caso.contar_deshacer)
        for d in problemas:
            inf.falla(caso.nombre, "otro_comando", d)
        if problemas:
            # volver a como estaba, para que lo que dejó mal no arrastre a las reglas siguientes
            # (ya quedó anotado): anular lo abierto, deshacer lo de más y borrar lo que sobre
            try:
                if doc.HasPendingTransaction:
                    doc.abortTransaction()
                while doc.UndoCount > base["undo"]:
                    doc.undo()
                for n in [n for n in fotodoc()["objs"] if n not in base["objs"]]:
                    if doc.getObject(n) is not None:
                        doc.removeObject(n)
                doc.recompute()
            except Exception:
                pass
            yield ESPERA_CORTA
            limpiar_ventana()
            restos = diferencias(base, fotodoc(), con_undo=False)
            if restos:
                inf.nota("%s: después de otro_comando no se pudo volver atrás: %s" % (caso.nombre, restos[:3]))
                base = fotodoc()

    hecho = None
    if "aceptar" in caso.reglas:
        alguna = False
        for semilla in semillas:
            ultima = semilla == semillas[-1]
            rng = random.Random(semilla)
            desde = informe_largo()
            yield from caso.abrir(rng)
            yield from caso.elegir(rng)
            yield ESPERA_PANEL
            yield from caso.aceptar()
            yield ESPERA_PANEL
            if not caso.ok:
                if not caso.aviso:
                    inf.falla(caso.nombre, "aceptar", "semilla %d: no aceptó y no dijo por qué" % semilla)
                elif caso.aviso.startswith("No se pudo"):
                    inf.falla(caso.nombre, "aceptar", "semilla %d: error al aceptar: %r" % (semilla, caso.aviso))
                else:
                    inf.nota("%s: semilla %d no aceptó: %s" % (caso.nombre, semilla, caso.aviso))
                yield from caso.cancelar()
                chequear_ventana("aceptar", desde)
                base = medir("aceptar", base)
                if ultima and alguna:
                    inf.falla(caso.nombre, "aceptar", "la última vuelta no aceptó: editar y guardar quedaron sin probar")
                continue
            alguna = True
            chequear_ventana("aceptar", desde)
            despues = fotodoc()
            nuevos = _nuevos(base, despues)
            tipos = [despues["objs"][n][0] for n in nuevos]
            traza("  %s semilla %d: aceptó, nuevos %s" % (caso.nombre, semilla, tipos))
            validos = caso.tipo if isinstance(caso.tipo, tuple) else (caso.tipo,)
            cuantas = sum(1 for t in tipos if t in validos)
            hecho_aca = None
            if caso.tipo is None:  # herramienta que cambia algo que ya existe (p. ej. un croquis)
                validos = ()
                if not diferencias(base, despues, con_undo=False):
                    inf.falla(caso.nombre, "aceptar", "semilla %d: aceptó pero no cambió nada" % semilla)
                else:
                    hecho_aca = True
            elif (caso.cuantos is not None and cuantas != caso.cuantos) or cuantas == 0:
                inf.falla(caso.nombre, "aceptar", "semilla %d: esperaba una %s nueva, hay %s" % (semilla, caso.tipo, tipos))
            raros = [t for t in tipos if t not in validos and t not in caso.ayudantes]
            if raros:
                inf.falla(caso.nombre, "aceptar", "semilla %d: objetos de más: %s" % (semilla, raros))
            if caso.contar_deshacer and despues["undo"] != base["undo"] + 1:
                inf.falla(caso.nombre, "aceptar", "semilla %d: pasos de deshacer %d -> %d (se espera uno)"
                          % (semilla, base["undo"], despues["undo"]))
            if despues["abierta"]:
                inf.falla(caso.nombre, "aceptar", "semilla %d: quedó una transacción abierta" % semilla)
            for n in nuevos:
                if despues["objs"][n][0] in validos:
                    hecho_aca = n
            for problema in caso.comprobar_aceptado(doc):
                inf.falla(caso.nombre, "aceptar", "semilla %d: %s" % (semilla, problema))
            for n in sorted(invalidos_todos() - malos0):
                inf.falla(caso.nombre, "aceptar", "semilla %d: quedó con error: %s" % (semilla, n))
            ctrl_z(doc)
            doc.recompute()
            yield ESPERA_CORTA
            for d in diferencias(base, fotodoc(), con_undo=False):
                if not any(d == "sobra %s (%s)" % (n, t) for n, t in caso.antes_del_panel):
                    inf.falla(caso.nombre, "aceptar", "semilla %d, después de Deshacer: %s" % (semilla, d))
            ctrl_y(doc)
            doc.recompute()
            yield ESPERA_CORTA
            for d in diferencias(despues, fotodoc(), con_undo=False):
                inf.falla(caso.nombre, "aceptar", "semilla %d, después de Rehacer: %s" % (semilla, d))
            for n in sorted(invalidos_todos() - malos0):
                inf.falla(caso.nombre, "aceptar", "semilla %d, después de Rehacer quedó con error: %s" % (semilla, n))
            if not ultima:
                ctrl_z(doc)
                doc.recompute()
                yield ESPERA_CORTA
            else:
                hecho = hecho_aca
            yield from caso.despues_de_aceptar()
            chequear_ventana("aceptar", desde)  # errores de Deshacer / Rehacer / al salir
        if not alguna:
            inf.falla(caso.nombre, "aceptar", "ninguna semilla dio una operación aceptada")

    if hecho is None and getattr(caso, "hecho_inicial", None):
        hecho = caso.hecho_inicial  # paneles que solo existen al editar (p. ej. Corte desdoblado)
    obj = doc.getObject(hecho) if isinstance(hecho, str) else None
    if obj is not None and "editar" in caso.reglas and caso.cambiar(random.Random(5)) is not None:
        # editar, cambiar un valor y Cancelar: queda como antes de editar
        desde = informe_largo()
        antes = fotodoc()
        yield from caso.editar(obj)
        yield from caso.cambiar(random.Random(5))
        yield ESPERA_PANEL
        yield from caso.cancelar()
        chequear_ventana("editar_cancelar", desde)
        for d in diferencias(antes, fotodoc(), con_undo=caso.contar_deshacer):
            inf.falla(caso.nombre, "editar_cancelar", d)
        # editar, cambiar un valor y Aceptar: cambia, un paso de deshacer, Deshacer y Rehacer exactos
        obj = doc.getObject(hecho)
        if obj is not None:
            desde = informe_largo()
            antes = fotodoc()
            yield from caso.editar(obj)
            yield from caso.cambiar(random.Random(6))
            yield ESPERA_PANEL
            yield from caso.aceptar()
            yield ESPERA_PANEL
            if not caso.ok:
                inf.falla(caso.nombre, "editar_cambiar", "no aceptó el cambio: %r" % caso.aviso)
                yield from caso.cancelar()
            chequear_ventana("editar_cambiar", desde)
            despues = fotodoc()
            if caso.ok and caso.cambio_visible and not diferencias(antes, despues, con_undo=False):
                inf.falla(caso.nombre, "editar_cambiar", "aceptó pero el cambio no se aplicó")
            if caso.ok and not caso.cambio_visible:
                problema = caso.verificar_cambio(doc.getObject(hecho))
                if problema:
                    inf.falla(caso.nombre, "editar_cambiar", problema)
            if caso.ok and caso.contar_deshacer and despues["undo"] != antes["undo"] + 1:
                inf.falla(caso.nombre, "editar_cambiar", "pasos de deshacer %d -> %d (se espera uno)"
                          % (antes["undo"], despues["undo"]))
            if despues["abierta"]:
                inf.falla(caso.nombre, "editar_cambiar", "quedó una transacción abierta")
            for n in sorted(invalidos_todos() - malos0):
                inf.falla(caso.nombre, "editar_cambiar", "quedó con error: %s" % n)
            if caso.ok:
                ctrl_z(doc)
                doc.recompute()
                yield ESPERA_CORTA
                for d in diferencias(antes, fotodoc(), con_undo=False):
                    inf.falla(caso.nombre, "editar_cambiar", "después de Deshacer: %s" % d)
                ctrl_y(doc)
                doc.recompute()
                yield ESPERA_CORTA
                for d in diferencias(despues, fotodoc(), con_undo=False):
                    inf.falla(caso.nombre, "editar_cambiar", "después de Rehacer: %s" % d)
                chequear_ventana("editar_cambiar", desde)
        obj = doc.getObject(hecho)
    if obj is None and isinstance(hecho, str) and "editar" in caso.reglas:
        inf.falla(caso.nombre, "editar", "la operación %s ya no existe (¿cambió de nombre al editar?)" % hecho)
    if obj is not None and "editar" in caso.reglas:
        desde = informe_largo()
        antes = fotodoc()
        yield from caso.editar(obj)
        if caso.panel() is None and not FreeCADGui.Control.activeDialog():
            inf.falla(caso.nombre, "editar", "no se abrió el panel al editar")
        yield from caso.aceptar()
        yield ESPERA_PANEL
        if not caso.ok:
            inf.falla(caso.nombre, "editar", "no aceptó sin cambios: %s" % caso.aviso)
            yield from caso.cancelar()
        chequear_ventana("editar", desde)
        for d in diferencias(antes, fotodoc(), con_undo=False):
            inf.falla(caso.nombre, "editar", d)
        for n in sorted(invalidos_todos() - malos0):
            inf.falla(caso.nombre, "editar", "quedó con error: %s" % n)

    if hecho is not None and "guardar" in caso.reglas:
        antes = fotodoc()
        # si ya tiene archivo (un ensamblaje, junto a sus piezas), se guarda ahí mismo; las piezas
        # que cambió el panel también se guardan, y después se abren para compararlas
        rutas_otros = []
        for o in caso.documentos(doc):
            if getattr(o, "FileName", ""):
                o.save()
                rutas_otros.append(o.FileName)
        ruta = doc.FileName or os.path.join(carpeta_temporal(), "reglas.FCStd")
        doc.saveAs(ruta)
        abiertos = set(FreeCAD.listDocuments())
        FreeCAD.closeDocument(doc.Name)
        yield ESPERA_CORTA
        # pregunta 4 de las 7 (paso 7): el archivo abre SIN FreeWorks: no guarda objetos de Python
        # de FreeWorks (si los guardara, sin el addon esas operaciones quedarían rotas)
        for r in [ruta] + rutas_otros:
            for modulo in sin_freeworks(r):
                inf.falla(caso.nombre, "guardar", "el archivo necesita FreeWorks para abrir: guarda %s" % modulo)
        desde = informe_largo()
        doc = FreeCAD.openDocument(ruta)
        yield ESPERA_PANEL
        otros = []
        for r in rutas_otros:
            try:
                otros.append(FreeCAD.openDocument(r))
            except Exception:
                inf.falla(caso.nombre, "guardar", "no abre la pieza %s" % r)
        try:
            reabierto = foto_varios(doc, otros)
        except ReferenceError:
            # visto una vez (Esquinas, 08/11) y no se repitió: el documento recién abierto dejó de
            # existir durante la espera. Se anota y se sigue (Issue #40, a investigar)
            inf.falla(caso.nombre, "guardar", "el documento reabierto se cerró solo")
            doc = FreeCAD.openDocument(ruta)
            yield ESPERA_PANEL
            reabierto = foto_varios(doc, otros)
        for d in diferencias(antes, reabierto, con_undo=False):
            inf.falla(caso.nombre, "guardar", d)
        for o in otros:
            try:
                FreeCAD.closeDocument(o.Name)
            except Exception:
                pass
        gdoc = FreeCADGui.getDocument(doc.Name)
        if getattr(gdoc, "Modified", False):
            inf.falla(caso.nombre, "guardar", "al abrir quedó modificado")
        chequear_ventana("guardar", desde)
        for extra in set(FreeCAD.listDocuments()) - abiertos:  # piezas de un ensamblaje (memoria)
            if extra != doc.Name:
                try:
                    FreeCAD.closeDocument(extra)
                except Exception:
                    pass

    try:
        FreeCAD.closeDocument(doc.Name)
    except Exception:
        pass
    for o in caso.documentos(doc):  # piezas de un ensamblaje: no acumularlas (memoria)
        try:
            FreeCAD.closeDocument(o.Name)
        except Exception:
            pass
    caso.cerrar()
    yield ESPERA_CORTA


def correr(casos, deuda=None, semillas=None):
    """Generador para `prueba()`: corre todos los casos y al final falla si hay algo nuevo."""
    if semillas is None:
        n = int(os.environ.get("FW_SEMILLAS", "2"))
        base = int(os.environ.get("FW_SEMILLA", "1"))
        semillas = tuple(range(base, base + n))
    inf = Informe(deuda)
    solo = os.environ.get("FW_CASO", "")  # para probar un panel solo: FW_CASO=Redondeo
    if solo:
        casos = [c for c in casos if solo.lower() in c.nombre.lower()]
        deuda = inf.deuda = {k: v for k, v in (deuda or {}).items() if solo.lower() in k[0].lower()}
    for caso in casos:
        traza("caso " + caso.nombre)
        try:
            yield from correr_caso(caso, inf, semillas)
        except Exception:
            import traceback
            inf.falla(caso.nombre, "(la prueba)", traceback.format_exc(limit=6))
            limpiar_ventana()
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
            yield ESPERA_CORTA
    nuevas, viejas, arregladas = inf.resumen()
    lineas = []
    if nuevas:
        lineas.append("Incumplimientos nuevos:")
        lineas += ["  %s / %s: %s" % f for f in nuevas]
    if arregladas:
        lineas.append("Ya no fallan (sacarlos de DEUDA y cerrar la Issue): %s"
                      % ["%s/%s %s" % (c, r, (deuda or {})[(c, r)]) for c, r in arregladas])
    if viejas:
        traza("conocidos: %s" % ["%s/%s" % (c, r) for c, r, _d in viejas])
    assert not lineas, "\n".join(lineas)


def cambia_numero(atributo, menor, mayor, entero=False):
    """Para `Caso.cambiar`: pone al azar otro valor en el campo `atributo` del panel (spinbox) y
    hace la vista previa. Uso: `cambiar = cambia_numero("radius", 0.5, 4.0)`."""
    def cambiar(self, rng):
        def gen():
            p = self.panel()
            campo = getattr(p, atributo)
            if entero:
                v = rng.randint(int(menor), int(mayor))
            else:
                v = round(rng.uniform(menor, mayor), 2)
            if abs(campo.value() - v) < 1e-6:  # que sea otro valor de verdad
                v = v + 1 if entero else round(v + (mayor - menor) / 3.0, 2)
            campo.setValue(v)
            vista = getattr(p, "preview", None) or getattr(p, "_changed", None)
            if vista is not None:
                vista()
            yield 900
        return gen()
    return cambiar


def cambia_lista(atributo):
    """Para `Caso.cambiar`: elige otra opción al azar en la lista desplegable `atributo`."""
    def cambiar(self, rng):
        def gen():
            p = self.panel()
            combo = getattr(p, atributo)
            n = combo.count()
            if n > 1:
                actual = combo.currentIndex()
                combo.setCurrentIndex(rng.choice([i for i in range(min(n, 6)) if i != actual] or [0]))
            vista = getattr(p, "preview", None) or getattr(p, "_changed", None)
            if vista is not None:
                vista()
            yield 1200
        return gen()
    return cambiar
