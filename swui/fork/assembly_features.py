# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Operaciones de ensamblaje como SW 2018 (fase 5, etapa 4): Asistente para taladro y Extruir
corte que agujerean varias piezas de una vez, atados a un croquis del ensamblaje.

Flujo como SW: se elige la cara plana en el ensamblaje, se abre un croquis ahí (posiciones de
los agujeros o el perfil del corte), al salir del croquis el panel muestra el tipo de taladro (el
mismo de la fase 2) o la profundidad del corte, y la lista "Piezas afectadas" (arranca con las
piezas que el agujero o el corte atraviesan; un clic en una pieza la suma o la saca).

Por debajo, como "Propagar operación a piezas" de SW: en cada pieza afectada, dentro de su
Cuerpo, una COPIA CONGELADA del croquis del ensamblaje (SubShapeBinder suelto, posición = inversa
de la del componente) y un Taladro (PartDesign::Hole) o Vaciado (PartDesign::Pocket) nativo con
ese perfil. El agujero queda en la pieza (planos, DXF). Congelada (#38, decisión del usuario
11/11): con el vínculo al croquis, ensamblaje -> pieza -> ensamblaje era un círculo que FreeCAD no
admite ("The graph must be a DAG", el ensamblaje quedaba modificado al abrirlo). FreeWorks vuelve
a copiar al editar la operación o su croquis desde el ensamblaje; si el croquis cambió por otro
camino, la operación de la pieza pasa de "Taladro1 -> Conjunto" a "Taladro1 ->? Conjunto" (como
la flecha de referencia externa de SW) y se avisa. El croquis del ensamblaje queda suelto
(apoyado en la cara de una pieza que se agujerea sería un ciclo). Si la pieza se mueve en el
ensamblaje, un observador pone al día la posición del binder (decisión del usuario, 2026-10-27).
Los datos de cada operación van en un App::VarSet del ensamblaje (SWUI_AsmFeature).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.fork import safe_ops  # noqa: E402  (#60: cerrar pasos con end_step)

HOLE_CMD = "SWUI_AssemblyHole"
CUT_CMD = "SWUI_AssemblyCut"
KIND = "SWUI_AsmFeature"  # "hole" / "cut" en el VarSet (nombre estable)
SKETCH = "SWUI_Sketch"
ENTRIES = "SWUI_Entries"  # "componente|documento|binder|operación" por pieza
BINDER_MARK = "SWUI_AsmBinder"  # en el binder dentro de la pieza: "<documento del ensamblaje>"
# en la copia dentro de la pieza (#38; nombres estables): de dónde viene, cuándo se copió y la huella
# del croquis copiado (para saber si quedó desactualizada)
ORIGIN = "SWUI_AsmOrigin"
COPIED = "SWUI_AsmCopied"
PRINT = "SWUI_AsmPrint"
ARROW, STALE = " -> ", " ->? "
TITLES = {"hole": "TaladroEnsamblaje", "cut": "CorteEnsamblaje"}
LABELS = {"hole": "Asistente para taladro (ensamblaje)", "cut": "Extruir corte (ensamblaje)"}
MARKER_RADIUS = 0.5  # círculo chico en cada punto de posición (el taladro toma círculos del binder)

_state = {"pending": None, "panel": None}
_installed = False


# --- Cuentas sin FreeCAD (probables en el test) ---------------------------------


def entry_text(link_name, doc_name, binder_name, feature_name):
    return "|".join((link_name, doc_name, binder_name, feature_name))


def parse_entry(text):
    parts = (text or "").split("|")
    return tuple(parts) if len(parts) == 4 else None


def unique_parts(links):
    """Una sola vez cada pieza (dos instancias del mismo archivo = una sola operación en la pieza)."""
    seen, out, repeated = set(), [], []
    for link in links:
        key = id(link)
        target = part_of(link)
        key = (target.Document.Name, target.Name) if target is not None else key
        if key in seen:
            repeated.append(link)
            continue
        seen.add(key)
        out.append(link)
    return out, repeated


def next_title(used, kind):
    n = 1
    while "%s%d" % (TITLES[kind], n) in used:
        n += 1
    return "%s%d" % (TITLES[kind], n)


# --- FreeCAD -------------------------------------------------------------------


def part_of(link):
    """
    La pieza (Cuerpo) del componente. Con otra configuración, LinkedObject es la copia que
    FreeCAD guarda dentro del ensamblaje: el taladro tiene que ir a la pieza de verdad (en la copia
    se perdía al volver a copiarla).
    """
    src = getattr(link, "LinkCopyOnChangeSource", None)
    if src is not None and getattr(link, "LinkCopyOnChange", "Disabled") != "Disabled":
        return src
    return getattr(link, "LinkedObject", None)


def _suppressed(link):
    try:
        from swui.fork import config_asm

        return config_asm.is_suppressed(link)
    except Exception:
        return False


def _components(asm):
    """Componentes de pieza del ensamblaje, sin los suprimidos (como SW: no se agujerean)."""
    return [o for o in asm.Group if o.TypeId == "App::Link" and not getattr(o, "ElementCount", 0)
            and getattr(part_of(o), "TypeId", "") == "PartDesign::Body" and not _suppressed(o)]


def sketch_normal(sk):
    return sk.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))


def centers(sk):
    """Centros globales: puntos y círculos del croquis (sin los de construcción)."""
    out = []
    for i, g in enumerate(sk.Geometry):
        try:
            if sk.getConstruction(i):
                continue
        except Exception:
            pass
        name = type(g).__name__
        if name == "Point":
            p = FreeCAD.Vector(g.X, g.Y, g.Z)
        elif name in ("Circle", "ArcOfCircle"):
            p = g.Center
        else:
            continue
        out.append(sk.Placement.multVec(p))
    return out


def hit_by_holes(asm, sk):
    """
    Componentes que atraviesan los ejes de los agujeros (hacia adentro de la cara). No se suma
    solo el que está metido en el eje (perno, pasador): el agujero pasa a cada pieza, y en uno de
    esos se comería el perno entero y sus relaciones quedarían sin caras (en SW el taladro queda en
    el ensamblaje y no lo rompe). Se puede sumar a mano con un clic.
    """
    import Part

    n = sketch_normal(sk)
    points = _unique(centers(sk))
    out = []
    for comp in _components(asm):
        try:
            shape = comp.Shape
            hits = [c for c in points
                    if Part.LineSegment(c + n * 0.01, c - n * 1e4).toShape().distToShape(shape)[0] < 1e-6]
            if hits and not all(_shaft_on_axis(shape, c, n) for c in hits):
                out.append(comp)
        except Exception:
            pass
    return out


