"""
Flujo de personas y aislamiento por tramo: funciones comunes a todas las
ciudades (las usan el paso 4 de Pittsburgh y el de Arequipa).

Senales de que hay gente, por franja horaria:
    - buses por hora en paradas cercanas
    - locales abiertos cercanos (bares, restaurantes, tiendas...)
Senales de posible aislamiento:
    - es_sendero: senderos, escaleras o caminos sin una calle cerca
    - en_parque: interior de parques y cementerios
"""
import re
import zipfile
from datetime import timedelta

import geopandas as gpd
import osmnx as ox
import pandas as pd

from comun import id_tramo
from riesgo_pie import FRANJAS

RADIO_FLUJO = 150      # metros: paradas y locales que "aportan gente" a un tramo
DIST_CALLE = 25        # metros: un camino sin calle a esta distancia = sendero
DENTRO_PARQUE = 30     # metros hacia adentro del borde de un parque/cementerio = interior aislado
TAGS_PARQUES = {"leisure": ["park", "nature_reserve", "golf_course"], "landuse": ["cemetery"]}

# Horario tipico (hora de apertura, hora de cierre) cuando OSM no lo tiene
HORARIO_TIPICO = {
    "bar": (16, 2), "pub": (16, 2), "nightclub": (21, 3),
    "restaurant": (11, 22), "fast_food": (10, 23), "cafe": (7, 17),
    "pharmacy": (9, 21), "fuel": (6, 23), "cinema": (12, 23), "theatre": (18, 23),
    "marketplace": (6, 19),
    "convenience": (7, 23), "supermarket": (7, 22), "shop": (10, 19),
}
TIPOS_LOCAL = ["bar", "pub", "nightclub", "restaurant", "fast_food", "cafe",
               "pharmacy", "fuel", "cinema", "theatre"]
TIPOS_SENDERO = {"path", "track", "steps", "bridleway", "cycleway"}
# Calles "con vida" (casas, comercios). Autopistas (motorway) y vias de bus
# NO cuentan: un camino junto a una autopista sigue estando aislado.
# Ojo: "trunk" SI cuenta; en Pittsburgh incluye avenidas como Fifth y Forbes en Oakland.
TIPOS_CALLE = ["trunk", "primary", "secondary", "tertiary", "residential", "unclassified",
               "living_street", "service", "pedestrian",
               "trunk_link", "primary_link", "secondary_link", "tertiary_link"]

DIAS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
MIERCOLES = 2  # el dia de referencia (el mismo que el horario de buses)


def horas_de(apertura, cierre):
    """Horas (0-23) abiertas entre apertura y cierre; soporta pasar la medianoche."""
    if cierre <= apertura:
        cierre += 24
    return {h % 24 for h in range(apertura, cierre)}


def incluye_miercoles(dias):
    """'Mo-Fr', 'We', 'Th-Su', 'Mo,We,Fr', 'Sa-Tu' (da la vuelta) -> incluye el miercoles?"""
    for parte in dias.split(","):
        if "-" in parte:
            a, b = parte.split("-", 1)
            if a in DIAS and b in DIAS:
                i, j = DIAS.index(a), DIAS.index(b)
                rango = range(i, j + 1) if i <= j else [*range(i, 7), *range(0, j + 1)]
                if MIERCOLES in rango:
                    return True
        elif parte == DIAS[MIERCOLES]:
            return True
    return False


def horas_abierto(texto, tipo):
    """Horas abiertas un MIERCOLES segun opening_hours de OSM (las reglas se
    aplican en orden y gana la ultima que incluye el miercoles; 'off' = cerrado).
    Si no hay nada que se entienda, horario tipico del tipo de local."""
    if isinstance(texto, str):
        if "24/7" in texto:
            return set(range(24))
        horas = None
        con_dias = sin_dias = 0
        # Las reglas se separan con ';' o con ',' cuando la coma viene despues de una
        # hora ("Su 11:00-19:00, Mo-Sa 09:00-22:00"); no se parten listas de dias
        for regla in re.split(r";|(?<=\d),\s*(?=(?:Mo|Tu|We|Th|Fr|Sa|Su|PH)\b)", texto):
            regla = regla.strip()
            m = re.match(r"^((?:Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*[-,]\s*(?:Mo|Tu|We|Th|Fr|Sa|Su))*)\s*(.*)$", regla)
            if m:
                con_dias += 1
                if not incluye_miercoles(m.group(1).replace(" ", "")):
                    continue
                resto = m.group(2)
            elif re.match(r"^(PH|SH)\b", regla):
                continue  # feriados
            else:
                sin_dias += 1
                resto = regla  # sin dias = todos los dias
            if re.search(r"\b(off|closed)\b", resto):
                horas = set()
                continue
            rangos = re.findall(r"(\d{1,2}):\d{2}\s*-\s*(\d{1,2}):\d{2}", resto)
            if rangos:
                horas = set().union(*(horas_de(int(a), int(c)) for a, c in rangos))
        if horas is not None:
            return horas
        if con_dias and not sin_dias:
            return set()  # todas las reglas nombran dias y ninguna es el miercoles: cerrado
    return horas_de(*HORARIO_TIPICO.get(tipo, HORARIO_TIPICO["shop"]))


