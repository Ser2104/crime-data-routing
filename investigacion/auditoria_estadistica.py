"""
AUDITORIA ESTADISTICA de los examenes de la formula v2 (EXPLORATORIA, posterior a ver los
resultados; no reemplaza nada de lo registrado). Usa solo lo que los examenes ya guardaron:
los viajes de cada mapa (<ciudad>_viajes_<mapa>_2000.jsonl) y los delitos del futuro por
tramo (<ciudad>_mapa_delitos.csv). No abre ninguna caja fuerte.

Preguntas:
 1. Intervalos que respetan la cercania entre viajes. El intervalo registrado remuestrea
    viajes como si fueran independientes. Aqui se remuestrean ZONAS de origen (1 y 2 km,
    con todos sus viajes), y ademas se agrega el azar de los delitos (cada conteo del
    futuro se vuelve a sortear con Poisson, el mismo sorteo para todos los viajes que
    pasan por ese tramo).
 2. Efecto sobre TODOS los viajes. El registrado se mide solo donde la app ofrece una
    ruta de menor riesgo. Aqui, cada viaje toma la ruta de menor riesgo si existe y la
    mas rapida si no; se compara con tomar siempre la mas rapida.
 3. Cuanto se superponen los viajes: tramos distintos usados, viajes por tramo y parte
    de los delitos de las rutas rapidas que esta en tramos compartidos por muchos viajes.
 4. Comparaciones pareadas registradas (H2, H3b) con remuestreo por zonas.

Ejecutar desde la carpeta del proyecto:
    python investigacion/auditoria_estadistica.py
Salida: investigacion/resultados/auditoria/ (tablas) y resumen en pantalla.
"""
import sys
from pathlib import Path

import numpy as np
import osmnx as ox
import pandas as pd
from scipy.sparse import csr_matrix

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src" / "multiciudad"))
import evaluar_rutas as E  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

CIUDADES = {"filadelfia": "investigacion/resultados/examen_v2", "baton_rouge": "investigacion/resultados/examen_v2",
            "tempe": "investigacion/resultados/examen_v2_tempe"}
MAPAS = ["B", "A", "C", "zona", "totales", "sin_delitos", "solo_mapa", "mapa_de_calor_A", "mapa_de_calor_B",
         "evitar_avenidas", "evitar_comercios", "oraculo"]
PAREJAS = [("mapa_de_calor_A", "A"), ("mapa_de_calor_B", "B"), ("evitar_avenidas", "sin_delitos"),
           ("evitar_comercios", "sin_delitos")]
REMUESTREOS = 2000
POISSON = 1000
SALIDA = RAIZ / "investigacion/resultados/auditoria"
LISTA_FRANJAS = list(FRANJAS)


def zonas_de_origen(ciudad):
    """Zona de 1 y 2 km del ORIGEN de cada viaje (mismos viajes que el examen)."""
    red = RAIZ / "data/public_features" / ciudad / "red_peatonal.graphml"
    lista = E.tareas(red, ciudad)
    G = ox.project_graph(ox.load_graphml(red))
    filas = []
    for i, o, _, _ in lista:
        x, y = G.nodes[o]["x"], G.nodes[o]["y"]
        filas.append((i, f"{int(x // 1000)}_{int(y // 1000)}", f"{int(x // 2000)}_{int(y // 2000)}"))
    return pd.DataFrame(filas, columns=["viaje", "zona1", "zona2"]).set_index("viaje")


class Rutas:
    """Rutas mas rapida y de menor riesgo de un mapa, con sus tramos (matriz dispersa)."""

    def __init__(self, archivo, columnas):
        v = pd.read_json(archivo, lines=True)
        v = v[~v["relleno"] & v["etiqueta"].isin(["Fastest", "Lowest risk"])]
        v = v.drop_duplicates(["viaje", "etiqueta"])
        self.v = v.reset_index(drop=True)
        filas, cols = [], []
        for k, (ids, f) in enumerate(zip(self.v["ids"], self.v["franja"])):
            j = columnas.get_indexer([f"{t}|{f}" for t in ids])
            j = j[j >= 0]
            filas.extend([k] * len(j))
            cols.extend(j)
        self.M = csr_matrix((np.ones(len(filas)), (filas, cols)), shape=(len(self.v), len(columnas)))

    def por_viaje(self, fut):
        """Tabla por viaje: delitos en la mas rapida (a) y en la de menor riesgo (b, NaN si no hay)."""
        s = self.v.assign(d=self.M @ fut).pivot_table(index="viaje", columns="etiqueta", values="d", aggfunc="first")
        return s.reindex(columns=["Fastest", "Lowest risk"])


