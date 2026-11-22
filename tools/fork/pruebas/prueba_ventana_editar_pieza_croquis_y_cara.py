# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#114: editando el Taco, con una arista de un croquis del Taco elegida y además la cara de arriba de la Placa
(otro componente), Extruir mostraba el cartel nativo "El objeto seleccionado debe pertenecer al cuerpo activo" y no
hacía nada. Visto en SW 2018 con el mouse el 22/11 (Conjunto114): Extruir saliente usa el croquis elegido como
perfil (Contornos seleccionados: solo el croquis) y no usa la cara del otro componente para nada.
Tiene que pasar:
1) croquis cerrado + cara de la Placa, Extruir: sin cartel, se abre la extrusión con ese croquis; Cancelar no deja
   nada y se sigue editando;
2) lo mismo y Aceptar: queda una extrusión del Taco con ese croquis de perfil, sana, y se sigue editando; un Ctrl+Z
   la saca y Ctrl+Y la vuelve;
3) croquis abierto (una línea) + cara de la Placa: sin el cartel de #114, lo mismo que con la línea sola
   (SW haría una Operación lámina; FreeCAD 1.1 no la tiene)."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from deshacer_comun import abrir_paso6, cara_arriba, prefijo  # noqa: E402

V = FreeCAD.Vector


def _malos(pdoc):
    return ["%s (%s): %s" % (o.Name, o.Label, o.State) for o in pdoc.Objects
            if "Invalid" in o.State or "Error" in str(o.State) or (hasattr(o, "isValid") and not o.isValid())]


