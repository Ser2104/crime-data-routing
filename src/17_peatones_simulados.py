"""
Paso 17: peatones por tramo en Pittsburgh SIMULANDO VIAJES A PIE (src/peatones.py)
y comparacion contra conteos reales de peatones.

Hoy el riesgo usa una formula supuesta para "gente que pasa": buses por hora
cerca + 3 x locales abiertos cerca (paso 4). Aqui se estima con viajes simulados
entre casas, trabajos, paradas y comercios, y se mide cual de los dos se parece
mas a los conteos reales.

Datos (se descargan la primera vez y se guardan en data/peatones/):
    - poblacion por manzana: Censo 2020 (TIGERweb)
    - empleos por manzana: LEHD LODES 2023 (Pensilvania)
    - comercios: data/raw/osm_locales.geojson (paso 4)
    - estacionamientos: OpenStreetMap (amenity=parking)
    - paradas: horario GTFS de PRT (paso 4) y, como variante, las subidas y
      bajadas REALES por parada que publica PRT (dia de semana)
    - conteos reales: Envision Downtown 2016 (WPRDC), 7 a. m. a 8 p. m., en
      esquinas del centro (se mide lo que pasa a menos de 30 m de la esquina)

Salidas:
    data/processed/peatones_tramos.csv  (personas por hora en cada franja, por tramo)
    data/peatones/comparacion_pittsburgh.csv

Ejecutar desde la carpeta del proyecto:
    python src/17_peatones_simulados.py
"""
import json
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
import requests
from scipy.stats import spearmanr

import flujo as F
import peatones as P
from riesgo_pie import FRANJAS

RED = "data/processed/red_peatonal.graphml"
GTFS = "data/raw/gtfs_prt.zip"
LOCALES = "data/raw/osm_locales.geojson"
FLUJO = "data/processed/flujo_tramos.csv"
CARPETA = Path("data/peatones")
MANZANAS = CARPETA / "manzanas_pittsburgh.geojson"
ESTACIONAMIENTOS = CARPETA / "estacionamientos_pittsburgh.geojson"
LUGAR = "Pittsburgh, Pennsylvania, USA"
SUBIDAS = CARPETA / "subidas_prt.csv"
CONTEOS = CARPETA / "envision_2016.json"
SALIDA = "data/processed/peatones_tramos.csv"
USO_PARADAS = ("https://services3.arcgis.com/544gNI3xxlFIWuTc/arcgis/rest/services/"
               "PRT_Bus_Stop_Usage_Unweighted/FeatureServer/0/query")
ENVISION = ("https://data.wprdc.org/api/3/action/datastore_search?"
            "resource_id=dc29d000-7461-4b2b-a4b2-e5db202a1c83&limit=1000")
HORAS_CONTEO = {"manana": 5, "tarde": 6, "noche": 3}  # 7-11, 12-17, 18-20 h
MIN_HORAS = 12   # un punto necesita casi todo el dia contado
CARPETA.mkdir(parents=True, exist_ok=True)


def subidas_reales():
    """Subidas + bajadas por parada en un dia de semana (el mes mas reciente con dato)."""
    if not SUBIDAS.exists():
        filas, desde = [], 0
        while True:
            r = requests.get(USO_PARADAS, timeout=120, params={
                "where": "route_code='All Routes'", "outFields": "*", "returnGeometry": "false",
                "resultOffset": desde, "resultRecordCount": 2000, "f": "json"}).json()
            filas += [f["attributes"] for f in r.get("features", [])]
            desde += len(r.get("features", []))
            if not r.get("exceededTransferLimit"):
                break
        pd.DataFrame(filas).to_csv(SUBIDAS, index=False)
    u = pd.read_csv(SUBIDAS)
    meses = sorted({c[-6:] for c in u.columns if c.startswith("B_W_")}, reverse=True)
    suben = pd.concat([u[f"B_W_{m}"] for m in meses], axis=1).bfill(axis=1).iloc[:, 0]
    bajan = pd.concat([u[f"A_W_{m}"] for m in meses], axis=1).bfill(axis=1).iloc[:, 0]
    return (suben.fillna(0) + bajan.fillna(0)).groupby(u["stop_code"].astype(str)).sum()


