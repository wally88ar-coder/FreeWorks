# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Planos dibujados como en SW 2018 (etapa B de los planos; la A es origin_planes.py).

Relevado en SW 2018 con el mouse (04/11; bloque 100x60x20 corrido del origen, medido en
píxeles): cada plano es el rectángulo de la caja de la pieza vista sobre ese plano, agrandado 5 %
por lado en cada dirección (100 mm -> 5 mm; con 200 mm, 10 mm), en el lugar del plano (no se
estira hasta el origen); sigue a la pieza al reconstruir; contorno azul fino sin relleno, tapado
por la pieza; el nombre arriba a la izquierda, en el plano, del mismo tamaño en pantalla.

FreeCAD 1.1.4 dibuja el plano del origen como un cuadradito del mismo tamaño en pantalla
(`SoShapeScale` dentro del `SoFCSelection` del switch del plano) y el plano de referencia
(`PartDesign::Plane`) como un rectángulo de 4 puntos con relleno amarillo transparente.

Lo que hace este módulo, SOLO en el dibujo (nada en el archivo; sin el addon se ve lo de FreeCAD):
  - plano del origen: el cuadradito pasa a un SoSwitch apagado y al lado, dentro del mismo
    `SoFCSelection`, va el rectángulo + el nombre: un clic sobre el borde elige el plano como
    siempre, el color de elegido lo pinta, y ocultar / mostrar / Ver > Planos siguen andando
    porque todo queda dentro del switch del plano;
  - plano de referencia: sus 4 puntos pasan al rectángulo, sin relleno y en azul, más el nombre;
  - pieza sin sólidos: se deja el dibujo de FreeCAD;
  - se vuelve a calcular después de cada recálculo y si cambia la visibilidad de un Cuerpo.
Si FreeCAD arma el dibujo de otra forma (otra versión), no se toca nada (`self_check`).

Función pública: `refresh(doc)` (sin interfaz no hace nada).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

BODY = "PartDesign::Body"
ORIGIN_PLANE = "App::Plane"
DATUM_PLANE = "PartDesign::Plane"
MARGIN = 0.05  # 5 % por lado, medido en SW
# Pieza sin sólidos: SW dibuja cada plano de ~178 x 110 mm centrado en el origen (medido con el mouse
# el 04/11 contra un cuadrado de 100 mm en el croquis, a 2,3 px/mm; un croquis no lo cambia).
EMPTY_RECT = (-89.0, -55.0, 89.0, 55.0)
COLOR = (0.12, 0.12, 0.85)  # azul de los planos de SW
# Nombre dentro de un SoShapeScale (tamaño fijo en pantalla). Medido con el mouse en 1.1.4 a
# 1366x768: con fuente 10 el texto sale de ~7 px y cambiar scaleFactor no lo cambia (se toma el de
# fábrica); SW lo dibuja de ~14 px -> fuente 20.
LABEL_SCALE = 1
LABEL_FONT = 20.0
WB_NAME = "LikeSolidWorksUIWorkbench"

_state = {"obs": None, "pending": set(), "nodes": {}}


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
    """(x0, y0, x1, y1) del rectángulo SW en las coordenadas del plano; None sin pieza."""
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


# --- Nodos ---------------------------------------------------------------------------------


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


def _label_node(text):
    """Nombre en el plano, del mismo tamaño en pantalla (SoShapeScale de FreeCAD)."""
    from pivy import coin

    # El nombre va encima de la pieza, como en SW (visto con 200 mm de largo): sin prueba de
    # profundidad solo para el texto. OJO: un SoAnnotation adentro del SoFCSelection deja TODA la
    # vista de FreeCAD en blanco (probado con el mouse, 04/11).
    sep = coin.SoSeparator()
    trans = coin.SoTranslation()
    sep.addChild(trans)
    try:
        depth = coin.SoDepthBuffer()
        depth.test = False
        sep.addChild(depth)
    except Exception:
        pass
    inner = coin.SoSeparator()
    font = coin.SoFont()
    font.name = "Arial:Bold"  # SW: negrita derecha (de frente se ve sin cursiva)
    font.size = LABEL_FONT
    shift = coin.SoTranslation()
    shift.translation = (LABEL_FONT * 0.25, -LABEL_FONT * 1.2, 0)  # adentro del rectángulo, arriba a la izquierda
    txt = coin.SoAsciiText()
    txt.string = text
    inner.addChild(font)
    inner.addChild(shift)
    inner.addChild(txt)
    kit = None
    try:
        kit = coin.cast(coin.SoType.fromName("SoShapeScale").createInstance(), "SoBaseKit")
        kit.set("scaleFactor %s" % LABEL_SCALE)
        kit.setPart("shape", inner)
        sep.addChild(kit)
    except Exception:
        sep.addChild(inner)  # sin SoShapeScale: texto en milímetros (se ajusta en _update)
        kit = None
    return {"sep": sep, "trans": trans, "text": txt, "kit": kit, "font": font}


