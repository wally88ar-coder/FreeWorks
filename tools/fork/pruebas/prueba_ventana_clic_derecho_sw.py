# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Clic derecho como SW (decisiones del usuario 15/11, etapa A): en la vista el clic derecho elige lo
que está debajo del mouse (si ya estaba elegido no cambia nada); el menú de una operación en el árbol,
de una cara en la vista, de un componente en el árbol y de la cara de un componente en la vista trae
solo lo de la tabla, con sus títulos de sección como SW; lo de FreeCAD que SW no tiene queda detrás de
la "»" y se despliega en el mismo menú; lo que no sirve no está; nada en inglés. Con un croquis en
edición el menú es el de FreeCAD. Abrir el menú y cerrarlo con Esc no cambia el documento; lo que se
elige del menú hace lo que dice."""
TIPO = "completa"
import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector
INGLES = ("Fit All", "Draw Style", "Standard Views", "Go to Selection", "Rotate", "Link Actions", "Make Link",
          "Select All", "Docked", "Clarify", "Toggle", "Show Selection", "Hide Selection", "Edit Pad", "Send to")
NUNCA = ("Enviar a consola de Python", "Acciones de expresión", "Enlazar acciones", "Marcar para recalcular",
         "Ajustes del árbol", "Estilos de navegación", "Ventana de documento", "Color aleatorio", "Mover arriba",
         "Mover abajo", "Toggle Freeze")


def _menu(abrir, cerrar=True):
    """Abre un clic derecho con abrir() y devuelve (visibles, con lo de atrás, desplegado) del menú."""
    from swui.compat import QtCore, QtWidgets
    from swui.fork import context_menus as cm

    visto = {}

    class F(QtCore.QObject):
        def eventFilter(self, obj, ev):
            if (ev.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QMenu)
                    and not isinstance(obj.parent(), QtWidgets.QMenu) and "menu" not in visto):
                visto["menu"] = obj

                def leer():
                    try:
                        visto["vis"] = cm.visible_texts(obj)
                        visto["todo"] = cm.visible_texts(obj, with_hidden=True)
                        visto["acciones"] = {a.text().replace("&", ""): a for a in obj.actions()}
                        if cm.expand(obj):
                            bombear(150)
                        visto["desplegado"] = cm.visible_texts(obj)
                        visto["elegir"] = visto.get("elegir_fn")(obj) if visto.get("elegir_fn") else None
                    finally:
                        if cerrar:
                            obj.close()
                QtCore.QTimer.singleShot(350, leer)
            return False

    f = F()
    app = QtWidgets.QApplication.instance()
    app.installEventFilter(f)
    try:
        abrir()
        bombear(900)
    finally:
        app.removeEventFilter(f)
    return visto


def _arbol():
    import FreeCADGui
    from swui.compat import QtWidgets
    for t in FreeCADGui.getMainWindow().findChildren(QtWidgets.QTreeWidget):
        if t.metaObject().className() == "Gui::TreeWidget" and t.isVisible():
            return t


def _item(label):
    from swui.compat import QtWidgets
    tree = _arbol()
    it = QtWidgets.QTreeWidgetItemIterator(tree)
    while it.value():
        if it.value().text(0) == label:
            return it.value()
        it += 1


def derecho_arbol(label):
    from swui.compat import QtCore, QtGui, QtWidgets
    tree = _arbol()
    item = _item(label)
    assert item is not None, "no está %s en el árbol" % label
    tree.scrollToItem(item)
    r = tree.visualItemRect(item)
    p = QtCore.QPoint(r.left() + 30, r.center().y())
    vp = tree.viewport()

    def abrir():
        ev = QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Reason.Mouse, p, vp.mapToGlobal(p))
        QtWidgets.QApplication.sendEvent(vp, ev)
    return abrir


def _px(view, vp, p):
    s = view.getSize()
    x, y = view.getPointOnViewport(p)[:2]
    return x * vp.width() / s[0], vp.height() - y * vp.height() / s[1]


def derecho_vista(punto):
    import FreeCADGui
    from swui.compat import QtCore, QtGui, QtWidgets
    view = FreeCADGui.ActiveDocument.ActiveView
    vp = view.graphicsView().viewport()
    x, y = _px(view, vp, punto)
    R, N = QtCore.Qt.MouseButton.RightButton, QtCore.Qt.MouseButton.NoButton

    def ev(t, b, bs, dx=0):
        p = QtCore.QPointF(x + dx, y)
        return QtGui.QMouseEvent(t, p, QtCore.QPointF(vp.mapToGlobal(p)), b, bs,
                                 QtCore.Qt.KeyboardModifier.NoModifier)

    def abrir():
        for dx in (3, 1, 0):  # que FreeCAD preseleccione lo de abajo
            QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseMove, N, N, dx))
            bombear(80)
        QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseButtonPress, R, R))
        bombear(30)
        QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseButtonRelease, R, N))
    return abrir


def _sel():
    import FreeCADGui
    return sorted("%s.%s:%s" % (s.DocumentName, s.ObjectName, ",".join(s.SubElementNames))
                  for s in FreeCADGui.Selection.getSelectionEx("", 0))


def _comun(m, que):
    assert m.get("vis") is not None, "%s: no se abrió el menú" % que
    todo = m["todo"]
    for t in todo:
        for ing in INGLES:
            assert ing not in t, "%s: queda en inglés %r (%s)" % (que, t, todo)
        for nunca in NUNCA:
            assert nunca not in t, "%s: está %r, que se quitó (%s)" % (que, t, todo)


def _pieza():
    doc = FreeCAD.newDocument("Taco")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(60, 0, 0), V(60, 40, 0), V(0, 40, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    pad = body.newObject("PartDesign::Pad", "Extruir")
    pad.Profile = sk
    pad.Length = 20
    doc.recompute()
    return doc, body, sk, pad


def prueba():
    import FreeCADGui
    import casos_relacion as cr
    from swui.fork import context_menus as cm

    doc, body, sk, pad = _pieza()
    gdoc = FreeCADGui.getDocument(doc.Name)
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    doc.recompute()
    arriba = V(30, 20, 20)

    # 1) Operación en el árbol
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pad.Name + ".")
    bombear(150)
    m = _menu(derecho_arbol(pad.Label))
    _comun(m, "operación en el árbol")
    esperado = ["Editar operación", "Editar croquis", "Suprimir", "Retroceder", "Ocultar", "Apariencia",
                "[Operación (%s)]" % pad.Label, "Padre/Hijo...", "Eliminar", "Cambiar transparencia", "»"]
    assert m["vis"] == esperado, "operación en el árbol:\n%s\nesperado:\n%s" % (m["vis"], esperado)
    atras = [t for t in m["todo"] if t not in m["vis"]]
    for t in ("Copiar", "Renombrar"):
        assert any(t in a for a in atras), "operación en el árbol: %r no quedó detrás de la » (%s)" % (t, atras)
    assert "»" not in m["desplegado"] and len(m["desplegado"]) > len(m["vis"]), \
        "la » no desplegó: %s" % m["desplegado"]
    assert not doc.isTouched() and not [o for o in doc.Objects if "Touched" in o.State], "abrir el menú tocó el documento"
    yield 100

    # 2) Cara en la vista, sin nada elegido: el clic derecho la elige
    FreeCADGui.Selection.clearSelection()
    bombear(100)
    m = _menu(derecho_vista(arriba))
    sel = _sel()
    assert len(sel) == 1 and "Face" in sel[0], "el clic derecho no eligió la cara de abajo: %s" % sel
    _comun(m, "cara en la vista")
    esperado = ["Editar operación", "Editar croquis", "Suprimir", "Retroceder", "Apariencia", "Seleccionar otra",
                "Croquis", "Ocultar", "Redondeo", "Chaflán", "[Cara]", "Cambiar transparencia",
                "[Operación (%s)]" % pad.Label, "Padre/Hijo...", "Eliminar", "»"]
    assert m["vis"] == esperado, "cara en la vista:\n%s\nesperado:\n%s" % (m["vis"], esperado)
    assert "Zoom para ajustar" not in m["todo"], "Zoom/Trasladar/Girar tenía que quitarse: %s" % m["todo"]
    yield 100

    # 2b) Cara de una operación que no es la última (revisión del 15/11): el título y lo que hacen
    # Suprimir / Eliminar es la operación que creó la cara, no la última del sólido
    import Part as _P
    skc = body.newObject("Sketcher::SketchObject", "CroquisCorte")
    skc.AttachmentSupport = [(pad, "Face6")]
    skc.MapMode = "FlatFace"
    skc.addGeometry(_P.Circle(V(45, 20, 0), V(0, 0, 1), 4))
    corte = body.newObject("PartDesign::Pocket", "Corte")
    corte.Profile = skc
    corte.Length = 5
    doc.recompute()
    bombear(300)
    assert body.Tip is corte
    lado = V(30, 0, 10)  # cara del frente: la hizo la extrusión, no el corte
    FreeCADGui.Selection.clearSelection()
    elegido = {}

    def suprimir(menu):
        for a in menu.actions():
            if a.text() == "Suprimir":
                elegido["ok"] = True
                elegido["nombre"] = a.objectName()
                a.trigger()
                elegido["sel"] = [o.Name for o in FreeCADGui.Selection.getSelection()]
                elegido["activo"] = FreeCADGui.Command.get("SWUI_Suppress").isActive()
                return True
        return False
    visto = {}
    from swui.compat import QtCore as _C, QtWidgets as _W

    class F2(_C.QObject):
        def eventFilter(self, obj, ev):
            if (ev.type() == _C.QEvent.Type.Show and isinstance(obj, _W.QMenu)
                    and not isinstance(obj.parent(), _W.QMenu) and "m" not in visto):
                visto["m"] = obj

                def hacer():
                    visto["vis"] = cm.visible_texts(obj)
                    suprimir(obj)
                    obj.close()
                _C.QTimer.singleShot(350, hacer)
            return False
    f2 = F2()
    _W.QApplication.instance().installEventFilter(f2)
    derecho_vista(lado)()
    bombear(1200)
    _W.QApplication.instance().removeEventFilter(f2)
    assert "[Operación (%s)]" % pad.Label in (visto.get("vis") or []), "título: %s" % visto.get("vis")
    assert elegido.get("ok"), "no estaba Suprimir"
    doc.recompute()
    assert pad.Suppressed and not corte.Suppressed or pad.Suppressed,         "Suprimir no actuó sobre la operación del título (%s / %s) %s" % (pad.Suppressed, corte.Suppressed, elegido)
    doc.undo()
    doc.recompute()
    assert not pad.Suppressed, "Ctrl+Z no volvió la supresión"
    FreeCADGui.Selection.clearSelection()
    for o in (corte, skc):
        body.removeObject(o)
        doc.removeObject(o.Name)
    body.Tip = pad
    pad.Visibility, sk.Visibility = True, False
    doc.recompute()
    bombear(300)
    yield 100

    # 2c) Un clic derecho que no abrió menú no hace que se arme el menú de una barra de herramientas
    from swui.compat import QtWidgets as _W2
    cm._last.update(where="View", t=__import__("time").time())
    boton = _W2.QToolButton(FreeCADGui.getMainWindow())
    menu_barra = _W2.QMenu(boton)
    menu_barra.addAction("Una")
    assert not cm.arrange(menu_barra), "se armó como clic derecho el menú de una barra de herramientas"
    boton.deleteLater()

    # 3) Ya elegida: dos caras elegidas, clic derecho sobre una de ellas -> quedan las dos
    FreeCADGui.Selection.clearSelection()
    face_top = cm.plain_sub(sel[0].split(":", 1)[1])
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, face_top)
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pad.Name + ".Face1")
    antes = _sel()
    m = _menu(derecho_vista(arriba))
    assert _sel() == antes, "con lo de abajo ya elegido, el clic derecho cambió la selección: %s -> %s" % (
        antes, _sel())
    _comun(m, "dos caras")
    yield 100

    # 4) Fondo vacío sin nada elegido: queda el zoom (es lo único que hay), sin lo que no sirve
    FreeCADGui.Selection.clearSelection()
    m = _menu(derecho_vista(V(2000, 2000, -2000)))
    assert _sel() == [], "el clic derecho en el vacío eligió algo: %s" % _sel()
    _comun(m, "fondo vacío")
    assert "Zoom para ajustar" in m["vis"], "fondo vacío: falta el zoom: %s" % m["vis"]
    yield 100

    # 5) Caso general: el Cuerpo en el árbol (sin títulos, lo de FreeCAD detrás de la »)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, "")
    m = _menu(derecho_arbol(body.Label))
    _comun(m, "cuerpo")
    assert not [t for t in m["vis"] if t.startswith("[")], "cuerpo: no lleva títulos: %s" % m["vis"]
    assert "Copiar" not in m["vis"] and "»" in m["vis"], "cuerpo: Copiar tenía que ir detrás de la »: %s" % (
        m["vis"])
    yield 100

    # 6) Croquis en edición: el menú es el de FreeCAD (sin tocar) y el clic derecho no elige
    gdoc.setEdit(sk)
    bombear(800)
    FreeCADGui.Selection.clearSelection()
    m = _menu(derecho_vista(V(30, 20, 0)))
    assert not [t for t in (m.get("vis") or []) if t.startswith("[") or t == "»"], \
        "con el croquis en edición se armó el menú de FreeWorks: %s" % m.get("vis")
    gdoc.resetEdit()
    bombear(500)
    doc.recompute()
    yield 100

    # 7) Lo elegido del menú hace lo que dice: Ocultar (copia de la acción de FreeCAD)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, body.Name, pad.Name + ".")

    def ocultar(menu):
        for a in menu.actions():
            if a.text() == "Ocultar":
                a.trigger()
                return True
        return False
    from swui.compat import QtCore, QtWidgets
    visto = {}

    class F(QtCore.QObject):
        def eventFilter(self, obj, ev):
            if (ev.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QMenu)
                    and not isinstance(obj.parent(), QtWidgets.QMenu) and "m" not in visto):
                visto["m"] = obj

                def hacer():
                    visto["ok"] = ocultar(obj)
                    obj.close()
                QtCore.QTimer.singleShot(350, hacer)
            return False
    f = F()
    QtWidgets.QApplication.instance().installEventFilter(f)
    derecho_arbol(pad.Label)()
    bombear(900)
    QtWidgets.QApplication.instance().removeEventFilter(f)
    assert visto.get("ok"), "no estaba Ocultar en el menú"
    assert not body.Visibility or not pad.Visibility, "Ocultar no ocultó"
    pad.Visibility = True
    yield 100

    # 8) Ensamblaje (con la pieza abierta: dos documentos)
    carpeta = carpeta_temporal()
    rutas = [cr._pieza(carpeta, "TacoA", 60, 40, 20), cr._pieza(carpeta, "TacoB", 60, 40, 20)]
    adoc, asm, (a, b) = cr._ensamblaje(rutas)
    b.Placement.Base = V(120, 0, 0)
    adoc.recompute()
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(600)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(adoc.Name, asm.Name, b.Name + ".")
    bombear(150)
    m = _menu(derecho_arbol(b.Label))
    _comun(m, "componente en el árbol")
    esperado = ["Abrir pieza", "Ocultar", "Cambiar transparencia", "Suprimir", "Relación de posición",
                "Ver relaciones de posición", "Apariencia", "[Componente (TacoB)]", "Cambiar de nombre", "Fijar",
                "Eliminar", "»"]
    assert m["vis"] == esperado, str(cm.last_decision) + "componente en el árbol:\n%s\nesperado:\n%s" % (m["vis"], esperado)
    yield 100

    cb = b.Shape.BoundBox
    FreeCADGui.Selection.clearSelection()
    m = _menu(derecho_vista(V(cb.Center.x, cb.Center.y, cb.ZMax)))
    sel = _sel()
    assert len(sel) == 1 and b.Name in sel[0] and "Face" in sel[0], "no eligió la cara del componente: %s" % sel
    _comun(m, "componente en la vista")
    esperado = ["Seleccionar otra", "Abrir pieza", "Ocultar", "Cambiar transparencia", "Suprimir",
                "Relación de posición", "Ver relaciones de posición", "Apariencia", "[Componente (TacoB)]", "Fijar",
                "Eliminar", "»"]
    assert m["vis"] == esperado, "componente en la vista:\n%s\nesperado:\n%s" % (m["vis"], esperado)
    assert not adoc.isTouched(), "abrir el menú tocó el ensamblaje"
    yield 100

    # 9) Las acciones de FreeCAD son compartidas: después de tantos menús siguen a la vista (antes,
    # lo mandado detrás de la » quedaba oculto en el clic derecho siguiente y en la barra de menús)
    for nombre in ("Std_Copy", "Std_Placement", "Std_Properties", "Std_ToggleVisibility"):
        acciones = FreeCADGui.Command.get(nombre).getAction()
        assert acciones and all(x.isVisible() for x in acciones), "%s quedó oculto en FreeCAD" % nombre

    # 10) La parte que decide, sin ventana: un caso raro (nada / dos objetos) es el caso general
    assert cm.context_of([]).kind is None and cm.context_of([(pad, [""]), (sk, [""])]).kind is None


from _base import ejecutar  # noqa: E402
ejecutar(globals())
