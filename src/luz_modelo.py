"""
Modelo GLOBAL de iluminacion: la probabilidad de que una calle tenga alumbrado,
para cualquier ciudad del mundo, solo con datos que existen en todas partes:
OpenStreetMap (tipo de via, si es vereda o sendero, nombre, pavimento, densidad
de calles, distancia a una avenida) y el brillo nocturno del satelite.

Aprende de las calles que personas marcaron a mano en OSM con lit=yes / lit=no
en ciudades de todo el mundo, y se valida dejando fuera una ciudad entera cada
vez (asi se sabe cuanto acierta en una ciudad que no vio).

El satelite solo distingue zonas (~500 m); lo que separa una calle de otra es el
tipo de via y su entorno. Las faroles dibujadas en OSM y los inventarios NO se
usan aqui: son evidencia directa y se combinan despues (src/capa_luz.py).
"""
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree

import luz_satelite as LS

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
TIPOS_PEATON = {"footway", "path", "pedestrian", "steps", "cycleway", "bridleway", "track", "corridor"}
TIPOS_PRINCIPAL = {"motorway", "trunk", "primary", "secondary", "motorway_link", "trunk_link", "primary_link",
                   "secondary_link"}
PAVIMENTO = {"asphalt", "paved", "concrete", "paving_stones", "sett", "concrete:plates", "cobblestone", "bricks"}
COLUMNAS = ["tipo", "peatonal", "vereda", "cruce", "con_nombre", "pavimentada", "sin_pavimento", "acera",
            "servicio", "densidad_300", "fraccion_peatonal_300", "dist_principal", "radiancia",
            "radiancia_relativa", "saturado"]
_S = requests.Session()
_S.headers["User-Agent"] = "safe-routes-pgh/0.1 (proyecto personal)"


def overpass(consulta):
    for servidor in OVERPASS:
        for intento in range(3):
            try:
                r = _S.post(servidor, data={"data": consulta}, timeout=600)
                if r.ok and r.text.lstrip().startswith("{"):
                    return r.json()["elements"]
            except requests.RequestException:
                pass
            time.sleep(10 * (intento + 1))
    raise RuntimeError("Overpass no respondio")


def vias_osm(caja):
    """Todas las vias de la caja (oeste, sur, este, norte): su centro y etiquetas."""
    oeste, sur, este, norte = caja
    elementos = overpass(f'[out:json][timeout:600];way["highway"]({sur},{oeste},{norte},{este});out center tags;')
    filas = []
    for w in elementos:
        t, c = w.get("tags", {}), w.get("center")
        if c:
            filas.append({"osm_id": w["id"], "lon": c["lon"], "lat": c["lat"], "highway": t.get("highway"),
                          "lit": t.get("lit"), "footway": t.get("footway"), "name": t.get("name"),
                          "surface": t.get("surface"), "sidewalk": t.get("sidewalk"), "service": t.get("service")})
    return pd.DataFrame(filas)


def caracteristicas(vias, brillo):
    """Caracteristicas universales de cada via (vias: DataFrame de vias_osm;
    brillo: dict de luz_satelite.brillo para la misma caja)."""
    x = pd.DataFrame(index=vias.index)
    h = vias["highway"].fillna("")
    x["tipo"] = h
    x["peatonal"] = h.isin(TIPOS_PEATON).astype(int)
    x["vereda"] = (vias["footway"] == "sidewalk").astype(int)
    x["cruce"] = (vias["footway"] == "crossing").astype(int)
    x["con_nombre"] = vias["name"].notna().astype(int)
    x["pavimentada"] = vias["surface"].isin(PAVIMENTO).astype(int)
    x["sin_pavimento"] = (vias["surface"].notna() & ~vias["surface"].isin(PAVIMENTO)).astype(int)
    x["acera"] = vias["sidewalk"].isin(["both", "left", "right", "separate", "yes"]).astype(int)
    x["servicio"] = vias["service"].notna().astype(int)
    # Entorno: densidad de vias y de caminos peatonales a 300 m, distancia a una avenida
    pts = gpd.GeoSeries(gpd.points_from_xy(vias["lon"], vias["lat"]), crs=4326)
    xy = np.column_stack([pts.to_crs(pts.estimate_utm_crs()).x, pts.to_crs(pts.estimate_utm_crs()).y])
    arbol = cKDTree(xy)
    vecinos = arbol.query_ball_point(xy, 300)
    peaton = x["peatonal"].to_numpy()
    x["densidad_300"] = [len(v) for v in vecinos]
    x["fraccion_peatonal_300"] = [peaton[v].mean() for v in vecinos]
    principal = h.isin(TIPOS_PRINCIPAL).to_numpy()
    if principal.any():
        d, _ = cKDTree(xy[principal]).query(xy, distance_upper_bound=2000)
        x["dist_principal"] = np.minimum(d, 2000)
    else:
        x["dist_principal"] = 2000.0
    # Satelite (zona de ~500 m) y relativo a la mediana de toda la caja
    rad = LS.valor_en(brillo, vias["lon"].to_numpy(), vias["lat"].to_numpy())
    x["radiancia"] = rad
    x["radiancia_relativa"] = rad / np.nanmedian(brillo["normal"])
    x["saturado"] = (rad >= LS.SATURA).astype(int)
    return x


def preparar(x, categorias=None):
    """Tipos de dato para LightGBM (el tipo de via como categoria fija)."""
    x = x[COLUMNAS].copy()
    x["tipo"] = pd.Categorical(x["tipo"], categories=categorias) if categorias is not None \
        else x["tipo"].astype("category")
    return x
