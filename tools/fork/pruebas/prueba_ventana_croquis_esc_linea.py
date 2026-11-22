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
   deselecciona: el croquis sigue abierto, como SW.
4) #111 (visto con el mouse el 21/11): lo mismo con un clic DE VERDAD en el panel y Esc con el teclado (QTest, sin
   poner el foco por código).
5) Línea sin usar (Esc antes del segundo clic): no queda nada (lo de antes sigue).
6) Esc sin nada elegido NO sale del croquis, como SW (decisión del usuario del 21/11: la casilla nativa
   "Esc puede salir del croquis" queda apagada desde el primer arranque de FreeWorks)."""
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


def _punto_panel(donde):
    """(widget, punto) para un clic de verdad en el panel del croquis: en la lista de elementos ("lista"), en un rótulo
    ("rotulo") o en el fondo vacío del panel ("fondo", debajo de las cajas)."""
    import FreeCADGui
    from swui.compat import QtCore, QtWidgets
    if donde == "lista":
        w = _panel_widget()
        return (w.viewport(), QtCore.QPoint(5, 5)) if w is not None else (None, None)
    mw = FreeCADGui.getMainWindow()
    tv = next((w for w in mw.findChildren(QtWidgets.QWidget)
               if w.metaObject().className() == "Gui::TaskView::TaskView" and w.isVisible()), None)
    if tv is None:
        return None, None
    if donde == "rotulo":
        for lab in tv.findChildren(QtWidgets.QLabel):
            if lab.isVisible() and lab.width() > 10 and lab.text():
                return lab, QtCore.QPoint(3, lab.height() // 2)
        return None, None
    area = tv.viewport() if hasattr(tv, "viewport") else tv
    for y in range(area.height() - 3, 0, -6):  # de abajo para arriba: el primer punto sin nada encima
        pt = QtCore.QPoint(area.width() // 2, y)
        hijo = area.childAt(pt)
        if hijo is None or hijo.metaObject().className() in ("QWidget", "QFrame", "Gui::TaskView::TaskPanel"):
            return area, pt
    return None, None


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
    from swui.compat import QtCore, QtWidgets
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

    traza("#111: clic de verdad en el panel con la línea elegida y Esc con el teclado")
    import os
    from PySide6.QtTest import QTest
    if os.environ.get("FW_ESC_SALE") == "1":  # para ver la falla de antes: Esc vuelve a poder salir del croquis
        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Sketcher").SetBool("LeaveSketchWithEscape", True)
    traza("  Esc puede salir del croquis: %s" % FreeCAD.ParamGet(
        "User parameter:BaseApp/Preferences/Mod/Sketcher").GetBool("LeaveSketchWithEscape", True))
    for donde in ("lista", "rotulo", "fondo"):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.Edge1" % (uno.Name, sk.Name))
        bombear(300)
        assert FreeCADGui.Selection.getSelectionEx("*", 0), "no pude elegir la línea"
        destino, punto = _punto_panel(donde)
        assert destino is not None, "no encontré dónde hacer clic en el panel (%s)" % donde
        traza("  clic en %s: %s" % (donde, destino.metaObject().className()))
        QTest.mouseClick(destino, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier, punto)
        bombear(400)
        foco = QtWidgets.QApplication.focusWidget()
        traza("  clic en %s: foco en %s; elegido %s" % (donde, foco.metaObject().className() if foco else None,
                                                       bool(FreeCADGui.Selection.getSelectionEx("*", 0))))
        if not FreeCADGui.Selection.getSelectionEx("*", 0):  # el clic en la lista puede deseleccionar: volver a elegir
            FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.Edge1" % (uno.Name, sk.Name))
            bombear(300)
        QTest.keyClick(foco or w, QtCore.Qt.Key.Key_Escape)
        bombear(800)
        assert getattr(gdoc.getInEdit(), "Object", None) is sk, "#111: clic en el panel (%s) y Esc cerró el croquis" % donde
        assert not FreeCADGui.Selection.getSelectionEx("*", 0), "#111: Esc no deseleccionó (%s)" % donde
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

    traza("sin nada elegido, Esc NO sale del croquis (como SW, 21/11)")
    FreeCADGui.Selection.clearSelection()
    _esc(vpw)
    bombear(800)
    assert getattr(gdoc.getInEdit(), "Object", None) is sk, "sin nada elegido Esc salió del croquis (en SW nunca)"
    from PySide6.QtTest import QTest as _QT
    _QT.keyClick(vpw, QtCore.Qt.Key.Key_Escape)
    bombear(800)
    assert getattr(gdoc.getInEdit(), "Object", None) is sk, "Esc con el teclado salió del croquis (en SW nunca)"
    traza("  Salir del croquis activo: %s; documento activo %s" % (
        FreeCADGui.Command.get("Sketcher_LeaveSketch").isActive(), FreeCAD.ActiveDocument.Name))
    FreeCADGui.runCommand("Sketcher_LeaveSketch")
    bombear(1500)
    # (el ensamblaje activo queda "en edición" él mismo: lo de FreeCAD; el croquis no)
    assert getattr(gdoc.getInEdit(), "Object", None) is not sk, "Salir del croquis no salió"
    assert ep.editing(doc) is uno, "salir del croquis sacó de Editar pieza"
    ep.stop(doc)
    bombear(300)
    del QtCore
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
