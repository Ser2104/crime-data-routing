"""
Paso 19: LINEA BASE para la simulacion de peatones: un modelo de "demanda
directa", el metodo estandar en transporte (Schneider et al. 2009; modelo de
San Francisco 2010, R2 ~ 0.80): una regresion de los conteos contra lo que hay
a menos de RADIO m del punto.

    log(personas) ~ log(1 + habitantes) + log(1 + empleos)
                    + log(1 + suben/bajan del metro) + log(1 + buses que pasan)
                    + log(1 + comercios) + universidad a menos de RADIO m

A diferencia de la simulacion (src/peatones.py), este modelo NECESITA conteos
de la misma ciudad para ajustarse. Para que la comparacion sea justa se mide
con validacion cruzada "dejando uno afuera": cada punto se predice con un
modelo ajustado SIN ese punto. La simulacion no usa ningun conteo.

Se compara, en los mismos 98 puntos de Nueva York (paso 18):
    - formula actual (buses + 3 x locales)
    - demanda directa (validacion cruzada)
    - simulacion (entradas reales al metro)
    - demanda directa + simulacion como una variable mas (validacion cruzada)

Entradas: data/peatones/nyc/ (paso 18: conteos, manzanas, metro, GTFS, osm_nyc.pkl)
          data/peatones/comparacion_nueva_york.csv (paso 18)
Salida:   data/peatones/demanda_directa_nueva_york.csv

Ejecutar desde la carpeta del proyecto:
    python src/19_peatones_demanda_directa.py
"""
import json
import pickle
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

import flujo as F
import peatones as P
from riesgo_pie import FRANJAS

CARPETA = Path("data/peatones/nyc")
COMPARACION = "data/peatones/comparacion_nueva_york.csv"
SALIDA = "data/peatones/demanda_directa_nueva_york.csv"
CRS = 32618
RADIO = 400            # m (un cuarto de milla, como en los modelos de demanda directa)
GTFS_BUS = ["gtfs_m", "gtfs_b", "gtfs_bx", "gtfs_q", "gtfs_si", "gtfs_busco"]
SIMULACION = "simulacion (entradas reales al metro)"
FORMULA = "formula actual (buses + 3 x locales)"


def suma_cerca(puntos_xy, fuentes_xy, valores, radio=RADIO):
    """Suma de 'valores' de las fuentes a menos de 'radio' m de cada punto."""
    arbol = cKDTree(fuentes_xy)
    valores = np.asarray(valores, float)
    return np.array([valores[i].sum() for i in arbol.query_ball_point(puntos_xy, radio)])


def a_utm(lon, lat):
    g = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs=4326).to_crs(CRS)
    return np.column_stack([g.x, g.y])


def dejando_uno_afuera(X, y):
    """Prediccion de cada fila con una regresion lineal ajustada sin esa fila."""
    X = np.column_stack([np.ones(len(X)), X])
    pred = np.empty(len(y))
    for i in range(len(y)):
        resto = np.arange(len(y)) != i
        coef, *_ = np.linalg.lstsq(X[resto], y[resto], rcond=None)
        pred[i] = X[i] @ coef
    return pred


# ---------------------------------------------------------------------------
# 1. Puntos de conteo (paso 18) con sus coordenadas
comp = pd.read_csv(COMPARACION)
crudo = pd.DataFrame(json.loads((CARPETA / "conteos.json").read_text()))
xy_loc = {str(r["loc"]): r["the_geom"]["coordinates"] for _, r in crudo.iterrows()}
lon, lat = zip(*[xy_loc[str(l)] for l in comp["loc"]])
xy = a_utm(lon, lat)

