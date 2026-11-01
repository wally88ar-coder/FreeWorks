# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Paneles del fork y otro comando apretado mientras están abiertos (problema visto por el
usuario el 2026-10-31: Redondeo abierto -> Extruir corte -> ya no se podían elegir caras).

Qué pasaba: con un panel abierto, FreeCAD pregunta "Un diálogo ya está abierto en el panel de
tareas"; con "Sí" lo cierra por su cuenta, sin llamar a Cancelar del panel. El "escucha" de
selección del panel quedaba prendido y huérfano: se llevaba cada cara elegida y vaciaba la
selección (y daba "QListWidget already deleted").

Dos arreglos:
1. Red de seguridad (`orphaned`): cada escucha de los paneles del fork (dress_up_panel
   _PickObserver y mates_sw._SelObserver) pregunta primero si su panel sigue vivo. Si FreeCAD
   lo cerró (su ventana ya no existe o no hay ningún panel abierto), se da de baja solo, el
   panel limpia lo que dibujó (`_orphaned`, si lo tiene) y no toca la selección.
2. Como SW: apretar otro comando en la cinta con un panel del fork abierto cancela ese panel
   (su Cancelar de verdad, con su limpieza) y arranca el comando nuevo, sin la pregunta de
   FreeCAD. Los comandos de vista, medir y archivo no lo cancelan (como en SW).
   Desde menús o atajos de FreeCAD sigue la pregunta; con "Sí" actúa la red de seguridad.

