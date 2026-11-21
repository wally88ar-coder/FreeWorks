# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Visto con el mouse el 21/11 (paso 16, #109): editando una pieza dentro del ensamblaje, el DOBLE CLIC de verdad
en una cara de la pieza muestra sus cotas sobre la pieza, como SW; también después de abrir y cerrar un croquis (queda
la pieza como documento activo). #110 (revisión): las cotas quedan sobre la instancia del clic (dos instancias de la
misma pieza, cada una en su lugar, también con la pieza como documento activo); el doble clic en otro componente
muestra las suyas en su lugar; con un panel abierto no se muestra nada y el doble clic sigue de largo."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _doble_clic(vista, punto_3d):
    from swui.compat import QtCore, QtGui, QtWidgets
    vp = vista.graphicsView().viewport()
    cx, cy = vista.getPointOnViewport(punto_3d)
    r = vp.devicePixelRatioF()
    p = QtCore.QPointF(cx / r, vp.height() - cy / r)
    g = vp.mapToGlobal(p.toPoint())
    izq, nada = QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton
    sin = QtCore.Qt.KeyboardModifier.NoModifier
    E = QtCore.QEvent.Type
    QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(E.MouseMove, p, g, nada, nada, sin))
    for t, b in ((E.MouseButtonPress, izq), (E.MouseButtonRelease, nada), (E.MouseButtonDblClick, izq),
                 (E.MouseButtonRelease, nada)):
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(t, p, g, izq, b, sin))
        bombear(40)
    bombear(800)


def _sobre(idm, vista, comp, que):
    """Las cotas mostradas están sobre el componente comp (o un Placement): su ubicación y cada rótulo en pantalla."""
    assert idm.shown(), "%s: el doble clic no mostró las cotas" % que
    donde = comp if isinstance(comp, FreeCAD.Placement) else comp.Placement
    plc = idm._state["plc"]
    assert plc is not None and plc.isSame(donde, 1e-6), \
        "%s: cotas con la ubicación %s, el componente está en %s" % (que, plc, donde)
    vp = vista.graphicsView().viewport()
    r = vp.devicePixelRatioF()
    for boton, cota in idm._state["labels"]:
        x, y = vista.getPointOnViewport(donde.multVec(cota.label_at))
        cx = boton.x() + boton.width() / 2.0
        cy = boton.y() + boton.height() / 2.0
        assert abs(cx - x / r) < 3 and abs(cy - (vp.height() - y / r)) < 3, \
            "%s: el rótulo '%s' quedó corrido (%.0f, %.0f) en vez de (%.0f, %.0f)" % (
                que, boton.text(), cx, cy, x / r, vp.height() - y / r)


def _modificar(idm, valor):
    """Abrir "Modificar" en el primer rótulo, escribir el valor y Enter."""
    import FreeCADGui
    from swui.compat import QtWidgets
    boton, cota = idm._state["labels"][0]
    idm._modify(cota, boton)
    bombear(300)
    caja = next((b for b in FreeCADGui.getMainWindow().findChildren(QtWidgets.QFrame, "SWUI_Modificar")
                 if b.isVisible()), None)
    assert caja is not None, "no se abrió Modificar"
    campo = caja.findChild(QtWidgets.QLineEdit)
    campo.setText(valor)
    campo.returnPressed.emit()
    bombear(1200)


