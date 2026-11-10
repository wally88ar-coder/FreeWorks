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
