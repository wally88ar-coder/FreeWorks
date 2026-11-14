# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
"Guardar también STEP": al guardar una pieza o ensamblaje, deja al lado un
.step con el mismo nombre (pieza.FCStd -> pieza.step).

Es el resguardo para versiones futuras de FreeCAD: el STEP no tiene historial,
pero la geometría queda siempre, abra o no el .FCStd. Se prende y apaga en el
menú "LikeSolidWorks UI" (apagado de fábrica; parámetro
BaseApp/Preferences/Mod/SWUI/AlsoSaveStep).

Se exportan los objetos de primer nivel que tienen forma (cuerpos, piezas,
ensamblajes, sólidos importados), sin croquis, planos ni hojas de dibujo, con
ImportGui (conserva colores). Si la pieza se guardó retrocedida y se elige
"Avanzar hasta el final y guardar", el STEP sale de esa segunda vez.
"""

import os
import traceback

import FreeCAD
import FreeCADGui

PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
KEY = "AlsoSaveStep"
COMMAND = "SWUI_AlsoSaveStep"
SHAPED = ("PartDesign::Body", "App::Part", "Assembly::AssemblyObject", "App::Link")
NOT_SHAPES = ("Sketcher::SketchObject", "TechDraw::DrawPage", "Spreadsheet::Sheet", "App::VarSet")

_observer = None


def enabled():
    try:
        return FreeCAD.ParamGet(PARAMS).GetBool(KEY, False)
    except Exception:
        return False


def set_enabled(on):
    FreeCAD.ParamGet(PARAMS).SetBool(KEY, bool(on))


def step_path(fcstd):
    """pieza.FCStd -> pieza.step (misma carpeta)."""
    return os.path.splitext(fcstd)[0] + ".step"


def _has_solid(obj):
    import Part

    shape = Part.getShape(obj)
    return not shape.isNull() and bool(shape.Solids)


def exportable(objs):
    """Objetos de primer nivel con forma, sin croquis ni hojas. Un ensamblaje se exporta por sus
    componentes con sólido: entero, el exportador de FreeCAD recorría también las relaciones, la
    tabla de variables y los planos (sin sólido) y llenaba el informe de errores ("has null shape",
    "Failed to get subshape Face1"; mono de ensamblaje, 12/11)."""
    out = []
    for obj in objs:
        kind = getattr(obj, "TypeId", "")
        if kind in NOT_SHAPES:
            continue
        if kind == "Assembly::AssemblyObject":
            out += [c for c in exportable(obj.Group) if c.TypeId != kind and _has_solid(c)]
            continue
        if kind in SHAPED or (hasattr(obj, "isDerivedFrom") and obj.isDerivedFrom("Part::Feature")
                              and not obj.isDerivedFrom("Part::Part2DObject")):
            out.append(obj)
    return out


def export(doc, filename=None):
    """Escribir el .step de doc (al lado de `filename`, o de su archivo). Devuelve la ruta o None."""
    filename = filename or getattr(doc, "FileName", "")
    objs = exportable(doc.RootObjects)
    if not filename or not objs:
        return None
    path = step_path(filename)
    try:
        import ImportGui

        ImportGui.export(objs, path)
    except Exception:
        import Import

        Import.export(objs, path)
    FreeCAD.Console.PrintLog("[SWUI fork] STEP guardado: %s\n" % path)
    return path


def after_save(name, filename=""):
    """Llamado al terminar de guardar (desde feature_tree, después del aviso de retroceso)."""
    if not enabled():
        return
    try:
        mw = FreeCADGui.getMainWindow()
        mw.statusBar().showMessage("Guardando también STEP...")
        if name in FreeCAD.listDocuments():
            path = export(FreeCAD.getDocument(name))
        else:
            path = _export_closed(filename)
        mw.statusBar().showMessage("STEP guardado: %s" % path if path else "", 5000)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] No se pudo guardar el STEP:\n%s\n" % traceback.format_exc())


def _export_closed(filename):
    """
    Guardar al cerrar ("¿Guardar cambios?" -> Sí, o Cerrar todo): cuando llega el turno del STEP
    el documento ya se cerró (salía un error rojo, visto con el mouse 2026-10-31). Se abre oculta
    una COPIA del archivo recién guardado (en la misma carpeta, así sus piezas se encuentran igual),
    se exporta el STEP con el nombre del original y se cierra solo lo que se abrió para eso.

    Copia y no el archivo mismo (#40): si el usuario abría ese archivo mientras se escribía el STEP,
    FreeCAD le daba el documento oculto que había abierto FreeWorks, y al terminar se lo cerraba
    ("el documento se cerró solo"). Con la copia, lo que abre el usuario es siempre suyo.
    """
    if not filename or not os.path.isfile(filename):
        return None
    import shutil

    folder, base = os.path.split(filename)
    _sweep(folder)
    copy = os.path.join(folder, "~fw_step_%d_%s" % (os.getpid(), base))
    try:
        shutil.copy2(filename, copy)
        source = copy
    except Exception:
        # carpeta de solo lectura o sin lugar: el archivo mismo, como antes (mejor el STEP que nada)
        FreeCAD.Console.PrintLog("[SWUI fork] STEP sin copia de trabajo:\n%s\n" % traceback.format_exc())
        source = None
    before = set(FreeCAD.listDocuments())
    try:
        doc = FreeCAD.openDocument(source or filename, True)
        doc.recompute()
        return export(doc, filename)
    finally:
        # lo que se abrió para esto (también lo que cargó el recálculo), salvo lo que el usuario
        # tiene en una ventana (revisión del 14/11)
        for n in set(FreeCAD.listDocuments()) - before:
            if not _shown(n):
                try:
                    FreeCAD.closeDocument(n)
                except Exception:
                    pass
        if source:
            for leftover in (copy, os.path.splitext(copy)[0] + ".FCBak", copy + ".FCBak"):
                try:
                    if os.path.isfile(leftover):
                        os.remove(leftover)
                except Exception:
                    pass


STALE_S = 3600


def _sweep(folder):
    """Borrar copias de trabajo viejas que dejó un cierre a mitad de camino (FreeCAD colgado)."""
    import time

    try:
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            if name.startswith("~fw_step_") and time.time() - os.path.getmtime(path) > STALE_S:
                os.remove(path)
    except Exception:
        pass


def _shown(name):
    """¿El usuario tiene ese documento en una ventana? (uno abierto oculto no tiene vista)"""
    try:
        return bool(FreeCADGui.getDocument(name).mdiViewsOfType("Gui::View3DInventor"))
    except Exception:
        return False


class _AlsoSaveStep:
    """Menú LikeSolidWorks UI -> Guardar también STEP (con tilde)."""

    def GetResources(self):
        return {"MenuText": "Guardar también STEP",
                "ToolTip": "Al guardar, deja al lado un .step con el mismo nombre (resguardo sin historial)",
                "Checkable": enabled()}

    def IsActive(self):
        return True

    def Activated(self, checked=None):
        set_enabled(bool(checked) if checked is not None else not enabled())


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _AlsoSaveStep())
    except Exception:
        pass  # ya registrado
