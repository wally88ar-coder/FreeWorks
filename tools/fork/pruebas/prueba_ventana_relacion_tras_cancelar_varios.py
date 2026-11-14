# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (#76, la seguidilla que encontró el mono de ensamblaje): con Ecuaciones abierto y
cancelado cada vez, Relación de posición → aceptar Relación → Extruir corte de ensamblaje → Plano
de ensamblaje → Taladro de ensamblaje → Relación de posición. Como SW: ni FreeCAD ni FreeWorks dejan
errores en el informe ("Solve failed: invalid vector subscript" del resolvedor) y cada Cancelar
deja todo como estaba."""
TIPO = "completa"

from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

PASOS = [("ecuaciones", 0), ("aceptar", 3511), ("ecuaciones", 42371), ("ecuaciones", 233655),
         ("ecuaciones", 694), ("ecuaciones", 0)]


def _juntas(m):
    try:
        from swui.fork import mates_sw
        g = mates_sw._assembly_modules()[1].getJointGroup(m.asm)
        return [(o.Name, getattr(o, "JointType", getattr(o, "ObjectToGround", None) and "Ground"),
                 getattr(o, "Reference1", None) and o.Reference1[1], getattr(o, "Reference2", None) and o.Reference2[1])
                for o in g.Group]
    except Exception as exc:
        return "?? %s" % exc


def prueba():
    from mono_comun import paso
    from mono_entornos import Ensamblaje
    m = Ensamblaje()
    historia = []
    for accion, semilla in PASOS:
        traza("  %s %s: antes %s" % (accion, semilla, _juntas(m)))
        paso(m, accion, semilla, historia)
        bombear(300)
    traza("  al final: %s" % (_juntas(m),))
    yield 300
    # la relación que contradice a la primera (Paralela de la Face4 de la placa con la Face1 del
    # bloque, cuando el bloque ya tiene su cara +Y contra la placa). Como SW 2018 (probado con el
    # mouse el 14/11): mientras se elige, "definido en exceso" y nada se mueve; al aceptar pregunta
    # "romper otras" / "definir en exceso" / Cancelar
    import Part
    import FreeCADGui
    from casos_ensamblaje import Relacion
    from swui.fork import mates_sw, panel_guard
    from reglas_paneles import informe_largo, mensajes_nuevos
    placa, bloque = m.comps
    primera = [j for j in mates_sw.joints_of(m.asm)][0]
    original = mates_sw.ask_overdefined
    try:
        for respuesta in (None, "error", "break"):
            caso = Relacion()
            caso.doc, caso.asm, caso.comps = m.doc, m.asm, m.comps
            juntas0 = len(_juntas(m))
            lugar0 = bloque.Placement
            pasos0 = m.doc.UndoCount
            desde = informe_largo()
            yield from caso.abrir(None)
            p = panel_guard.open_panel()
            p.set_key("parallel")
            yield 300
            caso.elegir_en(placa, "Face4")
            yield 500
            caso.elegir_en(bloque, "Face1")
            yield 1500
            que = "respuesta %s" % respuesta
            assert "sobredefine" in p.message.text(), "%s: no avisó que sobredefine: %r" % (que, p.message.text())
            assert bloque.Placement.isSame(lugar0, 1e-6), "%s: mientras se elige, el bloque se movió" % que
            mates_sw.ask_overdefined = lambda r=respuesta: r
            cerrado = p.accept()
            yield 800
            malos = [x for x in mensajes_nuevos(desde) if "Solve failed" in x]
            assert not malos, "%s: el resolvedor dejó errores en el informe (#76): %s" % (que, malos[:3])
            if respuesta is None:  # Cancelar: nada agregado, la selección vacía, el panel sigue
                assert cerrado is False and FreeCADGui.Control.activeDialog(), "%s: el panel se cerró" % que
                assert len(_juntas(m)) == juntas0, "%s: se agregó algo: %s" % (que, _juntas(m))
                assert not FreeCADGui.Selection.getSelectionEx(), "%s: quedó la selección" % que
                p.reject()
                yield 500
                continue
            assert not FreeCADGui.Control.activeDialog(), "%s: el panel quedó abierto" % que
            nueva = [j for j in mates_sw.joints_of(m.asm) if j is not primera][-1]
            n1 = Part.getShape(placa).getElement("Face4").normalAt(0, 0)
            n2 = Part.getShape(bloque).getElement("Face1").normalAt(0, 0)
            from swui.fork import mates_tree
            arboles = list(mates_tree._trees())
            for arbol in arboles:  # que el árbol esté desplegado para ver la marca
                arbol.expandAll()
            yield 600
            assert any(mates_tree.error_rows(a) for a in arboles), \
                "%s: el árbol no marca en rojo la relación con error (como SW)" % que
            if respuesta == "error":  # la nueva con error; el bloque donde estaba (cumple la primera)
                assert mates_sw.mate_error(nueva) and nueva.Suppressed, "%s: la nueva no quedó con error" % que
                assert not mates_sw.mate_error(primera) and not primera.Suppressed, "%s: tocó la primera" % que
                assert bloque.Placement.isSame(lugar0, 1e-6), "%s: el bloque se movió" % que
            else:  # romper: la nueva se cumple; la primera queda con error
                assert not mates_sw.mate_error(nueva) and not nueva.Suppressed, "%s: la nueva quedó apagada" % que
                assert mates_sw.mate_error(primera) and primera.Suppressed, "%s: la primera no quedó rota" % que
                assert abs(abs(n1.dot(n2)) - 1) < 1e-6, "%s: la nueva no se cumple (caras no paralelas)" % que
                # sacarle la supresión a la rota desde el árbol: sigue chocando, queda suprimida y roja
                mates_tree.toggle_suppressed(primera)
                yield 500
                assert primera.Suppressed and mates_sw.mate_error(primera), \
                    "%s: la rota quedó activa aunque sigue chocando (el ensamblaje no resolvería)" % que
                m.doc.undo()  # ese intento es su propio paso de deshacer
                m.doc.recompute()
                yield 300
            assert m.doc.UndoCount == pasos0 + 1, "%s: no es un solo paso de deshacer" % que
            m.doc.undo()  # Ctrl+Z: como antes de agregarla
            m.doc.recompute()
            yield 500
            assert len(_juntas(m)) == juntas0, "%s: Ctrl+Z no sacó la relación" % que
            assert not mates_sw.mate_error(primera) and not primera.Suppressed, "%s: Ctrl+Z no arregló la primera" % que
            assert bloque.Placement.isSame(lugar0, 1e-6), "%s: después de Ctrl+Z el bloque no volvió" % que
    finally:
        mates_sw.ask_overdefined = original

from _base import ejecutar  # noqa: E402
ejecutar(globals())
