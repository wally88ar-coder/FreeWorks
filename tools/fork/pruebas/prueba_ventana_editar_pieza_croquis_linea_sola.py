# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#112 (visto por el usuario el 21/11, paso6): editando el Taco, un croquis en la cara de arriba de la Placa con
UNA línea suelta (desde un vértice de la Placa), que se cierra con la línea elegida, queda en el Taco SIN error (en SW
un croquis abierto no es un error). Después, Extruir sobre la misma cara con un círculo (Salir, Aceptar) no llena
el informe de avisos "Wire is not closed", y la extrusión nueva queda sana y usa el croquis del círculo."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from deshacer_comun import abrir_paso6, cara_arriba  # noqa: E402

V = FreeCAD.Vector


def _informe():
    import FreeCADGui
    from swui.compat import QtWidgets
    rv = FreeCADGui.getMainWindow().findChild(QtWidgets.QTextEdit, "Report view")
    return rv.toPlainText() if rv is not None else ""


def _malos(pdoc):
    return ["%s (%s): %s" % (o.Name, o.Label, o.State) for o in pdoc.Objects
            if "Invalid" in o.State or "Error" in str(o.State) or (hasattr(o, "isValid") and not o.isValid())]


def prueba():
    import FreeCADGui
    from croquis_esc_comun import clic, esc
    from swui import ribbon
    from swui.compat import QtWidgets
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, taco, placa = abrir_paso6(c)
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.activeView()
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(800)
    sub_taco, cara_taco = cara_arriba(asm, taco)
    sub_placa, cara_placa = cara_arriba(asm, placa)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub_taco)
    FreeCADGui.runCommand("SWUI_EditPart")
    bombear(1000)
    assert ep.editing(doc) is taco, "no entró a Editar pieza"
    pdoc = taco.LinkedObject.Document
    assert not _malos(pdoc), "el Taco ya tenía errores: %s" % _malos(pdoc)
    yield 100

    traza("croquis en la cara de la Placa con una línea suelta; se cierra con la línea elegida")
    bb = cara_placa.BoundBox
    esquina = V(bb.XMin, bb.YMin, bb.ZMax)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub_placa)
    ribbon._run("PartDesign_NewSketch")
    bombear(3000)
    sk = getattr(gdoc.getInEdit(), "Object", None)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "no abrió el croquis"
    FreeCADGui.runCommand("Sketcher_CreateLine")
    bombear(400)
    clic(vista, esquina)
    clic(vista, esquina + V(12, 8, 0))
    vpw = vista.graphicsView().viewport()
    esc(vpw)
    assert sk.GeometryCount == 1, "no quedó la línea: %d" % sk.GeometryCount
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s%s.Edge1" % (sub_taco.rsplit(".", 2)[0] + ".", sk.Name))
    bombear(300)
    traza("  elegido al cerrar: %s" % [(s.ObjectName, s.SubElementNames) for s in FreeCADGui.Selection.getSelectionEx("", 0)])
    FreeCADGui.runCommand("Sketcher_LeaveSketch")
    bombear(2500)
    traza("  croquis %s: estado %s, válido %s; Taco: %s" % (sk.Name, sk.State, sk.isValid(), _malos(pdoc)))
    assert not _malos(pdoc), "#112: el croquis con una línea suelta dejó errores en el Taco: %s" % _malos(pdoc)
    yield 100

    traza("Extruir sobre la cara de la Placa con un círculo")
    desde = len(_informe())
    antes = set(o.Name for o in pdoc.Objects)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub_placa)
    traza("  elegido: %s" % [(s.ObjectName, s.SubElementNames) for s in FreeCADGui.Selection.getSelectionEx("", 0)])
    from swui.compat import QtCore
    carteles = []

    def mirar():
        d = QtWidgets.QApplication.activeModalWidget()
        if d is not None:
            carteles.append("%s: %s" % (d.windowTitle(), d.text() if hasattr(d, "text") else d.metaObject().className()))
            d.reject()
    reloj = QtCore.QTimer()
    reloj.timeout.connect(lambda: mirar())
    reloj.start(300)
    ribbon._run("PartDesign_Pad")
    bombear(3000)
    reloj.stop()
    traza("  carteles al Extruir: %s" % carteles)
    assert not carteles, "Extruir mostró un cartel: %s" % carteles
    sk2 = getattr(gdoc.getInEdit(), "Object", None)
    traza("  en edición: %s; panel %s" % (getattr(sk2, "Name", sk2), FreeCADGui.Control.activeDialog()))
    assert sk2 is not None and sk2.TypeId == "Sketcher::SketchObject" and sk2 is not sk, "Extruir no abrió un croquis nuevo"
    centro = V(bb.XMax - 10, bb.YMin + 10, bb.ZMax)
    FreeCADGui.runCommand("Sketcher_CreateCircle")
    bombear(400)
    clic(vista, centro)
    clic(vista, centro + V(4, 0, 0))
    esc(vpw)
    FreeCADGui.runCommand("Sketcher_LeaveSketch")
    bombear(2500)
    for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        b = box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if b is not None and b.isVisible():
            b.click()
            break
    bombear(2500)
    nuevo = _informe()[desde:]
    abiertos = [ln for ln in nuevo.splitlines() if "not closed" in ln]
    traza("  informe nuevo: %s" % [ln for ln in nuevo.splitlines() if ln.strip()][:12])
    pads = [o for o in pdoc.Objects if o.Name not in antes and o.TypeId == "PartDesign::Pad"]
    assert len(pads) == 1, "no quedó una extrusión nueva: %s" % [o.Name for o in pdoc.Objects if o.Name not in antes]
    pad = pads[0]
    traza("  extrusión %s: perfil %s, válida %s; Taco: %s" % (pad.Name, pad.Profile[0].Name, pad.isValid(), _malos(pdoc)))
    assert not abiertos, "#112: avisos 'Wire is not closed' durante la extrusión: %s" % abiertos[:3]
    assert pad.Profile[0] is sk2, "la extrusión no usa el croquis del círculo: %s" % pad.Profile[0].Name
    assert pad.isValid() and not _malos(pdoc), "quedaron errores: %s" % _malos(pdoc)
    ep.stop(doc)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
