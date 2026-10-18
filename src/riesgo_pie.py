"""
Calculo del riesgo A PIE por tramo. Lo usan el paso 5 (con todos los incidentes)
y el paso 10 (validacion: con los incidentes de un periodo, para predecir el siguiente).

A) Cada incidente reparte peligro a su tramo y a los cercanos, midiendo la distancia
   CAMINANDO: 0-40 m = 100%, -10% cada 20 m, 0% a mas de 220 m. Cada tramo recibe
   el peso PROMEDIO a lo largo de su largo.
B) El peligro se divide por raiz(1 + flujo de personas / FLUJO_REF).
C) De madrugada y de noche: penalizacion por lugar aislado vacio y por faroles.
"""
import math

import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely import MultiPoint, Point

from comun import id_tramo

# Flujo de personas = buses por hora cercanos + PESO_LOCAL x locales abiertos
PESO_LOCAL = 3         # un local abierto "atrae" gente como 3 buses por hora
FLUJO_REF = 5          # con este flujo, el riesgo se divide por raiz(2) = 1.4

# Penalizaciones nocturnas, medidas como percentiles del riesgo de la ciudad
FRANJAS_NOCTURNAS = ["madrugada", "noche"]
PERCENTIL_SENDERO = 0.90
PERCENTIL_FAROLES = 0.50
FAROLES_MAX = 10       # con 10+ reportes cercanos, penalizacion completa

# Escala de peligro por distancia caminando (metros)
PRIMERA_CAPA = 40   # hasta aqui, 100%
ANCHO_CAPA = 20     # cada capa siguiente mide 20 m...
BAJADA = 0.10       # ...y baja un 10%
RADIO = 220         # mas lejos, 0%

# Franjas horarias (hora del reporte)
FRANJAS = {
    "madrugada": range(0, 6),
    "manana": range(6, 12),
    "tarde": range(12, 18),
    "noche": range(18, 24),
}

# La escala como capas (desde, hasta, peso): 0-40 m = 1.0, 40-60 = 0.9, ..., 200-220 = 0.1
CAPAS = [(0, PRIMERA_CAPA, 1.0)] + [
    (PRIMERA_CAPA + ANCHO_CAPA * i, PRIMERA_CAPA + ANCHO_CAPA * (i + 1), round(1 - BAJADA * (i + 1), 2))
    for i in range(round((RADIO - PRIMERA_CAPA) / ANCHO_CAPA))
]
LEJOS = 1e9  # distancia "infinita" para intersecciones que el incidente no alcanza


def peso(distancia):
    """Que fraccion del peligro de un incidente llega a esta distancia."""
    if distancia < PRIMERA_CAPA:
        return 1.0
    if distancia >= RADIO:
        return 0.0
    capa = math.floor((distancia - PRIMERA_CAPA) / ANCHO_CAPA)
    return round(1 - BAJADA * (capa + 1), 2)


def integral_peso(x):
    """Area bajo la escala de peso entre 0 y x metros (para promediar sin aproximar)."""
    return sum(p * min(max(x - a, 0), b - a) for a, b, p in CAPAS)


def peso_promedio(d_a, d_b, largo):
    """Peso PROMEDIO a lo largo de un tramo, sabiendo la distancia caminando desde
    el incidente a cada extremo (d_a, d_b). En cada punto del tramo se llega por el
    extremo mas cercano; asi un tramo largo con el incidente en una punta solo
    recibe el peligro completo cerca de esa punta, no en todo su largo."""
    if largo <= 0:
        return peso(min(d_a, d_b))
    s = min(max((d_b + largo - d_a) / 2, 0), largo)  # punto donde los dos caminos empatan
    area = (integral_peso(d_a + s) - integral_peso(d_a)) + (integral_peso(d_b + largo - s) - integral_peso(d_b))
    return area / largo


def peso_propio(x, largo):
    """Peso promedio del tramo donde esta el incidente (a x metros de uno de sus extremos)."""
    if largo <= 0:
        return 1.0
    return (integral_peso(x) + integral_peso(largo - x)) / largo


