# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Reordenar arrastrando en el árbol, como SW (decisión del usuario 15/11; FreeCAD 1.1.4 convertía la
operación soltada en BaseFeature): soltar una operación en la mitad de arriba de otra la deja antes;
en la de abajo, después. Un paso de deshacer (Ctrl+Z / Ctrl+Y exactos). Si depende de la de destino
no se puede soltar y nada cambia. La barra de retroceso queda donde estaba. Arrastrar otra cosa (un
croquis) sigue siendo de FreeCAD. Guardar y abrir conserva el orden."""
TIPO = "completa"
import os  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _arbol():
    import FreeCADGui
    from swui.compat import QtWidgets
    for t in FreeCADGui.getMainWindow().findChildren(QtWidgets.QTreeWidget):
        if t.metaObject().className() == "Gui::TreeWidget" and t.isVisible():
            return t


def _item(label):
    from swui.compat import QtWidgets
    it = QtWidgets.QTreeWidgetItemIterator(_arbol())
    while it.value():
        if it.value().text(0) == label:
            return it.value()
        it += 1


def soltar(doc, body, origen, destino, arriba):
    """Arrastra origen sobre destino (mitad de arriba o de abajo). Devuelve si el arrastre se aceptaba."""
    import FreeCADGui
    from swui.compat import QtCore, QtGui, QtWidgets
    tree = _arbol()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, origen.Name + ".")
    bombear(150)
    src, dst = _item(origen.Label), _item(destino.Label)
    assert src is not None and dst is not None, (origen.Label, destino.Label)
    tree.scrollToItem(dst)
    mime = tree.model().mimeData([tree.indexFromItem(src)])
    r = tree.visualItemRect(dst)
    y = r.top() + 2 if arriba else r.bottom() - 2
    pos = QtCore.QPoint(r.center().x(), y)
    vp = tree.viewport()
    L, M = QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.DropAction.MoveAction
    N = QtCore.Qt.KeyboardModifier.NoModifier
    traza("enter")
    QtWidgets.QApplication.sendEvent(vp, QtGui.QDragEnterEvent(pos, M, mime, L, N))
    traza("move")
    mv = QtGui.QDragMoveEvent(pos, M, mime, L, N)
    QtWidgets.QApplication.sendEvent(vp, mv)
    aceptado = mv.isAccepted()
    traza("drop (aceptado %s)" % aceptado)
    QtWidgets.QApplication.sendEvent(vp, QtGui.QDropEvent(QtCore.QPointF(pos), M, mime, L, N))
    traza("soltado")
    bombear(500)
    traza("listo %s" % _orden(body))
    return aceptado


def _orden(body):
    from swui.fork import feature_tree as ft
    return [f.Name for f in ft.features(body)]


def prueba():
    import FreeCADGui
    from swui.fork import feature_tree as ft
    from swui.fork import tree_drag as td

    doc = FreeCAD.newDocument("Arrastre")
    body = doc.addObject("PartDesign::Body", "Body")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 60, 40, 20
    cil = body.newObject("PartDesign::AdditiveCylinder", "Cil")
    cil.Radius, cil.Height = 5, 40
    esf = body.newObject("PartDesign::AdditiveSphere", "Esf")
    esf.Radius = 6
    doc.recompute()
    # un corte con croquis apoyado en la cara de arriba de la caja: depende de ella
    sk = body.newObject("Sketcher::SketchObject", "CroquisCorte")
    sk.AttachmentSupport = [(caja, "Face6")]
    sk.MapMode = "FlatFace"
    sk.addGeometry(Part.Circle(V(45, 20, 0), V(0, 0, 1), 4))
    corte = body.newObject("PartDesign::Pocket", "Corte")
    corte.Profile = sk
    corte.Length = 5
    doc.recompute()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(500)
    traza("pieza armada %s" % _orden(body))
    assert _orden(body) == ["Caja", "Cil", "Esf", "Corte"], _orden(body)
    vol0 = body.Shape.Volume

    # 1) Esf a la mitad de arriba de Caja -> primera
    assert soltar(doc, body, esf, caja, True), "no se aceptaba soltar Esf sobre Caja"
    assert _orden(body) == ["Esf", "Caja", "Cil", "Corte"], "arrastre hacia arriba: %s" % _orden(body)
    assert "BaseFeature" not in [o.Name for o in doc.Objects], "FreeCAD convirtió la operación en BaseFeature"
    assert body.Tip is corte, "la barra se movió: %s" % body.Tip.Name
    assert abs(body.Shape.Volume - vol0) < 1e-6, "cambió la pieza al reordenar (%s / %s)" % (body.Shape.Volume, vol0)

    # 2) Deshacer y rehacer: un solo paso
    doc.undo()
    doc.recompute()
    assert _orden(body) == ["Caja", "Cil", "Esf", "Corte"], "Ctrl+Z no volvió el orden: %s" % _orden(body)
    doc.redo()
    doc.recompute()
    assert _orden(body) == ["Esf", "Caja", "Cil", "Corte"], "Ctrl+Y no rehizo: %s" % _orden(body)
    yield 100

    # 3) Hacia abajo, mitad de abajo de Cil -> después de Cil
    assert soltar(doc, body, caja, cil, False)
    assert _orden(body) == ["Esf", "Cil", "Caja", "Corte"], "arrastre hacia abajo: %s" % _orden(body)

    # 4) El corte depende de Caja: no puede quedar arriba de ella
    antes = _orden(body)
    assert not soltar(doc, body, corte, cil, True), "dejaba soltar el corte arriba de lo que usa"
    assert _orden(body) == antes, "con la dependencia, igual se movió: %s" % _orden(body)
    assert td.blocker(ft.features(body), corte, 0, ft.ancestors), "la función no ve la dependencia"
    yield 100

    # 5) Con la barra retrocedida, queda donde estaba
    ft.set_tip(body, cil)
    doc.recompute()
    assert soltar(doc, body, esf, caja, False)
    assert body.Tip is cil, "con la barra retrocedida, se movió la barra: %s" % body.Tip.Name
    ft.set_tip(body, ft.features(body)[-1])
    doc.recompute()

    # 5b) Con un croquis en edición no se reordena (revisión del 15/11)
    antes = _orden(body)
    FreeCADGui.getDocument(doc.Name).setEdit(sk)
    bombear(600)
    soltar(doc, body, esf, cil, True)
    assert _orden(body) == antes, "con el croquis en edición, se reordenó: %s" % _orden(body)
    FreeCADGui.getDocument(doc.Name).resetEdit()
    bombear(400)
    doc.recompute()

    # 5c) Ctrl (copiar) no lo toma FreeWorks
    from swui.compat import QtCore, QtGui
    tree = _arbol()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, esf.Name + ".")
    mime = tree.model().mimeData([tree.indexFromItem(_item(esf.Label))])
    r = tree.visualItemRect(_item(cil.Label))
    ev = QtGui.QDragMoveEvent(QtCore.QPoint(r.center().x(), r.top() + 2), QtCore.Qt.DropAction.CopyAction, mime,
                              QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.ControlModifier)
    assert not td.on_event(tree.viewport(), ev), "FreeWorks tomaba un arrastre con Ctrl"

    # 5d) Otro documento abierto con una operación del mismo nombre: soltar ahí no reordena este
    otro = FreeCAD.newDocument("Otro")
    b2 = otro.addObject("PartDesign::Body", "Body")
    c2 = b2.newObject("PartDesign::AdditiveBox", "Caja")
    c2.Label = caja.Label
    otro.recompute()
    FreeCAD.setActiveDocument(doc.Name)
    bombear(400)
    antes = _orden(body)
    item_otro = None
    tree = _arbol()

    def buscar(item):
        for k in range(item.childCount()):
            hijo = item.child(k)
            if hijo.text(0) == caja.Label:
                return hijo
            hallado = buscar(hijo)
            if hallado is not None:
                return hallado
        return None
    for k in range(tree.topLevelItemCount()):
        raiz = tree.topLevelItem(k)
        for j in range(raiz.childCount()):
            if raiz.child(j).text(0) == otro.Label:
                item_otro = buscar(raiz.child(j))
        if raiz.text(0) == otro.Label:
            item_otro = buscar(raiz)
    if item_otro is not None:  # el árbol muestra los dos documentos
        tree.scrollToItem(item_otro)
        assert td.target_at(tree, tree.visualItemRect(item_otro).center(), esf) == (None, None),             "tomaba como destino una operación de otro documento"
    FreeCAD.closeDocument(otro.Name)
    FreeCAD.setActiveDocument(doc.Name)
    bombear(300)
    assert _orden(body) == antes

    # 6) Arrastrar un croquis sigue siendo de FreeCAD (FreeWorks no lo toma)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, sk.Name + ".")
    assert td._dragged() is None, "FreeWorks tomaba el arrastre de un croquis"
    yield 100

    # 7) Guardar y abrir: el orden queda
    orden = _orden(body)
    ruta = os.path.join(carpeta_temporal(), "Arrastre.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    doc2 = FreeCAD.openDocument(ruta)
    body2 = doc2.getObject("Body")
    assert _orden(body2) == orden, "guardar y abrir cambió el orden: %s / %s" % (_orden(body2), orden)
    FreeCAD.closeDocument(doc2.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
