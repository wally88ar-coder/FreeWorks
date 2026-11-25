# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#102: con un croquis abierto en la cara de arriba de un bloque y vista isométrica, pasar el mouse por el medio
de la cara, donde en pantalla cae una arista de la cara de ABAJO (tapada por el sólido), la enganchaba (naranja) y
el clic de la Línea iba a esa arista. En SW no se enganchan las aristas tapadas.
Tiene que pasar, con la herramienta Línea activa y el mouse de verdad (eventos de movimiento):
1) sobre una arista tapada (de abajo, detrás de la cara de arriba): no se resalta nada;
2) sobre un vértice tapado (el de abajo, detrás de la cara): no se resalta nada;
3) sobre una arista visible de la cara de arriba: se resalta esa arista;
4) sobre una arista visible de abajo (que en pantalla cae fuera de la cara de arriba) y sobre una arista vertical
   visible: se resaltan (lo visible se sigue enganchando aunque no esté en el plano del croquis);
5) lo mismo con el croquis abierto en la cara de ABAJO, mirando desde arriba: las aristas de arriba (visibles, más
   cerca de la cámara) se enganchan, y las de abajo que quedan tapadas por la cara de arriba no;
6) chapa fina (300 x 200 x 2, vista entera): las de abajo de atrás, tapadas a 2 mm, no se enganchan; las de abajo
   de adelante, sí (revisión del 24/11: la tolerancia no puede pasar el espesor);
7) arista curva: en un cilindro Ø100 x 20, el borde de abajo de adelante (visible) se engancha y el de atrás no
   (2.ª revisión: medir con el punto de la curva, no el de su cuerda).
