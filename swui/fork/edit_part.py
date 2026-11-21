# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Editar la pieza dentro del ensamblaje, como SOLIDWORKS (etapa D del clic derecho, 15/11; plan, medidas
y respuestas del usuario en docs/ESTADO.md).

- Editar pieza (ícono de la bandeja de un componente): activa el Cuerpo de la pieza a través del
  componente (lo nativo de FreeCAD 1.1.4: `vista.setActiveObject("pdbody", ensamblaje, "Comp.")`), los
  otros componentes se ven transparentes y arriba queda la barra "Editando pieza: X — Salir". Croquis,
  Extruir, Cortar... van a la pieza; Ctrl+Z en el ensamblaje deshace lo último de la pieza (FreeCAD lo
  anota en los dos documentos, medido). Salir vuelve todo como estaba y recalcula el ensamblaje.
- Editar operación / Editar croquis desde la cara de un componente: abre la operación (o su croquis) que
  hizo esa cara, en la pieza, sin salir del ensamblaje (`setEdit(ensamblaje, 0, "Comp.Body.Op.")`).
- Un componente en otra configuración es una COPIA de la pieza dentro del ensamblaje (límite conocido):
  editarla no cambiaría el archivo de la pieza; se avisa y no se entra (decisión del usuario, 15/11).
- Al guardar un ensamblaje en el que se editaron piezas, pregunta si guardar también las piezas
  cambiadas (SW hace lo mismo).

