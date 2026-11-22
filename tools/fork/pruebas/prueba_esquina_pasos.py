# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Esquina de confirmación, Cancelar croquis (revisión del 21/11): cuántos pasos deshacer para volver a la pila de
deshacer de cuando se abrió el croquis. Exacto; con la pila en su tope (FreeCAD descartó los más viejos) alcanza con
el comienzo; si dentro del croquis se deshizo algo de antes de abrirlo, NO hay número (no se deshace nada, en vez de
seguir hasta el fondo); nombres repetidos no cortan antes de tiempo."""
from _base import traza  # noqa: E402


def prueba():
    from swui.fork.confirm_corner import steps_back
    base = ["Croquis", "Extruir", "Croquis previo"]
    casos = [
        (["Add line", "Add line"] + base, base, 20, 2),
        (base, base, 20, 0),
        ([], [], 20, 0),
        (["Add line"], [], 20, 1),
        # deshizo uno de más dentro del croquis (Extruir ya no está): no se puede
        (["Add line", "Croquis previo"], base, 20, None),
        (["Extruir", "Croquis previo"], base, 20, None),
        # nombres repetidos: "Add line" también estaba en la base; tiene que ser exacto
        (["Add line", "Add line", "Add line", "Extruir"], ["Add line", "Extruir"], 20, 2),
        # tope de 5: los dos más viejos de la base se descartaron
        (["Add line", "Add line", "Add line", "Croquis", "Extruir"], base, 5, 3),
        # tope: sin la base entera y sin estar llena, no vale
        (["Add line", "Croquis"], base, 5, None),
    ]
    for now, target, cap, quiero in casos:
        k = steps_back(now, target, cap)
        traza("  %s -> %s (quiero %s)" % (now, k, quiero))
        assert k == quiero, "steps_back(%s, %s, %d) = %s, quiero %s" % (now, target, cap, k, quiero)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
