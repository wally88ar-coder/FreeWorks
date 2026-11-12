# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#71 (puente IA): un script de 'ejecutar_python' que crea un documento nuevo y le agrega objetos,
con otro documento activo, no deja ningún paso de deshacer pendiente (ni en el documento nuevo ni en
la aplicación): el script siguiente que cambia ese documento corre sin el aviso de "panel abierto"."""

import FreeCAD  # noqa: E402


def prueba():
    from swui.fork.ia.nucleo import ejecutar as ej
    activo = FreeCAD.newDocument("Activo")
    FreeCAD.setActiveDocument(activo.Name)
    codigo = ("import FreeCAD as App\n"
              "d = App.newDocument('NuevoIA')\n"
              "d.addObject('Part::Box', 'Caja')\n"
              "d.recompute()\n")
    res = ej._run(codigo, "documento nuevo", activo.Name)
    assert res.get("ok"), res.get("error")
    nuevo = [d for d in FreeCAD.listDocuments().values() if d.Label.startswith("NuevoIA")]
    assert nuevo, "el script no creó el documento"
    nuevo = nuevo[0]
    assert not nuevo.HasPendingTransaction, "el documento nuevo quedó con un paso abierto (#71)"
    assert not FreeCAD.getActiveTransaction(), "quedó abierto el paso de la aplicación (#71): %s" % (
        FreeCAD.getActiveTransaction(),)
    res = ej._run("import FreeCAD as App\nApp.getDocument('%s').getObject('Caja').Length = 20\n" % nuevo.Name,
                  "cambiar", nuevo.Name)
    assert res.get("ok"), "el script siguiente no corrió: %s" % res.get("error")
    FreeCAD.closeDocument(nuevo.Name)
    FreeCAD.closeDocument(activo.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
