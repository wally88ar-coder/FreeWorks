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
        for name, (override, transparency) in st["saved"].items():
            obj = doc.getObject(name)
            if obj is None or not _ghostable(obj):
                continue
            vo = obj.ViewObject
            m = vo.ShapeMaterial
            m.Transparency = GHOST if on else transparency
            vo.ShapeMaterial = m
            vo.OverrideMaterial = True if on else override
    _quiet(doc, run)


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
    body = getattr(link, "LinkedObject", None)
    if body is None or getattr(body, "TypeId", "") != "PartDesign::Body":
        return "La pieza de este componente no es un Cuerpo de Part Design (%s): abrila para cambiarla." % (
            getattr(body, "TypeId", "nada"))
    return None


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
            saved[c.Name] = (bool(c.ViewObject.OverrideMaterial), c.ViewObject.ShapeMaterial.Transparency)
    st = {"link": link.Name, "saved": saved, "body": link.LinkedObject.Name}
    _editing[doc.Name] = st
    try:
        _set_ghosts(doc, st, True)
        _view(doc).setActiveObject("pdbody", asm, path)
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
    return bool(act) and act[0] is not None and getattr(act[0], "Name", None) == st["body"]


_timers = {}


def _watch(doc):
    """Mientras se edita: si FreeCAD sale solo (otro Cuerpo activo, vista cerrada), salir también."""
    from swui.compat import QtCore

    name = doc.Name
    timer = _timers.get(name)
    if timer is None:
        timer = QtCore.QTimer()
        timer.setInterval(1000)

        def tick():
            if name not in FreeCAD.listDocuments() or name not in _editing:
                timer.stop()
                return
            d = FreeCAD.getDocument(name)
            if not _still_active(d):
                stop(d)
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
    base = tokens[:i + 2] if i + 1 < len(tokens) and tokens[i + 1] == body.Name else tokens[:i + 1]
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
    FreeCADGui.getDocument(top.Document.Name).setEdit(top, 0, path)
    return target


def _picked_face():
    from swui.fork import context_menus as cm

    entries = cm.selection_entries()
    if len(entries) != 1 or len(entries[0][1]) != 1:
        return None
    top, (sub,) = entries[0][0], entries[0][1]
    return (top, sub) if cm.ELEMENT.match(sub.split(".")[-1] or "") else None


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
    """A la vista solo la barra del documento al frente (con dos ensamblajes, una cada uno)."""
    active = FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument is not None else None
    for n, w in list(_bars.items()):
        try:
            w.setVisible(n == active)
            if n == active:
                w.raise_()
        except RuntimeError:
            _bars.pop(n, None)


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
