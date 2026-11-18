# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Top-down (Editar pieza = pieza, paso 6, 17/11; como SW 2018): editando una pieza, con la cara plana de OTRO
componente elegida, Croquis abre un croquis NUEVO en la pieza editada, apoyado en una referencia externa (copia de
forma nativa en contexto, "Referencia externa (...)", oculta) de esa cara. Si el otro componente se mueve, el
croquis lo sigue al recalcular. Extruir sobre la cara de otro componente: croquis ahí y, al cerrarlo, la extrusión
en la pieza editada. Cancelar (croquis vacío) no deja la referencia suelta. Cara curva de otro componente: no se
arma nada propio (lo de FreeCAD). No saca de Editar pieza."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _al_frente(doc):
    import FreeCADGui
    from swui.compat import QtWidgets
    FreeCAD.setActiveDocument(doc.Name)
    vista = FreeCADGui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor")[0]
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in area.subWindowList():
        if sub.isAncestorOf(vista.graphicsView()):
            area.setActiveSubWindow(sub)
    bombear(500)


def _refs(pdoc):
    return [o for o in pdoc.Objects if hasattr(o, "SWUI_ExternalRef")]


def _elegir_otro(doc, asm, dos, cara="Face6"):
    import FreeCADGui
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.%s" % (dos.Name, cara))


