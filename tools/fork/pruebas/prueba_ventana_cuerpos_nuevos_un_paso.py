# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#119 (y #118): en una pieza con el contenedor Parte de FreeWorks, los Cuerpos nuevos que crea una herramienta
entraban al contenedor DESPUÉS, con un temporizador, en un paso de deshacer propio ("Cuerpo a la pieza"): un solo
Aceptar necesitaba dos Ctrl+Z y, editando la pieza en un ensamblaje, el primero dejaba el Cuerpo fuera de la pieza.
Tiene que pasar (editando una pieza con contenedor, como SW: una operación = un paso):
1) Mover/Copiar sólido copiando, Simetría con sólidos aparte y "Fusionar resultado" apagado: después de Aceptar hay
   UN paso de deshacer nuevo, con el nombre de la herramienta, y el Cuerpo nuevo ya está dentro del contenedor;
2) se sigue editando; un Ctrl+Z saca todo lo nuevo (se sigue editando) y Ctrl+Y lo vuelve, dentro del contenedor;
3) un grupo creado en un paso de FreeCAD (no de una herramienta de FreeWorks) que queda en la raíz no entra
   callado a la pieza dentro del paso de otra herramienta (revisión del 22/11)."""
TIPO = "completa"
import os  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from reglas_paneles import esperar_panel  # noqa: E402

V = FreeCAD.Vector


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from reglas_paneles import ctrl_y, ctrl_z, tocar
    from swui import ribbon
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    from swui.fork import multibody, panel_guard
    from swui.fork import part_container as pc
    c = carpeta_temporal()
    for sub in ("b", "o"):
        os.makedirs(os.path.join(c, sub), exist_ok=True)
    adoc, _asm, (comp, _o) = pe.ensamblaje([pe.bloque(os.path.join(c, "b")), pe.bloque(os.path.join(c, "o"), "Otro")])
    assert ep.start(comp, warn=False), "no entró a Editar pieza"
    yield 800
    pdoc = comp.LinkedObject.Document
    ep.prepare_container(ec.current(adoc))
    yield 800
    part = pc.container(pdoc)
    assert part is not None and hasattr(part, pc.MARK), "no se armó el contenedor de la pieza"
    view = ep._view(adoc)

    def cuerpos():
        return set(o.Name for o in pdoc.Objects if o.TypeId == "PartDesign::Body")

    def sigue(que):
        bombear(1200)
        assert ep.editing(adoc) is comp, "%s: salió de Editar pieza" % que
        act = view.getActiveObject("pdbody", False)
        traza("  %s: sigue editando, Cuerpo activo %s" % (que, getattr(act[0], "Name", None) if act else None))

    def un_paso(que, nombre, antes):
        """Después de Aceptar: un solo paso nuevo, con su nombre, y lo nuevo dentro del contenedor."""
        bombear(1500)  # que corra también el temporizador del contenedor (antes armaba ahí su paso aparte)
        sigue(que)
        nuevos = cuerpos() - antes
        traza("  %s: pasos %s, Cuerpos nuevos %s" % (que, list(pdoc.UndoNames[:3]), sorted(nuevos)))
        assert nuevos, "%s: no creó un Cuerpo" % que
        assert pdoc.UndoCount == 1 and pdoc.UndoNames[0] == nombre, (
            "#119: %s dejó %d pasos de deshacer: %s" % (que, pdoc.UndoCount, list(pdoc.UndoNames[:3])))
        afuera = [n for n in nuevos if pdoc.getObject(n).getParentGeoFeatureGroup() is not part]
        assert not afuera, "%s: Cuerpos fuera del contenedor: %s" % (que, afuera)
        ctrl_z(adoc)
        sigue("%s, Ctrl+Z" % que)
        assert not (cuerpos() - antes), "%s: Ctrl+Z no sacó todo: %s" % (que, sorted(cuerpos() - antes))
        ctrl_y(adoc)
        sigue("%s, Ctrl+Y" % que)
        assert cuerpos() - antes == nuevos, "%s: Ctrl+Y no volvió los Cuerpos" % que
        afuera = [n for n in nuevos if pdoc.getObject(n).getParentGeoFeatureGroup() is not part]
        assert not afuera, "%s: después de Ctrl+Y, fuera del contenedor: %s" % (que, afuera)
        ctrl_z(adoc)
        sigue("%s, otra vez Ctrl+Z" % que)

    ext = pdoc.getObject("Extruir")
    body = [o for o in pdoc.Objects if o.TypeId == "PartDesign::Body"][0]

    traza("1) Mover/Copiar sólido, copiando")
    antes = cuerpos()
    pdoc.clearUndos()
    FreeCADGui.Selection.clearSelection()
    ec.select(ext, "Face6", clear=False)
    ribbon._run("SWUI_MoveBodies")
    yield from esperar_panel()
    p = panel_guard.open_panel()
    p.copy.setChecked(True)
    p.deltas[0].setValue(60.0)
    p.preview()
    yield 800
    assert tocar(rechazar=False), "Mover/Copiar sólido no aceptó"
    from swui.fork import move_bodies
    un_paso("Mover/Copiar sólido", move_bodies.LABEL, antes)
    yield 100

    traza("2) Simetría con el sólido aparte")
    antes = cuerpos()
    pdoc.clearUndos()  # antes de abrir el panel (limpiar con el panel abierto confirmaría su paso)
    FreeCADGui.Selection.clearSelection()
    ec.select(ext, "Face6", clear=False)
    ribbon._run("PartDesign_Mirrored")
    yield from esperar_panel()
    p = panel_guard.open_panel()
    traza("  panel: %s" % type(p).__name__)
    p.mirror_bodies = [body]
    p.refs["MirrorPlane"] = (ext, ["Face6"])
    p.merge.setChecked(False)
    p.preview()
    yield 800
    assert tocar(rechazar=False), "Simetría no aceptó"
    un_paso("Simetría de sólidos", "Simetría de sólidos", antes)
    yield 100

    traza("3) Fusionar resultado apagado en una extrusión")
    antes = cuerpos()
    pdoc.clearUndos()
    multibody._apply_decision(("merge", False), pdoc.Name, ext.Name)
    un_paso("Fusionar resultado", "Fusionar resultado", antes)
    yield 100

    traza("4) un grupo de un paso que no es de FreeWorks no entra callado en el paso de otra herramienta (revisión)")
    pdoc.openTransaction("Carpeta")  # como un comando de FreeCAD: sus pasos no pasan por end_step
    carpeta = pdoc.addObject("App::DocumentObjectGroup", "Carpeta")
    pdoc.commitTransaction()
    bombear(1500)  # la carpeta entra al contenedor
    pdoc.openTransaction("Grupo nativo")
    grupo = pdoc.addObject("App::DocumentObjectGroup", "GrupoSuelto")
    carpeta.addObject(grupo)  # creado dentro de una carpeta: el temporizador no lo mueve (queda anotado)
    pdoc.commitTransaction()
    bombear(1500)
    pdoc.openTransaction("Sacar de la carpeta")
    carpeta.removeObject(grupo)  # después alguien lo saca a la raíz
    if grupo.getParentGeoFeatureGroup() is not None:  # sale de la carpeta pero queda en la Parte
        grupo.getParentGeoFeatureGroup().removeObject(grupo)
    pdoc.commitTransaction()
    bombear(800)
    traza("  pasos: %s; padre: %s" % (list(pdoc.UndoNames[:3]), getattr(grupo.getParentGroup(), "Name", None)))
    assert grupo.getParentGeoFeatureGroup() is None and grupo.getParentGroup() is None,         "el grupo no quedó en la raíz para la prueba"
    antes = cuerpos()
    pdoc.clearUndos()
    multibody._apply_decision(("merge", False), pdoc.Name, ext.Name)
    bombear(1500)
    traza("  después de otra herramienta: padre del grupo %s" % getattr(grupo.getParentGeoFeatureGroup(), "Name", None))
    assert grupo.getParentGeoFeatureGroup() is None, "el grupo de otro paso entró a la pieza dentro de otra herramienta"
    un_paso("Fusionar resultado (después del grupo)", "Fusionar resultado", antes)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
