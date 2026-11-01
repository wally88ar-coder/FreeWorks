# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Configuraciones en ensamblajes (etapas 4 y 5 de 5).

Etapa 4, componente en otra configuración (como SW):
- Al hacer clic en un componente (árbol o zona gráfica) aparece al lado del cursor una barrita
  con la lista de configuraciones de su pieza, como la barra contextual de SW (pedido del
  usuario, 01/11). También en el clic derecho: "Configuración del componente".
- Por debajo, el vínculo nativo con "copia al cambiar" (App::Link, LinkCopyOnChange): en
  "Tracking" (decisión del fork: sigue los cambios de la pieza, como SW). Si la configuración no
  es la de la pieza, FreeCAD guarda una copia de la pieza dentro del ensamblaje.
- Error de FreeCAD (NOTAS_TECNICAS, error 3): cuando el vínculo pasa a otra copia, las
  relaciones se guardan con nombres de cara viejos y aparecen rotas al reabrir. El fork las
  vuelve a poner (vaciar y volver a asignar) cada vez que cambia el objeto vinculado.

Etapa 5, configuraciones del ensamblaje:
- La pestaña Configuraciones también sirve en un ensamblaje: la tabla de diseño vive en el
  Ensamblaje (lista "Configuracion" en el objeto Ensamblaje).
- Suprimir componente (clic derecho, "Esta configuración" si el ensamblaje tiene varias): el
  componente se oculta y sus relaciones se suprimen; con configuraciones, por expresión desde
  la columna "Sup_<componente>" (0/1). En 1.1.4 no hay supresión de componentes: queda cargado.
- Con varias configuraciones del ensamblaje, elegir la configuración de un componente la anota
  en la tabla (columna "Conf_<componente>") solo para la configuración activa.

NOMBRES INTERNOS ESTABLES: los de configurations.py, más los alias "Sup_<Name>" y "Conf_<Name>"
de los componentes.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets
from swui.fork import configurations as cf

WB_NAME = "LikeSolidWorksUIWorkbench"
LINK_TYPES = ("App::Link",)
MODE = "Tracking"
SUPPRESS_CMD = "SWUI_ComponentSuppress"
UNSUPPRESS_CMD = "SWUI_ComponentUnsuppress"
CONFIG_CMD = "SWUI_ComponentConfig"

FADE_PX = 100  # distancia del mouse a la barra del componente para que se vaya sola

_state = {"bar": None, "busy": False}


# --- Núcleo (sin interfaz) ------------------------------------------------------------


def assembly_of(obj):
    for p in getattr(obj, "InList", []):
        if p.TypeId == cf.ASSEMBLY:
            return p
    return None


def is_component(obj):
    return getattr(obj, "TypeId", "") in LINK_TYPES and assembly_of(obj) is not None \
        and not getattr(obj, "ElementCount", 0)


def source(link):
    """La pieza (Cuerpo) original del componente, aunque esté apuntando a una copia."""
    try:
        src = getattr(link, "LinkCopyOnChangeSource", None)
        if src is not None:
            return src
        return link.getLinkedObject(True)
    except Exception:
        return None


def part_configs(link):
    """Configuraciones de la pieza del componente ([] si no tiene)."""
    src = source(link)
    if src is None or cf.PROP not in getattr(src, "PropertiesList", []):
        return []
    try:
        return list(src.getEnumerationsOfProperty(cf.PROP) or [])
    except Exception:
        return []


def current(link):
    if cf.PROP in link.PropertiesList:
        return getattr(link, cf.PROP)
    src = source(link)
    return getattr(src, cf.PROP, None) if src is not None else None


def joints_of(link):
    asm = assembly_of(link)
    out = []
    for o in getattr(link, "InList", []):
        if hasattr(o, "Reference1") and hasattr(o, "Reference2") and hasattr(o, "JointType"):
            out.append(o)
    if asm is not None:
        for o in asm.Document.Objects:
            if o not in out and hasattr(o, "Reference1") and hasattr(o, "JointType"):
                if any(r and r[0] is link for r in (o.Reference1, o.Reference2)):
                    out.append(o)
    return out


