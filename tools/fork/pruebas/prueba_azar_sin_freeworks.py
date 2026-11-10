# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Pregunta 4 de las 7 (paso 7), sin ventana: lo que arma FreeWorks se abre SIN FreeWorks. Se arma
en un archivo, por las funciones públicas, un poco de todo: marco soldado con esquinas a tope y a
inglete, cartela y tapa de extremo; configuraciones con una medida configurada y una operación
suprimida en una; ecuaciones (variables y una ecuación sobre una cota); sólido espejado; material
asignado; dato de chapa en un Cuerpo. Se guarda y:
- el archivo no guarda objetos de Python de FreeWorks (`module="swui..."` en Document.xml): sin el
  addon, nada queda roto;
- se abre de nuevo: todo sin errores y cada sólido con el mismo volumen.
(Que no quede "modificado" al abrir necesita la ventana: lo controla la regla "guardar" de los paneles.)"""
TIPO = "azar"

import os  # noqa: E402
import re  # noqa: E402
import zipfile  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import cerca  # noqa: E402
from comun import croquis_rectangulo  # noqa: E402

V = FreeCAD.Vector


def _paso(nombre, fn, hechos, saltados):
    try:
        fn()
        hechos.append(nombre)
    except Exception as exc:
        saltados.append("%s (%s: %s)" % (nombre, type(exc).__name__, str(exc)[:120]))


def prueba():
    from swui.fork import configurations as cf
    from swui.fork import equations as eq
    from swui.fork import material as mt
    from swui.fork import mirror_bodies as mb
    from swui.fork import sheet_metal as sm
    from swui.fork import weldments as w
    doc = FreeCAD.newDocument("SinFreeWorks")
    hechos, saltados = [], []
    estado = {}

    def soldada():
        sk, _c = croquis_rectangulo(doc, 600, 400)
        size = [s for s, _d in w.sizes("Caño cuadrado") if s.startswith("40x40x2")][0]
        cuerpos = w.create_members(doc, [(sk, "Edge%d" % (i + 1)) for i in range(4)], "Caño cuadrado", size)
        esquinas = w.find_corners(cuerpos)
        w.apply_corner(esquinas[0], "tope")
        for c in esquinas[1:]:
            w.apply_corner(c, "inglete")
        doc.recompute()
        w.gusset(cuerpos[0], cuerpos[1])
        doc.recompute()
        sk2, _c2 = croquis_rectangulo(doc, 300, 100, nombre="Suelto")
        suelto = w.create_members(doc, [(sk2, "Edge1")], "Caño cuadrado", size)
        w.end_cap(suelto[0], 0)
        doc.recompute()

    def pieza():
        body = doc.addObject("PartDesign::Body", "Pieza")
        caja = body.newObject("PartDesign::AdditiveBox", "Caja")
        caja.Length, caja.Width, caja.Height = 50, 30, 10
        hueco = body.newObject("PartDesign::SubtractiveCylinder", "Agujero")
        hueco.Radius, hueco.Height = 3, 10
        hueco.Placement.Base = V(10, 10, 0)
        doc.recompute()
        estado.update(body=body, caja=caja, hueco=hueco)

    def configuraciones():
        cf.ensure(doc, estado["body"])
        cf.add(doc, "Larga")
        cf.configure(doc, ("prop", estado["caja"], "Length"), 80.0, scope="this")
        cf.suppress(estado["hueco"], scope="this")
        doc.recompute()

    def ecuaciones():
        m = eq.Model(doc)
        m.set_variable("Ancho", "35")
        nombres = eq.feature_dim_names(estado["caja"].TypeId, estado["caja"].PropertiesList)
        m.set_equation("%s@%s" % (nombres.get("Width", "Width"), estado["caja"].Label), '= "Ancho"')
        doc.recompute()

    def espejo():
        plano = [f for f in estado["body"].Origin.OriginFeatures if f.Role == "YZ_Plane"][0]
        mb.make_mirror_body(estado["body"], (plano, ""))
        doc.recompute()

    def material():
        todos = mt.all_materials()
        info = (todos[0] if isinstance(todos[0], dict) else mt.info_of(todos[0])) if todos else None
        if info is None:
            raise RuntimeError("no hay materiales en la biblioteca")
        mt.assign([estado["body"]], info)
        doc.recompute()

    def chapa():
        b = doc.addObject("PartDesign::Body", "Chapa")
        c = b.newObject("PartDesign::AdditiveBox", "Plancha")
        c.Length, c.Width, c.Height = 100, 60, 2
        doc.recompute()
        sm.write_spec(b, {"thickness": 2.0, "radius": 2.0, "k": 0.5})
        doc.recompute()

    for nombre, fn in (("soldada", soldada), ("pieza", pieza), ("configuraciones", configuraciones),
                       ("ecuaciones", ecuaciones), ("espejo", espejo), ("material", material), ("chapa", chapa)):
        _paso(nombre, fn, hechos, saltados)
    traza("  armado: %s" % ", ".join(hechos))
    # todas: si una parte deja de poder armarse es un error (y justo las que más podrían guardar
    # objetos de FreeWorks, soldadas y configuraciones, no pueden faltar sin que se note)
    assert not saltados, "no se pudo armar: %s" % "; ".join(saltados)

    malos = [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
    assert not malos, "antes de guardar ya hay objetos con error: %s" % malos
    vol = {o.Name: o.Shape.Volume for o in doc.Objects if o.TypeId == "PartDesign::Body" and o.Shape.Solids}
    ruta = os.path.join(carpeta_temporal(), "sin_freeworks.FCStd")
    doc.saveAs(ruta)
    FreeCAD.closeDocument(doc.Name)
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("Document.xml").decode("utf-8", "replace")
        if "GuiDocument.xml" in z.namelist():  # (sin ventana no se guarda, pero por si acaso)
            xml += z.read("GuiDocument.xml").decode("utf-8", "replace")
    propios = sorted(set(re.findall(r'module="(swui[^"]*)"', xml)))
    assert not propios, "el archivo necesita FreeWorks para abrir: guarda objetos de %s" % propios
    doc = FreeCAD.openDocument(ruta)
    try:
        doc.recompute()
        malos = [o.Name for o in doc.Objects if "Invalid" in o.State or "Error" in o.State]
        assert not malos, "al abrir quedaron con error: %s" % malos
        for n, v in vol.items():
            o = doc.getObject(n)
            assert o is not None and cerca(o.Shape.Volume, v, rel=1e-6, absoluto=1e-3), \
                "%s cambió al abrir (%.3f, era %.3f)" % (n, o.Shape.Volume if o else -1, v)
        traza("  %d sólidos iguales al abrir; el archivo no guarda nada de FreeWorks" % len(vol))
    finally:
        FreeCAD.closeDocument(doc.Name)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
