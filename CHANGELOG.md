# Änderungen / Changelog

Neueste Version oben. / Newest version first.

## Unveröffentlicht / Unreleased

**Fork (wally88ar-coder, español)**
- **Errores arreglados la noche del 11/11 (causa raíz):** #1 (multicuerpo y Simetría de sólidos
  borraban operaciones sin la pieza común: el sólido perdía lo anterior); #3 y #13 (Ecuaciones,
  Material, Suprimir, barra de retroceso, cotas con doble clic, configuraciones, agarraderas de
  plano, suprimir relación, reparar referencias y Ctrl+Q abrían su propio paso de deshacer y
  rompían el Cancelar del panel abierto: ahora todos usan `safe_ops.undo_step`/`begin_step`);
  #41 (Girar entidades del croquis: `Geometry.rotate` descarta el centro; ahora `transform`);
  #53 (lista de cortes: iguales en un solo renglón, agrupando con tolerancia y no por el valor
  redondeado); #61 era de la prueba (la punta de un caño redondo en ángulo no tiene vértice en el
  extremo: ahora se mide exacto). Encontrado detrás de #3: #76 (ensamblaje, conocido).
  Además: #42 (Alcance automático con Por todo: la forma del corte se leía en otras coordenadas
  y no llegaba a toda la pila); #36 (editar una operación y Ctrl+Z la dejaba oculta: el panel
  anotaba como "antes" la vista de edición; ahora vuelve a la vista normal antes de abrir su
  paso); #8 (Miembro estructural solo sobre líneas rectas, con aviso; antes salía un caño recto
  sobre un arco o error sobre un círculo); #50 y #51 (configuraciones: lista con rango exacto,
  sin "None" fantasma al deshacer; borrar la primera con una medida configurada ya anda);
  #6, #29 y #30 (paneles de soldadas, vista de sección, referencia de ensamblaje y Agregar
  configuración anotados en el guardia; las escuchas de soldadas ya no tocan un panel cerrado).
- **Tercera tanda (11/11):** #9 (Extruir corte de la pestaña Chapa: lo de "hasta el espesor"
  vale solo para el corte pedido; Cancelar ya no deja nada armado que cambie el próximo corte,
  ni uno que traiga FreeCAD al abrir un archivo o deshacer); #22, chapa: copiar y pegar una chapa
  con su desarrollo deja una copia independiente (el desarrollo se reconoce por su vínculo nativo).
- **#2 (soldadas, grave):** las esquinas a inglete y a tope siguen al esqueleto: la caja que corta
  cada punta se ubica con una fórmula nativa de FreeCAD sobre las dos líneas (también sin
  FreeWorks) y el caño se alarga de más para que la caja corte al ras (antes: números fijos y el
  marco quedaba con huecos o caños sobresalidos al cambiar una medida). #22, soldadas: las marcas
  de esquina y de recorte son vínculos a la Ruta del otro caño y los alargues van en cada operación
  (antes, nombres: una copia pegada apuntaba al original); los archivos anteriores se siguen
  entendiendo. Las esquinas de archivos anteriores siguen fijas hasta que se vuelvan a tratar.
  Tapas de extremo y cartelas nuevas también siguen a sus miembros (ancladas a la línea, con
  fórmula); las de archivos anteriores quedan fijas.
- **Decisiones del 11/11:** Ecuaciones como SW: una ecuación que se calcula bien pero con la que
  una operación no se puede construir se acepta, la operación queda con error en el árbol y el
  aviso dice cuál (antes se rechazaba); una fórmula mal escrita se sigue rechazando.
  #77 era de la prueba (el Ángulo de salida buscaba la cara en la operación nueva).
  #47: con configuraciones, la supresión de una operación nueva en las otras entra en el mismo
  paso de deshacer (Ctrl+Z la saca entera y Ctrl+Y la trae suprimida donde corresponde); rodeo
  a un error de FreeCAD 1.1.4 por el que una fórmula dejaba de seguir a la tabla tras Rehacer.
  #34: toda la interfaz trata de usted, como SW 2018 en castellano.
