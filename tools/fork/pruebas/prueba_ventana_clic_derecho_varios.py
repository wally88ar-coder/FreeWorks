# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Clic derecho como SW con VARIOS elegidos (etapa E1, 15/11). Con dos o más componentes elegidos (en el
árbol, o caras de dos componentes en la vista) el clic derecho muestra el menú "Componente" (bandeja y
lista de las decisiones del usuario, sin Cambiar de nombre, Propiedades ni Padre/Hijo) y no cambia la
selección. Cada opción actúa sobre TODOS en un solo Ctrl+Z: Aislar deja a la vista los elegidos (sin
dejar el documento modificado); Suprimir y Fijar los que falten; Ver relaciones las de todos; Relación de
posición abre con los dos cargados y propone Bloquear; Configurar componente (tabla) aplica todo junto y
Cancelar no cambia nada; Material va a las piezas de todos (un paso en cada pieza); Abrir pieza abre cada
pieza una sola vez. Dos caras del mismo componente: el menú de ese componente. Mezclado con otra cosa:
el menú general."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from azar_comun import bombear  # noqa: E402
from menu_comun import abrir_menu as _menu, derecho_arbol, derecho_vista  # noqa: E402

V = FreeCAD.Vector


def _sel():
    import FreeCADGui
    return sorted("%s.%s:%s" % (s.DocumentName, s.ObjectName, ",".join(s.SubElementNames))
                  for s in FreeCADGui.Selection.getSelectionEx("", 0))


def _elegir(doc, asm, *comps):
    import FreeCADGui
    FreeCADGui.Selection.clearSelection()
    for c in comps:
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, c.Name + ".")
    bombear(150)


def _bloque_con_configs(carpeta):
    """Pieza Bloque con dos configuraciones: la primera (30 de largo) y "Larga" (50)."""
    import os
    from comun import caja
    from swui.fork import configurations as cf
    pdoc = FreeCAD.newDocument("Bloque")
    body = pdoc.addObject("PartDesign::Body", "Body")
    c = caja(body, "Caja", 30, 20, 15)
    pdoc.recompute()
    cf.ensure(pdoc)
    primera = cf.active(pdoc)
    cf.add(pdoc, "Larga")
    cf.configure(pdoc, ("prop", c, "Length"), 50, "this")
    cf.activate(pdoc, primera)
    pdoc.recompute()
    ruta = os.path.join(carpeta, "Bloque.FCStd")
    pdoc.saveAs(ruta)
    FreeCAD.closeDocument(pdoc.Name)
    return ruta


