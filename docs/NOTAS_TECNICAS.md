# Notas técnicas (para quien siga el trabajo)

## Probar
- Test sin GUI (antes de cada entrega): `D:\Freecad\bin\python.exe tools/test_load.py .`
  Debe terminar en `ERGEBNIS: OK`. Simula FreeCAD con objetos falsos (Qt = MagicMock).
- Prueba en FreeCAD REAL, sin tocar la configuración del usuario:
  `tools/fork/gui_probe.py` es una plantilla. Copiarla al scratchpad, completar los pasos y correr
  ```
  cp %APPDATA%/FreeCAD/v1-1/user.cfg <scratch>/user.cfg
  timeout 90 D:/Freecad/bin/freecad.exe -u <scratch>/user.cfg <scratch>/probe.py
  ```
  `-u` usa una copia de la configuración (FreeCAD la guarda al cerrar). El script escribe un
  JSON y capturas PNG; leerlas con la herramienta de imágenes.
  - Capturas: `mw.grab()` sirve para la interfaz; la vista 3D puede salir atrasada si hay
    animación (esperar o usar `view.saveImage(...)`).
  - Si FreeCAD queda colgado (diálogo modal, excepción sin cerrar), `timeout` lo mata. Cerrar
    siempre los documentos antes de `mw.close()` (si no, pregunta "¿guardar?" y se cuelga).
  - Envolver cada paso en try/except y volcar el JSON después de CADA paso.
  - Simular el mouse: `QApplication.sendEvent(viewport, QMouseEvent(...))` sobre
    `QGraphicsView.viewport()` de la vista `Gui::View3DInventor`.
- El usuario puede tener su FreeCAD abierto (proceso sin argumentos): no tocarlo.
- Pruebas de checklist: siempre comparativas, FreeCAD y SW 2018 manejados los dos con el mouse y
  el teclado (pedido del usuario); los guiones solo preparan piezas o miden.
- Teclas del fork dentro de LikeSolidWorks UI (como el SW del usuario): **barra espaciadora =
  Medir** (no alterna visibilidad: para ocultar, el ojo del árbol o clic derecho), N = normal a,
  F = ajustar, Ctrl+B / Ctrl+Q = reconstruir, 0/1/5 = isométrica/frontal/inferior.
- Medir colores de capturas del usuario: `QImage(...).pixelColor(x, y)` con el Python de FreeCAD.

## FreeCAD 1.1.4 en Windows: hallazgos
- Los nombres de objeto de formularios usan `__` en vez de `::` (`PartDesignGui__TaskPadPocketParameters`).
- Part Design cambia de banco al abrir cualquier diálogo de operación vía
  `Gui.activateWorkbench('PartDesignWorkbench')` ejecutado desde C++ (archivo `"<string>"`).
- La página de Inicio ("Cuerpo paramétrico", "Ensamblaje") cambia de banco desde C++ sin pasar por
  Python: solo se puede reaccionar después con la señal `MainWindow.workbenchActivated(nombre)`.
- `ParamGet(...).GetBools()` devuelve solo los NOMBRES (no pares nombre-valor).
- Observadores de documento en Python: `slotFinishRestoreDocument` y `slotBeforeRecomputeDocument`
  NO llegan (ni con interfaz, probado 2026-10-30). Para "al abrir": `slotCreatedDocument` + QTimer
  (el documento ya está cargado cuando corre). `doc.Recomputing` sí existe.
- Barra de menú: FreeCAD 1.1 trae `MenuBarLeftArea` / `MenuBarRightArea` como cornerWidgets.
  Para listar todos los menús: recorrer `menuBar().actions()` y `action.menu()` (emitir
  `aboutToShow` antes llena los dinámicos); la acción de cada comando tiene objectName = comando.
  Nombres reales en 1.1.4: `Std_CascadeWindows` (no WindowCascade), ayuda = `Std_FreeCADUserHub`,
  pantalla completa = `Std_MainFullscreen` (Alt+F11; F11 es `Std_ViewFullscreen`), cerrar = Ctrl+F4.
  Graphviz viene con FreeCAD (`D:\Freecad\bin\dot.exe`): el Gráfico de dependencias anda sin instalar nada.
- Menús propios del banco (`swui/fork/menus_sw.py`, probado en 1.1.4): el banco Python arranca con
  los menús estándar; `removeMenu` + `appendMenu(ruta, comandos)` los reemplazan (rutas de
  submenús, "Separator", comandos grupo como Std_RecentFiles salen como submenú). Trampas:
  (1) `reloadActive()` llamado mientras el banco arranca da "Access violation" y deja el banco roto
  -> armar todo DENTRO de Initialize, antes de que FreeCAD dibuje la barra; (2) sacar "&Help" da
  "Access violation" (FreeCAD lo usa de referencia; los menús nuevos van antes de "&Windows");
  `removeMenu` no saca entradas de adentro de un menú, solo menús enteros -> lo de Ventana / Ayuda
  se oculta con `QAction.setVisible`; (3) los nombres con tilde que se pasan a appendMenu llegan
  como Latin-1 ("EdiciÃ³n"): se arregla el texto con encode("latin-1").decode("utf-8");
  (4) con cualquier panel de tareas abierto (el croquis) FreeCAD apaga los comandos sin
  `"CmdType": "ForEdit"`; (5) FreeCAD no recalcula IsActive al abrir un menú ni al pasar a una
  hoja (y `FreeCADGui.updateCommands` no existe): se hace a mano en `aboutToShow`.
  Los subpuntos de Std_DrawStyle (Std_DrawStyleShaded...) no son comandos sueltos: van con índice.
  Los submenús (QAction con menu()) no se ponen grises solos: `_grey_submenus` los apaga si todo
  lo de adentro está gris; FreeCAD deja ocultos algunos separadores (antes de un submenú):
  `_show_separators`. El texto de un QAction de comando se puede cambiar al vuelo (Insertar >
  Croquis pasa a "Salir del croquis" en `aboutToShow`).
- Graphviz que viene con FreeCAD 1.1.4 (D:\Freecad\bin): sin registrar sus complementos ("Format
  png not recognized... dot -c"); `dot.exe -c` una vez en esa carpeta lo arregla (hecho el 01/11
  con permiso del usuario). Otra PC con FreeCAD recién instalado va a necesitar lo mismo (fase 6).
- Cancelar un panel nativo de PartDesign desde Python: `abortTransaction()` primero, después
  `resetEdit()` (que si no confirma) y `Control.closeDialog()`; la edición deja oculta la punta del
  cuerpo: volver a mostrarla (`dress_up_panel._cancel_native_edit`, `SwPanel.reject`).
- Croquis vacío: observador de documento (`slotCreatedObject`, croquis nuevos de la sesión) + de
  Gui (`slotResetEdit`) y borrar fuera del aviso con QTimer (`swui/fork/empty_sketch.py`).
- Al tabificar paneles, Qt deja barras de pestañas vacías encima de la buena: ocultarlas.
  FreeCAD repone la barra de título del panel Tareas al abrir operaciones: volver a quitarla.
- Preferencias útiles: `View/RotationMode`, `View/OrbitStyle`, `General/AutoloadModule`,
  `OutputWindow/checkShowReportViewOn*`, `Mod/Sketcher/View/EdgeWidth|ConstructionWidth|ConstructionPattern`,
  `View/HighlightColor|SelectionColor|DefaultShapeLineWidth|BackgroundColor2/3/4`.

## Herramientas (entorno de Claude Code)
- En la consola Bash, un `\n` dentro de un heredoc puede llegar convertido en salto de línea real
  al archivo: para textos con `\n` en código Python, editar con la herramienta Edit/Write.
- `git config core.autocrlf=true`: los avisos "LF will be replaced by CRLF" son normales.

## Arquitectura del fork
- `swui/fork/__init__.py` instala todo (cada parte en su try). Se llama desde `InitGui.Initialize`.
- Patrón: cambiar tablas/funciones del original desde afuera (`layout._dock_right`, `layout.enter`,
  `layout.leave`, `theme.COLORS`, `theme.build_qss`, `view_background._target_values`,
  `overlay_panels.TARGET`), marcando cada envoltura con un atributo `_swui_*` para no envolver dos
  veces. Toda preferencia que se cambie se guarda antes y se devuelve al salir del banco.
- `tools/test_load.py` (del original) tiene chequeos agregados del fork, marcados "fork".
- Selección: `getSelectionEx()` (resuelta) da las formas en coordenadas LOCALES del objeto;
  para la posición real (cuerpo girado, ensamblaje) usar `getSelectionEx("", 0)` y
  `raiz.getSubObject(sub)`; un `App::Plane` no tiene forma: `getSubObject(sub, retType=3)`
  da su Placement global.
- Cámara: `view.getCameraOrientation()` / `setCameraOrientation(Rotation)` (anima). Una
  animación en curso (p. ej. `viewIsometric()`) pisa un giro pedido enseguida: en pruebas,
  esperar ~1,5 s entre pasos.
- Atajos: `QTest.keyClick` dispara atajos de verdad (sendEvent no). Editando un croquis la
  vista 3D se queda con las teclas sueltas: los atajos de la ventana no llegan.
- `Std_ViewFitAll` SÍ anima (con "UseNavigationAnimations"): `animatedViewAll(10, 20)` corre
  los pasos DENTRO de la llamada (~0,35 s bloqueando) y recién después vuelve; por eso leer la
  cámara justo después la da final y parece instantáneo (error mío del 25/10, lo destapó un
  video del usuario). Medir el TIEMPO de la llamada, no la cámara. Sin animación: apagar la
  preferencia, `SendMsgToActiveView("ViewFit")`, prenderla (FreeCAD la aplica en el acto).
- `runCommand` desde dentro de otro comando queda para después (no correr un comando de
  FreeCAD desde el Activated de otro si importa el momento).
- Un atajo de varias teclas que empieza con la tecla suelta ("F, S" de Part_SelectFilter,
  acción [2] del grupo, invisible para `Command.get(...).getShortcut()`) hace esperar ~0,3 s
  a la tecla suelta. Buscar con `mw.findChildren(QAction)` y `shortcuts()`.
- Menú de clic derecho: `FreeCADGui.addWorkbenchManipulator(obj)` con
  `modifyContextMenu(recipient)` (recipient "Tree" o "View") que devuelve
  `[{"insert": cmd, "menuItem": "Std_Placement"}]` inserta ANTES de ese comando ("Separator" vale).
  El manipulador es global: revisar el banco activo. En el árbol FreeCAD igual pone arriba las
  opciones del objeto ("Editar vaciado", "Suprimido", "Toggle Freeze"): `feature_tree.arrange_menu`
  las reordena al mostrarse el menú (filtro de eventos de la aplicación, solo dentro del banco).
  Las acciones de comandos tienen objectName = nombre del comando.
- **No usar Std_ToggleFreeze**: con un croquis congelado, guardar el documento cuelga FreeCAD 1.1.4
  (probado dos veces). Para suprimir sin errores, apagar el apoyo del croquis (MapMode "Deactivated").
- Part Design: las operaciones de sólido son `isDerivedFrom("PartDesign::Feature")` (croquis, planos
  de referencia y binders no). `Suppressed` existe en 1.1.4. Los vínculos de una operación incluyen
  `BaseFeature` (el sólido anterior: no es "padre" en sentido SW) y `_Body`.
- Árbol (`Gui::TreeWidget`): **no guardar QTreeWidgetItem** para usarlos después; PySide los da
  por borrados ("Internal C++ object already deleted"). Medir rectángulos en el momento. Los
  renglones se relacionan con objetos por Label (`doc.getObjectsByLabel`); el renglón de primer
  nivel es el documento. Dibujar encima: widget hermano del viewport (hijo del árbol, no del
  viewport, así no se corre al desplazar), transparente al mouse; arrastre con filtro en el viewport.
- Estilo de los renglones del árbol: FreeCAD 1.1 los pinta con el estilo de una vista interna
  `QTreeView#DocumentTreeItems` (hija de `Gui::TreeWidget`): un estilo cambiado solo en el
  TreeWidget no se ve. Una regla `::item:selected` agregada al final no le gana a la primera:
  sacar la vieja (regex) y poner la nueva. Estilar `::branch` borra la flechita de abrir/cerrar;
  la zona de la flechita se pinta con el fondo de `::item:selected`.
