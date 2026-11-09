# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de secuencias ("el mono", plan de calidad, paso 8.3): con la ventana, sobre una pieza,
una seguidilla de operaciones al azar en cualquier orden, como un usuario apurado:
- abrir un panel (Redondeo, Chaflán, Ángulo de salida, Matrices, Simetría, Plano, Eje, Punto, Mover
  cara), elegir al azar y Aceptar → Ctrl+Z vuelve exacto a como estaba, Ctrl+Y lo trae igual;
- abrir un panel, elegir y Cancelar → todo igual;
- suprimir una operación desde el árbol → Ctrl+Z la vuelve;
- Deshacer / Rehacer sueltos;
- guardar, cerrar y abrir → igual y sin quedar "modificado";
- (regla aparte, error conocido #3) abrir Ecuaciones o Material con un panel abierto, cerrarlos y
  Cancelar el panel → todo igual.
Después de CADA paso: sin errores en el informe de FreeCAD, sin diálogos ni paneles colgados, sin
objetos con error nuevos. Si algo falla, Hypothesis achica la seguidilla a la más corta que falla.
Casos (seguidillas) por regla: FW_CASOS_AZAR (6); largo de cada una: 3 a FW_LARGO_MONO (8).
De noche se corre con muchos casos y seguidillas largas."""
TIPO = "completa"

import os  # noqa: E402

import FreeCAD  # noqa: E402

from _base import carpeta_temporal, traza  # noqa: E402
from azar_comun import Fallas, bombear, comprobado, hypothesis_listo  # noqa: E402

given, cfg, st = hypothesis_listo()
LARGO = int(os.environ.get("FW_LARGO_MONO", "8"))


def _correr(gen):
    """Corre un generador de los casos (`yield ms`) de corrido, bombeando la ventana."""
    if gen is None:
        return
    for ms in gen:
        bombear(int(ms or 0))


class Mono:
    """La pieza, los paneles que se pueden abrir y lo que se mide."""

    def __init__(self):
        from casos_pieza import AnguloSalida, Chaflan, MatrizCircular, MatrizLineal, Redondeo, Simetria, armar_pieza
        from casos_pieza2 import Eje, MoverCara, Plano, Punto
        from azar_comun import limpiar
        limpiar()  # cada seguidilla, de cero y con un solo archivo abierto (memoria de la PC)
        self.doc = FreeCAD.newDocument("Mono")
        self.doc.UndoMode = 1
        self.body, self.hueco = armar_pieza(self.doc)
        self.casos = [c() for c in (Redondeo, Chaflan, AnguloSalida, MatrizLineal, MatrizCircular, Simetria,
                                    Plano, Eje, Punto, MoverCara)]
        self._atar()
        bombear(1000)  # que la ventana termine de mostrar la pieza nueva antes de la primera foto

    def _atar(self):
        for c in self.casos:
            c.doc, c.body, c.hueco = self.doc, self.body, self.hueco

    def foto(self):
        from reglas_paneles import foto
        return foto(self.doc)

    def malos(self):
        from reglas_paneles import invalidos
        return invalidos(self.doc)


def _diferencias(a, b, visibilidad=True):
    """visibilidad=False (después de Ctrl+Z / Ctrl+Y): no cuentan los cambios SOLO de visibilidad
    (error conocido #36: Ctrl+Z vuelve las visibilidades de cuando el panel estaba abierto; lo
    controla prueba_ventana_reglas_*). Si no, el mono se frenaría siempre ahí."""
    from reglas_paneles import diferencias
    out = diferencias(a, b, con_undo=False)
    if not visibilidad:
        out = [d for d in out if " cambió (visible): " not in d]
    return out


def _ventana(m, que, desde, malos0):
    """Después de cada paso: nada colgado, sin errores en el informe, sin objetos con error nuevos."""
    from reglas_paneles import limpiar_ventana, mensajes_nuevos
    restos = limpiar_ventana()
    assert not restos, "%s: quedó %s" % (que, restos)
    # "... not possible ...": aviso propio de FreeCAD cuando lo elegido al azar no sirve (radio que
    # no entra, arista de costura...); ahí lo que importa es que el panel no acepte y avise, y eso
    # ya se mide. Si el aviso viene de código de FreeWorks ("[swui..."), cuenta igual.
    errores = [l for l in mensajes_nuevos(desde) if not l.lstrip().startswith("Traceback")
               and not ("not possible" in l and "[swui" not in l)]
    assert not errores, "%s: informe de FreeCAD: %s" % (que, errores[:3])
    nuevos = m.malos() - malos0
    assert not nuevos, "%s: quedaron con error: %s" % (que, sorted(nuevos))


def paso(m, accion, semilla, historia):
    import random
    from reglas_paneles import ctrl_y, ctrl_z, informe_largo
    rng = random.Random(semilla)
    caso = m.casos[semilla % len(m.casos)]
    que = " → ".join(historia + ["%s %s" % (accion, caso.nombre)])
    desde = informe_largo()
    malos0 = m.malos()
    f0 = m.foto()
    if accion == "aceptar":
        _correr(caso.abrir(rng))
        _correr(caso.elegir(rng))
        bombear(800)
        _correr(caso.aceptar())
        bombear(800)
        if caso.ok:
            m.doc.recompute()
            f1 = m.foto()
            ctrl_z(m.doc)
            m.doc.recompute()
            bombear(400)
            d = _diferencias(f0, m.foto(), visibilidad=False)
            assert not d, "%s: Ctrl+Z no volvió a como estaba: %s" % (que, d[:3])
            ctrl_y(m.doc)
            m.doc.recompute()
            bombear(400)
            d = _diferencias(f1, m.foto(), visibilidad=False)
            assert not d, "%s: Ctrl+Y no lo trajo igual: %s" % (que, d[:3])
        else:
            _correr(caso.cancelar())
            bombear(800)  # FreeCAD vuelve a ocultar el origen un rato después de cerrar el panel
            d = _diferencias(f0, m.foto())
            assert not d, "%s: no aceptó y quedó algo: %s" % (que, d[:3])
    elif accion == "cancelar":
        _correr(caso.abrir(rng))
        _correr(caso.elegir(rng))
        bombear(800)
        _correr(caso.cancelar())
        bombear(800)  # FreeCAD vuelve a ocultar el origen un rato después de cerrar el panel
        d = _diferencias(f0, m.foto())
        assert not d, "%s: Cancelar dejó algo: %s" % (que, d[:3])
    elif accion in ("ecuaciones", "material"):
        _correr(caso.abrir(rng))
        _correr(caso.elegir(rng))
        bombear(800)
        if accion == "ecuaciones":
            from swui.fork import equations
            dlg = equations.show_dialog(m.doc)
        else:
            from swui.fork import material
            dlg = material.show_dialog(m.doc)
        bombear(800)
        dlg.reject()
        bombear(500)
        _correr(caso.cancelar())
        bombear(800)  # FreeCAD vuelve a ocultar el origen un rato después de cerrar el panel
        d = _diferencias(f0, m.foto())
        assert not d, "%s: con %s abierto, el Cancelar del panel no deshizo: %s" % (que, accion, d[:3])
    elif accion == "suprimir":
        import FreeCADGui
        from swui.fork import feature_tree as ft
        feats = [o for o in ft.features(m.body) if not getattr(o, "Suppressed", False)]
        if len(feats) > 1:
            obj = feats[1 + semilla % (len(feats) - 1)]  # no la primera (el cubo)
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(obj)
            FreeCADGui.runCommand("SWUI_Suppress")
            bombear(600)
            FreeCADGui.Selection.clearSelection()
            assert obj.Suppressed, "%s: %s no quedó suprimida" % (que, obj.Label)
            ctrl_z(m.doc)
            m.doc.recompute()
            bombear(400)
            d = _diferencias(f0, m.foto(), visibilidad=False)
            assert not d, "%s: Ctrl+Z después de suprimir no volvió: %s" % (que, d[:3])
    elif accion == "deshacer":
        ctrl_z(m.doc)
        m.doc.recompute()
        bombear(400)
    elif accion == "rehacer":
        ctrl_y(m.doc)
        m.doc.recompute()
        bombear(400)
    elif accion == "guardar":
        import FreeCADGui
        ruta = m.doc.FileName or os.path.join(carpeta_temporal(), "mono.FCStd")
        cuerpo, hueco = m.body.Name, m.hueco.Name
        m.doc.saveAs(ruta)
        FreeCAD.closeDocument(m.doc.Name)
        bombear(400)
        m.doc = FreeCAD.openDocument(ruta)
        bombear(1200)
        m.body, m.hueco = m.doc.getObject(cuerpo), m.doc.getObject(hueco)
        m._atar()
        FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", m.body)
        d = _diferencias(f0, m.foto())
        assert not d, "%s: guardar y abrir cambió: %s" % (que, d[:3])
        assert not getattr(FreeCADGui.getDocument(m.doc.Name), "Modified", False), "%s: al abrir quedó modificado" % que
        malos0 = m.malos()
    _ventana(m, que, desde, malos0)
    historia.append("%s %s" % (accion, caso.nombre if accion in ("aceptar", "cancelar", "ecuaciones", "material") else ""))


def _mono(acciones):
    @cfg
    @given(pasos=st.lists(st.tuples(st.sampled_from(acciones), st.integers(0, 10 ** 6)), min_size=3, max_size=LARGO))
    def regla(pasos):
        m = Mono()
        historia = []
        traza("  seguidilla: %s" % [a for a, _s in pasos])
        for accion, semilla in pasos:
            paso(m, accion, semilla, historia)
        comprobado()
    return regla


def prueba():
    fallas = Fallas()
    solo = os.environ.get("FW_CASO", "")
    base = ["aceptar", "aceptar", "cancelar", "suprimir", "deshacer", "rehacer", "guardar"]
    for nombre, acciones, conocido in (("mono", base, ""),
                                       ("mono con otra herramienta abierta", ["ecuaciones", "material", "aceptar"], "#3")):
        if not solo or solo.lower() in nombre:
            fallas.correr(nombre, _mono(acciones), conocido)
    fallas.terminar()


from _base import ejecutar  # noqa: E402
ejecutar(globals())
