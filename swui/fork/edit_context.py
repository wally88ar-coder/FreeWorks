# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Pieza común de "Editar pieza = pieza" (plan del 16/11, docs/ESTADO.md): las preguntas que toda herramienta
de pieza se hace, contestadas igual en la pieza sola y editando la pieza dentro de un ensamblaje.

Editando (edit_part.start), la pieza está en su documento (sin ventana propia) y se ve y se toca a través
del componente, en la ventana del ensamblaje: lo elegido viene con el camino del ensamblaje
("Comp.Extruir.;#..;F.Face6"), lo que se abre en edición se abre en la ventana del ensamblaje con ese camino
(`Gui.Document.setEdit(ensamblaje, 0, "Comp.Op.")`), y lo nuevo tiene que ir al documento de la pieza.
Una herramienta que pregunta acá en vez de a FreeCADGui.ActiveDocument / getDocument(obj.Document.Name)
anda igual en los dos casos.

    edit_context.current()          contexto de edición del documento activo (o None)
    edit_context.for_document(doc)  contexto de edición de un documento de pieza (o None)
    edit_context.work_document()    dónde crear: la pieza editada, o el documento activo
    edit_context.gui_document(obj)  la ventana (Gui.Document) donde se edita obj
    edit_context.in_edit(doc)       lo que está en edición de doc (también a través del ensamblaje)
    edit_context.set_edit(obj)      abrir obj en edición (a través del componente si hace falta)
    edit_context.reset_edit(doc)    cerrar la edición de doc
    edit_context.path_of(obj)       camino de obj desde el ensamblaje
    edit_context.selection()        lo elegido como lo ve la pieza: ([(obj, [elementos])], hay_de_afuera)
    edit_context.select(obj, el)    elegir obj (y su elemento) por el camino del componente
    edit_context.new_sketch(obj,el) croquis nuevo en la pieza, apoyado en obj, abierto