def prueba():
    import FreeCADGui
    import Part
    from reglas_paneles import ctrl_y, ctrl_z
    from swui import ribbon
    from swui.compat import QtCore, QtWidgets
    from swui.fork import edit_part as ep
    c = carpeta_temporal()
    doc, asm, taco, placa = abrir_paso6(c)
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    gdoc.activeView().viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(800)
    sub_taco, cara_taco = cara_arriba(asm, taco)
    sub_placa, _cara_placa = cara_arriba(asm, placa)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub_taco)
    FreeCADGui.runCommand("SWUI_EditPart")
    bombear(1000)
    assert ep.editing(doc) is taco, "no entró a Editar pieza"
    pdoc = taco.LinkedObject.Document
    pre, body = prefijo(taco)
    assert not _malos(pdoc), "el Taco ya tenía errores: %s" % _malos(pdoc)

    # preparar (guion): dos croquis del Taco sobre su cara de arriba, uno con un círculo y otro con una línea
    face_name = sub_taco.rsplit(".", 1)[-1]

    def croquis(nombre, geo):
        sk = body.newObject("Sketcher::SketchObject", nombre)
        sk.AttachmentSupport = [(body.Tip, face_name)]
        sk.MapMode = "FlatFace"
        sk.addGeometry(geo, False)
        sk.Visibility = True
        return sk

    pdoc.openTransaction("preparar")
    circulo = croquis("Circulo", Part.Circle(V(0, 0, 0), V(0, 0, 1), 3))
    linea = croquis("Linea", Part.LineSegment(V(-3, -3, 0), V(3, 2, 0)))
    pdoc.commitTransaction()
    pdoc.recompute()
    bombear(800)
    assert circulo.isValid() and linea.isValid(), "los croquis de preparación quedaron con error: %s" % _malos(pdoc)

    carteles = []

    def mirar():
        d = QtWidgets.QApplication.activeModalWidget()
        if d is not None:
            carteles.append("%s: %s" % (d.windowTitle(), d.text() if hasattr(d, "text") else d.metaObject().className()))
            d.reject()

    def extruir(sk):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s%s.Edge1" % (pre, sk.Name))
        FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub_placa)
        traza("  elegido: %s" % [(s.ObjectName, s.SubElementNames) for s in FreeCADGui.Selection.getSelectionEx("", 0)])
        del carteles[:]
        reloj = QtCore.QTimer()
        reloj.timeout.connect(lambda: mirar())
        reloj.start(300)
        ribbon._run("PartDesign_Pad")
        bombear(2500)
        reloj.stop()
        traza("  carteles: %s; panel: %s; en edición: %s" % (
            carteles, FreeCADGui.Control.activeDialog(), getattr(getattr(gdoc.getInEdit(), "Object", None), "Name", None)))

    def pads():
        return [o for o in pdoc.Objects if o.TypeId == "PartDesign::Pad"]

    def sigue(que):
        bombear(800)
        assert ep.editing(doc) is taco, "%s: salió de Editar pieza" % que

    def boton(cual):
        for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
            b = box.button(cual)
            if b is not None and b.isVisible():
                b.click()
                return True
        return False

    base = [o.Name for o in pads()]
    traza("1) croquis cerrado + cara de la Placa, Cancelar")
    extruir(circulo)
    assert not carteles, "#114: Extruir mostró un cartel: %s" % carteles
    nuevos = [o for o in pads() if o.Name not in base]
    assert FreeCADGui.Control.activeDialog() and len(nuevos) == 1, "no se abrió la extrusión: %s" % [o.Name for o in nuevos]
    assert nuevos[0].Profile[0] is circulo, "la extrusión no usa el croquis elegido: %s" % nuevos[0].Profile[0].Name
    assert boton(QtWidgets.QDialogButtonBox.StandardButton.Cancel), "sin botón Cancelar"
    sigue("Cancelar")
    assert [o.Name for o in pads()] == base, "Cancelar dejó la extrusión"
    yield 100

    traza("2) croquis cerrado + cara de la Placa, Aceptar")
    extruir(circulo)
    assert not carteles, "#114: Extruir mostró un cartel: %s" % carteles
    assert boton(QtWidgets.QDialogButtonBox.StandardButton.Ok), "sin botón Aceptar"
    sigue("Aceptar")
    nuevos = [o for o in pads() if o.Name not in base]
    assert len(nuevos) == 1 and nuevos[0].Profile[0] is circulo, "no quedó la extrusión del círculo: %s" % nuevos
    assert nuevos[0].isValid() and not _malos(pdoc), "quedaron errores: %s" % _malos(pdoc)
    ctrl_z(doc)
    sigue("Ctrl+Z")
    assert [o.Name for o in pads()] == base, "Ctrl+Z no sacó la extrusión"
    ctrl_y(doc)
    sigue("Ctrl+Y")
    assert len(pads()) == len(base) + 1, "Ctrl+Y no la volvió"
    ctrl_z(doc)
    sigue("otra vez Ctrl+Z")
    yield 100

    traza("3) croquis abierto: con la cara de la Placa y solo (lo mismo)")
    extruir(linea)
    con_cara = (list(carteles), bool(FreeCADGui.Control.activeDialog()), len(pads()) - len(base))
    assert not [x for x in carteles if "activ" in x], "#114: con el croquis abierto, el cartel del cuerpo activo: %s" % carteles
    if FreeCADGui.Control.activeDialog():
        boton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    sigue("cancelar con la línea")
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s%s.Edge1" % (pre, linea.Name))
    del carteles[:]
    reloj = QtCore.QTimer()
    reloj.timeout.connect(lambda: mirar())
    reloj.start(300)
    ribbon._run("PartDesign_Pad")
    bombear(2500)
    reloj.stop()
    sola = (list(carteles), bool(FreeCADGui.Control.activeDialog()), len(pads()) - len(base))
    traza("  con la cara: %s; sola: %s" % (con_cara, sola))
    if FreeCADGui.Control.activeDialog():
        boton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    sigue("cancelar con la línea sola")
    assert con_cara == sola, "con la cara de la Placa no pasa lo mismo que con la línea sola: %s / %s" % (con_cara, sola)
    ep.stop(doc)
    bombear(300)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