def preparar_red(ruta_red):
    """Carga la red peatonal (en metros) y arma lo que necesita el reparto."""
    G = ox.project_graph(ox.load_graphml(ruta_red))
    aristas = ox.graph_to_gdfs(G, nodes=False).reset_index()
    aristas["tramo_id"] = [id_tramo(u, v, o, largo) for u, v, o, largo in
                           zip(aristas["u"], aristas["v"], aristas["osmid"], aristas["length"])]
    tramos = aristas.drop_duplicates("tramo_id").set_index("tramo_id")
    # Grafo simple para Dijkstra: intersecciones unidas por su largo en metros
    red = nx.Graph()
    for u, v, largo in zip(tramos["u"], tramos["v"], tramos["length"]):
        if not red.has_edge(u, v) or red[u][v]["length"] > largo:
            red.add_edge(u, v, length=largo)
    tramos_de_nodo = {}
    for t, u, v in zip(tramos.index, tramos["u"], tramos["v"]):
        tramos_de_nodo.setdefault(u, []).append(t)
        tramos_de_nodo.setdefault(v, []).append(t)
    return {
        "G": G,
        "tramos": tramos,
        "geometria": aristas.set_index(["u", "v", "key"])["geometry"],  # para ubicar incidentes
        "red": red,
        "extremos": {t: (u, v, largo) for t, u, v, largo in
                     zip(tramos.index, tramos["u"], tramos["v"], tramos["length"])},
        "tramos_de_nodo": tramos_de_nodo,
    }


def pesos_por_franja(df, columna_peso="gravedad"):
    """Cuanto aporta cada incidente a cada franja (su peso; si la hora es
    desconocida, 00:00, se reparte en partes iguales entre las 4 franjas)."""
    df = df.copy()
    valor = df[columna_peso] if columna_peso else pd.Series(1.0, index=df.index)
    conocida = ~df["hora_desconocida"].astype(bool)
    for franja, horas in FRANJAS.items():
        df[franja] = np.where(conocida, df["Hour"].isin(horas) * valor, valor / len(FRANJAS))
    return df


def pesos_de_punto(ctx, u, v, key, x, y):
    """Que peso recibe cada tramo cercano de un incidente ubicado en (x, y) sobre
    el tramo (u, v, key): {tramo_id: peso promedio a lo largo del tramo}."""
    red, extremos, tramos_de_nodo = ctx["red"], ctx["extremos"], ctx["tramos_de_nodo"]
    linea = ctx["geometria"][(u, v, key)]
    desde_u = linea.project(Point(x, y))      # metros hasta u
    hasta_v = max(linea.length - desde_u, 0)  # metros hasta v
    # Distancia caminando desde el incidente a cada interseccion cercana
    du = nx.single_source_dijkstra_path_length(red, u, cutoff=RADIO, weight="length")
    dv = nx.single_source_dijkstra_path_length(red, v, cutoff=RADIO, weight="length")
    dist_nodo = {n: d + desde_u for n, d in du.items()}
    for n, d in dv.items():
        dist_nodo[n] = min(dist_nodo.get(n, math.inf), d + hasta_v)
    # Cada tramo alcanzado recibe el peso PROMEDIO a lo largo de su largo
    pesos = {}
    for n in dist_nodo:
        for t in tramos_de_nodo.get(n, []):
            if t not in pesos:
                d_a = dist_nodo.get(extremos[t][0], LEJOS)
                d_b = dist_nodo.get(extremos[t][1], LEJOS)
                pesos[t] = peso_promedio(d_a, d_b, extremos[t][2])
    datos = ctx["G"].edges[u, v, key]
    pesos[id_tramo(u, v, datos["osmid"], datos["length"])] = peso_propio(desde_u, linea.length)
    return {t: w for t, w in pesos.items() if w > 0}


