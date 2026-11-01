# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
"Python seguro": correr un script escrito por la IA sin arriesgar la pieza.

Pasos (idea tomada de ghbalf/freecad-ai, core/executor.py; código propio):
1. En el hilo principal: copia de respaldo del documento activo (`saveCopy`, no cambia el
   archivo del usuario) y el script escrito en la consola de Python como registro.
2. Fuera del hilo principal: la misma copia se abre en un FreeCAD aparte sin pantalla
   (freecadcmd) y se corre el script ahí. Si da error, deja una operación con error o se cuelga
   (corte por tiempo que sí anda en Windows), no se toca la pieza del usuario.
3. En el hilo principal: el script corre de verdad como UN paso de Ctrl+Z ("IA: <título>").
   Si falla a mitad, se deshace solo.

Límite: la prueba aparte no tiene parte visual (colores, vistas): esos cambios no se prueban.
"""

import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import traceback

import FreeCAD

from swui.fork.ia.nucleo import config, puente

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


def _safe(text):
    return re.sub(r"[^\w.-]+", "_", text or "documento").strip("_")[:40] or "documento"


# --- 1. Preparar (hilo principal) ------------------------------------------------------


def _prepare(code, title):
    doc = FreeCAD.ActiveDocument
    copy = ""
    if doc is not None and doc.Objects:
        folder = os.path.join(config.data_dir(), "respaldos")
        os.makedirs(folder, exist_ok=True)
        tag = hashlib.sha1((doc.FileName or doc.Name).encode("utf-8")).hexdigest()[:8]
        copy = os.path.join(folder, "%s.%s.FCStd" % (_safe(doc.Label), tag))
        doc.saveCopy(copy)  # el documento del usuario sigue con su nombre y su archivo
    return {"doc": doc.Name if doc is not None else "", "copy": copy}


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


def _run(code, title, doc_name):
    doc = FreeCAD.getDocument(doc_name) if doc_name else None
    before = {o.Name for o in doc.Objects} if doc else set()
    bad_before = set(_invalid(doc)) if doc else set()
    out = io.StringIO()
    log(code, title)
    if doc:
        doc.openTransaction("IA: %s" % title)
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(code, "<script de la IA>", "exec"), _namespace(doc))
        for d in FreeCAD.listDocuments().values():
            d.recompute()
        if doc:
            doc.commitTransaction()
    except BaseException:
        if doc:
            try:
                doc.abortTransaction()
                doc.recompute()
            except Exception:
                pass
        return {"ok": False, "error": traceback.format_exc()[-3000:], "output": out.getvalue()[-MAX_OUTPUT:],
                "undone": bool(doc)}
    active = FreeCAD.ActiveDocument
    res = {"ok": True, "output": out.getvalue()[-MAX_OUTPUT:],
           "documento": active.Label if active else ""}
    if doc:
        after = {o.Name: o for o in doc.Objects}
        res["nuevos"] = ["%s (%s)" % (o.Label, o.TypeId) for n, o in after.items() if n not in before]
        res["borrados"] = sorted(before - set(after))
        res["con_error"] = [x for x in _invalid(doc) if x not in bad_before]
    return res


# --- Todo junto (lo llama la herramienta, desde el hilo del servidor) --------------------


def run_safe(code, title="Script de la IA", test=True):
    """Devuelve un dict: ok, mensaje para la IA y detalles."""
    title = (title or "Script de la IA").strip()[:80]
    prep = puente.on_gui(lambda: _prepare(code, title), timeout=60, name="preparar script")
    if "error" in prep:
        return {"ok": False, "mensaje": "No se pudo preparar el script: %s" % prep["error"]}
    notes = []
    if test:
        ok, report = test_apart(code, prep["copy"])
        if not ok:
            puente.on_gui(lambda: log(code, title, "falló la prueba aparte") or {}, timeout=30, name="registro")
            return {"ok": False, "mensaje": "No se ejecutó (la pieza no se tocó). " + report}
        notes.append(report)
    res = puente.on_gui(lambda: _run(code, title, prep["doc"]), timeout=RUN_TIMEOUT, name="ejecutar_python")
    if "error" in res and "ok" not in res:
        return {"ok": False, "mensaje": "Se trabó o falló al correr en FreeCAD: %s" % res["error"]}
    if not res["ok"]:
        undone = " Se deshizo lo que había hecho." if res.get("undone") else ""
        return {"ok": False, "mensaje": "El script dio error en FreeCAD." + undone, "detalle": res}
    if prep["copy"]:
        notes.append("respaldo previo: %s" % prep["copy"])
    if prep["doc"]:
        notes.append("un paso de Ctrl+Z: 'IA: %s'" % title)
    res["notas"] = notes
    return {"ok": True, "mensaje": "Listo.", "detalle": res}
