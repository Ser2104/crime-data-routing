"""
Multiciudad, paso 5b: rasgos de LUGARES y USO DEL SUELO por tramo, para TODAS las
ciudades (reglas de datos, version 3). Solo datos publicos: nada de delitos.

Por tramo (desde su punto medio):
    escuelas_400, universidades_400, hospitales_400, comisarias_800, gasolineras_150,
    licorerias_150, cajeros_150, estaciones_400, estadios_800     cuantos hay a esa distancia
    paradas_gtfs_300      paradas con horario oficial a 300 m (reemplaza a las de OpenStreetMap)
    edificios_200         edificios a 200 m
    cobertura_edificios   parte del circulo de 200 m cubierta por edificios (0 a 1)
    uso_suelo             comercial | industrial | residencial | ninguno (donde cae el punto medio)
Prohibidos por las reglas (indican sobre todo pobreza): casas de empeno, prestamos
rapidos, albergues y centros de servicios sociales.

Entradas: data/public_features/<ciudad>/ (pasos 3 y 5), mapas de los estados
Salida:   data/public_features/<ciudad>/tramos_lugares.csv

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/05b_rasgos_lugares.py [ciudad ...]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import osmnx as ox  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.signal import fftconvolve  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

import flujo as F  # noqa: E402
import osm_local as OL  # noqa: E402
from ciudades import PUBLICOS, TODAS, carpeta_publica  # noqa: E402

MAPAS = Path("data/public_features/osm")
MARGEN = 1000
CELDA = 25           # m: grilla para los edificios
RADIO_EDIFICIOS = 200
# (nombre, condicion sobre los lugares de OpenStreetMap, radio en m)
LUGARES = [
    ("escuelas", lambda l: l["amenity"].isin(["school", "kindergarten"]), 400),
    ("universidades", lambda l: l["amenity"].isin(["university", "college"]), 400),
    ("hospitales", lambda l: l["amenity"] == "hospital", 400),   # sin clinicas: Tempe dibujo todas
    ("comisarias", lambda l: l["amenity"] == "police", 800),
    ("gasolineras", lambda l: l["amenity"] == "fuel", 150),
    ("licorerias", lambda l: l["shop"] == "alcohol", 150),
    ("cajeros", lambda l: l["amenity"] == "atm", 150),
]
USOS = ["comercial", "industrial", "residencial"]   # si un punto cae en varios, gana el primero


def contar(medios_xy, puntos_xy, radio):
    if len(puntos_xy) == 0:
        return np.zeros(len(medios_xy), int)
    return cKDTree(puntos_xy).query_ball_point(medios_xy, radio, return_length=True)


def edificios_cerca(medios_xy, edif_xy, areas):
    """Cantidad y area de edificios a RADIO_EDIFICIOS m de cada punto (grilla + convolucion)."""
    if len(edif_xy) == 0:
        return np.zeros(len(medios_xy)), np.zeros(len(medios_xy))
    x0, y0 = np.minimum(medios_xy.min(0), edif_xy.min(0)) - RADIO_EDIFICIOS
    x1, y1 = np.maximum(medios_xy.max(0), edif_xy.max(0)) + RADIO_EDIFICIOS
    nx, ny = int((x1 - x0) // CELDA) + 1, int((y1 - y0) // CELDA) + 1
    ix = ((edif_xy[:, 0] - x0) // CELDA).astype(int)
    iy = ((edif_xy[:, 1] - y0) // CELDA).astype(int)
    cuenta, area = np.zeros((nx, ny)), np.zeros((nx, ny))
    np.add.at(cuenta, (ix, iy), 1)
    np.add.at(area, (ix, iy), areas)
    r = int(np.ceil(RADIO_EDIFICIOS / CELDA))
    gx, gy = np.mgrid[-r:r + 1, -r:r + 1]
    disco = ((gx ** 2 + gy ** 2) * CELDA ** 2 <= RADIO_EDIFICIOS ** 2).astype(float)
    cuenta_c = fftconvolve(cuenta, disco, mode="same")
    area_c = fftconvolve(area, disco, mode="same")
    mx = ((medios_xy[:, 0] - x0) // CELDA).astype(int)
    my = ((medios_xy[:, 1] - y0) // CELDA).astype(int)
    circulo = np.pi * RADIO_EDIFICIOS ** 2
    return np.round(np.maximum(cuenta_c[mx, my], 0)), np.clip(area_c[mx, my] / circulo, 0, 1)


def main():
    for ciudad in sys.argv[1:] or list(TODAS):
        cfg, pub = TODAS[ciudad], carpeta_publica(ciudad)
        salida = pub / "tramos_lugares.csv"
        if salida.exists():
            print(f"{cfg['nombre']}: ya estaba")
            continue
        t = time.time()
        print(f"=== {cfg['nombre']}", flush=True)
        crs = cfg["crs"]
        G = ox.project_graph(ox.load_graphml(pub / "red_peatonal.graphml"), to_crs=crs)
        tramos, medios = F.tramos_y_medios(G)
        mxy = np.column_stack([medios.geometry.x, medios.geometry.y])
        x = pd.DataFrame(index=tramos.index)
        a_xy = lambda g: np.column_stack([g.x, g.y]) if len(g) else np.zeros((0, 2))

        lugares = gpd.read_file(pub / "osm.gpkg", layer="lugares").to_crs(crs)
        for col in ["amenity", "shop"]:
            if col not in lugares:
                lugares[col] = None
        puntos = lugares.geometry.representative_point()
        for nombre, condicion, radio in LUGARES:
            x[f"{nombre}_{radio}"] = contar(mxy, a_xy(puntos[condicion(lugares).fillna(False).values]), radio)

        limite = gpd.read_file(pub / "limite.geojson")
        caja = tuple(limite.to_crs(crs).buffer(MARGEN).to_crs(4326).total_bounds)
        extra = OL.leer_extra(MAPAS / f"{PUBLICOS[ciudad]['estado']}-latest.osm.pbf", caja, pub / "osm_extra.pkl")
        aproyectado = lambda geoms: gpd.GeoSeries(geoms, crs=4326).to_crs(crs)
        x["estaciones_400"] = contar(mxy, a_xy(aproyectado(extra["estaciones"])), 400)
        x["estadios_800"] = contar(mxy, a_xy(aproyectado(extra["estadios"])), 800)

        paradas = pd.concat([F.buses_gtfs(z) for z in sorted(pub.glob("gtfs_*.zip"))], ignore_index=True)
        paradas = gpd.GeoDataFrame(paradas, geometry="geometry", crs=4326).to_crs(crs)
        x["paradas_gtfs_300"] = contar(mxy, a_xy(paradas.geometry), 300)

        if extra["edificios"]:
            e = np.array(extra["edificios"])
            exy = a_xy(aproyectado(gpd.points_from_xy(e[:, 0], e[:, 1])))
            x["edificios_200"], x["cobertura_edificios"] = edificios_cerca(mxy, exy, e[:, 2])
        else:
            x["edificios_200"], x["cobertura_edificios"] = 0.0, 0.0
        x["cobertura_edificios"] = x["cobertura_edificios"].round(3)

        x["uso_suelo"] = "ninguno"
        if extra["usos"]:
            usos = gpd.GeoDataFrame({"uso": [u for u, _ in extra["usos"]]},
                                    geometry=[g for _, g in extra["usos"]], crs=4326).to_crs(crs)
            cae = gpd.sjoin(gpd.GeoDataFrame(geometry=medios.geometry, index=medios.index), usos, predicate="within")
            prioridad = cae["uso"].map({u: i for i, u in enumerate(USOS)})
            elegido = cae.assign(p=prioridad).sort_values("p").groupby(level=0)["uso"].first()
            x.loc[elegido.index, "uso_suelo"] = elegido
        x.index.name = "tramo_id"
        x.to_csv(salida)
        print(f"  {time.time() - t:.0f} s | {len(x):,} tramos | edificios {len(extra['edificios']):,} | "
              f"estaciones {len(extra['estaciones'])} | uso del suelo: "
              f"{x['uso_suelo'].value_counts(normalize=True).round(2).to_dict()}", flush=True)


if __name__ == "__main__":
    main()
