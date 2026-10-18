"""
Multiciudad, paso 3: datos PUBLICOS de cada ciudad (desarrollo y examen). Nada
de delitos: son los datos que existirian aunque no conocieramos ningun delito
(investigacion/reglas_de_datos.md, seccion 4).

Para cada ciudad, en data/public_features/<ciudad>/:
    limite.geojson         contorno de la ciudad (Nominatim)
    osm.pkl                lo leido del mapa del estado (Geofabrik; src/osm_local.py)
    red_peatonal.graphml   red caminable dentro del contorno (mismo filtro que OSMnx)
    osm.gpkg               capas: calles, parques, paradas, lugares (comercios,
                           estacionamientos, instituciones)
    manzanas.gpkg          manzanas del Censo 2020 con habitantes y empleos (LODES 2023)
    gtfs_<n>.zip           horarios del operador urbano principal

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/03_datos_publicos.py [ciudad ...]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401

import geopandas as gpd  # noqa: E402
import osmnx as ox  # noqa: E402
import requests  # noqa: E402

import osm_local as OL  # noqa: E402
import peatones as P  # noqa: E402
from ciudades import PUBLICOS, TODAS, carpeta_publica  # noqa: E402

ox.settings.http_user_agent = "safe-routes-pgh/0.1 (proyecto personal)"
MAPAS = Path("data/public_features/osm")
MARGEN = 1000   # m alrededor del contorno para leer el mapa y las manzanas


def paso(texto):
    print(f"  {texto}...", flush=True)
    return time.time()


ciudades = sys.argv[1:] or list(TODAS)
for ciudad in ciudades:
    cfg, pub = TODAS[ciudad], PUBLICOS[ciudad]
    out = carpeta_publica(ciudad)
    out.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {cfg['nombre']} ({cfg['grupo']})")

    if not (out / "limite.geojson").exists():
        ox.geocode_to_gdf(cfg["lugar"])[["geometry"]].to_file(out / "limite.geojson", driver="GeoJSON")
    limite = gpd.read_file(out / "limite.geojson")
    poligono = limite.geometry.iloc[0]
    caja = tuple(limite.to_crs(cfg["crs"]).buffer(MARGEN).to_crs(4326).total_bounds)
    print(f"  contorno: {limite.to_crs(cfg['crs']).area.iloc[0] / 1e6:.0f} km2")

    t = paso("leyendo el mapa del estado")
    d = OL.leer_ciudad(MAPAS / f"{pub['estado']}-latest.osm.pbf", caja, out / "osm.pkl")
    print(f"    {time.time() - t:.0f} s | calles {len(d['calles']):,} | lugares {len(d['lugares']):,} | "
          f"paradas {len(d['paradas']):,} | parques {len(d['areas']):,}")

    if not (out / "red_peatonal.graphml").exists():
        t = paso("armando la red caminable")
        G = OL.red_peatonal(d, poligono)
        ox.save_graphml(G, out / "red_peatonal.graphml")
        km = sum(x["length"] for *_, x in G.edges(data=True)) / 2000
        print(f"    {time.time() - t:.0f} s | {len(G):,} nodos, {km:,.0f} km")

    if not (out / "osm.gpkg").exists():
        OL.calles_gdf(d).to_file(out / "osm.gpkg", layer="calles", driver="GPKG")
        OL.parques_gdf(d).to_file(out / "osm.gpkg", layer="parques", driver="GPKG")
        OL.paradas_gdf(d).to_file(out / "osm.gpkg", layer="paradas", driver="GPKG")
        lugares = OL.lugares(d, poligono.buffer(0.01))
        columnas = [c for c in ["amenity", "shop", "name", "opening_hours", "parking", "capacity",
                                "building:levels", "access", "leisure"] if c in lugares]
        lugares[columnas + ["geometry"]].to_file(out / "osm.gpkg", layer="lugares", driver="GPKG")

    if not (out / "manzanas.gpkg").exists():
        t = paso("manzanas del Censo y empleos (LODES)")
        m = P.manzanas_censo(caja)
        m["empleos"] = m["geoid"].map(P.empleos_lodes(pub["lodes"])).fillna(0)
        m.to_file(out / "manzanas.gpkg", driver="GPKG")
        print(f"    {time.time() - t:.0f} s | {len(m):,} manzanas, {m['poblacion'].sum():,.0f} habitantes, "
              f"{m['empleos'].sum():,.0f} empleos")

    for i, url in enumerate(pub["gtfs"]):
        archivo = out / f"gtfs_{i}.zip"
        if not archivo.exists():
            r = requests.get(url, headers={"User-Agent": "safe-routes-pgh/0.1"}, timeout=300)
            r.raise_for_status()
            archivo.write_bytes(r.content)
    print(f"  horarios: {len(pub['gtfs'])} archivo(s)")
