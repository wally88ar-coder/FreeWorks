# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
"Python seguro": correr un script escrito por la IA sin arriesgar la pieza.

Pasos (idea tomada de ghbalf/freecad-ai, core/executor.py; código propio):
1. En el hilo principal: el respaldo de la IA si el documento no tiene uno desde que se guardó
   (`respaldo.py`: uno solo, se borra al guardar) y una copia de trabajo para la prueba
   (`saveCopy`: no cambian el nombre ni el archivo del usuario).
2. Fuera del hilo principal: la copia se abre en un FreeCAD aparte sin pantalla (freecadcmd) y se
   corre el script ahí. Si da error, deja una operación con error o se cuelga (corte por tiempo
   que sí anda en Windows), no se toca la pieza del usuario.
3. En el hilo principal: el script corre de verdad como UN paso de Ctrl+Z ("IA: <título>"), queda
   escrito en la consola de Python, y si falla a mitad se deshace solo.

Scripts de "solo leer" (consultas): sin respaldo ni prueba aparte; si igual cambian algo, se
deshace y vuelve como error. Si un script no cambió nada, no queda paso de deshacer (FreeCAD
descarta los vacíos) y el respaldo hecho para él se borra.

Límite: la prueba aparte no tiene parte visual (colores, vistas): esos cambios no se prueban.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import traceback

import FreeCAD

from swui.fork.ia.nucleo import config, puente, respaldo
from swui.fork.ia.nucleo.deshacer import new_steps

TEST_TIMEOUT = 90  # segundos para la prueba aparte (incluye arrancar freecadcmd)
RUN_TIMEOUT = 180  # segundos en el hilo principal antes de avisar que quedó trabado
MAX_OUTPUT = 6000  # caracteres de salida que vuelven a la IA

_HARNESS = r'''# Prueba aparte de un script de la IA (FreeWorks). Se borra sola.
import json, os, sys, traceback, types
result = {{"ok": False}}
try:
    import FreeCAD as App

    class _NoGui:
        def __getattr__(self, _name):
            return self
        def __call__(self, *a, **k):
            return self
        def __bool__(self):
            return False
    _gui = types.ModuleType("FreeCADGui")
    _gui.ActiveDocument = _NoGui()
    _gui.Selection = _NoGui()
    _gui.SendMsgToActiveView = lambda *a, **k: None
    _gui.updateGui = lambda *a, **k: None
    _gui.doCommandSkip = lambda *a, **k: None
    sys.modules["FreeCADGui"] = _gui

    def _bad(o):
        if "Invalid" in (getattr(o, "State", None) or []):
            return True
        try:
            if o.isDerivedFrom("PartDesign::Feature") and not o.Suppressed:
                return o.Shape.isNull() or not o.Shape.isValid()
        except Exception:
            pass
        return False

    copy = {copy!r}
    if copy:
        doc = App.openDocument(copy)
        doc.recompute()
    else:
        doc = App.newDocument("PruebaIA")
    before = {{o.Name for o in doc.Objects if _bad(o)}}
    ns = {{"__name__": "__main__", "App": App, "FreeCAD": App, "Gui": _gui, "FreeCADGui": _gui,
          "doc": doc}}
    for _name in ("Part", "PartDesign", "Sketcher", "math"):
        try:
            ns[_name] = __import__(_name)
        except Exception:
            pass
    with open({code_path!r}, encoding="utf-8") as fh:
        src = fh.read()
    exec(compile(src, "script_ia.py", "exec"), ns)
    for d in App.listDocuments().values():
        d.recompute()
    bad = []
    for d in App.listDocuments().values():
        for o in d.Objects:
            if _bad(o) and not (d is doc and o.Name in before):
                bad.append("%s (%s)" % (o.Label, o.TypeId))
    result["bad"] = bad
    result["ok"] = not bad
except BaseException:
    result["error"] = traceback.format_exc()[-3000:]
finally:
    with open({result_path!r}, "w", encoding="utf-8") as fh:
        json.dump(result, fh)
    os._exit(0)
'''


def _freecadcmd():
    home = FreeCAD.getHomePath()
    for name in ("freecadcmd.exe", "FreeCADCmd.exe", "freecadcmd", "FreeCADCmd"):
        path = os.path.join(home, "bin", name)
        if os.path.isfile(path):
            return path
    return ""


# --- 1. Preparar (hilo principal) ------------------------------------------------------