def _shaft_on_axis(shape, center, n, tol=1e-3):
    """¿La pieza tiene un cilindro EXTERIOR (no un agujero) sobre el eje que pasa por center?"""
    for face in shape.Faces:
        surf = face.Surface
        if type(surf).__name__ != "Cylinder":
            continue
        axis = surf.Axis
        if axis.cross(n).Length > tol:
            continue
        gap = center - surf.Center
        if (gap - axis * gap.dot(axis)).Length > tol:
            continue
        u0, u1, v0, v1 = face.ParameterRange
        u, v = (u0 + u1) / 2, (v0 + v1) / 2
        p = face.valueAt(u, v)
        radial = p - surf.Center
        radial = radial - axis * radial.dot(axis)
        if face.normalAt(u, v).dot(radial) > 0:  # la normal sale del eje: el sólido está adentro
            return True
    return False


def _unique(points):
    out = []
    for p in points:
        if all((p - q).Length > 1e-6 for q in out):
            out.append(p)
    return out


CUT_DEPTH = 10.0  # mm: el corte de ensamblaje arranca en "Hasta profundidad especificada" (SW)


def hit_by_cut(asm, sk, both=False, depth=1e4):
    """Componentes que toca el perfil extruido hacia adentro `depth` mm (o a los dos lados)."""
    import Part

    try:
        faces = Part.makeFace(sk.Shape.Wires, "Part::FaceMakerBullseye")
    except Exception:
        return []
    n = sketch_normal(sk)
    tool = faces.extrude(n * -depth)
    if both:
        tool = tool.fuse(faces.extrude(n * 1e4))
    out = []
    for comp in _components(asm):
        try:
            if tool.common(comp.Shape).Volume > 1e-6:
                out.append(comp)
        except Exception:
            pass
    return out


def add_markers(sk):
    """Un círculo chico atado a cada punto de posición (el taladro toma los círculos del binder)."""
    import Part
    import Sketcher

    points = []
    for i, g in enumerate(sk.Geometry):
        if type(g).__name__ == "Point" and not sk.getConstruction(i):
            points.append((i, FreeCAD.Vector(g.X, g.Y, g.Z)))
    circles = [g.Center for g in sk.Geometry if type(g).__name__ == "Circle"]
    added = 0
    for i, p in points:
        if any((p - c).Length < 1e-6 for c in circles):
            continue
        k = sk.addGeometry(Part.Circle(p, FreeCAD.Vector(0, 0, 1), MARKER_RADIUS), False)
        sk.addConstraint(Sketcher.Constraint("Coincident", k, 3, i, 1))
        sk.addConstraint(Sketcher.Constraint("Radius", k, MARKER_RADIUS))
        added += 1
    if added:
        sk.recompute()
    return added


def make_sketch(asm, comp, sub):
    """Croquis suelto del ensamblaje, ubicado sobre la cara elegida (no queda apoyado: sería un ciclo)."""
    sk = asm.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(comp, sub)]
    sk.MapMode = "FlatFace"
    sk.recompute()
    plc = sk.Placement
    sk.MapMode = "Deactivated"
    sk.AttachmentSupport = None
    sk.Placement = plc
    return sk


def begin_operation(label):
    """
    Un solo paso de deshacer para toda la operación, en el ensamblaje y en todas las piezas (#37):
    el paso de la APLICACIÓN (FreeCAD.setActiveTransaction), no uno por documento. Con pasos por
    documento, Ctrl+Z en el ensamblaje sacaba la operación y dejaba el taladro en las piezas
    (probado con la ventana el 11/11: el paso de la aplicación se deshace entero en todos los
    documentos; los pasos sueltos, solo en el activo). Ojo: salir de edición CIERRA este paso
    (también probado): lo que va en el ensamblaje se anota antes (`_Scope._record`).
    """
    if not FreeCAD.getActiveTransaction():
        FreeCAD.setActiveTransaction(label)


def sketch_print(sk):
    """Huella del croquis: su geometría y si cada elemento es constructivo (sin su ubicación, que la
    sigue el observador de siempre). Igual huella = misma copia."""
    import hashlib

    items = []
    for i, g in enumerate(sk.Geometry):
        try:
            constr = sk.getConstruction(i)
        except Exception:
            constr = False
        items.append("%s%s" % ("c" if constr else "", g))
    return hashlib.sha1("|".join(items).encode("utf-8")).hexdigest()[:16]


def feature_label(title, asm_label, stale=False):
    """'Taladro1 -> Conjunto' (o '->?' si la copia quedó desactualizada), como SW."""
    return "%s%s%s" % (title, STALE if stale else ARROW, asm_label)


def _str_prop(obj, name, value, doc):
    if name not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", name, "SW", doc)
        obj.setEditorMode(name, 1)  # se ve en propiedades, no se edita
    if getattr(obj, name) != value:
        setattr(obj, name, value)


def copy_sketch(binder, sk, title):
    """
    Copia CONGELADA de `sk` (croquis del ensamblaje) en `binder` (dentro de la pieza): se enlaza un
    momento para tomar la forma y se suelta (BindMode "Detached"), así la pieza no apunta al
    ensamblaje (#38). Guarda de dónde viene, cuándo y la huella.
    """
    import datetime

    binder.BindMode = "Synchronized"
    binder.Support = [(sk, ("",))]
    binder.recompute()
    binder.BindMode = "Detached"
    if binder.Support:  # por si FreeCAD no lo suelta solo al pasar a "Detached"
        binder.Support = []
    asm_doc = sk.Document
    archivo = (asm_doc.FileName.replace("\\", "/").split("/")[-1] if asm_doc.FileName else asm_doc.Label)
    _str_prop(binder, ORIGIN, "%s en %s" % (title, archivo), "De qué operación de ensamblaje viene esta copia")
    _str_prop(binder, COPIED, datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "Cuándo se copió del ensamblaje")
    _str_prop(binder, PRINT, sketch_print(sk), "Huella del croquis copiado (FreeWorks)")


def refresh_copies(v, entries=None):
    """Vuelve a copiar el croquis de la operación `v` en las piezas cuya copia no coincide, y les
    pone el nombre sin '?'. Devuelve los documentos tocados."""
    sk = getattr(v, SKETCH, None)
    if sk is None:
        return []
    want = sketch_print(sk)
    touched = []
    for link, binder, feat in (entries if entries is not None else entries_of(v)):
        if getattr(binder, PRINT, None) != want or binder.Support:
            copy_sketch(binder, sk, _title(v))
            touched.append(binder.Document)
        label = feature_label(_title(v), sk.Document.Label)
        if feat.Label != label:
            feat.Label = label
            if binder.Document not in touched:
                touched.append(binder.Document)
    _mark_operation(v, False)
    return touched


