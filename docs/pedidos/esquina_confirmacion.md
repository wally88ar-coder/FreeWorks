# Esquina de confirmación estilo SW 2018 + fichas #111, #112, #113

Pedido del usuario (21/11). Lo trabaja un `/goal`. Análisis de SW (ayuda oficial 2018) en la sesión del
21/11: la esquina de confirmación (arriba a la derecha de la vista) aparece con un panel de operación
abierto (✓/✗), en el croquis (Salir del croquis / Cancelar croquis), editando una pieza en el ensamblaje
(volver al ensamblaje), con la chapa aplanada (Salir de aplanar), en bloques y en el formato de hoja
(planos). Aislar NO va en la esquina (barra emergente propia, ya hecha en FreeWorks).

## Decisiones del usuario (21/11, no cambiar)
- Esc dentro del croquis: **como SW, nunca sale del croquis**. Esc suelta la herramienta; con algo
  elegido, deselecciona; sin nada, no hace nada. Se sale con la esquina, la cinta, el panel o
  Insertar > Croquis. (Cambia lo que hoy prueba `editar_pieza_teclas`: actualizar esa prueba.)
- La barra "Editando pieza: X — Salir" **se reemplaza** por el ícono de la esquina.
- Casos anidados (p. ej. croquis abierto dentro de Editar pieza): **los decide el goal**, lo más parecido
  a SW 2018 según la documentación, y los anota en `docs/ESTADO.md` para que el usuario los revise.
- La batería completa con ventana se puede correr a cualquier hora (el usuario deja la PC libre).
- Fuera de alcance: planos (bloques, formato de hoja), tecla D.

## Orden
1. #113, 2. #111, 3. #112, 4. la esquina por partes (A a F). Cada parte con su commit, su prueba y las
7 preguntas (`docs/SIETE_PREGUNTAS.md`).

## Qué tiene que pasar

**#113 — Ctrl+Z editando una pieza:** Ctrl+Z (y Ctrl+Y) con la vista del ensamblaje al frente, después de
crear algo en la pieza editada, deshace (rehace) ese paso SIN el cartel nativo "Hay transacciones de
grupo... Sí/No/Abort", como SW. No se rompe #108 (el componente editado no se oculta). La prueba deshace
con el atajo real de la ventana (no con `ctrl_z(pdoc)`), para ver el cartel si aparece. Revisar también la
marca en el ícono del Extruir de Placa<1>. Si no tiene arreglo limpio sin tocar FreeCAD: anotarlo en
ESTADO.md y en la ficha con el motivo y seguir.

**#111 — Esc con una línea elegida:** con la línea elegida y un clic REAL en el panel Tareas (u otro
widget), Esc solo deselecciona; el croquis sigue abierto. Con la decisión de Esc, ningún Esc cierra el
croquis. La prueba simula el clic con eventos de Qt sobre el widget, no poniendo el foco por código.

**#112 — croquis con una línea sola:** un croquis abierto (línea suelta) no queda con ícono de error en
la pieza y no aparecen avisos repetidos "Extruir: Wire is not closed" mientras se arma otra operación.
Primero averiguar de dónde sale el aviso (ese croquis o el recálculo con el círculo a medio dibujar).

**A. Pieza común de la esquina** (`swui/fork/confirm_corner.py`, lógica en funciones públicas):
- Arriba a la derecha de la vista 3D de la ventana al frente; sin tapar el cubo de navegación de FreeCAD
  (al lado o debajo, lo que se parezca más a SW).
- Sigue a la ventana al frente (varias ventanas, dos documentos) y queda SIEMPRE encima de la vista
  (lección de #105: no fiarse de `isVisible()`).
- Muestra los botones de lo que esté abierto en ese momento; nada abierto = esquina vacía/oculta.
- Íconos propios (`tools/fork/make_icons_fork.py`), nada de Dassault; nombre en castellano al pasar el
  mouse.
- Opción "Habilitar esquina de confirmación" en las opciones de FreeWorks (encendida de fábrica); apagada,
  no aparece nada y todo lo demás funciona igual.

**B. ✓ / ✗ de cualquier panel abierto:** con un panel de Tareas abierto (nativo o de FreeWorks) aparecen
✓ Aceptar y ✗ Cancelar; hacen exactamente lo mismo que los botones del panel (mismo resultado, mismo paso
de deshacer). Si el panel no tiene Aceptar (solo Cerrar), solo se muestra lo que tenga.

**C. Croquis:** con un croquis abierto aparecen "Salir del croquis" (= cerrar el croquis guardando, igual
que la cinta) y "Cancelar croquis" (= descartar TODOS los cambios desde que se abrió; un croquis nuevo
desaparece; la operación que esperaba el croquis, p. ej. Extruir sin croquis, no arranca). También dentro
de Editar pieza. Ctrl+Z después de Cancelar no trae nada raro.

**D. Volver al ensamblaje:** editando una pieza aparece el ícono de volver al ensamblaje; hace lo mismo
que el "Salir" de la barra actual, que desaparece. Lo que hoy prueba la barra (sigue la ventana al
frente, queda encima de la vista, #105) pasa a probarse sobre la esquina.

**E. Salir de aplanar:** con la chapa aplanada (`sheet_panels.toggle_flat`) aparece "Salir de aplanar";
vuelve a la chapa plegada igual que el botón de la cinta. Por documento: en otra ventana no aparece.

**F. Anidados:** cuando hay más de un modo a la vez (croquis o panel dentro de Editar pieza, croquis con
la chapa aplanada...), lo decide el goal y lo anota.

## Al terminar
Fichas cerradas con "Arregla #N" (o anotadas como no resolubles), batería completa toda BIEN después del
último commit de código, push, ESTADO.md + CHANGELOG + checklist al día separando lo probado de lo "sin
probar", capturas nuevas en `capturas/nuevas/` esperando aprobación del usuario. La prueba con el mouse
contra SW queda para después (la decide el usuario).
