# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Planos dibujados como en SW 2018 (etapa B de los planos; la A es origin_planes.py; las agarraderas
para cambiar el tamaño, plane_handles.py).

Relevado en SW 2018 con el mouse (04/11; bloque 100x60x20 corrido del origen, medido en
píxeles): cada plano es el rectángulo de la caja de la pieza vista sobre ese plano, agrandado 5 %
por lado en cada dirección (100 mm -> 5 mm; con 200 mm, 10 mm), en el lugar del plano (no se
estira hasta el origen); sigue a la pieza al reconstruir; contorno azul fino sin relleno, tapado
por la pieza; el nombre arriba a la izquierda, en el plano, del mismo tamaño en pantalla y SIEMPRE
encima de la pieza. Pieza sin sólidos: ~178 x 110 mm centrado en el origen. Agrandado a mano con
las agarraderas: conserva ese tamaño (no vuelve al automático; tampoco en SW).

FreeCAD 1.1.4 dibuja el plano del origen como un cuadradito del mismo tamaño en pantalla
(`SoShapeScale`, primer hijo del `SoFCSelection` del switch del plano) y el plano de referencia
(`PartDesign::Plane`) como un rectángulo de 4 puntos con relleno amarillo transparente.

Lo que hace este módulo:
  - plano del origen: el cuadradito de FreeCAD queda en su lugar con `scaleFactor` 0 (moverlo dio
    "Access violation") y al final del mismo `SoFCSelection` va el rectángulo: un clic sobre el
    borde elige el plano como siempre, el color de elegido lo pinta, y ocultar / mostrar /
    Ver > Planos siguen andando porque queda dentro del switch del plano;
  - plano de referencia: sus 4 puntos pasan al rectángulo, sin relleno y en azul;
  - nombres: en una capa encima de todo (SoAnnotation en la raíz de la vista, como las vistas
    previas del croquis; adentro del SoFCSelection dejaba la vista en blanco), visibles solo si el
    plano se está dibujando (`refresh_labels`);
  - tamaño: el de la propiedad `SWUI_PlaneRect` si se cambió con las agarraderas (único dato en
    el archivo; nombre estable), si no el automático;
  - se vuelve a calcular después de cada recálculo y si cambia la visibilidad de un Cuerpo.
Si FreeCAD arma el dibujo de otra forma (otra versión), no se toca nada (`self_check`).

Funciones públicas: `refresh(doc)`, `refresh_labels(doc)`, `plane_rect(plane)`,
`show_rect(plane, rect)` (sin interfaz no hacen nada).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

BODY = "PartDesign::Body"
ORIGIN_PLANE = "App::Plane"
DATUM_PLANE = "PartDesign::Plane"
PLANES = (ORIGIN_PLANE, DATUM_PLANE)
RECT_PROP = "SWUI_PlaneRect"  # [x0, y0, x1, y1] en coordenadas del plano (agarraderas). Nombre estable.
MARGIN = 0.05  # 5 % por lado, medido en SW
# Pieza sin sólidos: SW dibuja cada plano de ~178 x 110 mm centrado en el origen (medido con el mouse
# el 04/11 contra un cuadrado de 100 mm en el croquis, a 2,3 px/mm; un croquis no lo cambia).
EMPTY_RECT = (-89.0, -55.0, 89.0, 55.0)
COLOR = (0.12, 0.12, 0.85)  # azul de los planos de SW
# Nombre dentro de un SoShapeScale (tamaño fijo en pantalla). Medido con el mouse en 1.1.4 a
# 1366x768: con fuente 10 el texto sale de ~7 px y cambiar scaleFactor no lo cambia (se toma el de
# fábrica); SW lo dibuja de ~14 px -> fuente 20.
LABEL_FONT = 20.0
WB_NAME = "LikeSolidWorksUIWorkbench"

_state = {"obs": None, "pending": set(), "nodes": {}, "overlays": {}}


# --- Geometría (sin interfaz) ------------------------------------------------------------


def part_corners(doc):
    """Esquinas de la caja de los sólidos a la vista de la pieza (coordenadas globales)."""
    try:
        from swui.fork import configurations as cf

        is_copy = cf.is_copy
    except Exception:
        def is_copy(_b):
            return False
    box = None
    for o in doc.Objects:
        if getattr(o, "TypeId", "") != BODY or is_copy(o):
            continue
        try:
            if not o.Visibility or o.Shape.isNull() or not o.Shape.Solids:
                continue
            bb = o.Shape.BoundBox
        except Exception:
            continue
        if box is None:
            box = FreeCAD.BoundBox(bb)
        else:
            box.add(bb)
    if box is None or not box.isValid():
        return []
    return [FreeCAD.Vector(x, y, z) for x in (box.XMin, box.XMax)
            for y in (box.YMin, box.YMax) for z in (box.ZMin, box.ZMax)]


