# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#43 (como SW: el desarrollo sigue siempre a la pieza): con el desarrollo ya hecho (después de
Aplanar ida y vuelta queda oculto en el árbol), agregar bridas y dobladillos, quitarlos y cambiar el
espesor nunca lo deja con la cara fija perdida ("?Face6"): cada vez apunta a la cara fija de la
pieza de ese momento. Si el desarrollo da error, es porque SheetMetal no puede desplegar esa pieza
(un desarrollo nuevo da el mismo error), no por la cara vieja."""

import random  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402

V = FreeCAD.Vector


def _chapa(sm):
    import SheetMetalBaseCmd
    doc = FreeCAD.newDocument("DesarrolloSigue")
    body = doc.addObject("PartDesign::Body", "Cuerpo")
    sk = body.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(100, 0, 0), V(100, 40, 0), V(0, 40, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    doc.recompute()
    base = doc.addObject("PartDesign::FeaturePython", "BaseBend")
    SheetMetalBaseCmd.SMBaseBend(base, sk)
    body.addObject(base)
    sm.ensure_k(base)
    base.Thickness = 2
    base.setExpression("Radius", "Thickness")
    doc.recompute()
    flat = sm.ensure_flat(body, sketches=False)
    doc.recompute()
    assert flat.isValid(), "el desarrollo de la placa tendría que salir"
    return doc, body, base, flat


def _rectas(tip):
    return ["Edge%d" % (i + 1) for i, e in enumerate(tip.Shape.Edges)
            if e.Curve.__class__.__name__ == "Line" and e.Length > 10]


def _sacar(doc, body, obj, tip):
    body.removeObject(obj)
    doc.removeObject(obj.Name)
    body.Tip = tip
    doc.recompute()


def _desplegable(doc, body, sm):
    """¿SheetMetal puede desplegar la pieza como está? (con un desarrollo nuevo, que después se borra)"""
    import SheetMetalUnfoldCmd
    nuevo = doc.addObject("Part::FeaturePython", "Prueba")
    SheetMetalUnfoldCmd.SMUnfold(nuevo, body, [sm.fixed_face(body)])
    nuevo.GenerateSketch = False
    doc.recompute()
    ok = nuevo.isValid()
    doc.removeObject(nuevo.Name)
    return ok


def prueba():
    import SheetMetalCmd
    import SheetMetalHem
    from swui.fork import sheet_metal as sm
    assert sm.patch_unfold_document(), "no se pudo enganchar el desarrollo de SheetMetal"
    for semilla in (1, 2, 3, 4):
        rng = random.Random(semilla)
        doc, body, base, flat = _chapa(sm)
        hechos = []
        for paso in range(12):
            accion = rng.choice(["pared", "pared", "dobladillo", "quitar", "espesor"])
            tip = body.Tip
            if accion in ("pared", "dobladillo"):
                arista = rng.choice(_rectas(tip))
                if accion == "pared":
                    w = doc.addObject("PartDesign::FeaturePython", "Bend")
                    SheetMetalCmd.SMBendWall(w, tip, [arista])
                    body.addObject(w)
                    w.setExpression("radius", "%s.Radius" % base.Name)
                    w.length = rng.choice([10, 20, 30])
                else:
                    w = doc.addObject("PartDesign::FeaturePython", "Hem")
                    SheetMetalHem.SMHem(w, tip, [arista])
                    body.addObject(w)
                doc.recompute()
                if w.isValid():
                    hechos.append(w)
                else:  # como cancelar el panel
                    _sacar(doc, body, w, tip)
            elif accion == "quitar" and hechos:
                _sacar(doc, body, hechos.pop(), hechos[-1] if hechos else base)
            elif accion == "espesor":
                base.Thickness = rng.choice([1.5, 2, 3])
                doc.recompute()
            donde = "semilla %d, paso %d (%s)" % (semilla, paso, accion)
            caras = list(flat.baseObject[1])
            assert not [c for c in caras if c.startswith("?")], "%s: el desarrollo perdió la cara: %s" % (donde, caras)
            assert caras == [sm.fixed_face(body)], "%s: apunta a %s, la cara fija es %s" % (donde, caras, sm.fixed_face(body))
            if not flat.isValid():
                assert not _desplegable(doc, body, sm), "%s: el desarrollo da error y uno nuevo no" % donde
                break
        FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
