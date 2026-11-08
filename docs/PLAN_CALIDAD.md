# Plan para cometer menos errores — aprobado el 08/11/2026

Estado: pasos 1 a 6 implementados el 08/11 (reglas en CLAUDE.md, `swui/fork/safe_ops.py`,
`tools/fork/pruebas/`, `tools/fork/hooks/pre-commit`, Issues, `docs/MAPA_PRUEBAS.md`). Pasos 8
(pruebas adversariales) y 9 (todo `swui`, capturas de referencia, tiempos) sumados el 08/11, sin
empezar. Pasos 7 a 9 y corrección de errores: cuando el usuario diga.

Objetivo: trabajar al nivel de un proyecto abierto serio ("profesional bueno"), no al de aviones
o equipos médicos. Base: las 4 causas que mostró la auditoría (`docs/AUDITORIA_2026-11-08.md`):
trabajo repetido hecho distinto, casos que nadie se preguntó, pruebas que no se repiten y
afirmar sin comprobar.

Hoy existe: `tools/test_load.py` (comprueba que el banco carga, con un FreeCAD de mentira, sin
geometría real) y una sola prueba de geometría (`tools/fork/test_sketch_entities.py`).

## Paso 1. Reglas fijas (en las instrucciones del proyecto, valen en todas las sesiones)

- **Antes de programar**, escribir en 2 o 3 renglones qué tiene que pasar. Ejemplo: "si cambio
  el esqueleto, el inglete se rehace sin hueco". La prueba se arma con eso.
- **Las preguntas obligatorias** de toda herramienta nueva o cambiada:
  1. ¿Y si cancelo?
  2. ¿Y si deshago y rehago?
  3. ¿Y si cambio una medida de algo anterior y recalculo?
  4. ¿Y si guardo, cierro y abro? ¿Queda sin "modificado"? ¿Abre sin FreeWorks?
  5. ¿Y si abro otra herramienta (o Ecuaciones, Material, Suprimir) con el panel abierto?
  6. ¿Y con dos archivos abiertos?
  7. ¿Y si elijo algo raro (arco en vez de recta, cara curva, otro sólido, nada)?
- **No anotar que algo anda** (en ESTADO, en el checklist o al usuario) sin una prueba que lo
  muestre. Si no se probó, se dice "sin probar".
- **Antes de cada entrega**: revisión del cambio por un agente que no lo escribió (recibe el
  código, no mis conclusiones) y el analizador automático (ruff).
- **Lo nativo antes que el enganche**: meterse en el funcionamiento interno de FreeCAD solo si no
  hay otra forma, y cada enganche con su prueba.

## Paso 2. Piezas comunes (cada tarea delicada escrita una sola vez)

Un módulo nuevo del fork con las tareas donde ya hubo errores, y que todos usen:

- **Borrar una operación** del medio de un sólido sin dejar a la siguiente sin base (grave 1).
- **Empezar algo que se pueda deshacer** sin romper el Cancelar de un panel abierto (grave 3:
  FreeCAD no anida las transacciones).
- **Panel base**: todo panel nuevo queda registrado en el "guardia" de paneles y se limpia si
  FreeCAD lo cierra (medianos 6 y 12).
- **Escucha base**: no hace nada mientras FreeCAD abre un archivo o deshace (el error que
  encontró la auditoría en las referencias).
- **Nada de guardar el nombre interno de un documento** (mediano 5): se guarda el archivo.

Se pasan a la pieza común de a poco: cada vez que se arregla o se toca un módulo, no todos de una.

## Paso 3. Batería de pruebas automáticas

Carpeta `tools/fork/pruebas/`, una prueba por caso, cada una con su "qué tiene que pasar" arriba.

- **Rápida** (FreeCAD sin ventana, 1 o 2 minutos): geometría y lógica. Arranca con: abrir un
  archivo no lo modifica; borrar una copia de Alcance no vacía otro sólido; el inglete sigue al
  esqueleto; las herramientas del croquis (la prueba que ya existe).
