# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Planos principales (Alzado, Planta, Vista lateral) que se muestran y ocultan como en SW 2018.

Relevado en SW 2018 con el mouse (04/11, pedido del usuario):
  - pieza nueva: los tres planos ocultos;
  - cada plano tiene su propio mostrar/ocultar;
  - un plano oculto elegido en el árbol se dibuja mientras está elegido (también con
    Ver > Ocultar/Mostrar > Planos apagado);
  - Ver > Ocultar/Mostrar > Planos apaga/prende el dibujo de TODOS los planos sin cambiar lo
    que se mostró uno por uno;
  - Ver > Ocultar/Mostrar > Planos primarios muestra u oculta los tres de una vez (sí cambia
    lo de cada uno).

FreeCAD 1.1.4 (medido con guion): los planos, ejes y el punto del origen están dentro de la
carpeta "Origen de Coordenadas" (`App::Origin`), y esa carpeta manda: oculta, no se dibuja
nada aunque el plano tenga el ojo abierto; prenderla o apagarla NO cambia el ojo de los de
adentro.

Lo que hace este módulo (solo visibilidad nativa; el archivo queda normal, sin nada propio):
  - el ojo de cada plano / eje / punto es el que manda: la carpeta se prende sola si hay algo
    adentro a la vista y se apaga sola si no queda nada; el ojo de la carpeta prende los tres
    planos o apaga todo lo de adentro;
  - al abrir un archivo y en una pieza nueva, si la carpeta está oculta, los de adentro quedan
    con el ojo cerrado (antes tenían el ojo abierto sin verse; sin marcar el archivo cambiado);
  - plano / eje / punto del origen oculto elegido en el árbol: se dibuja mientras está elegido,
    tocando solo el dibujo (SwitchNode), no el ojo;
  - Ver > Ocultar/Mostrar > Planos (preferencia "VerPlanos"): apagado, los planos con el ojo
    abierto no se dibujan (SwitchNode), y vuelven al prenderlo;
  - Ver > Ocultar/Mostrar > Planos primarios: los tres planos del primer Cuerpo de la pieza;
  - la carpeta de una pieza nueva se llama "Origen" y el punto "Punto de origen" (la traducción
    de FreeCAD les ponía el mismo nombre y la carpeta quedaba "Origen de Coordenadas001").

La lógica se puede usar sin menú (regla "panel = cara de una función"): `set_visible`,
`set_primary_planes`, `primary_planes_shown`, `set_planes_drawn`, `normalize`.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

WB_NAME = "LikeSolidWorksUIWorkbench"
BODY = "PartDesign::Body"
ORIGIN = "App::Origin"
ORIGIN_FEATURES = ("App::Plane", "App::Line", "App::Point")
# planos que apaga Ver > Planos (los del origen, los de referencia de pieza y de ensamblaje)
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
PRIMARY_ROLES = ("XY_Plane", "XZ_Plane", "YZ_Plane")
PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
KEY_PLANES = "VerPlanos"
CMD_PLANES = "SWUI_ViewPlanes"
CMD_PRIMARY = "SWUI_ViewPrimaryPlanes"
COMMANDS = (CMD_PLANES, CMD_PRIMARY)
ORIGIN_LABEL = "Origen"
POINT_LABEL = "Punto de origen"

_state = {"busy": 0, "app_obs": None, "sel_obs": None, "pending": {}, "preview": [],
          "planes_pending": False}


# --- Lógica (funciones públicas) ---------------------------------------------------------


def origin_of(obj):
    """La carpeta del origen que contiene a obj (plano, eje o punto del origen), o None."""
    try:
        for parent in obj.InList:
            if parent.TypeId == ORIGIN:
                return parent
    except Exception:
        pass
    return None


def planes_drawn():
    """Ver > Ocultar/Mostrar > Planos: True = se dibujan los planos con el ojo abierto."""
    return FreeCAD.ParamGet(PARAMS).GetBool(KEY_PLANES, True)


def set_visible(obj, on):
    """
    Mostrar / ocultar un plano, eje o punto del origen como en SW: cambia su ojo y la carpeta
    sigue sola (también sirve para cualquier otro objeto: cambia solo su ojo).
    """
    obj.ViewObject.Visibility = bool(on)
    origin = origin_of(obj)
    if origin is not None:
        _sync_origin(origin, "child")