def conteos_envision():
    """Personas contadas un jueves de 7 a. m. a 8 p. m., por punto (grados)."""
    if not CONTEOS.exists():
        CONTEOS.write_text(requests.get(ENVISION, timeout=120).text)
    d = pd.DataFrame(json.loads(CONTEOS.read_text())["result"]["records"])
    d = d[d["Day"] == "Thursday"]
    d["personas"] = pd.to_numeric(d["Persons_pr_Hour"], errors="coerce")
    g = d.groupby(["Sub Location", "Latitiude", "Longitude"]).agg(
        nombre=("Street", "first"), horas=("personas", "count"), por_hora=("personas", "mean")).reset_index()
    g = g[g["horas"] >= MIN_HORAS]   # descarta coordenadas sueltas mal escritas
    g["personas_dia"] = g["por_hora"] * sum(HORAS_CONTEO.values())
    return gpd.GeoDataFrame(g, geometry=gpd.points_from_xy(g["Longitude"].astype(float),
                                                           g["Latitiude"].astype(float)), crs=4326)


def en_horas_de_conteo(tabla, prefijo):
    """Personas en las horas del conteo segun una tabla por franja (por hora)."""
    return sum(tabla[f"{prefijo}{f}"] * h for f, h in HORAS_CONTEO.items())


# ---------------------------------------------------------------------------
# 1. Red y lugares
print("Cargando red...")
G = ox.project_graph(ox.load_graphml(RED))
red = P.preparar_red(G)
tramos, _ = F.tramos_y_medios(G)
caja = tuple(gpd.GeoSeries(gpd.points_from_xy(red["xy"][:, 0], red["xy"][:, 1]), crs=G.graph["crs"])
             .to_crs(4326).total_bounds)
print(f"Nodos: {red['n']:,} | pares de nodos con calle: {len(red['claves']):,}")

if not MANZANAS.exists():
    print("Descargando manzanas del Censo y empleos (LODES)...")
    m = P.manzanas_censo(caja)
    m["empleos"] = m["geoid"].map(P.empleos_lodes("pa")).fillna(0)
    m.to_file(MANZANAS, driver="GeoJSON")
manzanas = gpd.read_file(MANZANAS).to_crs(G.graph["crs"])
print(f"Manzanas: {len(manzanas):,} | habitantes {manzanas['poblacion'].sum():,.0f} | "
      f"empleos {manzanas['empleos'].sum():,.0f}")

locales = F.locales_por_franja(gpd.read_file(LOCALES)).to_crs(G.graph["crs"])
if not ESTACIONAMIENTOS.exists():
    ox.features_from_place(LUGAR, tags={"amenity": ["parking"]}).to_file(ESTACIONAMIENTOS, driver="GeoJSON")
estacionamientos = gpd.read_file(ESTACIONAMIENTOS).to_crs(G.graph["crs"])
estacionamientos["plazas"] = P.plazas(estacionamientos)
print(f"Estacionamientos: {len(estacionamientos):,} ({estacionamientos['plazas'].sum():,.0f} plazas estimadas)")
paradas = P.salidas_gtfs(GTFS).to_crs(G.graph["crs"])
reales = subidas_reales()
paradas["personas_dia"] = paradas["stop_code"].astype(str).map(reales)
print(f"Paradas con subidas reales: {paradas['personas_dia'].notna().mean():.0%} "
      f"({paradas['personas_dia'].sum():,.0f} suben+bajan al dia)")


def masas(actividad_parada, con_estacionamientos=True):
    """Masas por nodo. actividad_parada: personas que suben+bajan al dia en cada parada."""
    salidas_dia = paradas[list(FRANJAS)].sum(axis=1).replace(0, np.nan)
    return {
        "estacionamientos": P.a_nodos(red, estacionamientos.geometry.representative_point(),
                                      estacionamientos["plazas"] * con_estacionamientos),
        "poblacion": P.a_nodos(red, manzanas.geometry, manzanas["poblacion"]),
        "empleos": P.a_nodos(red, manzanas.geometry, manzanas["empleos"]),
        "comercios": {f: P.a_nodos(red, locales.geometry, locales[f]) for f in FRANJAS},
        # la actividad del dia se reparte entre franjas segun los buses que pasan
        "paradas": {f: P.a_nodos(red, paradas.geometry, (actividad_parada * paradas[f] / salidas_dia).fillna(0))
                    for f in FRANJAS},
    }


