"""
R10 de la revision (investigacion/analisis_revision.md, commit 78484c0): el metodo publicado de
Galbrun, Pelechrinis y Terzi (G16) con dos variantes mas, y el ancho de banda de su densidad.
Exploratorio, posterior al examen. Reutiliza investigacion/comparacion_metodos.py (envolvente
Sum-Recursive, eleccion dentro del limite de tiempo, evaluacion) sin cambiarlo.

    "por franja"   el KDE de cada franja usa solo los delitos del pasado de esa franja (los de hora
                   desconocida con peso 1/4 en cada una); cada viaje usa el riesgo de su franja
    "isotropico"   el nucleo de su ecuacion 1 (un solo ancho h para los dos ejes):
                   h^2 = factor de Scott^2 x (var_x + var_y) / 2
Cada una con "como se publico" (suma en los vertices) y "muestreo uniforme", con los delitos del
nucleo y con todos.

    python investigacion/revision_g16.py ensayo     Gainesville (practica), 100 viajes
    python investigacion/revision_g16.py examen     Filadelfia, Baton Rouge y Tempe (datos ya abiertos)
Salida: investigacion/resultados/revision/ (ensayo: data/practice/revision/)
"""
import sys
import zlib
from multiprocessing import Pool
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
from scipy.ndimage import map_coordinates
from scipy.signal import fftconvolve
from scipy.stats import gaussian_kde

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "investigacion"))
import comparacion_metodos as CM  # noqa: E402  (agrega src/ y src/multiciudad/ a la ruta)
import evaluar_rutas as E  # noqa: E402
import preparar as PR  # noqa: E402
import rasgos_delitos as RD  # noqa: E402
from ciudades import DESARROLLO, EXAMEN, carpeta, carpeta_publica  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

SEMILLA = 20261011
LISTA = list(FRANJAS)
FRANJA_DE_HORA = {h: f for f, hs in FRANJAS.items() for h in hs}


# --------------------------------------------------------------------------------------
# Densidad con pesos y con nucleo isotropico (misma grilla y convolucion que comparacion_metodos)
class Exacta:
    """Densidad exacta de un KDE gaussiano con covarianza 'cov' y pesos (para el control de la grilla)."""

    def __init__(self, puntos, pesos, cov):
        self.p, self.w = puntos, pesos / pesos.sum()
        self.inv, self.norm = np.linalg.inv(cov), 1 / (2 * np.pi * np.sqrt(np.linalg.det(cov)))

    def __call__(self, q):
        q = np.asarray(q).T
        salida = np.zeros(len(q))
        for i in range(0, len(q), 50):
            d = q[i:i + 50, None, :] - self.p[None, :, :]
            m = np.einsum("abi,ij,abj->ab", d, self.inv, d)
            salida[i:i + 50] = (np.exp(-0.5 * m) * self.w[None, :]).sum(1) * self.norm
        return salida


def densidad(crimenes, puntos, pesos=None, isotropo=False):
    pesos = np.ones(len(crimenes)) if pesos is None else np.asarray(pesos, float)
    kde = gaussian_kde(crimenes.T, bw_method="scott", weights=pesos)
    cov = kde.covariance
    if isotropo:
        cov = np.eye(2) * np.trace(cov) / 2
    sd = np.sqrt(np.diag(cov))
    pad = 4 * sd.max()
    lo = np.minimum(crimenes.min(0), puntos.min(0)) - pad
    hi = np.maximum(crimenes.max(0), puntos.max(0)) + pad
    n = np.ceil((hi - lo) / CM.CELDA).astype(int) + 1
    H, _, _ = np.histogram2d(crimenes[:, 0], crimenes[:, 1], bins=n, weights=pesos,
                             range=[[lo[0], lo[0] + n[0] * CM.CELDA], [lo[1], lo[1] + n[1] * CM.CELDA]])
    H /= pesos.sum()
    k = np.ceil(4 * sd / CM.CELDA).astype(int)
    X, Y = np.meshgrid(np.arange(-k[0], k[0] + 1) * CM.CELDA, np.arange(-k[1], k[1] + 1) * CM.CELDA, indexing="ij")
    inv = np.linalg.inv(cov)
    nucleo = np.exp(-0.5 * (inv[0, 0] * X ** 2 + 2 * inv[0, 1] * X * Y + inv[1, 1] * Y ** 2)) \
        / (2 * np.pi * np.sqrt(np.linalg.det(cov)))
    D = np.clip(fftconvolve(H, nucleo, mode="same"), 0, None)
    fx = (puntos[:, 0] - lo[0]) / CM.CELDA - 0.5
    fy = (puntos[:, 1] - lo[1]) / CM.CELDA - 0.5
    return map_coordinates(D, [fx, fy], order=1, mode="nearest"), Exacta(crimenes, pesos, cov)


