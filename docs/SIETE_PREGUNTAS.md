# Las 7 preguntas a las herramientas que ya existen (plan de calidad, paso 7)

Cada herramienta de FreeWorks se pasa por las 7 preguntas de `CLAUDE.md` ("Calidad"). Este cuadro
dice **qué prueba automática contesta cada pregunta hoy** y qué falta. Armado el 09/11/2026 mirando
las pruebas de `tools/fork/pruebas/` (no el código de las herramientas).

Las preguntas:

1. **Cancelar.** ¿Y si cancelo?
2. **Deshacer.** ¿Deshago y rehago?
3. **Medida anterior.** ¿Cambio una medida de algo anterior y recalculo?
4. **Guardar.** ¿Guardo, cierro y abro, sin que quede "modificado"? ¿Abre sin FreeWorks?
5. **Otra herramienta.** ¿Abro otra herramienta con el panel abierto?
6. **Dos archivos.** ¿Y con dos archivos abiertos?
7. **Algo raro.** ¿Elijo algo raro, o escribo algo raro?

Abreviaturas de las pruebas:

- **R**: reglas de paneles (`prueba_ventana_reglas_*`). Cubre cancelar, inválido, otro comando, aceptar con Ctrl+Z/Ctrl+Y, editar, editar cambiando un valor y guardar.
- **M**: el mono (`prueba_ventana_mono*`). Hace secuencias al azar y abre Ecuaciones o Material con el panel abierto.
- **A**: medidas al azar (`prueba_*azar_*`).
- **C**: fuzzing de campos (`prueba_ventana_campos_*`, `prueba_azar_campos_ecuaciones`).
- **SF**: abrir sin FreeWorks (`prueba_guardar_sin_freeworks`).
- **—**: ninguna prueba contesta esa pregunta todavía.

## Cuadro

