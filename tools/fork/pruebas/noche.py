# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
La corrida de noche del plan de calidad (paso 8, "tres niveles": de noche, fuzzing y casos al azar
largos). Corre por tandas, una prueba a la vez (memoria de la PC), y para a la hora tope para dejar
la PC libre a la mañana:

  1. batería rápida (como en cada commit);
  2. pruebas al azar sin ventana, con muchos casos;
  3. reglas de paneles, medidas al azar con ventana y capturas de referencia;
  4. el mono (secuencias) y el fuzzing de campos, con muchos casos y seguidillas largas;
  5. el mapa de cobertura de todo FreeWorks (al informe de la noche, no a docs/);
  6. si sobra tiempo, más vueltas del mono (cada vuelta, valores nuevos), hasta la hora tope.

La hora tope llega a cada prueba (FW_HORA_TOPE): ninguna arranca ni sigue después. Si igual una
tanda se pasa, se corta con todo lo que lanzó (taskkill /T), así no queda ningún FreeCAD abierto.
Si arranca más de 14 h antes de la hora tope (p. ej. la tarea programada corrió tarde a la mañana),
no corre nada.

No arregla nada, no hace commit ni push, no abre Issues: deja un informe en
%LOCALAPPDATA%/FreeWorks-dev/noche/<fecha_hora>.md (resumen arriba, el detalle de cada tanda abajo)
que Claude lee a la mañana para registrar lo encontrado en las Issues.

    D:/Freecad/bin/python.exe tools/fork/pruebas/noche.py            (hasta las 07:30)
    ... noche.py --hasta 06:00 --prueba                             (--prueba: tandas cortas, para ver que anda)
    ... noche.py --prueba --sin-ventana                             (solo lo que no abre ventanas)

