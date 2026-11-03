# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Pruebas sin interfaz de las herramientas de entidades del croquis (Simetría, Mover, Copiar,
Girar, Escalar, Matriz lineal, Equidistanciar). Correr con FreeCADCmd:
    D:/Freecad/bin/freecadcmd.exe tools/fork/test_sketch_entities.py
Cada caso imprime sus relaciones; ninguno debe quedar con redundantes ni en conflicto.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402
from swui.fork import sketch_entities as se  # noqa: E402
V=App.Vector
def rep(s,t):
    s.solve(); print(t,"geo",s.GeometryCount,"cons",[c.Type for c in s.Constraints],"dof",s.solve(), "red",list(s.RedundantConstraints),"conf",list(s.ConflictingConstraints))
d=App.newDocument("t1")
# caso 1: linea+arco tangente+circulo, eje V
s=d.addObject("Sketcher::SketchObject","S1")
s.addGeometry(Part.LineSegment(V(5,5,0),V(20,5,0)))
s.addGeometry(Part.ArcOfCircle(Part.Circle(V(20,10,0),V(0,0,1),5),-1.5708,1.5708))
s.addGeometry(Part.Circle(V(10,20,0),V(0,0,1),3))
s.addConstraint(Sketcher.Constraint("Tangent",0,2,1,1))
s.addConstraint(Sketcher.Constraint("Horizontal",0))
dx=s.addConstraint(Sketcher.Constraint("DistanceX",0,1,0,2,15))
r=s.addConstraint(Sketcher.Constraint("Radius",2,3))
d.recompute()
new=se.mirror_entities(s,[0,1,2],-2); print("new",new); rep(s,"caso1")
s.setDatum(dx,App.Units.Quantity("25 mm")); s.setDatum(r,App.Units.Quantity("4 mm")); d.recompute()
print("orig end",s.getPoint(0,2),"copy end",s.getPoint(new[0],2),"copy r",s.Geometry[new[2]].Radius)
# caso 2: media silueta con extremos sobre linea constructiva vertical en x=0
s=d.addObject("Sketcher::SketchObject","S2")
s.addGeometry(Part.LineSegment(V(0,-20,0),V(0,20,0)),True)
s.addGeometry(Part.LineSegment(V(0,0,0),V(10,0,0)))
s.addGeometry(Part.LineSegment(V(10,0,0),V(10,8,0)))
s.addGeometry(Part.LineSegment(V(10,8,0),V(0,8,0)))
s.addConstraint(Sketcher.Constraint("Coincident",1,2,2,1))
s.addConstraint(Sketcher.Constraint("Coincident",2,2,3,1))
s.addConstraint(Sketcher.Constraint("PointOnObject",1,1,0))
s.addConstraint(Sketcher.Constraint("Horizontal",1)); s.addConstraint(Sketcher.Constraint("Vertical",2))
d.recompute()
new=se.mirror_entities(s,[1,2,3],0); print("new",new); rep(s,"caso2")
# caso 3: sin copiar
s=d.addObject("Sketcher::SketchObject","S3")
s.addGeometry(Part.LineSegment(V(5,5,0),V(20,5,0))); s.addGeometry(Part.Point(V(8,9,0)))
s.addGeometry(Part.LineSegment(V(-30,-1,0),V(30,-1,0)))
d.recompute()
new=se.mirror_entities(s,[0,1],2,copy=False); print("new",new); rep(s,"caso3"); print([ (type(g).__name__) for g in s.Geometry], s.getPoint(new[0],1))
print("preview", len(se.mirror_preview(s,[0],1)))
print("names", se.sw_name(s,0), se.sw_name(s,1), se.parse_sub(s,"Edge2"), se.parse_sub(s,"V_Axis"), se.parse_sub(s,"ExternalEdge1"))
# caso 4: como SW: rectangulo con lados que tocan el eje
s=d.addObject("Sketcher::SketchObject","S4")
s.addGeometry(Part.LineSegment(V(0,-40,0),V(0,40,0)),True)
s.addGeometry(Part.LineSegment(V(0,0,0),V(30,0,0)))
s.addGeometry(Part.LineSegment(V(30,0,0),V(30,20,0)))
s.addGeometry(Part.LineSegment(V(30,20,0),V(0,20,0)))
s.addGeometry(Part.Circle(V(15,10,0),V(0,0,1),4))
for c in (("Coincident",1,2,2,1),("Coincident",2,2,3,1),("PointOnObject",1,1,0),("PointOnObject",3,2,0)):
    s.addConstraint(Sketcher.Constraint(*c))
s.addConstraint(Sketcher.Constraint("Horizontal",1)); s.addConstraint(Sketcher.Constraint("Horizontal",3)); s.addConstraint(Sketcher.Constraint("Vertical",2))
d.recompute(); s.solve(); dof0=s.solve()
new=se.mirror_entities(s,[1,2,3,4],0); print("new",new); rep(s,"caso4")
for g in range(s.GeometryCount): print(g,type(s.Geometry[g]).__name__, s.getPoint(g,1) if type(s.Geometry[g]).__name__!="Circle" else s.getPoint(g,3), s.getPoint(g,2) if type(s.Geometry[g]).__name__=="LineSegment" else "")
# mover la esquina original y ver que todo sigue
s.moveGeometry(2,2,V(40,25,0),False); s.solve(); d.recompute()
for g in range(s.GeometryCount):
    G=s.Geometry[g]
    if type(G).__name__=="LineSegment": print("tras mover",g,G.StartPoint,G.EndPoint)