def primary_body(doc):
    """El Cuerpo cuyos planos son "los planos primarios": el primero de la pieza (no copias)."""
    try:
        from swui.fork import configurations as cf

        is_copy = cf.is_copy
    except Exception:
        def is_copy(_b):
            return False
    for o in doc.Objects:
        if getattr(o, "TypeId", "") == BODY and not is_copy(o):
            return o
    return None


def primary_planes(doc):
    body = primary_body(doc) if doc is not None else None
    if body is None or getattr(body, "Origin", None) is None:
        return []
    return [f for f in body.Origin.OriginFeatures if getattr(f, "Role", "") in PRIMARY_ROLES]


def primary_planes_shown(doc):
    planes = primary_planes(doc)
    return bool(planes) and all(p.ViewObject.Visibility for p in planes)


def set_primary_planes(doc, on):
    """Mostrar u ocultar los tres planos principales de la pieza (Planos primarios de SW)."""
    planes = primary_planes(doc)
    for p in planes:
        p.ViewObject.Visibility = bool(on)
    if planes:
        _sync_origin(origin_of(planes[0]), "child")
    _update_actions()


def set_planes_drawn(on):
    """Ver > Ocultar/Mostrar > Planos: dibujar o no TODOS los planos (los ojos no cambian)."""
    FreeCAD.ParamGet(PARAMS).SetBool(KEY_PLANES, bool(on))
    for doc in FreeCAD.listDocuments().values():
        _apply_planes_drawn(doc, restore=bool(on))
    _update_actions()


def normalize(doc):
    """
    Carpetas del origen ocultas con planos/ejes/punto de ojo abierto (lo normal en FreeCAD: no se
    ven): cerrarles el ojo, para que el ojo diga lo que se ve. No marca el archivo como cambiado.
    """
    def work():
        for o in list(doc.Objects):
            if getattr(o, "TypeId", "") != ORIGIN:
                continue
            if o.ViewObject is None or o.ViewObject.Visibility:
                continue
            for f in o.OriginFeatures:
                if f.ViewObject is not None and f.ViewObject.Visibility:
                    f.ViewObject.Visibility = False

    _quiet(doc, work)


# --- Interno ------------------------------------------------------------------------------


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _quiet(doc, fn):
    """Cambios de dibujo propios: sin que los vea el observador y sin marcar el archivo."""
    gdoc = None
    modified = None
    try:
        gdoc = FreeCADGui.getDocument(doc.Name)
        modified = gdoc.Modified
    except Exception:
        pass
    _state["busy"] += 1
    try:
        fn()
    finally:
        _state["busy"] -= 1
        try:
            if gdoc is not None and modified is False:
                gdoc.Modified = False
        except Exception:
            pass


def _sync_origin(origin, kind):
    """
    kind "child": la carpeta a la vista si y solo si hay algo adentro a la vista.
    kind "container" (el usuario tocó el ojo de la carpeta): prendida sin nada adentro -> los tres
    planos; apagada -> todo lo de adentro con el ojo cerrado.
    """
    try:
        vo = origin.ViewObject
        feats = [f for f in origin.OriginFeatures if f.ViewObject is not None]
    except Exception:
        return
    any_on = any(f.ViewObject.Visibility for f in feats)

    def work():
        if kind == "container":
            if vo.Visibility and not any_on:
                for f in feats:
                    if getattr(f, "Role", "") in PRIMARY_ROLES:
                        f.ViewObject.Visibility = True
            elif not vo.Visibility and any_on:
                for f in feats:
                    f.ViewObject.Visibility = False
        else:
            if any_on and not vo.Visibility:
                vo.Visibility = True
            elif not any_on and vo.Visibility:
                vo.Visibility = False

    _state["busy"] += 1
    try:
        work()
    finally:
        _state["busy"] -= 1
    if not planes_drawn():
        _apply_planes_drawn(origin.Document, restore=False)


def _flush():
    pending = dict(_state["pending"])
    _state["pending"].clear()
    for (doc_name, name), kind in pending.items():
        try:
            origin = FreeCAD.getDocument(doc_name).getObject(name)
        except Exception:
            origin = None
        if origin is not None:
            _sync_origin(origin, kind)
    _update_actions()


def _queue(origin, kind):
    key = (origin.Document.Name, origin.Name)
    _state["pending"][key] = kind  # vale el último cambio (pick_plane prende carpeta y planos juntos)
    QtCore.QTimer.singleShot(0, _flush)