Variables: FW_NOCHE_CASOS (casos al azar sin ventana, 300), FW_NOCHE_MONO (seguidillas por regla, 30),
FW_NOCHE_LARGO (largo máximo de una seguidilla, 15).
"""

import datetime
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
SALIDA = os.path.join(os.environ.get("LOCALAPPDATA", ""), "FreeWorks-dev", "noche")
MAX_ANTES = 14 * 3600   # más de esto antes de la hora tope: no es "de noche", no corre
MAX_VUELTAS = 12        # vueltas extra del mono, como mucho


def _hora_tope(texto):
    h, m = [int(x) for x in texto.split(":")]
    ahora = datetime.datetime.now()
    tope = ahora.replace(hour=h, minute=m, second=0, microsecond=0)
    if tope <= ahora:
        tope += datetime.timedelta(days=1)
    return tope


def _matar_arbol(proc):
    """Corta correr.py y todo lo que lanzó (el FreeCAD de la prueba), antes de que quede huérfano."""
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


class Noche:
    def __init__(self, tope, corta=False, sin_ventana=False):
        self.tope = tope
        self.corta = corta
        self.sin_ventana = sin_ventana
        os.makedirs(SALIDA, exist_ok=True)
        self.base = os.path.join(SALIDA, datetime.datetime.now().strftime("%Y-%m-%d_%H%M"))
        self.archivo = self.base + ".md"
        self.resumen = []
        self.detalle = []

    def queda(self):
        return (self.tope - datetime.datetime.now()).total_seconds()

    def tanda(self, titulo, args, env_extra, minimo=600):
        """Corre correr.py con esos argumentos si queda tiempo; anota el resultado. Devuelve cuántas
        pruebas dieron resultado (0: no corrió o no anduvo)."""
        if self.sin_ventana and ("solo_ventana" in args or "completa" in args):
            self.resumen.append("- %s: no corrió (--sin-ventana)" % titulo)
            return 0
        if self.queda() < minimo:
            self.resumen.append("- %s: **no corrió** (no quedaba tiempo antes de las %s)" % (titulo, self.tope.strftime("%H:%M")))
            return 0
        env = dict(os.environ, **env_extra)
        env["FW_HORA_TOPE"] = str(time.time() + self.queda())
        env.setdefault("FW_TIEMPO_VENTANA", "900")
        t0 = time.time()
        proc = subprocess.Popen([PY, os.path.join(AQUI, "correr.py")] + args + ["--detalle"], env=env, cwd=AQUI,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        cortada = False
        try:
            out, _ = proc.communicate(timeout=max(60, self.queda() - 30))
        except subprocess.TimeoutExpired:
            _matar_arbol(proc)
            out, _ = proc.communicate()
            cortada = True
        texto = (out or b"").decode("utf-8", errors="replace")
        minutos = (time.time() - t0) / 60.0
        lineas = [l for l in texto.splitlines() if l[:11].strip() in ("BIEN", "FALLA", "CONOCIDO", "ARREGLADO?")]
        malas = [l for l in lineas if l.startswith(("FALLA", "ARREGLADO?"))]
        ultima = [l for l in texto.splitlines() if " pruebas: " in l]
        estado = ultima[-1].strip() if ultima else "sin resultado"
        if cortada:
            empezadas = [l.split()[-1] for l in texto.splitlines() if l.startswith("EMPIEZA")]
            estado = "**cortada por la hora tope**%s; %d pruebas con resultado" % (
                " (se colgó en %s)" % empezadas[-1] if empezadas else "", len(lineas))
        self.resumen.append("- %s (%.0f min): %s%s" % (titulo, minutos, estado,
                                                       "".join("\n  - %s" % m.strip() for m in malas)))
        deudas = sorted({l.strip() for l in texto.splitlines() if "(deuda #" in l})
        if deudas:
            self.resumen.append("  - deudas vistas (errores ya registrados): %d" % len(deudas))
        self.detalle.append("\n## %s\n\n```\n%s\n```\n" % (titulo, texto[-60000:]))
        self.guardar()
        return len(lineas)

    def guardar(self):
        with open(self.archivo, "w", encoding="utf-8") as fh:
            fh.write("# Corrida de noche %s\n\nHora tope: %s. Una prueba a la vez.\n\n## Resumen\n\n%s\n%s"
                     % (datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), self.tope.strftime("%H:%M"),
                        "\n".join(self.resumen), "".join(self.detalle)))

    def correr(self):
        if self.queda() > MAX_ANTES:
            self.resumen.append("No corrió: faltaban más de %d h para la hora tope (%s); no es de noche."
                                % (MAX_ANTES // 3600, self.tope.strftime("%H:%M")))
            self.guardar()
            print(self.archivo)
            return
        c = self.corta
        casos = "4" if c else os.environ.get("FW_NOCHE_CASOS", "300")
        mono = "2" if c else os.environ.get("FW_NOCHE_MONO", "30")
        largo = "5" if c else os.environ.get("FW_NOCHE_LARGO", "15")
        self.tanda("1. Batería rápida", ["rapida"], {}, minimo=300)
        self.tanda("2. Al azar sin ventana", ["solo_azar"], {"FW_CASOS_AZAR": casos})
        self.tanda("3a. Reglas de paneles", ["solo_ventana", "reglas"], {"FW_SEMILLAS": "1" if c else "3"})
        # con 40 casos, las de pieza y ensamblaje (8-10 reglas) no entran en 15 min (Issue #70)
        self.tanda("3b. Medidas al azar con ventana", ["solo_ventana", "ventana_azar"],
                   {"FW_CASOS_AZAR": "2" if c else "40", "FW_TIEMPO_VENTANA": "2400"})
        self.tanda("3c. Capturas de referencia", ["solo_ventana", "capturas"], {})
        largas = {"FW_TIEMPO_VENTANA": "2400"}  # el mono largo necesita más que los 15 min de las demás
        self.tanda("4a. El mono", ["solo_ventana", "mono"], dict(largas, FW_CASOS_AZAR=mono, FW_LARGO_MONO=largo))
        self.tanda("4b. Fuzzing de campos", ["solo_ventana", "campos"], {"FW_CASOS_CAMPOS": "1" if c else "6", "FW_TIEMPO_VENTANA": "5400"})
        if not c:
            mapa = {"FW_CASOS_AZAR": "2", "FW_MAPA": self.base + "_mapa_cobertura.md"}
            if self.sin_ventana:
                self.tanda("5. Mapa de cobertura (sin ventana)", ["sin_ventana", "--cobertura"], mapa, minimo=1800)
            else:
                self.tanda("5. Mapa de cobertura de todo FreeWorks", ["completa", "--cobertura"], mapa, minimo=5400)
        vuelta = 2
        while not c and not self.sin_ventana and self.queda() > 3600 and vuelta <= MAX_VUELTAS + 1:
            t0 = time.time()
            n = self.tanda("6. El mono, vuelta %d" % vuelta, ["solo_ventana", "mono"],
                           dict(largas, FW_CASOS_AZAR=mono, FW_LARGO_MONO=largo), minimo=3600)
            if n == 0 or time.time() - t0 < 300:  # no anduvo (FreeCAD no arranca...): no insistir
                self.resumen.append("- (las vueltas del mono se cortaron: la última no dio resultado o duró menos de 5 min)")
                break
            vuelta += 1
        self.resumen.append("\nTerminó a las %s." % datetime.datetime.now().strftime("%H:%M"))
        self.guardar()
        print(self.archivo)


def main(args):
    hasta = "07:30"
    if "--hasta" in args:
        hasta = args[args.index("--hasta") + 1]
    Noche(_hora_tope(hasta), corta="--prueba" in args, sin_ventana="--sin-ventana" in args).correr()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
