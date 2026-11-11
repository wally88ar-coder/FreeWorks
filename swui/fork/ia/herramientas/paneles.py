# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Etapa 1c: el conductor de paneles, para las 6 herramientas "delicadas" cuya lógica de FreeWorks
vive adentro del panel (Mover cara, planos/ejes/puntos SW, Mover/Copiar y Eliminar/Conservar
sólido, chapa, taladro/corte de ensamblaje). Decisión del usuario (01/11): esas van por el panel
en pantalla, como las usa él.

Cómo: igual que una persona. Abre el panel con su comando (con lo elegido antes, si hace falta),
elige referencias con la selección de FreeCAD (los paneles las toman como un clic), pone valores
en los campos que se ven (por su etiqueta) y aprieta OK o Cancelar. No usa nada interno de los
paneles: así FreeWorks no cambia y sirve también para paneles que no son SwPanel. Ventanillas:
`panel_guard.open_panel` / `cancel_open` (públicas).

Mientras el panel lo maneja la IA (pedido del usuario, 01/11): cartel "no toques el mouse" sobre
la vista y en la barra de estado; si llega un clic o una tecla de verdad (no simulada), se cancela
el panel sin aplicar nada y se avisa.
"""

import time

import FreeCAD

from swui.fork.ia.herramientas import comun as c
from swui.fork.ia.terceros.registry import ToolDefinition, ToolParam, ToolResult

OPS = {
    "mover_cara": ("SWUI_MoveFace", "Mover cara"),
    "plano": ("PartDesign_Plane", "Plano"),
    "eje": ("PartDesign_Line", "Eje"),
    "punto": ("PartDesign_Point", "Punto"),
    "mover_copiar_solido": ("SWUI_MoveBodies", "Mover/Copiar sólido"),
    "eliminar_conservar_solido": ("SWUI_DeleteBodies", "Eliminar/Conservar sólido"),
    "combinar": ("SWUI_Combine", "Combinar"),
    "brida_base": ("SWUI_SMBaseFlange", "Brida base"),
    "brida_arista": ("SWUI_SMEdgeFlange", "Brida de arista"),
    "dobladillo": ("SWUI_SMHem", "Dobladillo"),
    "convertir_chapa": ("SWUI_SMConvert", "Convertir en chapa"),
    "corte_chapa": ("SWUI_SMCut", "Extruir corte (chapa)"),
    "taladro_ensamblaje": ("SWUI_AssemblyHole", "Taladro de ensamblaje"),
    "corte_ensamblaje": ("SWUI_AssemblyCut", "Corte de ensamblaje"),
}
OPEN_WAIT_S = 15

_run = {"op": None, "title": "", "touched": False, "typing": False, "banner": None, "guard": None, "undo0": None,
        "err0": None}


# --- Cartel y guardia de clics (hilo principal) -----------------------------------------


def _banner(text):
    import FreeCADGui

    from swui.compat import QtCore, QtWidgets

    mw = FreeCADGui.getMainWindow()
    area = mw.centralWidget() or mw  # el área de la vista 3D: arriba de todo lo demás de la ventana no se ve
    if _run["banner"] is None:
        lbl = QtWidgets.QLabel(area)
        lbl.setObjectName("SWUI_IABanner")
        lbl.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lbl.setStyleSheet("QLabel { background: #fff3b0; color: #222; border: 2px solid #c79a00; "
                          "border-radius: 6px; padding: 8px 14px; font-size: 13px; font-weight: 600; }")
        _run["banner"] = lbl
    lbl = _run["banner"]
    lbl.setText(text)
    lbl.setWordWrap(False)
    lbl.adjustSize()
    lbl.move(max(10, (area.width() - lbl.width()) // 2), 14)
    lbl.raise_()
    lbl.show()
    mw.statusBar().showMessage(text)


def _guard_install():
    from swui.compat import QtCore, QtWidgets

    class _Guard(QtCore.QObject):
        def eventFilter(self, obj, event):
            t = event.type()
            if _run["typing"]:
                return False  # QTest marca sus teclas como "de verdad": las de la IA pasan
            if t in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.KeyPress) and event.spontaneous():
                if not _run["touched"]:
                    _run["touched"] = True
                    QtCore.QTimer.singleShot(0, _interrupted)
                return True  # el clic o la tecla no le llegan al panel
            return False

    if _run["guard"] is None:
        _run["guard"] = _Guard()
        QtWidgets.QApplication.instance().installEventFilter(_run["guard"])


def _cleanup():
    import FreeCADGui

    from swui.compat import QtWidgets

    if _run["guard"] is not None:
        QtWidgets.QApplication.instance().removeEventFilter(_run["guard"])
        _run["guard"] = None
    if _run["banner"] is not None:
        _run["banner"].hide()
        _run["banner"].deleteLater()
        _run["banner"] = None
    c._state["ia_panel"] = False
    try:
        FreeCADGui.getMainWindow().statusBar().clearMessage()
    except Exception:
        pass


def _interrupted():
    _cancel_dialog()
    _cleanup()
    import FreeCADGui

    FreeCADGui.getMainWindow().statusBar().showMessage(
        "Cancelé lo que hacía la IA en el panel porque tocó el mouse o el teclado (no se aplicó nada).", 10000)


def _cancel_dialog():
    import FreeCADGui

    from swui.fork import panel_guard

    try:
        if panel_guard.cancel_open():
            return
    except Exception:
        pass
    btn = _button(reject=True)
    if btn is not None:
        btn.click()
        return
    try:
        if FreeCADGui.Control.activeDialog():
            doc = FreeCAD.ActiveDocument
            if doc is not None and doc.HasPendingTransaction:
                doc.abortTransaction()
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass


# --- Leer el panel (hilo principal) -----------------------------------------------------


def _taskview():
    import FreeCADGui

    from swui.compat import QtWidgets

    for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QWidget):
        if w.metaObject().className() == "Gui::TaskView::TaskView" and w.isVisible():
            return w
    return None


def _button(reject=False):
    from swui.compat import QtWidgets

    tv = _taskview()
    if tv is None:
        return None
    role = QtWidgets.QDialogButtonBox.ButtonRole.RejectRole if reject else QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
    for box in tv.findChildren(QtWidgets.QDialogButtonBox):
        if not box.isVisible():
            continue
        for b in box.buttons():
            if box.buttonRole(b) == role and b.isEnabled():
                return b
    return None


def _label_of(w):
    from swui.compat import QtWidgets

    parent = w.parentWidget()
    lay = parent.layout() if parent is not None else None
    if isinstance(lay, QtWidgets.QFormLayout):
        lbl = lay.labelForField(w)
        if lbl is not None and hasattr(lbl, "text"):
            return lbl.text()
    if parent is not None:
        for lbl in parent.findChildren(QtWidgets.QLabel):
            if lbl.buddy() is w:
                return lbl.text()
    lay = _layout_with(lay, w) if lay is not None else None  # puede estar en un sub-renglón
    if lay is not None:
        idx = lay.indexOf(w)
        for i in range(idx - 1, -1, -1):
            item = lay.itemAt(i)
            other = item.widget() if item is not None else None
            if isinstance(other, QtWidgets.QLabel) and other.text().strip():
                return other.text()
            if other is not None and other.isVisible():
                break
    return _box_title(w)


def _layout_with(lay, w):
    """El layout (o sub-layout) que tiene a w directamente."""
    if lay.indexOf(w) >= 0:
        return lay
    for i in range(lay.count()):
        sub = lay.itemAt(i).layout()
        if sub is not None:
            found = _layout_with(sub, w)
            if found is not None:
                return found
    return None


def _box_title(w):
    """Título del recuadro que contiene a w: QGroupBox o caja de tareas de FreeCAD ("Primera referencia")."""
    from swui.compat import QtWidgets

    for anc in _ancestors(w):
        if isinstance(anc, QtWidgets.QGroupBox) and anc.title():
            return anc.title()
        name = anc.metaObject().className()
        if "TaskBox" in name or "ActionGroup" in name:
            if anc.windowTitle():
                return anc.windowTitle()
            for lbl in anc.findChildren(QtWidgets.QLabel):
                if lbl.text().strip() and not lbl.isAncestorOf(w):
                    return lbl.text()
    return ""


def _fields():
    """[(id, widget, dict)] de los campos visibles del panel abierto."""
    from swui.compat import QtWidgets

    tv = _taskview()
    if tv is None:
        return []
    out = []
    for w in tv.findChildren(QtWidgets.QWidget):
        if not w.isVisible() or isinstance(w, QtWidgets.QDialogButtonBox):
            continue
        if any(isinstance(a, QtWidgets.QDialogButtonBox) for a in _ancestors(w)):
            continue
        info = None
        if isinstance(w, QtWidgets.QAbstractSpinBox):
            if isinstance(w.parentWidget(), QtWidgets.QAbstractSpinBox):
                continue
            info = {"tipo": "numero", "valor": w.text()}
        elif isinstance(w, QtWidgets.QComboBox):
            info = {"tipo": "lista", "valor": w.currentText(), "opciones": [w.itemText(i) for i in range(w.count())]}
        elif isinstance(w, QtWidgets.QCheckBox):
            info = {"tipo": "casilla", "valor": w.isChecked(), "etiqueta": w.text()}
        elif isinstance(w, QtWidgets.QRadioButton):
            info = {"tipo": "opcion", "valor": w.isChecked(), "etiqueta": w.text()}
        elif isinstance(w, QtWidgets.QLineEdit) and not isinstance(w.parentWidget(), (QtWidgets.QAbstractSpinBox,
                                                                                      QtWidgets.QComboBox)):
            info = {"tipo": "referencia" if w.isReadOnly() else "texto", "valor": w.text()}
        elif isinstance(w, QtWidgets.QListWidget):
            info = {"tipo": "lista_elegidos", "valor": [w.item(i).text() for i in range(w.count())]}
        elif isinstance(w, QtWidgets.QPushButton) and w.text().strip():
            info = {"tipo": "boton", "etiqueta": w.text().replace("&", "")}
        if info is None:
            continue
        info.setdefault("etiqueta", _label_of(w))
        info["habilitado"] = w.isEnabled()
        out.append(("c%d" % (len(out) + 1), w, info))
    return out


def _ancestors(w):
    p = w.parentWidget()
    while p is not None:
        yield p
        p = p.parentWidget()


def _messages():
    """Textos de aviso visibles en el panel (p. ej. "elegí una cara")."""
    from swui.compat import QtWidgets

    tv = _taskview()
    if tv is None:
        return []
    out = []
    for lbl in tv.findChildren(QtWidgets.QLabel):
        if lbl.isVisible() and lbl.text().strip() and lbl.buddy() is None and len(lbl.text()) > 3:
            out.append(lbl.text().strip()[:200])
    return out[:12]


def _snapshot():
    import FreeCADGui

    return {"abierto": bool(FreeCADGui.Control.activeDialog()),
            "campos": [dict(info, id=fid) for fid, _w, info in _fields()],
            "textos": _messages()}


def _find_field(campo):
    fields = _fields()
    for fid, w, info in fields:
        if fid == campo:
            return w, info
    want = str(campo).strip().lower().rstrip(":")
    norm = lambda info: (info.get("etiqueta") or "").strip().lower().rstrip(":")  # noqa: E731
    hits = [(w, info) for _fid, w, info in fields if want and norm(info) == want] or \
           [(w, info) for _fid, w, info in fields if want and want in norm(info)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise c.Problema("No hay un campo \"%s\" en el panel. Campos: %s"
                         % (campo, [(f, i.get("etiqueta")) for f, _w, i in fields]))
    raise c.Problema("\"%s\" encaja con varios campos: usá el id (c1, c2...)." % campo)


def _set_field(campo, valor):
    from PySide6.QtTest import QTest

    from swui.compat import QtCore, QtWidgets

    w, info = _find_field(campo)
    if not w.isEnabled():
        raise c.Problema("El campo \"%s\" está deshabilitado (¿atado a una ecuación?)." % info.get("etiqueta"))
    if isinstance(w, QtWidgets.QAbstractSpinBox):
        if isinstance(w, (QtWidgets.QDoubleSpinBox, QtWidgets.QSpinBox)):
            w.setValue(float(valor) if isinstance(w, QtWidgets.QDoubleSpinBox) else int(valor))
        else:  # Gui::QuantitySpinBox de FreeCAD: escribir como el usuario
            _run["typing"] = True
            try:
                w.setFocus()
                w.selectAll()
                QTest.keyClicks(w, str(valor).replace(".", ","))
                QTest.keyClick(w, QtCore.Qt.Key.Key_Return)
            finally:
                _run["typing"] = False
    elif isinstance(w, QtWidgets.QComboBox):
        texts = [w.itemText(i) for i in range(w.count())]
        match = [i for i, t in enumerate(texts) if t.lower() == str(valor).lower()] or \
                [i for i, t in enumerate(texts) if str(valor).lower() in t.lower()]
        if not match:
            raise c.Problema("\"%s\" no es una opción de %s: %s" % (valor, info.get("etiqueta"), texts))
        w.setCurrentIndex(match[0])
    elif isinstance(w, (QtWidgets.QCheckBox, QtWidgets.QRadioButton)):
        want = valor if isinstance(valor, bool) else str(valor).lower() in ("1", "true", "si", "sí")
        if w.isChecked() != want:
            w.click()
    elif isinstance(w, QtWidgets.QPushButton):
        w.click()
    elif isinstance(w, QtWidgets.QLineEdit):
        if w.isReadOnly():
            w.setFocus()  # caja de referencia: queda activa para la próxima elección
        else:
            w.setText(str(valor))
            w.editingFinished.emit()
    else:
        raise c.Problema("No sé llenar ese campo.")
    return info.get("etiqueta")


def _select(refs):
    import FreeCADGui

    doc = FreeCAD.ActiveDocument
    for ref in refs:
        name, _, sub = str(ref).partition(".")
        obj = c.find(doc, name)
        asm = _assembly_of(obj)
        if asm is not None:  # componente: se elige dentro del ensamblaje, como un clic en la pantalla
            from swui.fork.ia.herramientas import ensamblaje

            FreeCADGui.Selection.addSelection(doc.Name, asm.Name, ensamblaje._path(doc, asm, ref))
        else:
            FreeCADGui.Selection.addSelection(doc.Name, obj.Name, sub)


def _assembly_of(obj):
    for parent in obj.InList:
        if parent.TypeId == "Assembly::AssemblyObject" and obj in parent.Group:
            return parent
    return None


def _sketch_in_edit():
    import FreeCADGui

    gdoc = FreeCADGui.ActiveDocument
    vp = gdoc.getInEdit() if gdoc is not None else None
    obj = getattr(vp, "Object", None)
    return obj if obj is not None and obj.TypeId.startswith("Sketcher::") else None


def _draw(elementos):
    """Dibujar en el croquis que abrió el panel (coordenadas globales) y salir del croquis, como el
    usuario: el panel sigue solo (p. ej. el taladro de ensamblaje muestra las piezas afectadas)."""
    import FreeCADGui

    from swui.fork.ia.herramientas import pieza_operar

    sk = _sketch_in_edit()
    if sk is None:
        raise c.Problema("No hay un croquis abierto por el panel (¿falta elegir la cara?).")
    for el in elementos or []:
        pieza_operar._add_element(sk, el)
    sk.recompute()
    FreeCADGui.ActiveDocument.resetEdit()
    return sk.Label


# --- La herramienta (hilo del servidor) -------------------------------------------------


def _gui(fn, timeout=60, name="panel"):
    from swui.fork.ia.nucleo import puente

    def task():
        try:
            return {"ok": fn()}
        except c.Problema as exc:
            return {"problema": str(exc)}
    res = puente.on_gui(task, timeout=timeout, name=name)
    if res.get("problema"):
        raise c.Problema(res["problema"])
    if "error" in res and "ok" not in res:
        raise c.Problema("FreeCAD no respondió: %s" % res["error"])
    return res.get("ok")


def _check_touched():
    if _run["touched"]:
        _run["touched"] = False
        _run["op"] = None
        raise c.Problema("El usuario tocó el mouse o el teclado mientras la IA usaba el panel: lo cancelé sin "
                         "aplicar nada. Pedile que no toque nada y volvé a empezar.")


def _open(operacion, preseleccion):
    import FreeCADGui

    from swui.compat import QtCore

    if operacion not in OPS:
        raise c.Problema("Operación \"%s\" desconocida. Hay: %s" % (operacion, ", ".join(OPS)))
    c.require_free()
    command, title = OPS[operacion]
    doc = c.document()
    _run.update(op=operacion, title=title, touched=False, undo0=list(doc.UndoNames),
                err0={o.Name for o in doc.Objects if "Invalid" in (getattr(o, "State", None) or [])})
    c._state["ia_panel"] = True
    _banner("La IA está usando el panel de %s: no toque el mouse ni el teclado hasta que termine." % title)
    _guard_install()
    FreeCADGui.Selection.clearSelection()
    if preseleccion:
        _select(preseleccion)
    QtCore.QTimer.singleShot(0, lambda: FreeCADGui.runCommand(command))
    return True


def panel(accion, operacion=None, referencias=None, campo=None, valor=None, valores=None, preseleccion=None,
          elementos=None):
    import FreeCADGui

    if accion in ("abrir", "hacer"):
        if _run["op"] is not None:
            raise c.Problema("Ya hay un panel de la IA abierto (%s): aceptalo o cancelalo primero." % _run["title"])
        _gui(lambda: _open(operacion, preseleccion or []), name="abrir panel")
        deadline = time.time() + OPEN_WAIT_S
        while time.time() < deadline:
            time.sleep(0.4)
            if _gui(lambda: bool(FreeCADGui.Control.activeDialog()), name="panel abierto?"):
                break
        else:
            _gui(_cleanup, name="limpiar")
            _run["op"] = None
            raise c.Problema("El comando de %s no abrió un panel (¿faltaba elegir algo antes? usá preseleccion)."
                             % OPS[operacion][1])
        time.sleep(0.6)  # que el panel termine de armarse
        _check_touched()
        if accion == "abrir":
            snap = _gui(_snapshot, name="ver panel")
            return ToolResult(success=True, output="Panel de %s abierto. Campos y textos:" % _run["title"], data=snap)
    if _run["op"] is None:
        raise c.Problema("No hay un panel de la IA abierto (accion='abrir' primero).")
    _check_touched()
    if accion == "ver":
        return ToolResult(success=True, output="Panel de %s." % _run["title"], data=_gui(_snapshot, name="ver panel"))
    if accion == "elegir" or (accion == "hacer" and referencias):
        if campo:
            _gui(lambda: _set_field(campo, None), name="activar campo")
            time.sleep(0.3)
        _gui(lambda: _select(referencias or []), name="elegir")
        time.sleep(0.8)
        _check_touched()
        if accion == "elegir":
            return ToolResult(success=True, output="Elegido: %s." % ", ".join(referencias or []),
                              data=_gui(_snapshot, name="ver panel"))
    if accion == "croquis":
        label = _gui(lambda: _draw(elementos), name="croquis")
        deadline = time.time() + 10
        while time.time() < deadline and not _gui(lambda: bool(FreeCADGui.Control.activeDialog()), name="panel?"):
            time.sleep(0.4)
        time.sleep(0.8)
        _check_touched()
        return ToolResult(success=True, output="Dibujado en %s y cerrado el croquis." % label,
                          data=_gui(_snapshot, name="ver panel"))
    if accion == "poner" or (accion == "hacer" and valores):
        pairs = valores.items() if (accion == "hacer" or valores) else [(campo, valor)]
        done = []
        for k, v in pairs:
            done.append("%s = %s" % (_gui(lambda k=k, v=v: _set_field(k, v), name="poner"), v))
            time.sleep(0.3)
        time.sleep(0.8)  # vista previa
        _check_touched()
        if accion == "poner":
            return ToolResult(success=True, output="Puesto: %s." % "; ".join(done), data=_gui(_snapshot, name="ver panel"))
    if accion in ("aceptar", "hacer"):
        btn_ok = _gui(lambda: _button() is not None, name="ok?")
        if not btn_ok:
            raise c.Problema("El panel no tiene un OK habilitado (¿falta elegir algo?). Mirá con accion='ver'.")
        _gui(lambda: _button().click(), name="OK")
        deadline = time.time() + 30
        while time.time() < deadline and _gui(lambda: bool(FreeCADGui.Control.activeDialog()), name="cerró?"):
            time.sleep(0.4)
        still = _gui(lambda: bool(FreeCADGui.Control.activeDialog()), name="cerró?")
        if still:
            texts = _gui(_messages, name="avisos")
            raise c.Problema("El panel no se cerró con OK; sigue abierto con estos avisos: %s" % texts)
        return _finish("aceptado")
    if accion == "cancelar":
        _gui(_cancel_dialog, name="cancelar")
        time.sleep(0.5)
        return _finish("cancelado")
    raise c.Problema("Acción \"%s\" desconocida." % accion)


def _finish(how):
    title = _run["title"]

    def done():
        _cleanup()
        doc = FreeCAD.ActiveDocument
        out = {"pasos": [], "con_error": []}
        if doc is not None:
            from swui.fork.ia.herramientas.pedido import new_steps

            k = new_steps(list(doc.UndoNames), _run["undo0"] or [])
            out["pasos"] = list(doc.UndoNames)[:k or 0]
            out["con_error"] = [c.label_of(o) for o in doc.Objects
                                if "Invalid" in (getattr(o, "State", None) or []) and o.Name not in (_run["err0"] or set())]
        return out
    out = _gui(done, name="terminar panel")
    _run["op"] = None
    text = "Panel de %s %s." % (title, how)
    if out["pasos"]:
        text += " Pasos de deshacer: %s." % ", ".join(out["pasos"])
    if out["con_error"]:
        text += " OJO, con error: %s (Ctrl+Z lo deshace)." % ", ".join(out["con_error"])
    return ToolResult(success=not out["con_error"], output=text, error=text if out["con_error"] else "")


def register(registry):
    registry.register(ToolDefinition(
        name="panel",
        description=(
            "Maneja en pantalla, como el usuario, los paneles SW cuya lógica de FreeWorks vive adentro del panel: "
            + ", ".join(OPS) + ". Mientras dura, FreeWorks muestra 'no toque el mouse'; si el usuario toca algo, "
            "se cancela sin aplicar. Pasos: accion='abrir' (con preseleccion si el comando necesita algo elegido "
            "antes, p. ej. 'Body.Face6'); 'ver' (campos con id, etiqueta, valor y opciones, y los avisos del panel); "
            "'elegir' referencias como clics ('Objeto.FaceN'; con campo=id de una caja de referencia, la activa "
            "antes); 'poner' un valor (campo + valor, o valores={campo: valor}); 'aceptar' (OK) o 'cancelar'. "
            "'croquis' dibuja (elementos, coordenadas globales) en el croquis que abrió el panel y lo cierra (taladro y "
            "corte de ensamblaje: elegir la cara, después croquis con puntos o el perfil). "
            "'hacer' = abrir + elegir + poner + aceptar en una llamada. No uses esto para lo que tiene herramienta "
            "propia sin panel."),
        parameters=[
            ToolParam("accion", "string", "abrir, ver, elegir, croquis, poner, aceptar, cancelar o hacer",
                      enum=["abrir", "ver", "elegir", "croquis", "poner", "aceptar", "cancelar", "hacer"]),
            ToolParam("operacion", "string", "Qué panel (abrir/hacer)", required=False, enum=list(OPS)),
            ToolParam("preseleccion", "array", "Lo elegido antes de abrir ('Objeto.FaceN')", required=False,
                      items={"type": "string"}),
            ToolParam("referencias", "array", "Referencias a elegir ('Objeto.FaceN', 'Objeto.EdgeN'...)",
                      required=False, items={"type": "string"}),
            ToolParam("campo", "string", "Id (c1, c2...) o parte de la etiqueta del campo", required=False),
            ToolParam("valor", "string", "Valor para el campo (número, opción de la lista, true/false)",
                      required=False),
            ToolParam("valores", "object", "Varios campos a la vez: {campo: valor}", required=False),
            ToolParam("elementos", "array", "Para accion='croquis': [{tipo: punto|circulo|rectangulo|poligono, "
                      "centro: [x,y,z], diametro, ancho, alto, desde, hasta, puntos}] en coordenadas globales",
                      required=False, items={"type": "object"}),
        ],
        handler=c.guarded(panel), category="operar", main_thread=False))