Editando una pieza en un ensamblaje, lo de atrás de un componente TRANSPARENTE se sigue enganchando (como SW): lo
cubre prueba_ventana_croquis_esc_linea (falló con la primera versión del arreglo)."""
TIPO = "completa"
import FreeCAD  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _mover(vista, punto_3d):
    """Mueve el mouse (evento de verdad) al lugar de la pantalla donde cae el punto."""
    from swui.compat import QtCore, QtGui, QtWidgets
    vp = vista.graphicsView().viewport()
    cx, cy = vista.getPointOnViewport(punto_3d)
    r = vp.devicePixelRatioF()
    punto = QtCore.QPointF(cx / r, vp.height() - cy / r)
    nada = QtCore.Qt.MouseButton.NoButton
    QtWidgets.QApplication.sendEvent(vp, QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, punto,
                                                           vp.mapToGlobal(punto.toPoint()), nada, nada,
                                                           QtCore.Qt.KeyboardModifier.NoModifier))
    bombear(250)


def _lado(p, poligono, margen=12.0):
    """1 si el punto de pantalla p cae dentro del polígono convexo con al menos `margen` píxeles de sobra, -1 si
    cae afuera con margen, 0 si está cerca del borde (dudoso: no se usa)."""
    import math
    signo, adentro, minimo = 0, True, None
    n = len(poligono)
    for i in range(n):
        a, b = poligono[i], poligono[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        largo = math.hypot(dx, dy) or 1.0
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (largo * largo)))
        d = math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])
        minimo = d if minimo is None else min(minimo, d)
        cruz = dx * (p[1] - a[1]) - dy * (p[0] - a[0])
        s = 1 if cruz > 0 else -1
        if signo and s != signo:
            adentro = False
        signo = signo or s
    if minimo < margen:
        return 0
    return 1 if adentro else -1


def prueba():
    import FreeCADGui
    from swui.fork import sketch_model_edges as sme
    doc = FreeCAD.newDocument("Tapada")
    FreeCAD.setActiveDocument(doc.Name)
    body = doc.addObject("PartDesign::Body", "Body")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 60, 40, 20
    doc.recompute()
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.mdiViewsOfType("Gui::View3DInventor")[0]
    shape = caja.Shape
    yield 500

    def cara(z):
        return "Face%d" % (1 + [i for i, f in enumerate(shape.Faces) if abs(f.CenterOfMass.z - z) < 1e-6
                                and abs(f.normalAt(0, 0).z) > 0.99][0])

    def caso(nombre, z_croquis, mirar):
        traza("%s: croquis en z=%g" % (nombre, z_croquis))
        sk = body.newObject("Sketcher::SketchObject", "Croquis")
        sk.AttachmentSupport = [(caja, [cara(z_croquis)])]
        sk.MapMode = "FlatFace"
        doc.recompute()
        gdoc.setEdit(sk.Name)
        bombear(800)
        mirar()
        vista.fitAll()
        bombear(800)
        FreeCADGui.runCommand("Sketcher_CreateLine")
        bombear(500)
        return sk

    def resaltado(punto, que):
        sme._state["hot"] = None
        _mover(vista, punto)
        hot = sme._state["hot"]
        traza("  %s %s -> %s" % (que, tuple(round(c, 1) for c in punto), hot and hot[:2]))
        return hot and hot[1]

    def salir():
        from swui.compat import QtCore, QtGui, QtWidgets
        vp = vista.graphicsView().viewport()
        for _i in range(2):
            QtWidgets.QApplication.sendEvent(vp, QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Escape,
                                                                 QtCore.Qt.KeyboardModifier.NoModifier))
            bombear(300)
        gdoc.resetEdit()
        bombear(500)

    def revisar(z_plano, z_lejos):
        """Aristas del lado lejano (z_lejos): las que en pantalla caen dentro de la cara cercana están tapadas."""
        cercana = [v.Point for v in shape.Faces[int(cara(z_plano)[4:]) - 1].OuterWire.OrderedVertexes]
        poligono = [tuple(vista.getPointOnViewport(p)) for p in cercana]
        tapadas, visibles = [], []
        for i, e in enumerate(shape.Edges):
            a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
            if abs(a.z - z_lejos) > 1e-6 or abs(b.z - z_lejos) > 1e-6:
                continue
            medio = (a + b) * 0.5
            lado = _lado(tuple(vista.getPointOnViewport(medio)), poligono)
            if lado:
                (tapadas if lado > 0 else visibles).append(("Edge%d" % (i + 1), medio))
        vert = [(i, v.Point) for i, v in enumerate(shape.Vertexes) if abs(v.Point.z - z_lejos) < 1e-6
                and _lado(tuple(vista.getPointOnViewport(v.Point)), poligono) > 0]
        traza("  tapadas %s, visibles %s, vértices tapados %s" % ([t[0] for t in tapadas], [v[0] for v in visibles],
                                                                   [v[0] + 1 for v in vert]))
        assert tapadas and visibles and vert, "la vista no deja aristas tapadas y visibles para probar"
        ocultos = set(t[0] for t in tapadas) | set("Vertex%d" % (v[0] + 1) for v in vert)
        malas = []  # lo enganchado sobre algo tapado no puede ser algo tapado (sí otra arista visible que pase por ahí)
        for nombre, medio in tapadas:
            if resaltado(medio, "tapada %s" % nombre) in ocultos:
                malas.append(nombre)
        for i, p in vert:
            if resaltado(p, "vértice tapado %d" % (i + 1)) in ocultos:
                malas.append("Vertex%d" % (i + 1))
        assert not malas, "#102: se enganchan aristas o vértices tapados por la cara: %s" % malas
        for nombre, medio in visibles:
            assert resaltado(medio, "visible %s" % nombre), "una arista visible (%s) ya no se engancha" % nombre
        # una arista de la cara del croquis (visible): se engancha
        borde = [(i, e) for i, e in enumerate(shape.Edges) if abs(e.Vertexes[0].Point.z - z_plano) < 1e-6
                 and abs(e.Vertexes[-1].Point.z - z_plano) < 1e-6][0]
        medio = (borde[1].Vertexes[0].Point + borde[1].Vertexes[-1].Point) * 0.5
        assert resaltado(medio, "del plano Edge%d" % (borde[0] + 1)), "una arista de la cara del croquis no se engancha"
        # una arista vertical visible (fuera de la cara cercana en pantalla)
        for i, e in enumerate(shape.Edges):
            a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
            medio = (a + b) * 0.5
            if abs(a.z - b.z) > 1e-6 and _lado(tuple(vista.getPointOnViewport(medio)), poligono) < 0:
                assert resaltado(medio, "vertical Edge%d" % (i + 1)), "la arista vertical visible Edge%d no se " \
                    "engancha" % (i + 1)
                break

    caso("1-4) cara de arriba, isométrica", 20, vista.viewIsometric)
    revisar(20, 0)
    salir()
    yield 100

    def desde_arriba_inclinado():
        # mirando desde arriba y un poco de costado (como isométrica, pero el croquis queda abajo)
        vista.viewIsometric()

    caso("5) cara de abajo, vista desde arriba", 0, desde_arriba_inclinado)
    # desde arriba, las aristas de abajo que caen dentro de la cara de arriba están tapadas por el sólido
    cercana = [v.Point for v in shape.Faces[int(cara(20)[4:]) - 1].OuterWire.OrderedVertexes]
    poligono = [tuple(vista.getPointOnViewport(p)) for p in cercana]
    abajo = []
    for i, e in enumerate(shape.Edges):
        a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
        medio = (a + b) * 0.5
        if abs(a.z) < 1e-6 and abs(b.z) < 1e-6 and _lado(tuple(vista.getPointOnViewport(medio)), poligono) > 0:
            abajo.append(("Edge%d" % (i + 1), medio))
    assert abajo, "la vista no deja aristas de abajo tapadas para probar"
    malas = [n for n, medio in abajo if resaltado(medio, "abajo tapada %s" % n) in set(x[0] for x in abajo)]
    assert not malas, "#102: con el croquis abajo, se enganchan aristas de abajo tapadas por la cara de arriba: %s" \
        % malas
    for i, e in enumerate(shape.Edges):
        a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
        if abs(a.z - 20) < 1e-6 and abs(b.z - 20) < 1e-6:
            assert resaltado((a + b) * 0.5, "arriba Edge%d" % (i + 1)), "una arista visible de arriba no se engancha"
            break
    salir()
    yield 100

    # 6) chapa fina (revisión del 24/11: la tolerancia no puede pasar el espesor): 300 x 200 x 2 vista entera; las
    # aristas de abajo de atrás (y = 200, x = 0) quedan tapadas a 2 mm de la cara de arriba; las de adelante, a la vista
    caja.Length, caja.Width, caja.Height = 300, 200, 2
    doc.recompute()
    shape = caja.Shape
    caso("6) chapa fina 300 x 200 x 2, cara de arriba, isométrica", 2, vista.viewIsometric)
    tapadas, visibles = [], []
    for i, e in enumerate(shape.Edges):
        a, b = e.Vertexes[0].Point, e.Vertexes[-1].Point
        if abs(a.z) > 1e-6 or abs(b.z) > 1e-6:
            continue
        medio = (a + b) * 0.5
        if abs(medio.y - 200) < 1e-6 or abs(medio.x) < 1e-6:
            tapadas.append(("Edge%d" % (i + 1), medio))
        else:
            visibles.append(("Edge%d" % (i + 1), medio))
    ocultas = set(n for n, _m in tapadas)
    malas = [n for n, medio in tapadas if resaltado(medio, "chapa, abajo atrás %s" % n) in ocultas]
    assert not malas, "#102: en chapa fina se enganchan aristas de abajo tapadas: %s" % malas
    for nombre, medio in visibles:
        assert resaltado(medio, "chapa, abajo adelante %s" % nombre) == nombre, \
            "en chapa fina, la arista de abajo visible %s no se engancha" % nombre
    salir()
    FreeCAD.closeDocument(doc.Name)
    yield 100

    # 7) arista curva (2.ª revisión del 24/11: el punto de la cuerda cae dentro del círculo): cilindro Ø100 x 20,
    # croquis arriba, isométrica; el borde de abajo de ADELANTE se ve y se engancha, el de ATRÁS está tapado
    doc = FreeCAD.newDocument("Cilindro")
    FreeCAD.setActiveDocument(doc.Name)
    body = doc.addObject("PartDesign::Body", "Body")
    caja = body.newObject("PartDesign::AdditiveCylinder", "Cilindro")
    caja.Radius, caja.Height = 50, 20
    doc.recompute()
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.mdiViewsOfType("Gui::View3DInventor")[0]
    shape = caja.Shape
    caso("7) cilindro Ø100 x 20, cara de arriba, isométrica", 20, lambda: vista.viewIsometric())
    abajo = ["Edge%d" % (i + 1) for i, e in enumerate(shape.Edges)
             if e.Curve.__class__.__name__ == "Circle" and abs(e.Curve.Center.z) < 1e-6][0]
    hacia = V(-vista.getViewDirection()[0], -vista.getViewDirection()[1], 0)  # hacia la cámara, en el piso
    hacia.normalize()
    assert resaltado(hacia * 50, "cilindro, borde de abajo adelante") == abajo, \
        "el borde de abajo visible del cilindro (curvo) no se engancha"
    assert resaltado(hacia * -50, "cilindro, borde de abajo atrás") != abajo, \
        "#102: se engancha el borde de abajo del cilindro tapado por la pared"
    salir()
    FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