def stale_entries(v):
    """[(componente, binder, operación)] cuya copia ya no coincide con el croquis del ensamblaje."""
    sk = getattr(v, SKETCH, None)
    if sk is None:
        return []
    want = sketch_print(sk)
    return [e for e in entries_of(v) if not e[1].Support and getattr(e[1], PRINT, None) not in (None, want)]


def _title(v):
    return v.Label.replace(" (desactualizada)", "")


def _mark_operation(v, stale):
    """En el árbol del ensamblaje: la operación con ' (desactualizada)' si alguna copia no coincide."""
    base = v.Label.replace(" (desactualizada)", "")
    want = base + (" (desactualizada)" if stale else "")
    if v.Label != want:
        v.Label = want


def check_copies(asm_doc, tell=True):
    """Compara la huella del croquis de cada operación con la de sus copias: marca '->?' en las
    piezas desactualizadas y en la operación, y avisa en la barra de estado (#38)."""
    stale_ops = []
    for v in operations(asm_doc):
        stale = stale_entries(v)
        title = _title(v)
        for _l, _b, feat in entries_of(v):
            if ARROW.strip() not in feat.Label:
                continue  # archivo anterior ("Taladro1 (Conjunto)"): se pasa al editar o al guardar
            want = feature_label(title, asm_doc.Label, any(feat is e[2] for e in stale))
            if feat.Label != want:
                feat.Label = want
        if stale or v.Label != title:
            _mark_operation(v, bool(stale))
        if stale:
            stale_ops.append((title, [e[0].Label for e in stale]))
    if stale_ops and tell:
        text = "; ".join("%s está desactualizado en %s" % (t, ", ".join(ps)) for t, ps in stale_ops)
        text += ": edítelo desde el ensamblaje (clic derecho > Editar operación) para actualizar."
        FreeCAD.Console.PrintWarning("[SWUI] %s\n" % text)
        try:
            FreeCADGui.getMainWindow().statusBar().showMessage(text, 15000)
        except Exception:
            pass
    return stale_ops


def add_to_part(link, sk, kind, title):
    """Binder del croquis + taladro / vaciado nativo en el Cuerpo de la pieza."""
    body = part_of(link)
    pdoc = body.Document
    if not pdoc.HasPendingTransaction and not FreeCAD.getActiveTransaction():
        pdoc.openTransaction(LABELS[kind])
    binder = body.newObject("PartDesign::SubShapeBinder", "CroquisEnsamblaje")
    # No relativo y con la posición puesta a mano: el modo relativo de FreeCAD recalcula la
    # posición según el contexto y en un ensamblaje llegó a aplicarla dos veces (probado en 1.1.4)
    binder.Relative = False
    binder.Placement = binder_placement(link, sk)
    binder.addProperty("App::PropertyString", BINDER_MARK, "SW", "Operación de ensamblaje de LikeSolidWorks UI")
    setattr(binder, BINDER_MARK, sk.Document.Name)
    copy_sketch(binder, sk, title)
    binder.Label = "Croquis de %s (%s)" % (title, sk.Document.Label)
    binder.Visibility = False
    if kind == "hole":
        feat = body.newObject("PartDesign::Hole", "Taladro")
        feat.Profile = binder
        from swui.fork import hole_panel

        hole_panel._defaults(feat)  # como el taladro de la fase 2: ISO, M6, agujero normal
        feat.DepthType = "ThroughAll"
    else:
        feat = body.newObject("PartDesign::Pocket", "Corte")
        feat.Profile = binder
        feat.Type = "Length"  # como SW: arranca en "Hasta profundidad especificada", 10 mm
        feat.Length = CUT_DEPTH
    label = feature_label(title, sk.Document.Label)
    feat.Label = label
    if FreeCAD.GuiUp:  # después del nombre SW que pone el original (naming.py, también con QTimer 0)
        QtCore.QTimer.singleShot(0, lambda d=pdoc.Name, n=feat.Name: _relabel(d, n, label))
    body.Tip = feat
    return binder, feat


def _relabel(doc_name, name, label):
    try:
        obj = FreeCAD.getDocument(doc_name).getObject(name)
        if obj is not None:
            obj.Label = label
    except Exception:
        pass


def binder_placement(link, sk):
    """Croquis del ensamblaje llevado a las coordenadas de la pieza."""
    return link.Placement.inverse().multiply(sk.Placement)


def remove_from_part(binder, feat):
    for obj in (feat, binder):
        try:
            body = obj.getParentGeoFeatureGroup()
            if body is not None:
                body.removeObject(obj)
            obj.Document.removeObject(obj.Name)
        except Exception:
            pass


def _entry_doc(asm_doc, entry):
    """
    El documento de la pieza de una entrada guardada. Sale de su COMPONENTE (estable, vive en el
    ensamblaje), no del nombre interno del documento, que cambia entre sesiones: dos "Placa.FCStd"
    de carpetas distintas abiertos son "Placa" y "Placa1", y el vínculo se perdía o tocaba la otra
    (Issue #5). Lo guardado (la ruta del archivo; en archivos viejos, el nombre interno) queda
    solo de respaldo, si el componente ya no está.
    """
    link = asm_doc.getObject(entry[0])
    body = part_of(link) if link is not None else None
    if body is not None:
        return body.Document
    from swui.fork import safe_ops

    key = entry[1]
    doc = safe_ops.find_doc(key)
    if doc is None and not key.startswith(safe_ops.UNSAVED) and "/" not in key and "\\" not in key:
        doc = FreeCAD.listDocuments().get(key)  # archivo de antes del 11/11: nombre interno
    return doc


def entries_of(v):
    """[(componente, binder, operación)] de una operación guardada."""
    out = []
    asm_doc = v.Document
    for text in getattr(v, ENTRIES, []) or []:
        e = parse_entry(text)
        if e is None:
            continue
        link_name, _doc, binder_name, feat_name = e
        pdoc = _entry_doc(asm_doc, e)
        if pdoc is None:
            continue
        link, binder, feat = asm_doc.getObject(link_name), pdoc.getObject(binder_name), pdoc.getObject(feat_name)
        if link is not None and binder is not None and feat is not None:
            out.append((link, binder, feat))
    return out


def operations(doc):
    """Las operaciones de ensamblaje del documento (los VarSet con KIND). Filtra primero por tipo
    en FreeCAD: se llama en cada cambio de ubicación de un componente y recorrer todos los objetos
    en Python se notaba en ensamblajes grandes (Issue #15: 1,2 ms por cambio con 500 componentes)."""
    return [o for o in doc.findObjects("App::VarSet") if hasattr(o, KIND)]


