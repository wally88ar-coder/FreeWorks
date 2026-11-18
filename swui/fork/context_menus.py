# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Clic derecho como SOLIDWORKS 2018 (decisiones del usuario del 15/11, pestaña "Clic derecho como SW"
del documento de checklists y docs/ESTADO.md).

Qué hace, solo dentro de LikeSolidWorks UI:
- En la vista 3D, el clic derecho elige primero lo que está debajo del mouse (la cara, la arista, el
  componente), como SW. Si eso ya estaba elegido, la selección queda como estaba. Con un panel de
  tareas abierto o un croquis en edición no toca nada.
- Arma el menú con una TABLA por caso (operación en el árbol de la pieza, cara en la vista de la
  pieza, componente en el árbol del ensamblaje, cara de un componente en la vista): primero lo más
  usado (la "bandeja" de SW), después secciones con título en negrita ("Operación (Extruir1)",
  "Cara", "Componente (Taco)"). Todo lo que la tabla no nombra queda detrás de la "»" del pie (se
  despliega en el mismo menú), y lo que no sirve se quita.
- En los demás casos (un Cuerpo, un plano, varias cosas elegidas...) solo quita lo que no sirve y
  pasa detrás de la "»" lo de FreeCAD que SW no tiene (Colocación, Copiar/Pegar...).

Por debajo son las mismas acciones de FreeCAD y de FreeWorks: el menú solo las ordena. Las que
cambian de nombre (por ejemplo "Ir a la pieza" -> "Abrir pieza") son acciones nuevas que llaman a la
original, para no cambiarle el nombre en la barra de menús. Nada queda guardado en los archivos.