def prueba():
    import FreeCADGui
    import Part
    import piezas_editar as pe
    from reglas_paneles import tocar
    from swui import ribbon
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, (uno, dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    _al_frente(doc)
    gdoc = FreeCADGui.getDocument(doc.Name)
    assert ep.start(uno, warn=False)
    bombear(400)
    pdoc = uno.LinkedObject.Document
    otro_doc = dos.LinkedObject.Document

    traza("paso 1")
    # 1) Croquis sobre la cara de arriba del otro componente
    _elegir_otro(doc, asm, dos)
    antes = set(o.Name for o in pdoc.Objects)
    antes_otro = set(o.Name for o in otro_doc.Objects)
    ribbon._run("PartDesign_NewSketch")
    bombear(1200)
    nuevos = [o for o in pdoc.Objects if o.Name not in antes]
    sk = [o for o in nuevos if o.TypeId == "Sketcher::SketchObject"]
    refs = _refs(pdoc)
    assert sk and len(refs) == 1, "no armó croquis + referencia en la pieza editada: %s" % [o.Name for o in nuevos]
    sk, ref = sk[0], refs[0]
    assert set(o.Name for o in otro_doc.Objects) == antes_otro, "tocó la otra pieza"
    assert sk.AttachmentSupport[0][0] is ref, "el croquis no está apoyado en la referencia externa"
    assert ref.Label.startswith("Referencia externa"), ref.Label
    assert not ref.ViewObject.Visibility, "la referencia externa quedó a la vista"
    vp = gdoc.getInEdit()
    assert getattr(vp, "Object", None) is sk, "el croquis no quedó abierto (por el ensamblaje)"
    sk.addGeometry(Part.Circle(V(10, 10, 0), V(0, 0, 1), 4))
    pdoc.recompute()
    ec.reset_edit(pdoc)
    bombear(600)
    assert ep.editing(doc) is uno, "salió de Editar pieza"
    # en el ensamblaje, el croquis está a la altura de la cara del otro (arriba: z = 20 del otro)
    z_global = uno.Placement.multVec(sk.getGlobalPlacement().Base).z
    assert abs(z_global - (dos.Placement.Base.z + 20)) < 1e-6, "croquis a z=%s" % z_global
    yield 100

    traza("paso 2")
    # 2) el otro componente se mueve: el croquis lo sigue al recalcular
    dos.Placement.Base = dos.Placement.Base + V(0, 0, 33)
    doc.recompute()
    pdoc.recompute()
    bombear(300)
    z_global = uno.Placement.multVec(sk.getGlobalPlacement().Base).z
    assert abs(z_global - (dos.Placement.Base.z + 20)) < 1e-6, "el croquis no siguió al otro: z=%s" % z_global
    # y si se mueve la pieza editada, la referencia se corrige (el contexto es el ensamblaje)
    uno.Placement.Base = uno.Placement.Base + V(0, 0, 5)
    doc.recompute()
    pdoc.recompute()
    bombear(300)
    z_global = uno.Placement.multVec(sk.getGlobalPlacement().Base).z
    assert abs(z_global - (dos.Placement.Base.z + 20)) < 1e-6, "con la pieza editada movida, z=%s" % z_global
    uno.Placement.Base = uno.Placement.Base - V(0, 0, 5)
    doc.recompute()
    pdoc.recompute()
    yield 100

    traza("paso 3")
    # 3) Cancelar: croquis vacío sobre la cara del otro -> no queda nada (ni la referencia)
    _elegir_otro(doc, asm, dos)
    antes = set(o.Name for o in pdoc.Objects)
    ribbon._run("PartDesign_NewSketch")
    bombear(1200)
    assert len(_refs(pdoc)) == 2, "no armó la segunda referencia"
    ec.reset_edit(pdoc)
    bombear(800)
    quedan = [o.Name for o in pdoc.Objects if o.Name not in antes]
    assert not quedan, "cancelar dejó %s" % quedan
    assert ep.editing(doc) is uno
    yield 100

    traza("paso 4")
    # 4) Extruir sobre la cara del otro: croquis y, al cerrarlo, la extrusión en la pieza editada
    _elegir_otro(doc, asm, dos)
    antes = set(o.Name for o in pdoc.Objects)
    ribbon._run("PartDesign_Pad")
    bombear(1200)
    sk2 = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "Sketcher::SketchObject"]
    assert sk2, "Extruir no abrió el croquis sobre la cara del otro"
    sk2 = sk2[0]
    for a, b in (((0, 0), (20, 0)), ((20, 0), (20, 10)), ((20, 10), (0, 10)), ((0, 10), (0, 0))):
        sk2.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))
    pdoc.recompute()
    ec.reset_edit(pdoc)
    bombear(2000)
    pads = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "PartDesign::Pad"]
    assert pads, "no arrancó la extrusión al cerrar el croquis"
    if FreeCADGui.Control.activeDialog():
        tocar(rechazar=False)
        bombear(800)
    pdoc.recompute()
    assert pads[0].isValid() and pads[0].Shape.Volume > 0, "la extrusión quedó mal"
    assert not [o for o in doc.Objects if o.TypeId == "PartDesign::Pad"], "la extrusión fue al ensamblaje"
    assert ep.editing(doc) is uno
    yield 100

    traza("paso 4b")
    # 4b) Convertir entidades con aristas del otro componente (croquis propio abierto): entran como externas
    sk3 = ec.new_sketch(pdoc.getObject("Extruir"), "Face6")
    bombear(600)
    n_ext = len(sk3.ExternalGeo) if hasattr(sk3, "ExternalGeo") else len(sk3.ExternalGeometry)
    FreeCADGui.Selection.clearSelection()
    aristas = [i + 1 for i, e in enumerate(dos.LinkedObject.Shape.Edges)
               if abs(e.BoundBox.ZMin - 20) < 1e-6 and abs(e.BoundBox.ZMax - 20) < 1e-6][:2]
    for i in aristas:
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Edge%d" % (dos.Name, i))
    n_refs = len(_refs(pdoc))
    ribbon._run("Sketcher_Projection")
    bombear(800)
    n_ext2 = len(sk3.ExternalGeo) if hasattr(sk3, "ExternalGeo") else len(sk3.ExternalGeometry)
    assert n_ext2 - n_ext == len(aristas) == 2, "Convertir entidades no trajo las aristas del otro: %d" % (n_ext2 - n_ext)
    assert len(_refs(pdoc)) == n_refs + 1
    assert getattr(gdoc.getInEdit(), "Object", None) is sk3, "Convertir cerró el croquis"
    if FreeCADGui.Control.activeDialog():
        FreeCADGui.Control.closeDialog()
    sk3.addGeometry(Part.Circle(V(5, 5, 0), V(0, 0, 1), 2))
    pdoc.recompute()
    ec.reset_edit(pdoc)
    bombear(500)
    assert ep.editing(doc) is uno
    yield 100

    traza("paso 5")
    # 5) cara curva (o arista) del otro: nada propio
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.Extruir.Edge1" % dos.Name)
    n = len(_refs(pdoc))
    ribbon._run("PartDesign_NewSketch")
    bombear(1000)
    assert len(_refs(pdoc)) == n, "armó una referencia con una arista"
    if FreeCADGui.Control.activeDialog():
        FreeCADGui.Control.closeDialog()
    if getattr(gdoc.getInEdit(), "Object", None) is not None:
        gdoc.resetEdit()
    bombear(400)
    yield 100

    traza("paso 6")
    # 6) Extruir "Hasta la superficie" con la cara de abajo del otro componente (puesto 60 más arriba)
    from swui.compat import QtWidgets
    dos.Placement.Base = FreeCAD.Vector(dos.Placement.Base.x, 0, 60)
    doc.recompute()
    body = uno.LinkedObject if uno.LinkedObject.TypeId == "PartDesign::Body" else \
        [o for o in pdoc.Objects if o.TypeId == "PartDesign::Body"][0]
    FreeCAD.setActiveTransaction("prueba")
    sk4 = body.newObject("Sketcher::SketchObject", "Hasta")
    sk4.AttachmentSupport = [(pdoc.getObject("Extruir"), ["Face6"])]
    sk4.MapMode = "FlatFace"
    sk4.addGeometry(Part.Circle(V(40, 30, 0), V(0, 0, 1), 3))
    pad = body.newObject("PartDesign::Pad", "HastaPad")
    pad.Profile = sk4
    pad.Length = 5
    FreeCAD.closeActiveTransaction()
    pdoc.recompute()
    ec.set_edit(pad)
    bombear(1000)
    traza("  6 abierto")
    cb = [w for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QComboBox)
          if w.isVisible() and w.objectName() == "changeMode"][0]
    cb.setCurrentIndex([i for i in range(cb.count()) if "superficie" in cb.itemText(i).lower()][0])
    bombear(500)
    assert pad.Type == "UpToFace", pad.Type
    traza("  6 modo")
    # clic de verdad (evento de mouse) en el centro de la cara de arriba del otro (z = 60 + 20)
    from swui.compat import QtCore, QtGui
    vista = gdoc.activeView()
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(500)
    centro = dos.Placement.multVec(V(30, 20, 20))
    vp = vista.graphicsView().viewport()
    cx, cy = vista.getPointOnViewport(centro)
    r = vp.devicePixelRatioF()
    punto = QtCore.QPointF(cx / r, vp.height() - cy / r)
    traza("  6 clic en %s" % punto)
    for tipo in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease):
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(
            tipo, punto, vp.mapToGlobal(punto.toPoint()), QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.LeftButton if tipo == QtCore.QEvent.Type.MouseButtonPress else QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.KeyboardModifier.NoModifier))
        bombear(100)
    bombear(1500)
    traza("  6 elegido: %s" % (pad.UpToFace,))
    assert pad.UpToFace, "Hasta la superficie no tomó la cara del otro componente"
    tocar(rechazar=False)
    traza("  6 aceptado")
    bombear(800)
    traza("  6 recalcula")
    pdoc.recompute()
    cara = pad.UpToFace
    assert cara and hasattr(cara[0], "SWUI_ExternalRef"), "Hasta la superficie no tomó la cara del otro: %s" % (cara,)
    zmax = pad.AddSubShape.BoundBox.ZMax  # lo que agrega esta extrusión (la del paso 4 siguió al otro)
    assert abs(zmax - 80) < 1e-4, "la extrusión no llega a la cara del otro: %s" % zmax
    assert ep.editing(doc) is uno
    yield 100

    traza("paso 7")
    # 7) Extruir NUEVO, "Hasta la superficie" con la cara del otro y Cancelar: no queda ni la extrusión ni la
    # referencia (la referencia entra en el paso de deshacer del panel; revisión 17/11)
    FreeCADGui.Selection.clearSelection()
    ec.select(pdoc.getObject("Extruir"), "Face6")
    antes = set(o.Name for o in pdoc.Objects)
    ribbon._run("PartDesign_Pad")
    bombear(1200)
    sk5 = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "Sketcher::SketchObject"][0]
    sk5.addGeometry(Part.Circle(V(50, 30, 0), V(0, 0, 1), 2))
    pdoc.recompute()
    ec.reset_edit(pdoc)
    bombear(2000)
    nuevo = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "PartDesign::Pad"]
    assert nuevo and FreeCADGui.Control.activeDialog(), "no se abrió el Extruir nuevo"
    cb = [w for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QComboBox)
          if w.isVisible() and w.objectName() == "changeMode"][0]
    cb.setCurrentIndex([i for i in range(cb.count()) if "superficie" in cb.itemText(i).lower()][0])
    bombear(500)
    cx, cy = vista.getPointOnViewport(dos.Placement.multVec(V(30, 20, 20)))
    punto = QtCore.QPointF(cx / r, vp.height() - cy / r)
    for tipo in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease):
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(
            tipo, punto, vp.mapToGlobal(punto.toPoint()), QtCore.Qt.MouseButton.LeftButton,
            QtCore.Qt.MouseButton.LeftButton if tipo == QtCore.QEvent.Type.MouseButtonPress else QtCore.Qt.MouseButton.NoButton,
            QtCore.Qt.KeyboardModifier.NoModifier))
        bombear(100)
    bombear(1500)
    assert nuevo[0].UpToFace, "no tomó la cara del otro"
    tocar(rechazar=True)
    bombear(800)
    quedan = [o.Name for o in pdoc.Objects if o.Name not in antes and o.TypeId != "Sketcher::SketchObject"]
    assert not quedan, "Cancelar dejó %s" % quedan
    assert ep.editing(doc) is uno
    ep.stop(doc)
    bombear(300)
    yield 100

    traza("paso 8")
    # 8) la misma pieza dos veces: la cara de la OTRA instancia no arma referencia (sería un ciclo)
    d2, asm2, (a, b) = pe.ensamblaje([pe.bloque(c, "Doble"), pe.bloque(c, "Doble")])
    if a.LinkedObject is b.LinkedObject:
        _al_frente(d2)
        assert ep.start(a, warn=False)
        bombear(400)
        assert ec.external_reference(["%s.Extruir.Face6" % b.Name]) is None, "armó una referencia circular"
        ep.stop(d2)
    else:
        traza("  (la misma pieza entró como dos archivos: sin caso)")
    bombear(300)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