def record(asm, kind, sk, entries, data=None, title=None):
    v = data
    if v is None:
        v = asm.newObject("App::VarSet", "VarSet")
        v.Label = title or next_title({o.Label for o in asm.Document.Objects}, kind)
        v.addProperty("App::PropertyString", KIND, "SW", "Operación de ensamblaje de LikeSolidWorks UI")
        v.addProperty("App::PropertyLinkHidden", SKETCH, "SW", "Croquis del ensamblaje")
        v.addProperty("App::PropertyStringList", ENTRIES, "SW", "componente|documento|binder|operación")
        setattr(v, KIND, kind)
        setattr(v, SKETCH, sk)
    from swui.fork import safe_ops

    # el documento, por su archivo (respaldo; el que manda es el componente: _entry_doc, #5)
    setattr(v, ENTRIES, [entry_text(l.Name, safe_ops.doc_key(f.Document), b.Name, f.Name) for l, b, f in entries])
    return v


def operation_of(obj):
    """VarSet de la operación (desde el VarSet, el croquis, o el binder/operación en una pieza)."""
    if obj is None:
        return None
    if hasattr(obj, KIND):
        return obj
    for doc in FreeCAD.listDocuments().values():
        for v in operations(doc):
            if getattr(v, SKETCH, None) is obj:
                return v
            for text in getattr(v, ENTRIES, []) or []:
                e = parse_entry(text)
                if e and obj.Name in (e[2], e[3]) and _entry_doc(doc, e) is obj.Document:
                    return v
    return None


def _recompute_later(docs):
    names = sorted({d.Name for d in docs})

    def run():
        for n in names:
            try:
                FreeCAD.getDocument(n).recompute()
            except Exception:
                pass
    QtCore.QTimer.singleShot(0, run)


# --- Observador: piezas que se mueven, croquis editado, pieza abierta sola -------------


class _Observer:
    def slotChangedObject(self, obj, prop):
        try:
            if prop != "Placement" or obj.TypeId not in ("App::Link", "Sketcher::SketchObject")                     or obj.Document.Restoring:
                return
            touched = []
            for v in operations(obj.Document):
                sk = getattr(v, SKETCH, None)
                for link, binder, _feat in entries_of(v):
                    if link is obj or sk is obj:
                        want = binder_placement(link, sk)
                        if not binder.Placement.isSame(want, 1e-9):
                            binder.Placement = want
                            touched.append(binder.Document)
            if touched:
                _recompute_later(touched + [obj.Document])
        except Exception:
            pass

    def slotCreatedDocument(self, doc):
        QtCore.QTimer.singleShot(0, lambda n=doc.Name: _tell_if_from_assembly(n))

    def slotFinishSaveDocument(self, doc, _filename):
        if any(o.TypeId == "Assembly::AssemblyObject" for o in doc.Objects):
            QtCore.QTimer.singleShot(0, lambda n=doc.Name: _after_save(n))

    def slotRecomputedDocument(self, doc):
        """Con el ensamblaje abierto, ¿alguna copia quedó desactualizada? (p. ej. una ecuación que
        cambió una cota del croquis): '->?' y aviso (#38). Nunca al abrir ni al deshacer."""
        from swui.fork import safe_ops

        if safe_ops.doc_busy(doc) or not operations(doc):
            return
        name = doc.Name
        QtCore.QTimer.singleShot(0, lambda: _check_later(name))


_told = set()  # operaciones ya avisadas como desactualizadas (no repetir en cada recálculo)


def _check_later(doc_name):
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        return
    try:
        stale = check_copies(doc, tell=False)
        new = [(t, ps) for t, ps in stale if (doc_name, t) not in _told]
        for t, _ps in stale:
            _told.add((doc_name, t))
        for t in [t for (d, t) in list(_told) if d == doc_name and t not in [x for x, _ in stale]]:
            _told.discard((doc_name, t))
        if new:
            check_copies(doc, tell=True)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Copias del ensamblaje:\n%s\n" % traceback.format_exc())


def _after_save(doc_name):
    """Archivos anteriores al 11/11: las copias todavía enlazadas al croquis (el círculo de #38) se
    pasan a congeladas al guardar el ensamblaje; save_modified_parts guarda las piezas."""
    try:
        doc = FreeCAD.getDocument(doc_name)
        for v in operations(doc):
            if any(e[1].Support for e in entries_of(v)):
                refresh_copies(v)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Copias del ensamblaje:\n%s\n" % traceback.format_exc())
    save_modified_parts(doc_name)


def modified_parts(asm_doc):
    """Documentos que usa el ensamblaje (piezas, simétricas...) con cambios sin guardar y ya con archivo."""
    out = []
    # de los componentes (vínculos): getDependentDocuments falla con el ciclo pieza <-> croquis
    # del ensamblaje ("The graph must be a DAG")
    for o in asm_doc.Objects:
        if o.TypeId != "App::Link":
            continue
        try:
            d = (part_of(o) or o.getLinkedObject(True)).Document
        except Exception:
            continue
        if d is asm_doc or d in out or not getattr(d, "FileName", ""):
            continue
        try:
            if FreeCADGui.getDocument(d.Name).Modified:
                out.append(d)
        except Exception:
            pass
    return out


def save_modified_parts(doc_name):
    """
    Como SW: guardar el ensamblaje guarda también las piezas que cambiaron (un taladro o corte de
    ensamblaje, la versión simétrica...). FreeCAD 1.1.4 no las guardaba con Ctrl+S y "Guardar todo"
    mostraba un error rojo de "dependencias cíclicas" (las piezas usan el croquis del ensamblaje):
    se guarda cada una por su lado, que no pasa por esa revisión. Visto con el mouse, 2026-10-31.
    """
    try:
        asm_doc = FreeCAD.getDocument(doc_name)
    except Exception:
        return []
    saved = []
    for d in modified_parts(asm_doc):
        try:
            d.save()
            saved.append(d.Label)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] No se pudo guardar %s:\n%s\n" % (d.Label, traceback.format_exc()))
    if saved:
        # pieza <-> ensamblaje se enlazan en ciclo: al guardar uno, FreeCAD marca al otro como
        # cambiado (sello del vínculo externo, no un cambio de verdad) y el título quedaba con "*"
        for name in [asm_doc.Name] + [d.Name for d in FreeCAD.listDocuments().values() if d.Label in saved]:
            try:
                FreeCADGui.getDocument(name).Modified = False
            except Exception:
                pass
        text = "También se guardaron las piezas: %s" % ", ".join(saved)
        FreeCAD.Console.PrintMessage("[SWUI fork] %s\n" % text)
        try:
            FreeCADGui.getMainWindow().statusBar().showMessage(text, 10000)
        except Exception:
            pass
    return saved


