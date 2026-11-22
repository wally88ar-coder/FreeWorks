# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Esquina de confirmación, como SOLIDWORKS 2018 (pedido del usuario del 21/11; plan aprobado en
docs/pedidos/esquina_confirmacion.md).

Arriba a la derecha de la vista 3D que se ve quedan los botones de lo que está abierto en ese momento (en SW,
"Confirmation Corner"; ayuda oficial de SW 2018, "Accepting Features" y otras, revisada el 21/11):
  - un panel de operación abierto: ✓ Aceptar y ✗ Cancelar (los mismos botones del panel);
  - un croquis abierto: Salir del croquis (como la cinta) y Cancelar croquis (descarta todo lo hecho desde que se
    abrió; un croquis nuevo desaparece; la operación que esperaba el croquis, p. ej. Extruir sin croquis, no
    arranca);
  - la chapa aplanada: Salir de aplanar;
  - editando una pieza dentro del ensamblaje: Volver al ensamblaje (reemplaza la barra "Editando pieza: X — Salir").
Aislar no va acá: en SW es una barra aparte (ya hecha, context_tools).

Casos anidados (decididos por Claude el 21/11, anotados en docs/ESTADO.md): se muestra solo lo de más adentro,
en este orden: panel > croquis > chapa aplanada > Editar pieza. Así, con un croquis abierto dentro de Editar pieza
se ven Salir/Cancelar croquis; al salir del croquis aparece Volver al ensamblaje.

Lugar: arriba a la derecha de la vista; si el cubo de navegación de FreeCAD está en esa esquina, la esquina de
confirmación queda a su izquierda (no lo tapa). Opción "Habilitar esquina de confirmación" (menú FreeWorks,
prendida de fábrica, como en SW: Opciones > General).

