# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#85: al reparar una relación cuya cara cambió, FreeWorks busca "la más parecida". Como SW, nunca
la pasa a una cara (o eje) girado: la del frente de una placa no puede pasar a la de arriba aunque
sea la única plana que queda. Sí sigue a la misma cara corrida (pieza más gruesa) o agujereada."""

FRENTE = {"t": "Face", "g": "plane", "n": [0, -1, 0], "p": [50, 0, 5], "s": 1000.0}
ARRIBA = {"t": "Face", "g": "plane", "n": [0, 0, 1], "p": [50, 30, 10], "s": 6000.0}
FRENTE_AGUJEREADA = {"t": "Face", "g": "plane", "n": [0, -1, 0], "p": [48, 0, 5], "s": 950.0}
FRENTE_CORRIDA = {"t": "Face", "g": "plane", "n": [0, -1, 0], "p": [50, -5, 5], "s": 1000.0}
EJE = {"t": "Face", "g": "cylinder", "d": [0, 0, 1], "c": [0, 0, 0], "r": 5.0, "p": [5, 0, 0]}
EJE_ACOSTADO = {"t": "Face", "g": "cylinder", "d": [1, 0, 0], "c": [0, 0, 0], "r": 5.0, "p": [0, 5, 0]}
EJE_DADO_VUELTA = {"t": "Face", "g": "cylinder", "d": [0, 0, -1], "c": [0, 0, 0], "r": 5.0, "p": [5, 0, 0]}


def prueba():
    from swui.fork import mate_refs as mr
    assert mr.best_match(FRENTE, [("Face6", ARRIBA)]) == (None, None), \
        "la cara del frente pasó a la de arriba (girada 90°) (#85)"
    assert mr.best_match(FRENTE, [("Face6", ARRIBA), ("Face9", FRENTE_AGUJEREADA)])[0] == "Face9", \
        "no siguió a la cara del frente agujereada"
    assert mr.best_match(FRENTE, [("Face6", ARRIBA), ("Face2", FRENTE_CORRIDA)])[0] == "Face2", \
        "no siguió a la cara del frente corrida (pieza más gruesa)"
    assert mr.best_match(EJE, [("Face3", EJE_ACOSTADO)]) == (None, None), \
        "un eje vertical pasó a uno acostado (#85)"
    assert mr.best_match(EJE, [("Face3", EJE_DADO_VUELTA)])[0] == "Face3", \
        "un eje dado vuelta (mismo eje, otro sentido) dejó de contar como el mismo"
    # una pieza real tiene caras de todos los tipos: las de otro tipo se descartan sin reventar
    # (revisión del 14/11: un cilindro no tiene normal "n", una cara plana no tiene eje "d")
    OTRA = {"t": "Face", "g": "other", "p": [0, 0, 0], "s": 5.0}
    ARISTA = {"t": "Edge", "g": "line", "d": [1, 0, 0], "c": [0, 0, 0], "s": 10.0}
    todas = [("Face1", EJE), ("Face2", OTRA), ("Face6", ARRIBA), ("Face9", FRENTE_AGUJEREADA), ("Edge1", ARISTA)]
    assert mr.best_match(FRENTE, todas)[0] == "Face9", "con caras de otros tipos no siguió a la del frente"
    assert mr.best_match(EJE, [("Face6", ARRIBA), ("Face2", OTRA), ("Face3", EJE_DADO_VUELTA)])[0] == "Face3", \
        "con caras planas al lado no siguió al eje"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
