# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
QUE = """Fuzzing de secuencias ("el mono", plan de calidad, paso 8.3) sobre una PIEZA, con la ventana:
una seguidilla de acciones al azar en cualquier orden, como un usuario apurado (motor y reglas en
`mono_comun.py`): Aceptar / Cancelar / editar en los paneles de Redondeo, Chaflán, Ángulo de salida,
Matrices, Simetría, Plano, Eje, Punto y Mover cara; suprimir; Deshacer / Rehacer; guardar y abrir.
Después de CADA paso: Ctrl+Z / Ctrl+Y exactos, sin errores, nada colgado, sin objetos con error.
Regla aparte: Ecuaciones o Material abiertos con un panel abierto (error conocido #3).
Seguidillas por regla: FW_CASOS_AZAR (6); largo: 3 a FW_LARGO_MONO (8). De noche, muchas y largas."""
TIPO = "completa"

from mono_comun import Entorno, correr_reglas  # noqa: E402


class Pieza(Entorno):
    nombre = "pieza"
    vinculos = ("body", "hueco")

    def armar(self):
        from casos_pieza import armar_pieza
        self.body, self.hueco = armar_pieza(self.doc)

    def crear_casos(self):
        from casos_pieza import AnguloSalida, Chaflan, MatrizCircular, MatrizLineal, Redondeo, Simetria
        from casos_pieza2 import Eje, MoverCara, Plano, Punto
        return [c() for c in (Redondeo, Chaflan, AnguloSalida, MatrizLineal, MatrizCircular, Simetria,
                              Plano, Eje, Punto, MoverCara)]


def prueba():
    correr_reglas(Pieza)


from _base import ejecutar  # noqa: E402
ejecutar(globals())
