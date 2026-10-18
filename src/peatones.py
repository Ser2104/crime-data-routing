"""
Peatones por tramo SIMULANDO VIAJES A PIE. Sirve para cualquier ciudad: solo
necesita la red de calles y donde estan las personas y los lugares.

La gente camina entre lugares: de su casa a una tienda o al trabajo, de una
parada de bus a su casa o a su trabajo, del trabajo a almorzar. Si sabemos
cuantas personas hay en cada lugar, podemos simular esos viajes por la ruta mas
corta (la que recomendaria un navegador) y contar cuantos pasan por cada calle.

Tipos de viaje (VIAJES): de donde salen, a donde van y cuantos por dia.
    poblacion        -> comercios, empleos            (por habitante)
    paradas          -> poblacion, empleos, comercios (por persona que sube o baja)
    estacionamientos -> empleos, comercios            (por plaza: quien llega en carro
                                                       y camina el ultimo tramo)
    empleos          -> comercios                     (por empleo: almuerzo, compras)
A donde va cada viaje: a un destino mas probable cuanto mas pesa y mas cerca
esta: peso x exp(-distancia / ALCANCE). Nadie camina mas de CORTE metros.
Los viajes de vuelta recorren las mismas calles: duplicarian todo por igual,
asi que no se cuentan.

Los numeros por defecto salen de la encuesta nacional de viajes de EE. UU.
(NHTS 2017: ~0.35 viajes a pie por persona al dia, la mitad de menos de 800 m)
y de supuestos razonables; el paso 17 mide si aciertan contra conteos reales.
"""
import io
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from shapely import LineString, Point

from comun import id_tramo
from riesgo_pie import FRANJAS

ALCANCE = 800          # m: la probabilidad de un destino baja a 1/e cada 800 m
CORTE = 2400           # m: nadie camina mas que esto (3 x ALCANCE)
MAX_ENGANCHE = 200     # m: lugares mas lejos de la red no cuentan
LOTE = 48              # origenes por calculo de caminos (memoria vs velocidad)
PASAJEROS_POR_SALIDA = 1.0  # suben + bajan por cada bus que pasa por una parada (si no hay datos reales)

# (origen, destino, viajes por unidad de origen al dia)
VIAJES = [
    ("poblacion", "comercios", 0.20),
    ("poblacion", "empleos", 0.03),
    ("paradas", "poblacion", 0.50),
    ("paradas", "empleos", 0.40),
    ("paradas", "comercios", 0.10),
    ("estacionamientos", "empleos", 0.70),
    ("estacionamientos", "comercios", 0.30),
    ("empleos", "comercios", 0.25),
]
# Parte de los viajes de cada origen en cada franja (las paradas y los comercios
# usan su propio horario: buses que pasan y locales abiertos en cada franja)
HORARIO = {
    "poblacion": {"madrugada": 0.03, "manana": 0.27, "tarde": 0.42, "noche": 0.28},
    "empleos": {"madrugada": 0.00, "manana": 0.30, "tarde": 0.60, "noche": 0.10},
    "estacionamientos": {"madrugada": 0.02, "manana": 0.45, "tarde": 0.40, "noche": 0.13},
}
# Plazas de estacionamiento cuando OSM no trae 'capacity': por area
M2_POR_PLAZA = {"surface": 25, "multi-storey": 30, "underground": 30}
PISOS_SI_NO_HAY = {"multi-storey": 5, "underground": 2}
_S = requests.Session()
_S.headers["User-Agent"] = "safe-routes-pgh/0.1 (proyecto personal)"


