# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Sin el aviso "Referencia" de FreeCAD (pedido del usuario, 07/11: "tiene que ser lo más
similar a SW"). En SW una pieza multicuerpo es una sola pieza: cualquier cara de cualquier
sólido sirve, sin preguntas. En Part Design cada sólido es un Cuerpo y, si lo elegido es de
otro Cuerpo que el activo, FreeCAD pregunta "Hacer copia independiente / dependiente / Crear
referencia cruzada" (diálogo DlgReference). Con piezas soldadas (un Cuerpo por miembro) y
multicuerpo salía todo el tiempo; el usuario lo vio con el Asistente para taladro.

Dos casos y una red de seguridad:

A. La operación va EN el sólido de lo elegido (croquis sobre una cara, taladro, extruir
   desde una cara, redondeo...). Antes de arrancar cualquier comando de la cinta o de los
   menús, y antes de abrir el croquis desde el panel "elegí una cara", se activa el Cuerpo de
   lo elegido (`activate_for_selection`). Es lo que ya hace auto_body al elegir, pero ese se
   salteaba con un panel abierto (el panel "elegí una cara" del taladro: así le pasó al
   usuario).

B. La operación va en un sólido y toma una referencia de OTRO (hasta una cara de otro
   miembro, plano de simetría, eje...). En SW queda asociada; el equivalente de FreeCAD es la
   "copia dependiente" (SubShapeBinder que sigue al original). La red de seguridad la elige
   sola cuando el aviso sale dentro de un panel.

Red de seguridad: si el aviso aparece igual, se contesta solo, sin mostrarlo:
- con un panel abierto (caso B): "Hacer copia dependiente";
- sin panel (caso A por un camino no previsto): Cancelar, activar el Cuerpo de lo elegido y
  volver a lanzar el último comando de la cinta (una sola vez).