def _front(doc):
    """Poner al frente la ventana 3D del documento (pestaña de la vista)."""
    FreeCADGui.setActiveDocument(doc.Name)
    mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in (mdi.subWindowList() if mdi is not None else []):
        title = sub.windowTitle().replace("[*]", "").strip()
        if title == doc.Label or title.startswith(doc.Label + " :"):
            mdi.setActiveSubWindow(sub)
            return


def edit_redirect(obj):
    """
    Doble clic en el taladro o corte de ensamblaje DENTRO de la pieza: en lugar del diálogo de
    FreeCAD (que lo editaba suelto, visto con el mouse 2026-10-31), como SW con una operación
    propagada: se edita desde el ensamblaje. Si está abierto, se abre su panel; si no, se avisa.
    """
    profile = getattr(obj, "Profile", None)
    binder = profile[0] if isinstance(profile, (list, tuple)) and profile else profile
    if binder is None or not hasattr(binder, BINDER_MARK):
        return None
    v = operation_of(obj)
    doc_name, label = obj.Document.Name, obj.Label

    def act():
        try:
            FreeCADGui.getDocument(doc_name).resetEdit()
        except Exception:
            pass
        asm_doc = v.Document if v is not None else None
        if asm_doc is not None and _shown(asm_doc):
            try:
                _front(asm_doc)
                open_panel(v)
                return
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Editar desde la pieza:\n%s\n" % traceback.format_exc())
        name = asm_doc.Label if asm_doc is not None else getattr(binder, BINDER_MARK)
        FreeCAD.Console.PrintTranslatedUserWarning(
            label, "%s se hizo desde el ensamblaje %s: se edita desde ahí (abra el ensamblaje, clic "
                   "derecho > Editar operación).\n" % (label, name))

    return act


def _shown(doc):
    """¿El usuario tiene el documento abierto en una ventana? (no solo cargado como dependencia)"""
    try:
        return bool(FreeCADGui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor"))
    except Exception:
        return False


def _tell_if_from_assembly(doc_name):
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        return
    binders = [o for o in doc.Objects if hasattr(o, BINDER_MARK)]
    if binders:
        # el ensamblaje sale de lo que el binder enlaza (FreeCAD lo carga oculto al abrir la
        # pieza); la marca guarda el nombre interno de entonces ("Unnamed" si no estaba guardado)
        asms = []
        for o in binders:
            for obj, _subs in (getattr(o, "Support", None) or []):  # archivos anteriores (enlazados)
                d = getattr(obj, "Document", None)
                if d is not None and d not in asms:
                    asms.append(d)
            mark = getattr(o, BINDER_MARK, "")
            d = FreeCAD.listDocuments().get(mark)
            if d is not None and d not in asms and operations(d):
                asms.append(d)
        origins = sorted({getattr(o, ORIGIN, "").split(" en ")[-1] for o in binders if getattr(o, ORIGIN, "")})
        names = [d.Label for d in asms] or origins or sorted({getattr(o, BINDER_MARK) for o in binders})
        text = ("%s tiene agujeros o cortes hechos desde el ensamblaje %s: se editan desde ahí "
                "(clic derecho > Editar operación en el ensamblaje).\n" % (doc.Label, ", ".join(names)))
        if any(_shown(d) for d in asms):
            FreeCAD.Console.PrintMessage("[SWUI] " + text)  # abierta junto con su ensamblaje
        else:
            # pieza abierta sola: aviso a la vista (cartelito de FreeCAD que se va solo; la vista
            # de informe está oculta en el fork). Como la flecha "->" de referencia externa de SW.
            FreeCAD.Console.PrintTranslatedUserWarning(doc.Label, text)


class _GuiObserver:
    """Al salir del croquis: seguir con el panel (operación nueva) o poner al día las piezas."""

    def slotResetEdit(self, vp):
        try:
            obj = vp.Object
        except Exception:
            return
        pending = _state["pending"]
        if pending is not None and obj is pending["sketch"]:
            QtCore.QTimer.singleShot(0, _after_sketch)
            return
        v = operation_of(obj) if obj.TypeId == "Sketcher::SketchObject" else None
        if v is not None:
            QtCore.QTimer.singleShot(0, lambda: _sketch_edited(v))


def _sketch_edited(v):
    """Salir del croquis de la operación en el ensamblaje = editarla desde el ensamblaje: las copias
    de las piezas se ponen al día (#38), en un paso de deshacer propio."""
    try:
        sk = getattr(v, SKETCH)
        if getattr(v, KIND) == "hole" and add_markers(sk):
            sk.Document.recompute()
        if stale_entries(v) or any(e[1].Support for e in entries_of(v)):
            mine = not FreeCAD.getActiveTransaction()  # cerrar solo el paso que se abre acá
            begin_operation("Actualizar " + _title(v))
            try:
                refresh_copies(v)
            finally:
                if mine:
                    FreeCAD.closeActiveTransaction()
        _recompute_later([b.Document for _l, b, _f in entries_of(v)] + [v.Document])
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Croquis de ensamblaje:\n%s\n" % traceback.format_exc())


# --- Flujo: cara -> croquis -> panel ----------------------------------------------


def start(kind):
    from swui.fork import mates_sw

    asm = mates_sw.ensure_active()
    if asm is None:
        FreeCAD.Console.PrintWarning("[SWUI] %s: abra o active un ensamblaje primero.\n" % LABELS[kind])
        return
    face = _picked_face(asm)
    if face is not None:
        _open_sketch(asm, kind, *face)
        return
    try:
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass
    _state["panel"] = _FacePanel(asm, kind)
    FreeCADGui.Control.showDialog(_state["panel"])


def _picked_face(asm):
    from swui.fork import component_patterns as cp

    for obj, sub, kind in cp.pick_from_selection(asm):
        if kind == "plane" and obj.TypeId == "App::Link":
            return obj, sub
    return None


class _FacePanel:
    """'Elegí la cara plana' (como el primer paso del taladro de SW en un ensamblaje)."""

    def __init__(self, asm, kind):
        from swui.fork import mates_sw

        self.asm, self.kind = asm, kind
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(LABELS[kind])
        box = QtWidgets.QVBoxLayout(self.form)
        text = QtWidgets.QLabel("Elija la cara plana donde empieza el %s. Se abre un croquis ahí: %s"
                                % ("taladro" if kind == "hole" else "corte",
                                   "marque los centros con puntos." if kind == "hole" else "dibuje el perfil."))
        text.setWordWrap(True)
        box.addWidget(text)
        box.addStretch(1)
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._check)
        self.observer = mates_sw._SelObserver(self)
        try:
            FreeCADGui.Selection.addObserver(self.observer, FreeCADGui.Selection.ResolveMode.NoResolve)
        except Exception:
            FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()

    def schedule(self):
        self.timer.start(0)

    def _check(self):
        face = _picked_face(self.asm)
        if face is None:
            return
        self._close()
        FreeCADGui.Control.closeDialog()
        QtCore.QTimer.singleShot(0, lambda: _open_sketch(self.asm, self.kind, *face))

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Cancel

    def reject(self):
        self._close()
        FreeCADGui.Control.closeDialog()
        return True

    def _close(self):
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        _state["panel"] = None


