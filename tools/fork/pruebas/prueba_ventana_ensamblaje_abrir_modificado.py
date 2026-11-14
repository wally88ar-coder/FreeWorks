# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#79): un ensamblaje con dos piezas, guardado, cerrado y abierto de nuevo sin
tocar nada, NO queda como modificado (no pregunta si guardar al cerrarlo). Como SW: si una pieza se
cambió y se guardó con el ensamblaje cerrado, al abrirlo SÍ queda para guardar."""
TIPO = "completa"

import os  # noqa: E402
import tempfile  # noqa: E402

import FreeCAD  # noqa: E402

from casos_ensamblaje2 import TaladroEnsamblaje  # noqa: E402


def prueba():
    import FreeCADGui
    doc = FreeCAD.newDocument("Conjunto")
    caso = TaladroEnsamblaje()
    yield from caso.preparar(doc)
    doc = caso.doc
    ruta = doc.FileName
    if not ruta:
        ruta = os.path.join(tempfile.mkdtemp(), "conj.FCStd")
        doc.saveAs(ruta)
    for d in FreeCAD.listDocuments().values():
        if d.FileName:
            d.save()
    yield 1000
    FreeCAD.closeDocument(doc.Name)
    yield 800
    doc = FreeCAD.openDocument(ruta)
    yield 3000
    assert not FreeCADGui.getDocument(doc.Name).Modified, "el ensamblaje quedó modificado al abrirlo (#79)"
    # abrir en su ventana una pieza que el ensamblaje ya tiene cargada: el ensamblaje no cambia (SW)
    from swui.fork import open_clean
    cambios = []

    class _Obs:
        def slotChangedObject(self, obj, prop):
            if obj.Document is doc:
                cambios.append("%s.%s" % (obj.Name, prop))
    obs = _Obs()
    FreeCAD.addDocumentObserver(obs)
    try:
        for d in open_clean._linked_docs(doc):
            FreeCAD.openDocument(d.FileName)
            yield 1500
    finally:
        FreeCAD.removeDocumentObserver(obs)
    assert not FreeCADGui.getDocument(doc.Name).Modified, \
        "abrir una pieza en su ventana dejó el ensamblaje modificado (#79); cambió: %s" % sorted(set(cambios))[:12]
    # y si después se CAMBIA la pieza en su ventana, el ensamblaje sí queda para guardar
    pieza = [d for d in open_clean._linked_docs(doc) if d.getObject("Caja") is not None][-1]
    caja = pieza.getObject("Caja")
    caja.Length = float(caja.Length.Value) + 5
    pieza.recompute()
    doc.recompute()
    yield 1500
    assert FreeCADGui.getDocument(doc.Name).Modified, "con la pieza cambiada, el ensamblaje no quedó para guardar"
    # una pieza cambiada (y guardada) con el ensamblaje cerrado: queda para guardar, como SW
    from swui.fork import open_clean
    archivos = [d.FileName for d in open_clean._linked_docs(doc)]
    assert archivos, "el ensamblaje de la prueba no usa piezas de otro archivo"
    for d in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(d.Name)
    yield 2500  # después del margen de "guardar todo"
    pieza = FreeCAD.openDocument(archivos[0])
    pieza.Objects[0].Label = pieza.Objects[0].Label + " cambiada"
    pieza.save()
    FreeCAD.closeDocument(pieza.Name)
    yield 500
    doc = FreeCAD.openDocument(ruta)
    yield 3000
    assert FreeCADGui.getDocument(doc.Name).Modified, "con una pieza cambiada, al abrir no quedó para guardar"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
