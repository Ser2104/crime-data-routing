"""
Busqueda de rutas A PIE y EN CARRO: la mas rapida y alternativas con menos riesgo.

No es un paso del pipeline (no genera datos): es la "caja de herramientas"
que usa la API. Si se ejecuta directamente, muestra rutas de ejemplo:
    python src/rutas.py

Que riesgo se compara en cada modo:
  - A pie: riesgo de delito (paso 5: incidentes, flujo de personas, aislamiento).
  - En carro: riesgo de choque por cada carro que pasa (paso 8). Ademas se da
    un AVISO sobre el riesgo de delito a pie alrededor del destino (donde te bajas).

Como se comparan las rutas (principios del proyecto):
  - Nunca se dice que una ruta es "segura": solo se compara con la mas rapida.
  - Los tramos que comparten las dos rutas no suman diferencia.
  - Toda calle tiene un RIESGO DE FONDO (nada es 100% seguro, y mucho riesgo
    no aparece en los datos: delitos no denunciados, falta de informacion).
  - El % se calcula sobre el VIAJE COMPLETO de la ruta mas rapida, y lo que
    se muestra tiene un tope: los datos no permiten afirmar diferencias enormes.
  - A pie, el % se CALIBRA con la validacion del paso 10 (rutas elegidas con el
    mapa del pasado, medidas con los incidentes del ano siguiente): se muestra
    lo que de verdad cambio el riesgo y cuantas veces de cada 10 se cumplio.

Ciudades (CIUDADES): Pittsburgh (a pie y en carro, textos en ingles),
Arequipa (solo a pie, textos en espanol) y State College (a pie con riesgo
ESTIMADO, en carro con choques reales; textos en ingles).

Entradas:
    Pittsburgh a pie:    data/processed/red_peatonal.graphml (paso 2), riesgo_tramos.csv (paso 5)
    Pittsburgh en carro: data/processed/red_carro.graphml (paso 7), riesgo_carro.csv (paso 8)
    Arequipa a pie:      data/arequipa/processed/red_peatonal.graphml, riesgo_tramos.csv
    calibracion (opcional): data/processed/calibracion_rutas.json (paso 10)
"""
import json
import math
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from pyproj import Transformer
from shapely import Point

import capa_luz as CL
from comun import id_tramo, valores

# fondo_veces: riesgo de fondo = fondo_veces x el riesgo promedio de la ciudad.
#   A pie es alto (3): muchos delitos no se denuncian y faltan datos de muchos riesgos.
#   En carro es bajo (0.5): PennDOT registra casi todos los choques con heridos o
#   danos importantes, y la tasa del paso 8 ya esta suavizada. Con un fondo alto,
#   el % mediria casi solo kilometros y no los choques de los datos.
MODOS = {
    "a_pie": {"red": "data/processed/red_peatonal.graphml", "riesgo": "data/processed/riesgo_tramos.csv",
              "fondo_veces": 3},
    "carro": {"red": "data/processed/red_carro.graphml", "riesgo": "data/processed/riesgo_carro.csv",
              "fondo_veces": 0.5},
}
# Ciudades: sus archivos por modo y el idioma de los textos que ve el usuario.
# Arequipa solo a pie: no hay datos de choques (salvo los fatales).
CIUDADES = {
    "pittsburgh": {"nombre": "Pittsburgh", "idioma": "en", "modos": MODOS,
                   "luz": "data/processed/luz_tramos.csv"},
    "arequipa": {"nombre": "Arequipa", "idioma": "es", "luz": "data/arequipa/processed/luz_tramos.csv", "modos": {
        "a_pie": {"red": "data/arequipa/processed/red_peatonal.graphml",
                  "riesgo": "data/arequipa/processed/riesgo_tramos.csv", "fondo_veces": 3},
    }},
    # State College: la policia no publica sus incidentes, asi que el riesgo a pie
    # es ESTIMADO con el modelo de transferencia (estimado=True: sin "zonas de alto
    # riesgo" ni aviso del destino, y % con la calibracion del mapa estimado).
    # En carro, choques reales de PennDOT como Pittsburgh.
    "state_college": {"nombre": "State College", "idioma": "en",
                      "luz": "data/state_college/processed/luz_tramos.csv", "modos": {
        "a_pie": {"red": "data/state_college/processed/red_peatonal.graphml",
                  "riesgo": "data/state_college/processed/riesgo_tramos.csv", "fondo_veces": 3,
                  "estimado": True},
        "carro": {"red": "data/state_college/processed/red_carro.graphml",
                  "riesgo": "data/state_college/processed/riesgo_carro.csv", "fondo_veces": 0.5},
    }},
}
CIUDAD_VALIDADA = "pittsburgh"  # la calibracion del paso 10 se midio aqui