def repartir(ctx, df, columna_peso="gravedad", conservar_masa=False, avisar=True, memoria=None):
    """Reparte el peligro de los incidentes (df) por la red. Devuelve un DataFrame
    tramo x franja.
    conservar_masa=True: cada incidente reparte EXACTAMENTE su peso entre los
    tramos (proporcional a peso x largo), asi la suma por tramo son incidentes
    ESPERADOS en ese tramo (sirve para calibrar contra incidentes reales).
    memoria: un dict para guardar los pesos de cada punto y no recalcularlos si
    se llama varias veces (la validacion reparte varios periodos)."""
    df = pesos_por_franja(df, columna_peso)
    lugar = ["XCOORD", "YCOORD", "u", "v", "key"]
    puntos = df.groupby(lugar)[list(FRANJAS)].sum().reset_index()
    memoria = {} if memoria is None else memoria
    nuevos = puntos[[tuple(fila) not in memoria for fila in puntos[lugar].itertuples(index=False)]]
    if len(nuevos):
        xy = ox.projection.project_geometry(MultiPoint(list(zip(nuevos["XCOORD"], nuevos["YCOORD"]))),
                                            crs="EPSG:4326", to_crs=ctx["G"].graph["crs"])[0]
        if avisar:
            print(f"Repartiendo peligro de {len(nuevos):,} puntos por la red (unos minutos)...")
        for i, (fila, p) in enumerate(zip(nuevos[lugar].itertuples(index=False), xy.geoms)):
            memoria[tuple(fila)] = pesos_de_punto(ctx, fila.u, fila.v, fila.key, p.x, p.y)
            if avisar and (i + 1) % 2000 == 0:
                print(f"  {i + 1:,} / {len(nuevos):,}")

    largo = {t: max(e[2], 1) for t, e in ctx["extremos"].items()}
    riesgo = {f: {} for f in FRANJAS}
    for fila, cantidades in zip(puntos[lugar].itertuples(index=False), puntos[list(FRANJAS)].values):
        pesos = memoria[tuple(fila)]
        if conservar_masa:
            # peso x largo = "cuanto del incidente cae en ese tramo"; se normaliza a 1
            masa = {t: w * largo[t] for t, w in pesos.items()}
            total = sum(masa.values())
            pesos = {t: m / total for t, m in masa.items()}
        for f, n_inc in zip(FRANJAS, cantidades):
            if n_inc:
                acumulado = riesgo[f]
                for t, w in pesos.items():
                    acumulado[t] = acumulado.get(t, 0) + w * n_inc
    return pd.DataFrame(riesgo).reindex(ctx["tramos"].index).fillna(0)


def combinar(ctx, incidentes, flujo, avisar=True):
    """Riesgo final por tramo y franja: incidentes / flujo de personas +
    penalizaciones nocturnas (lugar aislado vacio y faroles)."""
    tramos = ctx["tramos"]
    flujo = flujo.reindex(tramos.index)
    salida = tramos[["u", "v", "key", "name", "highway", "length"]].copy()
    salida["es_sendero"] = flujo["es_sendero"].fillna(False).astype(bool)
    salida["es_aislado"] = flujo["es_aislado"].fillna(False).astype(bool)  # sendero o interior de parque
    faroles = (flujo["faroles_311"].fillna(0) / FAROLES_MAX).clip(upper=1)
    for f in FRANJAS:
        inc = incidentes[f].reindex(salida.index).fillna(0)
        gente = flujo[f"buses_{f}"].fillna(0) + PESO_LOCAL * flujo[f"locales_{f}"].fillna(0)
        ajustado = inc / (1 + gente / FLUJO_REF) ** 0.5
        salida[f"incidentes_{f}"] = inc.round(3)
        salida[f"flujo_{f}"] = gente.round(1)
        if f in FRANJAS_NOCTURNAS:
            con_riesgo = ajustado[ajustado > 0]
            vacio = (1 - gente / FLUJO_REF).clip(lower=0)  # 1 = nadie, 0 = con gente
            aislado = salida["es_aislado"] * vacio * con_riesgo.quantile(PERCENTIL_SENDERO)
            oscuro = faroles * con_riesgo.quantile(PERCENTIL_FAROLES)
            ajustado = ajustado + aislado + oscuro
            if avisar:
                print(f"  {f}: penalizacion lugar aislado vacio = {con_riesgo.quantile(PERCENTIL_SENDERO):.2f}, "
                      f"faroles = {con_riesgo.quantile(PERCENTIL_FAROLES):.2f} (en unidades de riesgo)")
        salida[f"riesgo_{f}"] = ajustado.round(3)
    salida["length"] = salida["length"].round(1)
    return salida
