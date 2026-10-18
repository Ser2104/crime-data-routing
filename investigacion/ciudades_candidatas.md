# Paso 0: ciudades candidatas (revisado el 3 de octubre de 2026)

Solo se revisó **la descripción** de cada base de datos: columnas, fechas más antigua y más reciente, y si se actualiza. **No se descargó ni se miró ningún delito.**

**Requisitos para entrar al estudio:**

- cada delito con su ubicación (coordenadas o cuadra);
- fecha y hora;
- datos de 2024 a 2026;
- ciudad de EE. UU.

## Sirven (nivel 1: cada delito con ubicación y hora)

| Ciudad | Tipo | Habitantes (aprox.) | Base de datos | Datos desde – hasta |
|---|---|---|---|---|
| Pittsburgh, PA | Mediana | 300 mil | WPRDC | 2024 – 2026 (ya la usamos) |
| Filadelfia, PA | Grande | 1.6 millones | OpenDataPhilly `incidents_part1_part2` | 2006 – oct 2026 |
| Chicago, IL | Grande | 2.7 millones | `ijzp-q8t2` | 2001 – sep 2026 |
| Dallas, TX | Grande | 1.3 millones | `qv6i-rri7` | actualizada oct 2026 |
| San Francisco, CA | Grande | 800 mil | `wg3w-h783` | 2018 – oct 2026 |
| Seattle, WA | Grande | 750 mil | `tazs-3rd5` | hasta oct 2026 |
| Boston, MA | Grande | 650 mil | data.boston.gov (2023 en adelante) | 2023 – 2026 |
| Colorado Springs, CO | Grande | 490 mil | `bc88-hemr` | hasta oct 2026 |
| Cincinnati, OH | Mediana | 310 mil | `7aqy-xrv9` | **solo desde jun 2024** |
| Baton Rouge, LA | Mediana | 220 mil | `pbin-pcm7` | hasta oct 2026 |
| **Gainesville, FL** | **Universitaria** (U. de Florida) | 145 mil | `gvua-xt9q` | 2011 – oct 2026 |
| **Tempe, AZ** | **Universitaria** (Arizona State) | 185 mil | General Offenses (ArcGIS); dirección aproximada por cuadra | hasta oct 2026 |
| **Chapel Hill, NC** | **Universitaria** (UNC) | 60 mil | Police Incident Reports Written (ArcGIS) | 2010 – jun 2026 |
| Nueva York, NY | Muy grande | 8.3 millones | `qgea-i56i` + `5uac-w243` | hasta jun 2026 (muy pesada; ya usada para peatones) |

## Ciudades reales de "nivel 2" (publican solo por zona, no por dirección)

Austin (por grupo de manzanas), Cambridge MA (por zona), Somerville MA (por cuadra codificada) y Los Ángeles (por área). Sirven como ejemplos reales de nivel 2, pero no como examen a nivel de calle.

## No sirven

- Honolulu: solo 6 meses.
- Richmond VA: sin ubicación.
- Charlottesville: solo totales.
- Boulder: no se encontró la base de delitos con ubicación.
- Evanston y Urbana: datos viejos.

## Reserva externa (*external holdout*): no se tocan

Dallas, San Francisco, Boston y Colorado Springs no entran a las 9. Quedan como **reserva externa** según `investigacion/protocolo.md` (punto 3): el examen limpio de la versión de la fórmula que corresponda.

## Propuesta: 9 ciudades

- **Grandes:** Filadelfia, Chicago, Seattle.
- **Medianas:** Pittsburgh, Cincinnati, Baton Rouge.
- **Universitarias:** Gainesville, Tempe, Chapel Hill. Chapel Hill es la más parecida a State College en tamaño.

**Reglas del sorteo:**

- **Pittsburgh va fijo a "aprender"**: ya vimos sus datos, así que no puede ser examen.
- Las otras 8 se sortean.
- **El examen final lleva una ciudad de cada tipo** (una grande, una mediana, una universitaria). Así el examen prueba los tres casos, incluido el parecido a State College.
- El sorteo usa un número que elige el usuario. Con el mismo número, cualquiera puede repetirlo y obtener el mismo resultado, así que no se puede cambiar después.
