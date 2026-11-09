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

## Fuzzing de secuencias, "el mono" (paso 8.3)

Motor `mono_comun.py`, entornos `mono_entornos.py`, una prueba por entorno
`prueba_ventana_mono*.py` (con ventana): sobre una pieza de arranque (sin historial de deshacer,
como recién abierta), una seguidilla de acciones al azar en cualquier orden, como un usuario
apurado. Acciones comunes: Aceptar (Ctrl+Z vuelve exacto, Ctrl+Y lo trae igual) o Cancelar (todo
igual) en los paneles del entorno; editar algo hecho cambiándole un valor; suprimir; Deshacer y
Rehacer sueltos; guardar, cerrar y abrir (igual y sin "modificado"). Después de cada paso: sin
errores en el informe, nada colgado, sin objetos con error nuevos. Regla aparte: Ecuaciones /
Material abiertos con un panel abierto (error conocido #3; en croquis no aplica).

| Entorno | Prueba | Acciones propias |
|---|---|---|
| Pieza | `prueba_ventana_mono.py` | 10 paneles (redondeo, chaflán, ángulo de salida, matrices, simetría, plano, eje, punto, mover cara) |
| Chapa | `prueba_ventana_mono_chapa.py` | brida de arista, dobladillo, desplegar y plegar, exportar DXF |
| Ensamblaje | `prueba_ventana_mono_ensamblaje.py` | relaciones, matriz, plano, taladro y corte de ensamblaje, suprimir componente, cambiar una medida de la pieza |
| Soldadas | `prueba_ventana_mono_soldadas.py` | miembro, esquinas, cartela, tapa, cotas del esqueleto (cada caño igual que un marco armado de cero) |
| Croquis | `prueba_ventana_mono_croquis.py` | las 7 herramientas de entidades |
| Multicuerpo | `prueba_ventana_mono_multicuerpo.py` | combinar, mover/copiar y eliminar/conservar sólidos |
| Configuraciones | `prueba_ventana_mono_configuraciones.py` | agregar configuraciones con otro largo, pasar de una a otra |

- Cuántas seguidillas: `FW_CASOS_AZAR` (6); largo: 3 a `FW_LARGO_MONO` (8). De noche, muchas y
  largas. `FW_ACHICAR=0`: no achica el caso al fallar (más rápido; para comprobar roturas).
- **Deudas**: errores ya registrados que el mono anota en la traza ("deuda #N en: ...") y no lo
  frenan, para que siga buscando otros: `deuda` (texto en el informe) y `deuda_pasos` (aviso de
  una comprobación) en cada entorno. Al arreglar la Issue, sacar su renglón.
- No cuentan: la visibilidad después de Ctrl+Z / Ctrl+Y (#36), el aviso de FreeCAD "... not
  possible ..." y los errores que vienen enteros de adentro de otro addon (SheetMetal): lo que
  importa es que FreeWorks no deje una operación con error, y eso sí se mide.
- Si una herramienta contesta con un aviso en ventanita al abrirse ("Hacen falta al menos dos
  sólidos"), el mono lo lee, lo cierra y saltea el paso; igual si no queda dónde elegir.
- Comprobado rompiendo algo a propósito en cada entorno (08-09/11): el Cancelar de los paneles SW,
  plegar la chapa, suprimir componente, el Cancelar de soldadas, el paso de deshacer del croquis y
  activar una configuración: todos atrapados.
- Encontró: #43 (chapa: el desarrollo queda con error tras exportar el DXF y cambiar la pieza),
  #44 (chapa: suprimir una brida con otra encima), #47 (configuraciones: deshacer deja la columna
  "Suprimir ..." en la tabla); y vio en acción #2, #3, #6, #36, #37 y #38.

## Fuzzing de campos (paso 8.4)

- Ecuaciones (`prueba_azar_campos_ecuaciones.py`, sin ventana, TIPO "azar"): textos raros
  (negativos, cero, enormes, "1,5", "inf", texto en un número, fórmulas rotas, referencias
  circulares, nombres que no existen) en variables y en ecuaciones sobre cotas, por las funciones
  que usa el diálogo. Reglas: solo se rechaza con un aviso claro en castellano; lo aceptado da un
  número finito y recalcula sin errores; borrar la ecuación deja la pieza como estaba. Encontró
  #45 (avisos de FreeCAD en inglés) y #46 (acepta infinito o NaN; con una ecuación infinita
  FreeCAD se cuelga: la prueba evalúa la fórmula antes de recalcular para no colgarse).
- Configuraciones, material y chapa (`prueba_azar_campos_otros.py`, sin ventana): nombres raros al
  agregar y renombrar configuraciones, valores raros para una medida (cero, negativo, enorme,
  infinito, NaN), celdas de la tabla escritas a mano con cualquier cosa; la copia del material y el
  dato de chapa guardados con texto roto; espesores raros para el nombre del DXF. Encontró #55 y
  sumó casos a #46 (los tolera como deuda, anotada en la traza).
- Paneles (`campos_comun.py`, `prueba_ventana_campos_pieza.py` y `_otros.py`, con ventana): en
  cada panel, escribir lo que sea en un campo al azar y Aceptar o Cancelar. Al teclear se manda
  cada carácter como una tecla con su texto, porque `QTest.keyClicks` cierra FreeCAD de golpe con
  caracteres como "∞". Reglas: sin errores de Python ni ventanas colgadas; lo aceptado es válido y
  se deshace exacto. Sin terminar de probar (09/11): dio bien en los primeros 4 paneles; la corrida
  completa va de noche.

## Tiempos máximos y capturas de referencia (paso 9)

- `prueba_azar_tiempos.py` (sin ventana): piezas grandes (soldada de 22 miembros, 12
  configuraciones, 60 sólidos, 100 variables encadenadas), con un tope de segundos para cada cosa
  (~4 veces lo medido el 09/11). Los tiempos medidos quedan en la traza.
- `prueba_ventana_capturas.py` (con ventana): una foto de cada pestaña de la cinta y de 6 paneles,
  comparada con la aprobada (`capturas/aprobadas/`). Las fotos que no tienen aprobada quedan en
  `capturas/nuevas/` (no se suben) para que el usuario las apruebe copiándolas a `aprobadas/`.
- Mapa de cobertura de TODO FreeWorks (`swui/`, no solo `swui/fork/`): `correr.py completa
  --cobertura` (lo corre la noche) o `correr.py sin_ventana --cobertura` (rápida + al azar).

## Las 7 preguntas (paso 7)

- Sin ventana, pregunta 4 ("abre sin FreeWorks"): `prueba_azar_sin_freeworks.py` arma con las
  funciones públicas un marco soldado con esquinas, cartela y tapa, configuraciones, ecuaciones, un
  sólido espejado, material y dato de chapa; guarda, controla que el archivo no guarde objetos de
  Python de FreeWorks y lo abre: todo sano y con el mismo volumen.

`docs/SIETE_PREGUNTAS.md`: qué prueba contesta cada pregunta en cada herramienta, y qué falta.
Agregado a partir de ese cuadro:

- La regla "guardar" controla que el archivo abra sin FreeWorks (no guarda objetos de Python
  `swui...`).
- El mono suma "otro_archivo": abre un segundo archivo, que no tiene que cambiar.
- El mono suma "medida_base": cambia el largo del cubo de base y lo vuelve a poner.

## Los errores conocidos siguen abiertos

`prueba_azar_conocidos.py` (sin ventana, necesita internet): junta los números de Issue que las
pruebas toleran (CONOCIDO, conocido=, DEUDA, deuda, deuda_pasos) y consulta GitHub: si una está
cerrada o no existe, falla con el archivo y el número. Así una prueba no queda tapando un error
que ya se arregló. Comprobado con un #16 (cerrada) y un #9999 (no existe) puestos a propósito.

## La corrida de noche

`noche.py` corre por tandas, una prueba a la vez, hasta la hora tope (07:30 por omisión):

1. batería rápida;
2. al azar sin ventana, con muchos casos;
3. reglas de paneles, medidas al azar con ventana y capturas;
4. el mono y el fuzzing de campos, con muchos casos y seguidillas largas;
5. el mapa de cobertura de todo FreeWorks;
6. si sobra tiempo, más vueltas del mono.

No arregla nada, no sube nada y no abre Issues. Deja el informe en
`%LOCALAPPDATA%/FreeWorks-dev/noche/<fecha>.md`; Claude lo lee a la mañana y registra lo
encontrado.

```
D:/Freecad/bin/python.exe tools/fork/pruebas/noche.py --hasta 07:30
D:/Freecad/bin/python.exe tools/fork/pruebas/noche.py --prueba --sin-ventana   (para ver que anda)
```

Tarea programada de Windows (la registra el usuario, o Claude con su permiso):

```
schtasks /Create /TN "FreeWorks noche" /SC DAILY /ST 01:00 /TR "D:\Freecad\bin\python.exe C:\Users\Windows\AppData\Roaming\FreeCAD\v1-1\Mod\LikeSolidWorks-UI\tools\fork\pruebas\noche.py --hasta 07:30"
```

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