def tipos(highway):
    """El tipo de via puede venir como texto o como lista en texto: "['footway', 'steps']"."""
    return set(re.findall(r"[a-z_]+", str(highway)))


def tramos_y_medios(G):
    """Tramos de la red proyectada (uno por tramo_id) y su punto medio."""
    tramos = ox.graph_to_gdfs(G, nodes=False).reset_index()
    tramos["tramo_id"] = [id_tramo(u, v, o, largo) for u, v, o, largo in
                          zip(tramos["u"], tramos["v"], tramos["osmid"], tramos["length"])]
    tramos = tramos.drop_duplicates("tramo_id").set_index("tramo_id")
    medios = gpd.GeoDataFrame(geometry=tramos.geometry.interpolate(0.5, normalized=True), crs=G.graph["crs"])
    return tramos, medios


def aporte_cercano(fuentes, columnas, radio, medios):
    """Suma de 'columnas' de las fuentes a menos de 'radio' m de cada tramo,
    pesando mas las cercanas (1 junto al tramo, 0 en el borde del radio)."""
    fuentes = fuentes.to_crs(medios.crs).reset_index(drop=True)
    pares = gpd.sjoin(medios, fuentes.set_geometry(fuentes.buffer(radio)), predicate="within")
    tramo = medios.geometry.loc[pares.index].reset_index(drop=True)
    fuente = fuentes.geometry.loc[pares["index_right"]].reset_index(drop=True)
    peso = (1 - tramo.distance(fuente) / radio).clip(lower=0).values
    suma = pares[columnas].mul(peso, axis=0).groupby(level=0).sum()
    return suma.reindex(medios.index).fillna(0)


def _limpio(tabla):
    """Quita espacios y tabuladores invisibles de los textos (algunos GTFS los traen,
    p. ej. Gainesville: "\tWB" en vez de "WB")."""
    return tabla.apply(lambda c: c.str.strip() if pd.api.types.is_string_dtype(c) or c.dtype == object else c)


def activos_en(dia, calendario, excepciones):
    """Servicios que funcionan ese dia (AAAAMMDD), segun el calendario y sus excepciones."""
    activos = set()
    if calendario is not None:
        semana = pd.to_datetime(dia).day_name().lower()
        vigente = (calendario["start_date"] <= dia) & (calendario["end_date"] >= dia)
        activos |= set(calendario.loc[vigente & (calendario[semana] == "1"), "service_id"])
    if excepciones is not None:
        hoy = excepciones[excepciones["date"] == dia]
        activos |= set(hoy.loc[hoy["exception_type"] == "1", "service_id"])
        activos -= set(hoy.loc[hoy["exception_type"] == "2", "service_id"])
    return activos


def buses_gtfs(archivo):
    """Buses por hora en cada parada, por franja, un MIERCOLES tipico: el miercoles con
    MAS viajes dentro del periodo del horario (el primero si hay empate). Asi no cae en
    vacaciones o feriados (antes se usaba el 2do miercoles: en Chapel Hill caia en las
    vacaciones de invierno). GeoDataFrame de paradas (grados)."""
    with zipfile.ZipFile(archivo) as z:
        leer = lambda nombre, **kw: _limpio(pd.read_csv(z.open(nombre), dtype=str, **kw))
        archivos = set(z.namelist())
        paradas = leer("stops.txt")
        viajes = leer("trips.txt")
        calendario = leer("calendar.txt") if "calendar.txt" in archivos else None
        excepciones = leer("calendar_dates.txt") if "calendar_dates.txt" in archivos else None

    fechas = []
    if calendario is not None:
        fechas += list(calendario["start_date"]) + list(calendario["end_date"])
    if excepciones is not None:
        fechas += list(excepciones["date"])
    inicio, fin = pd.to_datetime(min(fechas)).date(), pd.to_datetime(max(fechas)).date()
    por_servicio = viajes.groupby("service_id").size()
    mejor, mas_viajes = None, -1
    dia = inicio + timedelta(days=(2 - inicio.weekday()) % 7)
    while dia <= fin:
        n = int(por_servicio.reindex(list(activos_en(dia.strftime("%Y%m%d"), calendario, excepciones))).fillna(0).sum())
        if n > mas_viajes:
            mejor, mas_viajes = dia, n
        dia += timedelta(days=7)
    miercoles = mejor
    activos = activos_en(miercoles.strftime("%Y%m%d"), calendario, excepciones)
    viajes_dia = set(viajes.loc[viajes["service_id"].isin(activos), "trip_id"])
    print(f"Buses: dia de referencia {miercoles} ({len(viajes_dia):,} viajes)")

    # stop_times puede ser enorme (ciudades grandes): se lee por partes
    partes = []
    with zipfile.ZipFile(archivo) as z:
        columnas = pd.read_csv(z.open("stop_times.txt"), nrows=0).columns
        usar = [c for c in ["trip_id", "departure_time", "arrival_time", "stop_id", "stop_sequence"] if c in columnas]
        for horarios in pd.read_csv(z.open("stop_times.txt"), dtype=str, chunksize=2_000_000, usecols=usar):
            horarios = _limpio(horarios)
            horarios = horarios[horarios["trip_id"].isin(viajes_dia)].copy()
            if "arrival_time" in horarios:
                horarios["departure_time"] = horarios["departure_time"].fillna(horarios["arrival_time"])
            if horarios["departure_time"].isna().any() and "stop_sequence" in horarios:
                # GTFS permite dejar sin hora las paradas que no son "puntos de control" (se
                # interpolan): toman la hora de la parada anterior del mismo viaje
                horarios["_orden"] = pd.to_numeric(horarios["stop_sequence"], errors="coerce")
                horarios = horarios.sort_values(["trip_id", "_orden"])
                horarios["departure_time"] = horarios.groupby("trip_id")["departure_time"].ffill()
                horarios["departure_time"] = horarios.groupby("trip_id")["departure_time"].bfill()
            salidas = horarios.dropna(subset=["departure_time"])
            hora = salidas["departure_time"].str.split(":").str[0].astype(int) % 24
            partes.append(pd.DataFrame({franja: hora.isin(horas) / len(horas)  # buses por hora
                                        for franja, horas in FRANJAS.items()}).assign(stop_id=salidas["stop_id"])
                          .groupby("stop_id").sum())
    buses = pd.concat(partes).groupby(level=0).sum()
    paradas = paradas.set_index("stop_id").join(buses, how="inner")
    paradas = gpd.GeoDataFrame(
        paradas, geometry=gpd.points_from_xy(paradas["stop_lon"].astype(float),
                                             paradas["stop_lat"].astype(float)), crs="EPSG:4326")
    print(f"  paradas con servicio: {len(paradas):,}")
    return paradas


