# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Esquina de confirmación como SW 2018 (21/11, partes A, B, C, E; docs/pedidos/esquina_confirmacion.md), en una
pieza sola, con clics de verdad (QTest) en sus botones:
A) arriba a la derecha de la vista, sin tapar el cubo de navegación y POR ENCIMA de la vista; nada abierto = nada.
B) panel abierto (Redondeo): ✓ y ✗; ✗ = Cancelar (no queda nada, ni paso de deshacer); ✓ = Aceptar (un paso).
C) croquis: Salir del croquis (queda lo dibujado) y Cancelar croquis (descarta lo hecho desde que se abrió; un
   croquis nuevo desaparece; Extruir sin croquis: la operación no arranca). Ctrl+Z después no rompe nada.
E) chapa aplanada: Salir de aplanar (vuelve plegada); con otro documento al frente no aparece (sigue a la ventana).
La opción del menú FreeWorks la apaga (no se ve nada) y la prende."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from deshacer_comun import al_frente  # noqa: E402
from esquina_comun import claves as _claves, clic_boton as _clic_boton, lugar_ok as _lugar_ok  # noqa: E402

V = FreeCAD.Vector






def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from croquis_esc_comun import clic, esc
    from menu_comun import pieza
    from swui import ribbon
    from swui.fork import confirm_corner as cc
    from swui.fork import edit_context as ec
    c = carpeta_temporal()
    assert cc.enabled(), "la esquina viene apagada de fábrica"
    doc, body, sk0, pad = pieza()
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = al_frente(doc)
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(800)
    assert _claves() == [], "con nada abierto se ve la esquina: %s" % _claves()
    yield 100

    traza("B) Redondeo: ✗ cancela, ✓ acepta")
    for boton in ("cancel", "ok"):
        n0, antes = doc.UndoCount, set(o.Name for o in doc.Objects)
        FreeCADGui.Selection.clearSelection()
        ec.select(pad, "Edge1")
        ribbon._run("PartDesign_Fillet")
        bombear(1500)
        assert _claves() == ["ok", "cancel"], "con el panel abierto la esquina tiene %s" % _claves()
        _lugar_ok(vista)
        _clic_boton(boton)
        assert not FreeCADGui.Control.activeDialog(), "%s no cerró el panel" % boton
        nuevos = [o.Name for o in doc.Objects if o.Name not in antes]
        traza("  %s: nuevos %s; pasos %d -> %d" % (boton, nuevos, n0, doc.UndoCount))
        if boton == "cancel":
            assert not nuevos and doc.UndoCount == n0, "✗ dejó algo: %s / pasos %d" % (nuevos, doc.UndoCount - n0)
        else:
            assert any(o.TypeId == "PartDesign::Fillet" for o in doc.Objects if o.Name in nuevos), "✓ no hizo el redondeo"
            assert doc.UndoCount == n0 + 1, "✓ dejó %d pasos" % (doc.UndoCount - n0)
    assert _claves() == [], "cerrado el panel, la esquina sigue: %s" % _claves()
    yield 100

    traza("C) croquis nuevo en la cara de arriba: Salir del croquis deja la línea")
    tope = body.Tip

    def cara_arriba():
        for i, f in enumerate(tope.Shape.Faces):
            if f.normalAt(0, 0).z > 0.99 and abs(f.BoundBox.ZMax - tope.Shape.BoundBox.ZMax) < 1e-6:
                return "Face%d" % (i + 1)

    FreeCADGui.Selection.clearSelection()
    ec.select(tope, cara_arriba())
    ribbon._run("PartDesign_NewSketch")
    bombear(2500)
    sk = getattr(gdoc.getInEdit(), "Object", None)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "no abrió el croquis"
    assert _claves() == ["exit_sketch", "cancel_sketch"], "en el croquis la esquina tiene %s" % _claves()
    _lugar_ok(vista)
    vpw = vista.graphicsView().viewport()
    z = tope.Shape.BoundBox.ZMax

    def linea(a, b):
        FreeCADGui.runCommand("Sketcher_CreateLine")
        bombear(300)
        clic(vista, a)
        clic(vista, b)
        esc(vpw)

    linea(V(10, 10, z), V(30, 10, z))
    assert sk.GeometryCount == 1, "no dibujó la línea"
    _clic_boton("exit_sketch")
    assert getattr(gdoc.getInEdit(), "Object", None) is not sk, "Salir del croquis no salió"
    assert sk.GeometryCount == 1 and sk.Name in [o.Name for o in doc.Objects], "Salir del croquis perdió la línea"
    yield 100

    traza("C) con una planilla abierta en el mismo documento (dos vistas), volver a abrir el croquis, otra línea y")
    traza("   Cancelar croquis: queda solo la primera y la pila de deshacer queda como al abrir (revisión del 21/11)")
    planilla = doc.addObject("Spreadsheet::Sheet", "Planilla")
    doc.recompute()
    planilla.ViewObject.doubleClicked()  # su vista: el documento queda con dos vistas
    bombear(800)
    vista = al_frente(doc)
    gdoc.setEdit(sk.Name)
    bombear(2000)
    al_abrir = list(doc.UndoNames)
    assert _claves() == ["exit_sketch", "cancel_sketch"], "al reabrir el croquis la esquina tiene %s" % _claves()
    traza("  otro documento al frente: la esquina no muestra el croquis de este")
    otro = FreeCAD.newDocument("OtroDoc")
    bombear(800)
    al_frente(otro)
    assert _claves() == [], "con otro documento al frente se ven los botones del croquis: %s" % _claves()
    FreeCAD.closeDocument(otro.Name)
    bombear(500)
    vista = al_frente(doc)
    assert _claves() == ["exit_sketch", "cancel_sketch"], "al volver, la esquina tiene %s" % _claves()
    linea(V(10, 25, z), V(30, 25, z))
    linea(V(40, 25, z), V(50, 30, z))
    assert sk.GeometryCount == 3, "no dibujó las líneas nuevas: %d" % sk.GeometryCount
    _clic_boton("cancel_sketch")
    traza("  geometrías después de Cancelar: %d; pasos %s (al abrir %s)" % (sk.GeometryCount, doc.UndoNames[:4],
                                                                          al_abrir[:4]))
    assert getattr(gdoc.getInEdit(), "Object", None) is not sk, "Cancelar croquis no salió"
    assert sk.GeometryCount == 1, "Cancelar croquis no descartó las líneas nuevas: %d" % sk.GeometryCount
    # la de cuando se abrió, más el "Sketch recompute" de salir del croquis
    assert cc.steps_back(doc.UndoNames, al_abrir) in (0, 1), "Cancelar croquis deshizo de más o de menos: %s / %s" % (
        doc.UndoNames, al_abrir)
    yield 100

    traza("C) croquis NUEVO con una línea y Cancelar croquis: el croquis desaparece")
    antes = set(o.Name for o in doc.Objects)
    pila_antes = list(doc.UndoNames)
    FreeCADGui.Selection.clearSelection()
    ec.select(tope, cara_arriba())
    ribbon._run("PartDesign_NewSketch")
    bombear(2500)
    nuevo = getattr(gdoc.getInEdit(), "Object", None)
    assert nuevo is not None and nuevo is not sk, "no abrió un croquis nuevo"
    linea(V(10, 30, z), V(40, 35, z))
    traza("  marca %s; creado %s; pila %s" % (cc._marks.get((doc.Name, nuevo.Name)), cc._created.get((doc.Name, nuevo.Name)),
                                             doc.UndoNames[:5]))
    _clic_boton("cancel_sketch")
    sobran = [o.Name for o in doc.Objects if o.Name not in antes]
    traza("  quedaron: %s; pasos %s" % (sobran, doc.UndoNames[:4]))
    assert not sobran, "Cancelar croquis en un croquis nuevo dejó %s" % sobran
    assert list(doc.UndoNames) == pila_antes, "la pila de deshacer no volvió a la de antes del croquis: %s / %s" % (
        doc.UndoNames, pila_antes)
    traza("  Ctrl+Z después de Cancelar: deshace lo anterior (la otra línea del primer croquis), no trae el cancelado")
    from deshacer_comun import atajo
    from swui.compat import QtCore
    n_antes = doc.UndoCount
    atajo(vista, QtCore.Qt.Key.Key_Z)
    malos = [o.Name for o in doc.Objects if not o.isValid()]
    volvio = [o.Name for o in doc.Objects if o.Name not in antes]
    traza("  después de Ctrl+Z: objetos nuevos %s; con error %s; pasos %d -> %d" % (volvio, malos, n_antes, doc.UndoCount))
    assert not volvio, "Ctrl+Z después de Cancelar trajo el croquis cancelado: %s" % volvio
    assert not malos, "Ctrl+Z después de Cancelar dejó errores: %s" % malos
    atajo(vista, QtCore.Qt.Key.Key_Y)
    assert not [o.Name for o in doc.Objects if o.Name not in antes], "Ctrl+Y trajo el croquis cancelado"
    yield 100

    traza("C) Extruir sin croquis (cara) y Cancelar croquis: la extrusión no arranca")
    antes = set(o.Name for o in doc.Objects)
    FreeCADGui.Selection.clearSelection()
    ec.select(tope, cara_arriba())
    ribbon._run("PartDesign_Pad")
    bombear(2500)
    sk3 = getattr(gdoc.getInEdit(), "Object", None)
    assert sk3 is not None and sk3.TypeId == "Sketcher::SketchObject", "Extruir no abrió el croquis"
    FreeCADGui.runCommand("Sketcher_CreateCircle")
    bombear(300)
    clic(vista, V(20, 20, z))
    clic(vista, V(24, 20, z))
    esc(vpw)
    _clic_boton("cancel_sketch")
    bombear(1500)
    sobran = [o.Name for o in doc.Objects if o.Name not in antes]
    traza("  panel abierto %s; quedaron %s" % (bool(FreeCADGui.Control.activeDialog()), sobran))
    assert not FreeCADGui.Control.activeDialog(), "Cancelar croquis igual arrancó la extrusión"
    assert not sobran, "Cancelar croquis (Extruir sin croquis) dejó %s" % sobran
    yield 100

    traza("E) chapa aplanada: Salir de aplanar; con otro documento al frente no aparece")
    from swui.fork import sheet_panels
    ruta = pe.chapa(c)
    cdoc = FreeCAD.openDocument(ruta)
    bombear(1500)
    vch = al_frente(cdoc)
    FreeCADGui.SendMsgToActiveView("ViewFit")
    cuerpo = [o for o in cdoc.Objects if o.TypeId == "PartDesign::Body"][0]
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(cuerpo)
    sheet_panels.toggle_flat()
    bombear(2500)
    flat = sheet_panels.flattened(cdoc)
    assert flat is not None, "no quedó aplanada"
    assert _claves() == ["exit_flat"], "con la chapa aplanada la esquina tiene %s" % _claves()
    _lugar_ok(vch)
    al_frente(doc)
    assert _claves() == [], "con la pieza al frente aparece la esquina de la chapa: %s" % _claves()
    vch = al_frente(cdoc)
    assert _claves() == ["exit_flat"], "al volver a la chapa no está Salir de aplanar: %s" % _claves()
    _clic_boton("exit_flat")
    assert sheet_panels.flattened(cdoc) is None and cuerpo.Visibility, "Salir de aplanar no volvió a la chapa plegada"
    assert _claves() == [], "después de Salir de aplanar la esquina sigue: %s" % _claves()
    yield 100

    traza("opción apagada: nada; prendida: vuelve")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(cuerpo)
    sheet_panels.toggle_flat()
    bombear(1500)
    try:
        FreeCADGui.runCommand(cc.COMMAND, 0)
        assert not cc.enabled(), "el comando no apagó la esquina"
        assert _claves() == [], "apagada, la esquina se ve: %s" % _claves()
    finally:
        FreeCADGui.runCommand(cc.COMMAND, 1)
    assert cc.enabled() and _claves() == ["exit_flat"], "prendida otra vez no vuelve: %s" % _claves()
    _clic_boton("exit_flat")
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
