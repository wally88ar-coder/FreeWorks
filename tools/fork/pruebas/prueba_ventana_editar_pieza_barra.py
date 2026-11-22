# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#105 y #106 (vistos con el mouse el 18/11): editando una pieza dentro del ensamblaje, la esquina de confirmación
(desde el 21/11 reemplaza la barra "Editando pieza / Salir": Volver al ensamblaje, o los botones del croquis o del panel
abierto) sigue a la vista después de Editar operación > Cancelar, de abrir y cerrar un croquis en la pieza y de un
croquis sobre la cara de OTRO componente (top-down). Cancelar no deja el ensamblaje ni la pieza modificados. Abrir
un croquis de la pieza editada no abre ninguna ventana aparte (la de la pieza) y la vista queda mirando al croquis
(su origen y la cara donde está apoyado, dentro de la pantalla)."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from menu_comun import derecho_vista  # noqa: E402

V = FreeCAD.Vector


def _con_menu(abrir, que):
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


def _en_edicion(gdoc):
    return getattr(gdoc.getInEdit(), "Object", None)


def _barra_visible():
    """La esquina de confirmación se VE: visible, con botones y por ENCIMA de la zona central (la vista): entre
    hermanos, el último es el de arriba (#105). Desde el 21/11 reemplaza a la barra "Editando pieza / Salir"."""
    import FreeCADGui
    from swui.compat import QtWidgets
    from swui.fork import confirm_corner as cc
    bombear(400)  # el reloj de la esquina
    mw = FreeCADGui.getMainWindow()
    assert not [w for w in mw.findChildren(QtWidgets.QFrame, "SWUI_edit_part_bar") if w.isVisible()],         "con la esquina prendida se ve la barra vieja"
    w = cc.widget()
    if w is None or not cc.visible_keys():
        return False
    hijos = [c for c in mw.children() if isinstance(c, QtWidgets.QWidget)]
    central = mw.centralWidget()
    if w.parent() is mw and central in hijos and hijos.index(w) < hijos.index(central):
        traza("  esquina tapada por la zona central")
        return False
    traza("  esquina: %s" % cc.visible_keys())
    return True


def _ventanas():
    import FreeCADGui
    from swui.compat import QtWidgets
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    bar = area.findChild(QtWidgets.QTabBar)
    tabs = [bar.tabText(i) for i in range(bar.count()) if bar.isTabVisible(i)] if bar is not None else []
    limpio = lambda t: t.replace("[*]", "").rstrip("*")  # noqa: E731
    # 21/11 (visto con el mouse): ocultar una ventana sacaba a las otras de las pestañas (quedaban flotando)
    cur = area.currentSubWindow()
    assert area.viewMode() == QtWidgets.QMdiArea.ViewMode.TabbedView and (cur is None or cur.isMaximized()), \
        "las ventanas dejaron de estar en pestañas: al frente %s, maximizada %s" % (
            cur.windowTitle() if cur else None, cur.isMaximized() if cur else None)
    return limpio(cur.windowTitle()) if cur is not None else None, sorted(limpio(t) for t in tabs)


def _en_pantalla(view, punto):
    """¿El punto (del ensamblaje) cae dentro de la vista 3D?"""
    x, y = view.getPointOnViewport(punto)
    w, h = view.getSize()
    return 0 <= x <= w and 0 <= y <= h, (round(x), round(y), w, h)


def _cancelar_panel():
    """Como el botón Cancelar del panel de tareas."""
    import FreeCADGui
    from swui.compat import QtWidgets
    for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        b = box.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        if b is not None and b.isVisible():
            b.click()
            return True
    return False


