# Protocolo de evaluación (versión 1, 3 de octubre de 2026; cambios anotados al final)

Reglas fijadas **antes del sorteo** de ciudades. Cualquier cambio a este protocolo se anota al final, con fecha y motivo.

## 1. Grupos de ciudades

| Grupo | Ciudades | Para qué | Cuándo se miran sus delitos |
|---|---|---|---|
| **Aprender** | Pittsburgh (fija), Chapel Hill, Chicago, Seattle | Crear la fórmula | Siempre |
| **Práctica** | Cincinnati, Gainesville | Probar y mejorar la fórmula | Muchas veces |
| **Examen principal** | Filadelfia (grande), Baton Rouge (mediana), Tempe (universitaria) | La nota de una versión sellada | **Una sola vez** |
| **Reserva externa** (*external holdout*) | Dallas, San Francisco, Boston, Colorado Springs | Prueba limpia de **una** versión (ver punto 3) | **Una sola vez en total** |
| **Por zona** | Austin, Cambridge, Somerville, Los Ángeles | Comprobación extra a nivel de zona | **Una sola vez en total** |
| **Aplicación real** | State College | Uso de la fórmula sin datos públicos | Sus datos (Right-to-Know) se tratan como examen: una vez, con versión sellada |

**Sorteo:** hecho el 2026-10-03 a las 11:44 con el número **4818**, elegido por el autor.

- Comando: `python investigacion/sorteo_ciudades.py 4818` (Python 3.13.3). Repetido dos veces, mismo resultado.
- Hasta este momento, de las ciudades de examen solo se revisó la descripción de sus bases (nombres de columnas y fechas más antigua y más reciente). **Ningún delito.**

## 2. Caja fuerte y sello

- Los delitos de las ciudades del examen principal, de la reserva externa y de las ciudades por zona se descargan **directo a la caja fuerte**, sin mirarlos. Se registra la huella digital de cada archivo (SHA-256) y la fecha.
- El programa que crea la fórmula **no puede leer** la caja fuerte, y una comprobación automática lo detiene si lo intenta.
- La fórmula solo usa rasgos generales: nunca nombres de calles, coordenadas ni la identidad de la ciudad.
- Antes de abrir cualquier examen, la versión de la fórmula se **sella**: se guarda el archivo, se publica su huella digital con fecha y el código queda congelado con una etiqueta en git.

## 3. Versiones de la fórmula: cada grupo de examen es una "bala de una sola vez"

1. **La primera versión sellada** se aplica **una sola vez** al **examen principal**. Es **v2**: las pruebas de práctica se llamaron v0, v0.1, v1 y v2, y ninguna tocó el examen. En los puntos siguientes, "v1" quiere decir esta primera versión sellada. Su resultado es **el resultado principal** y se reporta tal cual, sea bueno o malo.
2. **Si v1 se modifica** (rasgos, parámetros, reglas, datos de entrenamiento), nace **v2**. Se documenta en el registro de versiones: qué cambió, por qué y la fecha. Los resultados de v1 **no se borran ni se reemplazan**.
3. **Si la reserva externa nunca se abrió**, v2 puede usarla como examen limpio, una sola vez.
4. **Si la reserva ya se abrió con v1**, ya no sirve como examen limpio de v2: harían falta **ciudades nuevas, nunca vistas**.
5. **Una ciudad cuyo resultado ya se vio** (aunque sea solo un número resumen) puede usarse después para desarrollo o aprendizaje, pero **nunca más como prueba independiente**.
6. **Lo mismo con State College:** una vez abiertos los delitos del Right-to-Know, dejan de ser un examen limpio.
7. **Un disparo puede evaluar varias fórmulas a la vez**, siempre que todas se hayan sellado **antes** de abrir. Así, las fórmulas de los niveles 1 a 5 se sellan juntas y se evalúan juntas en una sola apertura del examen principal.
8. **Estrategia:** como las ciudades limpias son pocas, la reserva **no se abre para v1** salvo que v1 se declare versión final. Si hay mejoras después del examen principal, la reserva queda para la versión mejorada.

### Sellado de los datos de examen (hecho)

- **2026-10-03, de 22:35 a 22:49 UTC:** el autor selló las 11 ciudades de `holdout_main`, `holdout_reserve` y `holdout_zona`, con `investigacion/caja_fuerte.py` (commit `fa14800`, guardado en git **antes** de correrlo).
  - Lo ejecutó en su terminal, con una frase-contraseña que solo él conoce.
  - Las 11 pasaron la verificación inmediata sin mostrar contenido.
