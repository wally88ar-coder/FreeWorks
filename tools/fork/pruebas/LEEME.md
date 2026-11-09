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
copia de `user.cfg`, nunca la del usuario; si una se pasa de tiempo (FW_TIEMPO_VENTANA, 600 s por
omisión) se corta, y FreeCAD puede dejar un archivo de recuperación de esa prueba (avisa la
próxima vez que se abre FreeCAD: descartarlo). `--detalle` muestra el registro paso a paso.

## Reglas comunes de los paneles (paso 8.1 del plan)

`reglas_paneles.py` tiene las reglas que TODO panel cumple (cancelar, invalido, otro_comando,
aceptar con deshacer/rehacer, editar, guardar; sin errores en el informe de FreeCAD) y las corre
con elecciones y valores al azar. Cada panel es un "caso" en `casos_*.py`; cada
`prueba_ventana_reglas_*.py` corre un grupo y tiene su DEUDA: (panel, regla) -> Issue de lo que ya
se sabe que falla (si deja de fallar, la prueba avisa para sacarlo).

- Un panel solo: `FW_CASO=Redondeo ... correr.py solo_ventana reglas_pieza --detalle`.
- Más vueltas al azar: `FW_SEMILLAS=10 FW_SEMILLA=37` (por omisión 2 vueltas desde la 1). Cada
  vuelta suma ~13 s por panel: con muchas vueltas, de a un panel (`FW_CASO`) o con más tiempo
  (`FW_TIEMPO_VENTANA=3600`).
- DEUDA: `(panel, regla): ("#N", "texto", ...)` tapa solo las fallas de esa regla que contienen
  alguno de esos textos; cualquier otra falla en la misma regla sale igual.
- Qué compara (`foto`): por objeto, tipo, volumen y caja envolvente (también de vínculos, planos y
  ejes), ubicación, visibilidad, marcas `SWUI_` (con el nombre del objeto apuntado), contenido de
  planillas y, en croquis, qué hay dibujado y dónde; pasos de deshacer y transacciones abiertas;
  objetos con error y croquis con relaciones en conflicto.
- Panel nuevo: agregar su clase `Caso` al `casos_*.py` del área (preparar, abrir, elegir, inválido).

Paneles en el banco (08/11, 48 + 4 variantes): Redondeo, Chaflán, Ángulo de salida, Matriz lineal, Matriz
circular, Simetría, Plano, Eje, Punto, Combinar, Mover cara, Extruir, Extruir corte, Revolución,
Taladro, Mover/Copiar sólidos, Eliminar/Conservar sólidos, Brida base, Brida de arista,
Dobladillo, Miembro estructural, Esquinas, Cartela, Tapa de extremo, Relación de posición, Matriz
de componentes, Plano de ensamblaje, las 7 herramientas del croquis, Convertir a chapa, Vista de
sección, Agregar configuración, Croquis (elegir plano), Croquis 3D, Eje y Punto de ensamblaje,
Recortar miembro, Hélice, Barrido, Recubrir, Taladro y Extruir corte de ensamblaje, Corte
desdoblado. Variantes: Mover sin copiar, Mover cara trasladando y girando, Tapa de extremo elegida
con un clic. Reglas extra al editar: cambiar un valor y Cancelar (queda como antes) o Aceptar (se
aplica, un paso de deshacer, Ctrl+Z / Ctrl+Y exactos). Deshacer y Rehacer son los del usuario
(Std_Undo / Std_Redo), no `doc.undo()`: el del usuario alcanza a otros documentos de la misma
operación (ensamblaje + piezas). **Fuera, a propósito
(decidido por el usuario el 08/11): los paneles de planos** (Insertar imagen, Propiedades de
hoja, Acabado superficial, Símbolo de soldadura): se prueban cuando se encaren los planos de
forma integral.

## Medidas al azar (paso 8.2)