def capture(links):
    """Geometría de cada referencia de las relaciones de estos componentes, antes de un cambio."""
    from swui.fork import mate_refs

    out = {}
    for link in links:
        for j in joints_of(link):
            for prop in ("Reference1", "Reference2"):
                ref = getattr(j, prop, None)
                if ref and ref[0] is link and ref[1]:
                    try:
                        sigs = mate_refs.ref_signatures(ref)
                    except Exception:
                        sigs = None
                    if sigs:
                        out[(j.Name, prop)] = sigs
    return out


def refresh_joints(link, captured=None, prefer_stored=False):
    """
    Después de cambiar la configuración del componente: volver a ubicar cada cara de sus
    relaciones por geometría (las caras se renumeran entre configuraciones) y vaciar y volver a
    poner la referencia (error 3 de FreeCAD: si no, se guarda con nombres de la copia anterior y
    aparece rota al reabrir). Sin geometría tomada antes, usa la que guarda mate_refs.
    """
    from swui.fork import mate_refs

    captured = captured or {}
    done = []
    try:
        link.recompute()
    except Exception:
        pass
    for j in joints_of(link):
        for prop in ("Reference1", "Reference2"):
            ref = getattr(j, prop, None)
            if not ref or ref[0] is not link or not ref[1]:
                continue
            ref = [ref[0], [s.replace("?", "") for s in ref[1]]]
            saved = mate_refs._read(j).get(prop)
            taken = captured.get((j.Name, prop))
            stored = (saved or taken) if prefer_stored else (taken or saved)
            if stored:
                try:
                    new_ref, _sigs = mate_refs._fix_ref(j, prop, ref, stored)
                    if new_ref is not None:
                        ref = [new_ref[0], list(new_ref[1])]
                except Exception:
                    FreeCAD.Console.PrintLog("[SWUI fork] Reubicar %s:\n%s\n" % (j.Label, traceback.format_exc()))
            try:
                ref = mate_refs.plain_ref(ref)
            except Exception:
                pass
            setattr(j, prop, None)
            setattr(j, prop, ref)
            done.append(j)
    for j in set(done):
        try:
            mate_refs.snapshot(j)
        except Exception:
            pass
    return done


def copy_objects(link):
    """Objetos de la copia de la pieza que FreeCAD guarda para este componente (o [])."""
    for g in getattr(link, "OutList", []):
        if g.TypeId == "App::LinkGroup" and g.Name.startswith("CopyOnChangeGroup"):
            return list(getattr(g, "ElementList", []) or [])
    return []


def repair_copy(link):
    """
    Error de FreeCAD (NOTAS_TECNICAS, error 4): en la copia, un croquis apoyado en una cara de una
    operación que estaba suprimida al copiarse no la vuelve a encontrar ("?Face8", "No planar
    face") y frena el recálculo de toda la copia. Volver a poner el apoyo con el nombre simple de
    la cara lo arregla (probado: después cambia de configuración y vuelve sin errores).
    """
    fixed = []
    for obj in copy_objects(link):
        try:
            support = obj.AttachmentSupport
        except Exception:
            continue
        if not support or not any("?" in s for _o, subs in support for s in subs):
            continue
        plain = [(o, tuple(s.split(".")[-1].replace("?", "") for s in subs)) for o, subs in support]
        obj.AttachmentSupport = None
        obj.AttachmentSupport = plain
        fixed.append(obj)
    return fixed


def _settle(link):
    """Recalcular y, si la copia quedó trabada por un apoyo perdido, arreglarla y recalcular."""
    doc = link.Document
    doc.recompute()
    if repair_copy(link):
        doc.recompute()
    settle_doc(doc)


def settle_doc(doc, rounds=3):
    """
    Con "Tracking", el primer recálculo después de un cambio de la pieza vuelve a copiarla y la
    copia queda tocada con la forma vieja: hace falta otro recálculo (probado 01/11). Recalcular
    hasta que no quede nada tocado. Devuelve cuántos recálculos hizo.
    """
    n = 0
    while n < rounds and any("Touched" in o.State for o in doc.Objects):
        doc.recompute()
        n += 1
    return n


def _force_copy(link, name):
    """
    FreeCAD copia la pieza recién cuando la configuración del componente es distinta de la de
    la pieza: con la misma, el componente seguía atado a la pieza y cambiaba con ella. Pasar por
    otra configuración y volver deja la copia hecha (probado 01/11).
    """
    try:
        if link.LinkedObject is not source(link):
            return False
    except Exception:
        return False
    other = [n for n in part_configs(link) if n != name]
    if not other:
        return False
    link.setExpression(cf.PROP, None)
    setattr(link, cf.PROP, other[0])
    link.Document.recompute()
    setattr(link, cf.PROP, name)
    link.Document.recompute()
    return True


