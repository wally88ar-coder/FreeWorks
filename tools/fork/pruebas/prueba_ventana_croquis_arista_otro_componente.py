# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Top-down, paso 4 (18/11, decisión del usuario: mejor que SW): editando una pieza dentro de un ensamblaje con un
croquis abierto, un clic en una arista o vértice de OTRO componente lo trae solo al croquis, por una referencia
externa (copia de forma en contexto) en el Cuerpo del croquis, sin Convertir entidades; queda elegido. Repetir el
clic no lo duplica. Las aristas de la pieza editada se enganchan en su lugar aunque el componente esté movido
(antes quedaban corridas). Si el otro componente se mueve, la referencia lo sigue. Ctrl+Z la saca entera.
Con la herramienta Línea, empezar en el vértice de otro componente deja la línea pegada a él (la referencia queda);
si se cancela con Esc sin usarla, no queda nada."""
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


def _mouse(vista, punto_3d, apretar=True):
    """Mueve el mouse al punto (coordenadas del ensamblaje) y, si apretar, hace clic (eventos de verdad)."""
    from swui.compat import QtCore, QtGui, QtWidgets
    vp = vista.graphicsView().viewport()
    cx, cy = vista.getPointOnViewport(punto_3d)
    r = vp.devicePixelRatioF()
    punto = QtCore.QPointF(cx / r, vp.height() - cy / r)
    nada = QtCore.Qt.MouseButton.NoButton
    izq = QtCore.Qt.MouseButton.LeftButton
    sin = QtCore.Qt.KeyboardModifier.NoModifier
    QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, punto,
                                                           vp.mapToGlobal(punto.toPoint()), nada, nada, sin))
    bombear(300)
    if apretar:
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonPress, punto,
                                                               vp.mapToGlobal(punto.toPoint()), izq, izq, sin))
        bombear(150)
        QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseButtonRelease, punto,
                                                               vp.mapToGlobal(punto.toPoint()), izq, nada, sin))
        bombear(500)


def _externas(sk):
    """[(objeto, elemento)] de la geometría externa del croquis."""
    out = []
    for target, subs in sk.ExternalGeometry:
        for s in subs:
            out.append((target, s))
    return out


def _punto_externa(sk, ctx, i, cual="medio"):
    """Punto (en el ensamblaje) de la geometría externa número i (desde 0) del croquis."""
    from swui.fork import edit_context as ec
    geo = sk.ExternalGeo[2 + i].toShape()  # 0 y 1: los ejes del croquis
    plc = ec.part_placement(ctx).multiply(sk.getGlobalPlacement())
    if geo.ShapeType == "Vertex" or cual == "punto":
        p = geo.Vertexes[0].Point
    else:
        e = geo.Edges[0]
        p = e.valueAt((e.FirstParameter + e.LastParameter) / 2)
    return plc.multVec(p)


def _en_plano(sk, ctx, punto):
    """El punto (ensamblaje) proyectado sobre el plano del croquis: la geometría externa se proyecta ahí (como
    Convertir entidades en SW)."""
    from swui.fork import edit_context as ec
    plc = ec.part_placement(ctx).multiply(sk.getGlobalPlacement())
    n = plc.Rotation.multVec(V(0, 0, 1))
    return punto - n * (punto - plc.Base).dot(n)


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from reglas_paneles import ctrl_z
    from swui import ribbon
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, (uno, dos) = pe.ensamblaje([pe.bloque(c), pe.bloque(c, "Otro")])
    # la pieza editada, movida (no en el origen): sus aristas tienen que engancharse donde se ven
    uno.Placement.Base = V(0, -30, 15)
    doc.recompute()
    _al_frente(doc)
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.activeView()
    assert ep.start(uno, warn=False)
    bombear(400)
    pdoc = uno.LinkedObject.Document
    otro_doc = dos.LinkedObject.Document
    pad = pdoc.getObject("Extruir")
    ctx = ec.for_document(pdoc)
    assert ctx is not None, "no quedó editando la pieza"

    traza("paso 1")
    # 1) Croquis en la cara de arriba de la pieza editada
    assert ec.select(pad, "Face6")
    ribbon._run("PartDesign_NewSketch")
    bombear(1200)
    vp_edit = gdoc.getInEdit()
    sk = getattr(vp_edit, "Object", None)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "no quedó un croquis abierto: %s" % sk
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    yield 100

    traza("paso 2")
    # 2) clic (sin herramienta) en la arista de abajo-adelante de la cara de arriba del OTRO (z = 20 local)
    medio_otro = dos.Placement.multVec(V(30, 0, 20))
    antes = set(o.Name for o in pdoc.Objects)
    antes_otro = set(o.Name for o in otro_doc.Objects)
    FreeCADGui.Selection.clearSelection()
    _mouse(vista, medio_otro)
    refs = _refs(pdoc)
    traza("  externas: %s" % [(t.Name, s) for t, s in _externas(sk)])
    assert len(refs) == 1, "no armó la referencia externa: %s" % [o.Name for o in pdoc.Objects if o.Name not in antes]
    ref = refs[0]
    assert set(o.Name for o in otro_doc.Objects) == antes_otro, "tocó la otra pieza"
    assert ref in [t for t, _s in _externas(sk)], "la referencia no entró al croquis"
    assert not ref.ViewObject.Visibility, "la referencia externa quedó a la vista"
    i = [t for t, _s in _externas(sk)].index(ref)
    p = _punto_externa(sk, ctx, i)
    quiero = _en_plano(sk, ctx, medio_otro)
    assert (p - quiero).Length < 1e-4, "la arista traída no está donde la del otro: %s vs %s" % (p, quiero)
    elegido = [s for x in FreeCADGui.Selection.getSelectionEx("", 0) for s in x.SubElementNames]
    traza("  elegido: %s" % elegido)
    assert any(s.endswith("ExternalEdge%d" % (i + 1)) for s in elegido), "no quedó elegida: %s" % elegido
    assert ep.editing(doc) is uno, "salió de Editar pieza"
    yield 100

    traza("paso 3")
    # 3) el mismo clic otra vez: no duplica
    FreeCADGui.Selection.clearSelection()
    _mouse(vista, medio_otro)
    assert len(_refs(pdoc)) == 1, "duplicó la referencia"
    assert len(_externas(sk)) == 1, "duplicó la geometría externa: %s" % _externas(sk)
    yield 100

    traza("paso 4")
    # 4) arista de la pieza editada (movida): la de abajo-adelante de la cara de abajo (z = 0 local)
    medio_uno = uno.Placement.multVec(V(30, 0, 0))
    FreeCADGui.Selection.clearSelection()
    _mouse(vista, medio_uno)
    ext = _externas(sk)
    traza("  externas: %s" % [(t.Name, s) for t, s in ext])
    assert len(ext) == 2 and ext[1][0] is pad, "no trajo la arista de la propia pieza: %s" % [(t.Name, s) for t, s in ext]
    p = _punto_externa(sk, ctx, 1)
    quiero = _en_plano(sk, ctx, medio_uno)
    assert (p - quiero).Length < 1e-4, "la arista propia no es la del clic (corrida): %s vs %s" % (p, quiero)
    yield 100

    traza("paso 5")
    # 5) el otro componente se mueve: la referencia lo sigue
    dos.Placement.Base = dos.Placement.Base + V(0, 0, 10)
    doc.recompute()
    pdoc.recompute()
    bombear(400)
    p = _punto_externa(sk, ctx, 0)
    esperado = _en_plano(sk, ctx, dos.Placement.multVec(V(30, 0, 20)))
    assert (p - esperado).Length < 1e-4, "no siguió al otro componente: %s vs %s" % (p, esperado)
    yield 100

    traza("paso 6")
    # 6) Ctrl+Z: primero la arista propia, después la del otro entera (copia incluida)
    ctrl_z(pdoc)
    bombear(400)
    assert len(_externas(sk)) == 1, "Ctrl+Z no sacó la arista propia: %s" % _externas(sk)
    ctrl_z(pdoc)
    bombear(600)
    assert not _externas(sk), "Ctrl+Z no sacó la del otro: %s" % _externas(sk)
    assert not _refs(pdoc), "Ctrl+Z dejó la referencia externa"
    assert getattr(gdoc.getInEdit(), "Object", None) is sk, "Ctrl+Z cerró el croquis"
    yield 100

    traza("paso 6b")
    # 6b) Línea, clic en un vértice del otro y Esc (cancelar): no queda nada (revisión del 18/11, hallazgo 4)
    from swui.compat import QtCore, QtGui, QtWidgets
    vpw = vista.graphicsView().viewport()

    def esc():
        for t in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
            QtWidgets.QApplication.sendEvent(vpw, QtGui.QKeyEvent(t, QtCore.Qt.Key.Key_Escape,
                                                                  QtCore.Qt.KeyboardModifier.NoModifier))
        bombear(300)
    n_geo = len(sk.Geometry)
    _al_frente(doc)  # ctrl_z de la prueba deja activa la pieza; el usuario trabaja en la ventana del ensamblaje
    FreeCADGui.runCommand("Sketcher_CreateLine")
    bombear(500)
    assert vpw.cursor().shape() != QtCore.Qt.CursorShape.ArrowCursor, "no arrancó la herramienta Línea"
    _mouse(vista, dos.Placement.multVec(V(60, 40, 20)))
    traza("  traída al clic: %s" % [(t.Name, s) for t, s in _externas(sk)])
    esc()
    esc()
    bombear(1500)  # lo traído se revisa cuando termina la herramienta
    traza("  después de Esc: externas %s, referencias %s" % ([(t.Name, s) for t, s in _externas(sk)],
                                                             [o.Name for o in _refs(pdoc)]))
    assert not _externas(sk) and not _refs(pdoc), "cancelar la Línea dejó la referencia del otro"
    assert len(sk.Geometry) == n_geo, "cancelar la Línea dejó geometría"
    assert getattr(gdoc.getInEdit(), "Object", None) is sk, "Esc cerró el croquis"
    yield 100

    traza("paso 7")
    # 7) Línea que empieza en un vértice del otro: la línea queda pegada a él
    esquina = dos.Placement.multVec(V(0, 0, 20))
    FreeCADGui.runCommand("Sketcher_CreateLine")
    bombear(500)
    n_geo = len(sk.Geometry)
    _mouse(vista, esquina)
    traza("  primer clic: externas %s, cursor %s, esquina en el croquis %s" % (
        [(t.Name, s) for t, s in _externas(sk)], vpw.cursor().shape(),
        ec.part_placement(ctx).multiply(sk.getGlobalPlacement()).inverse().multVec(esquina)))
    _mouse(vista, uno.Placement.multVec(V(30, 20, 20)))
    bombear(500)
    esc()  # soltar la herramienta
    esc()
    bombear(1500)
    pdoc.recompute()
    traza("  geometrías: %d -> %d; externas %s; restricciones %s" % (
        n_geo, len(sk.Geometry), [(t.Name, s) for t, s in _externas(sk)],
        [(k.Type, k.First, k.Second) for k in sk.Constraints]))
    refs = _refs(pdoc)
    assert len(refs) == 1 and _externas(sk), "el vértice del otro no entró como referencia"
    assert len(sk.Geometry) == n_geo + 1, "no se dibujó la línea"
    linea = sk.Geometry[-1]
    traza("  línea: %s -> %s; vértice en el croquis: %s" % (linea.StartPoint, linea.EndPoint,
          [g.toShape().Vertexes[0].Point for g in sk.ExternalGeo[2:] if g.toShape().ShapeType == "Vertex"]))
    pegada = [k for k in sk.Constraints if k.Type == "Coincident" and (k.First <= -3 or k.Second <= -3)]
    assert pegada, "la línea no quedó pegada al vértice del otro"
    yield 100

    traza("paso 8")
    # 8) cerrar el croquis: sigue editando la pieza, nada en el ensamblaje ni en la otra pieza
    ec.reset_edit(pdoc)
    bombear(600)
    assert ep.editing(doc) is uno, "salió de Editar pieza"
    assert set(o.Name for o in otro_doc.Objects) == antes_otro, "tocó la otra pieza"
    ep.stop(doc)
    bombear(300)
    for d in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(d.Name)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
