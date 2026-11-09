# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Los errores que las pruebas toleran ("conocidos" y "deudas") siguen abiertos en GitHub. Las pruebas
dejan pasar un error ya registrado para seguir buscando otros (CONOCIDO = "#N", conocido="#N" en
Fallas.correr, DEUDA de las reglas de paneles, deuda / deuda_pasos del mono...). Si esa Issue se
cerró (se arregló, o se descartó) y la prueba la sigue tolerando, la prueba quedó tapando algo que
ya no debería pasar: esta prueba lo avisa, con el archivo y el número.
También avisa si un número no existe en el repositorio.
Necesita internet (consulta GitHub con `gh`); sin conexión, falla diciéndolo (no pasa callada)."""
TIPO = "azar"

import glob  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402

from _base import traza  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = "wally88ar-coder/FreeWorks"
# un número de Issue: "#12", "~#40" (intermitente), "#6 #19"; no un color con letras ("#1E90FF"); un color solo
# de dígitos ("#333") no se puede distinguir: en las pruebas no hay colores
NUMERO = re.compile(r"~?#(\d+)(?![0-9A-Fa-f])")


def referencias():
    """{número: [archivos]} de los números de Issue que aparecen en los TEXTOS del código (no en
    comentarios), leídos con tokenize (textos de varias líneas, comillas escapadas...)."""
    import io
    import tokenize
    out = {}
    for ruta in sorted(glob.glob(os.path.join(AQUI, "**", "*.py"), recursive=True)):
        nombre = os.path.relpath(ruta, AQUI)
        if os.path.basename(ruta) == os.path.basename(__file__):
            continue
        with open(ruta, encoding="utf-8") as fh:
            fuente = fh.read()
        try:
            fichas = list(tokenize.generate_tokens(io.StringIO(fuente).readline))
        except (tokenize.TokenError, SyntaxError):
            continue
        previas = []  # las fichas significativas anteriores
        saltear = {tokenize.NL, tokenize.COMMENT, tokenize.ENCODING}
        for f in fichas:
            if f.type in saltear:
                continue
            if f.type == tokenize.STRING:
                anterior = previas[-1] if previas else None
                # las descripciones no toleran nada (cuentan historia: "Issue #28, arreglado"): el
                # QUE = """...""" y los textos que van solos en su renglón (explicación de una función)
                es_descripcion = (anterior is None or anterior.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)
                                  or (len(previas) >= 2 and previas[-1].string == "=" and previas[-2].string == "QUE"))
                if not es_descripcion:
                    for n in NUMERO.findall(f.string):
                        out.setdefault(int(n), set()).add(nombre)
            previas.append(f)
    return out


def estados():
    """{número: "OPEN"/"CLOSED"} de todas las Issues del repositorio."""
    try:
        r = subprocess.run(["gh", "issue", "list", "--repo", REPO, "--state", "all", "--limit", "1000",
                            "--json", "number,state"], capture_output=True, timeout=60)
    except Exception as exc:
        raise AssertionError("no se pudo consultar GitHub (¿sin internet o sin gh?): %s" % exc)
    if r.returncode != 0:
        raise AssertionError("no se pudo consultar GitHub: %s" % r.stderr.decode("utf-8", "replace")[:300])
    return {d["number"]: d["state"] for d in json.loads(r.stdout.decode("utf-8"))}


def prueba():
    refs = referencias()
    assert refs, "no encontré ningún error conocido en las pruebas (¿cambió cómo se escriben?)"
    est = estados()
    problemas = []
    for n in sorted(refs):
        donde = ", ".join(sorted(refs[n]))
        if n not in est:
            problemas.append("#%d no existe en GitHub (aparece en %s)" % (n, donde))
        elif est[n] != "OPEN":
            problemas.append("#%d está cerrada pero %s la sigue tolerando: sacar el conocido o la deuda" % (n, donde))
    traza("  %d errores conocidos en las pruebas: %s" % (len(refs), " ".join("#%d" % n for n in sorted(refs))))
    assert not problemas, "\n".join(problemas)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
