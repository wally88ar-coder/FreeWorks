# Auditoría de errores — 08/11/2026

Pedida por el usuario ("¿serviría una auditoría de búsqueda de bugs?"). Dos pasos:

1. **Análisis automático** (ruff + pyflakes, 163 archivos): sin errores seguros. 107 avisos de
   prolijidad (variables o importaciones sin usar); los 6 de "lambda en un bucle" revisados, bien.
2. **Revisión enfocada** con 4 agentes en paralelo (archivos guardados, enganches a FreeCAD,
   recálculo, paneles y deshacer), sin conocer las conclusiones de Claude. Claude verificó lo
   marcado **[verificado]** volviendo a correr las pruebas o con una propia; lo demás sale de leer
   el código (**[probable]**).

**Pasada a las Issues de GitHub el 08/11** (https://github.com/wally88ar-coder/FreeWorks/issues):
graves 1-3 = #1-#3, medianos 4-15 = #4-#15, chicos = #16-#27 (sin "Deshacer con un panel
abierto", aceptable), punto 0 = #28 (cerrada). El seguimiento sigue allá, no en este archivo.

Nada de esta lista está arreglado salvo el punto 0 (error propio de la tarde anterior). El usuario
elige qué arreglar.

**Guardar archivos — bien:** sin FreeWorks los archivos abren igual (las propiedades propias son
nativas y se leen con valores por defecto; no hay clases Python propias guardadas en el archivo).
Probado: estructura soldada y tabla CIRSOC guardadas y reabiertas en FreeCAD solo.

## 0. Ya arreglado (sin subir)

- **Abrir un archivo lo modificaba** (`cross_body.py`, hecho el 07/11): si un "Hasta la superficie"
  u otra referencia apuntaba a otro sólido, al abrirlo se agregaba una copia y quedaba "modificado".
  FreeCAD 1.1.4 no avisa a Python cuando empieza a abrir; ahora mira `doc.Restoring`.
  [verificado antes y después]

## Graves (pueden romper una pieza sin avisar)

1. **Multicuerpo: borrar una copia de "Alcance" vacía otro sólido.** [verificado] Si un corte tiene
   copia en otro sólido y ese sólido tiene operaciones DESPUÉS de la copia, al borrar el corte o
   cambiar su alcance, la operación siguiente se queda sin base y el sólido pierde todo lo anterior
   (prueba: volumen de 1968 a 1000). `multibody.py:530`, falta `body.removeObject` antes de borrar
   (weldments y Mover cara ya lo hacen bien).
2. **Piezas soldadas: las esquinas a inglete no siguen al croquis esqueleto.** [verificado] Marco con
   inglete, cambiar 600 → 800 en el esqueleto: el caño horizontal sigue cortado en el lugar viejo
   (hueco de 200 mm) y el vertical sobresale 113 mm. Sin ningún error. Lo mismo la punta en ángulo
   ("PuntaTope") y las tapas. A tope a 90° sí sigue. ESTADO decía que el inglete "sí sigue la
   posición": no es así. `weldments.py` (_box_cut, inglete, _butt_tip_cut).
3. **Con un panel abierto, abrir Ecuaciones o Material (franja de arriba del árbol), Suprimir o mover
   la barra de retroceso rompe el Cancelar del panel.** [verificado el mecanismo] FreeCAD no anida
   las transacciones: la nueva confirma la del panel. Ej.: Redondeo abierto → Ecuaciones → cerrar →
   Cancelar: el redondeo queda. `feature_tree.py:665`, `tree_strip.py:143`, `equations.py:569`,
   `material.py:948`, `instant_dims.py:458`.

## Medianos (algo sale mal en un caso realista)

4. **Ecuaciones: una variable global nueva puede pisar el espaciado de una matriz de componentes.**
   [verificado] Sin "VariablesGlobales", toma el primer VarSet del documento (el de la matriz).
   `equations.py:227`.
5. **Taladro/corte de ensamblaje guarda el nombre interno del documento de la pieza**, que cambia
   (dos "Placa.FCStd" en carpetas distintas = "Placa" y "Placa1"). Se pierde el vínculo: editar o
   borrar la operación deja el agujero huérfano en la pieza; con dos copias del proyecto abiertas
   podría tocar la equivocada. [probable] `assembly_features.py:336`.
6. **Miembro estructural: el panel no lo conoce el "guardia" de paneles.** Otro comando lo cierra
   sin Cancelar: quedan los caños de la vista previa y su escucha sigue viva dando errores en cada
   clic. [probable] `weld_panels.py:112, 818`.
7. **Miembro estructural: Aceptar enseguida de cambiar la medida guarda la vista previa vieja**
   (dentro de 0,35 s). [probable, por código] `weld_panels.py:141, 393`.
8. **Miembro estructural sobre un arco o un círculo:** el arco da un caño recto tangente; el círculo
   da error y deja un sólido a medio hacer. [verificado] Habría que aceptar solo rectas (o seguir el
   arco, como SW).
9. **Chapa: Extruir corte cancelado deja una "trampa" armada** que, en el próximo corte de cualquier
   pieza (incluso al abrir un archivo o deshacer), cambia "Por todo" a "espesor de la chapa".
   [probable] `sheet_panels.py:1081`.
10. **Corte de ensamblaje que falló se guarda igual** (cortes en rojo en las piezas, el panel cierra
    como si anduviera). [probable, por código] `assembly_features.py:1073`.
11. **Relación Tangente: borrarla y deshacer la vuelve sin su eje acompañante** (queda a medias, las
    piezas se mueven); cambiar de configuración un componente y deshacer se vuelve a aplicar solo.
    [probable] `mates_sw.py:437, 473`, `config_asm.py:865`.
12. **Panel cerrado por FreeCAD ("Sí" a "ya hay un diálogo abierto")** en Mover/Copiar sólidos,
    Eliminar/Conservar, Mover cara (esperando cara) o Convertir a chapa: después Redondeo, Chaflán,
    matrices, taladro y planos abren el panel nativo en inglés hasta que se abre y cierra uno de esos
    cuatro. Además quedan restos (marcas amarillas, vista previa). [probable] `dress_up_panel.py:1419`.
13. **Ecuaciones: Cancelar no deshace** si en el medio se cambió una cota con doble clic.
    [verificado por el agente] `equations.py:805`.
14. **Configuraciones: un croquis desactivado a propósito se reactiva** pegado a la cara si su
    operación se suprime por configuración. [probable] `configurations.py:633`.
15. **Lentitud en piezas grandes:** después de cada recálculo, los cortes con alcance automático
    hacen una operación booleana contra cada sólido (en una soldadura con muchos caños se nota);
    en ensamblajes, cada movimiento de un componente recorre todo el documento. [probable]
    `multibody.py:963`, `assembly_features.py:375`, `config_asm.py:855`.

## Chicos (casos raros o molestias)

- Deshacer con un panel abierto: cierra el panel y borra la operación nueva (igual que Cancelar).
  [verificado] Aceptable; el agente lo creía peor.
- Mover cara en Girar sin elegir la bisagra: Aceptar no hace nada y no dice por qué.
- Taladro > editar posiciones con la vista previa en error: el taladro se borra y el panel no vuelve.
- Eliminar/Conservar sólido: si falla a mitad, reintentar deja sólidos duplicados.
- Miembro estructural editado con error: el panel se cierra y se pierden los cambios.
- Chapa "Editar croquis sobre el desarrollo" deja cambiada para siempre la vista del croquis.
- Material quitado con la herramienta nativa sigue contando para la masa.
- Copiar y pegar un miembro o una chapa: las marcas internas siguen apuntando al original.
- Si se edita a mano el largo de un miembro en Ecuaciones, el alargue del extremo se lee como 0.
- Al abrir un archivo se despliegan todos los Cuerpos en el árbol.
- Pequeñas pérdidas de rendimiento en el árbol y en el croquis (refrescos repetidos).
- Ya visto antes: el aviso en inglés "One transformed shape does not intersect the support" al abrir
  una matriz vacía; el botón "Select Face" de Extruir en inglés.

## Recomendación de Claude

Arreglar primero 1, 2 y 3 (pueden dejar una pieza mal sin que se note), después 4 a 9 (los de
piezas soldadas y chapa son los que más usa el usuario). Los chicos, de a poco.
