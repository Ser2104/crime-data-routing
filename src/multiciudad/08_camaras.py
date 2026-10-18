"""
Multiciudad, paso 8 (EXPLORATORIO): las calles con camaras de vigilancia, ¿tuvieron
menos delitos violentos? Solo ciudades de DESARROLLO. Las camaras NO son un rasgo de
la formula (reglas de datos, version 3): estan dibujadas de forma muy desigual.

Datos: camaras dibujadas en OpenStreetMap (man_made=surveillance), separando los
lectores de placas (surveillance:type=ALPR, como las Flock) del resto. No se sabe
cuando se instalo cada una: NO es un "antes y despues", y las camaras no se ponen al
azar. Por eso se hacen dos comparaciones y se reportan con cautela:

1. Observado contra esperado: una formula (nivel A, version actual) entrenada SIN la
   ciudad evaluada predice el nucleo del futuro de cada tramo sin saber donde hay
   camaras. Se compara observado/esperado en tramos con camaras a <= RADIO m contra
   el resto.
2. Tendencia: cambio del nucleo del pasado al futuro (por anio) en tramos con camaras
   contra tramos sin camaras con el MISMO nivel del pasado (mismos grupos de deciles),
   dentro de la misma ciudad.
3. Prueba de robustez: lo mismo que (1), pero comparando cada tramo con camara solo
   contra tramos SIN camara del mismo tipo de calle y la misma distancia a una avenida
   (las camaras de placas se ponen sobre todo en avenidas, y la formula podria
   sobreestimar el riesgo ahi). Si la razon se mantiene, la senal es mas creible.
Intervalos del 95% remuestreando zonas de 1 km.

Salida: investigacion/resultados/camaras.csv

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/08_camaras.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import osmnx as ox  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

import flujo as F  # noqa: E402
import formula as FO  # noqa: E402
import rasgos_delitos as RD  # noqa: E402
from ciudades import DESARROLLO, carpeta, carpeta_publica  # noqa: E402

RADIO = 100
ZONA = 1000
REMUESTREOS = 500
SALIDA = Path("investigacion/resultados/camaras.csv")
APRENDER = [c for c, d in DESARROLLO.items() if d["grupo"] == "train"]
NIVEL = "A"


def cargar(ciudad):
    publicos = FO.leer_publicos(carpeta_publica(ciudad))
    delitos = pd.read_csv(carpeta(ciudad) / "mapa_delitos.csv", index_col="tramo_id")
    return publicos, delitos


def camaras_cerca(ciudad, cfg):
    G = ox.project_graph(ox.load_graphml(carpeta_publica(ciudad) / "red_peatonal.graphml"), to_crs=cfg["crs"])
    _, medios = F.tramos_y_medios(G)
    elementos = json.loads((carpeta_publica(ciudad) / "camaras_osm.json").read_text())
    tipo = ["alpr" if e.get("tags", {}).get("surveillance:type") == "ALPR" else "otra" for e in elementos]
    pts = gpd.GeoSeries(gpd.points_from_xy([e["lon"] for e in elementos], [e["lat"] for e in elementos]),
                        crs=4326).to_crs(cfg["crs"])
    xy = np.column_stack([medios.geometry.x, medios.geometry.y])
    salida = pd.DataFrame(index=medios.index)
    for t in ["alpr", "otra"]:
        sel = np.array(tipo) == t
        salida[t] = (cKDTree(np.column_stack([pts.x[sel], pts.y[sel]])).query_ball_point(xy, RADIO, return_length=True)
                     if sel.any() else 0)
    return salida


def razon_boot(con, sin, zonas_con, zonas_sin, rng):
    """(sum obs/sum esp) en tramos con camara / lo mismo sin camara, con IC por zonas."""
    def razon(o_c, e_c, o_s, e_s):
        return (o_c.sum() / max(e_c.sum(), 1e-9)) / (o_s.sum() / max(e_s.sum(), 1e-9))
    punto = razon(con["obs"], con["esp"], sin["obs"], sin["esp"])
    zonas = np.unique(np.concatenate([zonas_con, zonas_sin]))
    boot = []
    for _ in range(REMUESTREOS):
        veces = pd.Series(rng.choice(zonas, len(zonas))).value_counts()
        wc = pd.Series(zonas_con).map(veces).fillna(0).values
        ws = pd.Series(zonas_sin).map(veces).fillna(0).values
        boot.append(razon(con["obs"] * wc, con["esp"] * wc, sin["obs"] * ws, sin["esp"] * ws))
    return punto, np.nanpercentile(boot, 2.5), np.nanpercentile(boot, 97.5)


def main():
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    datos = {c: cargar(c) for c in DESARROLLO}
    filas = []
    for ciudad, cfg in DESARROLLO.items():
        print(f"{cfg['nombre']}...", flush=True)
        # 1. Formula sin la ciudad evaluada (si es de aprender, se saca de su entrenamiento)
        otras = [c for c in APRENDER if c != ciudad]
        entreno = pd.concat([FO.largo_formato(*datos[c], c) for c in otras])
        modelo, cats = FO.entrenar(entreno, NIVEL)
        del entreno
        publicos, delitos = datos[ciudad]
        x = FO.largo_formato(publicos, delitos, ciudad)
        x["esp"] = FO.predecir(modelo, cats, x, NIVEL)
        # el modelo predice relativo al promedio: se lleva a la escala de los delitos del futuro
        x["esp"] *= x["fut"].sum() / x["esp"].sum()
        por_tramo = x.groupby(level=0)[["fut", "esp"]].sum().rename(columns={"fut": "obs"})
        cam = camaras_cerca(ciudad, cfg).reindex(por_tramo.index).fillna(0)
        por_tramo["tipo"] = publicos["tipo"].reindex(por_tramo.index).astype(str)
        por_tramo["dist_avenida"] = pd.cut(publicos["dist_principal"].reindex(por_tramo.index),
                                           [-1, 25, 75, 150, 300, 600, 10_000], labels=False)
        estrato = por_tramo["tipo"] + "_" + por_tramo["dist_avenida"].astype(str)
        zona = ((publicos["cx"] // ZONA).astype(int).astype(str) + "_" +
                (publicos["cy"] // ZONA).astype(int).astype(str)).reindex(por_tramo.index)
        # 2. Tendencia: pasado (por anio) contra futuro (por anio), dentro de grupos del mismo nivel pasado
        anios_pasado = (pd.Timestamp(RD.PASADO[1]) - pd.Timestamp(RD.PASADO[0])).days / 365.25
        pasado = delitos[[c for c in delitos if c.startswith("a_")]].sum(axis=1).reindex(por_tramo.index).fillna(0)
        grupo = pd.qcut(pasado.rank(method="first"), 10, labels=False)
        for tipo in ["alpr", "otra"]:
            tiene = cam[tipo] > 0
            if tiene.sum() < 20:
                continue
            p, lo, hi = razon_boot(por_tramo[tiene], por_tramo[~tiene], zona[tiene].values, zona[~tiene].values, rng)
            # tendencia: esperado = pasado anual escalado por el cambio de la ciudad en su grupo
            fut_anual = por_tramo["obs"]
            cambio_grupo = (fut_anual[~tiene].groupby(grupo[~tiene]).sum()
                            / (pasado[~tiene].groupby(grupo[~tiene]).sum() / anios_pasado).replace(0, np.nan))
            esperado_t = (pasado / anios_pasado) * grupo.map(cambio_grupo).fillna(1)
            t_tabla = pd.DataFrame({"obs": fut_anual, "esp": esperado_t})
            pt, lot, hit = razon_boot(t_tabla[tiene], t_tabla[~tiene], zona[tiene].values, zona[~tiene].values, rng)
            # 3. robustez: esperado ajustado por lo que pasa en tramos sin camara del mismo estrato
            sin = por_tramo[~tiene]
            ajuste = (sin.groupby(estrato[~tiene])["obs"].sum() / sin.groupby(estrato[~tiene])["esp"].sum()).replace([np.inf], np.nan)
            esp_aj = por_tramo["esp"] * estrato.map(ajuste).fillna(1)
            r_tabla = pd.DataFrame({"obs": por_tramo["obs"], "esp": esp_aj})
            uno = pd.DataFrame({"obs": por_tramo["esp"] * 0 + 1, "esp": por_tramo["esp"] * 0 + 1})
            pr, lor, hir = razon_boot(r_tabla[tiene], uno[~tiene].assign(obs=1.0, esp=1.0),
                                      zona[tiene].values, zona[~tiene].values, rng)
            filas.append({"ciudad": ciudad, "camaras": "lectores de placas" if tipo == "alpr" else "otras camaras",
                          "tramos_con_camara": int(tiene.sum()), "delitos_futuros_cerca": float(por_tramo.loc[tiene, "obs"].sum()),
                          "obs_vs_esperado": round(p, 2), "ic95": f"{lo:.2f}-{hi:.2f}",
                          "tendencia_vs_similares": round(pt, 2), "ic95_tendencia": f"{lot:.2f}-{hit:.2f}",
                          "vs_mismo_tipo_de_calle": round(pr, 2), "ic95_mismo_tipo": f"{lor:.2f}-{hir:.2f}"})
            print(f"  {filas[-1]}", flush=True)
    tabla = pd.DataFrame(filas)
    tabla.to_csv(SALIDA, index=False)
    pd.set_option("display.width", 220)
    print("\n" + tabla.to_string(index=False))
    print("\n1 = igual que lo esperado; <1 = menos delitos violentos de lo esperado cerca de camaras.")


if __name__ == "__main__":
    main()
