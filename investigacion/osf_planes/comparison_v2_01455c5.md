# Comparación con métodos publicados: plan fijado ANTES de correr (2026-10-08)

**Qué es:** un análisis **exploratorio**. Los datos de las 3 ciudades del examen ya se abrieron y sus resultados ya se vieron, así que esto no es una prueba confirmatoria. Para que sea limpio:
- este plan se guarda en git, con fecha, **antes** de escribir el programa y de ver cualquier número;
- los parámetros salen del artículo original, sin ajustar nada;
- se reporta todo lo que salga, sea bueno o malo.

Si algo del plan tuviera que cambiar, el cambio se anota abajo con su fecha y su motivo.

## 1. Método de referencia: Galbrun, Pelechrinis y Terzi (2016)

Se usa la versión de conferencia, de libre acceso: "Safe Navigation in Urban Environments" (UrbComp 2014). La versión de revista es *Information Systems* 57:160–171 (2016). Se implementa tal como lo describe el artículo:

1. **Modelo de riesgo** (su ecuación 3 y su ecuación 4):
   - densidad de los delitos con un **núcleo gaussiano (KDE)** y ancho según la **regla de Scott**. Se implementa con `scipy.stats.gaussian_kde` (`bw_method="scott"`), en coordenadas proyectadas (metros, la zona UTM de la ciudad);
   - la densidad se evalúa en los **puntos de la geometría de cada tramo** (sus vértices) y se **suma**: Λ(e) = Σ λ(ξ);
   - el riesgo del tramo es la suma **normalizada**: r(e) = Λ(e) / Σ Λ.
   - **Por eficiencia,** la densidad se calcula sobre una grilla de 20 m (convolución FFT con el mismo núcleo) y se interpola en cada punto. Antes de usarla se comprueba contra el cálculo exacto en una muestra aleatoria de puntos: la diferencia relativa mediana debe ser **menor al 1%**.
2. **Riesgo de una ruta:** riesgo total r_t(P) = 1 − Π(1 − r(e)), su ecuación 1. Se minimiza como la suma de −log(1 − r(e)).
3. **Conjunto de rutas:** la **envolvente convexa inferior** del par (largo, riesgo total), con su algoritmo *Sum-Recursive*:
   - las dos puntas son la ruta más corta y la de menor riesgo;
   - entre dos rutas P_u y P_l se busca una ruta intermedia con Dijkstra y pesos −log(1 − r(e)) + μ·largo(e), donde μ = −λ y λ = (r(P_u) − r(P_l)) / (largo(P_u) − largo(P_l));
   - se repite hasta que no aparezcan rutas nuevas, con un tope de seguridad de 30 niveles.
4. **Ruta elegida** (el artículo no elige una sola, porque la elige la persona): **la de menor riesgo total dentro del mismo límite de tiempo extra que usa nuestra app**, es decir, el mayor entre 10 minutos y la mitad del tiempo de la ruta más corta, a 80 m/min. La ruta más corta siempre está dentro del límite, así que siempre hay una elegida.
5. **Sin franjas horarias:** el modelo del artículo no usa la hora, y se respeta así.

**Dos variantes,** según qué delitos del **pasado** (2024-01-01 a 2025-08-31, tras las exclusiones de siempre) recibe:
- **G16-núcleo:** solo los delitos violentos del núcleo. Es la misma información que nuestro nivel A.
- **G16-todos:** todos los delitos conservados. Es la misma información que nuestros niveles B y C.

## 2. Descomposición: su mapa de riesgo dentro de nuestro buscador de rutas

Para separar "mejor mapa" de "mejor forma de elegir la ruta":
- **KDE-núcleo** y **KDE-todos:** el mismo r(e) de arriba, usado como mapa de riesgo en **nuestro** buscador, sin cambios, igual en las 4 franjas. Se evalúa igual que nuestros mapas.

## 3. Evaluación (igual para todos)

- **Ciudades:** Filadelfia, Baton Rouge y Tempe (examen de reemplazo). Se leen de los archivos ya abiertos, y no se abre ninguna caja.
- **Viajes:** los **mismos 2,000** de cada ciudad (`evaluar_rutas.tareas`, misma semilla).
- **Delitos que se cuentan:** los del núcleo del futuro (2025-09-01 a 2026-08-31) en los tramos de cada ruta, solo en la franja del viaje. Es lo mismo que en el examen.
- **Medida principal de esta comparación: el cambio sobre TODOS los viajes.**
  - con G16: la ruta elegida contra la más corta;
  - con nuestros mapas: la ruta de menor riesgo si la app la ofrece, y la más rápida si no.
  - Se usa esta medida porque los métodos tienen reglas distintas para "ofrecer" una alternativa: comparar sobre todos los viajes es lo justo.
- **Comparaciones pareadas** (mismos viajes):
  - G16-núcleo y KDE-núcleo **contra nuestro nivel A** y contra el mapa de calor A;
  - G16-todos y KDE-todos **contra nuestros niveles B y C** y contra el mapa de calor B.
- **Intervalos de 95%:**
  - remuestreando **viajes** (2,000 remuestreos);
  - remuestreando **zonas de 1 km** del origen (2,000 remuestreos);
  - semilla fija 20261009.
- **Secundarias:** el cambio solo en los viajes donde la ruta elegida difiere de la más corta, y los minutos extra (mediana).

## 4. Orden de trabajo

1. **Pruebas del programa sin datos del examen:**
   - la densidad en grilla contra el cálculo exacto;
   - la envolvente convexa en un grafo pequeño, cuyo resultado se conoce;
   - las puntas de la envolvente son la ruta más corta y la de menor riesgo.
2. **Ensayo completo con Gainesville** (ciudad de práctica), con pocos viajes.
3. **Las 3 ciudades** del examen, con 2,000 viajes.
4. **Informe:** todos los números, y en el artículo, en la sección de análisis exploratorios.

## Cambios a este plan

*(ninguno)*

## Detalles de implementación

Anotados el 2026-10-08, después de las pruebas y **antes** de correr las ciudades del examen. Programa: `investigacion/comparacion_metodos.py`.

- **Desempate:** a cada peso se le suma 10⁻¹² por metro. Entre rutas de igual riesgo gana la más corta, y ningún tramo queda con peso cero, porque el buscador de caminos ignora los pesos cero. Es miles de veces menor que cualquier diferencia de riesgo.
- **Calles paralelas:** si entre dos esquinas hay más de un tramo, cada búsqueda usa el de menor peso para ese costo.
- **Normalización:** r(e) se normaliza sobre los tramos distintos. Los dos sentidos de una calle comparten tramo, como en el resto del proyecto.
- **Pruebas superadas:**
  - la envolvente coincide con la fuerza bruta en 20 de 20 grafos al azar;
  - la densidad en grilla difiere de la exacta en un 0.05% (núcleo) y un 0.11% (todos) en Gainesville.
- **Control al correr:** los delitos en la ruta más corta de G16 deben coincidir con los de nuestra ruta más rápida. Las dos minimizan el largo, y solo un empate entre rutas de igual largo podría hacerlas distintas.