`azar_comun.py` + `prueba_ventana_azar_*.py`, con Hypothesis (en la carpeta de herramientas;
`pip install --target ... hypothesis`). Van por el panel, como el usuario; cada regla compara la
pieza con la fórmula de libro y lo puesto en el panel con lo que quedó en el objeto. Si una falla,
Hypothesis achica el caso al más simple y lo recuerda (`%LOCALAPPDATA%/FreeWorks-dev/hypothesis`).
Memoria (pedido del usuario 08/11): nunca más de 4 archivos abiertos a la vez (`cerrar_viejos`;
en ensamblajes, se cierran los del caso anterior). Al fallar, Hypothesis achica el caso probando
muchas variantes (con ventana, decenas de piezas): para comprobar una rotura a propósito usar
`FW_ACHICAR=0`, y no hacerlo con ventana mientras el usuario usa la PC.
Casos por regla: `FW_CASOS_AZAR` (6 por omisión, de noche cientos). Una regla sola:
`FW_CASO=redondeo`. Ojo al escribir en campos de FreeCAD: Enter = Aceptar del panel (usar Tab).

- Operaciones de pieza (`prueba_ventana_azar_pieza.py`, 10 reglas): extruir (4 modos), corte (con
  y sin Por todo), revolución, redondeo, chaflán, taladro (Ø según ISO 273), matriz lineal y
  circular, simetría, ángulo de salida. Comprobado que atrapa errores: con el radio del Redondeo
  roto a propósito (+10 %) falló y lo achicó a un cubo de 2 mm con radio 0,5.

- Piezas soldadas (`prueba_azar_soldadas.py`, sin ventana, TIPO "azar": corre en la entrega y de
  noche, no en cada commit; `correr.py solo_azar`): marcos paralelogramo y triángulo con cualquier
  perfil que entre, tope o inglete: válidos, sin superposición (lo que comparte cada par; unir todo
  no sirve con caños redondos), sin huecos en las esquinas, lista de cortes = largo real, guardar y
  abrir igual, y mover un vértice del esqueleto = armar el marco de cero (#2, a tope y a inglete).

- Chapa (`prueba_ventana_azar_chapa.py`): Brida base de perfil abierto al azar (1 a 3 pliegues)
  y Brida de arista al azar (largo, ángulo, cómo se mide, posición): lo puesto queda en la chapa,
  y el desarrollo tiene la superficie que da SW con el factor K (volumen/espesor − Σ ángulo·ancho
  ·(0,5 − K)·espesor), con una línea de plegado por pliegue y el contorno del DXF cerrado.
  Comprobado: con el desarrollo forzado a K = 0,5 falla enseguida. Falta comparar contra SW mismo
  (el puente con SW no mide desarrollos todavía).

- Ensamblajes (`prueba_ventana_azar_ensamblaje.py`): piezas de medida al azar, la que se mueve en
  posición y giro al azar. Coincidente, Distancia, Ángulo, Paralela, Perpendicular (medidas sobre
  las caras globales), Concéntrica (ejes en la misma recta), la fija no se mueve, cambiar la medida
  de una pieza y que se siga cumpliendo, guardar y abrir, Matriz de componentes (paso exacto, sin
  corrimientos) y Taladro de ensamblaje en una pieza girada (eje en el punto marcado). Comprobado:
  con la Distancia guardada un 10 % de más, falla. También: Tangente, simetría de componentes
  (copia en espejo), Extruir corte de ensamblaje en una pieza girada (saca rectángulo × alto) y
  configuraciones (suprimir en una, volver a la otra). 10 reglas en total, todas bien.

- Croquis (`prueba_azar_croquis.py`, sin ventana): mover/girar/escalar y volver, simetría dos
  veces, copiar, matriz; sin relaciones malas. Encontró #41 (Girar con centro fuera del origen).
- Multicuerpo (`prueba_azar_multicuerpo.py`, sin ventana): Alcance exacto por sólido, detectar
  los sólidos que atraviesa un Por todo (#42), sacar del Alcance (#1).
- Evaluar (`prueba_azar_evaluar.py`, sin ventana): masa, centro de masa e inercia de cubos y
  cilindros girados al azar contra fórmulas de libro, varios sólidos con Steiner.
- Configuraciones de pieza (`prueba_azar_configuraciones.py`, sin ventana): ir y venir entre
  configuraciones en cualquier orden, guardar y abrir.
- Mover cara (`prueba_ventana_azar_mover_cara.py`, con ventana): equidistanciar (volumen = área ×
  d) y girar (inclinación exacta).

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