# Iluminacion (capa de src/capa_luz.py, paso 14): de noche, un tramo oscuro tiene
# mas riesgo para quien camina. Cuanto: segun los experimentos con alumbrado (la
# revision de Welsh y Farrington, 2008: mejorar el alumbrado bajo los delitos ~21%,
# es decir una calle oscura tiene 1/0.79 = 1.27 veces el riesgo). Con los datos de
# Pittsburgh no se puede medir por persona (no hay conteos de peatones; ver paso 12).
RIESGO_OSCURIDAD = 1.27
FRANJAS_NOCTURNAS = {"madrugada", "noche"}
VELOCIDAD_PIE = 80    # metros por minuto (4.8 km/h, paso normal)
LAMBDAS = [0, 0.5, 1, 2, 4, 8, 16]  # cuanto castigar el riesgo (0 = solo tiempo)
MAX_EXTRA = 0.5       # descartar rutas que tarden mas de 50% extra...
MAX_EXTRA_MIN = 10    # ...o 10 min extra, lo que sea mayor (viajes cortos)
MAX_RUTAS = 4         # la mas rapida + hasta 3 alternativas
MAX_SOLAPE = 0.85     # si una ruta repite 85%+ del camino de otra, no aporta
MAX_SOLAPE_DISTINTO = 0.70  # un "otro camino" debe ser distinto de verdad
AFINAR = 5            # busquedas extra para afinar el precio del riesgo junto al limite de tiempo
# Siempre al menos MIN_RUTAS rutas: si ninguna alternativa pasa los filtros, la mejor
# segunda opcion con limites mas amplios (con su % honesto, aunque no baje el riesgo)
MIN_RUTAS = 2
EXTRA_RELAJADO = 1.0       # hasta el doble de tiempo...
EXTRA_RELAJADO_MIN = 15    # ...o +15 min, lo que sea mayor
SOLAPE_RELAJADO = 0.95     # y que no repita mas del 95% de la mas rapida
# Tramos donde se concentran los errores de OpenStreetMap (caminos que quiza ya
# no existen o no se pueden pasar): se avisa si una ruta recorre MIN_METROS_INCIERTOS o mas
TIPOS_INCIERTOS = {"path", "track", "steps", "bridleway"}
MIN_METROS_INCIERTOS = 30
MAX_DIST_RED = 500    # metros: si un punto esta mas lejos de la red, se rechaza
# En carro no se sale/llega desde una autopista (ni desde una rampa de frenado de emergencia)
VIAS_SIN_ACCESO = {"motorway", "motorway_link", "escape"}
# En carro: espera promedio (segundos) al llegar a un cruce con semaforo o pare.
# No hay datos de trafico en tiempo real: los tiempos suponen trafico normal fluido.
ESPERA_CRUCE = {"traffic_signals": 20, "stop": 5}

# Escala de los porcentajes (ser modestos)
MIN_DIFERENCIA = 3       # menos de 3% = "practicamente igual"
MIN_MEJORA = 3            # cada alternativa: al menos 3 puntos % mejor que la anterior
TOPE_PCT = 30             # nunca mostrar mas de 30%
MAX_DATOS_MISMO_RIESGO = 10  # un "otro camino" no puede tener mas de 10% mas riesgo segun los datos

# Calibracion del % por modo (paso 10): % real ~ pendiente x % calculado + origen
# (en la mediana), y P(de verdad menos riesgo) = logistica(a + b x % calculado).
# Solo existe para los modos validados; sin ella el % se muestra sin calibrar.
ARCHIVO_CALIBRACION = Path("data/processed/calibracion_rutas.json")
CALIBRACION = json.loads(ARCHIVO_CALIBRACION.read_text()) if ARCHIVO_CALIBRACION.exists() else {}

# Aviso del destino (en los dos modos): riesgo de delito a pie a menos de
# RADIO_AVISO m, comparado con la ciudad a esa hora. Solo estas 5 categorias
# (percentiles de la ciudad). La ultima es una ADVERTENCIA: el destino esta en
# uno de los focos de incidentes de la ciudad (el 2% mas alto a esa hora).
RADIO_AVISO = 150
CATEGORIAS_AVISO = [(40, "menor"), (75, "similar"), (92, "algo_mayor"), (98, "mayor"), (100, "alto_riesgo")]
PIES_POR_METRO = 3.28084

