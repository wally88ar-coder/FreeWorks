# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Herramientas para mirar sin tocar: "estado" (documentos, árbol, selección, panel abierto) y
"captura" (imagen de la vista 3D o de la ventana entera). Corren en el hilo principal.

Privacidad (decisión del usuario, 01/11): la captura se manda solo cuando la IA la pide, y queda
anotado en la vista de informe.
"""

import base64
import os

import FreeCAD

from swui.fork.ia.nucleo import config
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult

MAX_OBJECTS = 400


def _state_of(obj):
    flags = [s for s in (getattr(obj, "State", None) or []) if s in ("Invalid", "Touched")]
    if getattr(obj, "Suppressed", False):
        flags.append("Suprimido")
    return flags


def _tree(doc):
    rows = []
    for obj in doc.Objects[:MAX_OBJECTS]:
        row = {"nombre": obj.Name, "etiqueta": obj.Label, "tipo": obj.TypeId}
        try:
            row["visible"] = bool(obj.Visibility)
        except Exception:
            pass
        try:
            parent = obj.getParentGeoFeatureGroup()
            if parent is not None:
                row["dentro_de"] = parent.Name
        except Exception:
            pass
        tip = getattr(obj, "Tip", None)
        if tip is not None and obj.TypeId == "PartDesign::Body":
            row["punta"] = tip.Name
        flags = _state_of(obj)
        if flags:
            row["estado"] = flags
        rows.append(row)
    return rows


def _selection():
    import FreeCADGui

    out = []
    for sel in FreeCADGui.Selection.getSelectionEx("", 0):
        out.append({"objeto": sel.ObjectName, "documento": sel.DocumentName,
                    "subelementos": list(sel.SubElementNames)})
    return out


def estado():
    import FreeCADGui

    active = FreeCAD.ActiveDocument
    data = {
        "documentos": [{"nombre": d.Name, "etiqueta": d.Label, "archivo": d.FileName,
                        "activo": d is active} for d in FreeCAD.listDocuments().values()],
        "banco": FreeCADGui.activeWorkbench().name(),
        "seleccion": _selection(),
    }
    try:
        data["panel_abierto"] = FreeCADGui.Control.activeDialog()
    except Exception:
        pass
    gdoc = FreeCADGui.ActiveDocument
    if gdoc is not None:
        editing = gdoc.getInEdit()
        if editing is not None:
            obj = getattr(editing, "Object", None)
            if obj is None:  # la vista de un ensamblaje no tiene .Object (#72): el objeto en edición
                obj = next((o for o in gdoc.Document.Objects if getattr(o, "ViewObject", None) is editing), None)
            data["editando"] = obj.Name if obj is not None else type(editing).__name__
    if active is not None:
        data["arbol"] = _tree(active)
        if len(active.Objects) > MAX_OBJECTS:
            data["arbol_recortado"] = "se muestran %d de %d objetos" % (MAX_OBJECTS, len(active.Objects))
    summary = ("Documento activo: %s, %d objetos, %d elegidos." % (active.Label, len(active.Objects),
                                                                len(data["seleccion"]))
               if active is not None else "No hay documento abierto.")
    return ToolResult(success=True, output=summary, data=data)


def captura(que="vista", ancho=900, alto=650, ajustar=False):
    import FreeCADGui

    if ajustar and FreeCADGui.ActiveDocument is not None:
        FreeCADGui.SendMsgToActiveView("ViewFit")  # solo el zoom, no la pieza
    path = os.path.join(config.data_dir(), "captura.png")
    if os.path.exists(path):
        os.remove(path)
    if que == "ventana":
        FreeCADGui.getMainWindow().grab().save(path, "PNG")
    else:
        gdoc = FreeCADGui.ActiveDocument
        view = gdoc.ActiveView if gdoc is not None else None
        if view is None or not hasattr(view, "saveImage"):
            return ToolResult(success=False, output="", error="No hay una vista 3D activa (probá con que='ventana').")
        view.saveImage(path, int(ancho), int(alto), "Current")
    with open(path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("ascii")
    FreeCAD.Console.PrintMessage("FreeWorks IA: se envió una captura de la %s.\n" % que)
    return ToolResult(success=True, output="Captura de la %s." % que,
                      images=[{"mimeType": "image/png", "data": data}])


def register(registry):
    registry.register(ToolDefinition(
        name="estado",
        description=("Mira FreeWorks sin cambiar nada: documentos abiertos, banco activo, árbol del "
                     "documento activo (nombre interno, etiqueta, tipo, visible, dentro de qué Cuerpo, "
                     "punta, errores), selección del usuario, panel abierto y objeto en edición. "
                     "Usala antes de cambiar algo y después, para verificar."),
        parameters=[],
        handler=estado,
        category="ver",
        timeout=30,
    ))
    registry.register(ToolDefinition(
        name="captura",
        description=("Imagen PNG de la vista 3D activa (que='vista') o de la ventana entera de "
                     "FreeWorks con sus paneles (que='ventana'). Pedila solo cuando haga falta ver: "
                     "viaja a la nube y queda anotada."),
        parameters=[
            ToolParam("que", "string", "vista o ventana", required=False, enum=["vista", "ventana"],
                      default="vista"),
            ToolParam("ancho", "integer", "Ancho en píxeles (solo vista)", required=False, default=900),
            ToolParam("alto", "integer", "Alto en píxeles (solo vista)", required=False, default=650),
            ToolParam("ajustar", "boolean", "Ajustar el zoom para ver la pieza entera antes (como F)",
                      required=False, default=False),
        ],
        handler=captura,
        category="ver",
        timeout=30,
    ))
