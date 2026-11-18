# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Clic derecho como SW con VARIAS operaciones (etapa E2, 15/11). Con dos o más operaciones del mismo
Cuerpo elegidas en el árbol, el menú "Operaciones": bandeja Suprimir y Apariencia; Invertir la selección
(elige las otras operaciones del Cuerpo); Configurar operación, Eliminar, Cambiar transparencia, Contraer;
sin Editar, Retroceder, Ocultar ni Padre/Hijo. Con caras de dos operaciones en la vista: bandeja
Seleccionar otra, Ocultar, Suprimir, Apariencia; grupos Caras / Operaciones / Sólido (Aislar,
Eliminar...); sin Croquis, Redondeo, Chaflán ni Exportar a DXF. Suprimir actúa sobre todas (en la vista,
sobre las que crearon las caras) en un solo Ctrl+Z; Aislar aísla el sólido; Configurar operación con
varias es una tabla con las columnas de todas, Aceptar en un paso y Cancelar sin cambios. Mezclado con un
croquis, o de dos Cuerpos: el menú general. Abrir el menú no toca el documento."""
TIPO = "completa"
import FreeCAD  # noqa: E402
import Part  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from menu_comun import abrir_menu as _menu, derecho_arbol, derecho_vista, pieza as _pieza  # noqa: E402

V = FreeCAD.Vector


def _sel():
    import FreeCADGui
    return sorted("%s.%s:%s" % (s.DocumentName, s.ObjectName, ",".join(s.SubElementNames))
                  for s in FreeCADGui.Selection.getSelectionEx("", 0))


def _corte(body, pad, nombre, x, y):
    sk = body.newObject("Sketcher::SketchObject", "Croquis" + nombre)
    sk.AttachmentSupport = [(pad, "Face6")]
    sk.MapMode = "FlatFace"
    sk.addGeometry(Part.Circle(V(x, y, 0), V(0, 0, 1), 4))
    c = body.newObject("PartDesign::Pocket", nombre)
    c.Profile = sk
    c.Length = 5
    return c


def _con_menu(abrir, que):
    """Abre el menú, hace clic en el texto que y lo cierra. Devuelve (visibles, si estaba)."""
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
        bombear(1200)
    finally:
        QtWidgets.QApplication.instance().removeEventFilter(f)
    return visto.get("vis"), visto.get("ok")


def prueba():
    import FreeCADGui
    from swui.fork import config_feature, configurations as cf, context_menus as cm, context_tools as ct

    doc, body, sk, pad = _pieza()
    corte = _corte(body, pad, "Corte", 45, 20)
    corte2 = _corte(body, pad, "Corte2", 15, 20)
    otro = doc.addObject("PartDesign::Body", "Body2")
    caja = otro.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Placement.Base = V(100, 0, 0)
    doc.recompute()
    gdoc = FreeCADGui.getDocument(doc.Name)
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)

    traza("paso 0")
    # 0) La parte que decide, sin ventana
    ctx = cm.context_of([(body, [pad.Name + ".", corte.Name + "."])])
    assert ctx.kind == "features" and ctx.features == [pad, corte], (ctx.kind, ctx.features)
    assert cm.title_of(ctx) == "Operaciones"
    assert cm.context_of([(body, [pad.Name + "."]), (body, [corte.Name + "."])]).kind == "features"
    assert cm.context_of([(body, [pad.Name + ".", sk.Name + "."])]).kind is None, "con un croquis: el general"
    assert cm.context_of([(body, [pad.Name + "."]), (otro, [caja.Name + "."])]).kind is None, "dos Cuerpos: general"
    pared = next("Face%d" % (i + 1) for i, f in enumerate(body.Shape.Faces)
                 if f.Surface.__class__.__name__ == "Cylinder" and abs(f.CenterOfMass.x - 45) < 1e-3)
    arriba = next("Face%d" % (i + 1) for i, f in enumerate(body.Shape.Faces)
                  if abs(f.CenterOfMass.z - 20) < 1e-6 and f.Area > 1000)
    vista = cm.context_of([(body, [arriba, pared])])
    assert vista.kind == "features" and vista.features == [pad, corte] and vista.element_kind == "Face", \
        "caras de dos operaciones: %s %s" % (vista.kind, vista.features)
    yield 100

    traza("paso 1")
    # 1) Árbol: dos operaciones elegidas -> menú Operaciones; abrir el menú no toca nada
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pad.Name + ".")
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, corte.Name + ".")
    bombear(150)
    antes = _sel()
    m = _menu(derecho_arbol(corte.Label))
    assert m.get("vis") is not None, "árbol: no se abrió el menú"
    assert _sel() == antes, "árbol: el clic derecho cambió la selección"
    esperado = ["{Suprimir|Apariencia}", "Invertir la selección", "[Operaciones]", "Eliminar",
                "Cambiar transparencia", "Contraer operaciones", "»"]
    assert m["vis"] == esperado, "árbol, varias:\n%s\nesperado:\n%s" % (m["vis"], esperado)
    assert not doc.isTouched(), "abrir el menú tocó el documento"
    yield 100

    traza("paso 2")
    # 2) Suprimir desde el menú: las dos, un paso; Ctrl+Z vuelve las dos
    n = len(doc.UndoNames)
    _vis, ok = _con_menu(derecho_arbol(corte.Label), "Suprimir")
    assert ok, "no estaba Suprimir"
    doc.recompute()
    assert pad.Suppressed and corte.Suppressed, "Suprimir no suprimió las dos"
    assert len(doc.UndoNames) == n + 1, "suprimir dos: tenía que ser UN paso: %s" % doc.UndoNames[:3]
    doc.undo()
    doc.recompute()
    assert not pad.Suppressed and not corte.Suppressed, "Ctrl+Z no volvió las dos"
    yield 100

    traza("paso 3")
    # 3) Invertir la selección: las otras operaciones del Cuerpo
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pad.Name + ".")
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, corte.Name + ".")
    assert FreeCADGui.Command.get(ct.INVERT).isActive(), "Invertir con dos operaciones no está activo"
    _vis, ok = _con_menu(derecho_arbol(corte.Label), "Invertir la selección")
    assert ok, "no estaba Invertir la selección"
    elegidas = [o.Name for o in FreeCADGui.Selection.getSelection()]
    assert elegidas == [corte2.Name], "Invertir: %s" % elegidas
    yield 100

    traza("paso 4")
    # 4) Vista: cara de arriba (la hizo la extrusión) + pared del agujero (el corte) -> grupos Caras /
    # Operaciones / Sólido; el clic derecho sobre una no suelta la otra
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, arriba)
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pared)
    antes = _sel()
    m = _menu(derecho_vista(V(30, 30, 20)))
    assert m.get("vis") is not None, "vista: no se abrió el menú"
    assert _sel() == antes, "vista: el clic derecho cambió la selección: %s -> %s" % (antes, _sel())
    esperado = ["{Seleccionar otra|Ocultar|Suprimir|Apariencia}", "[Caras]", "Cambiar transparencia",
                "[Operaciones]", "Eliminar", "[Sólido]", "Aislar", "Eliminar...", "»"]
    assert m["vis"] == esperado, "vista, varias:\n%s\nesperado:\n%s" % (m["vis"], esperado)
    for nunca in ("Croquis", "Redondeo", "Chaflán", "Exportar a DXF/DWG...", "Editar operación"):
        assert nunca not in m["vis"][0] and nunca not in m["vis"], "vista, varias: %r no va (%s)" % (nunca, m["vis"])
    assert not doc.isTouched(), "abrir el menú de la vista tocó el documento"
    # cara + arista mezcladas: menú de la vista (grupo "Elementos"), lo de la operación sobre las que
    # crearon cara y arista (la arista del agujero del corte, no la punta)
    borde = next("Edge%d" % (i + 1) for i, e in enumerate(body.Shape.Edges)
                 if e.Curve.__class__.__name__ == "Circle" and abs(e.Curve.Center.x - 45) < 1e-3
                 and abs(e.Curve.Center.z - 20) < 1e-3)
    mix = cm.context_of([(body, [arriba, borde])])
    assert mix.kind == "features" and mix.element and getattr(mix, "mixed", False), (mix.kind, mix.element)
    assert corte in mix.features and corte2 not in mix.features, "la arista tenía que ser del corte: %s" % mix.features
    assert ("Elementos", ["Std_ToggleTransparency"]) in cm.layout(mix, "View"), cm.layout(mix, "View")
    yield 100

    traza("paso 5")
    # 5) Suprimir desde el menú de la vista: las operaciones que crearon las caras (extrusión y corte)
    n = len(doc.UndoNames)
    _vis, ok = _con_menu(derecho_vista(V(30, 30, 20)), "Suprimir")
    assert ok, "vista: no estaba Suprimir"
    doc.recompute()
    assert pad.Suppressed and corte.Suppressed, "vista: Suprimir no actuó sobre las que crearon las caras"
    assert len(doc.UndoNames) == n + 1, "vista: suprimir tenía que ser UN paso"
    doc.undo()
    doc.recompute()
    assert not pad.Suppressed and not corte.Suppressed
    traza("desactivar")
    # Desactivar supresión en el árbol, con las dos suprimidas
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, corte.Name + ".")
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, corte2.Name + ".")
    FreeCADGui.runCommand("SWUI_Suppress")
    doc.recompute()
    assert corte.Suppressed and corte2.Suppressed
    vis, ok = _con_menu(derecho_arbol(corte.Label), "Desactivar supresión")
    assert ok, "no estaba Desactivar supresión: %s" % vis
    doc.recompute()
    assert not corte.Suppressed and not corte2.Suppressed, "Desactivar supresión no actuó sobre las dos"
    yield 100

    traza("eliminar")
    # Eliminar desde el menú de la vista: caras de los dos cortes -> se borran los dos, un Ctrl+Z
    pared2 = next("Face%d" % (i + 1) for i, f in enumerate(body.Shape.Faces)
                  if f.Surface.__class__.__name__ == "Cylinder" and abs(f.CenterOfMass.x - 15) < 1e-3)
    pared1 = next("Face%d" % (i + 1) for i, f in enumerate(body.Shape.Faces)
                  if f.Surface.__class__.__name__ == "Cylinder" and abs(f.CenterOfMass.x - 45) < 1e-3)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pared1)
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pared2)
    n = len(doc.UndoNames)
    nombres = {corte.Name, corte2.Name}
    # FreeCAD pregunta antes de borrar (su aviso de dependencias): se contesta Sí, como el usuario
    from swui.compat import QtCore as _QC, QtWidgets as _QW
    pregunta = {}

    def contestar(vueltas=[0]):
        vueltas[0] += 1
        for w in _QW.QApplication.topLevelWidgets():
            if isinstance(w, _QW.QMessageBox) and w.isVisible():
                pregunta["texto"] = w.text()
                si = [b for b in w.buttons() if w.buttonRole(b) in (_QW.QMessageBox.ButtonRole.YesRole,
                                                                     _QW.QMessageBox.ButtonRole.AcceptRole)]
                pregunta["botones"] = [b.text() for b in w.buttons()]
                (si[0].click() if si else w.accept())
                return
        if vueltas[0] < 80:
            _QC.QTimer.singleShot(100, contestar)
    _QC.QTimer.singleShot(500, contestar)
    # un punto de la pared del agujero que se vea (el clic derecho sobre algo no elegido lo elegiría)
    import math
    view = FreeCADGui.ActiveDocument.ActiveView
    punto = None
    for k in range(36):
        a = math.radians(10 * k)
        q = V(45 + 4 * math.cos(a), 20 + 4 * math.sin(a), 18)
        info = view.getObjectInfo(tuple(view.getPointOnViewport(q))[:2])
        if info and str(info.get("Component", "")).endswith(pared1):
            punto = q
            break
    assert punto is not None, "no se encontró un punto visible de la pared del agujero"
    vis, ok = _con_menu(derecho_vista(punto), "Eliminar")
    bombear(1500)
    assert ok, "no estaba Eliminar: %s" % vis
    doc.recompute()
    bombear(300)
    assert not [o for o in doc.Objects if o.Name in nombres], "Eliminar no borró los dos cortes: quedan %s, preguntó %r, botones %s" % ([o.Name for o in doc.Objects if o.Name in nombres], pregunta.get("texto"), pregunta.get("botones"))
    assert len(doc.UndoNames) == n + 1, "eliminar dos tenía que ser UN paso: %s" % doc.UndoNames[:3]
    doc.undo()
    doc.recompute()
    corte, corte2 = doc.getObject("Corte"), doc.getObject("Corte2")
    assert corte is not None and corte2 is not None, "Ctrl+Z no volvió los dos cortes"
    yield 100

    traza("paso 6")
    # 6) Aislar con caras de dos operaciones: el sólido; el otro Cuerpo se oculta; sin "modificado"
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, arriba)
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pared)
    gdoc.Modified = False
    assert FreeCADGui.Command.get(ct.ISOLATE).isActive(), "Aislar no está activo con dos caras"
    FreeCADGui.runCommand(ct.ISOLATE)
    bombear(200)
    assert body.Visibility and not otro.Visibility, "Aislar no aisló el sólido"
    assert not gdoc.Modified
    ct.exit_isolate(doc)
    assert otro.Visibility
    yield 100

    traza("paso 7")
    # 7) Configurar operación con dos: una tabla con las columnas de las dos; Cancelar no cambia;
    # Aceptar con el corte suprimido en la configuración activa -> un paso
    cf.ensure(doc)
    cf.add(doc, "Otra")
    cf.activate(doc, cf.names(doc)[0])
    doc.recompute()
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pad.Name + ".")
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, corte.Name + ".")
    assert FreeCADGui.Command.get(config_feature.COMMAND).isActive(), "Configurar operación con dos no está activo"
    n = len(doc.UndoNames)
    dlg = config_feature.Dialog([pad, corte])
    titulos = [dlg.table.horizontalHeaderItem(c).text() for c in range(dlg.table.columnCount())]
    assert "%s: Suprimir" % pad.Label in titulos and "%s: Suprimir" % corte.Label in titulos, titulos
    from swui.compat import QtCore
    dlg.table.item(0, titulos.index("%s: Suprimir" % corte.Label)).setCheckState(QtCore.Qt.CheckState.Checked)
    dlg.reject()  # Cancelar con un cambio hecho en la tabla
    doc.recompute()
    assert len(doc.UndoNames) == n and not corte.Suppressed, "Cancelar cambió algo"
    traza("configurar desde la vista")
    # desde el menú de la vista, con caras de las dos: está "Configurar operación" y abre la tabla
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, arriba)
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pared)
    from swui.compat import QtWidgets as _QW
    abierta = {}

    def cerrar_tabla():
        for w in _QW.QApplication.topLevelWidgets():
            if isinstance(w, config_feature.Dialog) and w.isVisible():
                abierta["titulo"] = w.windowTitle()
                w.reject()
                return
        QtCore.QTimer.singleShot(100, cerrar_tabla)
    QtCore.QTimer.singleShot(600, cerrar_tabla)
    vis, ok = _con_menu(derecho_vista(V(30, 30, 20)), "Configurar operación")
    bombear(800)
    assert ok, "vista: no estaba Configurar operación: %s" % vis
    assert pad.Label in abierta.get("titulo", "") and corte.Label in abierta.get("titulo", ""), \
        "la tabla no se abrió con las dos operaciones de las caras: %s" % abierta
    n = len(doc.UndoNames)
    dlg = config_feature.Dialog([pad, corte])
    from swui.compat import QtCore
    fila = cf.names(doc).index(cf.active(doc))
    col = titulos.index("%s: Suprimir" % corte.Label)
    dlg.table.item(fila, col).setCheckState(QtCore.Qt.CheckState.Checked)
    dlg._accept()
    doc.recompute()
    bombear(300)
    assert corte.Suppressed, "Aceptar no suprimió el corte en la configuración activa"
    assert not pad.Suppressed
    assert len(doc.UndoNames) == n + 1, "configurar dos: tenía que ser UN paso: %s" % doc.UndoNames[:3]
    doc.undo()
    doc.recompute()
    bombear(300)
    assert not corte.Suppressed, "Ctrl+Z no volvió"
    yield 100

    traza("paso 8")
    # 8) Guardar, cerrar y abrir: sin "modificado"
    from _base import carpeta_temporal
    import os
    ruta = os.path.join(carpeta_temporal(), "Operaciones.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    bombear(300)
    doc2 = FreeCAD.openDocument(ruta)
    bombear(800)
    assert not FreeCADGui.getDocument(doc2.Name).Modified, "abre como modificado"
    FreeCAD.closeDocument(doc2.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
