# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Herramientas del clic derecho como SW que FreeCAD no trae (etapa C, decisiones del usuario 15/11):
Contraer operaciones, Invertir la selección, Aislar / Salir de aislar, Cambiar de nombre, Propiedades
del componente, Padre/Hijo del componente, Material del componente, Seleccionar tangencia, Exportar
cara a DXF y Abrir pieza en posición.

Regla del fork "panel = cara de una función": cada herramienta es una función pública que se puede
llamar sin abrir nada (la usan las pruebas y la IA); el comando solo junta lo elegido y la llama.
Nada de esto guarda propiedades nuevas en los archivos.
"""

import math
import os
import traceback

import FreeCAD
import FreeCADGui

V = FreeCAD.Vector

COLLAPSE = "SWUI_CollapseTree"
INVERT = "SWUI_InvertSelection"
ISOLATE = "SWUI_Isolate"
EXIT_ISOLATE = "SWUI_ExitIsolate"
RENAME = "SWUI_RenameComponent"
PROPERTIES = "SWUI_ComponentProperties"
PARENT_CHILD = "SWUI_ComponentParentChild"
MATERIAL = "SWUI_ComponentMaterial"
TANGENT = "SWUI_SelectTangent"
FACE_DXF = "SWUI_ExportFaceDXF"
OPEN_IN_POSITION = "SWUI_OpenPartInPosition"

BODY = "PartDesign::Body"
ASSEMBLY = "Assembly::AssemblyObject"


# --- Lo elegido -------------------------------------------------------------------------------------


def _entries():
    try:
        return FreeCADGui.Selection.getSelectionEx("", 0)
    except Exception:
        return []


def picked():
    """(contexto de context_menus, entrada de selección) de lo elegido, o (None, None)."""
    from swui.fork import context_menus as cm

    sel = _entries()
    if len(sel) != 1:
        return None, None
    ctx = cm.context_of([(sel[0].Object, list(sel[0].SubElementNames))])
    return (ctx if ctx.kind else None), sel[0]


def picked_component():
    ctx, _s = picked()
    return ctx.component if ctx is not None and ctx.kind == "component" else None


def assembly_of(comp):
    for parent in getattr(comp, "InList", []):
        if getattr(parent, "TypeId", "") == ASSEMBLY:
            return parent
    return None


# --- Contraer operaciones -----------------------------------------------------------------------------


def collapse_tree(doc):
    """Cierra todas las ramas del árbol del documento; deja abiertos los Cuerpos y ensamblajes (SW)."""
    gdoc = FreeCADGui.getDocument(doc.Name)
    keep = (BODY, ASSEMBLY, "App::Part")
    for obj in doc.Objects:
        if not getattr(obj, "OutList", None) and not getattr(obj, "Group", None):
            continue
        try:
            gdoc.toggleTreeItem(obj, 2 if obj.TypeId in keep else 1)  # 2 = abrir, 1 = cerrar
        except Exception:
            pass


# --- Invertir la selección ------------------------------------------------------------------------------


def invert_components(asm, chosen):
    """Los componentes del ensamblaje que no están en chosen (para elegirlos)."""
    from swui.fork import mates_sw

    return [c for c in mates_sw.components_of(asm) if c not in chosen]


def invert_selection():
    comps = []
    asm = None
    for s in _entries():
        for sub in (list(s.SubElementNames) or [""]):
            from swui.fork import context_menus as cm

            ctx = cm.context_of([(s.Object, [sub])])
            if ctx.kind == "component":
                comps.append(ctx.component)
                asm = asm or assembly_of(ctx.component)
    if asm is None:
        return []
    others = invert_components(asm, comps)
    FreeCADGui.Selection.clearSelection()
    for c in others:
        FreeCADGui.Selection.addSelection(asm.Document.Name, asm.Name, c.Name + ".")
    return others


# --- Aislar ------------------------------------------------------------------------------------------------

_isolated = {}  # nombre del documento -> {nombre de objeto: Visibility de antes}
_shown = {}  # nombre del documento -> (lo que se oculta, lo que queda a la vista) al aislar


def isolate_targets(keep):
    """Lo que se oculta al aislar keep: los otros Cuerpos de la pieza o los otros componentes."""
    from swui.fork import mates_sw

    asm = assembly_of(keep)
    if asm is not None:
        return [c for c in mates_sw.components_of(asm) if c is not keep]
    from swui.fork import material

    # los otros Cuerpos y los sólidos sueltos (un STEP importado), como los que cuenta Material
    return [o for o in material.part_objects(keep.Document) if o is not keep]


def _quiet(doc, fn):
    """Cambiar la visibilidad sin dejar el documento "modificado" si no lo estaba."""
    gdoc = FreeCADGui.getDocument(doc.Name)
    was = getattr(gdoc, "Modified", None)
    fn()
    if was is False:
        try:
            gdoc.Modified = False
        except Exception:
            pass


def isolate(keep):
    """
    Aislar como SW: se ve solo keep (un Cuerpo o un componente). Recuerda lo que se veía para
    "Salir de aislar". Aislar otra cosa estando aislado primero vuelve todo a como estaba.
    """
    doc = keep.Document
    exit_isolate(doc)
    saved = {}
    hide = isolate_targets(keep)

    def run():
        for o in hide:
            saved[o.Name] = bool(o.Visibility)
            o.Visibility = False
        if not keep.Visibility:
            saved[keep.Name] = False
            keep.Visibility = True
    _quiet(doc, run)
    _isolated[doc.Name] = saved
    _shown[doc.Name] = ([o.Name for o in hide], keep.Name)
    _show_exit_bar(doc)
    return hide


def is_isolated(doc):
    return doc is not None and doc.Name in _isolated


def exit_isolate(doc):
    """Vuelve a mostrar exactamente lo que se veía antes de aislar."""
    saved = _isolated.pop(doc.Name, None) if doc is not None else None
    if doc is not None:
        _shown.pop(doc.Name, None)
    if saved is None:
        if doc is not None:
            _hide_exit_bar(doc.Name)
        return False

    def run():
        for name, vis in saved.items():
            obj = doc.getObject(name)
            if obj is not None:
                obj.Visibility = vis
    _quiet(doc, run)
    _hide_exit_bar(doc.Name)
    return True


_bars = {}  # nombre del documento -> su barra "Salir de aislar"


def _show_exit_bar(doc):
    """El cartelito "Aislar" de SW con el botón Salir de aislar, arriba de la vista (uno por documento)."""
    from swui.compat import QtWidgets

    _hide_exit_bar(doc.Name)
    mw = FreeCADGui.getMainWindow()
    box = QtWidgets.QFrame(mw)
    box.setObjectName("SWUI_isolate_bar")
    box.setStyleSheet("#SWUI_isolate_bar { background: #f4f6f8; border: 1px solid #9aa4b0; border-radius: 3px; }")
    lay = QtWidgets.QHBoxLayout(box)
    lay.setContentsMargins(8, 4, 4, 4)
    lay.addWidget(QtWidgets.QLabel("Aislar"))
    button = QtWidgets.QPushButton("Salir de aislar")
    button.setObjectName("SWUI_isolate_exit")
    name = doc.Name
    button.clicked.connect(lambda _c=False: exit_isolate(FreeCAD.getDocument(name))
                           if name in FreeCAD.listDocuments() else _hide_exit_bar(name))
    lay.addWidget(button)
    box.adjustSize()
    geo = mw.centralWidget().geometry() if mw.centralWidget() is not None else mw.geometry()
    box.move(geo.left() + (geo.width() - box.width()) // 2, geo.top() + 40)
    _bars[name] = box
    _watch_active()
    sync_bars()


def _hide_exit_bar(name=None):
    names = list(_bars) if name is None else [name]
    for n in names:
        w = _bars.pop(n, None)
        try:
            if w is not None:
                w.hide()
                w.deleteLater()
        except RuntimeError:
            pass


def sync_bars():
    """A la vista solo la barra del documento activo (al cambiar de ventana, la del otro se esconde)."""
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


def _own_file(doc, filename):
    """¿Se guarda el archivo del documento? (FreeCAD avisa también con "Guardar una copia" y respaldos)."""
    try:
        return not filename or not doc.FileName or (
            os.path.normcase(os.path.abspath(filename)) == os.path.normcase(os.path.abspath(doc.FileName)))
    except Exception:
        return False


class _IsolateObserver:
    """
    Al guardar aislado: se guarda con todo como estaba antes de aislar (lo oculto no queda en el
    archivo) y después se vuelve a aislar. Con "Guardar una copia" o un respaldo no se hace nada
    (revisión del 15/11: si no, el documento quedaba como "no modificado" y se podía perder trabajo).
    """

    def slotStartSaveDocument(self, doc, filename):
        saved = _isolated.get(doc.Name)
        if not saved or not _own_file(doc, filename):
            return
        for name, vis in saved.items():
            obj = doc.getObject(name)
            if obj is not None:
                obj.Visibility = vis
        _pending_reisolate.add(doc.Name)

    def slotFinishSaveDocument(self, doc, filename):
        if doc.Name not in _pending_reisolate:
            return
        _pending_reisolate.discard(doc.Name)
        gdoc = FreeCADGui.getDocument(doc.Name)
        hide, keep = _shown.get(doc.Name, ([], None))
        for name in hide:
            obj = doc.getObject(name)
            if obj is not None:
                obj.Visibility = False
        if keep and doc.getObject(keep) is not None:
            doc.getObject(keep).Visibility = True
        # solo llega acá al guardar el archivo propio (no una copia ni un respaldo): recién guardado,
        # volver a ocultar no tiene que dejarlo como modificado
        try:
            gdoc.Modified = False
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        _shown.pop(doc.Name, None)
        _isolated.pop(doc.Name, None)
        _hide_exit_bar(doc.Name)


_pending_reisolate = set()


# --- Cambiar de nombre, propiedades, padre/hijo, material ------------------------------------------------


def rename(obj, text):
    """Cambia el nombre que se ve (Label) en un paso de deshacer. False si el texto está vacío."""
    from swui.fork import safe_ops

    text = (text or "").strip()
    if not text or text == obj.Label:
        return False
    with safe_ops.undo_step(obj.Document, "Cambiar de nombre"):
        obj.Label = text
    return True


def component_info(link):
    """Lo que muestra Propiedades del componente: nombre, archivo, configuraciones, la actual, suprimido."""
    from swui.fork import config_asm

    linked = getattr(link, "LinkedObject", None)
    path = ""
    try:
        if linked is not None and linked.Document is not link.Document:
            path = linked.Document.FileName
    except Exception:
        path = ""
    try:
        configs = config_asm.part_configs(link)
        current = config_asm.current(link) if len(configs) > 1 else ""
    except Exception:
        configs, current = [], ""
    try:
        suppressed = bool(config_asm.is_suppressed(link))
    except Exception:
        suppressed = False
    return {"name": link.Label, "file": path, "configs": configs, "config": current, "suppressed": suppressed}


def apply_component(link, name=None, config=None, suppressed=None):
    """Aplica lo cambiado en Propiedades del componente, todo en un paso de deshacer."""
    from swui.fork import config_asm, safe_ops

    info = component_info(link)
    doc = link.Document
    with safe_ops.undo_step(doc, "Propiedades del componente"):
        if name and name.strip() and name.strip() != info["name"]:
            link.Label = name.strip()
        if config and config != info["config"] and config in info["configs"]:
            config_asm.set_config(link, config)  # si falla, se anula todo el paso (no queda a medias)
        if suppressed is not None and bool(suppressed) != info["suppressed"]:
            config_asm.suppress(link, bool(suppressed))
        doc.recompute()


def component_relatives(link):
    """(relaciones de posición, lo del ensamblaje que lo usa) del componente."""
    from swui.fork import mates_sw

    asm = assembly_of(link)
    mates = list(mates_sw.mates_of(asm, link)) if asm is not None else []
    users = [o for o in getattr(link, "InList", []) if o is not asm and o not in mates
             and getattr(o, "TypeId", "") not in ("Assembly::JointGroup", "App::DocumentObjectGroup")]
    return mates, users


def component_material(link):
    """Abre Material sobre la pieza del componente (la pieza, como SW)."""
    from swui.fork import material

    linked = getattr(link, "LinkedObject", None)
    doc = linked.Document if linked is not None else link.Document
    return material.show_dialog(doc)


# --- Seleccionar tangencia -----------------------------------------------------------------------------------


def _normal_at(face, point):
    u, v = face.Surface.parameter(point)
    return face.normalAt(u, v)


def tangent_faces(shape, face_name, angle=1.0):
    """
    La cara y todas las que siguen tangentes a ella (como Seleccionar tangencia de SW): se avanza de
    cara en cara por las aristas compartidas mientras las normales en el medio de la arista no
    cambien más de angle grados. Devuelve los nombres "FaceN" en orden.
    """
    faces = shape.Faces
    start = int(face_name[4:]) - 1
    # aristas -> caras, una sola vez (con miles de caras, buscar cara por cara tardaba segundos)
    owners = {}
    for k, f in enumerate(faces):
        for e in f.Edges:
            owners.setdefault(e.hashCode(), []).append(k)
    done, todo = {start}, [start]
    limit = math.cos(math.radians(angle))
    while todo:
        i = todo.pop()
        face = faces[i]
        for edge in face.Edges:
            others = [j for j in owners.get(edge.hashCode(), []) if j not in done]
            if not others:
                continue
            try:
                mid = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2)
            except Exception:
                continue
            for j in others:
                try:
                    n1, n2 = _normal_at(face, mid), _normal_at(faces[j], mid)
                except Exception:
                    continue
                # con signo: un pliegue de 180° (normales opuestas) no es tangente
                if n1.Length > 0 and n2.Length > 0 and n1.dot(n2) / (n1.Length * n2.Length) >= limit:
                    done.add(j)
                    todo.append(j)
    return ["Face%d" % (k + 1) for k in sorted(done)]


def select_tangent():
    """Elige la cara elegida y las tangentes a ella. Devuelve los nombres de las caras."""
    from swui.fork import context_menus as cm

    sel = _entries()
    if len(sel) != 1 or len(sel[0].SubElementNames) != 1:
        return []
    top, sub = sel[0].Object, cm.plain_sub(sel[0].SubElementNames[0])
    parts = sub.split(".")
    if not parts[-1].startswith("Face"):
        return []
    prefix = ".".join(parts[:-1]) + ("." if len(parts) > 1 else "")
    try:
        shape = top.getSubObject(prefix) if prefix else top.Shape
        if shape is None or not hasattr(shape, "Faces"):
            shape = top.Shape
    except Exception:
        shape = top.Shape
    names = tangent_faces(shape, parts[-1])
    FreeCADGui.Selection.clearSelection()
    for n in names:
        FreeCADGui.Selection.addSelection(top.Document.Name, top.Name, prefix + n)
    return names


# --- Exportar cara a DXF -------------------------------------------------------------------------------------


def face_entities(face):
    """La cara plana vista de frente, en su plano, con la esquina de abajo a la izquierda en 0,0."""
    from swui.fork import sheet_metal as sm

    normal = face.Surface.Axis if hasattr(face.Surface, "Axis") else face.normalAt(0, 0)
    try:
        u, v = face.Surface.parameter(face.CenterOfMass)
        normal = face.normalAt(u, v)
    except Exception:
        pass
    rot = FreeCAD.Rotation(normal, V(0, 0, 1))
    flat = face.copy()
    flat.transformShape(FreeCAD.Placement(V(), rot).toMatrix())
    z = flat.BoundBox.ZMin
    flat.translate(V(-flat.BoundBox.XMin, -flat.BoundBox.YMin, -z))
    return sm.edges_to_entities(flat.Edges, sm.OUTLINE_LAYER)


def export_face_dxf(face, path):
    """Guarda el contorno de una cara plana (con sus agujeros) en un DXF 1:1. Devuelve path."""
    from swui.fork import sheet_metal as sm

    if type(face.Surface).__name__ != "Plane":
        raise ValueError("Solo se puede exportar una cara plana.")
    text = sm.dxf_text(face_entities(face))
    with open(path, "w", encoding="ascii", errors="replace", newline="\r\n") as fh:
        fh.write(text)
    return path


def picked_face():
    """(cara, nombre de la pieza, documento) de la cara elegida, o (None, None, None)."""
    ctx, s = picked()
    if ctx is None or ctx.kind not in ("feature", "sketch") or ctx.element_kind != "Face":
        return None, None, None
    try:
        face = s.SubObjects[0]
    except Exception:
        return None, None, None
    doc = s.Object.Document
    body = s.Object if s.Object.TypeId == BODY else None
    name = (body.Label if body is not None else None) or doc.Label
    return face, name, doc


def _export_face_dialog():
    from swui.compat import QtWidgets
    from swui.fork import sheet_metal as sm

    face, name, doc = picked_face()
    if face is None:
        return
    mw = FreeCADGui.getMainWindow()
    if type(face.Surface).__name__ != "Plane":
        QtWidgets.QMessageBox.information(mw, "Exportar a DXF", "Solo se puede exportar una cara plana.")
        return
    folder = os.path.dirname(doc.FileName) if doc.FileName else os.path.expanduser("~")
    start = os.path.join(folder, sm.clean_name(name) + "_cara.dxf")
    path, _f = QtWidgets.QFileDialog.getSaveFileName(mw, "Exportar cara a DXF", start, "DXF (*.dxf)")
    if path:
        try:
            export_face_dxf(face, path)
        except Exception as exc:
            FreeCAD.Console.PrintError("[SWUI fork] Exportar cara a DXF:\n%s\n" % traceback.format_exc())
            QtWidgets.QMessageBox.warning(mw, "Exportar a DXF", "No se pudo guardar el DXF:\n%s" % exc)


# --- Abrir pieza en posición ---------------------------------------------------------------------------------


def part_camera(cam_rotation, comp_rotation):
    """Orientación de la cámara en la pieza para verla igual que en el ensamblaje."""
    return comp_rotation.inverted().multiply(cam_rotation)


def component_rotation(link, asm=None):
    """Giro del componente en el mundo (el del ensamblaje por el suyo)."""
    pl = link.Placement
    parent = asm if asm is not None else assembly_of(link)
    seen = set()
    while parent is not None and parent.Name not in seen:  # subensamblajes: hasta el de afuera
        seen.add(parent.Name)
        pl = parent.Placement.multiply(pl)
        holder = next((o for o in parent.InList if getattr(o, "LinkedObject", None) is parent), None)
        if holder is None:
            break
        pl = holder.Placement.multiply(pl)
        parent = assembly_of(holder)
    return pl.Rotation


def open_in_position(link):
    """Abre la pieza del componente mirada como en el ensamblaje. Devuelve el documento de la pieza."""
    asm_view = FreeCADGui.ActiveDocument.ActiveView
    try:
        cam = asm_view.getCameraOrientation()
    except Exception:
        cam = FreeCAD.Rotation()
    asm = assembly_of(link)
    rot = component_rotation(link, asm)
    FreeCADGui.Selection.clearSelection()
    if asm is not None:
        FreeCADGui.Selection.addSelection(asm.Document.Name, asm.Name, link.Name + ".")
    else:
        FreeCADGui.Selection.addSelection(link)
    FreeCADGui.runCommand("Std_LinkSelectLinked")
    pdoc = link.LinkedObject.Document
    gdoc = FreeCADGui.ActiveDocument
    if gdoc is None or gdoc.Document is not pdoc:
        # no quedó al frente la pieza: no se toca la vista del ensamblaje (revisión del 15/11)
        FreeCAD.Console.PrintLog("[SWUI fork] Abrir pieza en posición: la pieza no quedó al frente.\n")
        return None
    try:
        view = gdoc.ActiveView
        view.setCameraOrientation(part_camera(FreeCAD.Rotation(cam), rot))
        view.fitAll()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Abrir pieza en posición:\n%s\n" % traceback.format_exc())
    return pdoc


# --- Comandos ----------------------------------------------------------------------------------------------


class _Cmd:
    menu = ""
    tip = ""
    icon = ""

    def GetResources(self):
        from swui import paths

        out = {"MenuText": self.menu, "ToolTip": self.tip}
        if self.icon and paths.icon(self.icon):
            out["Pixmap"] = paths.icon(self.icon)
        return out


class _Collapse(_Cmd):
    menu, tip = "Contraer operaciones", "Cierra todas las ramas del árbol"

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        collapse_tree(FreeCAD.ActiveDocument)


class _Invert(_Cmd):
    menu, tip = "Invertir la selección", "Elige todos los otros componentes del ensamblaje"

    def IsActive(self):
        return picked_component() is not None

    def Activated(self):
        invert_selection()


class _Isolate(_Cmd):
    menu, tip = "Aislar", "Muestra solo esto; Salir de aislar vuelve a mostrar todo"

    def target(self):
        ctx, _s = picked()
        if ctx is None:
            return None
        if ctx.kind == "component":
            return ctx.component
        from swui.fork import context_menus as cm

        return cm._body_of(ctx.feature)

    def IsActive(self):
        if self.target() is not None:
            return True
        sel = _entries()  # un sólido suelto (Part::Feature de un STEP)
        return len(sel) == 1 and sel[0].Object.TypeId.startswith("Part::") and hasattr(sel[0].Object, "Shape")

    def Activated(self):
        target = self.target()
        if target is None:
            target = _entries()[0].Object
        isolate(target)


class _ExitIsolate(_Cmd):
    menu, tip = "Salir de aislar", "Vuelve a mostrar lo que se veía antes de aislar"

    def IsActive(self):
        return is_isolated(FreeCAD.ActiveDocument)

    def Activated(self):
        exit_isolate(FreeCAD.ActiveDocument)


class _Rename(_Cmd):
    menu, tip = "Cambiar de nombre", "Cambia el nombre del componente"

    def IsActive(self):
        return picked_component() is not None

    def Activated(self):
        from swui.compat import QtWidgets

        link = picked_component()
        text, ok = QtWidgets.QInputDialog.getText(FreeCADGui.getMainWindow(), "Cambiar de nombre",
                                                  "Nombre:", text=link.Label)
        if ok:
            rename(link, text)


class _Properties(_Cmd):
    menu, tip, icon = "Propiedades del componente...", "Nombre, archivo, configuración y supresión", \
        "fork/t_properties"

    def IsActive(self):
        return picked_component() is not None

    def Activated(self):
        show_properties(picked_component())


class _ParentChild(_Cmd):
    menu, tip = "Padre/Hijo...", "Relaciones de posición del componente y lo que lo usa"

    def IsActive(self):
        return picked_component() is not None

    def Activated(self):
        show_relatives(picked_component())


class _Material(_Cmd):
    menu, tip = "Material...", "Material de la pieza del componente"

    def IsActive(self):
        return picked_component() is not None

    def Activated(self):
        component_material(picked_component())


class _Tangent(_Cmd):
    menu, tip = "Seleccionar tangencia", "Elige la cara y las que siguen tangentes a ella"

    def IsActive(self):
        ctx, _s = picked()
        return ctx is not None and ctx.element_kind == "Face"

    def Activated(self):
        select_tangent()


class _FaceDxf(_Cmd):
    menu, tip, icon = "Exportar a DXF/DWG...", "Guarda la cara plana elegida en un DXF 1:1", "fork/sm_dxf"

    def IsActive(self):
        face, _n, _d = picked_face()
        return face is not None and type(face.Surface).__name__ == "Plane"

    def Activated(self):
        _export_face_dialog()


class _OpenInPosition(_Cmd):
    menu, tip, icon = "Abrir pieza en posición", "Abre la pieza mirada como en el ensamblaje", \
        "fork/t_open_part_pos"

    def IsActive(self):
        return picked_component() is not None

    def Activated(self):
        open_in_position(picked_component())


COMMANDS = ((COLLAPSE, _Collapse), (INVERT, _Invert), (ISOLATE, _Isolate), (EXIT_ISOLATE, _ExitIsolate),
            (RENAME, _Rename), (PROPERTIES, _Properties), (PARENT_CHILD, _ParentChild),
            (MATERIAL, _Material), (TANGENT, _Tangent), (FACE_DXF, _FaceDxf),
            (OPEN_IN_POSITION, _OpenInPosition))


# --- Ventanas -------------------------------------------------------------------------------------------------


def show_properties(link):
    """Propiedades del componente (modal). Devuelve True si se aceptó."""
    from swui.compat import QtWidgets

    info = component_info(link)
    dlg = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dlg.setObjectName("SWUI_component_properties")
    dlg.setWindowTitle("Propiedades del componente")
    form = QtWidgets.QFormLayout(dlg)
    name = QtWidgets.QLineEdit(info["name"])
    form.addRow("Nombre del componente:", name)
    path = QtWidgets.QLabel(info["file"] or "(dentro del ensamblaje)")
    path.setTextInteractionFlags(path.textInteractionFlags())
    form.addRow("Archivo:", path)
    combo = None
    if len(info["configs"]) > 1:
        combo = QtWidgets.QComboBox()
        combo.addItems(info["configs"])
        if info["config"] in info["configs"]:
            combo.setCurrentIndex(info["configs"].index(info["config"]))
        form.addRow("Configuración:", combo)
    sup = QtWidgets.QCheckBox("Suprimido")
    sup.setChecked(info["suppressed"])
    form.addRow("Estado:", sup)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                         | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("Aceptar")
    buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    form.addRow(buttons)
    if dlg.exec():
        apply_component(link, name.text(), combo.currentText() if combo is not None else None, sup.isChecked())
        return True
    return False


def show_relatives(link):
    """Padre/Hijo del componente: sus relaciones de posición y lo del ensamblaje que lo usa."""
    from swui.compat import QtWidgets

    mates, users = component_relatives(link)
    dlg = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dlg.setObjectName("SWUI_component_relatives")
    dlg.setWindowTitle("Padre/Hijo: %s" % link.Label)
    lay = QtWidgets.QVBoxLayout(dlg)
    lay.addWidget(QtWidgets.QLabel("Relaciones de posición:"))
    lst = QtWidgets.QListWidget()
    lst.addItems([m.Label for m in mates] or ["(ninguna)"])
    lay.addWidget(lst)
    lay.addWidget(QtWidgets.QLabel("Lo usan:"))
    lst2 = QtWidgets.QListWidget()
    lst2.addItems([u.Label for u in users] or ["(nada)"])
    lay.addWidget(lst2)
    close = QtWidgets.QPushButton("Cerrar")
    close.clicked.connect(dlg.accept)
    lay.addWidget(close)
    dlg.resize(360, 320)
    dlg.show()
    return dlg


_observer = None


def install():
    global _observer
    for name, cls in COMMANDS:
        try:
            FreeCADGui.addCommand(name, cls())
        except Exception:
            pass  # ya registrado
    if _observer is None:
        _observer = _IsolateObserver()
        FreeCAD.addDocumentObserver(_observer)
