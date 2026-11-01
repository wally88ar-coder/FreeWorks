# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Configuraciones en chapa (etapa 2 de 5).

- Espesor y Profundidad de la Brida base aparecen como cotas con doble clic (instant_dims),
  así que se configuran como cualquier cota ("Esta configuración / Todas").
- Los paneles del fork (Brida base, redondeo...) con un valor atado a la tabla de diseño lo
  cambian solo en la configuración activa (antes lo salteaban, como a una ecuación).
- Al cambiar de configuración, el desarrollo (Chapa desplegada) vuelve a elegir su cara fija:
  SheetMetal la guarda por número ("Face15") y si la configuración suprime algo las caras se
  renumeran y el desarrollo queda en error (probado 01/11).
- Exportar DXF en una pieza con configuraciones pregunta "Esta configuración / Todas las
  configuraciones"; el nombre lleva la configuración: Pieza-Config_2mm_Material.dxf.
"""

import os
import traceback

import FreeCAD

from swui.compat import QtWidgets
from swui.fork import configurations as cf

SHEET_DIMS = (("Thickness", "Espesor"), ("Length", "Profundidad"))


def _sm():
    from swui.fork import sheet_metal as sm

    return sm


def _flats(doc):
    sm = _sm()
    return [f for f in (sm.flat_of(b) for b in sm.sheet_bodies(doc)) if f is not None]


def refresh_flats(doc):
    """Que cada desarrollo apunte a la cara fija que corresponde a la configuración activa."""
    sm = _sm()
    changed = False
    for body in sm.sheet_bodies(doc):
        flat = sm.flat_of(body)
        if flat is None:
            continue
        try:
            face = sm.fixed_face(body)
            if face and list(flat.baseObject[1]) != [face]:
                flat.baseObject = (body, [face])
                changed = True
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Cara fija:\n%s\n" % traceback.format_exc())
    if changed or any("Touched" in f.State for f in _flats(doc)):
        with sm._active(doc):
            doc.recompute()
    _hide_flat_sketches(doc)
    return changed


def _hide_flat_sketches(doc):
    """SheetMetal vuelve a crear visibles los croquis del desarrollo en cada recálculo."""
    try:
        from swui.fork import sheet_panels as sp

        for flat in _flats(doc):
            sp._sketches_follow(flat)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Croquis del desarrollo:\n%s\n" % traceback.format_exc())


def _activate_skipping_flats(doc, name, original):
    """
    Cambiar de configuración sin recalcular todavía los desarrollos: con la cara fija vieja
    ("Face6" que en la otra configuración no existe) FreeCAD mostraba el error "Chapa
    desplegada1: Invalid shape name ?Face6" antes de que refresh_flats la corrigiera (visto con
    el mouse, 01/11). Primero el resto, después la cara fija, después el desarrollo.
    """
    flats = _flats(doc)
    body = cf.owner(doc)
    if (not flats or body is None or name not in cf.names(doc)
            or getattr(body, "TypeId", "") == cf.ASSEMBLY):
        return original(doc, name)  # ensamblaje: lo maneja config_asm
    skip = set()
    for f in flats:
        skip.add(f)
        skip.update(f.InListRecursive)
    cf.before_activate(doc, name)
    if getattr(body, cf.PROP) != name:
        setattr(body, cf.PROP, name)
    doc.recompute([o for o in doc.Objects if o not in skip])
    return None


def _hook_activate():
    if getattr(cf.activate, "_swui_sheet", False):
        return
    original = cf.activate

    def activate(doc, name, _original=original):
        _activate_skipping_flats(doc, name, _original)
        try:
            refresh_flats(doc)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Desarrollo por configuración:\n%s\n" % traceback.format_exc())

    activate._swui_sheet = True
    cf.activate = activate


def _hook_part_name():
    sm = _sm()
    if getattr(sm.part_name, "_swui_conf", False):
        return
    original = sm.part_name

    def part_name(body, _original=original):
        name = _original(body)
        doc = body.Document
        if cf.owner(doc) is not None and cf.configured(doc):
            name += "-" + cf.active(doc)
        return name

    part_name._swui_conf = True
    sm.part_name = part_name


def _hook_panels():
    from swui.fork import dress_up_panel as dp

    if getattr(dp.SwPanel._set, "_swui_conf", False):
        return
    original = dp.SwPanel._set

    def _set(self, prop, value, _original=original):
        obj = self.obj
        try:
            alias = cf.bound_alias(obj, prop)
        except Exception:
            alias = None
        if not alias:
            return _original(self, prop, value)
        old = getattr(obj, prop)
        old = getattr(old, "Value", old)
        if isinstance(old, (int, float)) and abs(float(old) - float(value)) <= 1e-9:
            return
        cf.configure(obj.Document, ("prop", obj, prop), value, "this")

    _set._swui_conf = True
    dp.SwPanel._set = _set


def _is_base_bend(obj):
    proxy = getattr(obj, "Proxy", None)
    return proxy is not None and type(proxy).__name__ == "SMBaseBend"


def _hook_dims():
    from swui.fork import instant_dims as idm

    if getattr(idm.feature_dims, "_swui_sheet", False):
        return
    original = idm.feature_dims

    def feature_dims(obj, _original=original):
        out = _original(obj)
        if not _is_base_bend(obj):
            return out
        try:
            bb = obj.Shape.BoundBox
            locked = idm._expressions(obj)
            spots = (FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMax), FreeCAD.Vector(bb.XMax, bb.YMax, bb.ZMin))
            for (prop, _title), at in zip(SHEET_DIMS, spots):
                if obj.TypeId and prop in obj.PropertiesList:
                    if prop == "Length" and getattr(obj, "Length", None) is None:
                        continue
                    value = getattr(obj, prop).Value
                    text = ("e" if prop == "Thickness" else "") + idm.fmt(value)
                    out.append(idm.Dim(text, value, "length", ("prop", obj, prop), [], at, (),
                                       any(p.lstrip(".") == prop for p in locked)))
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Cotas de chapa:\n%s\n" % traceback.format_exc())
        return out

    feature_dims._swui_sheet = True
    idm.feature_dims = feature_dims


# --- DXF de todas las configuraciones ------------------------------------------------


def export_configs(body, folder):
    """Un DXF por configuración en folder; deja activa la que estaba. Devuelve (hechos, fallados)."""
    sm = _sm()
    from swui.fork import sheet_panels as sp

    doc = body.Document
    was = cf.active(doc)
    done, failed = [], []
    new = sm.flat_of(body) is None
    try:
        for name in cf.names(doc):
            try:
                cf.activate(doc, name)
                with sm._active(doc):
                    sm.ensure_flat(body, sketches=True)
                    doc.recompute()
                fname = sm.dxf_filename(sm.part_name(body), sm.thickness(body), sm.material_name(body))
                sm.write_dxf(body, os.path.join(folder, fname))
                done.append(fname)
            except Exception as exc:
                FreeCAD.Console.PrintError("[SWUI fork] DXF de %s:\n%s\n" % (name, traceback.format_exc()))
                failed.append("%s (%s)" % (name, exc))
    finally:
        cf.activate(doc, was)
        added = sm.flat_of(body) if new else None
        if added is not None:
            try:
                sp._drop_flat(added)
                doc.recompute()
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Borrar desarrollo:\n%s\n" % traceback.format_exc())
    return done, failed


def _ask_scope():
    from swui.fork import sheet_panels as sp

    box = QtWidgets.QMessageBox(sp._mw())
    box.setWindowTitle("Exportar DXF")
    box.setIcon(QtWidgets.QMessageBox.Icon.Question)
    box.setText("La pieza tiene configuraciones. ¿Qué DXF exportar?")
    this = box.addButton("Esta configuración", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    every = box.addButton("Todas las configuraciones", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancelar", QtWidgets.QMessageBox.ButtonRole.RejectRole)
    box.exec()
    clicked = box.clickedButton()
    return "this" if clicked is this else "all" if clicked is every else None


def _hook_export():
    from swui.fork import sheet_panels as sp

    if getattr(sp.export_dxf, "_swui_conf", False):
        return
    original = sp.export_dxf

    def export_dxf(_original=original):
        doc = FreeCAD.ActiveDocument
        if doc is None or sp._is_assembly(doc) or not cf.configured(doc):
            return _original()
        scope = _ask_scope()
        if scope is None:
            return None
        if scope == "this":
            return _original()
        body = sp.target_body()
        if body is None:
            return None
        if doc.FileName:
            folder = os.path.dirname(doc.FileName)
        else:
            folder = QtWidgets.QFileDialog.getExistingDirectory(sp._mw(), "Carpeta para los DXF")
            if not folder:
                return None
        sm = _sm()
        was = cf.active(doc)
        names = []
        for name in cf.names(doc):  # nombres que van a salir, para preguntar antes de pisar
            names.append(sm.dxf_filename(sm.part_name(body).rsplit("-" + was, 1)[0] + "-" + name,
                                         sm.thickness(body), sm.material_name(body)))
        existing = [n for n in names if os.path.exists(os.path.join(folder, n))]
        if existing and not sp._ask_overwrite(existing):
            return None
        done, failed = export_configs(body, folder)
        text = "DXF guardados en %s:\n%s" % (folder, "\n".join(done) or "(ninguno)")
        if failed:
            text += "\n\nNo se pudieron exportar:\n" + "\n".join(failed)
        FreeCAD.Console.PrintMessage("[SWUI fork] %s\n" % text)
        sp._info(text)
        return done

    export_dxf._swui_conf = True
    sp.export_dxf = export_dxf
    # los comandos de la cinta guardaron la función vieja: que busquen la del módulo
    if not getattr(sp._Command.Activated, "_swui_conf", False):
        def Activated(self):
            fn = self.run
            current = getattr(sp, getattr(fn, "__name__", ""), None)
            if callable(current) and getattr(current, "_swui_conf", False):
                fn = current
            fn()

        Activated._swui_conf = True
        sp._Command.Activated = Activated


def install():
    _hook_activate()
    _hook_part_name()
    _hook_panels()
    _hook_dims()
    _hook_export()