# Textos que ve el usuario, en el idioma de cada ciudad: Pittsburgh en ingles
# (millas y pies), Arequipa en espanol (metros)
TEXTOS = {
    "en": {
        "zona": {
            "menor": "fewer recorded incidents than the city average at this time.",
            "similar": "about as many incidents as the city average at this time.",
            "algo_mayor": "somewhat more incidents than the city average at this time.",
            "mayor": "more incidents than the city average at this time. Stay alert.",
            "alto_riesgo": "It's one of the areas with the most incidents in the city at this time.",
        },
        "sujeto": {"a_pie": "Your destination", "carro": "The place where you'll get out of the car"},
        "advertencia": "Warning: {sujeto} is in a high-risk area. {como}",
        "normal": "{sujeto} is in an area with {como}",
        "lejos": "The point ({lat}, {lon}) is {dist} from the nearest street: it's probably outside {ciudad}.",
        "misma_esquina": "The starting point and the destination are at the same corner: "
                         "there's no route to calculate.",
        "rapida": "fastest route",
        "igual": "+{min} min, about the same risk",
        "cambio": "+{min} min, {cuanto} {sentido} risk than the fastest route",
        "al_menos": "at least ", "menos": "less", "mas": "more",
    },
    "es": {
        "zona": {
            "menor": "menos denuncias que el promedio de la ciudad a esta hora.",
            "similar": "más o menos tantas denuncias como el promedio de la ciudad a esta hora.",
            "algo_mayor": "algo más de denuncias que el promedio de la ciudad a esta hora.",
            "mayor": "más denuncias que el promedio de la ciudad a esta hora. Mantente atento.",
            "alto_riesgo": "Es una de las zonas con más denuncias de la ciudad a esta hora.",
        },
        "sujeto": {"a_pie": "Tu destino", "carro": "El lugar donde bajarás del carro"},
        "advertencia": "Advertencia: {sujeto} está en una zona de alto riesgo. {como}",
        "normal": "{sujeto} está en una zona con {como}",
        "lejos": "El punto ({lat}, {lon}) está a {dist} de la calle más cercana: "
                 "probablemente está fuera de {ciudad}.",
        "misma_esquina": "El punto de partida y el destino están en la misma esquina: "
                         "no hay ruta que calcular.",
        "rapida": "ruta más rápida",
        "igual": "+{min} min, más o menos el mismo riesgo",
        "cambio": "+{min} min, {cuanto} {sentido} riesgo que la ruta más rápida",
        "al_menos": "al menos ", "menos": "menos", "mas": "más",
    },
}


def distancia_texto(metros, idioma):
    """Distancia para el usuario: pies en ingles (EE. UU.), metros en espanol."""
    if idioma == "en":
        return f"{metros * PIES_POR_METRO:,.0f} ft"
    return f"{metros:,.0f} m".replace(",", " ")
MUESTRA_AVISO = 3000          # zonas de muestra para conocer la distribucion de la ciudad

# Advertencia en las rutas A PIE: tramos del PERCENTIL_ALTO_RIESGO de la ciudad
# (a esa hora) son "zona de alto riesgo". Se avisa si la ruta recorre al menos
# MIN_METROS_ALTO_RIESGO por ellos.
PERCENTIL_ALTO_RIESGO = 98
MIN_METROS_ALTO_RIESGO = 25

FRANJAS = {
    "madrugada": range(0, 6),
    "manana": range(6, 12),
    "tarde": range(12, 18),
    "noche": range(18, 24),
}


def franja_de(hora):
    return next(f for f, horas in FRANJAS.items() if hora in horas)


def _tipo(highway):
    return highway if isinstance(highway, str) else highway[0]


def cargar_red(modo="a_pie", archivo_riesgo=None, ciudad="pittsburgh"):
    """Carga la red de un modo (en metros) y le pega el riesgo de cada tramo.
    archivo_riesgo: otro mapa de riesgo en lugar del normal (la validacion usa
    uno hecho solo con incidentes del pasado)."""
    archivos = CIUDADES[ciudad]["modos"][modo]
    G = ox.project_graph(ox.load_graphml(archivos["red"]))
    G.graph["modo"] = modo
    G.graph["ciudad"] = ciudad
    G.graph["idioma"] = CIUDADES[ciudad]["idioma"]
    G.graph["estimado"] = archivos.get("estimado", False)  # riesgo estimado, sin datos de delitos
    riesgo = pd.read_csv(archivo_riesgo or archivos["riesgo"], index_col="tramo_id")
    columnas = {f: riesgo[f"riesgo_{f}"].to_dict() for f in FRANJAS}
    for u, v, k, datos in G.edges(keys=True, data=True):
        t = id_tramo(u, v, datos["osmid"], datos["length"])  # el mismo id que en los pasos 2-8
        datos["tramo_id"] = t
        for f in FRANJAS:
            datos[f] = columnas[f].get(t, 0.0)
        # Tiempo de cada tramo: a pie a paso normal; en carro, segun su velocidad
        # mas la espera promedio si al final del tramo hay semaforo o pare
        if modo == "a_pie":
            datos["segundos"] = datos["length"] / VELOCIDAD_PIE * 60
        else:
            datos["segundos"] = float(datos["travel_time"]) + ESPERA_CRUCE.get(G.nodes[v].get("highway"), 0)
    # Riesgo de fondo por franja: fondo_veces x el promedio por metro
    G.graph["fondo"] = {
        f: archivos["fondo_veces"] * (riesgo[f"riesgo_{f}"] * riesgo["length"]).sum()
        / riesgo["length"].sum()
        for f in FRANJAS
    }
    # Velocidad de referencia (m/s) para pasar el castigo por riesgo (por km) a segundos
    largo = sum(d["length"] for _, _, d in G.edges(data=True))
    G.graph["vel_ref"] = largo / sum(d["segundos"] for _, _, d in G.edges(data=True))
    # En carro, los puntos de salida/llegada se enganchan solo a calles normales
    if modo == "carro":
        acceso = {n for u, v, d in G.edges(data=True) if _tipo(d["highway"]) not in VIAS_SIN_ACCESO
                  for n in (u, v)}
        G.graph["acceso"] = G.subgraph(acceso)
    else:
        G.graph["acceso"] = G
        _preparar_aviso(G, riesgo)
        # Umbral de "zona de alto riesgo" por franja (percentil pesado por largo)
        G.graph["umbral_alto"] = {
            f: _percentil_pesado(riesgo[f"riesgo_{f}"].values, riesgo["length"].values, PERCENTIL_ALTO_RIESGO)
            for f in FRANJAS
        }
        # Iluminacion de cada tramo, si la ciudad tiene su capa (paso 14)
        archivo_luz = CIUDADES[ciudad].get("luz")
        G.graph["luz_base"] = (pd.read_csv(archivo_luz, index_col="tramo_id")
                               if archivo_luz and Path(archivo_luz).exists() else None)
        aplicar_luz(G, G.graph["luz_base"])
    return G