No se puede envolver FreeCADGui.Control.showDialog (FreeCAD no deja: "Extension object
missing implement of setattr"): los paneles se anotan solos al crear su escucha (`track`).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

_tracked = []  # paneles del fork con escucha de selección (el último es el más nuevo)
_state = {"installed": False}

# Comandos que no cancelan el panel abierto (en SW tampoco: vista, medir, archivo, deshacer...)
KEEP_PREFIXES = ("Std_",)
KEEP = {"SWUI_Measure", "SWUI_NormalTo", "SWUI_FitAll", "SWUI_OrbitSpeed", "SWUI_MassProperties",
        "SWUI_Rebuild", "SWUI_ForceRebuild"}


def cancels_panel(command):
    """¿Apretar este comando cancela el panel abierto? (como SW: una operación nueva sí)."""
    if not command or command in KEEP:
        return False
    return not command.startswith(KEEP_PREFIXES)


def _shiboken():
    try:
        import shiboken6 as sb
    except ImportError:
        try:
            import shiboken2 as sb
        except ImportError:
            return None
    return sb


def _form_ok(panel):
    """
    La ventana del panel existe y sigue dentro de la ventana de FreeCAD. Visto en 1.1.4: al
    cerrar FreeCAD el panel ("Sí" a "Un diálogo ya está abierto"), la lista del panel se borra
    pero el contenedor queda vivo y suelto: por eso se mira también dónde está y la lista.
    """
    sb = _shiboken()
    if sb is None:
        return True  # no se puede saber: se lo da por vivo
    widget = getattr(panel, "list", None)
    if widget is not None and not sb.isValid(widget):
        return False
    form = getattr(panel, "form", None)
    if form is None:
        # visto en 1.1.4: tras el "Sí", FreeCAD deja panel.form en None
        return not getattr(panel, "_swui_had_form", False)
    panel._swui_had_form = True
    forms = form if isinstance(form, (list, tuple)) else [form]
    if not all(sb.isValid(f) for f in forms):
        return False
    try:
        main = FreeCADGui.getMainWindow()
        return all(f.window() == main for f in forms)
    except Exception:
        return True


def _form_exists(panel):
    """La ventana del panel existe (aunque todavía no esté puesta dentro de FreeCAD)."""
    sb = _shiboken()
    form = getattr(panel, "form", None)
    if sb is None or form is None:
        return form is not None
    forms = form if isinstance(form, (list, tuple)) else [form]
    return all(sb.isValid(f) for f in forms)


def alive(panel):
    """El panel sigue abierto: su ventana existe, está en FreeCAD y hay un panel en Tareas."""
    try:
        return _form_ok(panel) and bool(FreeCADGui.Control.activeDialog())
    except Exception:
        return True


def track(panel):
    if panel is None:
        return
    _prune()
    if panel in _tracked:
        _tracked.remove(panel)
    _tracked.append(panel)


def _prune():
    _tracked[:] = [p for p in _tracked if _form_ok(p)]


def open_panel():
    """El panel del fork abierto ahora (el más nuevo que sigue vivo), o None."""
    _prune()
    for panel in reversed(_tracked):
        if alive(panel):
            return panel
    return None


def orphaned(observer):
    """
    Red de seguridad, al principio de cada aviso de selección de un escucha de panel:
    True si el panel ya no existe (el escucha se da de baja y el aviso se ignora).
    """
    panel = getattr(observer, "panel", None)
    if panel is None:
        return False
    if alive(panel):
        panel._swui_was_alive = True
        return False
    if not getattr(panel, "_swui_was_alive", False) and _form_exists(panel):
        # todavía se está abriendo: muchos paneles limpian la selección justo después de
        # anotarse como escuchas, antes de mostrarse; con algo elegido, ese aviso los daba por
        # cerrados y dejaban de escuchar (corte de ensamblaje que no abría el croquis, 01/11)
        return False
    if getattr(observer, "_swui_orphan", False):
        return True
    observer._swui_orphan = True
    if panel in _tracked:
        _tracked.remove(panel)
    # darse de baja fuera del aviso que FreeCAD está repartiendo
    QtCore.QTimer.singleShot(0, lambda: _drop(observer, panel))
    return True


def _drop(observer, panel):
    try:
        FreeCADGui.Selection.removeObserver(observer)
    except Exception:
        pass
    cleanup = getattr(panel, "_orphaned", None)
    if cleanup is not None:
        try:
            cleanup()
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Panel cerrado por FreeCAD:\n%s\n" % traceback.format_exc())
    FreeCAD.Console.PrintLog("[SWUI fork] %s: FreeCAD cerró el panel; su escucha se apagó.\n"
                             % type(panel).__name__)


def _pick_plane_panel():
    """
    El panel "seleccionar un plano" del original (Croquis / Extruir sin selección), si está
    abierto. No se anota con `track`: con él abierto, Redondeo desde la cinta o el menú daba la
    pregunta de FreeCAD y, con "No", dejaba un Redondeo vacío con error y la pieza oculta (visto
    con el mouse, 01/11).
    """
    try:
        from swui import pick_plane

        panel = getattr(pick_plane, "_panel", None)
        if panel is not None and not getattr(panel, "done", True) and FreeCADGui.Control.activeDialog():
            return panel
    except Exception:
        pass
    return None


def cancel_open():
    """Cancela el panel del fork abierto (su Cancelar, con su limpieza). True si había uno."""
    panel = open_panel() or _pick_plane_panel()
    if panel is None:
        return False
    try:
        panel.reject()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Cancelar el panel abierto:\n%s\n" % traceback.format_exc())
    try:
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass
    if panel in _tracked:
        _tracked.remove(panel)
    return True


def _wrap_ribbon():
    from swui import ribbon

    original = ribbon._run
    if getattr(original, "_swui_guard", False):
        return

    def run(command, index=None, *args):
        try:
            if cancels_panel(command) and cancel_open():
                # como SW: el panel anterior se cancela y arranca el comando nuevo
                QtCore.QTimer.singleShot(100, lambda: original(command, index, *args))
                return None
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Panel abierto y otro comando:\n%s\n" % traceback.format_exc())
        return original(command, index, *args)

    run._swui_guard = True
    ribbon._run = run


def install():
    """Antes de que se arme la cinta (los botones toman ribbon._run al armarse)."""
    if _state["installed"]:
        return
    try:
        _wrap_ribbon()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Panel abierto y otro comando:\n%s\n" % traceback.format_exc())
    _state["installed"] = True