Regla del fork "panel = cara de una función": todo es función pública; los comandos solo la llaman.
Nada de esto queda guardado en los archivos (la transparencia se pone y se saca sin dejar el
ensamblaje "modificado", y al guardar se guarda como estaba).
"""

import traceback

import FreeCAD
import FreeCADGui

EDIT_PART = "SWUI_EditPart"
EDIT_FEATURE = "SWUI_EditPartFeature"
EDIT_SKETCH = "SWUI_EditPartSketch"
COPY_WARNING = "Este componente usa otra configuración; abrí la pieza para cambiarla."
COPY_SAME = ("Este componente usa una copia de la pieza (la pieza tiene configuraciones): "
             "abrí la pieza para cambiarla.")
GHOST = 0.75  # transparencia de los otros componentes mientras se edita (0 a 1)

_editing = {}  # nombre del ensamblaje -> {"link": nombre, "saved": {componente: transparencia}, ...}
# ensamblaje -> piezas (nombres de documento) que se editaron desde él: al guardar el ensamblaje se
# pregunta solo por esas, si quedaron modificadas (revisión del 15/11: antes, por cualquier pieza)
_touched = {}


# --- Lo elegido ------------------------------------------------------------------------------------------


def _ctx():
    from swui.fork import context_menus as cm

    return cm.context_of(cm.selection_entries())


def picked_component():
    """El componente elegido (uno solo), o None."""
    ctx = _ctx()
    return ctx.component if ctx.kind == "component" else None


def is_copy(link):
    """
    ¿El componente usa una copia de la pieza que FreeCAD guarda dentro del ensamblaje (componente con
    configuraciones)? Un Cuerpo propio del ensamblaje (mismo archivo) no es copia (revisión del 15/11).
    """
    from swui.fork import configurations as cf

    linked = getattr(link, "LinkedObject", None)
    return linked is not None and cf.is_copy(linked)


def assembly_and_path(link):
    """
    (ensamblaje, camino del componente desde el ensamblaje), también con el componente dentro de una
    carpeta del ensamblaje ('Carpeta.Comp.'). (None, '') si no está en un ensamblaje.
    """
    names, node, seen = [link.Name], link, set()
    while node is not None and node.Name not in seen:
        seen.add(node.Name)
        parent = next((p for p in getattr(node, "InList", []) if node in (getattr(p, "Group", None) or [])), None)
        if parent is None:
            return None, ""
        if parent.TypeId == "Assembly::AssemblyObject":
            return parent, ".".join(reversed(names)) + "."
        names.append(parent.Name)
        node = parent
    return None, ""


def _assembly(link):
    return assembly_and_path(link)[0]


def _view(doc):
    gdoc = FreeCADGui.getDocument(doc.Name)
    for v in gdoc.mdiViewsOfType("Gui::View3DInventor"):
        return v
    view = gdoc.ActiveView
    if view is None or not hasattr(view, "setActiveObject"):
        raise RuntimeError("El ensamblaje no tiene una vista 3D abierta.")
    return view


def _touch(asm_doc, link):
    linked = getattr(link, "LinkedObject", None)
    if linked is not None and linked.Document is not asm_doc:
        _touched.setdefault(asm_doc.Name, set()).add(linked.Document.Name)


def _warn(text):
    from swui.compat import QtWidgets

    QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Editar pieza", text)


# --- Editar pieza ------------------------------------------------------------------------------------------


def editing(doc):
    """El componente que se está editando en el ensamblaje doc, o None."""
    st = _editing.get(doc.Name) if doc is not None else None
    return doc.getObject(st["link"]) if st else None


def _quiet(doc, fn):
    from swui.fork import context_tools as ct

    ct._quiet(doc, fn)


def _ghostable(obj):
    """¿Se puede poner transparente? Los componentes (vínculos) no tienen Transparency: se usa su
    material propio (OverrideMaterial + ShapeMaterial), medido el 15/11 en 1.1.4."""
    vo = getattr(obj, "ViewObject", None)
    return vo is not None and "OverrideMaterial" in vo.PropertiesList and "ShapeMaterial" in vo.PropertiesList


def _set_ghosts(doc, st, on):
    """Los otros componentes transparentes (on) o como estaban; sin dejar el ensamblaje modificado."""
    def run():
        for name, (override, transparency, diffuse) in st["saved"].items():
            obj = doc.getObject(name)
            if obj is None or not _ghostable(obj):
                continue
            vo = obj.ViewObject
            m = vo.ShapeMaterial
            m.Transparency = GHOST if on else transparency
            if on and not override:
                # con el color de la pieza (si no, el material propio la pinta celeste; visto con el
                # mouse el 15/11): SW la deja de su color, transparente
                color = _part_color(obj)
                if color is not None:
                    m.DiffuseColor = color
            elif not on:
                m.DiffuseColor = diffuse  # todo como estaba (nada distinto queda en el archivo)
            vo.ShapeMaterial = m
            vo.OverrideMaterial = True if on else override
    _quiet(doc, run)


def _part_color(link):
    """El color con que se ve la pieza del componente (el de su Cuerpo), o None."""
    try:
        vo = link.LinkedObject.ViewObject
        if "ShapeAppearance" in vo.PropertiesList and vo.ShapeAppearance:
            return vo.ShapeAppearance[0].DiffuseColor
        if "ShapeMaterial" in vo.PropertiesList:
            return vo.ShapeMaterial.DiffuseColor
    except Exception:
        pass
    return None


def ghost_level(obj):
    """Transparencia que se ve en el componente (0 a 1; 0 si no tiene material propio)."""
    if not _ghostable(obj) or not obj.ViewObject.OverrideMaterial:
        return 0.0
    return obj.ViewObject.ShapeMaterial.Transparency


def check(link):
    """None si se puede editar la pieza del componente; si no, el motivo (en castellano)."""
    if _assembly(link) is None:
        return "El componente no está en un ensamblaje."
    if is_copy(link):
        # con configuraciones, el componente apunta siempre a una copia de la pieza dentro del ensamblaje
        # (así funciona configuraciones en FreeWorks): cambiarla no cambiaría el archivo de la pieza
        try:
            from swui.fork import config_asm, configurations as cf

            src = config_asm.source(link)
            same = src is not None and config_asm.current(link) == cf.active(src.Document)
        except Exception:
            same = False
        return COPY_SAME if same else COPY_WARNING
    part = getattr(link, "LinkedObject", None)
    if part is None or work_body(part) is None:
        return "La pieza de este componente no tiene un Cuerpo de Part Design (%s): abrila para cambiarla." % (
            getattr(part, "TypeId", "nada"))
    return None


def bodies_of(part):
    """Cuerpos de la pieza de un componente: el Cuerpo mismo, o los de un contenedor Parte (varios Cuerpos)."""
    if getattr(part, "TypeId", "") == "PartDesign::Body":
        return [part]
    if getattr(part, "TypeId", "") == "App::Part":
        return [o for o in part.Document.Objects if o.TypeId == "PartDesign::Body"
                and getattr(o.getParentGeoFeatureGroup(), "Name", None) == part.Name]
    return []


def work_body(part):
    """El Cuerpo que queda activo al editar: el único, o el último con sólido de un contenedor Parte."""
    bodies = bodies_of(part)
    if not bodies:
        return None
    solid = [b for b in bodies if b.Tip is not None and not b.Shape.isNull()]
    return (solid or bodies)[-1]


def start(link, warn=True):
    """
    Editar pieza: el Cuerpo de la pieza del componente queda activo (lo nuevo va a la pieza), los otros
    componentes transparentes y la barra "Editando pieza". False si no se puede (copia de otra
    configuración, sin ensamblaje, sin Cuerpo).
    """
    reason = check(link)
    if reason is not None:
        if warn:
            _warn(reason)
        return False
    asm, path = assembly_and_path(link)
    doc = asm.Document
    stop(doc)
    from swui.fork import mates_sw

    saved = {}
    for c in mates_sw.components_of(asm):
        if c is not link and _ghostable(c):
            m = c.ViewObject.ShapeMaterial
            saved[c.Name] = (bool(c.ViewObject.OverrideMaterial), m.Transparency, m.DiffuseColor)
    part = link.LinkedObject
    body = work_body(part)
    st = {"link": link.Name, "saved": saved, "body": body.Name, "prefix": path}
    _editing[doc.Name] = st
    try:
        _set_ghosts(doc, st, True)
        from swui.fork import edit_context as ec

        body_path = ec.path_of(body, ec.Context(asm, link, path, part, part.Document)) or path
        _view(doc).setActiveObject("pdbody", asm, body_path)
        _show_bar(doc, link)
    except Exception:
        # sin vista 3D o algo que falla: no queda a medias (revisión del 15/11)
        FreeCAD.Console.PrintError("[SWUI fork] Editar pieza:\n%s\n" % traceback.format_exc())
        stop(doc)
        if warn:
            _warn("No se pudo entrar a Editar pieza (detalle en la vista de informe).")
        return False
    _touch(doc, link)
    _watch(doc)
    return True


def _still_active(doc):
    """¿Sigue activo el Cuerpo de la pieza? (se puede salir por lo nativo: doble clic en otro Cuerpo)."""
    st = _editing.get(doc.Name)
    if st is None:
        return False
    try:
        act = _view(doc).getActiveObject("pdbody", False)
    except Exception:
        return False
    if not act or act[0] is None:
        return False
    # cualquier Cuerpo de la pieza editada (en una de varios Cuerpos se puede pasar de uno a otro)
    return len(act) > 2 and act[1] is not None and bool(st.get("prefix")) and str(act[2]).startswith(st["prefix"])


_timers = {}


def _watch(doc):
    """Mientras se edita: si FreeCAD sale solo (otro Cuerpo activo, vista cerrada), salir también."""
    from swui.compat import QtCore

    name = doc.Name
    timer = _timers.get(name)
    if timer is None:
        timer = QtCore.QTimer()
        timer.setInterval(500)

        def tick():
            if name not in FreeCAD.listDocuments() or name not in _editing:
                timer.stop()
                return
            d = FreeCAD.getDocument(name)
            if not _still_active(d):
                stop(d)
                return
            # #105 (21/11, visto con el mouse): al cerrarse un panel, la zona central se redibuja ENCIMA de la barra
            # (sigue "visible" para Qt pero no se ve): se la vuelve a poner arriba
            sync_bars()
        timer.timeout.connect(tick)
        _timers[name] = timer
    timer.start()


def stop(doc):
    """Salir de Editar pieza: el Cuerpo deja de estar activo, todo se ve como antes, se recalcula."""
    st = _editing.pop(doc.Name, None) if doc is not None else None
    _hide_bar(doc.Name if doc is not None else None)
    if doc is not None and doc.Name in _timers:
        _timers[doc.Name].stop()
    if st is None:
        return False
    try:
        _view(doc).setActiveObject("pdbody", None)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Editar pieza (salir):\n%s\n" % traceback.format_exc())
    _set_ghosts(doc, st, False)
    try:
        from swui.fork import edit_context as ec

        ec.release_aside(doc.Name)  # #106: las ventanas de la pieza apartadas vuelven con su pestaña
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Editar pieza (ventanas):\n%s\n" % traceback.format_exc())
    try:
        doc.recompute()
    except Exception:
        pass
    return True


def toggle(link):
    doc = link.Document
    if editing(doc) is link:
        return stop(doc)
    return start(link)


# --- Editar operación / croquis desde la cara de un componente ---------------------------------------------


def feature_path(top, sub):
    """
    (ensamblaje, componente, operación, camino) de la cara de un componente elegida en la vista: la
    operación de la pieza que hizo esa cara y el camino para abrirla desde el ensamblaje.
    """
    from swui.fork import context_menus as cm

    comp = cm.component_of(top, sub)
    if comp is None:
        return None
    feat, _element = cm.feature_of(top, sub)
    body = getattr(comp, "LinkedObject", None)
    if feat is None or body is None:
        return None
    asm = _assembly(comp)
    # el camino sale de la selección (con carpetas): hasta el Cuerpo, más la operación
    # FreeCAD la nombra 'Comp.Body.Caja.Face6' o 'Comp.Caja.Face6' (el clic en la vista): se corta en
    # el componente, y en el Cuerpo si está, y se agrega la operación (open_in_assembly lo verifica)
    tokens = cm.plain_sub(sub).split(".")
    if comp.Name not in tokens:
        return None
    i = tokens.index(comp.Name)
    base = tokens[:i + 1]
    if body.TypeId == "App::Part":  # contenedor (pieza de varios Cuerpos): hasta el Cuerpo de la operación
        from swui.fork import feature_tree as ft

        owner = ft.body_of(feat)
        if owner is None:
            return None
        base = base + [owner.Name]
    elif i + 1 < len(tokens) and tokens[i + 1] == body.Name:
        base = tokens[:i + 2]
    path = ".".join(base) + "." + feat.Name + "."
    return asm, comp, feat, path


def open_in_assembly(top, sub, sketch=False, warn=True):
    """
    Abre la operación (o su croquis) que hizo la cara del componente, sin salir del ensamblaje.
    Devuelve el objeto abierto, o None (con la copia de otra configuración: aviso y nada).
    """
    found = feature_path(top, sub)
    if found is None:
        return None
    asm, comp, feat, path = found
    reason = check(comp)
    if reason is not None:
        if warn:
            _warn(reason)
        return None
    target = feat
    if sketch:
        from swui.fork import feature_tree as ft

        target = ft._profile_sketch(feat)
        if target is None:
            return None
        path = path[:-len(feat.Name) - 1] + target.Name + "."
    try:
        if top.getSubObject(path, 1) is not target:
            return None  # el camino no llega a la operación: no se abre otra cosa
    except Exception:
        return None
    _touch(top.Document, comp)
    docs = [top.Document] + ([target.Document] if target.Document is not top.Document else [])
    before = _doc_states(docs)
    from swui.fork import edit_context as ec

    windows = [w for w in ec._part_windows(target.Document) if ec.tab_visible(w)]
    camera = ec.asm_camera(top.Document.Name)
    FreeCADGui.getDocument(top.Document.Name).setEdit(top, 0, path)
    _clean_after_cancel(top.Document.Name, before)
    ctx = ec.for_document(target.Document)
    if target.TypeId == "Sketcher::SketchObject" and ctx is not None:
        ec._after_sketch_open(ctx, target, windows, camera)  # #106 también por Editar croquis desde la cara
    return target


def _undo_mark(doc):
    """
    La pila de deshacer y rehacer entera. Revisión (18/11): con la pila llena (20 pasos), UndoCount deja de crecer
    aunque haya pasos nuevos: hay que comparar también los nombres y lo que queda por rehacer.
    """
    return (doc.UndoCount, tuple(doc.UndoNames), doc.RedoCount, tuple(doc.RedoNames))


def _doc_states(docs):
    """(nombre, ¿modificado?, pila de deshacer) de cada documento, para devolverlos al cancelar."""
    out = []
    for d in docs:
        g = FreeCADGui.getDocument(d.Name)
        out.append((d.Name, bool(g is not None and g.Modified), _undo_mark(d)))
    return out


def _clean_after_cancel(asm_name, before):
    """
    #105 (18/11): abrir una operación desde el ensamblaje la deja "modificada" y, al cancelar, FreeCAD recalcula y
    marca también el ensamblaje, aunque no cambió nada (sin pasos nuevos de deshacer). Como SW: al cerrar el panel
    sin pasos nuevos, cada documento vuelve a como estaba.
    """
    from swui.compat import QtCore

    timer = QtCore.QTimer()
    timer.setInterval(250)
    state = {"seen": False, "after": 0}

    def tick():
        try:
            if asm_name not in FreeCAD.listDocuments():
                _end()
                return
            gdoc = FreeCADGui.getDocument(asm_name)
            if gdoc.getInEdit() is not None:
                state["seen"] = True
                return
            state["after"] += 1
            if state["after"] < 2:  # el recálculo del cancelar llega un momento después
                return
            _end()
            for name, modified, undo in before:
                if name not in FreeCAD.listDocuments():
                    continue
                if _undo_mark(FreeCAD.getDocument(name)) != undo:
                    return  # hubo un cambio de verdad (Aceptar): se deja todo como lo dejó FreeCAD
            for name, modified, _undo in before:
                if name in FreeCAD.listDocuments() and not modified:
                    FreeCADGui.getDocument(name).Modified = False
        except Exception:
            _end()
            FreeCAD.Console.PrintLog("[SWUI fork] Editar operación (cancelar):\n%s\n" % traceback.format_exc())

    def _end():
        timer.stop()
        if timer in _cancel_timers:
            _cancel_timers.remove(timer)

    timer.timeout.connect(tick)
    _cancel_timers.append(timer)  # que no lo junte la basura (uno por cada panel abierto, hasta que termine)
    timer.start()


_cancel_timers = []


def _picked_face():
    from swui.fork import context_menus as cm

    entries = cm.selection_entries()
    if len(entries) != 1 or len(entries[0][1]) != 1:
        return None
    top, (sub,) = entries[0][0], entries[0][1]
    return (top, sub) if cm.ELEMENT.match(sub.split(".")[-1] or "") else None


# --- Croquis / Extruir / Corte sobre una cara, editando (16/11, visto por el usuario) -----------------------
# FreeWorks arma "croquis en la cara y después la operación" en pick_plane, que se apaga en los ensamblajes.
# Editando una pieza, se enciende: lo elegido se lee a través del componente y se vuelve a elegir por ese
# mismo camino (FreeCAD solo acepta la cara o el croquis de la pieza elegidos desde el ensamblaje).


def _edit_target(doc=None):
    """(ensamblaje, componente, camino del componente) que se está editando en doc (o el activo), o None."""
    from swui.fork import edit_context as ec

    ctx = ec.current(doc)
    return (ctx.asm, ctx.link, ctx.prefix) if ctx is not None else None


def selection_in_part(doc=None):
    """Lo elegido como lo ve la pieza editada (edit_context.selection)."""
    from swui.fork import edit_context as ec

    return ec.selection() if ec.current(doc) is not None else None


def select_in_part(obj, element="", doc=None):
    """Elige obj por el camino del componente (edit_context.select). False si no se edita esa pieza."""
    from swui.fork import edit_context as ec

    if ec.for_document(getattr(obj, "Document", None)) is None:
        return False
    return ec.select(obj, element)


def new_sketch_in_part(obj, element="", doc=None):
    """Croquis nuevo en la pieza editada, apoyado en obj y abierto (edit_context.new_sketch)."""
    from swui.fork import edit_context as ec

    return ec.new_sketch(obj, element)


class _Outside:
    """Cara plana de OTRO componente elegida editando (top-down): el croquis va sobre su referencia externa."""

    def __init__(self, sub):
        self.sub = sub


def _outside_face():
    """La única cara plana de otro componente elegida (sin nada de la pieza), como _Outside, o None."""
    from swui.fork import edit_context as ec

    subs = ec.outside_selection() or []
    if len(subs) != 1:
        return None
    shape = ec.outside_shape(subs[0])
    if shape is None or shape.ShapeType != "Face" or shape.Surface.__class__.__name__ != "Plane":
        return None
    return _Outside(subs[0])


def _hook_pick_plane():
    """
    Croquis / Extruir / Corte (pick_plane: croquis en la cara o plano y, al salir, la operación) también
    editando una pieza del ensamblaje; pick_plane solo, en un ensamblaje, deja todo a FreeCAD.
    """
    from swui import pick_plane as pp

    if getattr(pp.handle, "_swui_edit_part", False):
        return
    handle, selection, picked, tick = pp.handle, pp._selection, pp.picked, pp.tick
    picked_target = pp.picked_target
    def commands():
        # todos los de pick_plane, leídos en el momento (Taladro y Brida base se anotan después; "Editar
        # pieza = pieza", 16/11: todo lo de la pieza también editando)
        return (pp.SKETCH_COMMAND,) + tuple(pp.FEATURE_COMMANDS)

    def _start(command, target):
        from swui.fork import edit_context as ec

        try:
            if isinstance(target[0], _Outside):  # top-down: sobre la cara de otro componente
                sketch = ec.sketch_on_outside_face(target[0].sub)
            else:
                sketch = new_sketch_in_part(*target)
        except Exception:
            # sin volver al Croquis nativo, que acá tiene el error de FreeCAD
            FreeCAD.Console.PrintError("[SWUI fork] Croquis en la pieza editada:\n%s\n" % traceback.format_exc())
            return
        if sketch is not None and command != pp.SKETCH_COMMAND:
            pp.arm(command, sketch)
            if pp._armed:
                pp._armed["swui_edit"] = True  # armado editando: si se sale antes, no se hace nada

    def _open_panel(command):
        found = _edit_target()
        try:
            from swui.fork import edit_context as ec

            body = ec.active_body()  # el Cuerpo editado (con contenedor, LinkedObject es la Parte)
            panel = pp._TaskPanel(command, body if body is not None else found[1].LinkedObject)
            panel._swui_edit = True
            panel._orphaned = panel._cleanup  # si FreeCAD lo cierra solo: sacar la escucha de la selección
            pp._panel = panel
            from swui.fork import safe_ops

            safe_ops.show_panel(panel)
            panel.start()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Croquis en la pieza editada:\n%s\n" % traceback.format_exc())

    def _handle(command):
        if command not in commands() or _edit_target() is None or pp._dialog_open():
            return handle(command)
        inside, outside = selection_in_part()
        if outside:
            external = None if inside else _outside_face()
            if external is None:
                return False  # algo de otro componente que no es una cara plana sola: lo de FreeCAD
            pp._disarm()
            _start(command, (external, ""))
            return True
        pp._disarm()
        if not inside:
            _open_panel(command)
            return True
        target = pp.picked_target(inside)
        if target is None:
            return False  # un croquis u otra cosa elegida: decide FreeCAD
        _start(command, target)
        return True

    def _selection():
        found = selection_in_part()
        if found is None:
            return selection()
        inside, outside = found
        if outside:  # de otro componente: su cara plana (top-down) o "no es plano ni cara"
            external = None if inside else _outside_face()
            return [(external, [])] if external is not None else [(None, [])]
        return inside

    def _picked(target, command):
        from swui.compat import QtCore

        from_edit = getattr(pp._panel, "_swui_edit", False)
        if _edit_target() is None:
            if from_edit:  # el panel se abrió editando y ya se salió: nada (no el Croquis nativo)
                try:
                    FreeCADGui.Control.closeDialog()
                except Exception:
                    pass
                return None
            return picked(target, command)
        try:
            FreeCADGui.Control.closeDialog()
        except Exception:
            pass

        def go():
            try:
                _start(command, target)
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] Croquis en la pieza editada:\n%s\n" % traceback.format_exc())

        QtCore.QTimer.singleShot(pp.DELAY_MS, go)
        return None

    def _tick():
        # como pick_plane.tick, pero el croquis terminado se elige por el camino del componente (FreeCAD no
        # toma para la operación un croquis elegido directo en el documento de la pieza)
        armed = pp._armed
        if not armed or not armed.get("swui_edit"):
            return tick()
        if _edit_target() is None:
            pp._disarm()  # se salió de Editar pieza con el croquis abierto: la operación no arranca
            return None
        sketch = armed["sketch"]
        try:
            alive = sketch.Document is not None and sketch.Document.getObject(sketch.Name) is sketch
        except Exception:
            alive = False
        if not alive:
            pp._disarm()
            return None
        if pp._editing() is sketch:
            armed["seen_edit"] = True
            return None
        if not armed["seen_edit"] or pp._dialog_open():
            return None
        command = armed["command"]
        pp._disarm()
        if pp._used_by_feature(sketch) or not pp._has_geometry(sketch):
            return None
        try:
            if select_in_part(sketch):
                FreeCADGui.runCommand(command)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] %s con el croquis de la pieza editada:\n%s\n"
                                       % (command, traceback.format_exc()))
        return None

    def _picked_target(sel):
        if len(sel) == 1 and isinstance(sel[0][0], _Outside):
            return sel[0][0], ""
        return picked_target(sel)

    for fn in (_handle, _selection, _picked, _tick, _picked_target):
        fn._swui_edit_part = True
    pp.handle, pp._selection, pp.picked, pp.tick = _handle, _selection, _picked, _tick
    pp.picked_target = _picked_target


# --- Guardar -------------------------------------------------------------------------------------------------


def changed_parts(doc):
    """Las piezas editadas desde este ensamblaje que quedaron modificadas."""
    out = []
    for name in sorted(_touched.get(doc.Name, ())):
        if name not in FreeCAD.listDocuments():
            continue
        d = FreeCAD.getDocument(name)
        g = FreeCADGui.getDocument(name)
        if g is not None and g.Modified:
            out.append(d)
    return out


def save_parts(docs):
    """Guarda las piezas (con su archivo). Devuelve las que guardó."""
    out = []
    for d in docs:
        try:
            if d.FileName:
                d.save()
                # #103: doc.save() desde Python escribe el archivo pero no limpia la marca de la ventana (medido en
                # #104); a veces otra cosa la limpiaba y la prueba pasaba: intermitente
                g = FreeCADGui.getDocument(d.Name)
                if g is not None:
                    g.Modified = False
                out.append(d)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Guardar %s:\n%s\n" % (d.Label, traceback.format_exc()))
    return out


def ask_save_parts(doc):
    """Después de guardar el ensamblaje: ¿guardar también las piezas cambiadas? (como SW)."""
    from swui.compat import QtWidgets

    docs = changed_parts(doc)
    if not docs:
        return []
    names = "\n".join("  " + d.Label for d in docs)
    answer = QtWidgets.QMessageBox.question(
        FreeCADGui.getMainWindow(), "Guardar piezas",
        "Se cambiaron piezas desde el ensamblaje:\n%s\n\n¿Guardarlas también?" % names)
    if answer == QtWidgets.QMessageBox.StandardButton.Yes:
        return save_parts(docs)
    return []


class _Observer:
    """Al guardar mientras se edita: el archivo sin la transparencia; después, preguntar por las piezas."""

    def slotChangedObject(self, obj, prop):
        """
        #108 (21/11, reproducido con el mouse y con guion): el croquis de FreeCAD oculta lo que depende de él al abrirse
        y lo vuelve a mostrar al cerrarse, y ese "mostrar" queda grabado en un paso de deshacer ("Sketch recompute")
        que el ensamblaje comparte con la pieza. Deshacerlo ocultaba el componente editado. Mostrar u ocultar nunca es
        un paso de deshacer (ni en FreeCAD ni en SW): si deshacer/rehacer oculta el componente que se edita, vuelve.
        """
        if prop != "Visibility":
            return
        try:
            doc = obj.Document
            if not getattr(doc, "Transacting", False) or obj.Visibility:
                return
            if editing(doc) is not obj:
                return
            from swui.compat import QtCore

            name, oname = doc.Name, obj.Name

            def show():
                if name in FreeCAD.listDocuments():
                    o = FreeCAD.getDocument(name).getObject(oname)
                    if o is not None and not o.Visibility and editing(o.Document) is o:
                        o.Visibility = True
            QtCore.QTimer.singleShot(0, show)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Editar pieza (deshacer):\n%s\n" % traceback.format_exc())

    def slotStartSaveDocument(self, doc, filename):
        from swui.fork import context_tools as ct

        st = _editing.get(doc.Name)
        if st and ct._own_file(doc, filename):
            _set_ghosts(doc, st, False)
            st["resave"] = True

    def slotFinishSaveDocument(self, doc, filename):
        from swui.fork import context_tools as ct

        st = _editing.get(doc.Name)
        if st and st.pop("resave", False):
            _set_ghosts(doc, st, True)
            try:
                FreeCADGui.getDocument(doc.Name).Modified = False
            except Exception:
                pass
        # solo al guardar el archivo propio (no "Guardar una copia" ni respaldos) y solo por las piezas
        # editadas desde este ensamblaje que quedaron modificadas
        if not ct._own_file(doc, filename) or not changed_parts(doc):
            return
        from swui.compat import QtCore

        name = doc.Name

        def later():
            if name in FreeCAD.listDocuments():
                ask_save_parts(FreeCAD.getDocument(name))
                if name not in _editing:
                    _touched.pop(name, None)  # ya preguntó; editando, se sigue mirando
        QtCore.QTimer.singleShot(0, later)

    def slotDeletedDocument(self, doc):
        _editing.pop(doc.Name, None)
        _touched.pop(doc.Name, None)
        for parts in _touched.values():
            parts.discard(doc.Name)
        timer = _timers.pop(doc.Name, None)
        if timer is not None:
            timer.stop()
        _hide_bar(doc.Name)


# --- Barra "Editando pieza" ----------------------------------------------------------------------------------

_bars = {}


def _show_bar(doc, link):
    from swui.compat import QtWidgets

    _hide_bar(doc.Name)
    mw = FreeCADGui.getMainWindow()
    box = QtWidgets.QFrame(mw)
    box.setObjectName("SWUI_edit_part_bar")
    box.setStyleSheet("#SWUI_edit_part_bar { background: #e5f1fb; border: 1px solid #3c82c8; border-radius: 3px; }")
    lay = QtWidgets.QHBoxLayout(box)
    lay.setContentsMargins(8, 4, 4, 4)
    linked = getattr(link, "LinkedObject", None)
    name = linked.Document.Label if linked is not None else link.Label
    label = QtWidgets.QLabel("Editando pieza: %s" % name)
    label.setObjectName("SWUI_edit_part_label")
    lay.addWidget(label)
    button = QtWidgets.QPushButton("Salir")
    button.setObjectName("SWUI_edit_part_exit")
    doc_name = doc.Name
    button.clicked.connect(lambda _c=False: stop(FreeCAD.getDocument(doc_name))
                           if doc_name in FreeCAD.listDocuments() else _hide_bar(doc_name))
    lay.addWidget(button)
    box.adjustSize()
    geo = mw.centralWidget().geometry() if mw.centralWidget() is not None else mw.geometry()
    box.move(geo.left() + (geo.width() - box.width()) // 2, geo.top() + 8)
    _bars[doc.Name] = box
    _watch_active()
    sync_bars()


def sync_bars():
    """
    A la vista solo la barra del documento al frente (con dos ensamblajes, una cada uno). #105 (18/11): "al frente" es
    la ventana que se ve, no FreeCAD.ActiveDocument: Editar operación, Miembro estructural o un croquis de la pieza
    editada dejan activo el documento de la pieza aunque se sigue viendo (y editando) el ensamblaje.
    """
    from swui.compat import QtWidgets
    from swui.fork import edit_context as ec

    try:  # #106: la ventana apartada de la pieza no vuelve al frente
        area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        ec.keep_aside(area.currentSubWindow() if area is not None else None)
    except Exception:
        pass
    active = _front_document()
    for n, w in list(_bars.items()):
        try:
            w.setVisible(n == active)
            if n == active:
                w.raise_()
        except RuntimeError:
            _bars.pop(n, None)


def _front_document():
    """Nombre del documento de la ventana 3D al frente (o el activo, si no hay ventana al frente)."""
    from swui.compat import QtWidgets
    from swui.fork import edit_context as ec

    try:
        area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        # currentSubWindow: la de adelante aunque FreeCAD no tenga el foco (activeSubWindow da None)
        sub = area.currentSubWindow() if area is not None else None
        if sub is not None:
            for name in list(_bars) + list(FreeCAD.listDocuments()):
                gdoc = FreeCADGui.getDocument(name)
                if gdoc is not None and sub in ec._part_windows(gdoc.Document):
                    return name
    except Exception:
        pass
    return FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument is not None else None


_watching = {}


def _watch_active():
    if _watching:
        return
    from swui.compat import QtWidgets

    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        mdi.subWindowActivated.connect(lambda *_a: sync_bars())
        _watching["mdi"] = mdi
    except Exception:
        pass


def _hide_bar(name=None):
    for n in (list(_bars) if name is None else [name]):
        w = _bars.pop(n, None)
        try:
            if w is not None:
                w.hide()
                w.deleteLater()
        except RuntimeError:
            pass


# --- Comandos ------------------------------------------------------------------------------------------------


class _Cmd:
    menu = tip = icon = ""

    def GetResources(self):
        from swui import paths

        out = {"MenuText": self.menu, "ToolTip": self.tip}
        if self.icon and paths.icon(self.icon):
            out["Pixmap"] = paths.icon(self.icon)
        return out


class _EditPart(_Cmd):
    menu, tip, icon = "Editar pieza", "Edita la pieza dentro del ensamblaje (otra vez: volver al ensamblaje)", \
        "fork/t_edit_part"

    def IsActive(self):
        return picked_component() is not None or editing(FreeCAD.ActiveDocument) is not None

    def Activated(self):
        link = picked_component()
        doc = FreeCAD.ActiveDocument
        if link is None or editing(doc) is link:
            stop(doc)
        else:
            start(link)


class _EditFeature(_Cmd):
    menu, tip, icon = "Editar operación", "Abre la operación de la pieza que hizo esta cara", "fork/t_edit_feature"
    sketch = False

    def IsActive(self):
        face = _picked_face()
        if face is None:
            return False
        found = feature_path(*face)
        if found is None:
            return False
        if self.sketch:
            from swui.fork import feature_tree as ft

            return ft._profile_sketch(found[2]) is not None
        return True

    def Activated(self):
        face = _picked_face()
        if face is not None:
            open_in_assembly(face[0], face[1], sketch=self.sketch)


class _EditSketch(_EditFeature):
    menu, tip, icon = "Editar croquis", "Abre el croquis de la operación de la pieza que hizo esta cara", \
        "fork/t_edit_sketch"
    sketch = True


_observer = None


def install():
    global _observer
    for name, cls in ((EDIT_PART, _EditPart), (EDIT_FEATURE, _EditFeature), (EDIT_SKETCH, _EditSketch)):
        try:
            FreeCADGui.addCommand(name, cls())
        except Exception:
            pass  # ya registrado
    if _observer is None:
        _observer = _Observer()
        FreeCAD.addDocumentObserver(_observer)
    try:
        _hook_pick_plane()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Editar pieza / pick_plane:\n%s\n" % traceback.format_exc())
    global _up_to
    if _up_to is None:
        _up_to = _make_up_to_filter()
        from swui.compat import QtWidgets

        QtWidgets.QApplication.instance().installEventFilter(_up_to)
    try:
        _hook_ribbon()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Editar pieza / cinta:\n%s\n" % traceback.format_exc())


# --- Top-down: "Hasta la superficie" con la cara de otro componente (17/11) --------------------------------
UP_TO_TYPES = ("PartDesign::Pad", "PartDesign::Pocket")
_up_to = None


def _up_to_target():
    """(contexto, operación) si se edita una pieza con Extruir / Extruir corte abierto esperando la cara de
    "Hasta la superficie"; si no, None."""
    from swui.fork import edit_context as ec

    if not _editing:
        return None
    ctx = ec.current()
    if ctx is None:
        return None
    feat = getattr(ec.in_edit(ctx.pdoc), "Object", None)
    if feat is None or feat.TypeId not in UP_TO_TYPES or getattr(feat, "Type", "") != "UpToFace":
        return None
    return ctx, feat


def _waiting_face():
    """¿El panel de Extruir está esperando la cara ("Elegir cara" apretado)?"""
    from swui.compat import QtWidgets

    try:
        return any(b.isVisible() and b.isChecked()
                   for b in FreeCADGui.getMainWindow().findChildren(QtWidgets.QAbstractButton, "buttonFace"))
    except Exception:
        return False


def outside_face_at(view, x, y):
    """Camino ('Otro.Extruir.Face5') de la cara de OTRO componente bajo el punto Qt (x, y) de la vista, o None."""
    from swui.fork import context_menus as cm
    from swui.fork import edit_context as ec

    ctx = ec.current()
    if ctx is None:
        return None
    viewport = view.graphicsView().viewport()
    ratio = viewport.devicePixelRatioF()
    info = view.getObjectInfo((int(round(x * ratio)), int(round((viewport.height() - y) * ratio))))
    # medido (1.1.4): {'ParentObject': <el ensamblaje>, 'SubName': 'Body001.Extruir.Face6', 'Document': 'Otro', ...}
    if not info or info.get("ParentObject") is not ctx.asm:
        return None
    plain = cm.plain_sub(info.get("SubName") or "")
    if not plain or plain.startswith(ctx.prefix) or not plain.split(".")[-1].startswith("Face"):
        return None
    return plain


def _make_up_to_filter():
    """
    Con Extruir / Extruir corte de la pieza editada abierto en "Hasta la superficie", un clic en la cara de OTRO
    componente: el panel nativo la filtra (es de otro archivo) antes de que llegue a la selección. Se mira el
    clic en la vista: se arma la referencia externa en la pieza y se elige su cara, que el panel sí acepta
    (como en SW: la operación queda referida al otro componente).
    """
    from swui.compat import QtCore

    class UpToOutside(QtCore.QObject):
        def eventFilter(self, obj, event):
            try:
                if event.type() != QtCore.QEvent.Type.MouseButtonRelease or event.button() != QtCore.Qt.MouseButton.LeftButton:
                    return False
                found = _up_to_target()
                if found is None or not _waiting_face():
                    return False
                view = FreeCADGui.ActiveDocument.ActiveView
                if obj is not view.graphicsView().viewport():
                    return False
                pos = event.position() if hasattr(event, "position") else event.pos()
                sub = outside_face_at(view, pos.x(), pos.y())
                if sub is not None:
                    feat = found[1]
                    QtCore.QTimer.singleShot(0, lambda: up_to_outside_face(feat, sub))
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Hasta la superficie:\n%s\n" % traceback.format_exc())
            return False

    return UpToOutside()


def up_to_outside_face(feature, sub):
    """
    Pone la cara `sub` de otro componente (camino desde el ensamblaje) como "Hasta la superficie" de `feature`
    (Extruir / Extruir corte de la pieza editada, abierto): referencia externa y su cara elegida para el panel.
    Devuelve la referencia o None.
    """
    from swui.fork import edit_context as ec

    ctx = ec.for_document(feature.Document)
    if ctx is None:
        return None
    binder = ec.external_reference([sub], ctx)
    if binder is None:
        return None
    try:
        binder.ViewObject.Visibility = False
    except Exception:
        pass
    # el panel nativo, al recibir la cara del otro componente, deja de esperar una cara: se le vuelve a pedir
    try:
        from swui.compat import QtWidgets

        for button in FreeCADGui.getMainWindow().findChildren(QtWidgets.QAbstractButton, "buttonFace"):
            if button.isVisible() and button.isCheckable() and not button.isChecked():
                button.click()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Hasta la superficie:\n%s\n" % traceback.format_exc())
    FreeCADGui.Selection.clearSelection()
    ec.select(binder, "Face1")
    return binder


def new_body():
    """
    Cuerpo nuevo en la pieza que se edita (no en el ensamblaje), activo, como el botón Cuerpo en la pieza sola.
    La pieza pasa antes a contenedor si hacía falta (prepare_container). Devuelve el Cuerpo, o None.
    """
    from swui.compat import QtCore
    from swui.fork import edit_context as ec

    ctx = prepare_container(ec.current())
    if ctx is None:
        return None
    FreeCAD.setActiveTransaction("Cuerpo")
    try:
        body = ctx.pdoc.addObject("PartDesign::Body", "Body")
        # al contenedor en este mismo paso: un solo Ctrl+Z saca el Cuerpo (revisión del 18/11)
        from swui.fork import part_container as pc

        part = pc.container(ctx.pdoc)
        if part is not None and body.getParentGeoFeatureGroup() is None:
            part.addObject(body)
    except Exception:
        FreeCAD.closeActiveTransaction(True)
        raise
    FreeCAD.closeActiveTransaction()
    asm_doc, name = ctx.asm.Document, body.Name

    def activate():
        c = ec.current(asm_doc)
        b = c.pdoc.getObject(name) if c is not None else None
        path = ec.path_of(b, c) if b is not None else None
        if path:
            try:
                _view(asm_doc).setActiveObject("pdbody", c.asm, path)
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Cuerpo nuevo: activar\n%s\n" % traceback.format_exc())
    QtCore.QTimer.singleShot(100, activate)  # después de pasarlo al contenedor (part_container.adopt)
    return body


# comandos nativos que buscan sus croquis en el documento activo (Barrer, Recubrir, Hélice): editando, la pieza
PART_DOC_COMMANDS = ("PartDesign_AdditivePipe", "PartDesign_AdditiveLoft", "PartDesign_AdditiveHelix",
                     "PartDesign_SubtractivePipe", "PartDesign_SubtractiveLoft", "PartDesign_SubtractiveHelix")


# comandos que crean algo FUERA del Cuerpo (otro Cuerpo, un grupo): editando una pieza de un solo Cuerpo, la
# pieza pasa antes a contenedor Parte, para que lo nuevo se vea en el componente
OUTSIDE_BODY = ("SWUI_Sketch3D", "SWUI_WeldMember", "SWUI_WeldEndCap", "SWUI_WeldGusset")
CONVERT = ("Sketcher_Projection", "Sketcher_External")  # Convertir entidades (top-down: aristas de otro componente)


def prepare_container(ctx):
    """
    Si se edita una pieza de un solo Cuerpo, la pasa a contenedor (edit_context.ensure_container) en un paso de
    deshacer propio, ANTES del comando: si después se cancela el comando, el componente sigue apuntando a algo
    que existe. Devuelve el contexto actualizado (o el mismo, o None).
    """
    from swui.fork import edit_context as ec

    if ctx is None or ctx.part.TypeId != "PartDesign::Body":
        return ctx
    FreeCAD.setActiveTransaction("Pieza de varios cuerpos")
    try:
        ec.ensure_container(ctx)
    except Exception:
        FreeCAD.closeActiveTransaction(True)
        raise
    FreeCAD.closeActiveTransaction()
    return ec.current(ctx.asm.Document) or ctx


def _helix_defaults(body, feat, obj, subs):
    """Lo que el comando nativo de Hélice propone (medido en 1.1.4): eje Y del Cuerpo, paso = 1,1 x la diagonal
    del perfil, altura = vueltas x paso."""
    for axis in getattr(getattr(body, "Origin", None), "OriginFeatures", []):
        if getattr(axis, "Role", "") == "Y_Axis":
            feat.ReferenceAxis = (axis, [""])
            break
    try:
        shape = obj.Shape.getElement(subs[0]) if subs and subs[0] else obj.Shape
        diag = shape.BoundBox.DiagonalLength
        if diag > 0:
            feat.Pitch = 1.1 * diag
            feat.Height = feat.Turns * feat.Pitch.Value
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Hélice editando:\n%s\n" % traceback.format_exc())


def _pick_profile_sketch():
    """
    Sin nada elegido, editando: la lista de croquis del Cuerpo activo para el perfil (en la pieza sola FreeCAD
    muestra la suya; editando, la nativa no encuentra el Cuerpo a través del componente). None si se cancela o
    no hay croquis.
    """
    from swui.compat import QtWidgets
    from swui.fork import edit_context as ec

    body = ec.active_body()
    sketches = [o for o in getattr(body, "Group", []) if o.TypeId == "Sketcher::SketchObject"]
    main = FreeCADGui.getMainWindow()
    if not sketches:
        QtWidgets.QMessageBox.information(main, "Perfil", "No hay croquis en la pieza: dibujá primero el perfil.")
        return None
    labels = [s.Label for s in sketches]
    text, ok = QtWidgets.QInputDialog.getItem(main, "Perfil", "Croquis del perfil:", labels, len(labels) - 1, False)
    if not ok or text not in labels:
        return None
    return sketches[labels.index(text)]


def profile_feature(ctx, command, obj, subs):
    """
    Barrer / Recubrir / Hélice (PART_DOC_COMMANDS) con algo elegido, editando una pieza: como el comando nativo
    en la pieza sola (operación nueva en el Cuerpo activo de la pieza, con lo elegido de perfil, abierta), pero
    abierta por el camino del componente (el nativo la abre en la ventana de la pieza, donde no se puede elegir).
    El paso de deshacer queda abierto mientras está el panel, como en el nativo: Aceptar lo cierra, Cancelar lo
    deshace. Devuelve la operación.
    """
    from swui.fork import edit_context as ec

    body = ec.active_body()
    if body is None or body.Document is not ctx.pdoc:
        return None
    type_id = "PartDesign::" + command.split("_", 1)[1]
    FreeCAD.setActiveTransaction(type_id.split("::")[1])
    try:
        feat = body.newObject(type_id, type_id.split("::")[1])
        feat.Profile = (obj, [s for s in subs if s]) if subs else obj
        if type_id.endswith("Helix"):
            _helix_defaults(body, feat, obj, subs)
        ctx.pdoc.recompute()
        FreeCADGui.Selection.clearSelection()
        opened = ec.set_edit(feat)
    except Exception:
        FreeCAD.closeActiveTransaction(True)
        raise
    if not opened:  # como el nativo: si no se puede abrir (perfil que no sirve), la operación queda, con su error
        FreeCAD.closeActiveTransaction()
    return feat


def _hook_ribbon():
    """Botones de la cinta que, editando una pieza, tienen que trabajar en la pieza (Cuerpo nuevo)."""
    from swui import ribbon

    original = ribbon._run
    if getattr(original, "_swui_edit_part", False):
        return

    def run(command, index=None, *args):
        from swui.fork import edit_context as ec

        ctx = ec.current() if command in ("PartDesign_Body",) + PART_DOC_COMMANDS + OUTSIDE_BODY + CONVERT else None
        if ctx is None:
            return original(command, index, *args)
        if command in CONVERT:
            # top-down: con un croquis de la pieza abierto y aristas de otro componente elegidas
            sketch = getattr(ec.in_edit(ctx.pdoc), "Object", None)
            outside = ec.outside_selection() or []
            if sketch is None or sketch.TypeId != "Sketcher::SketchObject" or not outside:
                return original(command, index, *args)
            try:
                ec.convert_outside_edges(sketch, outside, ctx)
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] Convertir entidades:\n%s\n" % traceback.format_exc())
            return None
        if command in OUTSIDE_BODY:
            try:
                prepare_container(ctx)
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] Pieza a contenedor:\n%s\n" % traceback.format_exc())
            return original(command, index, *args)
        if command == "PartDesign_Body":
            try:
                new_body()
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] Cuerpo nuevo:\n%s\n" % traceback.format_exc())
            return None
        # el comando nativo busca sus croquis en el documento activo (el ensamblaje: "Ningún croquis
        # disponible"): mientras corre, el activo es la pieza (lo que se ve sigue siendo el ensamblaje)
        asm_name = ctx.asm.Document.Name
        # y lo elegido (con el camino del ensamblaje) pasa a la pieza, como lo vería en la pieza sola
        local = []
        try:
            local = [(s.Object, list(s.SubElementNames)) for s in ec.selection_ex(asm_name)
                     if s.Document is ctx.pdoc]
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Editar pieza / selección:\n%s\n" % traceback.format_exc())
        if not local:
            sketch = _pick_profile_sketch()
            if sketch is None:
                return None
            local = [(sketch, [])]
        try:
            return profile_feature(ctx, command, local[0][0], local[0][1])
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] %s editando:\n%s\n" % (command, traceback.format_exc()))
            return None

    run._swui_edit_part = True
    ribbon._run = run