def prueba():
    import FreeCADGui
    import Part
    import piezas_editar as pe
    from swui import ribbon
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, (uno, dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    # el componente editado fuera del origen (como el Taco del paso 6)
    uno.Placement.Base = V(30, 20, 10)
    doc.recompute()
    doc.save()
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    gdoc.Modified = False
    view = gdoc.activeView()
    view.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    pdoc = uno.LinkedObject.Document
    gpdoc = FreeCADGui.getDocument(pdoc.Name)
    traza("  antes de editar: ensamblaje %s, pieza %s" % (gdoc.Modified, gpdoc and gpdoc.Modified))
    assert ep.start(uno, warn=False)
    bombear(500)
    gpdoc = FreeCADGui.getDocument(pdoc.Name)
    traza("  editando: ensamblaje %s, pieza %s, activo %s" % (gdoc.Modified, gpdoc.Modified,
                                                             FreeCAD.ActiveDocument.Name))
    assert _barra_visible(), "no apareció la barra al empezar"
    ventanas = _ventanas()
    pieza_mod = gpdoc.Modified
    yield 100

    traza("Editar operación > Cancelar")
    FreeCADGui.Selection.clearSelection()
    vis, ok = _con_menu(derecho_vista(uno.Placement.multVec(V(50, 30, 20))), "Editar operación")
    bombear(1500)
    assert ok, "no estaba Editar operación: %s" % vis
    assert getattr(_en_edicion(gdoc), "Name", None) == "Extruir"
    traza("  panel abierto: ensamblaje %s, pieza %s, activo %s, barra %s, pasos %s / %s" % (
        gdoc.Modified, gpdoc.Modified, FreeCAD.ActiveDocument.Name, _barra_visible(), doc.UndoNames[:3],
        pdoc.UndoNames[:3]))
    assert _cancelar_panel(), "no encontré el botón Cancelar"
    bombear(1500)
    traza("  activo: %s, ensamblaje modificado %s, pieza %s, pasos %s / %s" % (
        FreeCAD.ActiveDocument.Name, gdoc.Modified, gpdoc.Modified, doc.UndoNames[:3], pdoc.UndoNames[:3]))
    assert ep.editing(doc) is uno, "Cancelar sacó de Editar pieza"
    assert _barra_visible(), "#105: la barra desapareció después de Editar operación > Cancelar"
    assert not gdoc.Modified, "Cancelar dejó el ensamblaje modificado"
    assert gpdoc.Modified == pieza_mod, "Cancelar dejó la pieza modificada"
    yield 100

    traza("croquis en la cara de arriba de la pieza editada")
    nodo = view.getCameraNode()
    cam_antes = (nodo.position.getValue().getValue(), nodo.orientation.getValue().getValue())
    FreeCADGui.Selection.clearSelection()
    vis, ok = _con_menu(derecho_vista(uno.Placement.multVec(V(30, 20, 20))), "Croquis")
    bombear(3000)  # la cámara se centra cuando termina la animación de FreeCAD
    sk = _en_edicion(gdoc)
    assert ok and sk is not None and sk.TypeId == "Sketcher::SketchObject", "no abrió el croquis: %s" % vis
    traza("  ventanas: %s" % (_ventanas(),))
    assert _ventanas() == ventanas, "#106: se abrió otra ventana: %s" % (_ventanas(),)
    cam = view.getCameraNode()
    traza("  cámara: pos %s orient %s tipo %s" % (cam.position.getValue().getValue(),
                                                  cam.orientation.getValue().getValue(), view.getCameraType()))
    from swui.fork import edit_context as ec
    traza("  pieza->vista: %s, croquis global: %s" % (ec.view_placement(part_doc=pdoc), sk.getGlobalPlacement()))
    adentro, donde = _en_pantalla(view, uno.Placement.multVec(V(30, 20, 20)))
    assert adentro, "#106: la vista quedó lejos del croquis: %s" % (donde,)
    assert _barra_visible(), "la barra no se ve con el croquis abierto"
    gdoc.resetEdit()
    bombear(3000)  # la animación de vuelta de la cámara
    assert _barra_visible(), "#105: la barra desapareció al cerrar el croquis"
    nodo = view.getCameraNode()
    cam_despues = (nodo.position.getValue().getValue(), nodo.orientation.getValue().getValue())
    dif = max(abs(a - b) for x, y in zip(cam_antes, cam_despues) for a, b in zip(x, y))
    traza("  cámara antes %s, después %s" % (cam_antes, cam_despues))
    assert dif < 1e-3, "al cerrar el croquis la cámara no volvió a donde estaba: %s -> %s" % (cam_antes, cam_despues)
    yield 100

    traza("croquis top-down en la cara de arriba del otro componente")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Face6" % dos.Name)
    ribbon._run("PartDesign_NewSketch")
    bombear(3000)  # la cámara se centra cuando termina la animación de FreeCAD
    sk = _en_edicion(gdoc)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "no abrió el croquis top-down"
    assert _ventanas() == ventanas, "#106: se abrió otra ventana: %s" % (_ventanas(),)
    adentro, donde = _en_pantalla(view, dos.Placement.multVec(V(30, 20, 20)))
    nodo = view.getCameraNode()
    traza("  top-down: cámara %s orient %s; apoyo %s; quiero ver %s" % (
        nodo.position.getValue().getValue(), nodo.orientation.getValue().getValue(),
        [(o.Name, s) for o, s in sk.AttachmentSupport], dos.Placement.multVec(V(30, 20, 20))))
    assert adentro, "#106: la vista quedó lejos de la cara del otro componente: %s" % (donde,)
    sk.addGeometry(Part.Circle(V(10, 10, 0), V(0, 0, 1), 3))
    pdoc.recompute()
    gdoc.resetEdit()
    bombear(800)
    assert ep.editing(doc) is uno
    assert _barra_visible(), "#105: la barra desapareció después del croquis top-down"

    traza("la pieza queda como documento activo (Miembro estructural, Editar operación...)")
    FreeCAD.setActiveDocument(pdoc.Name)
    ep.sync_bars()
    bombear(200)
    from swui.compat import QtWidgets
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    cur = area.currentSubWindow()
    traza("  al frente: %s (visible %s), ventanas %s, front %s" % (
        cur.windowTitle() if cur else None, cur.isVisible() if cur else None, _ventanas(), ep._front_document()))
    assert _barra_visible(), "#105: con la pieza como documento activo y el ensamblaje al frente, se fue la barra"
    FreeCAD.setActiveDocument(doc.Name)
    ep.stop(doc)
    bombear(300)
    assert not _barra_visible(), "Salir dejó la barra"

    traza("al salir, la ventana apartada no aparece; Abrir pieza la trae con su pestaña")
    from swui.fork import context_tools as ct
    from swui.fork import edit_context as ec
    assert not any(t.startswith(pdoc.Label) for t in _ventanas()[1]), "salir dejó a la vista la pestaña de la pieza"
    subs = ec._part_windows(pdoc)
    assert subs, "no quedó la ventana apartada de la pieza"
    ct.open_parts([uno])
    bombear(800)
    cur = area.currentSubWindow()
    traza("  al frente: %s; %s" % (cur.windowTitle() if cur else None, _ventanas()))
    assert cur in subs and cur.isVisible(), "Abrir pieza no trajo la ventana de la pieza"
    assert any(t.startswith(pdoc.Label) for t in _ventanas()[1]), "la pieza quedó sin pestaña: %s" % (_ventanas(),)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
