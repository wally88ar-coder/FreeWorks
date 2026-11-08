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
import random

import FreeCAD

from _base import carpeta_temporal, traza

ESPERA_PANEL = 1800   # ms para que un panel se abra y haga su vista previa
ESPERA_CORTA = 700


# --- Lo que se compara ----------------------------------------------------------------------


def _vol(o):
    try:
        s = o.Shape
        if s.isNull() or not s.Solids:
            return None
        return round(s.Volume, 2)
    except Exception:
        return None


def foto(doc):
    """Estado comparable del documento: objetos (tipo, volumen, visible) y pasos de deshacer."""
    objs = {}
    for o in doc.Objects:
        vis = None
        try:
            vis = bool(o.Visibility)
        except Exception:
            pass
        objs[o.Name] = (o.TypeId, _vol(o), vis)
    return {"objs": objs, "undo": doc.UndoCount}


def diferencias(a, b, con_undo=True):
    out = []
    for n in sorted(set(a["objs"]) | set(b["objs"])):
        if n not in b["objs"]:
            out.append("falta %s" % n)
        elif n not in a["objs"]:
            out.append("sobra %s (%s)" % (n, b["objs"][n][0]))
        elif a["objs"][n] != b["objs"][n]:
            out.append("%s cambió: %s -> %s" % (n, a["objs"][n], b["objs"][n]))
    if con_undo and a["undo"] != b["undo"]:
        out.append("pasos de deshacer: %d -> %d" % (a["undo"], b["undo"]))
    return out


# --- Informe ---------------------------------------------------------------------------------


class Informe:
    def __init__(self, deuda=None):
        self.fallas = []          # (caso, regla, detalle)
        self.notas = []
        self.deuda = deuda or {}  # (caso, regla) -> "#N": incumplimientos ya registrados

    def falla(self, caso, regla, detalle):
        traza("FALLA %s/%s: %s" % (caso, regla, detalle))
        self.fallas.append((caso, regla, detalle))

    def nota(self, texto):
        traza(texto)
        self.notas.append(texto)

    def resumen(self):
        nuevas = [f for f in self.fallas if (f[0], f[1]) not in self.deuda]
        viejas = [f for f in self.fallas if (f[0], f[1]) in self.deuda]
        arregladas = sorted(set(self.deuda) - {(f[0], f[1]) for f in self.fallas})
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
    return [l for l in texto.splitlines() if any(m in l for m in MALAS)]


def limpiar_ventana():
    """Cierra diálogos y paneles que hayan quedado (después de anotarlos)."""
    import FreeCADGui
    from PySide import QtWidgets
    restos = []
    d = QtWidgets.QApplication.activeModalWidget()
    if d is not None:
        restos.append("diálogo abierto: %s %r" % (d.objectName(), d.windowTitle()))
        d.reject()
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
        if gdoc is not None and gdoc.getInEdit() is not None:
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
                    b.click()
                    return True
    return False


# --- Caso: un panel --------------------------------------------------------------------------