La parte que decide (qué caso es, qué va en cada lugar) son funciones sin interfaz, probadas en la
batería rápida; la parte de Qt arma el menú con esa decisión.
"""

import re
import time
import traceback

import FreeCAD
import FreeCADGui

# --- Claves de las acciones ------------------------------------------------------------------------
# Una acción del menú se reconoce por el nombre de su comando (objectName) o, las que FreeCAD arma sin
# comando, por su texto (en castellano o en inglés, según el idioma de FreeCAD).

TEXT_KEYS = {
    "renombrar": "rename", "rename": "rename",
    "aclarar selección": "clarify", "clarify selection": "clarify",
    "marcar para recalcular": "markrecompute", "mark to recompute": "markrecompute",
    "recalcular objeto": "recompute", "recompute object": "recompute",
    "acciones de expresión": "expr", "expression actions": "expr",
    "ajustes del árbol": "treesettings", "tree settings": "treesettings",
    "activar documento": "activatedoc", "activate document": "activatedoc",
    "mostrar en el árbol lo oculto": "showhidden", "show items hidden in tree view": "showhidden",
    "show hidden items": "showhidden",
    "alternar visibilidad en el árbol": "treevis", "toggle visibility in tree view": "treevis",
    "agregar dependientes a la selección": "adddeps", "add dependent objects to selection": "adddeps",
    "cuerpo activo": "activebody", "active body": "activebody",
    "objeto activo": "activeobj", "active object": "activeobj",
    "transformar": "vptransform", "transform": "vptransform",
    "sustituir colores": "overridecolors", "override colors": "overridecolors",
    "colores de caras": "facecolors", "set face colors": "facecolors",
    "draw style": "drawstyle", "estilo de dibujo": "drawstyle", "estilo de visualización": "drawstyle",
    "ventana de documento": "docwindow", "document window": "docwindow",
    "estilos de navegación": "navstyles", "navigation styles": "navstyles",
    "finalizar edición": "finishedit", "finish editing": "finishedit",
    "suprimido": "nativesuppressed", "suppressed": "nativesuppressed",
}

# Quitados de todos los menús (decisión del usuario, 15/11: "lo de FreeCAD que no sirve")
REMOVE = {
    "Std_SendToPythonConsole", "expr", "Link Actions", "markrecompute", "treesettings", "navstyles",
    "docwindow", "Std_RandomColor", "Std_ToggleFreeze",
    "SWUI_MoveUp", "SWUI_MoveDown",  # como SW: se reordena arrastrando en el árbol (tree_drag.py)
}
# Quitados cuando hay algo elegido (decisión 15/11: Zoom/Trasladar/Girar fuera, Zoom a selección
# y Normal a no). Con el menú del fondo vacío quedan: es lo único que tiene.
REMOVE_WITH_SELECTION = {
    "Std_ViewFitAll", "Std_ViewFitSelection", "Std_AlignToSelection", "drawstyle", "Standard Views",
}
# Lo de FreeCAD que SW no tiene: detrás de la "»" (decisión 15/11)
BEHIND = {
    "Std_Placement", "Std_Cut", "Std_Copy", "Std_Paste", "rename", "recompute", "Std_Properties",
    "vptransform", "Std_TransformManip", "Std_ToggleSelectability", "Std_TreeSelectAllInstances",
    "showhidden", "treevis", "adddeps", "activatedoc", "Std_SetMaterial", "facecolors",
    "overridecolors", "Std_TreeSelection", "Std_ToggleVisibility",
}

# Nombres como SW (la acción se copia con este texto; la original no cambia)
LABELS = {
    "clarify": "Seleccionar otra",
    "Std_LinkSelectLinked": "Abrir pieza",
    "Std_ToggleTransparency": "Cambiar transparencia",
    "Std_SetAppearance": "Apariencia",
    "Std_HideSelection": "Ocultar",
    "Std_ShowSelection": "Mostrar",
    "Std_Delete": "Eliminar",
    "rename": "Cambiar de nombre",
    "PartDesign_NewSketch": "Croquis",
    "PartDesign_Fillet": "Redondeo",
    "PartDesign_Chamfer": "Chaflán",
    "SWUI_ConfigureFeature": "Configurar operación",
    "SWUI_ComponentConfig": "Configurar componente",
    "SWUI_DeleteBodies": "Eliminar...",  # DELETE_BODIES
}

# Comandos de FreeWorks (feature_tree, mates_sw, config_asm) por nombre, sin importar esos módulos
EDIT, EDIT_SKETCH = "SWUI_EditFeature", "SWUI_EditSketch"
SUPPRESS, UNSUPPRESS, UNSUPPRESS_ALL = "SWUI_Suppress", "SWUI_Unsuppress", "SWUI_UnsuppressWithChildren"
ROLLBACK, ROLL_FORWARD, ROLL_END = "SWUI_Rollback", "SWUI_RollForward", "SWUI_RollToEnd"
PARENT_CHILD, REPAIR = "SWUI_ParentChild", "SWUI_RepairReferences"
MATE, VIEW_MATES, FIX, FLOAT = "SWUI_Mate", "SWUI_ViewMates", "SWUI_FixComponent", "SWUI_FloatComponent"
COMP_SUPPRESS, COMP_UNSUPPRESS, COMP_CONFIG = ("SWUI_ComponentSuppress", "SWUI_ComponentUnsuppress",
                                               "SWUI_ComponentConfig")
HIDE_OR_SHOW = "hide_or_show"  # Ocultar u Mostrar, según esté a la vista lo elegido
# Herramientas propias del clic derecho (context_tools.py, etapa C)
COLLAPSE, INVERT, ISOLATE = "SWUI_CollapseTree", "SWUI_InvertSelection", "SWUI_Isolate"
RENAME_COMP, COMP_PROPS, COMP_PARENT = "SWUI_RenameComponent", "SWUI_ComponentProperties", "SWUI_ComponentParentChild"
COMP_MATERIAL, TANGENT, FACE_DXF = "SWUI_ComponentMaterial", "SWUI_SelectTangent", "SWUI_ExportFaceDXF"
OPEN_POS = "SWUI_OpenPartInPosition"
OPEN_PARTS = "SWUI_OpenParts"  # Abrir pieza con varios componentes elegidos (E1)
DELETE_BODIES = "SWUI_DeleteBodies"  # Sólido > Eliminar... con caras de varias operaciones (E2)
# Editar la pieza dentro del ensamblaje (etapa D, edit_part.py)
EDIT_PART, EDIT_IN_ASM, EDIT_SKETCH_IN_ASM = "SWUI_EditPart", "SWUI_EditPartFeature", "SWUI_EditPartSketch"
SELECTION_TOOLS = "submenu:selection"  # Herramientas de selección ▸

# Íconos de la bandeja para lo que no trae ícono (propios, tools/fork/make_icons_fork.py; nada de SW)
TRAY_ICONS = {
    EDIT: "fork/t_edit_feature", EDIT_SKETCH: "fork/t_edit_sketch", SUPPRESS: "fork/t_suppress",
    UNSUPPRESS: "fork/t_unsuppress", UNSUPPRESS_ALL: "fork/t_unsuppress", ROLLBACK: "fork/t_rollback",
    ROLL_FORWARD: "fork/t_roll_forward", ROLL_END: "fork/t_roll_end", "clarify": "fork/t_select_other",
    VIEW_MATES: "fork/t_view_mates", "Std_ToggleTransparency": "fork/t_transparency",
    "Std_LinkSelectLinked": "fork/t_open_part", COMP_SUPPRESS: "fork/t_suppress",
    COMP_UNSUPPRESS: "fork/t_unsuppress", MATE: "sketch/m_coincident", OPEN_POS: "fork/t_open_part_pos",
    COMP_PROPS: "fork/t_properties", OPEN_PARTS: "fork/t_open_part",
    EDIT_PART: "fork/t_edit_part", EDIT_IN_ASM: "fork/t_edit_feature", EDIT_SKETCH_IN_ASM: "fork/t_edit_sketch",
    "PartDesign_NewSketch": "sketch/sketch_new", "PartDesign_Fillet": "sketch/f_fillet",
    "PartDesign_Chamfer": "sketch/f_chamfer",
}
TRAY_COLUMNS = 8  # íconos por fila, como la bandeja de SW

# Lo que actúa sobre la operación del título: con una cara elegida en la vista, antes de correrlo se
# elige esa operación (la que creó la cara, como SW). Sin esto, Suprimir/Eliminar/Retroceder actuaban
# sobre la última operación del sólido aunque el título dijera otra (revisión del 15/11).
ON_FEATURE = {EDIT, EDIT_SKETCH, SUPPRESS, UNSUPPRESS, UNSUPPRESS_ALL, ROLLBACK, ROLL_FORWARD, ROLL_END,
              PARENT_CHILD, REPAIR, "SWUI_ConfigureFeature", "Std_Delete"}

# Comandos que la tabla puede pedir aunque FreeCAD no los haya puesto en el menú
FETCHABLE = {COLLAPSE, INVERT, ISOLATE, RENAME_COMP, COMP_PROPS, COMP_PARENT, COMP_MATERIAL, FACE_DXF,
             OPEN_POS, OPEN_PARTS, EDIT_PART, EDIT_IN_ASM, EDIT_SKETCH_IN_ASM, SELECTION_TOOLS, "PartDesign_NewSketch", "PartDesign_Fillet", "PartDesign_Chamfer", "SWUI_ConfigureFeature",
             "Std_HideSelection", "Std_ShowSelection", "Std_SetAppearance", "Std_ToggleTransparency",
             "Std_Delete", "Std_LinkSelectLinked", MATE, VIEW_MATES}

# Con varios elegidos FreeCAD (y los menús de FreeWorks) no ponen estos comandos: se piden (E1)
FETCH_MANY = {COMP_SUPPRESS, COMP_UNSUPPRESS, COMP_CONFIG, FIX, FLOAT, SUPPRESS, UNSUPPRESS, UNSUPPRESS_ALL,
              DELETE_BODIES}

ELEMENT = re.compile(r"^(Face|Edge|Vertex)\d+$")
ELEMENT_NAMES = {"Face": "Cara", "Edge": "Arista", "Vertex": "Vértice"}
ELEMENTS_NAMES = {"Face": "Caras", "Edge": "Aristas", "Vertex": "Vértices"}


def action_key(object_name, text):
    """Clave de una acción del menú: su comando, o su texto conocido; si no, 'txt:<texto>'."""
    if object_name:
        return object_name
    plain = (text or "").replace("&", "").split("\t")[0].strip()
    low = plain.lower()
    if low in TEXT_KEYS:
        return TEXT_KEYS[low]
    if low.startswith("editar ") or low.startswith("edit "):
        return "vpedit"  # "Editar Pad": el editar de FreeCAD, repite nuestro Editar operación
    return "txt:" + plain


# --- Qué caso es -----------------------------------------------------------------------------------


class Context:
    """
    Lo elegido, visto como SW: kind = 'feature' | 'sketch' | 'component' | 'components' | 'features'
    | None. 'components' = dos o más componentes elegidos (etapa E1, 15/11): components tiene la lista.
    'features' = dos o más operaciones del mismo Cuerpo, o caras de ellas en la vista (etapa E2):
    features tiene las operaciones (las que crearon las caras), sin repetir.
    """

    def __init__(self, kind=None, feature=None, component=None, element="", visible=True, planar=False,
                 components=None, features=None):
        self.kind = kind
        self.feature = feature  # la operación (o el croquis)
        self.component = component  # el vínculo dentro del ensamblaje
        self.element = element  # 'Face6' / 'Edge3' / '' (todo el objeto)
        self.visible = visible
        self.planar = planar  # la cara elegida es plana (para "Croquis")
        self.components = list(components or [])
        self.features = list(features or [])

    @property
    def element_kind(self):
        m = ELEMENT.match(self.element or "")
        return m.group(1) if m else ""


def _is_feature(obj):
    try:
        return bool(obj.isDerivedFrom("PartDesign::Feature"))
    except Exception:
        return False


def _is_sketch(obj):
    try:
        return bool(obj.isDerivedFrom("Sketcher::SketchObject"))
    except Exception:
        return False


def _body_of(obj):
    try:
        group = obj.getParentGeoFeatureGroup()
    except Exception:
        return None
    return group if group is not None and getattr(group, "TypeId", "") == "PartDesign::Body" else None


def _is_component(obj, parent):
    return (getattr(obj, "TypeId", "") in ("App::Link", "Assembly::AssemblyLink")
            and getattr(parent, "TypeId", "") == "Assembly::AssemblyObject")


def _chain(top, sub):
    """Los objetos del camino de selección: [top, hijo, nieto...] (sin el elemento final)."""
    out = [top]
    try:
        out += [o for o in top.getSubObjectList(sub)[1:] if o is not None]
    except Exception:
        pass
    return out


def component_of(top, sub):
    """El componente (vínculo de un ensamblaje) por el que pasa la selección (top, sub), o None."""
    chain = _chain(top, sub)
    for parent, child in zip(chain, chain[1:]):
        if _is_component(child, parent):
            return child
    if _is_component(top, top.InList[0] if getattr(top, "InList", None) else None):
        return top
    return None


def feature_of(top, sub):
    """
    (operación, elemento) de la selección (top, sub): la operación de Part Design elegida, o la que
    creó la cara elegida en la vista (como SW). (None, '') si no es una operación de un Cuerpo.
    """
    element = sub.split(".")[-1] if ELEMENT.match(sub.split(".")[-1] or "") else ""
    last = _chain(top, sub)[-1]
    if element and getattr(last, "TypeId", "") == "PartDesign::Body":
        last = last.Tip  # 'Body.Face5': la cara del sólido, o sea de la punta
    if not _is_feature(last) or _body_of(last) is None:
        return None, ""
    if element.startswith("Face") or element.startswith("Edge"):
        try:
            import Part

            from swui.fork import feature_tree as ft

            shape = last.Shape
            sub_shape = shape.getElement(element)
            if element.startswith("Face"):
                return ft.creator(last, sub_shape) or last, element
            # la arista nace con la última de las operaciones que hicieron sus caras (el borde del
            # agujero es del corte, no de la extrusión que hizo la tapa)
            order = ft.features(_body_of(last))
            makers = [ft.creator(last, f) or last for f in shape.ancestorsOfType(sub_shape, Part.Face)]
            makers = [m for m in makers if m in order]
            return (max(makers, key=order.index) if makers else last), element
        except Exception:
            return last, element
    return last, element


def _several_features(pairs):
    """Varias operaciones del mismo Cuerpo (o caras de ellas en la vista): Context('features') (E2)."""
    feats, elements = [], []
    for top, sub in pairs:
        if component_of(top, sub) is not None:
            return Context()
        feat, element = feature_of(top, sub)
        if feat is None:
            return Context()  # un croquis, un plano, otra cosa: el menú general
        elements.append(element)
        if feat not in feats:
            feats.append(feat)
    bodies = {_body_of(f).Name for f in feats}
    if len(bodies) != 1:
        return Context()
    kinds = {ELEMENT.match(e).group(1) for e in elements if ELEMENT.match(e)}
    # con algún elemento (cara, arista) es el menú de la vista y lo de la operación elige antes las
    # operaciones; cara + arista mezcladas: grupo "Elementos" (revisión del 15/11)
    element = next((e for e in elements if e), "")
    body = _body_of(feats[0])
    ctx = Context("features", feature=feats[0], features=feats, element=element,
                  visible=bool(getattr(body, "Visibility", True)))
    ctx.mixed = len(kinds) > 1
    return ctx


def _several(pairs):
    """
    Varias cosas elegidas: Context de componentes (E1), de operaciones (E2) o Context() si se mezcla
    con otra cosa.
    """
    comps = []
    for top, sub in pairs:
        comp = component_of(top, sub)
        if comp is None:
            return _several_features(pairs) if not comps else Context()
        if comp not in comps:
            comps.append(comp)
    visible = all(bool(getattr(c, "Visibility", True)) for c in comps)
    if len(comps) == 1:  # dos caras del mismo componente: el menú de ese componente
        ctx = Context("component", component=comps[0], visible=visible)
        ctx.many = True  # el "Abrir pieza" de FreeCAD no anda con dos caras elegidas: va el propio
        return ctx
    return Context("components", components=comps, visible=visible)


def context_of(entries):
    """
    entries: [(objeto de arriba, [subnombres])] como da getSelectionEx("", 0).
    Un solo objeto elegido (con a lo sumo un elemento) -> Context del caso; varios componentes ->
    Context('components'); si no, Context() (caso general).
    """
    pairs = [(top, sub) for top, subs in entries for sub in (list(subs or []) or [""])]
    if not pairs:
        return Context()
    if len(pairs) > 1:
        return _several(pairs)
    top, sub = pairs[0]
    element = sub.split(".")[-1] if ELEMENT.match(sub.split(".")[-1] or "") else ""
    chain = _chain(top, sub)
    # componente de un ensamblaje: el primer vínculo que cuelga de un ensamblaje
    for parent, child in zip(chain, chain[1:]):
        if _is_component(child, parent):
            return Context("component", component=child, element=element,
                           visible=bool(getattr(child, "Visibility", True)))
    if _is_component(top, top.InList[0] if getattr(top, "InList", None) else None):
        return Context("component", component=top, visible=bool(getattr(top, "Visibility", True)))
    last = chain[-1]
    if (_is_feature(last) or _is_sketch(last)) and _body_of(last) is not None:
        feature = last
        planar = False
        if element and _is_feature(last):
            try:
                face = last.Shape.getElement(element)
                if element.startswith("Face"):
                    planar = face.Surface.__class__.__name__ == "Plane"
                from swui.fork import feature_tree as ft

                feature = ft.creator(last, face) or last if element.startswith("Face") else last
            except Exception:
                pass
        body = _body_of(last)
        visible = bool(getattr(body, "Visibility", True)) if body is not None else True
        return Context("sketch" if _is_sketch(feature) else "feature", feature=feature, element=element,
                       visible=visible, planar=planar)
    return Context()


def title_of(ctx):
    """Título de la sección principal, como SW: 'Operación (Extruir1)', 'Componente (Taco)'."""
    if ctx.kind == "component":
        linked = getattr(ctx.component, "LinkedObject", None)
        name = None
        try:
            if linked is not None and linked.Document is not ctx.component.Document:
                name = linked.Document.Label
            elif linked is not None:
                name = linked.Label
        except Exception:
            name = None
        return "Componente (%s)" % (name or ctx.component.Label)
    if ctx.kind == "components":
        return "Componente"  # SW, con varios: sin nombre
    if ctx.kind == "features":
        return "Operaciones"  # SW, con varias
    if ctx.kind == "sketch":
        return "Croquis (%s)" % ctx.feature.Label
    if ctx.kind == "feature":
        return "Operación (%s)" % ctx.feature.Label
    return None


def layout(ctx, where):
    """
    La tabla para este caso: [(título o None, [claves])]. El primer grupo, sin título, es la
    bandeja de SW (lo más usado). where = 'Tree' | 'View'.
    """
    view = where == "View"
    hide = HIDE_OR_SHOW
    if ctx.kind in ("feature", "sketch"):
        roll = [SUPPRESS, UNSUPPRESS, UNSUPPRESS_ALL, ROLLBACK, ROLL_FORWARD, ROLL_END]
        if ctx.kind == "sketch":
            tray = [EDIT_SKETCH] + roll + [hide]
            return [(None, tray), (title_of(ctx), [PARENT_CHILD, "Std_Delete"])]
        if view and ctx.element:
            tray = [EDIT, EDIT_SKETCH] + roll + ["Std_SetAppearance", "clarify"]
            top = [SELECTION_TOOLS] if ctx.element_kind == "Face" else []
            if ctx.element_kind == "Face" and ctx.planar:
                tray.append("PartDesign_NewSketch")
            tray.append(hide)
            if ctx.element_kind in ("Face", "Edge"):
                tray += ["PartDesign_Fillet", "PartDesign_Chamfer"]
            solid = [ISOLATE] + ([FACE_DXF] if ctx.element_kind == "Face" and ctx.planar else [])
            return [(None, tray), (None, top),
                    (ELEMENT_NAMES.get(ctx.element_kind), ["Std_ToggleTransparency"]),
                    (title_of(ctx), [PARENT_CHILD, "SWUI_ConfigureFeature", "Std_Delete", REPAIR]),
                    ("Sólido", solid)]
        tray = [EDIT, EDIT_SKETCH] + roll + [hide, "Std_SetAppearance"]
        return [(None, tray),
                (title_of(ctx), [PARENT_CHILD, "SWUI_ConfigureFeature", "Std_Delete", "Std_ToggleTransparency",
                                 REPAIR, COLLAPSE])]
    if ctx.kind == "component":
        edit_face = [EDIT_IN_ASM, EDIT_SKETCH_IN_ASM] if view and ctx.element_kind == "Face" else []
        tray = (["clarify"] if view else []) + edit_face + [
            OPEN_PARTS if getattr(ctx, "many", False) else "Std_LinkSelectLinked", OPEN_POS, EDIT_PART, hide, "Std_ToggleTransparency", COMP_SUPPRESS, COMP_UNSUPPRESS, MATE,
            VIEW_MATES, COMP_PROPS, "Std_SetAppearance"]
        top = [INVERT] + ([SELECTION_TOOLS] if view and ctx.element_kind == "Face" else [])
        comp = ([RENAME_COMP] if view else ["rename"]) + [ISOLATE, COMP_CONFIG, FIX, FLOAT, "Std_Delete",
                                                          COMP_PARENT, COMP_MATERIAL]
        if not view:
            comp.append(COLLAPSE)
        return [(None, tray), (None, top), (title_of(ctx), comp)]
    if ctx.kind == "components":
        # varios componentes (E1, decisiones del usuario 15/11): sin Editar pieza, Propiedades,
        # Cambiar de nombre ni Padre/Hijo; cada opción actúa sobre todos los elegidos
        tray = [OPEN_PARTS, OPEN_POS, hide, "Std_ToggleTransparency", COMP_SUPPRESS, COMP_UNSUPPRESS, MATE,
                VIEW_MATES, "Std_SetAppearance"]
        comp = [ISOLATE, COMP_CONFIG, FIX, FLOAT, "Std_Delete", COMP_MATERIAL] + ([] if view else [COLLAPSE])
        return [(None, tray), (None, [INVERT]), (title_of(ctx), comp)]
    if ctx.kind == "features":
        # varias operaciones (E2, decisiones del usuario 15/11): sin Editar operación/croquis,
        # Retroceder, Ocultar (en el árbol) ni Padre/Hijo; Redondeo/Chaflán/Mover cara con varias: no
        if view and ctx.element:
            tray = ["clarify", hide, SUPPRESS, UNSUPPRESS, "Std_SetAppearance"]
            group = "Elementos" if getattr(ctx, "mixed", False) else ELEMENTS_NAMES.get(ctx.element_kind)
            return [(None, tray), (group, ["Std_ToggleTransparency"]),
                    (title_of(ctx), ["SWUI_ConfigureFeature", "Std_Delete"]),
                    ("Sólido", [ISOLATE, DELETE_BODIES])]
        tray = [SUPPRESS, UNSUPPRESS, UNSUPPRESS_ALL, "Std_SetAppearance"]
        return [(None, tray), (None, [INVERT]),
                (title_of(ctx), ["SWUI_ConfigureFeature", "Std_Delete", "Std_ToggleTransparency", COLLAPSE])]
    return []


def hide_key(ctx):
    return "Std_HideSelection" if ctx.visible else "Std_ShowSelection"


def place(keys, ctx, where, has_selection=True):
    """
    Decide el menú: keys = claves de las acciones que trajo FreeCAD, en orden.
    Devuelve (grupos [(título, [claves])], detrás [claves], quitadas [claves]).
    Las claves de los grupos que no vinieron en el menú son comandos para pedir (FETCHABLE).
    """
    removed = [k for k in keys if k in REMOVE or (has_selection and k in REMOVE_WITH_SELECTION)]
    table = layout(ctx, where)
    if not table:  # caso general: solo quitar y mandar atrás lo de FreeCAD
        behind = [k for k in keys if k in BEHIND and k not in removed] if has_selection else []
        return [], behind, removed
    ours = {EDIT, EDIT_SKETCH, SUPPRESS, UNSUPPRESS}
    if ours & set(keys) or ctx.kind in ("feature", "sketch", "features"):
        removed += [k for k in keys if k in ("vpedit", "nativesuppressed") and k not in removed]
    groups, used = [], set(removed)
    for title, wanted in table:
        out = []
        for k in wanted:
            if k == HIDE_OR_SHOW:
                k = hide_key(ctx)
            if k in used:
                continue
            if k in keys or k in FETCHABLE or (ctx.kind in ("components", "features") and k in FETCH_MANY):
                out.append(k)
                used.add(k)
        if out:
            groups.append((title, out))
    behind = [k for k in keys if k not in used]
    return groups, behind, removed


# --- Interfaz -----------------------------------------------------------------------------------------

_last = {"where": None, "t": 0.0}
last_decision = {}  # lo que decidió el último menú (para las pruebas y el diagnóstico)
WINDOW = 1.5  # segundos entre el clic derecho y el menú


def _in_workbench():
    try:
        from swui.fork import feature_tree

        return feature_tree._in_workbench()
    except Exception:
        return False


def _busy():
    """¿Hay un panel de tareas abierto o algo en edición (croquis...)? Ahí no se toca nada."""
    try:
        if FreeCADGui.Control.activeDialog():
            return True
        gdoc = FreeCADGui.ActiveDocument
        editing = gdoc.getInEdit() if gdoc is not None else None
        if editing is None:
            return False
        # el ensamblaje activo está "en edición" para FreeCAD (así se activa): eso no cuenta
        kind = "%s %s %s" % (getattr(editing, "TypeId", ""), type(editing).__name__,
                             getattr(getattr(editing, "Object", None), "TypeId", ""))
        return "Assembly" not in kind
    except Exception:
        return True


def widget_kind(w):
    """'Tree' si w es el árbol de FreeCAD, 'View' si es la vista 3D; si no, None."""
    try:
        for _i in range(5):
            if w is None:
                return None
            name = w.metaObject().className()
            if name == "Gui::TreeWidget":
                return "Tree"
            if name == "Gui::View3DInventor":
                return "View"
            w = w.parent()
    except Exception:
        return None
    return None


def selection_entries():
    try:
        return [(s.Object, list(s.SubElementNames)) for s in FreeCADGui.Selection.getSelectionEx("", 0)]
    except Exception:
        return []


def plain_sub(sub):
    """'Extruir.;#14:1;:G0;XTR;:H55e:8,F.Face6' -> 'Extruir.Face6' (sin el nombre topológico de FreeCAD)."""
    return ".".join(p for p in (sub or "").split(".") if not p.startswith(";"))


def same_element(obj, sub_a, sub_b):
    """
    ¿Las dos selecciones (de obj) son el mismo elemento? FreeCAD nombra la misma cara de dos maneras
    según el camino: por el Cuerpo ('Body003.Body.Face6') o por la operación ('Body003.Caja.Face6')
    (visto el 15/11 con dos componentes elegidos). Mismo componente de arriba, mismo tipo de elemento
    y la misma forma en el mismo lugar.
    """
    a, b = plain_sub(sub_a), plain_sub(sub_b)
    if a == b:
        return True
    ea, eb = a.split(".")[-1], b.split(".")[-1]
    ka, kb = ELEMENT.match(ea), ELEMENT.match(eb)
    if not ka or not kb or ka.group(1) != kb.group(1):
        return False
    # en un ensamblaje, el primer nombre es el componente: tiene que ser el mismo (en una pieza puede
    # faltar: 'Face5' por el Cuerpo y 'Corte2.Face5' por la operación son la misma cara)
    pa, pb = a.split("."), b.split(".")
    if len(pa) > 1 and len(pb) > 1 and pa[0] != pb[0]:
        return False
    try:
        sa, sb = obj.getSubObject(sub_a), obj.getSubObject(sub_b)
        if sa is None or sb is None or sa.ShapeType != sb.ShapeType:
            return False
        if sa.isSame(sb):
            return True
        if ka.group(1) == "Vertex":
            return sa.Point.distanceToPoint(sb.Point) < 1e-7
        size = (lambda s: s.Area) if ka.group(1) == "Face" else (lambda s: s.Length)
        return (abs(size(sa) - size(sb)) < 1e-7 * max(1.0, size(sa))
                and sa.CenterOfMass.distanceToPoint(sb.CenterOfMass) < 1e-7 * max(1.0, sa.BoundBox.DiagonalLength))
    except Exception:
        return False


def pick_under_cursor():
    """
    Como SW: el clic derecho en la vista elige lo que está debajo del mouse. Si ya estaba elegido,
    la selección queda igual (varias cosas elegidas siguen elegidas). Devuelve True si cambió.
    """
    if _busy():
        return False
    try:
        pre = FreeCADGui.Selection.getPreselection()
    except Exception:
        return False
    if pre is None or not pre.DocumentName or not pre.ObjectName:
        return False
    sub = (list(pre.SubElementNames) or [""])[0]
    sels = FreeCADGui.Selection.getSelectionEx("", 0)
    several = sum(len(list(s.SubElementNames) or [""]) for s in sels) > 1
    for s in sels:
        if (s.DocumentName, s.ObjectName) != (pre.DocumentName, pre.ObjectName):
            continue
        for chosen in (list(s.SubElementNames) or [""]):
            if same_element(s.Object, chosen, sub):
                return False
            # varios objetos enteros elegidos en el árbol ('Placa.', 'Bloque.') y el mouse sobre una cara
            # de uno de ellos: ya está elegido, quedan todos (revisión del 15/11, E1). Con uno solo, la
            # cara pasa a ser lo elegido, como antes.
            whole = plain_sub(chosen)
            if several and whole.endswith(".") and plain_sub(sub).startswith(whole):
                return False
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(pre.DocumentName, pre.ObjectName, sub)
    return True


def on_event(obj, event):
    """Desde el filtro de la aplicación (feature_tree._MenuShow): clic derecho y menú del teclado."""
    from swui.compat import QtCore

    t = event.type()
    if t == QtCore.QEvent.Type.MouseButtonPress:
        if event.button() != QtCore.Qt.MouseButton.RightButton:
            # cualquier otro clic (la cinta, una barra...) cancela un clic derecho que no abrió menú:
            # si no, el menú de esa barra se armaba como clic derecho (revisión del 15/11)
            _last["where"] = None
            return
        where = widget_kind(obj)
        if where is None:
            return
        _last.update(where=where, t=time.time())
        if where == "View":
            try:
                pick_under_cursor()
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Clic derecho:\n%s\n" % traceback.format_exc())
    elif t == QtCore.QEvent.Type.ContextMenu:
        where = widget_kind(obj)
        if where is not None:
            _last.update(where=where, t=time.time())


def _QAction():
    from swui.compat import QtGui, QtWidgets

    return getattr(QtGui, "QAction", None) or QtWidgets.QAction  # Qt6 / Qt5


def select_feature(feature):
    """Deja elegida la operación entera (como en el árbol), para que los comandos actúen sobre ella."""
    select_features([feature])


def select_features(features):
    """Deja elegidas las operaciones enteras (varias: E2), para que los comandos actúen sobre ellas."""
    FreeCADGui.Selection.clearSelection()
    for feature in features:
        body = _body_of(feature)
        if body is not None:
            FreeCADGui.Selection.addSelection(feature.Document.Name, body.Name, feature.Name + ".")
        else:
            FreeCADGui.Selection.addSelection(feature)


def active_for_features(features, names):
    """
    ¿Qué comandos de la operación valen para estas operaciones? (E2: con caras elegidas en la vista,
    Suprimir todavía no ve las operaciones, que se eligen recién al hacer clic). Se decide mirando las
    operaciones, sin tocar la selección (revisión del 15/11).
    """
    def suppressed(f):
        return bool(getattr(f, "Suppressed", False))
    out = set()
    for n in names:
        if n == SUPPRESS and any(not suppressed(f) for f in features):
            out.add(n)
        elif n in (UNSUPPRESS, UNSUPPRESS_ALL) and any(suppressed(f) for f in features):
            out.add(n)
        elif n == "SWUI_ConfigureFeature":
            try:
                from swui.fork import configurations as cf

                if features and cf.configured(features[0].Document):
                    out.add(n)
            except Exception:
                pass
        elif n not in (SUPPRESS, UNSUPPRESS, UNSUPPRESS_ALL):
            out.add(n)
    return out


def _command_action(name, menu, text=None, before=None, active=None):
    """
    Una acción nueva que corre el comando (para ponerlo aunque FreeCAD no lo haya puesto). active:
    si se sabe de antemano si queda activo (con before), en vez de preguntarle al comando ahora.
    """
    try:
        cmd = FreeCADGui.Command.get(name)
    except Exception:
        cmd = None
    if cmd is None:
        return None
    try:
        if not (cmd.isActive() if active is None else active):
            return None
    except Exception:
        pass
    icon = None
    try:
        acts = cmd.getAction()
        if acts:
            icon = acts[0].icon()
            text = text or acts[0].text()
    except Exception:
        pass
    if not text:
        try:
            text = cmd.getInfo().get("menuText") or None
        except Exception:
            text = None
    act = _QAction()(text or name, menu)
    if icon is not None:
        act.setIcon(icon)
    act.setObjectName("SWUI_cm_" + name)

    def run(_checked=False, n=name):
        if before is not None:
            before()
        FreeCADGui.runCommand(n)
    act.triggered.connect(run)
    return act


def _is_command(name):
    try:
        return bool(name) and FreeCADGui.Command.get(name) is not None
    except Exception:
        return False


def _enabled(original):
    """
    ¿Se puede usar? Para un comando se le pregunta en el momento: FreeCAD actualiza el estado de sus
    acciones con un temporizador y, justo después de que el clic derecho eligió la cara, la acción
    todavía figura deshabilitada (visto el 15/11: Suprimir salía gris y no hacía nada).
    """
    name = original.objectName()
    if _is_command(name):
        try:
            return bool(FreeCADGui.Command.get(name).isActive())
        except Exception:
            pass
    return original.isEnabled()


def _copy_action(original, text, menu, before=None):
    """
    Una copia de la acción que llama a la original. Las acciones de FreeCAD son COMPARTIDAS (la misma
    está en la barra de menús, en las barras de herramientas y en el próximo clic derecho): cambiarles
    el texto o esconderlas las cambiaría en todos lados (visto el 15/11: "Copiar" y "Renombrar"
    quedaban ocultos en el clic derecho siguiente). Por eso se copia y la original no se toca.
    """
    act = _QAction()(original.icon(), text or original.text(), menu)
    act.setEnabled(_enabled(original))
    act.setObjectName("SWUI_cm_" + (original.objectName() or (text or original.text()).replace("&", "")))
    if original.menu() is not None:
        act.setMenu(original.menu())
        return act
    if original.isCheckable():
        act.setCheckable(True)
        act.setChecked(original.isChecked())

    def run(_checked=False, a=original):
        if before is not None:
            before()
            # recién elegida, FreeCAD todavía no volvió a habilitar la acción original (lo hace con
            # un temporizador): se corre el comando, que mira la selección en el momento
            name = a.objectName()
            if name and name.replace("_", "").isalnum():
                try:
                    FreeCADGui.runCommand(name)
                    return
                except Exception:
                    pass
        a.trigger()
    act.triggered.connect(run)
    return act


def _title_action(menu, text, first):
    from swui.compat import QtWidgets

    label = QtWidgets.QLabel(text)
    label.setObjectName("SWUI_cm_title")
    border = "" if first else "border-top: 1px solid #d4d4d4;"
    label.setStyleSheet("QLabel { font-weight: bold; color: #000; padding: 3px 8px 3px 8px; %s }" % border)
    act = QtWidgets.QWidgetAction(menu)
    act.setDefaultWidget(label)
    act.setObjectName("SWUI_cm_title")
    act.setEnabled(False)  # un clic en el título no cierra el menú (el color negro lo fija la hoja de estilo)
    return act


def _more_action(menu, hidden):
    """La "»" del pie: muestra en el mismo menú lo que estaba detrás."""
    from swui.compat import QtCore, QtWidgets

    button = QtWidgets.QToolButton()
    button.setObjectName("SWUI_cm_more")
    button.setText("»")
    button.setToolTip("Más opciones")
    button.setAutoRaise(True)
    button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
    button.setStyleSheet("QToolButton { border: none; padding: 1px; font-size: 13px; color: #333; }"
                         "QToolButton:hover { background: #e5f1fb; }")
    act = QtWidgets.QWidgetAction(menu)
    act.setDefaultWidget(button)
    act.setObjectName("SWUI_cm_more")

    def expand():
        for a in hidden:
            a.setVisible(True)
        act.setVisible(False)
        menu.adjustSize()
        _fit_on_screen(menu)

    button.clicked.connect(lambda _c=False: QtCore.QTimer.singleShot(0, expand))
    act.setProperty("swui_expand", True)
    act._swui_expand = expand  # para las pruebas
    return act


def _fit_on_screen(menu):
    from swui.compat import QtGui

    try:
        screen = QtGui.QGuiApplication.screenAt(menu.geometry().center()) or QtGui.QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        geo = menu.geometry()
        if geo.bottom() > area.bottom():
            menu.move(geo.left(), max(area.top(), area.bottom() - geo.height()))
    except Exception:
        pass


def expand(menu):
    """Despliega la "»" (para las pruebas y el teclado). True si había algo detrás."""
    for a in menu.actions():
        if a.objectName() == "SWUI_cm_more" and a.isVisible():
            a._swui_expand() if hasattr(a, "_swui_expand") else a.defaultWidget().click()
            return True
    return False


def _tray_action(menu, items):
    """
    La bandeja de SW: una fila de íconos arriba del menú. items = [(clave, acción)]. Cada ícono hace
    lo mismo que la acción (la copia, que ya sabe elegir la operación del título) y dice su nombre al
    pasar el mouse; gris si no se puede usar.
    """
    from swui import paths
    from swui.compat import QtCore, QtGui, QtWidgets

    box = QtWidgets.QWidget()
    box.setObjectName("SWUI_cm_tray")
    box.setStyleSheet("#SWUI_cm_tray { background: transparent; }"
                      "QToolButton { border: 1px solid transparent; border-radius: 2px; padding: 2px; }"
                      "QToolButton:hover { border-color: #7eb4ea; background: #e5f1fb; }")
    grid = QtWidgets.QGridLayout(box)
    grid.setContentsMargins(2, 1, 2, 1)  # casi sin huecos: un clic entre íconos cerraba el menú sin hacer nada
    grid.setSpacing(0)
    act = QtWidgets.QWidgetAction(menu)
    act.setObjectName("SWUI_cm_tray")
    for i, (key, a) in enumerate(items):
        button = QtWidgets.QToolButton(box)
        button.setObjectName("SWUI_cm_tray_" + key)
        icon = a.icon()
        own = TRAY_ICONS.get(key)
        if (icon is None or icon.isNull()) and own and paths.icon(own):
            icon = QtGui.QIcon(paths.icon(own))
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(20, 20))
        button.setAutoRaise(True)
        text = a.text().replace("&", "")
        button.setToolTip(text)
        button.setAccessibleName(text)
        button.setEnabled(a.isEnabled())
        button.setProperty("swui_text", text)

        def click(_c=False, a=a):
            menu.hide()  # como un ícono de SW: se cierra el menú y se hace
            a.trigger()
        button.clicked.connect(click)
        grid.addWidget(button, i // TRAY_COLUMNS, i % TRAY_COLUMNS)
    act.setDefaultWidget(box)
    return act


def _selection_menu(menu, by_key):
    """Herramientas de selección ▸ (como SW): Seleccionar otra y Seleccionar tangencia."""
    from swui.compat import QtWidgets

    sub = QtWidgets.QMenu("Herramientas de selección", menu)
    sub.setObjectName("SWUI_cm_selection")
    if "clarify" in by_key:
        sub.addAction(_copy_action(by_key["clarify"], LABELS["clarify"], sub))
    tangent = _command_action(TANGENT, sub)
    if tangent is not None:
        sub.addAction(tangent)
    if sub.isEmpty():
        return None
    act = sub.menuAction()
    act.setObjectName("SWUI_cm_selection")
    return act


def _menu_parent_ok(menu):
    """Solo el menú del clic derecho: sin padre (el del árbol) o hijo del árbol o la vista 3D."""
    parent = menu.parent()
    return parent is None or widget_kind(parent) is not None


def arrange(menu):
    """
    Arma el menú del clic derecho (el árbol o la vista) con la tabla. True si lo arregló (lo viejo de
    feature_tree ya no hace falta); False si no es un clic derecho del árbol o la vista.
    """
    if not _in_workbench() or menu.property("swui_cm"):
        return False
    where = _last["where"]
    if where is None or time.time() - _last["t"] > WINDOW or not _menu_parent_ok(menu):
        return False
    _last["where"] = None
    menu.setProperty("swui_cm", True)
    if _busy():
        return False  # croquis en edición o panel abierto: el menú es el de FreeCAD, sin tocar
    entries = selection_entries()
    ctx = context_of(entries)
    acts = [a for a in menu.actions()]
    by_key, keys = {}, []
    for a in acts:
        if a.isSeparator() or not a.isVisible():
            continue
        k = action_key(a.objectName(), a.text())
        if k not in by_key:
            by_key[k] = a
            keys.append(k)
    groups, behind, removed = place(keys, ctx, where, has_selection=bool(entries))
    last_decision.clear()
    last_decision.update(where=where, kind=ctx.kind, keys=keys, groups=groups, behind=behind, removed=removed)
    if not groups:
        _arrange_general(menu, acts, by_key, behind, removed)
        return True
    # con una cara elegida en la vista, lo de la operación elige antes la operación del título
    before = None
    if ctx.kind in ("feature", "sketch") and ctx.element and ctx.feature is not None:
        before = (lambda f=ctx.feature: select_feature(f))
    elif ctx.kind == "features" and ctx.element:
        before = (lambda fs=tuple(ctx.features): select_features(fs))
    # con caras de varias operaciones, lo que se pide (Suprimir...) se mira con las operaciones elegidas
    active_later = None
    if ctx.kind == "features" and before is not None:
        wanted_cmds = [k for _t, ks in groups for k in ks if k in ON_FEATURE and k not in by_key]
        active_later = active_for_features(ctx.features, wanted_cmds)
    # primero se arma todo y recién después se cambia el menú: si algo falla, queda el de FreeCAD
    new = []  # ("title", texto) / ("sep", None) / ("act", acción)
    first = True
    for title, wanted in groups:
        items, tray_keys = [], []
        for k in wanted:
            pre = before if k in ON_FEATURE else None
            a = by_key.get(k)
            if k == SELECTION_TOOLS:
                a = _selection_menu(menu, by_key)
            elif a is not None and (k in LABELS or pre is not None or _is_command(a.objectName())):
                a = _copy_action(a, LABELS.get(k), menu, pre)
            elif a is None:
                known = (k in active_later) if (active_later is not None and pre is not None) else None
                a = _command_action(k, menu, LABELS.get(k), pre, known)
            if a is not None:
                items.append(a)
                tray_keys.append(k)
        if not items:
            continue
        if title is None and first:
            # la bandeja: íconos arriba, sin repetirlos en el texto (como SW)
            new.append(_tray_action(menu, [(k, a) for k, a in zip(tray_keys, items)]))
            first = False
            continue
        if title:
            new.append(_title_action(menu, title, first))
        elif not first:
            new.append(None)
        new += items
        first = False
    hidden = [_copy_action(by_key[k], None, menu) for k in behind if k in by_key]
    for a in acts:
        menu.removeAction(a)
    for a in new:
        if a is None:
            menu.addSeparator()
        else:
            menu.addAction(a)
    if hidden:
        sep = menu.addSeparator()
        sep.setVisible(False)
        for a in hidden:
            menu.addAction(a)
            a.setVisible(False)
        menu.addAction(_more_action(menu, [sep] + hidden))
    return True


def _arrange_general(menu, acts, by_key, behind, removed):
    """Caso general: quitar lo que no sirve y mandar detrás de la "»" lo de FreeCAD."""
    gone = set(removed) | set(behind)
    for a in acts:
        if a.isSeparator():
            continue
        if action_key(a.objectName(), a.text()) in gone:
            menu.removeAction(a)
    _tidy_separators(menu)
    rest = [by_key[k] for k in behind if k in by_key]
    if rest:
        hidden = [menu.addSeparator()]
        hidden[0].setVisible(False)
        for a in rest:
            copy = _copy_action(a, None, menu)
            menu.addAction(copy)
            copy.setVisible(False)
            hidden.append(copy)
        menu.addAction(_more_action(menu, hidden))


def _tidy_separators(menu):
    """Separadores repetidos, al principio o al final: fuera."""
    last_sep = True
    for a in menu.actions():
        if a.isSeparator():
            if last_sep:
                menu.removeAction(a)
            last_sep = True
        elif a.isVisible():
            last_sep = False
    acts = menu.actions()
    if acts and acts[-1].isSeparator():
        menu.removeAction(acts[-1])


def click_text(menu, text):
    """Hace clic en lo que dice text (un ícono de la bandeja o una opción). True si estaba."""
    for a in menu.actions():
        if a.objectName() == "SWUI_cm_tray":
            for b in tray_buttons(a):
                if b.property("swui_text") == text:
                    b.click()
                    return b.isEnabled()
        elif not a.isSeparator() and a.text().replace("&", "") == text:
            a.trigger()
            return a.isEnabled()
    return False


def tray_buttons(action):
    """Los íconos de la bandeja, en orden."""
    from swui.compat import QtWidgets

    box = action.defaultWidget()
    grid = box.layout()
    return [grid.itemAt(i).widget() for i in range(grid.count())
            if isinstance(grid.itemAt(i).widget(), QtWidgets.QToolButton)]


def visible_texts(menu, with_hidden=False):
    """Textos del menú como los ve el usuario (para las pruebas): títulos entre [ ], » al final."""
    out = []
    for a in menu.actions():
        if a.isSeparator():
            continue
        if not a.isVisible() and not with_hidden:
            continue
        if a.objectName() == "SWUI_cm_title":
            out.append("[%s]" % a.defaultWidget().text())
        elif a.objectName() == "SWUI_cm_more":
            out.append("»")
        elif a.objectName() == "SWUI_cm_tray":
            out.append("{%s}" % "|".join(b.property("swui_text") for b in tray_buttons(a)))
        else:
            out.append(a.text().replace("&", "").split("\t")[0])
    return out