def aplicar_luz(G, capa):
    """Pega a cada tramo su oscuridad (1 - probabilidad de tener luz) y su estado
    de iluminacion. Sin capa: 'sin_informacion' y sin castigo nocturno."""
    p = capa["p_luz"].to_dict() if capa is not None else {}
    estado = capa["estado"].to_dict() if capa is not None else {}
    for _, _, d in G.edges(data=True):
        t = d["tramo_id"]
        d["oscuridad"] = 1 - p[t] if t in p else 0.0
        d["estado_luz"] = estado.get(t, "sin_informacion")


def actualizar_luz(G, eventos):
    """Aplica los eventos de oscuridad en tiempo real (farol apagado, corte de luz,
    apagon) sobre la capa base. Devuelve cuantos tramos quedaron con la luz apagada."""
    if G.graph.get("luz_base") is None:
        return 0
    capa = CL.con_tiempo_real(G.graph["luz_base"], G.graph["zonas"], eventos)
    aplicar_luz(G, capa)
    return int((capa["estado"] == "apagada_reportada").sum())


def _factor_luz(datos, franja):
    """De noche, un tramo oscuro pesa hasta RIESGO_OSCURIDAD veces mas."""
    if franja not in FRANJAS_NOCTURNAS:
        return 1.0
    return 1 + (RIESGO_OSCURIDAD - 1) * datos.get("oscuridad", 0.0)


def resumen_luz(G, ruta):
    """Metros de la ruta por estado de iluminacion (lista cerrada de capa_luz,
    sin juntar lo confirmado con lo estimado). Solo a pie y si hay capa de luz."""
    if G.graph["modo"] != "a_pie" or G.graph.get("luz_base") is None:
        return None
    metros = dict.fromkeys(CL.ESTADOS, 0.0)
    for t in ruta["tramos"]:
        metros[t.get("estado_luz", "sin_informacion")] += t["length"]
    return {e: round(v) for e, v in metros.items()}


def _percentil_pesado(valores, pesos, q):
    """Percentil q de 'valores' donde cada valor pesa segun 'pesos' (el largo del tramo)."""
    orden = np.argsort(valores)
    acumulado = np.cumsum(np.asarray(pesos)[orden]) / np.sum(pesos)
    return float(np.asarray(valores)[orden][np.searchsorted(acumulado, q / 100)])


def _preparar_aviso(G, riesgo):
    """Guarda lo necesario para el aviso de destino: el punto medio y el riesgo de
    cada tramo peatonal, y la distribucion del riesgo por zona en la ciudad."""
    aristas = ox.graph_to_gdfs(G, nodes=False).reset_index()
    aristas["tramo_id"] = [id_tramo(u, v, o, largo) for u, v, o, largo in
                           zip(aristas["u"], aristas["v"], aristas["osmid"], aristas["length"])]
    aristas = aristas.drop_duplicates("tramo_id").set_index("tramo_id")
    # Se guarda la linea completa de cada tramo (no solo su punto medio), para que
    # un tramo largo cuente aunque su punto medio quede lejos del destino
    zonas = gpd.GeoDataFrame({"length": aristas["length"]}, geometry=aristas.geometry, crs=aristas.crs)
    for f in FRANJAS:
        zonas[f] = riesgo[f"riesgo_{f}"].reindex(aristas.index).fillna(0)
    G.graph["zonas"] = zonas
    # Distribucion de la ciudad: riesgo de zona alrededor de una muestra de tramos
    muestra = zonas.sample(min(MUESTRA_AVISO, len(zonas)), random_state=0)
    valores = {f: [] for f in FRANJAS}
    for linea in muestra.geometry:
        z = _riesgo_zona(zonas, linea.interpolate(0.5, normalized=True))
        for f in FRANJAS:
            valores[f].append(z[f])
    G.graph["cortes_aviso"] = {f: [np.percentile(valores[f], c) for c, _ in CATEGORIAS_AVISO[:-1]]
                               for f in FRANJAS}


def _riesgo_zona(zonas, punto):
    """Riesgo promedio (pesado por largo) de los tramos a menos de RADIO_AVISO m.
    None si no hay ningun tramo cerca (sin datos no se puede decir nada)."""
    idx = zonas.sindex.query(punto.buffer(RADIO_AVISO), predicate="intersects")
    cerca = zonas.iloc[idx]
    if cerca.empty:
        return None
    return {f: float((cerca[f] * cerca["length"]).sum() / cerca["length"].sum()) for f in FRANJAS}