# ---------------------------------------------------------------------------
# 2. Simulacion: con subidas reales (la que se guarda) y con el supuesto
#    "1 persona por bus que pasa" (lo que habria en una ciudad sin esos datos)
reales = paradas["personas_dia"].fillna(0)
variantes = {
    "simulacion (subidas reales)": (reales, True),
    "simulacion (solo horario de buses)": (paradas[list(FRANJAS)].sum(axis=1) * P.PASAJEROS_POR_SALIDA, True),
    "simulacion sin estacionamientos": (reales, False),
}
resultados = {}
for nombre, (actividad, con_estacionamientos) in variantes.items():
    print(f"\nSimulando viajes: {nombre}")
    t0 = time.time()
    por_par = P.simular(red, masas(actividad, con_estacionamientos))
    resultados[nombre] = P.por_tramo(red, por_par)
    print(f"  listo en {time.time() - t0:.0f} s")

principal = resultados["simulacion (subidas reales)"]
salida = (principal / pd.Series({f: len(h) for f, h in FRANJAS.items()})).add_prefix("peatones_")
salida = salida.reindex(tramos.index).fillna(0).round(2)
salida.index.name = "tramo_id"
salida.to_csv(SALIDA)
print(f"\nGuardado {SALIDA} (personas por hora, promedio de cada franja)")

# ---------------------------------------------------------------------------
# 3. Comparacion contra los conteos reales del centro
conteos = conteos_envision().to_crs(G.graph["crs"])
flujo = pd.read_csv(FLUJO, index_col="tramo_id")
for f in FRANJAS:
    flujo[f"gente_{f}"] = flujo[f"buses_{f}"] + 3 * flujo[f"locales_{f}"]
formula = en_horas_de_conteo(flujo.reindex(tramos.index).fillna(0), "gente_")
estimaciones = {"formula actual (buses + 3 x locales)": formula}
for nombre, tabla in resultados.items():
    por_hora = (tabla / pd.Series({f: len(h) for f, h in FRANJAS.items()})).add_prefix("p_")
    estimaciones[nombre] = en_horas_de_conteo(por_hora.reindex(tramos.index).fillna(0), "p_")

comp = conteos[["Sub Location", "nombre", "personas_dia"]].copy()
for nombre, valores in estimaciones.items():
    if nombre.startswith("formula"):  # la formula es un campo suave: el tramo mas cercano basta
        cerca = tramos.sindex.nearest(conteos.geometry, return_all=False)[1]
        comp[nombre] = valores.reindex(tramos.index[cerca]).values
    else:
        comp[nombre] = [P.alrededor(red, tramos, p.x, p.y, valores) for p in conteos.geometry]
sin_red = comp[list(resultados)[0]].isna()
print(f"\nSin red a menos de 30 m (no se pueden medir): {', '.join(comp.loc[sin_red, 'nombre'])}")
comp = comp[~sin_red]
comp.to_csv(CARPETA / "comparacion_pittsburgh.csv", index=False)
print(f"Conteos reales: {len(comp)} esquinas del centro (jueves, 7 a. m. a 8 p. m.)")
print(comp.round(0).to_string(index=False))

rng = np.random.default_rng(1)
print("\nParecido con los conteos reales (Spearman: 1 = mismo orden, 0 = nada que ver):")
for nombre in estimaciones:
    x, y = comp[nombre].values, comp["personas_dia"].values
    rho = spearmanr(x, y).statistic
    boot = [spearmanr(x[i], y[i]).statistic for i in rng.integers(0, len(x), (2000, len(x)))]
    print(f"  {nombre:40s} rho = {rho:+.2f} (IC95 {np.nanpercentile(boot, 2.5):+.2f} a {np.nanpercentile(boot, 97.5):+.2f})")
