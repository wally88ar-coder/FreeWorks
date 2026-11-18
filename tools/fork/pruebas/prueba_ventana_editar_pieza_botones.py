# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Relevamiento (16/11, pedido del usuario): cada botón de las pestañas Operaciones y Croquis, en la
pieza sola y editando la pieza dentro del ensamblaje (Editar pieza), con nada, una cara o una arista
elegida (los del croquis, dentro de un croquis). Anota qué panel abre, qué queda en edición, qué crea y en
qué documento, avisos y errores, y lista lo que se comporta distinto en los dos modos. Por ahora solo
releva (no falla por diferencias): la tabla la aprueba el usuario y después se arregla."""
TIPO = "completa"
TIEMPO_MAXIMO = 3000
import json  # noqa: E402
import os  # noqa: E402

import FreeCAD  # noqa: E402
from _base import carpeta_temporal  # noqa: E402
from _base import traza  # noqa: E402
from azar_comun import bombear  # noqa: E402

V = FreeCAD.Vector
SALIDA = os.environ.get("FW_SONDEO_OUT", "")
NO_PROBAR = ("Sketcher_LeaveSketch",)


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
    walk(rl.FEATURES[1], "Operaciones")
    walk(rl.SKIZZE[1], "Croquis")
    return out


def _en_croquis(tab, cmd):
    return tab == "Croquis" and cmd not in ("PartDesign_NewSketch", "SWUI_Sketch3D")


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
        from swui.compat import QtWidgets
        d = QtWidgets.QApplication.activeModalWidget()
        if d is not None and d.isVisible():
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
    return getattr(o, "TypeId", type(vp).__name__)


# --- cada prueba ----------------------------------------------------------------------------------


def _correr(ctx, tab, cmd, sel):
    import FreeCADGui
    from reglas_paneles import informe_largo, mensajes_nuevos
    from swui import ribbon
    pdoc, adoc, gdoc = ctx["pdoc"], ctx.get("adoc"), ctx["gdoc"]
    antes_p = set(o.Name for o in pdoc.Objects)
    antes_a = set(o.Name for o in adoc.Objects) if adoc else set()
    ctx["elegir"](sel)
    desde = informe_largo()
    cerr = _Cerrador()
    excepcion = ""
    try:
        ribbon._run(cmd)
    except Exception as e:  # noqa: BLE001
        excepcion = repr(e)[:120]
    bombear(1300)
    modales = cerr.parar()
    r = {
        "modo": ctx["modo"], "pestaña": tab, "comando": cmd, "eleccion": sel,
        "panel": _paneles(), "edicion": _en_edicion(gdoc),
        "nuevo_pieza": sorted(o.TypeId for o in pdoc.Objects if o.Name not in antes_p),
        "nuevo_ensamblaje": sorted(o.TypeId for o in adoc.Objects if o.Name not in antes_a) if adoc else [],
        "avisos": modales, "excepcion": excepcion,
        "errores": [m[:140] for m in mensajes_nuevos(desde)][:4],
        "banco": FreeCADGui.activeWorkbench().name(),
    }
    if ctx["modo"] == "editando":
        from swui.fork import edit_part as ep
        r["sigue_editando"] = ep.editing(adoc) is ctx["comp"]
    _limpiar(ctx, tab, cmd, antes_p, antes_a)
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
    if vp is not None and getattr(getattr(vp, "Object", None), "Name", None) != getattr(ctx.get("croquis"), "Name", 0):
        if getattr(vp, "Object", None) is not None:
            gdoc.resetEdit()
            bombear(300)
    if not en_croquis and gdoc.getInEdit() is not None and getattr(gdoc.getInEdit(), "Object", None) is not None:
        gdoc.resetEdit()
        bombear(300)
    FreeCADGui.Selection.clearSelection()
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


def _modo_pieza(pdoc, comandos, resultados):
    import FreeCADGui
    FreeCAD.setActiveDocument(pdoc.Name)
    bombear(800)
    gdoc = FreeCADGui.getDocument(pdoc.Name)
    assert FreeCADGui.ActiveDocument is not None and FreeCADGui.ActiveDocument.Document is pdoc,         "la pieza no quedó al frente: %s" % FreeCADGui.ActiveDocument
    body = pdoc.getObject("Body")
    gdoc.activeView().setActiveObject("pdbody", body)
    gdoc.activeView().viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    ctx = {"modo": "pieza", "pdoc": pdoc, "gdoc": gdoc}

    def elegir(sel):
        FreeCADGui.Selection.clearSelection()
        if sel == "cara":
            FreeCADGui.Selection.addSelection(pdoc.Name, body.Name, "Extruir.Face6")
        elif sel == "arista":
            FreeCADGui.Selection.addSelection(pdoc.Name, body.Name, "Extruir." + _arista(body))
    ctx["elegir"] = elegir
    _recorrer(ctx, comandos, resultados, abrir_croquis=lambda: _croquis_pieza(ctx, body))
    bombear(500)


def _croquis_pieza(ctx, body):
    import Part
    pdoc, gdoc = ctx["pdoc"], ctx["gdoc"]
    sk = body.newObject("Sketcher::SketchObject", "SondeoCroquis")
    sk.AttachmentSupport = [(pdoc.getObject("Extruir"), ["Face6"])]
    sk.MapMode = "FlatFace"
    sk.addGeometry(Part.LineSegment(V(5, 5, 0), V(25, 5, 0)))
    pdoc.recompute()
    gdoc.setEdit(sk)
    bombear(800)
    return sk


def _modo_editando(ruta, comandos, resultados):
    import FreeCADGui
    import casos_relacion as cr
    from swui.fork import edit_part as ep
    adoc, asm, (uno, dos) = cr._ensamblaje([ruta, ruta])
    dos.Placement.Base = V(0, 80, 0)
    adoc.recompute()
    FreeCAD.setActiveDocument(adoc.Name)
    bombear(800)
    gdoc = FreeCADGui.getDocument(adoc.Name)
    gdoc.activeView().viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    body = uno.LinkedObject
    assert ep.start(uno, warn=False), "no entró a Editar pieza"
    bombear(500)
    ctx = {"modo": "editando", "pdoc": body.Document, "adoc": adoc, "gdoc": gdoc, "comp": uno}

    def elegir(sel):
        if ep.editing(adoc) is not uno:
            FreeCADGui.Selection.clearSelection()
            ep.start(uno, warn=False)
            bombear(300)
        FreeCADGui.Selection.clearSelection()
        if sel == "cara":
            FreeCADGui.Selection.addSelection(adoc.Name, asm.Name, "%s.Extruir.Face6" % uno.Name)
        elif sel == "arista":
            FreeCADGui.Selection.addSelection(adoc.Name, asm.Name, "%s.Extruir.%s" % (uno.Name, _arista(body)))
    ctx["elegir"] = elegir

    def abrir():
        import Part
        if ep.editing(adoc) is not uno:
            ep.start(uno, warn=False)
            bombear(300)
        sk = ep.new_sketch_in_part(body.Document.getObject("Extruir"), "Face6", adoc)
        sk.addGeometry(Part.LineSegment(V(5, 5, 0), V(25, 5, 0)))
        body.Document.recompute()
        bombear(800)
        return sk
    _recorrer(ctx, comandos, resultados, abrir_croquis=abrir)
    ep.stop(adoc)


def _arista(body):
    """Una arista de arriba (la de y=0) de la pieza."""
    shp = body.getObject("Extruir").Shape if hasattr(body, "getObject") else body.Document.getObject("Extruir").Shape
    for i, e in enumerate(shp.Edges):
        b = e.BoundBox
        if abs(b.ZMin - 20) < 1e-6 and abs(b.ZMax - 20) < 1e-6 and abs(b.YMax) < 1e-6:
            return "Edge%d" % (i + 1)
    return "Edge1"


def _recorrer(ctx, comandos, resultados, abrir_croquis):
    import FreeCADGui
    for tab, cmd in comandos:
        if _en_croquis(tab, cmd):
            continue
        for sel in ("nada", "cara", "arista"):
            r = _correr(ctx, tab, cmd, sel)
            resultados.append(r)
            _anotar(r)
    # los del croquis, dentro de un croquis abierto
    sk = ctx["croquis"] = abrir_croquis()
    for tab, cmd in comandos:
        if not _en_croquis(tab, cmd):
            continue
        vp = ctx["gdoc"].getInEdit()
        if getattr(getattr(vp, "Object", None), "Name", None) != sk.Name:
            if vp is not None:
                ctx["gdoc"].resetEdit()
                bombear(300)
            sk = ctx["croquis"] = abrir_croquis()
        ctx["elegir"]("nada")
        r = _correr(ctx, tab, cmd, "nada (en croquis)")
        resultados.append(r)
        _anotar(r)
        _escape()
    ctx["croquis"] = None
    if ctx["gdoc"].getInEdit() is not None:
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


def prueba():
    from menu_comun import pieza
    carpeta = carpeta_temporal()
    doc, body, sk, pad = pieza()
    ruta = os.path.join(carpeta, "Disco.FCStd")
    doc.saveAs(ruta)
    comandos = _comandos()
    traza("comandos: %d" % len(comandos))
    resultados = []
    modos = os.environ.get("FW_SONDEO_MODOS", "pieza,editando").split(",")
    if "pieza" in modos:
        _modo_pieza(doc, comandos, resultados)
    FreeCAD.closeDocument(doc.Name)
    bombear(500)
    yield 100
    if "editando" in modos:
        _modo_editando(ruta, comandos, resultados)
    yield 100
    traza("listo: %d corridas" % len(resultados))


from _base import ejecutar  # noqa: E402
ejecutar(globals())