def aviso_destino(G_pie, lat, lon, hora, modo="a_pie"):
    """Como es el destino (riesgo de delito a pie a su alrededor), en una de 5
    categorias fijas; la ultima ("alto_riesgo") es una advertencia.
    None si no hay calles con datos cerca, o si el riesgo es solo estimado (sin
    denuncias que lo respalden no se califica una zona): no se muestra aviso."""
    if G_pie.graph.get("estimado"):
        return None
    franja = franja_de(hora)
    p, _ = ox.projection.project_geometry(Point(lon, lat), to_crs=G_pie.graph["crs"])
    zona = _riesgo_zona(G_pie.graph["zonas"], p)
    if zona is None:
        return None
    valor = zona[franja]
    cortes = G_pie.graph["cortes_aviso"][franja]
    i = next((i for i, c in enumerate(cortes) if valor <= c), len(cortes))
    _, categoria = CATEGORIAS_AVISO[i]
    t = TEXTOS[G_pie.graph["idioma"]]
    sujeto, como = t["sujeto"][modo], t["zona"][categoria]
    texto = (t["advertencia"].format(sujeto=sujeto.lower(), como=como) if categoria == "alto_riesgo"
             else t["normal"].format(sujeto=sujeto, como=como))
    return {"categoria": categoria, "advertencia": categoria == "alto_riesgo", "texto": texto}


def nodo_cercano(G, lat, lon):
    """Interseccion de la red mas cercana a un punto (lat, lon)."""
    p, _ = ox.projection.project_geometry(Point(lon, lat), to_crs=G.graph["crs"])
    nodo, distancia = ox.distance.nearest_nodes(G.graph["acceso"], p.x, p.y, return_dist=True)
    if distancia > MAX_DIST_RED:
        idioma = G.graph["idioma"]
        raise ValueError(TEXTOS[idioma]["lejos"].format(
            lat=lat, lon=lon, dist=distancia_texto(distancia, idioma),
            ciudad=CIUDADES[G.graph["ciudad"]]["nombre"]))
    return nodo


def _costo_riesgo(G, franja, lam):
    """Costo de un tramo = tiempo + lambda x exposicion relativa (por km, pasada a
    segundos con la velocidad de referencia del modo). Asi la busqueda optimiza la
    misma exposicion (riesgo x km, con la oscuridad de noche) que despues se muestra.
    Incluye el riesgo de fondo: desviarse mucho tambien expone.
    A pie es identico a tiempo x (1 + lambda x exposicion relativa)."""
    fondo, vel = G.graph["fondo"][franja], G.graph["vel_ref"]
    return lambda datos: (datos["segundos"] + lam * (datos["length"] / vel) * (datos[franja] + fondo) / fondo
                          * _factor_luz(datos, franja))


def _costo_distinto(usados, veces=2):
    """Costo para buscar OTRO camino: las calles ya usadas cuestan 'veces' mas."""
    return lambda datos: datos["segundos"] * (veces if datos["tramo_id"] in usados else 1)


def _ruta(G, origen, destino, costo):
    """Ruta de menor costo. Devuelve (intersecciones, tramos)."""
    nodos = nx.shortest_path(
        G, origen, destino,
        weight=lambda u, v, paralelos: min(costo(d) for d in paralelos.values()),
    )
    # Entre tramos paralelos (mismos extremos) quedarse con el mas barato
    tramos = [min(G[u][v].values(), key=costo) for u, v in zip(nodos[:-1], nodos[1:])]
    return nodos, tramos


def _puntos_tramo(G, u, v, datos):
    """Puntos (x, y) de un tramo, en el sentido del recorrido u -> v."""
    pu, pv = (G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])
    if "geometry" not in datos:
        return [pu, pv]
    puntos = list(datos["geometry"].coords)
    # La geometria puede venir dibujada de v a u: darla vuelta si hace falta
    if Point(puntos[0]).distance(Point(pu)) > Point(puntos[-1]).distance(Point(pu)):
        puntos.reverse()
    return puntos


def _a_latlon(G, xy):
    a_latlon = Transformer.from_crs(G.graph["crs"], "EPSG:4326", always_xy=True)
    lon, lat = a_latlon.transform(*zip(*xy))
    return [[round(la, 6), round(lo, 6)] for la, lo in zip(lat, lon)]


def linea_latlon(G, ruta, cuales=None):
    """La ruta como lista de [lat, lon], en el sentido del recorrido (para mapas).
    Si se da 'cuales' (un True/False por tramo), devuelve una lista de lineas:
    una por cada tramo seguido de tramos marcados."""
    pasos = zip(ruta["nodos"][:-1], ruta["nodos"][1:], ruta["tramos"])
    if cuales is None:
        xy = []
        for u, v, datos in pasos:
            puntos = _puntos_tramo(G, u, v, datos)
            xy.extend(puntos if not xy else puntos[1:])
        return _a_latlon(G, xy)
    lineas, actual = [], []
    for (u, v, datos), marcado in zip(pasos, cuales):
        if marcado:
            puntos = _puntos_tramo(G, u, v, datos)
            actual.extend(puntos if not actual else puntos[1:])
        elif actual:
            lineas.append(actual)
            actual = []
    if actual:
        lineas.append(actual)
    return [_a_latlon(G, xy) for xy in lineas]