# ---------------------------------------------------------------------------
# Red
def preparar_red(G):
    """Red proyectada -> matriz de distancias entre nodos (el tramo mas corto
    entre cada par) y, por par de nodos, sus tramos."""
    nodos = np.array(list(G.nodes))
    pos = {n: i for i, n in enumerate(nodos)}
    filas = [(*sorted((pos[u], pos[v])), max(d["length"], 0.01), id_tramo(u, v, d["osmid"], d["length"]))
             for u, v, d in G.edges(data=True) if u != v]
    tramos = pd.DataFrame(filas, columns=["a", "b", "largo", "tramo_id"]).drop_duplicates("tramo_id")
    pares = tramos.sort_values("largo").drop_duplicates(["a", "b"])
    n = len(nodos)
    pares = pares.assign(clave=pares["a"].astype(np.int64) * n + pares["b"]).sort_values("clave")
    return {
        "G": G, "nodos": nodos, "n": n,
        "xy": np.array([(G.nodes[x]["x"], G.nodes[x]["y"]) for x in nodos]),
        "matriz": csr_matrix((pares["largo"].values, (pares["a"].values, pares["b"].values)), shape=(n, n)),
        "claves": pares["clave"].values,
        # cada tramo -> su par de nodos (los tramos paralelos comparten par y flujo)
        "par_de_tramo": pd.Series(np.searchsorted(pares["clave"].values,
                                                  tramos["a"].astype(np.int64) * n + tramos["b"]),
                                  index=tramos["tramo_id"].values),
    }


def a_nodos(red, puntos, valores):
    """Suma 'valores' de los puntos (GeoSeries en el CRS de la red) en su nodo mas cercano."""
    d, i = cKDTree(red["xy"]).query(np.column_stack([puntos.x, puntos.y]))
    ok = d <= MAX_ENGANCHE
    return np.bincount(i[ok], weights=np.asarray(valores, float)[ok], minlength=red["n"])


def plazas(estacionamientos):
    """Plazas de cada estacionamiento (GeoDataFrame proyectado de OSM, amenity=parking):
    'capacity' si existe; si no, area / m2 por plaza x pisos. Los de calle no cuentan."""
    vacio = pd.Series(np.nan, index=estacionamientos.index)
    tipo = estacionamientos.get("parking", vacio).fillna("surface")
    pisos = pd.to_numeric(estacionamientos.get("building:levels", vacio), errors="coerce")
    pisos = pisos.fillna(tipo.map(PISOS_SI_NO_HAY)).fillna(1)
    por_area = estacionamientos.area / tipo.map(M2_POR_PLAZA) * pisos
    capacidad = pd.to_numeric(estacionamientos.get("capacity", vacio), errors="coerce")
    return capacidad.fillna(por_area).fillna(0)


# ---------------------------------------------------------------------------
# Simulacion
def canales(masas):
    """Lista de (franja, origen, destino, masa_origen, peso_destino) por nodo.
    masas: {"poblacion": vector, "empleos": vector,
            "paradas": {franja: vector de personas que suben/bajan al dia en esa franja},
            "comercios": {franja: vector de locales abiertos (fraccion) en esa franja}}"""
    salida = []
    for origen, destino, tasa in VIAJES:
        for f in FRANJAS:
            m = masas[origen][f] if origen == "paradas" else masas[origen] * HORARIO[origen][f]
            d = masas[destino][f] if destino in ("paradas", "comercios") else masas[destino]
            if m.sum() > 0 and d.sum() > 0:
                salida.append((f, origen, destino, m * tasa, d))
    return salida


