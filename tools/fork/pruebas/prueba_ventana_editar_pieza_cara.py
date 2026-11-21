# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Editando una pieza dentro del ensamblaje (Editar pieza), como en SW: con una cara plana de esa pieza
elegida con un clic en la vista, Croquis abre el croquis sobre esa cara (en la pieza) y Extruir corte /
Extruir saliente abren primero el croquis en la cara y, al salir del croquis, la operación con ese croquis
(no toman la cara entera como perfil). Visto por el usuario el 16/11: abría "Seleccione un plano" y el
corte tomaba la cara entera. La pieza está dos veces en el ensamblaje (como la del usuario)."""
TIPO = "completa"
import os  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from menu_comun import px  # noqa: E402

V = FreeCAD.Vector


def _pieza(carpeta):
    from menu_comun import pieza
    doc, body, sk, pad = pieza()
    ruta = os.path.join(carpeta, "Disco.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    return ruta


def _clic(punto, comp_name, mirar=True):
    """Clic izquierdo en la vista sobre `punto` (como el usuario); devuelve lo que quedó elegido."""
    import FreeCADGui
    from swui.compat import QtCore, QtGui, QtWidgets
    view = FreeCADGui.ActiveDocument.ActiveView
    vp = view.graphicsView().viewport()
    x, y = px(view, vp, punto)
    info = view.getObjectInfo((int(x), int(view.getSize()[1] - y)))
    traza("  bajo el cursor: %s" % (info,))
    L, N = QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton

    def ev(t, b, bs, dx=0):
        p = QtCore.QPointF(x + dx, y)
        return QtGui.QMouseEvent(t, p, QtCore.QPointF(vp.mapToGlobal(p)), b, bs,
                                 QtCore.Qt.KeyboardModifier.NoModifier)
    FreeCADGui.Selection.clearSelection()
    for dx in (3, 1, 0):
        QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseMove, N, N, dx))
        bombear(80)
    QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseButtonPress, L, L))
    bombear(30)
    QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseButtonRelease, L, N))
    bombear(300)
    sel = [(s.Object.Name, list(s.SubElementNames)) for s in FreeCADGui.Selection.getSelectionEx("", 0)]
    traza("  elegido: %s" % sel)
    assert not mirar or sel and any(comp_name in n for _o, ns in sel for n in ns), "el clic no eligió la cara: %s" % sel
    return sel


def _croquis_nuevos(pdoc, antes):
    return [o for o in pdoc.Objects if o.TypeId == "Sketcher::SketchObject" and o.Name not in antes]


def _en_edicion():
    import FreeCADGui
    vp = FreeCADGui.ActiveDocument.getInEdit()
    return getattr(vp, "Object", vp) if vp is not None else None


def prueba():
    import FreeCADGui
    import casos_relacion as cr
    from swui import ribbon
    from swui.fork import edit_part as ep

    carpeta = carpeta_temporal()
    ruta = _pieza(carpeta)
    doc, asm, (uno, dos) = cr._ensamblaje([ruta, ruta])  # asm: para elegir con el camino del ensamblaje
    dos.Placement.Base = V(0, 80, 0)
    doc.recompute()
    doc.save()
    FreeCAD.setActiveDocument(doc.Name)
    FreeCADGui.getMainWindow().setActiveWindow(FreeCADGui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor")[0]) if False else None
    bombear(500)
    traza("  documento al frente: %s" % (FreeCADGui.ActiveDocument and FreeCADGui.ActiveDocument.Document.Name))
    FreeCADGui.getDocument(doc.Name).activeView().viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(500)
    body = uno.LinkedObject
    pdoc = body.Document
    assert ep.start(uno, warn=False), "no entró a Editar pieza"
    bombear(500)
    arriba = V(30, 20, 20)  # centro de la cara de arriba del disco (en la pieza y en el componente uno)

    traza("paso 1")
    # 1) Croquis con la cara de arriba elegida con un clic: croquis nuevo en la pieza, abierto, sobre la cara
    antes = [o.Name for o in pdoc.Objects]
    _clic(uno.Placement.multVec(arriba), uno.Name)
    ribbon._run("PartDesign_NewSketch")
    bombear(1500)
    dialogo = FreeCADGui.Control.activeDialog()
    nuevos = _croquis_nuevos(pdoc, antes)
    assert nuevos, "Croquis no creó el croquis en la pieza (diálogo abierto: %s)" % dialogo
    sk = nuevos[0]
    assert _en_edicion() is sk, "el croquis nuevo no quedó abierto: %s" % _en_edicion()
    soporte = [(o.Name, s) for o, s in sk.AttachmentSupport]
    assert soporte and all(s and s[0].startswith("Face") for _n, s in soporte), "croquis no apoyado en la cara: %s" % soporte
    assert abs(sk.Placement.Base.z - 20) < 1e-6, "el croquis no está en la cara de arriba: %s" % sk.Placement
    FreeCADGui.ActiveDocument.resetEdit()  # vacío: FreeWorks lo borra
    bombear(800)
    yield 100

    traza("paso 2")
    # 2) Extruir corte con la cara elegida: primero el croquis en la cara (sin corte todavía)
    antes = [o.Name for o in pdoc.Objects]
    _clic(uno.Placement.multVec(arriba), uno.Name)
    ribbon._run("PartDesign_Pocket")
    bombear(1500)
    cortes = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "PartDesign::Pocket"]
    assert not cortes, "Extruir corte tomó la cara entera como perfil: %s" % [o.Name for o in cortes]
    nuevos = _croquis_nuevos(pdoc, antes)
    assert nuevos and _en_edicion() is nuevos[0], "Extruir corte no abrió el croquis en la cara: %s / %s" % (
        [o.Name for o in nuevos], _en_edicion())
    sk = nuevos[0]
    from swui import pick_plane as pp
    traza("  armado: %s; timer conectado a %s" % (pp.armed(), getattr(pp.tick, "_swui_edit_part", None)))
    import Part
    sk.addGeometry(Part.Circle(V(30, 20, 0), V(0, 0, 1), 5))
    FreeCADGui.ActiveDocument.resetEdit()
    bombear(2000)
    traza("  después de salir del croquis: diálogo %s, armado %s, en edición %s, elegido %s" % (
        FreeCADGui.Control.activeDialog(), pp.armed(), _en_edicion(),
        [(x.Object.Name, x.SubElementNames) for x in FreeCADGui.Selection.getSelectionEx("", 0)]))
    cortes = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "PartDesign::Pocket"]
    assert cortes and cortes[0].Profile[0] is sk, "al salir del croquis no arrancó el corte con ese croquis"
    FreeCADGui.Control.closeDialog()
    bombear(800)
    pdoc.recompute()
    assert body.Shape.isValid() and body.Shape.Volume < 60 * 40 * 20 - 1, "el corte no cortó"
    assert ep.editing(doc) is uno, "se salió de Editar pieza"
    yield 100

    traza("paso 3")
    # 3) Ctrl+Z en el ensamblaje deshace el corte (y su croquis) y se sigue editando
    FreeCADGui.Selection.clearSelection()
    for _ in range(3):
        if not [o for o in pdoc.Objects if o.TypeId == "PartDesign::Pocket"]:
            break
        FreeCADGui.runCommand("Std_Undo")
        bombear(500)
    assert not [o for o in pdoc.Objects if o.TypeId == "PartDesign::Pocket"], "Ctrl+Z no sacó el corte"
    viejo = sk  # el croquis del corte, que queda apoyado en la cara de arriba
    assert pdoc.getObject(viejo.Name) is viejo, "Ctrl+Z sacó también el croquis (se esperaba solo el corte)"
    soporte_viejo, lugar_viejo = [(o.Name, x) for o, x in viejo.AttachmentSupport], viejo.Placement
    assert ep.editing(doc) is uno, "Ctrl+Z sacó de Editar pieza"
    yield 100

    import Part
    traza("paso 4")
    # 4) Croquis sin nada elegido: el panel "elegí un plano o cara"; Cancelar no deja nada
    FreeCADGui.Selection.clearSelection()
    antes = [o.Name for o in pdoc.Objects]
    ribbon._run("PartDesign_NewSketch")
    bombear(1000)
    from swui import pick_plane as pp
    assert isinstance(pp._panel, pp._TaskPanel) and FreeCADGui.Control.activeDialog(), "no salió el panel de FreeWorks"
    pp._panel.reject()
    bombear(500)
    assert not FreeCADGui.Control.activeDialog(), "Cancelar dejó el panel abierto"
    assert [o.Name for o in pdoc.Objects] == antes, "Cancelar dejó algo en la pieza"
    # ... y con el panel abierto, un clic en la cara de la pieza abre el croquis ahí (lo que vio el usuario)
    ribbon._run("PartDesign_NewSketch")
    bombear(1000)
    assert FreeCADGui.Control.activeDialog(), "no salió el panel de FreeWorks (otra vez)"
    _clic(uno.Placement.multVec(arriba), uno.Name, mirar=False)  # el panel toma la cara al momento
    bombear(1500)
    nuevos = _croquis_nuevos(pdoc, antes)
    assert nuevos and _en_edicion() is nuevos[0], "el clic en la cara con el panel no abrió el croquis: %s / %s (%s) %s" % (
        [o.Name for o in nuevos], _en_edicion(), getattr(_en_edicion(), "FullName", ""), antes)
    assert abs(nuevos[0].Placement.Base.z - 20) < 1e-6, "el croquis no quedó en la cara: %s" % nuevos[0].Placement
    # error de FreeCAD 1.1.4 (el Croquis nativo, dentro de un ensamblaje, apoya y abre el "Sketch" que ya había):
    # el croquis viejo sigue igual y el abierto es el nuevo
    assert [(o.Name, x) for o, x in viejo.AttachmentSupport] == soporte_viejo and viejo.Placement.isSame(lugar_viejo, 1e-9),         "se movió el croquis que ya estaba"
    nuevo = nuevos[0]
    nuevo.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)))
    FreeCADGui.ActiveDocument.resetEdit()
    bombear(800)
    # Ctrl+Z en la ventana del ensamblaje saca el croquis nuevo (y se sigue editando)
    nombre = nuevo.Name
    for _ in range(3):
        if pdoc.getObject(nombre) is None:
            break
        FreeCADGui.runCommand("Std_Undo")
        bombear(500)
    assert pdoc.getObject(nombre) is None, "Ctrl+Z en el ensamblaje no sacó el croquis nuevo: %s" % list(doc.UndoNames)[:4]
    assert pdoc.getObject(viejo.Name) is viejo and ep.editing(doc) is uno
    yield 100

    traza("paso 5")
    # 5) Extruir saliente con la cara elegida: croquis en la cara y, al salir, la extrusión con ese croquis
    antes = [o.Name for o in pdoc.Objects]
    _clic(uno.Placement.multVec(arriba), uno.Name)
    ribbon._run("PartDesign_Pad")
    bombear(1500)
    nuevos = _croquis_nuevos(pdoc, antes)
    assert nuevos and _en_edicion() is nuevos[0], "Extruir saliente no abrió el croquis en la cara"
    assert not [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "PartDesign::Pad"], "tomó la cara entera"
    nuevos[0].addGeometry(Part.Circle(V(30, 20, 0), V(0, 0, 1), 5))
    FreeCADGui.ActiveDocument.resetEdit()
    bombear(2000)
    pads = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "PartDesign::Pad"]
    assert pads and pads[0].Profile[0] is nuevos[0], "al salir del croquis no arrancó la extrusión con ese croquis"
    FreeCADGui.Control.closeDialog()
    bombear(800)
    yield 100

    traza("paso 5b")
    # 5b) La cara nombrada por el Cuerpo ('Comp.Body.Face6', FreeCAD la nombra así a veces): el croquis se
    # apoya en la última operación, no en el Cuerpo (sería una dependencia circular)
    antes = [o.Name for o in pdoc.Objects]
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.Face6" % (uno.Name, body.Name))
    ribbon._run("PartDesign_NewSketch")
    bombear(1500)
    nuevos = _croquis_nuevos(pdoc, antes)
    assert nuevos and _en_edicion() is nuevos[0], "con la cara nombrada por el Cuerpo no abrió el croquis"
    apoyo = [o for o, _x in nuevos[0].AttachmentSupport]
    assert apoyo and body not in apoyo and apoyo[0] is body.Tip, "croquis apoyado en %s (punta %s)" % (
        [o.Name for o in apoyo], body.Tip.Name)
    FreeCADGui.ActiveDocument.resetEdit()
    # al cerrar el croquis FreeCAD vuelve la cámara a donde estaba con una animación (más larga desde #106, que
    # centra la vista en el croquis): esperar a que termine antes del clic de 5c (una persona espera lo mismo)
    bombear(2000)
    yield 100

    traza("paso 5c")
    # 5c) Salir de Editar pieza con el croquis de un Extruir corte abierto: al cerrar el croquis no arranca nada
    antes = [o.Name for o in pdoc.Objects]
    _clic(uno.Placement.multVec(V(10, 10, 20)), uno.Name)  # lejos de la extrusión del paso 5
    ribbon._run("PartDesign_Pocket")
    bombear(1500)
    nuevos = _croquis_nuevos(pdoc, antes)
    assert nuevos and _en_edicion() is nuevos[0], "Extruir corte no abrió el croquis (5c): nuevos %s, en edición %s" % (
        [o.Name for o in nuevos], getattr(_en_edicion(), "Name", _en_edicion()))
    nuevos[0].addGeometry(Part.Circle(V(10, 10, 0), V(0, 0, 1), 3))
    ep.stop(doc)
    bombear(300)
    if _en_edicion() is nuevos[0]:
        FreeCADGui.ActiveDocument.resetEdit()
    bombear(2000)
    assert not [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "PartDesign::Pocket"],         "salir de Editar pieza y cerrar el croquis igual arrancó el corte"
    assert not FreeCADGui.Control.activeDialog() or _en_edicion() is not None, "quedó un panel abierto"
    FreeCADGui.Control.closeDialog()
    bombear(300)
    assert ep.start(uno, warn=False), "no volvió a entrar a Editar pieza"
    bombear(500)
    yield 100

    traza("paso 6")
    # 6) Una cara del OTRO componente (la misma pieza, en otro lugar): sigue lo nativo de FreeCAD (sin croquis
    # de FreeWorks); 7) Salir: en el ensamblaje todo vuelve a ser como antes
    assert pp._selection is not None
    _clic(dos.Placement.multVec(arriba), dos.Name)
    dentro, afuera = ep.selection_in_part(doc)
    assert afuera and not dentro, "la cara del otro componente se tomó como de la pieza editada: %s" % dentro
    FreeCADGui.Selection.clearSelection()
    ep.stop(doc)
    bombear(300)
    assert pp._is_assembly_doc(doc) and ep.selection_in_part(doc) is None, "después de Salir sigue el modo de edición"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
