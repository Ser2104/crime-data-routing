"""
Paso 18: probar la simulacion de peatones (src/peatones.py) en NUEVA YORK, una
ciudad con la que NO se ajusto nada, contra los conteos reales de NYC DOT
(Bi-Annual Pedestrian Counts): 99 puntos en calles de los cinco distritos. Los
15 de puentes y del Hudson River Greenway quedan fuera: alli camina sobre todo
gente que pasea, y el modelo solo simula viajes entre lugares.

Conteos: dia de semana, 7-9 a. m. y 4-7 p. m., a mitad de cuadra en las dos
aceras. Se mide igual: lo que cruza una linea perpendicular a la calle
(peatones.cruce). Promedio de mayo 2023 a mayo 2026.

Para no descargar toda la ciudad, los puntos se agrupan (a menos de 4 km entre
si) y cada grupo tiene su ventana: la red a menos de VENTANA m de sus puntos.
Solo salen viajes de lugares a menos de CORTE de algun punto (los demas no
pueden pasar por el); los destinos son todos los de la ventana.

Se comparan las mismas variantes que en Pittsburgh (paso 17), sin cambiar nada:
    - formula actual (buses y trenes por hora cerca + 3 x locales abiertos cerca)
    - simulacion con entradas REALES al metro (en los buses: 1 persona por bus que pasa)
    - simulacion solo con el horario (1 persona por bus o tren que pasa)
    - simulacion sin estacionamientos (entradas reales al metro)

Datos (se descargan la primera vez en data/peatones/nyc/): Censo 2020, LODES 2023
(Nueva York), horarios GTFS de MTA (metro y buses), entradas al metro por hora
(data.ny.gov, una semana de mayo 2025), y calles, locales y estacionamientos de
OSM: del archivo de Geofabrik (src/osm_local.py) si esta en data/peatones/nyc/,
si no, consultando a Overpass (que limita y bloquea si se le pide mucho).
Salida: data/peatones/comparacion_nueva_york.csv

Ejecutar desde la carpeta del proyecto (tarda: descarga la red de cada ventana):
    python src/18_peatones_nueva_york.py
"""
import json
import re
import socket
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
import requests
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from osmnx import _http
from shapely import Point

import flujo as F
import luz_modelo as LM
import osm_local as OL
import peatones as P
from redes import red_peatonal
from riesgo_pie import FRANJAS

CARPETA = Path("data/peatones/nyc")
CONTEOS_URL = "https://data.cityofnewyork.us/resource/cqsj-cfgu.json?$limit=500"
METRO_URL = "https://data.ny.gov/resource/5wq4-mkjj.json"
SEMANA_METRO = ("2025-05-05T00:00:00", "2025-05-09T23:59:59")   # lunes a viernes
GTFS = ["gtfs_subway", "gtfs_m", "gtfs_b", "gtfs_bx", "gtfs_q", "gtfs_si", "gtfs_busco"]
GTFS_URL = "https://rrgtfsfeeds.s3.amazonaws.com/{}.zip"
CRS = 32618                 # UTM 18N (metros)
GRUPO = 4000                # m: puntos de un mismo grupo, a menos de esto entre si
VENTANA = 3000              # m de red alrededor de cada punto
DESDE_ANIO = 23             # conteos desde mayo 2023
HORAS_CONTEO = {"manana": 2, "tarde": 2, "noche": 1}   # 7-9 a. m. y 4-7 p. m.
NO_CALLE = r"Bridge|Greenway"
PBF = CARPETA / "new-york-latest.osm.pbf"   # https://download.geofabrik.de/north-america/us/new-york.html
OSM_LOCAL = CARPETA / "osm_nyc.pkl"
CARPETA.mkdir(parents=True, exist_ok=True)
(CARPETA / "redes").mkdir(exist_ok=True)


SERVIDORES = list(LM.OVERPASS)
ox.settings.requests_timeout = 600   # las ventanas grandes (Manhattan) tardan en descargarse
# overpass-api.de rechaza (406) o corta a clientes sin identificacion propia
UA = "safe-routes-pgh/0.1 (proyecto personal)"
ox.settings.http_user_agent = UA


def ip_que_responde(host):
    """overpass-api.de tiene dos maquinas y a veces una no acepta conexiones: se
    usa la primera que acepte una conexion en 5 s (OSMnx elegiria una al azar)."""
    for *_, direccion in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP):
        try:
            socket.create_connection(direccion[:2], timeout=5).close()
            return direccion[0]
        except OSError:
            continue
    return host


