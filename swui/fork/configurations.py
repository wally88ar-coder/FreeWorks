# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Configuraciones de pieza como en SOLIDWORKS (etapa 1): núcleo sin interfaz.

Por debajo, solo lo nativo de FreeCAD 1.1.4 (análisis del 01/11, docs/NOTAS_TECNICAS.md,
"Configuraciones"): la "tabla de configuración" de la planilla (lo mismo que arma su
diálogo Configuration Table, DlgSheetConf.cpp) y expresiones. El fork solo la arma y la
escribe (asistente): cambiar de configuración, guardar y abrir funciona sin el addon.

Tabla de diseño ("Tabla de diseño", una planilla):
    fila 1      títulos para leer ("Configuración", "D1@Croquis", "Suprimir Cortar1"...)
    fila 2      valores de la configuración activa (enlazados por FreeCAD, con alias)
    fila 3...   una fila por configuración: nombre en A, valores desde B
La lista desplegable "Configuracion" del Cuerpo (CopyOnChange, para los ensamblajes de la
etapa 4) se llena sola con la columna A desde la fila 3.

Qué se ata a la tabla (solo cuando el usuario elige "Esta configuración"):
- una cota de croquis: la restricción (con nombre; si no tiene, se le pone "Dn" como SW);
- una cota de operación (Length, Radius, Size, Angle...);
- la supresión de una operación (0/1); un croquis o plano apoyado en una cara suprimida
  apaga su apoyo por expresión (como feature_tree.sync_attachments, pero por configuración).

NOMBRES INTERNOS ESTABLES (quedan en los archivos, no cambiarlos nunca): la propiedad
"Configuracion" del Cuerpo, la disposición de filas de la tabla y los alias "Sup_<Name>",
"<Croquis>_<Restricción>" y "<Operación>_<Propiedad>".
"""

import math
import re
import traceback

import FreeCAD

PROP = "Configuracion"  # NO CAMBIAR: queda en los archivos
GROUP = "Configuraciones"
TABLE_NAME = "TablaDiseno"
TABLE_LABEL = "Tabla de diseño"
FIRST = "Predeterminado"
HEAD_ROW, BIND_ROW, FIRST_ROW = 1, 2, 3
SUP = "Sup_"
CONF = "Conf_"
OFF = "Deactivated"
ENUM_PATH = PROP + ".Enum"
PROP_TITLES = {"Length": "Profundidad", "Length2": "Profundidad 2", "Radius": "Radio", "Size": "Distancia",
               "Angle": "Ángulo", "Thickness": "Espesor", "Depth": "Profundidad", "Diameter": "Diámetro"}


# --- Celdas -----------------------------------------------------------------


def col_letter(n):
    """1 -> "A", 27 -> "AA"."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def clean_alias(text):
    """Alias válido para la planilla: letras, números y _, sin empezar con número."""
    s = re.sub(r"[^A-Za-z0-9_]", "_", text or "")
    return s if s and not s[0].isdigit() else "_" + s


