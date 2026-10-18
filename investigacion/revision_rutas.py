"""
ANALISIS DE LA REVISION (exploratorios, posteriores al examen) que usan las rutas y los
mapas que el examen ya guardo. Plan fijado antes: investigacion/analisis_revision.md
(commit 78484c0). No abre ninguna caja ni lee los datos del examen abiertos.

    python investigacion/revision_rutas.py r1 [--ensayo]   el buscador frente a la cota de Lagrange
    python investigacion/revision_rutas.py r2 [--ensayo]   riesgo de fondo 1x y 10x (el examen: 3x)
    python investigacion/revision_rutas.py r7 [--ensayo]   por persona: pisos 25 y 75, y sin noche
    python investigacion/revision_rutas.py r8 [--ensayo]   viajes ponderados por peatones
    python investigacion/revision_rutas.py r9 [--ensayo]   modelo frente a mapa de calor (todos los viajes)
Salida: investigacion/resultados/revision/ (ensayo con Gainesville: data/practice/revision/)
"""
import math
import sys
from multiprocessing import Pool
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src" / "multiciudad"))
sys.path.insert(0, str(RAIZ / "investigacion"))
import analisis_transporte as AT  # noqa: E402
import evaluar_rutas as E  # noqa: E402
import formula as FO  # noqa: E402
import rutas as R  # noqa: E402
from ciudades import carpeta_publica  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

SEMILLA = 20261011
REMUESTREOS = 2000
CIUDADES = {"filadelfia": (RAIZ / "investigacion/resultados/examen_v2", 2000),
            "baton_rouge": (RAIZ / "investigacion/resultados/examen_v2", 2000),
            "tempe": (RAIZ / "investigacion/resultados/examen_v2_tempe", 2000)}
ENSAYO = {"gainesville": (RAIZ / "data/practice/ensayo_examen", 100)}
NIVELES = ["B", "A", "C", "zona", "totales", "sin_delitos", "solo_mapa"]
PRECIOS = [0] + list(np.geomspace(0.005, 200, 30))   # los mismos 31 precios del paso 11
FONDOS = [1, 10]
LISTA = list(FRANJAS)


# --------------------------------------------------------------------------------------
# Comunes
def futuro_tabla(carpeta, ciudad):
    m = pd.read_csv(carpeta / f"{ciudad}_mapa_delitos.csv", index_col="tramo_id")
    return m[[f"fut_{f}" for f in LISTA]]


def viajes_de(carpeta, ciudad, mapa, n):
    return pd.read_json(carpeta / f"{ciudad}_viajes_{mapa}_{n}.jsonl", lines=True)


def ic(x):
    return [float(np.nanpercentile(x, 2.5)), float(np.nanpercentile(x, 97.5))]


def medidas(v, futuro, zonas, rng):
    """Las dos medidas de rutas: la registrada (viajes con alternativa, IC por viajes con la
    semilla 1 del examen) y sobre todos los viajes (IC por zonas de 1 km)."""
    reg = E.calificar(v, futuro)
    t = AT.por_viaje(v, {f: futuro[f"fut_{f}"] for f in LISTA})
    todos = AT.resumen(t, zonas, rng)
    return {"cambio_registrado": reg.get("cambio_pct", np.nan), "ic95_registrado": reg.get("ic95", [np.nan, np.nan]),
            "viajes_con_alternativa": reg["viajes_con_menor_riesgo"], "min_extra_mediana": reg.get("min_extra_mediana", np.nan),
            "cambio_todos": todos["cambio_todos"], "ic95_todos_zonas": todos["ic95_zonas"],
            "parte_con_alternativa": todos["parte_con_alternativa"]}