def locales_por_franja(locales):
    """Agrega a cada local la fraccion de cada franja que esta abierto."""
    abierto = [horas_abierto(t, tipo) for t, tipo in zip(locales["opening_hours"], locales["tipo"])]
    for franja, horas in FRANJAS.items():
        locales[franja] = [len(a & set(horas)) / len(horas) for a in abierto]
    return locales


def locales_de_osm(osm, tipos_local=TIPOS_LOCAL):
    """Locales de OSM (resultado de features_from_*) con su tipo, nombre, horario y punto."""
    osm = osm.reset_index()
    if "shop" in osm:  # locales vacios o abandonados no atraen gente
        osm = osm[~osm["shop"].isin(["vacant", "disused"])]
    osm["tipo"] = osm["amenity"].where(osm["amenity"].isin(tipos_local), None)
    if "shop" in osm:
        osm["tipo"] = osm["tipo"].fillna(osm["shop"].where(
            osm["shop"].isin(["convenience", "supermarket"]), "shop"))
    if "opening_hours" not in osm:
        osm["opening_hours"] = None
    osm = osm[["tipo", "name", "opening_hours", "geometry"]].copy()
    osm["geometry"] = osm.geometry.representative_point()
    return osm


def senderos(tramos, medios, calles):
    """True por tramo: tipo sendero, o camino peatonal sin ninguna calle cerca.
    Se compara contra TODAS las calles de OSM (no solo la red peatonal), porque
    a veces la acera esta dibujada aparte y la calle no esta en la red."""
    tipos_tramo = tramos["highway"].apply(tipos)
    es_calle = tipos_tramo.apply(lambda t: bool(t & set(TIPOS_CALLE)))
    calles = calles.to_crs(medios.crs)
    calles = calles[calles["highway"].apply(lambda h: bool(tipos(h) & set(TIPOS_CALLE)))]
    calle_cerca = medios.index.isin(
        gpd.sjoin_nearest(medios[~es_calle.values], calles[["geometry"]], max_distance=DIST_CALLE).index)
    return ~es_calle & (tipos_tramo.apply(lambda t: bool(t & TIPOS_SENDERO)) | ~calle_cerca)


def en_parques(medios, parques):
    """True por tramo: su punto medio esta en el interior de un parque o cementerio."""
    interior = parques.to_crs(medios.crs).buffer(-DENTRO_PARQUE)
    interior = gpd.GeoDataFrame(geometry=interior[~interior.is_empty], crs=medios.crs)
    return medios.index.isin(gpd.sjoin(medios, interior, predicate="within").index)


def parques_de_osm(osm):
    """Parques y cementerios de OSM (resultado de features_from_*) como poligonos."""
    osm = osm.reset_index()
    osm = osm[osm.geom_type.isin(["Polygon", "MultiPolygon"])]
    osm["tipo"] = osm["leisure"].fillna(osm["landuse"]) if "landuse" in osm else osm["leisure"]
    return osm[["tipo", "name", "geometry"]]