def simular(red, masas, origen_en=None, avisar=True):
    """Personas que caminan por cada par de nodos al dia, por franja.
    origen_en: nodos desde donde se simulan viajes (por defecto todos; los
    destinos siempre son todos). Devuelve un DataFrame (una fila por par de
    nodos de la red, una columna por franja)."""
    lista = canales(masas)
    M = np.column_stack([c[3] for c in lista])   # masa de origen por nodo y canal
    D = np.column_stack([c[4] for c in lista])   # peso de destino por nodo y canal
    if origen_en is not None:
        M[~origen_en] = 0
    flujo = np.zeros((len(red["claves"]), len(lista)))
    origenes = np.flatnonzero(M.sum(1) > 0)
    n = red["n"]
    paso = max(8, min(LOTE, int(LOTE * 60_000 / n)))  # redes grandes: lotes chicos (memoria)
    for k in range(0, len(origenes), paso):
        lote = origenes[k:k + paso]
        dist, pred = dijkstra(red["matriz"], directed=False, indices=lote, limit=CORTE,
                              return_predecessors=True)
        r, c = np.nonzero(np.isfinite(dist))
        d = dist[r, c]
        # indice de cada par (origen, nodo) para encontrar el par "padre" en el camino
        posicion = np.full(dist.shape, -1, dtype=np.int64)
        posicion[r, c] = np.arange(len(r))
        p = pred[r, c]
        padre = np.where(p >= 0, posicion[r, np.maximum(p, 0)], -1)
        # viajes de cada origen a cada destino alcanzado, por canal
        W = D[c] * np.exp(-d / ALCANCE)[:, None]
        total = np.zeros((len(lote), len(lista)))
        np.add.at(total, r, W)
        with np.errstate(invalid="ignore", divide="ignore"):
            W *= np.where(total > 0, M[lote] / total, 0.0)[r]
        # cada viaje recorre su camino hasta el origen: se acumula de las hojas al origen
        prof = np.zeros(len(r), dtype=np.int64)
        idx = np.flatnonzero(padre >= 0)
        anc = padre[idx]
        while len(idx):
            prof[idx] += 1
            anc = padre[anc]
            sigue = anc >= 0
            idx, anc = idx[sigue], anc[sigue]
        orden = np.argsort(-prof, kind="stable")
        cortes = np.flatnonzero(np.diff(prof[orden])) + 1
        for grupo in np.split(orden, cortes):
            grupo = grupo[padre[grupo] >= 0]
            if len(grupo):
                np.add.at(W, padre[grupo], W[grupo])
        # lo acumulado en cada nodo es lo que pasa por el tramo que llega a el
        sel = np.flatnonzero(p >= 0)
        a, b = np.minimum(c[sel], p[sel]), np.maximum(c[sel], p[sel])
        par = np.searchsorted(red["claves"], a.astype(np.int64) * n + b)
        np.add.at(flujo, par, W[sel])
        if avisar and (k // paso) % 50 == 0:
            print(f"  origenes {k + len(lote):,} / {len(origenes):,}")
    franjas = pd.DataFrame({f: flujo[:, [i for i, c in enumerate(lista) if c[0] == f]].sum(1) for f in FRANJAS})
    return franjas


def por_tramo(red, por_par):
    """Flujo por par de nodos -> por tramo (los tramos paralelos comparten el de su par)."""
    return por_par.iloc[red["par_de_tramo"].values].set_index(red["par_de_tramo"].index)


# ---------------------------------------------------------------------------
# Conteo en un punto: como un contador, suma lo que cruza una linea perpendicular
# a la calle (las dos aceras y la calle, si estan dibujadas aparte)
SEMI_LINEA = 25   # m a cada lado del punto


def cruce(red, tramos, x, y, valores):
    """Suma 'valores' (por tramo_id) de los tramos que cruzan una linea de
    2 x SEMI_LINEA m perpendicular a la calle mas cercana al punto (x, y)."""
    punto = Point(x, y)
    cerca = tramos.iloc[tramos.sindex.query(punto.buffer(SEMI_LINEA))]
    if cerca.empty:
        return np.nan
    linea = cerca.geometry.iloc[cerca.distance(punto).argmin()]
    s = linea.project(punto)
    a, b = linea.interpolate(max(s - 5, 0)), linea.interpolate(min(s + 5, linea.length))
    dx, dy = b.x - a.x, b.y - a.y
    largo = np.hypot(dx, dy) or 1.0
    nx, ny = -dy / largo * SEMI_LINEA, dx / largo * SEMI_LINEA
    corte = LineString([(x - nx, y - ny), (x + nx, y + ny)])
    cruzan = cerca[cerca.intersects(corte)]
    pares = red["par_de_tramo"].reindex(cruzan.index)
    return float(valores.reindex(cruzan.index)[~pares.duplicated().values].sum())


def alrededor(red, tramos, x, y, valores, radio=30):
    """Para conteos en una ESQUINA: lo que pasa por los tramos a menos de 'radio' m
    del punto (sin repetir tramos paralelos), dividido entre 2 porque quien
    cruza la esquina recorre al menos dos de esos tramos. NaN si no hay red cerca."""
    punto = Point(x, y)
    cerca = tramos.iloc[tramos.sindex.query(punto.buffer(radio))]
    cerca = cerca[cerca.distance(punto) <= radio]
    if cerca.empty:
        return np.nan
    pares = red["par_de_tramo"].reindex(cerca.index)
    return float(valores.reindex(cerca.index)[~pares.duplicated().values].sum() / 2)


# ---------------------------------------------------------------------------
# Datos de EE. UU.: poblacion y empleos por manzana del Censo
TIGERWEB = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10/query"
LODES = "https://lehd.ces.census.gov/data/lodes/LODES8/{estado}/wac/{estado}_wac_S000_JT00_{anio}.csv.gz"


def manzanas_censo(caja):
    """Manzanas del Censo 2020 en la caja (oeste, sur, este, norte): GEOID,
    habitantes y punto interior (grados)."""
    filas, desde = [], 0
    while True:
        r = _S.get(TIGERWEB, timeout=180, params={
            "where": "1=1", "geometry": ",".join(map(str, caja)), "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "returnGeometry": "false",
            "outFields": "GEOID,POP100,INTPTLAT,INTPTLON", "resultOffset": desde,
            "resultRecordCount": 5000, "f": "json"}).json()
        feats = r.get("features", [])
        filas += [f["attributes"] for f in feats]
        desde += len(feats)
        if not r.get("exceededTransferLimit") and len(feats) < 5000:
            break
    m = pd.DataFrame(filas)
    return gpd.GeoDataFrame({"geoid": m["GEOID"], "poblacion": m["POP100"].astype(float)},
                            geometry=gpd.points_from_xy(m["INTPTLON"].astype(float), m["INTPTLAT"].astype(float)),
                            crs=4326)


def empleos_lodes(estado, anio=2023):
    """Empleos por manzana (lugar de trabajo) de LEHD LODES: Series geoid -> empleos."""
    r = _S.get(LODES.format(estado=estado, anio=anio), timeout=300)
    r.raise_for_status()
    w = pd.read_csv(io.BytesIO(r.content), compression="gzip", usecols=["w_geocode", "C000"],
                    dtype={"w_geocode": str})
    return w.set_index("w_geocode")["C000"].astype(float)


def salidas_gtfs(archivo):
    """Salidas de buses/trenes por parada y franja en un dia de semana (usa flujo.buses_gtfs,
    que da buses por hora): GeoDataFrame de paradas con una columna por franja (salidas en la franja)."""
    import flujo as F
    paradas = F.buses_gtfs(archivo)
    for f, horas in FRANJAS.items():
        paradas[f] = paradas[f] * len(horas)
    return paradas


# ---------------------------------------------------------------------------
# Redes grandes: simular por cuadrados (teselas), en paralelo
LADO_TESELA = 2000   # m
PROCESOS_TESELAS = 6


def _calcular_tesela(trabajo):
    """Un cuadrado (en otro proceso): simula y guarda sus personas por tramo."""
    red, masas, origen_en, archivo = trabajo
    parte = por_tramo(red, simular(red, masas, origen_en, avisar=False)).groupby(level=0).sum()
    parte.to_csv(archivo)
    return archivo


def simular_por_teselas(G, fuentes, guardar, lado=LADO_TESELA, procesos=PROCESOS_TESELAS, avisar=True):
    """Igual que simular() sobre toda la red, pero por cuadrados de 'lado' m: los viajes
    salen de los nodos de cada cuadrado y se calculan sobre el cuadrado mas un borde de
    CORTE m (nadie camina mas que eso, asi que el resultado es el mismo). Usa mucha
    menos memoria y varios procesos. fuentes: {"poblacion": (geometrias, valores),
    "empleos": ..., "estacionamientos": ..., "comercios": {franja: (geometrias, valores)},
    "paradas": {franja: (geometrias, valores)}} (en el CRS de G).
    guardar: carpeta donde queda cada cuadrado (si se corta, se retoma). Devuelve las
    personas por tramo y franja (por dia), como por_tramo(red, simular(...)).
    OJO (Windows): quien llame debe estar dentro de if __name__ == "__main__"."""
    import geopandas as gpd
    from multiprocessing import Pool
    from pathlib import Path
    from shapely import box
    carpeta = Path(guardar) / f"lado_{lado}"
    carpeta.mkdir(parents=True, exist_ok=True)
    nodos = np.array(list(G.nodes))
    xy = np.array([(G.nodes[v]["x"], G.nodes[v]["y"]) for v in nodos])
    celda = np.floor(xy / lado).astype(int)
    teselas = sorted({tuple(c) for c in celda})
    geos = {}

    def geo(geoms):
        if id(geoms) not in geos:
            geos[id(geoms)] = gpd.GeoSeries(geoms).reset_index(drop=True)
        return geos[id(geoms)]

    def trabajos():
        for cx, cy in teselas:
            archivo = carpeta / f"tesela_{cx}_{cy}.csv"
            if archivo.exists():
                continue
            x0, y0 = cx * lado - CORTE, cy * lado - CORTE
            x1, y1 = x0 + lado + 2 * CORTE, y0 + lado + 2 * CORTE
            dentro = (xy[:, 0] >= x0) & (xy[:, 0] <= x1) & (xy[:, 1] >= y0) & (xy[:, 1] <= y1)
            sub = G.subgraph(nodos[dentro])
            if sub.number_of_edges() == 0:
                pd.DataFrame(columns=list(FRANJAS)).to_csv(archivo)
                continue
            red = preparar_red(sub)
            caja = box(x0, y0, x1, y1)

            def masa(geoms, valores):
                g = geo(geoms)
                v = np.asarray(valores, float)
                ok = g.within(caja).values
                return a_nodos(red, g[ok], v[ok])

            masas = {k: ({f: masa(*fv) for f, fv in val.items()} if isinstance(val, dict) else masa(*val))
                     for k, val in fuentes.items()}
            pos = pd.Series(np.arange(red["n"]), index=red["nodos"])
            origen_en = np.zeros(red["n"], bool)
            origen_en[pos.reindex(nodos[(celda == (cx, cy)).all(1)]).dropna().astype(int).values] = True
            liviana = {k: red[k] for k in ("n", "matriz", "claves", "par_de_tramo")}
            yield liviana, masas, origen_en, archivo

    pendientes = sum(not (carpeta / f"tesela_{cx}_{cy}.csv").exists() for cx, cy in teselas)
    if avisar:
        print(f"    {len(teselas)} cuadrados ({pendientes} por calcular, {procesos} a la vez)", flush=True)
    hechos = 0
    with Pool(procesos) as pool:
        for _ in pool.imap_unordered(_calcular_tesela, trabajos()):
            hechos += 1
            if avisar and hechos % 10 == 0:
                print(f"    {hechos}/{pendientes}", flush=True)
    partes = [pd.read_csv(carpeta / f"tesela_{cx}_{cy}.csv", index_col=0) for cx, cy in teselas]
    total = pd.concat([p for p in partes if len(p)])
    return total.groupby(level=0).sum()