def _apply_planes_drawn(doc, restore):
    """Planos apagados: SwitchNode en -1 a los que tienen el ojo abierto. restore: devolverlos."""
    previewed = {(d, n) for d, n, _kind, _old in _state["preview"]}

    def work():
        for o in list(doc.Objects):
            if getattr(o, "TypeId", "") not in PLANE_TYPES:
                continue
            vo = o.ViewObject
            if vo is None or not vo.Visibility or (doc.Name, o.Name) in previewed:
                continue
            try:
                sw = vo.SwitchNode
                if restore:
                    if sw.whichChild.getValue() == -1:
                        vo.Visibility = False  # FreeCAD vuelve a armar su dibujo al prender
                        vo.Visibility = True
                elif sw.whichChild.getValue() != -1:
                    sw.whichChild = -1
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Ver planos: %s\n" % traceback.format_exc())

    _quiet(doc, work)


def _apply_planes_later():
    if _state["planes_pending"]:
        return
    _state["planes_pending"] = True

    def go():
        _state["planes_pending"] = False
        if planes_drawn():
            return
        for doc in FreeCAD.listDocuments().values():
            _apply_planes_drawn(doc, restore=False)

    QtCore.QTimer.singleShot(0, go)


def _new_origin(doc_name, name):
    """Pieza nueva: nombres claros y planos ocultos (como SW), sin marcar nada."""
    try:
        doc = FreeCAD.getDocument(doc_name)
        origin = doc.getObject(name)
        if origin is None:
            return
        if origin.Label.startswith("Origen de Coordenadas") or origin.Label.startswith("Origin"):
            origin.Label = ORIGIN_LABEL
        for f in origin.OriginFeatures:
            if f.TypeId == "App::Point" and (f.Label.startswith("Origen de Coordenadas")
                                            or f.Label.startswith("Origin")):
                f.Label = POINT_LABEL
        normalize(doc)
        _update_actions()
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Origen nuevo: %s\n" % traceback.format_exc())


# --- Plano oculto elegido: se dibuja mientras está elegido ------------------------------


def _drawn(obj):
    vo = obj.ViewObject
    if vo is None or not vo.Visibility:
        return False
    origin = origin_of(obj)
    if origin is not None and not origin.ViewObject.Visibility:
        return False
    if obj.TypeId in PLANE_TYPES and not planes_drawn():
        return False
    return True


def _start_preview(doc_name, obj_name):
    try:
        if not _in_workbench():
            return
        doc = FreeCAD.getDocument(doc_name)
        obj = doc.getObject(obj_name)
        if obj is None or obj.TypeId not in ORIGIN_FEATURES or _drawn(obj):
            return
        if any(d == doc_name and n == obj_name for d, n, _k, _o in _state["preview"]):
            return
        origin = origin_of(obj)
        sw = obj.ViewObject.SwitchNode
        old = sw.whichChild.getValue()

        def work():
            if origin is not None and not origin.ViewObject.Visibility:
                origin.ViewObject.Visibility = True  # sus hijos con el ojo cerrado siguen sin verse
                _state["preview"].append((doc_name, origin.Name, "origin", False))
            sw.whichChild = 0

        _quiet(doc, work)
        _state["preview"].append((doc_name, obj_name, "switch", old))
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Plano elegido: %s\n" % traceback.format_exc())


def _end_preview():
    if not _state["preview"]:
        return
    try:
        selected = {(s.Object.Document.Name, s.Object.Name) for s in FreeCADGui.Selection.getSelectionEx("*")}
    except Exception:
        selected = set()
    keep, done = [], []
    entries = list(_state["preview"])
    # se mantiene lo que sigue elegido (y la carpeta que lo muestra)
    live = {(d, n) for d, n, k, _o in entries if k == "switch" and (d, n) in selected}
    for d, n, k, old in entries:
        if k == "switch" and (d, n) in live:
            keep.append((d, n, k, old))
        elif k == "origin" and any(dd == d for dd, _nn in live):
            keep.append((d, n, k, old))
        else:
            done.append((d, n, k, old))
    _state["preview"] = keep
    for d, n, k, old in reversed(done):
        try:
            doc = FreeCAD.getDocument(d)
            obj = doc.getObject(n)
            if obj is None:
                continue

            def work(obj=obj, k=k, old=old):
                if k == "switch":
                    if not obj.ViewObject.Visibility:
                        obj.ViewObject.SwitchNode.whichChild = -1
                    elif old == -1 and not planes_drawn() and obj.TypeId in PLANE_TYPES:
                        obj.ViewObject.SwitchNode.whichChild = -1
                elif k == "origin":
                    if not any(f.ViewObject.Visibility for f in obj.OriginFeatures):
                        obj.ViewObject.Visibility = False

            _quiet(doc, work)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Plano elegido (fin): %s\n" % traceback.format_exc())


