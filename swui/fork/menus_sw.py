# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Barra de menús como la de SOLIDWORKS 2018 (decidido con el usuario el 01/11/2026, maqueta
"Menús de FreeWorks": https://claude.ai/artifact/AD833geJYQtUpny242DxAC).

Archivo, Edición, Ver, Insertar, Herramientas, Ventana, FreeWorks y "?", con la estructura de SW
2018 (relevada del SW real con el mouse) y solo lo que FreeWorks y FreeCAD tienen. Insertar y
Herramientas van en bloques Pieza / Ensamblaje / Plano / Croquis separados por líneas; lo que no
corresponde al documento activo queda en gris (editando un croquis, Pieza sigue activa, como SW).
Lo útil de FreeCAD que SW no tiene va en FreeWorks > FreeCAD.

Cómo: el banco es de Python (Gui::PythonWorkbench) y arranca con los menús estándar de FreeCAD;
`removeMenu` los saca y `appendMenu` arma los nuestros (probado en 1.1.4). Se hace dentro de
Initialize, al final de fork.install, antes de que FreeCAD arme la barra (rearmarla después con
`reloadActive` rompe el banco en 1.1.4). Los otros bancos de FreeCAD no se tocan.
- Comandos de FreeCAD que actúan directo (Guardar, Copiar...): van tal cual, con su atajo de
  siempre, y se les pone el texto de SW mientras se está en el banco (se devuelve al salir).
- Lo demás va con un comando "envoltorio" SWUI_Menu_...: texto de SW, gris según el entorno y,
  al usarlo, el mismo camino que el botón de la cinta (ribbon._run: elegir plano sin selección,
  paneles SW, cerrar el croquis y seguir...).
- Atajos de SW donde FreeCAD usa otros: Ctrl+W (cerrar) y F11 (pantalla completa); las teclas que
  chocan se les sacan a las acciones de FreeCAD mientras tanto (como rebuild_keys).
- "Mostrar los menús originales de FreeCAD" (FreeWorks > FreeCAD): salida de emergencia; se aplica
  al reiniciar FreeCAD.
