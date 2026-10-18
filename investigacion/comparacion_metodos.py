"""
COMPARACION EXPLORATORIA con un metodo publicado: Galbrun, Pelechrinis y Terzi (2016).
Implementa exactamente el plan fijado antes en investigacion/comparacion_metodos_publicados.md
(commit e680684). No abre ninguna caja fuerte: usa los datos del examen que ya estan abiertos.

Pasos:
    python investigacion/comparacion_metodos.py pruebas
        pruebas sin datos del examen: envolvente convexa contra fuerza bruta en un grafo
        pequeno, y densidad en grilla contra la exacta (con Gainesville, de practica)
    python investigacion/comparacion_metodos.py ensayo
        ensayo completo con Gainesville (100 viajes, los del ensayo del examen)
    python investigacion/comparacion_metodos.py examen
        Filadelfia, Baton Rouge y Tempe con 2,000 viajes
Salida: investigacion/resultados/comparacion_metodos/ (ensayo: data/practice/comparacion_metodos/)
"""
import importlib.util
import json
import sys
import zlib
from multiprocessing import Pool
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from scipy.ndimage import map_coordinates
from scipy.signal import fftconvolve
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.stats import gaussian_kde
import shapely
from shapely.geometry import LineString

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src" / "multiciudad"))
import evaluar_rutas as E  # noqa: E402
import preparar as PR  # noqa: E402
from ciudades import DESARROLLO, EXAMEN, carpeta, carpeta_publica  # noqa: E402
from comun import id_tramo  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

PASADO = ("2024-01-01", "2025-08-31")
PASO = 10.0                  # m, muestreo uniforme a lo largo de cada tramo (cambio 1 del plan)
CELDA = 20.0                 # m, grilla de la densidad
VEL = 80.0                   # m/min, como rutas.VELOCIDAD_PIE
EXTRA_MIN, EXTRA_FRAC = 10.0, 0.5   # limite de tiempo extra de nuestra app (rutas.MAX_EXTRA_MIN, MAX_EXTRA)
PROF_MAX = 30                # tope de seguridad de la recursion
DESEMPATE = 1e-12            # por metro: entre rutas de igual riesgo, la mas corta (y evita pesos 0)
SEMILLA = 20261009
REMUESTREOS = 2000
PROCESOS = 8
CIUDADES_EXAMEN = {"filadelfia": ("holdout_main", RAIZ / "investigacion/resultados/examen_v2", 2000),
                   "baton_rouge": ("holdout_main", RAIZ / "investigacion/resultados/examen_v2", 2000),
                   "tempe": ("holdout_tempe2", RAIZ / "investigacion/resultados/examen_v2_tempe", 2000)}
NUESTROS = {"nucleo": ["A", "mapa_de_calor_A"], "todos": ["B", "C", "mapa_de_calor_B"]}
LISTA_FRANJAS = list(FRANJAS)


# --------------------------------------------------------------------------------------
# 1. Densidad (KDE gaussiana, regla de Scott) en grilla, validada contra la exacta
def densidad(crimenes, puntos):
    """Densidad de 'crimenes' (n x 2, metros) evaluada en 'puntos' (m x 2). Devuelve
    (valores, kde exacta de scipy). Grilla de CELDA m + convolucion FFT con el mismo nucleo."""
    kde = gaussian_kde(crimenes.T, bw_method="scott")
    cov = kde.covariance
    sd = np.sqrt(np.diag(cov))
    pad = 4 * sd.max()
    lo = np.minimum(crimenes.min(0), puntos.min(0)) - pad
    hi = np.maximum(crimenes.max(0), puntos.max(0)) + pad
    n = np.ceil((hi - lo) / CELDA).astype(int) + 1
    H, _, _ = np.histogram2d(crimenes[:, 0], crimenes[:, 1], bins=n,
                             range=[[lo[0], lo[0] + n[0] * CELDA], [lo[1], lo[1] + n[1] * CELDA]])
    H /= len(crimenes)
    k = np.ceil(4 * sd / CELDA).astype(int)
    X, Y = np.meshgrid(np.arange(-k[0], k[0] + 1) * CELDA, np.arange(-k[1], k[1] + 1) * CELDA, indexing="ij")
    inv = np.linalg.inv(cov)
    nucleo = np.exp(-0.5 * (inv[0, 0] * X ** 2 + 2 * inv[0, 1] * X * Y + inv[1, 1] * Y ** 2)) \
        / (2 * np.pi * np.sqrt(np.linalg.det(cov)))
    D = np.clip(fftconvolve(H, nucleo, mode="same"), 0, None)
    fx = (puntos[:, 0] - lo[0]) / CELDA - 0.5
    fy = (puntos[:, 1] - lo[1]) / CELDA - 0.5
    return map_coordinates(D, [fx, fy], order=1, mode="nearest"), kde


