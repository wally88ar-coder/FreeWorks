# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana: girar con la ruedita "Como SolidWorks" (swui/fork/orbit_speed.py, 14/11).
Arrastrar a los costados gira alrededor del eje vertical de la pantalla y arriba/abajo alrededor del
horizontal, en cualquier parte de la vista y sin torcer; los grados son los medidos en SW 2018
(377° por alto de vista horizontal, por ancho + 236 px vertical) y proporcionales al recorrido. Con la
pieza entera gira en su centro (no se mueve en pantalla); con mucho zoom, cerca de lo que hay en el
centro de la pantalla. Ctrl + ruedita sigue desplazando, un clic suelto no mueve nada, girar no deja
el archivo modificado ni toca la vista de otro archivo, anda editando un croquis, y "Como FreeCAD"
deja girar a FreeCAD."""
TIPO = "completa"

import math  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal  # noqa: E402

TOL_GRADOS = 0.6


def _sw(dx, dy, w, h):
    """Grados que gira SW 2018 (medido el 14/11 con 3 tamaños de ventana; a propósito sin usar el código)."""
    return 377.0 * dx / h, 377.0 * dy / (w + 236.0)


def _vp(view):
    return view.graphicsView().viewport()


def _arrastrar(view, x0, y0, dx, dy, n=20, mods=None):
    from PySide import QtCore, QtGui, QtWidgets
    w = _vp(view)
    mods = mods if mods is not None else QtCore.Qt.KeyboardModifier.NoModifier
    M, N = QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.MouseButton.NoButton

    def ev(t, x, y, b, bs):
        p = QtCore.QPointF(x, y)
        QtWidgets.QApplication.sendEvent(w, QtGui.QMouseEvent(t, p, QtCore.QPointF(w.mapToGlobal(p)), b, bs, mods))
        QtWidgets.QApplication.processEvents()

    ev(QtCore.QEvent.Type.MouseMove, x0, y0, N, N)
    ev(QtCore.QEvent.Type.MouseButtonPress, x0, y0, M, M)
    for i in range(1, n + 1):
        ev(QtCore.QEvent.Type.MouseMove, x0 + dx * i / n, y0 + dy * i / n, N, M)
    ev(QtCore.QEvent.Type.MouseButtonRelease, x0 + dx, y0 + dy, M, N)


def _giro(a, b):
    """Grados y eje (en ejes de la cámara) entre dos orientaciones de cámara."""
    q = a.inverted().multiply(b)
    return math.degrees(q.Angle), q.Axis


def _iso(view):
    view.viewIsometric()
    view.fitAll()


def _px(view, p):
    x, y = view.getPointOnViewport(p)[:2]
    return x, y


def prueba():
    """Prepara las preferencias y las devuelve como estaban al terminar (bien o mal)."""
    from swui.fork import orbit_speed as osp
    vista = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
    swui = FreeCAD.ParamGet(osp.PARAMS)
    antes = (vista.GetString("NavigationStyle", ""), vista.GetBool("UseNavigationAnimations", True),
             swui.GetBool(osp.SW_KEY, True), swui.GetFloat(osp.KEY, osp.DEFAULT))
    vista.SetString("NavigationStyle", "Gui::SolidWorksNavigationStyle")
    vista.SetBool("UseNavigationAnimations", False)
    osp.set_like_sw(True)
    try:
        yield from _pasos(osp)
    finally:
        vista.SetString("NavigationStyle", antes[0])
        vista.SetBool("UseNavigationAnimations", antes[1])
        swui.SetBool(osp.SW_KEY, antes[2])
        swui.SetFloat(osp.KEY, antes[3])
        for nombre in list(FreeCAD.listDocuments()):  # cada prueba corre en su propio FreeCAD
            FreeCAD.closeDocument(nombre)


def _pasos(osp):
    import FreeCADGui
    from PySide import QtCore

    doc = FreeCAD.newDocument("GiroSW")
    caja = doc.addObject("Part::Box", "Caja")
    caja.Length = caja.Width = caja.Height = 50
    doc.recompute()
    ruta = os.path.join(carpeta_temporal(), "giro.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    yield 500
    doc = FreeCAD.openDocument(ruta)  # recién abierto: sin "modificado" (como el mono)
    yield 1500
    view = FreeCADGui.getDocument(doc.Name).ActiveView
    assert hasattr(view.getCameraNode(), "height"), "la prueba necesita la cámara ortográfica (la de SW)"
    _iso(view)
    yield 500
    w = _vp(view)
    W, H = w.width(), w.height()
    centro = FreeCAD.Vector(25, 25, 25)
    assert not FreeCADGui.getDocument(doc.Name).Modified, "recién abierto ya figura modificado"

    # 1) grados y ejes en distintos lugares de la vista, sin torcer
    casos = [("horizontal al centro", W / 2, H / 2, 150, 0), ("horizontal arriba", W / 2, H * 0.12, 150, 0),
             ("horizontal abajo", W / 2, H * 0.88, 150, 0), ("vertical al centro", W / 2, H / 2, 0, 150),
             ("vertical a la izquierda", W * 0.1, H / 2, 0, 150), ("horizontal corto", W / 2, H / 2, 50, 0),
             ("vertical corto", W / 2, H / 2, 0, 50), ("diagonal", W / 2, H / 2, 100, 100)]
    for nombre, x, y, dx, dy in casos:
        _iso(view)
        yield 150
        a = view.getCameraOrientation()
        c0 = _px(view, centro)
        _arrastrar(view, x - dx / 2, y - dy / 2, dx, dy)
        yield 150
        b = view.getCameraOrientation()
        ang, eje = _giro(a, b)
        gh, gv = _sw(dx, dy, W, H)
        esperado = math.hypot(gh, gv)
        assert abs(ang - esperado) < TOL_GRADOS, "%s: giró %.1f°, SW %.1f°" % (nombre, ang, esperado)
        assert abs(eje.z) * ang < TOL_GRADOS, "%s: se torció %.1f°" % (nombre, eje.z * ang)
        if dx and dy:
            assert abs(abs(eje.x) / abs(eje.y) - gv / gh) < 0.05, "diagonal: eje %s" % eje
        c1 = _px(view, centro)
        assert math.hypot(c1[0] - c0[0], c1[1] - c0[1]) < 2.0, \
            "%s: con la pieza entera el centro se movió %s -> %s" % (nombre, c0, c1)

    # 2) mucho zoom: gira cerca de lo que hay en el centro de la pantalla, no del centro de la pieza
    _iso(view)
    cam = view.getCameraNode()
    cam.height.setValue(cam.height.getValue() * 0.4)
    yield 300
    s = view.getSize()
    info = view.getObjectInfo((int(s[0] / 2), int(s[1] / 2)))
    assert info, "con zoom no hay pieza en el centro de la pantalla"
    sup = FreeCAD.Vector(info["x"], info["y"], info["z"])
    c0, s0 = _px(view, centro), _px(view, sup)
    _arrastrar(view, W / 2 + 60, H / 2 + 40, 150, 0)
    yield 150
    c1, s1 = _px(view, centro), _px(view, sup)
    mueve_c = math.hypot(c1[0] - c0[0], c1[1] - c0[1])
    mueve_s = math.hypot(s1[0] - s0[0], s1[1] - s0[1])
    assert mueve_c > 50, "con mucho zoom siguió girando en el centro de la pieza (se movió %.0f px)" % mueve_c
    assert mueve_s < 0.6 * mueve_c, "con zoom el centro de la pantalla se escapó (%.0f px, centro de pieza %.0f)" % (
        mueve_s, mueve_c)

    # 3) Ctrl + ruedita desplaza (no gira); clic suelto no mueve nada
    _iso(view)
    yield 150
    a, c0 = view.getCameraOrientation(), _px(view, centro)
    _arrastrar(view, W / 2, H / 2, 120, 40, mods=QtCore.Qt.KeyboardModifier.ControlModifier)
    yield 150
    ang, _e = _giro(a, view.getCameraOrientation())
    c1 = _px(view, centro)
    assert ang < 0.1, "Ctrl + ruedita giró %.1f° (tiene que desplazar)" % ang
    assert math.hypot(c1[0] - c0[0], c1[1] - c0[1]) > 30, "Ctrl + ruedita no desplazó la vista"
    for nombre, mover in (("un clic suelto", 0), ("un clic con 1 px de temblor", 1)):
        _iso(view)
        yield 150
        a, p = view.getCameraOrientation(), cam.position.getValue().getValue()
        _arrastrar(view, W / 2, H / 2, mover, 0, n=1)
        yield 300
        ang, _e = _giro(a, view.getCameraOrientation())
        p2 = cam.position.getValue().getValue()
        assert ang < 0.01 and max(abs(u - v) for u, v in zip(p, p2)) < 1e-3, "%s movió la vista" % nombre
    # doble clic con la ruedita (Qt: apretar, soltar, doble clic, soltar): tampoco mueve nada
    from PySide import QtGui, QtWidgets
    _iso(view)
    yield 150
    a, p = view.getCameraOrientation(), cam.position.getValue().getValue()
    M, N = QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.MouseButton.NoButton
    pt = QtCore.QPointF(W / 2 + 30, H / 2 + 20)
    for t, b, bs in ((QtCore.QEvent.Type.MouseButtonPress, M, M), (QtCore.QEvent.Type.MouseButtonRelease, M, N),
                     (QtCore.QEvent.Type.MouseButtonDblClick, M, M), (QtCore.QEvent.Type.MouseButtonRelease, M, N)):
        QtWidgets.QApplication.sendEvent(w, QtGui.QMouseEvent(t, pt, QtCore.QPointF(w.mapToGlobal(pt)), b, bs,
                                                             QtCore.Qt.KeyboardModifier.NoModifier))
    yield 600
    ang, _e = _giro(a, view.getCameraOrientation())
    p2 = cam.position.getValue().getValue()
    assert ang < 0.01 and max(abs(u - v) for u, v in zip(p, p2)) < 1e-3, "un doble clic con la ruedita movió la vista"
    # el cursor que había (el de una herramienta del croquis, por ejemplo) vuelve después de girar
    w.setCursor(QtCore.Qt.CursorShape.CrossCursor)
    _arrastrar(view, W / 2, H / 2, 80, 0)
    yield 150
    assert w.cursor().shape() == QtCore.Qt.CursorShape.CrossCursor, \
        "después de girar el cursor quedó %s (era la cruz)" % w.cursor().shape()
    w.unsetCursor()

    # 4) girar no deja el archivo modificado
    assert not FreeCADGui.getDocument(doc.Name).Modified, "girar dejó el archivo como modificado"

    # 5) otro archivo: girar en uno no toca la vista del otro
    doc2 = FreeCAD.newDocument("Otro")
    doc2.addObject("Part::Box", "Caja2")
    doc2.recompute()
    yield 1000
    view2 = FreeCADGui.getDocument(doc2.Name).ActiveView
    _iso(view2)
    a1 = view.getCameraOrientation()
    b0 = view2.getCameraOrientation()
    w2 = _vp(view2)
    _arrastrar(view2, w2.width() / 2, w2.height() / 2, 150, 0)
    yield 150
    ang2 = _giro(b0, view2.getCameraOrientation())[0]
    esperado2 = _sw(150, 0, w2.width(), w2.height())[0]
    assert abs(ang2 - esperado2) < TOL_GRADOS, "en el segundo archivo giró %.1f°, SW %.1f°" % (ang2, esperado2)
    assert _giro(a1, view.getCameraOrientation())[0] < 0.01, "girar en otro archivo movió esta vista"
    FreeCAD.closeDocument(doc2.Name)
    yield 500

    # 6) editando un croquis también gira como SW
    sk = doc.addObject("Sketcher::SketchObject", "Croquis")
    doc.recompute()
    FreeCADGui.getDocument(doc.Name).setEdit(sk.Name)
    yield 1200
    view = FreeCADGui.getDocument(doc.Name).ActiveView
    a = view.getCameraOrientation()
    w = _vp(view)
    _arrastrar(view, w.width() / 2, w.height() / 2, 150, 0)
    yield 150
    ang, eje = _giro(a, view.getCameraOrientation())
    esperado = _sw(150, 0, w.width(), w.height())[0]
    assert abs(ang - esperado) < TOL_GRADOS, "en el croquis giró %.1f°, SW %.1f°" % (ang, esperado)
    FreeCADGui.getDocument(doc.Name).resetEdit()
    yield 800

    # 7) "Como FreeCAD": gira FreeCAD, no FreeWorks
    osp.set_like_sw(False)
    osp.set_factor(1.0)
    _iso(view)
    yield 150
    a = view.getCameraOrientation()
    _arrastrar(view, W / 2 - 75, H / 2, 150, 0)
    yield 150
    ang, _e = _giro(a, view.getCameraOrientation())
    assert ang > 5, "con \"Como FreeCAD\" no giró"
    assert abs(ang - _sw(150, 0, W, H)[0]) > 2, \
        "con \"Como FreeCAD\" giró igual que \"Como SolidWorks\" (%.1f°)" % ang


from _base import ejecutar  # noqa: E402
ejecutar(globals())