- **Registro público:** `investigacion/caja_fuerte/manifiesto.json`, con ciudad, fuente, fecha, huellas SHA-256 del original y del cifrado, salt e iv, y el commit del programa. **No registra el tamaño de los archivos.**
- **No se analiza** ni el tamaño de los archivos cifrados ni el tiempo que tardó cada descarga (la diferencia entre las horas del manifiesto): ambos dependen indirectamente de cuántos delitos hay.
- En disco solo existen los archivos `.enc`. Nunca se escribió una copia legible.

**Declaración para el artículo:**

> The holdout datasets were downloaded and encrypted (AES-256-GCM, scrypt key derivation) by a program executed locally by the author on 2026-10-03; the program was committed to version control before execution, no plaintext copy was written to disk, and the passphrase was never provided to the system used to develop the models. Before the city lottery, only dataset metadata (column names and earliest/latest dates) was inspected; no incident records of holdout cities were inspected before the formulas were frozen.

## 4. Pruebas trampa (en cada examen)

- **Mapa desordenado:** los valores del mejor nivel se mezclan al azar entre las calles (dentro de cada franja).
  - Su calificación rápida debe quedar más cerca del azar (0.10) que del mapa real.
  - En las rutas, debe evitar menos de la mitad de lo que evita el mapa real.
- **Futuro desordenado:** los delitos del futuro se mezclan al azar entre las calles, y se califican con el mapa real. Su calificación rápida debe quedar más cerca del azar que del mapa real. Aquí el azar es la parte de calles que cae en el 10% marcado.

Si alguna "acierta", hubo una fuga: el examen de esa ciudad se invalida, se investiga y se reporta.

La prueba de **ciudad equivocada** (la predicción de una ciudad contra los delitos de otra) se reemplazó por la del futuro desordenado **antes de abrir**. No se puede hacer bien, porque cada ciudad tiene calles distintas y no hay forma de poner una sobre otra.

## 5. Quién corre los exámenes

El examen lo corre un programa separado que **no aprende nada**: `src/multiciudad/09_examen.py`. Solo recibe la fórmula sellada y la caja fuerte. Lo ejecuta el autor, en su terminal:

1. `python investigacion/caja_fuerte.py abrir holdout_main --motivo "examen formula v2"` (pide la frase).
2. `python src/multiciudad/09_examen.py`.
   - Primero comprueba las huellas de los modelos contra `sello_v2.json`.
   - Después hace el **chequeo de lectura**: fechas, coordenadas y categorías legibles, con los mínimos del pre-registro.
   - Si la lectura no pasa, se detiene **sin calcular ningún resultado**. Se corrige solo el lector (nunca la fórmula ni las tablas de categorías), se anota como desviación y se vuelve a correr.
   - Recién entonces califica.
3. Los resultados quedan en `investigacion/resultados/examen_v2/` y se reportan todos, tal cual.

## Registro de versiones

| Versión | Fecha de sello | Huella digital | Qué cambió | Evaluada en |
|---|---|---|---|---|
| v2 | 2026-10-05 | `investigacion/sello_v2.json` (SHA-256 de los 14 archivos de `models/multiciudad/v2/`), etiqueta git `formula-v2-sellada` | Primera versión sellada: rasgos públicos + lugares de OSM + horarios corregidos; aprende con Pittsburgh, Chapel Hill, Chicago y Seattle (ver `registro_practica.md`) | Examen principal (pendiente) |

## Cambios a este protocolo

- 2026-10-03: la reserva no se llama "segundo examen", sino reserva externa (*external holdout*), atada a la versión que evalúa (punto 3). Propuesto por el autor.
- 2026-10-03: cada grupo de examen es una "bala de una sola vez" en total, no una por versión (puntos 3.3 a 3.6). Se agregan los puntos 3.7 (un disparo puede evaluar varias fórmulas selladas juntas) y 3.8 (estrategia de la reserva). Propuesto por el autor.
- 2026-10-05, antes de sellar v2 y antes de abrir cualquier examen:
  - la primera versión sellada se llama v2, por los nombres de práctica (punto 3.1);
  - la prueba de "ciudad equivocada" se reemplaza por la del "futuro desordenado", y se fijan los criterios numéricos de las trampas (sección 4);
  - se nombra el programa del examen y se agrega el chequeo de lectura (sección 5).