def riesgo_tramos(Gp, crimenes, rng, validar=True):
    """Tres valores por tramo (uno por tramo_id, igual en los dos sentidos):
    vertices        r(e) de Galbrun et al. tal como se publico: suma de la densidad en los
                    vertices de la geometria, normalizada sobre los tramos
    uniforme        cambio 1 del plan: integral de la densidad cada PASO m a lo largo del
                    tramo (trapecio), normalizada (G16-uniforme)
    densidad_media  la integral dividida por el largo: riesgo por metro para nuestro buscador"""
    geoms, ids = [], {}
    for u, v, k, d in Gp.edges(keys=True, data=True):
        t = id_tramo(u, v, d["osmid"], d["length"])
        if t in ids:
            continue
        geom = d.get("geometry")
        if geom is None:
            geom = LineString([(Gp.nodes[u]["x"], Gp.nodes[u]["y"]), (Gp.nodes[v]["x"], Gp.nodes[v]["y"])])
        ids[t] = len(ids)
        geoms.append(geom)
    geoms = np.array(geoms, dtype=object)
    # vertices
    vert = [np.asarray(g.coords) for g in geoms]
    dueno_v = np.concatenate([np.full(len(x), i) for i, x in enumerate(vert)])
    vert = np.vstack(vert)
    # muestreo uniforme cada PASO m (incluye las dos puntas)
    largo = shapely.length(geoms)
    n = np.maximum(2, np.ceil(largo / PASO).astype(int) + 1)
    dueno_u = np.repeat(np.arange(len(geoms)), n)
    pos = np.concatenate([np.linspace(0, L, k) for L, k in zip(largo, n)])
    unif = shapely.get_coordinates(shapely.line_interpolate_point(geoms[dueno_u], pos))
    valores, kde = densidad(crimenes, np.vstack([vert, unif]))
    val_v, val_u = valores[:len(vert)], valores[len(vert):]
    control = None
    if validar:
        todos = np.vstack([vert, unif])
        muestra = rng.choice(len(todos), min(500, len(todos)), replace=False)
        exacta = kde(todos[muestra].T)
        control = float(np.median(np.abs(valores[muestra] - exacta) / np.maximum(exacta, 1e-300)))
    lam_v = np.bincount(dueno_v, weights=val_v, minlength=len(geoms))
    # trapecio: paso * (suma - (primera + ultima) / 2)
    suma = np.bincount(dueno_u, weights=val_u, minlength=len(geoms))
    inicio = np.r_[0, np.cumsum(n)[:-1]]
    puntas = (val_u[inicio] + val_u[inicio + n - 1]) / 2
    lam_u = (largo / (n - 1)) * (suma - puntas)
    indice = list(ids)
    return {"vertices": pd.Series(lam_v / lam_v.sum(), index=indice),
            "uniforme": pd.Series(lam_u / lam_u.sum(), index=indice),
            "densidad_media": pd.Series(lam_u / np.maximum(largo, 1e-9), index=indice)}, control