def _configured_links(doc):
    return [o for o in doc.Objects if is_component(o) and len(part_configs(o)) > 1]


def set_config(link, name, scope="this"):
    """Poner el componente en la configuración name de su pieza."""
    if name not in part_configs(link):
        raise ValueError("La pieza no tiene la configuración \"%s\"." % name)
    doc = link.Document
    if cf.PROP not in link.PropertiesList or link.LinkCopyOnChange == "Disabled":
        link.LinkCopyOnChange = MODE
        doc.recompute()
    taken = capture([link])
    _state["busy"] = True  # el observador no repite lo que se hace acá
    try:
        _force_copy(link, name)
        if cf.owner(doc) is not None and cf.configured(doc):
            cf.configure(doc, ("conf", link), name, scope)
        elif getattr(link, cf.PROP) != name:
            setattr(link, cf.PROP, name)
        _settle(link)
        if refresh_joints(link, taken):
            doc.recompute()
    finally:
        _state["busy"] = False
    return link.LinkedObject


def pinned(link):
    """¿El componente tiene su propia configuración (copia de la pieza)?"""
    return cf.PROP in link.PropertiesList and link.LinkCopyOnChange != "Disabled"


def followers(body):
    """Componentes (en los documentos abiertos) que muestran la pieza tal como está, sin configuración propia."""
    out = []
    for doc in FreeCAD.listDocuments().values():
        for obj in doc.Objects:
            try:
                if is_component(obj) and not pinned(obj) and source(obj) is body:
                    out.append(obj)
            except Exception:
                pass
    return out


def pin_followers(doc, name):
    """
    Como SW, cada componente tiene su configuración: cambiar la configuración activa en la
    ventana de la pieza no cambia los componentes. Los que todavía mostraban la pieza tal cual
    se quedan en la configuración de antes (visto con el mouse, 01/11: cambiaban todos).
    """
    body = cf.owner(doc)
    if body is None or getattr(body, "TypeId", "") == cf.ASSEMBLY:
        return []
    old = getattr(body, cf.PROP, None)
    if not old or old == name:
        return []
    done = []
    for link in followers(body):
        set_config(link, old, "all")
        done.append(link)
    return done


def _users(body, name):
    """
    Dónde se usa la configuración name de la pieza en los documentos abiertos:
    [(componente, celdas de la tabla del ensamblaje con ese nombre)]. Celdas vacías = el
    componente la tiene puesta directo (ensamblaje sin configuraciones).
    """
    out = []
    for doc in FreeCAD.listDocuments().values():
        if body is not None and doc is body.Document:
            continue
        for link in list(doc.Objects):
            try:
                if not (is_component(link) and pinned(link) and source(link) is body):
                    continue
            except Exception:
                continue
            cells = []
            alias = cf.bound_alias(link, cf.PROP, doc)
            sheet = cf.table(doc)
            n = cf.alias_col(sheet, alias) if alias and sheet is not None else None
            if n is not None:
                for row in cf.config_rows(sheet):
                    cell = "%s%d" % (cf.col_letter(n), row)
                    if cf._plain(cf._contents(sheet, cell)) == name:
                        cells.append((sheet, cell))
            if cells or (not alias and getattr(link, cf.PROP, None) == name):
                out.append((link, cells))
    return out


def _point_users(users, name):
    docs = []
    for link, cells in users:
        for sheet, cell in cells:
            sheet.set(cell, cf.text_cell(name))
        if link.Document not in docs:
            docs.append(link.Document)
    for doc in docs:
        doc.recompute()  # la lista de configuraciones del componente toma el nombre nuevo
    for link, cells in users:
        if not cells:
            try:
                link.setExpression(cf.PROP, None)
            except Exception:
                pass
            try:
                items = list(link.getEnumerationsOfProperty(cf.PROP) or [])
            except Exception:
                items = []
            if name not in items:
                setattr(link, cf.PROP, part_configs(link))  # la lista de la pieza, ya con el nombre nuevo
            setattr(link, cf.PROP, name)
    for doc in docs:
        doc.recompute()
        settle_assembly(doc)
    return [link for link, _c in users]