def local_rect(plane, corners):
    """(x0, y0, x1, y1) del rectángulo SW automático en las coordenadas del plano; None sin pieza."""
    if not corners:
        return None
    try:
        inv = plane.getGlobalPlacement().inverse()
    except Exception:
        inv = plane.Placement.inverse()
    pts = [inv.multVec(c) for c in corners]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mx, my = (x1 - x0) * MARGIN, (y1 - y0) * MARGIN
    if mx < 1e-6 and my < 1e-6:
        return None
    # una pieza plana vista de canto: que el rectángulo tenga algo de alto
    mx = mx or my
    my = my or mx
    return x0 - mx, y0 - my, x1 + mx, y1 + my


def manual_rect(plane):
    """El tamaño puesto a mano con las agarraderas, o None."""
    try:
        vals = list(getattr(plane, RECT_PROP, []) or [])
    except Exception:
        return None
    if len(vals) != 4 or vals[2] - vals[0] < 1e-6 or vals[3] - vals[1] < 1e-6:
        return None
    return tuple(vals)


def plane_rect(plane, corners=None):
    """Rectángulo del plano tal como se dibuja: a mano, automático, o el de la pieza vacía."""
    rect = manual_rect(plane)
    if rect is not None:
        return rect
    if corners is None:
        corners = part_corners(plane.Document)
    return local_rect(plane, corners) or EMPTY_RECT


# --- Nodos del plano -----------------------------------------------------------------------


def _type(node):
    try:
        return str(node.getTypeId().getName())
    except Exception:
        return ""


def _find(node, name, out=None):
    out = [] if out is None else out
    if _type(node) == name:
        out.append(node)
    try:
        for i in range(node.getNumChildren()):
            _find(node.getChild(i), name, out)
    except Exception:
        pass
    return out


def _display_switch(vo):
    root = vo.RootNode
    for i in range(root.getNumChildren()):
        child = root.getChild(i)
        if _type(child) == "Switch":
            return child
    return None


def _origin_nodes(plane):
    """Arma (una vez) el dibujo SW dentro del plano del origen. None si FreeCAD lo arma distinto."""
    from pivy import coin

    key = (plane.Document.Name, plane.Name)
    sw = _display_switch(plane.ViewObject)
    if sw is None:
        return None
    sel = None
    for i in range(sw.getNumChildren()):
        if _type(sw.getChild(i)) == "SoFCSelection":
            sel = sw.getChild(i)
            break
    if sel is None:
        return None
    # El cuadradito de FreeCAD (SoShapeScale) NO se mueve de lugar: FreeCAD lo busca como primer hijo
    # del SoFCSelection; moverlo a otro switch dio "Access violation" en el FreeCAD del usuario al
    # tocar el ojo del origen (04/11). Se esconde poniendo su scaleFactor en 0.
    if sel.getNumChildren() < 1 or _type(sel.getChild(0)) != "SoShapeScale":
        return None
    known = _state["nodes"].get(key)
    # pivy da un objeto Python nuevo por cada nodo pedido: comparar con findChild, no con "is"
    if known is not None and sel.findChild(known["ours"]) >= 0:
        return known
    ours = coin.SoSwitch()
    ours.whichChild = 0
    sep = coin.SoSeparator()
    color = coin.SoBaseColor()
    color.rgb = COLOR
    style = coin.SoDrawStyle()
    style.lineWidth = 1
    coords = coin.SoCoordinate3()
    lines = coin.SoLineSet()
    for n in (color, style, coords, lines):
        sep.addChild(n)
    ours.addChild(sep)
    sel.addChild(ours)  # al final: los hijos de FreeCAD quedan en su lugar
    nodes = {"kind": "origin", "sel": sel, "ours": ours, "coords": coords, "lines": lines}
    _state["nodes"][key] = nodes
    return nodes


def _datum_nodes(plane):
    """Plano de referencia: sus propios nodos (4 puntos, cara, material)."""
    sw = _display_switch(plane.ViewObject)
    if sw is None:
        return None
    coords = _find(sw, "Coordinate3")
    faces = _find(sw, "SoBrepFaceSet")
    mats = _find(sw, "Material")
    if len(coords) != 1 or len(faces) != 1 or len(mats) != 1 or coords[0].point.getNum() != 4:
        return None
    nodes = {"kind": "datum", "coords": coords[0], "faces": faces[0], "mat": mats[0]}
    _state["nodes"][(plane.Document.Name, plane.Name)] = nodes
    return nodes