Cada vez queda anotado en el informe (Ver > Paneles > Vista de informe) para cubrir ese camino.
No guarda nada propio en el archivo.
"""

import time
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

# nombre del diálogo nativo: en 1.1.4 "PartDesignGui__DlgReference" (:: pasa a __)
DIALOG = "DlgReference"
DEPENDENT = "radioDependent"
RETRY_S = 5.0  # el aviso de un comando sale enseguida; más tarde no se relanza nada

_state = {"filter": None, "last": None, "retried": None, "installed": False}


# --- A: activar el Cuerpo de lo elegido ------------------------------------------------


def bodies_in(sel):
    """sel = [(objeto, [subelementos])]: los Cuerpos distintos de lo elegido (en orden)."""
    from swui.fork import auto_body

    out = []
    for obj, _subs in sel:
        body = auto_body.body_of(obj)
        if body is not None and body not in out:
            out.append(body)
    return out


def target_body(sel):
    """El Cuerpo donde va la operación: el único de lo elegido; None si hay 0 o varios."""
    bodies = bodies_in(sel)
    return bodies[0] if len(bodies) == 1 else None


def _selection():
    try:
        return [(s.Object, list(s.SubElementNames or [])) for s in FreeCADGui.Selection.getSelectionEx()]
    except Exception:
        return []


def _is_assembly(doc):
    return any(getattr(o, "TypeId", "") == "Assembly::AssemblyObject" for o in doc.Objects)


def activate_for_selection():
    """
    Activa el Cuerpo de lo elegido si es uno solo y no es el activo. Nada si hay un panel
    abierto o algo en edición (ese panel decide), en un ensamblaje o en la copia de un
    componente configurado. Devuelve el Cuerpo activado, o None.
    """
    try:
        doc = FreeCAD.ActiveDocument
        gdoc = FreeCADGui.ActiveDocument
        if doc is None or gdoc is None or _is_assembly(doc):
            return None
        if FreeCADGui.Control.activeDialog() or gdoc.getInEdit() is not None:
            return None
        body = target_body(_selection())
        if body is None:
            return None
        from swui.fork import configurations as cf

        if cf.is_copy(body):
            return None
        view = gdoc.ActiveView
        if view is None or view.getActiveObject("pdbody") is body:
            return None
        view.setActiveObject("pdbody", body)
        return body
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cuerpo de lo elegido:\n%s\n" % traceback.format_exc())
        return None


def _wrap_ribbon():
    """Todo botón de la cinta y todo menú de FreeWorks pasa por ribbon._run."""
    from swui import ribbon

    original = ribbon._run
    if getattr(original, "_swui_cross_body", False):
        return

    def run(command, index=None, *args):
        _state["last"] = (command, index, time.time())
        activate_for_selection()
        return original(command, index, *args)

    run._swui_cross_body = True
    ribbon._run = run


def _wrap_pick_plane():
    """Panel "elegí una cara" (croquis, extruir, taladro sin selección): al elegir, su Cuerpo."""
    from swui import pick_plane

    original = pick_plane.start_sketch
    if getattr(original, "_swui_cross_body", False):
        return

    def start_sketch(command):
        activate_for_selection()
        return original(command)

    start_sketch._swui_cross_body = True
    pick_plane.start_sketch = start_sketch


# --- B: referencia de otro sólido = copia dependiente (como SW: queda asociada) --------

BINDER = "PartDesign::SubShapeBinder"
ORIGIN_TYPES = ("App::Line", "App::Plane", "App::Point")


def needs_binder(body, obj):
    """¿(obj) queda fuera del alcance de una operación de `body`? (otro Cuerpo o suelto)."""
    from swui.fork import auto_body

    if body is None or obj is None:
        return False
    other = auto_body.body_of(obj)
    if other is body:
        return False
    if other is None and getattr(obj, "TypeId", "") in ORIGIN_TYPES:
        return False  # origen del documento: FreeCAD lo acepta
    return True


def bind_ref(body, obj, sub):
    """
    Referencia usable desde `body` (función pública: la usan los paneles y la IA).
    Lo del mismo Cuerpo vuelve igual: (obj, [sub]). Lo de otro Cuerpo pasa por una copia
    dependiente oculta (PartDesign::SubShapeBinder dentro de `body`, la misma que pone la
    "copia dependiente" de FreeCAD; si ya hay una de lo mismo, se reusa) -> (copia, ["Face1"]).
    """
    if not needs_binder(body, obj):
        return (obj, [sub])
    support = [(obj, (sub,) if sub else ())]
    binder = None
    for o in body.Group:
        try:
            if o.TypeId == BINDER and [(s[0], tuple(s[1])) for s in o.Support] == support:
                binder = o
                break
        except Exception:
            pass
    if binder is None:
        binder = body.newObject(BINDER, "Referencia")
        binder.Label = "Referencia de %s" % _owner_label(obj)
        binder.Support = support
        try:
            binder.Visibility = False
        except Exception:
            pass
        _state.setdefault("made", []).append((binder.Document.Name, binder.Name))
    binder.recompute()
    leaf = sub.split(".")[-1] if sub else ""
    for prefix in ("Face", "Edge", "Vertex"):
        if leaf.startswith(prefix):
            return (binder, [prefix + "1"])
    return (binder, [""])


def _owner_label(obj):
    from swui.fork import auto_body

    body = auto_body.body_of(obj)
    return (body or obj).Label


def prune_unused():
    """Copias puestas por bind_ref que al final nadie usa (se eligió otra cosa): se borran."""
    left = []
    for doc_name, name in _state.get("made", []):
        try:
            doc = FreeCAD.getDocument(doc_name)
            obj = doc.getObject(name)
        except Exception:
            continue
        if obj is None:
            continue
        users = [o for o in obj.InList if o.TypeId != "PartDesign::Body"]
        if users:
            left.append((doc_name, name))
            continue
        try:
            doc.removeObject(name)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Copia sin usar:\n%s\n" % traceback.format_exc())
    _state["made"] = left


def _own_body(panel):
    from swui.fork import auto_body

    return auto_body.body_of(panel.obj)


def _circle_edge(shape, sub):
    """Cara cilíndrica -> nombre de una arista circular suya (mismo eje), o None."""
    from swui.fork import dress_up_panel as dp

    face = dp._element(shape, sub)
    try:
        if type(face.Surface).__name__ not in ("Cylinder", "Cone"):
            return None
    except Exception:
        return None
    for edge in face.Edges:
        if type(getattr(edge, "Curve", None)).__name__ == "Circle":
            for i, cand in enumerate(shape.Edges):
                if cand.isSame(edge):
                    return "Edge%d" % (i + 1)
    return None


def _hook_patterns():
    """Matriz lineal / circular / Simetría: dirección, eje o plano de otro sólido."""
    from swui.fork import dress_up_panel as dp
    from swui.fork import pattern_panel as pp

    original = pp.TransformedPanel._pick
    if getattr(original, "_swui_cross_body", False):
        return

    def _pick(self, obj, sub):
        try:
            prop = self._active_ref()
            body = _own_body(self)
            if prop and sub and obj not in (self.obj, self.base) and needs_binder(body, obj):
                if sub.startswith("Face") and prop == "Axis":
                    edge = _circle_edge(obj.Shape, sub)
                    if edge is not None:
                        sub = edge
                geo = dp._element(obj.Shape, sub)
                if geo is not None and (sub.startswith("Edge") or
                                        (sub.startswith("Face") and self._accepts_face(geo))):
                    return self._set_ref(prop, bind_ref(body, obj, sub))
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Referencia de otro sólido:\n%s\n" % traceback.format_exc())
        return original(self, obj, sub)

    _pick._swui_cross_body = True
    pp.TransformedPanel._pick = _pick


def _hook_draft():
    """Ángulo de salida: plano neutro en una cara de otro sólido."""
    from swui.fork import dress_up_panel as dp

    original = dp.DraftPanel._pick
    if getattr(original, "_swui_cross_body", False):
        return

    def _pick(self, obj, sub):
        try:
            body = _own_body(self)
            if getattr(self, "active", None) is self.neutral and sub.startswith("Face") \
                    and obj not in (self.obj, self.base) and needs_binder(body, obj):
                face = dp._element(obj.Shape, sub)
                if face is not None and type(face.Surface).__name__ == "Plane":
                    self.neutral_ref = bind_ref(body, obj, sub)
                    self._show_neutral()
                    self._activate(self.list)
                    return True
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Plano neutro de otro sólido:\n%s\n" % traceback.format_exc())
        return original(self, obj, sub)

    _pick._swui_cross_body = True
    dp.DraftPanel._pick = _pick


# Redondeo, chaflán y ángulo de salida arrancados sin nada elegido van al Cuerpo activo; si lo
# primero que se toca es de otro sólido, en SW la operación es de ese sólido: se cancela la
# vacía y se vuelve a lanzar con lo tocado elegido (su Cuerpo queda activo).
RESTART = {"PartDesign::Fillet": "PartDesign_Fillet", "PartDesign::Chamfer": "PartDesign_Chamfer",
           "PartDesign::Draft": "PartDesign_Draft"}


def _hook_dress_up():
    from swui.fork import dress_up_panel as dp

    original = dp.DressUpPanel._pick
    if getattr(original, "_swui_cross_body_restart", False):
        return

    def _pick(self, obj, sub):
        try:
            command = RESTART.get(self.obj.TypeId)
            if command and self.is_new and not self.subs and sub.startswith(("Edge", "Face")) \
                    and obj not in (self.obj, self.base) \
                    and getattr(self, "active", self.list) is self.list:  # redondeo: sin casillas
                from swui.fork import auto_body

                body = auto_body.body_of(obj)
                if body is not None and body is not _own_body(self):
                    QtCore.QTimer.singleShot(0, lambda: _restart(self, command, obj, sub))
                    return False
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Operación en otro sólido:\n%s\n" % traceback.format_exc())
        return original(self, obj, sub)

    _pick._swui_cross_body_restart = True
    dp.DressUpPanel._pick = _pick


def _restart(panel, command, obj, sub):
    try:
        panel.reject()
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cancelar la operación vacía:\n%s\n" % traceback.format_exc())

    def go():
        try:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(obj, sub)
            from swui import ribbon

            ribbon._run(command)  # activa el Cuerpo de lo elegido y arranca con eso
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Operación en otro sólido:\n%s\n" % traceback.format_exc())

    QtCore.QTimer.singleShot(50, go)


def _hook_accept():
    """Al aceptar un panel SW, las copias que quedaron sin usar se borran."""
    from swui.fork import dress_up_panel as dp

    original = dp.SwPanel.accept
    if getattr(original, "_swui_cross_body", False):
        return

    def accept(self):
        result = original(self)
        if result is not False:
            QtCore.QTimer.singleShot(0, prune_unused)
        return result

    accept._swui_cross_body = True
    dp.SwPanel.accept = accept


# --- Red de seguridad: el diálogo nativo se contesta solo ------------------------------


def _answer(dialog):
    try:
        if FreeCADGui.Control.activeDialog():
            radio = dialog.findChild(QtWidgets.QRadioButton, DEPENDENT)
            if radio is not None:
                radio.setChecked(True)
                FreeCAD.Console.PrintLog("[SWUI fork] Aviso 'Referencia' de FreeCAD: copia dependiente.\n")
                dialog.accept()
                return
        names = [o.Label for o in bodies_in(_selection())]
        FreeCAD.Console.PrintLog("[SWUI fork] Aviso 'Referencia' de FreeCAD sin panel (%s): "
                                 "se cancela y se activa el Cuerpo de lo elegido.\n" % ", ".join(names))
        dialog.reject()
        QtCore.QTimer.singleShot(0, _retry)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Aviso 'Referencia':\n%s\n" % traceback.format_exc())


def _retry():
    """Después de cancelar el aviso: activar el Cuerpo y relanzar el último comando (una vez)."""
    try:
        body = activate_for_selection()
        if body is None:
            return
        last = _state.get("last")
        if last is None or time.time() - last[2] > RETRY_S or _state.get("retried") == last:
            # sin comando reciente de la cinta (atajo o menú de FreeCAD): sin panel abierto,
            # el único que pregunta así es el croquis sobre la cara
            if len(_selection()) == 1:
                FreeCADGui.runCommand("PartDesign_NewSketch")
            return
        _state["retried"] = last
        from swui import ribbon

        ribbon._run(last[0], last[1])
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Relanzar el comando:\n%s\n" % traceback.format_exc())


def _focus_changed(_old, _new):
    """
    El aviso es modal y al abrirse se lleva el foco: con la señal focusChanged de Qt (barata,
    solo cuando cambia el foco) se lo reconoce. Un filtro de eventos en toda la aplicación era
    caro y a la salida de FreeCAD daba errores; uno en la ventana principal no lo veía (el aviso
    del croquis no nace hijo de ella).
    """
    try:
        dialog = QtWidgets.QApplication.activeModalWidget()
        if dialog is None or not dialog.objectName().endswith(DIALOG) or not _in_workbench():
            return
        if getattr(dialog, "_swui_answered", False):
            return
        dialog._swui_answered = True
        dialog.setWindowOpacity(0.0)  # que casi no se llegue a ver
        # dentro del exec() del diálogo: contestar apenas arranca su vuelta de eventos
        QtCore.QTimer.singleShot(0, lambda d=dialog: _answer(d))
    except Exception:
        pass


# --- B por cualquier camino: vínculos fuera de alcance -> copia dependiente -------------

# Propiedades de operaciones de Part Design que apuntan a una referencia. Si quedan apuntando a
# otro Cuerpo (Extruir "Hasta la superficie" de otro miembro no pregunta: deja el vínculo
# afuera y FreeCAD avisa "go out of the allowed scope"), se pasan a una copia dependiente.
WATCH = ("UpToFace", "UpToShape", "ReferenceAxis", "MirrorPlane", "Direction", "Direction2", "Axis",
         "NeutralPlane", "PullDirection", "Spine", "AuxiliarySpine", "Sections")
LOCAL_LINKS = ("App::PropertyLinkSub", "App::PropertyLinkSubList")


def fix_scope(obj, prop):
    """
    Pasa a copias dependientes las referencias de `obj.prop` que están en otro Cuerpo.
    Función pública. Devuelve True si cambió algo.
    """
    from swui.fork import auto_body

    if prop not in WATCH or not obj.TypeId.startswith("PartDesign::") or obj.TypeId == BINDER:
        return False
    if obj.getTypeIdOfProperty(prop) not in LOCAL_LINKS:
        return False
    body = auto_body.body_of(obj)
    value = getattr(obj, prop)
    if body is None or not value:
        return False
    single = obj.getTypeIdOfProperty(prop) == "App::PropertyLinkSub"
    items = [value] if single else list(value)
    out, changed = [], False
    for target, subs in items:
        subs = [subs] if isinstance(subs, str) else list(subs or [])
        if target is None or not needs_binder(body, target):
            out.append((target, subs))
            continue
        changed = True
        for sub in subs or [""]:
            out.append(bind_ref(body, target, sub))
    if not changed:
        return False
    if single:
        merged = (out[0][0], [s for o, ss in out if o is out[0][0] for s in ss])
        setattr(obj, prop, merged)
    else:
        setattr(obj, prop, out)
    FreeCAD.Console.PrintLog("[SWUI fork] %s.%s apuntaba a otro sólido: ahora a una copia dependiente.\n"
                             % (obj.Label, prop))
    return True


class _ScopeObserver:
    def __init__(self):
        self.restoring = set()

    def slotStartRestoreDocument(self, doc):
        self.restoring.add(doc.Name)

    def slotFinishRestoreDocument(self, doc):
        self.restoring.discard(doc.Name)

    def slotChangedObject(self, obj, prop):
        if prop not in WATCH:
            return
        try:
            doc = obj.Document
            if doc.Name in self.restoring or getattr(doc, "Transacting", False) or not _in_workbench():
                return
            names = (doc.Name, obj.Name, prop)
        except Exception:
            return
        if _state.get("fixing"):
            return
        # en el momento, antes de que el panel recalcule: si no, FreeCAD alcanza a avisar en
        # inglés "go out of the allowed scope" (visto con el mouse, 07/11)
        _state["fixing"] = True
        try:
            fix_scope(obj, prop)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Referencia fuera de alcance (en el momento):\n%s\n"
                                     % traceback.format_exc())
            QtCore.QTimer.singleShot(0, lambda: _fix_later(*names))  # de nuevo, fuera del aviso
        finally:
            _state["fixing"] = False


def _fix_later(doc_name, name, prop):
    try:
        doc = FreeCAD.getDocument(doc_name)
        obj = doc.getObject(name)
        if obj is not None and fix_scope(obj, prop):
            doc.recompute()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Referencia fuera de alcance:\n%s\n" % traceback.format_exc())


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == "LikeSolidWorksUIWorkbench"
    except Exception:
        return False


def install():
    """Antes de que se arme la cinta (los botones toman ribbon._run al armarse)."""
    if _state["installed"]:
        return
    _state["installed"] = True
    for step in (_wrap_ribbon, _wrap_pick_plane, _hook_patterns, _hook_draft, _hook_dress_up, _hook_accept):
        try:
            step()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Cuerpo de lo elegido:\n%s\n" % traceback.format_exc())
    try:
        QtWidgets.QApplication.instance().focusChanged.connect(_focus_changed)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Aviso 'Referencia':\n%s\n" % traceback.format_exc())
    try:
        _state["scope"] = _ScopeObserver()
        FreeCAD.addDocumentObserver(_state["scope"])
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Referencias fuera de alcance:\n%s\n" % traceback.format_exc())