def marcar_alto_riesgo(G, ruta):
    """A pie: que tramos de la ruta estan en zona de alto riesgo y cuantos metros suman.
    En carro no aplica (el riesgo de delito es para quien camina), ni donde el
    riesgo es solo estimado (no se marca una calle sin denuncias que lo respalden)."""
    if G.graph["modo"] != "a_pie" or G.graph.get("estimado"):
        return [False] * len(ruta["tramos"]), 0
    umbral = G.graph["umbral_alto"][ruta["franja"]]
    cuales = [t[ruta["franja"]] >= umbral for t in ruta["tramos"]]
    metros = round(sum(t["length"] for t, m in zip(ruta["tramos"], cuales) if m))
    if metros < MIN_METROS_ALTO_RIESGO:
        return [False] * len(ruta["tramos"]), 0
    return cuales, metros


def _exposicion(tramos, franja, fondo):
    """(Riesgo del tramo + riesgo de fondo) x km recorridos; de noche, mas en los
    tramos oscuros (_factor_luz)."""
    return sum((d[franja] + fondo) * _factor_luz(d, franja) * d["length"] / 1000 for d in tramos)


def _solape(a, b):
    """Que fraccion del largo de b recorre tambien a."""
    comun = sum(t["length"] for t in b["tramos"] if t["tramo_id"] in a["ids"])
    return comun / max(b["metros"], 1)