- **Completa** (FreeCAD de prueba con ventana, solo, un FreeCAD a la vez para cuidar la memoria):
  paneles, Cancelar, deshacer, otra herramienta en el medio. Antes de cada entrega.
- **Regla**: todo error arreglado deja su prueba, y toda herramienta nueva entra con las suyas
  (las preguntas del paso 1). Así lo que ya se arregló no vuelve.

## Paso 4. Que la batería corra sola

Un enganche de git en esta PC: antes de cada commit corre `test_load.py`, ruff y la batería
rápida. Si algo falla, el commit no se hace hasta arreglarlo. No usa servicios externos. La
completa la corro yo antes de cada entrega (con ventana no conviene en cada commit).

## Paso 5. Registro de errores con su causa: Issues de GitHub (decidido 08/11)

https://github.com/wally88ar-coder/FreeWorks/issues (activadas el 08/11; el repositorio es
público). Cada error encontrado (por el usuario, por Claude o por una auditoría) es una ficha con:
qué pasa, dónde, causa, estado (verificado/probable) y qué prueba lo cubre. Etiquetas: gravedad
(grave/mediano/chico), verificado/probable, **causa** (`causa: repetido`, `causa: caso no
pensado`, `causa: sin prueba`, `causa: sin comprobar`) y área. El commit que lo arregla dice
"Arregla #N" y la ficha se cierra sola al subirlo. Si una causa se repite, se arregla de raíz
(normalmente con una pieza común). Arrancó con la auditoría: #1 a #27 abiertas, #28 cerrada.
Sin `docs/ERRORES.md`: los errores van solo ahí; ESTADO enlaza, el checklist sigue con las fases.

## Paso 6. Mapa de qué no prueba nadie (sumado por el usuario, 08/11)

Una herramienta (coverage, en una carpeta aparte, sin tocar FreeCAD) marca qué partes del código
no tocó ninguna prueba. Se usa como **mapa** para elegir qué probar, no como meta de un número
(que una línea se ejecute no quiere decir que esté bien probada). Se mide al armar la base de la
batería y otra vez después de graves y medianos.

## Paso 7. Las 7 preguntas a lo que ya existe (en vez de repetir la auditoría)

Repetir la auditoría ahora daría lo mismo (el mismo código, leído igual). En cambio, las 7
preguntas del paso 1 se pasan, una herramienta por vez, a lo que ya está hecho, como pruebas que
quedan en la batería: encuentra lo que leer el código no ve y confirma (o descarta) los
"probable" de la auditoría. Orden: lo que más usa el usuario (chapa, piezas soldadas, pieza) y lo
que el mapa muestre sin pruebas. Auditoría de lectura otra vez, completa, antes de compartir
FreeWorks con amigos.

## Paso 8. Pruebas adversariales (decidido por el usuario el 08/11, después del video "Tus tests ya no bastan")

Idea: si la misma IA escribe el código y sus pruebas, las pruebas tienen sus mismos puntos ciegos
(pasó el 08/11: la prueba de `safe_ops` daba bien y el revisor encontró el caso de la transacción
abierta y vacía). Hacen falta pruebas hechas para **romper**, no para confirmar. En este orden:

1. **Propiedades de paneles** (lo primero: la mayoría de los errores de la auditoría están en
   paneles). Reglas que TODO panel cumple, con elecciones y valores al azar, aplicadas a la lista
   de paneles (uno nuevo entra agregándolo a la lista):
   - Cancelar: documento idéntico, sin pasos de deshacer nuevos ni restos (marcas, vista previa).
   - Aceptar: exactamente una operación y un paso de deshacer; deshacer vuelve, rehacer la trae.
   - Editar y Aceptar sin tocar nada: la pieza no cambia.
   - Guardar y abrir: igual y sin quedar "modificado".
   - Entrada inválida (cero, arista que no sirve, otro sólido): aviso en castellano; nunca error
     en inglés ni operación a medio hacer.
   - Otro comando con el panel abierto: se cancela de verdad.
   Lo que tiene su lógica en una función se prueba sin ventana (muchos casos); el panel en sí, con
   ventana, en un solo FreeCAD (decenas de casos por panel en una corrida de noche). Las 6
   herramientas con la lógica dentro del panel solo por ventana (motivo más para pasarlas a
   funciones cuando se toquen).
