"""
Caracteristicas UNIVERSALES de cada tramo peatonal.

Todo sale de OpenStreetMap (calles, comercios, parques, paradas de bus), asi que
se puede calcular en CUALQUIER ciudad: Pittsburgh, Arequipa, etc. Nada depende
de datos policiales, horarios GTFS ni reportes 311 (que no existen en todas partes).

Se usan en el modelo de transferencia (paso 9): aprender en una ciudad con
datos oficiales de delitos y estimar el riesgo donde no los hay.
"""
import re

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd

from comun import id_tramo

TIPOS_PRINCIPALES = {"trunk", "primary", "secondary", "trunk_link", "primary_link", "secondary_link"}
TIPOS_SENDERO = {"path", "track", "steps", "bridleway", "cycleway"}
TIPOS_CALLE = {"trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "living_street",
               "service", "pedestrian", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
DIST_CALLE = 25        # m: un camino sin calle a esta distancia es un sendero
DENTRO_PARQUE = 30     # m hacia adentro del borde de un parque
ALCANCE = 400          # m caminando para medir que tan conectada esta la zona

COLUMNAS = ["tipo", "largo", "es_sendero", "en_parque", "dist_principal", "locales_150", "locales_400",
            "paradas_300", "intersecciones_300", "alcance_400"]


def tipo_principal(highway):
    """Tipo de via de un tramo (si hay varios, el primero)."""
    tipos = re.findall(r"[a-z_]+", str(highway))
    return tipos[0] if tipos else "otro"


def contar_cerca(medios, puntos, radio):
    """Cuantos puntos hay a menos de 'radio' m del punto medio de cada tramo."""
    if puntos.empty:
        return pd.Series(0, index=medios.index)
    zonas = gpd.GeoDataFrame(geometry=medios.buffer(radio), index=medios.index, crs=medios.crs)
    pares = gpd.sjoin(zonas, puntos[["geometry"]], predicate="contains")
    return pares.groupby(level=0).size().reindex(medios.index).fillna(0).astype(int)


def calcular(G, calles, locales, parques, paradas):
    """
    G: red peatonal PROYECTADA (metros). calles, locales, parques, paradas:
    GeoDataFrames de OSM en cualquier CRS (se pasan al de G).
    Devuelve un DataFrame con una fila por tramo (tramo_id) y las COLUMNAS.
    """
    crs = G.graph["crs"]
    aristas = ox.graph_to_gdfs(G, nodes=False).reset_index()
    aristas["tramo_id"] = [id_tramo(u, v, o, largo) for u, v, o, largo in
                           zip(aristas["u"], aristas["v"], aristas["osmid"], aristas["length"])]
    tramos = aristas.drop_duplicates("tramo_id").set_index("tramo_id")
    medios = gpd.GeoSeries(tramos.geometry.interpolate(0.5, normalized=True), index=tramos.index, crs=crs)
    medios_gdf = gpd.GeoDataFrame(geometry=medios, crs=crs)
    x = pd.DataFrame(index=tramos.index)

    # Tipo de via y largo
    x["tipo"] = tramos["highway"].apply(tipo_principal)
    x["largo"] = tramos["length"].round(1)

    # Sendero: tipo sendero, o camino que no es calle y no tiene calle a DIST_CALLE m
    calles = calles.to_crs(crs)
    tipos_tramo = tramos["highway"].apply(lambda h: set(re.findall(r"[a-z_]+", str(h))))
    es_calle = tipos_tramo.apply(lambda t: bool(t & TIPOS_CALLE))
    cerca = medios_gdf[~es_calle.values].sjoin_nearest(calles[["geometry"]], max_distance=DIST_CALLE).index
    x["es_sendero"] = ~es_calle & (tipos_tramo.apply(lambda t: bool(t & TIPOS_SENDERO)) | ~x.index.isin(cerca))

    # Interior de parques y cementerios
    interior = parques.to_crs(crs).buffer(-DENTRO_PARQUE)
    interior = gpd.GeoDataFrame(geometry=interior[~interior.is_empty], crs=crs)
    x["en_parque"] = x.index.isin(gpd.sjoin(medios_gdf, interior, predicate="within").index)

    # Distancia a la avenida principal mas cercana (tope 1000 m)
    principales = calles[calles["highway"].apply(lambda h: tipo_principal(h) in TIPOS_PRINCIPALES)]
    if principales.empty:
        x["dist_principal"] = 1000.0
    else:
        d = medios_gdf.sjoin_nearest(principales[["geometry"]], distance_col="d", max_distance=1000)
        x["dist_principal"] = d.loc[~d.index.duplicated(), "d"].reindex(x.index).fillna(1000).round(0)

    # Comercios y paradas de bus cerca
    locales = locales.to_crs(crs)
    locales = locales.set_geometry(locales.geometry.representative_point())
    x["locales_150"] = contar_cerca(medios, locales, 150)
    x["locales_400"] = contar_cerca(medios, locales, 400)
    x["paradas_300"] = contar_cerca(medios, paradas.to_crs(crs), 300)

    # Intersecciones y conectividad medidas SOLO sobre las calles (sin veredas ni
    # senderos): en algunas ciudades el mapa dibuja cada vereda aparte (p.ej. el
    # campus de Penn State) y cada cruce de veredas contaria como una interseccion.
    # Asi estas medidas no dependen de cuan detallado esta el mapa.
    red = nx.Graph()
    for u, v, largo in zip(tramos.loc[es_calle, "u"], tramos.loc[es_calle, "v"], tramos.loc[es_calle, "length"]):
        if not red.has_edge(u, v) or red[u][v]["length"] > largo:
            red.add_edge(u, v, length=largo)
    nodos = ox.graph_to_gdfs(G, edges=False)
    # Intersecciones de calles (3 o mas calles) a 300 m
    cruces = nodos.loc[[n for n in red.nodes if red.degree(n) >= 3]]
    x["intersecciones_300"] = contar_cerca(medios, cruces, 300)
    # Conectividad: cuantas intersecciones se alcanzan por la calle en ALCANCE m.
    # Los tramos que no son calle (veredas, senderos) toman el valor de la calle mas cercana.
    alcance = {n: len(nx.single_source_dijkstra_path_length(red, n, cutoff=ALCANCE, weight="length"))
               for n in red.nodes}
    por_calle = pd.Series([max(alcance.get(u, 0), alcance.get(v, 0)) for u, v in
                           zip(tramos.loc[es_calle, "u"], tramos.loc[es_calle, "v"])], index=tramos.index[es_calle])
    x["alcance_400"] = por_calle.reindex(x.index)
    sin = x["alcance_400"].isna()
    if sin.any() and len(por_calle):
        cerca = medios_gdf[sin.values].sjoin_nearest(
            gpd.GeoDataFrame({"alcance": por_calle.values}, geometry=medios[es_calle].values, crs=crs),
            max_distance=ALCANCE)
        x.loc[sin, "alcance_400"] = cerca.loc[~cerca.index.duplicated(), "alcance"].reindex(x.index[sin])
    x["alcance_400"] = x["alcance_400"].fillna(0).astype(int)

    # Punto medio (en metros): no es una caracteristica del modelo, sirve para
    # agrupar los tramos en celdas al validar
    x["cx"], x["cy"] = medios.x.round(1), medios.y.round(1)
    return x[COLUMNAS + ["cx", "cy"]]


def preparar_para_modelo(x, categorias=None):
    """Tipos de dato para LightGBM: 'tipo' como categoria (con las mismas categorias
    que en el entrenamiento, para poder aplicar el modelo en otra ciudad)."""
    x = x.copy()
    x["es_sendero"] = x["es_sendero"].astype(int)
    x["en_parque"] = x["en_parque"].astype(int)
    x["tipo"] = pd.Categorical(x["tipo"], categories=categorias) if categorias is not None \
        else x["tipo"].astype("category")
    return x
