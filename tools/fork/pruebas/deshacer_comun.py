# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""Ayudas para las pruebas de deshacer editando una pieza (#113): atajos con el teclado de verdad, carteles,
ventana al frente, clic derecho."""
import FreeCAD
from azar_comun import bombear


def visibles(asm):
    return {o.Name: bool(o.Visibility) for o in asm.Group if o.TypeId in ("App::Link", "Assembly::AssemblyLink")}


def al_frente(doc):
    import FreeCADGui
    from swui.compat import QtWidgets
    FreeCAD.setActiveDocument(doc.Name)
    vista = FreeCADGui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor")[0]
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in area.subWindowList():
        if sub.isAncestorOf(vista.graphicsView()):
            area.setActiveSubWindow(sub)
    bombear(300)
    return vista


def atajo(vista, letra):
    """Ctrl+<letra> con el teclado sobre la vista (QTest pasa por los atajos de la ventana, como el usuario).
    Cierra y anota los carteles que aparezcan (contestando lo que FreeCAD trae marcado)."""
    from PySide6.QtTest import QTest
    from swui.compat import QtCore, QtWidgets
    carteles = []

    def mirar():
        d = QtWidgets.QApplication.activeModalWidget()
        if isinstance(d, QtWidgets.QMessageBox):
            carteles.append(d.text())
            b = d.defaultButton() or d.button(QtWidgets.QMessageBox.StandardButton.Yes)
            if b is not None:
                b.click()
            else:
                d.reject()
    reloj = QtCore.QTimer()
    reloj.timeout.connect(lambda: mirar())
    reloj.start(200)
    try:
        vp = vista.graphicsView().viewport()
        vp.setFocus()
        bombear(100)
        QTest.keyClick(vp, letra, QtCore.Qt.KeyboardModifier.ControlModifier)
        bombear(900)
    finally:
        reloj.stop()
    return carteles


def con_menu(abrir, que):
    """Abre el clic derecho, hace clic en `que` y lo cierra (como prueba_ventana_editar_pieza_menu)."""
    from swui.compat import QtCore, QtWidgets
    from swui.fork import context_menus as cm
    visto = {}

    class F(QtCore.QObject):
        def eventFilter(self, obj, ev):
            if (ev.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QMenu)
                    and not isinstance(obj.parent(), QtWidgets.QMenu) and "m" not in visto):
                visto["m"] = obj

                def hacer():
                    visto["vis"] = cm.visible_texts(obj)
                    visto["ok"] = cm.click_text(obj, que)
                    obj.close()
                QtCore.QTimer.singleShot(350, hacer)
            return False
    f = F()
    QtWidgets.QApplication.instance().installEventFilter(f)
    try:
        abrir()
        bombear(1500)
    finally:
        QtWidgets.QApplication.instance().removeEventFilter(f)
    return visto.get("vis"), visto.get("ok")


def cancelar_panel():
    """Como el botón Cancelar del panel de tareas."""
    import FreeCADGui
    from swui.compat import QtWidgets
    for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        b = box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        if b is not None and b.isVisible():
            b.click()
            return True
    return False


def ventana_activa():
    import FreeCADGui
    from swui.compat import QtWidgets
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    sub = area.activeSubWindow()
    return sub.windowTitle() if sub is not None else None


def doble_clic(vista, punto_3d):
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


def modificar(idm, valor):
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


def vista_activa_doc():
    """El documento de la vista que FreeCAD tiene como activa (la que recibe Std_Undo)."""
    import FreeCADGui
    try:
        g = FreeCADGui.activeDocument()
        return g.Document.Name if g is not None else None
    except Exception as exc:  # noqa: BLE001
        return "? %s" % exc