def buscar_rutas(G, origen, destino, hora):
    """
    origen, destino: (lat, lon). hora: 0-23.
    Devuelve una lista de rutas; la primera es la mas rapida.
    """
    franja = franja_de(hora)
    fondo = G.graph["fondo"][franja]
    o, d = nodo_cercano(G, *origen), nodo_cercano(G, *destino)
    if o == d:
        raise ValueError(TEXTOS[G.graph["idioma"]]["misma_esquina"])

    vistas = {}   # ids de tramos -> ruta (la misma ruta encontrada dos veces es una sola)
    cal = calibracion_de(G)
    rapida = None

    def buscar(costo):
        """Ruta de menor costo, ya comparada con la mas rapida."""
        nodos, tramos = _ruta(G, o, d, costo)
        ids = frozenset(t["tramo_id"] for t in tramos)
        if ids not in vistas:
            vistas[ids] = {
                "nodos": nodos, "tramos": tramos, "ids": ids, "franja": franja,
                "metros": round(sum(t["length"] for t in tramos)),
                "minutos": round(sum(t["segundos"] for t in tramos) / 60, 1),
                "riesgo": _exposicion(tramos, franja, fondo),
                "metros_inciertos": round(sum(t["length"] for t in tramos
                                              if valores(t.get("highway")) & TIPOS_INCIERTOS)),
            }
            if rapida is not None:
                vistas[ids].update(comparar(rapida, vistas[ids], franja, fondo, cal, G.graph["idioma"]))
        return vistas[ids]

    # 1. Rutas que cambian tiempo por menos riesgo (lambda = cuanto importa el riesgo)
    rapida = buscar(_costo_riesgo(G, franja, 0))
    rapida.update(comparar(rapida, rapida, franja, fondo, cal, G.graph["idioma"]))
    limite = max(rapida["minutos"] * MAX_EXTRA, MAX_EXTRA_MIN)
    dentro_lam, fuera_lam = 0, None   # lambdas cuya ruta tarda menos / mas que el limite
    for lam in LAMBDAS[1:]:
        if buscar(_costo_riesgo(G, franja, lam))["minutos_extra"] <= limite:
            dentro_lam = lam
        elif fuera_lam is None:
            fuera_lam = lam
    # 1b. Afinar junto al limite de tiempo: la ruta de MENOS riesgo que no tarda
    #     demasiado esta donde las rutas pasan a ser "muy lentas" (paso 11: con
    #     esto la busqueda llega a la mejor ruta posible). Se busca partiendo el
    #     intervalo de lambdas por la mitad, en escala logaritmica.
    if fuera_lam is None:
        fuera_lam = LAMBDAS[-1] * 16  # ni con el lambda mas alto se pasa: probar mas alto
    for _ in range(AFINAR):
        lam = math.sqrt(max(dentro_lam, LAMBDAS[1] / 4) * fuera_lam)
        if buscar(_costo_riesgo(G, franja, lam))["minutos_extra"] <= limite:
            dentro_lam = lam
        else:
            fuera_lam = lam
    por_riesgo = [r for r in vistas.values() if r is not rapida]
    # 2. Caminos distintos: penalizar las calles ya usadas y buscar otra vez
    usados = set(rapida["ids"])
    distintos = []
    for _ in range(3):
        antes = len(vistas)
        r = buscar(_costo_distinto(usados))
        if len(vistas) == antes:
            break  # no aparecio un camino nuevo
        distintos.append(r)
        usados |= r["ids"]

    elegidas = [rapida]
    # 3a. Alternativas con menos riesgo: cada una al menos MIN_MEJORA puntos
    #     mejor que la anterior (si tarda mas, tiene que compensar)
    for r in sorted(por_riesgo, key=lambda r: r["minutos"]):
        muy_lenta = r["minutos_extra"] > limite
        poca_mejora = r["cambio_calculado"] > elegidas[-1]["cambio_calculado"] - MIN_MEJORA
        repetida = any(_solape(e, r) >= MAX_SOLAPE for e in elegidas)
        if not (muy_lenta or poca_mejora or repetida) and len(elegidas) < MAX_RUTAS:
            elegidas.append(r)
    # La de MENOR riesgo dentro del limite no puede quedar afuera por falta de
    # lugar: si es MIN_MEJORA puntos mejor que la ultima elegida, la reemplaza
    dentro = [r for r in por_riesgo if r["minutos_extra"] <= limite and _solape(rapida, r) < MAX_SOLAPE]
    mejor = min(dentro, key=lambda r: (r["cambio_calculado"], r["minutos"]), default=None)
    if (mejor is not None and not any(e is mejor for e in elegidas)
            and mejor["cambio_calculado"] <= elegidas[-1]["cambio_calculado"] - MIN_MEJORA):
        if len(elegidas) >= MAX_RUTAS:
            elegidas[-1] = mejor
        else:
            elegidas.append(mejor)
    # 3b. Completar con caminos distintos que NO tengan mas riesgo que la mas rapida.
    #     Si se presentaria como "menos riesgo", no debe haber otra alternativa
    #     ya elegida que sea mas rapida y casi igual de buena (MIN_MEJORA puntos de margen).
    for r in sorted(distintos, key=lambda r: r["minutos"]):
        muy_lenta = r["minutos_extra"] > limite
        # No tener mas riesgo: ni con el fondo, ni segun los datos solos
        mas_riesgo = r["cambio_calculado"] > MIN_DIFERENCIA or r["cambio_datos"] > MAX_DATOS_MISMO_RIESGO
        repetida = any(_solape(e, r) >= MAX_SOLAPE_DISTINTO for e in elegidas)
        # Superada = otra alternativa ya elegida es mas rapida y (casi) igual de buena
        # (si r se presentaria como "menos riesgo") o claramente mejor (si r seria
        # "el mismo riesgo"): mostrar r no le aporta nada al usuario
        margen = MIN_MEJORA if r["cambio_calculado"] <= -MIN_DIFERENCIA else -MIN_MEJORA
        superada = any(
            e is not rapida and e["minutos"] <= r["minutos"]
            and e["cambio_calculado"] <= r["cambio_calculado"] + margen
            for e in elegidas)
        if not (muy_lenta or mas_riesgo or repetida or superada) and len(elegidas) < MAX_RUTAS:
            elegidas.append(r)

    # 3c. Siempre al menos MIN_RUTAS: si ninguna alternativa paso los filtros, la mejor
    #     segunda opcion con limites mas amplios. Si hace falta, se fuerza otro camino
    #     haciendo mucho mas "caras" las calles de la mas rapida.
    if len(elegidas) < MIN_RUTAS:
        for veces in (4, 10):
            buscar(_costo_distinto(set(rapida["ids"]), veces))
        relajado = max(rapida["minutos"] * EXTRA_RELAJADO, EXTRA_RELAJADO_MIN)
        opciones = [r for r in vistas.values() if r is not rapida
                    and r["minutos_extra"] <= relajado and _solape(rapida, r) < SOLAPE_RELAJADO]
        if opciones:
            # Preferir una que no tenga mas riesgo; entre ellas, la mas rapida
            segunda = min(opciones, key=lambda r: (r["cambio_calculado"] > MIN_DIFERENCIA, r["minutos"]))
            segunda["relleno"] = True
            elegidas.append(segunda)

    elegidas.sort(key=lambda r: r["minutos"])
    menor = min(elegidas[1:], key=lambda r: r["cambio_calculado"], default=None)
    # Nombre de cada ruta (en ingles, lo ve el usuario)
    for r in elegidas:
        if r is rapida:
            r["etiqueta"] = "Fastest"
        elif r is menor and r["cambio_calculado"] <= -MIN_DIFERENCIA:
            r["etiqueta"] = "Lowest risk"
        elif r["cambio_calculado"] <= -MIN_DIFERENCIA:
            r["etiqueta"] = "Balanced"
        else:
            r["etiqueta"] = "Alternate route"
    return elegidas


def calibrar(pct, cal):
    """% calibrado: lo que de verdad cambio el riesgo (mediana) en la validacion
    del paso 10 para rutas con este % calculado. Los % chicos se acercan a 0.
    Solo se calibran las promesas de MENOS riesgo (las validadas); un % de mas
    riesgo se deja como esta, para no restarle importancia."""
    if not cal or pct >= 0:
        return pct
    return min(0.0, cal["pendiente"] * pct + cal["origen"])


def veces_de_10(pct, cal):
    """En cuantos de cada 10 viajes de la validacion una ruta con este % calculado
    tuvo de verdad menos riesgo que la mas rapida (None sin calibracion).
    Nunca se dice 10 de 10: ninguna ruta es segura siempre."""
    if not cal or "logit_a" not in cal:
        return None
    return min(9, round(10 / (1 + math.exp(-(cal["logit_a"] + cal["logit_b"] * pct)))))


