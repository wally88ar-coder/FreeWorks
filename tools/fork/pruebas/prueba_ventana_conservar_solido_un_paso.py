# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#119, Conservar sólido (no tenía prueba propia): editando una pieza con el contenedor Parte de FreeWorks,
con el Cuerpo partido en dos pedazos, Conservar sólidos con un pedazo arma un Cuerpo nuevo para ese pedazo.
Tiene que pasar (como SW: una operación = un paso):
1) Cancelar: no queda nada, todo como estaba, sin pasos de deshacer, se sigue editando;
2) Aceptar: UN paso de deshacer, "Eliminar/Conservar sólido"; el Cuerpo nuevo y la operación dentro del
   contenedor; se sigue editando; Ctrl+Z saca todo y Ctrl+Y lo vuelve, dentro del contenedor;
3) (#122) armar el pedazo no falla ("FreeCAD no pudo armar la operación": el filtro se creaba en el documento del
   ensamblaje) ni deja en el Informe el aviso de FreeCAD de un vínculo fuera de la pieza ("allowed scope")."""
TIPO = "completa"
from _base import traza  # noqa: E402


def prueba():
    from reglas_paneles import tocar
    from swui.fork import delete_bodies as db
    from un_paso_comun import abrir_eliminar, informe, partir, pedazo, preparar
    p = yield from preparar()
    body = partir(p)
    yield 300
    p.pdoc.clearUndos()

    traza("1) Conservar un pedazo y Cancelar")
    foto = p.foto()
    panel = yield from abrir_eliminar()
    panel._mode(db.KEEP)
    panel.spec["items"] = [{"body": body.Name, "point": pedazo(body, 0)}]
    panel._refresh()
    yield 500
    assert tocar(rechazar=True), "no encontré Cancelar"
    p.cancelado("Cancelar", foto)
    yield 100

    traza("2) Conservar un pedazo y Aceptar")
    antes = p.cuerpos()
    largo = len(informe())
    panel = yield from abrir_eliminar()
    panel._mode(db.KEEP)
    panel.spec["items"] = [{"body": body.Name, "point": pedazo(body, 0)}]
    panel._refresh()
    yield 500
    assert tocar(rechazar=False), "no encontré Aceptar"
    p.un_paso("Conservar sólido", db.LABEL, antes)
    nuevo_texto = informe()[largo:]
    assert "allowed scope" not in nuevo_texto, "#122: FreeCAD avisó un vínculo fuera de la pieza: %s" % (
        [r for r in nuevo_texto.splitlines() if "scope" in r][:2])
    nuevos = [p.pdoc.getObject(n) for n in p.cuerpos() - antes]
    assert len(nuevos) == 1 and len(nuevos[0].Shape.Solids) == 1, "Conservar no dejó un Cuerpo con un pedazo"
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