- Part Design: `Body.removeObject(f)` + `Body.insertObject(f, otro, after)` reordena y reengancha
  BaseFeature solo; si se saca la punta, la punta pasa a la anterior (volver a ponerla).
  `Shape.getElementHistory` no devuelve nada útil en 1.1.4: para "qué operación creó esta cara"
  se compara geometría (misma superficie en la operación anterior).
- Redondeo/chaflán (`PartDesign::DressUp`): `Base` = (sólido anterior, ["EdgeN"...]) y FreeCAD
  lo sigue al cambiar BaseFeature, pero con los MISMOS números de arista: al reordenar quedan en
  otra arista o con error. `feature_tree.move` guarda la forma de cada arista antes y las vuelve a
  buscar por forma (misma recta/circunferencia y superpuestas) en el sólido nuevo.
- Croquis en edición: el modelo no se puede preseleccionar, pero `view.getObjectsInfo((x, y))`
  (coordenadas Coin: y desde abajo, píxeles reales = Qt * devicePixelRatio) devuelve también las
  aristas cercanas del sólido. Con una herramienta del croquis activa el cursor del viewport es
  `BitmapCursor`. `sketch.addExternal("Pad", "Edge10")` + `sketch.recompute()` y un MouseMove
  sintético en el mismo punto: el croquis la preselecciona y el clic la toma. No usar
  `view.getCursorPos()` (es el cursor real, no el del evento). Dos Esc seguidos cierran el croquis.
  `view.getPointOnViewport` da puntos fuera de la ventana si la cámara no los muestra (ajustar antes).
  Es rápido (~0,05 ms por punto): proyectar aristas discretizadas una vez por posición de cámara.
  Resaltar en la vista: pivy `SoAnnotation` (encima de todo) con SoLineSet/SoMarkerSet agregado a
  `view.getSceneGraph()`. Forma global con los mismos índices: `Part.getShape(raíz, "Pad.")` usando
  `obj.getParents()`. Una referencia externa encima de un eje del croquis le gana al eje en la
  preselección.
- Sin herramienta (cursor flecha) la preselección del croquis (`Selection.getPreselection()`)
  no se actualiza con movimientos sintéticos y puede quedar vieja: medir en pantalla si hay
  geometría del croquis cerca (`View/PickRadius`). En ese modo el croquis elige al SOLTAR el
  botón: para sumar una referencia a la selección usar
  `Selection.addSelection(doc, sketch, "ExternalEdgeN")` (N desde 1, orden de ExternalGeometry)
  y no dejar pasar ese soltar.
- `PySide.QtTest` no existe en el envoltorio de FreeCAD: `from PySide6.QtTest import QTest`.
  Los íconos del árbol y la vista 3D se refrescan después: capturar ~1 s más tarde.
- Videos: medir cuadro a cuadro con ffmpeg a 30 fps en gris crudo + numpy (caja de píxeles
  oscuros de la pieza por cuadro); las hojas de miniaturas no alcanzan para ver animaciones.
- Videos del usuario: ffmpeg 9.0.2 instalado con winget (Gyan.FFmpeg, solo su usuario) en
  `%LOCALAPPDATA%/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build/bin/`
  (alias `ffmpeg` en consolas nuevas). Sacar cuadros: `ffmpeg -i video.mp4 -vf fps=2 <scratch>/c_%03d.png`.
- Reemplazar un diálogo de operación por uno propio: observador de documento de Gui
  (`FreeCADGui.addDocumentObserver`) con `slotInEdit(vp)`; fuera del slot (QTimer 0)
  `Control.closeDialog()` cierra el diálogo nativo SIN cancelarlo: la operación, el modo edición
  y la transacción del comando ("Make Fillet") quedan abiertos. Editar una existente no abre
  transacción (abrir una propia). **`resetEdit()` confirma la transacción pendiente**: para
  cancelar, `abortTransaction()` primero y después `resetEdit()`. Sin selección,
  `PartDesign_Fillet` crea igual el redondeo (vacío, con error) sobre la punta y lo pone en edición.
  Para evitar ese error, `dress_up_panel.start_empty` (enganchado en `pick_plane.handle`, por
  donde la cinta pasa cada botón) hace `body.newObject(...)` + `Base = (BaseFeature, [])` +
  `setEdit` dentro de una transacción propia, sin recalcular.
- Una ventana Qt abierta pero oculta: `close()` no le manda `closeEvent`; lo que limpie ahí hay
  que llamarlo aparte (`measure_sw._MeasureWindow.shutdown`).
- Pruebas con el mouse (computer-use) en SW y FreeCAD: ver `docs/ESTADO.md` > "Pruebas
  comparadas con SW". Un .py pasado a `freecad.exe -u <cfg> script.py` corre con GUI: sirve para
  armar la pieza de prueba visible (un .FCStd hecho con FreeCADCmd abre con todo oculto).
- En el envoltorio de PySide de FreeCAD 1.1 (Qt6), `QAction` está en `QtGui`, no en `QtWidgets`.
- Paneles SW sobre operaciones nativas (`swui/fork/dress_up_panel.py`): base `SwPanel` +
  registro `PANELS` {TypeId: clase}; `pattern_panel.py` y `hole_panel.py` suman los suyos en su
  `install()`. Para un tipo nuevo: subclase con `_build` (self.form), `_apply` (valores al objeto,
  devuelve un problema o ""), `_pick(obj, sub)` y registrarla.
- La "vista previa superpuesta" magenta de Part Design es la preferencia
  `Mod/PartDesign/Preview/ShowTransparentPreview`; se apaga con la casilla
  `showTransparentPreviewCheckBox` del diálogo nativo antes de cerrarlo y se devuelve al cerrar.
- `PartDesign_LinearPattern/PolarPattern/Mirrored/Draft/Hole` crean el objeto y lo ponen en edición
  igual que el redondeo (sin selección: matriz/simetría arrancan en "Whole shape"). La matriz
  circular pide una ARISTA como eje ("Axis reference must be an edge"): una cara cilíndrica se
  cambia por un borde circular suyo. `ThreadSize` del taladro: "M6x1.0" (no "M6"); con
  `ThreadType` "None" el tamaño es "---". Las tablas de tornillos están en
  `<recursos>/Mod/PartDesign/Resources/Hole/*.json` (`cut_type` counterbore/countersink).
- Taladro sin selección: `pick_plane.FEATURE_COMMANDS` (del original) se extiende desde el fork
  con `PartDesign_Hole`, y `pick_plane.arm` se envuelve para prender `Sketcher_CreatePoint`.
- En las pruebas: no llamar `dump` a una función propia (la plantilla ya tiene `dump()`); una lista
  guardada en el log se vuelca al final (guardar copias: `list(...)`).

## Fase 3 (Evaluar): hallazgos en FreeCAD 1.1.4
- Materiales: `Materials.MaterialManager()`; `MaterialLibraries` da tuplas (nombre, carpeta,
  ícono): "System" (`D:/Freecad/data/Mod/Material/Resources/Materials`) y "User"
  (`%APPDATA%/FreeCAD/v1-1/Material`, no existe hasta que se guarda algo). Con las preferencias
  `Mod/Material/Resources` UseMaterialsFromConfigDir=False, UseMaterialsFromCustomDir=True y
  CustomMaterialsDir=<carpeta> aparece una biblioteca "Custom": así se prueba sin tocar la del
  usuario (en una copia de user.cfg). No hay `defaultMaterial()`: el "Default" tiene UUID
  `7f9fd73b-50c9-41d8-b7b2-575a030c1eeb` (está en System y tiene densidad: filtrarlo).
- `ShapeMaterial` se guarda en el archivo SOLO como UUID (`<PropertyMaterial uuid=.../>`). Material
  que falta al abrir: "Material not found" en la consola y queda "Default". Un .FCMat escrito a
  mano (YAML, ver `material.fcmat_text`) con el mismo UUID + `refresh()` lo vuelve a encontrar.
  `refresh()` NO olvida un material cuyo archivo se borró (sigue hasta reiniciar): las pruebas de
  "material faltante" van en otro proceso.
- Asignar `ShapeMaterial` desde Python no cambió `ShapeAppearance` en la prueba, pero igual se
  guarda y se devuelve la apariencia (versiones nuevas podrían cambiarla).
- `getPhysicalValue` da Quantity (`getValueAs("kg/m^3")`), float (Poisson, en float32: 0,29 ->
  0,28999999) o None; propiedad del modelo sin valor = nan.
- Inercia: `Solid.MatrixOfInertia` es el tensor en el centro de masa con densidad 1 (fuera de la
  diagonal -∫xy). Un compuesto no tiene MatrixOfInertia ni CenterOfMass: sumar sólido por sólido
  (Steiner, `mass_props.combine`).
- Expresiones: aceptan coma decimal (FreeCAD la guarda como punto), trigonometría en grados,
  `a ? b : c`, `trunc`, `sqrt`. En un VarSet FreeCAD guarda las referencias a sí mismo SIN el
  nombre del objeto ("Largo / 4"). Una PropertyFloat acepta un resultado con mm (lo guarda sin
  unidad). Ruta de una cota de croquis: `.Constraints.D1` o `.Constraints[3]`; de una operación,
  `Length` (sin punto). `renameConstraint(i, "D1")` deja la ecuación atada aunque se borren cotas.
  `setDocumentationOfProperty` cambia el comentario de una propiedad dinámica.
- `doc.openTransaction` al abrir la ventana + varios cambios + `abortTransaction` deshace todo
  (también un VarSet creado y un renombre de cota). Por eso Ecuaciones es modal.
- Selección en ensamblajes: el observador (`addSelection(doc, obj, sub, pnt)`) recibe el objeto
  RESUELTO (p. ej. "Box", "Face6"), sin la ruta del componente. La ruta completa sale de
  `Selection.getSelectionEx("", 0)` (raíz "Ensamblaje", sub "Pieza1.Box.Face6");
  `raíz.getSubObject(sub)` da la forma en su posición real y `Part.getShape(raíz, "Pieza1.",
  needSubElement=False)` el sólido entero ubicado. Los vínculos del original se llaman "Body<1>".
- Un clic del usuario en la vista llega como clearSelection + addSelection; un clic en el vacío,
  solo clearSelection: Medir espera 60 ms para distinguirlos.
- Las ventanas sueltas (QDialog) no salen en `mw.grab()`: capturarlas con `dialogo.grab()`.
- El test arma la cinta esperada desde `ribbon_layout.py` por AST; el fork suma
  `swui/fork/evaluate_tab.py` (`_fork_layout_commands`, `FORK_REPLACED`) y sus textos en castellano
  no se exigen en de/en.
- Distancia máxima (`max_distance.py`): OpenCASCADE no la trae (BRepExtrema/distToShape es solo la
  mínima). `Edge.valueAt(t)` / `Face.valueAt(u, v)` dan el punto en posición real (con la
  ubicación de la forma); `Face.ParameterRange` y `Face.isInside(p, tol, True)` para caras
  recortadas. Las esferas tienen aristas degeneradas (polos, `Edge.Degenerated`) cuyo `.Curve`
  da "undefined curve type": saltearlas. La primera llamada tarda ~1,5 s más (carga de numpy).

## Multicuerpo (etapa B): hallazgos en FreeCAD 1.1.4
- Diálogos nativos de operación: el formulario (`PartDesignGui__TaskPadPocketParameters`...) vive
  en un `Gui::TaskView::TaskPanel` que FreeCAD REUSA entre diálogos: un widget agregado al panel
  queda en el diálogo siguiente (sacarlo al cerrar). Agregado adentro del formulario, FreeCAD lo
  destruye al cerrar: leer lo que haga falta ANTES.
- Aceptar: conectar a `pressed` del botón OK del `QDialogButtonBox` visible; `accepted` no llega
  (FreeCAD cierra y destruye el diálogo en su propio manejo, antes que el nuestro). Enter aprieta
  el botón por defecto y también emite `pressed`. Al cerrar llega `slotResetEdit(vp)` (observador
  de documento de Gui); FreeCAD avisa `slotInEdit` dos veces al editar una operación existente.
