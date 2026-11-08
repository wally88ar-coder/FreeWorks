# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Base de las pruebas con medidas al azar (plan de calidad, paso 8.2): herramienta Hypothesis
(inventa medidas, también las raras; si una rompe la regla, la achica al caso más simple que
falla y la recuerda para la próxima corrida).

Las pruebas van por el PANEL, como el usuario: lo propio de FreeWorks es cómo el panel traduce
lo elegido a FreeCAD. Como Hypothesis corre de corrido (no por pasos), mientras espera a que
el panel se abra "bombea" los eventos de la ventana (`bombear`).

Cantidad de casos por regla: FW_CASOS_AZAR (por omisión 6; de noche, cientos). Memoria de los
casos que fallaron: %LOCALAPPDATA%/FreeWorks-dev/hypothesis (se repiten primero la vez siguiente).
"""

import math
import os
import time
import traceback

import FreeCAD

from _base import traza

V = FreeCAD.Vector


def hypothesis_listo():
    """Importa Hypothesis desde la carpeta de herramientas y devuelve (given, settings, st)."""
    import sys
    herr = os.environ.get("FW_HERRAMIENTAS") or os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                                             "FreeWorks-dev", "pkgs")
    if herr not in sys.path:
        sys.path.insert(0, herr)
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
    from hypothesis.database import DirectoryBasedExampleDatabase
    base = DirectoryBasedExampleDatabase(os.path.join(os.path.dirname(herr), "hypothesis"))
    cfg = settings(max_examples=int(os.environ.get("FW_CASOS_AZAR", "6")), deadline=None,
                   database=base, derandomize=False, print_blob=False,
                   suppress_health_check=list(HealthCheck))
    return given, cfg, st


# --- Ventana, de corrido -------------------------------------------------------------------------


def bombear(ms):
    """Esperar `ms` dejando que la ventana procese lo suyo (paneles que se abren con QTimer)."""
    from PySide import QtWidgets
    fin = time.time() + ms / 1000.0
    app = QtWidgets.QApplication.instance()
    while time.time() < fin:
        app.processEvents()
        time.sleep(0.02)


def hay_panel():
    import FreeCADGui
    return bool(FreeCADGui.Control.activeDialog())


def esperar_panel(maximo_ms=12000):
    hecho = 0
    while hecho < maximo_ms:
        bombear(200)
        hecho += 200
        if hay_panel():
            bombear(700)
            return True
    return False


def aceptar():
    """Clic en Aceptar del panel (como el usuario); True si el panel se cerró."""
    from reglas_paneles import tocar
    tocar(rechazar=False)
    for _i in range(15):
        bombear(200)
        if not hay_panel():
            return True
    return False


def limpiar():
    from reglas_paneles import limpiar_ventana
    limpiar_ventana()
    for n in list(FreeCAD.listDocuments()):
        try:
            FreeCAD.closeDocument(n)
        except Exception:
            pass
    bombear(200)


def cinta(comando):
    from swui import ribbon
    ribbon._run(comando)


# --- Campos de los paneles nativos ---------------------------------------------------------------


def _vista_tareas():
    import FreeCADGui
    from PySide import QtWidgets
    for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QWidget):
        if w.metaObject().className() == "Gui::TaskView::TaskView" and w.isVisible():
            return w
    return None


def campo(nombre):
    """El widget visible del panel con ese objectName (p. ej. 'lengthEdit', 'sidesMode')."""
    from PySide import QtWidgets
    tv = _vista_tareas()
    for w in tv.findChildren(QtWidgets.QWidget) if tv is not None else []:
        if w.objectName() == nombre and w.isVisible():
            return w
    raise AssertionError("el panel no tiene el campo %r a la vista" % nombre)


def escribir(widget, valor):
    """Escribe un número en un campo de cantidad de FreeCAD como el usuario (coma decimal) y pasa
    al campo siguiente con Tab. Con Enter no: en un panel de Tareas, Enter es Aceptar."""
    from PySide import QtCore
    from PySide6.QtTest import QTest
    widget.setFocus()
    widget.selectAll()
    QTest.keyClicks(widget, ("%.3f" % valor).replace(".", ","))
    QTest.keyClick(widget, QtCore.Qt.Key.Key_Tab)
    bombear(300)


def elegir_opcion(nombre, texto):
    """Elige en la lista desplegable `nombre` la opción cuyo texto (en castellano) empieza así."""
    combo = campo(nombre)
    textos = [combo.itemText(i) for i in range(combo.count())]
    for i, t in enumerate(textos):
        if t.lower().startswith(texto.lower()):
            combo.setCurrentIndex(i)
            bombear(400)
            return
    raise AssertionError("%r no es una opción de %s: %s" % (texto, nombre, textos))


def tildar(nombre, valor):
    caja = campo(nombre)
    if caja.isChecked() != valor:
        caja.click()
        bombear(300)


# --- Piezas --------------------------------------------------------------------------------------


def documento(nombre="Azar"):
    import FreeCADGui
    doc = FreeCAD.newDocument(nombre)
    doc.UndoMode = 1
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
    return doc, body


def plano(body, rol):
    return [f for f in body.Origin.OriginFeatures if f.Role == rol][0]


def croquis(body, rol="XY_Plane", z=0.0, rects=(), circulos=()):
    import Part
    sk = body.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(plano(body, rol), "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = FreeCAD.Placement(V(0, 0, z), FreeCAD.Rotation())
    for x0, y0, x1, y1 in rects:
        pts = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
        for i in range(4):
            sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for cx, cy, r in circulos:
        sk.addGeometry(Part.Circle(V(cx, cy, 0), V(0, 0, 1), r))
    body.Document.recompute()
    return sk


def caja(body, largo, ancho, alto, base=V(0, 0, 0)):
    b = body.newObject("PartDesign::AdditiveBox", "Caja")
    b.Length, b.Width, b.Height = largo, ancho, alto
    b.Placement.Base = base
    body.Document.recompute()
    return b


def volumen(obj):
    return float(obj.Shape.Volume)


def cerca(a, b, rel=1e-4, absoluto=1e-3):
    return abs(a - b) <= max(absoluto, rel * max(abs(a), abs(b)))


CASOS = [0]  # casos que llegaron a la comprobación (las reglas llaman a `comprobado()`)


def comprobado():
    CASOS[0] += 1


class Fallas:
    """Junta las reglas que fallaron (cada una con su caso mínimo) para informarlas todas."""

    def __init__(self):
        self.lista = []

    def correr(self, nombre, fn):
        traza("regla " + nombre)
        CASOS[0] = 0
        try:
            fn()
            traza("  %s: bien (%d casos comprobados)" % (nombre, CASOS[0]))
            if CASOS[0] == 0:
                self.lista.append("%s: ningún caso llegó a comprobarse (todos descartados)" % nombre)
        except Exception:
            texto = traceback.format_exc(limit=4)
            traza("  %s: FALLA\n%s" % (nombre, texto))
            self.lista.append("%s:\n%s" % (nombre, texto))
        finally:
            limpiar()

    def terminar(self):
        assert not self.lista, "\n\n".join(self.lista)


PI = math.pi
