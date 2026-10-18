"""
ANALISIS DE TRANSPORTE (exploratorios) para la version TR-C del articulo. Implementa el
plan fijado antes en investigacion/analisis_transporte.md (commit 140a8b6). No abre
ninguna caja: usa los mapas de riesgo y los delitos del futuro que el examen ya guardo.

    python investigacion/analisis_transporte.py ensayo      Gainesville (practica), 50 viajes
    python investigacion/analisis_transporte.py curva       A. curva costo-beneficio (3 ciudades)
    python investigacion/analisis_transporte.py sistema     B. concentracion de peatones
    python investigacion/analisis_transporte.py tiempos     C. costo de calculo
Salida: investigacion/resultados/transporte/ (ensayo: data/practice/transporte/)
"""
import json
import platform
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import osmnx as ox
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src" / "multiciudad"))
import evaluar_rutas as E  # noqa: E402
import rutas as R  # noqa: E402
from ciudades import carpeta_publica  # noqa: E402

LIMITES = [2, 5, 10]                       # minutos extra exactos
MAPAS = ["B", "sin_delitos", "oraculo"]
SEMILLA = 20261010
REMUESTREOS = 2000
CIUDADES = {"filadelfia": RAIZ / "investigacion/resultados/examen_v2",
            "baton_rouge": RAIZ / "investigacion/resultados/examen_v2",
            "tempe": RAIZ / "investigacion/resultados/examen_v2_tempe"}
TOMADAS = ["Fastest", "Lowest risk"]


# --------------------------------------------------------------------------------------
def _iniciar_con_limite(nombre, red, riesgo, limite):
    """El inicializador del examen + un limite de tiempo extra fijo (el resto del buscador igual)."""
    E._iniciar(nombre, red, riesgo)
    R.MAX_EXTRA = 0.0
    R.MAX_EXTRA_MIN = float(limite)


def simular_con_limite(nombre, red, riesgo, lista, limite):
    with Pool(E.PROCESOS, initializer=_iniciar_con_limite, initargs=(nombre, str(red), str(riesgo), limite)) as pool:
        filas = [r for rs in pool.imap_unordered(E._viaje, lista, chunksize=10) for r in rs]
    return pd.DataFrame(filas)


def futuro_de(carpeta, ciudad):
    m = pd.read_csv(carpeta / f"{ciudad}_mapa_delitos.csv", index_col="tramo_id")
    return {f: m[f"fut_{f}"] for f in ["madrugada", "manana", "tarde", "noche"]}


def por_viaje(v, fut):
    """Por viaje: delitos y minutos de la mas rapida y de la que toma la persona
    (la de menor riesgo si la app la ofrece; si no, la mas rapida)."""
    v = v[~v["relleno"] & v["etiqueta"].isin(TOMADAS)].drop_duplicates(["viaje", "etiqueta"]).copy()
    v["d"] = [float(fut[f].reindex(ids).fillna(0).sum()) for ids, f in zip(v["ids"], v["franja"])]
    d = v.pivot_table(index="viaje", columns="etiqueta", values="d", aggfunc="first").reindex(columns=TOMADAS)
    m = v.pivot_table(index="viaje", columns="etiqueta", values="minutos", aggfunc="first").reindex(columns=TOMADAS)
    ok = d["Fastest"].notna()
    d, m = d[ok], m[ok]
    alternativa = d["Lowest risk"].notna()
    return pd.DataFrame({"a": d["Fastest"], "b": d["Lowest risk"].where(alternativa, d["Fastest"]),
                         "extra": (m["Lowest risk"] - m["Fastest"]).where(alternativa, 0.0), "alt": alternativa})


def zonas_de(red, ciudad, n):
    lista = E.tareas(red, ciudad, n=n)
    G = ox.project_graph(ox.load_graphml(red))
    return lista, pd.Series({i: f"{int(G.nodes[o]['x'] // 1000)}_{int(G.nodes[o]['y'] // 1000)}" for i, o, _, _ in lista})


def resumen(t, zonas, rng):
    z = t.groupby(zonas.reindex(t.index).values)[["a", "b"]].sum()
    idx = rng.integers(0, len(z), (REMUESTREOS, len(z)))
    boot = (z["b"].values[idx].sum(1) / np.maximum(z["a"].values[idx].sum(1), 1e-12) - 1) * 100
    return {"viajes": len(t), "parte_con_alternativa": float(t["alt"].mean()),
            "cambio_todos": (t["b"].sum() / max(t["a"].sum(), 1e-12) - 1) * 100,
            "ic95_zonas": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "min_extra_mediana_todos": float(t["extra"].median()),
            "min_extra_mediana_con_alternativa": float(t.loc[t["alt"], "extra"].median()) if t["alt"].any() else np.nan}


