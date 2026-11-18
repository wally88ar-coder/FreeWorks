# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Instalación de cero (18/11; lo vio el usuario el 17/11 al reinstalar FreeCAD): con una configuración de FreeCAD
NUEVA, el PRIMER arranque ya queda en FreeWorks (cinta a la vista, sin las barras de FreeCAD ni el selector de
bancos) y con el idioma en castellano; después de tocar "Done" en el asistente de bienvenida de FreeCAD, sigue en
castellano. Un idioma ya elegido no se toca. Se arranca otro FreeCAD (con ventana) con una configuración vacía,
mientras este espera: nunca la configuración del usuario."""
TIPO = "completa"
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402

SONDA = r'''
import json, os, traceback
import FreeCAD, FreeCADGui
from PySide import QtCore, QtWidgets
OUT = os.environ["FW_PRIMER_OUT"]
res = {"etapas": []}

def medir(etapa):
    mw = FreeCADGui.getMainWindow()
    barras = sorted(b.objectName() for b in mw.findChildren(QtWidgets.QToolBar)
                    if b.isVisible() and mw.toolBarArea(b) != QtCore.Qt.ToolBarArea.NoToolBarArea)
    cinta = [w.objectName() for w in mw.findChildren(QtWidgets.QWidget)
             if w.objectName() == "SWUI_RibbonTabs" and w.isVisible()]
    wb = FreeCADGui.activeWorkbench().name() if FreeCADGui.activeWorkbench() else ""
    g = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General")
    menus = [a.text().replace("&", "") for a in mw.menuBar().actions()]
    res["etapas"].append({"etapa": etapa, "barras": barras, "menus": menus, "cinta": bool(cinta), "banco": wb,
                          "idioma": g.GetString("Language", ""), "arranque": g.GetString("AutoloadModule", "")})

def done():
    for b in FreeCADGui.getMainWindow().findChildren(QtWidgets.QPushButton):
        if b.isVisible() and b.text().strip() in ("Done", "Listo", "Hecho", "Terminado"):
            res["done"] = b.text()
            b.click()
            return
    res["done"] = None

def fin():
    try:
        medir("después de Done")
    except Exception:
        res["error"] = traceback.format_exc()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False)
    FreeCAD.saveParameter()  # lo que se grabaría al cerrar (el proceso se corta abajo)
    # os._exit no alcanza: en Windows FreeCAD queda colgado descargando sus bibliotecas (visto el 18/11)
    import ctypes
    k = ctypes.windll.kernel32
    k.TerminateProcess(ctypes.c_void_p(-1), 0)  # -1 = este mismo proceso
    os._exit(0)

def paso1():
    try:
        medir("al arrancar")
        done()
    except Exception:
        res["error"] = traceback.format_exc()
    QtCore.QTimer.singleShot(2500, fin)

QtCore.QTimer.singleShot(6000, paso1)  # después del segundo repaso de las barras (#101)
'''


def _arrancar(carpeta, cfg_texto=None):
    """Otro FreeCAD con ventana y configuración nueva (o la dada); devuelve lo que midió la sonda."""
    cfg = os.path.join(carpeta, "user.cfg")
    if cfg_texto is not None:
        with open(cfg, "w", encoding="utf-8") as fh:
            fh.write(cfg_texto)
    sonda = os.path.join(carpeta, "sonda.py")
    with open(sonda, "w", encoding="utf-8") as fh:
        fh.write(SONDA)
    salida = os.path.join(carpeta, "salida.json")
    env = dict(os.environ)
    env["FW_PRIMER_OUT"] = salida
    env["FREECAD_USER_TEMP"] = os.path.join(carpeta, "temp")
    os.makedirs(env["FREECAD_USER_TEMP"], exist_ok=True)
    for k in ("FW_PRUEBA", "FW_RESULTADO", "FW_COBERTURA"):
        env.pop(k, None)
    exe = os.path.join(FreeCAD.getHomePath(), "bin", "freecad.exe")
    proc = subprocess.Popen([exe, "-u", cfg, sonda], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        proc.wait(timeout=150)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)  # solo ESE FreeCAD
        raise AssertionError("el FreeCAD de primer arranque no terminó")
    assert os.path.exists(salida), "la sonda no dejó resultado"
    with open(salida, encoding="utf-8") as fh:
        res = json.load(fh)
    with open(cfg, encoding="utf-8") as fh:
        res["cfg"] = fh.read()
    return res


def prueba():
    c = carpeta_temporal()
    traza("paso 1")
    # 1) configuración nueva (no existe el archivo): primer arranque
    uno = os.path.join(c, "nueva")
    os.makedirs(uno)
    res = _arrancar(uno)
    traza("  %s" % json.dumps({k: v for k, v in res.items() if k != "cfg"}, ensure_ascii=False))
    assert "error" not in res, res.get("error")
    al_arrancar = res["etapas"][0]
    assert al_arrancar["banco"] == "LikeSolidWorksUIWorkbench", "no arrancó en FreeWorks: %s" % al_arrancar["banco"]
    assert al_arrancar["cinta"], "no está la cinta"
    assert not al_arrancar["barras"], "barras de FreeCAD a la vista: %s" % al_arrancar["barras"]
    assert al_arrancar["idioma"].startswith("Spanish"), "idioma: %r" % al_arrancar["idioma"]
    # no alcanza con el parámetro: la ventana tiene que estar en castellano YA en el primer arranque (revisión 18/11)
    assert "Archivo" in al_arrancar["menus"] and "File" not in al_arrancar["menus"], \
        "menús en el primer arranque: %s" % al_arrancar["menus"]
    # el asistente de bienvenida de FreeCAD tiene que aparecer con la configuración nueva (si no se encuentra su
    # botón, la prueba no probó lo que dice: revisión del 18/11)
    assert res.get("done") is not None, "no encontré el botón Done del asistente de primer arranque"
    despues = res["etapas"][-1]
    assert despues["idioma"].startswith("Spanish"), "el asistente dejó el idioma en %r" % despues["idioma"]
    assert despues["banco"] == "LikeSolidWorksUIWorkbench" and despues["cinta"], "después de Done: %s" % despues
    assert not despues["barras"], "después de Done, barras de FreeCAD: %s" % despues["barras"]
    yield 100

    traza("paso 2")
    # 2) idioma ya elegido (inglés) y una barra que el usuario dejó a la vista (Vista): no se tocan
    dos = os.path.join(c, "ingles")
    os.makedirs(dos)
    cfg = ('<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n<FCParameters>\n<FCParamGroup Name="Root">\n'
           '<FCParamGroup Name="BaseApp"><FCParamGroup Name="Preferences"><FCParamGroup Name="General">\n'
           '<FCText Name="Language">English</FCText>\n</FCParamGroup></FCParamGroup>\n'
           '<FCParamGroup Name="MainWindow"><FCParamGroup Name="Toolbars"><FCBool Name="View" Value="1"/>'
           '</FCParamGroup></FCParamGroup></FCParamGroup>\n'
           '</FCParamGroup>\n</FCParameters>\n')
    res = _arrancar(dos, cfg)
    traza("  %s" % json.dumps({k: v for k, v in res.items() if k != "cfg"}, ensure_ascii=False))
    assert res["etapas"][0]["idioma"] == "English", "tocó el idioma elegido: %r" % res["etapas"][0]["idioma"]
    assert '<FCBool Name="View" Value="1"/>' in res["cfg"], "tocó la barra que el usuario dejó a la vista"
    assert '<FCBool Name="File" Value="0"/>' in res["cfg"], "no anotó oculta la barra Archivo"
    yield 100

    traza("paso 3")
    # 3) destildar "Usar siempre FreeWorks" devuelve las barras a los otros bancos (en la copia de la configuración
    #    de esta prueba; revisión del 18/11, hallazgo 7)
    from swui.fork import always_swui, first_run
    bars = FreeCAD.ParamGet(first_run.TOOLBARS)
    antes = always_swui.enabled()
    try:
        always_swui._AlwaysCommand().Activated(False)
        ocultas = [n for n in first_run.HIDDEN_TOOLBARS if not bars.GetBool(n, True)]
        assert not ocultas, "al destildar quedaron ocultas: %s" % ocultas
    finally:
        always_swui._AlwaysCommand().Activated(antes)
        for n in first_run.HIDDEN_TOOLBARS:
            bars.SetBool(n, False)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
