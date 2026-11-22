# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Hallado por prueba_ventana_editar_pieza_botones en la batería del 22/11: editando una pieza que ya tiene su
contenedor Parte (lo arma FreeWorks antes de crear algo fuera del Cuerpo), Eliminar sólido con una cara del único
Cuerpo sacaba de Editar pieza: el Cuerpo pasa al grupo de la operación, su camino cambia y FreeCAD lo suelta.
Tiene que pasar (como SW, se sigue editando la pieza):
1) Eliminar sólido con una cara, Aceptar: se sigue editando, con el mismo Cuerpo activo;
2) es un solo paso de deshacer (antes el grupo entraba al contenedor en un paso aparte, "Cuerpo a la pieza", y
   el primer Ctrl+Z dejaba el grupo con el Cuerpo fuera de la pieza: ahí se salía); Ctrl+Z y Ctrl+Y: se sigue
   editando;
3) abrir Eliminar sólido y Cancelar: se sigue editando;
4) soltar el Cuerpo a propósito (lo nativo: doble clic en el Cuerpo activo) sigue saliendo de Editar pieza."""
TIPO = "completa"
import os  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from reglas_paneles import ctrl_y, ctrl_z, tocar
    from swui import ribbon
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    for sub in ("b", "o"):
        os.makedirs(os.path.join(c, sub), exist_ok=True)
    adoc, _asm, (comp, _o) = pe.ensamblaje([pe.bloque(os.path.join(c, "b")), pe.bloque(os.path.join(c, "o"), "Otro")])
    assert ep.start(comp, warn=False), "no entró a Editar pieza"
    yield 800
    pdoc = comp.LinkedObject.Document
    ep.prepare_container(ec.current(adoc))
    yield 800
    assert any(o.TypeId == "App::Part" for o in pdoc.Objects), "no se armó el contenedor de la pieza"
    view = ep._view(adoc)

    def activo():
        act = view.getActiveObject("pdbody", False)
        return getattr(act[0], "Name", None) if act else None

    def sigue(que, espera=1500):
        bombear(espera)
        assert ep.editing(adoc) is comp, "%s: salió de Editar pieza" % que
        assert activo() == "Body", "%s: el Cuerpo activo es %s" % (que, activo())
        traza("  %s: sigue editando, Cuerpo activo %s" % (que, activo()))

    def eliminar(aceptar):
        FreeCADGui.Selection.clearSelection()
        ec.select(pdoc.getObject("Extruir"), "Face6", clear=False)
        ribbon._run("SWUI_DeleteBodies")
        bombear(1300)
        assert FreeCADGui.Control.activeDialog(), "no abrió Eliminar sólido"
        tocar(rechazar=not aceptar)

    grupos = lambda: [o for o in pdoc.Objects if o.TypeId == "App::DocumentObjectGroup"]  # noqa: E731
    eliminar(True)
    sigue("Aceptar")
    assert grupos(), "no se creó la operación"
    yield 100
    assert pdoc.UndoNames[:1] == ["Eliminar/Conservar sólido"], (
        "Eliminar sólido no quedó en un solo paso de deshacer: %s" % pdoc.UndoNames[:3])
    ctrl_z(adoc)
    sigue("Ctrl+Z")
    assert not grupos(), "Ctrl+Z no sacó la operación"
    ctrl_y(adoc)
    sigue("Ctrl+Y")
    assert grupos(), "Ctrl+Y no la volvió"
    ctrl_z(adoc)
    sigue("otra vez Ctrl+Z")
    yield 100
    eliminar(False)
    sigue("Cancelar")
    assert not grupos(), "Cancelar dejó la operación"
    yield 100
    view.setActiveObject("pdbody", None)  # como el doble clic en el Cuerpo activo
    bombear(1500)
    assert ep.editing(adoc) is None, "soltar el Cuerpo a propósito ya no sale de Editar pieza"
    traza("  soltar el Cuerpo: sale de Editar pieza")


from _base import ejecutar  # noqa: E402
ejecutar(globals())
