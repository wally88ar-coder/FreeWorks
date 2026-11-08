# Proyecto: fork de LikeSolidWorks UI para FreeCAD (flujo e interfaz estilo SolidWorks 2018)

## Contexto
- Usuario: ~20 años de experiencia en SolidWorks (referencia: SW 2018). Habla español rioplatense.
  Trabaja en Windows, pantalla de 1366x768 al 100 % de escala.
- Uso: personal y, más adelante, para compartir con amigos y conocidos.
- Objetivo: que FreeCAD se sienta lo más parecido posible a SW 2018, limitado a las funciones
  que el usuario realmente usa (ver Alcance).

## Base: fork de LikeSolidWorks UI
- Original: https://github.com/Schlauminik/LikeSolidWorks-UI (autor: Dominik Ladewig, LGPL-2.1+,
  íconos CC-BY-SA-4.0). Comentarios y README del original en alemán.
- Este repositorio es el fork del usuario. Configurar el remoto `upstream` apuntando al original
  y revisar sus novedades con regularidad.
- Respetar SIEMPRE las convenciones del original (ver su README): Qt solo vía `swui.compat`,
  IDs de comandos con prefijo `SWUI_`, rutas vía `swui.paths`, imports pesados en `Initialize()`,
  cabecera SPDX en cada archivo, contenido de la cinta solo en `swui/ribbon_layout.py`,
  íconos generados con `tools/make_icons.py` (no editar SVG a mano), test `tools/test_load.py`
  en verde antes de cada entrega, entrada en CHANGELOG.md.
- Lo que sirve a todos (traducciones, correcciones, mejoras de flujo generales) se prepara en
  ramas separadas y limpias para proponerlo al original con un pull request. Consultar al usuario
  antes de abrir cualquier PR o issue en el repositorio original.
- Lo propio del usuario (chapa, mover/rotar cara, etc.) va en módulos separados nuevos, tocando lo
  mínimo los archivos existentes, para que incorporar cambios del original no genere conflictos.