def fijar_ip(url):
    """Reemplaza osmnx._http._config_dns, que fija la PRIMERA ip del DNS (a veces
    la maquina que no responde): aqui se fija la que si responde."""
    host = _http._hostname_from_url(url)
    ip = ip_que_responde(host)

    def _getaddrinfo(*args, **kwargs):
        if host == next(iter(args), kwargs.get("host")):
            kwargs.pop("host", None)
            return _http._original_getaddrinfo(ip, *args[1:], **kwargs)
        return _http._original_getaddrinfo(*args, **kwargs)

    socket.getaddrinfo = _getaddrinfo


_http._config_dns = fijar_ip


def vivo(servidor):
    """True si el servidor Overpass contesta algo en 20 s (la descarga puede tardar mas)."""
    try:
        requests.get(servidor.replace("interpreter", "status"), timeout=20, headers={"User-Agent": UA})
        return True
    except requests.RequestException:
        return False


def con_reintentos(funcion, *args):
    """Descargas de OpenStreetMap: se usa el primer servidor Overpass que conteste
    (luz_modelo.OVERPASS); el que funciona pasa a ser el primero. Si ninguno
    contesta, se espera cada vez mas (1, 2, 4... min) y se vuelve a intentar."""
    for intento in range(7):
        for servidor in list(SERVIDORES):
            if not vivo(servidor):
                continue
            ox.settings.overpass_url = servidor.rsplit("/", 1)[0]
            try:
                resultado = funcion(*args)
                SERVIDORES.remove(servidor)
                SERVIDORES.insert(0, servidor)
                return resultado
            except Exception as e:  # servidor caido o saturado
                print(f"  Overpass {servidor} fallo ({type(e).__name__}); probando otro...")
        espera = min(60 * 2 ** intento, 900)
        print(f"  Ningun servidor Overpass responde; espero {espera // 60} min...")
        time.sleep(espera)
    raise RuntimeError("Ningun servidor Overpass respondio")


def conteos():
    """Personas contadas en dia de semana (7-9 a. m. + 4-7 p. m.), promedio desde DESDE_ANIO."""
    archivo = CARPETA / "conteos.json"
    if not archivo.exists():
        archivo.write_text(requests.get(CONTEOS_URL, timeout=120).text)
    d = pd.DataFrame(json.loads(archivo.read_text()))
    patron = re.compile(r"^(may|june|sept|oct)_?(\d{2})_?(am|pm|p_m|md)$")
    sesiones = {}
    for col in d.columns:
        m = patron.match(col)
        if m and int(m.group(2)) >= DESDE_ANIO and m.group(3) != "md":   # md = sabado
            sesiones.setdefault((m.group(1), m.group(2)), []).append(col)
    totales = pd.concat([d[cols].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=len(cols))
                         for cols in sesiones.values() if len(cols) == 2], axis=1)
    d["personas"] = totales.mean(axis=1)
    d["sesiones"] = totales.notna().sum(axis=1)
    d = d[~d["street_nam"].str.contains(NO_CALLE, case=False) & (d["sesiones"] > 0)]
    xy = [g["coordinates"] for g in d["the_geom"]]
    return gpd.GeoDataFrame(d[["loc", "borough", "street_nam", "from_stree", "to_street", "personas", "sesiones"]],
                            geometry=gpd.points_from_xy([c[0] for c in xy], [c[1] for c in xy]), crs=4326)


def metro_real():
    """Entradas al metro por estacion y franja, un dia de semana promedio (personas que suben).
    Las salidas son parecidas a las entradas: la actividad de la estacion es el doble."""
    archivo = CARPETA / "metro.json"
    if not archivo.exists():
        r = requests.get(METRO_URL, timeout=300, params={
            "$select": "station_complex_id,avg(latitude) as lat,avg(longitude) as lon,"
                       "sum(ridership) as total,date_extract_hh(transit_timestamp) as h",
            "$where": f"transit_timestamp between '{SEMANA_METRO[0]}' and '{SEMANA_METRO[1]}'",
            "$group": "station_complex_id,h", "$limit": 50000})
        archivo.write_text(r.text)
    m = pd.DataFrame(json.loads(archivo.read_text()))
    m[["lat", "lon", "total", "h"]] = m[["lat", "lon", "total", "h"]].astype(float)
    franja_de = {h: f for f, horas in FRANJAS.items() for h in horas}
    m["franja"] = m["h"].astype(int).map(franja_de)
    t = m.pivot_table(index="station_complex_id", columns="franja", values="total", aggfunc="sum").fillna(0) / 5
    pos = m.groupby("station_complex_id")[["lon", "lat"]].mean()
    return gpd.GeoDataFrame(2 * t[list(FRANJAS)], geometry=gpd.points_from_xy(pos.loc[t.index, "lon"],
                                                                             pos.loc[t.index, "lat"]), crs=4326)


