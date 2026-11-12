# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#24): al abrir un archivo con varios Cuerpos, el árbol NO los despliega todos
(antes cada Cuerpo leído del archivo se tomaba como nuevo y se abría con su Origen). Un Cuerpo
nuevo hecho a mano sí se abre (como antes)."""
TIPO = "completa"

import os  # noqa: E402
import tempfile  # noqa: E402

import FreeCAD  # noqa: E402

from comun import caja  # noqa: E402


def _abiertos(doc):
    """Etiquetas de los Cuerpos de doc que están desplegados en el árbol."""
    import FreeCADGui
    from swui.compat import QtWidgets
    nombres = {o.Label for o in doc.Objects if o.TypeId == "PartDesign::Body"}
    out = set()
    for tree in FreeCADGui.getMainWindow().findChildren(QtWidgets.QTreeWidget):
        it = QtWidgets.QTreeWidgetItemIterator(tree)
        while it.value():
            item = it.value()
            if item.text(0) in nombres and item.isExpanded():
                out.add(item.text(0))
            it += 1
    return out


def prueba():
    import FreeCADGui
    doc = FreeCAD.newDocument("VariosCuerpos")
    for i in range(3):
        body = doc.addObject("PartDesign::Body", "Cuerpo")
        caja(body, "Caja", 10, 10, 10, FreeCAD.Vector(20 * i, 0, 0))
    doc.recompute()
    yield 800
    for body in [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]:
        FreeCADGui.getDocument(doc.Name).toggleTreeItem(body, 1)  # 1 = cerrar
    yield 300
    ruta = os.path.join(tempfile.mkdtemp(), "varios.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    yield 500
    doc = FreeCAD.openDocument(ruta)
    yield 1500
    abiertos = _abiertos(doc)
    assert not abiertos, "al abrir se desplegaron: %s (#24)" % sorted(abiertos)
    nuevo = doc.addObject("PartDesign::Body", "Nuevo")
    yield 1000
    assert nuevo.Label in _abiertos(doc), "un Cuerpo nuevo ya no se abre en el árbol"
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
