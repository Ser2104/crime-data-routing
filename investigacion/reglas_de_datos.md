# Reglas de datos por nivel (versión 3, 5 de octubre de 2026)

Se fijan **antes** de desarrollar la fórmula. Son iguales para todas las ciudades. Cualquier cambio se anota al final con fecha y motivo, y si llega después de sellar una versión de la fórmula, crea una versión nueva (`protocolo.md`, punto 3).

**Idea central:** lo que se **califica** (los delitos del futuro) es **lo mismo en todas las ciudades y todos los niveles**. Lo que cambia por nivel es **qué información del pasado** puede usar la fórmula.

## 1. Periodos (iguales para todas las ciudades)

- **Pasado** (lo que se permite usar para construir el mapa de una ciudad): 2024-01-01 a 2025-08-31.
- **Futuro** (con lo que se califica): 2025-09-01 a 2026-08-31.

## 2. Qué se califica: el núcleo universal

**Medida principal:** cantidad de delitos del **núcleo universal** en el futuro. Es la definición del FBI de delito violento, sin la violación:

| Clase | Código NIBRS | Incluye |
|---|---|---|
| `homicidio` | 09A | Homicidio doloso y homicidio no negligente |
| `robo` | 120 | Robo con violencia o amenaza (asalto) |
| `agresion_grave` | 13A | Agresión grave (con arma o con lesión grave) |

- **Sin pesos de gravedad.** Cada delito cuenta 1. Así no depende de detalles, como el tipo de arma, que no todas las ciudades publican.
- **Hora:** la de **ocurrencia** si la ciudad la publica; si no, la del reporte. Se registra cuál se usó.
- **Medida secundaria** (solo en las ciudades que permiten separar las categorías; **se reporta aparte y nunca se compara entre ciudades con otra definición**): la definición amplia de Pittsburgh, que suma agresión simple, amenazas, armas, arrebato, carterista, secuestro y drogas.

**Traducción de las categorías de cada ciudad** (archivo `src/multiciudad/categorias.py`):

- por **códigos estándar** (NIBRS o UCR) cuando la ciudad los publica;
- si no, por el **nombre de la categoría**;
- para las ciudades de examen, la tabla se escribe **antes de abrir**, usando solo el diccionario de datos oficial de la ciudad (sus documentos), nunca sus registros;
- lo que no aparece en la tabla se excluye, y el informe dice cuántos casos fueron.

**Se excluye en todas las ciudades** (solo reglas que se pueden aplicar igual en todas):

- delitos sin ubicación;
- delitos sexuales (Pittsburgh oculta su ubicación por privacidad; misma regla para todas);
- delitos fuera del contorno de la ciudad o a más de 50 m de una calle caminable;
- delitos a menos de 30 m de cárceles, hospitales, comisarías o centros de servicios sociales (con OpenStreetMap).

La marca de "violencia doméstica" **no** se usa para excluir en la medida principal, porque no todas las ciudades la publican.

**Ubicación:** la que publica la ciudad. Se aceptan las ubicaciones redondeadas a la cuadra.

## 3. Qué información del pasado puede usar la fórmula

Todas las fórmulas pueden usar **lo aprendido en las ciudades del grupo "aprender"**, con toda su información. Lo que cambia por nivel es qué datos **de la ciudad evaluada**, y **solo del pasado**, pueden entrar:

| Nivel | Delitos del pasado de la ciudad evaluada | Datos públicos de la ciudad evaluada |
|---|---|---|
| **B: Detallado** | Todos los delitos, con ubicación y su categoría amplia (sección 2) | Todos los permitidos (sección 4) |
| **A: Solo núcleo** | Solo los del núcleo universal, con ubicación | Todos los permitidos |
| **C: Grueso** | Todos los delitos, con ubicación, pero solo en tres bolsas: `violento` (el núcleo, más los violentos sin detalle; la violación está excluida en todas las ciudades), `propiedad` (hurto, robo de vehículo, robo en vivienda o local, incendio intencional) y `otro` (todo lo demás) | Todos los permitidos |
| **Por zona** | Conteos del núcleo por **grupo de manzanas del censo** (*block group*) | Todos los permitidos |
| **Totales** | Solo el **total de la ciudad** del núcleo, por mes (como lo que se reporta al FBI) | Todos los permitidos |
| **Sin delitos** | **Ninguno** | Todos los permitidos |
| **Solo mapa** | **Ninguno** | **Solo OpenStreetMap** (calles, lugares, faroles dibujados) |

- **A y C son ramas, no peldaños:** A tiene la categoría exacta pero menos casos; C tiene todos los casos pero mezclados. Comparar B contra A y C responde: **¿cuánto ayuda saber del pasado los delitos menores para predecir los violentos?**
- **B es la referencia de cada ciudad:** "lo mejor con todos los datos de esa ciudad". El resultado de los otros niveles se expresa como **porcentaje del beneficio de B en la misma ciudad**.
- **El nivel C se simula en cualquier ciudad** agrupando sus categorías. Cincinnati, que publica así, es un caso real de C.

## 4. Datos públicos permitidos

| Dato | Detalle |
|---|---|
| OpenStreetMap | Calles, comercios, estacionamientos, parques, faroles dibujados, edificios (archivos de Geofabrik). Desde la versión 3: escuelas, universidades, hospitales, comisarías, gasolineras, tiendas de licor, cajeros automáticos, estaciones de tren o metro, estadios, uso del suelo (residencial, comercial, industrial) y densidad de edificios |
| Población del Censo 2020 | **Solo el total por manzana** |
| Empleos LEHD LODES | **Solo el total por manzana** (C000) |
| Horarios de transporte | GTFS (buses que pasan por hora y paradas cerca; las paradas salen de los horarios oficiales, no de OpenStreetMap, salvo en el nivel "solo mapa") |
| Luz | Satélite VIIRS (NASA) e inventarios oficiales de faroles |
| Peatones simulados | `src/peatones.py`, que usa solo lo anterior |
| 311 | **Solo categorías sin relación con delitos** (faroles, baches…) |

