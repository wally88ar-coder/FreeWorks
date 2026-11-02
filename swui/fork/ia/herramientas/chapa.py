# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Chapa sin panel (grupo con ventanilla de FreeWorks): exportar el DXF del desarrollo con el mismo
nombre automático que el botón (pieza_espesor_material.dxf), por las funciones de abajo del botón
que no preguntan (`sheet_metal.write_dxf`, `dxf_filename`, `part_name`, `thickness`,
`material_name`, `sheet_bodies`, `sheet_parts`, `flat_of`). No pisa un DXF que ya existe salvo que
se pida (como el botón, que pregunta). Las operaciones de chapa con panel (bridas, dobladillo,
convertir, corte) van por la herramienta 'panel'; desplegar / plegar, por 'comando' (SWUI_SMFlatten).
"""

import os

import FreeCAD

from swui.fork.ia.herramientas import comun as c
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult


def _folder(doc, carpeta):
    if carpeta:
        if not os.path.isdir(carpeta):
            raise c.Problema("No existe la carpeta %s." % carpeta)
        return carpeta
    if doc.FileName:
        return os.path.dirname(doc.FileName)
    from swui.fork import sheet_metal as sm

    folder = FreeCAD.ParamGet(sm.PREFS).GetString("DxfFolder", "") or os.path.join(os.path.expanduser("~"), "Documents")
    return folder if os.path.isdir(folder) else os.path.expanduser("~")


def dxf(documento=None, cuerpo=None, carpeta=None, reemplazar=False):
    from swui.fork import sheet_metal as sm

    doc = c.document(documento)
    c.require_free()
    if cuerpo:
        bodies = [c.find(doc, cuerpo)]
        if not sm.is_sheet_body(bodies[0]):
            raise c.Problema("%s no es una chapa." % c.label_of(bodies[0]))
    else:
        bodies = list(sm.sheet_parts(doc))
    if not bodies:
        raise c.Problema("No hay chapas en %s (ni en las piezas de un ensamblaje)." % doc.Label)
    folder = _folder(doc, carpeta)
    plan = []
    for body in bodies:
        name = sm.dxf_filename(sm.part_name(body), sm.thickness(body), sm.material_name(body))
        plan.append((body, os.path.join(folder, name)))
    exists = [p for _b, p in plan if os.path.exists(p)]
    if exists and not reemplazar:
        raise c.Problema("Ya existen: %s. Preguntale al usuario si los reemplazo (reemplazar=true)." % exists)
    done = []
    for body, path in plan:
        bdoc = body.Document
        had_flat = sm.flat_of(body) is not None
        bdoc.openTransaction("IA: desarrollo para DXF")
        try:
            sm.write_dxf(body, path)
            bdoc.recompute()
        except Exception as exc:
            bdoc.abortTransaction()
            raise c.Problema("No se pudo exportar el DXF de %s: %s" % (body.Label, exc))
        bdoc.commitTransaction()
        flat = sm.flat_of(body)
        if flat is not None:
            for sk_name in getattr(flat, "UnfoldSketches", []) or []:
                sk = bdoc.getObject(sk_name)
                if sk is not None and not flat.Visibility:
                    sk.Visibility = False
            if bdoc is not doc and not had_flat:
                bdoc.removeObject(flat.Name)  # por lotes: la pieza queda como estaba (decisión 31/10)
        done.append(path)
    FreeCAD.Console.PrintMessage("FreeWorks IA: DXF guardado: %s\n" % ", ".join(done))
    return ToolResult(success=True, output="DXF guardado%s: %s" % ("s" if len(done) > 1 else "", ", ".join(done)),
                      data={"archivos": done})


def register(registry):
    registry.register(ToolDefinition(
        name="dxf",
        description=("Exporta el DXF del desarrollo de la chapa con un clic, como el botón de FreeWorks: contorno y "
                     "líneas de plegado en capas separadas, nombre automático pieza_espesor_material.dxf, en la "
                     "carpeta del archivo. En un ensamblaje, uno por cada pieza de chapa (por lotes). Si el DXF ya "
                     "existe no lo pisa: hay que preguntarle al usuario y repetir con reemplazar=true."),
        parameters=[ToolParam("documento", "string", "Documento (por defecto el activo)", required=False),
                    ToolParam("cuerpo", "string", "Una chapa en particular", required=False),
                    ToolParam("carpeta", "string", "Otra carpeta", required=False),
                    ToolParam("reemplazar", "boolean", "Pisar los DXF que ya existen", required=False, default=False)],
        handler=c.guarded(dxf), category="operar", timeout=180))
