# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """#104 (18/11): insertar en un ensamblaje una pieza de varios cuerpos (una soldadura) deja su contenedor GUARDADO
en el archivo de la pieza (antes quedaba solo en memoria: FreeCAD tiene la pieza de solo lectura durante la
inserción). Guardar, cerrar todo y reabrir el ensamblaje: el componente encuentra su pieza entera. Deshacer la
inserción saca el componente; insertar la misma pieza otra vez usa el mismo contenedor (no arma otro). Revisión: si
el usuario tenía la pieza abierta con cambios sin guardar, insertarla NO la guarda sola (queda modificada)."""
TIPO = "completa"
import zipfile  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal, cerrar_todo, traza  # noqa: E402
from azar_comun import bombear  # noqa: E402


def _partes_en_archivo(ruta):
    with zipfile.ZipFile(ruta) as z:
        return z.read("Document.xml").count(b'type="App::Part"')


def prueba():
    import FreeCADGui
    import casos_relacion as cr
    import piezas_editar as pe
    from swui import assembly_drop
    c = carpeta_temporal()
    marco = pe.soldadura(c, "Marco")
    assert _partes_en_archivo(marco) == 0

    traza("insertar")
    doc, asm, (comp,) = cr._ensamblaje([marco])
    bombear(800)
    assert comp.LinkedObject is not None and comp.LinkedObject.TypeId == "App::Part", comp.LinkedObject
    assert _partes_en_archivo(marco) == 1, "el contenedor no quedó guardado en la pieza"
    m = comp.LinkedObject.Document
    traza("  pieza: modificada %s, por recalcular %s" % (FreeCADGui.getDocument(m.Name).Modified,
                                                        [o.Name for o in m.Objects if "Touched" in o.State][:6]))
    assert not FreeCADGui.getDocument(m.Name).Modified, "la pieza quedó modificada después de guardarla"
    ruta = doc.FileName
    doc.save()
    yield 100

    traza("cerrar todo y reabrir")
    cerrar_todo()
    bombear(500)
    doc = FreeCAD.openDocument(ruta)
    bombear(1500)
    assert not FreeCADGui.getDocument(doc.Name).Modified, "el ensamblaje abrió modificado"
    links = [o for o in doc.Objects if o.TypeId == "App::Link"]
    assert len(links) == 1 and links[0].LinkedObject is not None, "el componente quedó sin destino al reabrir"
    import Part
    s = Part.getShape(links[0])
    assert len(s.Solids) == 4 and s.isValid(), "el componente no trae los 4 caños: %d" % len(s.Solids)
    yield 100

    traza("insertar la misma pieza otra vez, y deshacer")
    asm = [o for o in doc.Objects if o.TypeId == "Assembly::AssemblyObject"][0]
    nuevos = assembly_drop.insert_files(asm, [marco])
    bombear(800)
    assert len(nuevos) == 1 and nuevos[0].LinkedObject is links[0].LinkedObject, "armó otro contenedor"
    assert _partes_en_archivo(marco) == 1, "la pieza tiene dos contenedores"
    FreeCADGui.runCommand("Std_Undo")
    bombear(800)
    assert len([o for o in doc.Objects if o.TypeId == "App::Link"]) == 1, "deshacer no sacó el componente"
    cerrar_todo()
    yield 100

    traza("pieza abierta con un cambio sin guardar: no se guarda sola")
    otra = pe.soldadura(c, "Otra")
    p = FreeCAD.openDocument(otra)
    bombear(500)
    esq = p.getObject("Esqueleto")
    ancho = [i for i, k in enumerate(esq.Constraints) if k.Type == "DistanceX"][0]
    esq.setDatum(ancho, FreeCAD.Units.Quantity("650 mm"))
    p.recompute()
    assert FreeCADGui.getDocument(p.Name).Modified
    with zipfile.ZipFile(otra) as z:
        antes = z.read("Document.xml")
    # el ensamblaje guardado ANTES de insertar (guardar un ensamblaje guarda sus piezas cambiadas, como SW: eso
    # va al guardar el ensamblaje, no al insertar)
    doc2 = FreeCAD.newDocument("Conjunto2")
    asm2 = doc2.addObject("Assembly::AssemblyObject", "Assembly")
    asm2.Type = "Assembly"
    asm2.newObject("Assembly::JointGroup", "Joints")
    doc2.recompute()
    doc2.saveAs(c + "/Conjunto2.FCStd")
    bombear(800)
    (comp2,) = assembly_drop.insert_files(asm2, [otra])
    bombear(800)
    assert comp2.LinkedObject is not None and comp2.LinkedObject.TypeId == "App::Part"
    with zipfile.ZipFile(otra) as z:
        assert z.read("Document.xml") == antes, "guardó sola la pieza que tenía cambios sin guardar"
    assert FreeCADGui.getDocument(p.Name).Modified, "la pieza con cambios quedó como no modificada"
    cerrar_todo()
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
