"""
Preparacion COMUN de los delitos de cualquier ciudad (desarrollo y examen), para que
el examen use exactamente el mismo procedimiento que el desarrollo:

    normalizar(d, ciudad, con_detalle)   pasos 2: periodo, hora, clases, exclusiones basicas
    asignar(d, G, limite, lugares, crs)  paso 4: fuera de la ciudad, tramo mas cercano,
                                         lejos de la calle, junto a instituciones
Las reglas: investigacion/reglas_de_datos.md, seccion 2.
"""
import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd

import categorias as K
from comun import id_tramo

DESDE, HASTA = "2024-01-01", "2026-08-31"
MOTIVOS = ["ninguno", "sin_ubicacion", "sin_fecha", "sexual", "fuera_de_ciudad", "lejos_de_calle", "lugar_cerrado"]
DISTANCIA_MAX = 50
DISTANCIA_LUGAR = 30
TIPOS_LUGAR = ["prison", "hospital", "police", "social_facility"]
COLUMNAS = ["ciudad", "id", "fecha", "hora", "hora_tipo", "hora_desconocida", "lat", "lon", "original",
            "codigo", "clase_nucleo", "categoria_amplia", "bolsa", "motivo_exclusion"]


def normalizar(d, ciudad, con_detalle):
    """d: DataFrame con id, momento (fecha y hora local), hora_tipo, lat, lon, original, codigo.
    Devuelve el formato comun (COLUMNAS), solo el periodo del estudio."""
    d = d.copy()
    d.insert(0, "ciudad", ciudad)
    d["lat"], d["lon"] = pd.to_numeric(d["lat"], errors="coerce"), pd.to_numeric(d["lon"], errors="coerce")
    d = d[(d["momento"] >= DESDE) & (d["momento"] < pd.Timestamp(HASTA) + pd.Timedelta(days=1)) | d["momento"].isna()]
    d["fecha"] = d["momento"].dt.strftime("%Y-%m-%d")
    d["hora"] = d["momento"].dt.hour
    d["hora_desconocida"] = (d["momento"].dt.hour == 0) & (d["momento"].dt.minute == 0)
    clases = d["codigo"].map(K.clasificar)
    d["clase_nucleo"], d["categoria_amplia"], d["bolsa"] = zip(*clases) if len(d) else ([], [], [])
    if not con_detalle:
        d["categoria_amplia"] = None   # la ciudad no permite separar las categorias amplias
    ubicacion_ok = d["lat"].between(20, 60) & d["lon"].between(-130, -60)
    d["motivo_exclusion"] = np.select([d["codigo"] == K.SEXUAL, d["momento"].isna(), ~ubicacion_ok],
                                      ["sexual", "sin_fecha", "sin_ubicacion"], "ninguno")
    d.loc[d["motivo_exclusion"] == "sexual", ["clase_nucleo", "categoria_amplia", "bolsa"]] = None
    assert set(d["motivo_exclusion"]) <= set(MOTIVOS)
    assert set(d["clase_nucleo"].dropna()) <= set(K.CLASES_NUCLEO)
    assert set(d["categoria_amplia"].dropna()) <= set(K.CATEGORIAS_AMPLIAS)
    assert set(d["bolsa"].dropna()) <= set(K.BOLSAS)
    return d[COLUMNAS]


def asignar(d, G, limite, lugares, crs):
    """Ubica cada delito en su tramo (red G proyectada en crs) y aplica las exclusiones
    del paso 4. limite: poligono de la ciudad (crs). lugares: capa 'lugares' de OSM."""
    d = d.copy()
    d["tramo_id"], d["distancia_m"] = None, np.nan
    libres = d["motivo_exclusion"] == "ninguno"
    puntos = gpd.GeoSeries(gpd.points_from_xy(d.loc[libres, "lon"], d.loc[libres, "lat"]), index=d.index[libres],
                           crs=4326).to_crs(crs)
    # 1. Fuera de la ciudad
    afuera = ~puntos.within(limite)
    d.loc[afuera[afuera].index, "motivo_exclusion"] = "fuera_de_ciudad"
    puntos = puntos[~afuera]
    # 2. Tramo mas cercano y distancia
    aristas, dist = ox.distance.nearest_edges(G, X=puntos.x.values, Y=puntos.y.values, return_dist=True)
    d.loc[puntos.index, "tramo_id"] = [id_tramo(u, v, G.edges[u, v, k]["osmid"], G.edges[u, v, k]["length"])
                                       for u, v, k in aristas]
    d.loc[puntos.index, "distancia_m"] = np.round(dist, 1)
    lejos = puntos.index[np.asarray(dist) > DISTANCIA_MAX]
    d.loc[lejos, "motivo_exclusion"] = "lejos_de_calle"
    puntos = puntos.drop(lejos)
    # 3. Junto a instituciones
    lugares = lugares[lugares["amenity"].isin(TIPOS_LUGAR)].to_crs(crs)
    if len(lugares):
        cerca = gpd.sjoin_nearest(gpd.GeoDataFrame(geometry=puntos), lugares[["geometry"]],
                                  max_distance=DISTANCIA_LUGAR)
        d.loc[cerca.index.unique(), "motivo_exclusion"] = "lugar_cerrado"
    assert set(d["motivo_exclusion"]) <= set(MOTIVOS)
    return d