def prueba():
    import FreeCADGui
    import casos_relacion as cr
    from swui.compat import QtCore, QtWidgets
    from swui.fork import config_asm, context_menus as cm, context_tools as ct, material, mates_sw

    carpeta = carpeta_temporal()
    rutas = [cr._pieza(carpeta, "Placa", 100, 60, 10), _bloque_con_configs(carpeta),
             cr._pieza(carpeta, "Suelto", 20, 20, 20)]
    doc, asm, (placa, bloque, suelto) = cr._ensamblaje(rutas)
    from swui import assembly_drop
    bloque2 = assembly_drop.insert_files(asm, [rutas[1]])[0]  # la misma pieza dos veces
    bloque.Placement.Base = V(120, 0, 0)
    bloque2.Placement = FreeCAD.Placement(V(120, 40, 0), FreeCAD.Rotation(V(0, 0, 1), 90))
    suelto.Placement.Base = V(0, 100, 0)
    _res, r = cr._relacionar(doc, asm, "coincident", [(placa, "Face6"), (bloque, "Face5")])
    doc.recompute()
    doc.save()
    gdoc = FreeCADGui.getDocument(doc.Name)
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(500)
    gdoc.Modified = False

    # 0) La parte que decide, sin ventana
    e = [(asm, [placa.Name + "."]), (asm, [bloque.Name + "."])]
    ctx = cm.context_of(e)
    assert ctx.kind == "components" and ctx.components == [placa, bloque], (ctx.kind, ctx.components)
    assert cm.context_of([(asm, [placa.Name + ".", bloque.Name + "."])]).kind == "components"
    uno = cm.context_of([(asm, [bloque.Name + ".Body.Face1", bloque.Name + ".Body.Face2"])])
    assert uno.kind == "component" and uno.component is bloque, "dos caras del mismo componente: %s" % uno.kind
    mezcla = cm.context_of([(asm, [placa.Name + "."]), (r, [""])])
    assert mezcla.kind is None, "componente + relación tenía que ser el menú general: %s" % mezcla.kind
    assert cm.title_of(ctx) == "Componente"
    # la misma cara nombrada por el Cuerpo o por la operación (comparación por la forma, no por el texto)
    cuerpo = placa.LinkedObject.Name
    caja_ = [o for o in placa.LinkedObject.Group if o.TypeId == "PartDesign::AdditiveBox"][0].Name
    assert cm.same_element(asm, "%s.%s.Face6" % (placa.Name, cuerpo), "%s.%s.Face6" % (placa.Name, caja_)), \
        "la misma cara por dos caminos no se reconoció"
    assert not cm.same_element(asm, "%s.%s.Face6" % (placa.Name, cuerpo), "%s.%s.Face5" % (placa.Name, caja_)), \
        "dos caras distintas dieron iguales"
    yield 100

    # 1) Árbol: dos componentes elegidos, clic derecho sobre uno -> menú Componente, selección igual
    _elegir(doc, asm, bloque, bloque2)
    antes = _sel()
    m = _menu(derecho_arbol(bloque2.Label))
    assert m.get("vis") is not None, "no se abrió el menú"
    assert _sel() == antes, "el clic derecho cambió la selección: %s -> %s" % (antes, _sel())
    vis = m["vis"]
    bandeja = vis[0]
    for t in ("Abrir pieza", "Abrir pieza en posición", "Ocultar", "Cambiar transparencia", "Suprimir",
              "Relación de posición", "Ver relaciones de posición", "Apariencia"):
        assert t in bandeja.strip("{}").split("|"), "árbol, varios: falta %r en la bandeja %s" % (t, bandeja)
    for t in ("Propiedades del componente...",):
        assert t not in bandeja, "árbol, varios: %r no va con varios (%s)" % (t, bandeja)
    resto = vis[1:]
    assert resto[:2] == ["Invertir la selección", "[Componente]"], "árbol, varios: %s" % vis
    for t in ("Aislar", "Fijar", "Eliminar", "Material...", "Contraer operaciones"):
        assert t in resto, "árbol, varios: falta %r (%s)" % (t, vis)
    for t in ("Cambiar de nombre", "Padre/Hijo...", "Propiedades del componente..."):
        assert t not in resto, "árbol, varios: %r no va con varios (%s)" % (t, vis)
    assert not doc.isTouched(), "abrir el menú tocó el ensamblaje"
    yield 100

    # 2) Vista: caras de dos componentes elegidas; clic derecho sobre una -> igual, sin Seleccionar otra
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.Face6" % (placa.Name, placa.LinkedObject.Name))
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.Face6" % (bloque2.Name, bloque2.LinkedObject.Name))
    antes = _sel()
    cb = bloque2.Shape.BoundBox
    m = _menu(derecho_vista(V(cb.Center.x, cb.Center.y, cb.ZMax)))
    assert m.get("vis") is not None, "vista: no se abrió el menú"
    assert _sel() == antes, "vista: el clic derecho cambió la selección: %s -> %s" % (antes, _sel())
    assert "[Componente]" in m["vis"] and "Aislar" in m["vis"], "vista, varios: %s" % m["vis"]
    assert "Seleccionar otra" not in m["vis"][0] and "Contraer operaciones" not in m["vis"], m["vis"]
    # 2b) Componentes elegidos en el árbol (enteros) y clic derecho sobre la cara de uno en la vista:
    # quedan los dos elegidos (revisión del 15/11)
    _elegir(doc, asm, placa, bloque2)
    antes = _sel()
    m = _menu(derecho_vista(V(cb.Center.x, cb.Center.y, cb.ZMax)))
    assert _sel() == antes, "árbol + vista: el clic derecho soltó lo elegido: %s -> %s" % (antes, _sel())
    assert "[Componente]" in (m.get("vis") or []), "árbol + vista: %s" % m.get("vis")
    yield 100

    # 3) Aislar con dos: quedan los dos a la vista, sin "modificado"; Salir vuelve a lo de antes
    _elegir(doc, asm, placa, bloque)
    gdoc.Modified = False
    FreeCADGui.runCommand(ct.ISOLATE)
    bombear(200)
    assert placa.Visibility and bloque.Visibility, "aislar dos: los elegidos tienen que quedar a la vista"
    assert not bloque2.Visibility and not suelto.Visibility, "aislar dos: los otros tenían que ocultarse"
    assert not gdoc.Modified, "aislar dejó el ensamblaje modificado"
    ct.exit_isolate(doc)
    assert all(c.Visibility for c in (placa, bloque, bloque2, suelto)), "salir de aislar no volvió todo"
    assert not gdoc.Modified
    yield 100

    # 4) Suprimir dos en un paso; un Ctrl+Z vuelve los dos
    _elegir(doc, asm, bloque, bloque2)
    n = len(doc.UndoNames)
    FreeCADGui.runCommand(config_asm.SUPPRESS_CMD)
    bombear(200)
    assert config_asm.is_suppressed(bloque) and config_asm.is_suppressed(bloque2), "no suprimió los dos"
    assert len(doc.UndoNames) == n + 1, "suprimir dos tenía que ser UN paso: %s" % doc.UndoNames[:3]
    doc.undo()
    doc.recompute()
    assert not config_asm.is_suppressed(bloque) and not config_asm.is_suppressed(bloque2), "Ctrl+Z no volvió los dos"
    # mezcla: uno suprimido y otro no -> Suprimir actúa sobre el que falta, Desactivar sobre el otro
    _elegir(doc, asm, bloque)
    FreeCADGui.runCommand(config_asm.SUPPRESS_CMD)
    _elegir(doc, asm, bloque, bloque2)
    assert FreeCADGui.Command.get(config_asm.SUPPRESS_CMD).isActive()
    assert FreeCADGui.Command.get(config_asm.UNSUPPRESS_CMD).isActive()
    FreeCADGui.runCommand(config_asm.UNSUPPRESS_CMD)
    assert not config_asm.is_suppressed(bloque) and not config_asm.is_suppressed(bloque2)
    yield 100

    # 5) Fijar dos que no están fijos: un paso, un Ctrl+Z los suelta a los dos; la selección queda
    _elegir(doc, asm, bloque, bloque2)
    assert mates_sw.grounded_joint(asm, bloque) is None and mates_sw.grounded_joint(asm, bloque2) is None
    antes = _sel()
    n = len(doc.UndoNames)
    FreeCADGui.runCommand(mates_sw.FIX)
    bombear(200)
    assert mates_sw.grounded_joint(asm, bloque) is not None and mates_sw.grounded_joint(asm, bloque2) is not None, \
        "Fijar no fijó los dos"
    assert len(doc.UndoNames) == n + 1, "fijar dos tenía que ser UN paso: %s" % doc.UndoNames[:3]
    assert _sel() == antes, "Fijar cambió la selección"
    doc.undo()
    doc.recompute()
    assert mates_sw.grounded_joint(asm, bloque) is None and mates_sw.grounded_joint(asm, bloque2) is None, \
        "Ctrl+Z no soltó los dos"
    yield 100

    # 6) Ver relaciones de los dos: la del bloque
    _elegir(doc, asm, bloque, bloque2)
    FreeCADGui.runCommand(mates_sw.VIEW_MATES)
    names = [s.Object.Name for s in FreeCADGui.Selection.getSelectionEx()]
    assert r.Name in names, "Ver relaciones con varios no eligió la del bloque: %s" % names

    # 7) Relación de posición con los dos elegidos: el panel abre con los dos y propone Bloquear
    _elegir(doc, asm, placa, bloque2)
    FreeCADGui.runCommand(mates_sw.COMMAND)
    bombear(600)
    panel = mates_sw._panel
    assert panel is not None, "no se abrió el panel de relaciones"
    comps = [e[0] for e in panel.entities]
    try:
        assert comps == [placa, bloque2] and [e[2] for e in panel.entities] == ["part", "part"], \
            "el panel no tomó los dos componentes: %s" % [(e[0].Label, e[2]) for e in panel.entities]
        assert mates_sw.applicable(["part", "part"]) == ["lock"]
    finally:
        panel.reject()  # Cancelar, como el usuario
        bombear(300)
    assert FreeCAD.getActiveTransaction() is None, "Cancelar el panel dejó un paso abierto"
    assert not [o for o in mates_sw.joints_of(asm) if o is not r], "Cancelar dejó una relación"

    yield 100

    # 8) Configurar componente (tabla): Cancelar no cambia; la función aplica todo en un paso
    def cerrar(aceptar):
        def hacer():
            for w in QtWidgets.QApplication.topLevelWidgets():
                if w.objectName() == "SWUI_component_configs" and w.isVisible():
                    w.accept() if aceptar else w.reject()
                    return
            QtCore.QTimer.singleShot(100, hacer)
        QtCore.QTimer.singleShot(200, hacer)
    n = len(doc.UndoNames)
    cerrar(False)
    assert not config_asm.show_configs_dialog([bloque, bloque2]), "Cancelar devolvió aceptado"
    assert len(doc.UndoNames) == n and not config_asm.is_suppressed(bloque), "Cancelar cambió algo"
    # el comando con varios queda activo (el bloque tiene dos configuraciones) y la tabla, aceptada con
    # cambios, pasa los dos a "Larga" en UN paso
    _elegir(doc, asm, bloque, bloque2)
    assert FreeCADGui.Command.get(config_asm.CONFIG_CMD).isActive(), "Configurar componente con varios no está activo"

    def aceptar_con_cambios():
        for w in QtWidgets.QApplication.topLevelWidgets():
            if w.objectName() == "SWUI_component_configs" and w.isVisible():
                t = w.findChild(QtWidgets.QTableWidget, "SWUI_component_configs_table")
                for fila in range(t.rowCount()):
                    combo = t.cellWidget(fila, 1)
                    if combo.isEnabled():
                        combo.setCurrentText("Larga")
                w.accept()
                return
        QtCore.QTimer.singleShot(100, aceptar_con_cambios)
    QtCore.QTimer.singleShot(200, aceptar_con_cambios)
    assert config_asm.show_configs_dialog([bloque, bloque2]), "Aceptar no devolvió aceptado"
    doc.recompute()
    bombear(800)
    assert config_asm.current(bloque) == "Larga" and config_asm.current(bloque2) == "Larga", \
        (config_asm.current(bloque), config_asm.current(bloque2))
    assert abs(bloque.Shape.BoundBox.XLength - 50) < 1e-6, "el bloque no tomó «Larga»: %s" % bloque.Shape.BoundBox
    assert len(doc.UndoNames) == n + 1, "configurar dos tenía que ser UN paso: %d -> %s" % (n, doc.UndoNames[:4])
    doc.undo()
    doc.recompute()
    bombear(1500)
    assert config_asm.current(bloque) != "Larga" and config_asm.current(bloque2) != "Larga", \
        "Ctrl+Z no volvió las dos configuraciones"
    config_asm.apply_configs([(bloque, None, True), (bloque2, None, True)])
    assert config_asm.is_suppressed(bloque) and config_asm.is_suppressed(bloque2)
    doc.undo()
    doc.recompute()
    assert not config_asm.is_suppressed(bloque) and not config_asm.is_suppressed(bloque2)
    yield 100

    # 9) Material para dos componentes de piezas distintas: a las dos piezas, un paso en cada una
    dlg = ct.component_material([placa, bloque, bloque2])
    bombear(200)
    info = material.all_materials()[0]
    try:
        objetivos = list(dlg.targets)
        pdocs = sorted({o.Document.Name for o in objetivos})
        assert pdocs == sorted({placa.LinkedObject.Document.Name, bloque.LinkedObject.Document.Name}), \
            "Material con varios: %s" % [o.Label for o in objetivos]
        pasos = {o.Document.Name: len(o.Document.UndoNames) for o in objetivos}
        dlg.current, dlg.editable = info, False
        dlg._apply()  # el botón Asignar de la ventana
        for o in objetivos:
            # un paso propio "Asignar material" en cada documento (FreeCAD suma "-> ..." en el que tiene
            # vínculos a otro documento cambiado: es su forma de anotar, no un paso nuestro)
            nuevos = o.Document.UndoNames[:len(o.Document.UndoNames) - pasos[o.Document.Name]]
            assert [x for x in nuevos if x == "Asignar material"] == ["Asignar material"], \
                "Material: no quedó UN paso en %s: %s" % (o.Document.Name, o.Document.UndoNames[:3])
    finally:
        dlg.close()
    for o in objetivos:
        assert o.ShapeMaterial.UUID == info["uuid"], "%s quedó sin el material" % o.Label
    for d in {o.Document for o in objetivos}:
        d.undo()
    for o in objetivos:
        assert o.ShapeMaterial.UUID != info["uuid"], "Ctrl+Z en la pieza no quitó el material de %s" % o.Label
    yield 100

    # 10) Abrir pieza con varios: cada pieza una sola vez (bloque y bloque2 son la misma)
    abiertos = ct.open_parts([bloque, bloque2, placa])
    bombear(400)
    assert [d.Name for d in abiertos] == [bloque.LinkedObject.Document.Name, placa.LinkedObject.Document.Name], \
        "Abrir pieza con varios: %s" % [d.Name for d in abiertos]
    assert FreeCADGui.ActiveDocument.Document is placa.LinkedObject.Document, "no quedó al frente la última pieza"

    # Abrir pieza en posición con dos (placa sin girar, bloque2 girado 90° en Z): cada pieza mirada
    # como en el ensamblaje, con la cámara del ensamblaje (no la de la pieza abierta antes)
    def al_frente(d):
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for w in mdi.subWindowList():
            if w.windowTitle().startswith(d.Label):
                mdi.setActiveSubWindow(w)
                break
        FreeCAD.setActiveDocument(d.Name)
        bombear(300)
    al_frente(doc)
    assert FreeCADGui.ActiveDocument.Document is doc, "no volvió al ensamblaje"
    mira = FreeCADGui.ActiveDocument.ActiveView.getViewDirection()
    docs = ct.open_parts_in_position([placa, bloque2])
    bombear(500)
    assert [d.Name for d in docs] == [placa.LinkedObject.Document.Name, bloque2.LinkedObject.Document.Name], docs
    for d, giro in ((placa.LinkedObject.Document, 0), (bloque2.LinkedObject.Document, 90)):
        vista = FreeCADGui.getDocument(d.Name).mdiViewsOfType("Gui::View3DInventor")[0]
        dir_pieza = vista.getViewDirection()
        girada = FreeCAD.Rotation(V(0, 0, 1), giro).multVec(dir_pieza)
        assert (girada - mira).Length < 1e-3, "%s no quedó mirada como en el ensamblaje: %s / %s" % (
            d.Name, girada, mira)
    al_frente(doc)

    # 11) Guardar, cerrar y abrir: nada de esto queda en el archivo; sin "modificado" de más
    doc.save()
    ruta = doc.FileName
    FreeCAD.closeDocument(doc.Name)
    bombear(300)
    doc2 = FreeCAD.openDocument(ruta)
    bombear(800)
    assert not [o for o in doc2.Objects if "SWUI_cm" in o.Name], "quedó algo del clic derecho en el archivo"
    assert not FreeCADGui.getDocument(doc2.Name).Modified, "el ensamblaje abre como modificado"
    FreeCAD.closeDocument(doc2.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