def cambio(a, b):
    return b.sum() / max(a.sum(), 1e-12) - 1


def ic(valores):
    return [float(np.nanpercentile(valores, 2.5) * 100), float(np.nanpercentile(valores, 97.5) * 100)]


def remuestreo_zonas(a, b, zonas, rng, n=REMUESTREOS):
    """IC del cambio remuestreando zonas (cada zona entra con todos sus viajes)."""
    df = pd.DataFrame({"a": a, "b": b, "z": zonas}).groupby("z")[["a", "b"]].sum()
    A, B = df["a"].values, df["b"].values
    idx = rng.integers(0, len(df), (n, len(df)))
    return B[idx].sum(1) / np.maximum(A[idx].sum(1), 1e-12) - 1


def auditar(ciudad, carpeta, rng):
    carpeta = RAIZ / carpeta
    mapa = pd.read_csv(carpeta / f"{ciudad}_mapa_delitos.csv", index_col="tramo_id")
    largo = mapa[[f"fut_{f}" for f in LISTA_FRANJAS]].stack()
    columnas = pd.Index([f"{t}|{f.replace('fut_', '')}" for t, f in largo.index])
    fut = largo.values.astype(float)
    zonas = zonas_de_origen(ciudad)
    filas, pareadas, superposicion = [], [], {}
    rutas = {m: Rutas(carpeta / f"{ciudad}_viajes_{m}_2000.jsonl", columnas) for m in MAPAS}
    tablas = {m: r.por_viaje(fut) for m, r in rutas.items()}
    # Delitos del futuro re-sorteados (Poisson), el mismo sorteo para todos los mapas
    usados = np.unique(np.concatenate([r.M.indices for r in rutas.values()]))
    sorteos = rng.poisson(fut[usados], (POISSON, len(usados))).astype(float)

    for m in MAPAS:
        t = tablas[m]
        con = t.dropna()   # viajes con ruta de menor riesgo (lo registrado)
        if len(con) == 0 or con["Fastest"].sum() == 0:
            filas.append({"ciudad": ciudad, "mapa": m, "estado": "N.A."})
            continue
        a, b = con["Fastest"].values, con["Lowest risk"].values
        z1, z2 = zonas["zona1"].reindex(con.index).values, zonas["zona2"].reindex(con.index).values
        idx = rng.integers(0, len(con), (REMUESTREOS, len(con)))
        viajes = b[idx].sum(1) / np.maximum(a[idx].sum(1), 1e-12) - 1
        # zonas de 1 km + delitos re-sorteados
        fut_p = fut.copy()
        zpois = []
        r = rutas[m]
        for k in range(POISSON):
            fut_p[usados] = sorteos[k]
            tp = r.por_viaje(fut_p).reindex(con.index)
            zpois.append(remuestreo_zonas(tp["Fastest"].values, tp["Lowest risk"].values, z1, rng, n=1)[0])
        # todos los viajes: ruta de menor riesgo si existe, si no la mas rapida
        todos = t.dropna(subset=["Fastest"])
        elegida = todos["Lowest risk"].fillna(todos["Fastest"])
        zt = zonas["zona1"].reindex(todos.index).values
        filas.append({
            "ciudad": ciudad, "mapa": m, "viajes_con_alternativa": len(con), "viajes_total": len(todos),
            "cambio_pct": cambio(a, b) * 100,
            "ic95_viajes": ic(viajes), "ic95_zonas_1km": ic(remuestreo_zonas(a, b, z1, rng)),
            "ic95_zonas_2km": ic(remuestreo_zonas(a, b, z2, rng)), "ic95_zonas_1km_y_poisson": ic(np.array(zpois)),
            "todos_cambio_pct": cambio(todos["Fastest"].values, elegida.values) * 100,
            "todos_ic95_zonas_1km": ic(remuestreo_zonas(todos["Fastest"].values, elegida.values, zt, rng)),
            "parte_delitos_rapidas_en_viajes_con_alternativa": float(a.sum() / max(todos["Fastest"].sum(), 1e-12)),
        })
    # superposicion de las rutas mas rapidas (iguales en todos los mapas: se usa B)
    rap = rutas["B"].v["etiqueta"].values == "Fastest"
    Mr = rutas["B"].M[rap]
    viajes_por_tramo = np.asarray((Mr > 0).sum(0)).ravel()
    usados_r = viajes_por_tramo > 0
    delitos_tramo = fut * viajes_por_tramo   # delitos contados en las rutas rapidas, por tramo y franja
    superposicion = {"ciudad": ciudad, "tramos_franja_usados": int(usados_r.sum()),
                     "viajes_por_tramo_mediana": float(np.median(viajes_por_tramo[usados_r])),
                     "viajes_por_tramo_max": int(viajes_por_tramo.max()),
                     "parte_delitos_en_tramos_con_5_o_mas_viajes": float(delitos_tramo[viajes_por_tramo >= 5].sum()
                                                                         / max(delitos_tramo.sum(), 1e-12))}
    # comparaciones pareadas registradas, remuestreando zonas de 1 km
    for base, otro in PAREJAS:
        comunes = tablas[base].dropna().index.intersection(tablas[otro].dropna().index)
        if len(comunes) == 0:
            pareadas.append({"ciudad": ciudad, "base": base, "otro": otro, "estado": "N.A."})
            continue
        tb, to = tablas[base].loc[comunes], tablas[otro].loc[comunes]
        z = zonas["zona1"].reindex(comunes).values
        df = pd.DataFrame({"ab": tb["Fastest"].values, "bb": tb["Lowest risk"].values,
                           "ao": to["Fastest"].values, "bo": to["Lowest risk"].values, "z": z}).groupby("z").sum()
        idx = rng.integers(0, len(df), (REMUESTREOS, len(df)))
        s = lambda c: df[c].values[idx].sum(1)
        dif = (s("bo") / np.maximum(s("ao"), 1e-12) - s("bb") / np.maximum(s("ab"), 1e-12))
        punto = cambio(to["Fastest"].values, to["Lowest risk"].values) - cambio(tb["Fastest"].values, tb["Lowest risk"].values)
        pareadas.append({"ciudad": ciudad, "base": base, "otro": otro, "viajes": len(comunes),
                         "diferencia_pp": punto * 100, "ic95_zonas_1km": ic(dif)})
    return filas, pareadas, superposicion


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261008)
    todas, pares, sup = [], [], []
    for ciudad, carpeta in CIUDADES.items():
        print(f"=== {ciudad}", flush=True)
        f, p, s = auditar(ciudad, carpeta, rng)
        todas += f
        pares += p
        sup.append(s)
    pd.DataFrame(todas).to_csv(SALIDA / "intervalos_y_todos_los_viajes.csv", index=False)
    pd.DataFrame(pares).to_csv(SALIDA / "pareadas_por_zonas.csv", index=False)
    pd.DataFrame(sup).to_csv(SALIDA / "superposicion.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    t = pd.DataFrame(todas)
    fmt = lambda x: f"{x[0]:+.0f} a {x[1]:+.0f}" if isinstance(x, list) else "-"
    for c in ["ic95_viajes", "ic95_zonas_1km", "ic95_zonas_2km", "ic95_zonas_1km_y_poisson", "todos_ic95_zonas_1km"]:
        t[c] = t[c].map(fmt)
    print(t[["ciudad", "mapa", "cambio_pct", "ic95_viajes", "ic95_zonas_1km", "ic95_zonas_2km", "ic95_zonas_1km_y_poisson",
             "todos_cambio_pct", "todos_ic95_zonas_1km", "viajes_con_alternativa"]].round(1).to_string(index=False))
    p = pd.DataFrame(pares)
    p["ic95_zonas_1km"] = p["ic95_zonas_1km"].map(fmt)
    print("\n" + p.round(1).to_string(index=False))
    print("\n" + pd.DataFrame(sup).round(3).to_string(index=False))
    print(f"\nTablas en {SALIDA}", flush=True)


if __name__ == "__main__":
    main()
