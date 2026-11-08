# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Base de cada prueba de la batería (ver LEEME.md). Cada archivo `prueba_*.py` termina con

    from _base import ejecutar
    ejecutar(globals())

y define QUE (qué tiene que pasar, en castellano), `prueba()` (falla con `assert` o una
excepción) y, opcionales, CONOCIDO = "#N" (error todavía abierto en las Issues) con ESPERA = un
pedazo del mensaje de error que da ese error (si falla con otro mensaje, es FALLA: así un
CONOCIDO no tapa un error nuevo), y TIPO = "completa" (necesita la ventana de FreeCAD; si no, es
"rapida", con FreeCADCmd).

Una prueba "completa" puede devolver una lista de pasos [(demora_ms, función), ...]: se corren
con la ventana viva (los paneles necesitan que Qt procese eventos entre clics); el último paso
suele ser el que comprueba. Cualquier excepción en un paso = la prueba falla.

El resultado va a un JSON que lee `correr.py`. Con FW_COBERTURA prendido, mide qué líneas de
`swui/fork` se ejecutaron (paso 6 del plan, mapa de cobertura).
"""

import json
import os
import sys
import tempfile
import traceback

AQUI = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(os.path.dirname(os.path.dirname(AQUI)))
if ADDON not in sys.path:
    sys.path.insert(0, ADDON)
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)


def carpeta_temporal():
    """Una carpeta nueva para los archivos que guarde la prueba."""
    return tempfile.mkdtemp(prefix="fw_prueba_")


def cerrar_todo():
    import FreeCAD
    for name in list(FreeCAD.listDocuments()):
        try:
            FreeCAD.closeDocument(name)
        except Exception:
            pass


COV = None  # la medición de cobertura, si la empezó _lanzar.py (antes de cargar la prueba)


def _cobertura():
    if COV is not None:
        return COV
    ruta = os.environ.get("FW_COBERTURA")
    if not ruta:
        return None
    herramientas = os.environ.get("FW_HERRAMIENTAS", "")
    if herramientas and herramientas not in sys.path:
        sys.path.insert(0, herramientas)
    import coverage
    cov = coverage.Coverage(data_file=ruta, source=[os.path.join(ADDON, "swui", "fork")])
    cov.start()
    return cov


def traza(texto):
    """Una línea en el registro de la prueba (lo muestra correr.py si la prueba no termina)."""
    salida = os.environ.get("FW_RESULTADO")
    if salida:
        with open(salida + ".log", "a", encoding="utf-8") as fh:
            fh.write(texto + "\n")


def _escribir(res):
    salida = os.environ.get("FW_RESULTADO")
    if salida:
        with open(salida, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
    else:
        print(json.dumps(res, ensure_ascii=False, indent=1))


class _Corrida:
    def __init__(self, g):
        self.g = g
        self.res = {"que": g.get("QUE", ""), "conocido": g.get("CONOCIDO", ""), "ok": False, "error": ""}
        self.espera = g.get("ESPERA", "")
        self.cov = None

    def empezar(self):
        traza("empieza")
        self.cov = _cobertura()
        try:
            pasos = self.g["prueba"]()
        except Exception:
            self.terminar(traceback.format_exc(limit=8))
            return
        if not pasos:
            self.terminar("")
            return
        if hasattr(pasos, "send"):  # un generador: cada `yield ms` espera eso con la ventana viva
            self.gen = pasos
            self.seguir_gen()
            return
        self.pasos = list(pasos)
        self.siguiente()

    def seguir_gen(self):
        from PySide import QtCore
        try:
            demora = next(self.gen)
        except StopIteration:
            self.terminar("")
            return
        except Exception:
            self.terminar(traceback.format_exc(limit=10))
            return
        QtCore.QTimer.singleShot(int(demora or 0), lambda: self.seguir_gen())

    def siguiente(self):
        from PySide import QtCore
        if not self.pasos:
            self.terminar("")
            return
        demora, fn = self.pasos.pop(0)

        def hacer():
            traza("paso " + fn.__name__)
            try:
                fn()
            except Exception:
                self.terminar(traceback.format_exc(limit=8))
                return
            self.siguiente()
        QtCore.QTimer.singleShot(demora, hacer)

    def terminar(self, error):
        traza("termina " + ("con error" if error else "bien"))
        self.res["ok"] = not error
        self.res["error"] = error
        if error and self.res["conocido"] and (not self.espera or self.espera not in error):
            # falló, pero no por el error conocido: cuenta como falla nueva
            self.res["error"] = ("falla distinta de la conocida %s (se esperaba %r):\n%s"
                                 % (self.res["conocido"], self.espera, error))
            self.res["conocido"] = ""
        if self.cov is not None:
            try:
                self.cov.stop()
                self.cov.save()
            except Exception:
                pass
        # el resultado ANTES de cerrar: si FreeCAD se cae al cerrar, lo que pasó ya quedó anotado
        _escribir(self.res)
        cerrar_todo()
        import FreeCAD
        if FreeCAD.GuiUp:
            import FreeCADGui
            from PySide import QtCore
            QtCore.QTimer.singleShot(300, FreeCADGui.getMainWindow().close)


def ejecutar(g):
    traza("cargada")
    corrida = _Corrida(g)
    import FreeCAD
    if FreeCAD.GuiUp:
        # con ventana: esperar a que FreeCAD termine de arrancar y entrar al banco
        from PySide import QtCore

        def entrar():
            traza("entra al banco")
            try:
                import FreeCADGui
                FreeCADGui.activateWorkbench("LikeSolidWorksUIWorkbench")
                mw = FreeCADGui.getMainWindow()
                mw.showNormal()
                mw.setGeometry(0, 23, 1366, 705)  # pantalla del usuario
            except Exception:
                corrida.terminar(traceback.format_exc(limit=8))
                return
            # lambda y no corrida.empezar: PySide guarda los métodos de objetos comunes con una
            # referencia débil y el aviso no llegaba nunca (visto 08/11)
            QtCore.QTimer.singleShot(1500, lambda: corrida.empezar())
        QtCore.QTimer.singleShot(3000, entrar)
    else:
        corrida.empezar()


def modal_abierto():
    """El diálogo modal abierto ahora (para cerrarlo en una prueba), o None."""
    from PySide import QtWidgets
    return QtWidgets.QApplication.activeModalWidget()