def _native_scale(nodes, value):
    """Tamaño del cuadradito de FreeCAD (0 = no se ve). Se vuelve a pedir el nodo cada vez."""
    from pivy import coin

    sel = nodes["sel"]
    if sel.getNumChildren() < 1 or _type(sel.getChild(0)) != "SoShapeScale":
        return
    kit = coin.cast(sel.getChild(0), "SoBaseKit")
    scale = coin.cast(kit.getField("scaleFactor"), "SoSFFloat")
    if abs(scale.getValue() - value) > 1e-9:
        scale.setValue(value)
    # Con scaleFactor 0 no se ve, pero SE SEGUÍA ELIGIENDO: con la cámara guardada en el archivo del
    # usuario ("test planos", 05/11) 192 de 300 clics en el fondo elegían Planta, y clics seguidos
    # alternaban plano / Cuerpo. Se lo hace no elegible desde adentro (SoPickStyle UNPICKABLE con
    # override al principio de su parte "shape": adentro hay PickStyle de FreeCAD que si no la pisan);
    # el nodo sigue siendo el primer hijo del SoFCSelection, que es lo que FreeCAD busca.
    try:
        shape = kit.getPart("shape", False)
        if shape is None:
            return
        group = coin.cast(shape, "SoGroup")
        pick = nodes.get("pick")
        has = pick is not None and group.findChild(pick) == 0
        if value == 0 and not has:
            pick = coin.SoPickStyle()
            pick.style = coin.SoPickStyle.UNPICKABLE
            pick.setOverride(True)
            group.insertChild(pick, 0)
            nodes["pick"] = pick
        elif value != 0 and has:
            group.removeChild(0)
            nodes["pick"] = None
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cuadradito del plano: %s\n" % traceback.format_exc())


def show_rect(plane, rect):
    """Dibujar el plano con ese rectángulo (también durante el arrastre de una agarradera)."""
    x0, y0, x1, y1 = rect
    if plane.TypeId == ORIGIN_PLANE:
        nodes = _origin_nodes(plane)
        if nodes is None:
            return False
        _native_scale(nodes, 0.0)
        nodes["ours"].whichChild = 0
        pts = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, 0)]
        nodes["coords"].point.setValues(0, len(pts), pts)
        nodes["coords"].point.setNum(len(pts))
        nodes["lines"].numVertices.setValue(len(pts))
    else:
        nodes = _datum_nodes(plane)
        if nodes is None:
            return False
        pts = [(x1, y1, 0), (x0, y1, 0), (x0, y0, 0), (x1, y0, 0)]
        nodes["coords"].point.setValues(0, 4, pts)
        nodes["faces"].coordIndex.setValues(0, 1, [-1])
        nodes["faces"].coordIndex.setNum(1)
        nodes["mat"].diffuseColor.setValue(COLOR)
        nodes["mat"].transparency.setValue(0)
    _label(plane, rect)
    return True


# --- Nombres encima de todo ------------------------------------------------------------------


def _overlay(doc):
    """Capa de nombres del documento, colgada de la raíz de su vista 3D (se rearma si cambió)."""
    from pivy import coin

    try:
        view = FreeCADGui.getDocument(doc.Name).ActiveView
        root = view.getSceneGraph()
    except Exception:
        return None
    ov = _state["overlays"].get(doc.Name)
    if ov is not None:
        try:
            if root.findChild(ov["root"]) >= 0:
                return ov
        except Exception:
            pass
    ann = coin.SoAnnotation()
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.UNPICKABLE  # los nombres no se eligen ni tapan clics
    ann.addChild(pick)
    root.addChild(ann)
    ov = {"root": ann, "labels": {}}
    _state["overlays"][doc.Name] = ov
    return ov


def _label_nodes(ov, name):
    from pivy import coin

    known = ov["labels"].get(name)
    if known is not None:
        return known
    sw = coin.SoSwitch()
    sw.whichChild = -1
    sep = coin.SoSeparator()
    color = coin.SoBaseColor()
    color.rgb = COLOR
    xf = coin.SoTransform()
    trans = coin.SoTranslation()
    inner = coin.SoSeparator()
    font = coin.SoFont()
    font.name = "Arial:Bold"  # SW: negrita derecha (de frente se ve sin cursiva)
    font.size = LABEL_FONT
    shift = coin.SoTranslation()
    shift.translation = (LABEL_FONT * 0.25, -LABEL_FONT * 1.2, 0)  # adentro, arriba a la izquierda
    txt = coin.SoAsciiText()
    for n in (font, shift, txt):
        inner.addChild(n)
    for n in (color, xf, trans):
        sep.addChild(n)
    try:
        kit = coin.cast(coin.SoType.fromName("SoShapeScale").createInstance(), "SoBaseKit")
        kit.setPart("shape", inner)
        sep.addChild(kit)
    except Exception:
        sep.addChild(inner)
    sw.addChild(sep)
    ov["root"].addChild(sw)
    nodes = {"sw": sw, "xf": xf, "trans": trans, "text": txt}
    ov["labels"][name] = nodes
    return nodes