def riesgos(Gp, crimenes, pesos, isotropo, rng):
    """comparacion_metodos.riesgo_tramos con esta densidad (pesos / isotropico)."""
    original = CM.densidad
    CM.densidad = lambda c, p: densidad(c, p, pesos, isotropo)
    try:
        r, control = CM.riesgo_tramos(Gp, crimenes, rng)
    finally:
        CM.densidad = original
    if control >= 0.01:
        sys.exit(f"La densidad en grilla no paso el control ({control:.4%} >= 1%). No se sigue.")
    return r, control


def ancho(crimenes, pesos=None):
    kde = gaussian_kde(crimenes.T, bw_method="scott", weights=pesos)
    sd = np.sqrt(np.diag(kde.covariance))
    return {"ancho_x_m": float(sd[0]), "ancho_y_m": float(sd[1]), "ancho_isotropico_m": float(np.sqrt(np.trace(kde.covariance) / 2)),
            "delitos": int(len(crimenes)), "factor_scott": float(kde.factor)}


# --------------------------------------------------------------------------------------
# Delitos del pasado con su franja
def delitos_pasados(ciudad, grupo, Gp, cfg, ex=None):
    if grupo is None:   # practica: ya preparados
        d = pd.read_csv(carpeta(ciudad) / "delitos_tramo.csv", dtype={"clase_nucleo": str})
    else:
        pub = carpeta_publica(ciudad)
        crudo = ex.leer_examen(ciudad, grupo)
        d = PR.normalizar(crudo, ciudad, True)
        limite = gpd.read_file(pub / "limite.geojson").to_crs(cfg["crs"]).geometry.iloc[0]
        lugares = gpd.read_file(pub / "osm.gpkg", layer="lugares")
        d = PR.asignar(d, Gp, limite, lugares, cfg["crs"])
    d = d[(d["motivo_exclusion"] == "ninguno") & (d["fecha"] >= RD.PASADO[0]) & (d["fecha"] <= RD.PASADO[1])].copy()
    xy = gpd.GeoSeries(gpd.points_from_xy(d["lon"], d["lat"]), crs=4326).to_crs(cfg["crs"])
    d["x"], d["y"] = xy.x.values, xy.y.values
    d["franja"] = d["hora"].map(FRANJA_DE_HORA)
    d["desconocida"] = d["hora_desconocida"].astype(str).str.lower().isin(["true", "1"])
    return d


def por_franja(d, f):
    """Puntos y pesos de la franja f: los de esa hora (peso 1) y los de hora desconocida (peso 1/4)."""
    m = (~d["desconocida"] & (d["franja"] == f)) | d["desconocida"]
    s = d[m]
    return np.c_[s["x"].values, s["y"].values], np.where(s["desconocida"], 1 / len(LISTA), 1.0)


# --------------------------------------------------------------------------------------
def correr_envolvente(Gp, r, lista, salida, etiqueta):
    nodos, nombres, arrays = CM.red_de(Gp, r)
    archivo = salida / f"_red_{etiqueta}.npz"
    np.savez(archivo, **arrays)
    tareas = [(i, nodos[o], nodos[d], h) for i, o, d, h in lista]
    with Pool(CM.PROCESOS, initializer=CM._iniciar, initargs=(str(archivo),)) as pool:
        res = [x for x in pool.imap_unordered(CM._un_viaje, tareas, chunksize=10) if x is not None]
    archivo.unlink()
    g = pd.DataFrame(res).set_index("viaje").sort_index()
    for col in ["corta", "elegida"]:
        g[col] = [[nombres[t] for t in ids] for ids in g[col]]
    return g