def _open_sketch(asm, kind, comp, sub):
    try:
        FreeCADGui.Selection.clearSelection()
        doc = asm.Document
        doc.openTransaction(LABELS[kind])
        sk = make_sketch(asm, comp, sub)
        safe_ops.end_step(doc)
        _state["pending"] = {"kind": kind, "asm": asm, "sketch": sk}
        FreeCADGui.ActiveDocument.setEdit(sk)
        if kind == "hole":
            from swui.fork import hole_panel

            QtCore.QTimer.singleShot(hole_panel.POINT_TOOL_DELAY_MS, lambda: hole_panel._point_tool(sk))
    except Exception:
        _state["pending"] = None
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABELS[kind], traceback.format_exc()))


def _after_sketch():
    pending, _state["pending"] = _state["pending"], None
    if pending is None:
        return
    asm, kind, sk = pending["asm"], pending["kind"], pending["sketch"]
    try:
        if kind == "hole":
            add_markers(sk)
        empty = not centers(sk) if kind == "hole" else not sk.Shape.Wires
        if empty:
            asm.Document.removeObject(sk.Name)
            FreeCAD.Console.PrintWarning("[SWUI] %s: el croquis quedó vacío, no se hizo nada.\n" % LABELS[kind])
            return
        FreeCADGui.ActiveDocument.setEdit(asm)  # volver a editar el ensamblaje
        FreeCADGui.Selection.clearSelection()  # si no, el panel de relaciones del original toma el croquis
        open_panel_new(asm, kind, sk)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABELS[kind], traceback.format_exc()))


def open_panel_new(asm, kind, sk):
    hits = hit_by_holes(asm, sk) if kind == "hole" else hit_by_cut(asm, sk, depth=CUT_DEPTH)
    parts, repeated = unique_parts(hits)
    title = next_title({o.Label for o in asm.Document.Objects}, kind)
    begin_operation(LABELS[kind])
    try:
        entries = []
        for link in parts:
            binder, feat = add_to_part(link, sk, kind, title)
            entries.append((link, binder, feat))
        if kind == "hole" and not entries:
            FreeCAD.Console.PrintWarning("[SWUI] El taladro no atraviesa ninguna pieza: elija las piezas en el panel.\n")
        _show(asm, kind, sk, entries, None, title, repeated)
    except Exception:
        FreeCAD.closeActiveTransaction(True)  # nada a medias en las piezas (revisión del 11/11)
        raise


def open_panel(v):
    asm = next((p for p in v.InList if p.TypeId == "Assembly::AssemblyObject"), None)
    if asm is None:
        return None
    kind, entries = getattr(v, KIND), entries_of(v)
    if not (kind == "hole" and entries):
        # el panel del taladro abre el paso él mismo, después de volver a la vista normal (#36)
        begin_operation("Editar " + _title(v))
    try:
        return _show(asm, kind, getattr(v, SKETCH), entries, v, _title(v), [])  # sin "(desactualizada)"
    except Exception:
        FreeCAD.closeActiveTransaction(True)
        raise


def _show(asm, kind, sk, entries, data, title, repeated):
    try:
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass
    if kind == "hole" and entries:
        panel = make_hole_panel()(entries, asm, sk, data, title, repeated)
    else:
        panel = CutPanel(entries, asm, sk, data, title, repeated, kind)
    _state["panel"] = panel
    FreeCADGui.Control.showDialog(panel)
    return panel


# --- Lo común de los dos paneles -----------------------------------------------------


class _Scope:
    """'Piezas afectadas': lista + clic en una pieza la suma o la saca; guarda la operación."""

    def _scope_init(self, entries, asm, sk, data, title, repeated, kind):
        self.entries = list(entries)
        self.asm, self.sketch, self.data, self.title, self.op_kind = asm, sk, data, title, kind
        self.repeated = repeated
        self.part_docs = {b.Document.Name: b.Document for _l, b, _f in entries}

    def _scope_group(self):
        from swui.fork import dress_up_panel as dp

        g = QtWidgets.QGroupBox("Piezas afectadas")
        gl = QtWidgets.QVBoxLayout(g)
        self.parts_list = dp.pick_list(self._remove_current_part, self._clear_parts, 44)
        self.parts_list.setMaximumHeight(70)
        gl.addWidget(self.parts_list)
        hint = QtWidgets.QLabel("Un clic en una pieza la suma o la saca. Cada agujero queda dentro de su pieza "
                                "(sale en sus planos y en el DXF) y sigue al croquis del ensamblaje.")
        hint.setWordWrap(True)
        gl.addWidget(hint)
        if self.repeated:
            warn = QtWidgets.QLabel("Pieza repetida en el ensamblaje: %s. La operación queda en la pieza "
                                    "y sigue a la primera instancia." % ", ".join(l.Label for l in self.repeated))
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #b05000;")
            gl.addWidget(warn)
        self._fill_parts()
        return g

    def _fill_parts(self):
        self.parts_list.clear()
        for link, _b, _f in self.entries:
            self.parts_list.addItem(link.Label)

    def _toggle_part(self, link):
        for e in self.entries:
            if e[0] is link:
                self._drop(e)
                return True
        if any(part_of(e[0]) is part_of(link) for e in self.entries):
            return False  # misma pieza, otra instancia
        binder, feat = add_to_part(link, self.sketch, self.op_kind, self.title)
        self.part_docs[binder.Document.Name] = binder.Document
        self.entries.append((link, binder, feat))
        self._copy_to_others()
        binder.Document.recompute()
        return True

    def _drop(self, entry):
        self.entries.remove(entry)
        remove_from_part(entry[1], entry[2])
        _recompute_later([d for d in self.part_docs.values()])

    def _remove_current_part(self):
        row = self.parts_list.currentRow()
        if 0 <= row < len(self.entries):
            self._drop(self.entries[row])
            self._parts_changed()

    def _clear_parts(self):
        for e in list(self.entries):
            self._drop(e)
        self._parts_changed()

    def _parts_changed(self):
        self._fill_parts()

    def _copy_to_others(self):
        pass

    def _link_of(self, obj):
        """Componente del ensamblaje al que pertenece algo elegido (resuelto a la pieza)."""
        from swui.fork import feature_tree as ft

        body = obj if obj.TypeId == "PartDesign::Body" else ft.body_of(obj)
        for link in _components(self.asm):
            if part_of(link) is body or link.LinkedObject is body:
                return link
        return None

    def _record(self):
        """Anota la operación en el ensamblaje, dentro del paso de la operación (antes de que una
        pieza salga de edición: eso cierra el paso)."""
        doc = self.asm.Document
        if not self.entries:
            if self.data is not None:
                doc.removeObject(self.data.Name)
            doc.removeObject(self.sketch.Name)
        else:
            self.data = record(self.asm, self.op_kind, self.sketch, self.entries, self.data, self.title)
            refresh_copies(self.data, self.entries)  # editar desde el ensamblaje vuelve a copiar (#38)

    def _finish(self):
        """Cierra el paso de la operación (si una pieza al salir de edición ya lo cerró, no queda
        nada abierto) y vuelve al ensamblaje."""
        FreeCAD.closeActiveTransaction()
        doc = self.asm.Document
        for d in list(self.part_docs.values()) + [doc]:
            if d.HasPendingTransaction:
                safe_ops.end_step(d)
        _recompute_later(list(self.part_docs.values()) + [doc])
        self._back()

    def _save(self):
        self._record()
        self._finish()

    def _back(self):
        from swui.fork import component_patterns

        QtCore.QTimer.singleShot(0, lambda: component_patterns._back_to(self.asm))

    def _cancel(self):
        FreeCAD.closeActiveTransaction(True)  # todo el paso, en todos los documentos
        for d in self.part_docs.values():
            safe_ops.end_step(d, abort=True)
            d.recompute()
        if self.data is None:  # operación nueva: se va también el croquis
            doc = self.asm.Document
            if doc.getObject(self.sketch.Name) is not None:
                doc.openTransaction(LABELS[self.op_kind])
                doc.removeObject(self.sketch.Name)
                safe_ops.end_step(doc)
        self._back()


