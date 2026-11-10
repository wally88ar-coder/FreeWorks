# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Fuzzing de campos en los paneles (plan de calidad, paso 8.4), con la ventana: para cada panel (los
"casos" de las reglas de paneles), abrirlo, elegir algo válido y escribir en UNO de sus campos (al
azar) lo que sea, como un usuario que se equivoca: negativos, cero, enormes, "1,5,5", letras,
fórmulas, vacío. Después Aceptar o Cancelar (al azar). Reglas:
- nunca un error de Python en el informe ni una ventana colgada;
- si el panel acepta, lo que queda es válido (sin objetos con error) y Ctrl+Z vuelve exacto;
- si no acepta, Cancelar deja todo exactamente como estaba; Cancelar siempre deja todo igual.
Cada caso arma su pieza una vez y repite FW_CASOS_CAMPOS (2; de noche 6) veces con valores
distintos: son ~20 paneles por prueba y cada vez tarda ~10-20 s (09/11).
"""

import os
import random

import FreeCAD

from _base import traza
from azar_comun import Fallas, bombear, comprobado, hypothesis_listo
from mono_comun import NadaQueElegir, abrir, chequear_ventana, correr, diferencias, sin_lo_previo

RAROS = ["", " ", "0", "-0", "-5", "-0,001", "0,0001", "1e9", "99999999", "1e-9", "1,5", "1.5", "1,5,5",
         "1..5", ",", "-", "+", "abc", "5 mm", "5 in", "5 m", "5 °", "=2*3", "2*3", "1/0", "(", "∞",
         "inf", "nan", " 3 ", "3,", ",3", "１２", "1e400", "-1e400", "0x10", "10%"]

# Paneles que de verdad no tienen dónde escribir (solo listas de lo elegido; visto 09/11). Para
# cualquier otro, no encontrar campos es una falla (la prueba no encontró el panel, o el panel
# perdió sus campos), no un "bien" sin comprobar nada.
# sin campos a la vista al abrirse (los del Taladro de ensamblaje y la Relación aparecen recién al
# elegir otra condición final o una relación con distancia; Esquinas tiene solo listas fijas)
SIN_CAMPOS = {"Simetría", "Eje", "Punto", "Combinar", "Eliminar/Conservar sólidos", "Esquinas",
              "Relación de posición", "Taladro de ensamblaje", "Croquis: Simetría",
              "Croquis: elegir plano", "Croquis 3D"}


def _campos(caso):
    """Los campos donde se escribe del panel a la vista (números, textos, listas editables). En el
    croquis, solo los del panel de la herramienta: el panel de Tareas del croquis tiene además los
    del Sketcher (cuadrícula, filtros), que no son de FreeWorks."""
    from azar_comun import _vista_tareas
    from PySide import QtWidgets
    raiz = None
    p = caso.panel()
    if getattr(caso, "edicion_ok", "") and isinstance(getattr(p, "widget", None), QtWidgets.QWidget):
        raiz = p.widget
    if raiz is None:
        raiz = _vista_tareas()
    if raiz is None:
        return []
    out = []
    for w in raiz.findChildren(QtWidgets.QWidget):
        if not (w.isVisible() and w.isEnabled()):
            continue
        if isinstance(w, QtWidgets.QAbstractSpinBox):
            if not w.isReadOnly():
                out.append(w)
        elif isinstance(w, QtWidgets.QLineEdit):
            padre = w.parent()
            if isinstance(padre, (QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox)) or w.isReadOnly():
                continue
            out.append(w)
        elif isinstance(w, QtWidgets.QComboBox) and w.isEditable():
            out.append(w)
    return out


def _nombre(w):
    return "%s %s" % (w.metaObject().className(), w.objectName() or "(sin nombre)")


def _cerrar_emergentes():
    """Cierra una ventanita emergente que haya quedado (el editor de fórmulas que abre "=" en un
    campo de medida es emergente, no modal: `activeModalWidget` no lo ve). Devuelve si había."""
    from PySide import QtWidgets
    w = QtWidgets.QApplication.activePopupWidget()
    if w is None:
        return False
    w.close()
    bombear(200)
    return True


def escribir(w, texto):
    """Como el usuario: seleccionar todo, escribir y pasar al campo siguiente con Tab."""
    import FreeCADGui
    from PySide import QtCore, QtWidgets
    from PySide6.QtTest import QTest
    # FreeCAD al frente: si no, setFocus no da el foco, el Tab no termina la edición y lo escrito
    # puede no aplicarse (con la PC en uso por otra cosa no se puede garantizar: queda en la traza)
    mw = FreeCADGui.getMainWindow()
    mw.raise_()
    mw.activateWindow()
    w.setFocus()
    bombear(100)
    if not w.hasFocus() and not (isinstance(w, QtWidgets.QComboBox) and w.lineEdit().hasFocus()):
        traza("      (aviso: el campo no tomó el foco; FreeCAD no estaba al frente)")
    if isinstance(w, QtWidgets.QAbstractSpinBox):
        w.selectAll()
    elif isinstance(w, QtWidgets.QComboBox):
        w.lineEdit().selectAll()
    else:
        w.selectAll()
    destino = w.lineEdit() if isinstance(w, QtWidgets.QComboBox) else w
    if texto:
        # una tecla por carácter con su texto (QTest.keyClicks aborta FreeCAD con caracteres que no
        # son del inglés básico: "∞", "１２"; visto 09/11)
        from PySide import QtGui
        for ch in texto:
            for tipo in (QtCore.QEvent.Type.KeyPress, QtCore.QEvent.Type.KeyRelease):
                QtWidgets.QApplication.sendEvent(destino, QtGui.QKeyEvent(tipo, 0, QtCore.Qt.KeyboardModifier.NoModifier, ch))
            # "=" abre el editor de fórmulas (emergente): lo que sigue va ahí, como con el usuario
            bombear(30)
    else:
        QTest.keyClick(destino, QtCore.Qt.Key.Key_Delete)
    emergente = QtWidgets.QApplication.activePopupWidget()
    if emergente is not None:
        # el editor de fórmulas: Escape lo cierra sin aplicar (como el usuario que se arrepiente)
        QTest.keyClick(emergente, QtCore.Qt.Key.Key_Escape)
        bombear(200)
        _cerrar_emergentes()
    QTest.keyClick(destino, QtCore.Qt.Key.Key_Tab)
    bombear(500)


class _Medidor:
    """Lo que `chequear_ventana` necesita (documentos a medir y deudas)."""

    def __init__(self, caso, deuda=()):
        self.caso, self.deuda = caso, deuda
        self.doc = caso.doc

    def otros(self):
        return [o for o in self.caso.documentos(self.doc) if o is not None and o is not self.doc]

    def foto(self):
        from reglas_paneles import foto_varios
        return foto_varios(self.doc, self.otros())

    def malos(self):
        from reglas_paneles import invalidos
        out = set(invalidos(self.doc))
        for o in self.otros():
            try:
                out |= {"%s:%s" % (o.Label, n) for n in invalidos(o)}
            except Exception:
                pass
        return out


def _con_avisos(fn):
    """Corre fn cerrando los avisos en ventanita que aparezcan (los devuelve y quedan en la traza:
    un aviso con un error de Python adentro sería una falla, ver `_aviso_con_error`)."""
    from PySide import QtCore, QtWidgets
    avisos = []

    def mirar():
        d = QtWidgets.QApplication.activeModalWidget()
        if isinstance(d, QtWidgets.QMessageBox):
            avisos.append(d.text())
            d.accept()
    reloj = QtCore.QTimer()
    reloj.timeout.connect(lambda: mirar())
    reloj.start(300)
    try:
        fn()
    finally:
        reloj.stop()
    for a in avisos:
        traza("      aviso en ventanita: %s" % a[:200].replace("\n", " "))
    return avisos


def _aviso_con_error(avisos, que):
    """Un aviso al usuario con un error de Python adentro (Traceback, Error: ...) es una falla."""
    for a in avisos:
        if "Traceback" in a or "Error:" in a or "Exception" in a:
            raise AssertionError("%s: aviso con un error de Python adentro: %s" % (que, a[:300]))


def _sigue_en_edicion_ok(caso):
    """Aceptó y quedó en la edición que el caso permite (el croquis, para sus herramientas de
    entidades): el panel de la herramienta se cerró pero el croquis sigue abierto."""
    import FreeCADGui
    tipo = getattr(caso, "edicion_ok", "")
    if not tipo or caso.panel() is not None:
        return False
    gdoc = FreeCADGui.ActiveDocument
    vp = gdoc.getInEdit() if gdoc is not None else None
    return vp is not None and getattr(vp.Object, "TypeId", "") == tipo


def _dejar_limpio(caso, m):
    """Cierra lo que haya quedado abierto (panel, croquis, ventanitas) y deshace lo que haya
    quedado a medias: cada ejemplo empieza limpio aunque el anterior haya fallado en el medio.
    Devuelve lo que encontró abierto."""
    import FreeCADGui
    from reglas_paneles import limpiar_ventana
    restos = []
    if _cerrar_emergentes():
        restos.append("ventanita emergente")
    try:
        if caso.panel() is not None or FreeCADGui.Control.activeDialog():
            _con_avisos(lambda: correr(caso.cancelar()))
            restos.append("panel")
    except Exception:
        pass
    restos += limpiar_ventana()
    try:
        if m.doc.HasPendingTransaction:
            m.doc.abortTransaction()
            restos.append("transacción a medias")
    except Exception:
        pass
    bombear(300)
    return restos


def una_vez(caso, m, texto, cual, aceptar, semilla):
    restos = _dejar_limpio(caso, m)
    if restos:
        traza("      (había quedado abierto de antes: %s)" % ", ".join(restos))
    try:
        _una_vez(caso, m, texto, cual, aceptar, semilla)
    except BaseException:
        _dejar_limpio(caso, m)
        raise


def _una_vez(caso, m, texto, cual, aceptar, semilla):
    import FreeCADGui
    from reglas_paneles import ctrl_y, ctrl_z, informe_largo
    rng = random.Random(semilla)
    desde = informe_largo()
    malos0 = m.malos()
    f0 = m.foto()
    try:
        abrir(caso, rng)
    except NadaQueElegir:
        return
    correr(caso.elegir(rng))
    bombear(600)
    campos = _campos(caso)
    if not campos:
        assert caso.nombre in SIN_CAMPOS, (
            "%s: no encontré ningún campo donde escribir (¿no se abrió el panel, o perdió sus "
            "campos?). Si este panel de verdad no tiene campos, sumarlo a SIN_CAMPOS" % caso.nombre)
        # panel sin nada donde escribir: lo que se comprueba es que Cancelar deje todo igual
        correr(caso.cancelar())
        bombear(600)
        d = diferencias(f0, sin_lo_previo(caso, m.foto(), f0))
        assert not d, "%s (panel sin campos): Cancelar no dejó todo como estaba: %s" % (caso.nombre, d[:3])
        chequear_ventana(m, "%s: (sin campos)" % caso.nombre, desde, malos0)
        comprobado()
        return
    w = campos[cual % len(campos)]
    que = "%s, campo %s = %r, %s" % (caso.nombre, _nombre(w), texto, "Aceptar" if aceptar else "Cancelar")
    _aviso_con_error(_con_avisos(lambda: escribir(w, texto)), que)
    comprobado()
    if aceptar:
        _aviso_con_error(_con_avisos(lambda: correr(caso.aceptar())), que)
        bombear(800)
        if caso.ok and _sigue_en_edicion_ok(caso):
            # herramientas de entidades del croquis: Aceptar deja el croquis abierto (como SW); se
            # sale del croquis y se controla que nada quede con error. El Ctrl+Z adentro del croquis
            # lo controlan las reglas de paneles (regla "aceptar" con edicion_ok). Lo aceptado queda:
            # el croquis crece un poco en cada ejemplo (2 a 6 por panel)
            correr(caso.despues_de_aceptar())
            bombear(400)
            m.doc.recompute()
            nuevos = m.malos() - malos0
            assert not nuevos, "%s: aceptó y quedó con error: %s" % (que, sorted(nuevos))
        elif caso.ok and not FreeCADGui.Control.activeDialog():
            m.doc.recompute()
            nuevos = m.malos() - malos0
            assert not nuevos, "%s: aceptó y quedó con error: %s" % (que, sorted(nuevos))
            f1 = m.foto()
            ctrl_z(m.doc)
            m.doc.recompute()
            bombear(400)
            d = diferencias(f0, sin_lo_previo(caso, m.foto(), f0), visibilidad=False)
            assert not d, "%s: Ctrl+Z no volvió a como estaba: %s" % (que, d[:3])
            ctrl_y(m.doc)  # y otra vez Ctrl+Z, para dejar la pieza como al empezar
            m.doc.recompute()
            d = diferencias(f1, m.foto(), visibilidad=False)
            assert not d, "%s: Ctrl+Y no lo trajo igual: %s" % (que, d[:3])
            ctrl_z(m.doc)
            m.doc.recompute()
            bombear(300)
            correr(caso.despues_de_aceptar())
        else:
            _aviso_con_error(_con_avisos(lambda: correr(caso.cancelar())), que)
            bombear(600)
            d = diferencias(f0, sin_lo_previo(caso, m.foto(), f0))
            assert not d, "%s: no aceptó y Cancelar no dejó todo como estaba: %s" % (que, d[:3])
    else:
        _aviso_con_error(_con_avisos(lambda: correr(caso.cancelar())), que)
        bombear(600)
        d = diferencias(f0, sin_lo_previo(caso, m.foto(), f0))
        assert not d, "%s: Cancelar no dejó todo como estaba: %s" % (que, d[:3])
    chequear_ventana(m, que, desde, malos0)


def regla_campos(caso, deuda, deuda_pasos=()):
    given, cfg, st = hypothesis_listo()
    cfg = type(cfg)(cfg, max_examples=int(os.environ.get("FW_CASOS_CAMPOS", "2")))
    from azar_comun import limpiar
    limpiar()
    doc = FreeCAD.newDocument("Campos")
    doc.UndoMode = 1
    correr(caso.preparar(doc))
    caso.doc = doc
    doc.recompute()
    doc.clearUndos()
    for o in caso.documentos(doc):
        if o is not None:
            o.clearUndos()
    bombear(1000)
    m = _Medidor(caso, deuda)
    texto_st = st.one_of(st.sampled_from(RAROS), st.text(max_size=8),
                         st.text(alphabet="0123456789,.-+e ", min_size=1, max_size=8))

    @cfg
    @given(texto=texto_st, cual=st.integers(0, 50), aceptar=st.booleans(), semilla=st.integers(0, 10 ** 6))
    def regla(texto, cual, aceptar, semilla):
        try:
            una_vez(caso, m, texto, cual, aceptar, semilla)
        except AssertionError as exc:
            # errores ya registrados que aparecen como una comprobación (no en el informe): se
            # anotan y no frenan la búsqueda (como deuda_pasos del mono)
            for issue, texto_falla in deuda_pasos:
                if texto_falla in str(exc):
                    traza("    (deuda %s en: %s)" % (issue, str(exc)[:200]))
                    return
            raise
    # la memoria de Hypothesis (casos que fallaron, para repetirlos primero la próxima vez) se
    # guarda por el código de la regla, que es el mismo para todos los paneles: sin esto, el caso
    # que falló en un panel se repite en los demás y se borra cuando ahí pasa
    try:
        regla.hypothesis.inner_test._hypothesis_internal_add_digest = caso.nombre.encode("utf-8")
    except Exception:
        pass
    return regla


def correr_campos(clases, deuda=None, deuda_pasos=None):
    """Una regla por panel. `deuda`: {nombre del caso: (("#N", texto que aparece en el informe,
    objeto o None), ...)}; `deuda_pasos`: {nombre del caso: (("#N", texto de la comprobación que
    falla), ...)}: errores ya registrados que no frenan la búsqueda."""
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "").lower()
    for cls in clases:
        caso = cls()
        if solo and solo not in caso.nombre.lower():
            continue
        try:
            regla = regla_campos(caso, (deuda or {}).get(caso.nombre, ()), (deuda_pasos or {}).get(caso.nombre, ()))
        except Exception as exc:
            traza("  %s: no se pudo armar la pieza: %s" % (caso.nombre, exc))
            fallas.lista.append("%s: no se pudo armar la pieza: %s" % (caso.nombre, exc))
            continue
        fallas.correr(caso.nombre, regla)
        try:
            caso.cerrar()
        except Exception:
            pass
    fallas.terminar()