import FreeCAD as App, Part, Sketcher
from swui.fork import sketch_transform as st, sketch_offset as so
V = App.Vector
d = App.newDocument("t2")


def L(s):
    """Escuadra en L: (0,0)-(30,0)-(30,20), unida, horizontal/vertical, cota 30 y punto en el origen."""
    s.addGeometry(Part.LineSegment(V(0, 0, 0), V(30, 0, 0)))
    s.addGeometry(Part.LineSegment(V(30, 0, 0), V(30, 20, 0)))
    s.addConstraint(Sketcher.Constraint("Coincident", 0, 2, 1, 1))
    s.addConstraint(Sketcher.Constraint("Horizontal", 0))
    s.addConstraint(Sketcher.Constraint("Vertical", 1))
    s.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
    s.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 30))
    d.recompute()


def rep(s, tag):
    s.solve()
    lines = [(g, tuple(round(c, 2) for c in s.getPoint(g, 1)), tuple(round(c, 2) for c in s.getPoint(g, 2)))
             for g in range(s.GeometryCount) if type(s.Geometry[g]).__name__ == "LineSegment"]
    print(tag, "geo", s.GeometryCount, "cons", [c.Type for c in s.Constraints], "red", list(s.RedundantConstraints),
          "conf", list(s.ConflictingConstraints))
    print("   ", lines)


s = d.addObject("Sketcher::SketchObject", "Mover"); L(s)
st.move_entities(s, [0, 1], V(5, 7, 0)); rep(s, "mover sin conservar")
s = d.addObject("Sketcher::SketchObject", "Copiar"); L(s)
print("copia", st.copy_entities(s, [0, 1], V(0, 40, 0))); rep(s, "copiar")
s = d.addObject("Sketcher::SketchObject", "Girar"); L(s)
st.rotate_entities(s, [0, 1], V(0, 0, 0), 90); rep(s, "girar 90")
s = d.addObject("Sketcher::SketchObject", "Girar30"); L(s)
st.rotate_entities(s, [0, 1], V(0, 0, 0), 30); rep(s, "girar 30")
s = d.addObject("Sketcher::SketchObject", "Escala"); L(s)
st.scale_entities(s, [0, 1], V(0, 0, 0), 2); rep(s, "escala x2")
s = d.addObject("Sketcher::SketchObject", "Escala2"); L(s)
print("copias", st.scale_entities(s, [0, 1], V(0, 0, 0), 0.5, copies=2)); rep(s, "escala 2 copias")
s = d.addObject("Sketcher::SketchObject", "Matriz"); L(s)
print("matriz", st.linear_pattern(s, [0, 1], 3, 40, 0, 2, 30, 90)); rep(s, "matriz 3x2")
s = d.addObject("Sketcher::SketchObject", "Matriz45"); L(s)
print("matriz45", st.linear_pattern(s, [0, 1], 2, 40, 0, 2, 30, 45)); rep(s, "matriz 2x2 a 45")
s = d.addObject("Sketcher::SketchObject", "Equi"); L(s)
print("equi", so.offset_entities(s, [0], 10, side=V(15, -5, 0))); rep(s, "equidistanciar afuera (como SW)")
print("    expr", s.ExpressionEngine, [c.Name for c in s.Constraints if c.Name])
s = d.addObject("Sketcher::SketchObject", "EquiB"); L(s)
print("equiB", so.offset_entities(s, [0], 5, both=True, caps="arcs")); rep(s, "bidireccional tapas arcos")
s = d.addObject("Sketcher::SketchObject", "EquiL"); L(s)
print("equiL", so.offset_entities(s, [1], 5, both=True, caps="lines")); rep(s, "bidireccional tapas lineas")
s = d.addObject("Sketcher::SketchObject", "Rect")
for a, b in ((V(0, 0, 0), V(30, 0, 0)), (V(30, 0, 0), V(30, 20, 0)), (V(30, 20, 0), V(0, 20, 0)), (V(0, 20, 0), V(0, 0, 0))):
    s.addGeometry(Part.LineSegment(a, b))
for i in range(4):
    s.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
s.addGeometry(Part.Circle(V(15, 10, 0), V(0, 0, 1), 4))
d.recompute()
print("rect", so.offset_entities(s, [2], 3, side=V(15, 30, 0))); rep(s, "rectangulo afuera 3")
print("circ", so.offset_entities(s, [4], 2, side=V(15, 10, 0))); rep(s, "circulo adentro 2")
print("chain", so.chain_of(s, 0))
# la matriz sigue al original
s = d.getObject("Matriz")
idx = [i for i, c in enumerate(s.Constraints) if c.Type == "DistanceX"][0]
s.setDatum(idx, 50.0); s.solve(); d.recompute()
print("matriz tras cambiar largo:", [round(s.Geometry[g].length(), 2) for g in (0, 2, 5, 8)], list(s.RedundantConstraints))
