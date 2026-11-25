# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#119 y #118, reabrir Eliminar/Conservar sólido para cambiarlo (no tenía prueba propia): editando una pieza
con el contenedor Parte de FreeWorks, con el bloque partido en dos pedazos y un segundo Cuerpo, una operación
Eliminar sólidos con el segundo Cuerpo entero y un pedazo del bloque (arma un Cuerpo para el otro pedazo).
Tiene que pasar (como SW: editar la operación = un paso):
1) reabrirla y Cancelar: todo como estaba, sin pasos de deshacer, se sigue editando;
2) reabrirla, sacar de la lista el segundo Cuerpo y Aceptar: UN paso de deshacer, "Eliminar/Conservar sólido";
   el Cuerpo nuevo del pedazo, la operación y el segundo Cuerpo (que vuelve) dentro del contenedor; se sigue
   editando; Ctrl+Z vuelve a la operación de antes y Ctrl+Y al cambio, todo dentro del contenedor."""
TIPO = "completa"
from _base import traza  # noqa: E402


def prueba():
    from reglas_paneles import esperar_panel, tocar
    from swui.fork import delete_bodies as db
    from swui.fork import panel_guard
    from un_paso_comun import abrir_eliminar, partir, pedazo, preparar, segundo
    p = yield from preparar()
    body = partir(p)
    seg = segundo(p)
    yield 300

    traza("preparación: Eliminar el segundo Cuerpo y un pedazo del bloque")
    panel = yield from abrir_eliminar()
    panel.spec["items"] = [{"body": seg.Name, "point": None}, {"body": body.Name, "point": pedazo(body, 1)}]
    panel._refresh()
    yield 500
    assert tocar(rechazar=False), "no encontré Aceptar"
    p.sigue("preparación")
    grupo = [o for o in p.pdoc.Objects if hasattr(o, db.MARK)]
    assert len(grupo) == 1, "no se armó la operación"
    grupo = grupo[0]
    assert seg in grupo.Group, "el segundo Cuerpo no quedó en la operación"
    assert not p.afuera(), "la preparación dejó cosas fuera de la pieza: %s" % p.afuera()
    p.pdoc.clearUndos()

    def reabrir():
        db.open_panel(grupo)  # lo que hace el doble clic en la operación
        yield from esperar_panel()
        abierto = panel_guard.open_panel()
        assert type(abierto).__name__ == "DeleteBodiesPanel", "no reabrió la operación: %s" % type(abierto).__name__
        return abierto

    traza("1) reabrir y Cancelar")
    foto = p.foto()
    yield from reabrir()
    yield 500
    assert tocar(rechazar=True), "no encontré Cancelar"
    p.cancelado("reabrir y Cancelar", foto)
    yield 100

    traza("2) reabrir, sacar el segundo Cuerpo de la lista y Aceptar")
    antes = p.cuerpos()  # el Cuerpo del pedazo se rearma (puede volver con el mismo nombre)
    panel = yield from reabrir()
    panel.spec["items"] = [i for i in panel.spec["items"] if i["body"] != seg.Name]
    panel._refresh()
    yield 500
    assert tocar(rechazar=False), "no encontré Aceptar"
    p.un_paso("reabrir y cambiar", db.LABEL, antes, nuevos=False)  # termina con Ctrl+Y: como después de Aceptar
    piezas = [o for o in p.pdoc.Objects if o.TypeId == "PartDesign::Body" and o.BaseFeature is not None]
    assert len(piezas) == 1 and len(piezas[0].Shape.Solids) == 1, "no quedó el Cuerpo del pedazo"
    assert seg not in grupo.Group, "el segundo Cuerpo sigue en la operación"
    assert p.part.hasObject(seg, True), "el segundo Cuerpo volvió fuera de la pieza"
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