Regla del fork "panel = cara de una función": `mode()` dice qué mostrar, `actions()` qué botones, y cada botón
llama a una función pública (`accept_panel`, `reject_panel`, `leave_sketch`, `cancel_sketch`, `exit_flat`,
`back_to_assembly`); el widget solo las muestra.
"""

import traceback

import FreeCAD
import FreeCADGui

PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
KEY = "ConfirmationCorner"
COMMAND = "SWUI_ConfirmationCorner"
SKETCH = "Sketcher::SketchObject"
NAVICUBE = "User parameter:BaseApp/Preferences/NaviCube"
VIEW = "User parameter:BaseApp/Preferences/View"
ICON_PX = 32
MARGIN = 8
TICK_MS = 250

_state = {"widget": None, "timer": None, "sig": None, "observer": None}
_marks = {}  # (documento, croquis) -> {"base": pila al abrir, "new": nuevo y vacío, "created": pila al crearlo}


# --- Opción ---------------------------------------------------------------------------------------------------


def enabled():
    return FreeCAD.ParamGet(PARAMS).GetBool(KEY, True)


def set_enabled(on):
    FreeCAD.ParamGet(PARAMS).SetBool(KEY, bool(on))
    try:  # apagada, vuelve la barra "Editando pieza — Salir"
        from swui.fork import edit_part as ep

        ep.corner_option_changed()
    except Exception:
        pass
    refresh()


# --- Qué está abierto -----------------------------------------------------------------------------------------


def _front_name():
    try:
        from swui.fork import edit_part as ep

        return ep._front_document()
    except Exception:
        return FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument is not None else None


def task_view():
    """El panel de Tareas de FreeCAD (aunque esté en la pestaña de atrás), o None. Se busca una vez y se recuerda:
    recorrer todos los widgets en cada vuelta del reloj es caro."""
    from swui.compat import QtWidgets

    tv = _state.get("tv")
    if tv is not None:
        try:
            tv.objectName()
            return tv
        except RuntimeError:
            _state["tv"] = None
    mw = FreeCADGui.getMainWindow()
    for w in mw.findChildren(QtWidgets.QWidget):
        try:
            if w.metaObject().className() == "Gui::TaskView::TaskView":
                _state["tv"] = w
                return w
        except RuntimeError:
            continue
    return None


def panel_buttons():
    """{"accept": botón, "reject": botón} del panel abierto (los que tiene y están habilitados). También con la
    pestaña Modelo al frente: la esquina sigue mostrando ✓ y ✗ (en SW, igual). Son los botones de abajo del panel
    (los de FreeCAD, en TaskEditControl); un cuadro de botones de adentro del panel solo si no hay otro."""
    from swui.compat import QtWidgets

    out = {}
    if not FreeCADGui.Control.activeDialog():
        return out
    tv = task_view()
    if tv is None:
        return out
    box_cls = QtWidgets.QDialogButtonBox
    roles = {box_cls.ButtonRole.AcceptRole: "accept", box_cls.ButtonRole.YesRole: "accept",
             box_cls.ButtonRole.RejectRole: "reject", box_cls.ButtonRole.NoRole: "reject"}
    boxes = [bx for bx in tv.findChildren(box_cls) if bx.isVisibleTo(tv)]

    def own(bx):
        try:
            return "TaskEditControl" in bx.parentWidget().metaObject().className()
        except Exception:
            return False

    boxes.sort(key=lambda bx: 0 if own(bx) else 1)
    for box in boxes[:1]:
        for b in box.buttons():
            key = roles.get(box.buttonRole(b))
            if key and key not in out and b.isVisibleTo(tv) and b.isEnabled():
                out[key] = b
    return out


def _doc(name):
    return FreeCAD.getDocument(name) if name and name in FreeCAD.listDocuments() else None


def sketch_in_edit(front=None):
    """(documento de la vista, croquis) del croquis abierto EN LA VENTANA AL FRENTE, o (None, None). Editando una
    pieza, el croquis de la pieza está abierto en la ventana del ensamblaje. Un croquis abierto en otro documento
    (otra pestaña) no cuenta: la esquina es de la vista que se ve (revisión del 21/11)."""
    front = front or _front_name()
    gd = FreeCADGui.getDocument(front) if _doc(front) is not None else None
    vp = gd.getInEdit() if gd is not None else None
    obj = getattr(vp, "Object", None) if vp is not None else None
    if obj is not None and getattr(obj, "TypeId", "") == SKETCH:
        return front, obj
    return None, None


def _panel_here(front):
    """¿El panel abierto es del documento al frente? (el activo, o la pieza que se edita desde el ensamblaje al
    frente). Con otra pestaña al frente no se muestran sus ✓/✗ (revisión del 21/11)."""
    active = FreeCAD.ActiveDocument
    if active is None or front is None:
        return True
    mine = {front}
    try:
        from swui.fork import edit_part as ep

        link = ep.editing(_doc(front))
        if link is not None:
            mine.add(link.LinkedObject.Document.Name)
    except Exception:
        pass
    # algo en edición (un croquis, una operación) en un documento que no es el del frente: el panel es de ese.
    # editDocument() lo dice aunque esa ventana no esté al frente (getInEdit no: da None)
    try:
        ed = FreeCADGui.editDocument()
        if ed is not None and ed.Document.Name not in mine:
            return False
    except Exception:
        pass
    for name in FreeCAD.listDocuments():
        if name in mine:
            continue
        gd = FreeCADGui.getDocument(name)
        vp = gd.getInEdit() if gd is not None else None
        if vp is not None and getattr(vp, "Object", None) is not None \
                and getattr(vp.Object, "TypeId", "") != "Assembly::AssemblyObject":
            return False
    return active.Name in mine


def mode(front=None):
    """
    Lo de más adentro que está abierto en la ventana al frente: ("panel", botones) | ("sketch", croquis) |
    ("flat", desarrollo) | ("edit_part", ensamblaje) | (None, None).
    """
    front = front or _front_name()
    buttons = panel_buttons() if _panel_here(front) else {}
    _view_doc, sketch = sketch_in_edit(front)
    # el panel propio del croquis (TaskDlgEditSketch) no tiene Aceptar: es el croquis, no un panel
    if buttons and "accept" in buttons:
        return "panel", buttons
    if sketch is not None:
        return "sketch", sketch
    if FreeCADGui.Control.activeDialog():
        return ("panel", buttons) if buttons else (None, None)
    doc = _doc(front)
    try:
        from swui.fork import sheet_panels

        flat = sheet_panels.flattened(doc)
        if flat is not None:
            return "flat", flat
    except Exception:
        pass
    try:
        from swui.fork import edit_part as ep

        if doc is not None and ep.editing(doc) is not None:
            return "edit_part", doc
    except Exception:
        pass
    return None, None


def _in_freeworks():
    try:
        from swui import layout

        return FreeCADGui.activeWorkbench().name() == layout.WB_NAME
    except Exception:
        return False


def actions(front=None):
    """[(clave, ícono, nombre, función)] de los botones a mostrar ahora (vacía: nada). Solo en FreeWorks: en los
    bancos de FreeCAD (con "Usar siempre FreeWorks" apagado) no hay esquina."""
    if not enabled() or not _in_freeworks():
        return []
    kind, what = mode(front)
    if kind == "panel":
        out = []
        if "accept" in what:
            out.append(("ok", "fork/c_ok", "Aceptar", accept_panel))
        if "reject" in what:
            out.append(("cancel", "fork/c_cancel", "Cancelar", reject_panel))
        return out
    if kind == "sketch":
        return [("exit_sketch", "fork/c_exit_sketch", "Salir del croquis", leave_sketch),
                ("cancel_sketch", "fork/c_cancel_sketch", "Cancelar croquis (descarta los cambios)", cancel_sketch)]
    if kind == "flat":
        return [("exit_flat", "fork/c_exit_flat", "Salir de aplanar", exit_flat)]
    if kind == "edit_part":
        return [("back_assembly", "fork/c_back_assembly", "Volver al ensamblaje", back_to_assembly)]
    return []


# --- Lo que hace cada botón --------------------------------------------------------------------------------------


def accept_panel():
    """✓: lo mismo que el botón Aceptar del panel abierto."""
    b = panel_buttons().get("accept")
    if b is None:
        return False
    b.click()
    return True


def reject_panel():
    """✗: lo mismo que el botón Cancelar del panel abierto."""
    b = panel_buttons().get("reject")
    if b is None:
        return False
    b.click()
    return True


def leave_sketch():
    """Salir del croquis: lo mismo que el botón de la cinta (Sketcher_LeaveSketch)."""
    _view, sketch = sketch_in_edit()
    if sketch is None:
        return False
    FreeCADGui.runCommand("Sketcher_LeaveSketch")
    return True


def _undo_cap():
    """Cuántos pasos de deshacer guarda FreeCAD (Preferencias > Documento); más viejos se descartan."""
    try:
        return int(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document").GetInt("MaxUndoSize", 20))
    except Exception:
        return 20


def steps_back(now, target, cap=None):
    """
    Cuántos pasos hay que deshacer para que la pila de deshacer `now` (lo más nuevo primero) vuelva a ser `target`:
    el menor k con now[k:] == target. Si la pila llegó a su tope, FreeCAD descartó los pasos más viejos: alcanza
    con que now[k:] sea el comienzo de target. None si no hay manera (p. ej. dentro del croquis se deshizo algo de
    antes de abrirlo): en ese caso no se deshace nada (revisión del 21/11: antes podía seguir hasta el fondo).
    """
    now, target = list(now), list(target)
    cap = cap or _undo_cap()
    full = len(now) >= cap
    for k in range(len(now) + 1):
        rest = now[k:]
        if rest == target:
            return k
        if full and rest and rest == target[:len(rest)]:
            return k
    return None


def _undo_steps(doc, route, k):
    """Deshace k pasos por el documento route (como Ctrl+Z en su ventana; editando una pieza, la del ensamblaje),
    contestando "Sí" si FreeCAD pregunta por transacciones de grupo. Devuelve cuántos deshizo."""
    from swui.fork import undo_route

    done = 0
    other = _doc(route)
    for _i in range(k):
        before = (doc.UndoCount, list(doc.UndoNames),
                  list(other.UndoNames) if other is not None and other is not doc else None)
        undo_route._state["routing"] = True
        try:
            undo_route.step(route, True)
        finally:
            undo_route._state["routing"] = False
        after = (doc.UndoCount, list(doc.UndoNames),
                 list(other.UndoNames) if other is not None and other is not doc else None)
        if after == before:
            break  # no se pudo deshacer más
        done += 1
    return done


def _unused_external_ref(doc):
    """¿Hay en doc una referencia a otro componente (Editar pieza) que nadie usa?"""
    try:
        from swui.fork import edit_context as ec

        mark = ec.EXTERNAL_MARK
    except Exception:
        return False
    for obj in doc.Objects:
        if getattr(obj, mark, False) and not [o for o in obj.InList if o.TypeId != "PartDesign::Body"]:
            return True
    return False


def _release_waiters(sketch):
    """Lo que esperaba que este croquis se cerrara para seguir (Extruir sin croquis, Doblar, taladro o corte de
    ensamblaje) no sigue: Cancelar croquis es "no hacer nada". True si el croquis era del taladro/corte de
    ensamblaje (lo armó él: es nuevo)."""
    try:
        from swui import pick_plane

        armed = pick_plane.armed()
        if armed and armed.get("sketch") is sketch:
            pick_plane._disarm()
    except Exception:
        pass
    try:
        from swui.fork import assembly_features as af

        pending = af._state.get("pending")
        if pending and pending.get("sketch") is sketch:
            af._state["pending"] = None
            return True
    except Exception:
        pass
    return False


def _warn(text):
    FreeCAD.Console.PrintWarning("[SWUI] %s\n" % text)
    try:
        from swui.compat import QtWidgets

        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Cancelar croquis", text)
    except Exception:
        pass


def cancel_sketch(sketch=None):
    """
    Cancelar croquis: descarta todo lo hecho en el croquis desde que se abrió (deshaciendo esos pasos con el croquis
    abierto, como Ctrl+Z) y sale. Un croquis nuevo desaparece sin dejar nada (como en SW: también se deshace su
    creación y, editando una pieza, la referencia a la cara del otro componente hecha para él; Ctrl+Z después deshace
    lo anterior, no lo trae). Lo que esperaba el croquis (Extruir sin croquis, taladro o corte de ensamblaje...) no
    sigue.
    Si la pila de deshacer no coincide con la de cuando se abrió (dentro del croquis se deshizo algo de antes) o no
    hay de dónde sacarla, no descarta nada y avisa (el croquis queda abierto). Límite: si dentro del croquis se
    hicieron más pasos que los que guarda FreeCAD (Preferencias > Documento), los más viejos no se descartan.
    Devuelve la cantidad de pasos deshechos, o None si no se hizo nada.
    """
    view_doc, current = sketch_in_edit()
    sketch = sketch or current
    if sketch is None:
        return None
    doc = sketch.Document
    name = sketch.Name
    mark = _marks.get((doc.Name, name))
    k = steps_back(doc.UndoNames, mark["base"]) if mark is not None else None
    if k is None:
        _warn("No se pudo descartar lo hecho en el croquis (la lista de deshacer cambió desde que se abrió). "
              "El croquis sigue abierto: use Deshacer o Salir del croquis.")
        return None
    new = mark["new"]
    if _release_waiters(sketch):
        new = True
    route = view_doc if view_doc and view_doc != doc.Name else doc.Name
    steps = _undo_steps(doc, route, k)
    if sketch_in_edit()[1] is sketch:
        FreeCADGui.runCommand("Sketcher_LeaveSketch")
    created = mark.get("created")
    if new and created is not None:
        from swui.compat import QtWidgets

        for _i in range(3):  # que empty_sketch termine lo suyo (borra el croquis vacío con un temporizador)
            QtWidgets.QApplication.processEvents()
        # el croquis nuevo: también su creación (y lo que borró empty_sketch al salir vacío), hasta antes de crearlo
        k2 = steps_back(doc.UndoNames, created)
        if k2:
            steps += _undo_steps(doc, route, k2)
        if doc.UndoNames[:1] == ["Referencia externa"] and _unused_external_ref(doc):
            steps += _undo_steps(doc, route, 1)
    _marks.pop((doc.Name, name), None)
    return steps


def exit_flat():
    """Salir de aplanar: la chapa del documento al frente vuelve a verse plegada."""
    from swui.fork import sheet_panels

    front = _front_name()
    doc = FreeCAD.getDocument(front) if front and front in FreeCAD.listDocuments() else None
    flat = sheet_panels.flattened(doc)
    if flat is None:
        return False
    sheet_panels.exit_flat(flat)
    return True


def back_to_assembly():
    """Volver al ensamblaje: sale de Editar pieza en el ensamblaje al frente (lo que hacía la barra "Salir")."""
    from swui.fork import edit_part as ep

    front = _front_name()
    doc = FreeCAD.getDocument(front) if front and front in FreeCAD.listDocuments() else None
    if doc is None or ep.editing(doc) is None:
        return False
    ep.stop(doc)
    return True


# --- Al abrir un croquis: anotar la pila de deshacer ---------------------------------------------------------


class _AppObserver:
    """Al crearse un croquis: la pila de deshacer de ese momento (todavía sin el paso que lo crea) = a dónde volver si
    se cancela siendo nuevo (revisión del 21/11: no suponer que su creación es el último paso al abrirlo)."""

    def slotCreatedObject(self, obj):
        try:
            doc = obj.Document
            if obj.TypeId == SKETCH and not doc.Transacting:
                names = list(doc.UndoNames)
                # con la transacción que lo crea abierta, FreeCAD ya la lista arriba (medido 21/11): no cuenta
                if getattr(doc, "HasPendingTransaction", False) and names:
                    names = names[1:]
                _created[(doc.Name, obj.Name)] = names
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        try:
            for key in [k for k in _created if k[0] == doc.Name]:
                _created.pop(key, None)
        except Exception:
            pass


_created = {}  # (documento, croquis) -> pila de deshacer justo antes de crearlo


class _GuiObserver:
    def slotInEdit(self, vp):
        try:
            obj = getattr(vp, "Object", None)
            if obj is not None and obj.TypeId == SKETCH:
                key = (obj.Document.Name, obj.Name)
                new = False
                try:
                    from swui.fork import empty_sketch

                    new = key in empty_sketch._new and empty_sketch.is_empty(obj)
                except Exception:
                    pass
                _marks[key] = {"base": list(obj.Document.UndoNames), "new": new, "created": _created.get(key)}
        except Exception:
            pass

    def slotResetEdit(self, vp):
        try:
            obj = getattr(vp, "Object", None)
            if obj is not None and obj.TypeId == SKETCH:
                _marks.pop((obj.Document.Name, obj.Name), None)
        except Exception:
            pass

    def slotDeletedDocument(self, gdoc):
        try:
            name = gdoc.Document.Name
            for k in [k for k in _marks if k[0] == name]:
                _marks.pop(k, None)
        except Exception:
            pass


# --- El widget ------------------------------------------------------------------------------------------------


def _front_view_widget(name=None):
    """El widget de dibujo de la vista 3D al frente (para ubicar la esquina), o None."""
    name = name or _front_name()
    gd = FreeCADGui.getDocument(name) if name and name in FreeCAD.listDocuments() else None
    if gd is None:
        return None
    try:
        views = gd.mdiViewsOfType("Gui::View3DInventor")
        view = gd.activeView() if gd.activeView() in views else (views[0] if views else None)
        return view.graphicsView().viewport() if view is not None else None
    except Exception:
        return None


def cube_offset():
    """Ancho a dejar libre a la derecha por el cubo de navegación de FreeCAD (0 si no está en esa esquina)."""
    try:
        if not FreeCAD.ParamGet(VIEW).GetBool("ShowNaviCube", True):
            return 0
        if FreeCAD.ParamGet(NAVICUBE).GetInt("CornerNaviCube", 1) != 1:  # 1 = arriba a la derecha
            return 0
        return int(FreeCAD.ParamGet(NAVICUBE).GetInt("CubeSize", 132)) + int(
            FreeCAD.ParamGet(NAVICUBE).GetInt("OffsetX", 0))
    except Exception:
        return 0


def _build(acts):
    from swui import paths
    from swui.compat import QtCore, QtGui, QtWidgets

    old = _state["widget"]
    if old is not None:
        try:
            old.hide()
            old.deleteLater()
        except RuntimeError:
            pass
    _state["widget"] = None
    if not acts:
        return None
    mw = FreeCADGui.getMainWindow()
    box = QtWidgets.QFrame(mw)
    box.setObjectName("SWUI_confirm_corner")
    box.setStyleSheet("#SWUI_confirm_corner { background: transparent; border: none; }"
                      "#SWUI_confirm_corner QToolButton { border: none; background: transparent; }"
                      "#SWUI_confirm_corner QToolButton:hover { background: rgba(60,130,200,40); border-radius: 3px; }")
    lay = QtWidgets.QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    for key, icon, name, fn in acts:
        b = QtWidgets.QToolButton(box)
        b.setObjectName("SWUI_corner_" + key)
        path = paths.icon(icon)
        if path:
            b.setIcon(QtGui.QIcon(path))
        b.setIconSize(QtCore.QSize(ICON_PX, ICON_PX))
        b.setToolTip(name)
        b.setAccessibleName(name)
        b.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)  # el clic no le saca el foco a la vista ni al panel

        def run(_c=False, _fn=fn, _name=name):
            # mientras corre (Cancelar croquis procesa eventos) el reloj no rehace la esquina: borraría el botón
            # que se está apretando (revisión del 21/11)
            if _state.get("busy"):
                return
            _state["busy"] = True
            try:
                _fn()
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] Esquina de confirmación (%s):\n%s\n" % (
                    _name, traceback.format_exc()))
            finally:
                _state["busy"] = False
            QtCore.QTimer.singleShot(0, refresh)

        b.clicked.connect(run)
        lay.addWidget(b)
    box.adjustSize()
    _state["widget"] = box
    return box


def _place(box, front=None):
    view = _front_view_widget(front)
    mw = FreeCADGui.getMainWindow()
    # vista desacoplada o a pantalla completa (F11): no es parte de la ventana principal; la esquina no se pone
    # ahí (mapTo avisaría en cada vuelta) (revisión del 21/11)
    if view is None or not view.isVisible() or view.window() is not mw:
        box.hide()
        return
    from swui.compat import QtCore

    top_left = view.mapTo(mw, QtCore.QPoint(0, 0))
    x = top_left.x() + view.width() - MARGIN - cube_offset() - box.width()
    y = top_left.y() + MARGIN
    box.move(max(top_left.x() + MARGIN, x), y)
    box.show()
    box.raise_()  # lección de #105: la vista puede taparla; se vuelve a poner arriba en cada vuelta


def refresh():
    """Pone la esquina al día (qué botones, dónde). La llama el reloj; también se puede llamar directo."""
    if _state.get("busy"):
        return
    try:
        mw = FreeCADGui.getMainWindow()
        if mw is None or mw.isMinimized() or not mw.isVisible():
            return
        front = _front_name()
        acts = actions(front)
        sig = tuple(a[0] for a in acts)
        box = _state["widget"]
        alive = box is not None
        if alive:
            try:
                box.isVisible()
            except RuntimeError:
                alive = False
        if sig != _state["sig"] or not alive:
            box = _build(acts)
            _state["sig"] = sig
        if box is not None:
            _place(box, front)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Esquina de confirmación:\n%s\n" % traceback.format_exc())


def widget():
    """El cuadro de la esquina a la vista (para las pruebas), o None."""
    box = _state["widget"]
    try:
        return box if box is not None and box.isVisible() else None
    except RuntimeError:
        return None


def visible_keys():
    """Claves de los botones a la vista ("ok", "cancel", "exit_sketch"...), para las pruebas."""
    box = widget()
    if box is None:
        return []
    from swui.compat import QtWidgets

    return [b.objectName()[len("SWUI_corner_"):] for b in box.findChildren(QtWidgets.QToolButton) if b.isVisible()]


# --- Comando de la opción e instalación ----------------------------------------------------------------------------


class _CornerCommand:
    def GetResources(self):
        return {
            "MenuText": "Habilitar esquina de confirmación",
            "ToolTip": "Muestra arriba a la derecha de la vista los botones para aceptar, cancelar o salir "
                       "(como SW: Opciones > General > Habilitar esquina de confirmación).",
            "Checkable": enabled(),
        }

    def IsActive(self):
        return True

    def Activated(self, checked=None):
        set_enabled(bool(checked) if checked is not None else not enabled())


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _CornerCommand())
    except Exception:
        pass  # ya registrado
    if _state["observer"] is None:
        _state["observer"] = (_GuiObserver(), _AppObserver())
        FreeCADGui.addDocumentObserver(_state["observer"][0])
        FreeCAD.addDocumentObserver(_state["observer"][1])
    if _state["timer"] is None:
        from swui.compat import QtCore

        timer = QtCore.QTimer()
        timer.setInterval(TICK_MS)
        timer.timeout.connect(refresh)
        timer.start()
        _state["timer"] = timer
