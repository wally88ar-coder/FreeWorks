# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Las piezas comunes (`swui/fork/safe_ops.py`) hacen lo que dicen:
- borrar una operación del medio de un Cuerpo no deja a la siguiente sin base, y borrar la punta
  pasa la punta a la anterior;
- borrar un Cuerpo entero con `remove_feature` da error (dejaría sus operaciones sueltas);
- `undo_step` sin nada abierto deja un paso de deshacer propio; con una transacción en curso, aun
  VACÍA, se suma a esa (no la confirma); dos anidados dan un solo paso; si algo falla adentro, se
  anula;
- `doc_key` guarda la ruta del archivo y `find_doc` la encuentra, también con dos "Placa.FCStd"
  de carpetas distintas abiertos a la vez;
- `QuietObserver.busy` está prendido mientras FreeCAD abre un archivo."""

import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from comun import V, caja, cerca  # noqa: E402


def prueba():
    from swui.fork import safe_ops
    doc = FreeCAD.newDocument("Comunes")
    doc.UndoMode = 1
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    caja(body, "Caja", 10, 10, 10)
    corte = body.newObject("PartDesign::SubtractiveCylinder", "Corte")
    corte.Radius, corte.Height = 2, 20
    caja(body, "Caja2", 10, 10, 10, V(10, 0, 0))
    doc.recompute()
    # borrar del medio
    safe_ops.remove_feature(corte)
    doc.recompute()
    assert cerca(body.Shape.Volume, 2000), "borrar del medio dejó %.1f" % body.Shape.Volume
    assert doc.getObject("Caja2").BaseFeature.Name == "Caja"
    # borrar la punta
    safe_ops.remove_feature(doc.getObject("Caja2"))
    doc.recompute()
    assert body.Tip.Name == "Caja" and cerca(body.Shape.Volume, 1000), (body.Tip.Name, body.Shape.Volume)

    try:
        safe_ops.remove_feature(body)
        raise AssertionError("borró un Cuerpo entero")
    except ValueError:
        pass

    caja_ = doc.getObject("Caja")
    # paso propio
    n = doc.UndoCount
    with safe_ops.undo_step(doc, "Largo") as propio:
        caja_.Length = 12
    assert propio and doc.UndoCount == n + 1 and doc.UndoNames[0] == "Largo", (propio, doc.UndoNames)
    # dentro de otra transacción: no la confirma
    doc.openTransaction("Panel")
    caja_.Width = 12
    with safe_ops.undo_step(doc, "Material") as propio:
        caja_.Height = 12
    assert not propio and doc.HasPendingTransaction, "confirmó la transacción del panel"
    doc.abortTransaction()
    assert cerca(caja_.Width, 10) and cerca(caja_.Height, 10), "Cancelar del 'panel' no deshizo todo"
    # transacción ajena abierta y VACÍA (un panel que todavía no cambió nada): se suma
    doc.openTransaction("Panel vacío")
    with safe_ops.undo_step(doc, "Material") as propio:
        caja_.Height = 14
    caja_.Width = 14
    doc.abortTransaction()
    assert not propio, "abrió un paso propio y cerró la transacción vacía del 'panel'"
    assert cerca(caja_.Width, 10) and cerca(caja_.Height, 10), "Cancelar del 'panel' vacío no deshizo"
    # dos anidados: un solo paso, con todo adentro
    n = doc.UndoCount
    with safe_ops.undo_step(doc, "Afuera"):
        with safe_ops.undo_step(doc, "Adentro") as propio:
            caja_.Width = 11
        caja_.Height = 11
    assert not propio and doc.UndoCount == n + 1 and doc.UndoNames[0] == "Afuera", doc.UndoNames
    doc.undo()
    assert cerca(caja_.Width, 10) and cerca(caja_.Height, 10), "deshacer 'Afuera' no deshizo todo"
    # falla adentro: se anula
    try:
        with safe_ops.undo_step(doc, "Falla"):
            caja_.Length = 30
            raise ValueError("a propósito")
    except ValueError:
        pass
    assert cerca(caja_.Length, 12), "no anuló lo hecho antes del error: %s" % caja_.Length

    # documentos por ruta (dos "Placa.FCStd" de carpetas distintas)
    sin = safe_ops.doc_key(doc)
    assert safe_ops.find_doc(sin) is doc, sin
    ruta = os.path.join(carpeta_temporal(), "Placa.FCStd")
    doc.saveAs(ruta)
    assert safe_ops.find_doc(sin) is None, "la clave de 'sin guardar' sigue valiendo después de guardar"
    clave = safe_ops.doc_key(doc)
    assert clave.lower().endswith("placa.fcstd"), clave
    otro = FreeCAD.newDocument("Placa")
    otro.saveAs(os.path.join(carpeta_temporal(), "Placa.FCStd"))
    clave2 = safe_ops.doc_key(otro)
    assert clave != clave2 and safe_ops.find_doc(clave) is doc and safe_ops.find_doc(clave2) is otro
    FreeCAD.closeDocument(otro.Name)
    FreeCAD.closeDocument(doc.Name)
    assert safe_ops.find_doc(clave) is None

    # escucha callada al abrir
    vistos = []

    class Escucha(safe_ops.QuietObserver):
        def slotChangedObject(self, obj, prop):
            vistos.append(self.busy(obj.Document))
    obs = Escucha()
    FreeCAD.addDocumentObserver(obs)
    try:
        FreeCAD.openDocument(ruta)
    finally:
        FreeCAD.removeDocumentObserver(obs)
    assert vistos and all(vistos), "la escucha no se enteró de que se estaba abriendo: %s" % vistos[:5]


from _base import ejecutar  # noqa: E402
ejecutar(globals())
