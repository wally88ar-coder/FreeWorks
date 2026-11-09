# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Agente atacante, Configuraciones de pieza (escrito sin mirar el código, desde lo que promete
cada función y cómo se comporta SW 2018):
- una seguidilla al azar de agregar (con nombres raros: acentos, espacios, "123", "=1+1", "2mm",
  comillas, punto y coma), configurar la profundidad y el ancho del croquis "en esta" o "en todas",
  pasar de una a otra, cambiar el nombre y eliminar (no la activa) deja SIEMPRE la pieza con las
  medidas de la configuración activa, según un modelo llevado a mano;
- después de guardar, cerrar y abrir: mismos nombres, misma activa y, al pasar por cada una, las
  mismas medidas;
- un nombre repetido o vacío se rechaza con ValueError (como SW) y no cambia nada;
- suprimir una operación en una configuración no la suprime en las otras;
- agregar una configuración dentro de un paso de deshacer: Deshacer la saca y vuelve a la pieza
  de antes;
- col_letter es una numeración de columnas sin huecos ni repetidos (1 -> A, 27 -> AA) y
  clean_alias siempre da un alias válido (letras, números y _, sin empezar con número).
"""
TIPO = "azar"

import os  # noqa: E402
import re  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import Fallas, cerca, comprobado, hypothesis_listo  # noqa: E402

V = FreeCAD.Vector
ALTO = 5.0


def _pieza(nombre="Conf"):
    doc = FreeCAD.newDocument(nombre)
    doc.UndoMode = 1
    b = doc.addObject("PartDesign::Body", "Body")
    sk = b.newObject("Sketcher::SketchObject", "Sketch")
    xy = [f for f in b.Origin.OriginFeatures if f.Role == "XY_Plane"][0]
    sk.AttachmentSupport = [(xy, "")]
    sk.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(10, 0, 0), V(10, ALTO, 0), V(0, ALTO, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 0))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sk.addConstraint(Sketcher.Constraint("Vertical", 1))
    sk.addConstraint(Sketcher.Constraint("Vertical", 3))
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 10.0))  # índice 8: el ancho
    sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, ALTO))
    pad = b.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = 7.0
    doc.recompute()
    return doc, b, sk, pad


NOMBRES = ["Corta", "Larga ñandú", "Con espacio", "123", "=1+1", "2mm", "'Comilla", 'Dice "hola"',
           "a;b", "Ácido", "Configuración2", "X"]


def _medidas(doc):
    b = doc.getObject("Body")
    return float(doc.getObject("Pad").Length), float(doc.getObject("Sketch").Constraints[8].Value), b


def _comprobar(doc, modelo, c, paso):
    largo, ancho, b = _medidas(doc)
    act = c.active(doc)
    assert act in modelo, "%s: la activa %r no está en el modelo %r" % (paso, act, list(modelo))
    el, ea = modelo[act]
    assert cerca(largo, el) and cerca(ancho, ea), ("%s: en %r la pieza tiene prof %r ancho %r y debería "
                                                   "tener %r, %r" % (paso, act, largo, ancho, el, ea))
    assert cerca(b.Shape.Volume, el * ea * ALTO), "%s: volumen %r" % (paso, b.Shape.Volume)
    assert sorted(c.names(doc)) == sorted(modelo), "%s: nombres %r, modelo %r" % (paso, c.names(doc), list(modelo))


def prueba():
    given, cfg, st = hypothesis_listo()
    from swui.fork import configurations as c
    f = Fallas()

    accion = st.one_of(
        st.tuples(st.just("add"), st.sampled_from(NOMBRES)),
        st.tuples(st.just("largo"), st.integers(1, 60), st.sampled_from(["this", "all"])),
        st.tuples(st.just("ancho"), st.integers(1, 60), st.sampled_from(["this", "all"])),
        st.tuples(st.just("activar"), st.integers(0, 20)),
        st.tuples(st.just("renombrar"), st.integers(0, 20), st.sampled_from(NOMBRES)),
        st.tuples(st.just("eliminar"), st.integers(0, 20)),
    )

    @cfg
    @given(acciones=st.lists(accion, min_size=1, max_size=10),
           doc_nombre=st.sampled_from(["Pieza", "Pieza con ñ y espacio"]))
    def seguidilla(acciones, doc_nombre):
        doc, body, sk, pad = _pieza(doc_nombre)
        carpeta = carpeta_temporal()
        try:
            c.ensure(doc)
            doc.recompute()
            modelo = {c.active(doc): (7.0, 10.0)}
            t_largo = ("prop", pad, "Length")
            t_ancho = ("sketch", sk, 8)
            for i, a in enumerate(acciones):
                paso = "paso %d %r" % (i, a)
                traza("  " + paso)
                act = c.active(doc)
                nombres = c.names(doc)
                if a[0] == "add":
                    if a[1] in modelo:
                        try:
                            c.add(doc, a[1])
                        except ValueError:
                            pass
                        else:
                            raise AssertionError("%s: aceptó un nombre repetido" % paso)
                    else:
                        nuevo = c.add(doc, a[1])
                        assert nuevo == a[1], "%s: devolvió %r" % (paso, nuevo)
                        modelo[nuevo] = modelo[act]
                elif a[0] in ("largo", "ancho"):
                    t = t_largo if a[0] == "largo" else t_ancho
                    c.configure(doc, t, float(a[1]), a[2])
                    for n in (modelo if a[2] == "all" else [act]):
                        el, ea = modelo[n]
                        modelo[n] = (float(a[1]), ea) if a[0] == "largo" else (el, float(a[1]))
                elif a[0] == "activar":
                    c.activate(doc, nombres[a[1] % len(nombres)])
                elif a[0] == "renombrar":
                    viejo = nombres[a[1] % len(nombres)]
                    nuevo = a[2]
                    if nuevo in modelo and nuevo != viejo:
                        try:
                            c.rename(doc, viejo, nuevo)
                        except ValueError:
                            pass
                        else:
                            raise AssertionError("%s: dejó renombrar %r a un nombre que ya existe" % (paso, viejo))
                    else:
                        c.rename(doc, viejo, nuevo)
                        modelo[nuevo] = modelo.pop(viejo)
                elif a[0] == "eliminar":
                    n = nombres[a[1] % len(nombres)]
                    if n == act:
                        try:
                            c.delete(doc, n)
                        except ValueError:
                            pass
                        else:
                            raise AssertionError("%s: dejó eliminar la activa" % paso)
                    else:
                        c.delete(doc, n)
                        modelo.pop(n)
                doc.recompute()
                _comprobar(doc, modelo, c, paso)
            # cada configuración tiene sus medidas
            for n in list(modelo):
                c.activate(doc, n)
                doc.recompute()
                _comprobar(doc, modelo, c, "activar %r al final" % n)
            # guardar, cerrar, abrir
            activa = c.active(doc)
            ruta = os.path.join(carpeta, "conf.FCStd")
            doc.saveAs(ruta)
            FreeCAD.closeDocument(doc.Name)
            doc = FreeCAD.openDocument(ruta)
            doc.recompute()
            assert c.active(doc) == activa, "al abrir la activa es %r y era %r" % (c.active(doc), activa)
            _comprobar(doc, modelo, c, "al abrir")
            for n in list(modelo):
                c.activate(doc, n)
                doc.recompute()
                _comprobar(doc, modelo, c, "al abrir, activar %r" % n)
            malos = [o.Name for o in doc.Objects if "Invalid" in o.State]
            assert not malos, "objetos con error: %s" % malos
            comprobado()
        finally:
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
    f.correr("seguidilla", seguidilla, "#51")  # error registrado: Issue #51

    @cfg
    @given(nombre=st.sampled_from(["", "   ", "Predeterminado", "Otra"]))
    def nombre_malo(nombre):
        doc, body, sk, pad = _pieza()
        try:
            c.ensure(doc)
            c.add(doc, "Otra")
            c.activate(doc, "Predeterminado")
            doc.recompute()
            antes = (c.names(doc), c.active(doc))
            pruebas = [("agregar", lambda: c.add(doc, nombre), True)]
            # renombrar a sí mismo puede ser "no hacer nada"; a vacío o a otra que existe, no
            pruebas.append(("renombrar", lambda: c.rename(doc, "Predeterminado", nombre),
                            nombre != "Predeterminado"))
            for que, fn, debe_rechazar in pruebas:
                try:
                    fn()
                except ValueError:
                    pass
                else:
                    if debe_rechazar:
                        raise AssertionError("%s con el nombre %r no lo rechazó: %r"
                                             % (que, nombre, c.names(doc)))
                assert (c.names(doc), c.active(doc)) == antes, ("%s %r cambió algo: %r -> %r"
                                                                % (que, nombre, antes,
                                                                   (c.names(doc), c.active(doc))))
            comprobado()
        finally:
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
    f.correr("nombre_malo", nombre_malo)

    @cfg
    @given(cual=st.integers(0, 2), cuantas=st.integers(2, 4))
    def suprimir_en_una(cual, cuantas):
        doc, body, sk, pad = _pieza()
        try:
            # una segunda operación (suprimir la única no vacía el Cuerpo en FreeCAD, ni siquiera a mano)
            caja = body.newObject("PartDesign::AdditiveBox", "Caja")
            caja.Length, caja.Width, caja.Height = 10.0, ALTO, 3.0
            caja.Placement.Base = V(0, 0, 7.0)
            doc.recompute()
            c.ensure(doc)
            for i in range(cuantas - 1):
                c.add(doc, "C%d" % i)
            nombres = c.names(doc)
            elegida = nombres[cual % len(nombres)]
            c.activate(doc, elegida)
            doc.recompute()
            c.suppress(caja, "this")
            doc.recompute()
            for n in nombres:
                c.activate(doc, n)
                doc.recompute()
                sup = bool(caja.Suppressed)
                assert sup == (n == elegida), ("suprimido en %r: en %r Suppressed=%r" % (elegida, n, sup))
                v = body.Shape.Volume
                esperado = 350.0 if n == elegida else 500.0
                assert cerca(v, esperado), "en %r el volumen es %r y debería ser %r" % (n, v, esperado)
            comprobado()
        finally:
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
    f.correr("suprimir_en_una", suprimir_en_una)

    @cfg
    @given(largo=st.integers(1, 80))
    def deshacer_agregar(largo):
        doc, body, sk, pad = _pieza()
        try:
            c.ensure(doc)
            doc.recompute()
            antes = (c.names(doc), c.active(doc), body.Shape.Volume)
            doc.openTransaction("Agregar configuración")
            c.add(doc, "Nueva")
            c.configure(doc, ("prop", pad, "Length"), float(largo), "this")
            doc.recompute()
            doc.commitTransaction()
            assert cerca(body.Shape.Volume, largo * 50.0)
            doc.undo()
            doc.recompute()
            despues = (c.names(doc), c.active(doc), body.Shape.Volume)
            assert despues[0] == antes[0] and despues[1] == antes[1] and cerca(despues[2], antes[2]), \
                "Deshacer: %r, antes %r" % (despues, antes)
            doc.redo()
            doc.recompute()
            assert c.active(doc) == "Nueva" and cerca(body.Shape.Volume, largo * 50.0), \
                "Rehacer: %r %r" % (c.active(doc), body.Shape.Volume)
            comprobado()
        finally:
            for d in list(FreeCAD.listDocuments()):
                FreeCAD.closeDocument(d)
    f.correr("deshacer_agregar", deshacer_agregar, "#50")  # error registrado: Issue #50

    @cfg
    @given(n=st.integers(1, 20000))
    def columnas(n):
        def inversa(texto):
            r = 0
            for ch in texto:
                r = r * 26 + (ord(ch) - 64)
            return r
        t = c.col_letter(n)
        assert re.fullmatch(r"[A-Z]+", t) and inversa(t) == n, "col_letter(%d) = %r" % (n, t)
        comprobado()
    f.correr("columnas", columnas)

    @cfg
    @given(texto=st.text(max_size=20))
    def alias(texto):
        a = c.clean_alias(texto)
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", a), "clean_alias(%r) = %r" % (texto, a)
        comprobado()
    f.correr("alias", alias)

    f.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