# --- Taladro: el panel de la fase 2 sobre el taladro de la primera pieza ---------------

HOLE_PROPS = ("Threaded", "ModelThread", "ThreadType", "ThreadSize", "ThreadClass", "ThreadFit", "Diameter",
              "ThreadDirection", "HoleCutType", "HoleCutCustomValues", "HoleCutDiameter", "HoleCutDepth",
              "HoleCutCountersinkAngle", "DepthType", "Depth", "DrillPoint", "DrillPointAngle",
              "DrillForDepth", "Tapered", "TaperedAngle", "ThreadDepthType", "ThreadDepth", "UseCustomThreadClearance",
              "CustomThreadClearance")

_hole_class = None


def make_hole_panel():
    global _hole_class
    if _hole_class is not None:
        return _hole_class
    from swui.fork import hole_panel

    class AsmHolePanel(hole_panel.HolePanel, _Scope):
        TRANSACTION = LABELS["hole"]

        def __init__(self, entries, asm, sk, data, title, repeated):
            self._scope_init(entries, asm, sk, data, title, repeated, "hole")
            super().__init__(entries[0][2])
            self.form.setWindowTitle(title)
            self.form.layout().insertWidget(0, self._scope_group())

        def _sketch(self):
            return self.sketch

        def centers(self):
            return len(_unique(centers(self.sketch)))  # punto + su círculo chico = un centro

        def _apply(self):
            problem = super()._apply()
            self._copy_to_others()
            return problem

        def _copy_to_others(self):
            src = self.obj
            for _l, _b, feat in self.entries:
                if feat is src:
                    continue
                for prop in HOLE_PROPS:
                    if not hasattr(src, prop):
                        continue
                    try:
                        if prop == "ThreadSize":  # depende de ThreadType: después de él
                            continue
                        setattr(feat, prop, getattr(src, prop))
                    except Exception:
                        pass
                try:
                    feat.ThreadSize = src.ThreadSize
                    feat.Diameter = src.Diameter
                except Exception:
                    pass
                feat.Document.recompute()

        def _pick(self, obj, sub):
            link = self._link_of(obj)
            if link is None:
                return False
            if link is self.entries[0][0] and len(self.entries) > 1:
                self._switch_main()
            changed = self._toggle_part(link)
            if changed:
                self._fill_parts()
            return changed

        def _switch_main(self):
            """Se saca la primera pieza: el panel pasa a mostrar el taladro de la siguiente."""
            nxt = self.entries[1][2]
            self._copy_to_others()
            self._restore_visibility()
            self.obj, self.doc = nxt, nxt.Document
            self.gdoc = FreeCADGui.getDocument(self.doc.Name)
            self.base = self._base()
            self.visible = self._remember_visibility()

        def _nothing(self):
            return not self.entries or super()._nothing()

        def accept(self):
            self._copy_to_others()
            if self.timer.isActive():
                self.preview()
            if self._nothing() or not self.valid:
                return super().accept()  # avisa por qué y no cierra
            self._record()  # dentro del paso: el Aceptar de la pieza sale de edición y lo cierra
            done = super().accept()
            if done:
                self._finish()
            return done

        def _open_step(self):
            begin_operation(self.TRANSACTION)  # el de la aplicación: ensamblaje y piezas (#37)

        def _abort_step(self):
            FreeCAD.closeActiveTransaction(True)  # el paso entero, en todos los documentos

        def reject(self):
            super().reject()  # vuelve lo visible, deshace el paso entero y recién sale de edición
            self._cancel()
            return True

        def edit_positions(self, *_a):
            if not self.accept():
                return
            FreeCADGui.Control.closeDialog()
            QtCore.QTimer.singleShot(100, lambda: FreeCADGui.ActiveDocument.setEdit(self.sketch))

    _hole_class = AsmHolePanel
    return AsmHolePanel


# --- Corte ------------------------------------------------------------------------


def _both_sides(feat):
    """¿El vaciado va a los dos lados? En 1.1 'Midplane' está obsoleto (avisa): se usa SideType."""
    if hasattr(feat, "SideType"):
        return feat.SideType == "Symmetric"
    return bool(getattr(feat, "Midplane", False))


def _set_both_sides(feat, both):
    if hasattr(feat, "SideType"):
        feat.SideType = "Symmetric" if both else "One side"
    else:
        feat.Midplane = both


