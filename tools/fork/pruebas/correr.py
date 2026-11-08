# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Corre la batería de pruebas (ver LEEME.md). Con el Python de FreeCAD:

    D:/Freecad/bin/python.exe tools/fork/pruebas/correr.py            (rápida: FreeCADCmd)
    D:/Freecad/bin/python.exe tools/fork/pruebas/correr.py completa   (rápida + con ventana)
    D:/Freecad/bin/python.exe tools/fork/pruebas/correr.py solo_ventana
    ... correr.py rapida --cobertura      (además, mapa de cobertura en docs/MAPA_PRUEBAS.md)
    ... correr.py prueba_inglete          (solo las pruebas cuyo nombre contiene eso)

Cada prueba corre en su propio FreeCAD (una a la vez, para cuidar la memoria). Las de ventana
usan una COPIA de la configuración del usuario, nunca la suya.

Resultado de cada una: BIEN, FALLA, CONOCIDO (#N: error abierto, no frena) o ARREGLADO? (tenía
CONOCIDO pero ahora pasa: sacarle el CONOCIDO y cerrar la Issue). Sale con código 1 si hay
alguna FALLA o ARREGLADO?, para que el enganche de git frene el commit.

Variables: FW_FREECAD (carpeta bin de FreeCAD, por omisión D:/Freecad/bin), FW_HERRAMIENTAS
(carpeta con coverage y ruff, por omisión %LOCALAPPDATA%/FreeWorks-dev/pkgs).
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(os.path.dirname(os.path.dirname(AQUI)))
BIN = os.environ.get("FW_FREECAD", "D:/Freecad/bin")
HERRAMIENTAS = os.environ.get("FW_HERRAMIENTAS",
                              os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeWorks-dev", "pkgs"))
TIEMPO = {"rapida": 240, "completa": int(os.environ.get("FW_TIEMPO_VENTANA", "600"))}


def tipo(ruta):
    with open(ruta, encoding="utf-8") as fh:
        texto = fh.read()
    m = re.search(r'^TIPO\s*=\s*["\'](\w+)["\']', texto, re.M)
    return m.group(1) if m else "rapida"


def matar(proc):
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def correr_una(ruta, clase, cobertura, tmp):
    nombre = os.path.splitext(os.path.basename(ruta))[0]
    salida = os.path.join(tmp, nombre + ".json")
    env = dict(os.environ, FW_RESULTADO=salida, FW_HERRAMIENTAS=HERRAMIENTAS, PYTHONIOENCODING="utf-8",
               FW_PRUEBA=ruta)
    lanzar = os.path.join(AQUI, "_lanzar.py")
    if cobertura:
        env["FW_COBERTURA"] = os.path.join(tmp, ".coverage." + nombre)
    if clase == "completa":
        cfg_dir = os.path.join(tmp, "cfg_" + nombre)
        os.makedirs(cfg_dir)
        cfg = os.path.join(cfg_dir, "user.cfg")
        propia = os.path.join(os.environ.get("APPDATA", ""), "FreeCAD", "v1-1", "user.cfg")
        if os.path.exists(propia):
            shutil.copy(propia, cfg)
        cmd = [os.path.join(BIN, "freecad.exe"), "-u", cfg, lanzar]
    else:
        cmd = [os.path.join(BIN, "freecadcmd.exe"), lanzar]
    t0 = time.time()
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=AQUI)
    try:
        out, _ = proc.communicate(timeout=TIEMPO[clase])
    except subprocess.TimeoutExpired:
        matar(proc)
        out = b"(se paso de tiempo y se corto)"
    seg = time.time() - t0
    res = None
    if os.path.exists(salida):
        try:
            with open(salida, encoding="utf-8") as fh:
                res = json.load(fh)
        except ValueError:
            res = {"que": "", "conocido": "", "ok": False, "error": "resultado a medio escribir"}
    if res is None:
        res = {"que": "", "conocido": "", "ok": False,
               "error": "no dejo resultado:\n" + out.decode("utf-8", "replace")[-1500:]}
        if os.path.exists(salida + ".log"):
            with open(salida + ".log", encoding="utf-8") as fh:
                res["error"] += "\nregistro de la prueba:\n" + fh.read()
    res["nombre"], res["segundos"] = nombre, round(seg, 1)
    if os.path.exists(salida + ".log"):
        with open(salida + ".log", encoding="utf-8") as fh:
            res["registro"] = fh.read()
    return res


def veredicto(res):
    if res["ok"]:
        return "ARREGLADO?" if res.get("conocido") else "BIEN"
    return "CONOCIDO" if res.get("conocido") else "FALLA"


