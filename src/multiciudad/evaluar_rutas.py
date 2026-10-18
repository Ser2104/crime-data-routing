"""
Prueba de rutas en cualquier ciudad, con el MISMO buscador de la app (src/rutas.py),
igual para todas las ciudades y niveles (investigacion/reglas_de_datos.md, seccion 6):

    VIAJES viajes a pie al azar (semilla fija por ciudad), de 500 a 3,000 m en linea
    recta, a las 2 a. m., 9 a. m., 3 p. m. y 9 p. m.; para cada viaje, la ruta mas
    rapida y la de menor riesgo segun el mapa evaluado; se cuentan los delitos del
    NUCLEO del FUTURO en sus calles.

Medida principal: cambio total de delitos (menor riesgo vs mas rapida) con su
intervalo de confianza del 95% (bootstrap de viajes).
"""
import zlib
from multiprocessing import Pool

import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from pyproj import Transformer

import rutas as R

VIAJES = 2000
DIST_VIAJE = (500, 3000)
HORAS = [2, 9, 15, 21]
PROCESOS = 8
FONDO_VECES = 3   # igual que la app a pie
_G = _T = None


def semilla(ciudad):
    """Semilla fija por ciudad (no depende de nada que se pueda elegir despues)."""
    return zlib.crc32(f"viajes-{ciudad}".encode())


def tareas(ruta_red, ciudad, n=VIAJES):
    G = ox.project_graph(ox.load_graphml(ruta_red))
    rng = np.random.default_rng(semilla(ciudad))
    nodos = np.array(list(G.nodes))
    xy = np.array([(G.nodes[v]["x"], G.nodes[v]["y"]) for v in nodos])
    salida = []
    for i in range(n):
        o = rng.integers(len(nodos))
        dist = np.hypot(*(xy - xy[o]).T)
        candidatos = np.flatnonzero((dist >= DIST_VIAJE[0]) & (dist <= DIST_VIAJE[1]))
        if len(candidatos):
            salida.append((i, nodos[o], nodos[rng.choice(candidatos)], HORAS[i % len(HORAS)]))
    return salida


def _iniciar(ciudad, ruta_red, ruta_riesgo):
    global _G, _T
    R.CALIBRACION = {}
    R.CIUDADES[ciudad] = {"nombre": ciudad, "idioma": "en",
                          "modos": {"a_pie": {"red": ruta_red, "riesgo": ruta_riesgo, "fondo_veces": FONDO_VECES}}}
    R.MUESTRA_AVISO = 50   # el aviso de destino no se usa aqui
    _G = R.cargar_red("a_pie", ciudad=ciudad)
    _T = Transformer.from_crs(_G.graph["crs"], "EPSG:4326", always_xy=True)


def _latlon(n):
    lon, lat = _T.transform(_G.nodes[n]["x"], _G.nodes[n]["y"])
    return lat, lon


def _viaje(tarea):
    i, o, d, hora = tarea
    try:
        rutas = R.buscar_rutas(_G, _latlon(o), _latlon(d), hora)
    except (ValueError, nx.NetworkXNoPath):
        return []
    return [{"viaje": i, "hora": hora, "franja": R.franja_de(hora), "etiqueta": r["etiqueta"],
             "minutos": r["minutos"], "relleno": r.get("relleno", False), "ids": sorted(r["ids"])} for r in rutas]


def simular(ciudad, ruta_red, ruta_riesgo, lista):
    with Pool(PROCESOS, initializer=_iniciar, initargs=(ciudad, str(ruta_red), str(ruta_riesgo))) as pool:
        filas = [r for rs in pool.imap_unordered(_viaje, lista, chunksize=10) for r in rs]
    return pd.DataFrame(filas)


def calificar(viajes, futuro, rng=None, personas=None):
    """futuro: DataFrame por tramo con fut_<franja> (delitos del nucleo del futuro).
    Compara la ruta de menor riesgo con la mas rapida en los viajes donde hay ambas.
    personas (opcional): peatones simulados por hora por tramo (pea_<franja>); agrega la
    medida secundaria "por persona": suma de delitos / personas que pasan por cada tramo
    (con un piso: la mediana de los tramos con gente, para no dividir por casi cero)."""
    rng = rng or np.random.default_rng(1)
    v = viajes[~viajes["relleno"]].copy()
    v["delitos"] = [futuro[f"fut_{f}"].reindex(ids).fillna(0).sum() for f, ids in zip(v["franja"], v["ids"])]
    if personas is not None:
        tasa = {}
        for f in futuro.columns.str.replace("fut_", ""):
            gente = personas[f"pea_{f}"].reindex(futuro.index).fillna(0)
            piso = gente[gente > 0].median()
            tasa[f] = futuro[f"fut_{f}"] / np.maximum(gente, piso)
        v["por_persona"] = [tasa[f].reindex(ids).fillna(0).sum() for f, ids in zip(v["franja"], v["ids"])]
    rap = v[v["etiqueta"] == "Fastest"].set_index("viaje")
    seg = v[v["etiqueta"] == "Lowest risk"].set_index("viaje")
    c = seg.index.intersection(rap.index)
    a, b = rap.loc[c, "delitos"].values, seg.loc[c, "delitos"].values
    resultado = {"viajes": int(v["viaje"].nunique()), "viajes_con_menor_riesgo": len(c)}
    if len(c) and a.sum() > 0:
        m = rng.integers(0, len(c), (2000, len(c)))
        boot = b[m].sum(1) / np.maximum(a[m].sum(1), 1e-9) - 1
        resultado.update({
            "cambio_pct": (b.sum() / a.sum() - 1) * 100,
            "ic95": [np.percentile(boot, 2.5) * 100, np.percentile(boot, 97.5) * 100],
            "delitos_rapida": float(a.sum()), "delitos_menor_riesgo": float(b.sum()),
            "min_extra_mediana": float((seg.loc[c, "minutos"] - rap.loc[c, "minutos"]).median()),
        })
        if "por_persona" in v:
            pa, pb = rap.loc[c, "por_persona"].values, seg.loc[c, "por_persona"].values
            boot = pb[m].sum(1) / np.maximum(pa[m].sum(1), 1e-12) - 1
            resultado["por_persona_pct"] = (pb.sum() / pa.sum() - 1) * 100
            resultado["por_persona_ic95"] = [np.percentile(boot, 2.5) * 100, np.percentile(boot, 97.5) * 100]
    return resultado