# 2. Lo que hay a menos de RADIO m de cada punto
manzanas = gpd.read_file(CARPETA / "manzanas.geojson").to_crs(CRS)
mz_xy = np.column_stack([manzanas.geometry.x, manzanas.geometry.y])
metro = pd.DataFrame(json.loads((CARPETA / "metro.json").read_text()))
metro[["lat", "lon", "total"]] = metro[["lat", "lon", "total"]].astype(float)
metro = metro.groupby("station_complex_id").agg(lat=("lat", "mean"), lon=("lon", "mean"), total=("total", "sum"))
buses = pd.concat([P.salidas_gtfs(CARPETA / f"{n}.zip") for n in GTFS_BUS], ignore_index=True)
datos_osm = pickle.loads((CARPETA / "osm_nyc.pkl").read_bytes())
comercio = [(g.representative_point().x, g.representative_point().y) for t, g in datos_osm["lugares"]
            if t.get("amenity") in F.TIPOS_LOCAL or "shop" in t]
universidad = [(g.representative_point().x, g.representative_point().y) for t, g in datos_osm["lugares"]
               if t.get("amenity") in ("university", "college")]

X = pd.DataFrame({
    "habitantes": suma_cerca(xy, mz_xy, manzanas["poblacion"]),
    "empleos": suma_cerca(xy, mz_xy, manzanas["empleos"]),
    "metro": suma_cerca(xy, a_utm(metro["lon"], metro["lat"]), metro["total"] / 5 * 2),  # suben + bajan al dia
    "buses": suma_cerca(xy, a_utm(buses.geometry.x, buses.geometry.y), buses[list(FRANJAS)].sum(axis=1)),
    "comercios": suma_cerca(xy, a_utm(*zip(*comercio)), np.ones(len(comercio))),
})
X = np.log1p(X)
u_xy = a_utm(*zip(*universidad))
X["universidad"] = (cKDTree(u_xy).query(xy)[0] <= RADIO).astype(float)
y = np.log(comp["personas"].values)

# 3. Modelos con validacion cruzada (cada punto predicho sin usarlo)
comp["demanda directa (validacion cruzada)"] = np.exp(dejando_uno_afuera(X.values, y))
con_sim = np.column_stack([X.values, np.log1p(comp[SIMULACION].values)])
comp["demanda directa + simulacion (validacion cruzada)"] = np.exp(dejando_uno_afuera(con_sim, y))
pd.concat([comp, X.add_prefix("x_")], axis=1).to_csv(SALIDA, index=False)

coef, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(X)), X.values]), y, rcond=None)
print("Demanda directa ajustada con todos los puntos (solo para leer los coeficientes):")
print("  " + ", ".join(f"{c} {b:+.2f}" for c, b in zip(["constante"] + list(X.columns), coef)))

metodos = [FORMULA, "demanda directa (validacion cruzada)", SIMULACION,
           "demanda directa + simulacion (validacion cruzada)"]
rng = np.random.default_rng(1)
muestras = rng.integers(0, len(comp), (4000, len(comp)))
real = comp["personas"].values
print(f"\nParecido con los conteos reales en {len(comp)} puntos de Nueva York (Spearman, IC95):")
for m in metodos:
    x = comp[m].values
    boot = [spearmanr(x[i], real[i]).statistic for i in muestras]
    dif = [spearmanr(comp[SIMULACION].values[i], real[i]).statistic - b for i, b in zip(muestras, boot)]
    linea = f"  {m:52s} {spearmanr(x, real).statistic:+.2f} ({np.percentile(boot, 2.5):+.2f} a {np.percentile(boot, 97.5):+.2f})"
    if m != SIMULACION:
        linea += f" | simulacion - este: {np.mean(dif):+.2f} ({np.percentile(dif, 2.5):+.2f} a {np.percentile(dif, 97.5):+.2f})"
    print(linea)
r = comp["demanda directa (validacion cruzada)"] / comp["personas"]
print(f"\nDemanda directa, tamano: dentro del doble en {((r > 0.5) & (r < 2)).mean():.0%} de los puntos "
      f"(ajustada con conteos de NYC; la simulacion, sin ajustar: ver paso 18)")