2. **Propiedades de geometría** con medidas al azar (herramienta Hypothesis, en la carpeta de
   herramientas): marcos cerrados sin hueco ni superposición con cualquier esqueleto y perfil;
   chapa (el DXF cuadra en área y capas con la chapa); multicuerpo; Mover cara; croquis (sin
   relaciones redundantes); Evaluar (un cubo L×A×H da ese volumen y esa masa).
3. **Fuzzing de secuencias** ("mono"), de noche: operaciones al azar en cualquier orden (abrir un
   panel, cancelar, deshacer, Ecuaciones con el panel abierto, suprimir, cambiar una medida,
   guardar y reabrir, configuraciones...) controlando después de cada paso: sin errores, pieza
   válida, deshacer vuelve exactamente al estado anterior, abrir no modifica. Es el tipo de error
   de #3, #11, #12, #13. Lo que encuentre, a las Issues.
4. **Fuzzing de campos** donde se escribe: medidas negativas, cero, enormes, "1,5", texto en un
   número, fórmulas rotas en Ecuaciones, celdas raras en la tabla de configuraciones.
5. **Agente atacante**: escribe pruebas a partir del QUE de cada herramienta, sin ver el código, con
   la tarea de hacerla fallar (además del revisor de cada entrega, que sí ve el código).

Fuzzing "clásico" (millones de casos por segundo buscando caídas): no, porque cada caso en FreeCAD
tarda de 0,1 a 2 s y las caídas serían de FreeCAD / OpenCASCADE (no arreglables acá; las reporta
el usuario).

## Paso 9. Lo que faltaba medir (08/11)

- **Todo `swui`**, no solo `swui/fork`: el usuario usa también lo del original (cinta, extruir desde
  croquis, planos, relaciones, textos). El mapa y las pruebas lo incluyen.
- **Capturas de referencia** (pruebas visuales): una captura aprobada de cada pantalla (cinta,
  paneles, árbol, croquis, a 1366 x 768) y la prueba avisa si cambió algo sin querer. No juzga si
  está bien: detecta cambios. Sirven también para la fase 6 (referencia para cuando no haya SW).
- **Tiempos máximos**: p. ej. un marco de 50 caños recalcula en menos de X s; abrir un ensamblaje
  de prueba en menos de Y s. Avisa si algo se vuelve lento (Issue #15).

## Orden propuesto

1. Pasos 1, 4 y 5 (son cortos), el esqueleto de la batería y el primer mapa (paso 6). HECHO 08/11.
2. Arreglar los 3 graves **usando** este método: cada arreglo con su pieza común y su prueba.
3. Los medianos, igual.
4. Pasos 7, 8 y 9, herramienta por herramienta (paneles primero); segundo mapa.
5. Auditoría completa antes de compartir con amigos.

## Límites (para no prometer de más)

- Lo que ninguna prueba automática cubre: **el parecido con SW** (las pruebas comprueban nuestras
  reglas, no que sean las de SW: siguen las pruebas con mouse contra SW y el ojo del usuario), **el
  aspecto** (las capturas detectan cambios, no juzgan), **la sensación de uso** (giro, resaltado,
  arrastrar, cantidad de clics), **errores de FreeCAD / SheetMetal / OpenCASCADE** (fase 6), **las
  piezas reales del usuario** (sus STEP y chapas) y **lo de afuera** (CypCut, la plegadora).
- La interfaz gráfica no se puede probar del todo sola (tampoco en la industria): siguen las
  pruebas con mouse, pero menos, porque la lógica ya viene probada.
- La batería atrapa errores de FreeWorks, no de FreeCAD; para eso está la fase 6.
- Cada herramienta nueva va a tardar un 20 a 30 % más.