# --------------------------------------------------------------------------------------
# R1: el buscador frente a la cota de Lagrange (metodo del paso 11, con la configuracion del examen)
def _exposicion_y_minutos(G, o, d, franja, fondo, mu):
    costo = lambda p: (p[franja] + fondo) * p["length"] / 1000 + mu * p["segundos"] / 60
    nodos = nx.shortest_path(G, o, d, weight=lambda u, v, par: min(costo(p) for p in par.values()))
    tramos = [min(G[u][v].values(), key=costo) for u, v in zip(nodos[:-1], nodos[1:])]
    return (sum((p[franja] + fondo) * p["length"] / 1000 for p in tramos), sum(p["segundos"] for p in tramos) / 60)


def _viaje_r1(tarea):
    i, o, d, hora = tarea
    G = E._G
    try:
        rutas = R.buscar_rutas(G, E._latlon(o), E._latlon(d), hora)
    except (ValueError, nx.NetworkXNoPath):
        return None
    franja = R.franja_de(hora)
    fondo = G.graph["fondo"][franja]
    rapida = rutas[0]
    limite = rapida["minutos"] + max(rapida["minutos"] * R.MAX_EXTRA, R.MAX_EXTRA_MIN)
    segura = [r for r in rutas if r.get("etiqueta") == "Lowest risk" and not r.get("relleno")]
    e_app = segura[0]["riesgo"] if segura else rapida["riesgo"]   # la que toma la persona
    on, dn = R.nodo_cercano(G, *E._latlon(o)), R.nodo_cercano(G, *E._latlon(d))
    escala = rapida["riesgo"] / max(rapida["minutos"], 0.1)
    piso, mejor = -math.inf, math.inf
    for k in PRECIOS:
        mu = escala * k
        e, t = _exposicion_y_minutos(G, on, dn, franja, fondo, mu)
        piso = max(piso, e + mu * (t - limite))
        if t <= limite:
            mejor = min(mejor, e)
    base = rapida["riesgo"] / 100   # 1 punto del % frente a la mas rapida
    return {"viaje": i, "franja": franja, "con_alternativa": bool(segura), "minutos_rapida": rapida["minutos"],
            "brecha_app": (e_app - piso) / base, "brecha_precios": (mejor - piso) / base,
            "mejora_perdida": max(0.0, (e_app - mejor) / base)}


def r1(ciudades, salida):
    filas = []
    for ciudad, (carpeta, n) in ciudades.items():
        red = carpeta_publica(ciudad) / "red_peatonal.graphml"
        lista = E.tareas(red, ciudad, n=n)
        for mapa in ["B", "sin_delitos"]:
            riesgo = carpeta / f"{ciudad}_riesgo_{mapa}.csv"
            with Pool(E.PROCESOS, initializer=E._iniciar, initargs=(f"r1_{ciudad}_{mapa}", str(red), str(riesgo))) as pool:
                res = [x for x in pool.imap_unordered(_viaje_r1, lista, chunksize=5) if x]
            df = pd.DataFrame(res).sort_values("viaje")
            df.to_csv(salida / f"r1_{ciudad}_{mapa}.csv", index=False)
            b = df["brecha_app"]
            filas.append({"ciudad": ciudad, "mapa": mapa, "viajes": len(df), "con_alternativa": float(df["con_alternativa"].mean()),
                          "brecha_mediana": float(b.median()), "brecha_p95": float(b.quantile(0.95)),
                          "parte_brecha_hasta_1": float((b <= 1).mean()), "parte_brecha_hasta_3": float((b <= 3).mean()),
                          "brecha_mediana_con_alternativa": float(b[df["con_alternativa"]].median()),
                          "parte_mejora_perdida_3": float((df["mejora_perdida"] >= 3).mean()),
                          "brecha_precios_p95": float(df["brecha_precios"].quantile(0.95))})
            print(f"  {ciudad} {mapa}: {filas[-1]}", flush=True)
            pd.DataFrame(filas).to_csv(salida / "r1_buscador.csv", index=False)
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# R2: riesgo de fondo
def _iniciar_fondo(nombre, red, riesgo, veces):
    E.FONDO_VECES = veces
    E._iniciar(nombre, red, riesgo)


