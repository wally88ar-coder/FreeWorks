# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Clic derecho como SW, la parte que decide (sin ventana): qué caso es lo elegido, qué va en cada
grupo de la tabla, qué va detrás de la "»" y qué se quita (decisiones del usuario 15/11); y para
reordenar arrastrando, a qué lugar va una operación y cuándo una dependencia lo impide."""

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

V = FreeCAD.Vector

# Lo que trae FreeCAD (medido 15/11) en el clic derecho de una operación en el árbol, más lo nuestro
ARBOL_OPERACION = ["SWUI_EditFeature", "SWUI_EditSketch", "SWUI_Suppress", "SWUI_Rollback", "SWUI_MoveUp",
                   "SWUI_MoveDown", "SWUI_ParentChild", "vpedit", "facecolors", "Std_Placement",
                   "Std_ToggleVisibility", "Std_ShowSelection", "Std_HideSelection", "Std_ToggleSelectability",
                   "Std_TreeSelectAllInstances", "Std_SetMaterial", "Std_SetAppearance", "Std_RandomColor",
                   "Std_ToggleTransparency", "Std_Cut", "Std_Copy", "Std_Paste", "Std_Delete",
                   "Std_SendToPythonConsole", "Std_Properties", "expr", "Link Actions", "showhidden", "treevis",
                   "adddeps", "markrecompute", "recompute", "rename", "treesettings"]
VISTA_COMPONENTE = ["clarify", "Link Actions", "SWUI_FixComponent", "SWUI_ViewMates", "SWUI_ComponentSuppress",
                    "Std_ViewFitAll", "Std_ViewFitSelection", "Std_AlignToSelection", "drawstyle",
                    "Standard Views", "docwindow", "Std_ToggleVisibility", "Std_ToggleSelectability",
                    "Std_TreeSelection", "Std_SetMaterial", "Std_SetAppearance", "Std_RandomColor",
                    "Std_ToggleTransparency", "Std_Delete", "Std_SendToPythonConsole", "Std_TransformManip",
                    "Std_Placement", "navstyles"]


class _Obj:
    def __init__(self, label):
        self.Label = label


def _pieza():
    doc = FreeCAD.newDocument("Tabla")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(60, 0, 0), V(60, 40, 0), V(0, 40, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    pad = body.newObject("PartDesign::Pad", "Extruir")
    pad.Profile = sk
    pad.Length = 20
    doc.recompute()
    return doc, body, sk, pad


def prueba():
    from swui.fork import context_menus as cm
    from swui.fork import tree_drag as td

    # Claves: comando, texto conocido en castellano o inglés, "Editar X" de FreeCAD
    assert cm.action_key("Std_Copy", "Copiar") == "Std_Copy"
    assert cm.action_key("", "Renombrar\tF2") == "rename" and cm.action_key("", "&Rename") == "rename"
    assert cm.action_key("", "Aclarar selección") == "clarify" and cm.action_key("", "Editar Pad") == "vpedit"
    assert cm.action_key("", "Algo nuevo de 26.3") == "txt:Algo nuevo de 26.3"

    # Qué caso es
    doc, body, sk, pad = _pieza()
    assert cm.context_of([(body, ["Extruir."])]).kind == "feature"
    face = cm.context_of([(body, ["Extruir.Face6"])])
    assert face.kind == "feature" and face.element_kind == "Face" and face.planar and face.feature is pad, \
        (face.kind, face.element, face.planar)
    assert cm.context_of([(body, ["Croquis."])]).kind == "sketch"
    assert cm.context_of([(body, [""])]).kind is None, "el Cuerpo es el caso general"
    assert cm.context_of([]).kind is None and cm.context_of([(body, ["Extruir.Face1", "Extruir.Face2"])]).kind is None
    assert cm.plain_sub("Extruir.;#14:1;:G0;XTR;:H55e:8,F.Face6") == "Extruir.Face6"

    # Operación en el árbol: la tabla del usuario
    ctx = cm.context_of([(body, ["Extruir."])])
    groups, behind, removed = cm.place(ARBOL_OPERACION, ctx, "Tree")
    assert groups[0] == (None, ["SWUI_EditFeature", "SWUI_EditSketch", "SWUI_Suppress", "SWUI_Rollback",
                                "Std_HideSelection", "Std_SetAppearance"]), groups[0]
    assert groups[1][0] == "Operación (%s)" % pad.Label
    assert groups[1][1] == ["SWUI_ParentChild", "SWUI_ConfigureFeature", "Std_Delete", "Std_ToggleTransparency",
                            "SWUI_CollapseTree"], groups[1]
    for k in ("SWUI_MoveUp", "SWUI_MoveDown", "vpedit", "Std_SendToPythonConsole", "expr", "Link Actions",
              "markrecompute", "treesettings", "Std_RandomColor"):
        assert k in removed and k not in behind, k
    for k in ("Std_Placement", "Std_Copy", "rename", "Std_Properties"):
        assert k in behind, k
    usados = [k for _t, ks in groups for k in ks]
    assert not set(usados) & set(behind) and not set(usados) & set(removed), "una clave en dos lugares"

    # Cara de un componente en la vista: Zoom/Trasladar/Girar fuera; sin "Cambiar de nombre" (solo en el árbol)
    comp = cm.Context("component", component=None, element="Face6", visible=True)
    comp.component = type("L", (), {"Label": "TacoB", "LinkedObject": None})()
    groups, behind, removed = cm.place(VISTA_COMPONENTE, comp, "View")
    assert groups[0][1][:3] == ["clarify", "Std_LinkSelectLinked", "SWUI_OpenPartInPosition"], groups[0]
    assert groups[1] == (None, ["SWUI_InvertSelection", "submenu:selection"]), groups[1]
    assert groups[2] == ("Componente (TacoB)", ["SWUI_RenameComponent", "SWUI_Isolate", "SWUI_FixComponent",
                                                "Std_Delete", "SWUI_ComponentParentChild",
                                                "SWUI_ComponentMaterial"]), groups[2]
    for k in ("Std_ViewFitAll", "drawstyle", "Standard Views", "docwindow", "navstyles"):
        assert k in removed, k
    # Varios componentes (E1): menú "Componente" sin nombre, sin Cambiar de nombre / Propiedades /
    # Padre/Hijo / Seleccionar otra; los comandos que FreeCAD no puso se piden
    varios = cm.Context("components", components=[comp.component, comp.component], visible=True)
    assert cm.title_of(varios) == "Componente"
    groups, behind, removed = cm.place(VISTA_COMPONENTE, varios, "View")
    assert groups[0][1] == ["SWUI_OpenParts", "SWUI_OpenPartInPosition", "Std_HideSelection",
                            "Std_ToggleTransparency", "SWUI_ComponentSuppress", "SWUI_ComponentUnsuppress",
                            "SWUI_Mate", "SWUI_ViewMates", "Std_SetAppearance"], groups[0]
    assert groups[1] == (None, ["SWUI_InvertSelection"]), groups[1]
    assert groups[2] == ("Componente", ["SWUI_Isolate", "SWUI_ComponentConfig", "SWUI_FixComponent",
                                        "SWUI_FloatComponent", "Std_Delete", "SWUI_ComponentMaterial"]), groups[2]
    oculto = cm.Context("components", components=[comp.component], visible=False)
    assert "Std_ShowSelection" in cm.place([], oculto, "Tree")[0][0][1], "con alguno oculto: Mostrar"
    arbol = cm.place([], varios, "Tree")[0]
    assert arbol[2][1][-1] == "SWUI_CollapseTree", arbol[2]
    # Un componente solo: los comandos de varios no se piden (queda como antes)
    groups, _b, _r = cm.place(VISTA_COMPONENTE, comp, "View")
    assert "SWUI_ComponentConfig" not in groups[2][1] and "SWUI_FloatComponent" not in groups[2][1]
    # La misma cara nombrada de dos maneras (por el Cuerpo o por la operación) es la misma
    assert cm.same_element(None, "Body003.Body.;Face6;:H18d,F.Face6", "Body003.Body.Face6")
    assert not cm.same_element(None, "Body003.Body.Face6", "Body002.Body.Face6")
    assert not cm.same_element(None, "Body003.Body.Face6", "Body003.Body.Edge6")

    # Sin nada elegido (fondo vacío) el zoom queda: es lo único que tiene ese menú
    _g, _b, removed = cm.place(["Std_ViewFitAll", "drawstyle", "Std_SendToPythonConsole"], cm.Context(), "View",
                               has_selection=False)
    assert removed == ["Std_SendToPythonConsole"], removed
    # Componente oculto: "Mostrar" en vez de "Ocultar"
    comp.visible = False
    assert "Std_ShowSelection" in cm.place([], comp, "Tree")[0][0][1]
    # Cara plana de la pieza en la vista: Herramientas de selección arriba; Sólido con Aislar y Exportar a DXF
    groups, _b, _r = cm.place(["clarify"], face, "View")
    assert (None, ["submenu:selection"]) in groups, groups
    assert ("Sólido", ["SWUI_Isolate", "SWUI_ExportFaceDXF"]) in groups, groups

    # Herramientas nuevas, sin ventana: tangencia y DXF de una cara
    from swui.fork import context_tools as ct
    import Part as _P
    caja = _P.makeBox(40, 30, 10)
    redondeada = caja.makeFillet(3, [e for e in caja.Edges if abs(e.Vertexes[0].Point.z - 10) < 1e-6
                                     and abs(e.Vertexes[1].Point.z - 10) < 1e-6])
    arriba = [i for i, f in enumerate(redondeada.Faces)
              if abs(f.CenterOfMass.z - 10) < 1e-6 and f.Area > 300][0]
    tang = ct.tangent_faces(redondeada, "Face%d" % (arriba + 1))
    # la tapa y las 4 franjas redondeadas y las 4 esquinas (tangentes entre sí); no los costados planos
    assert len(tang) == 9, "tangencia: %s" % tang
    assert ct.tangent_faces(caja, "Face1") == ["Face1"], "una cara de una caja no tiene tangentes"
    plana = _P.makeBox(50, 20, 5).cut(_P.makeCylinder(4, 5, FreeCAD.Vector(25, 10, 0))).Faces
    tapa = [f for f in plana if abs(f.CenterOfMass.z - 5) < 1e-6][0]
    ents = ct.face_entities(tapa)
    tipos = sorted(e[0] for e in ents)
    assert tipos.count("LINE") == 4 and tipos.count("CIRCLE") == 1, "DXF de la cara: %s" % tipos
    xs = [v for e in ents if e[0] == "LINE" for v in (e[2], e[4])]
    assert abs(min(xs)) < 1e-6 and abs(max(xs) - 50) < 1e-6, "la cara no quedó 1:1 desde 0,0: %s" % xs
    assert abs(ct.part_camera(FreeCAD.Rotation(), FreeCAD.Rotation()).Angle) < 1e-9

    # Reordenar arrastrando: lugar final y dependencias
    a, b, c, d = _Obj("A"), _Obj("B"), _Obj("C"), _Obj("D")
    feats = [a, b, c, d]
    assert td.drop_index(feats, d, a, True) == 0 and td.drop_index(feats, d, a, False) == 1
    assert td.drop_index(feats, a, c, True) == 1 and td.drop_index(feats, a, c, False) == 2
    assert td.drop_index(feats, b, c, True) is None and td.drop_index(feats, b, b, True) is None
    deps = {d: {b}, c: set(), b: set(), a: set()}
    assert td.blocker(feats, d, 0, lambda o: deps[o]) is not None, "D depende de B: no puede quedar arriba"
    assert td.blocker(feats, d, 2, lambda o: deps[o]) is None
    assert td.blocker(feats, b, 3, lambda o: deps[o]) is not None, "B no puede quedar abajo de D, que la usa"
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