def _prepare(read_only, test):
    doc = FreeCAD.ActiveDocument
    res = {"doc": doc.Name if doc is not None else "", "copy": "", "backup": "", "new_backup": False}
    if doc is not None and doc.HasPendingTransaction and not read_only:
        raise RuntimeError("hay un panel abierto con cambios sin aceptar: aceptalo o cancelalo antes")
    if doc is None or not doc.Objects or read_only:
        return res
    res["backup"], res["new_backup"] = respaldo.ensure(doc)
    if test:
        folder = os.path.join(config.data_dir(), "prueba")
        os.makedirs(folder, exist_ok=True)
        res["copy"] = os.path.join(folder, "documento.FCStd")
        respaldo.save_copy(doc, res["copy"])  # copia de trabajo para la prueba (se pisa cada vez)
    return res


def log(code, title, note=""):
    """Registro: el script queda escrito en la consola de Python (para revisarlo o guardarlo
    como macro) y una línea en la vista de informe. note: por qué no se ejecutó."""
    head = "# --- IA: %s%s ---" % (title, " (NO se ejecutó: %s)" % note if note else "")
    try:
        import FreeCADGui

        FreeCADGui.doCommandSkip("%s\n%s" % (head, code.rstrip()))
    except Exception:
        pass
    if note:
        FreeCAD.Console.PrintWarning("FreeWorks IA: '%s' no se ejecutó (%s).\n" % (title, note))
    else:
        FreeCAD.Console.PrintMessage("FreeWorks IA: %s (el script quedó en la consola de Python)\n" % title)


# --- 2. Prueba aparte (fuera del hilo principal) ----------------------------------------


def test_apart(code, copy, timeout=TEST_TIMEOUT):
    """Correr el script en un freecadcmd aparte sobre la copia. Devuelve (ok, informe)."""
    exe = _freecadcmd()
    if not exe:
        return True, "sin prueba aparte (no se encontró freecadcmd)"
    folder = os.path.join(config.data_dir(), "prueba")
    os.makedirs(folder, exist_ok=True)
    code_path = os.path.join(folder, "script_ia.py")
    result_path = os.path.join(folder, "resultado.json")
    script_path = os.path.join(folder, "prueba.py")
    with open(code_path, "w", encoding="utf-8") as fh:
        fh.write(code)
    with open(script_path, "w", encoding="utf-8") as fh:
        fh.write(_HARNESS.format(copy=copy, code_path=code_path, result_path=result_path))
    if os.path.exists(result_path):
        os.remove(result_path)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        subprocess.run([exe, script_path], timeout=timeout, capture_output=True, creationflags=flags)
    except subprocess.TimeoutExpired:
        return False, ("La prueba aparte tardó más de %d s (¿el script se cuelga?). No se tocó la "
                       "pieza." % timeout)
    if not os.path.exists(result_path):
        return False, "La prueba aparte se cerró sin terminar (FreeCAD se cayó con este script)."
    with open(result_path, encoding="utf-8") as fh:
        result = json.load(fh)
    if result.get("ok"):
        return True, "prueba aparte bien"
    if result.get("error"):
        return False, "En la prueba aparte el script dio error:\n" + result["error"]
    return False, ("En la prueba aparte quedaron operaciones con error: %s"
                   % ", ".join(result.get("bad") or []))


# --- 3. Correr de verdad (hilo principal) ----------------------------------------------


def _namespace(doc):
    import FreeCADGui

    ns = {"__name__": "__main__", "App": FreeCAD, "FreeCAD": FreeCAD, "Gui": FreeCADGui,
          "FreeCADGui": FreeCADGui, "doc": doc}
    for name in ("Part", "PartDesign", "Sketcher", "math"):
        try:
            ns[name] = __import__(name)
        except Exception:
            pass
    return ns


def _invalid(doc):
    return ["%s (%s)" % (o.Label, o.TypeId) for o in doc.Objects
            if "Invalid" in (getattr(o, "State", None) or [])]


def _others_pending(doc, docs_before):
    """¿Otro documento que ya estaba abierto tiene un paso de deshacer en curso (un panel)?"""
    return any(d is not doc and name in docs_before and d.HasPendingTransaction
               for name, d in FreeCAD.listDocuments().items())