def prueba():
    import FreeCADGui
    import Part
    import piezas_editar as pe
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    from swui.fork import instant_dims as idm
    c = carpeta_temporal()
    ruta = pe.bloque(c)
    doc, asm, (uno, gemela, dos) = pe.ensamblaje([ruta, ruta, pe.bloque(c, "Otro")])
    uno.Placement.Base = V(30, 20, 10)
    gemela.Placement = FreeCAD.Placement(V(-120, 60, 0), FreeCAD.Rotation(V(0, 0, 1), 30))
    doc.recompute()
    assert uno.LinkedObject.Document is gemela.LinkedObject.Document, "no son dos instancias de la misma pieza"
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.activeView()
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    assert ep.start(uno, warn=False)
    bombear(500)
    pdoc = uno.LinkedObject.Document

    def cara(comp):
        return comp.Placement.multVec(V(30, 0, 10))  # el frente del bloque

    traza("doble clic en la pieza editada y en la otra instancia de la misma pieza")
    _doble_clic(vista, cara(uno))
    _sobre(idm, vista, uno, "pieza editada")
    idm.hide()
    _doble_clic(vista, cara(gemela))
    _sobre(idm, vista, gemela, "otra instancia")
    _modificar(idm, "25")
    _sobre(idm, vista, gemela, "otra instancia, después de Modificar")
    idm.hide()
    pdoc.undo()
    pdoc.recompute()
    doc.recompute()
    bombear(300)
    traza("doble clic en otro componente")
    _doble_clic(vista, cara(dos))
    _sobre(idm, vista, dos, "otro componente")
    bombear(500)
    assert idm.shown(), "las cotas del otro componente se fueron solas"
    _modificar(idm, "25")
    _sobre(idm, vista, dos, "otro componente, después de Modificar")
    idm.hide()
    otro = dos.LinkedObject.Document
    otro.undo()
    otro.recompute()
    doc.recompute()
    bombear(300)

    traza("doble clic en una copia de una matriz de componentes")
    arr = asm.newObject("App::Link", "Matriz")
    arr.LinkedObject = dos.LinkedObject
    arr.ShowElement = True
    arr.ElementCount = 2
    arr.recompute()
    arr.ElementList[0].Placement = FreeCAD.Placement(V(250, 0, 0), FreeCAD.Rotation())
    arr.ElementList[1].Placement = FreeCAD.Placement(V(250, 120, 0), FreeCAD.Rotation(V(0, 0, 1), 20))
    doc.recompute()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(800)
    copia = arr.Placement.multiply(arr.ElementList[1].Placement)
    _doble_clic(vista, copia.multVec(V(30, 0, 10)))
    _sobre(idm, vista, copia, "copia de la matriz")
    idm.hide()
    doc.removeObject(arr.Name)
    doc.recompute()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(500)
    bombear(300)
    yield 100

    traza("después de abrir y cerrar un croquis de la pieza (la pieza queda como documento activo)")
    sk = ec.new_sketch(pdoc.getObject("Extruir"), "Face6")
    bombear(1500)
    sk.addGeometry(Part.LineSegment(V(5, 5, 0), V(15, 10, 0)))
    pdoc.recompute()
    ec.reset_edit(pdoc)
    bombear(3000)
    FreeCAD.setActiveDocument(pdoc.Name)  # como lo deja FreeCAD (título "Taco *" con el mouse)
    bombear(300)
    _doble_clic(vista, cara(uno))
    traza("  activo %s; cotas: %s" % (FreeCAD.ActiveDocument.Name, idm.shown()))
    _sobre(idm, vista, uno, "con la pieza como documento activo")
    bombear(500)
    assert idm.shown(), "con la pieza como documento activo las cotas se fueron solas"
    idm.hide()
    _doble_clic(vista, cara(gemela))
    _sobre(idm, vista, gemela, "otra instancia, con la pieza como documento activo")
    idm.hide()
    yield 100

    traza("con un panel abierto: nada")
    FreeCAD.setActiveDocument(doc.Name)
    bombear(300)
    from swui.compat import QtWidgets

    class Panel:
        def __init__(self):
            self.form = QtWidgets.QWidget()

        def reject(self):
            FreeCADGui.Control.closeDialog()
            return True

    FreeCADGui.Control.showDialog(Panel())
    bombear(300)
    try:
        _doble_clic(vista, cara(dos))
        assert not idm.shown(), "con un panel abierto el doble clic mostró cotas"
    finally:
        FreeCADGui.Control.closeDialog()
        bombear(300)
    ep.stop(doc)
    bombear(300)
    yield 100

    traza("una pieza sola: el doble clic y las cotas de su croquis (como antes)")
    from menu_comun import pieza
    import Sketcher
    sola, _body, croquis, _pad = pieza()
    croquis.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 60.0))
    croquis.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 40.0))
    sola.recompute()
    FreeCAD.setActiveDocument(sola.Name)
    vs = FreeCADGui.getDocument(sola.Name).activeView()
    vs.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    _doble_clic(vs, V(30, 0, 10))
    assert idm.shown() and idm._state["plc"] is None, "pieza sola: el doble clic no mostró las cotas (o corridas)"
    idm.hide()
    assert idm.show(croquis) > 0 and idm._state["plc"] is None, "pieza sola: las cotas del croquis no se muestran"
    idm.hide()
    FreeCAD.closeDocument(sola.Name)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