def paradas_gtfs():
    """Salidas por parada y franja de todos los horarios de MTA, con su tipo (metro o bus)."""
    partes = []
    for nombre in GTFS:
        archivo = CARPETA / f"{nombre}.zip"
        if not archivo.exists():
            archivo.write_bytes(requests.get(GTFS_URL.format(nombre), timeout=300).content)
        p = P.salidas_gtfs(archivo)
        p["metro"] = nombre == "gtfs_subway"
        partes.append(p[list(FRANJAS) + ["metro", "geometry"]])
    return gpd.GeoDataFrame(pd.concat(partes, ignore_index=True), crs=4326)


def lugares(ventana, grupo):
    """Locales y estacionamientos de OSM en la ventana (grados)."""
    archivo = CARPETA / f"lugares_{grupo}.geojson"
    if not archivo.exists():
        if osm_local:
            osm = OL.lugares(osm_local, ventana)
            quiere = osm.get("amenity").isin(F.TIPOS_LOCAL + ["parking"]) | osm.get("shop").notna()
            osm = osm[quiere]
        else:
            osm = con_reintentos(ox.features_from_polygon, ventana,
                                 {"amenity": F.TIPOS_LOCAL + ["parking"], "shop": True})
        osm = osm.reset_index()
        columnas = [c for c in ["amenity", "shop", "name", "opening_hours", "parking", "capacity",
                                "building:levels", "geometry"] if c in osm]
        osm[columnas].to_file(archivo, driver="GeoJSON")
    osm = gpd.read_file(archivo)
    estac = osm[osm["amenity"] == "parking"]
    return F.locales_de_osm(osm[osm["amenity"] != "parking"]), estac


def formula(paradas, locales, medios):
    """Formula actual (paso 4): buses por hora a menos de 150 m + 3 x locales abiertos."""
    buses = F.aporte_cercano(paradas.assign(**{f: paradas[f] / len(h) for f, h in FRANJAS.items()}),
                             list(FRANJAS), F.RADIO_FLUJO, medios)
    locs = F.aporte_cercano(locales, list(FRANJAS), F.RADIO_FLUJO, medios)
    return sum((buses[f] + 3 * locs[f]) * h for f, h in HORAS_CONTEO.items())


def en_horas_de_conteo(por_tramo):
    """Personas por tramo en las horas del conteo (la simulacion da personas por franja al dia)."""
    return sum(por_tramo[f] / len(FRANJAS[f]) * h for f, h in HORAS_CONTEO.items())


# ---------------------------------------------------------------------------
puntos = conteos().to_crs(CRS)
print(f"Puntos de conteo en calles: {len(puntos)} ({puntos['sesiones'].median():.0f} sesiones por punto)")
xy = np.column_stack([puntos.geometry.x, puntos.geometry.y])
puntos["grupo"] = fcluster(linkage(xy, "complete"), GRUPO, "distance")
print(f"Grupos (ventanas): {puntos['grupo'].nunique()}")

caja = tuple(puntos.to_crs(4326).buffer(0.04).total_bounds)
archivo_manzanas = CARPETA / "manzanas.geojson"
if not archivo_manzanas.exists():
    print("Descargando manzanas del Censo y empleos (LODES)...")
    m = P.manzanas_censo(caja)
    m["empleos"] = m["geoid"].map(P.empleos_lodes("ny")).fillna(0)
    m.to_file(archivo_manzanas, driver="GeoJSON")
manzanas = gpd.read_file(archivo_manzanas).to_crs(CRS)
metro = metro_real().to_crs(CRS)
osm_local = None
if PBF.exists():
    print("Leyendo OpenStreetMap del archivo de Geofabrik (sin Overpass)...")
    osm_local = OL.leer(PBF, tuple(puntos.buffer(5000).to_crs(4326).total_bounds), OSM_LOCAL)
paradas = paradas_gtfs().to_crs(CRS)
print(f"Manzanas {len(manzanas):,} | estaciones de metro {len(metro)} | paradas GTFS {len(paradas):,}")

