"""
Multiciudad, paso 6: rasgos de delitos por tramo de las ciudades de DESARROLLO
(src/multiciudad/rasgos_delitos.py): niveles A, B, C, por zona y totales (del
pasado) y lo que se califica (del futuro).

Entradas: data/<grupo>/<ciudad>/delitos_tramo.csv (paso 4), data/public_features/<ciudad>/ (paso 3)
Salida:   data/<grupo>/<ciudad>/mapa_delitos.csv

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/06_mapas_delitos.py [ciudad ...]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401

import geopandas as gpd  # noqa: E402
import osmnx as ox  # noqa: E402
import pandas as pd  # noqa: E402

import categorias as K  # noqa: E402
import flujo as F  # noqa: E402
import rasgos_delitos as RD  # noqa: E402
from ciudades import DESARROLLO, carpeta, carpeta_publica  # noqa: E402

for ciudad in sys.argv[1:] or list(DESARROLLO):
    cfg, pub = DESARROLLO[ciudad], carpeta_publica(ciudad)
    salida = carpeta(ciudad) / "mapa_delitos.csv"
    if salida.exists():
        print(f"{cfg['nombre']}: ya estaba")
        continue
    t = time.time()
    print(f"{cfg['nombre']}...", flush=True)
    G = ox.project_graph(ox.load_graphml(pub / "red_peatonal.graphml"), to_crs=cfg["crs"])
    delitos = pd.read_csv(carpeta(ciudad) / "delitos_tramo.csv", dtype={"codigo": str, "clase_nucleo": str,
                                                                        "categoria_amplia": str, "bolsa": str})
    delitos = delitos[delitos["motivo_exclusion"] == "ninguno"]
    manzanas = gpd.read_file(pub / "manzanas.gpkg").to_crs(cfg["crs"])
    _, medios = F.tramos_y_medios(G)
    limite = gpd.read_file(pub / "limite.geojson").to_crs(cfg["crs"]).geometry.iloc[0]
    adentro = manzanas[manzanas.within(limite)]   # la tasa de la ciudad: solo su poblacion
    cercana = gpd.sjoin_nearest(medios, manzanas[["geoid", "geometry"]])
    tramo_manzana = cercana.loc[~cercana.index.duplicated(), "geoid"]
    mapa = RD.construir(G, delitos, adentro, tramo_manzana, ciudad in K.CON_DETALLE)
    mapa.to_csv(salida)
    fut = mapa[[c for c in mapa if c.startswith("fut_")]].sum()
    print(f"  {time.time() - t:.0f} s | {len(mapa):,} tramos, {mapa.shape[1]} columnas | "
          f"nucleo futuro: {fut.sum():,.0f} | tasa del pasado: {mapa['t_tasa'].iloc[0]:.2f} por 1,000 hab/anio")
