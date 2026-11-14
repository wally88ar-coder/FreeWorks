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
    # bloque, cuando el bloque ya tiene su cara +Y contra la placa): como SW, aviso y no se agrega
    import FreeCADGui
    from casos_ensamblaje import Relacion
    from swui.fork import mates_sw, panel_guard
    from reglas_paneles import informe_largo, mensajes_nuevos
    caso = Relacion()
    caso.doc, caso.asm, caso.comps = m.doc, m.asm, m.comps
    juntas0 = len(_juntas(m))
    desde = informe_largo()
    yield from caso.abrir(None)
    p = panel_guard.open_panel()
    p.set_key("parallel")
    yield 300
    caso.elegir_en(caso.comps[0], "Face4")
    yield 500
    caso.elegir_en(caso.comps[1], "Face1")
    yield 1500
    assert "sobredefine" in p.message.text(), "no avisó que la relación sobredefine el ensamblaje: %r" % p.message.text()
    assert p.joint is None, "dejó armada la relación que no se puede resolver"
    p.accept()
    yield 800
    assert len(_juntas(m)) == juntas0, "se agregó la relación que no se puede resolver: %s" % (_juntas(m),)
    malos = [x for x in mensajes_nuevos(desde) if "Solve failed" in x]
    assert not malos, "el resolvedor dejó errores en el informe (#76): %s" % malos[:3]
    assert not FreeCADGui.Control.activeDialog(), "el panel quedó abierto"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
