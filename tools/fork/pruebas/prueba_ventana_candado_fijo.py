# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (pedido del usuario 15/11): la pieza fija de un ensamblaje no muestra el candado
de FreeCAD en la vista (SW no muestra nada, solo "(f)" en el árbol) y sigue fija; al Fijar otra,
tampoco; deshacer/rehacer, guardar y reabrir (sin quedar modificado) lo mantienen, también en el
archivo sin FreeWorks. Arrastrar la fija muestra el globito de SW "El componente seleccionado está
fijo. No se puede mover."; un clic, la totalmente definida y la suelta, no (la suelta se mueve)."""
TIPO = "completa"
import os  # noqa: E402
import zipfile  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _fijas(doc):
    return [o for o in doc.Objects if hasattr(o, "ObjectToGround")]


def _px(view, vp, p):
    s = view.getSize()
    x, y = view.getPointOnViewport(p)[:2]
    return x * vp.width() / s[0], vp.height() - y * vp.height() / s[1]


def _arrastrar(view, comp, pasos=10, paso=6):
    """Botón izquierdo sobre el centro del componente y arrastre; devuelve si se vio el globito."""
    from swui.compat import QtCore, QtGui, QtWidgets

    QtWidgets.QToolTip.hideText()
    bombear(50)
    vp = view.graphicsView().viewport()
    x, y = _px(view, vp, comp.Shape.BoundBox.Center)
    L, N = QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.MouseButton.NoButton

    def ev(t, ex, ey, b, bs):
        p = QtCore.QPointF(ex, ey)
        return QtGui.QMouseEvent(t, p, QtCore.QPointF(vp.mapToGlobal(p)), b, bs,
                                 QtCore.Qt.KeyboardModifier.NoModifier)

    QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseMove, x, y, N, N))
    bombear(100)
    QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseButtonPress, x, y, L, L))
    bombear(100)
    for k in range(1, pasos + 1):
        QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseMove, x + paso * k, y + paso * k / 2, N, L))
        bombear(40)
    visto = QtWidgets.QToolTip.isVisible() and QtWidgets.QToolTip.text()
    QtWidgets.QApplication.sendEvent(vp, ev(QtCore.QEvent.Type.MouseButtonRelease, x + paso * pasos,
                                            y + paso * pasos / 2, L, N))
    bombear(50)
    QtWidgets.QToolTip.hideText()
    return visto or ""


def _visibilidad_en_archivo(ruta, nombre):
    """Lo que dice Document.xml del archivo para la Visibility de un objeto (sin FreeWorks)."""
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("Document.xml").decode("utf-8")
    i = xml.index('<Object name="%s"' % nombre, xml.index("<ObjectData"))
    j = xml.index("</Object>", i)
    trozo = xml[i:j]
    k = trozo.index('name="Visibility"')
    return 'value="true"' in trozo[k:k + 200]


