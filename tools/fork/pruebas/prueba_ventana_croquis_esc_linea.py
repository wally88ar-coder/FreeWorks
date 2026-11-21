# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#107 (visto con el mouse el 18/11): editando una pieza, en un croquis apoyado en la cara de OTRO componente
(top-down):
1) Línea con el primer clic en un vértice de ese otro componente SIN pasar antes el mouse por encima (sin
   preselección: la línea no queda pegada por una relación) y el segundo adentro; Esc corta la herramienta y la
   LÍNEA QUEDA (antes la limpieza de "referencia sin usar" deshacía su paso entero y se llevaba la línea).
2) Lo mismo pasando el mouse (queda pegada con Coincidente).
3) Esc con algo elegido y el foco en el panel del costado (Agregar relaciones, la lista de elementos) solo
   deselecciona: el croquis sigue abierto, como SW. Sin nada elegido, Esc sale del croquis (como siempre).
4) Línea sin usar (Esc antes del segundo clic): no queda nada (lo de antes sigue)."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _punto(vista, punto_3d):
    from swui.compat import QtCore
    vp = vista.graphicsView().viewport()
    cx, cy = vista.getPointOnViewport(punto_3d)
    r = vp.devicePixelRatioF()
    return vp, QtCore.QPointF(cx / r, vp.height() - cy / r)


def _clic(vista, punto_3d, mover=True):
    """Clic de verdad en el punto (del ensamblaje); mover=False: sin MouseMove antes (como un clic que no pasó por
    encima, sin preselección)."""
    from swui.compat import QtCore, QtGui, QtWidgets
    vp, p = _punto(vista, punto_3d)
    nada, izq = QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.LeftButton
    sin = QtCore.Qt.KeyboardModifier.NoModifier
    g = vp.mapToGlobal(p.toPoint())
    if mover:
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, p, g, nada, nada, sin))
        bombear(300)
    QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, p, g, izq, izq, sin))
    bombear(150)
    QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonRelease, p, g, izq, nada, sin))
    bombear(500)


def _esc(widget):
    from swui.compat import QtCore, QtGui, QtWidgets
    widget.setFocus()
    for t in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
        QtWidgets.QApplication.sendEvent(widget, QtGui.QKeyEvent(t, QtCore.Qt.Key.Key_Escape,
                                                                 QtCore.Qt.KeyboardModifier.NoModifier))
    bombear(400)


def _panel_widget():
    """Un widget del panel de tareas (la lista de elementos del croquis, o cualquiera enfocable del panel)."""
    import FreeCADGui
    from swui.compat import QtWidgets
    mw = FreeCADGui.getMainWindow()
    for w in mw.findChildren(QtWidgets.QListWidget) + mw.findChildren(QtWidgets.QTreeWidget):
        p, dentro = w, False
        while p is not None:
            if "TaskView" in p.metaObject().className():
                dentro = True
                break
            p = p.parentWidget()
        if dentro and w.isVisible():
            return w
    return None


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from swui import ribbon
    from swui.compat import QtCore
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, (uno, dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    uno.Placement.Base = V(0, -30, 25)
    doc.recompute()
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.activeView()
    assert ep.start(uno, warn=False)
    bombear(500)
    pdoc = uno.LinkedObject.Document

    # croquis top-down en la cara de arriba del otro
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % dos.Name)
    ribbon._run("PartDesign_NewSketch")
    bombear(2500)
    sk = getattr(gdoc.getInEdit(), "Object", None)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "no abrió el croquis"
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    vpw = vista.graphicsView().viewport()
    yield 100

    for mover in (False, True):
        traza("Línea desde un vértice del otro (mover=%s) y Esc" % mover)
        n_geo = len(sk.Geometry)
        FreeCADGui.runCommand("Sketcher_CreateLine")
        bombear(500)
        esquina = dos.Placement.multVec(V(60, 40, 20) if not mover else V(0, 40, 20))
        _clic(vista, esquina, mover)
        _clic(vista, dos.Placement.multVec(V(30, 20, 20)), mover)
        _esc(vpw)  # un Esc: corta la herramienta (como en la prueba con el mouse)
        bombear(1500)  # la limpieza de lo traído corre cuando termina la herramienta
        pdoc.recompute()
        traza("  geometrías %d -> %d, restricciones %s" % (n_geo, len(sk.Geometry),
                                                          [(k.Type, k.First, k.Second) for k in sk.Constraints]))
        assert getattr(gdoc.getInEdit(), "Object", None) is sk, "Esc cerró el croquis"
        assert len(sk.Geometry) == n_geo + 1, "#107: Esc se llevó la línea recién dibujada (mover=%s)" % mover
        yield 100

    traza("referencia traída y una línea SIN relación con ella (lo que pasó con el mouse): Esc no la borra")
    import Part
    n_geo = len(sk.Geometry)
    FreeCADGui.runCommand("Sketcher_CreateLine")
    bombear(500)
    _clic(vista, dos.Placement.multVec(V(0, 0, 20)), True)  # trae el vértice (primer clic de la línea)
    sk.addGeometry(Part.LineSegment(V(-20, -20, 0), V(-5, -10, 0)))  # una línea suelta, sin relación
    bombear(200)
    _esc(vpw)
    _esc(vpw)
    bombear(1500)
    pdoc.recompute()
    traza("  geometrías %d -> %d" % (n_geo, len(sk.Geometry)))
    assert len(sk.Geometry) == n_geo + 1, "#107: la limpieza de la referencia sin usar se llevó la línea dibujada"
    assert getattr(gdoc.getInEdit(), "Object", None) is sk, "Esc cerró el croquis"
    yield 100

    traza("Esc con algo elegido y el foco en el panel: solo deselecciona")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.Edge1" % (uno.Name, sk.Name))
    bombear(300)
    elegido = FreeCADGui.Selection.getSelectionEx("*", 0)
    traza("  elegido: %s" % [(s.Object.Name, s.SubElementNames) for s in elegido])
    assert elegido, "no pude elegir la línea"
    w = _panel_widget()
    assert w is not None, "no encontré la lista del panel del croquis"
    _esc(w)
    assert getattr(gdoc.getInEdit(), "Object", None) is sk, "#107: Esc con algo elegido (foco en el panel) cerró el croquis"
    assert not FreeCADGui.Selection.getSelectionEx("*", 0), "Esc no deseleccionó"
    yield 100

    traza("Línea sin usar (Esc antes del segundo clic): no queda nada")
    n_geo, n_ext = len(sk.Geometry), len(sk.ExternalGeometry)
    FreeCADGui.runCommand("Sketcher_CreateLine")
    bombear(500)
    _clic(vista, dos.Placement.multVec(V(60, 0, 20)), True)
    _esc(vpw)
    _esc(vpw)
    bombear(1500)
    assert len(sk.Geometry) == n_geo, "cancelar la Línea dejó geometría"
    assert getattr(gdoc.getInEdit(), "Object", None) is sk, "Esc cerró el croquis"
    yield 100

    traza("sin nada elegido, Esc sale del croquis (como siempre en FreeWorks)")
    FreeCADGui.Selection.clearSelection()
    _esc(vpw)
    bombear(800)
    assert gdoc.getInEdit() is None, "sin nada elegido Esc no salió del croquis"
    assert ep.editing(doc) is uno, "Esc sacó de Editar pieza"
    ep.stop(doc)
    bombear(300)
    del QtCore
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