def _run(code, title, doc_name, read_only=False):
    doc = FreeCAD.getDocument(doc_name) if doc_name else None
    before = {o.Name for o in doc.Objects} if doc else set()
    bad_before = set(_invalid(doc)) if doc else set()
    undo_before = list(doc.UndoNames) if doc else []
    out = io.StringIO()
    step = "IA: %s" % title
    # Con un panel abierto hay un paso de deshacer pendiente: abrir otro lo cierra y mezcla lo del
    # panel con lo nuestro (visto el 01/11). Una consulta corre sin paso propio; un cambio, no corre.
    pending = bool(doc) and doc.HasPendingTransaction
    if pending and not read_only:
        return {"ok": False, "error": "Hay un panel abierto con cambios sin aceptar: aceptalo o cancelalo antes "
                "de correr un script que cambia la pieza.", "output": "", "undone": False}
    if not read_only:
        log(code, title)
    own = bool(doc) and not pending
    docs_before = set(FreeCAD.listDocuments())
    if own:
        doc.openTransaction(step)
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(code, "<script de la IA>", "exec"), _namespace(doc))
        if not read_only:
            for d in FreeCAD.listDocuments().values():
                d.recompute()
        if own:
            doc.commitTransaction()
            # en 1.1.4 openTransaction abre también el paso de la APLICACIÓN: lo que el script hizo
            # en un documento nuevo quedaba ahí, pendiente, y trababa el script siguiente (#71)
            if not _others_pending(doc, docs_before):  # un panel abierto en otro documento: su paso
                FreeCAD.closeActiveTransaction()        # es suyo (revisión del 12/11)
            for name, d in FreeCAD.listDocuments().items():
                if name not in docs_before and d.HasPendingTransaction:
                    d.commitTransaction()
        # FreeCAD descarta las transacciones vacías: si apareció un paso nuevo, el script cambió algo
        changed = own and new_steps(list(doc.UndoNames), undo_before) not in (0, None)
        if read_only and changed:
            doc.undo()
            doc.recompute()
            return {"ok": False, "error": "El script estaba marcado 'solo leer' pero cambió el "
                    "documento: se deshizo.", "output": out.getvalue()[-MAX_OUTPUT:], "undone": True}
    except BaseException:
        if own:
            try:
                doc.abortTransaction()
                if not _others_pending(doc, docs_before):
                    FreeCAD.closeActiveTransaction(True)
                doc.recompute()
            except Exception:
                pass
        return {"ok": False, "error": traceback.format_exc()[-3000:], "output": out.getvalue()[-MAX_OUTPUT:],
                "undone": own}
    active = FreeCAD.ActiveDocument
    res = {"ok": True, "output": out.getvalue()[-MAX_OUTPUT:],
           "documento": active.Label if active else "", "cambio": changed}
    if doc and not read_only:
        after = {o.Name: o for o in doc.Objects}
        res["nuevos"] = ["%s (%s)" % (o.Label, o.TypeId) for n, o in after.items() if n not in before]
        res["borrados"] = sorted(before - set(after))
        res["con_error"] = [x for x in _invalid(doc) if x not in bad_before]
    return res


# --- Todo junto (lo llama la herramienta, desde el hilo del servidor) --------------------


def _forget_new_backup(prep):
    """El script no cambió nada: el respaldo hecho recién para él no hace falta."""
    if prep.get("new_backup"):
        respaldo.discard_quiet(prep["doc"])
    return {}


def run_safe(code, title="Script de la IA", test=True, read_only=False):
    """Devuelve un dict: ok, mensaje para la IA y detalles."""
    title = (title or "Script de la IA").strip()[:80]
    test = bool(test) and not read_only
    prep = puente.on_gui(lambda: _prepare(read_only, test), timeout=60, name="preparar script")
    if "error" in prep:
        return {"ok": False, "mensaje": "No se pudo preparar el script: %s" % prep["error"]}
    notes = []
    if test:
        ok, report = test_apart(code, prep["copy"])
        if not ok:
            puente.on_gui(lambda: log(code, title, "falló la prueba aparte") or _forget_new_backup(prep),
                          timeout=30, name="registro")
            return {"ok": False, "mensaje": "No se ejecutó (la pieza no se tocó). " + report}
        notes.append(report)
    res = puente.on_gui(lambda: _run(code, title, prep["doc"], read_only), timeout=RUN_TIMEOUT,
                        name="ejecutar_python")
    if "error" in res and "ok" not in res:
        return {"ok": False, "mensaje": "Se trabó o falló al correr en FreeCAD: %s" % res["error"]}
    if not res["ok"]:
        puente.on_gui(lambda: _forget_new_backup(prep), timeout=30, name="respaldo")
        undone = " Se deshizo lo que había hecho." if res.get("undone") else ""
        return {"ok": False, "mensaje": "El script dio error en FreeCAD." + undone, "detalle": res}
    if read_only:
        return {"ok": True, "mensaje": "Listo (solo lectura, no cambió nada).", "detalle": res}
    if res.get("cambio"):
        notes.append("un paso de Ctrl+Z: 'IA: %s'" % title)
        if prep["backup"]:
            notes.append("respaldo de antes de los cambios de la IA (se borra al guardar): %s"
                         % prep["backup"])
    elif prep["doc"]:
        puente.on_gui(lambda: _forget_new_backup(prep), timeout=30, name="respaldo")
        notes.append("no cambió nada en el documento activo (sin paso de deshacer)")
    res["notas"] = notes
    return {"ok": True, "mensaje": "Listo.", "detalle": res}