# --------------------------------------------------------------------------------------
# 2. Red para Dijkstra (scipy) y envolvente convexa inferior (Sum-Recursive)
class Red:
    """Aristas dirigidas con largo, peso de riesgo -log(1 - r) y tramo. Entre dos nodos con
    varias aristas, cada busqueda usa la de menor peso para ese costo."""

    def __init__(self, n, u, v, largo, wr, tramo):
        orden = np.lexsort((v, u))
        self.n = n
        self.u, self.v = u[orden], v[orden]
        self.largo, self.wr, self.tramo = largo[orden], wr[orden], tramo[orden]
        nuevo = np.r_[True, (self.u[1:] != self.u[:-1]) | (self.v[1:] != self.v[:-1])]
        self.inicio = np.flatnonzero(nuevo)
        self.pu, self.pv = self.u[self.inicio], self.v[self.inicio]
        self.grupo = np.cumsum(nuevo) - 1
        self.clave = self.pu.astype(np.int64) * n + self.pv   # ordenada (por u y luego v)

    def ruta(self, o, d, mu=None):
        """mu=None: ruta mas corta por largo. Si no: minimiza riesgo + mu * largo."""
        w = self.largo.copy() if mu is None else self.wr + mu * self.largo
        w = w + DESEMPATE * self.largo
        orden = np.lexsort((w, self.grupo))          # dentro de cada par, la de menor peso primero
        primera = orden[np.r_[True, self.grupo[orden][1:] != self.grupo[orden][:-1]]]
        g = csr_matrix((w[primera], (self.u[primera], self.v[primera])), shape=(self.n, self.n))
        _, pred = dijkstra(g, directed=True, indices=o, return_predecessors=True)
        if pred[d] < 0 and o != d:
            return None
        nodos = [d]
        while nodos[-1] != o:
            nodos.append(pred[nodos[-1]])
        nodos.reverse()
        nodos = np.asarray(nodos, dtype=np.int64)
        grupos = np.searchsorted(self.clave, nodos[:-1] * self.n + nodos[1:])
        aristas = [int(e) for e in primera[grupos]]   # primera[g] = arista elegida del par g
        return Ruta(tuple(aristas), float(self.largo[aristas].sum()), float(self.wr[aristas].sum()))


class Ruta:
    def __init__(self, aristas, L, R):
        self.aristas, self.L, self.R = aristas, L, R   # R = suma de -log(1 - r): r_t = 1 - exp(-R)


def envolvente(red, o, d):
    """Rutas de la envolvente convexa inferior de (largo, riesgo total), algoritmo Sum-Recursive."""
    corta, segura = red.ruta(o, d), red.ruta(o, d, mu=0.0)
    if corta is None:
        return []
    casco = {corta.aristas: corta, segura.aristas: segura}

    def rec(a, b, prof):   # a: mas corta y mas riesgosa; b: mas larga y mas segura
        dl, dr = b.L - a.L, a.R - b.R
        if prof > PROF_MAX or dl <= 0 or dr <= 0:
            return
        mu = dr / dl                       # = -lambda del articulo
        c = red.ruta(o, d, mu=mu)
        costo = lambda p: p.R + mu * p.L
        if c.aristas in casco or costo(c) >= costo(a) - 1e-12 * max(1.0, abs(costo(a))):
            return
        casco[c.aristas] = c
        rec(a, c, prof + 1)
        rec(c, b, prof + 1)

    rec(corta, segura, 0)
    return sorted(casco.values(), key=lambda p: p.L)


def elegir(rutas):
    """La de menor riesgo dentro del limite de tiempo extra de nuestra app."""
    corta = rutas[0]
    limite = max(EXTRA_MIN, EXTRA_FRAC * corta.L / VEL)
    dentro = [p for p in rutas if (p.L - corta.L) / VEL <= limite + 1e-9]
    return corta, min(dentro, key=lambda p: (p.R, p.L))


# --------------------------------------------------------------------------------------
# 3. Trabajo en paralelo: cada proceso carga la red de un archivo .npz
_RED = None


def _iniciar(archivo):
    global _RED
    z = np.load(archivo)
    _RED = Red(int(z["n"]), z["u"], z["v"], z["largo"], z["wr"], z["tramo"])


def _un_viaje(t):
    i, o, d, hora = t
    rutas = envolvente(_RED, o, d)
    if not rutas:
        return None
    corta, elegida = elegir(rutas)
    return {"viaje": i, "hora": hora, "n_envolvente": len(rutas),
            "corta": [int(x) for x in _RED.tramo[list(corta.aristas)]], "elegida": [int(x) for x in _RED.tramo[list(elegida.aristas)]],
            "L_corta": corta.L, "L_elegida": elegida.L}


def red_de(Gp, r):
    nodos = {n: i for i, n in enumerate(Gp.nodes)}
    u, v, largo, wr, tramo, nombres = [], [], [], [], [], {}
    for a, b, k, d in Gp.edges(keys=True, data=True):
        t = id_tramo(a, b, d["osmid"], d["length"])
        u.append(nodos[a]); v.append(nodos[b]); largo.append(float(d["length"]))
        wr.append(-np.log1p(-float(r.get(t, 0.0))))
        tramo.append(nombres.setdefault(t, len(nombres)))
    return nodos, list(nombres), dict(n=len(nodos), u=np.array(u), v=np.array(v), largo=np.array(largo),
                                      wr=np.array(wr), tramo=np.array(tramo))