- Radiobotones creados sin dueño y marcados antes de ponerlos en un layout no son excluyentes:
  usar `QButtonGroup` (o crearlos con dueño).
- `PartDesign_Pad` desde el diálogo deja `ReferenceAxis = (croquis, ['N_Axis'])`: al pasar la
  operación a otro Cuerpo ese vínculo queda fuera de alcance y da "Invalid shape name N_Axis".
  Con perfil = SubShapeBinder la dirección sale del perfil: se borra (`ReferenceAxis = None`).
- Croquis de un Cuerpo apoyado directo en una cara de otro: la extrusión se trae el otro sólido
  (base implícita). Usar SubShapeBinder del croquis (o de la cara) dentro del Cuerpo nuevo.
- Recta de referencia sobre el eje de un croquis: `PartDesign::Line` con
  `AttachmentSupport = [(croquis, "")]` y `MapMode = "ObjectY"` (V_Axis) / `"ObjectX"` (H_Axis);
  apoyarla en `(croquis, "V_Axis")` da error del motor de apoyo.
- Expresiones de un Pocket a otro Pocket de OTRO Cuerpo: funcionan, también en propiedades de
  enumeración (`Type`) y booleanas (`Reversed`). `Midplane` está obsoleto en Pocket (avisa): usar
  `SideType`. Groove 1.1.4 todavía usa `Midplane`.
- Un `App::PropertyLink` hacia un objeto de otro Cuerpo da aviso "go out of the allowed scope":
  usar `App::PropertyLinkGlobal`.
- "Qué sólidos atraviesa un corte": `feature.AddSubShape` (herramienta, en coordenadas del Cuerpo)
  contra la forma de cada sólido ANTES del corte (en el propio, `BaseFeature.Shape`; la forma del
  Cuerpo ya tiene el agujero y el común da 0).
- `swui/naming.py` del original renombra a lo SW toda operación nueva en un QTimer(0): lo que
  arma el asistente vuelve a poner su nombre en otro QTimer(0) posterior (`multibody._keep_label`).
- Probar sin GUI: un FeaturePython definido en el script de prueba no se puede reabrir en otro
  proceso (1.1.4 bloquea importar módulos que no sean de FreeCAD o de addons instalados).
- Supr: los atajos se resuelven con `QEvent.ShortcutOverride` (al widget con foco) ANTES del
  KeyPress: un filtro de la QApplication que escucha solo KeyPress llega tarde (Std_Delete ya
  corrió). Escuchando ShortcutOverride, sumar objetos a la selección hace que Std_Delete los borre
  en el mismo paso y sin el aviso de "objetos que dependen". Para probar el atajo real:
  `QTest.keyClick(ventana_principal, Key_Delete)` con la ventana activa y esperando ~1 s después de
  cambiar la selección (FreeCAD habilita Std_Delete con un pequeño retraso; antes no dispara).
- `slotDeletedObject` (observador de App) llega con el objeto todavía vivo: guardar los nombres y
  borrar otras cosas en un QTimer (borrar adentro del aviso es reentrante).
- Separar una extrusión en el `pressed` de Aceptar (para un solo paso de deshacer) NO sirve:
  el Aceptar de FreeCAD vuelve a aplicar la dirección del diálogo (`ReferenceAxis` al croquis).
- Simetría de Part (`Part::Mirroring`): `MirrorPlane` acepta planos del origen y caras, pero IGNORA
  en silencio un `PartDesign::Plane` (y una SubShapeBinder de él): usa Normal/Base por defecto.
  Apuntar a través del Cuerpo (`(Cuerpo, "Origin.YZ_Plane.")`, `(Cuerpo, "Pad.Face6")`) evita el
  aviso "fuera de alcance". Para un plano de referencia: ecuaciones
  `Base = <<Cuerpo>>.Placement * <<Plano>>.Placement.Base` y
  `Normal = <<Cuerpo>>.Placement.Rotation * <<Plano>>.Placement.Rotation * vector(0; 0; 1)`.
- Ecuaciones: un objeto llamado "A" no se puede nombrar así (es la unidad amperes): usar
  `<<Etiqueta>>`. No se puede tomar `.Base` de un paréntesis (`(a * b).Base` no se entiende).
- Un Cuerpo puede arrancar de cualquier sólido: `Body.BaseFeature = objeto` (simetría, pieza de un
  Dividir...); queda paramétrico.
- Pruebas: `PartDesign_Hole` (y otros comandos de Part Design) sin Cuerpo activo abren el aviso
  modal "Cuerpo Activo Requerido" y la prueba queda colgada (el usuario lo vio en su pantalla):
  `FreeCADGui.ActiveDocument.ActiveView.setActiveObject("pdbody", cuerpo)` antes del comando.

## Mover cara (fase 4): hallazgos en FreeCAD 1.1.4
- Pad / Pocket aceptan como `Profile` caras del sólido anterior `(operación, ["Face6", "Face9"])`:
  el Pad sale según la normal de la cara (también la de abajo, hacia -Z), el Pocket entra.
- `PartDesign::Draft` gira una cara alrededor de una arista: `NeutralPlane` = cara plana que
  contiene la arista; `PullDirection` = arista recta perpendicular a ella dentro de la cara (la
  cara queda paralela al tiro y el ángulo es el giro). Prolonga las vecinas aunque sean inclinadas.
  Si la cara girada atraviesa la de enfrente, falla sin mensaje (`Draft: ` vacío).
- Un plano de referencia con MapMode OXY/OXZ/OZX apoyado en (vértice, arista, cara) sale paralelo
  a la cara en vez de contener su normal: no sirve para el plano neutro.
- `Body.BaseFeature = sólido`: el Cuerpo toma la forma SIN el Placement del sólido (lo mismo con una
  SubShapeBinder o un Clon con Placement): copiar el Placement al Cuerpo.
- `doc.removeObject(nombre)`: leer `obj.Name` antes (después da "deleted object").
- `SwPanel.preview` vuelve a leer `self.obj` después de `_apply` (un panel puede cambiar la
  operación por otra); `dress_up_panel.CHOOSERS` elige el panel por marca antes que por TypeId.
- (2026-10-31) Pad/Pocket `Type` en 1.1.4: Length, UpToLast, UpToFirst, UpToFace, TwoLengths,
  UpToShape. "UpToFace" acepta una cara de otro objeto y `Offset` (negativo = se queda antes).
  "UpToFace"/"UpToShape" con un vértice: forma inválida. "UpToShape" con un sólido entero (sin
  subelementos o con todas sus caras): no llega ("Unable to reach the selected shape").
- El `Offset` de "Hasta cara" NO es "antes de la superficie" siempre: con la cara +X de una caja
  hacia la cara +X de otra que no la tapa (no se superponen al proyectar), -2 quedó 2 mm DESPUÉS
  (57 en vez de 53); con superficies que la tapan, -2 queda antes. Equidistante usa un plano
  (FlatFace sobre la superficie + AttachmentOffset en Z, con el signo según el Z del plano).
- Dentro de un Cuerpo, el árbol de FreeCAD 1.1.4 muestra los objetos con ShowInTree = False
  (fuera de un Cuerpo los esconde): hay que esconder el renglón (QTreeWidgetItem.setHidden).
- SheetMetal (SMUnfold.execute) arma los croquis en FreeCAD.ActiveDocument: si se recalcula con
  otro documento activo, caen ahí.
- FreeCAD rearma la barra de menús sin emitir workbenchActivated (al abrir un ensamblaje):
  QEvent ActionAdded/ActionChanged en el menuBar.
- Plano de referencia por un vértice y paralelo a una cara: MapMode "OXY" (también OZX/OZY) con
  (vértice, arista de la cara, cara). Con solo (vértice, cara) queda inválido; "Translate" no
  sirve para "Hasta cara".
- Una operación de PartDesign no puede apuntar a caras de otro Cuerpo o de un sólido suelto
  (fuera de alcance): pasar por un `PartDesign::SubShapeBinder` dentro del Cuerpo (su forma es
  "Face1"/"Vertex1").
