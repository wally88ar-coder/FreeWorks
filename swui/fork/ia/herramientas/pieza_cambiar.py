# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Etapa 1b: cambiar valores por las ventanillas de FreeWorks (sin panel): cotas con "esta
configuración / todas" (instant_dims.apply_value, configurations.configure / set_values), árbol
(feature_tree.suppress / unsuppress / move / set_tip), configuraciones (configurations.add /
activate / rename / delete), material (material.assign) y comandos sin panel.

Reglas del usuario (01/11): si él tiene un panel o un croquis abierto, nada cambia (espera y avisa);
la IA no pone nombres (los SW los pone FreeWorks). Cada cambio es un paso de Ctrl+Z "IA: ...".
"""

import time

import FreeCAD

from swui.fork.ia.herramientas import comun as c
from swui.fork.ia.herramientas import pieza_ver
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult

WATCH_S = 10  # segundos que el vigilante de ventanitas mira después de correr un comando


def _transaction(doc, title, fn):
    doc.openTransaction("IA: %s" % title)
    try:
        out = fn()
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        doc.recompute()
        raise
    doc.commitTransaction()
    return out


def _bodies(doc):
    return [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]


def _errors(doc):
    return {o.Name for o in doc.Objects if "Invalid" in (getattr(o, "State", None) or [])}


def _new_errors(doc, before):
    return [c.label_of(doc.getObject(n)) for n in sorted(_errors(doc) - before) if doc.getObject(n)]


# --- cambiar_cota -----------------------------------------------------------------------


def _find_dim(doc, nombre, objeto):
    owners = [c.find(doc, objeto)] if objeto else _bodies(doc) + [
        o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject" and not o.InList]
    want = nombre.strip().lower()
    hits, every = [], []
    for owner in owners:
        for name, dim in pieza_ver.all_dims(owner):
            every.append(name)
            if name.lower() == want or name.split("@")[0].lower() == want:
                hits.append((name, dim))
    if not hits:
        raise c.Problema("No encuentro la cota \"%s\". Cotas: %s" % (nombre, ", ".join(every[:60])))
    if len(hits) > 1:
        raise c.Problema("\"%s\" encaja con varias cotas (%s): usá el nombre completo D1@Croquis1."
                         % (nombre, ", ".join(n for n, _d in hits)))
    return hits[0]


def cambiar_cota(nombre, valor, documento=None, objeto=None, en="esta"):
    from swui.fork import configurations as cf
    from swui.fork import instant_dims

    doc = c.document(documento)
    c.require_free()
    name, dim = _find_dim(doc, nombre, objeto)
    if dim.locked:
        raise c.Problema("%s está atada a una ecuación: cambiá la ecuación, no la cota." % name)
    value = valor if isinstance(valor, (int, float)) else instant_dims.parse(str(valor), dim.kind)
    if value is None:
        raise c.Problema("No entiendo el valor \"%s\"." % valor)
    before_val, before_err = dim.value, _errors(doc)
    target = dim.setter
    if cf.configured(doc):
        if isinstance(en, (list, tuple)):
            wrong = [n for n in en if n not in cf.names(doc)]
            if wrong:
                raise c.Problema("No hay configuraciones %s. Hay: %s" % (wrong, cf.names(doc)))

            def work():
                cf.set_values(doc, target, {n: value for n in en})
                cf.activate(doc, cf.active(doc))
            where = ", ".join(en)
        else:
            scope = "all" if en == "todas" else "this"

            def work():
                cf.configure(doc, target, value, scope)
            where = "todas las configuraciones" if scope == "all" else "la configuración %s" % cf.active(doc)
        _transaction(doc, "%s = %s" % (name, instant_dims.fmt(value, dim.kind)), work)
    else:
        where = ""
        if not instant_dims.apply_value(dim, float(value)):
            raise c.Problema("FreeCAD no aceptó el valor %s para %s (¿croquis sobredefinido?)." % (valor, name))
    errs = _new_errors(doc, before_err)
    text = "%s: %s -> %s%s." % (name, instant_dims.fmt(before_val, dim.kind), instant_dims.fmt(value, dim.kind),
                                " en " + where if where else "")
    if errs:
        text += " OJO: quedaron con error: %s (Ctrl+Z lo deshace)." % ", ".join(errs)
    return ToolResult(success=not errs, output=text, error=text if errs else "")


# --- arbol ------------------------------------------------------------------------------


def arbol(accion, objeto=None, documento=None, con_dependientes=False):
    from swui.fork import feature_tree as ft

    doc = c.document(documento)
    c.require_free()
    if accion == "reconstruir":
        import FreeCADGui

        FreeCADGui.runCommand("SWUI_ForceRebuild")
        return ToolResult(success=True, output="Reconstruido (Ctrl+Q).")
    obj = c.find(doc, objeto)
    body = ft.body_of(obj) if obj.TypeId != "PartDesign::Body" else obj
    if body is None:
        raise c.Problema("%s no está en un Cuerpo." % c.label_of(obj))
    feats = ft.features(body)
    if accion == "suprimir":
        done = _transaction(doc, "suprimir %s" % obj.Label, lambda: ft.suppress(obj))
        text = "Suprimido: %s." % ", ".join(o.Label for o in done or [obj])
    elif accion == "desactivar_supresion":
        done = _transaction(doc, "desactivar supresión %s" % obj.Label,
                            lambda: ft.unsuppress(obj, with_children=bool(con_dependientes)))
        text = "Desactivada la supresión: %s." % ", ".join(o.Label for o in done or [obj])
    elif accion in ("subir", "bajar"):
        if obj not in feats:
            raise c.Problema("%s no es una operación del Cuerpo." % obj.Label)
        i = feats.index(obj)
        if (accion == "subir" and i == 0) or (accion == "bajar" and i == len(feats) - 1):
            raise c.Problema("%s ya está %s." % (obj.Label, "primera" if accion == "subir" else "última"))
        lost = _transaction(doc, "%s %s" % (accion, obj.Label), lambda: ft.move(obj, "up" if accion == "subir" else "down"))
        text = "%s movida %s." % (obj.Label, "arriba" if accion == "subir" else "abajo")
        missing = [(f.Label, edges) for f, edges in lost or [] if edges]
        if missing:
            text += " OJO: aristas que no se encontraron: %s" % missing
    elif accion == "retroceder_hasta":
        if obj not in feats:
            raise c.Problema("%s no es una operación del Cuerpo." % obj.Label)
        _transaction(doc, "retroceder a %s" % obj.Label,
                     lambda: ft.set_tip(body, ft.rollback_target(feats, obj)))
        text = "Barra de retroceso antes de %s." % obj.Label
    elif accion == "avanzar_al_final":
        _transaction(doc, "avanzar al final", lambda: ft.set_tip(body, feats[-1]))
        text = "Barra de retroceso al final."
    else:
        raise c.Problema("Acción \"%s\" desconocida." % accion)
    errs = [c.label_of(o) for o in doc.Objects if "Invalid" in (getattr(o, "State", None) or [])]
    if errs:
        text += " Con error: %s." % ", ".join(errs)
    return ToolResult(success=True, output=text)


# --- configuracion ----------------------------------------------------------------------


def configuracion(accion, nombre=None, nuevo=None, documento=None):
    from swui.fork import configurations as cf

    doc = c.document(documento)
    c.require_free()
    if accion == "activar":
        _transaction(doc, "mostrar configuración %s" % nombre, lambda: cf.activate(doc, nombre))
    elif accion == "agregar":
        nombre = _transaction(doc, "agregar configuración %s" % nombre, lambda: cf.add(doc, nombre))
    elif accion == "cambiar_nombre":
        _transaction(doc, "cambiar nombre %s" % nombre, lambda: cf.rename(doc, nombre, nuevo))
    elif accion == "eliminar":
        _transaction(doc, "eliminar configuración %s" % nombre, lambda: cf.delete(doc, nombre))
    else:
        raise c.Problema("Acción \"%s\" desconocida." % accion)
    return ToolResult(success=True, output="Hecho. Configuraciones: %s; activa: %s."
                      % (cf.names(doc), cf.active(doc)))


def _config_problem(fn):
    def wrapper(**kw):
        try:
            return fn(**kw)
        except ValueError as exc:  # configurations avisa con ValueError en castellano
            return c.fail(str(exc))
    wrapper.__name__ = fn.__name__
    return wrapper


# --- material ---------------------------------------------------------------------------


def material(accion="listar", nombre=None, objetos=None, documento=None):
    from swui.fork import material as mat

    doc = c.document(documento)
    if accion == "listar":
        items = [{"nombre": i["name"], "categoria": i.get("category", "")} for i in mat.all_materials()]
        return ToolResult(success=True, output="%d materiales con densidad." % len(items), data={"materiales": items})
    c.require_free()
    if accion != "asignar":
        raise c.Problema("Acción \"%s\" desconocida (listar o asignar)." % accion)
    found = [i for i in mat.all_materials() if i["name"].lower() == (nombre or "").lower()]
    if not found:
        near = [i["name"] for i in mat.all_materials() if (nombre or "").lower() in i["name"].lower()][:15]
        raise c.Problema("No hay un material \"%s\". Parecidos: %s" % (nombre, near))
    objs = [c.find(doc, n) for n in objetos] if objetos else _bodies(doc)
    _transaction(doc, "material %s" % found[0]["name"], lambda: mat.assign(objs, found[0]))
    return ToolResult(success=True, output="%s asignado a %s." % (found[0]["name"], ", ".join(o.Label for o in objs)))


# --- comando ----------------------------------------------------------------------------


def comando(nombre, espera=1.5):
    """Corre un comando como un clic en la cinta. Si abre un panel o una ventanita, los cierra sin
    aceptar y avisa: para operaciones con panel están las herramientas propias."""
    import FreeCADGui

    from swui.compat import QtCore, QtWidgets
    from swui.fork.ia.nucleo import puente

    if nombre not in FreeCADGui.listCommands():
        return c.fail("No existe el comando \"%s\"." % nombre)
    seen = {}
    holder = {}

    def launch():
        busy = c.user_busy()
        if busy:
            return {"busy": busy}

        # Vigilante: cada 200 ms, hasta WATCH_S, cierra sin aceptar la ventanita que pida respuesta.
        # Corre también adentro del bucle propio de la ventanita (los QTimer siguen andando ahí).
        # Una sola mirada no alcanza: hay ventanas (Preferencias) que tardan en aparecer.
        timer = QtCore.QTimer()
        timer.setInterval(200)
        ticks = {"n": 0}

        def watch():
            ticks["n"] += 1
            w = QtWidgets.QApplication.activeModalWidget()
            if w is not None:
                seen["modal"] = w.windowTitle() + ": " + " ".join(
                    lbl.text() for lbl in w.findChildren(QtWidgets.QLabel) if lbl.text())[:300]
                w.reject()
            if ticks["n"] * 0.2 > WATCH_S:
                timer.stop()
        timer.timeout.connect(watch)
        timer.start()
        holder["timer"] = timer
        QtCore.QTimer.singleShot(0, lambda: FreeCADGui.runCommand(nombre))
        return {}

    res = puente.on_gui(launch, timeout=20, name="comando")
    if res.get("busy") or res.get("error"):
        return c.fail(res.get("busy") or res.get("error"))
    time.sleep(espera)

    def after():
        out = {}
        if holder.get("timer") is not None:
            holder["timer"].stop()
        if FreeCADGui.Control.activeDialog():
            doc = FreeCAD.ActiveDocument
            if doc is not None and doc.HasPendingTransaction:
                doc.abortTransaction()
            FreeCADGui.Control.closeDialog()
            if FreeCADGui.ActiveDocument is not None:
                FreeCADGui.ActiveDocument.resetEdit()
            out["panel"] = True
        return out

    state = puente.on_gui(after, timeout=WATCH_S + 10, name="comando (después)")
    if state.get("error"):
        return c.fail("FreeCAD quedó ocupado después del comando: %s" % state["error"])
    if seen.get("modal"):
        return c.fail("El comando abrió una ventanita que pide respuesta (%s); la cerré sin aceptar." % seen["modal"])
    if state.get("panel"):
        return c.fail("Ese comando abre un panel; lo cancelé. Para operaciones con panel usá las herramientas propias.")
    return ToolResult(success=True, output="Comando %s corrido." % nombre)


# --- Registro ---------------------------------------------------------------------------

_DOC = ToolParam("documento", "string", "Documento (por defecto el activo)", required=False)


def register(registry):
    registry.register(ToolDefinition(
        name="cambiar_cota",
        description=("Cambia una cota como el Modificar de FreeWorks (doble clic + valor): por nombre SW "
                     "(D1@Croquis1; ver 'cotas'). Con configuraciones: en='esta' (por defecto, como SW), "
                     "'todas' o una lista de configuraciones. Un paso de Ctrl+Z. No actúa si el usuario "
                     "tiene un panel o un croquis abierto. Después, verificá."),
        parameters=[ToolParam("nombre", "string", "Nombre SW de la cota, p. ej. D1@Croquis1"),
                    ToolParam("valor", "number", "Valor nuevo en mm (o grados)"), _DOC,
                    ToolParam("objeto", "string", "Croquis u operación donde buscarla", required=False),
                    ToolParam("en", "string", "esta, todas, o lista de configuraciones", required=False,
                              default="esta")],
        handler=c.guarded(cambiar_cota), category="cambiar", timeout=120))
    registry.register(ToolDefinition(
        name="arbol",
        description=("Árbol de operaciones como en FreeWorks: suprimir (con sus dependientes, solo en la "
                     "configuración activa si hay), desactivar_supresion, subir / bajar una operación (los "
                     "redondeos vuelven a encontrar sus aristas), retroceder_hasta (barra de retroceso antes "
                     "de esa operación), avanzar_al_final, reconstruir (Ctrl+Q)."),
        parameters=[ToolParam("accion", "string", "Qué hacer", enum=["suprimir", "desactivar_supresion", "subir",
                                                                     "bajar", "retroceder_hasta",
                                                                     "avanzar_al_final", "reconstruir"]),
                    ToolParam("objeto", "string", "Operación (o el Cuerpo para avanzar_al_final)", required=False),
                    _DOC,
                    ToolParam("con_dependientes", "boolean", "Desactivar supresión también de lo que depende",
                              required=False, default=False)],
        handler=c.guarded(arbol), category="cambiar", timeout=120))
    registry.register(ToolDefinition(
        name="configuracion",
        description=("Configuraciones como SW: activar (mostrar), agregar (copia de la activa y la activa), "
                     "cambiar_nombre, eliminar (no la activa ni una que use un ensamblaje)."),
        parameters=[ToolParam("accion", "string", "Qué hacer",
                              enum=["activar", "agregar", "cambiar_nombre", "eliminar"]),
                    ToolParam("nombre", "string", "Configuración"),
                    ToolParam("nuevo", "string", "Nombre nuevo (cambiar_nombre)", required=False), _DOC],
        handler=c.guarded(_config_problem(configuracion)), category="cambiar", timeout=120))
    registry.register(ToolDefinition(
        name="material",
        description=("Materiales de FreeWorks: listar (los que tienen densidad) o asignar uno por nombre a "
                     "objetos (por defecto, a todos los Cuerpos del documento). No cambia el color."),
        parameters=[ToolParam("accion", "string", "listar o asignar", enum=["listar", "asignar"], required=False,
                              default="listar"),
                    ToolParam("nombre", "string", "Nombre del material (asignar)", required=False),
                    ToolParam("objetos", "array", "Objetos (asignar)", required=False, items={"type": "string"}),
                    _DOC],
        handler=c.guarded(material), category="cambiar", timeout=120))
    registry.register(ToolDefinition(
        name="comando",
        description=("Corre un comando de la cinta o el menú que NO abre panel (vistas como Std_ViewIsometric, "
                     "Std_ViewFitAll, Std_ToggleVisibility, guardar con Std_Save...). Si abre un panel o una "
                     "ventanita que pide respuesta, los cierra sin aceptar y avisa."),
        parameters=[ToolParam("nombre", "string", "Nombre del comando, p. ej. Std_ViewIsometric")],
        handler=c.guarded(comando), category="cambiar", main_thread=False))