def r2(ciudades, salida):
    rng = np.random.default_rng(SEMILLA)
    filas = []
    for ciudad, (carpeta, n) in ciudades.items():
        red = carpeta_publica(ciudad) / "red_peatonal.graphml"
        lista, zonas = AT.zonas_de(red, ciudad, n)
        futuro = futuro_tabla(carpeta, ciudad)
        for mapa in ["B", "sin_delitos"]:
            riesgo = carpeta / f"{ciudad}_riesgo_{mapa}.csv"
            filas.append({"ciudad": ciudad, "mapa": mapa, "fondo": 3,
                          **medidas(viajes_de(carpeta, ciudad, mapa, n), futuro, zonas, rng)})
            for veces in FONDOS:
                archivo = salida / f"r2_{ciudad}_viajes_{mapa}_fondo{veces}_{n}.jsonl"
                if archivo.exists():
                    v = pd.read_json(archivo, lines=True)
                else:
                    with Pool(E.PROCESOS, initializer=_iniciar_fondo,
                              initargs=(f"r2_{ciudad}_{mapa}_{veces}", str(red), str(riesgo), veces)) as pool:
                        v = pd.DataFrame([r for rs in pool.imap_unordered(E._viaje, lista, chunksize=10) for r in rs])
                    v.to_json(archivo, orient="records", lines=True)
                filas.append({"ciudad": ciudad, "mapa": mapa, "fondo": veces, **medidas(v, futuro, zonas, rng)})
                print(f"  {ciudad} {mapa} fondo {veces}x: registrado {filas[-1]['cambio_registrado']:+.1f}% "
                      f"| todos {filas[-1]['cambio_todos']:+.1f}%", flush=True)
                pd.DataFrame(filas).to_csv(salida / "r2_fondo.csv", index=False)
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# R7: medida por persona (piso en otros percentiles, y sin las franjas de noche)
def por_persona(v, futuro, personas, cuantil=0.5, franjas=None):
    """Como evaluar_rutas.calificar (misma semilla 1 y mismo remuestreo), con otro piso o solo
    algunas franjas."""
    rng = np.random.default_rng(1)
    v = v[~v["relleno"]].copy()
    if franjas is not None:
        v = v[v["franja"].isin(franjas)]
    tasa = {}
    for f in LISTA:
        gente = personas[f"pea_{f}"].reindex(futuro.index).fillna(0)
        piso = gente[gente > 0].quantile(cuantil)
        tasa[f] = futuro[f"fut_{f}"] / np.maximum(gente, piso)
    v["pp"] = [tasa[f].reindex(ids).fillna(0).sum() for f, ids in zip(v["franja"], v["ids"])]
    v["d"] = [futuro[f"fut_{f}"].reindex(ids).fillna(0).sum() for f, ids in zip(v["franja"], v["ids"])]
    rap = v[v["etiqueta"] == "Fastest"].set_index("viaje")
    seg = v[v["etiqueta"] == "Lowest risk"].set_index("viaje")
    c = seg.index.intersection(rap.index)
    a, b = rap.loc[c, "d"].values, seg.loc[c, "d"].values
    if not len(c) or a.sum() <= 0:
        return {"viajes": len(c), "por_persona_pct": np.nan, "ic95": [np.nan, np.nan]}
    m = rng.integers(0, len(c), (2000, len(c)))   # el mismo remuestreo que calificar()
    pa, pb = rap.loc[c, "pp"].values, seg.loc[c, "pp"].values
    boot = pb[m].sum(1) / np.maximum(pa[m].sum(1), 1e-12) - 1
    return {"viajes": len(c), "por_persona_pct": (pb.sum() / pa.sum() - 1) * 100,
            "ic95": [np.percentile(boot, 2.5) * 100, np.percentile(boot, 97.5) * 100]}