"""

import functools
import re
import time
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

WB_NAME = "LikeSolidWorksUIWorkbench"
PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
ORIGINALS_KEY = "MenusOriginales"
ORIGINALS_CMD = "SWUI_MenusOriginales"
PREFIX = "SWUI_Menu_"
OLD_MENU = "LikeSolidWorks UI"  # el menú del original y del fork hasta ahora (se reparte)

SEP = "---"

# Atajos de SW que FreeCAD tiene en otra tecla: (tecla, comando de FreeCAD)
SW_KEYS = (("Ctrl+W", "Std_CloseActiveWindow"), ("F11", "Std_MainFullscreen"))


def E(label, target, env=None, k=None, index=None, tip=None, label_c=None):
    """Entrada: target = comando, {entorno: comando} o una función; label_c = texto en el croquis."""
    return {"label": label, "target": target, "env": env, "k": k, "index": index, "tip": tip,
            "label_c": label_c}


def S(label, items, env=None):
    """Submenú; env vale para las entradas de adentro que no dicen otro."""
    return {"label": label, "items": items, "env": env}


def _pick_language(code):
    from swui import ribbon

    ribbon._pick_language(code)


def _edit_table():
    from swui.fork import config_tab

    config_tab.edit_table()


def _assembly_from_part():
    """
    Archivo > Crear ensamblaje desde pieza, como SW: ensamblaje nuevo (archivo propio, como
    SWUI_NewAssembly) con la pieza activa adentro, fija en el origen. Antes solo creaba el
    ensamblaje vacío (visto con el mouse, 01/11). El vínculo necesita la pieza guardada.
    """
    import os

    doc = FreeCAD.ActiveDocument
    if doc is None:
        return
    if not getattr(doc, "FileName", ""):
        path, _flt = QtWidgets.QFileDialog.getSaveFileName(
            FreeCADGui.getMainWindow(), "Guardar la pieza (el ensamblaje la toma de su archivo)",
            os.path.join(os.path.expanduser("~"), (doc.Label or doc.Name) + ".FCStd"),
            "Archivo de FreeCAD (*.FCStd)")
        if not path:
            return
        if not path.lower().endswith(".fcstd"):
            path += ".FCStd"
        doc.saveAs(path)
    path = doc.FileName
    from swui.commands import new_assembly

    new = new_assembly.create()
    if new is not None:
        _insert_when_ready(new, path, 20)


def _insert_when_ready(doc, path, tries):
    """new_assembly arma el ensamblaje un instante después: esperarlo y meter la pieza."""
    try:
        asms = [o for o in doc.Objects if o.TypeId == "Assembly::AssemblyObject"]
    except Exception:
        return  # el documento se cerró
    if not asms:
        if tries > 0:
            QtCore.QTimer.singleShot(150, functools.partial(_insert_when_ready, doc, path, tries - 1))
        return
    from swui import assembly_drop

    assembly_drop._safe_insert(asms[0], [path])


def _language_items():
    try:
        from swui import i18n

        langs = [(i18n.AUTO, "Automático (el de FreeCAD)")] + list(i18n.choices())
    except Exception:
        langs = []
    return [E(name, functools.partial(_pick_language, code)) for code, name in langs]


# P = pieza, E = ensamblaje, D = plano (dibujo), C = croquis. "PC": pieza o croquis, etc.
def menus():
    return [
        ("Archivo", [
            E("Nuevo...", "Std_New"),
            E("Abrir...", "Std_Open"),
            E("Abrir reciente", "Std_RecentFiles"),
            E("Cerrar", "Std_CloseActiveWindow"),
            SEP,
            E("Crear dibujo desde pieza", "SWUI_NewDrawing", env="PE"),
            E("Crear ensamblaje desde pieza", _assembly_from_part, env="P",
              tip="Ensamblaje nuevo con esta pieza adentro, fija en el origen (como SW)"),
            SEP,
            E("Guardar", "Std_Save"),
            E("Guardar como...", "Std_SaveAs"),
            E("Guardar todo", "Std_SaveAll"),
            E("Guardar copia...", "Std_SaveCopy"),
            E("Exportar (STEP, IGES, STL...)...", "Std_Export"),
            E("Importar...", "Std_Import"),
            E("Guardar como PDF...", "SWUI_ExportPDF", env="D"),
            E("Exportar DXF...", "SWUI_ExportDXF", env="D"),
            E("Exportar DXF del desarrollo...", "SWUI_SMExportDXF", env="PE"),
            SEP,
            E("Vista preliminar...", "Std_PrintPreview"),
            E("Imprimir...", "Std_Print"),
            SEP,
            E("Volver a cargar", "Std_Revert"),
            SEP,
            E("Salir", "Std_Quit"),
        ]),
        ("Edición", [
            E("Deshacer", "Std_Undo"),
            E("Rehacer", "Std_Redo"),
            SEP,
            E("Seleccionar todo", "Std_SelectAll"),
            E("Cortar", "Std_Cut"),
            E("Copiar", "Std_Copy"),
            E("Pegar", "Std_Paste"),
            E("Eliminar", "Std_Delete"),
            SEP,
            E("Reconstruir", "SWUI_Rebuild", k="Ctrl+B"),
            E("Forzar reconstrucción", "SWUI_ForceRebuild", k="Ctrl+Q"),
            E("Retroceder", "SWUI_Rollback", env="PC"),
            E("Avanzar", "SWUI_RollForward", env="PC"),
            E("Avanzar al final", "SWUI_RollToEnd", env="PC"),
            SEP,
            E("Ocultar", "Std_HideSelection"),
            E("Visualizar", "Std_ShowSelection"),
            E("Mostrar todo", "Std_ShowObjects"),
            SEP,
            E("Suprimir", {"P": "SWUI_Suppress", "E": "SWUI_ComponentSuppress"}, env="PE"),
            E("Desactivar supresión", {"P": "SWUI_Unsuppress", "E": "SWUI_ComponentUnsuppress"}, env="PE"),
            E("Desactivar supresión con dependientes", "SWUI_UnsuppressWithChildren", env="P"),
            E("Configurar operación...", "SWUI_ConfigureFeature", env="P"),
            E("Configuración del componente...", "SWUI_ComponentConfig", env="E"),
            SEP,
            E("Croquis", "SWUI_EditSketch", env="P"),
            S("Tabla de diseño", [E("Editar tabla...", _edit_table)], env="P"),
            SEP,
            E("Definición...", "SWUI_EditFeature", env="PE"),
        ]),
        ("Ver", [
            S("Visualizar", [
                # subpuntos del grupo Std_DrawStyle (como la cinta: 2 alámbrica ... 6 con aristas)
                E("Estructura alámbrica", "Std_DrawStyle", index=2),
                E("Líneas ocultas visibles", "Std_DrawStyle", index=3),
                E("Sombreado con aristas", "Std_DrawStyle", index=6),
                E("Sombreado", "Std_DrawStyle", index=5),
                SEP,
                E("Perspectiva", "Std_PerspectiveCamera"),
                E("Ortogonal", "Std_OrthographicCamera"),
                E("Vista de sección", "Std_ToggleClipPlane"),
            ]),
            S("Modificar", [
                S("Orientación", [
                    E("Isométrica", "Std_ViewIsometric"),
                    E("Dimétrica", "Std_ViewDimetric"),
                    E("Trimétrica", "Std_ViewTrimetric"),
                    SEP,
                    E("Frontal", "Std_ViewFront"),
                    E("Superior", "Std_ViewTop"),
                    E("Derecha", "Std_ViewRight"),
                    E("Posterior", "Std_ViewRear"),
                    E("Inferior", "Std_ViewBottom"),
                    E("Izquierda", "Std_ViewLeft"),
                    SEP,
                    E("Normal a", "SWUI_NormalTo", k="N"),
                ]),
                E("Zoom para ajustar", "SWUI_FitAll", k="F"),
                E("Zoom encuadre", "Std_ViewBoxZoom"),
                E("Zoom acercar", "Std_ViewZoomIn"),
                E("Zoom alejar", "Std_ViewZoomOut"),
                E("Ampliar selección", "Std_ViewFitSelection"),
            ]),
            # como SW 2018 (relevado con el mouse el 04/11): origin_planes.py
            S("Ocultar/Mostrar", [
                E("Planos", "SWUI_ViewPlanes"),
                E("Planos primarios", "SWUI_ViewPrimaryPlanes"),
            ]),
            SEP,
            E("Pantalla completa", "Std_MainFullscreen"),
        ]),
        ("Insertar", [
            # Pieza
            S("Saliente/Base", [
                E("Extruir...", "PartDesign_Pad"),
                E("Revolución...", "PartDesign_Revolution"),
                E("Barrer...", "PartDesign_AdditivePipe"),
                E("Recubrir...", "PartDesign_AdditiveLoft"),
            ], env="P"),
            S("Cortar", [
                E("Extruir...", "PartDesign_Pocket"),
                E("Revolución...", "PartDesign_Groove"),
                E("Barrer...", "PartDesign_SubtractivePipe"),
                E("Recubrir...", "PartDesign_SubtractiveLoft"),
            ], env="P"),
            S("Operaciones", [
                E("Redondeo...", "PartDesign_Fillet"),
                E("Chaflán...", "PartDesign_Chamfer"),
                E("Asistente para taladro...", "PartDesign_Hole"),
                SEP,
                E("Ángulo de salida...", "PartDesign_Draft"),
                E("Vaciado...", "PartDesign_Thickness"),
                SEP,
                E("Combinar...", "SWUI_Combine"),
                E("Mover/Copiar...", "SWUI_MoveBodies"),
                E("Eliminar/Conservar sólido...", "SWUI_DeleteBodies"),
            ], env="P"),
            S("Matriz/Simetría", [
                E("Matriz lineal...", "PartDesign_LinearPattern"),
                E("Matriz circular...", "PartDesign_PolarPattern"),
                E("Simetría...", "PartDesign_Mirrored"),
            ], env="P"),
            S("Cara", [E("Mover...", "SWUI_MoveFace")], env="P"),
            S("Curva", [E("Hélice/Espiral...", "PartDesign_AdditiveHelix")], env="P"),
            S("Geometría de referencia", [
                E("Plano...", "PartDesign_Plane"),
                E("Eje...", "PartDesign_Line"),
                E("Sistema de coordenadas...", "PartDesign_CoordinateSystem"),
                E("Punto...", "PartDesign_Point"),
            ], env="P"),
            S("Chapa metálica", [
                E("Brida base...", "SWUI_SMBaseFlange"),
                E("Convertir en chapa metálica...", "SWUI_SMConvert"),
                E("Brida de arista...", "SWUI_SMEdgeFlange"),
                E("Dobladillo...", "SWUI_SMHem"),
                SEP,
                E("Desdoblar...", "SWUI_SMUnfold"),
                E("Doblar...", "SWUI_SMFold"),
                E("Aplanar", "SWUI_SMFlatten"),
                SEP,
                E("Corte normal (extruir corte)...", "SWUI_SMCut"),
            ], env="P"),
            S("Piezas soldadas", [  # como el menú de SW 2018 (07/11)
                E("Miembro estructural...", "SWUI_WeldMember"),
                E("Recortar/Alargar...", "SWUI_WeldTrim"),
                E("Tratamiento de esquinas...", "SWUI_WeldCorners"),
                SEP,
                E("Tapa de extremo...", "SWUI_WeldEndCap"),
                E("Cartela...", "SWUI_WeldGusset"),
                SEP,
                E("Lista de cortes...", "SWUI_WeldCutList"),
            ], env="P"),
            SEP,
            # Ensamblaje
            S("Componente", [
                E("Pieza/Ensamblaje existente...", "Assembly_InsertLink"),
                E("Nueva pieza...", "Assembly_InsertNewPart"),
            ], env="E"),
            E("Relación de posición...", "SWUI_Mate", env="E"),
            S("Matriz de componente", [
                E("Matriz lineal...", "SWUI_ComponentLinearPattern"),
                E("Matriz circular...", "SWUI_ComponentCircularPattern"),
            ], env="E"),
            E("Simetría de componentes...", "SWUI_MirrorComponents", env="E"),
            E("Vista explosionada...", "Assembly_CreateView", env="E"),
            E("Nuevo estudio de movimiento", "Assembly_CreateSimulation", env="E"),
            S("Operación de ensamblaje", [
                S("Cortar", [E("Extruir...", "SWUI_AssemblyCut")]),
                S("Taladro", [E("Asistente para taladro...", "SWUI_AssemblyHole")]),
            ], env="E"),
            S("Geometría de referencia ", [  # el espacio la distingue de la de Pieza (mismo menú)
                E("Plano...", "SWUI_AssemblyPlane"),
                E("Eje...", "SWUI_AssemblyAxis"),
                E("Punto...", "SWUI_AssemblyPoint"),
            ], env="E"),
            S("Tablas", [E("Lista de materiales...", "Assembly_CreateBom")], env="E"),
            SEP,
            # Plano
            S("Vista de dibujo", [
                E("Modelo...", "TechDraw_View"),
                E("Proyectada", "SWUI_ProjectedView"),
                E("Sección", "TechDraw_SectionView"),
                E("Alineada de sección", "TechDraw_ComplexSection"),
                E("Detalle", "TechDraw_DetailView"),
                E("3 vistas estándar...", "TechDraw_ProjectionGroup"),
                E("Rotura", "TechDraw_BrokenView"),
                E("Recortar vista", "TechDraw_ClipGroup"),
                SEP,
                E("Escala de la vista...", "SWUI_ViewScale"),
            ], env="D"),
            S("Anotaciones", [
                E("Nota...", "TechDraw_RichTextAnnotation"),
                S("Rosca cosmética", [
                    E("Agujero, vista lateral", "TechDraw_ExtensionThreadHoleSide"),
                    E("Agujero, vista de frente", "TechDraw_ExtensionThreadHoleBottom"),
                    E("Perno, vista lateral", "TechDraw_ExtensionThreadBoltSide"),
                    E("Perno, vista de frente", "TechDraw_ExtensionThreadBoltBottom"),
                ]),
                E("Texto", "SWUI_Text"),
                E("Globo...", "TechDraw_Balloon"),
                E("Símbolo de acabado superficial...", "SWUI_SurfaceFinish"),
                E("Símbolo de soldadura...", "SWUI_WeldSymbol"),
                E("Línea indicativa", "TechDraw_LeaderLine"),
                SEP,
                E("Centro de círculo...", "TechDraw_ExtensionCircleCenterLines"),
                E("Centro de círculo de taladros", "TechDraw_ExtensionHoleCircle"),
                E("Línea constructiva...", "TechDraw_FaceCenterLine"),
                E("Línea constructiva entre 2 líneas", "TechDraw_2LineCenterLine"),
                E("Línea constructiva entre 2 puntos", "TechDraw_2PointCenterLine"),
                SEP,
                E("Área rayada/Rellenar", "TechDraw_Hatch"),
            ], env="D"),
            E("Hoja...", "TechDraw_PageDefault", env="D"),
            E("Imagen...", "SWUI_InsertImage", env="D"),
            E("Propiedades de hoja...", "SWUI_SheetProperties", env="D"),
            E("Formato de línea...", "SWUI_LineFormat", env="D"),
            SEP,
            # Croquis
            E("Croquis", {"P": "PartDesign_NewSketch", "C": "Sketcher_LeaveSketch"}, env="PC",
              label_c="Salir del croquis"),  # como SW: dentro del croquis cambia el nombre
        ]),
        ("Herramientas", [
            E("Selección de cuadro", "Std_BoxSelection"),
            E("Selección de cuadro de elementos", "Std_BoxElementSelection"),
            SEP,
            S("Entidades de croquis", [
                E("Línea", {"C": "Sketcher_CreatePolyline", "D": "SWUI_SheetShape_Line"}, env="CD"),
                E("Rectángulo de esquina", {"C": "Sketcher_CreateRectangle", "D": "SWUI_SheetShape_Rectangle"},
                  env="CD"),
                E("Rectángulo de centro", "Sketcher_CreateRectangle_Center"),
                E("Ranura recta", "Sketcher_CreateSlot"),
                E("Ranura de arco", "Sketcher_CreateArcSlot"),
                E("Polígono", {"C": "Sketcher_CreateRegularPolygon", "D": "SWUI_SheetShape_Polygon"}, env="CD"),
                SEP,
                E("Círculo", {"C": "Sketcher_CreateCircle", "D": "SWUI_SheetShape_Circle"}, env="CD"),
                E("Círculo perimetral", "Sketcher_Create3PointCircle"),
                E("Arco centro extremos", {"C": "Sketcher_CreateArc", "D": "SWUI_SheetShape_Arc"}, env="CD"),
                E("Arco 3 puntos", "Sketcher_Create3PointArc"),
                SEP,
                E("Elipse", "Sketcher_CreateEllipseByCenter"),
                E("Elipse parcial", "Sketcher_CreateArcOfEllipse"),
                E("Parábola", "Sketcher_CreateArcOfParabola"),
                E("Spline", "Sketcher_CreateBSpline"),
                E("Punto", "Sketcher_CreatePoint"),
                E("Línea constructiva", "SWUI_Centerline"),
                E("Línea de punto medio", "SWUI_MidpointLine"),
            ], env="C"),
            S("Herramientas de croquizar", [
                E("Redondeo...", "Sketcher_CreateFillet"),
                E("Chaflán de croquis...", "Sketcher_CreateChamfer"),
                E("Equidistanciar entidades...", "SWUI_SketchOffset"),
                E("Convertir entidades", "Sketcher_Projection"),
                E("Curva de intersección", "Sketcher_Intersection"),
                SEP,
                E("Recortar", "Sketcher_Trimming"),
                E("Extender", "Sketcher_Extend"),
                E("Partir entidades", "Sketcher_Split"),
                E("Geometría constructiva", "Sketcher_ToggleConstruction"),
                SEP,
                E("Simetría", "SWUI_SketchMirror"),
                E("Mover", "SWUI_SketchMove"),
                E("Copiar", "SWUI_SketchCopy"),
                E("Girar", "SWUI_SketchRotate"),
                E("Escala", "SWUI_SketchScale"),
                E("Matriz lineal", "SWUI_SketchLinearPattern"),
            ], env="C"),
            S("Cotas", [
                E("Inteligente", {"C": "Sketcher_Dimension", "D": "TechDraw_Dimension"}, env="CD"),
                E("Horizontal", {"C": "Sketcher_ConstrainDistanceX", "D": "TechDraw_HorizontalDimension"},
                  env="CD"),
                E("Vertical", {"C": "Sketcher_ConstrainDistanceY", "D": "TechDraw_VerticalDimension"}, env="CD"),
                E("Cota de cadena", "TechDraw_ExtensionCreateHorizChainDimension", env="D"),
                E("Cota de coordenadas", "TechDraw_ExtensionCreateHorizCoordDimension", env="D"),
                E("Cota de chaflán", "TechDraw_ExtensionCreateHorizChamferDimension", env="D"),
                E("Cota conducida", "Sketcher_ToggleDrivingConstraint", env="C"),
            ]),
            S("Relaciones", [
                E("Coincidente", "Sketcher_ConstrainCoincidentUnified"),
                E("Horizontal", "Sketcher_ConstrainHorizontal"),
                E("Vertical", "Sketcher_ConstrainVertical"),
                E("Paralela", "Sketcher_ConstrainParallel"),
                E("Perpendicular", "Sketcher_ConstrainPerpendicular"),
                E("Tangente", "Sketcher_ConstrainTangent"),
                E("Igual", "Sketcher_ConstrainEqual"),
                E("Simétrica", "Sketcher_ConstrainSymmetric"),
                E("Fijar", "Sketcher_ConstrainLock"),
            ], env="C"),
            SEP,
            E("Ecuaciones...", "SWUI_Equations", env="PE"),
            E("Editar material...", "SWUI_Material", env="P"),
            SEP,
            S("Macro", [
                E("Ejecutar...", "Std_DlgMacroExecute"),
                E("Grabar...", "Std_DlgMacroRecord"),
                E("Recientes", "Std_RecentMacros"),
            ]),
            S("Evaluar", [
                E("Medir...", "SWUI_Measure", k="Espacio"),
                E("Propiedades físicas...", "SWUI_MassProperties", env="PE"),
                E("Verificar...", "Part_CheckGeometry", env="P"),
                SEP,
                E("¿Qué es incorrecto?", "SWUI_WhatsWrong", env="PE"),
                E("Reparar referencias...", "SWUI_RepairReferences", env="PE"),
            ]),
            SEP,
            E("Personalizar...", "Std_DlgCustomize"),
            E("Opciones...", "Std_DlgPreferences"),
        ]),
        ("FreeWorks", [
            E("Usar siempre FreeWorks", "SWUI_AlwaysSWUI"),
            E("Velocidad de giro...", "SWUI_OrbitSpeed"),
            E("Guardar también STEP", "SWUI_AlsoSaveStep"),
            E("Chequear carpeta...", "SWUI_CheckFolder"),
            E("Diagnóstico", "SWUI_Diagnostics"),
            S("Idioma", _language_items()),
            S("IA", [
                E("Puente IA", "SWUI_IABridge"),
                E("Conectar la IA...", "SWUI_IAConnect"),
            ]),
            SEP,
            S("FreeCAD", [
                E("Mostrar los menús originales de FreeCAD", ORIGINALS_CMD),
                SEP,
                E("Bancos de trabajo", "Std_Workbench"),
                E("Complementos (gestor de addons)...", "Std_AddonMgr"),
                E("Paneles", "Std_DockViewMenu"),
                E("Barras de herramientas de FreeCAD", "Std_ToolBarMenu"),
                SEP,
                E("Propiedades (panel Ver/Datos)", "Std_Properties"),
                E("Apariencia (color y transparencia)...", "Std_SetAppearance"),
                E("Colocación (mover con números)...", "Std_Placement"),
                E("Alinear a...", "Std_Alignment"),
                E("Duplicar selección", "Std_DuplicateSelection"),
                E("Aclarar selección", "Std_ClarifySelection"),
                SEP,
                E("Gráfico de dependencias...", "Std_DependencyGraph"),
                E("Exportar gráfico de dependencias...", "Std_ExportDependencyGraph"),
                E("Fusionar documento...", "Std_MergeProjects"),
                E("Información del documento...", "Std_ProjectInfo"),
                E("Convertidor de unidades...", "Std_UnitsCalculator"),
                E("Cargar imagen en la vista 3D...", "Std_ViewLoadImage"),
                SEP,
                S("Diseño de piezas extra", [
                    E("Engranaje (involuta)...", "PartDesign_InvoluteGear"),
                    E("Piñón de cadena...", "PartDesign_Sprocket"),
                    E("Asistente para ejes...", "PartDesign_WizardShaft"),
                ], env="P"),
                S("Croquis extra", [
                    E("Reparar croquis (Validar)...", "Sketcher_ValidateSketch"),
                    E("Seleccionar lo que falta definir", "Sketcher_SelectElementsWithDoFs", env="C"),
                    E("Copia de carbón", "Sketcher_CarbonCopy", env="C"),
                    E("Reflejar croquis", "Sketcher_MirrorSketch"),
                    E("Unir croquis", "Sketcher_MergeSketches"),
                ], env="PC"),
                SEP,
                E("Editor de parámetros...", "Std_DlgParameter"),
            ]),
        ]),
        # Ventana y "?" son los menús de FreeCAD (&Windows y &Help no se pueden sacar: FreeCAD los usa
        # de referencia para ubicar los demás y sin &Help da "Access violation", probado en 1.1.4).
        # Se les cambia el título, se agrega lo que falta y se oculta lo que no va (HIDE).
        ("&Windows", [
            SEP,
            E("Nueva ventana", "Std_ViewCreate"),
            E("Cerrar todo", "Std_CloseAllWindows"),
        ]),
    ]


KEEP_MENUS = ("&Windows", "&Help")
TOP_TITLES = {"&Windows": "Ventana", "&Help": "?"}  # objectName del menú -> título de SW
# textos de SW para lo que FreeCAD ya trae en Ventana y en "?"
NATIVE_TEXTS = {
    "Std_ActivateNextWindow": "Siguiente", "Std_ActivatePrevWindow": "Anterior",
    "Std_TileWindows": "Mosaico", "Std_CascadeWindows": "Cascada",
    "Std_Windows": "Examinar documentos abiertos...",
    "Std_WhatsThis": "¿Qué es esto?", "Start_Start": "Página de inicio",
    "Std_FreeCADUserHub": "Documentación de FreeCAD", "Std_FreeCADForum": "Foro de FreeCAD",
    "Std_ReportBug": "Informar de un problema", "Std_RestartInSafeMode": "Reiniciar en modo seguro",
    "Std_About": "Acerca de FreeCAD",
}
# de "?" de FreeCAD: lo que no va (revisado con el usuario en la maqueta)
HIDE = ("Std_DevHandbook", "Std_PythonHelp", "Std_FreeCADWebsite", "Std_FreeCADDonation")


# --- Entorno -----------------------------------------------------------------------

_env_cache = {"t": 0.0, "v": None}


def current_env():
    """'P', 'E', 'D', 'C' o None (sin documento). Se recalcula como mucho cada 0,25 s."""
    now = time.monotonic()
    if now - _env_cache["t"] < 0.25:
        return _env_cache["v"]
    _env_cache["t"], _env_cache["v"] = now, _compute_env()
    return _env_cache["v"]


def _compute_env():
    try:
        from swui import ribbon

        if ribbon._editing_sketch():
            return "C"
        if ribbon._drawing_active():
            return "D"
    except Exception:
        pass
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None
    try:
        from swui.fork import asm_tab

        kind = asm_tab.kind_of(doc)
    except Exception:
        kind = None
    if kind == "assembly":
        return "E"
    if kind is None and any(o.TypeId == "TechDraw::DrawPage" for o in doc.Objects):
        return "D"
    return "P"


def env_ok(env, current=None):
    """¿Corresponde la entrada al entorno? Editando un croquis, Pieza sigue activa (como SW)."""
    if not env:
        return True
    cur = current_env() if current is None else current
    if cur is None:
        return False
    return cur in env or (cur == "C" and "P" in env)


def resolve(target, current=None):
    """Comando a usar según el entorno (target puede ser {entorno: comando})."""
    if not isinstance(target, dict):
        return target
    cur = current_env() if current is None else current
    if cur in target:
        return target[cur]
    if cur == "C" and "P" in target:
        return target["P"]
    return None


# --- Comandos envoltorio -------------------------------------------------------------


def _command_exists(name):
    try:
        return FreeCADGui.Command.get(name) is not None
    except Exception:
        return False


def _info(name):
    try:
        return FreeCADGui.Command.get(name).getInfo() or {}
    except Exception:
        return {}


def _pixmap(name):
    """
    Los íconos de TechDraw están en :/icons/actions/, carpeta que FreeCAD suma recién al abrir el
    banco TechDraw: pedidos por nombre al armar la barra daban "Cannot find icon: TechDraw_View" en
    las notificaciones al arrancar (visto por el usuario, 01/11). Se pasa la ruta completa, o nada
    si no existe (TechDraw_ExportPagePDF no está en ningún lado). Los demás, por nombre.
    """
    if not name or not name.startswith("TechDraw_"):
        return name
    path = ":/icons/actions/%s.svg" % name
    try:
        return path if QtCore.QFile.exists(path) else None
    except Exception:
        return None


class _Wrapper:
    """Entrada de menú propia: texto de SW, gris según el entorno, ejecuta como la cinta."""

    def __init__(self, entry, env):
        self.entry, self.env = entry, env

    def GetResources(self):
        e = self.entry
        text = e["label"] + ("\t" + e["k"] if e.get("k") else "")
        # ForEdit: si no, FreeCAD lo apaga con cualquier panel abierto (el croquis es uno). Como la
        # cinta, que pregunta IsActive sin esa regla; un panel abierto lo cancela panel_guard.
        res = {"MenuText": text, "ToolTip": e.get("tip") or e["label"], "CmdType": "ForEdit"}
        target = e["target"]
        first = next(iter(target.values())) if isinstance(target, dict) else target
        if isinstance(first, str):
            info = _info(first)
            if info.get("toolTip") and not e.get("tip"):
                res["ToolTip"] = re.sub(r"<[^>]+>", "", info["toolTip"]).strip() or e["label"]
            pixmap = _pixmap(info.get("pixmap"))
            if pixmap:
                res["Pixmap"] = pixmap
        return res

    def IsActive(self):
        try:
            if not env_ok(self.env):
                return False
            target = resolve(self.entry["target"])
            if target is None:
                return False
            if callable(target):
                return True
            cmd = FreeCADGui.Command.get(target)
            return cmd is not None and bool(cmd.isActive())
        except Exception:
            return False

    def Activated(self, *_args):
        target = resolve(self.entry["target"])
        if target is None:
            return
        # fuera del comando: FreeCAD deja para después un comando corrido desde otro (NOTAS)
        QtCore.QTimer.singleShot(0, functools.partial(_run, target, self.entry.get("index")))


def _run(target, index=None):
    try:
        if callable(target):
            target()
            return
        from swui import ribbon

        ribbon._run(target, index)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Menú: %s\n" % traceback.format_exc())


class _Originals:
    def GetResources(self):
        return {"MenuText": "Mostrar los menús originales de FreeCAD",
                "ToolTip": "Salida de emergencia: vuelve a los menús de FreeCAD (se aplica al reiniciar)",
                "Checkable": originals_wanted()}

    def IsActive(self):
        return True

    def Activated(self, checked=None):
        on = bool(checked) if checked is not None else not originals_wanted()
        FreeCAD.ParamGet(PARAMS).SetBool(ORIGINALS_KEY, on)
        msg = ("Al reiniciar FreeCAD vuelven los menús originales de FreeCAD (para volver a los de "
               "FreeWorks: FreeWorks > Mostrar los menús originales de FreeCAD)." if on else
               "Al reiniciar FreeCAD vuelven los menús de FreeWorks.")
        try:
            QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "FreeWorks", msg)
        except Exception:
            FreeCAD.Console.PrintMessage("[SWUI fork] %s\n" % msg)


def originals_wanted():
    try:
        return FreeCAD.ParamGet(PARAMS).GetBool(ORIGINALS_KEY, False)
    except Exception:
        return False


def _slug(text):
    table = str.maketrans("áéíóúñÁÉÍÓÚÑ", "aeiounAEIOUN")
    return re.sub(r"[^A-Za-z0-9]+", "", text.translate(table).title())


def _needs_wrapper(entry):
    target = entry["target"]
    return bool(entry.get("env") or entry.get("k") or entry.get("index") is not None
                or not isinstance(target, str))


def plan(structure=None):
    """
    De la estructura a lo que hay que hacer:
    (llamadas [(ruta, [comandos o 'Separator'])], envoltorios {nombre: (entrada, entorno)},
    textos {comando de FreeCAD usado directo: texto de SW}).
    """
    calls, wrappers, labels = [], {}, {}

    def walk(path, items, env):
        run = []
        for it in items:
            if it == SEP:
                run.append("Separator")
            elif "items" in it:
                if run:
                    calls.append((list(path), run))
                    run = []
                walk(path + [it["label"]], it["items"], it.get("env") or env)
            else:
                entry_env = it.get("env") or env
                if entry_env or _needs_wrapper(it):
                    name = PREFIX + "_".join(_slug(p) for p in path + [it["label"]])
                    while name in wrappers:
                        name += "_"
                    wrappers[name] = (it, entry_env)
                    run.append(name)
                else:
                    run.append(it["target"])
                    labels[it["target"]] = it["label"]
        if run:
            calls.append((list(path), run))

    for title, items in (structure if structure is not None else menus()):
        walk([title], items, None)
    return calls, wrappers, labels


# --- Armar la barra ------------------------------------------------------------------

_state = {"applied": False, "labels": {}, "texts": [], "keys": [], "hidden": [], "filter": None,
          "pending": False, "hidden_actions": [], "watched": set(), "wrappers": {}, "submenus": set()}


def _register_partdesign_extras():
    """Engranaje, Piñón y Asistente para ejes los registra Part Design recién al abrir su banco."""
    pairs = (("PartDesign_InvoluteGear", "PartDesign.InvoluteGearFeature", "CommandInvoluteGear"),
             ("PartDesign_Sprocket", "PartDesign.SprocketFeature", "CommandSprocket"))
    for name, module, cls in pairs:
        if _command_exists(name):
            continue
        try:
            mod = __import__(module, fromlist=[cls])
            FreeCADGui.addCommand(name, getattr(mod, cls)())
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Menú: sin %s\n" % name)
    if not _command_exists("PartDesign_WizardShaft"):
        try:
            from PartDesign.WizardShaft import WizardShaft  # noqa: F401  (registra el comando)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Menú: sin PartDesign_WizardShaft\n")


def apply(wb):
    """
    Sacar los menús estándar del banco y poner los de SW. Se hace dentro de Initialize, antes de que
    FreeCAD arme la barra: rearmarla después (`reloadActive`) mientras el banco arranca da "Access
    violation" en 1.1.4 y deja el banco roto (probado).
    """
    if _state["applied"] or originals_wanted() or wb is None:
        return False
    try:
        try:
            from swui import ribbon

            ribbon._load_gui_modules()  # comandos de Croquis, Part Design, TechDraw y Ensamblaje
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Menú: módulos de FreeCAD:\n%s\n" % traceback.format_exc())
        _register_partdesign_extras()
        calls, wrappers, labels = plan()
        for name, (entry, env) in wrappers.items():
            wrapper = _Wrapper(entry, env)
            try:
                FreeCADGui.addCommand(name, wrapper)
                _state["wrappers"][name] = wrapper
            except Exception:
                pass  # ya registrado
        for menu in list(wb.listMenus()):
            if menu in KEEP_MENUS:
                continue
            try:
                wb.removeMenu(menu)
            except Exception:
                FreeCAD.Console.PrintLog("[SWUI fork] Menú: no se sacó %s\n" % menu)
        for path, items in calls:
            items = [c for c in items if c == "Separator" or c.startswith(PREFIX) or _command_exists(c)]
            if items:
                wb.appendMenu(path if len(path) > 1 else path[0], items)
        _state["labels"] = dict(NATIVE_TEXTS, **labels)
        _state["submenus"] = {name for p, _items in calls for name in p[1:]}
        _state["applied"] = True
        _ignore_old_menu(wb)
        return True
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Menús estilo SW:\n%s\n" % traceback.format_exc())
        return False


def _ignore_old_menu(wb):
    """InitGui agrega "Diagnose" al menú viejo después de fork.install: ya está en FreeWorks, así que
    lo que llegue a ese menú se descarta (solo en este objeto del banco)."""
    original = wb.appendMenu

    def append(name, commands, _original=original):
        if name == OLD_MENU:
            return None
        return _original(name, commands)

    try:
        wb.appendMenu = append
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Menú: no se pudo filtrar el menú viejo.\n")


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _action_class():
    return QtGui.QAction if hasattr(QtGui, "QAction") else QtWidgets.QAction  # Qt6 / Qt5


def _menu_actions():
    """Acciones (con submenús) de nuestra barra."""
    out = []

    def walk(menu, depth):
        for a in menu.actions():
            out.append(a)
            if a.menu() is not None and depth < 4:
                walk(a.menu(), depth + 1)

    try:
        for a in FreeCADGui.getMainWindow().menuBar().actions():
            if a.menu() is not None:
                walk(a.menu(), 0)
    except Exception:
        pass
    return out


# títulos de submenús que arma FreeCAD (grupos de comandos): texto sin & -> texto de SW
SUBMENU_TEXTS = {"Workbench": "Bancos de trabajo", "Macros recientes": "Recientes",
                 "Abrir reciente": "Abrir reciente"}


def _fix_accents(text):
    """Los nombres de menú que se pasan a appendMenu llegan con las tildes rotas ("EdiciÃ³n"): 1.1.4
    los toma como Latin-1. Se arreglan en el texto que se ve; None si no hace falta."""
    if not text or "Ã" not in text:
        return None
    try:
        return text.encode("latin-1").decode("utf-8")
    except Exception:
        return None


def relabel():
    """Textos de SW en los comandos de FreeCAD usados directo (se guarda el original)."""
    if not _state["applied"] or not _in_workbench():
        return
    labels = _state["labels"]
    known = {id(a) for a, _t in _state["texts"]}
    hidden = {id(a) for a in _state["hidden_actions"]}

    def set_text(action, new):
        if new is None:
            new = _fix_accents(action.text())
        if new is None or action.text() == new:
            return
        if id(action) not in known:
            _state["texts"].append((action, action.text()))
            known.add(id(action))
        action.setText(new)

    try:
        for action in FreeCADGui.getMainWindow().menuBar().actions():
            menu = action.menu()
            if menu is not None:
                set_text(action, TOP_TITLES.get(menu.objectName()))
                if id(menu) not in _state["watched"]:
                    _state["watched"].add(id(menu))
                    menu.aboutToShow.connect(_refresh_states)
    except Exception:
        pass
    try:
        for action in FreeCADGui.getMainWindow().menuBar().actions():
            if action.menu() is not None:
                _show_separators(action.menu(), 0)
    except Exception:
        pass
    for action in _menu_actions():
        name = action.objectName()
        if name in HIDE:
            if id(action) not in hidden and action.isVisible():
                _state["hidden_actions"].append(action)
                hidden.add(id(action))
                action.setVisible(False)
            continue
        new = labels.get(name)
        if new is None:
            new = SUBMENU_TEXTS.get(action.text().replace("&", ""))
        set_text(action, new)


def _show_separators(menu, depth):
    """FreeCAD deja ocultas algunas líneas de separación (antes de un submenú, visto con el mouse en
    FreeWorks): se muestran las que quedan entre dos entradas que se ven."""
    actions = [a for a in menu.actions() if a.isSeparator() or a.isVisible()]
    for i, action in enumerate(actions):
        if action.isSeparator():
            if (not action.isVisible() and 0 < i < len(actions) - 1
                    and not actions[i - 1].isSeparator() and not actions[i + 1].isSeparator()):
                action.setVisible(True)
        elif action.menu() is not None and depth < 5:
            _show_separators(action.menu(), depth + 1)


def _refresh_states():
    """Al abrir un menú: FreeCAD pregunta qué está activo solo ante ciertos cambios (selección,
    documento), no al pasar a una hoja de plano o al abrir el menú; se actualizan los nuestros acá.
    (FreeCADGui no tiene updateCommands en 1.1.4.)"""
    if not _in_workbench():
        return
    _env_cache["t"] = 0.0
    wrappers = _state["wrappers"]
    try:
        for action in FreeCADGui.getMainWindow().findChildren(_action_class()):
            wrapper = wrappers.get(action.objectName())
            if wrapper is not None:
                action.setEnabled(wrapper.IsActive())
                other = wrapper.entry.get("label_c")
                if other:
                    action.setText(other if current_env() == "C" else wrapper.entry["label"])
        for action in FreeCADGui.getMainWindow().menuBar().actions():
            if action.menu() is not None:
                _grey_submenus(action.menu(), 0)
    except Exception:
        pass


def _grey_submenus(menu, depth):
    """
    Como SW: un submenú nuestro con todo lo de adentro en gris queda en gris (en el plano,
    Insertar > Saliente/Base...). Devuelve si el menú tiene algo activo. Solo se tocan los
    submenús que arma este módulo (los de FreeCAD, como Abrir reciente, quedan como están).
    """
    any_on = False
    for action in menu.actions():
        if action.isSeparator() or not action.isVisible():
            continue
        sub = action.menu()
        if sub is not None and depth < 5:
            on = _grey_submenus(sub, depth + 1)
            if action.text() in _state["submenus"]:
                action.setEnabled(on)
            else:
                on = action.isEnabled()
        else:
            on = action.isEnabled()
        any_on = any_on or on
    return any_on


def restore_texts():
    for action, text in _state["texts"]:
        try:
            action.setText(text)
        except Exception:
            pass  # la acción ya no existe
    del _state["texts"][:]
    for action in _state["hidden_actions"]:
        try:
            action.setVisible(True)
        except Exception:
            pass
    del _state["hidden_actions"][:]


def add_keys():
    """Ctrl+W y F11 como en SW, sobre las acciones de FreeCAD (se devuelve al salir)."""
    if _state["keys"]:
        return
    try:
        mw = FreeCADGui.getMainWindow()
        actions = mw.findChildren(_action_class())
        owners = {}
        for key, command in SW_KEYS:
            for action in actions:
                if action.objectName() == command:
                    owners[key] = action
                    break
        taken = set(owners)
        for action in actions:
            if action in owners.values():
                continue
            shortcuts = list(action.shortcuts())
            keep = [s for s in shortcuts if s.toString() not in taken]
            if len(keep) != len(shortcuts):
                _state["hidden"].append((action, shortcuts))
                action.setShortcuts(keep)
        for key, action in owners.items():
            shortcuts = list(action.shortcuts())
            _state["keys"].append((action, shortcuts))
            action.setShortcuts([QtGui.QKeySequence(key)] + [s for s in shortcuts if s.toString() != key])
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Menú, atajos de SW:\n%s\n" % traceback.format_exc())


def remove_keys():
    for action, shortcuts in _state["keys"] + _state["hidden"]:
        try:
            action.setShortcuts(shortcuts)
        except Exception:
            pass  # la acción ya no existe
    del _state["keys"][:]
    del _state["hidden"][:]


def enter():
    if not _state["applied"] or not _in_workbench():
        return
    relabel()
    add_keys()


def leave():
    restore_texts()
    remove_keys()


def _on_workbench(name):
    if name == WB_NAME:
        QtCore.QTimer.singleShot(0, enter)
    else:
        leave()


class _MenuBarFilter(QtCore.QObject):
    """FreeCAD rearma la barra también sin cambiar de banco (al abrir un ensamblaje): volver a poner
    los textos (como brand.py)."""

    def eventFilter(self, obj, event):
        try:
            if (event.type() in (QtCore.QEvent.Type.ActionAdded, QtCore.QEvent.Type.ActionChanged)
                    and _state["applied"] and not _state["pending"]):
                _state["pending"] = True
                QtCore.QTimer.singleShot(0, _relabel_later)
        except Exception:
            pass
        return False


def _relabel_later():
    _state["pending"] = False
    relabel()


def install(workbench=None):
    """Comando de la salida de emergencia y armado de la barra (llamado al final de fork.install,
    dentro de Initialize)."""
    try:
        FreeCADGui.addCommand(ORIGINALS_CMD, _Originals())
    except Exception:
        pass  # ya registrado
    if originals_wanted():
        if workbench is not None:
            from swui.fork import MENU

            workbench.appendMenu(MENU, [ORIGINALS_CMD])
        return
    try:
        mw = FreeCADGui.getMainWindow()
        mw.workbenchActivated.connect(_on_workbench)
        if _state["filter"] is None:
            _state["filter"] = _MenuBarFilter()
            mw.menuBar().installEventFilter(_state["filter"])
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Menú: señales no disponibles.\n")
    apply(workbench)