## 5. Prohibido (en todos los niveles)

- **Raza, etnia, ingreso o pobreza**, de cualquier fuente. Tampoco lugares que indican sobre todo pobreza: casas de empeño, préstamos rápidos y cambio de cheques, albergues y centros de servicios sociales (estos últimos solo se usan para excluir delitos ocurridos junto a ellos, sección 2). Tampoco datos de víctimas o sospechosos (edad, raza, género); ni siquiera se descargan cuando se puede evitar.
- **Cualquier dato derivado de delitos** de la ciudad evaluada, salvo lo que permite su nivel en la tabla de la sección 3. Esto incluye:
  - totales del FBI (son información del nivel "Totales");
  - mapas de delitos, rankings de barrios y noticias;
  - categorías del 311 relacionadas con delitos (por ejemplo "actividad de drogas").
- **Como rasgos de la fórmula:** nombres de calles o barrios, coordenadas, identificadores de tramos y la identidad de la ciudad.
- **Ajustes manuales para una ciudad o barrio en particular.** La fórmula es la misma para todas y se construye solo con código.
- **Usar datos del examen** (caja fuerte) para cualquier cosa antes de la apertura registrada.

## 6. Cómo se califica (igual en todas las ciudades y niveles)

- **Viajes:** 2,000 viajes a pie al azar por ciudad, de 500 a 3,000 m en línea recta, a las 2 a. m., 9 a. m., 3 p. m. y 9 p. m. La semilla de cada ciudad se fija antes de abrir.
- **Medida principal:** cambio en los delitos **del núcleo universal** del **futuro** en las calles de la ruta de menor riesgo, frente a la más rápida, con su intervalo de confianza del 95% (bootstrap).
- **Medidas secundarias:**
  - parte de los delitos futuros del núcleo que cae en el 10% de la red marcada como más riesgosa;
  - si el % mostrado se cumple (calibración);
  - la medida amplia (sección 2), solo donde existe y reportada aparte.
- **Ciudades con pocos casos:** antes de abrir el examen se calcula si cada ciudad tiene casos suficientes para una conclusión. Si alguna no alcanza, se declara de antemano que su resultado se combina con el de otras ciudades (resultado conjunto), y no se interpreta sola.
- **Pruebas trampa** (`protocolo.md`, punto 4).

## Cambios a estas reglas

- **2026-10-05 (versión 3), pedido por el autor.** Se agregan rasgos de lugares de OpenStreetMap: escuelas, universidades, hospitales, comisarías, gasolineras, tiendas de licor, cajeros, estaciones de tren o metro, estadios, uso del suelo y densidad de edificios. Las paradas de bus pasan a salir de los horarios oficiales (en Filadelfia casi no están dibujadas en OpenStreetMap). La tasa de la ciudad (nivel "totales") se calcula con la población dentro del contorno, no con la del margen de 1 km.
  - Se prohíben explícitamente los lugares que indican sobre todo pobreza.
  - Las cámaras de vigilancia **no** entran como rasgo: están dibujadas de forma muy desigual entre ciudades. Se estudian aparte.
  - Ninguna fórmula estaba sellada. Las versiones anteriores (v0 a v1) quedan en el registro de práctica.

- **2026-10-04 (versión 2), propuesto por el autor.** Se separa lo que se **califica** de lo que la fórmula **puede usar**:
  - La medida principal pasa a ser el **núcleo universal** (homicidio, robo, agresión grave, sin pesos) en todas las ciudades.
  - Los niveles se reorganizan en una escalera según la información de delitos del pasado: B, A, C, por zona, totales, sin delitos y solo mapa. Los antiguos niveles 1 a 5 equivalen a B, por zona, totales, sin delitos y solo mapa.
  - Delitos sexuales excluidos en todas las ciudades. La violencia doméstica ya no se usa para excluir. Prohibido también descargar datos de víctimas o sospechosos cuando se puede evitar.
  - **Motivo:** en las ciudades de desarrollo, las categorías varían mucho. Cincinnati (práctica) mezcla agresiones simples, armas y drogas en una sola bolsa ("Part 2"), y Chapel Hill (aprender) usa unos 1,900 nombres libres. Calificar con definiciones distintas haría injusta la comparación.
  - Ningún dato de las ciudades de examen se usó para este cambio, y ninguna fórmula estaba sellada.
- **2026-10-04 (versión 2).** Se quita la regla de "puntos concentrados" (10 o más delitos en la misma coordenada), y se agregan "fuera de la ciudad" y "a más de 50 m de una calle", como en Pittsburgh.
  - **Motivo:** cada ciudad publica la ubicación con distinta precisión. Seattle la redondea al centro de la cuadra (14% de coordenadas únicas): la regla borraría el 29% de sus delitos violentos, que son reales. Cincinnati desplaza cada punto (93% de coordenadas únicas) y nunca la activaría.
  - Lo que la regla buscaba (instituciones escondidas) ya lo cubre la regla de instituciones de OpenStreetMap, igual para todas.
  - Medido solo en ciudades de desarrollo.
- **2026-10-04 (corrección menor, versión 2).** La bolsa `violento` del nivel C ya no dice "núcleo + violación", porque la violación está excluida en todas las ciudades. Ahora es el núcleo más los violentos sin detalle (por ejemplo, el "Part 1 Violent" de Cincinnati).
