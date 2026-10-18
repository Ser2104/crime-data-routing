"""
OpenStreetMap SIN consultas a Overpass: lee el archivo regional .osm.pbf de
Geofabrik (https://download.geofabrik.de) y arma lo mismo que las descargas de
OSMnx: la red peatonal de un poligono y sus lugares (locales, estacionamientos).

Para ciudades grandes o muchas zonas: Overpass limita las consultas y bloquea
por un rato a quien le pide mucho; el archivo se baja una vez y se lee sin
limites. Es el camino para un mapa global.

Uso:
    datos = leer(pbf, caja, cache)          # una vez por region (minutos)
    G = red_peatonal(datos, poligono)       # como redes.red_peatonal
    osm = lugares(datos, poligono)          # como ox.features_from_polygon
"""
import pickle
import re
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

import geopandas as gpd
import osmium
import osmnx as ox
from shapely import Point, Polygon

from comun import prohibida_a_pie
from redes import ETIQUETAS_PIE

# El mismo filtro "walk" que OSMnx 2 manda a Overpass (sin anclar, como Overpass):
# se excluye la via si la etiqueta contiene el patron
NO_CAMINABLE = {
    "highway": r"abandoned|bus_guideway|construction|cycleway|motor|no|planned|platform|proposed|"
               r"raceway|razed|rest_area|services",
    "area": "yes", "access": "private", "foot": "no", "service": "private",
    "sidewalk": "separate", "sidewalk:both": "separate", "sidewalk:left": "separate",
    "sidewalk:right": "separate",
}
CLAVES_LUGAR = ("amenity", "shop")


def caminable(tags):
    return "highway" in tags and not any(k in tags and re.search(p, tags[k]) for k, p in NO_CAMINABLE.items())


def leer(pbf, caja, cache=None):
    """Vias caminables (con las coordenadas de sus nodos) y lugares con amenity o
    shop dentro de la caja (oeste, sur, este, norte). Se guarda en 'cache'."""
    if cache and Path(cache).exists():
        return pickle.loads(Path(cache).read_bytes())
    oeste, sur, este, norte = caja
    dentro = lambda x, y: oeste <= x <= este and sur <= y <= norte
    vias, nodos, lugares_ = [], {}, []
    proceso = (osmium.FileProcessor(str(pbf)).with_locations()
               .with_filter(osmium.filter.KeyFilter("highway", *CLAVES_LUGAR)))
    for o in proceso:
        tags = {t.k: t.v for t in o.tags}
        if o.is_node():
            if any(k in tags for k in CLAVES_LUGAR) and dentro(o.location.lon, o.location.lat):
                lugares_.append((tags, Point(o.location.lon, o.location.lat)))
        elif o.is_way():
            try:
                puntos = [(n.ref, n.lon, n.lat) for n in o.nodes]
            except osmium.InvalidLocationError:
                continue
            if not any(dentro(x, y) for _, x, y in puntos):
                continue
            if caminable(tags):
                vias.append((o.id, [r for r, _, _ in puntos], tags))
                nodos.update({r: (x, y) for r, x, y in puntos})
            if any(k in tags for k in CLAVES_LUGAR):
                cerrada = len(puntos) >= 4 and puntos[0][0] == puntos[-1][0]
                lugares_.append((tags, Polygon([(x, y) for _, x, y in puntos]) if cerrada
                                 else Point(puntos[0][1], puntos[0][2])))
    datos = {"vias": vias, "nodos": nodos, "lugares": lugares_}
    if cache:
        Path(cache).write_bytes(pickle.dumps(datos))
    return datos