def comparar_ciudad(ciudad, grupo, carpeta_res, viajes, salida, ex=None):
    cfg = EXAMEN.get(ciudad) or DESARROLLO[ciudad]
    rng = np.random.default_rng(SEMILLA + zlib.crc32(ciudad.encode()))
    red_archivo = carpeta_publica(ciudad) / "red_peatonal.graphml"
    G = ox.load_graphml(red_archivo)
    Gp = ox.project_graph(G, to_crs=cfg["crs"])
    lista = E.tareas(red_archivo, ciudad, n=viajes)
    Gz = ox.project_graph(G)
    zonas = pd.Series({i: f"{int(Gz.nodes[o]['x'] // 1000)}_{int(Gz.nodes[o]['y'] // 1000)}" for i, o, _, _ in lista})
    fut = CM.futuro_de(carpeta_res, ciudad)
    d = delitos_pasados(ciudad, grupo, Gp, cfg, ex)
    conjuntos = {"nucleo": d[d["clase_nucleo"].notna()], "todos": d}
    anchos, controles, tabla = [], [], {}
    for var, dv in conjuntos.items():
        pts = np.c_[dv["x"].values, dv["y"].values]
        anchos.append({"ciudad": ciudad, "conjunto": var, "franja": "todas", **ancho(pts)})
        # (1) isotropico: un riesgo (sin hora), como el original
        r, control = riesgos(Gp, pts, None, True, rng)
        controles.append({"ciudad": ciudad, "variante": f"isotropico_{var}", "control": control})
        for etiqueta, clave in [(f"G16i_{var}", "vertices"), (f"G16ui_{var}", "uniforme")]:
            g = correr_envolvente(Gp, r[clave], lista, salida, f"{ciudad}_{etiqueta}")
            g["franja"] = [FRANJA_DE_HORA[h] for h in g["hora"]]
            tabla[etiqueta] = pd.DataFrame({"a": [CM.delitos(ids, f, fut) for ids, f in zip(g["corta"], g["franja"])],
                                            "b": [CM.delitos(ids, f, fut) for ids, f in zip(g["elegida"], g["franja"])]},
                                           index=g.index)
            print(f"  {ciudad} {etiqueta}: listo", flush=True)
        # (2) por franja: un riesgo por franja; cada viaje usa el de la suya
        partes = {f"G16f_{var}": [], f"G16uf_{var}": []}
        for f in LISTA:
            pf, wf = por_franja(dv, f)
            anchos.append({"ciudad": ciudad, "conjunto": var, "franja": f, **ancho(pf, wf)})
            r, control = riesgos(Gp, pf, wf, False, rng)
            controles.append({"ciudad": ciudad, "variante": f"franja_{f}_{var}", "control": control})
            de_f = [t for t in lista if FRANJA_DE_HORA[t[3]] == f]
            for etiqueta, clave in [(f"G16f_{var}", "vertices"), (f"G16uf_{var}", "uniforme")]:
                g = correr_envolvente(Gp, r[clave], de_f, salida, f"{ciudad}_{etiqueta}_{f}")
                partes[etiqueta].append(pd.DataFrame({"a": [CM.delitos(ids, f, fut) for ids in g["corta"]],
                                                      "b": [CM.delitos(ids, f, fut) for ids in g["elegida"]]}, index=g.index))
        for etiqueta, ps in partes.items():
            tabla[etiqueta] = pd.concat(ps).sort_index()
            print(f"  {ciudad} {etiqueta}: listo", flush=True)
    for m in ["A", "B"]:
        tabla[m], _ = CM.nuestros_por_viaje(carpeta_res, ciudad, m, viajes, fut)
    comunes = None
    for t in tabla.values():
        comunes = t.index if comunes is None else comunes.intersection(t.index)
    junta = pd.concat({k: t.loc[comunes] for k, t in tabla.items()}, axis=1)
    junta.columns = [f"{c}_{k}" for k, c in junta.columns]
    res = CM.intervalos(junta, zonas, rng, list(tabla))
    resumen = [{"ciudad": ciudad, "metodo": m, "viajes_comunes": len(comunes), "cambio_todos_los_viajes": x["cambio"],
                "ic95_zonas_1km": CM.ic(x["boot_z"])} for m, x in res.items()]
    pares = []
    for metodo in [k for k in tabla if k.startswith("G16")]:
        nuestro = "A" if metodo.endswith("nucleo") else "B"
        dz = res[nuestro]["boot_z"] - res[metodo]["boot_z"]
        pares.append({"ciudad": ciudad, "nuestro": nuestro, "publicado": metodo,
                      "diferencia_pp": res[nuestro]["cambio"] - res[metodo]["cambio"], "ic95_zonas_1km": CM.ic(dz)})
    return resumen, pares, anchos, controles


def main():
    accion = sys.argv[1]
    if accion == "ensayo":
        salida = RAIZ / "data/practice/revision"
        ciudades = {"gainesville": (None, RAIZ / "data/practice/ensayo_examen", 100)}
        ex = None
    else:
        salida = RAIZ / "investigacion/resultados/revision"
        ciudades = CM.CIUDADES_EXAMEN
        ex = CM._examen()
    salida.mkdir(parents=True, exist_ok=True)
    resumen, pares, anchos, controles = [], [], [], []
    for ciudad, (grupo, carpeta_res, viajes) in ciudades.items():
        print(f"=== {ciudad}", flush=True)
        r, p, a, c = comparar_ciudad(ciudad, grupo, carpeta_res, viajes, salida, ex)
        resumen += r; pares += p; anchos += a; controles += c
        pd.DataFrame(resumen).to_csv(salida / "r10_g16_cambio_todos.csv", index=False)
        pd.DataFrame(pares).to_csv(salida / "r10_g16_pareadas.csv", index=False)
        pd.DataFrame(anchos).to_csv(salida / "r10_g16_anchos.csv", index=False)
        pd.DataFrame(controles).to_csv(salida / "r10_g16_controles.csv", index=False)
    pd.set_option("display.width", 250)
    print("\n" + pd.DataFrame(resumen).round(1).to_string(index=False))
    print("\n(diferencia = nuestro - publicado; negativo = el nuestro evita mas)\n" + pd.DataFrame(pares).round(1).to_string(index=False))
    print("\n" + pd.DataFrame(anchos).round(1).to_string(index=False))


if __name__ == "__main__":
    main()