- `PartDesign::Draft`: `PullDirection` acepta una arista o una `PartDesign::Line` ("No pull
  direction reference specified" con un plano); `NeutralPlane` acepta un `PartDesign::Plane`.
  La cara gira hacia el sentido del tiro (sin Invertir). Lo que fallaba "según el sentido y el
  ángulo" (caja 50x30x10 con agujero: 10° hacia un lado falla, 5° anda) era un error de FreeCAD
  con la ubicación de la operación anterior (ver "Errores de FreeCAD encontrados", 1): arreglado
  en el fork el 2026-10-31 (`move_face.place_draft` / `draft_misplaced`).
- Nombres de caras (2026-11-01, FreeCAD 1.1.4): un Pad sobre una cara de la operación anterior
  sigue bien a la cara aunque cambie de número (espesor, agujero que deja de atravesar, otro
  agujero, agujero suprimido: Face5 -> Face6 correcto). La da por perdida ("?Face3", "Sub shape
  not found", operación con error) cuando la cara se parte en dos. En un SubShapeBinder no marca
  '?': borra el elemento (Support queda `(obj, ('',))`, el sólido entero) y el "Hasta cara" que lo
  usa salta a otra cara del sólido. A veces sigue a UNO de los pedazos sin avisar.
- Escribir una propiedad (también un PropertyString propio) deja la operación "Touched" (para
  recalcular). Con `setPropertyStatus(prop, ["Output", "NoRecompute"])` no; el estado se guarda en
  el archivo (probado al reabrir).
- Sketch con MapMode "SectionOfRevolution", "Concentric" u "ObjectXZ" sobre una cara cilíndrica:
  inválido. El croquis del anillo va con Placement fijo (MapMode "Deactivated").
- Las expresiones leen la forma: `Cyl.Shape.Faces[0].Surface.Radius` = 4 (no se usó: depende del
  número de la cara igual que una referencia).
- El observador de documento `slotRecomputedDocument` sí llega (con interfaz, 2026-10-31): lo usa
  el aviso de Mover cara atrasado (`move_face.check`, después con QTimer 0). Al abrir un archivo:
  `slotCreatedDocument` + QTimer.
- Un primitivo de PartDesign (AdditiveBox, SubtractiveCylinder) suelto (sin apoyo) ignora
  `AttachmentOffset`: ubicarlo con `Placement` (en las pruebas).

## Errores de FreeCAD encontrados (para reportar)
Los reporta el usuario si quiere (política de IA de FreeCAD: Claude no publica issues ni PR allá).
Cada uno con lo que hace el fork mientras tanto. Buscado en los issues de FreeCAD/FreeCAD el
2026-10-31: no estaban reportados.

1. **PartDesign Draft (Ángulo de salida) gira alrededor de una bisagra corrida en el primer
   cálculo** (FreeCAD 1.1.4; sigue igual en `main`, semanal 2026-10-28). En
   `src/Mod/PartDesign/App/FeatureDraft.cpp`, `Draft::execute()` pasa el tiro y el plano neutro a
   coordenadas locales con `this->getLocation().Inverted()` (líneas ~174 y ~300) ANTES de
   `this->positionByBaseFeature()` (~315), que recién ahí copia el Placement de la operación
   anterior. La forma base se usa sin transformar (`baseShape.setTransform(Matrix4D())`), o sea en
   las coordenadas de la operación anterior: si el Placement del Draft todavía no es el de ella,
   plano y tiro quedan corridos esa diferencia.
   - Cuándo pasa: la operación anterior tiene Placement propio. En 1.1.4 las operaciones con
     croquis (Pad, Pocket, Hole, Fillet, Mirrored...) quedan en el origen y no lo disparan; sí las
     primitivas de PartDesign (AdditiveBox, SubtractiveCylinder...) ubicadas fuera del origen, y
     un sólido base movido. Al crear el Draft (Placement identidad) o cuando cambia el Placement
     de la anterior.
   - Prueba (FreeCADCmd): Body; AdditiveBox 50x30x10; SubtractiveCylinder R5 H10 en (25,15,0);
     Draft de la cara de arriba, NeutralPlane = cara x=50, PullDirection = arista de 50 de largo
     de arriba, 10°. Da volumen 26 746,7 y ZMax 23,225 (bisagra en x=75); lo correcto es
     20 480,6 y 18,816. Con Reversed y 10° falla sin mensaje ("Draft: "). Un segundo recálculo
     (`d.touch(); doc.recompute()`) o poner antes `d.Placement = anterior.Placement` da exacto.
   - Arreglo propuesto: llamar a `positionByBaseFeature()` antes de transformar plano y tiro.
   - Fork: `move_face.place_draft` copia el Placement antes de calcular y anota el usado en
     "plc"; `draft_misplaced` marca "desactualizado: Ctrl+Q" si la anterior cambió de ubicación.
2. **Draft con Reversed descarta en silencio las caras que OpenCASCADE no acepta.**
   `Draft::execute()` llama `makeElementDraft(..., angle, neutralPlane, reversed)` y en
   `TopoShape::makeElementDraft` (`src/Mod/Part/App/TopoShapeExpansion.cpp`, ~4718) ese último
   parámetro es `retry`: si `BRepOffsetAPI_DraftAngle::AddDone()` falla, con retry saca la cara y
   sigue (solo un FC_ERR en el registro); sin retry no. O sea, el sentido cambia si un error se
   avisa o se traga, y la operación puede quedar "válida" sin girar nada.
   - Fork: el panel de Mover cara mira el resultado (`face_rotated`) y avisa "FreeCAD dejó la
     cara sin girar".
3. **Una unión de Assembly guarda un nombre de cara viejo cuando el vínculo pasa a otra copia
   (LinkCopyOnChange)** (FreeCAD 1.1.4, encontrado 2026-11-01). Si un `App::Link` con
   `LinkCopyOnChange` cambia de objeto vinculado (primer cambio de configuración en "Enabled":
   del original a la copia; o la recopia de "Tracking" cuando cambia la pieza), la unión sigue
   bien en la sesión pero `Reference1/2` se guarda con el nombre "mapeado" del objeto anterior; al
   reabrir: `missing element reference ... Face5`, "?Face5", "Broken link in: Reference1". Buscado
   el 01/11: #14056 (desplazamientos con CopyOnChange en Assembly) se cerró por inactividad, sin
   arreglo; esto no estaba reportado.
   - Prueba (FreeCADCmd): Placa con tabla de configuración en el Body (prop. `Configuracion` con
     estado CopyOnChange); ensamblaje con dos Link "Enabled" (Corta = original, Larga = copia),
     Distance 0 entre cara de arriba de uno y de abajo del otro; pasar el primero a "Media" y
     volver; guardar; reabrir -> Reference1 "?Face5". Con "Owned" (copia desde el principio) no pasa.
   - Lo que NO arregla: volver a asignar la misma referencia, ni `touch()` + recalcular.
     Lo que SÍ: `j.Reference1 = None` y después `j.Reference1 = [obj, ["Face5", "Face5"]]`, antes
     de guardar (probado en los dos casos, Enabled y Tracking).
   - Fork (`config_asm.refresh_joints`): en cada cambio de configuración del componente o
     recopia, vuelve a ubicar cada cara por geometría (`mate_refs._fix_ref`: entre configuraciones
     las caras se renumeran, el nombre simple solo no alcanza: la placa quedaba a z=7 en vez de 10)
     y vacía y vuelve a poner la referencia.
4. **En la copia de un componente (LinkCopyOnChange), un croquis apoyado en una cara de una
   operación que estaba suprimida al copiarse no la vuelve a encontrar** (FreeCAD 1.1.4,
   2026-11-01). La copia se hace con la pieza en una configuración donde la operación (Pad001)
   está suprimida; al pasar el componente a otra donde no lo está, el apoyo del croquis queda
   "?Face8" ("No planar face in AttachEngine3D") y frena el recálculo de TODA la copia: el
   componente muestra la forma de la configuración vieja. Con interfaz, además, FreeCAD quedó
   recalculando en bucle (repetía el aviso) hasta que lo cortó el timeout. En la pieza misma no
   pasa (mismo archivo, cambiar de configuración ahí anda bien).
   - Prueba (FreeCADCmd): pieza con configuraciones donde un saliente con un croquis encima se
     suprime en la activa (Nuc.FCStd de las pruebas); ensamblaje con un Link "Tracking";
     `l.Configuracion = "Larga"` -> volumen viejo y "Croquis002" inválido.
   - Arreglo: `obj.AttachmentSupport = None` y volver a ponerlo con el nombre simple ("Face8");
     queda bien para siempre en esa copia. Fork: `config_asm.repair_copy`.
5. **LinkCopyOnChange no copia si el valor nuevo es igual al de la pieza, y "Tracking" no vuelve
   a poner en la copia las propiedades del vínculo** (FreeCAD 1.1.4, 2026-11-01, visto con el
   mouse). (a) `l.LinkCopyOnChange = "Tracking"; l.Configuracion = <la misma que tiene la
   pieza>` no hace la copia (`LinkedObject` sigue siendo la pieza; `LinkCopyOnChangeTouched =
   True` tampoco): el componente cambia cuando cambia la pieza. (b) Con la copia hecha, al cambiar
   la pieza el primer recálculo del ensamblaje vuelve a copiarla y muestra la forma de la pieza
   (con el valor de la pieza); recién el SEGUNDO recálculo aplica el valor del vínculo.
   - Prueba (FreeCADCmd): pieza con 2 configuraciones (Placa de m1h); ensamblaje con un Link;
     `ca.set_config(l, <la activa>)` -> `l.LinkedObject` es la pieza. Pasando por otra y
     volviendo, hay copia; `body.Configuracion = <otra>; recompute` -> el componente toma la
     forma de la otra; un `ad.recompute()` más -> vuelve a la suya.
   - Arreglo del fork: `config_asm._force_copy` (pasar por otra configuración y volver) y
     `settle_doc` / `settle_assembly` (recalcular hasta que no quede nada tocado, después de
     cualquier recálculo de una pieza con componentes configurados abiertos).

## Chapa (fase 1): hallazgos con SheetMetal 0.8.26 en FreeCAD 1.1.4
- SheetMetal se importa por módulos (`SheetMetalBaseCmd`, `SheetMetalCmd`, `SheetMetalUnfoldCmd`):
  al importarlos registran sus comandos aunque su banco no esté activo. Sus objetos dentro de un
  Cuerpo son `PartDesign::FeaturePython`; el Unfold va en la raíz (`Part::FeaturePython`). Al abrir
  un archivo, FreeCAD carga sus módulos solo (hace falta el addon instalado).
- El desarrollador nuevo necesita networkx: está en `%APPDATA%/FreeCAD/v1-1/AdditionalPythonPackages`.
- Los croquis del desarrollo (`GenerateSketch`) solo con interfaz: sin GUI falla en
  `ViewObject.DrawStyle` y el Unfold queda inválido. `SeparateSketchLayers` da `<Label>_Sketch`
  (contorno), `_Sketch_Bends`, `_Sketch_Internal`, `_Sketch_Holes`, `_Sketch_Bend_Labels`; los
  busca por `Name.startswith(...)` del Label: Label sin espacios ni paréntesis, o crea croquis
  nuevos en cada recálculo. Los croquis quedan en el plano XY con Placement identidad.
- El exportador DXF de FreeCAD (`importDXF.export`) pone la capa según el grupo o la capa de Draft
  que contiene al objeto ("0" si no hay) y no lleva el tipo de línea: por eso el DXF lo escribe
  el fork. `importDXF.insert` en una prueba abre una ventana y la prueba queda colgada.
- Factor K: el Unfold tiene `KFactorStandard` "ansi" (K de SW, 0,5 = mitad del espesor) o "din"
  (el doble). La brida de arista tiene su propio `kfactor` (solo para su vista "unfold").
- Editar (setEdit) un objeto de SheetMetal abre su transacción y su panel; `resetEdit` llama a su
  `unsetEdit` (cierra el diálogo y oculta el `baseObject`) y la transacción queda abierta.
- (2026-10-31) Los croquis del desarrollo se llaman "<Label>_Sketch..." y se buscan por Name: con
  un espacio en el Label ("Chapa desplegada1") FreeCAD cambia el Name ("Chapa_desplegada1_...") y
  SheetMetal los borraba y creaba de nuevo en cada recálculo. `sheet_metal.patch_sketch_names`
  envuelve `SheetMetalNewUnfolder.SketchExtraction.edges_to_sketch_object` y le pasa el nombre ya
  como lo deja FreeCAD (probado: los mismos 3 croquis después de recalcular).
- Brida base cerrada: `Reverse` cambia el lado del espesor (`BendSide` no hace nada). Abierta:
  `BendSide` Inside = el croquis es la medida de afuera, Outside = de adentro, Middle = al medio.

## Mover/Copiar y Eliminar/Conservar sólidos: hallazgos en FreeCAD 1.1.4
- SubShapeBinder de un Cuerpo entero (`Support = [(Cuerpo, "")]`), en la raíz: su forma está en
  posición real (incluye el Placement del Cuerpo). Un Cuerpo que arranca de ella con
  `Body.Placement = P` queda en P * forma real.
- `CompoundTools.CompoundFilter` con `FilterType = "collision-pass"` y `Stencil = Part::Vertex`
  adentro de un pedazo se queda con ese pedazo; si cambian las cotas sigue el mismo (elegir por
  número de orden se cruza). Reabierto sin el addon funciona (es de FreeCAD).
- Un panel propio que limpia la selección en su `__init__`: leer la selección ANTES de crearlo.
- Nombres de operaciones agrupadas por una marca ("op"): calcular el siguiente libre con las
  marcas, no solo con los Label (los objetos se llamaban "...1 (2)" y el "...1" quedaba libre).
- Ecuaciones con vectores constantes: `vector(10; 0; 0) + Punto.Placement.Base * 2` funciona en
  `Body.Placement.Base` (`setExpression(".Placement.Base", ...)`). `Part::DatumPoint` (raíz,
  MapMode "Vertex", apoyo `(Cuerpo, "Box.Vertex3")`) no deriva de Part::Feature: no "consume".
- Tomar Supr para algo propio: aceptar el ShortcutOverride en un filtro de la aplicación (la tecla
  llega como KeyPress y Std_Delete no corre) y actuar en el KeyPress (`delete_bodies._DeleteKey`).

## Ensamblaje (fase 5): hallazgos en FreeCAD 1.1.4 (pruebas sin GUI, 2026-10-27)
- Crear uniones por script (FreeCADCmd): `asm.Type = "Assembly"` (si no, `setJointConnectors` no
  resuelve); `JointObject.Joint(j, JointTypes.index("Distance"))` en un `App::FeaturePython` del
  JointGroup; referencias = `[componente, [sub, sub]]` con
  `UtilsAssembly.getComponentReference(asm, asm, "Placa.Body.Face7")` -> `(Placa, "Body.Face7")`.
  `asm.solve()` devuelve 0 si converge; no hay API de redundantes/grados de libertad en Python.
- Concéntrica (Cylindrical) + coincidente (Distance 0) en la misma pieza: converge sin quejas.
  Tangente = Distance 0 entre plano y cilindro (probado; con Distance 5 queda a 5).
- Matriz: `App::Link` con `ShowElement=True`, `ElementCount=n`; cada `App::LinkElement`
  (`Matriz_i0`...) con expresión `Eje.Placement * translationm(0; 0; i * Datos.Espaciado) *
  minvert(Eje.Placement) * Semilla.Placement` (circular: `rotationz(i * Datos.Angulo)`).
  Eje = `Part::DatumLine` en el ensamblaje apoyado a través del vínculo: arista recta
  `TwoPointLine`, arista circular `AxisOfCurvature` (`AxisOfInertia1` falla en un cilindro).
  Los datos van en un `App::VarSet` aparte: una propiedad en el propio vínculo da "cyclic
  reference". Una relación se puede poner contra una copia (`getComponentReference` devuelve
  `Matriz_i1`). **El motor mueve piezas sin marcar a los que dependen**: las copias no se
  recalculan; tocarlas (`touch()`) desde un observador de documento al cambiar Placement de la
  semilla lo arregla en el mismo recálculo.
- Expresiones: un objeto llamado "A" no se puede usar (choca con la unidad Ampere);
  `rotation()` sin argumentos no se acepta; `Matriz.Placement.Matrix` y `minvert(...)` sí;
  `matrix(16 números) * X.Placement.Matrix * matrix(...)` asignado a un Placement funciona aunque
  tenga espejos (si el resultado es rígido).
- Simetría misma pieza: `Plano.Placement.Matrix * F * minvert(Plano.Placement.Matrix) *
  Semilla.Placement.Matrix * S` (F = espejo en Z, S = espejo propio de la pieza como literal),
  exacta. Plano propio detectado probando los 3 planos por el CDG del primer sólido.
- Versión opuesta: documento nuevo **guardado antes** ("Owner document not saved") con
  `PartDesign::SubShapeBinder` a la Body original + `Part::Mirroring` + Body con BaseFeature.
  Al abrirlo solo, FreeCAD abre la original, pero el binder no se recalcula hasta `touch()`.
- Taladro de ensamblaje: binder del croquis del ensamblaje dentro de la Body de cada pieza +
  Pocket ThroughAll Midplane. Posición en la etapa 1: `binder.Placement = vinculo.Placement.inverse()` fija
  (CORREGIDO en la etapa 4, ver abajo: `Relative = False` y `vinculo.inverse() * croquis.Placement`)
  (una expresión `minvert(Conjunto#Placa1.Placement)` es "cyclic reference"). El croquis no
  puede quedar apoyado en la cara de una pieza que se agujerea (ciclo): ubicarlo y desapoyarlo.
- Planos en relaciones: el panel nativo acepta solo planos del ensamblaje **sin apoyo**
  (`JointObject.py`: "accept only datum that are not attached"). Origen y plano suelto: bien.
- Taladro que sigue a la pieza: observador de documento (`slotChangedObject`, prop "Placement"
  del vínculo) que pone la posición del binder (fórmula de la etapa 4, abajo) y recalcula después el
  documento de la pieza. Anda al mover a mano y cuando mueve el motor. Comparar documentos por
  `.Name` (los objetos Python de un documento no son siempre el mismo: `is` falla).
  Ojo al medir: `Link.Shape` de un vínculo a otro archivo queda viejo hasta recalcular el
  ensamblaje; medir con `LinkedObject.Shape` + `Link.Placement`.
- Panel de relaciones (`mates_sw.py`, etapa 2): crea las uniones como el diálogo nativo
  (`Joint` + `ViewProviderJoint` + `setJointConnectors`) con transacción propia por relación;
  cambiar de tipo = `abortTransaction()` y crear de nuevo (las piezas vuelven a su lugar). En
  edición, una sola transacción: la unión vieja se borra y se crea otra; Cancelar la recupera.
  Selección como el diálogo nativo: `addObserver(obs, ResolveMode.NoResolve)` y estilo
  `GreedySelection` (sin Ctrl), devuelto a Normal al cerrar. Doble clic: se envuelve
  `JointObject.ViewProviderJoint.doubleClicked` (marca `_swui_mates`); lo que no es relación SW
  (giro, lineal, engranajes...) sigue con el diálogo de FreeCAD. Bloquear = Fixed con `Offset2`
  calculado para que no se mueva nada. El test lee como botón de la cinta toda tupla
  ("Assembly_...", "texto", ...): armar las demás con `tuple([...])`.
- Matriz/simetría de componentes (`component_patterns.py`, etapa 3): la selección en la vista trae
  subnombres con el nombre topológico de FreeCAD 1.x (`Body.;Face14;:Hda2,F….Face14`); para
  armar otro subnombre (una arista de esa cara) limpiar con `Part.splitSubname` (ruta +
  elemento). `isSame` no sirve entre la forma del vínculo y la de `getSubObject` (copias):
  comparar por geometría. Un VarSet que guarda vínculos a las copias que lo leen = ciclo: guardar
  nombres (StringList). A Python no le llega `slotFinishRestoreDocument` (1.1.4): usar
  `slotCreatedDocument` + QTimer 0. Crear un documento lo deja activo: volver al ensamblaje
  (`setActiveDocument` + `setEdit(asm)`) o los comandos ya no lo encuentran.
  Ejes del origen (App::Line): la dirección es su X local (eje de referencia con `ObjectX`).
- Taladro/corte de ensamblaje (`assembly_features.py`, etapa 4): el binder va con
  `Relative = False` y `Placement = vinculo.Placement.inverse() * croquis.Placement`. Con
  `Relative = True` (lo de la etapa 1) FreeCAD llegó a aplicar la posición del componente DOS
  veces después de crear otro objeto en el ensamblaje (probado). Un taladro nativo con un binder
  de perfil toma solo los círculos (los puntos sueltos no pasan al binder): a cada punto se le
  ata un círculo de 0,5 mm. `HolePanel` usa `self.kind` (un combo): no pisarlo en subclases.
  Al salir del croquis hay que limpiar la selección o el panel de relaciones del original
  (`assembly_mates`) toma el croquis. El nombre SW que pone `naming.py` se aplica con QTimer 0:
  para que quede el nuestro, ponerlo con otro QTimer 0 encolado después.
- Geometría de referencia en el ensamblaje (`asm_reference.py`, etapa 5): Part::DatumPlane/Line/
  Point en la raíz del ensamblaje con los paneles de la pieza (subclases que toman la selección
  por el componente; `ref_plane_panel.element()` entiende subnombres con punto). El motor del
  ensamblaje IGNORA una unión contra un plano apoyado (la unión existe, no mueve nada; probado):
  sin apoyo sí lo toma. `Gui.Document.setEdit` sobre un Part::DatumPlane devuelve False en 1.1.4
  (ni saliendo del ensamblaje): editar desde el clic derecho (`dp.OPENERS`).
- Vértices (2026-10-30): un punto de referencia apoyado en el vértice de ARRIBA de una extrusión
  queda "?Vertex6" al cambiar la altura (con el Cuerpo, con "Pad." o con la operación: los tres);
  a veces también una arista vertical ("?Edge5"). Las caras y las aristas de arriba resisten. Las
  selecciones traen el nombre interno con puntos adentro ("Pad.;#1a:2;:U;XTR;:H1f4:7,V.Vertex6"):
  el prefijo es lo anterior al primer ";" (`mate_refs.split_sub`), no lo anterior al último punto.
- Pruebas con el mouse de Claude (computer-use): FreeCAD recibe los clics pero NO el movimiento del
  mouse (contado con un filtro de eventos: cero MouseMove). Lo que depende de pasar el mouse
  (resaltado naranja de aristas del modelo, preselección) no se puede probar así.
- Uniones y renumeración (2026-10-30): `UtilsAssembly.getObject` devuelve el Cuerpo (o el vínculo)
  aunque la referencia diga "Pad.Edge15": el elemento se busca en la forma FINAL del Cuerpo, que
  renumera con cada operación nueva. FreeCAD además actualiza solo los nombres (contra "Pad", no
  contra la forma final) mientras recalcula la pieza, o los marca "Pad.?Face5" (error "Broken
  link"). La forma del vínculo del ensamblaje queda vieja hasta recalcular el ensamblaje: leer la
  del objeto enlazado y recalcular el vínculo antes de cambiar una referencia ("Shape index out of
  bound"). Arreglo en `mate_refs.py`. Sin interfaz, el motor mueve la pieza fija (la unión de
  fijar no cuenta): medir posiciones relativas.
- Renglones propios dentro del árbol (análisis para "relaciones debajo de cada componente",
  2026-10-31, código de FreeCAD 1.1.4 `src/Gui/Tree.cpp`, `ViewProviderLink.cpp`): FreeCAD
  revisa `item.type() == ObjectType` antes de tratar un renglón como objeto en casi todo el
  árbol (menú, selección, preselección, expandir, arrastrar, ordenar); las excepciones
  (`get/applyExpandedSnapshot`) solo usan funciones de QTreeWidgetItem. Un QTreeWidgetItem
  propio con otro `type` (UserType+N) dentro de un componente convive bien: probado con guion
  (cambiar la pieza, cerrar/abrir el componente, deshacer, guardar, crear y borrar objetos).
  PERO `DocumentItem::populateItem` BORRA los renglones que no reconoce cuando cambian los hijos
  del componente (operación nueva en la pieza): hay que volver a ponerlos (señal
  `rowsAboutToBeRemoved` del modelo). Elegir un renglón propio hace que FreeCAD vacíe la
  selección (`onItemSelectionChanged`). Vía nativa cerrada: `ViewProviderLink::claimChildren`
  copia los hijos de la pieza enlazada sin llamar a extensiones, y `addExtension` de Python solo
  sirve en objetos Python. Upstream (issue #23721) eligió un comando "seleccionar uniones
  asociadas" en vez de mostrarlas bajo la pieza.
  Hecho en `mates_tree.py`. Al recorrer el árbol de FreeCAD desde Python: `parent()` y
  `child(i)` a mano dieron "Internal C++ object already deleted"; el iterador
  `QTreeWidgetItemIterator` anda (lleva el documento al pasar por su renglón). Los renglones
  propios guardan adentro documento/componente/relación (data roles). Al entrar el mouse en un
  renglón ajeno FreeCAD borra la preselección (`onItemEntered`): ponerla un instante después.
  El menú del clic derecho trae lo de la selección pero no "Suprimido" (solo en renglones
  suyos): se agrega con un filtro que dura hasta que se muestra el menú. El color del texto de un
  renglón propio no se ve: la hoja de estilo de look_sw (`QTreeView::item { color }`) lo pisa; se
  atenúa con el velo de tree_overlay (`EXTRA_GREY`).
- Paneles y otro comando (31/10): con un panel abierto, los comandos de FreeCAD preguntan "Un
  diálogo ya está abierto en el panel de tareas" (Sí/No); con Sí FreeCAD quita el panel SIN llamar
  a su reject: el escucha de selección del panel queda vivo. Después de eso `panel.form` queda en
  None y la lista del panel borrada (el contenedor sigue válido). `FreeCADGui.Control` no deja
  envolver showDialog ("missing implement of setattr") ni tiene reject ni devuelve el panel
  Python (activeTaskDialog da un TaskDialog genérico): los paneles se anotan solos
  (`panel_guard.track`, desde sus escuchas).
- Capturas con computer-use (31/10, tarde): de golpe devolvían toda la pantalla oscura aunque
  FreeCAD estaba al frente; los clics sí llegaban. Salida: capturar con PowerShell
  (`Graphics.CopyFromScreen`, guion `cap.ps1` en el scratchpad). Y `timeout` de Git Bash NO
  cierra freecad.exe: quedaron 8 FreeCAD de prueba abiertos (usar `os._exit` al final del guion
  y revisar con Get-Process). `taskkill` desde la sesión de Claude dice "No hay ninguna instancia
  activa" para FreeCAD lanzados en otra llamada: cerrarlos con `(Get-Process -Id N).Kill()` fuera
  del sandbox (con permiso del usuario).

## Configuraciones (análisis, 2026-11-01): hallazgos en FreeCAD 1.1.4
Análisis completo y plan: documento "Configuraciones estilo SW 2018 en FreeWorks: análisis y plan"
(enlace en `docs/ESTADO.md`). Pruebas en FreeCADCmd 1.1.4 sin el addon (guiones t1 a t8 del
scratchpad de la sesión del 01/11; se rehacen fácil con lo de abajo).
- Tabla de configuración nativa (`Spreadsheet/Gui/DlgSheetConf.cpp`, `accept()`): lo que hace el
  diálogo se repite por guion así (fila 1 = parámetros con alias, filas 2.. = configuraciones):
  `body.addProperty("App::PropertyEnumeration", "Configuracion", "Configuraciones")`;
  `body.setPropertyStatus("Configuracion", "CopyOnChange")`;
  `body.setExpression("Configuracion.Enum", "Tabla.cells[<<A2:|>>]")` (el `|` = columna que crece:
  una fila nueva aparece sola en la lista); `sh.set("A1", "=hiddenref(Body.Configuracion.String)")`;
  `sh.setExpression(".cells.Bind.B1.D1", "tuple(.cells, <<B>> + str(hiddenref(Body.Configuracion)+2), <<D>> + str(hiddenref(Body.Configuracion)+2))")`.
  Después cotas por expresión (`sk.setExpression("Constraints.Ancho", "Tabla.Ancho")`).
- `Suppressed` de PartDesign acepta expresión (`pk.setExpression("Suppressed", "Tabla.SinAgujero")`,
  0/1). También `Visibility` de un Link y `Suppressed` de una unión de Assembly.
- Nombres de configuración: escribirlos con `'` delante (`sh.set("A2", "'2mm")`): si no, "2mm" se
  vuelve la cantidad "2.0 mm" y "1.5mm" no se puede elegir.
- Pieza (placa 60x40x10 con agujero / 120x40x6 sin / 90x40x8): ida y vuelta y reabierta, volumen
  exacto (23 214,602 / 28 800 / 28 171,682).
- Componentes en otra configuración = `App::Link` con `LinkCopyOnChange` (la propiedad con estado
  CopyOnChange tiene que estar en el objeto vinculado mismo, `Link.cpp setupCopyOnChange`; el Link
  la muestra como propia). "Enabled": copia (Body + croquis + Tabla, ocultos, grupo
  `CopyOnChangeGroup`) recién cuando la configuración difiere; después cambia la copia en el lugar.
  "Owned": copia enseguida. "Tracking": vuelve a copiar si cambia la pieza original. Cambio en la
  original (alto 40 -> 50): solo "Tracking" lo lleva a las copias (36 000 exacto). Ver error 3 en
  "Errores de FreeCAD encontrados" (uniones rotas al reabrir cuando el Link cambia de copia).
- Configuración del ensamblaje: misma tabla en el `Assembly` (enumeración ahí), columnas con la
  configuración de cada componente (`b.setExpression("Configuracion", "TablaConjunto.ConfPlaca2")`,
  texto) y supresión (`Visibility` = `TablaConjunto.SupPlaca2 == 0` + `Suppressed` de sus uniones).
  Funciona e ida y vuelta. En 1.1.4 los Link no tienen `SuppressibleExtension` (en `main`/26.3 sí,
  pero solo para elementos de matrices de vínculos, `isSuppressedLinkElement`, PR #32566).
- Chapa: `Thickness` y `Length` de la Brida base por expresión, bien en todas. El Unfold apunta a
  "FaceN" del Cuerpo: si una configuración renumera (agujero suprimido) queda "?Face15" e inválido;
  reelegida la cara (como `sheet_metal.ensure_flat`) sale bien. Para "DXF de cada configuración":
  activar, recalcular, `ensure_flat`, exportar, volver.
- Mover cara (Pad con una cara como perfil): Corta -> Larga lo sigue FreeCAD; Larga -> Media lo
  pierde ("?Face2") y no vuelve. Falta probar el reencuentro de `move_face.py` con cotas muy
  distintas.
- 26.3 (`releases/FreeCAD-26-3`): `DlgSheetConf.cpp` y `PropertyLinks.cpp` cambiaron de versión de
  archivo pero la tabla y CopyOnChange siguen; nuevo Assembly "Snapshot" (`CommandCreateSnapshot.py`:
  posiciones y visibilidad de componentes). Nada de configuraciones completas.
- Issues abiertos de la tabla: #30370 (insertar filas arriba deja la fila corrida), #15247 (no guarda el rango), #15249 (se duplica al renombrar),
  #14578 (no recalcula), #19182 (variantes y redondeos).
- `freecadcmd` imprime lo de `print` recién al final y mezclado con el registro: volcar a JSON
  después de cada paso.

## Paneles que dejaban de escuchar (01/11)
`mates_sw._SelObserver` llama `panel_guard.orphaned` en cada aviso. Muchos paneles se anotan como
escuchas y enseguida hacen `Selection.clearSelection()`, antes de `Control.showDialog`: con algo
elegido, ese aviso llegaba con el panel todavía sin mostrar (`activeDialog()` falso, la ventana
fuera de la de FreeCAD) y lo daba por huérfano: el escucha se daba de baja y el panel no veía
más los clics (corte de ensamblaje que no abría el croquis). Ahora `orphaned` no da por huérfano
a un panel que nunca estuvo vivo mientras su ventana exista (`_swui_was_alive`, `_form_exists`).

## Archivos .pyc rotos (01/11): FreeCAD colgado al cerrar
Con un FreeCADCmd y un FreeCAD con interfaz corriendo a la vez (pruebas) y los .py del addon
cambiando, un .pyc de `swui/**/__pycache__` quedó roto: el informe se llenó de "XXX lineno: 448,
opcode: 55", "SystemError: unknown opcode" en los eventFilter y al final "RecursionError"; el
FreeCAD de prueba no terminaba (`os._exit` no llegaba) y quedaba ocupando ~580 MB. Arreglo: borrar
los .pyc de `swui/__pycache__`, `swui/fork/__pycache__`, `swui/commands/__pycache__`,
`swui/lang/__pycache__` y `tools/__pycache__` (Python los rehace; están en .gitignore). Prevención:
no correr pruebas con interfaz y FreeCADCmd al mismo tiempo; si aparece "unknown opcode" en
run.log, borrar los .pyc antes de seguir.
07/11: volvió a pasar con dos FreeCAD de prueba abiertos a la vez (Croquis 3D); con los .pyc
borrados y un solo FreeCAD, cero errores. Un FreeCAD que inunda el informe así no se deja matar
(Stop-Process dice que terminó pero sigue en la lista hasta que se cierra la consola que lo lanzó).

## Configuraciones (implementación, etapas 1 a 5, 2026-11-01)
- Módulos: `configurations.py` (núcleo sin interfaz: tabla, lista, Esta/Todas, suprimir con
  apoyo de croquis por expresión), `config_tab.py` (pestaña, Modificar, Suprimir del árbol,
  Ecuaciones), `config_sheet.py` (chapa y DXF), `config_asm.py` (componentes y ensamblaje). Se
  instalan juntos al final de `swui/fork/__init__.py` y ENVUELVEN funciones de otros módulos del
  fork: `panel_sw.dock_left`, `instant_dims._expressions/apply_value/_modify/feature_dims`,
  `feature_tree.suppress/unsuppress`, `equations.Model.expressions`, `dress_up_panel.SwPanel._set`,
  `sheet_panels.export_dxf` (+ `_Command.Activated`, que guardaba la función vieja),
  `sheet_metal.part_name`, `mass_props.components`, y su propio `configurations.activate`
  (dos veces: chapa y ensamblaje).
- Tabla: fila 1 títulos, fila 2 "Activa: <nombre>" + valores enlazados (gris, cursiva), filas 3..
  configuraciones. `A2 = <<Activa: >> + hiddenref(Body.Configuracion.String)` (concatenar textos
  anda). El diálogo nativo "Configuration Table…" no la reconoce por eso (no hace falta).
- Dueño de la lista: el Cuerpo en una pieza; en un ensamblaje SIEMPRE el objeto Ensamblaje (los
  Cuerpos de ahí son copias de componentes, `CopyOnChangeGroup*`; una se colaba como dueña).
- Cotas sin nombre: se les pone "Dn" (como SW) y se atan por nombre (`Constraints.D1`), no por
  índice (el índice cambia al borrar restricciones).
- Suprimir en esta configuración: una columna "Sup_<Name>" por operación (ella y sus dependientes,
  como `feature_tree.suppress`); los croquis/planos apoyados en una suprimida llevan
  `MapMode = T.Sup_A + T.Sup_B > 0 ? <<Deactivated>> : <<FlatFace>>`.
- Componentes: `LinkCopyOnChange = "Tracking"` al elegir la configuración por primera vez.
  Suprimir componente: siempre por la tabla del ensamblaje (la arma con "Predeterminado" si no
  estaba), `Visibility = T.Sup_X == 0` y las uniones `Suppressed = T.Sup_X (+ T.Sup_Y) > 0`. Así
  "suprimido" (alias) se distingue de "oculto con el ojo".
- Pruebas: núcleo en FreeCADCmd (pieza 3 configuraciones, ida y vuelta, borrar, renombrar,
  reabrir: volúmenes exactos); con interfaz (gui_probe): pestaña, Modificar con Esta/Todas,
  Suprimir del árbol, tabla, chapa 2/3 mm con desarrollo y DXF de todas, barrita del componente
  en árbol y vista, Larga sin errores, ensamblaje "Sin_pieza_2", reabrir, DXF por lotes con dos
  configuraciones, Propiedades físicas sin el suprimido.
- Falta probar: Mover cara con configuraciones de cotas muy distintas (su reencuentro por
  parecido puede elegir mal); taladro/corte de ensamblaje sobre componentes suprimidos
  (`assembly_features._components` no los saltea); pieza multicuerpo (la lista vive en un solo
  Cuerpo: un componente vinculado a otro Cuerpo de la misma pieza no ve las configuraciones).
- Prueba con mouse contra SW (01/11, mañana): pieza (agregar, Modificar Esta configuración,
  Suprimir, cambiar, tabla), chapa (cambiar, DXF de todas) y ensamblaje (barrita en la vista,
  componente nuevo, suprimir) en FreeCAD y en SW 2018. Arreglado en el acto:
  - Cada componente tiene su configuración (SW): `config_asm.pin_followers` corre ANTES de cambiar
    la configuración de una pieza (`configurations._before`, lo llaman `activate` y el camino de
    chapa de `config_sheet`) y fija los componentes que mostraban la pieza tal cual; un
    componente nuevo (observador, `LinkedObject`) nace fijado en la activa. Ver error 5.
  - Chapa: `config_sheet._activate_skipping_flats` recalcula primero todo menos el desarrollo,
    después reelige la cara fija y recién ahí recalcula el desarrollo (sin el aviso "Invalid
    shape name ?Face6"); después oculta los croquis del desarrollo (`sheet_panels._sketches_follow`).
  - `feature_tree.arrange_menu` oculta la casilla nativa "Suprimido" (checkable) cuando está lo
    nuestro: no pasaba por las configuraciones.
  - `auto_body` no activa una copia de componente (`configurations.is_copy`).
  - Diferencias que quedan con SW (chicas): el Modificar no tiene "Especificar configuraciones";
    la lista no se ordena alfabéticamente; la barrita aplica al elegir (SW pide confirmar con un
    tilde); "Agregar configuración" y "Cambiar nombre" son diálogos (en SW, panel / en el árbol).
- 01/11 tarde, lo que había quedado abierto:
  - `config_feature.py`: Configurar operación. Columnas = `instant_dims.dims_of` (las cotas del
    doble clic, las atadas a la tabla también) + Suprimir; escribe con
    `configurations.set_values` / lee con `value_in`. Suprimir en una configuración suprime
    también los dependientes. Entra al clic derecho envolviendo `feature_tree.menu_commands` y
    sumándose a `feature_tree.COMMANDS` (así sube con lo nuestro).
  - `config_asm.config_rows` en `tree_overlay.EXTRA_TEXT` (como las piezas de las relaciones):
    " (Larga)" al lado del nombre del componente.
  - Mover cara: (1) `mate_refs.ANGLE` = 1e5 por radián (antes 1000): con configuraciones la cara
    de la punta se corre mucho (60 -> 100 mm) y una de costado girada 90° "se parecía" más; vale
    también para relaciones. (2) `move_face.snapshot_geo` guarda la firma por configuración
    (`geoc` en la marca) y `relink` usa la de la activa. (3) `config_sheet._activate_skipping_flats`
    deja los Mover cara (y lo que depende) para después de reencontrar la cara, sin avisos
    (`move_face._quiet`): sin "Sub shape not found". (4) `feature_tree.parents`: un
    Extruir/Cortar cuyo perfil es una cara del sólido anterior tiene de padre a la operación que
    creó la cara (`profile_creators`, como los redondeos): suprimir un agujero anterior suprimía
    el Mover cara de la punta.
  - Renombrar/eliminar: `config_asm._hook_rename_delete` anota antes quién usa el nombre
    (componentes y celdas de la tabla del ensamblaje) y después los apunta al nuevo / a la
    activa. En un componente sin tabla, la lista de la propiedad todavía no tiene el nombre
    nuevo: se le pone la lista de la pieza antes del valor.
  - `assembly_features.part_of`: con LinkCopyOnChange, `LinkedObject` es la copia del
    ensamblaje; el taladro va a `LinkCopyOnChangeSource`. `_components` saltea suprimidos.
  - Multicuerpo: FreeCAD solo copia en otra configuración si la propiedad CopyOnChange está en
    el objeto vinculado. La lista vive en un Cuerpo; atar los otros a ella sería un ciclo (la
    tabla depende del dueño, los sólidos de la tabla). Un componente de otro sólido muestra la
    configuración activa (barrita gris con explicación). En la pieza, la tabla maneja todo.
  - FreeCAD 1.1.4: con la única operación de un Cuerpo suprimida, el Cuerpo sigue mostrando el
    sólido (también suprimiendo a mano, sin configuraciones; el Pad queda con forma nula).
  - Visto con el mouse y arreglado: `feature_tree._MenuShow` plegaba en "Más opciones" también
    los menús de la barra (Archivo...) con un componente elegido (su padre es QMenuBar); la
    barrita del componente salía con el panel de relación abierto (ahora no, si hay
    `Control.activeDialog()`); `settle_assembly` usaba la geometría tomada con la copia a medio
    rehacer y avisaba "cara cambiada" al agregar una configuración (ahora prefiere la guardada).
  - Operación nueva como SW (`config_tab._NewFeatures`, observador del documento): junta las
    operaciones nuevas y, cuando no hay panel ni edición abiertos, `configurations.only_in` las
    suprime en las otras configuraciones (columna de supresión en la tabla). No se hace al crear
    el objeto: el panel todavía lo está armando y suprimirlo ahí rompía la operación.
  - Barrita del componente: el cambio vale recién con el tilde (`_Bar.ok`); la barrita se va
    sola al alejar el mouse sin cambiar nada. Avisos de relaciones al cambiar de
    configuración: `mate_refs._state["quiet"]` durante `set_config` / `settle` (`_quiet_mates`),
    van al informe (PrintLog) en vez de avisar.
  - Componente suprimido en gris (01/11, pregunta 2 del usuario): `config_asm.suppressed_rows`
    en `tree_overlay.EXTRA_GREY`, el mismo velo que lo suprimido de las piezas y las relaciones
    (el estilo del árbol pisa el color del texto: no sirve `setForeground`).
  - Tabla oculta con una sola configuración (pregunta 3): `configurations.show_table` pone
    `ShowInTree` de la planilla según haya una o más configuraciones; corre en `ensure` y al
    final de `activate` (agregar, eliminar y cambiar el nombre pasan por ahí). Fuera de un
    Cuerpo, FreeCAD 1.1.4 respeta `ShowInTree` (dentro no: ver `tree_overlay.hide_unlisted`).

## IA, etapa 0: el puente (2026-11-01)
Plan y decisiones: documento "IA en FreeWorks: análisis y plan" (enlace en `docs/ESTADO.md`).
- Estructura `swui/fork/ia/`: `terceros/` (copiado) -> `nucleo/` -> `herramientas/` -> `puertas/`;
  cada capa usa solo las de abajo y nada fuera de `ia/` la importa salvo `swui/fork/__init__.py`.
  `tools/test_load.py` (`check_ia`) verifica las dos reglas y responde un saludo MCP sin FreeCAD.
- Código copiado (origen y versión en `terceros/__init__.py`; cambios marcados "FreeWorks:"):
  neka-nat/freecad-mcp 8babe99 (`gui_dispatch.py`, `dispatch_health.py`, MIT: cabecera SPDX
  "LGPL-2.1-or-later AND MIT", el test lo acepta solo en `terceros/`) y ghbalf/freecad-ai 08d637d
  (`mcp_protocol.py`, `mcp_http.py` = HTTPServerTransport sin los transportes de cliente,
  `mcp_server.py` sin STDIO, `registry.py` + campo `timeout`). Para traer arreglos: comparar con
  esos archivos de origen. El `ip_filter` de neka-nat no se copió: el transporte de ghbalf ya
  rechaza Origin (páginas web) y Host que no sea local.
- Servidor: Streamable HTTP en `http://127.0.0.1:47115/mcp` (también /sse heredado), clave
  obligatoria (`Authorization: Bearer`), 401 si falta. Puerto en
  `BaseApp/Preferences/Mod/SWUI/IA` (Port); la clave en `<datos de usuario>/FreeWorks-IA/clave.txt`
  (no en user.cfg: FreeCAD lo reescribe al cerrarse y pisaría una clave creada con FreeCAD
  abierto). Se crea sola con `secrets`. Arranca apagado en cada sesión (privacidad). Conectar
  Claude Code:
  `claude mcp add --scope user --transport http freeworks <url> --header "Authorization: Bearer <clave>"`.
  En la PC del usuario no hay `claude` en el PATH (usa la app de escritorio, que trae su propio
  claude.exe en `%LOCALAPPDATA%\Claude-Data\claude_<id>\claude-code\<versión>\<hash>\`); con ese se
  registró el 01/11 (pedido del usuario "conectalo a la app"), escribe `~/.claude.json`. Con el
  puente prendido, `claude.exe mcp get freeworks` da "Connected". Ese claude.exe suelto no tiene
  sesión iniciada ("Not logged in"): las pruebas de punta a punta van por una sesión nueva de la app.
- Hilo principal: cada herramienta pasa por la cola de neka-nat (`dispatch_to_gui`, espera
  arrastres del mouse, menús y ventanas modales; marca "trabado" si se pasa de `timeout`). La de
  Python maneja sus propios pasos (`main_thread=False`) para no frenar la ventana durante la prueba.
- Respaldo de la IA (`nucleo/respaldo.py`, decisión del usuario 01/11: "no haremos control de
  versiones"): UNO por documento, el de antes del primer cambio de la IA desde el último guardado;
  los scripts siguientes no lo pisan; al guardar el usuario se borra (aceptó lo de la IA); cerrar
  sin guardar lo deja en `<datos de usuario>/FreeWorks-IA/respaldos/`. Observador de App
  `slotFinishSaveDocument(doc, archivo)`: en 1.1.4 llega también con `saveCopy` (probado en
  freecadcmd), por eso solo cuenta si `archivo` es `doc.FileName`. `saveCopy` sobre un archivo que
  ya existe deja un `.FCBak` al lado (preferencia de copias de seguridad de FreeCAD; guarda 1):
  `respaldo.save_copy` borra el archivo antes. Scripts `solo_leer`: sin respaldo ni prueba; si
  cambian algo (queda el paso en `UndoNames`) se hace `undo` y vuelve error. FreeCAD descarta las
  transacciones vacías: "cambió" = `UndoNames[0] == "IA: <título>"`; si no cambió nada, el
  respaldo hecho para ese script se borra. Probado en FreeCAD real (prueba 2 del 01/11: cambio,
  segundo cambio sin pisar, consulta, consulta que cambia -> deshecha, guardar -> borrado,
  cambio nuevo -> respaldo nuevo, sin .FCBak). En esa prueba el FreeCAD de prueba una vez quedó
  abierto después de cerrar los documentos (no se investigó; se cerró con `.Kill()`).
- Python seguro (`nucleo/ejecutar.py`): `doc.saveCopy(ruta)` (existe en 1.1.4) no cambia
  FileName ni Label. La copia de trabajo (`FreeWorks-IA/prueba/documento.FCStd`, se pisa) se abre
  en `freecadcmd.exe <script>` (CREATE_NO_WINDOW,
  corte con `subprocess.run(timeout=90)`, que en Windows sí mata el proceso; el corte de ghbalf
  usa SIGALRM y en Windows no hace nada) con un FreeCADGui falso; termina con `os._exit` y deja
  `resultado.json`. Falla si el script lanza, si deja algo "Invalid" o un PartDesign::Feature con
  forma nula/inválida que antes no estaba. Después corre en vivo dentro de
  `openTransaction("IA: <título>")`; si falla, `abortTransaction`. Registro:
  `FreeCADGui.doCommandSkip(texto)` escribe en la consola de Python sin ejecutar.
- Probado en FreeCAD real (copia de user.cfg, puerto 47199) con un cliente MCP de afuera:
  clave mala 401; saludo con instrucciones; estado; placa 100x60x10 con agujero Ø10 por script
  (59 214,602 mm³ exacto; `naming.py` le pone los nombres SW); captura con y sin ajustar; script
  con error -> no se ejecuta; con error y sin prueba -> se deshace solo; `while True` -> cortado a
  los 90 s sin tocar la pieza; un `doc.undo()` deshace la placa entera; apagar y prender desde el
  menú (tilde). Sin probar: Claude Code real conectado (falta el permiso del usuario para tocar su
  configuración de Claude Code).

## IA, etapa 1: hallazgos en FreeCAD 1.1.4 (2026-11-01)
Herramientas en `swui/fork/ia/herramientas/` (una por área); el contrato de funciones de FreeWorks
que usan está en `tools/test_load.py` (`check_ia`): si una cambia de firma, el test falla.
- **No hay transacciones anidadas:** `openTransaction` con otra pendiente cierra la de afuera y lo
  que sigue queda sin paso. Con un panel abierto (que tiene la suya) las consultas no abren paso y
  los cambios esperan (`comun.require_free`); "cambió" = `nucleo/deshacer.new_steps` (compara la
  lista `UndoNames` entera, no el nombre del primer paso). Un pedido entero se deshace con la
  herramienta `pedido` (empezar / deshacer). FreeCAD descarta las transacciones vacías.
- `body.newObject` no mueve la punta (Tip) en matrices ni simetrías; en un redondeo/chaflán la
  punta pasa a ser el nuevo: la base se toma ANTES de crearlo. `pieza_operar._make` llama a
  `feature_tree.set_tip`.
- `slotFinishSaveDocument` llega también con `saveCopy`: el observador de FreeWorks
  (`feature_tree._DocObserver`) solo cuenta el guardado si el archivo es `doc.FileName`.
- Ensamblaje: el ensamblaje activo está "en edición" siempre y su ViewProvider no tiene `.Object`
  (`comun.user_busy` lo tolera). Referencias: se eligen dentro del ensamblaje
  (`addSelection(doc, asm.Name, "Link.Body.FaceN")`) y se leen con
  `mates_sw.entities_from_selection`, igual que el panel. `asm.solve()` devuelve 0 aunque una
  relación choque con otras (la deja sin cumplir; 1.1.4 no tiene getLastConflicting ni similares):
  `ensamblaje._unmet` mide caras/ejes después de resolver y aborta.
- Conductor de paneles (`paneles.py`): campos visibles dentro de `Gui::TaskView::TaskView`
  (etiqueta por formulario, layout, título de la caja o buddy; primero la etiqueta exacta),
  escritura con QTest en QuantitySpinBox, selección con `Gui.Selection.addSelection`, OK/Cancelar.
  Un filtro de eventos cancela el panel ante un clic o tecla espontáneos (QTest también es
  espontáneo: bandera `typing` mientras escribe la IA). Cartel hijo de `mw.centralWidget()` (la
  cinta lo tapaba). Paso `croquis`: dibuja en el croquis en edición y `resetEdit()`; el panel sigue
  solo (taladro/corte de ensamblaje).
- Los FaceN cambian después de cada operación: volver a elegir.
- **Puerto del puente en Windows:** `HTTPServer.allow_reuse_address` = SO_REUSEADDR, que en Windows
  deja que otro proceso escuche en el mismo puerto y reciba los pedidos (con la clave). Se usa
  SO_EXCLUSIVEADDRUSE (`terceros/mcp_http.py`, marcado "FreeWorks:").
- Pruebas: un FreeCAD de prueba cerrado con `os._exit` mientras tenía un panel de la IA abierto
  quedó con un hilo al 100 % y la memoria creciendo (taskkill: "no hay instancia activa"); se
  cerró con `Invoke-CimMethod Terminate`. Es solo del `os._exit` de las pruebas: cerrando la ventana como el usuario (documentos y `mw.close()`) después de usar un panel de la IA, FreeCAD sale en ~8 s (probado 01/11).

## Planos del origen (04/11): hallazgos en FreeCAD 1.1.4
- `App::Origin` manda sobre sus hijos (ejes, planos, punto): oculto, no se dibuja ninguno aunque
  tengan Visibility True; prenderlo o apagarlo NO cambia la Visibility de los hijos. FreeCAD crea
  la carpeta oculta con todos los hijos en True.
- `App::Plane` no tiene tamaño (cuadradito en el cuadrante +, ~10 % de la pieza); `PartDesign::Plane`
  sí (`ResizeMode` Automatic/Manual, Length, Width).
- Dibujar sin tocar el ojo: `vo.SwitchNode.whichChild` (-1 oculto; 0 plano a la vista; la carpeta
  usa 1). Sobrevive a recalcular y a cambiar la selección; FreeCAD lo rehace solo al cambiar
  Visibility. El ojo del árbol se dibuja según lo que se ve (switch), pero el clic en el ojo usa la
  propiedad Visibility.
- Cambiar Visibility marca el documento modificado: `FreeCADGui.getDocument(n).Modified = False`
  lo devuelve (se usa en los cambios propios: abrir archivo, vista previa).
- `FreeCADGui.runCommand` de un comando "Checkable" llama `Activated(0)` siempre: en pruebas,
  `QAction.trigger()` (objectName = comando), como un clic de menú.
- Pruebas: un guion que hace `saveAs` y después cierra dejó el FreeCAD de prueba colgado (cerrado
  con `Invoke-CimMethod Terminate` filtrando por la línea de comando del guion). Evitar guardar en
  las pruebas o terminar con `os._exit` sin cerrar documentos.

## Herramientas de entidades del croquis (02/11): hallazgos en FreeCAD 1.1.4
- Los botones nativos Sketcher_Symmetry / Offset / Translate / Rotate / Scale /
  RectangularArray están en gris sin geometría elegida (toman la selección al clic y no dejan
  sumar después). Funciones del croquis usables desde Python (probadas): `addSymmetric(geos,
  refGeo, refPos)` (devuelve los números nuevos; respecto de una línea, un eje -1/-2 o un punto:
  refPos 1/2/3), `addCopy(geos, vector, clone)`, `addMove(geos, vector)`,
  `addRectangularArray(geos, vector, clone, filas, columnas, separación, escala)`,
  `delGeometries`, y en cada geometría `rotate/scale/translate/mirror`. `Part.Wire.makeOffset2D`
  en una cadena abierta: con `openResult=True` da un solo lado; con False el contorno de los dos
  lados con puntas redondeadas.
- `addSymmetric` copia las relaciones internas (coincidente, horizontal, radio...) pero NO pone
  relación Simétrico entre original y copia (no tiene la opción del botón nativo). En una copia
  simétrica, las de arco salen con inicio/fin cambiados: buscar el punto reflejado por posición.
- Redundancias: después de `solve()`, `RedundantConstraints`, `ConflictingConstraints`,
  `PartiallyRedundantConstraints`, `MalformedConstraints` (números desde 1). Agregar una relación
  y sacarla si aparece alguna nueva es simple y robusto (`sketch_entities._try_add`).
- Selección en el croquis: `Edge3` = geometría 2, `ExternalEdge1` = -3, `H_Axis`/`V_Axis` = -1/-2,
  `VertexN` -> `getGeoVertexIndex(N-1)`; `ExternalGeo[-g-1]` da la geometría de un número negativo
  (0 eje H, 1 eje V, 2... referencias).
- Panel propio dentro del croquis: se inserta arriba del TaskPanel del croquis como el panel de
  relaciones del original (`sketch_relations._task_panel`). Un filtro de eventos creado inline
  (`w.installEventFilter(Filtro())`) lo borra Python: guardarlo en un atributo.
- Probar sin el mouse real: QMouseEvent Move, Move, Press, Release al viewport en el punto de
  `view.getPointOnViewport` (y Qt = alto - y/ratio) selecciona en el croquis como un clic.
  La cinta: botón `SWUI_Btn_<comando>` (`findChild(QToolButton, ...)`).
- Matriz de FreeCAD: `addRectangularArray(geos, vector, clone, n_dirección, n_perpendicular,
  separación_con_relaciones, escala_perp)`: la segunda dirección va a -90° con escala +1 y a +90°
  (como SW) con escala negativa. Cada instancia: las entidades en orden + una línea constructiva;
  copia también las cotas de cada instancia (cada copia con su largo): `_follow_original` las
  cambia por Igual al original. Solo direcciones a 90°: si no, copias sueltas con `addCopy`.
- `addCopy(geos, V(0,0,0), False)` duplica con relaciones internas: base de Escala con copias.
- Cambiar geometría sin el resolvedor: `geos = list(sketch.Geometry)`, modificar, `sketch.Geometry
  = geos` (conserva relaciones y constructiva); `moveGeometry` arrastra todo el croquis.
- `setExpression("Constraints[i]", "Constraints.Nombre")` ata una cota a otra (Equidistanciar);
  `renameConstraint(i, nombre)`. FreeCAD muestra "Nombre = valor" en las cotas con nombre.
- Mouse en la vista: los eventos llegan a un `QOpenGLWidget` (viewport del QGraphicsView);
  punto del plano del croquis = `view.getPointOnFocalPlane(x, y)` (coordenadas Coin) proyectado
  por `getViewDirection()`. La herramienta de mouse de Claude NO genera movimientos sueltos
  (solo el de cada clic): lo que sigue al mouse se prueba con eventos simulados.


## Piezas soldadas (07/11): hallazgos en FreeCAD 1.1.4

- QDoubleSpinBox y QComboBox de Qt cambian de valor con la ruedita aunque no tengan foco: al bajar un
  panel largo con la ruedita se lleva puesto el valor de lo que pasa por debajo del mouse (así quedó
  Girar ángulo en -2° en la prueba del usuario). `weld_panels.guard_wheel(form)`: StrongFocus y un
  filtro que, sin foco, manda la ruedita al padre. Sirve para cualquier panel nuevo.
- El giro del perfil se puede cambiar en un miembro ya hecho: el AttachmentOffset del Perfil es un
  giro puro en Z (automático + Girar ángulo); el automático = yaw actual - SWUI_WeldRotation. Las
  envolventes de otros miembros copian ese AttachmentOffset (no es fórmula): hay que copiarlo de nuevo.

- Pad y Pocket de 1.1: "TwoLengths" ya no existe en Type; ahora `SideType = "Two sides"` con
  `Type`/`Type2` = "Length" y `Length`/`Length2`.
- Croquis acoplado "NormalToEdge" a la arista de un SubShapeBinder: el Pad sale para atrás; con
  `Reversed = True` va a lo largo de la línea (Length) y Length2 alarga hacia atrás. El Pocket de la
  envolvente, en cambio, va bien sin invertir.
- Fórmula del largo: `<NombreDeLaRuta>.Shape.Length` funciona en una expresión. Usar el NOMBRE
  interno (cada Cuerpo tiene "Ruta", "Ruta001"...): con el rótulo apunta a otra ruta.
- PartDesign SubtractiveBox con MapMode "Translate": FreeCAD descarta el giro de AttachmentOffset;
  para el inglete la caja se ubica con Placement directo (calculado al crearla).
- La numeración "EdgeN" de un croquis es la de su forma (FreeCAD reordena las líneas unidas), no
  la del orden de dibujo: en los guiones buscar la línea por su geometría.
- Dentro de FreeCAD, FreeWorks les cambia el rótulo a los croquis y operaciones nuevos (estilo SW):
  las partes de un miembro se buscan por cómo están armadas (primer SubShapeBinder, primer Pad y
  su Profile), nunca por el rótulo.
- Un archivo armado con FreeCADCmd (sin pantalla) abre con las operaciones de PartDesign ocultas
  (no tiene datos de vista): para pruebas con el mouse, armar los miembros dentro del FreeCAD de
  prueba.
- La caja envolvente (BoundBox) de caños redondos sale hasta 6 mm más grande: medir con vértices o
  `optimalBoundingBox()`. El largo de una boca de pescado se mide con puntos de la superficie
  (`tessellate`), no con vértices.
- Comparado con SW (herramienta del puente y con el mouse): marco 600 x 400 en 40x40x2 a inglete =
  2 x 640 + 2 x 440 a 45° (igual); a tope con los largueros pasantes = largo a ejes + 40 / - 40.

## Croquis 3D (07/11): hallazgos en FreeCAD 1.1.4
- No hay croquis 3D nativo (el Sketcher resuelve en un plano). Se arma con `Part::Line` (X1..Z2 son
  propiedades de longitud que aceptan fórmulas) dentro de un `App::DocumentObjectGroup` marcado
  `SWUI_Sketch3D`, y un `App::VarSet` con las cotas D1, D2... Probado: archivo reabierto en FreeCAD
  sin tocar nada de FreeWorks, cambiar D1 en el VarSet mueve todo.
- Una línea NO puede tener un link a su grupo (el grupo ya la tiene en Group): ciclo, "The graph
  must be a DAG" y nada se recalcula. Se busca el croquis por `InList`.
- Fórmulas: una propiedad puede usar otra del mismo objeto sin prefijo (`X2 = X1 + Cotas.D1`).
  `Obj.Shape.Length` y `Obj.Shape.Vertexes[i].Point.x` andan en fórmulas pero salen SIN unidad
  (multiplicar por `1 mm`). Al poner la fórmula con la forma todavía vacía FreeCAD imprime
  IndexError, pero después recalcula bien.
- Vista: `getCursorPos`, `getPointOnFocalPlane`, `getPointOnViewport` y `getObjectInfo` usan los
  mismos píxeles (Coin, y hacia arriba). `getObjectInfo` a veces no toma una línea fina en el
  primer píxel: para el doble clic, respaldo con lo que dejó elegido el primer clic. Los vértices se
  enganchan por cercanía en la pantalla (getObjectInfo solo da Vertex si el clic cae justo encima).
- Documento vacío: FreeCAD arranca con un zoom de pocos milímetros (100 mm = 13.000 píxeles): el
  croquis 3D pone una isométrica de ~1,4 m al abrirse si no hay nada a la vista.
- Tab y los números llegan como atajos (ShortcutOverride) antes que como teclas: aceptar el
  ShortcutOverride para quedárselas; los números solo con una línea empezada (si no, siguen las
  vistas 0..6). El clic derecho que corta la cadena debe tragarse también el ContextMenu, si no sale
  el menú de FreeCAD.
- El mouse automático de las pruebas no genera movimiento (ni en FreeCAD ni en SW): la vista previa
  que sigue al mouse y el largo tecleado se probaron moviendo el cursor de verdad desde un guion
  (`QCursor.setPos` + `mouse_moved`). En SW 2018, el Croquis 3D con el mouse automático dibuja
  arrastrando pero no con clic y clic; y Ctrl+Z justo después de abrirlo deshace el croquis entero.
- Cajita del largo como el croquis 2D: las On-View Parameters del Sketcher son
  `Gui::EditableDatumLabel` (C++, no se puede usar desde Python), pero su caja es un
  `Gui::QuantitySpinBox`: `FreeCADGui.UiLoader().createWidget("Gui::QuantitySpinBox", visor)`,
  hija del View3DInventorViewer (como la barrita de la vista), y la cota gris se dibuja en Coin.
  Para verlas en una prueba hay que mandar MouseMove de verdad (QCursor.setPos + QMouseEvent).
- Un panel de Tareas que FreeCAD cierra solo (otro comando, "Sí" a "Un diálogo ya está
  abierto") no llama a accept/reject: sin panel_guard el escucha de selección y el filtro de
  eventos quedan vivos y tocan widgets borrados ("QListWidget already deleted").