class CutPanel(_Scope):
    """Extruir corte de ensamblaje: condición final, profundidad, piezas afectadas."""

    ENDS = (("ThroughAll", "Por todo"), ("TwoSides", "Por todo - ambas direcciones"), ("Length", "Hasta profundidad especificada"))

    def __init__(self, entries, asm, sk, data, title, repeated, kind="cut"):
        self._scope_init(entries, asm, sk, data, title, repeated, kind)
        first = entries[0][2] if entries else None
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(title)
        box = QtWidgets.QVBoxLayout(self.form)
        g = QtWidgets.QGroupBox("Dirección 1")
        gl = QtWidgets.QFormLayout(g)
        self.end = QtWidgets.QComboBox()
        for key, text in self.ENDS:
            self.end.addItem(text, key)
        current = "ThroughAll"
        if first is not None:
            current = "TwoSides" if first.Type == "ThroughAll" and _both_sides(first) else first.Type
        keys = [k for k, _t in self.ENDS]
        self.end.setCurrentIndex(keys.index(current) if current in keys else 0)
        gl.addRow(self.end)
        self.depth = QtWidgets.QDoubleSpinBox()
        self.depth.setRange(0.01, 1e6)
        self.depth.setSuffix(" mm")
        self.depth.setValue(float(first.Length) if first is not None else 10.0)
        gl.addRow("Profundidad:", self.depth)
        self.flip = QtWidgets.QCheckBox("Invertir lado")
        self.flip.setChecked(bool(first.Reversed) if first is not None else False)
        gl.addRow(self.flip)
        box.addWidget(g)
        box.addWidget(self._scope_group())
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        box.addWidget(self.message)
        box.addStretch(1)
        self.end.currentIndexChanged.connect(lambda *_a: self._changed())
        self.depth.valueChanged.connect(lambda *_a: self._changed())
        self.flip.toggled.connect(lambda *_a: self._changed())
        from swui.fork import mates_sw

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._picked)
        self.observer = mates_sw._SelObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()
        self.busy = False
        self._changed()

    def schedule(self):
        if not self.busy:
            self.timer.start(0)

    def _picked(self):
        try:
            sels = FreeCADGui.Selection.getSelectionEx()
        except Exception:
            sels = []
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        changed = False
        for sel in sels:
            link = self._link_of(sel.Object)
            if link is not None:
                changed = self._toggle_part(link) or changed
        if changed:
            self._fill_parts()
            if self.op_kind == "hole" and self.entries:
                # taladro que no tocaba ninguna pieza (#68): con la primera elegida, el panel del
                # taladro (medida, tipo...), en el mismo paso de la operación
                self._close()
                QtCore.QTimer.singleShot(0, lambda: _show(self.asm, "hole", self.sketch, self.entries,
                                                          self.data, self.title, self.repeated))
                return
            self._changed()

    def _copy_to_others(self):
        self._apply_all()

    def _apply_all(self):
        end = self.end.currentData()
        for _l, _b, feat in self.entries:
            if feat.TypeId != "PartDesign::Pocket":
                continue  # un taladro (panel abierto para elegir piezas): lo maneja su panel
            feat.Type = "ThroughAll" if end == "TwoSides" else end
            _set_both_sides(feat, end == "TwoSides")
            feat.Length = self.depth.value()
            feat.Reversed = self.flip.isChecked()

    def _changed(self):
        self.depth.setEnabled(self.end.currentData() == "Length")
        problem = ""
        try:
            self._apply_all()
            for d in self.part_docs.values():
                d.recompute()
            bad = [l.Label for l, _b, f in self.entries if not f.isValid()]
            if bad:
                problem = "FreeCAD no pudo cortar: %s." % ", ".join(bad)
            elif not self.entries:
                problem = ("El taladro no toca ninguna pieza: elija las piezas (clic en la vista)."
                           if self.op_kind == "hole" else
                           "El corte no toca ninguna pieza: elija las piezas (clic en la vista).")
        except Exception:
            problem = "No se pudo calcular el corte."
            FreeCAD.Console.PrintError("[SWUI fork] Corte de ensamblaje:\n%s\n" % traceback.format_exc())
        self.message.setText(problem)
        self.message.setVisible(bool(problem))

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel

    def accept(self):
        self._changed()
        if self.message.text():
            return False  # el aviso dice por qué (no cortó, o no toca ninguna pieza): #10
        self._close()
        self._save()
        FreeCADGui.Control.closeDialog()
        return True

    def reject(self):
        self._close()
        self._cancel()
        FreeCADGui.Control.closeDialog()
        return True

    def _close(self):
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        _state["panel"] = None


# --- Comandos y cinta ----------------------------------------------------------------


class _Command:
    def __init__(self, kind):
        self.kind = kind

    def GetResources(self):
        from swui import paths

        tips = {"hole": "Taladro en varias piezas de una vez, desde el ensamblaje (queda dentro de cada pieza)",
                "cut": "Corte en varias piezas de una vez, desde el ensamblaje (queda dentro de cada pieza)"}
        icon = "sketch/f_hole" if self.kind == "hole" else "sketch/f_pocket"
        return {"MenuText": LABELS[self.kind], "ToolTip": tips[self.kind], "Pixmap": paths.icon(icon) or ""}

    def IsActive(self):
        from swui.fork import mates_sw

        doc = FreeCAD.ActiveDocument
        return doc is not None and bool(mates_sw._assemblies(doc))

    def Activated(self):
        start(self.kind)


FLYOUT = [
    ("SWUI_AssemblyHole", "Asistente para\ntaladro", {"svg": "sketch/f_hole"}),
    ("SWUI_AssemblyCut", "Extruir\ncorte", {"svg": "sketch/f_pocket"}),
]


def install_ribbon():
    from swui import ribbon_layout

    groups = ribbon_layout.BAUGRUPPE[1]
    for group in groups:
        if any(isinstance(e, dict) and e.get("flyout") == FLYOUT for e in group):
            return
    for group in groups:
        for i, e in enumerate(group):
            if isinstance(e, tuple) and e[0] == "Assembly_CreateView":
                group.insert(i, {"flyout": list(FLYOUT)})
                return
    groups.append([{"flyout": list(FLYOUT)}])


def install():
    global _installed
    if _installed:
        return
    for cmd, kind in ((HOLE_CMD, "hole"), (CUT_CMD, "cut")):
        try:
            FreeCADGui.addCommand(cmd, _Command(kind))
        except Exception:
            pass  # ya registrado
    install_ribbon()
    from swui.fork import dress_up_panel as dp

    if (operation_of, open_panel) not in dp.OPENERS:
        dp.OPENERS.append((operation_of, open_panel))
    if edit_redirect not in dp.EDIT_REDIRECTS:
        dp.EDIT_REDIRECTS.append(edit_redirect)
    FreeCAD.addDocumentObserver(_Observer())
    FreeCADGui.addDocumentObserver(_GuiObserver())
    _installed = True
