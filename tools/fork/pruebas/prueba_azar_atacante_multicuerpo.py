# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Agente atacante, Multicuerpo y simetría de sólidos (escrito sin mirar el código, desde lo que
promete cada función y cómo hace SW 2018 "Sólidos para simetría" sin fusionar):
- next_body_label da un 'CuerpoN' que no está usado;
- scope_bodies: el sólido del corte va siempre, sin repetidos, solo sólidos que existen y en el
  orden de all_bodies; "Seleccionados" = el suyo + los elegidos; "Todos" con selección automática
  = el suyo + los que atraviesa; "Todos" sin automática = todos;
- make_mirror_body con plano del origen, una cara de la pieza o un plano de referencia girado y
  corrido al azar: el sólido nuevo es el espejo exacto (sus vértices son los del original
  reflejados) y tiene el mismo volumen; cambiar el original lo cambia igual; guardar, cerrar y abrir
  (documento con acentos) lo deja igual; Deshacer lo saca entero y Rehacer lo vuelve a poner.
"""
TIPO = "azar"

import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402
from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

V = FreeCAD.Vector


def _reflejar(p, base, n):
    return p - n * (2.0 * (p - base).dot(n))


def _mismos_puntos(a, b, tol):
    usados = set()
    for p in a:
        hallado = None
        for j, q in enumerate(b):
            if j not in usados and (p - q).Length <= tol:
                hallado = j
                break
        if hallado is None:
            return False
        usados.add(hallado)
    return len(usados) == len(b)


def prueba():
    given, cfg, st = hypothesis_listo()
    from swui.fork import mirror_bodies as mir
    from swui.fork import multibody as mb
    f = Fallas()

    @cfg
    @given(usados=st.sets(st.integers(1, 30), max_size=15), extra=st.sets(st.text(max_size=8), max_size=4))
    def etiqueta_cuerpo(usados, extra):
        used = {"Cuerpo%d" % n for n in usados} | {"Cuerpo"} | set(extra)
        n = mb.next_body_label(used)
        assert n not in used and n.startswith("Cuerpo") and n[6:].isdigit(), "next_body_label(%r) = %r" % (used, n)
        comprobado()
    f.correr("etiqueta_cuerpo", etiqueta_cuerpo)

    nombres = ["B%d" % i for i in range(1, 7)]

    @cfg
    @given(mode=st.sampled_from(["all", "selected"]), auto=st.booleans(), own=st.sampled_from(nombres),
           tocados=st.lists(st.sampled_from(nombres + ["Fantasma"]), max_size=6),
           elegidos=st.lists(st.sampled_from(nombres + ["Fantasma"]), max_size=6),
           orden=st.permutations(nombres))
    def alcance(mode, auto, own, tocados, elegidos, orden):
        r = mb.scope_bodies(mode, auto, own, list(orden), list(tocados), list(elegidos))
        que = "scope_bodies(%r, %r, %r, %r, %r, %r) = %r" % (mode, auto, own, orden, tocados, elegidos, r)
        assert own in r, "%s: falta el sólido del corte" % que
        assert len(set(r)) == len(r), "%s: repetidos" % que
        assert all(x in orden for x in r), "%s: incluye sólidos que no existen" % que
        assert r == [x for x in orden if x in r], "%s: no está en el orden de all_bodies" % que
        if mode == "selected":
            esperado = {own} | (set(elegidos) & set(orden))
        elif auto:
            esperado = {own} | (set(tocados) & set(orden))
        else:
            esperado = set(orden)
        assert set(r) == esperado, "%s: esperado %r" % (que, sorted(esperado))
        comprobado()
    f.correr("alcance", alcance)

    @cfg
    @given(dims=st.tuples(st.floats(1, 80), st.floats(1, 80), st.floats(1, 80)),
           pos=st.tuples(st.floats(-50, 50), st.floats(-50, 50), st.floats(-50, 50)),
           plano=st.one_of(st.tuples(st.just("origen"), st.sampled_from(["XY_Plane", "XZ_Plane", "YZ_Plane"])),
                           st.tuples(st.just("cara"), st.integers(1, 6)),
                           st.tuples(st.just("referencia"), st.tuples(st.floats(-1, 1), st.floats(-1, 1),
                                                                      st.floats(-1, 1), st.floats(0, 360)),
                                     st.tuples(st.floats(-60, 60), st.floats(-60, 60), st.floats(-60, 60)))),
           nuevo_largo=st.floats(1, 80),
           nombre=st.sampled_from(["Simetría", "Pieza con ñ y espacio"]))
    def simetria(dims, pos, plano, nuevo_largo, nombre):
        if plano[0] == "referencia" and abs(plano[1][0]) + abs(plano[1][1]) + abs(plano[1][2]) < 0.05:
            return
        doc = FreeCAD.newDocument(nombre)
        doc.UndoMode = 1
        carpeta = carpeta_temporal()
        try:
            b = doc.addObject("PartDesign::Body", "Body")
            bx = b.newObject("PartDesign::AdditiveBox", "Box")
            bx.Length, bx.Width, bx.Height = dims
            bx.Placement.Base = V(*pos)
            doc.recompute()
            if plano[0] == "origen":
                ref = ([o for o in b.Origin.OriginFeatures if o.Role == plano[1]][0], [""])
            elif plano[0] == "cara":
                ref = (bx, ["Face%d" % plano[1]])
            else:
                eje, base = plano[1], plano[2]
                pl = b.newObject("PartDesign::Plane", "PlanoRef")
                pl.MapMode = "Deactivated"
                pl.Placement = FreeCAD.Placement(V(*base), FreeCAD.Rotation(V(*eje[:3]), eje[3]))
                doc.recompute()
                ref = (pl, [""])
            info = mir.plane_of(ref)
            assert info is not None, "plane_of(%r) = None para un plano que sirve" % (ref,)
            base_p, n = V(*info[0]) if not isinstance(info[0], FreeCAD.Vector) else info[0], info[1]
            n = (V(*n) if not isinstance(n, FreeCAD.Vector) else V(n)).normalize()
            # el plano de verdad, sacado a mano
            if plano[0] == "cara":
                fc = bx.Shape.getElement("Face%d" % plano[1])
                assert abs((base_p - fc.CenterOfMass).dot(fc.normalAt(0, 0))) < 1e-6, "plane_of: punto fuera de la cara"
                assert abs(abs(n.dot(fc.normalAt(0, 0))) - 1) < 1e-9, "plane_of: normal %r, la cara %r" % (n, fc.normalAt(0, 0))
            doc.openTransaction("Simetría")
            mirr, nuevo = mir.make_mirror_body(b, ref)
            doc.recompute()
            doc.commitTransaction()

            def comprobar(cuando, bb, nb):
                orig = [v.Point for v in bb.Shape.Vertexes]
                espejo = [_reflejar(p, base_p, n) for p in orig]
                assert cerca(nb.Shape.Volume, bb.Shape.Volume, rel=1e-7), \
                    "%s: volumen %r, el original %r" % (cuando, nb.Shape.Volume, bb.Shape.Volume)
                assert _mismos_puntos([v.Point for v in nb.Shape.Vertexes], espejo, 1e-6 * (1 + max(dims) + 200)), \
                    ("%s: el sólido espejado no es el reflejo del original en el plano (%r, %r)"
                     % (cuando, base_p, n))
            comprobar("recién hecho", b, nuevo)
            bx.Length = nuevo_largo
            doc.recompute()
            if plano[0] == "cara":  # la cara pudo moverse con el cambio: plano de nuevo
                info = mir.plane_of(ref)
                base_p, n = info[0], V(info[1]).normalize()
            comprobar("después de cambiar el largo", b, nuevo)
            cuerpos = len([o for o in doc.Objects if o.TypeId == "PartDesign::Body"])
            ruta = os.path.join(carpeta, "simetria.FCStd")
            doc.saveAs(ruta)
            nombre_nuevo = nuevo.Name
            FreeCAD.closeDocument(doc.Name)
            doc = FreeCAD.openDocument(ruta)
            doc.recompute()
            comprobar("al abrir", doc.getObject("Body"), doc.getObject(nombre_nuevo))
            malos = [o.Name for o in doc.Objects if "Invalid" in o.State]
            assert not malos, "al abrir, con error: %s" % malos
            assert len([o for o in doc.Objects if o.TypeId == "PartDesign::Body"]) == cuerpos
            comprobado()
        finally:
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
    f.correr("simetria", simetria)

    @cfg
    @given(rol=st.sampled_from(["XY_Plane", "XZ_Plane", "YZ_Plane"]), largo=st.floats(1, 50))
    def simetria_deshacer(rol, largo):
        doc = FreeCAD.newDocument("Deshacer")
        doc.UndoMode = 1
        try:
            b = doc.addObject("PartDesign::Body", "Body")
            bx = b.newObject("PartDesign::AdditiveBox", "Box")
            bx.Length = largo
            bx.Placement.Base = V(3, 4, 5)
            doc.recompute()
            antes = sorted(o.Name for o in doc.Objects)
            sol_antes = len(mb.solid_bodies(doc))
            doc.openTransaction("Simetría")
            mir.make_mirror_body(b, ([o for o in b.Origin.OriginFeatures if o.Role == rol][0], [""]))
            doc.recompute()
            doc.commitTransaction()
            despues = sorted(o.Name for o in doc.Objects)
            assert len(mb.solid_bodies(doc)) == sol_antes + 1, "no sumó un sólido: %r" % mb.solid_bodies(doc)
            doc.undo()
            doc.recompute()
            assert sorted(o.Name for o in doc.Objects) == antes, \
                "Deshacer dejó: %r" % sorted(set(o.Name for o in doc.Objects) - set(antes))
            doc.redo()
            doc.recompute()
            assert sorted(o.Name for o in doc.Objects) == despues, "Rehacer: %r, antes %r" % (
                sorted(o.Name for o in doc.Objects), despues)
            assert len(mb.solid_bodies(doc)) == sol_antes + 1
            assert not [o.Name for o in doc.Objects if "Invalid" in o.State]
            comprobado()
        finally:
            FreeCAD.closeDocument(doc.Name)
    f.correr("simetria_deshacer", simetria_deshacer)

    f.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
