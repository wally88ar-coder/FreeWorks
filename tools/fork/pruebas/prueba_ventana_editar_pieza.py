# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Editar la pieza dentro del ensamblaje, como SW (etapa D, 15/11). Editar pieza (ícono de la bandeja de un
componente) deja activo el Cuerpo de la pieza a través del componente, los otros componentes transparentes
sin dejar el ensamblaje modificado, y la barra "Editando pieza: X"; un croquis sobre una cara va a la
pieza; Ctrl+Z en el ensamblaje lo deshace y se sigue editando; Salir vuelve todo como estaba. Guardar
editando no deja la transparencia en el archivo; al guardar el ensamblaje pregunta si guardar las piezas
cambiadas (Sí las guarda). Editar operación / Editar croquis desde la cara de un componente abren la
operación o el croquis de la pieza sin salir del ensamblaje. Un componente en otra configuración (copia
dentro del ensamblaje): no se entra (aviso). Con varios componentes, Editar pieza no está."""
TIPO = "completa"
import os  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402
from menu_comun import abrir_menu as _menu, derecho_arbol, derecho_vista  # noqa: E402

V = FreeCAD.Vector


def _pieza_croquis(carpeta, nombre="Taco", configs=False):
    """Pieza hecha con croquis + extrusión (para Editar croquis); con configs, dos configuraciones."""
    from menu_comun import pieza
    from swui.fork import configurations as cf
    doc, body, sk, pad = pieza()
    if configs:
        cf.ensure(doc)
        primera = cf.active(doc)
        cf.add(doc, "Alta")
        cf.configure(doc, ("prop", pad, "Length"), 35, "this")
        cf.activate(doc, primera)
        doc.recompute()
    ruta = os.path.join(carpeta, nombre + ".FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    return ruta


def _contestar(que):
    """
    Contesta (Sí o No) el próximo cuadro de pregunta; devuelve dónde queda anotado lo que preguntó.
    visto["fin"] = True corta la espera (para que no conteste un cuadro de otra cosa).
    """
    from swui.compat import QtCore, QtWidgets
    visto = {}

    def mirar(vueltas=[0]):
        vueltas[0] += 1
        if visto.get("fin"):
            return
        for w in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(w, QtWidgets.QMessageBox) and w.isVisible():
                visto["texto"] = w.text()
                rol = QtWidgets.QMessageBox.ButtonRole.YesRole if que else QtWidgets.QMessageBox.ButtonRole.NoRole
                bs = [b for b in w.buttons() if w.buttonRole(b) == rol]
                (bs[0].click() if bs else w.reject())
                return
        if vueltas[0] < 60:
            QtCore.QTimer.singleShot(100, mirar)
    QtCore.QTimer.singleShot(150, mirar)
    return visto


def prueba():
    import FreeCADGui
    import casos_relacion as cr
    from swui.compat import QtWidgets
    from swui.fork import config_asm, edit_part as ep

    carpeta = carpeta_temporal()
    traza("armando")
    rutas = [cr._pieza(carpeta, "Placa", 100, 60, 10), _pieza_croquis(carpeta),
             _pieza_croquis(carpeta, "TacoConf", configs=True)]
    traza("piezas listas")
    doc, asm, (placa, taco, tconf) = cr._ensamblaje(rutas)
    taco.Placement.Base = V(120, 0, 0)
    tconf.Placement.Base = V(0, 120, 0)
    doc.recompute()
    doc.save()
    gdoc = FreeCADGui.getDocument(doc.Name)
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(500)
    gdoc.Modified = False
    pdoc = taco.LinkedObject.Document
    body = taco.LinkedObject
    view = FreeCADGui.ActiveDocument.ActiveView

    traza("paso 1")
    # 1) El clic derecho de un componente trae "Editar pieza"; con dos, no
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, taco.Name + ".")
    m = _menu(derecho_arbol(taco.Label))
    assert "Editar pieza" in m["vis"][0], "falta Editar pieza en la bandeja: %s" % m["vis"][0]
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, placa.Name + ".")
    m = _menu(derecho_arbol(taco.Label))
    assert "Editar pieza" not in m["vis"][0], "con dos componentes no va Editar pieza: %s" % m["vis"][0]
    yield 100

    traza("paso 2")
    # 2) Editar pieza: el Cuerpo del taco activo, la placa transparente, sin "modificado", la barra
    vo = placa.ViewObject
    tiene = ep._ghostable(placa)
    assert tiene, "el componente no tiene material propio: lo de la transparencia no se puede probar"
    antes = ep.ghost_level(placa)
    assert ep.check(taco) is None, "no se puede editar: %s" % ep.check(taco)
    pasos = (list(doc.UndoNames), list(pdoc.UndoNames))
    assert ep.start(taco, warn=False), "no entró a Editar pieza"
    assert (list(doc.UndoNames), list(pdoc.UndoNames)) == pasos, "entrar dejó un paso de deshacer"
    bombear(300)
    act = view.getActiveObject("pdbody", False)
    assert act and act[0] is body, "el Cuerpo activo no es el de la pieza: %s" % (act,)
    if tiene:
        assert abs(ep.ghost_level(placa) - ep.GHOST) < 1e-6, "la placa no quedó transparente: %s" % ep.ghost_level(placa)
        color = ep._part_color(placa)
        assert color is not None and tuple(vo.ShapeMaterial.DiffuseColor)[:3] == tuple(color)[:3],             "transparente, pero no con el color de la pieza: %s / %s" % (vo.ShapeMaterial.DiffuseColor, color)
    assert not gdoc.Modified, "entrar a Editar pieza dejó el ensamblaje modificado"
    barra = [w for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QLabel, "SWUI_edit_part_label")
             if w.isVisible()]
    assert barra and "Taco" in barra[0].text(), "falta la barra Editando pieza"
    assert ep.editing(doc) is taco
    yield 100

    traza("paso 3")
    # 3) Croquis sobre una cara del taco: va a la pieza; Ctrl+Z lo saca y se sigue editando
    croquis_asm = len([o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"])
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, "%s.%s.Face6" % (taco.Name, body.Name))
    traza("croquis nuevo")
    FreeCADGui.runCommand("PartDesign_NewSketch")
    bombear(1500)
    traza("croquis abierto")
    croquis = [o for o in pdoc.Objects if o.TypeId == "Sketcher::SketchObject" and o.Name != "Croquis"]
    assert croquis, "el croquis nuevo no quedó en la pieza"
    assert len([o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"]) == croquis_asm,         "el croquis quedó en el ensamblaje"
    import Part
    croquis[0].addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)))  # vacío, FreeWorks lo borra al salir
    FreeCADGui.Control.closeDialog()
    bombear(300)
    FreeCADGui.ActiveDocument.resetEdit()
    bombear(500)
    assert [o for o in pdoc.Objects if o.TypeId == "Sketcher::SketchObject" and o.Name != "Croquis"]
    FreeCADGui.runCommand("Std_Undo")
    bombear(800)
    assert not [o for o in pdoc.Objects if o.TypeId == "Sketcher::SketchObject" and o.Name != "Croquis"], \
        "Ctrl+Z en el ensamblaje no deshizo el croquis de la pieza"
    assert ep.editing(doc) is taco, "Ctrl+Z sacó de Editar pieza"
    yield 100

    traza("paso 4")
    # 4) Guardar editando: el archivo sin la transparencia; sigue transparente y sin "modificado"
    pregunta = _contestar(False)  # la pieza quedó modificada (Ctrl+Z): pregunta si guardarla; No
    doc.save()
    bombear(1500)
    assert "Taco" in pregunta.get("texto", ""), "guardando editando no preguntó por la pieza: %s" % pregunta
    import zipfile
    with zipfile.ZipFile(doc.FileName) as z:
        gui = z.read("GuiDocument.xml").decode("utf-8")
    i = gui.find('name="%s"' % placa.Name)
    trozo = gui[i:gui.find("</ViewProvider>", i)] if i >= 0 else ""
    assert trozo and 'name="OverrideMaterial"' in trozo, "no se encontró el material de la placa en el archivo"
    k = trozo.index('name="OverrideMaterial"')
    assert 'value="false"' in trozo[k:k + 200], "el material transparente de Editar pieza quedó en el archivo"
    assert abs(ep.ghost_level(placa) - ep.GHOST) < 1e-6, "después de guardar no volvió la transparencia"
    assert not gdoc.Modified, "guardar editando dejó el ensamblaje modificado"
    yield 100

    traza("paso 5")
    # 5) Algo que queda: un plano en la pieza; Salir: todo como antes; guardar pregunta por la pieza
    plano = body.newObject("PartDesign::Plane", "PlanoNuevo")
    plano.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    plano.MapMode = "FlatFace"
    pdoc.recompute()
    pasos = list(doc.UndoNames)
    # Salir con el botón de la barra
    from swui.compat import QtWidgets as _QW
    boton = [b for b in FreeCADGui.getMainWindow().findChildren(_QW.QPushButton, "SWUI_edit_part_exit")
             if b.isVisible()]
    assert boton, "no está el botón Salir de la barra"
    boton[0].click()
    bombear(300)
    assert ep.editing(doc) is None, "el botón Salir no salió"
    assert list(doc.UndoNames) == pasos, "salir dejó un paso de deshacer"
    quedo = view.getActiveObject("pdbody", False)
    assert not quedo or quedo[0] is None, "el Cuerpo siguió activo: %s" % (quedo,)
    assert ep.ghost_level(placa) == antes and not vo.OverrideMaterial, "la placa no volvió a como estaba"
    assert not [w for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QLabel, "SWUI_edit_part_label")
                if w.isVisible()], "quedó la barra"
    assert FreeCADGui.getDocument(pdoc.Name).Modified, "la pieza tenía que quedar modificada"
    visto = _contestar(True)
    doc.save()
    for _i in range(25):  # la pregunta sale apenas termina de guardar; Sí guarda la pieza
        bombear(200)
        if not FreeCADGui.getDocument(pdoc.Name).Modified:
            break
    assert "Taco" in visto.get("texto", ""), "no preguntó por la pieza cambiada: %s" % visto
    with zipfile.ZipFile(pdoc.FileName) as z:
        guardado = b"PlanoNuevo" in z.read("Document.xml")
    assert not FreeCADGui.getDocument(pdoc.Name).Modified, "Sí no guardó la pieza: %s, en el archivo %s, tocadas %s" % (visto, guardado, ep._touched)
    with zipfile.ZipFile(pdoc.FileName) as z:
        assert b"PlanoNuevo" in z.read("Document.xml"), "el archivo de la pieza no tiene el plano"
    yield 100

    traza("paso 6")
    # 6) Editar operación / Editar croquis desde la cara del componente: en la pieza, sin salir
    FreeCADGui.Selection.clearSelection()
    sub = "%s.%s.Face6" % (taco.Name, body.Name)
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, sub)
    cb = taco.Shape.BoundBox
    m = _menu(derecho_vista(V(cb.Center.x, cb.Center.y, cb.ZMax)))
    for t in ("Editar operación", "Editar croquis", "Editar pieza"):
        assert t in m["vis"][0], "cara del componente: falta %r en %s" % (t, m["vis"][0])
    abierto = ep.open_in_assembly(asm, sub)
    bombear(800)
    pad = [o for o in pdoc.Objects if o.TypeId == "PartDesign::Pad"][0]
    assert abierto is pad, "Editar operación no abrió la extrusión: %s" % abierto
    enedicion = FreeCADGui.getDocument(doc.Name).getInEdit()
    assert enedicion is not None and FreeCAD.ActiveDocument is doc, "no quedó abierta en el ensamblaje"
    FreeCADGui.Control.closeDialog()
    bombear(300)
    FreeCADGui.getDocument(doc.Name).resetEdit()
    bombear(500)
    sk = ep.open_in_assembly(asm, sub, sketch=True)
    bombear(800)
    assert sk is not None and sk.TypeId == "Sketcher::SketchObject", "Editar croquis no abrió el croquis"
    FreeCADGui.Control.closeDialog()
    bombear(300)
    FreeCADGui.getDocument(doc.Name).resetEdit()
    bombear(500)
    yield 100

    traza("paso 7")
    # 7) Componente de una pieza con configuraciones (copia dentro del ensamblaje): no entra, con el
    # aviso que corresponde; en otra configuración, el aviso aprobado por el usuario
    assert ep.is_copy(tconf), "el componente de la pieza con configuraciones no es una copia"
    assert ep.check(tconf) == ep.COPY_SAME, ep.check(tconf)
    assert not ep.start(tconf, warn=False), "entró a Editar pieza con una copia"
    sub2 = "%s.%s.Face6" % (tconf.Name, tconf.LinkedObject.Name)
    assert ep.open_in_assembly(asm, sub2, warn=False) is None, "abrió una operación de la copia"
    doc.openTransaction("Configuración")
    config_asm.set_config(tconf, "Alta")
    doc.recompute()
    doc.commitTransaction()
    bombear(1500)
    assert ep.check(tconf) == ep.COPY_WARNING, ep.check(tconf)
    assert ep.editing(doc) is None
    yield 100

    traza("paso 8")
    # 8) El ícono otra vez sale; salir por lo nativo (otro Cuerpo activo) también deja todo como antes
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, placa.Name + ".")
    FreeCADGui.runCommand(ep.EDIT_PART)
    bombear(300)
    assert ep.editing(doc) is placa, "el ícono no entró a Editar pieza"
    FreeCADGui.runCommand(ep.EDIT_PART)
    bombear(300)
    assert ep.editing(doc) is None, "el ícono otra vez no salió"
    assert ep.start(placa, warn=False)
    view.setActiveObject("pdbody", None)  # como un doble clic afuera
    bombear(2500)
    assert ep.editing(doc) is None, "saliendo por lo nativo quedó Editar pieza colgado"
    assert ep.ghost_level(placa) == antes
    yield 100

    # 9) Un Cuerpo propio del ensamblaje (mismo archivo) no es una copia: se puede editar
    propio = doc.addObject("PartDesign::Body", "Propio")
    caja = propio.newObject("PartDesign::AdditiveBox", "CajaPropia")
    caja.Placement.Base = V(0, -100, 0)
    vinculo = doc.addObject("App::Link", "PropioLink")
    vinculo.LinkedObject = propio
    asm.addObject(vinculo)
    propio.Visibility = False
    doc.recompute()
    assert not ep.is_copy(vinculo), "un Cuerpo del mismo archivo se tomó como copia de configuración"
    assert ep.check(vinculo) is None, ep.check(vinculo)
    yield 100

    # 10) Cerrar el ensamblaje editando: sin barra colgada ni estado
    assert ep.start(placa, warn=False), "no entró a Editar pieza con la placa"
    visto = _contestar(False)  # si pregunta por piezas al cerrar, No
    FreeCAD.closeDocument(doc.Name)
    bombear(500)
    visto["fin"] = True
    assert not ep._editing and not [w for w in FreeCADGui.getMainWindow().findChildren(
        QtWidgets.QLabel, "SWUI_edit_part_label") if w.isVisible()], "quedó Editar pieza después de cerrar"


from _base import ejecutar  # noqa: E402
ejecutar(globals())