def fmt_value(value):
    """Número para una celda (sin unidad; las cotas toman mm o °)."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, str):
        return text_cell(value)
    v = float(value)
    return str(int(round(v))) if abs(v - round(v)) < 1e-9 else repr(round(v, 9))


def text_cell(text):
    """Texto tal cual (con ' delante: "2mm" no se vuelve una cota)."""
    return "'" + text


def _contents(sheet, cell):
    try:
        return sheet.getContents(cell) or ""
    except Exception:
        return ""


def _plain(contents):
    return contents[1:] if contents.startswith("'") else contents


# --- Dónde está ---------------------------------------------------------------


ASSEMBLY = "Assembly::AssemblyObject"


def is_copy(obj):
    """¿Es una copia que FreeCAD guarda para un componente en otra configuración? (Copy on change)"""
    try:
        return any(p.TypeId == "App::LinkGroup" and p.Name.startswith("CopyOnChangeGroup") for p in obj.InList)
    except Exception:
        return False


def owner(doc):
    """El objeto con la lista de configuraciones: el Cuerpo de una pieza o el Ensamblaje (o None)."""
    objs = list(getattr(doc, "Objects", []))
    # en un ensamblaje, solo el Ensamblaje: los Cuerpos que hay ahí son copias de componentes
    kind = ASSEMBLY if any(getattr(o, "TypeId", "") == ASSEMBLY for o in objs) else "PartDesign::Body"
    for obj in objs:
        if getattr(obj, "TypeId", "") != kind or PROP not in obj.PropertiesList or is_copy(obj):
            continue
        if any(p.lstrip(".") == ENUM_PATH for p, _e in obj.ExpressionEngine):
            return obj
    return None


def table(doc, body=None):
    """La tabla de diseño (planilla), a partir de la expresión de la lista."""
    body = body or owner(doc)
    if body is None:
        return None
    for path, expr in body.ExpressionEngine:
        if path.lstrip(".") == ENUM_PATH:
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\.cells", expr)
            if m:
                return doc.getObject(m.group(1))
    return None


def names(doc):
    body = owner(doc)
    if body is None:
        return []
    try:
        return list(body.getEnumerationsOfProperty(PROP) or [])
    except Exception:
        return []


def active(doc):
    body = owner(doc)
    return getattr(body, PROP, None) if body is not None else None


def configured(doc):
    """¿La pieza tiene más de una configuración? (con una sola todo es como siempre)."""
    return len(names(doc)) > 1


def row_of(doc, name):
    sheet = table(doc)
    row = FIRST_ROW
    while sheet is not None:
        c = _contents(sheet, "A%d" % row)
        if not c:
            return None
        if _plain(c) == name:
            return row
        row += 1
    return None


def config_rows(sheet):
    rows, row = [], FIRST_ROW
    while _contents(sheet, "A%d" % row):
        rows.append(row)
        row += 1
    return rows


def param_cols(sheet):
    """Columnas de parámetros (2 = B...) mientras haya título en la fila 1."""
    cols, n = [], 2
    while _contents(sheet, "%s%d" % (col_letter(n), HEAD_ROW)):
        cols.append(n)
        n += 1
    return cols


def alias_col(sheet, alias):
    for n in param_cols(sheet):
        try:
            if sheet.getAlias("%s%d" % (col_letter(n), BIND_ROW)) == alias:
                return n
        except Exception:
            pass
    return None


# --- Armar la tabla -------------------------------------------------------------


def _bind_expr(body, first_col, last_col):
    return "tuple(.cells, <<%s>> + str(hiddenref(%s.%s)+%d), <<%s>> + str(hiddenref(%s.%s)+%d))" % (
        col_letter(first_col), body.Name, PROP, FIRST_ROW, col_letter(last_col), body.Name, PROP, FIRST_ROW)


def _rebind(sheet, body):
    """Enlazar la fila 2 con la fila de la configuración activa (lo hace FreeCAD)."""
    for path, _e in list(sheet.ExpressionEngine):
        if path.startswith(".cells.Bind."):
            sheet.setExpression(path, None)
    cols = param_cols(sheet)
    if cols:
        sheet.setExpression(".cells.Bind.%s%d.%s%d" % (col_letter(cols[0]), BIND_ROW, col_letter(cols[-1]), BIND_ROW),
                            _bind_expr(body, cols[0], cols[-1]))
    _style(sheet, cols[-1] if cols else 1)


def _style(sheet, last_col):
    """Títulos en negrita; la fila de la activa en gris y cursiva (no es una configuración más)."""
    try:
        last = col_letter(last_col)
        sheet.setStyle("A%d:%s%d" % (HEAD_ROW, last, HEAD_ROW), "bold")
        sheet.setStyle("A%d:%s%d" % (BIND_ROW, last, BIND_ROW), "italic")
        sheet.setBackground("A%d:%s%d" % (BIND_ROW, last, BIND_ROW), (0.9, 0.9, 0.9))
    except Exception:
        pass


def _main_body(doc):
    asm = next((o for o in doc.Objects if getattr(o, "TypeId", "") == ASSEMBLY), None)
    if asm is not None:
        return asm
    try:
        import FreeCADGui

        body = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody")
        if body is not None and body.Document is doc:
            return body
    except Exception:
        pass
    return next((o for o in doc.Objects if getattr(o, "TypeId", "") == "PartDesign::Body"), None)


def ensure(doc, body=None):
    """Tabla y lista con la configuración "Predeterminado" (si no estaban). Devuelve la planilla."""
    sheet = table(doc)
    if sheet is not None:
        return sheet
    body = body or _main_body(doc)
    if body is None:
        raise ValueError("No hay una pieza (Cuerpo) ni un ensamblaje en el documento.")
    sheet = doc.addObject("Spreadsheet::Sheet", TABLE_NAME)
    sheet.Label = TABLE_LABEL
    sheet.set("A%d" % HEAD_ROW, text_cell("Configuración"))
    sheet.set("A%d" % FIRST_ROW, text_cell(FIRST))
    sheet.recompute()
    if PROP not in body.PropertiesList:
        body.addProperty("App::PropertyEnumeration", PROP, GROUP, "Configuración activa (FreeWorks)")
    body.setPropertyStatus(PROP, "CopyOnChange")
    _bind_enum(sheet, body)
    body.recompute()
    sheet.set("A%d" % BIND_ROW, "=<<Activa: >> + hiddenref(%s.%s.String)" % (body.Name, PROP))
    _style(sheet, 1)
    sheet.recompute()
    show_table(doc)
    return sheet


def _bind_enum(sheet, body):
    """
    La lista de configuraciones del Cuerpo = las celdas A de las filas de configuración, con el
    rango EXACTO (A3:A5), no "hasta la última fila usada" (A3:|): al deshacer "Agregar", la celda
    vuelve a vacía pero la planilla la sigue contando como usada y aparecía una configuración
    fantasma "None" (Issue #50). La fórmula es una propiedad del Cuerpo: cambiarla en el mismo paso
    que la tabla hace que Deshacer y Rehacer la lleven junto con las filas. Los archivos con la
    fórmula vieja siguen andando; pasan a la nueva al agregar o borrar una configuración.
    """
    last = FIRST_ROW + max(1, len(config_rows(sheet))) - 1
    body.setExpression(ENUM_PATH, "%s.cells[<<A%d:A%d>>]" % (sheet.Name, FIRST_ROW, last))


def rebind_rows(doc):
    """La lista del Cuerpo con las filas que tiene hoy la tabla (si cambió). True si la cambió."""
    sheet, body = table(doc), owner(doc)
    if sheet is None or body is None:
        return False
    last = FIRST_ROW + max(1, len(config_rows(sheet))) - 1
    want = "%s.cells[<<A%d:A%d>>]" % (sheet.Name, FIRST_ROW, last)
    if any(p.lstrip(".") == ENUM_PATH and e == want for p, e in body.ExpressionEngine):
        return False
    _bind_enum(sheet, body)
    return True


def _rows_changed(doc, sheet, keep):
    """
    Después de agregar, renombrar o borrar filas de configuración: la lista del Cuerpo al día y la
    configuración `keep` activa, AUNQUE la pieza esté en error. La fila 2 toma los valores de la
    activa por su POSICIÓN en la lista; si la lista quedaba vieja (las operaciones con error frenan
    el recálculo del Cuerpo), apuntaba a otra fila o a una vacía, las medidas configuradas se
    quedaban sin valor y todo se trababa (Issues #51 y #55). Orden: tabla, lista nueva, recalcular
    SOLO el Cuerpo (actualiza la lista), la activa por su nombre, el enlace de la fila 2, todo.
    """
    body = owner(doc)
    sheet.recompute()
    _bind_enum(sheet, body)
    body.recompute()
    if keep in names(doc) and getattr(body, PROP) != keep:
        setattr(body, PROP, keep)
    _rebind(sheet, body)
    sheet.recompute()
    doc.recompute()


def show_table(doc):
    """
    Como SW: con una sola configuración la tabla es interna (la arma, por ejemplo, suprimir un
    componente) y no se ve en el árbol; con dos o más aparece.
    """
    sheet = table(doc)
    view = getattr(sheet, "ViewObject", None) if sheet is not None else None
    if view is None or not hasattr(view, "ShowInTree"):
        return
    want = len(names(doc)) > 1
    if view.ShowInTree != want:
        view.ShowInTree = want


def _unique_name(doc, wanted):
    taken = set(names(doc))
    if wanted not in taken:
        return wanted
    m = re.match(r"(.*?)(\d+)$", wanted)
    base, n = (m.group(1), int(m.group(2))) if m else (wanted, 1)
    while "%s%d" % (base, n) in taken:
        n += 1
    return "%s%d" % (base, n)


def next_name(doc):
    """Nombre propuesto para una configuración nueva ("Configuración2"...)."""
    return _unique_name(doc, "Configuración%d" % (max(len(names(doc)), 1) + 1))


def add(doc, name):
    """Configuración nueva copiando la activa, y activarla (como SW). Devuelve su nombre."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Falta el nombre de la configuración.")
    if name in names(doc):
        raise ValueError("Ya hay una configuración \"%s\"." % name)
    sheet = ensure(doc)
    src = row_of(doc, active(doc)) or FIRST_ROW
    row = FIRST_ROW + len(config_rows(sheet))
    for n in param_cols(sheet):
        c = col_letter(n)
        sheet.set("%s%d" % (c, row), _contents(sheet, "%s%d" % (c, src)))
    sheet.set("A%d" % row, text_cell(name))
    _rows_changed(doc, sheet, active(doc))
    activate(doc, name)
    return name


_before = []  # funciones (doc, nombre) que corren antes de cambiar de configuración


def before_activate(doc, name):
    for fn in list(_before):
        try:
            fn(doc, name)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Antes de cambiar de configuración:\n%s\n"
                                     % traceback.format_exc())


def activate(doc, name):
    body = owner(doc)
    if body is None or name not in names(doc):
        raise ValueError("No hay una configuración \"%s\"." % name)
    before_activate(doc, name)
    if getattr(body, PROP) != name:
        setattr(body, PROP, name)
    doc.recompute()
    show_table(doc)


def rename(doc, old, new):
    new = (new or "").strip()
    if not new:
        raise ValueError("Falta el nombre.")
    if new != old and new in names(doc):
        raise ValueError("Ya hay una configuración \"%s\"." % new)
    row = row_of(doc, old)
    if row is None:
        raise ValueError("No hay una configuración \"%s\"." % old)
    was = active(doc)
    sheet = table(doc)
    sheet.set("A%d" % row, text_cell(new))
    # con la pieza en error, recalcular todo no actualizaba la lista y el renombre quedaba a medias
    # ("No hay una configuración «Nueva»", Issue #55): misma secuencia que agregar y borrar
    _rows_changed(doc, sheet, new if was == old else was)
    activate(doc, new if was == old else was)


def delete(doc, name):
    """Borrar una configuración (no la activa, como SW)."""
    if name == active(doc):
        raise ValueError("No se puede eliminar la configuración activa: mostrá otra primero.")
    row = row_of(doc, name)
    if row is None:
        raise ValueError("No hay una configuración \"%s\"." % name)
    was = active(doc)
    sheet = table(doc)
    sheet.removeRows(str(row), 1)
    _rows_changed(doc, sheet, was)
    activate(doc, was)


# --- Parámetros (columnas) --------------------------------------------------------


def _ensure_constraint_name(sketch, index):
    c = sketch.Constraints[index]
    if c.Name:
        return c.Name
    used = {k.Name for k in sketch.Constraints if k.Name}
    n = 1
    while "D%d" % n in used:
        n += 1
    sketch.renameConstraint(index, "D%d" % n)
    return "D%d" % n


def target_info(target):
    """
    target: ("sketch", croquis, índice) | ("prop", objeto, propiedad) | ("sup", operación).
    Devuelve (objeto, ruta de la expresión, alias, título, valor actual).
    """
    kind, obj = target[0], target[1]
    if kind == "sketch":
        cname = _ensure_constraint_name(obj, target[2])
        c = obj.Constraints[target[2]]
        value = c.Value
        if c.Type == "Angle":
            import math

            value = math.degrees(value)
        return (obj, "Constraints." + cname, clean_alias("%s_%s" % (obj.Name, cname)),
                "%s@%s" % (cname, obj.Label), value)
    if kind == "prop":
        prop = target[2]
        q = getattr(obj, prop)
        value = getattr(q, "Value", q)
        return (obj, prop, clean_alias("%s_%s" % (obj.Name, prop)),
                "%s@%s" % (PROP_TITLES.get(prop, prop), obj.Label), value)
    if kind == "sup":
        return (obj, "Suppressed", clean_alias(SUP + obj.Name), "Suprimir %s" % obj.Label,
                1 if getattr(obj, "Suppressed", False) else 0)
    if kind == "conf":  # configuración de un componente (ensamblaje)
        return (obj, PROP, clean_alias(CONF + obj.Name), "Configuración %s" % obj.Label,
                getattr(obj, PROP, "") or "")
    raise ValueError(kind)


def bound_alias(obj, path, doc=None):
    """Alias de la tabla al que está atado obj.path (o None)."""
    sheet = table(doc or obj.Document)
    if sheet is None:
        return None
    want = path.lstrip(".")
    for p, expr in obj.ExpressionEngine:
        if p.lstrip(".") == want:
            m = re.match(r"\s*%s\.([A-Za-z_][A-Za-z0-9_]*)\s*$" % re.escape(sheet.Name), expr)
            return m.group(1) if m else None
    return None


def is_config_expression(obj, path, expr):
    """¿Es una expresión que arma la tabla de diseño? (no se muestra como ecuación, como SW)."""
    doc = obj.Document
    sheet = table(doc)
    if sheet is None:
        return False
    p = path.lstrip(".")
    if obj is sheet or p == ENUM_PATH:
        return True
    if p == "MapMode" and OFF in expr and sheet.Name + "." in expr:
        return True
    return re.match(r"\s*%s\.%s" % (re.escape(sheet.Name), r"[A-Za-z_][A-Za-z0-9_]*\s*$"), expr) is not None


def is_bound(target):
    obj, path = target[1], None
    if target[0] == "sketch":
        c = obj.Constraints[target[2]]
        paths = ["Constraints." + c.Name] if c.Name else []
        paths.append("Constraints[%d]" % target[2])
        return any(bound_alias(obj, p) for p in paths)
    path = target[2] if target[0] == "prop" else "Suppressed"
    return bound_alias(obj, path) is not None


def _add_column(doc, alias, title, value):
    """Columna nueva con el valor actual en todas las configuraciones."""
    sheet = ensure(doc)
    n = alias_col(sheet, alias)
    if n is not None:
        return n
    cols = param_cols(sheet)
    n = (cols[-1] + 1) if cols else 2
    c = col_letter(n)
    sheet.set("%s%d" % (c, HEAD_ROW), text_cell(title))
    for row in config_rows(sheet):
        sheet.set("%s%d" % (c, row), fmt_value(value))
    _rebind(sheet, owner(doc))
    sheet.setAlias("%s%d" % (c, BIND_ROW), alias)
    sheet.recompute()
    return n


def check_value(value):
    """Un valor de configuración tiene que ser un número de verdad: con infinito o "no es un
    número" (NaN) la tabla quedaba rota o saltaba un OverflowError de Python (Issue #46). Se avisa
    ANTES de tocar nada."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("La medida tiene que ser un número (no infinito).")


def configure(doc, target, value, scope="this"):
    """
    Poner value en target. scope "this": solo en la configuración activa (ata la cota o la
    supresión a la tabla si no lo estaba); "all": en todas.
    """
    check_value(value)
    obj, path, alias, title, current = target_info(target)
    bound = bound_alias(obj, path) is not None
    if scope == "all" and not bound:
        _set_plain(target, value)
        return
    sheet = ensure(doc)
    rows = config_rows(sheet) if scope == "all" else [row_of(doc, active(doc))]
    if None in rows:  # la tabla y la lista no coinciden: aviso ANTES de tocar nada (antes TypeError, #55)
        raise ValueError("La configuración activa no está en la tabla de diseño: revisá la tabla.")
    n = _add_column(doc, alias, title, current)
    if not bound:
        obj.setExpression(path, "%s.%s" % (sheet.Name, alias))
    c = col_letter(n)
    for row in rows:
        sheet.set("%s%d" % (c, row), fmt_value(value))
    doc.recompute()


def value_in(doc, target, name):
    """Valor de target en la configuración name (de la tabla si está atado; si no, el de todas)."""
    obj, path, _alias, _title, current = target_info(target)
    alias = bound_alias(obj, path)
    sheet = table(doc)
    if alias and sheet is not None:
        n, row = alias_col(sheet, alias), row_of(doc, name)
        if n is not None and row is not None:
            try:
                value = sheet.get("%s%d" % (col_letter(n), row))
                return float(getattr(value, "Value", value))
            except Exception:
                pass
    return current


def set_values(doc, target, values):
    """
    Configurar operación (como SW): {configuración: valor} de una vez. Ata target a la tabla si
    no lo estaba (las demás configuraciones quedan con el valor actual).
    """
    for value in values.values():
        check_value(value)
    obj, path, alias, title, current = target_info(target)
    sheet = ensure(doc)
    n = _add_column(doc, alias, title, current)
    if bound_alias(obj, path) is None:
        obj.setExpression(path, "%s.%s" % (sheet.Name, alias))
    c = col_letter(n)
    for name, value in values.items():
        row = row_of(doc, name)
        if row is not None:
            sheet.set("%s%d" % (c, row), fmt_value(value))
    doc.recompute()


def _set_plain(target, value):
    kind, obj = target[0], target[1]
    if kind == "sketch":
        c = obj.Constraints[target[2]]
        unit = "deg" if c.Type == "Angle" else "mm"
        obj.setDatum(target[2], FreeCAD.Units.Quantity("%r %s" % (float(value), unit)))
    elif kind == "prop":
        setattr(obj, target[2], value)
    elif kind == "conf":
        setattr(obj, PROP, value)
    else:
        obj.Suppressed = bool(value)


# --- Suprimir en esta configuración -------------------------------------------------


def _features(objs):
    return [o for o in objs if hasattr(o, "Suppressed") and o.isDerivedFrom("PartDesign::Feature")]


def suppress(obj, scope="this"):
    """Como feature_tree.suppress, pero solo en la configuración activa: obj y sus dependientes."""
    from swui.fork import feature_tree as ft

    doc = obj.Document
    done = []
    for o in _features([obj] + ft.dependents(obj)):
        if not o.Suppressed:
            configure(doc, ("sup", o), 1, scope)
            done.append(o)
    sync_attachments(doc)
    return done


def only_in(doc, feat, name):
    """
    Operación nueva, como SW: queda en la configuración donde se hizo (name) y suprimida en las
    demás (opción de SW "Suprimir operaciones nuevas"; decisión del usuario 01/11). Devuelve las
    configuraciones donde quedó suprimida.
    """
    others = [n for n in names(doc) if n != name]
    if not others or bound_alias(feat, "Suppressed") is not None:
        return []
    values = {n: 1 for n in others}
    values[name] = 0
    set_values(doc, ("sup", feat), values)
    sync_attachments(doc)
    doc.recompute()
    return others


def is_new_feature(obj):
    """¿Operación de pieza (PartDesign) recién hecha en un documento con configuraciones?"""
    try:
        if not obj.isDerivedFrom("PartDesign::Feature") or is_copy(obj):
            return False
        doc = obj.Document
        body = owner(doc)
        if body is None or getattr(body, "TypeId", "") == ASSEMBLY or not configured(doc):
            return False
        return not any(is_copy(p) for p in obj.InList)
    except Exception:
        return False


def unsuppress(obj, with_children=False, scope="this"):
    from swui.fork import feature_tree as ft

    doc = obj.Document
    todo = [obj] + (ft.dependents(obj) if with_children else [])
    done = []
    for o in _features(todo):
        if o.Suppressed:
            configure(doc, ("sup", o), 0, scope)
            done.append(o)
    sync_attachments(doc)
    return done


def _supports(obj):
    from swui.fork import feature_tree as ft

    return ft._attached_to(obj)


def _attach_expr(sheet, aliases, mode):
    cond = " + ".join("%s.%s" % (sheet.Name, a) for a in aliases)
    return "%s > 0 ? <<%s>> : <<%s>>" % (cond, OFF, mode)


def sync_attachments(doc):
    """
    Croquis y planos apoyados en una operación con supresión por configuración: su apoyo se
    apaga por expresión en las configuraciones donde esa operación está suprimida.
    """
    from swui.fork import feature_tree as ft

    sheet = table(doc)
    if sheet is None:
        return
    for obj in doc.Objects:
        if not hasattr(obj, "MapMode") or ft.is_feature(obj):
            continue
        aliases = [bound_alias(t, "Suppressed") for t in _supports(obj)]
        aliases = [a for a in aliases if a]
        ours = [e for p, e in obj.ExpressionEngine if p.lstrip(".") == "MapMode" and OFF in e]
        if aliases:
            mode = obj.MapMode
            if ours:
                m = re.search(r":\s*<<([^>]+)>>\s*$", ours[0])
                mode = m.group(1) if m else mode
            elif mode == OFF:
                mode = getattr(obj, ft.MAPMODE_PROP, None) or "FlatFace"
            want = _attach_expr(sheet, aliases, mode)
            if not ours or ours[0].replace(" ", "") != want.replace(" ", ""):
                obj.setExpression("MapMode", want)
        elif ours:
            m = re.search(r":\s*<<([^>]+)>>\s*$", ours[0])
            obj.setExpression("MapMode", None)
            if m:
                obj.MapMode = m.group(1)
