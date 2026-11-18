# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Herramientas del clic derecho como SW (etapa C, 15/11), con la ventana: Contraer operaciones deja
abiertos solo los Cuerpos/ensamblaje; Invertir la selección elige los otros componentes; Aislar muestra
solo eso sin dejar el documento modificado, Salir de aislar vuelve a mostrar exactamente lo de antes, y
guardar estando aislado no deja nada oculto en el archivo; Cambiar de nombre y Propiedades del componente
se deshacen en un paso; Padre/Hijo lista la relación de posición; Material abre sobre la pieza;
Seleccionar tangencia elige la cara y sus tangentes; Exportar a DXF escribe la cara 1:1; Abrir pieza en
posición abre la pieza mirada como en el ensamblaje."""
TIPO = "completa"
import os  # noqa: E402
import zipfile  # noqa: E402

import FreeCAD  # noqa: E402
import Part  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector


def _visibilidad_en_archivo(ruta, nombre):
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("Document.xml").decode("utf-8")
    i = xml.index('<Object name="%s"' % nombre, xml.index("<ObjectData"))
    trozo = xml[i:xml.index("</Object>", i)]
    k = trozo.index('name="Visibility"')
    return 'value="true"' in trozo[k:k + 200]


def _sel_comps(asm):
    import FreeCADGui
    out = []
    for s in FreeCADGui.Selection.getSelectionEx("", 0):
        for sub in s.SubElementNames:
            out.append(sub.split(".")[0])
    return sorted(out)


def prueba():
    import FreeCADGui
    import casos_relacion as cr
    from swui.fork import context_tools as ct

    carpeta = carpeta_temporal()
    rutas = [cr._pieza(carpeta, "Placa", 100, 60, 10), cr._pieza(carpeta, "Bloque", 30, 20, 15),
             cr._pieza(carpeta, "Suelto", 20, 20, 20)]
    doc, asm, (placa, bloque, suelto) = cr._ensamblaje(rutas)
    bloque.Placement.Base = V(120, 0, 0)
    suelto.Placement = FreeCAD.Placement(V(0, 100, 0), FreeCAD.Rotation(V(0, 0, 1), 90))
    r, _j = cr._relacionar(doc, asm, "coincident", [(placa, "Face6"), (bloque, "Face5")])
    doc.recompute()
    doc.save()
    gdoc = FreeCADGui.getDocument(doc.Name)
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    bombear(500)
    gdoc.Modified = False

    # Invertir la selección
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(doc.Name, asm.Name, bloque.Name + ".")
    otros = ct.invert_selection()
    assert sorted(o.Name for o in otros) == sorted([placa.Name, suelto.Name]), [o.Name for o in otros]
    assert _sel_comps(asm) == sorted([placa.Name, suelto.Name]), _sel_comps(asm)

    # Aislar el bloque: los otros ocultos, sin "modificado"; Salir vuelve todo
    suelto.Visibility = False  # estaba oculto antes: tiene que seguir oculto al salir
    gdoc.Modified = False
    ct.isolate(bloque)
    bombear(200)
    assert not placa.Visibility and bloque.Visibility, "aislar no ocultó lo demás"
    assert not gdoc.Modified, "aislar dejó el ensamblaje modificado"
    assert ct.is_isolated(doc)
    # guardar aislado: el archivo queda con todo como antes de aislar, y sigue aislado
    ruta = doc.FileName
    doc.save()
    bombear(300)
    assert _visibilidad_en_archivo(ruta, placa.Name), "guardó la placa oculta por aislar"
    assert not placa.Visibility and ct.is_isolated(doc), "después de guardar dejó de estar aislado"
    assert not gdoc.Modified
    ct.exit_isolate(doc)
    assert placa.Visibility and bloque.Visibility and not suelto.Visibility, \
        "salir de aislar no volvió a como estaba (%s %s %s)" % (placa.Visibility, bloque.Visibility, suelto.Visibility)
    assert not gdoc.Modified, "salir de aislar dejó el ensamblaje modificado"
    suelto.Visibility = True

    # Aislar dos veces seguidas: la segunda vuelve primero a como estaba; Salir deja todo a la vista
    ct.isolate(bloque)
    ct.isolate(placa)
    assert placa.Visibility and not bloque.Visibility and not suelto.Visibility, "aislar dos veces"
    ct.exit_isolate(doc)
    assert placa.Visibility and bloque.Visibility and suelto.Visibility, "salir después de aislar dos veces"

    # "Guardar una copia" estando aislado y con cambios sin guardar: sigue "modificado" (revisión 15/11)
    bloque.Label = bloque.Label + " "  # un cambio de verdad
    bloque.Label = bloque.Label.strip()
    gdoc.Modified = True
    ct.isolate(bloque)
    copia = os.path.join(carpeta_temporal(), "Copia.FCStd")
    doc.saveCopy(copia)
    bombear(200)
    assert gdoc.Modified, "Guardar una copia aislado dejó el documento como no modificado"
    assert not placa.Visibility and ct.is_isolated(doc)

    # Ctrl+Z después de aislar no desarma el aislado a medias
    doc.openTransaction("Algo")
    bloque.Label = "Algo"
    doc.commitTransaction()
    doc.undo()
    assert not placa.Visibility and ct.is_isolated(doc), "Ctrl+Z desarmó el aislado"
    ct.exit_isolate(doc)
    assert placa.Visibility and bloque.Visibility and suelto.Visibility
    yield 100

    # Cambiar de nombre: un paso de deshacer
    nombre = bloque.Label
    assert ct.rename(bloque, "Taco raro") and bloque.Label == "Taco raro"
    assert not ct.rename(bloque, "   "), "aceptó un nombre vacío"
    doc.undo()
    assert bloque.Label == nombre, "Ctrl+Z no volvió el nombre: %s" % bloque.Label

    # Propiedades del componente: suprimir y nombre, y deshacer
    info = ct.component_info(bloque)
    assert info["name"] == nombre and info["file"].endswith("Bloque.FCStd") and not info["suppressed"], info
    ct.apply_component(bloque, name="Otro nombre", suppressed=True)
    assert bloque.Label == "Otro nombre" and ct.component_info(bloque)["suppressed"], ct.component_info(bloque)
    doc.undo()
    doc.recompute()
    assert bloque.Label == nombre and not ct.component_info(bloque)["suppressed"], \
        "Ctrl+Z no deshizo Propiedades del componente en un paso: %s" % ct.component_info(bloque)

    # Padre/Hijo del componente
    relaciones, _usan = ct.component_relatives(bloque)
    assert len(relaciones) == 1, "Padre/Hijo: %s" % [m.Label for m in relaciones]
    dlg = ct.show_relatives(bloque)
    bombear(200)
    dlg.close()

    # Material: abre sobre la pieza del componente
    d = ct.component_material(bloque)
    bombear(300)
    assert d.doc is bloque.LinkedObject.Document, "Material no abrió sobre la pieza"
    d.close()
    yield 100

    # Contraer operaciones (no cambia el documento)
    gdoc.Modified = False
    ct.collapse_tree(doc)
    bombear(200)
    assert not gdoc.Modified, "contraer dejó el documento modificado"

    # Abrir pieza en posición: el suelto está girado 90° en Z. Medido aparte, sin la fórmula: la
    # dirección de mirada en la pieza, girada como el componente, es la del ensamblaje
    view = FreeCADGui.ActiveDocument.ActiveView
    mira_conjunto = view.getViewDirection()
    pdoc = ct.open_in_position(suelto)
    bombear(500)
    assert pdoc is suelto.LinkedObject.Document, "no abrió la pieza del componente"
    mira_pieza = FreeCADGui.ActiveDocument.ActiveView.getViewDirection()
    girada = FreeCAD.Rotation(V(0, 0, 1), 90).multVec(mira_pieza)
    assert (girada - mira_conjunto).Length < 1e-3, \
        "la pieza no quedó mirada como en el ensamblaje: %s / %s" % (girada, mira_conjunto)
    assert (mira_pieza - mira_conjunto).Length > 0.1, "la prueba no distingue: el giro no cambia la mirada"
    yield 100

    # Pieza con redondeos: Seleccionar tangencia y Exportar cara a DXF
    pz = FreeCAD.newDocument("Tangencia")
    body = pz.addObject("PartDesign::Body", "Body")
    caja = body.newObject("PartDesign::AdditiveBox", "Caja")
    caja.Length, caja.Width, caja.Height = 40, 30, 10
    pz.recompute()
    aristas = ["Edge%d" % (i + 1) for i, e in enumerate(caja.Shape.Edges)
               if all(abs(v.Point.z - 10) < 1e-6 for v in e.Vertexes)]
    red = body.newObject("PartDesign::Fillet", "Redondeo")
    red.Base = (caja, aristas)
    red.Radius = 3
    pz.recompute()
    tapa = [i for i, f in enumerate(red.Shape.Faces)
            if abs(f.CenterOfMass.z - 10) < 1e-6 and f.Area > 300][0] + 1
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(pz.Name, body.Name, "%s.Face%d" % (red.Name, tapa))
    caras = ct.select_tangent()
    assert len(caras) == 9, "Seleccionar tangencia: %s" % caras
    n = sum(len(s.SubElementNames) for s in FreeCADGui.Selection.getSelectionEx("", 0))
    assert n == 9, "quedaron elegidas %d caras" % n
    # DXF de la cara de abajo (plana, con el contorno redondeado arriba no la toca: es un rectángulo)
    abajo = [f for f in red.Shape.Faces if abs(f.CenterOfMass.z) < 1e-6][0]
    ruta = os.path.join(carpeta_temporal(), "cara.dxf")
    ct.export_face_dxf(abajo, ruta)
    texto = open(ruta, encoding="ascii").read()
    assert texto.count("\nLINE\n") == 4 and "EOF" in texto, "DXF de la cara: %s" % texto[-300:]
    try:
        ct.export_face_dxf([f for f in red.Shape.Faces if type(f.Surface).__name__ == "Cylinder"][0], ruta)
        assert False, "exportó una cara curva"
    except ValueError:
        pass
    # Cara del costado y cara de abajo, con un agujero corrido: 1:1 y el agujero a su distancia
    bloque2 = Part.makeBox(50, 20, 30).cut(Part.makeCylinder(4, 20, V(10, 0, 8), V(0, 1, 0))).cut(
        Part.makeCylinder(3, 30, V(40, 6, 0), V(0, 0, 1)))
    frente = [f for f in bloque2.Faces if abs(f.CenterOfMass.y) < 1e-6][0]
    abajo2 = [f for f in bloque2.Faces if abs(f.CenterOfMass.z) < 1e-6][0]
    for nombre, cara, lados, distancias in (("frente", frente, (50, 30), (10, 8)), ("abajo", abajo2, (50, 20), (10, 6))):
        ents = ct.face_entities(cara)
        lineas = [e for e in ents if e[0] == "LINE"]
        circ = [e for e in ents if e[0] == "CIRCLE"]
        xs = [v for e in lineas for v in (e[2], e[4])]
        ys = [v for e in lineas for v in (e[3], e[5])]
        assert abs(min(xs)) < 1e-6 and abs(min(ys)) < 1e-6, "%s: no arranca en 0,0" % nombre
        medidas = sorted((round(max(xs), 3), round(max(ys), 3)))
        assert medidas == sorted(lados), "%s: no quedó 1:1: %s" % (nombre, medidas)
        assert len(circ) == 1, "%s: falta el agujero" % nombre
        cx, cy = circ[0][2], circ[0][3]
        cerca = sorted((round(min(cx, max(xs) - cx), 3), round(min(cy, max(ys) - cy), 3)))
        assert cerca == sorted(distancias), "%s: el agujero no quedó en su lugar: %s" % (nombre, cerca)
    FreeCAD.closeDocument(pz.Name)

    # Cerrar el documento estando aislado: sin errores y sin barra colgada
    ct.isolate(bloque)
    nombre_doc = doc.Name
    FreeCAD.closeDocument(nombre_doc)
    bombear(300)
    assert nombre_doc not in ct._isolated, "quedó anotado como aislado un documento cerrado"
    assert not [n for n in ct._bars], "quedó la barra Salir de aislar del documento cerrado: %s" % list(ct._bars)
    yield 100


from _base import ejecutar  # noqa: E402
ejecutar(globals())