# --------------------------------------------------------------------------------------
def curva(ciudades, viajes, salida, viajes_examen=2000):
    rng = np.random.default_rng(SEMILLA)
    filas = []
    for ciudad, carpeta in ciudades.items():
        red = carpeta_publica(ciudad) / "red_peatonal.graphml"
        lista, zonas = zonas_de(red, ciudad, viajes)
        fut = futuro_de(carpeta, ciudad)
        for mapa in MAPAS:
            riesgo = carpeta / f"{ciudad}_riesgo_{mapa}.csv"
            # el punto de la app: los viajes del examen (limite por defecto)
            base = pd.read_json(carpeta / f"{ciudad}_viajes_{mapa}_{viajes_examen}.jsonl", lines=True)
            base = base[base["viaje"].isin([i for i, *_ in lista])]
            filas.append({"ciudad": ciudad, "mapa": mapa, "limite": "app", **resumen(por_viaje(base, fut), zonas, rng)})
            print(f"  {ciudad} {mapa} app: {filas[-1]['cambio_todos']:+.1f}%", flush=True)
            for limite in LIMITES:
                archivo = salida / f"{ciudad}_viajes_{mapa}_limite{limite}_{viajes}.jsonl"
                if archivo.exists():
                    v = pd.read_json(archivo, lines=True)
                else:
                    v = simular_con_limite(f"tr_{ciudad}_{mapa}_{limite}", red, riesgo, lista, limite)
                    v.to_json(archivo, orient="records", lines=True)
                filas.append({"ciudad": ciudad, "mapa": mapa, "limite": str(limite), **resumen(por_viaje(v, fut), zonas, rng)})
                print(f"  {ciudad} {mapa} limite {limite} min: {filas[-1]['cambio_todos']:+.1f}% "
                      f"(mediana extra {filas[-1]['min_extra_mediana_con_alternativa']:.1f} min con alternativa)", flush=True)
                pd.DataFrame(filas).to_csv(salida / "curva.csv", index=False)
    return pd.DataFrame(filas)


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum())) if x.sum() > 0 else np.nan


def sistema(ciudades, salida):
    filas = []
    for ciudad, carpeta in ciudades.items():
        for mapa in ["B", "sin_delitos"]:
            largo = pd.read_csv(carpeta / f"{ciudad}_riesgo_{mapa}.csv", index_col="tramo_id")["length"]
            v = pd.read_json(carpeta / f"{ciudad}_viajes_{mapa}_2000.jsonl", lines=True)
            v = v[~v["relleno"] & v["etiqueta"].isin(TOMADAS)].drop_duplicates(["viaje", "etiqueta"])
            rap = v[v["etiqueta"] == "Fastest"].set_index("viaje")["ids"]
            seg = v[v["etiqueta"] == "Lowest risk"].set_index("viaje")["ids"]
            tomada = {i: (seg[i] if i in seg.index else rap[i]) for i in rap.index}   # sugerencia de la app
            for escenario, rutas_ in [("mas_rapida", rap.to_dict()), ("sugerencia_app", tomada)]:
                cuenta = pd.Series([t for ids in rutas_.values() for t in ids]).value_counts()
                metros = (cuenta * largo.reindex(cuenta.index).fillna(0)).reindex(largo.index).fillna(0)
                orden = metros.sort_values(ascending=False)
                top = int(np.ceil(0.01 * len(orden)))
                filas.append({"ciudad": ciudad, "mapa": mapa, "escenario": escenario,
                              "tramos_distintos_usados": int((metros > 0).sum()),
                              "parte_metros_en_1pct_mas_usado": float(orden.iloc[:top].sum() / orden.sum()),
                              "gini_metros": gini(metros.values)})
            print(f"  {ciudad} {mapa}: {filas[-2]} | {filas[-1]}", flush=True)
    t = pd.DataFrame(filas)
    t.to_csv(salida / "sistema.csv", index=False)
    return t


def tiempos(ciudades, salida, n=200):
    filas = []
    for ciudad, carpeta in ciudades.items():
        red = carpeta_publica(ciudad) / "red_peatonal.graphml"
        lista = E.tareas(red, ciudad, n=n)
        E._iniciar(f"tiempo_{ciudad}", str(red), str(carpeta / f"{ciudad}_riesgo_B.csv"))
        medidas = []
        for i, o, d, hora in lista:
            t0 = time.perf_counter()
            try:
                R.buscar_rutas(E._G, E._latlon(o), E._latlon(d), hora)
            except Exception:
                continue
            medidas.append(time.perf_counter() - t0)
        filas.append({"ciudad": ciudad, "tramos": E._G.number_of_edges() // 2, "consultas": len(medidas),
                      "mediana_s": float(np.median(medidas)), "p95_s": float(np.percentile(medidas, 95)),
                      "procesador": platform.processor(), "sistema": platform.platform()})
        print(f"  {ciudad}: {filas[-1]}", flush=True)
    t = pd.DataFrame(filas)
    t.to_csv(salida / "tiempos.csv", index=False)
    return t


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "ensayo"
    if accion == "ensayo":
        salida = RAIZ / "data/practice/transporte"
        salida.mkdir(parents=True, exist_ok=True)
        ciudades = {"gainesville": RAIZ / "data/practice/ensayo_examen"}
        print(curva(ciudades, 50, salida, viajes_examen=100).round(2).to_string(index=False))
        return
    salida = RAIZ / "investigacion/resultados/transporte"
    salida.mkdir(parents=True, exist_ok=True)
    if accion == "curva":
        print(curva(CIUDADES, 2000, salida).round(2).to_string(index=False))
    elif accion == "sistema":
        print(sistema(CIUDADES, salida).round(3).to_string(index=False))
    elif accion == "tiempos":
        print(tiempos(CIUDADES, salida).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