class _SelObserver:
    def addSelection(self, doc, obj, sub, pnt):
        if not sub:  # elegido entero (árbol), no una cara
            QtCore.QTimer.singleShot(0, lambda: _start_preview(doc, obj))
        QtCore.QTimer.singleShot(0, _end_preview)

    def removeSelection(self, doc, obj, sub):
        QtCore.QTimer.singleShot(0, _end_preview)

    def setSelection(self, doc):
        QtCore.QTimer.singleShot(0, _end_preview)

    def clearSelection(self, doc):
        QtCore.QTimer.singleShot(0, _end_preview)


# --- Observador de documentos -------------------------------------------------------------


class _AppObserver:
    def slotChangedObject(self, obj, prop):
        if prop != "Visibility" or _state["busy"]:
            return
        try:
            doc = obj.Document
            if getattr(doc, "Restoring", False) or not _in_workbench():
                return
            t = obj.TypeId
        except Exception:
            return
        if t == ORIGIN:
            _queue(obj, "container")
        elif t in ORIGIN_FEATURES:
            origin = origin_of(obj)
            if origin is not None:
                _queue(origin, "child")
        if t in PLANE_TYPES and not planes_drawn():
            _apply_planes_later()

    def slotCreatedObject(self, obj):
        try:
            if obj.TypeId != ORIGIN or getattr(obj.Document, "Restoring", False) or not _in_workbench():
                return
            doc_name, name = obj.Document.Name, obj.Name
        except Exception:
            return
        QtCore.QTimer.singleShot(0, lambda: _new_origin(doc_name, name))

    def slotCreatedDocument(self, doc):
        name = doc.Name

        def later():
            try:
                d = FreeCAD.getDocument(name)
            except Exception:
                return
            if not _in_workbench():
                return
            normalize(d)
            if not planes_drawn():
                _apply_planes_drawn(d, restore=False)
            _update_actions()

        QtCore.QTimer.singleShot(0, later)  # al abrir: el documento ya está cargado cuando corre

    def slotActivateDocument(self, doc):
        QtCore.QTimer.singleShot(0, _update_actions)


# --- Comandos (Ver > Ocultar/Mostrar) -----------------------------------------------------


def _update_actions():
    """Tilde de los dos comandos según el estado (FreeCAD no lo pregunta al abrir el menú)."""
    try:
        from swui.compat import QtGui

        mw = FreeCADGui.getMainWindow()
        doc = FreeCAD.ActiveDocument
        states = {CMD_PLANES: planes_drawn(), CMD_PRIMARY: doc is not None and primary_planes_shown(doc)}
        for act in mw.findChildren(QtGui.QAction):
            want = states.get(act.objectName())
            if want is not None and act.isCheckable() and act.isChecked() != want:
                act.blockSignals(True)
                act.setChecked(want)
                act.blockSignals(False)
    except Exception:
        pass


class _PlanesCommand:
    def GetResources(self):
        return {"MenuText": "Planos",
                "ToolTip": "Dibujar o no todos los planos (lo que se mostró de cada uno no cambia)",
                "Checkable": planes_drawn()}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self, checked=None):
        on = bool(checked) if checked is not None else not planes_drawn()
        set_planes_drawn(on)


class _PrimaryCommand:
    def GetResources(self):
        return {"MenuText": "Planos primarios",
                "ToolTip": "Mostrar u ocultar Alzado, Planta y Vista lateral",
                "Checkable": False}

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and bool(primary_planes(doc))

    def Activated(self, checked=None):
        doc = FreeCAD.ActiveDocument
        if doc is None:
            return
        on = bool(checked) if checked is not None else not primary_planes_shown(doc)
        set_primary_planes(doc, on)


def install():
    if _state["app_obs"] is None:
        _state["app_obs"] = _AppObserver()
        FreeCAD.addDocumentObserver(_state["app_obs"])
    if _state["sel_obs"] is None:
        _state["sel_obs"] = _SelObserver()
        FreeCADGui.Selection.addObserver(_state["sel_obs"])
    for name, cmd in ((CMD_PLANES, _PlanesCommand()), (CMD_PRIMARY, _PrimaryCommand())):
        try:
            FreeCADGui.addCommand(name, cmd)
        except Exception:
            pass  # ya registrado
