# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Con la ventana (revisión del 14/11): relaciones válidas que no son entre dos caras planas
(arista recta contra cara, cilindro contra cara a una distancia, vértice contra cara) no se marcan
como "definidas en exceso" y no se gira ninguna pieza sin motivo: el control de "se cumple de
verdad" solo es estricto con dos caras planas (y dos ejes en la Concéntrica)."""
TIPO = "completa"
import FreeCAD  # noqa: E402

V = FreeCAD.Vector


def _caso(base, carpeta, nombre, key, sub_placa, sub_otro, perno=False, valor=None):
    from swui.fork import mates_sw
    otra = base._pieza(carpeta, nombre, 0, 0, 0, cilindro=(3, 20)) if perno else base._pieza(carpeta, nombre, 20, 20, 20)
    doc, asm, (placa, pieza) = base._ensamblaje([base._pieza(carpeta, "Placa" + nombre, 100, 60, 10), otra])
    pieza.Placement = FreeCAD.Placement(V(30, 20, 40), FreeCAD.Rotation())
    doc.recompute()
    sub = sub_otro(pieza) if callable(sub_otro) else sub_otro
    from _base import traza
    traza("  %s: %s %s / %s %s" % (nombre, placa.Name, sub_placa, pieza.Name, sub))
    r, joint = base._relacionar(doc, asm, key, [(placa, sub_placa), (pieza, sub)], valor)
    traza("  %s: resultado %s, objetos %s" % (nombre, r, [o.Name for o in doc.Objects]))
    return r, joint, mates_sw.joint_satisfied(joint), None


def prueba():
    import casos_relacion as base
    from _base import carpeta_temporal

    def arista_arriba(pieza):
        for i, e in enumerate(pieza.LinkedObject.Shape.Edges):
            if e.Curve.__class__.__name__ == "Line" and abs(e.Vertexes[0].Point.z - 20) < 1e-6 \
                    and abs(e.Vertexes[1].Point.z - 20) < 1e-6:
                return "Edge%d" % (i + 1)

    def cilindro(pieza):
        for i, f in enumerate(pieza.LinkedObject.Shape.Faces):
            if f.Surface.__class__.__name__ == "Cylinder":
                return "Face%d" % (i + 1)

    carpeta = carpeta_temporal()
    casos = [
        ("arista recta contra la cara de arriba", "A", "coincident", "Face6", arista_arriba, False, None),
        ("vértice contra la cara de arriba", "B", "coincident", "Face6", "Vertex1", False, None),
        ("cilindro a 15 mm de la cara de costado", "C", "distance", "Face3", cilindro, True, 15.0),
    ]
    for que, nombre, key, cara, sub, perno, valor in casos:
        carpeta = carpeta_temporal()  # cada caso en su carpeta (su propio Conjunto.FCStd)
        r, joint, cumple, giro = _caso(base, carpeta, nombre, key, cara, sub, perno, valor)
        assert r == 0, "%s: no se resolvió (%s)" % (que, r)
        assert cumple, "%s: una relación válida se toma como que no se cumple" % que
        assert not joint.Suppressed, "%s: quedó suprimida" % que
        yield 300
        base._cerrar()
        yield 300


from _base import ejecutar  # noqa: E402
ejecutar(globals())