def _hook_rename_delete():
    """
    Como SW: cambiar el nombre de una configuración de la pieza no cambia los componentes que
    la usan (antes volvían a la primera, visto con el mouse 01/11); borrar una que usa algún
    componente lo pasa a la activa de la pieza y avisa.
    """
    if getattr(cf.rename, "_swui_asm", False):
        return
    orig_rename, orig_delete = cf.rename, cf.delete

    def rename(doc, old, new, _orig=orig_rename):
        body = cf.owner(doc)
        part = body is not None and getattr(body, "TypeId", "") != cf.ASSEMBLY
        users = _users(body, old) if part else []
        _orig(doc, old, new)
        if users:
            _point_users(users, (new or "").strip())

    def delete(doc, name, _orig=orig_delete):
        body = cf.owner(doc)
        part = body is not None and getattr(body, "TypeId", "") != cf.ASSEMBLY
        users = _users(body, name) if part else []
        _orig(doc, name)
        if users:
            now = cf.active(doc)
            for link in _point_users(users, now):
                FreeCAD.Console.PrintWarning(
                    "%s usaba la configuración «%s», que se eliminó: ahora usa «%s».\n"
                    % (link.Label, name, now))

    rename._swui_asm = delete._swui_asm = True
    cf.rename, cf.delete = rename, delete


def _sup_col(doc, link):
    alias = cf.clean_alias(cf.SUP + link.Name)
    n = cf._add_column(doc, alias, "Suprimir %s" % link.Label, 0 if link.Visibility else 1)
    return alias, n


def _bind_suppression(doc, link, alias):
    sheet = cf.table(doc)
    link.setExpression("Visibility", "%s.%s == 0" % (sheet.Name, alias))
    for j in joints_of(link):
        aliases = []
        for prop in ("Reference1", "Reference2"):
            ref = getattr(j, prop, None)
            a = _visibility_alias(ref[0]) if ref and ref[0] is not None else None
            if a:
                aliases.append(a)
        if aliases:
            j.setExpression("Suppressed", " + ".join("%s.%s" % (sheet.Name, a) for a in sorted(set(aliases))) + " > 0")


def _visibility_alias(link):
    """Alias de supresión de un componente (de su expresión de Visibility) o None."""
    import re

    sheet = cf.table(link.Document)
    if sheet is None:
        return None
    for p, e in getattr(link, "ExpressionEngine", []):
        if p.lstrip(".") == "Visibility":
            m = re.match(r"\s*%s\.([A-Za-z_][A-Za-z0-9_]*)\s*==\s*0\s*$" % re.escape(sheet.Name), e)
            return m.group(1) if m else None
    return None


def is_suppressed(link):
    """Suprimido = oculto por la tabla del ensamblaje (un componente oculto con el ojo no lo está)."""
    return not link.Visibility and _visibility_alias(link) is not None


def suppress(link, on=True, scope="this"):
    """
    Suprimir (on=True) o desactivar la supresión de un componente. Siempre por la tabla del
    ensamblaje (si no estaba, se arma con "Predeterminado", como SW): así se distingue un componente
    suprimido de uno oculto, y Propiedades físicas lo saltea.
    """
    doc = link.Document
    cf.ensure(doc)
    alias = _visibility_alias(link)
    if alias is None:
        alias, _n = _sup_col(doc, link)
        _bind_suppression(doc, link, alias)
    sheet = cf.table(doc)
    n = cf.alias_col(sheet, alias)
    rows = cf.config_rows(sheet) if scope == "all" else [cf.row_of(doc, cf.active(doc))]
    for row in rows:
        sheet.set("%s%d" % (cf.col_letter(n), row), "1" if on else "0")
    doc.recompute()


def _hook_mass():
    """Propiedades físicas (y lo que use mass_props.components) sin los componentes suprimidos."""
    from swui.fork import mass_props as mp

    if getattr(mp.components, "_swui_conf", False):
        return
    original = mp.components

    def components(doc, hidden=True, _original=original):
        out = []
        for part, root, path in _original(doc, hidden):
            token = (path or "").split(".")[0]
            comp = doc.getObject(token) if token else None
            if comp is not None and is_component(comp) and is_suppressed(comp):
                continue
            out.append((part, root, path))
        return out

    components._swui_conf = True
    mp.components = components


