# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#100 (18/11): editando una pieza cuyo componente NO está en el origen (movido y girado), lo que FreeWorks toma de
la vista y lo que dibuja encima va donde se ve la pieza: el Croquis 3D (un vértice de la pieza cae en la pantalla
donde se ve; un clic en la pantalla da el punto de la pieza, no el del ensamblaje), las vistas previas de Redondeo,
Chaflán, Eliminar/Conservar y Matriz (corridas con el componente), las de las herramientas del croquis (Simetría,
Mover...), las cotas al hacer doble clic y la marca del centro de gravedad (su paso de coordenadas, solo para la pieza editada). Con
la pieza nueva todavía vacía, también. En la pieza sola, nada cambia."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _al_frente(doc):
    import FreeCADGui
    from swui.compat import QtWidgets
    FreeCAD.setActiveDocument(doc.Name)
    vista = FreeCADGui.getDocument(doc.Name).mdiViewsOfType("Gui::View3DInventor")[0]
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in area.subWindowList():
        if sub.isAncestorOf(vista.graphicsView()):
            area.setActiveSubWindow(sub)
    bombear(500)
    return vista


def _cerca(a, b, tol=1e-4):
    return (V(a) - V(b)).Length < tol


def prueba():
    import FreeCADGui
    import piezas_editar as pe
    from swui.fork import dress_up_panel as dp
    from swui.fork import edit_context as ec
    from swui.fork import edit_part as ep
    from swui.fork import sketch3d_panel as s3p
    from swui.fork import sketch_entities as se
    c = carpeta_temporal()
    ruta = pe.bloque(c)

    traza("pieza sola")
    pdoc = FreeCAD.openDocument(ruta)
    bombear(600)
    vista = _al_frente(pdoc)
    assert ec.view_placement() is None, "sin editar, no hay que pasar de coordenadas"
    p = V(60, 40, 20)
    assert _cerca(ec.to_view(p), p) and _cerca(ec.from_view(p), p)
    nodo = dp._faces_node([pdoc.getObject("Extruir").Shape.Faces[0]], (1, 1, 0))
    nodo.ref()  # que Coin no lo libere mientras se mira
    assert nodo.getChild(0).getTypeId().getName() != "Transform", "en la pieza sola la vista previa no lleva traslado"
    nodo.unref()
    FreeCAD.closeDocument(pdoc.Name)
    bombear(400)
    yield 100

    traza("editando, movida y girada")
    doc, asm, (uno, _dos) = pe.ensamblaje([ruta, pe.bloque(c, "Otro")])
    uno.Placement = FreeCAD.Placement(V(-80, 25, 40), FreeCAD.Rotation(V(0, 0, 1), 30))
    doc.recompute()
    vista = _al_frente(doc)
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(400)
    assert ep.start(uno, warn=False)
    bombear(400)
    pdoc = uno.LinkedObject.Document
    pad = pdoc.getObject("Extruir")
    plc = ec.view_placement()
    assert plc is not None, "editando, no dio la ubicación de la pieza"
    assert _cerca(plc.Base, uno.Placement.Base) and abs(plc.Rotation.Angle - uno.Placement.Rotation.Angle) < 1e-6, \
        "ubicación de la pieza: %s vs %s" % (plc, uno.Placement)

    # Croquis 3D: un vértice de la pieza cae en la pantalla donde se ve; y de la pantalla vuelve al punto de la pieza
    esquina = V(60, 40, 20)
    visto = vista.getPointOnViewport(uno.Placement.multVec(esquina))
    calc = s3p._screen(vista, esquina)
    assert abs(calc[0] - visto[0]) < 0.5 and abs(calc[1] - visto[1]) < 0.5, "Croquis 3D: %s vs %s" % (calc, visto)
    golpe = s3p._hit_plane(vista, calc, esquina, V(0, 0, 1))
    assert golpe is not None and _cerca(golpe, esquina, 0.5), "Croquis 3D: el clic dio %s, no %s" % (golpe, esquina)
    yield 100

    # vistas previas de caras (Redondeo, Chaflán, Eliminar/Conservar, Matriz): llevan la ubicación del componente
    nodo = dp._faces_node([pad.Shape.Faces[0]], (1, 1, 0))
    nodo.ref()
    t = nodo.getChild(0)
    assert t.getTypeId().getName() == "Transform", "la vista previa no lleva la ubicación del componente"
    tr = t.translation.getValue().getValue()
    assert _cerca(V(*tr), uno.Placement.Base), "traslado de la vista previa: %s" % (tr,)
    q = t.rotation.getValue().getValue()
    rot = FreeCAD.Rotation(*q)
    assert rot.isSame(uno.Placement.Rotation, 1e-6), "giro de la vista previa: %s vs %s" % (rot, uno.Placement.Rotation)
    # las líneas (aristas elegidas de Redondeo/Chaflán, referencias de Matriz, Plano, Mover cara): también
    lineas = dp._lines_node([pad.Shape.Edges[0]], (1, 0.5, 0), 3)
    lineas.ref()
    assert lineas.getChild(0).getTypeId().getName() == "Transform", "las líneas de la vista previa no se corren"
    # marca del centro de gravedad y cotas: el mismo paso de coordenadas, solo para la pieza editada
    assert _cerca(ec.to_view(esquina, part_doc=pdoc), uno.Placement.multVec(esquina))
    assert _cerca(ec.to_view(esquina, part_doc=doc), esquina), "el ensamblaje no es la pieza editada: no se corre"

    # herramientas del croquis: del croquis a la vista
    sk = pdoc.getObject("Croquis")
    assert _cerca(se.view_placement(sk).Base, uno.Placement.multiply(sk.getGlobalPlacement()).Base), \
        "herramientas del croquis: ubicación %s" % se.view_placement(sk)
    # recuadro del radio sobre la pieza (Redondeo): en la vista
    assert _cerca(ec.to_view(esquina), uno.Placement.multVec(esquina))
    assert _cerca(ec.from_view(uno.Placement.multVec(esquina)), esquina)
    ep.stop(doc)
    bombear(300)
    assert ec.view_placement() is None, "después de salir de Editar pieza sigue pasando de coordenadas"
    for d in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(d.Name)
    yield 100

    traza("pieza nueva vacía (revisión 18/11, hallazgo 1)")
    vacia = FreeCAD.newDocument("Vacia")
    vacia.addObject("PartDesign::Body", "Cuerpo")
    ruta_vacia = pe._guardar(vacia, c, "Vacia")
    doc, asm, (uno, _dos) = pe.ensamblaje([ruta_vacia, pe.bloque(c, "Otro2")])
    uno.Placement = FreeCAD.Placement(V(30, -20, 10), FreeCAD.Rotation(V(1, 0, 0), 45))
    doc.recompute()
    _al_frente(doc)
    assert ep.start(uno, warn=False)
    bombear(400)
    plc = ec.view_placement()
    glob_asm = asm.getGlobalPlacement() if hasattr(asm, "getGlobalPlacement") else asm.Placement
    quiero = glob_asm.multiply(uno.Placement)
    assert plc is not None and _cerca(plc.Base, quiero.Base) and plc.Rotation.isSame(quiero.Rotation, 1e-6),         "pieza vacía: %s, tendría que ser %s" % (plc, quiero)
    # con la primera operación la cuenta sigue bien (la caché no se queda con lo de la pieza vacía)
    pdoc = uno.LinkedObject.Document
    body = pdoc.getObject("Cuerpo")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    pdoc.recompute()
    doc.recompute()
    bombear(300)
    plc2 = ec.view_placement()
    assert _cerca(plc2.Base, quiero.Base) and plc2.Rotation.isSame(quiero.Rotation, 1e-6), "con la caja: %s" % plc2
    assert caja.isValid()
    ep.stop(doc)
    bombear(300)
    for d in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(d.Name)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
