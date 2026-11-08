# Batería de pruebas de FreeWorks

Plan de calidad del 08/11/2026 (`docs/PLAN_CALIDAD.md`). Cada error arreglado y cada herramienta
nueva dejan acá su prueba, para que lo que ya anda no se rompa sin que nadie se entere.

## Correr

Con el Python de FreeCAD, desde la carpeta del addon:

```
D:/Freecad/bin/python.exe tools/fork/pruebas/correr.py                 # rápida (FreeCADCmd, ~15 s)
D:/Freecad/bin/python.exe tools/fork/pruebas/correr.py completa        # rápida + con ventana
D:/Freecad/bin/python.exe tools/fork/pruebas/correr.py solo_ventana
D:/Freecad/bin/python.exe tools/fork/pruebas/correr.py inglete         # solo las que dicen "inglete"
D:/Freecad/bin/python.exe tools/fork/pruebas/correr.py completa --cobertura   # + docs/MAPA_PRUEBAS.md
```

Resultados: **BIEN**; **FALLA** (frena el commit); **CONOCIDO #N** (error abierto en las Issues,
no frena: se muestra la última línea para ver que falla por ese error y no por otro);
**ARREGLADO?** (tenía CONOCIDO y ahora pasa: sacarle el CONOCIDO y cerrar la Issue; frena).

Cada prueba corre en su propio FreeCAD, una a la vez (memoria de la PC). Las de ventana usan una
copia de `user.cfg`, nunca la del usuario; si una se pasa de tiempo (150 s) se corta, y FreeCAD
puede dejar un archivo de recuperación de esa prueba (avisa la próxima vez que se abre FreeCAD:
descartarlo).

## Enganche de git

`tools/fork/hooks/pre-commit` corre antes de cada commit (si el commit toca algún `.py`):
`tools/test_load.py`, ruff (solo errores seguros) y la batería rápida. Se instala una vez:

```
git config core.hooksPath tools/fork/hooks
```

Herramientas (fuera del repositorio): `%LOCALAPPDATA%/FreeWorks-dev/pkgs`, armada con
`D:/Freecad/bin/python.exe -m pip install --target %LOCALAPPDATA%/FreeWorks-dev/pkgs ruff coverage`.

## Escribir una prueba

Un archivo `prueba_<algo>.py` (las que necesitan la ventana: `prueba_ventana_<algo>.py`):

```python
QUE = """Qué tiene que pasar, en castellano, escrito ANTES de programar."""
CONOCIDO = "#12"     # solo si es un error todavía abierto
ESPERA = "quedó con"  # con CONOCIDO: parte del mensaje que da ESE error (otro = FALLA)
TIPO = "completa"    # solo si necesita la ventana

import FreeCAD  # noqa: E402
from comun import caja, cerca, marco  # noqa: E402   (piezas que arman varias pruebas)

def prueba():
    ...                 # falla con assert o con una excepción
    # con ventana: devolver [(demora_ms, función), ...] para dar tiempo a los paneles

from _base import ejecutar  # noqa: E402
ejecutar(globals())
```

Las 7 preguntas (CLAUDE.md, Calidad): cancelar, deshacer y rehacer, cambiar una medida anterior y
recalcular, guardar-cerrar-abrir, otra herramienta con el panel abierto, dos archivos, una
elección rara. Una prueba nueva que encuentra un error: abrir la Issue y marcarla `CONOCIDO`.

Antes de confiar en una prueba de un error arreglado, comprobar que **falla** con el error puesto
(se hizo con `prueba_abrir_no_modifica`: sacando el arreglo de cross_body, falla).