"""

import collections
import traceback

import FreeCAD
import FreeCADGui

Context = collections.namedtuple("Context", "asm link prefix part pdoc")


def _editing():
    from swui.fork import edit_part

    return edit_part._editing


def _context(asm_doc):
    from swui.fork import edit_part

    link = edit_part.editing(asm_doc)
    if link is None:
        return None
    asm, prefix = edit_part.assembly_and_path(link)
    part = getattr(link, "LinkedObject", None)
    if asm is None or part is None:
        return None
    return Context(asm, link, prefix, part, part.Document)


def current(doc=None):
    """Contexto de Editar pieza del documento doc (por omisión el activo), o None."""
    if not _editing():
        return None
    doc = doc or FreeCAD.ActiveDocument
    if not getattr(doc, "Name", None):
        return None
    return _context(doc)


def for_document(part_doc):
    """El contexto en el que se está editando la pieza part_doc (desde algún ensamblaje), o None."""
    if not _editing() or part_doc is None:
        return None
    for name in list(_editing()):
        try:
            ctx = _context(FreeCAD.getDocument(name))
        except Exception:
            ctx = None
        if ctx is not None and ctx.pdoc is part_doc:
            return ctx
    return None


def work_document():
    """Dónde va lo nuevo: el documento de la pieza editada, o el documento activo."""
    ctx = current()
    return ctx.pdoc if ctx is not None else FreeCAD.ActiveDocument


def active_body():
    """El Cuerpo activo de la ventana al frente (editando: el de la pieza, a través del componente)."""
    try:
        gdoc = FreeCADGui.ActiveDocument
        view = gdoc.ActiveView if gdoc is not None else None
        if view is None or not hasattr(view, "getActiveObject"):
            ctx = current()
            if ctx is None:
                return None
            from swui.fork import edit_part

            view = edit_part._view(ctx.asm.Document)
        return view.getActiveObject("pdbody")
    except Exception:
        return None


# --- Caminos ----------------------------------------------------------------------------------------------


def path_of(obj, ctx=None):
    """Camino de obj desde el ensamblaje ('Comp.Op.', 'Comp.Body.Op.' con contenedor), o None."""
    ctx = ctx or for_document(getattr(obj, "Document", None))
    if ctx is None or obj is None:
        return None
    if obj is ctx.part:
        return ctx.prefix
    try:
        for parent, sub in getattr(obj, "Parents", []):
            if parent is ctx.part:
                return ctx.prefix + sub
    except Exception:
        pass
    # un Cuerpo enlazado directo: sus operaciones y su Origen (getParents puede no dar el camino corto)
    body = ctx.part
    if getattr(body, "TypeId", "") == "PartDesign::Body":
        if obj in getattr(body, "Group", []):
            return ctx.prefix + obj.Name + "."
        origin = getattr(body, "Origin", None)
        if origin is not None and obj in origin.OriginFeatures:
            return "%s%s.%s." % (ctx.prefix, origin.Name, obj.Name)
    return None


def _plain(sub):
    from swui.fork import context_menus as cm

    return cm.plain_sub(sub)


def selection():
    """
    Lo elegido como lo ve la pieza editada: ([(objeto de la pieza, [elemento])], hay_algo_de_afuera), o
    None si no se edita. Una cara nombrada por el Cuerpo ('Comp.Body.Face6') se da por su Punta (la forma
    del Cuerpo es la de su Punta; un croquis apoyado en el Cuerpo sería una dependencia circular).
    """
    ctx = current()
    if ctx is None:
        return None
    out, outside = [], False
    for s in FreeCADGui.Selection.getSelectionEx("", 0):
        for sub in list(s.SubElementNames or []) or [""]:
            plain = _plain(sub)
            if s.Object is not ctx.asm or not plain.startswith(ctx.prefix):
                outside = True
                continue
            tokens = plain[len(ctx.prefix):].split(".")
            element, chain = tokens[-1], [t for t in tokens[:-1] if t]
            obj = ctx.pdoc.getObject(chain[-1]) if chain else ctx.part
            if obj is not None and element and obj.TypeId == "PartDesign::Body":
                obj = getattr(obj, "Tip", None) or obj
            if obj is None:
                outside = True
                continue
            out.append((obj, [element] if element else []))
    return out, outside


def outside_selection():
    """
    Lo elegido en OTROS componentes del ensamblaje mientras se edita una pieza: [camino desde el ensamblaje
    ('Otro.Extruir.Face6')], o [] (o None si no se edita).
    """
    ctx = current()
    if ctx is None:
        return None
    out = []
    for s in FreeCADGui.Selection.getSelectionEx(ctx.asm.Document.Name, 0):
        if s.Object is not ctx.asm:
            continue
        for sub in list(s.SubElementNames or []):
            plain = _plain(sub)
            if plain and not plain.startswith(ctx.prefix):
                out.append(plain)
    return out


def outside_shape(sub, ctx=None):
    """La forma (en el ensamblaje) del elemento de otro componente `sub`, o None."""
    ctx = ctx or current()
    try:
        shape = ctx.asm.getSubObject(sub)
        return shape if shape is not None and not shape.isNull() else None
    except Exception:
        return None


# Top-down (17/11, como SW: editando una pieza, croquis / referencias sobre la geometría de OTRO componente).
# Lo nativo de FreeCAD para eso es la copia de forma en contexto (PartDesign SubShapeBinder): queda en el
# Cuerpo editado, apunta al elemento del otro componente a través del ensamblaje y lo sigue si se mueve
# (medido el 17/11). Nombre visible "Referencia externa (...)"; la propiedad SWUI_ExternalRef la marca.
EXTERNAL_MARK = "SWUI_ExternalRef"
_creating = [0]  # >0 mientras external_reference elige lo de afuera para la copia (los observadores no actúan)


def external_reference(subs, ctx=None, body=None):
    """
    Copia de forma en contexto, en el Cuerpo activo de la pieza editada (o en `body`), de los elementos `subs`
    de otros componentes (caminos desde el ensamblaje, como da outside_selection). Un paso de deshacer.
    Devuelve la copia (sus elementos: Face1, Edge1... en el orden de subs) o None.
    Se arma por código y no con el comando nativo: con un panel abierto (Extruir) el comando no corre, y el
    contexto que pone solo a veces queda en el Cuerpo, y entonces no sigue a la pieza editada si se mueve
    (medido el 17/11): acá el contexto es siempre el ensamblaje, por el camino de la copia.
    """
    ctx = ctx or current()
    if ctx is None or not subs:
        return None
    body = body or active_body()
    if body is None or body.Document is not ctx.pdoc:
        return None
    support = collections.OrderedDict()
    for sub in subs:
        first, _dot, rest = sub.partition(".")
        link = ctx.asm.Document.getObject(first)
        if link is None or not rest or _would_cycle(link, ctx):
            return None
        support.setdefault(link.Name, (link, []))[1].append(rest)
    first_link = list(support.values())[0][0]
    _creating[0] += 1
    # con un panel abierto (Extruir nuevo) su paso de deshacer sigue abierto: la referencia va adentro (abrir
    # otro lo confirmaría y Cancelar ya no desharía la extrusión: revisión 17/11)
    own = not _transaction_open()
    if own:
        FreeCAD.setActiveTransaction("Referencia externa")
    try:
        binder = body.newObject("PartDesign::SubShapeBinder", "Referencia")
        binder.Label = "Referencia externa (%s)" % first_link.Label
        binder.addProperty("App::PropertyBool", EXTERNAL_MARK, "FreeWorks", "Referencia a otro componente")
        setattr(binder, EXTERNAL_MARK, True)
        binder.Support = [(link, tuple(rests)) for link, rests in support.values()]
        path = path_of(binder, ctx)
        if path is None:
            raise RuntimeError("sin camino a la referencia externa")
        binder.Context = (ctx.asm, path)
        binder.Relative = True
        ctx.pdoc.recompute()
        if binder.Shape.isNull():
            raise RuntimeError("referencia externa vacía")
    except Exception:
        log("Referencia externa")
        if own:
            FreeCAD.closeActiveTransaction(True)
        else:
            try:
                if ctx.pdoc.getObject(binder.Name) is binder:
                    ctx.pdoc.removeObject(binder.Name)
            except Exception:
                pass
        return None
    finally:
        _creating[0] -= 1
    if own:
        FreeCAD.closeActiveTransaction()
    return binder


def _transaction_open():
    try:
        return bool(FreeCAD.getActiveTransaction())
    except Exception:
        return False


def _would_cycle(link, ctx):
    """¿El otro componente es (o contiene) la pieza editada? (otra instancia de la misma pieza, o un
    subensamblaje que la tiene): la referencia haría un ciclo."""
    try:
        target = link.getLinkedObject(True)
        if target is None or target.Document is ctx.pdoc:
            return True
        return any(getattr(o, "Document", None) is ctx.pdoc for o in target.OutListRecursive)
    except Exception:
        return True


def sketch_on_outside_face(sub, ctx=None):
    """
    Top-down: croquis nuevo en la pieza editada sobre la cara plana `sub` de otro componente (a través de una
    referencia externa). Devuelve el croquis abierto, o None si no es una cara plana.
    """
    ctx = ctx or current()
    shape = outside_shape(sub, ctx)
    if shape is None or shape.ShapeType != "Face" or shape.Surface.__class__.__name__ != "Plane":
        return None
    binder = external_reference([sub], ctx)
    if binder is None:
        return None
    sketch = new_sketch(binder, "Face1")
    try:
        binder.ViewObject.Visibility = False  # como en SW: la referencia no se ve como una pieza más
    except Exception:
        pass
    return sketch


def convert_outside_edges(sketch, subs, ctx=None):
    """
    Top-down: Convertir entidades con aristas de OTRO componente, con el croquis `sketch` de la pieza editada
    abierto. Las aristas pasan por una referencia externa (external_reference) y entran al croquis como
    geometría externa (lo mismo que hace Convertir con las aristas de la pieza). Devuelve cuántas entraron.
    """
    ctx = ctx or for_document(sketch.Document)
    edges = []
    for sub in subs:
        shape = outside_shape(sub, ctx)
        if shape is not None and shape.ShapeType == "Edge":
            edges.append(sub)
    if not edges:
        return 0
    binder = external_reference(edges, ctx)
    if binder is None:
        return 0
    try:
        binder.ViewObject.Visibility = False
    except Exception:
        pass
    n = 0
    FreeCAD.setActiveTransaction("Convertir entidades")
    try:
        for i in range(len(binder.Shape.Edges)):
            sketch.addExternal(binder.Name, "Edge%d" % (i + 1))
            n += 1
    except Exception:
        log("Convertir entidades de otro componente")
    FreeCAD.closeActiveTransaction()
    ctx.pdoc.recompute()
    return n


def part_placement(ctx):
    """
    Dónde está la pieza editada dentro del ensamblaje (Placement de la pieza al ensamblaje; también con el
    componente dentro de un contenedor o movido). Identidad si no se puede saber.
    """
    import Part

    try:
        local = Part.getShape(ctx.part)
        glob = Part.getShape(ctx.asm, ctx.prefix)
        if not local.isNull() and not glob.isNull():
            return glob.Placement.multiply(local.Placement.inverse())
        # pieza todavía vacía (Cuerpo sin operaciones) o con error: sin forma, por la ubicación del camino
        # (revisión del 18/11). La del camino no incluye la de la pieza; si el componente la reemplaza
        # (LinkTransform falso, lo normal), se le saca (medido con FreeCADCmd, las 4 combinaciones)
        plc = ctx.asm.getSubObject(ctx.prefix, retType=3, transform=True)
        if not getattr(ctx.link, "LinkTransform", False):
            plc = plc.multiply(ctx.part.Placement.inverse())
        return plc
    except Exception:
        log("Ubicación de la pieza editada")
    return FreeCAD.Placement()


_view_cache = {}


def _cache_key(ctx):
    """Todo lo que cambia la ubicación de la pieza en la vista (revisión del 18/11, hallazgo 7)."""
    import Part

    link, part = ctx.link, ctx.part
    return (ctx.asm.Document.Name, link.Name, str(link.Placement), str(getattr(ctx.asm, "Placement", "")),
            bool(getattr(link, "LinkTransform", False)), part.Document.Name, part.Name, str(part.Placement),
            Part.getShape(part).isNull())


def view_placement(doc=None, part_doc=None):
    """
    #100 (18/11): editando una pieza dentro de un ensamblaje, la vista es la del ensamblaje y la pieza se ve donde
    está su componente. Placement de la pieza a la vista (para pasar puntos y dibujos de vista previa), o None si
    el documento activo (o doc) no edita una pieza. Con part_doc: solo si ESE documento es la pieza que se edita
    (para lo que ya sabe de qué documento es, como el croquis o las propiedades físicas).
    """
    ctx = for_document(part_doc) if part_doc is not None else current(doc)
    if ctx is None:
        return None
    try:
        key = _cache_key(ctx)
    except Exception:
        key = None
    if key is not None and key in _view_cache:
        return _view_cache[key]
    plc = part_placement(ctx)
    if key is not None:
        _view_cache.clear()
        _view_cache[key] = plc
    return plc


def to_view(point, doc=None, part_doc=None):
    """Punto de la pieza -> punto de la vista (igual sin edición)."""
    plc = view_placement(doc, part_doc)
    return plc.multVec(point) if plc is not None else point


def from_view(point, doc=None):
    """Punto de la vista -> punto de la pieza (igual sin edición)."""
    plc = view_placement(doc)
    return plc.inverse().multVec(point) if plc is not None else point


def direction_from_view(vec, doc=None):
    """Dirección de la vista -> dirección de la pieza (solo el giro)."""
    plc = view_placement(doc)
    return plc.Rotation.inverted().multVec(vec) if plc is not None else vec


def view_transform_node(doc=None):
    """
    Nodo Coin que pone lo que se dibuja en coordenadas de la pieza donde se ve la pieza en la vista del ensamblaje
    (va primero dentro del separador de la vista previa), o None si no se edita una pieza.
    """
    plc = view_placement(doc)
    if plc is None:
        return None
    from pivy import coin

    node = coin.SoTransform()
    node.translation.setValue(plc.Base.x, plc.Base.y, plc.Base.z)
    q = plc.Rotation.Q
    node.rotation.setValue(coin.SbRotation(q[0], q[1], q[2], q[3]))
    return node


def global_shape(obj, ctx=None):
    """Forma de obj (de la pieza editada) en coordenadas del ensamblaje; sin edición, la de siempre."""
    import Part

    ctx = ctx or for_document(getattr(obj, "Document", None))
    path = path_of(obj, ctx) if ctx is not None else None
    if path:
        try:
            shape = Part.getShape(ctx.asm, path)
            if not shape.isNull():
                return shape
        except Exception:
            pass
    shape = Part.getShape(obj)
    if ctx is not None and not shape.isNull():
        shape = shape.copy()
        shape.Placement = part_placement(ctx).multiply(shape.Placement)
    return shape


def other_components(ctx):
    """
    [(componente, forma en el ensamblaje)] de los OTROS componentes visibles del ensamblaje de la edición
    (los del primer nivel; no la pieza editada ni los que la contienen: una referencia haría un ciclo).
    """
    import Part

    out = []
    for o in getattr(ctx.asm, "Group", []) or []:
        try:
            if o is ctx.link or not getattr(o, "Visibility", True) or not hasattr(o, "getLinkedObject"):
                continue
            if o.TypeId not in ("App::Link", "App::LinkElement") or _would_cycle(o, ctx):
                continue
            shape = Part.getShape(ctx.asm, o.Name + ".")
            if not shape.isNull() and (shape.Edges or shape.Vertexes):
                out.append((o, shape))
        except Exception:
            pass
    return out


def _outside_external(sketch, link, sub):
    """(copia, elemento) de una referencia ya traída al croquis para `sub` del componente `link`, o None."""
    for target, subs in getattr(sketch, "ExternalGeometry", []) or []:
        if not hasattr(target, EXTERNAL_MARK):
            continue
        try:
            support = list(target.Support)
            if support == [(link, (sub,))] and subs:
                return target.Name, subs[0]
            # una copia de Convertir entidades trae varias aristas: la n-ésima es EdgeN (revisión 18/11, hallazgo 8)
            if len(support) == 1 and support[0][0] is link and sub.startswith("Edge"):
                names = list(support[0][1])
                if all(n.startswith("Edge") for n in names) and sub in names:
                    element = "Edge%d" % (names.index(sub) + 1)
                    if element in subs:
                        return target.Name, element
        except Exception:
            pass
    return None


def outside_element_in_sketch(sketch, sub, ctx=None):
    """
    Top-down (18/11, decisión del usuario: mejor que SW): con el croquis `sketch` de la pieza editada abierto,
    trae al croquis la arista o vértice `sub` de OTRO componente ('Otro.Edge5', camino desde el ensamblaje)
    como geometría externa, a través de una referencia externa en el Cuerpo del croquis; sin pasar por
    Convertir entidades. Un paso de deshacer (o dentro del que esté abierto). Si ya estaba, no repite.
    Devuelve (nombre de la copia, 'Edge1' o 'Vertex1') o None.
    """
    from swui.fork import feature_tree as ft

    ctx = ctx or for_document(sketch.Document)
    if ctx is None:
        return None
    first, _dot, element = sub.partition(".")
    link = ctx.asm.Document.getObject(first)
    kind = "Vertex" if element.startswith("Vertex") else "Edge"
    if link is None or not element.startswith(("Edge", "Vertex")) or "." in element:
        return None
    found = _outside_external(sketch, link, element)
    if found is not None:
        return found
    body = ft.body_of(sketch)
    if body is None:
        return None  # croquis fuera de un Cuerpo: la copia no podría ir a otro lado (revisión 18/11, hallazgo 6)
    own = not _transaction_open()
    if own:
        FreeCAD.setActiveTransaction("Referencia de otro componente")
    binder = None
    try:
        binder = external_reference([sub], ctx, body=body)
        if binder is None:
            raise RuntimeError("sin referencia externa")
        try:
            binder.ViewObject.Visibility = False
        except Exception:
            pass
        sketch.addExternal(binder.Name, kind + "1")
        sketch.recompute()
    except Exception:
        log("Arista de otro componente en el croquis")
        if own:
            FreeCAD.closeActiveTransaction(True)
        elif binder is not None:  # dentro de un paso ajeno: que no quede la copia colgada
            try:
                if ctx.pdoc.getObject(binder.Name) is binder:
                    ctx.pdoc.removeObject(binder.Name)
            except Exception:
                pass
        return None
    if own:
        FreeCAD.closeActiveTransaction()
    return binder.Name, kind + "1"


def resolved_selection():
    """
    Lo elegido como [(objeto, [elementos])], igual en la pieza sola (getSelectionEx) y editando (la pieza
    vista a través del componente; lo de otros componentes no entra).
    """
    found = selection()
    if found is None:
        try:
            return [(s.Object, list(s.SubElementNames or [])) for s in FreeCADGui.Selection.getSelectionEx()]
        except Exception:
            return []
    return found[0]


class LocalSelection:
    """Como un SelectionObject de FreeCAD, pero visto desde la pieza (lo elegido a través del componente)."""

    def __init__(self, obj, subs):
        self.Object = obj
        self.ObjectName = obj.Name
        self.Document = obj.Document
        self.DocumentName = obj.Document.Name
        self.FullName = obj.FullName
        self.SubElementNames = tuple(subs)
        self.HasSubObjects = bool(subs)
        self.PickedPoints = ()

    @property
    def SubObjects(self):
        out = []
        for sub in self.SubElementNames:
            try:
                out.append(self.Object.getSubObject(sub))
            except Exception:
                pass
        return tuple(o for o in out if o is not None)


def selection_ex(doc_name="", resolve=1):
    """
    Reemplazo de FreeCADGui.Selection.getSelectionEx(doc_name, resolve) para una herramienta de pieza: igual
    en la pieza sola; editando la pieza dentro de un ensamblaje (y pidiendo la pieza, el ensamblaje o "")
    devuelve lo elegido de la pieza como si se hubiera elegido en ella (resolve=0: desde la pieza con su
    camino interno; resolve=1: la operación y el elemento). Lo de otros componentes no entra.
    """
    if not isinstance(doc_name, str):
        doc_name = getattr(doc_name, "Name", "")
    ctx = current()
    if ctx is None or doc_name not in ("", ctx.pdoc.Name, ctx.asm.Document.Name):
        return FreeCADGui.Selection.getSelectionEx(doc_name, resolve)
    groups = collections.OrderedDict()
    for s in FreeCADGui.Selection.getSelectionEx(ctx.asm.Document.Name, 0):
        if s.Object is not ctx.asm:
            continue
        for sub in list(s.SubElementNames or []):
            plain = _plain(sub)
            if not plain.startswith(ctx.prefix):
                continue
            tokens = plain[len(ctx.prefix):].split(".")
            element, chain = tokens[-1], [t for t in tokens[:-1] if t]
            if resolve == 0:
                top, sub_out = ctx.part, plain[len(ctx.prefix):]
            else:
                top = ctx.pdoc.getObject(chain[-1]) if chain else ctx.part
                if top is not None and element and top.TypeId == "PartDesign::Body":
                    top = getattr(top, "Tip", None) or top
                sub_out = element
            if top is None:
                continue
            groups.setdefault(top.Name, (top, []))[1].extend([sub_out] if sub_out else [])
    return [LocalSelection(top, subs) for top, subs in groups.values()]


def local_click(doc_name, obj_name, sub):
    """
    Un clic que llega a un observador de selección (documento, objeto, subelemento) traducido a la pieza:
    editando, (documento de la pieza, objeto raíz de la pieza, camino interno); si no, igual.
    """
    ctx = current()
    if ctx is None or doc_name != ctx.asm.Document.Name or obj_name != ctx.asm.Name:
        return doc_name, obj_name, sub
    plain = _plain(sub or "")
    if not plain.startswith(ctx.prefix):
        return doc_name, obj_name, sub
    return ctx.pdoc.Name, ctx.part.Name, plain[len(ctx.prefix):]


def select(obj, element="", clear=True):
    """Elige obj (y su elemento): editando, por el camino del componente. False si no se pudo."""
    ctx = for_document(getattr(obj, "Document", None))
    if clear:
        FreeCADGui.Selection.clearSelection()
    if ctx is None or ctx.asm.Document is not FreeCAD.ActiveDocument:
        if element:
            FreeCADGui.Selection.addSelection(obj.Document.Name, obj.Name, element)
        else:
            FreeCADGui.Selection.addSelection(obj)
        return True
    path = path_of(obj, ctx)
    if path is None:
        return False
    try:
        if ctx.asm.getSubObject(path, 1) is not obj:
            return False
    except Exception:
        return False
    FreeCADGui.Selection.addSelection(ctx.asm.Document.Name, ctx.asm.Name, path + (element or ""))
    return True


# --- Edición ----------------------------------------------------------------------------------------------


def gui_document(obj_or_doc):
    """La ventana (Gui.Document) donde se edita: la del ensamblaje si la pieza se edita desde uno."""
    doc = getattr(obj_or_doc, "Document", None) if not hasattr(obj_or_doc, "Objects") else obj_or_doc
    if doc is None:
        return None
    ctx = for_document(doc)
    if ctx is not None:
        return FreeCADGui.getDocument(ctx.asm.Document.Name)
    return FreeCADGui.getDocument(doc.Name)


def in_edit(doc):
    """El proveedor de vista en edición de un objeto de doc (también editado desde el ensamblaje), o None."""
    if isinstance(doc, str):
        doc = FreeCAD.getDocument(doc)
    try:
        own = FreeCADGui.getDocument(doc.Name).getInEdit()
    except Exception:
        own = None
    if own is not None:
        return own
    ctx = for_document(doc)
    if ctx is None:
        return None
    vp = FreeCADGui.getDocument(ctx.asm.Document.Name).getInEdit()
    obj = getattr(vp, "Object", None)
    return vp if obj is not None and obj.Document is doc else None


def set_edit(obj, mode=0):
    """Abre obj en edición; editando la pieza, en la ventana del ensamblaje por el camino del componente."""
    ctx = for_document(obj.Document)
    path = path_of(obj, ctx) if ctx is not None else None
    if path is None:
        return FreeCADGui.getDocument(obj.Document.Name).setEdit(obj, mode)
    from swui.fork import edit_part as ep

    # #105: cancelar no deja el ensamblaje ni la pieza modificados (si no cambió nada)
    before = ep._doc_states([ctx.asm.Document] + ([obj.Document] if obj.Document is not ctx.asm.Document else []))
    windows = [w for w in _part_windows(obj.Document) if w.isVisible()]
    camera = asm_camera(ctx.asm.Document.Name)
    result = FreeCADGui.getDocument(ctx.asm.Document.Name).setEdit(ctx.asm, mode, path)
    ep._clean_after_cancel(ctx.asm.Document.Name, before)
    if obj.TypeId == "Sketcher::SketchObject":
        _after_sketch_open(ctx, obj, windows, camera)
    return result


def asm_camera(asm_name):
    """La cámara de la vista del ensamblaje (texto de Inventor), para volver a ella al cerrar el croquis."""
    try:
        gasm = FreeCADGui.getDocument(asm_name)
        view = gasm.activeView() if gasm is not None else None
        return view.getCamera() if view is not None else None
    except Exception:
        return None


def _part_windows(doc):
    """Ventanas (QMdiSubWindow) que muestran la vista 3D de doc."""
    from swui.compat import QtWidgets

    gdoc = FreeCADGui.getDocument(doc.Name)
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    if gdoc is None or area is None:
        return []
    out = []
    try:
        views = gdoc.mdiViewsOfType("Gui::View3DInventor")
    except Exception:
        return []
    for sub in area.subWindowList():
        if any(sub.isAncestorOf(v.graphicsView()) for v in views):
            out.append(sub)
    return out


def _after_sketch_open(ctx, sketch, windows_before, camera=None):
    """
    #106 (18/11): al abrir desde el ensamblaje un croquis de la pieza editada, FreeCAD 1.1.4 (código propio, al pasar
    el documento activo a la pieza) abre una ventana aparte de la pieza, vacía; y gira la vista normal al croquis pero
    la deja centrada donde estaba (el centro del ensamblaje): el croquis queda fuera de la pantalla. Como SW: ninguna
    ventana nueva a la vista (no se cierra: cerrar la última vista de la pieza cerraría la pieza) y la vista mirando
    al croquis, centrada en su cara.
    """
    from swui.compat import QtCore

    asm_name, part_name = ctx.asm.Document.Name, sketch.Document.Name

    def aside():
        # las de la pieza que no estaban a la vista (nuevas, o ya apartadas que FreeCAD vuelve a mostrar)
        new = [w for w in _part_windows(sketch.Document) if w.isVisible() and w not in windows_before]
        _set_aside(new, asm_name)

    # la cámara: FreeCAD la gira con una animación que termina después; se centra cuando deja de moverse. Al cerrar
    # el croquis FreeCAD la anima de vuelta, pero no llega a la de antes (por el centrado): cuando se queda quieta,
    # se pone la de antes de abrir el croquis (lo que hace FreeCAD fuera del ensamblaje)
    timer = QtCore.QTimer()
    timer.setInterval(150)
    state = {"last": None, "ticks": 0, "phase": "open"}

    def still(view):
        cam = view.getCameraNode()
        now = (tuple(round(v, 4) for v in cam.position.getValue().getValue()),
               tuple(round(v, 5) for v in cam.orientation.getValue().getValue()))
        same = now == state["last"]
        state["last"] = now
        state["ticks"] += 1
        return same or state["ticks"] > 20  # quieta (o 3 s)

    def tick():
        try:
            if asm_name not in FreeCAD.listDocuments() or part_name not in FreeCAD.listDocuments():
                _stop()
                return
            aside()
            gasm = FreeCADGui.getDocument(asm_name)
            views = gasm.mdiViewsOfType("Gui::View3DInventor") if gasm is not None else []
            if not views:
                _stop()
                return
            view = gasm.activeView() if gasm.activeView() in views else views[0]
            editing = getattr(gasm.getInEdit(), "Object", None) is sketch
            if state["phase"] == "open":
                if not editing:
                    _stop()  # se cerró antes de centrar: la cámara la vuelve FreeCAD
                    return
                if still(view):
                    _look_at_sketch(asm_name, sketch)
                    state["phase"], state["ticks"], state["last"] = "editing", 0, None
                return
            if state["phase"] == "editing":
                if not editing:
                    state["phase"], state["ticks"], state["last"] = "closing", 0, None
                return
            if still(view):  # "closing": la animación de vuelta terminó
                _stop()
                if camera:
                    view.setCamera(camera)
            return
        except Exception:
            _stop()
            FreeCAD.Console.PrintLog("[SWUI fork] Croquis en el ensamblaje:\n%s\n" % traceback.format_exc())

    def _stop():
        timer.stop()
        if timer in _sketch_timers:
            _sketch_timers.remove(timer)

    aside()
    timer.timeout.connect(tick)
    _sketch_timers.append(timer)  # que no lo junte la basura (hasta que termine)
    timer.start()


_sketch_timers = []


def _set_aside(windows, asm_name):
    """Saca de la vista (sin cerrarlas) las ventanas de la pieza y vuelve a poner al frente la del ensamblaje."""
    from swui.compat import QtWidgets

    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    if area is None or not windows:
        return
    bar = area.findChild(QtWidgets.QTabBar)
    titles = set()
    for w in windows:
        _aside[id(w)] = (w, asm_name)
        try:
            titles.add(w.windowTitle().replace("[*]", "*"))
            titles.add(w.windowTitle().replace("[*]", ""))
            w.hide()
        except RuntimeError:
            pass
    if bar is not None:
        for i in range(bar.count()):
            if bar.tabText(i) in titles:
                bar.setTabVisible(i, False)
    gasm = FreeCADGui.getDocument(asm_name)
    if gasm is not None:
        for sub in _part_windows(gasm.Document):
            if sub.isVisible():
                area.setActiveSubWindow(sub)
                break


_aside = {}  # id(ventana) -> (ventana, ensamblaje): ventanas de piezas apartadas por _set_aside


def keep_aside(sub):
    """
    Si la ventana que pasó al frente es una de las apartadas (FreeCAD la vuelve a mostrar cuando la pieza pasa a ser
    el documento activo), se aparta otra vez y vuelve al frente el ensamblaje. Devuelve True si lo hizo.
    """
    entry = _aside.get(id(sub)) if sub is not None else None
    if entry is None or entry[0] is not sub:
        return False
    asm_name = entry[1]
    from swui.fork import edit_part as ep

    if asm_name is None or asm_name not in FreeCAD.listDocuments() or ep.editing(FreeCAD.getDocument(asm_name)) is None:
        # ya no se edita: la abre el usuario (Abrir pieza...), vuelve con su pestaña
        _aside.pop(id(sub), None)
        try:
            sub.show()
        except RuntimeError:
            return False
        _show_tab(sub)
        return False
    _set_aside([sub], asm_name)
    return True


def release_aside(asm_name):
    """
    Al salir de Editar pieza: las ventanas apartadas de la pieza quedan liberadas. Siguen sin verse (en SW no hay
    ventana de la pieza: no aparece una pestaña de más), pero si el usuario abre la pieza (Abrir pieza, menú Ventana)
    vuelven con su pestaña (keep_aside). Revisión del 18/11.
    """
    for key, (sub, owner) in list(_aside.items()):
        if owner == asm_name:
            _aside[key] = (sub, None)


def _show_tab(sub):
    from swui.compat import QtWidgets

    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    bar = area.findChild(QtWidgets.QTabBar) if area is not None else None
    if bar is None:
        return
    try:
        title = sub.windowTitle()
    except RuntimeError:
        return
    for i in range(bar.count()):
        if bar.tabText(i) in (title.replace("[*]", "*"), title.replace("[*]", "")):
            bar.setTabVisible(i, True)


def _look_at_sketch(asm_name, sketch):
    """La vista del ensamblaje normal al croquis y centrada en la cara donde está apoyado (o en el croquis)."""
    import Part

    ctx = for_document(sketch.Document)
    gasm = FreeCADGui.getDocument(asm_name)
    if ctx is None or gasm is None:
        return
    views = gasm.mdiViewsOfType("Gui::View3DInventor")
    if not views:
        return
    view = gasm.activeView() if gasm.activeView() in views else views[0]
    plc = part_placement(ctx)
    rot = plc.Rotation.multiply(sketch.getGlobalPlacement().Rotation)

    def global_shape(obj, sub=""):
        # sin la colocación propia y con la global (Cuerpo incluido): revisión del 18/11, con un Cuerpo corrido
        # dentro de la pieza transform=True dejaba la cara corrida
        s = Part.getShape(obj, sub, needSubElement=bool(sub), transform=False).copy()
        s.transformShape(obj.getGlobalPlacement().toMatrix())
        return s

    shape = None
    try:
        support = sketch.AttachmentSupport
        if support:
            sobj, subs = support[0][0], [s for s in support[0][1] if s]
            shape = global_shape(sobj, subs[0] if subs else "")
    except Exception:
        shape = None
    if shape is None or shape.isNull():
        shape = global_shape(sketch)
    if shape.isNull():
        center, size = plc.multVec(sketch.getGlobalPlacement().Base), 100.0
    else:
        moved = shape.copy()
        moved.transformShape(plc.toMatrix())
        bb = moved.BoundBox
        center, size = bb.Center, max(bb.DiagonalLength, 1.0)
    view.setCameraOrientation(rot.Q)
    cam = view.getCameraNode()
    dist = max(float(cam.focalDistance.getValue()), size * 2.0)
    back = rot.multVec(FreeCAD.Vector(0, 0, 1))  # la cámara mira por -Z del croquis: se para del lado +Z
    pos = center + back * dist
    cam.position.setValue(pos.x, pos.y, pos.z)
    cam.focalDistance.setValue(dist)
    if hasattr(cam, "height"):  # ortográfica: la cara entera a la vista, con margen
        cam.height.setValue(size * 1.4)


def reset_edit(doc):
    """Cierra la edición de un objeto de doc (la propia o la abierta desde el ensamblaje)."""
    if isinstance(doc, str):
        doc = FreeCAD.getDocument(doc)
    gdoc = FreeCADGui.getDocument(doc.Name)
    if gdoc is not None and gdoc.getInEdit() is not None:
        gdoc.resetEdit()
        return True
    ctx = for_document(doc)
    if ctx is not None and in_edit(doc) is not None:
        FreeCADGui.getDocument(ctx.asm.Document.Name).resetEdit()
        return True
    return False


class EditGui:
    """
    Reemplazo de FreeCADGui.getDocument(doc.Name) para un panel: getInEdit / setEdit / resetEdit andan
    también cuando la pieza se edita desde un ensamblaje (en la ventana del ensamblaje, por el camino del
    componente); lo demás (ActiveView, Document...) es de la ventana donde se ve la pieza.
    """

    def __init__(self, doc):
        self._doc = doc

    def _target(self):
        ctx = for_document(self._doc)
        return FreeCADGui.getDocument(ctx.asm.Document.Name if ctx is not None else self._doc.Name)

    def getInEdit(self):
        return in_edit(self._doc)

    def setEdit(self, obj, mode=0, *args):
        if args or not hasattr(obj, "Document"):
            return self._target().setEdit(obj, mode, *args)
        return set_edit(obj, mode)

    def resetEdit(self):
        return reset_edit(self._doc)

    @property
    def Document(self):
        return self._doc

    def __getattr__(self, name):
        return getattr(self._target(), name)


def gui_for(doc):
    """Gui.Document para un panel de doc: el real, o EditGui si la pieza se edita desde un ensamblaje."""
    if isinstance(doc, str):
        doc = FreeCAD.getDocument(doc)
    if for_document(doc) is not None:
        return EditGui(doc)
    return FreeCADGui.getDocument(doc.Name)


def new_sketch(obj, element="", name="Sketch"):
    """
    Croquis nuevo en el Cuerpo de obj (pieza editada), apoyado en obj (cara `element` de una operación o un
    plano), abierto. No usa el Croquis nativo: en 1.1.4, dentro de un ensamblaje, apoya y abre OTRO croquis
    "Sketch" de la pieza (NOTAS_TECNICAS, errores de FreeCAD 10). Devuelve el croquis o None.
    """
    from swui.fork import feature_tree as ft

    ctx = for_document(getattr(obj, "Document", None))
    if ctx is None:
        return None
    body = obj if obj.TypeId == "PartDesign::Body" else ft.body_of(obj)
    if body is None or obj is body or path_of(body, ctx) is None:
        return None  # solo una operación o un plano de un Cuerpo de esa pieza
    pdoc = body.Document
    FreeCAD.setActiveTransaction("Croquis")
    try:
        sketch = body.newObject("Sketcher::SketchObject", name)
        sketch.AttachmentSupport = [(obj, [element] if element else [""])]
        sketch.MapMode = "FlatFace"
        pdoc.recompute()
    except Exception:
        FreeCAD.closeActiveTransaction(True)
        raise
    FreeCAD.closeActiveTransaction()
    FreeCADGui.Selection.clearSelection()
    set_edit(sketch)
    return sketch


def ensure_container(ctx=None):
    """
    Editando una pieza de UN Cuerpo (el componente apunta al Cuerpo), algo nuevo fuera del Cuerpo (otro
    Cuerpo, un croquis 3D, miembros de soldadura) no se vería en el componente. Se pasa la pieza a contenedor
    Parte (part_container.wrap), el componente apunta al contenedor en el mismo lugar, las relaciones de
    posición que lo tocan suman el nombre del Cuerpo a su camino y se sigue editando con el mismo Cuerpo.
    Devuelve el contenedor (o el que ya había), o None si no se edita.
    """
    from swui.fork import edit_part as ep
    from swui.fork import part_container as pc

    ctx = ctx or current()
    if ctx is None:
        return None
    if ctx.part.TypeId == "App::Part":
        return ctx.part
    body, link, asm = ctx.part, ctx.link, ctx.asm
    joints = []
    try:
        from swui.fork import mates_sw

        joints = mates_sw.joints_of(asm)
    except Exception:
        pass
    # todas las instancias de esa pieza en el ensamblaje (no solo la editada) pasan a apuntar al contenedor
    links = [o for o in asm.Document.Objects if getattr(o, "LinkedObject", None) is body] or [link]
    places = [(o, o.Placement) for o in links]
    part = pc.wrap(ctx.pdoc, save=False, transaction=False)
    for o, place in places:
        o.LinkedObject = part
        o.Placement = place
    for j in joints:
        for prop in ("Reference1", "Reference2"):
            ref = getattr(j, prop, None)
            if not ref or ref[0] not in links:
                continue
            subs = [s if s.startswith(body.Name + ".") else body.Name + "." + s for s in ref[1]]
            try:
                setattr(j, prop, (ref[0], subs))
            except Exception:
                log("Relación al pasar a contenedor")
    asm.Document.recompute()
    # seguir editando con el mismo Cuerpo, ahora por el camino del contenedor
    st = ep._editing.get(asm.Document.Name)
    if st is not None:
        try:
            ep._view(asm.Document).setActiveObject("pdbody", asm, ctx.prefix + body.Name + ".")
        except Exception:
            log("Editar pieza al pasar a contenedor")
    return part


def log(where):
    FreeCAD.Console.PrintLog("[SWUI fork] %s:\n%s\n" % (where, traceback.format_exc()))
