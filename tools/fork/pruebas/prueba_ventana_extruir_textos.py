# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#27): en los paneles de Extruir y Extruir corte (nativos, con los términos de
SW) no queda ningún botón ni texto en inglés, en ninguna condición final (p. ej. "Select Face" de
"Hasta la cara")."""
TIPO = "completa"

import FreeCAD  # noqa: E402

from azar_comun import bombear, cinta, croquis, documento, esperar_panel  # noqa: E402

INGLES = ("Select", "Face", "Shape", "Reference", "Direction", "Length", "Offset", "Reversed", "Type",
          "Dimension", "Through", "Two", "Symmetric", "Custom", "Taper", "Clear", "Preview", "Refine")


def _textos(nombre_raiz):
    import FreeCADGui
    from swui.compat import QtWidgets
    mw = FreeCADGui.getMainWindow()
    out = []
    for raiz in mw.findChildren(QtWidgets.QWidget):
        if raiz.objectName().replace("__", "::") != nombre_raiz:
            continue
        for w in raiz.findChildren(QtWidgets.QWidget):
            if not w.isVisible():
                continue
            t = w.text() if hasattr(w, "text") and callable(w.text) and not isinstance(w, QtWidgets.QLineEdit) else ""
            if isinstance(w, QtWidgets.QGroupBox):
                t = w.title()
            if t:
                out.append((w.objectName(), t))
    return out


def _combos(nombre_raiz):
    import FreeCADGui
    from swui.compat import QtWidgets
    mw = FreeCADGui.getMainWindow()
    for raiz in mw.findChildren(QtWidgets.QWidget):
        if raiz.objectName().replace("__", "::") == nombre_raiz:
            return [c for c in raiz.findChildren(QtWidgets.QComboBox) if c.objectName() == "changeMode"]
    return []


def prueba():
    import FreeCADGui
    malos = []
    for comando in ("PartDesign_Pad", "PartDesign_Pocket"):
        doc, body = documento()
        if comando == "PartDesign_Pocket":
            sk0 = croquis(body, rects=[(-20, -20, 40, 40)])
            pad = body.newObject("PartDesign::Pad", "Base")
            pad.Profile = sk0
            pad.Length = 30
            doc.recompute()
        sk = croquis(body, rects=[(0, 0, 10, 10)], z=30 if comando == "PartDesign_Pocket" else 0)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(sk)
        cinta(comando)
        assert esperar_panel(), "no se abrió el panel de %s" % comando
        bombear(800)
        combo = _combos("PartDesignGui::TaskPadPocketParameters")
        assert combo, "no encontré la condición final"
        for i in range(combo[0].count()):
            combo[0].setCurrentIndex(i)
            bombear(1000)
            for nombre, t in _textos("PartDesignGui::TaskPadPocketParameters"):
                if any(p in t for p in INGLES):
                    malos.append("%s / %s: %s = %r" % (comando, combo[0].itemText(i), nombre, t))
        FreeCADGui.Control.closeDialog()
        bombear(300)
        FreeCAD.closeDocument(doc.Name)
        bombear(300)
    assert not malos, "textos en inglés (#27):\n" + "\n".join(sorted(set(malos)))
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