| Herramienta | 1 Cancelar | 2 Deshacer | 3 Medida anterior | 4 Guardar | 5 Otra herramienta | 6 Dos archivos | 7 Algo raro |
|---|---|---|---|---|---|---|---|
| Redondeo, Chaflán, Ángulo de salida | R M | R M | — | R M | R M (#3) | — | R C |
| Matriz lineal y circular, Simetría | R M | R M | — | R M | R M (#3) | — | R C |
| Plano, Eje, Punto | R M | R M | — | R M | R M (#3) | — | R C |
| Extruir, Extruir corte, Revolución | R | R | — | R | R | — | R C |
| Taladro | R | R | — | R | R | — | R C |
| Mover cara (equidistanciar, trasladar, girar) | R M | R M | — | R M | R M (#3) | — | R A C |
| Combinar, Mover/Copiar y Eliminar/Conservar sólidos | R M | R M | — | R M | R M (#3) | — | R C |
| Alcance multicuerpo (Fusionar resultado) | — | — | A | — | — | — | A (#1, #42) |
| Brida base, Brida de arista, Dobladillo | R M | R M | M (editar el espesor) | R M | R M (#3) | — | R A C |
| Corte desdoblado | R | R | — | R | — | — | — |
| Desplegar / plegar, Exportar DXF | M | — | — | M | — | — | A |
| Miembro estructural, Esquinas, Cartela, Tapa | R M | R M | M A (#2) | R M SF | R M (#3, #6) | — | R C (#19) |
| Lista de cortes | — | — | M A | — | — | — | — |
| Relación de posición, Matriz de componentes, Plano/Eje/Punto de ensamblaje | R M | R M | M (medida de la pieza) | R M | R M (#3) | sí (son varios archivos) | R C |
| Taladro y Extruir corte de ensamblaje | R M | R M (#37) | — | R M (#38) | R M (#3) | sí | R C |
| Suprimir componente | M | M | — | M | — | — | — |
| Herramientas de entidades del croquis (7) | R M | R M | — | R M | R M | — | R C (#41) |
| Croquis 3D, Elegir plano del croquis | R | R | — | R | R | — | R |
| Convertir a chapa, Vista de sección | R | R | — | R | R | — | R |
| Agregar configuración / pasar de una a otra | R M | R M (#47) | A | R M A | R M (#3) | — | C |
| Ecuaciones | — | — | — | — | (es "la otra" en M) | — | C (#45, #46) |
| Material, Propiedades físicas | — | — | — | — | (es "la otra" en M) | — | A |
| Suprimir operación (árbol) | M | M | — | M | — | — | — |
| Hélice, Barrido, Recubrir (paneles nativos con términos SW) | R | R | — | R | R | — | R |
| Clic derecho como SW (15/11; `prueba_ventana_clic_derecho_sw`, `prueba_clic_derecho_tabla`) | Esc: no toca el documento | no cambia nada (solo ordena acciones) | no aplica | no guarda nada | croquis en edición: menú de FreeCAD sin tocar | pieza y ensamblaje abiertos a la vez | Cuerpo, vacío, dos caras, croquis |
| Editar pieza en el ensamblaje (D, 15/11; `prueba_ventana_editar_pieza`) | Salir sin cambios vuelve todo como estaba | croquis nuevo en la pieza: Ctrl+Z en el ensamblaje lo deshace y se sigue editando | — | guardar editando: sin la transparencia en el archivo y sin "modificado"; guardar pregunta por la pieza y Sí la guarda | Editar operación / croquis desde la cara (panel de la pieza dentro del ensamblaje) | pieza y ensamblaje: dos documentos | copia de pieza con configuraciones (misma y otra), cerrar editando, dos componentes (sin Editar pieza) |
| Editar pieza: Croquis / Extruir / Corte en una cara (#95, 16/11; `prueba_ventana_editar_pieza_cara`) | panel sin nada elegido: Cancelar no deja nada; salir de Editar pieza con el croquis del corte abierto: el corte no arranca | Ctrl+Z en el ensamblaje saca el corte y el croquis, y se sigue editando | — | — (sin cambios al guardar: lo cubre la prueba de la etapa D) | — | pieza y ensamblaje: dos documentos; la misma pieza dos veces en el ensamblaje | cara del otro componente (va a lo nativo), cara nombrada por el Cuerpo (se apoya en la Punta), cara curva (lo nativo, como en la pieza), croquis viejo en la cara (no se mueve) |
| Editar pieza = pieza, todos los botones (17/11; `prueba_ventana_editar_pieza_botones`) | cada botón se acepta o se cierra en los dos modos y se compara | Cuerpo nuevo: Ctrl+Z en el ensamblaje (`prueba_ventana_contenedor_pieza`) | — | abrir una soldadura no la cambia ni la guarda (#97) | Ecuaciones con un archivo cerrado (#99) | pieza + ensamblaje en cada caso | nada / cara / arista para cada botón; Taladro con arista (#98) |
| Top-down: croquis, Convertir entidades, Hasta la superficie con otro componente (17/11; `prueba_ventana_editar_pieza_topdown`) | croquis vacío: no queda ni la referencia externa | — | el otro componente y la pieza editada se mueven: lo sigue | — | — | dos piezas + ensamblaje | arista del otro con Croquis (nada propio) |
| Top-down: aristas y vértices de otro componente en cualquier herramienta del croquis (18/11, paso 4; `prueba_ventana_croquis_arista_otro_componente`) | Línea + clic en el vértice del otro + Esc: no queda ni la geometría externa ni la copia | Ctrl+Z saca la referencia entera (copia incluida); la arista propia en otro paso | el otro componente se mueve: la referencia lo sigue | — (sin prueba propia; la copia es una Referencia externa nativa, como en Convertir entidades) | — | pieza editada + otra pieza + ensamblaje | el mismo clic dos veces no duplica; arista de la propia pieza con el componente movido; croquis fuera de un Cuerpo: no se ofrecen (sin prueba) |
| Editar pieza con el componente fuera del origen (#100, 18/11; `prueba_ventana_editar_pieza_coordenadas`) | — | — | componente movido y girado; pieza nueva vacía y después su primera operación | — | Propiedades físicas abiertas sobre el ensamblaje: solo se corre lo de la pieza editada | ensamblaje + pieza + otra pieza | pieza vacía (sin forma) |
| Teclas editando una pieza (18/11; `prueba_ventana_editar_pieza_teclas`) | Esc con Redondeo abierto: cancela sin dejar nada, en la pieza sola y editando | — | — | — | Espacio abre y cierra Medir con la pieza editada | ensamblaje + pieza | Esc con un croquis abierto sin herramienta: lo mismo en los dos modos |
| Cuerpo nuevo al contenedor de la pieza (hallazgos 12 y 2 de las revisiones, 18/11; `prueba_ventana_contenedor_deshacer`) | — | un solo Ctrl+Z lo borra (mismo paso que lo crea); Ctrl+Y lo trae adentro y no abre un paso nuevo (no se pierde lo que queda por rehacer) | — | — | — | — | — |
| Primer arranque de una instalación nueva (#101, 18/11; `prueba_ventana_primer_arranque`) | — | — | — | la configuración queda con FreeWorks, castellano y sin barras de FreeCAD después del asistente | — | — | configuración con inglés ya elegido: no se toca |
| Clic derecho con varias operaciones (E2, 15/11; `prueba_ventana_clic_derecho_operaciones`) | Configurar operación (tabla): Cancelar no cambia | Suprimir dos (árbol y vista): UN paso, Ctrl+Z vuelve las dos; Configurar dos: un paso | — | guardar, cerrar y abrir sin "modificado" | — | — | operación + croquis y dos Cuerpos: menú general; dos caras de la misma operación; cara por el Cuerpo o por la operación |
| Clic derecho con varios componentes (E1, 15/11; `prueba_ventana_clic_derecho_varios`) | Configurar (tabla): Cancelar no cambia; Relación de posición: Cancelar no deja paso abierto ni relación | Suprimir, Fijar y Configurar dos: UN paso, Ctrl+Z vuelve los dos; Material: un paso en cada pieza | — | guardar, cerrar y abrir: nada del menú en el archivo; Aislar dos sin "modificado" | — | Material con piezas de dos archivos | dos caras del mismo componente, componente + relación (menú general), componente repetido (Abrir pieza una vez), uno suprimido y otro no |
| Herramientas del clic derecho (15/11; `prueba_ventana_herramientas_clic_derecho`) | Propiedades: Cancelar no cambia | renombrar y Propiedades: un paso, Ctrl+Z; Ctrl+Z no desarma Aislar | — | guardar aislado: el archivo con todo como antes; Guardar una copia no marca guardado | — | aislar en un documento no toca el otro (barra por documento) | nombre vacío, cara curva al DXF, aislar dos veces, cerrar aislado |
| Ctrl+Z / Ctrl+Y editando una pieza sin la pregunta de FreeCAD (#113, 21/11; `undo_route`; `prueba_ventana_editar_pieza_deshacer_desparejo`, `..._deshacer_cartel`, `..._deshacer_cartel3`) | — | pasos propios de la pieza o del ensamblaje más nuevos, desde la vista del ensamblaje y desde la de la pieza: de a un paso, sin cartel, vuelve al principio y Ctrl+Y rehace todo | Modificar cota (doble clic) en el medio (`..._cartel3`) | — (no cambia archivos) | — | ensamblaje + dos piezas abiertas (archivos de paso6 desde el disco) | Ctrl+Z hasta vaciar la pila (el principio) |
| Esc nunca sale del croquis (#111, 21/11; `first_run`; `prueba_ventana_croquis_esc_linea`, `prueba_ventana_primer_arranque`) | Esc con herramienta: la suelta; con algo elegido: deselecciona; sin nada: no hace nada | — | — | preferencia de FreeCAD, una vez por configuración; destildar FreeWorks la devuelve | clic en la lista, un rótulo y el fondo del panel antes del Esc | — | editando una pieza (croquis en otro componente) |
| Reordenar arrastrando en el árbol (15/11; `prueba_ventana_arrastre_arbol`) | soltar donde no se puede: nada cambia | un paso, Ctrl+Z/Ctrl+Y | volumen igual tras reordenar | guardar y abrir conserva el orden | — | — | croquis (sigue de FreeCAD), dependencia, barra retrocedida |

## Lo que falta, por pregunta

- **3. Medida anterior:** falta en las operaciones de pieza. Hay que cambiar el largo del cubo de
  base, recalcular y ver que el redondeo o la matriz sigan sanos. Se agrega al mono como acción
  "medida_base", para pieza y multicuerpo.
- **4. Abrir sin FreeWorks:** hoy solo se prueba con el marco soldado. Se agrega a la regla
  "guardar" de las reglas de paneles: el archivo guardado no tiene que guardar objetos de Python
  de FreeWorks (`swui.` en `Document.xml`). Así se controla en unos 50 paneles.
- **5. Otra herramienta:** el mono abre Ecuaciones y Material (#3). Falta suprimir desde el árbol
  con un panel abierto (queda para una tanda siguiente).
- **6. Dos archivos:** falta en todo, salvo ensamblaje. Se agrega al mono como acción
  "otro_archivo": abre un segundo archivo, vuelve al primero y sigue trabajando. Después de cada
  paso controla que el otro archivo no haya cambiado.
- **Ecuaciones, Material y Propiedades físicas:** no tienen panel de Tareas. Sus preguntas 1, 2 y
  4 se contestan mejor con pruebas sin ventana por sus funciones, y quedan para el agente
  atacante (paso 8.5).

## Estado

- Pregunta 4 sin ventana: `prueba_azar_sin_freeworks.py` (09/11, bien): soldadas, configuraciones,
  ecuaciones, espejo, material y chapa abren sin FreeWorks.

- Cuadro armado: 09/11.
- Las tres pruebas nuevas, probadas con ventana el 09/11 (bien, y cada una falla si se rompe a
  propósito lo que controla): medida_base (pieza y multicuerpo) y otro_archivo (todos los
  entornos del mono), y abrir sin FreeWorks en la regla "guardar" de las reglas de paneles.
  Con esto, la columna 3 suma M en Redondeo/Chaflán/Ángulo, Matrices/Simetría, Plano/Eje/Punto,
  Mover cara y Combinar/sólidos; la 4 suma SF en todos los paneles con R; la 6 suma M en todo lo
  que tiene M.