def mapa_cobertura(tmp):
    sys.path.insert(0, HERRAMIENTAS)
    import coverage
    datos = glob.glob(os.path.join(tmp, ".coverage.*"))
    if not datos:
        return
    cov = coverage.Coverage(data_file=os.path.join(tmp, ".coverage"))
    cov.combine(datos)
    cov.save()
    filas = []
    fork = os.path.join(ADDON, "swui", "fork")
    medidos = {os.path.normcase(m) for m in cov.get_data().measured_files()}
    for ruta in sorted(glob.glob(os.path.join(fork, "**", "*.py"), recursive=True)):
        rel = os.path.relpath(ruta, fork).replace("\\", "/")
        if rel.startswith("ia/terceros"):
            continue
        try:
            _f, ejecutables, _x, faltan, _t = cov.analysis2(ruta)
        except Exception:
            continue
        total = len(ejecutables)
        if not total:
            continue
        hechas = total - len(faltan) if os.path.normcase(ruta) in medidos else 0
        filas.append((rel, total, hechas))
    filas.sort(key=lambda f: (f[2] / f[1], -f[1]))
    total = sum(f[1] for f in filas)
    hechas = sum(f[2] for f in filas)
    lineas = ["# Mapa de pruebas (cobertura)", "",
              "Generado por `tools/fork/pruebas/correr.py --cobertura` el %s. Qué parte del código de "
              "`swui/fork` ejecutó la batería. Es un **mapa** para elegir qué probar, no una meta: que una "
              "línea se ejecute no quiere decir que esté bien probada (`docs/PLAN_CALIDAD.md`, paso 6)."
              % time.strftime("%d/%m/%Y %H:%M"), "",
              "Total: %d de %d líneas (%.0f %%). Módulos sin ninguna línea probada: %d de %d." % (
                  hechas, total, 100.0 * hechas / max(total, 1), sum(1 for f in filas if not f[2]), len(filas)),
              "", "| Módulo | Líneas | Probadas | % |", "|---|---:|---:|---:|"]
    for rel, n, h in filas:
        lineas.append("| `%s` | %d | %d | %.0f |" % (rel, n, h, 100.0 * h / n))
    with open(os.path.join(ADDON, "docs", "MAPA_PRUEBAS.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas) + "\n")
    print("\nMapa de cobertura: docs/MAPA_PRUEBAS.md (%.0f %% de las líneas)" % (100.0 * hechas / max(total, 1)))


def main(args):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # acentos bien en la consola de git
    except Exception:
        pass
    cobertura = "--cobertura" in args
    detalle = "--detalle" in args  # muestra el registro de cada prueba (qué hizo, paso a paso)
    args = [a for a in args if a not in ("--cobertura", "--detalle")]
    modo = "rapida"
    if args and args[0] in ("rapida", "completa", "solo_ventana"):
        modo = args.pop(0)
    filtro = args[0] if args else ""
    pruebas = sorted(glob.glob(os.path.join(AQUI, "prueba_*.py")))
    elegidas = []
    for ruta in pruebas:
        if filtro and filtro not in os.path.basename(ruta):
            continue
        clase = tipo(ruta)
        if (modo == "rapida" and clase != "rapida") or (modo == "solo_ventana" and clase != "completa"):
            continue
        elegidas.append((ruta, clase))
    if not elegidas:
        print("Ninguna prueba para %r (modo %s)." % (filtro, modo))
        return 1
    tmp = tempfile.mkdtemp(prefix="fw_bateria_")
    resultados = []
    for ruta, clase in elegidas:
        res = correr_una(ruta, clase, cobertura, tmp)
        v = veredicto(res)
        resultados.append((v, res))
        extra = (" " + res["conocido"]) if res.get("conocido") else ""
        print("%-11s %-45s %5.1f s%s" % (v, res["nombre"], res["segundos"], extra), flush=True)
        if detalle and res.get("registro"):
            print("    " + res["registro"].strip().replace("\n", "\n    "))
        if v == "FALLA":
            print("    " + res["error"].strip().replace("\n", "\n    "))
        elif v == "CONOCIDO":  # la última línea: que falle por el error conocido y no por otra cosa
            print("    " + res["error"].strip().splitlines()[-1])
    if cobertura:
        mapa_cobertura(tmp)
    malos = [r for v, r in resultados if v in ("FALLA", "ARREGLADO?")]
    cuenta = {}
    for v, _r in resultados:
        cuenta[v] = cuenta.get(v, 0) + 1
    print("\n%d pruebas: %s" % (len(resultados), ", ".join("%s %d" % kv for kv in sorted(cuenta.items()))))
    if any(v == "ARREGLADO?" for v, _r in resultados):
        print("ARREGLADO?: la prueba de un error conocido ahora pasa. Sacarle CONOCIDO y cerrar la Issue.")
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