# --------------------------------------------------------------------------------------
# 4. Pruebas
def prueba_envolvente():
    """Grafo en grilla 4x4 con largos y riesgos al azar: la envolvente del algoritmo debe
    coincidir con la envolvente convexa inferior calculada por fuerza bruta."""
    rng = np.random.default_rng(1)
    fallas = 0
    for intento in range(20):
        G = nx.grid_2d_graph(4, 4)
        idx = {n: i for i, n in enumerate(G.nodes)}
        u, v, largo, wr = [], [], [], []
        for a, b in G.edges:
            L, r = rng.uniform(50, 200), rng.uniform(0, 1e-3)
            for x, y in ((a, b), (b, a)):
                u.append(idx[x]); v.append(idx[y]); largo.append(L); wr.append(-np.log1p(-r))
        red = Red(len(idx), np.array(u), np.array(v), np.array(largo), np.array(wr), np.arange(len(u)))
        o, d = idx[(0, 0)], idx[(3, 3)]
        puntos = set()
        arista = {(int(red.u[e]), int(red.v[e])): e for e in range(len(red.u))}
        for camino in nx.all_simple_paths(nx.Graph(G), (0, 0), (3, 3)):
            es = [arista[(idx[a], idx[b])] for a, b in zip(camino[:-1], camino[1:])]
            puntos.add((round(float(red.largo[es].sum()), 6), round(float(red.wr[es].sum()), 12)))
        puntos = sorted(puntos)
        casco = []   # cadena monotona inferior (Andrew)
        for p in puntos:
            while len(casco) >= 2 and ((casco[-1][0] - casco[-2][0]) * (p[1] - casco[-2][1])
                                       - (casco[-1][1] - casco[-2][1]) * (p[0] - casco[-2][0])) <= 0:
                casco.pop()
            casco.append(p)
        # solo la parte que baja (de la mas corta a la de menor riesgo)
        minimo = min(range(len(casco)), key=lambda i: (casco[i][1], casco[i][0]))
        esperado = {(round(L, 3), round(R, 9)) for L, R in casco[:minimo + 1]}
        obtenido = {(round(p.L, 3), round(p.R, 9)) for p in envolvente(red, o, d)}
        if esperado != obtenido:
            fallas += 1
            print("  falla:", sorted(esperado), sorted(obtenido))
    print(f"envolvente vs fuerza bruta: {20 - fallas}/20 grafos coinciden", flush=True)
    return fallas == 0


# --------------------------------------------------------------------------------------
# 5. Datos de cada ciudad
def _examen():
    spec = importlib.util.spec_from_file_location("examen", RAIZ / "src/multiciudad/09_examen.py")
    ex = importlib.util.module_from_spec(spec)
    sys.argv = sys.argv[:1]
    spec.loader.exec_module(ex)
    return ex


def crimenes_pasados(ciudad, grupo, Gp, cfg, ex=None):
    """Delitos conservados del pasado (tras las exclusiones de siempre), en metros."""
    pub = carpeta_publica(ciudad)
    if grupo is None:   # practica: ya preparados
        d = pd.read_csv(carpeta(ciudad) / "delitos_tramo.csv", dtype={"clase_nucleo": str})
    else:
        import geopandas as gpd
        crudo = ex.leer_examen(ciudad, grupo)
        d = PR.normalizar(crudo, ciudad, True)
        limite = gpd.read_file(pub / "limite.geojson").to_crs(cfg["crs"]).geometry.iloc[0]
        lugares = gpd.read_file(pub / "osm.gpkg", layer="lugares")
        d = PR.asignar(d, Gp, limite, lugares, cfg["crs"])
    d = d[(d["motivo_exclusion"] == "ninguno") & (d["fecha"] >= PASADO[0]) & (d["fecha"] <= PASADO[1])]
    import geopandas as gpd
    xy = gpd.GeoSeries(gpd.points_from_xy(d["lon"], d["lat"]), crs=4326).to_crs(cfg["crs"])
    pts = np.c_[xy.x.values, xy.y.values]
    return {"todos": pts, "nucleo": pts[d["clase_nucleo"].notna().values]}