class Caso:
    """Cómo manejar un panel. Las subclases completan lo marcado."""

    nombre = ""
    tipo = ""            # TypeId de la operación que crea
    ayudantes = ()       # TypeId de objetos auxiliares que también puede crear al aceptar
    otro = "PartDesign_Chamfer"  # comando de la cinta para la regla otro_comando
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
        self.ok = tocar(rechazar=False)
        yield ESPERA_CORTA
        import FreeCADGui
        self.ok = self.ok and not FreeCADGui.Control.activeDialog()

    def cancelar(self):
        """Toca Cancelar del panel. Generador."""
        tocar(rechazar=True)
        yield ESPERA_CORTA

    def mensaje(self):
        """Texto del aviso del panel (para ver que avisa en castellano), o ''."""
        p = self.panel()
        try:
            m = p.message
            return m.text() if m.isVisible() else ""
        except Exception:
            return ""

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
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    caso.preparar(doc)
    doc.recompute()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    yield ESPERA_CORTA
    base = foto(doc)
    hecho = None

    def chequear_ventana(regla, desde):
        for r in limpiar_ventana():
            inf.falla(caso.nombre, regla, "quedó " + r)
        for l in mensajes_nuevos(desde):
            inf.falla(caso.nombre, regla, "informe de FreeCAD: " + l.strip()[:200])

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
            for d in diferencias(base, foto(doc)):
                inf.falla(caso.nombre, "cancelar", d)

    if "invalido" in caso.reglas:
        gen = None
        desde = informe_largo()
        yield from caso.abrir(random.Random(0))
        gen = caso.invalido()
        if gen is not None:
            yield from gen
            yield ESPERA_PANEL
            yield from caso.aceptar()
            traza("  %s inválido: %s, aviso %r" % (caso.nombre, "aceptó" if caso.ok else "no aceptó",
                                                   caso.mensaje()))
            if caso.ok:
                inf.falla(caso.nombre, "invalido", "aceptó algo inválido")
            elif not caso.mensaje():
                inf.falla(caso.nombre, "invalido", "no aceptó pero no dijo por qué")
            yield from caso.cancelar()
            chequear_ventana("invalido", desde)
            for d in diferencias(base, foto(doc)):
                inf.falla(caso.nombre, "invalido", d)
        else:
            yield from caso.cancelar()
            limpiar_ventana()

    if "otro_comando" in caso.reglas:
        desde = informe_largo()
        yield from caso.abrir(random.Random(1))
        yield from caso.elegir(random.Random(1))
        yield ESPERA_PANEL
        FreeCADGui.Selection.clearSelection()
        from swui import ribbon
        ribbon._run(caso.otro)
        yield ESPERA_PANEL
        # el panel nuevo (vacío) se cancela también; lo del primero no tiene que quedar
        from swui.fork import panel_guard
        tocar(rechazar=True)
        yield ESPERA_CORTA
        chequear_ventana("otro_comando", desde)
        for d in diferencias(base, foto(doc)):
            inf.falla(caso.nombre, "otro_comando", d)

    if "aceptar" in caso.reglas:
        for semilla in semillas:
            rng = random.Random(semilla)
            desde = informe_largo()
            yield from caso.abrir(rng)
            yield from caso.elegir(rng)
            yield ESPERA_PANEL
            yield from caso.aceptar()
            yield ESPERA_PANEL
            if not caso.ok:
                if not caso.mensaje():
                    inf.falla(caso.nombre, "aceptar", "semilla %d: no aceptó y no dijo por qué" % semilla)
                else:
                    inf.nota("%s: semilla %d no aceptó: %s" % (caso.nombre, semilla, caso.mensaje()))
                yield from caso.cancelar()
                limpiar_ventana()
                continue
            chequear_ventana("aceptar", desde)
            despues = foto(doc)
            nuevos = _nuevos(base, despues)
            tipos = [despues["objs"][n][0] for n in nuevos]
            traza("  %s semilla %d: aceptó, nuevos %s" % (caso.nombre, semilla, tipos))
            validos = caso.tipo if isinstance(caso.tipo, tuple) else (caso.tipo,)
            if sum(1 for t in tipos if t in validos) != 1:
                inf.falla(caso.nombre, "aceptar", "semilla %d: esperaba una %s nueva, hay %s" % (semilla, caso.tipo, tipos))
            raros = [t for t in tipos if t not in validos and t not in caso.ayudantes]
            if raros:
                inf.falla(caso.nombre, "aceptar", "semilla %d: objetos de más: %s" % (semilla, raros))
            if despues["undo"] != base["undo"] + 1:
                inf.falla(caso.nombre, "aceptar", "semilla %d: pasos de deshacer %d -> %d (se espera uno)"
                          % (semilla, base["undo"], despues["undo"]))
            for n in nuevos:
                o = doc.getObject(n)
                if o.TypeId in validos:
                    hecho = n
                    if not o.isValid() or "Invalid" in str(o.State):
                        inf.falla(caso.nombre, "aceptar", "semilla %d: %s quedó con error: %s" % (semilla, n, o.State))
            doc.undo()
            doc.recompute()
            yield ESPERA_CORTA
            for d in diferencias(base, foto(doc), con_undo=False):
                inf.falla(caso.nombre, "aceptar", "semilla %d, después de Deshacer: %s" % (semilla, d))
            doc.redo()
            doc.recompute()
            yield ESPERA_CORTA
            for d in diferencias(despues, foto(doc), con_undo=False):
                inf.falla(caso.nombre, "aceptar", "semilla %d, después de Rehacer: %s" % (semilla, d))
            if semilla != semillas[-1]:
                doc.undo()
                doc.recompute()
                yield ESPERA_CORTA
        if hecho is None:
            inf.falla(caso.nombre, "aceptar", "ninguna semilla dio una operación aceptada")

    if hecho is not None and "editar" in caso.reglas:
        desde = informe_largo()
        antes = foto(doc)
        yield from caso.editar(doc.getObject(hecho))
        if caso.panel() is None and not FreeCADGui.Control.activeDialog():
            inf.falla(caso.nombre, "editar", "no se abrió el panel al editar")
        yield from caso.aceptar()
        yield ESPERA_PANEL
        if not caso.ok:
            inf.falla(caso.nombre, "editar", "no aceptó sin cambios: %s" % caso.mensaje())
            yield from caso.cancelar()
        chequear_ventana("editar", desde)
        for d in diferencias(antes, foto(doc), con_undo=False):
            inf.falla(caso.nombre, "editar", d)

    if hecho is not None and "guardar" in caso.reglas:
        antes = foto(doc)
        ruta = os.path.join(carpeta_temporal(), "reglas.FCStd")
        doc.saveAs(ruta)
        nombre = doc.Name
        FreeCAD.closeDocument(nombre)
        yield ESPERA_CORTA
        desde = informe_largo()
        doc = FreeCAD.openDocument(ruta)
        yield ESPERA_PANEL
        for d in diferencias(antes, foto(doc), con_undo=False):
            inf.falla(caso.nombre, "guardar", d)
        try:
            if FreeCADGui.getDocument(doc.Name).Modified:
                inf.falla(caso.nombre, "guardar", "al abrir quedó modificado")
        except AttributeError:
            pass
        chequear_ventana("guardar", desde)

    try:
        FreeCAD.closeDocument(doc.Name)
    except Exception:
        pass
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