def red_peatonal(datos, poligono):
    """Red caminable dentro del poligono (grados), la parte conectada mas grande,
    sin vias prohibidas a pie: lo mismo que redes.red_peatonal."""
    ox.settings.useful_tags_way = list(dict.fromkeys(ox.settings.useful_tags_way + ETIQUETAS_PIE))
    oeste, sur, este, norte = poligono.bounds
    nodos = datos["nodos"]
    adentro = lambda r: oeste <= nodos[r][0] <= este and sur <= nodos[r][1] <= norte
    vias = [v for v in datos["vias"] if any(adentro(r) for r in v[1])]
    usados = {r for v in vias for r in v[1]}
    with tempfile.NamedTemporaryFile("w", suffix=".osm", delete=False, encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n')
        for r in usados:
            f.write(f'<node id="{r}" lat="{nodos[r][1]}" lon="{nodos[r][0]}"/>\n')
        for i, refs, tags in vias:
            f.write(f'<way id="{i}">' + "".join(f'<nd ref="{r}"/>' for r in refs)
                    + "".join(f"<tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in tags.items()) + "</way>\n")
        f.write("</osm>\n")
    G = ox.graph_from_xml(f.name, bidirectional=True, retain_all=True)
    Path(f.name).unlink()
    G = ox.truncate.truncate_graph_polygon(G, poligono)
    quitar = [(u, v, k) for u, v, k, d in G.edges(keys=True, data=True) if prohibida_a_pie(d)]
    G.remove_edges_from(quitar)
    print(f"Vias prohibidas a pie eliminadas (bus, acceso prohibido): {len(quitar)} tramos")
    return ox.truncate.largest_component(G, strongly=True)


def lugares(datos, poligono):
    """Lugares (amenity o shop) dentro del poligono, como GeoDataFrame en grados."""
    filas = [(t, g) for t, g in datos["lugares"] if poligono.contains(g.representative_point())]
    if not filas:
        return gpd.GeoDataFrame({"amenity": [], "shop": []}, geometry=[], crs=4326)
    return gpd.GeoDataFrame([t for t, _ in filas], geometry=[g for _, g in filas], crs=4326)


# ---------------------------------------------------------------------------
# Todo lo que necesita una ciudad, en dos pasadas por el archivo (multiciudad)
TAGS_AREA = {"leisure": {"park", "nature_reserve", "golf_course"}, "landuse": {"cemetery"}}


def leer_ciudad(pbf, caja, cache=None):
    """Como leer(), y ademas: todas las calles (lineas con su 'highway'), paradas de bus
    (puntos) y parques/cementerios como poligonos, incluidos los compuestos (relaciones
    multipolygon). Todo dentro de la caja (oeste, sur, este, norte), en grados."""
    if cache and Path(cache).exists():
        return pickle.loads(Path(cache).read_bytes())
    from shapely import LineString, from_wkb
    oeste, sur, este, norte = caja
    dentro = lambda x, y: oeste <= x <= este and sur <= y <= norte
    vias, nodos, lugares_, calles, paradas = [], {}, [], [], []
    proceso = (osmium.FileProcessor(str(pbf)).with_locations()
               .with_filter(osmium.filter.KeyFilter("highway", "public_transport", *CLAVES_LUGAR)))
    for o in proceso:
        tags = {t.k: t.v for t in o.tags}
        if o.is_node():
            x, y = o.location.lon, o.location.lat
            if not dentro(x, y):
                continue
            if any(k in tags for k in CLAVES_LUGAR):
                lugares_.append((tags, Point(x, y)))
            if tags.get("highway") == "bus_stop" or tags.get("public_transport") == "platform":
                paradas.append(Point(x, y))
        elif o.is_way():
            try:
                puntos = [(n.ref, n.lon, n.lat) for n in o.nodes]
            except osmium.InvalidLocationError:
                continue
            if not any(dentro(x, y) for _, x, y in puntos):
                continue
            if "highway" in tags and len(puntos) >= 2:
                calles.append((tags["highway"], LineString([(x, y) for _, x, y in puntos])))
                if caminable(tags):
                    vias.append((o.id, [r for r, _, _ in puntos], tags))
                    nodos.update({r: (x, y) for r, x, y in puntos})
            if any(k in tags for k in CLAVES_LUGAR):
                cerrada = len(puntos) >= 4 and puntos[0][0] == puntos[-1][0]
                lugares_.append((tags, Polygon([(x, y) for _, x, y in puntos]) if cerrada
                                 else Point(puntos[0][1], puntos[0][2])))
    # Segunda pasada: areas (parques y cementerios, simples o compuestos)
    fabrica, areas = osmium.geom.WKBFactory(), []
    # solo se arman las areas de parques y cementerios (no todos los usos de suelo del estado)
    etiquetas = [(k, v) for k, vs in TAGS_AREA.items() for v in sorted(vs)]
    for o in osmium.FileProcessor(str(pbf)).with_areas(osmium.filter.TagFilter(*etiquetas)) \
            .with_filter(osmium.filter.TagFilter(*etiquetas)):
        if not o.is_area():
            continue
        tags = {t.k: t.v for t in o.tags}
        tipo = next((v for k, vs in TAGS_AREA.items() if tags.get(k) in vs for v in [tags[k]]), None)
        if tipo is None:
            continue
        try:
            geom = from_wkb(fabrica.create_multipolygon(o))
        except (RuntimeError, ValueError):
            continue
        x0, y0, x1, y1 = geom.bounds
        if x1 >= oeste and x0 <= este and y1 >= sur and y0 <= norte:
            areas.append((tipo, tags.get("name"), geom))
    datos = {"vias": vias, "nodos": nodos, "lugares": lugares_, "calles": calles,
             "paradas": paradas, "areas": areas}
    if cache:
        Path(cache).write_bytes(pickle.dumps(datos))
    return datos


def calles_gdf(datos):
    return gpd.GeoDataFrame({"highway": [h for h, _ in datos["calles"]]},
                            geometry=[g for _, g in datos["calles"]], crs=4326)


def paradas_gdf(datos):
    return gpd.GeoDataFrame(geometry=datos["paradas"], crs=4326)


def parques_gdf(datos):
    return gpd.GeoDataFrame({"tipo": [t for t, _, _ in datos["areas"]], "name": [n for _, n, _ in datos["areas"]]},
                            geometry=[g for _, _, g in datos["areas"]], crs=4326)


# ---------------------------------------------------------------------------
# Lugares y uso del suelo extra (reglas de datos, version 3)
USOS_SUELO = {"residential": "residencial", "commercial": "comercial", "retail": "comercial",
              "industrial": "industrial"}


def leer_extra(pbf, caja, cache=None):
    """Estaciones de tren o metro (puntos), estadios (puntos), uso del suelo (poligonos
    residencial/comercial/industrial) y edificios (punto y area aproximada en m2),
    dentro de la caja (oeste, sur, este, norte), en grados.
    Los poligonos salen del contorno de cada via cerrada (sin armar las areas de todo
    el estado, que agota la memoria en estados grandes); se pierden solo los dibujados
    como relaciones (multipolygon), poco comunes en edificios. Igual en todas las ciudades."""
    if cache and Path(cache).exists():
        return pickle.loads(Path(cache).read_bytes())
    import math
    oeste, sur, este, norte = caja
    dentro = lambda x, y: oeste <= x <= este and sur <= y <= norte
    m2_por_grado2 = 111_320 ** 2 * math.cos(math.radians((sur + norte) / 2))
    estaciones, estadios, usos, edificios = [], [], [], []
    proceso = (osmium.FileProcessor(str(pbf)).with_locations()
               .with_filter(osmium.filter.KeyFilter("building", "landuse", "leisure", "railway", "public_transport")))
    for o in proceso:
        tags = {t.k: t.v for t in o.tags}
        es_estacion = tags.get("railway") in ("station", "halt", "subway_entrance") or             tags.get("public_transport") == "station"
        if o.is_node():
            if es_estacion and dentro(o.location.lon, o.location.lat):
                estaciones.append(Point(o.location.lon, o.location.lat))
            continue
        if not o.is_way():
            continue
        try:
            xy = [(n.lon, n.lat) for n in o.nodes]
        except osmium.InvalidLocationError:
            continue
        if len(xy) < 4 or xy[0] != xy[-1] or not any(dentro(x, y) for x, y in xy):
            continue
        poligono = Polygon(xy)
        if not poligono.is_valid:
            poligono = poligono.buffer(0)
        if "building" in tags:
            c = poligono.representative_point()
            edificios.append((c.x, c.y, poligono.area * m2_por_grado2))
        elif tags.get("landuse") in USOS_SUELO:
            usos.append((USOS_SUELO[tags["landuse"]], poligono))
        elif tags.get("leisure") == "stadium":
            estadios.append(poligono.representative_point())
        if es_estacion:
            estaciones.append(poligono.representative_point())
    datos = {"estaciones": estaciones, "estadios": estadios, "usos": usos, "edificios": edificios}
    if cache:
        Path(cache).write_bytes(pickle.dumps(datos))
    return datos