def futuro_de(carpeta_res, ciudad):
    m = pd.read_csv(carpeta_res / f"{ciudad}_mapa_delitos.csv", index_col="tramo_id")
    return {f: m[f"fut_{f}"] for f in LISTA_FRANJAS}


def delitos(ids, franja, fut):
    return float(fut[franja].reindex(ids).fillna(0).sum())


def nuestros_por_viaje(carpeta_res, ciudad, mapa, viajes, fut):
    """Por viaje: delitos en la mas rapida y en la que toma la persona (menor riesgo si se ofrece)."""
    v = pd.read_json(carpeta_res / f"{ciudad}_viajes_{mapa}_{viajes}.jsonl", lines=True)
    v = v[~v["relleno"] & v["etiqueta"].isin(["Fastest", "Lowest risk"])].drop_duplicates(["viaje", "etiqueta"])
    v["d"] = [delitos(ids, f, fut) for ids, f in zip(v["ids"], v["franja"])]
    t = v.pivot_table(index="viaje", columns="etiqueta", values="d", aggfunc="first").reindex(columns=["Fastest", "Lowest risk"])
    t = t.dropna(subset=["Fastest"])
    return pd.DataFrame({"a": t["Fastest"], "b": t["Lowest risk"].fillna(t["Fastest"])}), \
        v[v["etiqueta"] == "Fastest"].set_index("viaje")["ids"].map(lambda x: frozenset(x))


# --------------------------------------------------------------------------------------
# 6. Resumen con intervalos (viajes y zonas de 1 km)
def cambio(a, b):
    return b.sum() / max(a.sum(), 1e-12) - 1


def intervalos(tabla, zonas, rng, columnas):
    """tabla: por viaje, pares (a_m, b_m) por metodo m. Cambio y diferencias con IC por viajes y zonas."""
    zonas = zonas.reindex(tabla.index)
    idx_v = rng.integers(0, len(tabla), (REMUESTREOS, len(tabla)))
    por_zona = tabla.groupby(zonas.values).sum()
    idx_z = rng.integers(0, len(por_zona), (REMUESTREOS, len(por_zona)))
    salida = {}
    for m in columnas:
        a, b = tabla[f"a_{m}"].values, tabla[f"b_{m}"].values
        az, bz = por_zona[f"a_{m}"].values, por_zona[f"b_{m}"].values
        salida[m] = {"cambio": cambio(a, b) * 100,
                     "boot_v": (b[idx_v].sum(1) / np.maximum(a[idx_v].sum(1), 1e-12) - 1) * 100,
                     "boot_z": (bz[idx_z].sum(1) / np.maximum(az[idx_z].sum(1), 1e-12) - 1) * 100}
    return salida


def ic(x):
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]


