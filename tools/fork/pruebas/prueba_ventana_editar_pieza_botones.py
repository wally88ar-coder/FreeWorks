# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Editar pieza = pieza (plan del 16/11, objetivo del usuario: "TODO es TODO"). Cada botón de las pestañas de
la pieza (Operaciones, Croquis, Evaluar, Chapa, Piezas soldadas), en la pieza sola y editando esa pieza dentro
de un ensamblaje, con su pieza de prueba (bloque, chapa, marco soldado, pieza con ecuaciones) y selecciones que
tengan sentido; si abre un panel, se Acepta como viene. Se compara qué panel abre, qué queda en edición, qué
crea (y en qué documento), si queda bien, avisos y errores, y si se sigue editando. Lo distinto es falla,
salvo lo anotado en EXCEPCIONES con su motivo. Los del croquis, dentro de un croquis abierto."""
TIPO = "completa"
TIEMPO_MAXIMO = 4200
import json  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector
SALIDA = os.environ.get("FW_SONDEO_OUT", "")
SOLO_RELEVAR = os.environ.get("FW_SONDEO_SOLO", "") == "1"  # solo anota, no falla (para armar la tabla)
NO_PROBAR = ("Sketcher_LeaveSketch",
             "SWUI_SMExportDXF", "SWUI_ExportFaceDXF")  # cuadro de Windows para guardar: colgaría la prueba
PIEZA_DE = {"Operaciones": "bloque", "Croquis": "bloque", "Evaluar": "ecuaciones", "Chapa": "chapa",
            "Piezas soldadas": "marco"}
# (pestaña, comando, elección) -> motivo: diferencias aceptadas a propósito (vacío = ninguna)
_LISTA = ("sin nada elegido: en la pieza sola FreeCAD muestra su lista de croquis (la nativa no encuentra el Cuerpo "
          "a través del componente); editando, FreeWorks muestra la suya (mismo resultado al elegir un croquis)")
_ERROR = "con una arista de perfil los dos dan error (perfil abierto); solo cambia el texto del error de FreeCAD"
_CUERPO = ("con una cara o arista elegida, en la pieza sola FreeCAD da error (un Cuerpo no se puede basar en una "
           "operación) y crea el Cuerpo vacío igual; editando, sin ese aviso (decidido 17/11)")
EXCEPCIONES = dict(
    [(("Operaciones", c, "nada"), _LISTA) for c in (
        "PartDesign_AdditivePipe", "PartDesign_AdditiveLoft", "PartDesign_AdditiveHelix",
        "PartDesign_SubtractivePipe", "PartDesign_SubtractiveLoft", "PartDesign_SubtractiveHelix")]
    + [(("Operaciones", c, "arista"), _ERROR) for c in ("PartDesign_Revolution", "PartDesign_Groove")]
    + [(("Operaciones", "PartDesign_Body", s), _CUERPO) for s in ("cara", "arista")])


def _comandos():
    """(pestaña, comando) de la cinta tal como quedó armada (con lo que agrega FreeWorks)."""
    from swui import ribbon_layout as rl
    out = []

    def walk(items, tab):
        for it in items:
            if isinstance(it, (list, tuple)) and it and isinstance(it[0], str) and it[0][:1].isupper() \
                    and "_" in it[0]:
                if it[0] not in NO_PROBAR and (tab, it[0]) not in out:
                    out.append((tab, it[0]))
            elif isinstance(it, dict):
                for k in ("stack", "flyout", "toggle", "items", "variants"):
                    if k in it:
                        walk(it[k], tab)
            elif isinstance(it, (list, tuple)):
                walk(it, tab)
    nombres = {rl.FEATURES[0]: "Operaciones", rl.SKIZZE[0]: "Croquis", rl.EVALUIEREN[0]: "Evaluar",
               "Chapa": "Chapa", "Piezas soldadas": "Piezas soldadas"}
    solo = [t for t in os.environ.get("FW_SONDEO_TABS", "").split(",") if t]
    for title, groups in rl.TABS:
        tab = nombres.get(title)
        if tab and (not solo or tab in solo):
            walk(groups, tab)
    solo_cmd = [c for c in os.environ.get("FW_SONDEO_CMDS", "").split(",") if c]
    return [(t, c) for t, c in out if not solo_cmd or c in solo_cmd]


def _en_croquis(tab, cmd):
    return tab == "Croquis" and cmd not in ("PartDesign_NewSketch", "SWUI_Sketch3D")


# --- piezas y selecciones -----------------------------------------------------------------------------


def _tip(doc, nombre="Body"):
    b = doc.getObject(nombre)
    return b.Tip if b is not None else None


def _cara_mayor(obj, horizontal=True):
    caras = obj.Shape.Faces
    cand = [i for i, f in enumerate(caras) if f.Surface.__class__.__name__ == "Plane"
            and (not horizontal or abs(f.normalAt(0, 0).z) > 0.99)]
    i = max(cand, key=lambda k: (round(caras[k].Area, 3), caras[k].BoundBox.ZMax))
    return "Face%d" % (i + 1)


def _arista_recta(obj, z=None):
    for i, e in enumerate(obj.Shape.Edges):
        if e.Curve.__class__.__name__ == "Line" and e.Length > 10 and (z is None or abs(e.BoundBox.ZMax - z) < 1e-6
                                                                       and abs(e.BoundBox.ZMin - z) < 1e-6):
            return "Edge%d" % (i + 1)
    return "Edge1"


def _selecciones(pieza, pdoc):
    """{nombre: [(objeto, elemento)]} con sentido para la pieza de prueba."""
    if pieza in ("bloque", "ecuaciones"):
        ext = pdoc.getObject("Extruir")
        return {"nada": [], "cara": [(ext, "Face6")], "arista": [(ext, _arista_recta(ext, 20))]}
    if pieza == "chapa":
        tip = _tip(pdoc)
        return {"nada": [], "cara": [(tip, _cara_mayor(tip))], "arista": [(tip, _arista_recta(tip, 0))]}
    if pieza == "marco":
        esq = pdoc.getObject("Esqueleto")
        miembro = [o for o in pdoc.Objects if o.TypeId == "PartDesign::Body"][0]
        return {"nada": [], "arista esqueleto": [(esq, "Edge1"), (esq, "Edge2")],
                "cara miembro": [(miembro.Tip, _cara_mayor(miembro.Tip, horizontal=False))]}
    return {"nada": []}


def _fabricar(pieza, carpeta):
    import piezas_editar as pe
    f = {"bloque": pe.bloque, "chapa": pe.chapa, "marco": pe.soldadura, "ecuaciones": pe.ecuaciones}[pieza]
    ruta = f(carpeta)
    if pieza == "marco":  # la soldadura entra al ensamblaje por su contenedor Parte (part_container)
        d = FreeCAD.openDocument(ruta, True)
        from swui.fork import part_container as pc
        if pc.needs_container(d):
            pc.wrap(d)
        FreeCAD.closeDocument(d.Name)
    return ruta


# --- lo que se ve ---------------------------------------------------------------------------------


def _paneles():
    import FreeCADGui
    from swui.compat import QtWidgets
    out = []
    for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QWidget):
        if w.metaObject().className() == "Gui::TaskView::TaskBox" and w.isVisible():
            t = w.windowTitle()
            if not t:
                labs = [x.text() for x in w.findChildren(QtWidgets.QLabel) if x.isVisible() and x.text()]
                t = labs[0] if labs else "?"
            out.append(t[:60])
    return sorted(set(out))


class _Cerrador:
    """Cierra los cuadros modales (avisos, preguntas) y anota qué decían."""

    def __init__(self):
        from swui.compat import QtCore
        self.textos = []
        self.t = QtCore.QTimer()
        self.t.setInterval(250)
        self.t.timeout.connect(self.mirar)
        self.t.start()

    def mirar(self):
        import FreeCADGui
        from swui.compat import QtWidgets
        main = FreeCADGui.getMainWindow()
        abiertos = [QtWidgets.QApplication.activeModalWidget()] + [
            w for w in QtWidgets.QApplication.topLevelWidgets()
            if isinstance(w, (QtWidgets.QMessageBox, QtWidgets.QFileDialog, QtWidgets.QInputDialog))]
        for d in abiertos:
            if d is None or d is main or not d.isVisible():
                continue
            txt = d.windowTitle()
            if isinstance(d, QtWidgets.QMessageBox):
                txt += ": " + d.text()
            self.textos.append(txt[:120])
            d.reject()

    def parar(self):
        self.t.stop()
        self.mirar()
        return self.textos


def _en_edicion(gdoc):
    vp = gdoc.getInEdit() if gdoc is not None else None
    if vp is None:
        return ""
    o = getattr(vp, "Object", None)
    if o is None:
        return ""  # el ensamblaje activo (ViewProviderAssembly): no es "algo en edición"
    return o.TypeId


def _contenedor(doc):
    """Nombres del contenedor Parte de FreeWorks y su Origen (vacío si no hay)."""
    from swui.fork import part_container as pc
    part = pc.container(doc)
    if part is None or not hasattr(part, pc.MARK):
        return set()
    out = {part.Name}
    origen = getattr(part, "Origin", None)
    if origen is not None:
        out.add(origen.Name)
        out |= {o.Name for o in origen.OutList}
    return out


def _invalidos(doc, antes):
    out = []
    for o in doc.Objects:
        try:
            if "Invalid" in str(o.State) or (hasattr(o, "isValid") and not o.isValid()):
                out.append(o.TypeId + (" (nuevo)" if o.Name not in antes else ""))
        except Exception:  # noqa: BLE001
            pass
    return sorted(out)


# --- cada prueba ----------------------------------------------------------------------------------


def _correr(ctx, tab, cmd, sel):
    import time
    t0 = time.time()
    import FreeCADGui
    from reglas_paneles import informe_largo, mensajes_nuevos, tocar
    from swui import ribbon
    pdoc, adoc, gdoc = ctx["pdoc"], ctx.get("adoc"), ctx["gdoc"]
    antes_p = set(o.Name for o in pdoc.Objects)
    ctx["deshacer"] = pdoc.UndoCount
    antes_a = set(o.Name for o in adoc.Objects) if adoc else set()
    traza("    %s %s %s %s" % (ctx["modo"], tab, cmd, sel))
    ctx["elegir"](sel)
    cuerpos = sorted(o.Name for o in pdoc.Objects if o.TypeId == "PartDesign::Body")
    desde = informe_largo()
    cerr = _Cerrador()
    excepcion = ""
    try:
        ribbon._run(cmd)
    except Exception as e:  # noqa: BLE001
        excepcion = repr(e)[:120]
    bombear(1300)
    r = {"modo": ctx["modo"], "pieza": ctx["pieza"], "pestaña": tab, "comando": cmd, "eleccion": sel,
         "panel": _paneles(), "edicion": _en_edicion(gdoc)}
    # Aceptar como viene (si hay panel y no es un croquis abierto)
    aceptado = False
    if FreeCADGui.Control.activeDialog() and not r["edicion"].startswith("Sketcher"):
        aceptado = tocar(rechazar=False)
        bombear(1800)
    modales = cerr.parar()
    # el contenedor que FreeWorks le pone a una pieza de un Cuerpo antes de crear algo fuera del Cuerpo
    # (edit_part.prepare_container) es parte de la pieza desde ahí: ni "creado" ni se borra al limpiar
    antes_p |= _contenedor(pdoc)
    r.update({
        "aceptado": aceptado, "queda_panel": bool(FreeCADGui.Control.activeDialog()),
        "nuevo_pieza": sorted(o.TypeId for o in pdoc.Objects if o.Name not in antes_p),
        "nuevo_ensamblaje": sorted(o.TypeId for o in adoc.Objects if o.Name not in antes_a) if adoc else [],
        "invalidos": _invalidos(pdoc, antes_p),
        "avisos": modales, "excepcion": excepcion, "cuerpos_antes": cuerpos,
        "errores": [m[:200] for m in mensajes_nuevos(desde)][:14],
    })
    if os.environ.get("FW_SONDEO_INFORME") and r["errores"]:
        from reglas_paneles import _report_view
        r["informe"] = _report_view().toPlainText()[desde:][:3000]
    if ctx["modo"] == "editando":
        from swui.fork import edit_part as ep
        r["sigue_editando"] = ep.editing(adoc) is ctx["comp"]
    t1 = time.time()
    _limpiar(ctx, tab, cmd, antes_p, antes_a)
    r["segundos"] = (round(t1 - t0, 1), round(time.time() - t1, 1))
    return r


def _limpiar(ctx, tab, cmd, antes_p, antes_a):
    import FreeCADGui
    from reglas_paneles import tocar
    from swui.compat import QtWidgets
    gdoc = ctx["gdoc"]
    d = QtWidgets.QApplication.activeModalWidget()
    if d is not None:
        d.reject()
    try:
        from swui.fork import sketch_entities
        if sketch_entities.active_panel() is not None:
            sketch_entities.active_panel().reject()
    except Exception:  # noqa: BLE001
        pass
    if FreeCADGui.Control.activeDialog():
        tocar(rechazar=True)
        bombear(400)
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
            bombear(200)
    en_croquis = _en_croquis(tab, cmd)
    vp = gdoc.getInEdit()
    o = getattr(vp, "Object", None)
    if o is not None and (not en_croquis or getattr(o, "Name", None) != getattr(ctx.get("croquis"), "Name", 0)):
        gdoc.resetEdit()
        bombear(300)
    FreeCADGui.Selection.clearSelection()
    if ctx["pieza"] == "marco":  # Esquinas y otras rehacen operaciones que ya estaban: borrar no alcanza
        pdoc = ctx["pdoc"]
        while pdoc.UndoCount > ctx["deshacer"]:
            pdoc.undo()
        pdoc.recompute()
    for doc, antes in ((ctx["pdoc"], antes_p), (ctx.get("adoc"), antes_a)):
        if doc is None:
            continue
        for o in reversed(list(doc.Objects)):
            if o.Name not in antes and doc.getObject(o.Name) is not None:
                try:
                    doc.removeObject(o.Name)
                except Exception:  # noqa: BLE001
                    pass
        doc.recompute()
    bombear(200)


# --- los dos modos --------------------------------------------------------------------------------


def _al_frente(doc):
    """La ventana del documento al frente (abrir un archivo no siempre la deja activa)."""
    import FreeCADGui
    from swui.compat import QtWidgets
    FreeCAD.setActiveDocument(doc.Name)
    gdoc = FreeCADGui.getDocument(doc.Name)
    vista = gdoc.mdiViewsOfType("Gui::View3DInventor")[0]
    area = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
    for sub in area.subWindowList():
        if vista.graphicsView() is not None and sub.isAncestorOf(vista.graphicsView()):
            area.setActiveSubWindow(sub)
            break
    bombear(500)
    assert FreeCADGui.ActiveDocument is not None and FreeCADGui.ActiveDocument.Document is doc, \
        "%s no quedó al frente: %s" % (doc.Name, FreeCADGui.ActiveDocument)
    vista.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    return gdoc


def _modo_pieza(pieza, ruta, comandos, resultados):
    import FreeCADGui
    from swui.fork import edit_context as ec
    pdoc = FreeCAD.openDocument(ruta)
    bombear(800)
    gdoc = _al_frente(pdoc)
    bodies = [o for o in pdoc.Objects if o.TypeId == "PartDesign::Body"]
    gdoc.activeView().setActiveObject("pdbody", bodies[-1])
    sels = _selecciones(pieza, pdoc)
    ctx = {"modo": "pieza", "pieza": pieza, "pdoc": pdoc, "gdoc": gdoc, "sels": sels}

    def elegir(sel):
        FreeCADGui.Selection.clearSelection()
        for obj, el in _selecciones(pieza, pdoc).get(sel, []):  # al momento: una prueba puede rehacer operaciones
            ec.select(obj, el, clear=False)
    ctx["elegir"] = elegir
    _recorrer(ctx, comandos, resultados, abrir_croquis=lambda: _croquis(ctx, None))
    FreeCAD.closeDocument(pdoc.Name)
    bombear(500)


def _croquis(ctx, ep_ctx):
    """Croquis abierto (con una línea) sobre la cara de arriba de la pieza, en el modo que toque."""
    import Part
    from swui.fork import edit_context as ec
    pdoc = ctx["pdoc"]
    obj, el = (ctx["sels"].get("cara") or ctx["sels"].get("cara miembro"))[0]
    if ctx["modo"] == "editando":
        sk = ec.new_sketch(obj, el)
    else:
        from swui.fork import feature_tree as ft
        body = ft.body_of(obj)
        sk = body.newObject("Sketcher::SketchObject", "SondeoCroquis")
        sk.AttachmentSupport = [(obj, [el])]
        sk.MapMode = "FlatFace"
        pdoc.recompute()
        ctx["gdoc"].setEdit(sk)
    sk.addGeometry(Part.LineSegment(V(1, 1, 0), V(9, 1, 0)))
    pdoc.recompute()
    bombear(800)
    return sk


def _modo_editando(pieza, ruta, otra, comandos, resultados):
    import FreeCADGui
    import piezas_editar as pe
    from swui.fork import edit_part as ep
    adoc, asm, (comp, _otro) = pe.ensamblaje([ruta, otra])
    gdoc = _al_frente(adoc)
    assert ep.check(comp) is None, "no se puede editar %s: %s" % (pieza, ep.check(comp))
    assert ep.start(comp, warn=False), "no entró a Editar pieza (%s)" % pieza
    bombear(500)
    pdoc = comp.LinkedObject.Document
    sels = _selecciones(pieza, pdoc)
    ctx = {"modo": "editando", "pieza": pieza, "pdoc": pdoc, "adoc": adoc, "gdoc": gdoc, "comp": comp,
           "sels": sels}

    def asegurar():
        from swui.fork import edit_context as ec
        try:
            activo = ec.active_body()
            vivo = activo is not None and activo.Document is pdoc and pdoc.getObject(activo.Name) is activo
        except Exception:  # noqa: BLE001
            vivo = False
        # limpiar borra lo que creó la prueba anterior, a veces el Cuerpo activo (Cuerpo nuevo): volver a entrar
        if ep.editing(adoc) is not comp or not vivo:
            FreeCADGui.Selection.clearSelection()
            ep.start(comp, warn=False)
            bombear(300)

    def elegir(sel):
        from swui.fork import edit_context as ec
        asegurar()
        FreeCADGui.Selection.clearSelection()
        for obj, el in _selecciones(pieza, pdoc).get(sel, []):  # al momento: una prueba puede rehacer operaciones
            assert ec.select(obj, el, clear=False), "no se pudo elegir %s %s" % (obj.Name, el)
    ctx["elegir"] = elegir

    def abrir():
        asegurar()
        return _croquis(ctx, ep)
    _recorrer(ctx, comandos, resultados, abrir_croquis=abrir)
    ep.stop(adoc)
    for d in list(FreeCAD.listDocuments().values()):
        FreeCAD.closeDocument(d.Name)
    bombear(500)


def _recorrer(ctx, comandos, resultados, abrir_croquis):
    import FreeCADGui
    propios = [(t, c) for t, c in comandos if PIEZA_DE.get(t) == ctx["pieza"]]
    for tab, cmd in propios:
        if _en_croquis(tab, cmd):
            continue
        for sel in ctx["sels"]:
            r = _correr(ctx, tab, cmd, sel)
            resultados.append(r)
            _anotar(r)
    en_croquis = [(t, c) for t, c in propios if _en_croquis(t, c)]
    if not en_croquis:
        return
    sk = ctx["croquis"] = abrir_croquis()
    for tab, cmd in en_croquis:
        vp = ctx["gdoc"].getInEdit()
        if getattr(getattr(vp, "Object", None), "Name", None) != sk.Name:
            if getattr(vp, "Object", None) is not None:
                ctx["gdoc"].resetEdit()
                bombear(300)
            sk = ctx["croquis"] = abrir_croquis()
        FreeCADGui.Selection.clearSelection()
        r = _correr(ctx, tab, cmd, "nada (en croquis)")
        resultados.append(r)
        _anotar(r)
        _escape()
    ctx["croquis"] = None
    if getattr(ctx["gdoc"].getInEdit(), "Object", None) is not None:
        ctx["gdoc"].resetEdit()
        bombear(300)
    FreeCADGui.Selection.clearSelection()


def _escape():
    import FreeCADGui
    from swui.compat import QtCore, QtGui, QtWidgets
    try:
        vp = FreeCADGui.ActiveDocument.ActiveView.graphicsView().viewport()
        for t in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
            QtWidgets.QApplication.sendEvent(vp, QtGui.QKeyEvent(t, QtCore.Qt.Key.Key_Escape,
                                                                QtCore.Qt.KeyboardModifier.NoModifier))
        bombear(150)
    except Exception:  # noqa: BLE001
        pass


def _anotar(r):
    traza("  " + json.dumps(r, ensure_ascii=False))
    if SALIDA:
        with open(SALIDA, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


# --- comparar -------------------------------------------------------------------------------------


def firma(r):
    """Lo que tiene que dar igual en los dos modos."""
    return {"panel": r["panel"], "edicion": r["edicion"], "crea": r["nuevo_pieza"],
            "crea_en_ensamblaje": r["nuevo_ensamblaje"], "queda_panel": r["queda_panel"],
            "invalidos": r["invalidos"], "avisos": r["avisos"], "excepcion": r["excepcion"],
            "errores": bool(r["errores"])}


def diferencias(resultados):
    por = {}
    for r in resultados:
        por.setdefault((r["pestaña"], r["comando"], r["eleccion"]), {})[r["modo"]] = r
    out = []
    for k, v in por.items():
        p, e = v.get("pieza"), v.get("editando")
        if p is None or e is None:
            out.append((k, "falta un modo"))
            continue
        fp, fe = firma(p), firma(e)
        malas = ["%s: pieza=%s / editando=%s" % (c, fp[c], fe[c]) for c in fp if fp[c] != fe[c]]
        if not e.get("sigue_editando", True):
            malas.append("sale de Editar pieza")
        if malas and k not in EXCEPCIONES:
            out.append((k, "; ".join(malas)))
    return out


def prueba():
    carpeta = carpeta_temporal()
    comandos = _comandos()
    traza("comandos: %d" % len(comandos))
    resultados = []
    piezas = [p for p in ("bloque", "ecuaciones", "chapa", "marco") if any(PIEZA_DE.get(t) == p for t, _c in comandos)]
    for pieza in piezas:
        sub = os.path.join(carpeta, pieza)
        os.makedirs(sub, exist_ok=True)
        ruta = _fabricar(pieza, sub)
        otra = _fabricar("bloque", os.path.join(carpeta, pieza + "_otra")) if os.makedirs(
            os.path.join(carpeta, pieza + "_otra"), exist_ok=True) is None else None
        traza("pieza %s" % pieza)
        _modo_pieza(pieza, ruta, comandos, resultados)
        yield 100
        _modo_editando(pieza, ruta, otra, comandos, resultados)
        yield 100
    difs = diferencias(resultados)
    traza("listo: %d corridas, %d distintas" % (len(resultados), len(difs)))
    for k, d in difs:
        traza("  DISTINTO %s / %s / %s: %s" % (k[0], k[1], k[2], d[:400]))
    if not SOLO_RELEVAR:
        assert not difs, "%d botones se comportan distinto editando la pieza (ver registro):\n%s" % (
            len(difs), "\n".join("%s %s %s" % k for k, _d in difs[:30]))


from _base import ejecutar  # noqa: E402
ejecutar(globals())