- **Segunda tanda de la noche del 11/11:** Ecuaciones "todo o nada" (#45, #46, #48, #49: una
  fórmula que FreeCAD no puede calcular se rechaza con aviso en castellano y deja todo como
  estaba; nombres que FreeCAD toma como unidad, como h o m, se rechazan antes de crear nada;
  1e400, inf y nan no son números, tampoco como valor de una configuración) y sin tocar los VarSets de datos de FreeWorks (#4); números
  argentinos con puntos de miles y nombres reservados de Windows (#54); datos guardados rotos
  se controlan al leerlos (#56); configuraciones: agregar, renombrar y borrar con la pieza en
  error (#55); Medir distancia máxima con un punto en el eje de un círculo (#52, la parte de
  precisión sigue abierta); soldadas: Aceptar con un dato inválido deja el panel abierto con el
  aviso (#19), varias líneas elegidas de una (recuadro) se suman todas en vez de anularse,
  Aceptar enseguida de cambiar la medida usa la medida nueva (#7), alargue de un
  miembro editado a mano (#23); taladro y corte de ensamblaje encuentran la pieza por su
  componente y no por el nombre interno del documento (#5).
- **Forma de trabajar para cometer menos errores** (plan de calidad, `docs/PLAN_CALIDAD.md`):
  piezas comunes para las tareas delicadas (`swui/fork/safe_ops.py`: borrar una operación,
  paso de deshacer que no rompe el Cancelar de un panel, escuchas que no actúan al abrir o
  deshacer, abrir paneles anotados en el guardia, referencias a otro documento por su archivo);
  batería de pruebas automáticas (`tools/fork/pruebas/`, rápida sin ventana y completa con
  ventana) que corre sola antes de cada commit (`tools/fork/hooks/pre-commit`); mapa de qué
  código no prueba nadie (`docs/MAPA_PRUEBAS.md`); los errores se registran en las Issues de
  GitHub. Todavía no cambia nada de lo que se ve: los errores de la auditoría siguen abiertos.
- **Reglas comunes de los paneles** (`tools/fork/pruebas/reglas_paneles.py`): 39 paneles probados
  con valores al azar en Cancelar, algo inválido, otro comando, Aceptar con Deshacer/Rehacer,
  editar y guardar. Encontró 5 errores nuevos (#31 a #35) y confirmó 3 de la auditoría. Segunda
  tanda: 48 paneles + 4 variantes, reglas de edición (cambiar y Cancelar / Aceptar) y Deshacer real
  del usuario; encontró #36 a #40. Los paneles de planos quedan para cuando se encaren los planos.
- **Pruebas con medidas al azar** (`tools/fork/pruebas/azar_comun.py` y `prueba_*azar_*.py`, con
  la herramienta Hypothesis): cientos de piezas inventadas comparadas con fórmulas de libro, en 4
  grupos. Operaciones de pieza por el panel (extruir, corte, revolución, redondeo, chaflán, taladro
  con Ø ISO 273, matrices, simetría, ángulo de salida); piezas soldadas (marcos al azar: sin
  superposición ni huecos, lista de cortes = largo real, editar el esqueleto = armar de cero:
  amplió el error #2, también a tope); chapa (el desarrollo da lo que da SW con el factor K; DXF);
  ensamblajes (relaciones con piezas giradas al azar, concéntrica, pieza fija, matriz de
  componentes, taladro de ensamblaje en una pieza girada). Cada grupo se comprobó rompiendo algo
  a propósito. Checklist de control de calidad: pestaña nueva en el documento de checklists.
- **Fuzzing de secuencias, "el mono"** (`tools/fork/pruebas/prueba_ventana_mono.py`):
  seguidillas al azar de Aceptar, Cancelar, suprimir, deshacer, rehacer y guardar-abrir sobre una
  pieza, controlando después de cada paso que todo quede como debe. Corridas largas, de noche.
  Ahora en 7 entornos (pieza, chapa, ensamblaje, soldadas, croquis, multicuerpo,
  configuraciones); encontró #43, #44 y #47.
- **Fuzzing de campos** (paso 8.4): Ecuaciones con textos raros (`prueba_azar_campos_ecuaciones.py`);
  encontró #45 y #46.
- **Agente atacante** (paso 8.5): 7 pruebas escritas sin ver el código
  (`prueba_azar_atacante_*.py`); encontró #48 a #54.
- **Pruebas con ventana que faltaban**: capturas de referencia de la cinta y de 6 paneles,
  fuzzing de campos en ~40 paneles, "dos archivos abiertos" y "cambiar una medida anterior" en
  el mono, y "abre sin FreeWorks" en la regla guardar de los paneles. Cada prueba de FreeCAD usa
  su propia carpeta de recuperación (una prueba cortada ya no deja la ventana de recuperación).
- **Arreglado (#58)**: la relación Coincidente / Distancia / Paralela entre dos caras planas que
  están a 90° no movía la pieza (error de FreeCAD); ahora la gira y quedan cara contra cara
  (solo si esa pieza no está sujeta por otras relaciones).
- **Arreglado (#60, en parte)**: cancelar Cartela (o cualquier panel de soldadas) sin cambiar nada
  dejaba abierto el paso de deshacer y lo próximo que se hacía se sumaba a él (error de FreeCAD);
  pieza común nueva `safe_ops.end_step`. El resto de los paneles se pasa a ella al tocarlos.
- **Lo que encontró la corrida de noche del 10/11, reproducido** (sin cambiar el programa): #66
  (croquis: Mover/Girar borran la cota "Equidistancia1" y las atadas quedan con error; prueba
  nueva `prueba_croquis_cota_atada.py`) y #68 (taladro de ensamblaje que no toca pieza: panel sin
  medida) quedan como conocidos; #65 y #67 eran de las pruebas (cerrados); #69 y #70 arreglados en
  las pruebas. El mono ya no cuenta como error nuevo lo que repite un objeto que ya estaba roto.
  Encontrados al reproducirlos: #74 y #75 (configuraciones), como conocidos. La batería completa
  encontró #59 por otro camino (Exportar DXF en vez de Aplanar antes de suprimir), también como
  conocido.
- **Más pruebas sin ventana**: fuzzing de campos en configuraciones, material y chapa (encontró #55),
  "abre sin FreeWorks" con todo lo que se arma por funciones, y el control de que los errores que
  las pruebas toleran sigan abiertos en GitHub.
- **Corrida de noche** (`tools/fork/pruebas/noche.py`), **tiempos máximos**
  (`prueba_azar_tiempos.py`), mapa de cobertura de todo FreeWorks y cuadro de las 7 preguntas
  (`docs/SIETE_PREGUNTAS.md`).
- **Sin el aviso "Referencia" de FreeCAD, como SW** (`swui/fork/cross_body.py`): elegir una cara o
  arista de otro sólido (piezas soldadas, multicuerpo) ya no pregunta "Hacer copia independiente /
  dependiente / referencia cruzada". La operación va al sólido de lo elegido (se activa solo, también
  desde el panel "elegí una cara" del Asistente para taladro, Croquis y Extruir; Redondeo, Chaflán y
  Ángulo de salida empezados en otro sólido se pasan solos); una referencia de otro sólido (plano de
  simetría, dirección de matriz, plano neutro, "Hasta la superficie"...) entra como copia dependiente
  oculta que sigue al original. Si el aviso aparece igual, se contesta solo. Lo que FreeCAD no
  permite (aristas de dos sólidos en un mismo redondeo; repetir en una matriz una operación de otro
  sólido) ahora se avisa en castellano en el panel en vez de ignorarse callado.
- **Croquis 3D, como SW 2018** (`swui/fork/sketch3d.py`, `sketch3d_panel.py`, `sketch3d_tab.py`):
  botón al lado de Croquis y en Insertar. Líneas en el espacio en cadena (clic o arrastrar), que
  enganchan a X, Y o Z, a puntos, al origen y a vértices de la pieza; Tab cambia el plano (Alzado,
  Vista lateral, Planta) y Ctrl + clic toma una cara o un plano; el largo se escribe mientras se
  dibuja y queda como cota (D1@Croquis3D1, visible en Ecuaciones). Relaciones A lo largo de X/Y/Z,
  Paralela, Igual y Fijar; líneas negras (definidas) y azules. Se edita con doble clic o con clic
  derecho > Editar croquis. Hecho con líneas nativas de FreeCAD
  atadas con fórmulas: abre sin FreeWorks. Solo líneas (sin arcos) y sin resolvedor libre.
  Después de la primera prueba del usuario: el largo se escribe en la misma cajita con cota gris
  que usa el croquis 2D; enganche a puntos más grande; arreglado el error "QListWidget already
  deleted" cuando FreeCAD cerraba el panel por su cuenta.
- **Piezas soldadas, como SW 2018** (`swui/fork/weldments.py`, `weld_panels.py`, `weld_tab.py`):
  pestaña nueva con Miembro estructural (caños, ángulos, planchuelas y UPN sobre un croquis
  esqueleto, con vista previa), Esquinas (a tope eligiendo cuál pasa, o inglete), Recortar/Alargar
  (contra otro miembro o una cara plana), Tapa de extremo, Cartela y Lista de cortes (largos,
  ángulos y peso; CSV para Excel o planilla para los planos). Todo con operaciones nativas de FreeCAD.
  Después de la prueba del usuario ("bug estructura"): Editar operación (clic derecho sobre la carpeta
  del Miembro estructural o un caño) reabre el mismo panel con todo editable, como SW: tipo, tamaño,
  líneas, giro, ubicación, simetría y esquinas; los caños se cambian en su lugar, sin borrarlos; las
  cajitas y listas de los paneles ya no cambian con la ruedita si no se hizo clic en ellas; en una
  esquina de tres caños, cambiar una esquina ya no acorta la punta que usa la otra. Arreglado: al
  pasar de inglete a tope desaparecían de la vista los caños que pasan ("bug estructura2").
  Perfiles según las tablas CIRSOC 301/302 (IRAM-IAS; `swui/fork/weld_profiles.py`, datos en
  `weld_cirsoc.py`, generados con `tools/fork/cirsoc_tablas.py`): caños cuadrados, rectangulares y
  redondos, ángulo, T, UPN, IPN, IPE, IPB, IPBI e IPBv (sin las series americanas), dibujados con sus
  radios (caños: 2 espesores afuera, 1 adentro) y alas inclinadas (IPN 14 %, UPN 8 % / 5 %, T 2 %).
  Cada miembro guarda las propiedades de sección de la tabla (área, peso, inercias, módulos, radios de
  giro, torsión, alabeo), visibles en Datos > Sección CIRSOC y listas para un futuro cálculo por
  elementos finitos. Los archivos viejos abren igual; al editar el miembro pasan al dibujo con radios.
  Esquinas a tope y T con corte plano, como SW: en los caños cuadrados y rectangulares el caño que
  llega se corta recto a ras de la cara del que pasa (antes copiaba el radio de la esquina y lo
  rellenaba); el caño redondo sigue con la boca de pescado y "Recortar/Alargar" contra un miembro
  sigue ajustando contra el sólido. En las esquinas a tope en ángulo (no a 90°), la punta del que
  pasa también se corta en ángulo al ras de la cara de afuera del otro (antes quedaba recta y una
  esquina sobresalía); comparado con SW 2018 a 60° y 120°: mismos largos y cortes (534,64 mm a 30° y
  488,45 mm a 30° con 40 x 40 x 2).
- **Arreglado: Vista de sección no se sacaba con el botón después de reconstruir la pieza.**
- **Barrita sobre la vista con Vista de sección y Estilo de visualización, como SW 2018**
  (`swui/fork/view_bar.py`, `section_view.py`). Vista de sección con panel SW (plano, invertir,
  distancia, giros, tapa pintada), solo en la vista; estilos sombreado con aristas, sombreado, sin
  líneas ocultas y estructura alámbrica.
- **Cinta de alto fijo, como SW 2018** (`swui/fork/ribbon_fixed.py`, `look_sw.py`): sin la línea azul
  para estirarla ni la franja gris debajo; queda con el alto mínimo.
- **Pestañas que se iluminan al pasar el mouse, como SW 2018** (`swui/fork/look_sw.py`): las de la
  cinta (Operaciones, Croquis...) y Modelo / Tareas / Configuraciones.
- **Ventana sin la barra de título de Windows, como SW 2018** (`swui/fork/frameless.py`): menús,
  acceso rápido, nombre del documento y minimizar / maximizar / cerrar en una sola franja. Arrastrar
  la franja mueve la ventana y el doble clic maximiza / restaura.
- **Clic sobre lo que ya está elegido lo suelta, como SW 2018** (`swui/fork/click_toggle.py`). Antes
  FreeCAD pasaba a elegir lo que lo contiene (plano -> Origen -> Cuerpo).
- **Esc deselecciona, como SW 2018** (`swui/fork/esc_deselect.py`): con algo elegido (plano, cara,
  arista, operación) en la vista 3D o en el árbol, Esc deja sin nada elegido. Con un panel abierto o
  editando un croquis, Esc sigue haciendo lo de siempre.
- **Arreglado: un clic en el fondo de la vista elegía un plano** (y clics seguidos alternaban plano
  y Cuerpo). El cuadrado de FreeCAD que queda escondido debajo del dibujo SW ya no se puede elegir;
  un plano se elige solo con un clic en su borde, como en SW (`swui/fork/plane_look.py`).
- **Agarraderas de los planos y nombres encima, como SW 2018** (`swui/fork/plane_handles.py`,
  `plane_look.py`). Un plano elegido muestra 8 agarraderas celestes; arrastrando una, el plano
  cambia de tamaño y desde ahí lo conserva (no vuelve al automático, como SW). Se guarda en la
  propiedad oculta `SWUI_PlaneRect` del plano, con Ctrl+Z / Ctrl+Y. Los nombres de los planos se
  dibujan siempre encima de la pieza. Pieza vacía: rectángulos de 178 x 110 mm en el origen, como
  SW. Arreglado: "Access violation" al tocar el ojo del origen (no se mueve más el dibujo de FreeCAD).
- **Planos dibujados como SW 2018** (`swui/fork/plane_look.py`, etapa B). Cada plano (los del origen
  y los de referencia) es un rectángulo azul fino alrededor de la pieza, agrandado 5 % por lado
  (medido en SW), en su lugar y siguiendo a la pieza al recalcular, con su nombre en el plano y del
  mismo tamaño en pantalla. Un clic en el borde lo elige como siempre. Solo dibujo: nada en el
  archivo; pieza sin sólidos: el dibujo de FreeCAD.
- **Planos principales como SW 2018** (`swui/fork/origin_planes.py`, relevado en SW con el mouse
  el 04/11). El ojo de cada plano, eje y punto del origen es el que manda: la carpeta se prende y
  apaga sola (antes, con la carpeta oculta, un plano con el ojo abierto no se veía). Pieza nueva
  con los planos ocultos, como SW; la carpeta se llama "Origen" y el punto "Punto de origen" (antes
  "Origen de Coordenadas001"). Un plano oculto elegido en el árbol se dibuja mientras está elegido.
  Ver > Ocultar/Mostrar > **Planos** (apaga el dibujo de todos sin cambiar lo de cada uno) y
  **Planos primarios** (muestra u oculta los tres). Al abrir un archivo, los ojos quedan como lo
  que se ve, sin marcarlo cambiado.
- **Pieza nueva sin nada elegido y Extruir con el Cuerpo elegido** (`swui/fork/auto_body.py`,
  reportado por el usuario el 04/11). FreeCAD dejaba elegido el Cuerpo recién creado y Extruir
  daba "El objeto seleccionado debe pertenecer al cuerpo activo". Ahora el Cuerpo nuevo no queda
  elegido y, como en SW, con el Cuerpo entero elegido Extruir / Cortar / Revolución / Croquis
  piden el plano o la cara.
- **Simetría de entidades del croquis como SW** (`swui/fork/sketch_entities.py`). El botón ya no
  está en gris sin selección: abre arriba del panel del croquis el recuadro "Simetría" (✓ / ✗,
  mensaje, Entidades a simetrizar, Copiar, Respecto a), se marcan las entidades con clics (otro
  clic la saca; Supr o clic derecho Borrar en la lista), vista previa amarilla al momento, Enter
  acepta y Esc cancela sin cerrar el croquis. Lo ya elegido antes de hacer clic entra a la lista.
  La copia queda unida al original con relaciones Simétrico (un punto por lugar; sobre la línea,
  coincidente), círculos iguales, sin relaciones redundantes. Por debajo, la función del croquis
  de FreeCAD (`addSymmetric`); la lógica se puede llamar sin panel: `mirror_entities`. También en
  Herramientas > Herramientas de croquizar > Simetría.
- **Mover, Copiar, Girar, Escalar, Matriz lineal y Equidistanciar entidades como SW**
  (`swui/fork/sketch_transform.py`, `swui/fork/sketch_offset.py`). Igual que Simetría: botones
  siempre activos, panel SW con los mismos grupos y casillas que SW 2018 (relevados con el
  mouse), entidades por clic, vista previa amarilla. Mover/Copiar: Desde/Hasta (Punto inicial
  enganchado a los puntos del croquis, clic de destino, el panel queda abierto, Repetir) o X/Y,
  y Conservar relaciones. Girar: centro y ángulo. Escala: punto, factor, Copiar y número de
  copias. Matriz lineal: dos direcciones (espaciado, Acotar espacio, cantidad, ángulo); las
  copias siguen al original (Igual). Equidistanciar: clic en una entidad toma la cadena, el lado
  sigue al mouse y otro clic termina; esquinas en punta, una sola cota (las demás atadas a ella),
  Invertir, Bidireccional, Tapas en extremos (arcos o líneas), geometría constructiva. Copiar
  entidades se suma al desplegable de Mover. Funciones públicas: `move_entities`,
  `copy_entities`, `rotate_entities`, `scale_entities`, `linear_pattern`, `offset_entities`.
  Pruebas sin interfaz: `tools/fork/test_sketch_entities.py`.
- **IA, etapa 0: el puente** (`swui/fork/ia/`). FreeWorks > IA > **Puente IA** (se tilda; arranca
  apagado) deja que la IA de tu suscripción (Claude Code primero) maneje FreeWorks por MCP, solo
  en esta PC (127.0.0.1:47115) y con clave; **Conectar la IA...** muestra la línea para conectarla
  y deja cambiar la clave. Herramientas: **estado** (documentos, árbol, selección, panel abierto),
  **captura** (vista 3D o ventana; queda anotado) y **ejecutar_python** (copia de respaldo, prueba
  en un FreeCAD aparte sin pantalla que corta los scripts que fallan o se cuelgan, y un solo paso
  de Ctrl+Z "IA: ..."; el script queda en la consola de Python). Código copiado, con su aviso, de
  neka-nat/freecad-mcp (cola al hilo principal, MIT) y ghbalf/freecad-ai (servidor MCP,
  LGPL-2.1+), en `swui/fork/ia/terceros/`. Aislada: nada de FreeWorks la importa salvo el
  enganche (lo verifica el test).
- **IA, etapa 1: toda la interfaz** (`swui/fork/ia/herramientas/`). Mirar la pieza por números
  y elegir caras o aristas por descripción (si hay más de una, pregunta); cambiar cotas,
  configuraciones, material y el árbol; crear piezas (croquis definido, extruir, cortar,
  revolución, redondeo, chaflán, matrices, simetría, taladro métrico); las operaciones cuyo
  trabajo está en el panel (mover cara, geometría de referencia, sólidos, chapa, taladro y corte
  de ensamblaje) se hacen en el panel en pantalla con el aviso "no toques el mouse" (un clic tuyo
  lo cancela sin aplicar); DXF de chapa; ensamblajes (insertar, relaciones SW que se verifican
  después de resolver, fijar, matriz y simetría de componentes); `pedido` deshace de una vez
  todo lo de un pedido.
- Puente IA: puerto exclusivo en Windows (otro programa ya no puede escuchar en el mismo).
- IA: **un solo respaldo por documento**, el de antes del primer cambio de la IA desde que
  guardaste; **al guardar se borra** (aceptaste lo que hizo la IA). Las consultas (`solo_leer`)
  no hacen copia, y si cambian algo se deshacen. El aviso "un paso de Ctrl+Z" sale solo cuando
  de verdad hubo cambios. Sin archivos .FCBak de más.

## 0.11.0 — 2026-11-01

Primera versión de FreeWorks (fork de LikeSolidWorks UI). / First FreeWorks release.

**Deutsch**
- Oberfläche auch auf **Spanisch** (`swui/lang/es.py`), Begriffe wie im
  spanischen SOLIDWORKS (Croquis, Extruir saliente/base, Relaciones de
  posición, Planta/Alzado/Vista lateral …).
- *Automatisch* nimmt FreeCADs Sprache, wenn es dafür eine Sprachdatei gibt
  (bisher nur Deutsch, sonst Englisch); erkennt auch „Spanish (Argentina)“.
- **Kleine Bildschirme:** Das Ribbon erzwingt keine Mindestbreite des
  Fensters mehr (bisher ~1460 px – bei 1366 px ragte das Fenster rechts
  über den Rand). Passt ein Reiter nicht, zeigen die großen Knöpfe nur das
  Symbol (Name im Tooltip, wie in SOLIDWORKS ohne „große Knöpfe mit
  Text“); reicht das nicht, erscheinen Pfeile zum Verschieben.
- Feature-Dialoge (Linear austragen, Verrundung …) wechselten in FreeCAD
  1.1.4 selbst zur Workbench Part Design – Ribbon weg, Dialog ohne
  SW-Begriffe. Sie bleiben jetzt in LikeSolidWorks UI.
- SW-Begriffe in den Dialogen auch unter Windows (Objektname dort
  `PartDesignGui__…` statt `PartDesignGui::…`).
- **Skizze / Linear austragen / Linearer Schnitt ohne Auswahl** wie in
  SOLIDWORKS: Ebene oder ebene Fläche im Grafikbereich, im Baum oder in
  der Liste wählen, die Skizze öffnet sich darauf; bei Austragen/Schnitt
  startet das Feature nach „Skizze beenden“. Bisher: FreeCADs Dialog mit
  nur den Ursprungsebenen (Flächen nicht wählbar), beim automatisch
  angelegten Körper noch mit FreeCADs Ebenennamen.
  Auch ein Körper von der Startseite („Plano XY“ …) bekommt beim Öffnen
  des Panels die SW-Ebenennamen; ein Klick in die Liste brach unter
  Windows mit „Access violation“ ab.
- `tools/test_load.py` läuft auch unter Windows (Pfadvergleiche).

**English**
- Interface also in **Spanish** (`swui/lang/es.py`), terms as in the
  Spanish SOLIDWORKS.
- *Automatic* uses FreeCAD's language whenever there is a language file for
  it (before: German, otherwise English); also recognises "Spanish (Argentina)".
- **Small screens:** the ribbon no longer forces a minimum window width
  (before ~1460 px – on 1366 px screens the window was cut off on the
  right). If a tab does not fit, the large buttons show only their icon
  (name in the tooltip); if that is still too wide, arrows appear to scroll.
- Feature dialogs (Extruded Boss/Base, Fillet …) switched to the Part Design
  workbench by themselves in FreeCAD 1.1.4 – ribbon gone, no SW terms. They
  now stay in LikeSolidWorks UI.
- SW terms in the dialogs also on Windows (object name `PartDesignGui__…`
  there instead of `PartDesignGui::…`).
- **Sketch / Extruded Boss / Extruded Cut without a selection** as in
  SOLIDWORKS: pick a plane or planar face in the graphics area, the tree or
  the list, the sketch opens on it; for boss/cut the feature starts after
  "Exit Sketch". Before: FreeCAD's dialog with only the origin planes (faces
  not selectable).
- `tools/test_load.py` also runs on Windows (path comparisons).

**Fork (wally88ar-coder, español)**
- **Barra de menús como SW 2018** (01/11, `swui/fork/menus_sw.py`): Archivo, Edición, Ver,
  Insertar, Herramientas, FreeWorks, Ventana y "?", con la estructura del SW real y solo lo que
  FreeWorks y FreeCAD tienen. Insertar y Herramientas en bloques Pieza / Ensamblaje / Plano /
  Croquis separados por líneas; lo que no corresponde al documento activo, en gris (en el croquis
  Pieza sigue activa). Las entradas hacen lo mismo que la cinta (Extruir sin selección pide el
  plano, etc.). Textos de SW en castellano también en los comandos de FreeCAD (se devuelven al
  salir del banco); Ctrl+W cierra y F11 es pantalla completa, como SW. Lo útil de FreeCAD sin
  equivalente en SW, en FreeWorks > FreeCAD (Gráfico de dependencias, Paneles, Apariencia,
  Engranaje...). Salida de emergencia: FreeWorks > FreeCAD > "Mostrar los menús originales de
  FreeCAD" (al reiniciar). El menú "FreeWorks" de antes se repartió en su lugar de SW.
- Con el panel "seleccionar un plano" abierto (Croquis / Extruir sin selección), otra operación
  desde la cinta o el menú (p. ej. Redondeo) lo cancela y arranca, como SW. Antes salía la
  pregunta de FreeCAD y quedaba un Redondeo vacío con error y la pieza oculta.
- Editar operación / Editar croquis (Edición > Definición, Edición > Croquis, clic derecho) con
  una cara elegida abren la operación que creó la cara, como SW (antes, la última del sólido).
- Archivo > Crear ensamblaje desde pieza mete la pieza en el ensamblaje nuevo, fija en el origen.
- "Close this dialog?" y el aviso de Volver a cargar, en castellano.
- Un croquis nuevo que se cierra sin dibujar nada se borra, como SW (`swui/fork/empty_sketch.py`;
  un paso de deshacer lo devuelve). Los que ya tenían algo, los del fork y los que usa una
  operación no se tocan. Dentro del croquis, Insertar > Croquis dice "Salir del croquis", como SW.
- La relación fija del primer componente dice "Fijo (Placa<1>)" (antes "Fijo (Body)").
- Sin avisos "Cannot find icon: TechDraw_..." al arrancar (los íconos de Dibujo de los menús, por ruta).
- Redondeo o Chaflán con el panel de otra operación abierto lo cancelan y arrancan callados (antes
  quedaba un redondeo vacío con el aviso en inglés "Fillet not possible on selected shapes").
- **Configuraciones como SW** (01/11, etapa 1 de 5: piezas): pestaña **Configuraciones** junto a
  Modelo y Tareas (como el ConfigurationManager): lista con la activa en negrita, doble clic =
  mostrar; clic derecho: Agregar configuración, Cambiar nombre (F2), Eliminar, Editar tabla de
  diseño. Con más de una configuración, la cajita *Modificar* de las cotas pregunta **Esta
  configuración / Todas las configuraciones** y *Suprimir* del árbol vale solo para la activa,
  como SW. Por debajo, la tabla de configuración nativa de la planilla de FreeCAD (sin Excel,
  decisión del usuario): el archivo cambia de configuración, guarda y abre sin el addon
  (`swui/fork/configurations.py`, `config_tab.py`).
- **Configuraciones en chapa** (01/11, etapa 2): Espesor y Profundidad de la Brida base
  aparecen como cotas con doble clic (se configuran igual que las otras); los paneles del fork
  cambian un valor atado a la tabla solo en la configuración activa; al cambiar de configuración
  el desarrollo vuelve a elegir su cara fija; **Exportar DXF** pregunta *Esta configuración /
  Todas las configuraciones* y el nombre lleva la configuración (`Soporte-3mm_3mm.dxf`)
  (`swui/fork/config_sheet.py`).
- **Configuraciones en ensamblajes** (01/11, etapas 4 y 5): al hacer clic en un componente (árbol
  o zona gráfica) aparece al lado del cursor una barrita con la **configuración** de su pieza,
  como la barra contextual de SW (también clic derecho > *Configuración del componente...*). Las
  relaciones de posición se vuelven a ubicar por geometría al cambiar de configuración y no
  quedan rotas al reabrir (error de FreeCAD con las copias del componente). Clic derecho >
  **Suprimir / Desactivar supresión** de componentes (oculta el componente y suprime sus
  relaciones). La pestaña Configuraciones también sirve en el ensamblaje: con varias, suprimir y
  elegir la configuración de un componente valen solo para la activa. El DXF por lotes de un
  ensamblaje saca uno por pieza y configuración usada (`swui/fork/config_asm.py`).
- **Configuraciones: arreglos de la prueba con mouse contra SW** (01/11):
  - Cada componente tiene su configuración, como SW: cambiar la configuración en la ventana de
    la pieza ya no cambia los componentes del ensamblaje (antes cambiaban todos, y también los
    configurados desde la barrita: FreeCAD volvía a copiar la pieza). Un componente nuevo nace
    con la configuración activa de la pieza.
  - Al cambiar de configuración, la chapa ya no muestra el error "Chapa desplegada1: Invalid
    shape name ?Face6" ni deja el contorno del desarrollo dibujado en 3D.
  - Se oculta la casilla "Suprimido" de FreeCAD en el clic derecho de una operación: repetía
    *Suprimir* pero salteaba las configuraciones (el árbol la mostraba gris y el agujero seguía).
  - La lista muestra la configuración activa en el título ("Placa Configuraciones (Larga)").
  - La barrita del componente se va sola al alejar el mouse, como la de SW.
  - La copia que FreeCAD guarda de un componente configurado ya no queda como "Cuerpo activo"
    del ensamblaje.
- **Configuraciones: lo que había quedado abierto** (01/11, tarde):
  - **Configurar operación** (clic derecho en una operación, como SW): tabla con una fila por
    configuración, "Suprimir" y las cotas de la operación, todo de una vez
    (`swui/fork/config_feature.py`).
  - La **configuración al lado del nombre** de cada componente en el árbol: "Soporte<2> (3mm)".
  - **Mover cara** con configuraciones: mueve la cara correcta en cada una (antes, con un largo
    muy distinto movía una cara de costado) y sin el error "Sub shape not found" al cambiar;
    suprimir una operación anterior (un agujero) ya no suprime el Mover cara.
  - Cambiar el **nombre** de una configuración de la pieza lo cambia también en los componentes
    y en la tabla del ensamblaje; **eliminarla** los pasa a la activa y avisa.
  - Taladro y corte de ensamblaje **saltean los componentes suprimidos** y, en un componente en
    otra configuración, agujerean la pieza de verdad (no la copia del ensamblaje).
  - Pieza **multicuerpo**: la tabla maneja las cotas de todos los sólidos; un componente de un
    sólido que no es el principal muestra la configuración activa de la pieza (no puede tener
    otra: límite de FreeCAD, ver NOTAS_TECNICAS).
  - Arreglos vistos con el mouse: con un componente elegido, el menú Archivo ya no queda en
    "Más opciones"; la barrita no aparece con el panel de relación de posición abierto; sin
    avisos de "cara cambiada" en las relaciones al agregar una configuración en la pieza.
  - Comparado con SW con el mouse (01/11, mediodía): F2 cambia el nombre ahí mismo en la lista
    (sin cuadro aparte); no se puede eliminar una configuración que usa un componente de un
    ensamblaje abierto (SW tampoco deja) y avisa cuál la usa; la ventana de Configurar
    operación se llama "Modificar configuraciones", como en SW.
  - Últimas pruebas con mouse contra SW (01/11, 12:40): Mover cara con configuraciones (la punta
    se corre igual en Predeterminado, Larga y sin el agujero), corte de ensamblaje (saltea el
    suprimido y corta la pieza real), DXF por lotes y pieza multicuerpo. Arreglado en el acto:
    el corte/taladro de ensamblaje no abría el croquis si había algo elegido antes (también
    otros paneles: el escucha se daba de baja solo); el desarrollo de chapa ahora reelige su
    cara fija después de cualquier cambio de la pieza ("?Face6"); el DXF por lotes ya no repite
    el mismo archivo ni incluye componentes suprimidos.
- **Configuraciones: más como SW** (01/11, decisión del usuario "Como en SW"):
  - Una **operación nueva** queda suprimida en las otras configuraciones (como la opción de SW
    "Suprimir operaciones nuevas"); con una sola configuración no cambia nada.
  - *Modificar* de las cotas tiene la tercera opción **Especificar las configuraciones...** con
    la lista para tildar.
  - Lista de configuraciones y la de la barrita del componente en **orden alfabético**.
  - La barrita del componente pide **confirmar con un tilde**, como la barra contextual de SW.
  - **Agregar configuración** es un panel a la izquierda (Tareas), como el PropertyManager.
  - Sin avisos de "relación corregida" al cambiar de configuración (quedan en el informe).
  - Probado con el mouse contra SW: asistente para taladro de ensamblaje y Propiedades físicas
    con un componente suprimido (los dos lo dejan afuera, igual que SW).
  - Un componente suprimido se ve con **todo el renglón en gris** en el árbol, como SW.
  - Con una sola configuración la **tabla de diseño no aparece en el árbol** (suprimir un
    componente la arma por dentro, SW no muestra ninguna); con dos o más configuraciones aparece.
- **Decisiones del usuario del 31/10** (checklist):
  - Nombre visible **FreeWorks** (menú y lista de bancos; lo interno no cambia, los
    archivos y la configuración abren igual) (`swui/fork/brand.py`). Paquete (package.xml) y
    repositorio en GitHub: **FreeWorks** (https://github.com/wally88ar-coder/FreeWorks).
  - Chapa: espesor 2 mm y largo de brida 20 mm **siempre** al empezar; nombres como el SW
    2018 del usuario: *Brida base1*, *Brida de arista1*, *Chapa desplegada1* (los croquis
    del desarrollo ya no se rehacen en cada recálculo pese al espacio en el nombre). El DXF
    **pregunta antes de pisar** un archivo; el DXF por lotes pregunta una vez por los que
    ya existen y **ya no deja desarrollos agregados** en las piezas.
  - Evaluar: **sin material, densidad 0** (masa 0 y aviso; el centro sale del volumen).
    Propiedades físicas arranca **sin los sólidos ocultos**, como SW 2018. *Ecuaciones*
    siempre en la franja del árbol.
  - Ecuaciones **no modal**: con la ventana abierta se gira la vista, doble clic en una
    cara muestra sus cotas y **un clic en una cota la inserta**, como SW. **Comentarios en
    todas las filas** (los de las ecuaciones van en el objeto *Variables globales*).
  - Mover cara: **condición final** de Trasladar como SW (*Hasta el vértice, Hasta la
    superficie, Equidistante de la superficie, Hasta el sólido*); **Girar alrededor de
    cualquier eje paralelo a la cara** (arista de otra cara o pieza, eje de referencia);
    **Equidistanciar caras cilíndricas** enteras (agrandar o achicar un agujero o un eje).
    Todo con operaciones nativas (Extruir/Cortar hasta cara, Ángulo de salida, Revolución /
    Ranura) y auxiliares ocultos fuera del árbol. Si la pieza cambia y el giro con eje fuera o
    el agujero quedan atrasados, **avisa** (cartelito y "⚠ desactualizado: Ctrl+Q" en el árbol)
    y **Ctrl+Q** los pone al día (`swui/fork/rebuild_keys.py`), también en cadena con un solo
    Ctrl+Q. Si un Mover cara **pierde su cara** (FreeCAD renumeró las caras) avisa en vez de
    quedar sin hacer nada. El aviso se actualiza también al deshacer y rehacer.
  - Mover cara "Equidistante de la superficie" queda siempre del lado de la cara (antes podía
    quedar del otro lado de la superficie). Los croquis del desarrollo de una chapa ya no caen
    en otro documento abierto. Los auxiliares ocultos tampoco se ven dentro del Cuerpo en el
    árbol. El menú dice FreeWorks también después de abrir un ensamblaje.
  - Aplanar una chapa ya no muestra el aviso en inglés de SheetMetal "Link(s) to object(s)
    'Bend' go out of the allowed scope 'Unfold'" (el desarrollo apunta al Cuerpo). Mover cara
    "Hasta el vértice": un clic en una arista toma su punta más cercana al clic, y cambiar de
    vértice ya no muestra el aviso en inglés "subshape not found Enlace.?Vertex1".
  - Mover cara > Girar: ya no gira mal ni falla según el sentido. Era un error de FreeCAD en el
    Ángulo de salida (en el primer cálculo usa una ubicación vieja y corre la bisagra); el fork
    le da la ubicación correcta antes de calcular y avisa "desactualizado: Ctrl+Q" si después
    cambia. Si la cara de verdad atravesaría la pieza, lo dice; si FreeCAD la deja sin girar,
    también.
  - Mover cara vuelve a encontrar solo lo que FreeCAD pierde al cambiar la pieza (como las
    relaciones de posición): la cara que mueve, la bisagra, el destino y el eje, también en otras
    piezas. Si la cara quedó partida, mueve todos los pedazos. Avisa qué corrigió.
  - Campos numéricos como SW: un clic marca todo el valor y lo escrito lo reemplaza
    (`swui/fork/spin_select.py`). Ecuaciones no lista el largo de un corte "Por todo".
  - Ecuaciones: las cotas a la vista se actualizan después de cada ecuación y al Cancelar; no
    lista el largo sin uso de un Mover cara "Hasta la superficie". El árbol flotante ya no
    muestra los auxiliares ocultos.
- **Aspecto claro de SOLIDWORKS 2018** (colores medidos en capturas): cinta y paneles
  #F7F7F7, pestañas #D4D4D4, fondo degradado gris-celeste a blanco; croquis en azul puro
  (líneas 2 px, constructivas 1 px trazo y punto), resaltado naranja, aristas negras 1 px.
- Sin las barras Archivo y Editar (nuevo/abrir/guardar, deshacer/rehacer/recalcular):
  quedan los menús y los atajos de teclado. En su lugar, **íconos de acceso rápido** en la
  barra de menú (Nuevo, Abrir, Guardar, Deshacer, Recalcular), como en la barra de título
  de SW 2018.
- Panel izquierdo como en SOLIDWORKS: **Modelo y Tareas en pestañas** sobre fondo gris
  claro (el árbol ya no flota sobre la vista 3D); al abrir una operación pasa solo a Tareas
  y al cerrarla vuelve al árbol.
  Vista de informe abajo y **oculta** (se abre con Ver → Paneles → Vista de
  informe); dentro de LikeSolidWorks UI no se abre sola ante avisos/errores.
  Código propio del fork en `swui/fork/`.
- **Usar siempre LikeSolidWorks UI** (menú *LikeSolidWorks UI*, con tilde): FreeCAD
  arranca en LikeSolidWorks UI, vuelve a él si algo cambia de banco (por ejemplo
  "Cuerpo paramétrico" o "Ensamblaje" en la página de Inicio) y oculta el selector de
  bancos. Desmarcado, todo vuelve a ser como en FreeCAD.
- **Velocidad de giro** con la ruedita del mouse (menú *LikeSolidWorks UI →
  Velocidad de giro…*): x1 (como FreeCAD), x1,5 (de fábrica), x2, x2,5. Medido a
  1366 px: x1 = 16°, x1,5 = 25°, x2 = 35° por cada 100 px de arrastre.
- **Teclas N y F** como en SOLIDWORKS: **F** ajusta y centra todo, al instante (sin la
  animación de FreeCAD ni la espera por el atajo "F, S" del filtro de caras, que se quita
  dentro de LikeSolidWorks UI); **N** = *Normal a*, con animación:
  con una cara plana o un plano seleccionado lo mira de frente (otra vez N: del otro
  lado), editando un croquis mira el croquis de frente, y sin selección gira a la vista
  estándar más cercana. El "arriba" queda derecho. En un campo de texto la letra se
  escribe normalmente. Solo dentro de LikeSolidWorks UI (`swui/fork/view_keys.py`).
- Panel para elegir plano: los planos de un cuerpo creado desde la página de Inicio
  también se llaman Planta / Alzado / Vista lateral.
- **Árbol de operaciones como el FeatureManager de SW (etapa A)**. Clic derecho sobre una
  operación (en el árbol o sobre una cara), arriba de todo: *Editar operación*, *Editar
  croquis*, *Suprimir* (también lo que depende de ella, como en SW), *Desactivar supresión*
  (con o sin dependientes), *Retroceder* (la barra queda justo antes de la operación),
  *Avanzar*, *Avanzar hasta el final* y *Padre/Hijo…*. Por debajo, la "punta" del cuerpo y
  la supresión nativas de FreeCAD; se puede deshacer. "Toggle Freeze" se oculta del menú:
  en 1.1.4 cuelga FreeCAD al guardar.
- **Ctrl+B** reconstruye y **Ctrl+Q** fuerza la reconstrucción de todo; si quedan errores
  se abre **¿Qué es incorrecto?** (también en el menú *LikeSolidWorks UI*), con el
  mensaje de FreeCAD explicado en palabras simples. Dentro de LikeSolidWorks UI, Ctrl+B
  deja de ser el zoom de ventana de FreeCAD.
- **Barra espaciadora = Medir** (como la tiene el usuario en su SW). Dentro de LikeSolidWorks
  UI deja de ser "Alternar visibilidad" de FreeCAD (ocultar sigue en el clic derecho).
- Al crear un cuerpo, el árbol muestra abiertos el cuerpo y su Origen (Planta, Alzado,
  Vista lateral a la vista). Al guardar una pieza retrocedida, aviso con *Avanzar hasta el
  final y guardar*. Código en `swui/fork/feature_tree.py`, `rebuild_keys.py` y
  `tree_dialogs.py`.
- **Árbol, etapa B**: **barra de retroceso** amarilla debajo de la última operación, que
  se arrastra con el mouse (manito) como en SW; lo que queda debajo se ve **en gris**, y lo
  suprimido también. Clic derecho *Mover arriba* / *Mover abajo* (con su croquis); si
  rompería una dependencia, avisa por qué no se puede. Al elegir una cara en la vista, la
  operación que la creó se marca en el árbol **como en SW 2018: fondo celeste con borde
  azul** sobre ícono y nombre, y la última operación (que FreeCAD selecciona porque es la
  que se ve) ya no aparece resaltada: queda una sola marca, como en SW. Elegir en el árbol
  también se ve en celeste con borde y texto oscuro (antes azul fuerte con letra blanca). Menú *LikeSolidWorks UI → Guardar también STEP* (apagado de fábrica):
  al guardar deja al lado un `.step` con el mismo nombre, como resguardo sin historial.
  Código en `swui/fork/tree_overlay.py` y `step_copy.py`.
- **Aristas y vértices del modelo dentro del croquis, como en SW**: con una herramienta
  activa (cota inteligente, relaciones, línea, círculo…), al pasar el mouse a menos de 10 px
  de una arista o vértice de la pieza se **resalta en naranja** (primero vértices); al hacer
  clic se trae sola como referencia (lo mismo que *Convertir entidades*) y el clic cae justo
  sobre ella: la cota o la línea quedan enganchadas aunque no se apunte exacto. También una
  arista que coincide con un eje del croquis (gana la arista, como en SW). **Sin herramienta**
  (seleccionando) también: elegir un punto del croquis y después una arista del sólido la
  suma a la selección, y el panel *Agregar relaciones* ofrece *Sobre entidad*. Antes había que
  traerla a mano; FreeCAD 1.1.4 no deja tocar el modelo desde el croquis. No trae aristas de
  operaciones posteriores al croquis. Desde FreeCAD 26.3, que ya lo hace, queda lo nativo
  (`swui/fork/sketch_model_edges.py`).
- Árbol: un croquis suelto debajo de la última operación ya no aparece en gris (solo lo que
  queda debajo de la barra).
- **Mover arriba / abajo con redondeos y chaflanes en el medio**: FreeCAD los apoya en el
  sólido anterior por número de arista, y al cambiar el orden esos números cambian (el
  redondeo quedaba en otra arista sin avisar, o con error). Ahora se vuelven a buscar las
  mismas aristas por su forma, como en SW. El padre de un redondeo es la operación que creó
  sus aristas (no la de justo arriba): ya se puede mover un redondeo por encima de un corte
  que no lo afecta. Si después de mover algo queda con error, avisa y ofrece deshacer.
- **Cotas con doble clic (estilo Instant3D)**: doble clic en una operación o croquis del
  árbol, o en una cara de la pieza (la operación que la creó), muestra sobre el modelo sus
  cotas con líneas y flechas: las del croquis (distancias, Ø, R, ángulos) y las de la
  operación (profundidad, radio de redondeo, distancia de chaflán, ángulo de revolución).
  Clic en un valor abre **Modificar** (✓, ✗, ↻ reconstruir; acepta "12,5"); se puede
  deshacer. Las cotas atadas a una ecuación se marcan con Σ. Esc o un clic en otro lado las
  esconde. Como en SW, el doble clic ya no abre el diálogo: para eso, clic derecho → *Editar
  operación* (`swui/fork/instant_dims.py`). **Croquis, como en SW 2018: un clic** en el árbol
  (también en los que están adentro de una operación) muestra sus cotas y se pueden cambiar;
  el doble clic abre el croquis.
- **Reparar referencias…** (menú *LikeSolidWorks UI*, botón en "¿Qué es incorrecto?" y clic
  derecho de una operación con error): lista los croquis/planos que perdieron la cara donde
  se apoyaban, los redondeos/chaflanes que perdieron aristas y los croquis con referencias
  del modelo perdidas. Si hay una sola cara plana donde estaba el croquis, lo reapoya solo;
  si no, abre el editor de apoyo de FreeCAD o el diálogo de la operación para volver a
  elegir (`swui/fork/repair_refs.py`).
- **Chequear carpeta…** (menú *LikeSolidWorks UI*), para el día que se cambia de versión de
  FreeCAD: abre sin mostrar cada pieza de una carpeta (y subcarpetas), la recalcula entera,
  junta errores y referencias perdidas y la cierra **sin guardar**; las piezas abiertas no se
  tocan. Lista con doble clic para abrir y *Guardar informe* (.txt en la carpeta)
  (`swui/fork/folder_check.py`).
- *Desactivar supresión con dependientes* también devuelve los redondeos/chaflanes de la
  operación (antes quedaban suprimidos). "¿Qué es incorrecto?" explica el error de una
  operación sin sólido antes (por ejemplo, un corte con la base suprimida).
- **Panel de Redondeo como el PropertyManager de SW** (fase 2): la lista *Elementos a
  redondear* siempre espera selección (clic en una arista o cara la agrega, otro clic o Supr la
  saca; clic en la cara amarilla de la vista previa también), radio, vista previa con las caras
  nuevas en amarillo y aviso claro si FreeCAD no puede hacer el redondeo. Reemplaza al diálogo
  de FreeCAD desde la cinta, el menú, *Editar operación* y *Reparar referencias* (las
  referencias perdidas salen en rojo). Por debajo sigue siendo el redondeo de FreeCAD
  (`swui/fork/dress_up_panel.py`).
- **Redondeo más parecido a SW** (comparado con SW 2018 a mano, 2026-10-28): sin nada elegido
  abre el panel callado esperando aristas (antes FreeCAD avisaba un error en inglés; igual el
  chaflán); el radio arranca en 10 mm y después recuerda el último escrito; al elegir una
  arista el radio queda seleccionado para escribir el número directo; recuadro *Radio:*
  editable junto a la arista en la vista, con línea guía; barrita de selección de SW debajo
  (*Contorno* de la cara vecina —otro clic, la otra cara— y *Convexas*), que se apaga con
  *Mostrar barra de herramientas de selección*.
- **Barra de estado como SW al pasar el mouse**: *Longitud* de una arista, radio o diámetro de
  un arco o círculo, *Área* de una cara, en lugar del *Preselected: …* en inglés de FreeCAD
  (`swui/fork/preselect_status.py`).
- **Medir**: si la ventana quedaba abierta sin verse, la medición dibujada quedaba pegada en
  la vista; ahora la barra espaciadora la limpia y vuelve a mostrar la ventana.
- **Clic derecho del árbol en castellano**: *Mostrar/Ocultar selección*, *Alternar
  transparencia*, *Colores de caras*, *Editar …* y otras que FreeCAD 1.1.4 deja en inglés.
- **Chapa comparada con SW 2018**: brida base + bridas de arista dan el mismo volumen y el mismo
  desarrollo (DXF) que SW. La brida de arista recuerda cómo se mide y la posición (como SW);
  *Exportar DXF* con la pieza sin guardar propone la última carpeta o Documentos (antes, la del
  addon). *Extruir corte* de la pestaña Chapa queda vinculado al espesor (antes 5 mm fijos: con
  chapa más gruesa no atravesaba). La Brida base de un perfil abierto pone el espesor hacia
  afuera del croquis, como SW (*Invertir dirección* lo pasa adentro). Dobladillo, aplanar,
  cambio de espesor, perfil en L y desdoblar/doblar con un corte: mismo resultado que SW.
- **La pieza ya no queda oculta** al aceptar o cancelar la edición de una operación que no es la
  última (p. ej. cambiar el espesor de la Brida base con bridas después).
- **Fase 2 comparada a mano con SW 2018** (mismo volumen que SW en todo): el chaflán sigue el
  orden de SW (Tipo, Elementos, Parámetros) con Simétrico/Asimétrico y recuadro de medidas; las
  matrices y la simetría abren con la dirección, el eje o el plano vacíos esperando selección;
  chaflán, matrices, ángulo de salida y taladro recuerdan las últimas medidas o tipo (la primera
  vez, los valores de SW); el taladro vuelve a su panel después de *Editar posiciones*; el clic
  atraviesa la vista previa de planos, ejes y puntos; las cotas se modifican con doble clic.
- **Panel de Chaflán** igual al de redondeo, con los tipos de SW: *Ángulo-distancia* o
  *Distancia-distancia* (con *Distancia igual*) e *Invertir dirección*.
- **Paneles de Matriz lineal, Matriz circular y Simetría** estilo SW: casillas de selección
  (la activa en rosado; arista, eje o cara plana; en la circular también una cara cilíndrica
  como eje), *Dirección 2*, *Espaciado* e *Instancias*, *Separación igual*, *Operaciones y caras*
  (clic en una cara suma la operación que la creó), *Sólidos* (toda la pieza) y vista previa con
  las copias en amarillo. Se apaga la vista previa magenta de FreeCAD mientras el panel está
  abierto (`swui/fork/pattern_panel.py`).
- **Asistente para taladro con flujo SW**: sin nada elegido, se toca la cara plana, se abre el
  croquis con la herramienta Punto lista (Posiciones), y al salir del croquis aparece el panel
  *Tipo*: Refrentado / Avellanado / Agujero / Agujero roscado, estándar ISO (también rosca fina,
  UNC, UNF o sin norma), tipo de tornillo (ISO 4762, DIN 7984, ISO 10642...), tamaño (M6...),
  ajuste (Ajustado / Normal / Holgado), condición final, fondo, rosca; *Editar posiciones* vuelve
  al croquis. Todo sobre el taladro y las tablas de FreeCAD (`swui/fork/hole_panel.py`).
- **Árbol flotante** sobre la vista mientras un panel SW está abierto (como el FeatureManager
  desplegable de SW): un clic en una operación, plano o eje lo elige para el panel; el título lo
  pliega (`swui/fork/flyout_tree.py`). Matriz y Simetría nuevas arrancan con la lista de
  operaciones vacía, como SW (antes: toda la pieza).
- **Geometría de referencia como SW**: *Plano* con Primera/Segunda/Tercera referencia y sus
  relaciones (Coincidente, Paralelo, Perpendicular, Distancia con Invertir, Ángulo, Punto medio,
  Tangente) y el estado *Totalmente definido*; *Eje* (Una línea/arista/eje, Dos planos, Dos
  puntos, Superficie cilíndrica, Punto y cara) y *Punto* (Centro de arco, Centro de cara,
  Intersección, Proyección, A lo largo de la curva) con la lista *Selecciones*. Por debajo, los
  planos/ejes/puntos de referencia de FreeCAD (`swui/fork/ref_plane_panel.py`,
  `ref_axis_point_panel.py`). Los planos *En ángulo* y *Punto medio* (FreeCAD no los tiene) los
  recalcula el addon en cada reconstrucción: siguen a la pieza y a lo que se apoya en ellos.
- **Panel de Ángulo de salida** estilo SW: ángulo, *Plano neutro* (casilla rosada que espera una
  cara plana o un plano) y *Caras de salida*, con vista previa.
- **Términos de SW** en los diálogos que siguen siendo de FreeCAD: barrido (Perfil, Trayecto,
  Esquinas, Tipo de orientación/torsión: Seguir trayecto…), hélice (Definido por: Altura y paso,
  Paso y revolución…; Paso, Revoluciones, Sentido antihorario) y plano/eje/punto de referencia
  (textos que quedaban en inglés). En el barrido, con el perfil ya elegido, queda esperando el
  trayecto sin apretar nada (`swui/fork/native_terms.py`).
- **Pestaña Evaluar como en SW** (fase 3): *Medir*, *Propiedades físicas*, *Ecuaciones* y
  *Editar material*, con íconos propios (`tools/fork/make_icons_fork.py`).
- **Material**: ventana con *Materiales de FreeCAD* (por categoría, en castellano, solo los que
  tienen densidad) y *Materiales personalizados* que uno crea, copia, edita y borra (archivos
  .FCMat nativos en la biblioteca del usuario). Se asigna a lo elegido o a toda la pieza **sin
  cambiar el color**. Cada pieza guarda una copia del material: si se abre el archivo en una PC
  que no lo tiene (FreeCAD lo cambiaría por "Default" sin avisar), el addon avisa y lo recrea
  igual (`swui/fork/material.py`).
- **Propiedades físicas** con el informe de SW: densidad, masa en kg, volumen, área, centro de
  masa (marcado en la vista), ejes y momentos principales, momentos en el centro de masa y en el
  origen. Pieza entera, sólidos elegidos o ensamblaje (cada pieza con su material y en su
  lugar). Sin material: 1000 kg/m³, como SW (`swui/fork/mass_props.py`).
- **Ecuaciones, variables globales y cotas**: tabla como la de SW ("Largo" = 120,
  "D1@Croquis1" = "Largo" / 2...), lista de cotas para insertar con doble clic, funciones de SW
  (sqr, iif...), coma decimal; Aceptar es un solo paso de deshacer y Cancelar deja todo igual.
  Por debajo, expresiones y un VarSet de FreeCAD (abre sin el addon). Doble clic en una cota con
  ecuación abre la ventana (`swui/fork/equations.py`).
- **Medir** estilo SW (también con la barra espaciadora): cada clic suma un elemento, clic en el
  vacío borra; distancia con dX/dY/dZ, centro a centro en círculos y cilindros, distancia
  normal, ángulo, longitud, diámetro, área y perímetro; dibuja la distancia en la vista y mide
  bien en ensamblajes (`swui/fork/measure_sw.py`). Reemplaza al Medir de FreeCAD, en inglés.
  Tercera opción **Distancia máxima** (FreeCAD no la trae): entre bordes de agujeros como SW y
  entre cualquier otra geometría, con cálculo propio exacto (`swui/fork/max_distance.py`).
  *Centro a centro* también entre un agujero y una cara plana, arista recta o vértice (desde el
  eje del agujero, como SW).
  En la vista, como SW: línea de la distancia con su recuadro y la escalera de proyecciones
  dX (roja), dY (verde) y dZ (azul) con sus valores; siguen al girar el modelo (casilla para
  apagarlas).
- **Franja Ecuaciones / Sólidos(n) / Material** arriba del árbol, como las carpetas del
  FeatureManager (`swui/fork/tree_strip.py`).
- **Multicuerpo, etapa A** (cada sólido de SW = un Cuerpo de FreeCAD): Propiedades físicas y la
  franja ya no cuentan dos veces un Cuerpo usado en una Booleana (Combinar) o en un Dividir;
  *Sólidos(n)* marca con ⚠ un Cuerpo que tiene varios sólidos sueltos adentro.
- **Multicuerpo, etapa B**: en Extruir y Revolución, casilla **Fusionar resultado** (apagada, la
  operación queda como un sólido aparte en un Cuerpo nuevo) y, en los cortes, **Alcance de la
  operación** (Todos los sólidos / Sólidos seleccionados / Selección automática, como SW): el corte
  se copia en cada sólido elegido y las copias siguen las medidas del original. Todo con objetos
  nativos de FreeCAD: el archivo se abre y se recalcula bien sin el addon (`swui/fork/multibody.py`).
  Borrar el corte original (Supr) borra también sus copias en un solo paso; "Hasta la cara" se
  lleva a los otros sólidos; con selección automática, si el corte cambia y pasa a atravesar otro
  sólido, el addon pregunta si actualizar el alcance.
- **Simetría de sólidos** como SW: "Sólidos para simetría" y "Fusionar sólidos"; apagado, cada
  sólido espejado queda como sólido aparte que sigue al original (`swui/fork/mirror_bodies.py`).
- **Alcance de la operación en el Asistente para taladro**, igual que en los cortes.
- **Combinar** (pestaña Operaciones) con el panel de SW: Agregar / Eliminar / Común, sólidos
  elegidos con clics; por debajo la Booleana nativa de FreeCAD (`swui/fork/combine_panel.py`).
- **Mover cara** (pestaña Operaciones, fase 4) con el panel de SW: Equidistanciar / Trasladar
  (dirección o ΔX ΔY ΔZ) / Girar alrededor de una arista, solo caras planas, también en sólidos
  importados. Por debajo Extruir o Cortar desde la cara y el Ángulo de salida nativos: el archivo
  abre y se recalcula sin el addon (`swui/fork/move_face.py`). Límite: con caras vecinas
  inclinadas, mover (no girar) deja un escalón en vez de prolongarlas.
- **Mover/Copiar sólido** (pestaña Operaciones, botón con menú) con el panel de SW: sólidos,
  Copiar + cantidad, Trasladar (arista + distancia o ΔX ΔY ΔZ), Girar (arista + ángulo o centro +
  ángulos), también **de un vértice a otro** (sigue a los vértices si la pieza cambia). Cada copia
  (o el sólido movido) es un Cuerpo nuevo que sigue al original; al mover, lo de antes queda en el
  original oculto (`swui/fork/move_bodies.py`). Sin Restricciones (decisión del usuario).
- **Eliminar/Conservar sólidos** (mismo botón) para Cuerpos enteros y para los pedazos que deja un
  corte; cada pedazo que queda es un Cuerpo nuevo, elegido por un punto adentro (sigue siendo el
  mismo aunque cambien las cotas). Borrar la operación con Supr (o editarla con la lista vacía)
  devuelve los sólidos, como SW (`swui/fork/delete_bodies.py`).
- **Pestaña Chapa** (fase 1, primera versión) sobre el addon SheetMetal, que tiene que estar
  instalado: **Brida base** (con el croquis abierto o eligiendo plano/cara, como Extruir; contorno
  cerrado = placa, línea abierta = perfil plegado), **Brida de arista** (aristas con clics, ángulo,
  longitud hasta exterior virtual / interior virtual / tangente, posición de brida, radio
  predeterminado), **Aplanar** (muestra el desarrollo; otro clic vuelve a plegar) y **Exportar
  DXF** con un clic: contorno en la capa CONTORNO y líneas de plegado de trazos en PLEGADO, al lado
  de la pieza, con nombre pieza_espesor_material ("Soporte_1,5mm_SAE 1010.dxf"). Parámetros de
  chapa en la Brida base: espesor, radio (de fábrica = espesor) y factor K (0,5), que siguen las
  bridas y el desarrollo (`swui/fork/sheet_metal.py`, `sheet_panels.py`, `sheet_tab.py`).
- Chapa, segunda versión: **Dobladillo** (cerrado / abierto / lágrima / laminado, material interior
  o pliegue exterior), **Extruir corte** en la pestaña Chapa (el desarrollo lleva los agujeros),
  **Convertir en chapa** para chapas sin historia (STEP de SW: se elige la cara fija y el espesor
  se mide solo; después admite bridas, aplanar y DXF) y **DXF por lotes**: Exportar DXF en un
  ensamblaje guarda un DXF por cada pieza de chapa.
- Chapa, tercera versión: **Desdoblar / Doblar** como SW. Desdoblar muestra el desarrollo y abre un
  croquis encima; lo que se dibuja (puede cruzar los pliegues) se corta y la chapa se vuelve a
  plegar con Doblar o al salir del croquis (por debajo el "Wrap Cutout" de SheetMetal). Un corte
  entero sobre una brida avisa que va con Extruir corte. Editar un Corte-Desdoblado abre un panel
  en castellano (factor K y "Editar croquis sobre el desarrollo") en lugar del de SheetMetal.
- Ensamblaje (fase 5, etapa 2): **Relación de posición** como el PropertyManager de SW. Se eligen
  dos entidades, la relación que corresponde se aplica sola, "Agregar relación (✓)" la confirma y
  el panel queda abierto para la siguiente. Coincidente, Paralela, Perpendicular, **Tangente**,
  Concéntrica, Bloquear (deja las piezas donde están), Distancia y Ángulo (arrancan con el valor
  actual), Alineada / Antialineada y límites en la concéntrica. Doble clic en una relación la edita
  en el mismo panel; los botones del panel contextual del original también lo abren. Clic derecho
  sobre un componente: **Fijar / Flotar** y **Ver relaciones de posición**. Todo sobre las uniones
  nativas de FreeCAD (`swui/fork/mates_sw.py`).
- Ensamblaje (fase 5, etapa 3): **Matriz de componente lineal** (una o dos direcciones, desde una
  arista, una cara o un eje), **Matriz de componente circular** (eje desde una arista circular,
  una cara cilíndrica o un eje; "Separación igual") y **Simetría de componentes** (misma pieza si
  es simétrica, o **versión opuesta**: archivo nuevo "<pieza>-opuesta" atado a la original, que se
  reconstruye solo al abrirlo si la original cambió). Las copias siguen a la pieza semilla aunque
  la mueva el motor de cálculo. Se editan con clic derecho "Editar operación". Todo con objetos
  nativos (vínculos con copias, expresiones, VarSet) (`swui/fork/component_patterns.py`).
- Ensamblaje (fase 5, etapa 4): **Asistente para taladro** y **Extruir corte** de ensamblaje, que
  agujerean varias piezas de una vez. Se elige la cara, se abre un croquis ahí (puntos de posición
  o el perfil del corte) y al salir aparece el panel: el de taladro de siempre (tipo, norma,
  tamaño...) o profundidad del corte, más **Piezas afectadas** (arranca con las que el agujero
  atraviesa; un clic suma o saca). El agujero queda dentro de cada pieza (sale en sus planos y en
  el DXF), sigue al croquis del ensamblaje y se realinea solo si la pieza se mueve. Se edita con
  clic derecho "Editar operación" (`swui/fork/assembly_features.py`).
- Ensamblaje (fase 5, etapa 5): **Plano, Eje y Punto de referencia** en la pestaña Ensamblaje, con
  los mismos paneles SW de la pieza. Lo que se toca pasa por el componente, así que el plano sigue
  a la pieza. Un plano hecho solo sobre el origen del ensamblaje queda fijo y sirve para relaciones
  de posición; uno apoyado en una pieza sirve para matrices y simetría (en relaciones el panel
  avisa que conviene la cara con Distancia: FreeCAD no lo toma). Se editan con clic derecho
  "Editar operación" (`swui/fork/asm_reference.py`).
- Barrido y hélice: encabezados del panel en castellano ("Perfil y trayecto", "Opciones",
  antes "Pipe Parameters"/"Section Orientation"); con el perfil elegido, el botón del trayecto
  queda prendido de verdad (antes a veces no) y un clic en el croquis del trayecto alcanza, como
  en SW. La hélice se llama "Hélice1" en el árbol (antes "AdditiveHelix") (`swui/fork/native_terms.py`).
- Multicuerpo sin "Cuerpo activo", como SW: al elegir un croquis o una cara, su sólido pasa a ser el
  activo. Antes, con dos sólidos, Extruir pedía en inglés "Cuerpo Activo Requerido" y un croquis de
  otro sólido daba error (`swui/fork/auto_body.py`). El encabezado del corte decía "Parámetros de
  vaciado" (en SW Vaciado es otra operación): ahora "Parámetros de corte".
- Combinar abre con la lista vacía, como SW (antes traía ya el sólido activo y al hacer clic en los
  dos se sacaba); en Eliminar el "Sólido principal" arranca vacío y esperando el clic.
- Ensamblaje: las **relaciones de posición ya no saltan cuando cambia una pieza**. FreeCAD guarda
  la arista o cara de cada relación por su número, y al agregar una operación (un taladro de
  ensamblaje, por ejemplo) los números cambian: los pernos saltaban a otro agujero. Ahora cada
  relación guarda también cómo era lo elegido (centro, eje, radio, normal) y, cuando la pieza se
  recalcula o se abre el ensamblaje, vuelve a encontrarlo y corrige la referencia. Si lo elegido
  cambió de verdad, toma lo más parecido y avisa en la vista de informe (`swui/fork/mate_refs.py`).
- Mover/Copiar sólido "de un vértice a otro": al cambiar la pieza (por ejemplo la altura de la
  extrusión) las copias quedaban congeladas, porque FreeCAD pierde el vértice de arriba. Ahora el
  punto se vuelve a apoyar solo en el vértice equivalente y las copias siguen a la pieza.
- Relaciones de posición: también se corrigen las elegidas con el nombre largo que trae la
  selección de FreeCAD (";#1a:2;...Vertex6").
- Material: el aviso de "material faltante" al abrir una pieza no salía nunca (FreeCAD 1.1.4 no
  avisa el fin de la carga); ahora sale.
- Taladro de ensamblaje con un perno ya puesto (probado con el mouse, 2026-10-30): el conjunto se
  desarmaba y hasta la base fija quedaba girada. Tres arreglos:
  - "Piezas afectadas" ya no suma solo un perno o pasador metido en el eje del agujero (el agujero
    pasa a cada pieza y se lo comía entero); se puede sumar a mano con un clic.
  - Las relaciones guardan la cara o arista sin el nombre de la operación ("Face5" en vez de
    "Extruir1.Face5"): así FreeCAD mismo la sigue bien cuando la pieza cambia. Las relaciones de
    archivos anteriores se pasan solas al revisarlas.
  - Si la arista nueva quedó con el eje al revés, se compensa en la relación (si no, la concéntrica
    pedía dar vuelta el perno); y si al resolver se mueve una pieza fija, se vuelve a las
    posiciones de antes y se resuelve otra vez.
- Editar una relación con doble clic después de editar el croquis de un taladro de ensamblaje
  dejaba ocultas las piezas taladradas: el doble clic cancelaba lo pendiente. Ahora lo confirma.
- Simetría de componentes: la casilla "Versión opuesta" no se podía tildar con el mouse (al hacer
  clic en la pieza de la lista, la lista se rearmaba y perdía la fila); ahora queda elegida la
  última pieza agregada y la que se toca. Arregla también Supr en la lista de las matrices.
- Simetría de componentes: el plano acepta solo caras planas o planos, como SW (un vértice o una
  arista terminaban en una ventana de error con el detalle técnico).
- Corte de ensamblaje "Por todo - ambas direcciones" usa SideType (en 1.1.4 "Midplane" está
  obsoleto y FreeCAD mostraba avisos en inglés).
- "Convertir en chapa" y "Mover cara" sin nada elegido abren el panel y esperan la cara, como SW
  (antes, una ventanita de aviso). Mover cara muestra desde el principio Equidistanciar /
  Trasladar / Girar y sus parámetros, como SW; lo elegido pasa al panel completo con la primera cara.
- "Convertir en chapa" propone el radio de la mayoría de los pliegues de la pieza (antes, el
  cilindro más chico: con un dobladillo de R1 proponía 1 mm aunque los pliegues fueran de 2).
- El Cuerpo que se arma para un sólido importado se llama "Cuerpo" (antes "Body").
- Franja "Sólidos(n)": el desarrollo de chapa ya no cuenta como sólido aparte ni "se come" al
  Cuerpo (daba Sólidos(2) o Sólidos(0) al aplanar; ahora 1, como SW).
- Pestaña Evaluar: con la interfaz en castellano el botón "Language" dice "Idioma" ("Language"
  queda en el globo de ayuda).
- La cinta pasa sola a la pestaña Ensamblaje al abrir o pasar a un ensamblaje, y vuelve a
  Operaciones al pasar a una pieza, como SW (`swui/fork/asm_tab.py`).
- Una pieza con agujeros o cortes hechos desde el ensamblaje, abierta sola, lo avisa con un
  cartelito de FreeCAD (antes, solo en la vista de informes, que el fork tiene oculta).
- Relaciones de posición: ya no avisan "la arista circular elegida cambió... Revisala" cuando la
  pieza se recalcula y el agujero sigue igual (OpenCASCADE corre la costura del círculo).
- Guardar también STEP: al guardar cerrando ("¿Guardar cambios?" o Cerrar todo) el STEP se
  actualiza igual; antes salía un error rojo "Unknown document" y el STEP quedaba viejo.
- Tangente entre una cara plana y un cilindro: además acuesta el cilindro (eje paralelo a la
  cara), como SW; antes un rodillo parado quedaba atravesando la placa. Se arma con una unión
  Perpendicular nativa oculta en el árbol, que se suprime y se borra con la Tangente.
- Guardar el ensamblaje guarda también las piezas que cambiaron (taladro o corte de ensamblaje,
  versión opuesta), como SW; antes quedaban sin guardar y "Guardar todo" mostraba un error rojo
  de "dependencias cíclicas".
- En castellano: "Guardar como..." del menú Archivo, la pregunta al cerrar con cambios y sus
  botones, y "Editar croquis" en el clic derecho (`swui/fork/es_texts.py`).
- Cota nueva en el croquis: Escape en el cuadro del valor la deja con el valor medido, como SW
  (antes la borraba).
- Ensamblaje, más parecido a SW: los ejes y planos auxiliares de matrices y simetrías no se ven
  en el árbol; las relaciones no dejan sus ejes de colores en la vista; borrar la operación
  (MatrizCircular1...) borra también sus copias y auxiliares; la unión que fija una pieza se
  llama "Fijo (Placa<1>)" (no "GroundedJoint"); el clic derecho de un componente deja a mano lo
  de todos los días y el resto en "Más opciones".
- En castellano: el contador del panel Insertar ("1 insertado"), la barra de estado sobre una
  relación o un componente (su nombre, no "Preselected: ..."), "Cerrar" y "Edición de croquis"
  en el panel del croquis.
- Panel Plano: muestra "Cara (Placa<1>)" en vez del nombre interno, y Supr o clic derecho >
  Borrar saca una referencia elegida. Eje y Punto fijos del ensamblaje guardan sus selecciones
  para volver a editarlos (propiedad SWUI_RefSpec).
- Corte de ensamblaje: arranca en "Hasta profundidad especificada", 10 mm, como SW.
- Doble clic en un taladro o corte de ensamblaje dentro de la pieza: abre su panel en el
  ensamblaje (o avisa que se edita desde ahí) en vez del diálogo de FreeCAD.
- Al abrir un ensamblaje al arrancar FreeCAD (doble clic en el archivo) también se ocultan los
  ejes de las relaciones; borrar una matriz ya no tira errores rojos en inglés; "Ir a la pieza"
  (antes "Go to Linked Object") a mano en el menú del componente; el Cuerpo de la versión
  opuesta lleva el nombre de la pieza (antes "Body").
- Versión opuesta: al aceptar la simetría pide nombre y carpeta del archivo nuevo, como SW
  (propone "<pieza>-opuesta" junto a la original; Cancelar deja el panel abierto).
- Simetría de componentes: con la lista de componentes activa, un clic en una cara curva (un
  rodillo, un bulón) no agregaba el componente y avisaba "elegí una cara plana o un plano".
- Simetría de componentes: "Versión opuesta" pasa a llamarse "Versión simétrica" (como SW) y el
  archivo nuevo se propone como "<pieza>-simetría" (antes "<pieza>-opuesta"; los ya hechos siguen
  funcionando).
- Ensamblaje: cada componente muestra en el árbol, primero, la carpeta "Relaciones de posición en
  <Conjunto>" con sus relaciones, como el FeatureManager de SW (la carpeta general sigue). Clic
  elige, Ctrl+clic suma, doble clic edita, clic derecho con "Suprimido", pasar el mouse
  preselecciona; suprimidas en gris. Es solo dibujo: no se guarda nada en el archivo
  (`swui/fork/mates_tree.py`). Si una versión nueva de FreeCAD cambia el árbol, se apaga sola
  y lo avisa. Las suprimidas se atenúan con el mismo velo que lo suprimido de las piezas.
- Relaciones de posición con las piezas que unen, como SW: "Coincidente1 (Placa<1>,Brida<1>)",
  en la carpeta general y en la de cada componente. El nombre guardado sigue siendo
  "Coincidente1" (como en SW): las piezas se dibujan al lado, sin tocar el archivo.
- Botón "Yes" en castellano ("Sí") en los avisos de FreeCAD, por ejemplo "Material faltante".
- Ensamblajes que no se crearon dentro del fork: al abrirlos, la carpeta "Joints" (y las demás
  carpetas del ensamblaje) pasa a "Relaciones de posición", como SW; si el usuario la renombró,
  no se toca.
- Arreglo (visto por el usuario): con Redondeo abierto, apretar Extruir corte y contestar "Sí" a
  "Un diálogo ya está abierto" dejaba el Redondeo escuchando: ya no se podían elegir caras y
  salía "QListWidget already deleted". Ahora (`swui/fork/panel_guard.py`): (1) como SW, otro
  comando de la cinta cancela el panel abierto del fork y arranca, sin la pregunta (vista, medir,
  archivo y deshacer no lo cancelan); (2) red de seguridad: si FreeCAD cierra un panel del fork
  por su cuenta, su escucha se apaga solo y limpia lo que dibujó.

## 0.10.0 — 2026-10-18

**Deutsch**
- Oberfläche auf **Deutsch und Englisch** – Knopf *Language* im Reiter
  Evaluieren (Automatisch wie FreeCAD / Deutsch / English), wirkt sofort.
  Englische SOLIDWORKS-Begriffe im Ribbon, in den Dialogen und im Baum
  (Sketch1, Boss-Extrude1, Top Plane, Mates, Sheet1 …).
- Reiter *Evaluieren* ganz links, damit man die Sprache sofort findet.
- **„Skizze erstellen“ unter dem Mauspfeil** nach einem Klick auf eine
  ebene Fläche (blasst beim Wegbewegen aus).
- Zeichnungen:
  - englische Vorlagen A4 hoch / A3 quer (ISO 7200, Feld „Unit“)
  - **Projektionsmethode je Zeichnung wählbar** (Methode 1 / Methode 3),
    Symbol im Schriftfeld wechselt mit
  - **Linieneigenschaften**: Linienart, Strichstärke (ISO 128), Farbe
  - **Formen** auf dem Blatt (Linie, Rechteck, Kreis, Bogen, Vieleck) in
    einer Blatt-Skizze mit allen Abhängigkeiten, frei verschiebbar
  - **Text** per Klick aufs Blatt, Schriftgröße in mm oder pt
  - Export: zwei Blätter konnten denselben Dateinamen bekommen – behoben
- Kompatibilität: Fenster öffnen auch unter Qt5/PySide2; laufende
  Platzier-Modi enden beim Werkbankwechsel; geprüft gegen FreeCAD 1.0.2,
  1.1.4 und den Entwicklungsstand.
- Erste Freigabe über den Zweig `release`.

**English**
- Interface in **German and English** — *Language* button in the Evaluate
  tab (automatic like FreeCAD / German / English), switches immediately.
  English SOLIDWORKS terms in the ribbon, dialogs and tree.
- Evaluate tab moved to the far left so the language is easy to find.
- **"Sketch" context symbol** next to the pointer after clicking a planar
  face (fades out when moving away).
- Drawings: English title block templates (ISO 7200, "Unit" field);
  **projection method per drawing** (first/third angle) with matching
  symbol; **Line Format** (style, ISO 128 thickness, colour); **shapes** on
  the sheet in a sheet sketch with all relations, movable; **text** by
  clicking on the sheet, font size in mm or pt; fixed duplicate file names
  when exporting several sheets.
- Compatibility: dialogs also open with Qt5/PySide2; placement modes end
  when switching workbenches; checked against FreeCAD 1.0.2, 1.1.4 and the
  development version.
- First release through the `release` branch.

## 0.9.0 — 2026-10-18

**Deutsch** – Erste Veröffentlichung: Ribbon im Stil des
SOLIDWORKS-CommandManagers, dunkles Farbschema, SOLIDWORKS-Namen und
-Begriffe für Teile, Skizzen, Baugruppen und Zeichnungen, Beziehungs- und
Verknüpfungs-Panel, Drag & Drop in Baugruppen, Zeichnung erstellen mit
ISO-7200-Schriftfeld, Blatteigenschaften, Oberflächenangabe (ISO 1302),
Schweißsymbol (ISO 2553), PDF/DXF-Export, eigene Symbole.

**English** – First public version: CommandManager-style ribbon, dark
theme, SOLIDWORKS names and terms for parts, sketches, assemblies and
drawings, relations and mates panels, drag & drop into assemblies, drawing
creation with ISO 7200 title block, sheet properties, surface finish
(ISO 1302), weld symbol (ISO 2553), PDF/DXF export, own icons.
