# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#22, chapa): copiar y pegar (Ctrl+C, Ctrl+V) una chapa con su desarrollo deja una
copia independiente, como SW: el desarrollo pegado es de la chapa pegada (no del original), elegir
el desarrollo pegado trabaja sobre la chapa pegada, el original sigue con su desarrollo, y
desplegar la copia no crea un segundo desarrollo."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from casos_grupo3 import _SobreBrida  # noqa: E402


def prueba():
    import FreeCADGui
    from swui.fork import sheet_metal as sm
    from swui.fork import sheet_panels as sp
    doc = FreeCAD.newDocument("CopiarChapa")
    chapa = _SobreBrida()
    yield from chapa.preparar(doc)
    body = chapa.body
    flat = sm.ensure_flat(body, sketches=False)
    doc.recompute()
    assert flat is not None and sm.flat_of(body) is flat, "no se armó el desarrollo"
    antes = set(o.Name for o in doc.Objects)

    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(body)
    FreeCADGui.Selection.addSelection(flat)
    # FreeCAD pregunta al copiar o pegar (dependencias...): se anota y se contesta como el usuario
    from PySide import QtCore, QtWidgets
    from _base import traza
    vistos = []

    def contestar():
        w = QtWidgets.QApplication.activeModalWidget()
        if w is None:
            return
        texto = w.text() if hasattr(w, "text") else w.windowTitle()
        vistos.append(texto)
        traza("    pregunta: %s | botones: %s" % (texto[:200], [b.text() for b in w.findChildren(QtWidgets.QAbstractButton)]))
        si = [b for b in w.findChildren(QtWidgets.QAbstractButton) if b.text().replace("&", "") in ("Yes", "Sí", "Si", "OK", "Aceptar")]
        (si[0].click() if si else w.reject())
    vigia = QtCore.QTimer()
    vigia.timeout.connect(contestar)
    vigia.start(700)
    FreeCADGui.runCommand("Std_Copy")
    yield 1500
    FreeCADGui.runCommand("Std_Paste")
    yield 3000
    vigia.stop()
    doc.recompute()
    nuevos = [doc.getObject(n) for n in set(o.Name for o in doc.Objects) - antes]
    cuerpos = [o for o in nuevos if o.TypeId == "PartDesign::Body"]
    flats = [o for o in nuevos if sm.kind(o) == "flat"]
    assert len(cuerpos) == 1 and len(flats) == 1, "no se pegaron chapa y desarrollo: %s" % [o.Name for o in nuevos]
    copia, flat2 = cuerpos[0], flats[0]

    assert sm.flat_body(flat2) is copia, "el desarrollo pegado sigue siendo del original (#22)"
    assert sm.flat_of(copia) is flat2, "la chapa pegada no reconoce su desarrollo"
    assert sm.flat_of(body) is flat, "el original perdió su desarrollo"
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(flat2)
    assert sp.target_body(doc, quiet=True) is copia, "elegir el desarrollo pegado trabaja sobre el original (#22)"
    FreeCADGui.Selection.clearSelection()
    n_flats = len([o for o in doc.Objects if sm.kind(o) == "flat"])
    assert sm.ensure_flat(copia, sketches=False) is flat2, "desplegar la copia armó otro desarrollo"
    doc.recompute()
    assert len([o for o in doc.Objects if sm.kind(o) == "flat"]) == n_flats, "quedó un desarrollo de más"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