filas = []
for grupo, pts in puntos.groupby("grupo"):
    archivo_grupo = CARPETA / f"resultado_{grupo}.csv"
    if archivo_grupo.exists():
        filas.append(pd.read_csv(archivo_grupo))
        continue
    print(f"\n=== Grupo {grupo}: {len(pts)} puntos ({', '.join(pts['street_nam'].head(3))}...)")
    zona = pts.buffer(VENTANA).union_all()
    ventana = gpd.GeoSeries([zona], crs=CRS).to_crs(4326).iloc[0]
    archivo_red = CARPETA / "redes" / f"grupo_{grupo}.graphml"
    if not archivo_red.exists():
        G = OL.red_peatonal(osm_local, ventana) if osm_local else con_reintentos(red_peatonal, ventana)
        ox.save_graphml(G, archivo_red)
    G = ox.project_graph(ox.load_graphml(archivo_red), to_crs=CRS)
    red = P.preparar_red(G)
    tramos, medios = F.tramos_y_medios(G)
    print(f"  red: {red['n']:,} nodos, {len(tramos):,} tramos")
    locales, estac = lugares(ventana, grupo)
    locales = F.locales_por_franja(locales).to_crs(CRS)
    estac = estac.to_crs(CRS)
    estac["plazas"] = P.plazas(estac)
    adentro = lambda g: g[g.within(zona)]
    par, met, man = adentro(paradas), adentro(metro), adentro(manzanas)

    def masas(metro_real_si, con_estacionamientos=True):
        bus = par[~par["metro"]] if metro_real_si else par
        return {
            "poblacion": P.a_nodos(red, man.geometry, man["poblacion"]),
            "empleos": P.a_nodos(red, man.geometry, man["empleos"]),
            "comercios": {f: P.a_nodos(red, locales.geometry, locales[f]) for f in FRANJAS},
            "estacionamientos": P.a_nodos(red, estac.geometry.representative_point(),
                                          estac["plazas"] * con_estacionamientos),
            "paradas": {f: P.a_nodos(red, bus.geometry, bus[f] * P.PASAJEROS_POR_SALIDA)
                        + (P.a_nodos(red, met.geometry, met[f]) if metro_real_si else 0)
                        for f in FRANJAS},
        }

    # viajes solo desde nodos a menos de CORTE de algun punto del grupo
    d, _ = cKDTree(np.column_stack([pts.geometry.x, pts.geometry.y])).query(red["xy"])
    origen_en = d <= P.CORTE
    estimaciones = {}
    for nombre, (real, con_est) in {"simulacion (entradas reales al metro)": (True, True),
                                    "simulacion (solo horario)": (False, True),
                                    "simulacion sin estacionamientos": (True, False)}.items():
        print(f"  {nombre}...")
        estimaciones[nombre] = en_horas_de_conteo(P.por_tramo(red, P.simular(red, masas(real, con_est),
                                                                              origen_en, avisar=False)))
    cerca = tramos.sindex.nearest(pts.geometry, return_all=False)[1]
    form = formula(par, locales, medios.iloc[np.unique(cerca)])
    salida = pts.drop(columns="geometry").copy()
    salida["formula actual (buses + 3 x locales)"] = form.reindex(tramos.index[cerca]).values
    for nombre, valores in estimaciones.items():
        salida[nombre] = [P.cruce(red, tramos, p.x, p.y, valores) for p in pts.geometry]
    salida.to_csv(archivo_grupo, index=False)
    filas.append(salida)
    print(salida[["street_nam", "personas"] + list(estimaciones)].round(0).to_string(index=False))

comp = pd.concat(filas, ignore_index=True)
comp.to_csv("data/peatones/comparacion_nueva_york.csv", index=False)
metodos = [c for c in comp.columns if c.startswith(("formula", "simulacion"))]
rng = np.random.default_rng(1)
print(f"\nParecido con los conteos reales en {len(comp)} puntos (Spearman):")
for nombre in metodos:
    x, y = comp[nombre].values, comp["personas"].values
    ok = np.isfinite(x)
    x, y = x[ok], y[ok]
    boot = [spearmanr(x[i], y[i]).statistic for i in rng.integers(0, len(x), (2000, len(x)))]
    linea = (f"  {nombre:42s} rho = {spearmanr(x, y).statistic:+.2f} "
             f"(IC95 {np.nanpercentile(boot, 2.5):+.2f} a {np.nanpercentile(boot, 97.5):+.2f})")
    if nombre.startswith("simulacion"):
        razon = x / y
        linea += (f" | simulado/real: mediana {np.median(razon):.2f}, "
                  f"la mitad entre {np.percentile(razon, 25):.2f} y {np.percentile(razon, 75):.2f}")
    print(linea)
