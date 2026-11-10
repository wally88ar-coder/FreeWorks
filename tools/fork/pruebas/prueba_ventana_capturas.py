# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Capturas de referencia (plan de calidad, paso 9), con la ventana a 1366 x 705 (la pantalla del
usuario): una foto de la ventana con cada pestaña de la cinta y con los paneles principales abiertos
(Redondeo, Extruir, Brida base, Miembro estructural, Relación de posición), y una del diálogo de
Ecuaciones. Cada foto se compara con la aprobada por el usuario (`capturas/aprobadas/`): si cambia
más de un 0,02 % de los píxeles comparados (sin la barra de estado ni el dibujo de la vista 3D, que
se corre un píxel de una corrida a otra), falla y deja la foto nueva y una imagen con las
diferencias en `capturas/nuevas/`. Una foto sin aprobada queda en `nuevas/` para que el usuario la
mire y la apruebe (copiándola a `aprobadas/`); mientras falte alguna, la prueba da CONOCIDO #57
(no compara todo), salvo que haya otro problema (eso es FALLA).
Lo que esto controla: que un cambio no desarme sin querer el aspecto SW (cinta cortada, textos en
inglés, paneles corridos). Lo que no: si el aspecto es parecido a SW (eso lo juzga el usuario)."""
TIPO = "completa"
CONOCIDO = "#57"  # sacarlo cuando el usuario apruebe las capturas
ESPERA = "falta que el usuario apruebe"

import os  # noqa: E402
import random  # noqa: E402

import FreeCAD  # noqa: E402

from _base import traza  # noqa: E402
from azar_comun import bombear, limpiar  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
APROBADAS = os.path.join(AQUI, "capturas", "aprobadas")
NUEVAS = os.path.join(AQUI, "capturas", "nuevas")
ANCHO, ALTO = 1366, 705  # la ventana de FreeCAD maximizada en la pantalla del usuario (1366 x 768)
TOLERANCIA = 0.0002  # fracción de los píxeles comparados que puede cambiar: sin cambios da 0,00 %
                     # (dos corridas, 09/11); un texto de un panel cambiado da 0,11 % (Redondeo)
DIFERENTE = 40      # cuánto tiene que cambiar un píxel (0-255 por canal) para contar


def _ventana():
    import FreeCADGui
    return FreeCADGui.getMainWindow()


def _tamano_fijo():
    """La ventana a 1366 x 705 aunque el user.cfg copiado diga otra cosa (si el usuario cambia el
    tamaño de su FreeCAD, las fotos no tienen que fallar por eso)."""
    mw = _ventana()
    if (mw.width(), mw.height()) != (ANCHO, ALTO):
        traza("  ventana de %dx%d: se lleva a %dx%d" % (mw.width(), mw.height(), ANCHO, ALTO))
        if mw.isMaximized() or mw.isFullScreen():
            mw.showNormal()
        mw.resize(ANCHO, ALTO)
        bombear(800)


def _zona_vista():
    """El rectángulo de la vista 3D (en coordenadas de la ventana), que NO se compara: el dibujo de
    la pieza se corre uno o dos píxeles de una corrida a otra (probado: 1-2,5 % de la ventana con la
    misma pieza). La prueba controla la interfaz (cinta, paneles, textos), no el dibujo 3D. Los
    paneles de Tareas están en el panel izquierdo, afuera de esta zona (comprobado en las fotos del
    09/11). Sin documento abierto no hay vista: None."""
    from PySide import QtCore, QtWidgets
    mw = _ventana()
    mdi = mw.findChild(QtWidgets.QMdiArea)
    if mdi is None:
        return None
    arriba = mdi.mapTo(mw, QtCore.QPoint(0, 0))
    # sin las pestañas de documentos de abajo (Inicio / Captura), que sí se comparan
    return QtCore.QRect(arriba.x(), arriba.y(), mdi.width(), max(0, mdi.height() - 30))


def _comparar(nombre, img, problemas, pendientes, excluir=None, sin_abajo=0):
    """Compara la imagen con la aprobada. `excluir`: rectángulo que no se compara; `sin_abajo`:
    renglones de abajo que no se comparan (la barra de estado)."""
    from PySide import QtGui
    img = img.convertToFormat(QtGui.QImage.Format.Format_RGB32)
    os.makedirs(NUEVAS, exist_ok=True)
    ruta_ref = os.path.join(APROBADAS, nombre + ".png")
    if not os.path.exists(ruta_ref):
        img.save(os.path.join(NUEVAS, nombre + ".png"))
        pendientes.append(nombre)
        return
    ref = QtGui.QImage(ruta_ref).convertToFormat(QtGui.QImage.Format.Format_RGB32)
    if ref.size() != img.size():
        img.save(os.path.join(NUEVAS, nombre + ".png"))
        problemas.append("%s: cambió el tamaño (%sx%s, aprobada %sx%s)" % (
            nombre, img.width(), img.height(), ref.width(), ref.height()))
        return
    alto = img.height() - sin_abajo
    distintos = comparados = 0
    marca = QtGui.QImage(img)
    for y in range(0, alto, 2):  # un píxel de cada cuatro alcanza y es 4 veces más rápido
        for x in range(0, img.width(), 2):
            if excluir is not None and excluir.contains(x, y):
                continue
            comparados += 1
            a, b = img.pixel(x, y), ref.pixel(x, y)
            if a != b and max(abs(((a >> s) & 255) - ((b >> s) & 255)) for s in (0, 8, 16)) > DIFERENTE:
                distintos += 1
                marca.setPixel(x, y, 0xFFFF0000)
    fraccion = distintos / float(max(1, comparados))
    traza("  %s: %.2f %% distinto" % (nombre, 100 * fraccion))
    if fraccion > TOLERANCIA:
        img.save(os.path.join(NUEVAS, nombre + ".png"))
        marca.save(os.path.join(NUEVAS, nombre + "_diferencias.png"))
        problemas.append("%s: cambió el %.2f %% de lo comparado (ver capturas/nuevas)" % (nombre, 100 * fraccion))


def _foto(nombre, problemas, pendientes):
    """Saca la foto de la ventana y la compara con la aprobada."""
    bombear(800)
    img = _ventana().grab().toImage()
    _comparar(nombre, img, problemas, pendientes, excluir=_zona_vista(), sin_abajo=30)


def _pestanas():
    """Las pestañas de la cinta (la barra que tiene "Operaciones")."""
    from PySide import QtWidgets
    for barra in _ventana().findChildren(QtWidgets.QTabBar):
        textos = [barra.tabText(i) for i in range(barra.count())]
        if any("Operaciones" in t for t in textos):
            return barra, textos
    return None, []


def _con_panel(nombre, caso, problemas, pendientes):
    """Arma la pieza del caso, abre su panel, saca la foto y cancela."""
    from mono_comun import correr
    limpiar()
    doc = FreeCAD.newDocument("Captura")
    doc.UndoMode = 1
    correr(caso.preparar(doc))
    caso.doc = doc
    doc.recompute()
    import FreeCADGui
    FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    correr(caso.abrir(random.Random(1)))
    correr(caso.elegir(random.Random(1)))
    _foto(nombre, problemas, pendientes)
    correr(caso.cancelar())
    try:
        caso.cerrar()
    except Exception:
        pass


def prueba():
    problemas, pendientes = [], []
    _tamano_fijo()
    limpiar()
    FreeCAD.newDocument("Captura")
    barra, textos = _pestanas()
    assert barra is not None, "no encontré la cinta (barra de pestañas con Operaciones)"
    for i, texto in enumerate(textos):
        barra.setCurrentIndex(i)
        _foto("cinta_%02d_%s" % (i, "".join(c for c in texto if c.isalnum())), problemas, pendientes)
    # los paneles con la pestaña Operaciones al frente (como se trabaja), no la primera
    barra.setCurrentIndex([i for i, t in enumerate(textos) if "Operaciones" in t][0])
    from casos_ensamblaje import Relacion
    from casos_grupo3 import BridaBase
    from casos_pieza import Redondeo
    from casos_pieza2 import Extruir
    from casos_soldadas import Miembro
    for nombre, cls in (("panel_redondeo", Redondeo), ("panel_extruir", Extruir), ("panel_brida_base", BridaBase),
                        ("panel_miembro", Miembro), ("panel_relacion", Relacion)):
        try:
            _con_panel(nombre, cls(), problemas, pendientes)
        except Exception as exc:
            problemas.append("%s: no se pudo abrir (%s: %s)" % (nombre, type(exc).__name__, exc))
    limpiar()
    doc = FreeCAD.newDocument("Captura")
    from swui.fork import equations
    dlg = equations.show_dialog(doc)
    bombear(800)
    try:
        _comparar("dialogo_ecuaciones", dlg.grab().toImage(), problemas, pendientes)
    finally:
        dlg.reject()
        limpiar()
    # primero lo que es un problema de verdad (FALLA); después, lo pendiente de aprobar (CONOCIDO)
    assert not problemas, "\n".join(problemas)
    if pendientes:
        traza("  sin aprobada todavía (quedan en capturas/nuevas): %s" % ", ".join(pendientes))
    assert not pendientes, "%s %d capturas (en capturas/nuevas)" % (ESPERA, len(pendientes))


from _base import ejecutar  # noqa: E402
ejecutar(globals())