- Decidido (2026-10-31): no se propone nada al original (desarrollo propio) y el paquete se va a
  llamar **FreeWorks** (hecho 31/10: menú, package.xml y repositorio
  https://github.com/wally88ar-coder/FreeWorks; la carpeta local y los nombres internos no cambian).

## Decisiones de arquitectura (no cambiar sin consultar)
- Addon en Python encima de FreeCAD oficial; nada de modificar el código de FreeCAD.
- Versión objetivo: FreeCAD 1.1.4 (último mantenimiento de la rama 1.1). La "1.2" pasó a llamarse
  **26.3** (FreeCAD numera ahora año.N: 26.3, 27.1, 27.2...; tres por año). El usuario actualiza
  cada ~2 años: desarrollar para 1.1.4 aunque una versión nueva ya traiga la función, y que cada
  función ceda a lo nativo si la versión lo trae. Evitar detalles internos frágiles.
- Nombres internos de lo que el fork guarda en los archivos (propiedades, clases): estables para
  siempre (ver `docs/ESTADO.md`, Decisiones).
- Dependencia: addon SheetMetal para chapa. No reimplementarlo: construir la interfaz encima.
- Nada de íconos, nombres comerciales ni recursos de Dassault.
- Preferir siempre la herramienta nativa de FreeCAD por debajo, con interfaz y flujo estilo SW.
- Similitud total con SW (decidido por el usuario, 2026-10-25): LikeSolidWorks UI es el ÚNICO
  banco (arranca ahí, vuelve solo, selector oculto; se apaga en el menú); todo módulo nuevo
  (chapa, simulación FEM...) va como pestaña de la cinta dentro de él; aspecto claro SW 2018;
  panel izquierdo con Modelo y Tareas en pestañas.
- Código propio del fork en `swui/fork/` (comentarios en español): cambia tablas y funciones del
  original desde afuera, sin editar sus archivos. Detalle en `docs/NOTAS_TECNICAS.md`.
- **Panel = cara de una función** (decidido por el usuario, 2026-11-01): toda herramienta NUEVA
  de FreeWorks deja su lógica (crear la operación, sus marcas SWUI_, auxiliares, nombres) en una
  función pública documentada que se pueda llamar sin abrir el panel ni hacer clics; el panel
  solo junta los datos y la llama. Así la IA (y las pruebas con guion) la usan directo. Las
  únicas que hoy tienen la lógica adentro del panel son 6 (Mover cara, planos/ejes/puntos SW,
  Mover/Copiar sólido, Eliminar/Conservar sólido, chapa, taladro/corte de ensamblaje): la IA las
  maneja por el panel; si alguna se toca a fondo, aprovechar para pasar su lógica a funciones.

## Lo que el original ya resuelve (no rehacer)
Cinta tipo CommandManager; croquis (colores azul/negro, panel de relaciones aplicables, línea
constructiva, línea por punto medio, ícono contextual de croquis sobre cara plana); extruir desde
un croquis abierto (`swui/from_sketch.py`); términos SW en diálogos de extruir/cortar/revolución
(`swui/feature_terms.py`, solo cambia textos); panel de relaciones de posición
(`swui/assembly_mates.py`); planos muy completos (TechDraw, exportación PDF/DXF de hojas).

## Lo que falta y es el trabajo de este fork
**Rápidos / generales (candidatos a PR al original):**
- Traducción al español (`swui/lang/es.py`, copiando `en.py`). Hoy la cinta queda en inglés y los
  diálogos nativos en español: mezcla de idiomas.
- Pantallas chicas: con 1366 px la cinta fuerza un ancho mínimo de ventana de 1458 px y se corta el
  borde derecho (panel de Tareas incluido). La cinta debe compactarse o desplazarse.
- Extruir / extruir corte sin croquis: hoy cae en el panel nativo "Seleccione un plano", que no
  acepta caras del sólido. Debe aceptar cara plana o plano, abrir el croquis ahí y lanzar la
  operación al salir del croquis (como SW). Extender el mecanismo de `from_sketch.py`.
- (Hecho en la fase 2, en `swui/fork/`: paneles SW de redondeo, chaflán, simetría, matriz lineal y
  circular, ángulo de salida, plano/eje/punto de referencia; asistente para taladro con flujo SW;
  términos SW en barrido y hélice. Son propios del fork, no candidatos a PR tal cual.)
- (Hecho en la fase 5, `swui/fork/mates_sw.py`: tangente y panel que queda abierto para encadenar
  relaciones; propio del fork, no candidato a PR tal cual.)
- (Hecho en el fork: panel de tareas a la izquierda, sin opción a la derecha, por decisión del
  usuario.)

**Propios del usuario:**
- (Hecho en la fase 1, versiones 1 a 3, en `swui/fork/`; falta que lo pruebe el usuario.)
  Chapa metálica (trabaja con plegadora, no punzonadora): pestaña nueva con brida base, brida de
  arista, propiedades de chapa, desplegar/plegar, sobre SheetMetal. **Exportar DXF del desarrollo
  con un clic**: contorno y líneas de plegado en capas separadas, nombre de archivo automático
  (pieza + espesor + material), y exportación por lotes desde un ensamblaje.
- (Hecho en la fase 3, en `swui/fork/`; falta que lo pruebe el usuario.) Pestaña Evaluar: propiedades físicas (masa, volumen, área, CDG, inercia) con Shape.Volume, Area,
  CenterOfMass, MatrixOfInertia y la densidad del material; FreeCAD 1.1 no las trae (llegan en
  26.3 como Std_MassProperties): diseñar para migrar fácil a la herramienta oficial. Asignar
  material. Diálogo de Ecuaciones estilo SW sobre expresiones + Spreadsheet/VarSet. Mediciones en
  pieza y ensamblaje (el panel de Medir de FreeCAD sale en inglés). Franja Material / Ecuaciones /
  Sólidos arriba del árbol (pasada acá desde el plan del árbol).
- (Hecho en la fase 4, 2026-10-27, `swui/fork/move_face.py`.) Mover/rotar cara: solo caras
  **planas**, con operaciones nativas (no FeaturePython: aprobado por el usuario). Equidistanciar /
  Trasladar = Extruir o Cortar con la cara como perfil (componente normal); Girar alrededor de una
  arista de la cara = Ángulo de salida nativo. Límite: con vecinas inclinadas, mover deja escalón.
  (2026-11-01: Girar ya no falla según el sentido: era un error de FreeCAD en el Ángulo de salida,
  ver NOTAS_TECNICAS "Errores de FreeCAD encontrados"; y Mover cara vuelve a encontrar sola la
  cara, la bisagra, el destino o el eje que FreeCAD pierde, como las relaciones de posición.)

- (Decidido 2026-11-01, sin código; detalle en `docs/ESTADO.md` > "Falta / ideas" y Decisiones.)
  **Piezas soldadas / estructuras** con Cuerpos nativos (no FrameForge como dependencia; su código,
  LGPL-3.0, se puede copiar si es útil y está probado); próximo: plan para aprobar.
  **Tornillería** estilo Fijaciones inteligentes sobre el addon Fasteners (análisis empezado).
  **Muescas de plegado** calculadas al exportar el DXF. **Pestaña y ranura** (no urgente).
  Anidado: no (es CAM).

Operaciones de pieza que usa (menú Insertar de SW, lista completa en `docs/ESTADO.md` > Alcance):
todas hechas (Mover/Copiar y Eliminar/Conservar sólido: 2026-10-27, sin
Restricciones por decisión del usuario); Superficie y Operación Cierre, por ahora no.

El usuario NO usa en planos: tablas/notas de plegado, listas de materiales con globos,
tolerancias geométricas.

## Fases (orden propuesto; el usuario puede reordenar)
Estado al 2026-11-01: fase 0 terminada; fases 1 a 5 con código completo y probadas por Claude
(todo lo de los checklists); **fase 5 CERRADA** (31/10, decisión del usuario: probada por Claude
con el mouse sobre un conjunto realista y comparada con SW; lo que aparezca usándola se arregla
sobre la marcha); fases 1 a 4: todas las pruebas del checklist hechas con mouse y teclado (Claude,
casi todas comparadas con SW; el usuario probó redondeo y girar cara) y todas las decisiones
tomadas; quedan solo las que necesitan algo del usuario (un STEP suyo, una pieza suya, abrir el
DXF en CypCut, Brida base de punta a punta) y el Dobladillo abierto (Claude). Repositorio en
GitHub: wally88ar-coder/FreeWorks (todo subido). Fase 6 (chequeo de compatibilidad) acordada,
sin empezar.
Hecho además fuera de las fases: barra de menús como SW 2018 (2026-11-01, `swui/fork/menus_sw.py`;
maqueta, decisiones y pruebas en `docs/ESTADO.md`; croquis vacío que se borra al cerrarlo,
`swui/fork/empty_sketch.py`); configuraciones estilo SW en piezas, chapa (DXF de todas) y
ensamblajes (2026-11-01, `swui/fork/config*.py`; análisis y plan en el documento enlazado en
`docs/ESTADO.md`); IA, etapa 0 (2026-11-01, `swui/fork/ia/`: puente MCP en FreeWorks > IA,
conectado a la app de Claude del usuario como "freeworks" y probado de punta a punta; AISLADA:
nada de FreeWorks importa `swui/fork/ia` salvo el enganche, capas terceros/nucleo/herramientas/
puertas, código ajeno copiado con su aviso; plan, etapas 1 a 5 y decisiones en el documento de
IA enlazado en `docs/ESTADO.md`); árbol de operaciones estilo SW (barra de retroceso, suprimir,
mover, cotas con doble clic, reparar referencias...), aristas del modelo dentro del croquis,
multicuerpo (Fusionar resultado, Alcance, Combinar, simetría de sólidos) y Mover/Copiar /
Eliminar/Conservar sólidos; herramientas de entidades del croquis como SW (2026-11-02,
`swui/fork/sketch_entities.py` + `sketch_transform.py` + `sketch_offset.py`: Simetría, Mover,
Copiar, Girar, Escalar, Matriz lineal, Equidistanciar, siempre activas, panel único SW sobre
funciones nativas del croquis; falta que el usuario pruebe la vista previa que sigue al mouse). Próximo: lo que elija el usuario después de probar. Ver `docs/ESTADO.md`.
Trabajo de planos (TechDraw, sin número de fase): rosca simplificada automática, rótulo en
castellano, coma decimal; ver "Falta" en `docs/ESTADO.md`.
0. Puesta en marcha: remotos (origin = fork, upstream = original), verificar que carga y que el
   test pasa en Windows, traducción al español, arreglo de pantallas chicas, extruir/cortar sin
   croquis.
1. Chapa metálica + exportación DXF (es lo que más usa el usuario y no existe).
2. Flujos de pieza: diálogos restantes adaptados y asistente para taladro.
3. Evaluar: propiedades físicas, material, ecuaciones.
4. Mover/rotar cara (hecha 2026-10-27).
5. Ensamblaje — CERRADA el 2026-10-31 (código completo 2026-10-27, probada por Claude con el
   mouse y comparada con SW, decisiones del usuario hechas: relaciones colgadas de cada componente y con sus
   piezas en el nombre, versión simétrica que pide nombre y carpeta; las relaciones ya no saltan
   al cambiar una pieza): relaciones SW, matriz y
   simetría de componentes, taladro/corte de ensamblaje, geometría de referencia. Plan y checklist
   en la sección Fase 5 del documento de checklists (enlace en `docs/ESTADO.md`).
6. Chequeo de compatibilidad (fase aparte, decidido por el usuario 2026-10-31; sin empezar):
   aviso de versión de FreeCAD no probada, chequeo rápido al arrancar (cada función que depende
   de algo interno de FreeCAD registra su chequeo; si falla, se apaga sola y avisa en castellano
   con un informe técnico) y diagnóstico completo a pedido con pruebas reales. Pensado para
   cuando ya no haya SW: guardar capturas propias de cómo queda la interfaz como referencia.

## Forma de trabajo
- Antes de tocar algo grande, explicar el plan al usuario en lenguaje simple (no es programador).
- Cada fase termina en una versión que el usuario prueba en su FreeCAD. La interfaz gráfica la
  valida el usuario; la geometría probarla también con FreeCADCmd (sin GUI) cuando se pueda.
- Para Python fuera de FreeCAD, usar el intérprete incluido en FreeCAD si no hay otro instalado.
- Piezas de prueba reales del usuario (exportadas de SW en STEP): pedir la carpeta y usarlas.
- Commits pequeños y descriptivos. Nunca forzar push ni reescribir historia publicada.
- **Subir a GitHub (push) después de cada entrega que pase todo** (enganche en cada commit +
  batería completa), sin preguntar (decidido por el usuario 2026-11-08). Lo que no pasa todo,
  no se sube.
- Mantener actualizado `docs/ESTADO.md`: fase actual, qué está hecho, qué falta, problemas
  reportados por el usuario, decisiones nuevas y estado de los PR al original. Leerlo al inicio
  de cada sesión, junto con `docs/NOTAS_TECNICAS.md` (cómo probar en FreeCAD real con
  `tools/fork/gui_probe.py`, hallazgos de FreeCAD 1.1.4 en Windows).
- Checklists compartidos con el usuario (documentos de Claude, enlaces arriba en `docs/ESTADO.md`):
  un solo documento con lo que falta en cada fase (la fase 5 en detalle, adentro). Leerlo al inicio de cada
  sesión (qué tildó o comentó el usuario) y tildar ahí lo que se cierra, además de ESTADO.md.
- Antes de entregar cambios de interfaz, probarlos en FreeCAD real con la plantilla de prueba
  (copia de la configuración, nunca la del usuario) y mirar las capturas; después la valida él.
- Ser honesto sobre límites que el addon no puede resolver.

## Calidad: cometer menos errores (aprobado por el usuario 2026-11-08; detalle en `docs/PLAN_CALIDAD.md`)
- **Antes de programar**, escribir en 2-3 renglones qué tiene que pasar; la prueba se arma con eso.
- **Las 7 preguntas**, para toda herramienta nueva o cambiada, cada una con su prueba: ¿y si
  cancelo? ¿deshago y rehago? ¿cambio una medida de algo anterior y recalculo? ¿guardo, cierro y
  abro (sin quedar "modificado", y sin FreeWorks)? ¿abro otra herramienta (Ecuaciones, Material,
  Suprimir...) con el panel abierto? ¿dos archivos abiertos? ¿elijo algo raro (arco, cara curva,
  otro sólido, nada)?
- **Piezas comunes** (`swui/fork/safe_ops.py`): borrar una operación, empezar algo deshacible,
  registrar un panel, escuchas que no actúan al abrir o deshacer, guardar referencias a otro
  documento. No reescribirlas a mano en cada módulo; al tocar un módulo viejo, pasarlo a ellas.
- **Batería de pruebas** (`tools/fork/pruebas/`, ver su LEEME): todo error arreglado y toda
  herramienta nueva dejan su prueba. La rápida corre sola antes de cada commit (enganche de git,
  `tools/fork/hooks/`); la completa (con ventana) antes de cada entrega. Nunca saltear el enganche.
- **Errores en las Issues de GitHub** (wally88ar-coder/FreeWorks, propio: se pueden abrir y
  comentar fichas sin preguntar), con gravedad, causa y área; el commit que arregla dice
  "Arregla #N". Prueba de un error todavía abierto: `CONOCIDO = "#N"`.
- **No afirmar sin probar**: nada se anota como que anda (ESTADO, checklist, al usuario) sin una
  prueba que lo muestre; si no se probó, decir "sin probar".
- **Antes de cada entrega**: revisión del cambio por un agente que no lo escribió (recibe el
  código, no las conclusiones) y el analizador (`ruff`, lo corre el enganche).
- **Lo nativo antes que el enganche** al funcionamiento interno de FreeCAD; cada enganche, con prueba.
- **Pruebas para romper, no solo para confirmar** (pasos 8 y 9 del plan): reglas comunes de
  paneles y de geometría con valores al azar, fuzzing de secuencias y de campos, agente atacante
  que escribe pruebas sin ver el código, capturas de referencia y tiempos máximos.
- **Tres niveles**: cada commit, TODA la batería rápida (enganche); cada entrega, TODA la batería
  con ventana + reglas de paneles con más casos para lo tocado + capturas; **de noche** (aprobado
  por el usuario 08/11), fuzzing y casos al azar largos, con lo encontrado a las Issues. Si la
  rápida pasa de ~3 min, en el commit solo lo tocado y lo que depende de eso.
- **Flujo de una funcionalidad nueva**: plan simple + "qué tiene que pasar" (2-3 renglones) que el
  usuario aprueba ANTES de programar (él sabe cómo lo hace SW); lógica en función + panel +
  pruebas; revisor y atacante; batería completa (capturas nuevas las aprueba el usuario); mouse
  contra SW; entrega con qué está probado y qué no; push. Lo que no se
  automatiza (parecido con SW, aspecto, sensación, piezas reales, taller) sigue siendo del usuario
  y de las pruebas con mouse contra SW.

## Límites conocidos (comunicar, no prometer)
Motor OpenCASCADE menos robusto que Parasolid en redondeos complejos; rendimiento con ensamblajes
grandes; los .SLDPRT/.SLDASM solo se pueden traer como sólidos sin historial (STEP o el addon de
importación de SolidWorks); TechDraw requiere más clics para acotar; archivos de 1.1 pueden no
abrir en versiones anteriores. Configuraciones (hechas 2026-11-01, sobre la tabla de configuración
nativa de la planilla): sin Excel; cada componente en otra configuración guarda una copia de la
pieza dentro del ensamblaje; suprimir un componente lo oculta (sigue cargado en memoria).