def _label(plane, rect):
    ov = _overlay(plane.Document)
    if ov is None:
        return
    nodes = _label_nodes(ov, plane.Name)
    try:
        m = plane.getGlobalPlacement().toMatrix()
    except Exception:
        m = plane.Placement.toMatrix()
    nodes["xf"].setMatrix(_coin_matrix(m))
    nodes["trans"].translation = (rect[0], rect[3], 0)
    nodes["text"].string = plane.Label
    nodes["sw"].whichChild = 0 if _drawn(plane) else -1


def _coin_matrix(m):
    from pivy import coin

    return coin.SbMatrix(m.A11, m.A21, m.A31, m.A41,
                         m.A12, m.A22, m.A32, m.A42,
                         m.A13, m.A23, m.A33, m.A43,
                         m.A14, m.A24, m.A34, m.A44)


def _switch_on(vo):
    try:
        return vo.SwitchNode.whichChild.getValue() != -1
    except Exception:
        return bool(getattr(vo, "Visibility", False))


def _drawn(plane):
    """¿El plano se está dibujando? (su switch, el de su carpeta del origen y el de su Cuerpo)."""
    if plane.ViewObject is None or not _switch_on(plane.ViewObject):
        return False
    try:
        for parent in plane.InList:
            if parent.TypeId in ("App::Origin", BODY) and parent.ViewObject is not None:
                if not _switch_on(parent.ViewObject):
                    return False
                if parent.TypeId == "App::Origin":
                    for grand in parent.InList:
                        if grand.TypeId == BODY and grand.ViewObject is not None \
                                and not _switch_on(grand.ViewObject):
                            return False
    except Exception:
        pass
    return True


def refresh_labels(doc):
    """Prender / apagar los nombres según qué planos se ven (lo llama también origin_planes)."""
    ov = _state["overlays"].get(doc.Name)
    if ov is None:
        return
    for name, nodes in list(ov["labels"].items()):
        obj = doc.getObject(name)
        try:
            nodes["sw"].whichChild = 0 if obj is not None and _drawn(obj) else -1
        except Exception:
            pass


# --- Recalcular ------------------------------------------------------------------------------


def refresh(doc):
    """Dibujar como SW todos los planos de la pieza (origen y de referencia)."""
    try:
        if FreeCADGui.getDocument(doc.Name) is None:
            return
    except Exception:
        return
    corners = part_corners(doc)
    for o in list(doc.Objects):
        if getattr(o, "TypeId", "") not in PLANES or o.ViewObject is None:
            continue
        try:
            show_rect(o, plane_rect(o, corners))
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Dibujo de plano %s: %s\n" % (o.Name, traceback.format_exc()))
    refresh_labels(doc)


def self_check():
    """Para el chequeo de compatibilidad (fase 6): ¿se pudo armar el dibujo en una pieza abierta?"""
    return bool(_state["nodes"])


# --- Observador ----------------------------------------------------------------------------


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _later(doc):
    name = doc.Name
    if name in _state["pending"]:
        return
    _state["pending"].add(name)

    def go():
        _state["pending"].discard(name)
        try:
            d = FreeCAD.getDocument(name)
        except Exception:
            return
        refresh(d)

    QtCore.QTimer.singleShot(0, go)


class _Observer:
    def slotRecomputedDocument(self, doc):
        if _in_workbench():
            _later(doc)

    def slotCreatedDocument(self, doc):
        name = doc.Name
        QtCore.QTimer.singleShot(300, lambda: _later_by_name(name))

    def slotCreatedObject(self, obj):
        try:
            if obj.TypeId in (BODY,) + PLANES and _in_workbench():
                _later(obj.Document)
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        if prop not in ("Visibility", "Label", "Placement", RECT_PROP):
            return
        try:
            t = obj.TypeId
            if t in (BODY, "App::Origin") + PLANES and _in_workbench() \
                    and not getattr(obj.Document, "Restoring", False):
                _later(obj.Document)
        except Exception:
            pass

    def slotDeletedDocument(self, doc):
        _state["overlays"].pop(doc.Name, None)

    # Ctrl+Z / Ctrl+Y del tamaño puesto con las agarraderas: deshacer saca la propiedad sin avisar
    # un cambio (visto con el mouse, 05/11: Rehacer activo y el plano seguía grande)
    def slotUndoDocument(self, doc):
        if _in_workbench():
            _later(doc)

    def slotRedoDocument(self, doc):
        if _in_workbench():
            _later(doc)


def _later_by_name(name):
    try:
        if _in_workbench():
            _later(FreeCAD.getDocument(name))
    except Exception:
        pass


def install():
    if _state["obs"] is None:
        _state["obs"] = _Observer()
        FreeCAD.addDocumentObserver(_state["obs"])
