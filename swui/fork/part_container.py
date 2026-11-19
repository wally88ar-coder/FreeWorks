# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Piezas de varios Cuerpos (soldaduras, multicuerpo) como UN componente del ensamblaje, como en SW (16/11).

FreeCAD pone en el ensamblaje lo que está suelto en la raíz del archivo (assembly_drop.pick_objects): en una
soldadura de FreeWorks los miembros están en un grupo y quedaba solo el croquis esqueleto; en una pieza
multicuerpo, un componente por Cuerpo. Un vínculo a un grupo entre archivos no se puede ("PropertyLinkList
does not support external object", medido). Lo nativo de FreeCAD para una pieza de varios Cuerpos es el
contenedor Parte (App::Part): el componente apunta a él, tiene la forma de todos, sus caras se eligen y
Editar pieza activa un Cuerpo a través de él (medido el 16/11).

Al insertar un archivo así, se crea en el archivo de la pieza una Parte (nombre interno estable
CONTAINER_NAME, marca SWUI_PartContainer) con todo lo que estaba en la raíz, y se guarda la pieza (si no, el
vínculo no la encuentra al reabrir). Las variables (VarSet) y planillas quedan afuera: no son geometría.
"""

import FreeCAD

CONTAINER_NAME = "Pieza"          # nombre interno de la Parte (estable: lo guardan los archivos)
MARK = "SWUI_PartContainer"       # propiedad que la marca como contenedor puesto por FreeWorks
KEEP_OUT = ("App::VarSet", "Spreadsheet::Sheet", "App::MaterialObjectPython", "TechDraw::DrawPage")


def _is_root(o):
    """Suelto en la raíz: sin Cuerpo/Parte que lo contenga y sin carpeta (lo de una carpeta va con ella)."""
    try:
        if o.TypeId in ("App::Origin", "App::Line", "App::Plane", "App::Point") and o.InList:
            return False  # el Origen de un Cuerpo
        return o.getParentGeoFeatureGroup() is None and o.getParentGroup() is None
    except Exception:
        return False


def bodies(doc):
    return [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]


def container(doc):
    """La Parte que hace de pieza (la de FreeWorks o la única que haya), o None."""
    parts = [o for o in doc.Objects if o.TypeId == "App::Part"]
    marked = [p for p in parts if hasattr(p, MARK)]
    if marked:
        return marked[0]
    return parts[0] if len(parts) == 1 else None


def needs_container(doc):
    """¿Pieza de varios Cuerpos sin contenedor? (sin Parte ni ensamblaje, y dos o más Cuerpos)."""
    if any(o.TypeId in ("App::Part", "Assembly::AssemblyObject") for o in doc.Objects):
        return False
    return len(bodies(doc)) >= 2


def wrap(doc, save=True, transaction=True):
    """
    Pone todo lo de la raíz de la pieza (menos variables y planillas) en una Parte nueva y devuelve la Parte.
    Un paso de deshacer en la pieza (transaction=False: dentro del paso que ya esté abierto); se guarda si
    save y el archivo ya tiene nombre.
    """
    roots = [o for o in doc.Objects if _is_root(o) and o.TypeId not in KEEP_OUT
             and not o.TypeId.startswith(("TechDraw::", "Spreadsheet::"))]  # el plano y sus vistas quedan afuera
    from swui.fork import safe_ops

    own = transaction and safe_ops.begin_step(doc, "Pieza de varios cuerpos")
    try:
        part = doc.addObject("App::Part", CONTAINER_NAME)
        part.addProperty("App::PropertyBool", MARK, "FreeWorks", "Contenedor de la pieza (FreeWorks)")
        setattr(part, MARK, True)
        part.Label = doc.Label
        for o in roots:
            if o is not part and o.getParentGeoFeatureGroup() is None:
                part.addObject(o)
        doc.recompute()
    except Exception:
        if own:
            safe_ops.end_step(doc, abort=True)
        raise
    if own:
        safe_ops.end_step(doc)
    if save and getattr(doc, "FileName", ""):
        doc.save()
    return part


_inserting = [0]  # >0 mientras se insertan archivos en un ensamblaje (assembly_drop.insert_files)
_open_before = set()  # documentos abiertos cuando empezó la inserción (los del usuario)
_to_save = []  # (documento, su archivo, ¿tenía cambios sin guardar?) de las piezas a las que la inserción les puso el contenedor


def _gui_doc(name):
    try:
        import FreeCADGui

        return FreeCADGui.getDocument(name)
    except Exception:
        return None


def _save_wrapped():
    """
    Guarda las piezas que recibieron el contenedor al insertarlas. Una pieza que ya tenía cambios sin guardar
    (abierta por el usuario) NO se guarda: no se escriben sus cambios a medias sin preguntar; queda modificada y
    avisa. Si el guardado falla, queda modificada y avisa.
    """
    queued, _to_save[:] = list(_to_save), []
    for doc, path, dirty in queued:
        try:
            name = doc.Name  # documento cerrado: error, se saltea
            same = FreeCAD.listDocuments().get(name)
            if same is None or same.FileName != path:
                continue  # se cerró (o es otro documento con el mismo nombre)
            doc = same
            part = container(doc)
            if part is None or not hasattr(part, MARK) or not getattr(doc, "FileName", ""):
                continue
            gdoc = _gui_doc(name)
            if dirty:
                FreeCAD.Console.PrintWarning(
                    "[SWUI fork] %s tenía cambios sin guardar: no se guardó sola. Guardala para que el ensamblaje "
                    "la encuentre entera al reabrirlo.\n" % doc.Label)
                if gdoc is not None:
                    gdoc.Modified = True
                continue
            doc.recompute()  # si quedó algo por recalcular, el próximo recálculo la marcaría modificada
            doc.save()
            # doc.save() desde Python escribe el archivo pero no limpia la marca de la ventana (medido 18/11)
            if gdoc is not None:
                gdoc.Modified = False
        except Exception as exc:
            FreeCAD.Console.PrintWarning("[SWUI fork] No se pudo guardar una pieza con su contenedor (%s): guardala "
                                         "antes de cerrar el ensamblaje.\n" % exc)
            try:
                _gui_doc(doc.Name).Modified = True
            except Exception:
                pass


def _hook_insert():
    """
    assembly_drop.pick_objects: al INSERTAR en un ensamblaje, una pieza de varios Cuerpos entra entera, por su
    contenedor (se crea y se guarda la pieza). pick_objects lo usan también otros (Plano nuevo lo consulta todo el
    tiempo para saber si está activo): ahí no se cambia nada, solo se devuelve el contenedor si ya existe.
    """
    from swui import assembly_drop

    original = assembly_drop.pick_objects
    if getattr(original, "_swui_container", False):
        return

    def pick_objects(doc):
        try:
            if _inserting[0] and needs_container(doc):
                # sin guardar: durante la inserción FreeCAD 1.1.4 tiene la pieza "de solo lectura" (OSError al
                # guardar) y el contenedor quedaba solo en memoria: el ensamblaje se rompía al reabrirlo (#104).
                # Se guarda apenas termina de insertar (insert_files, abajo).
                # ¿el usuario la tenía abierta con cambios? Solo si ya estaba abierta antes de insertar: la que abre
                # la inserción (oculta) FreeCAD la marca modificada aunque no tenga nada (medido 18/11)
                gdoc = _gui_doc(doc.Name)
                dirty = bool(doc.Name in _open_before and gdoc is not None and gdoc.Modified)
                part = wrap(doc, save=False)
                _to_save.append((doc, doc.FileName, dirty))
                return [part]
            part = container(doc)
            if part is not None and hasattr(part, MARK):
                return [part]
        except Exception:
            import traceback

            FreeCAD.Console.PrintError("[SWUI fork] Pieza de varios cuerpos:\n%s\n" % traceback.format_exc())
        return original(doc)

    pick_objects._swui_container = True
    assembly_drop.pick_objects = pick_objects

    insert = assembly_drop.insert_files

    def insert_files(*args, **kwargs):
        if not _inserting[0]:
            _open_before.clear()
            _open_before.update(FreeCAD.listDocuments())
        _inserting[0] += 1
        try:
            return insert(*args, **kwargs)
        finally:
            _inserting[0] -= 1
            if not _inserting[0]:
                _save_wrapped()

    insert_files._swui_container = True
    assembly_drop.insert_files = insert_files


ADOPT = ("PartDesign::Body", "App::DocumentObjectGroup")  # lo que tiene que verse en el componente
BODY_STEP = "Add a Body"  # nombre (sin traducir) del paso que abre PartDesign_Body en FreeCAD 1.1.4


class _NewBodies:
    """
    Un Cuerpo (o grupo: croquis 3D, miembros) nuevo en una pieza con el contenedor de FreeWorks va adentro;
    si no, no se vería en el componente del ensamblaje. Se hace apenas termina el comando que lo creó
    (recién creado, un Cuerpo todavía arma su Origen).
    """

    def slotCreatedObject(self, obj):
        try:
            if obj.TypeId not in ADOPT:
                return
            if getattr(obj.Document, "Transacting", False):
                return  # lo trae Deshacer/Rehacer: su paso ya trae (o no) la entrada al contenedor; abrir uno
                #         nuevo acá borraría lo que queda por rehacer (revisión del 18/11, hallazgo 2)
            if getattr(obj.Document, "Restoring", False):
                return  # abriendo un archivo o pegando: lo que viene ya trae su lugar (revisión 18/11, 2.ª pasada)
            doc, name = obj.Document.Name, obj.Name
        except Exception:
            return
        active = FreeCAD.getActiveTransaction()  # (nombre, número) o None
        if obj.TypeId == "PartDesign::Body" and active and active[0] == BODY_STEP:
            # botón Cuerpo: ya mismo, dentro del paso del comando, así un solo Ctrl+Z saca el Cuerpo (como SW). Solo
            # ese comando: otros (miembros de soldadas...) ponen el Cuerpo en una carpeta después de crearlo, y
            # adoptarlo antes lo dejaba en dos grupos (revisión del 18/11, 2.ª pasada). En FreeCAD 1.1.4 el Cuerpo
            # ya tiene su Origen al avisar que se creó (medido con FreeCADCmd el 18/11).
            adopt(doc, name, recompute=False)
        from swui.compat import QtCore

        QtCore.QTimer.singleShot(0, lambda: adopt(doc, name))


def adopt(doc_name, obj_name, recompute=True):
    """
    Un Cuerpo o grupo nuevo suelto en la raíz de una pieza con el contenedor de FreeWorks va adentro. (Editando
    una pieza de un solo Cuerpo, el contenedor lo arma antes el botón: edit_part.prepare_container; acá no, porque
    si el comando se cancela el componente quedaría apuntando a algo borrado.)
    """
    try:
        doc = FreeCAD.getDocument(doc_name)
        obj = doc.getObject(obj_name)
        if obj is None or obj.getParentGeoFeatureGroup() is not None or obj.getParentGroup() is not None:
            return
        part = container(doc)
        if part is None or not hasattr(part, MARK):
            return
        # dentro del paso de deshacer que esté abierto (el del comando); si no hay, uno propio (hallazgo 12 de la
        # revisión del 17/11: quedaba fuera de todo paso y Ctrl+Z / Ctrl+Y no lo devolvían igual)
        from swui.fork import safe_ops

        own = not FreeCAD.getActiveTransaction() and safe_ops.begin_step(doc, "Cuerpo a la pieza")
        try:
            part.addObject(obj)
            if recompute:  # dentro del comando no: el comando recalcula al terminar
                doc.recompute()
        except Exception:
            if own:
                safe_ops.end_step(doc, abort=True)
            raise
        if own:
            safe_ops.end_step(doc)
    except Exception:
        import traceback

        FreeCAD.Console.PrintLog("[SWUI fork] Cuerpo nuevo al contenedor:\n%s\n" % traceback.format_exc())


_observer = None


def install():
    global _observer
    _hook_insert()
    if _observer is None:
        _observer = _NewBodies()
        FreeCAD.addDocumentObserver(_observer)