def calibracion_de(G):
    """Calibracion del % para esta red. En la ciudad validada, completa. En otra
    ciudad del mismo modo se usa solo la correccion de la recta (hace los %
    mas modestos), sin el "X de 10": eso solo se midio en la ciudad validada.
    Si el riesgo es ESTIMADO, la recta medida con un mapa estimado (paso 10,
    seccion 6), que es la que corresponde a ese tipo de mapa."""
    modo = G.graph["modo"]
    cal = CALIBRACION.get(f"{modo}_estimado") if G.graph.get("estimado") else None
    cal = cal or CALIBRACION.get(modo)
    if not cal or (G.graph["ciudad"] == CIUDAD_VALIDADA and not G.graph.get("estimado")):
        return cal
    return {"pendiente": cal["pendiente"], "origen": cal["origen"]}


def comparar(a, b, franja, fondo, cal=None, idioma="en"):
    """Compara la ruta b con la mas rapida (a).

    Los tramos compartidos no suman diferencia; el % se calcula sobre el
    viaje completo de a, se calibra con la validacion (cal, si hay) y lo que
    se muestra tiene un tope (TOPE_PCT)."""
    solo_a = [t for t in a["tramos"] if t["tramo_id"] not in b["ids"]]
    solo_b = [t for t in b["tramos"] if t["tramo_id"] not in a["ids"]]
    compartido = sum(t["length"] for t in a["tramos"] if t["tramo_id"] in b["ids"])
    diferencia = _exposicion(solo_b, franja, fondo) - _exposicion(solo_a, franja, fondo)
    bruto = float(diferencia / a["riesgo"] * 100)  # float normal (no numpy) para el JSON
    # Proteccion: solo se dice "menos riesgo" si los DATOS (sin el fondo) tambien
    # dan menos riesgo. Si la ventaja viene solo del fondo (menos km), es "el mismo riesgo".
    segun_datos = _exposicion(solo_b, franja, 0) - _exposicion(solo_a, franja, 0)
    if bruto < 0 and segun_datos >= 0:
        bruto = 0.0
    calculado = calibrar(bruto, cal)
    # % segun los datos solos (sin fondo), para no llamar "mismo riesgo" a una ruta
    # que segun los datos es claramente mas riesgosa
    base_datos = _exposicion(a["tramos"], franja, 0)
    pct_datos = float(segun_datos / base_datos * 100) if base_datos > 0 else 0.0
    minutos_extra = round(b["minutos"] - a["minutos"], 1)

    tope = abs(calculado) > TOPE_PCT
    cambio = round(max(-TOPE_PCT, min(TOPE_PCT, calculado)))
    de_10 = None
    t = TEXTOS[idioma]
    if a is b:
        texto, cambio = t["rapida"], None
    elif abs(calculado) < MIN_DIFERENCIA:
        texto, cambio = t["igual"].format(min=minutos_extra), 0
    else:
        cuanto = (t["al_menos"] if tope else "") + f"{abs(cambio)}%"
        texto = t["cambio"].format(min=minutos_extra, cuanto=cuanto, sentido=t["menos"] if cambio < 0 else t["mas"])
        if cambio < 0:
            de_10 = veces_de_10(bruto, cal)
    return {
        "cambio_pct": cambio,
        "cambio_calculado": 0.0 if a is b else calculado,
        "cambio_bruto": 0.0 if a is b else bruto,  # antes de calibrar (lo usa el paso 10)
        "cambio_datos": 0.0 if a is b else pct_datos,
        "tope": tope,
        "de_cada_10": de_10,  # validacion: en cuantos de 10 viajes parecidos se cumplio
        "minutos_extra": minutos_extra,
        "metros_compartidos": round(compartido),
        "texto": texto,
    }


if __name__ == "__main__":
    ejemplos = [
        ("Market Square -> PNC Park", (40.4406, -80.0025), (40.4469, -80.0057)),
        ("Cathedral of Learning -> E Carson St y S 18th", (40.4443, -79.9532), (40.4287, -79.9800)),
        ("Estacion Steel Plaza -> Strip District", (40.4418, -79.9960), (40.4525, -79.9820)),
        ("Shadyside -> East Liberty", (40.4540, -79.9350), (40.4610, -79.9250)),
    ]
    print("Cargando redes...")
    redes = {modo: cargar_red(modo) for modo in MODOS}
    for modo, G in redes.items():
        print(f"\n######## {modo} | riesgo de fondo:", {f: round(v, 2) for f, v in G.graph["fondo"].items()})
        for nombre, origen, destino in ejemplos:
            for hora in (10, 23):
                print(f"\n{nombre}  |  {hora}:00")
                for r in buscar_rutas(G, origen, destino, hora):
                    _, alto = marcar_alto_riesgo(G, r)
                    print(f"  {r['etiqueta']:12s}: {r['minutos']:5.1f} min, {r['metros']:5,} m "
                          f"| calculado {r['cambio_calculado']:6.1f}% | {r['texto']}"
                          + (f" | ALTO RIESGO {alto} m" if alto else ""))
                aviso = aviso_destino(redes["a_pie"], *destino, hora, modo)
                print("  destino:", aviso["texto"] if aviso else "(sin datos cerca: no se muestra)")