def is_config_expression_asm(obj, path, expr):
    p = path.lstrip(".")
    return p == "Visibility" and _visibility_alias(obj) is not None or \
        (p == "Suppressed" and hasattr(obj, "JointType") and cf.table(obj.Document) is not None
         and cf.table(obj.Document).Name + "." in expr)


def _hook_activate():
    """Cambiar la configuración del ensamblaje cambia la de sus componentes: reubicar relaciones."""
    if getattr(cf.activate, "_swui_asm", False):
        return
    original = cf.activate

    def activate(doc, name, _original=original):
        if not any(getattr(o, "TypeId", "") == cf.ASSEMBLY for o in doc.Objects):
            return _original(doc, name)
        links = _configured_links(doc)
        taken = capture(links)
        _state["busy"] = True
        try:
            _original(doc, name)
            settle_doc(doc)
            if any([repair_copy(link) for link in links]):
                doc.recompute()
            if any([refresh_joints(link, taken) for link in links]):
                doc.recompute()
        finally:
            _state["busy"] = False

    activate._swui_asm = True
    cf.activate = activate


# --- Partes de ensamblaje para el DXF ------------------------------------------------------


def copy_info(body):
    """Si body es una copia de un componente: (pieza original, configuración); si no, None."""
    if not cf.is_copy(body):
        return None
    for p in body.InList:
        if p.TypeId in LINK_TYPES and getattr(p, "LinkedObject", None) is body:
            return source(p), current(p)
    return None


def _hook_part_name():
    from swui.fork import sheet_metal as sm

    if getattr(sm.part_name, "_swui_asm", False):
        return
    original = sm.part_name

    def part_name(body, _original=original):
        info = copy_info(body)
        if info is None or info[0] is None:
            return _original(body)
        src, conf = info
        name = src.Document.Label or src.Document.Name
        if len(sm.sheet_bodies(src.Document)) > 1:
            name += "-" + src.Label
        return name + ("-" + conf if conf else "")

    part_name._swui_asm = True
    sm.part_name = part_name


# --- Interfaz ----------------------------------------------------------------------------


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def picked_component():
    """El componente elegido (árbol: el vínculo; zona gráfica: 'Placa_1.Face5' dentro del ensamblaje)."""
    try:
        sel = FreeCADGui.Selection.getSelectionEx("", 0)
    except Exception:
        return None
    if len(sel) != 1:
        return None
    s = sel[0]
    obj = s.Object
    if is_component(obj):
        return obj
    subs = list(s.SubElementNames) or [""]
    if len(subs) != 1 or not subs[0]:
        return None
    doc = obj.Document
    node = obj
    for token in subs[0].split(".")[:-1]:
        child = doc.getObject(token)
        if child is None:
            return None
        if is_component(child):
            return child
        node = child
    return None


def _run(doc, name, fn):
    doc.openTransaction(name)
    try:
        fn()
        doc.recompute()
    except ValueError as e:
        doc.abortTransaction()
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), name, str(e))
        return False
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (name, traceback.format_exc()))
        return False
    doc.commitTransaction()
    return True


def choose_config(link, name):
    if name == current(link):
        return
    if _run(link.Document, "Configuración del componente", lambda: set_config(link, name)):
        try:
            FreeCADGui.getMainWindow().statusBar().showMessage(
                "%s: configuración %s" % (link.Label, name), 5000)
        except Exception:
            pass