def r7(ciudades, salida):
    filas = []
    for ciudad, (carpeta, n) in ciudades.items():
        futuro = futuro_tabla(carpeta, ciudad)
        publicos = FO.leer_publicos(carpeta_publica(ciudad))
        personas = publicos[[f"peatones_{f}" for f in LISTA]].rename(columns=lambda c: c.replace("peatones_", "pea_"))
        for mapa in NIVELES:
            archivo = carpeta / f"{ciudad}_viajes_{mapa}_{n}.jsonl"
            if not archivo.exists():
                continue
            v = pd.read_json(archivo, lines=True)
            registrado = pd.read_json(carpeta / f"{ciudad}_rutas_{mapa}_{n}.json", typ="series")
            control = por_persona(v, futuro, personas)
            filas.append({"ciudad": ciudad, "mapa": mapa, "variante": "mediana (registrada)", **control,
                          "reproduce_el_registrado": bool(np.isclose(control["por_persona_pct"],
                                                                     registrado.get("por_persona_pct", np.nan), equal_nan=True))})
            for nombre, kw in [("percentil 25", {"cuantil": 0.25}), ("percentil 75", {"cuantil": 0.75}),
                               ("sin noche", {"franjas": ["manana", "tarde"]})]:
                filas.append({"ciudad": ciudad, "mapa": mapa, "variante": nombre, **por_persona(v, futuro, personas, **kw)})
            print(f"  {ciudad} {mapa}: " + " | ".join(f"{f['variante']} {f['por_persona_pct']:+.1f}%" for f in filas[-4:]), flush=True)
    t = pd.DataFrame(filas)
    t.to_csv(salida / "r7_por_persona.csv", index=False)
    if "reproduce_el_registrado" in t and not t["reproduce_el_registrado"].dropna().all():
        print("ATENCION: la variante registrada no reproduce el valor del examen", flush=True)
    return t


# --------------------------------------------------------------------------------------
# R8: viajes ponderados por los peatones simulados a lo largo de su ruta mas rapida
def r8(ciudades, salida):
    rng = np.random.default_rng(SEMILLA)
    filas = []
    for ciudad, (carpeta, n) in ciudades.items():
        red = carpeta_publica(ciudad) / "red_peatonal.graphml"
        _, zonas = AT.zonas_de(red, ciudad, n)
        futuro = futuro_tabla(carpeta, ciudad)
        publicos = FO.leer_publicos(carpeta_publica(ciudad))
        largo = publicos["largo"]
        pea = {f: publicos[f"peatones_{f}"] for f in LISTA}
        rap = viajes_de(carpeta, ciudad, "B", n)
        rap = rap[~rap["relleno"] & (rap["etiqueta"] == "Fastest")].drop_duplicates("viaje").set_index("viaje")
        peso = pd.Series({i: float((pea[f].reindex(ids).fillna(0) * largo.reindex(ids).fillna(0)).sum()
                                   / max(largo.reindex(ids).fillna(0).sum(), 1e-9))
                          for i, ids, f in zip(rap.index, rap["ids"], rap["franja"])})
        for mapa in NIVELES:
            archivo = carpeta / f"{ciudad}_viajes_{mapa}_{n}.jsonl"
            if not archivo.exists():
                continue
            t = AT.por_viaje(pd.read_json(archivo, lines=True), {f: futuro[f"fut_{f}"] for f in LISTA})
            w = peso.reindex(t.index).fillna(0).values
            a, b = t["a"].values * w, t["b"].values * w
            con = t["alt"].values
            # registrada ponderada (viajes con alternativa, remuestreo de viajes) y todos (zonas)
            ac, bc = a[con], b[con]
            m = np.random.default_rng(1).integers(0, len(ac), (REMUESTREOS, len(ac)))
            boot_c = bc[m].sum(1) / np.maximum(ac[m].sum(1), 1e-12) - 1
            z = pd.DataFrame({"a": a, "b": b}, index=t.index).groupby(zonas.reindex(t.index).values).sum()
            idx = rng.integers(0, len(z), (REMUESTREOS, len(z)))
            boot_t = z["b"].values[idx].sum(1) / np.maximum(z["a"].values[idx].sum(1), 1e-12) - 1
            filas.append({"ciudad": ciudad, "mapa": mapa,
                          "registrado_ponderado": (bc.sum() / ac.sum() - 1) * 100, "ic95_registrado": ic(boot_c * 100),
                          "todos_ponderado": (b.sum() / a.sum() - 1) * 100, "ic95_todos_zonas": ic(boot_t * 100),
                          "peso_mediano": float(np.median(w)), "peso_p90": float(np.percentile(w, 90))})
            print(f"  {ciudad} {mapa}: registrado ponderado {filas[-1]['registrado_ponderado']:+.1f}% "
                  f"| todos ponderado {filas[-1]['todos_ponderado']:+.1f}%", flush=True)
    t = pd.DataFrame(filas)
    t.to_csv(salida / "r8_ponderado.csv", index=False)
    return t