# --------------------------------------------------------------------------------------
def comparar(ciudad, grupo, carpeta_res, viajes, salida, ex=None):
    cfg = EXAMEN.get(ciudad) or DESARROLLO[ciudad]
    rng = np.random.default_rng(SEMILLA + zlib.crc32(ciudad.encode()))
    red_archivo = carpeta_publica(ciudad) / "red_peatonal.graphml"
    G = ox.load_graphml(red_archivo)
    Gp = ox.project_graph(G, to_crs=cfg["crs"])
    lista = E.tareas(red_archivo, ciudad, n=viajes)
    # zonas de 1 km del origen (mismos viajes y misma proyeccion que la auditoria)
    Gz = ox.project_graph(G)
    zonas = pd.Series({i: f"{int(Gz.nodes[o]['x'] // 1000)}_{int(Gz.nodes[o]['y'] // 1000)}" for i, o, _, _ in lista})
    fut = futuro_de(carpeta_res, ciudad)
    crimenes = crimenes_pasados(ciudad, grupo, Gp, cfg, ex)
    filas, tabla = [], {}
    for var in ["nucleo", "todos"]:
        riesgos, control = riesgo_tramos(Gp, crimenes[var], rng)
        print(f"  {ciudad} {var}: {len(crimenes[var]):,} delitos del pasado; densidad en grilla vs exacta: "
              f"diferencia mediana {control:.4%}", flush=True)
        if control >= 0.01:
            sys.exit("La densidad en grilla no paso el control (>= 1%). No se sigue.")
        # (a) Galbrun et al.: tal como se publico (vertices) y con muestreo uniforme (cambio 1)
        for etiqueta, r in [(f"G16_{var}", riesgos["vertices"]), (f"G16u_{var}", riesgos["uniforme"])]:
            nodos, nombres, arrays = red_de(Gp, r)
            archivo = salida / f"_red_{ciudad}_{etiqueta}.npz"
            np.savez(archivo, **arrays)
            tareas = [(i, nodos[o], nodos[d], h) for i, o, d, h in lista]
            with Pool(PROCESOS, initializer=_iniciar, initargs=(str(archivo),)) as pool:
                res = [x for x in pool.imap_unordered(_un_viaje, tareas, chunksize=10) if x is not None]
            archivo.unlink()
            g = pd.DataFrame(res).set_index("viaje").sort_index()
            g["franja"] = [next(f for f, hs in FRANJAS.items() if h in hs) for h in g["hora"]]
            g["a"] = [delitos([nombres[t] for t in ids], f, fut) for ids, f in zip(g["corta"], g["franja"])]
            g["b"] = [delitos([nombres[t] for t in ids], f, fut) for ids, f in zip(g["elegida"], g["franja"])]
            g["cambia"] = [set(x) != set(y) for x, y in zip(g["corta"], g["elegida"])]
            g[["hora", "n_envolvente", "L_corta", "L_elegida", "a", "b", "cambia"]].to_csv(salida / f"{ciudad}_{etiqueta}.csv")
            tabla[etiqueta] = g[["a", "b"]]
            con = g[g["cambia"]]
            filas.append({"ciudad": ciudad, "metodo": etiqueta, "viajes": len(g), "viajes_que_cambian": int(g["cambia"].sum()),
                          "cambio_solo_si_cambia": cambio(con["a"].values, con["b"].values) * 100 if len(con) else np.nan,
                          "min_extra_mediana_si_cambia": float(((con["L_elegida"] - con["L_corta"]) / VEL).median()) if len(con) else np.nan,
                          "tamano_envolvente_mediana": float(g["n_envolvente"].median()), "control_densidad": control})
        # (b) su mapa dentro de nuestro buscador
        mapa = pd.DataFrame({f"riesgo_{f}": riesgos["densidad_media"] for f in LISTA_FRANJAS})   # por metro (cambio 1)
        largo = pd.Series({id_tramo(u, v, d["osmid"], d["length"]): d["length"] for u, v, d in G.edges(data=True)})
        largo = largo[~largo.index.duplicated()]
        mapa["length"] = largo.reindex(mapa.index).values
        mapa.index.name = "tramo_id"
        ruta_csv = salida / f"{ciudad}_riesgo_kde_{var}.csv"
        mapa.to_csv(ruta_csv)
        v = E.simular(f"kde_{ciudad}_{var}", red_archivo, ruta_csv, lista)
        v.to_json(salida / f"{ciudad}_viajes_kde_{var}_{viajes}.jsonl", orient="records", lines=True)
        v = v[~v["relleno"] & v["etiqueta"].isin(["Fastest", "Lowest risk"])].drop_duplicates(["viaje", "etiqueta"])
        v["d"] = [delitos(ids, f, fut) for ids, f in zip(v["ids"], v["franja"])]
        t = v.pivot_table(index="viaje", columns="etiqueta", values="d", aggfunc="first").reindex(columns=["Fastest", "Lowest risk"])
        t = t.dropna(subset=["Fastest"])
        tabla[f"KDE_{var}"] = pd.DataFrame({"a": t["Fastest"], "b": t["Lowest risk"].fillna(t["Fastest"])})
        filas.append({"ciudad": ciudad, "metodo": f"KDE_{var}", "viajes": len(t),
                      "viajes_que_cambian": int(t["Lowest risk"].notna().sum())})
    # nuestros mapas y control: la ruta mas corta de G16 debe ser nuestra mas rapida
    rapidas = None
    for m in sorted({x for xs in NUESTROS.values() for x in xs}):
        tabla[m], rap = nuestros_por_viaje(carpeta_res, ciudad, m, viajes, fut)
        rapidas = rap if rapidas is None else rapidas
    comunes = tabla["G16_nucleo"].index.intersection(tabla["A"].index)
    iguales = np.mean([np.isclose(tabla["G16_nucleo"].loc[i, "a"], tabla["A"].loc[i, "a"]) for i in comunes])
    print(f"  control: delitos en la ruta mas corta de G16 = en nuestra mas rapida en {iguales:.1%} de los viajes", flush=True)
    # todo en una tabla por viaje (solo viajes presentes en todos los metodos)
    comunes = None
    for k, t in tabla.items():
        comunes = t.index if comunes is None else comunes.intersection(t.index)
    junta = pd.concat({k: t.loc[comunes] for k, t in tabla.items()}, axis=1)
    junta.columns = [f"{c}_{k}" for k, c in junta.columns]
    res = intervalos(junta, zonas, rng, list(tabla))
    resumen = []
    for m, x in res.items():
        resumen.append({"ciudad": ciudad, "metodo": m, "viajes_comunes": len(comunes), "cambio_todos_los_viajes": x["cambio"],
                        "ic95_viajes": ic(x["boot_v"]), "ic95_zonas_1km": ic(x["boot_z"])})
    pares = []
    for metodo, rivales in [(f"{m}_{var}", NUESTROS[var]) for var in ["nucleo", "todos"] for m in ["G16", "G16u", "KDE"]]:
        for nuestro in rivales:
            dv = res[nuestro]["boot_v"] - res[metodo]["boot_v"]
            dz = res[nuestro]["boot_z"] - res[metodo]["boot_z"]
            pares.append({"ciudad": ciudad, "nuestro": nuestro, "publicado": metodo,
                          "diferencia_pp": res[nuestro]["cambio"] - res[metodo]["cambio"],
                          "ic95_viajes": ic(dv), "ic95_zonas_1km": ic(dz)})
    return filas, resumen, pares, float(iguales)


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "pruebas"
    if accion == "pruebas":
        ok = prueba_envolvente()
        rng = np.random.default_rng(SEMILLA)
        cfg = DESARROLLO["gainesville"]
        Gp = ox.project_graph(ox.load_graphml(carpeta_publica("gainesville") / "red_peatonal.graphml"), to_crs=cfg["crs"])
        cr = crimenes_pasados("gainesville", None, Gp, cfg)
        for var in ["nucleo", "todos"]:
            riesgos, control = riesgo_tramos(Gp, cr[var], rng)
            r = riesgos["uniforme"]
            print(f"  ({var}) suma de r uniforme = {r.sum():.6f}; densidad media > 0 en {(riesgos['densidad_media'] > 0).mean():.1%} de los tramos")
            print(f"densidad en grilla vs exacta (Gainesville, {var}): diferencia mediana {control:.4%}", flush=True)
            ok &= control < 0.01
        print("PRUEBAS:", "OK" if ok else "FALLAN")
        return
    if accion == "ensayo":
        salida = RAIZ / "data/practice/comparacion_metodos"
        salida.mkdir(parents=True, exist_ok=True)
        ciudades = {"gainesville": (None, RAIZ / "data/practice/ensayo_examen", 100)}
        ex = None
    else:
        salida = RAIZ / "investigacion/resultados/comparacion_metodos"
        salida.mkdir(parents=True, exist_ok=True)
        ciudades = CIUDADES_EXAMEN
        ex = _examen()
    filas, resumen, pares, controles = [], [], [], {}
    for ciudad, (grupo, carpeta_res, viajes) in ciudades.items():
        print(f"=== {ciudad}", flush=True)
        f, r, p, c = comparar(ciudad, grupo, carpeta_res, viajes, salida, ex)
        filas += f; resumen += r; pares += p; controles[ciudad] = c
        pd.DataFrame(filas).to_csv(salida / "detalle.csv", index=False)
        pd.DataFrame(resumen).to_csv(salida / "cambio_todos_los_viajes.csv", index=False)
        pd.DataFrame(pares).to_csv(salida / "pareadas.csv", index=False)
    (salida / "control_ruta_mas_corta.json").write_text(json.dumps(controles, indent=2))
    pd.set_option("display.width", 250)
    fmt = lambda x: f"{x[0]:+.1f} a {x[1]:+.1f}"
    t = pd.DataFrame(resumen)
    for c in ["ic95_viajes", "ic95_zonas_1km"]:
        t[c] = t[c].map(fmt)
    print("\n" + t.round(1).to_string(index=False))
    p = pd.DataFrame(pares)
    for c in ["ic95_viajes", "ic95_zonas_1km"]:
        p[c] = p[c].map(fmt)
    print("\n(diferencia = nuestro - publicado; negativo = el nuestro evita mas)\n" + p.round(1).to_string(index=False))
    print("\n" + pd.DataFrame(filas).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