class _Bar(QtWidgets.QFrame):
    """Barrita al lado del cursor con la configuración del componente (como la de SW)."""

    def __init__(self):
        flags = (QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.FramelessWindowHint
                 | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        super().__init__(FreeCADGui.getMainWindow(), flags)
        self.setObjectName("SWUI_ComponentBar")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setStyleSheet("#SWUI_ComponentBar { background: #f4f4f4; border: 1px solid #a0a0a0; }")
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        icon = QtWidgets.QLabel("Configuración:")
        self.combo = QtWidgets.QComboBox(self)
        self.combo.setObjectName("SWUI_ComponentConfigCombo")
        self.combo.setMinimumWidth(130)
        lay.addWidget(icon)
        lay.addWidget(self.combo)
        self.link_name = None
        self.doc_name = None
        self.combo.activated.connect(self._picked)
        # como SW: la barra se va sola cuando el mouse se aleja (y la lista no está abierta)
        self._fade = QtCore.QTimer(self)
        self._fade.setInterval(150)
        self._fade.timeout.connect(self._check_mouse)

    def _check_mouse(self):
        if not self.isVisible():
            self._fade.stop()
            return
        if self.combo.view().isVisible():
            return
        if not self.geometry().adjusted(-FADE_PX, -FADE_PX, FADE_PX, FADE_PX).contains(QtGui.QCursor.pos()):
            self.hide()
            self._fade.stop()

    def show_for(self, link):
        names = part_configs(link)
        if len(names) < 2:
            self.hide()
            return
        self.link_name, self.doc_name = link.Name, link.Document.Name
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(names)
        cur = current(link)
        if cur in names:
            self.combo.setCurrentIndex(names.index(cur))
        self.combo.blockSignals(False)
        self.adjustSize()
        pos = QtGui.QCursor.pos() + QtCore.QPoint(18, -self.height() - 14)
        self.move(pos)
        self.show()
        self._fade.start()

    def _picked(self, i):
        try:
            link = FreeCAD.getDocument(self.doc_name).getObject(self.link_name)
        except Exception:
            link = None
        if link is not None:
            choose_config(link, self.combo.itemText(i))
        self.hide()


def _bar():
    if _state["bar"] is None:
        _state["bar"] = _Bar()
    return _state["bar"]


def _on_selection():
    try:
        bar = _state["bar"]
        if not _in_workbench():
            if bar is not None:
                bar.hide()
            return
        # con un panel abierto (relación de posición, operación...) lo elegido es para el panel:
        # la barra estorbaba al elegir la segunda cara (visto con el mouse 01/11; SW no la muestra)
        try:
            busy = FreeCADGui.Control.activeDialog()
        except Exception:
            busy = False
        link = None if busy else picked_component()
        if link is None or len(part_configs(link)) < 2:
            if bar is not None and not bar.combo.view().isVisible():
                bar.hide()
            return
        _bar().show_for(link)
    except RuntimeError:
        _state["bar"] = None
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Barra del componente:\n%s\n" % traceback.format_exc())


class _SelectionObserver:
    def _later(self, *_a):
        QtCore.QTimer.singleShot(0, _on_selection)

    addSelection = setSelection = removeSelection = clearSelection = _later


class _DocObserver:
    """Cuando un componente pasa a otra copia de la pieza, volver a poner sus relaciones."""

    def slotRecomputedDocument(self, doc):
        if _state["busy"] or _state.get("settling"):
            return
        try:
            names = assemblies_using(doc)
        except Exception:
            return
        if names:
            QtCore.QTimer.singleShot(0, lambda: _settle_later(names))

    def slotChangedObject(self, obj, prop):
        if prop != "LinkedObject" or _state["busy"]:
            return
        try:
            if not is_component(obj) or obj.Document.Restoring:
                return
        except Exception:
            return
        name, doc_name = obj.Name, obj.Document.Name
        QtCore.QTimer.singleShot(0, lambda: _refresh_later(doc_name, name))


def assemblies_using(doc):
    """Documentos abiertos con componentes configurados (copias) de piezas de doc."""
    out = []
    for other in FreeCAD.listDocuments().values():
        if other is doc:
            continue
        for obj in other.Objects:
            try:
                src = source(obj) if is_component(obj) and pinned(obj) else None
            except Exception:
                src = None
            if src is not None and src.Document is doc:
                out.append(other.Name)
                break
    return out


def settle_assembly(doc):
    """Después de un cambio en una pieza: recalcular hasta que la copia quede al día y reubicar relaciones."""
    links = [o for o in doc.Objects if is_component(o) and pinned(o)]
    taken = capture(links)
    if not settle_doc(doc):
        return False
    for link in links:
        if repair_copy(link):
            doc.recompute()
    # la configuración de los componentes no cambió: vale la geometría guardada cuando la relación
    # quedó bien (la tomada ahora puede ser la de la copia a medio rehacer: avisaba "la cara plana
    # elegida cambió" al agregar una configuración en la pieza, visto con el mouse 01/11)
    if any([refresh_joints(link, taken, prefer_stored=True) for link in links]):
        doc.recompute()
    return True


def _settle_later(names):
    _state["settling"] = True
    try:
        for name in names:
            try:
                settle_assembly(FreeCAD.getDocument(name))
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Ensamblaje al día:\n%s\n" % traceback.format_exc())
    finally:
        _state["settling"] = False


def _refresh_later(doc_name, name):
    try:
        doc = FreeCAD.getDocument(doc_name)
        link = doc.getObject(name)
    except Exception:
        return
    if link is None:
        return
    try:
        # componente nuevo de una pieza con configuraciones: nace con la configuración activa (SW)
        if not pinned(link) and len(part_configs(link)) > 1:
            set_config(link, current(link), "all")
            return
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Configuración del componente nuevo:\n%s\n" % traceback.format_exc())
    _state["busy"] = True
    try:
        if repair_copy(link):
            doc.recompute()
        if refresh_joints(link):
            doc.recompute()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Relaciones del componente:\n%s\n" % traceback.format_exc())
    finally:
        _state["busy"] = False


class _Command:
    menu = ""
    tip = ""

    def GetResources(self):
        return {"MenuText": self.menu, "ToolTip": self.tip}

    def IsActive(self):
        return self.target() is not None

    def target(self):
        return None


class _Suppress(_Command):
    menu = "Suprimir"
    tip = "Oculta el componente y suprime sus relaciones (en la configuración activa del ensamblaje)"

    def target(self):
        link = picked_component()
        return link if link is not None and not is_suppressed(link) else None

    def Activated(self):
        link = self.target()
        _run(link.Document, "Suprimir componente", lambda: suppress(link, True))


class _Unsuppress(_Command):
    menu = "Desactivar supresión"
    tip = "Vuelve a mostrar el componente y activa sus relaciones"

    def target(self):
        link = picked_component()
        return link if link is not None and is_suppressed(link) else None

    def Activated(self):
        link = self.target()
        _run(link.Document, "Desactivar supresión de componente", lambda: suppress(link, False))


class _ConfigCmd(_Command):
    menu = "Configuración del componente..."
    tip = "Elegir la configuración de la pieza para este componente"

    def target(self):
        link = picked_component()
        return link if link is not None and len(part_configs(link)) > 1 else None

    def Activated(self):
        link = self.target()
        names = part_configs(link)
        cur = current(link)
        name, ok = QtWidgets.QInputDialog.getItem(FreeCADGui.getMainWindow(), "Configuración del componente",
                                                  link.Label + ":", names, names.index(cur) if cur in names else 0,
                                                  False)
        if ok:
            choose_config(link, name)


class _Menu:
    def modifyContextMenu(self, recipient):
        try:
            from swui.fork import feature_tree as ft

            if recipient not in ft.ANCHOR or not _in_workbench() or picked_component() is None:
                return []
            cmds = [c for c, k in ((CONFIG_CMD, _ConfigCmd), (SUPPRESS_CMD, _Suppress), (UNSUPPRESS_CMD, _Unsuppress))
                    if k().target() is not None]
            return [{"insert": c, "menuItem": ft.ANCHOR[recipient]} for c in cmds + (["Separator"] if cmds else [])]
        except Exception:
            return []


def install():
    for name, cls in ((SUPPRESS_CMD, _Suppress), (UNSUPPRESS_CMD, _Unsuppress), (CONFIG_CMD, _ConfigCmd)):
        try:
            FreeCADGui.addCommand(name, cls())
        except Exception:
            pass
    try:
        _hook_part_name()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Nombre del DXF de componentes:\n%s\n" % traceback.format_exc())
    if not _state.get("installed"):
        _state["installed"] = True
        try:
            _state["sel"] = _SelectionObserver()
            FreeCADGui.Selection.addObserver(_state["sel"])
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Barra del componente: sin observador de selección.\n")
        try:
            _state["doc"] = _DocObserver()
            FreeCAD.addDocumentObserver(_state["doc"])
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Relaciones de componentes: sin observador.\n")
        try:
            _state["menu"] = _Menu()
            FreeCADGui.addWorkbenchManipulator(_state["menu"])
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Menú de componentes: no se pudo agregar.\n")
    _hook_activate()
    _hook_rename_delete()
    if pin_followers not in cf._before:
        cf._before.append(pin_followers)
    try:
        _hook_mass()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Propiedades físicas sin suprimidos:\n%s\n" % traceback.format_exc())
    # que no se muestren como ecuaciones
    original = cf.is_config_expression
    if not getattr(original, "_swui_asm", False):
        def is_config_expression(obj, path, expr, _original=original):
            return _original(obj, path, expr) or is_config_expression_asm(obj, path, expr)

        is_config_expression._swui_asm = True
        cf.is_config_expression = is_config_expression