# --------------------------------------------------------------------------------------
# R9: modelo frente al mapa de delitos del pasado, sobre todos los viajes (pareado, zonas)
def r9(ciudades, salida):
    rng = np.random.default_rng(SEMILLA)
    filas = []
    for ciudad, (carpeta, n) in ciudades.items():
        red = carpeta_publica(ciudad) / "red_peatonal.graphml"
        _, zonas = AT.zonas_de(red, ciudad, n)
        fut = {f: futuro_tabla(carpeta, ciudad)[f"fut_{f}"] for f in LISTA}
        for modelo, calor in [("B", "mapa_de_calor_B"), ("A", "mapa_de_calor_A")]:
            tm = AT.por_viaje(viajes_de(carpeta, ciudad, modelo, n), fut)
            tc = AT.por_viaje(viajes_de(carpeta, ciudad, calor, n), fut)
            comunes = tm.index.intersection(tc.index)
            df = pd.DataFrame({"am": tm.loc[comunes, "a"], "bm": tm.loc[comunes, "b"],
                               "ac": tc.loc[comunes, "a"], "bc": tc.loc[comunes, "b"]})
            z = df.groupby(zonas.reindex(comunes).values).sum()
            idx = rng.integers(0, len(z), (REMUESTREOS, len(z)))
            s = lambda c: z[c].values[idx].sum(1)
            dif = (s("bm") / np.maximum(s("am"), 1e-12) - s("bc") / np.maximum(s("ac"), 1e-12)) * 100
            punto = ((df["bm"].sum() / df["am"].sum()) - (df["bc"].sum() / df["ac"].sum())) * 100
            filas.append({"ciudad": ciudad, "modelo": modelo, "mapa_de_calor": calor, "viajes": len(comunes),
                          "cambio_modelo": (df["bm"].sum() / df["am"].sum() - 1) * 100,
                          "cambio_mapa_de_calor": (df["bc"].sum() / df["ac"].sum() - 1) * 100,
                          "diferencia_pp": punto, "ic95_zonas": ic(dif)})
            print(f"  {ciudad} {modelo} - {calor}: {punto:+.1f} pp {ic(dif)}", flush=True)
    t = pd.DataFrame(filas)
    t.to_csv(salida / "r9_modelo_vs_mapa_de_calor.csv", index=False)
    return t


def main():
    accion = sys.argv[1]
    ensayo = "--ensayo" in sys.argv
    ciudades = ENSAYO if ensayo else CIUDADES
    salida = RAIZ / ("data/practice/revision" if ensayo else "investigacion/resultados/revision")
    salida.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    t = {"r1": r1, "r2": r2, "r7": r7, "r8": r8, "r9": r9}[accion](ciudades, salida)
    print("\n" + t.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