def prueba():
    import FreeCADGui
    import casos_relacion as cr
    from swui.fork import fixed_drag_tip

    carpeta = carpeta_temporal()
    rutas = [cr._pieza(carpeta, "Placa", 100, 60, 10), cr._pieza(carpeta, "Bloque", 30, 20, 15),
             cr._pieza(carpeta, "Suelto", 20, 20, 20)]
    doc, asm, (placa, bloque, suelto) = cr._ensamblaje(rutas)
    fijas = _fijas(doc)
    assert len(fijas) == 1 and fijas[0].ObjectToGround is placa, "la primera pieza no quedó fija: %s" % fijas
    assert not fijas[0].Visibility, "se ve el candado de la pieza fija al insertarla"
    fija0 = placa.Placement
    for fa, fb in (("Face6", "Face5"), ("Face1", "Face1"), ("Face3", "Face3")):
        r, _j = cr._relacionar(doc, asm, "coincident", [(placa, fa), (bloque, fb)])
        assert r in (0, None), "no se resolvió la relación %s-%s (%s)" % (fa, fb, r)
    suelto.Placement.Base = V(150, 0, 0)
    doc.recompute()
    assert placa.Placement.isSame(fija0, 1e-6), "con el candado oculto la pieza fija se movió"
    yield 200

    # Fijar otra a mano (el comando de FreeCAD, como el botón Fijar/Flotar): sin candado; deshacer/rehacer
    from CommandCreateJoint import createGroundedJoint
    doc.openTransaction("Fijar")
    createGroundedJoint(suelto)
    doc.commitTransaction()
    bombear(100)
    nueva = [o for o in _fijas(doc) if o.ObjectToGround is suelto]
    assert nueva and not nueva[0].Visibility, "al Fijar otra pieza apareció el candado"
    doc.undo()
    bombear(100)
    assert not [o for o in _fijas(doc) if o.ObjectToGround is suelto], "Ctrl+Z no sacó el Fijar"
    doc.redo()
    bombear(100)
    nueva = [o for o in _fijas(doc) if o.ObjectToGround is suelto]
    assert nueva and not nueva[0].Visibility, "al rehacer el Fijar volvió el candado"
    doc.undo()
    bombear(100)
    yield 200

    # Globito al arrastrar (con el ensamblaje en edición, como queda al insertar)
    gdoc = FreeCADGui.getDocument(doc.Name)
    assert gdoc.getInEdit() is not None, "el ensamblaje no quedó en edición"
    view = gdoc.ActiveView
    view.viewTop()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(300)
    visto = _arrastrar(view, placa)
    assert visto == fixed_drag_tip.TEXT, "arrastrar la pieza fija no mostró el aviso de SW (%r)" % visto
    assert placa.Placement.isSame(fija0, 1e-6), "arrastrando, la pieza fija se movió"
    visto = _arrastrar(view, placa, pasos=1, paso=1)
    assert not visto, "un clic (sin arrastrar) en la fija mostró el aviso"
    b0 = bloque.Placement
    visto = _arrastrar(view, bloque)
    assert not visto, "la pieza totalmente definida mostró el aviso (SW no dice nada): %r" % visto
    s0 = suelto.Placement.Base
    visto = _arrastrar(view, suelto)
    assert not visto, "la pieza suelta mostró el aviso: %r" % visto
    assert (suelto.Placement.Base - s0).Length > 1, "la pieza suelta no se movió al arrastrarla"
    assert (bloque.Placement.Base - b0.Base).Length < 1e-3, "la pieza totalmente definida se movió al arrastrarla"
    yield 200

    # Guardar, cerrar y abrir: sin candado, sin quedar modificado, y en el archivo (sin FreeWorks)
    nombre_fija = fijas[0].Name
    doc.save()
    ruta = doc.FileName
    assert not _visibilidad_en_archivo(ruta, nombre_fija), "el archivo guarda la unión Fijar visible"
    for x in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(x.Name)
    bombear(200)
    doc = FreeCAD.openDocument(ruta)
    bombear(2500)
    fijas = _fijas(doc)
    assert fijas and not fijas[0].Visibility, "al reabrir volvió el candado"
    # el asterisco de "modificado" (lo que ve el usuario), como prueba_ventana_ensamblaje_abrir_modificado
    assert not FreeCADGui.getDocument(doc.Name).Modified, "al reabrir quedó modificado"
    yield 200

    # Dos archivos: el aviso funciona en el segundo y el primero no cambia
    carpeta2 = carpeta_temporal()
    doc2, asm2, (p2, b2) = cr._ensamblaje([cr._pieza(carpeta2, "Placa", 100, 60, 10),
                                           cr._pieza(carpeta2, "Bloque", 30, 20, 15)])
    assert _fijas(doc2) and not _fijas(doc2)[0].Visibility, "en el segundo archivo se ve el candado"
    view2 = FreeCADGui.getDocument(doc2.Name).ActiveView
    view2.viewTop()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(300)
    assert FreeCADGui.getDocument(doc2.Name).getInEdit() is not None, "el segundo ensamblaje no quedó en edición"
    visto = _arrastrar(view2, p2)
    assert visto == fixed_drag_tip.TEXT, "en el segundo archivo no salió el aviso (%r)" % visto
    assert not _fijas(doc)[0].Visibility, "abrir otro archivo volvió a mostrar el candado del primero"
    cr._cerrar()
    yield 200


from _base import ejecutar  # noqa: E402
ejecutar(globals())
