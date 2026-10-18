"""
Multiciudad, paso 5: rasgos PUBLICOS de cada tramo de calle, para TODAS las
ciudades (desarrollo y examen). No usa delitos: es lo que la formula puede ver
en cualquier ciudad (investigacion/reglas_de_datos.md, seccion 4).

Por tramo (una fila por tramo_id):
    forma        tipo, largo, es_sendero, en_parque, dist_principal, locales_150,
                 locales_400, paradas_300, intersecciones_300, alcance_400
                 (src/caracteristicas.py, igual que en Pittsburgh)
    actividad    buses_<franja> (buses por hora a 150 m), locales_<franja> (locales
                 abiertos a 150 m), bares_<franja> (bares y discotecas abiertos a 150 m)
    gente        habitantes_400, empleos_400 (manzanas del Censo a 400 m del tramo),
                 peatones_<franja> (viajes a pie simulados, src/peatones.py; las paradas
                 usan solo el horario: 1 persona por bus que pasa, igual en todas)
    luz          radiancia (satelite VIIRS: mediana de NOCHES_LUZ noches hasta
                 FIN_LUZ, el fin del periodo "pasado")
Excluido por las reglas: raza, etnia, ingreso, pobreza.

Entradas: data/public_features/<ciudad>/ (paso 3)
Salida:   data/public_features/<ciudad>/tramos.csv

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/05_rasgos_publicos.py [ciudad ...]
"""
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import osmnx as ox  # noqa: E402
import pandas as pd  # noqa: E402

import caracteristicas as C  # noqa: E402
import flujo as F  # noqa: E402
import luz_satelite as LS  # noqa: E402
import peatones as P  # noqa: E402
from ciudades import TODAS, carpeta_publica  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

RADIO_GENTE = 400
TIPOS_BAR = {"bar", "pub", "nightclub"}
FIN_LUZ = date(2025, 8, 31)
NOCHES_LUZ = 30


def paso(texto):
    print(f"  {texto}...", flush=True)
    return time.time()


def main():
    for ciudad in sys.argv[1:] or list(TODAS):
        cfg, pub = TODAS[ciudad], carpeta_publica(ciudad)
        salida = pub / "tramos.csv"
        if salida.exists():
            print(f"{cfg['nombre']}: ya estaba")
            continue
        print(f"\n=== {cfg['nombre']}")
        G = ox.project_graph(ox.load_graphml(pub / "red_peatonal.graphml"), to_crs=cfg["crs"])
        tramos, medios = F.tramos_y_medios(G)
        leer = lambda capa: gpd.read_file(pub / "osm.gpkg", layer=capa).to_crs(cfg["crs"])
        calles, parques, paradas_osm, lugares = leer("calles"), leer("parques"), leer("paradas"), leer("lugares")
        es_local = lugares["amenity"].isin(F.TIPOS_LOCAL) | (lugares["shop"].notna() if "shop" in lugares else False)
        locales = F.locales_por_franja(F.locales_de_osm(lugares[es_local]))
        estacionamientos = lugares[lugares["amenity"] == "parking"].copy()
        estacionamientos["plazas"] = P.plazas(estacionamientos)

        t = paso("forma de la calle")
        x = C.calcular(G, calles, locales, parques, paradas_osm)
        print(f"    {time.time() - t:.0f} s | {len(x):,} tramos")

        t = paso("actividad por franja (buses, locales, bares)")
        paradas = pd.concat([F.buses_gtfs(z) for z in sorted(pub.glob("gtfs_*.zip"))], ignore_index=True)
        paradas = gpd.GeoDataFrame(paradas, geometry="geometry", crs=4326).to_crs(cfg["crs"])
        x = x.join(F.aporte_cercano(paradas, list(FRANJAS), F.RADIO_FLUJO, medios).add_prefix("buses_"))
        x = x.join(F.aporte_cercano(locales, list(FRANJAS), F.RADIO_FLUJO, medios).add_prefix("locales_"))
        bares = locales[locales["tipo"].isin(TIPOS_BAR)]
        if len(bares):
            x = x.join(F.aporte_cercano(bares, list(FRANJAS), F.RADIO_FLUJO, medios).add_prefix("bares_"))
        else:
            x = x.assign(**{f"bares_{f}": 0.0 for f in FRANJAS})
        print(f"    {time.time() - t:.0f} s | {len(paradas):,} paradas con horario, {len(locales):,} locales, {len(bares):,} bares")

        t = paso("habitantes y empleos cerca")
        manzanas = gpd.read_file(pub / "manzanas.gpkg").to_crs(cfg["crs"])
        cerca = gpd.sjoin(gpd.GeoDataFrame(geometry=medios.buffer(RADIO_GENTE), index=medios.index),
                          manzanas[["poblacion", "empleos", "geometry"]], predicate="contains")
        suma = cerca.groupby(level=0)[["poblacion", "empleos"]].sum()
        x["habitantes_400"] = suma["poblacion"].reindex(x.index).fillna(0)
        x["empleos_400"] = suma["empleos"].reindex(x.index).fillna(0)
        print(f"    {time.time() - t:.0f} s")

        t = paso("peatones simulados (por cuadrados de 2 km en paralelo: mismo resultado, menos memoria)")
        salidas = pd.concat([P.salidas_gtfs(z) for z in sorted(pub.glob("gtfs_*.zip"))], ignore_index=True)
        salidas = gpd.GeoDataFrame(salidas, geometry="geometry", crs=4326).to_crs(cfg["crs"])
        fuentes = {
            "poblacion": (manzanas.geometry, manzanas["poblacion"]),
            "empleos": (manzanas.geometry, manzanas["empleos"]),
            "estacionamientos": (estacionamientos.geometry.representative_point(), estacionamientos["plazas"]),
            "comercios": {f: (locales.geometry, locales[f]) for f in FRANJAS},
            "paradas": {f: (salidas.geometry, salidas[f] * P.PASAJEROS_POR_SALIDA) for f in FRANJAS},
        }
        por_tramo = P.simular_por_teselas(G, fuentes, guardar=pub / "peatones_cuadrados")
        horas = pd.Series({f: len(h) for f, h in FRANJAS.items()})
        x = x.join((por_tramo / horas).add_prefix("peatones_"))
        print(f"    {time.time() - t:.0f} s")

        t = paso("luz nocturna (satelite)")
        caja = tuple(gpd.GeoSeries(medios.geometry, crs=cfg["crs"]).to_crs(4326).total_bounds)
        brillo = LS.brillo(caja, hasta=FIN_LUZ, noches=NOCHES_LUZ)
        lonlat = gpd.GeoSeries(medios.geometry, crs=cfg["crs"]).to_crs(4326)
        x["radiancia"] = np.round(LS.valor_en(brillo, lonlat.x.values, lonlat.y.values), 2)
        print(f"    {time.time() - t:.0f} s | {brillo['noches']} imagenes")

        x = x.fillna({c: 0 for c in x.columns if c.startswith(("buses_", "locales_", "bares_", "peatones_"))})
        x.index.name = "tramo_id"
        x.to_csv(salida)
        print(f"  guardado {salida}: {len(x):,} tramos, {x.shape[1]} columnas")


if __name__ == "__main__":
    main()