def _origin_nodes(plane):
    """Arma (una vez) el dibujo SW dentro del plano del origen. None si FreeCAD lo arma distinto."""
    from pivy import coin

    key = (plane.Document.Name, plane.Name)
    vo = plane.ViewObject
    sw = _display_switch(vo)
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
    try:
        native = coin.cast(sel.getChild(0), "SoBaseKit")
        scale = coin.cast(native.getField("scaleFactor"), "SoSFFloat")
        native_scale = scale.getValue() or 1.0
    except Exception:
        return None
    ours = coin.SoSwitch()
    ours.whichChild = 0
    sep = coin.SoSeparator()
    color = coin.SoBaseColor()
    color.rgb = COLOR
    style = coin.SoDrawStyle()
    style.lineWidth = 1
    coords = coin.SoCoordinate3()
    lines = coin.SoLineSet()
    label = _label_node(plane.Label)
    for n in (color, style, coords, lines, label["sep"]):
        sep.addChild(n)
    ours.addChild(sep)
    sel.addChild(ours)  # al final: los hijos de FreeCAD quedan en su lugar
    nodes = {"kind": "origin", "sel": sel, "ours": ours, "coords": coords,
             "lines": lines, "label": label, "native_scale": native_scale}
    _state["nodes"][key] = nodes
    return nodes


def _datum_nodes(plane):
    """Plano de referencia: sus propios nodos (4 puntos, borde, cara, material) + el nombre."""
    key = (plane.Document.Name, plane.Name)
    sw = _display_switch(plane.ViewObject)
    if sw is None:
        return None
    coords = _find(sw, "Coordinate3")
    faces = _find(sw, "SoBrepFaceSet")
    mats = _find(sw, "Material")
    if len(coords) != 1 or len(faces) != 1 or len(mats) != 1 or coords[0].point.getNum() != 4:
        return None
    known = _state["nodes"].get(key)
    seps = _find(sw, "Separator")
    if not seps:
        return None
    holder = seps[0]
    if known is not None and holder.findChild(known["label"]["sep"]) >= 0:
        known.update(coords=coords[0], faces=faces[0], mat=mats[0])
        return known
    label = _label_node(plane.Label)
    holder.addChild(label["sep"])
    nodes = {"kind": "datum", "coords": coords[0], "faces": faces[0], "mat": mats[0], "label": label}
    _state["nodes"][key] = nodes
    return nodes


def _native_scale(nodes, value):
    """Tamaño del cuadradito de FreeCAD (0 = no se ve). Se vuelve a pedir el nodo cada vez."""
    from pivy import coin

    sel = nodes["sel"]
    if sel.getNumChildren() < 1 or _type(sel.getChild(0)) != "SoShapeScale":
        return
    scale = coin.cast(coin.cast(sel.getChild(0), "SoBaseKit").getField("scaleFactor"), "SoSFFloat")
    if abs(scale.getValue() - value) > 1e-9:
        scale.setValue(value)


def _update(plane, corners):
    rect = local_rect(plane, corners) or EMPTY_RECT  # pieza sin sólidos: el tamaño de SW
    if plane.TypeId == ORIGIN_PLANE:
        nodes = _origin_nodes(plane)
        if nodes is None:
            return
        _native_scale(nodes, 0.0)
        nodes["ours"].whichChild = 0
        x0, y0, x1, y1 = rect
        pts = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, 0)]
        nodes["coords"].point.setValues(0, len(pts), pts)
        nodes["coords"].point.setNum(len(pts))
        nodes["lines"].numVertices.setValue(len(pts))
    else:
        nodes = _datum_nodes(plane)
        if nodes is None:
            return
        x0, y0, x1, y1 = rect
        pts = [(x1, y1, 0), (x0, y1, 0), (x0, y0, 0), (x1, y0, 0)]
        nodes["coords"].point.setValues(0, 4, pts)
        nodes["faces"].coordIndex.setValues(0, 1, [-1])
        nodes["faces"].coordIndex.setNum(1)
        nodes["mat"].diffuseColor.setValue(COLOR)
        nodes["mat"].transparency.setValue(0)
    label = nodes["label"]
    label["trans"].translation = (x0, y1, 0)
    label["text"].string = plane.Label
    if label["kit"] is None:
        label["font"].size = max(1.0, min(x1 - x0, y1 - y0) * 0.08)


def refresh(doc):
    """Dibujar como SW todos los planos de la pieza (origen y de referencia)."""
    try:
        if FreeCADGui.getDocument(doc.Name) is None:
            return
    except Exception:
        return
    corners = part_corners(doc)
    for o in list(doc.Objects):
        t = getattr(o, "TypeId", "")
        if t not in (ORIGIN_PLANE, DATUM_PLANE) or o.ViewObject is None:
            continue
        try:
            _update(o, corners)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Dibujo de plano %s: %s\n" % (o.Name, traceback.format_exc()))


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
            if obj.TypeId in (BODY, ORIGIN_PLANE, DATUM_PLANE) and _in_workbench():
                _later(obj.Document)
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        if prop not in ("Visibility", "Label", "Placement"):
            return
        try:
            t = obj.TypeId
            if t in (BODY, ORIGIN_PLANE, DATUM_PLANE) and _in_workbench() \
                    and not getattr(obj.Document, "Restoring", False):
                _later(obj.Document)
        except Exception:
            pass


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
