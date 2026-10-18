"""
La FORMULA: un modelo que predice el riesgo de cada tramo y franja (el nucleo del
futuro repartido, relativo al promedio de su ciudad) a partir de rasgos que
existen en cualquier ciudad, y de los delitos del pasado que permita cada nivel
(investigacion/reglas_de_datos.md, seccion 3).

Datos en formato largo: una fila por tramo y franja. Los rasgos que dependen de la
franja (buses_<franja>, a_<franja>...) pasan a llamarse igual en todas (buses, a...).
Los rasgos de delitos se expresan relativos al promedio de su ciudad (una ciudad
con mas delitos, o que publica mas, no confunde a la formula). Cada ciudad pesa
lo mismo al entrenar.

PROHIBIDO como rasgo (reglas, seccion 5): coordenadas (cx, cy), identificadores
y la identidad de la ciudad. comprobar_rasgos() lo verifica antes de entrenar.
"""
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from riesgo_pie import FRANJAS

VERSION = "v2"   # v1: sin lugares; v2: lugares y uso del suelo (reglas de datos, version 3)
FIJOS_MAPA = ["largo", "es_sendero", "en_parque", "dist_principal", "locales_150", "locales_400",
              "intersecciones_300", "alcance_400"]
# Lugares de OpenStreetMap dibujados de forma pareja entre ciudades. Fuera por estar muy
# desparejos (registro de practica, v2): edificios, uso del suelo, cajeros, tiendas de licor
LUGARES_MAPA = ["escuelas_400", "universidades_400", "hospitales_400", "comisarias_800", "gasolineras_150",
                "estaciones_400", "estadios_800"]
PARADAS_OSM = ["paradas_300"]          # solo en "solo mapa": en los demas niveles, las de los horarios
POR_FRANJA_MAPA = ["locales", "bares"]
FIJOS_OTROS = ["habitantes_400", "empleos_400", "radiancia", "paradas_gtfs_300"]
POR_FRANJA_OTROS = ["buses", "peatones"]
CATEGORICOS = ["tipo", "franja"]
USO_SUELO = False   # se decide segun que tan completo esta en todas las ciudades (registro de practica)
# Rasgos de delitos por nivel (prefijos de rasgos_delitos.py, ya sin la franja). Cada
# nivel puede usar cualquier cosa DERIVADA de su informacion: "<x>_todas" es la suma de
# las 4 franjas (mas estable), y con delitos ubicados se pueden armar la zona y el total.
_CATS = [f"b_cat_{c}" for c in ["homicidio", "robo", "agresion_grave", "agresion_simple", "amenaza",
                                 "armas", "arrebato", "carterista", "secuestro", "drogas"]]
_A = ["a", "a_todas", "z", "z_todas", "t_tasa"]
_C = [f"c_{b}{s}" for b in ["violento", "propiedad", "otro"] for s in ["", "_todas"]]
DELITOS = {
    "B": _A + ["b", "b_todas"] + _CATS,
    "A": _A,
    "C": _C + ["t_tasa"],
    "zona": ["z", "z_todas", "t_tasa"],
    "totales": ["t_tasa"],
    "sin_delitos": [],
    "solo_mapa": [],
}
NIVELES = list(DELITOS)
PROHIBIDOS = {"cx", "cy", "tramo_id", "ciudad", "u", "v", "key", "osmid", "lat", "lon"}
PARAMETROS = {"objective": "tweedie", "tweedie_variance_power": 1.5, "learning_rate": 0.05, "num_leaves": 31,
              "min_data_in_leaf": 200, "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1,
              "lambda_l2": 1.0, "verbose": -1, "seed": 7}
RONDAS = 400


def categoricos():
    return CATEGORICOS + (["uso_suelo"] if USO_SUELO else [])


def rasgos_de(nivel):
    mapa = FIJOS_MAPA + LUGARES_MAPA + POR_FRANJA_MAPA
    publicos = mapa + PARADAS_OSM if nivel == "solo_mapa" else mapa + FIJOS_OTROS + POR_FRANJA_OTROS
    return publicos + DELITOS[nivel] + categoricos()


def leer_publicos(carpeta):
    """Rasgos publicos de una ciudad: forma, actividad, gente y luz (paso 5) + lugares (paso 5b)."""
    carpeta = Path(carpeta)
    publicos = pd.read_csv(carpeta / "tramos.csv", index_col="tramo_id")
    lugares = carpeta / "tramos_lugares.csv"
    if lugares.exists():
        publicos = publicos.join(pd.read_csv(lugares, index_col="tramo_id"))
    return publicos


def comprobar_rasgos(columnas):
    malos = PROHIBIDOS & set(columnas)
    if malos:
        raise ValueError(f"Rasgos prohibidos por las reglas: {sorted(malos)}")


def largo_formato(publicos, delitos, ciudad):
    """Una fila por tramo y franja. publicos: tramos.csv (paso 5). delitos: mapa_delitos
    (paso 6) o None. Los rasgos de delitos quedan relativos al promedio de la ciudad."""
    filas = []
    tramos = publicos.index if delitos is None else publicos.index.intersection(delitos.index)
    for f in FRANJAS:
        fijos = [c for c in FIJOS_MAPA + LUGARES_MAPA + PARADAS_OSM + FIJOS_OTROS + ["tipo", "uso_suelo"]
                 if c in publicos.columns]
        x = publicos.loc[tramos, fijos].copy()
        for nombre in POR_FRANJA_MAPA + POR_FRANJA_OTROS:
            x[nombre] = publicos.loc[tramos, f"{nombre}_{f}"].values
        if delitos is not None:
            d = delitos.loc[tramos]
            for prefijo in ["a", "b", "z", "y", "fut"] + [f"c_{b}" for b in ["violento", "propiedad", "otro"]]:
                if f"{prefijo}_{f}" in d:
                    x[prefijo] = d[f"{prefijo}_{f}"].values
            for c in d.columns:
                if c.startswith("b_cat_") or c == "t_tasa":
                    x[c] = d[c].values
        x["franja"] = f
        x["ciudad"] = ciudad
        filas.append(x)
    x = pd.concat(filas)
    # suma de las 4 franjas de cada rasgo de delitos (mas estable que una sola franja)
    for prefijo in ["a", "b", "z"] + [f"c_{b}" for b in ["violento", "propiedad", "otro"]]:
        if prefijo in x:
            x[f"{prefijo}_todas"] = x.groupby(level=0)[prefijo].transform("sum")
    # relativos al promedio de la ciudad (por franja en los que dependen de ella)
    for c in [c for c in x.columns if c in ("a", "b", "z", "y") or c.startswith(("c_", "b_cat_", "a_", "b_", "z_"))]:
        media = x.groupby("franja")[c].transform("mean")
        x[c] = np.where(media > 0, x[c] / media, 0.0)
    return x


def preparar(x, nivel, categorias):
    columnas = [c for c in rasgos_de(nivel) if c in x.columns]
    comprobar_rasgos(columnas)
    X = x[columnas].copy()
    for c in categoricos():
        X[c] = pd.Categorical(X[c], categories=categorias[c])
    return X


def entrenar(datos, nivel):
    """datos: formato largo de las ciudades de aprender (con 'y'). Cada ciudad pesa igual."""
    datos = datos.dropna(subset=["y"])
    faltan = [c for c in DELITOS[nivel] if c not in datos.columns or datos[c].isna().all()]
    if faltan:
        raise ValueError(f"Nivel {nivel}: faltan rasgos {faltan}")
    categorias = {"tipo": sorted(datos["tipo"].astype(str).unique()), "franja": list(FRANJAS),
                  "uso_suelo": ["comercial", "industrial", "residencial", "ninguno"]}
    X = preparar(datos, nivel, categorias)
    peso = 1 / datos.groupby("ciudad")["y"].transform("size")
    modelo = lgb.train(PARAMETROS, lgb.Dataset(X, datos["y"], weight=peso, categorical_feature=categoricos()),
                       num_boost_round=RONDAS)
    return modelo, categorias


def predecir(modelo, categorias, x, nivel):
    return modelo.predict(preparar(x, nivel, categorias))


def mapa_de_riesgo(x, prediccion, largo):
    """Prediccion en formato largo -> tabla por tramo con riesgo_<franja> y length (lo que usa rutas.py)."""
    tabla = pd.DataFrame({"tramo_id": x.index, "franja": x["franja"].values, "riesgo": prediccion})
    mapa = tabla.pivot_table(index="tramo_id", columns="franja", values="riesgo").add_prefix("riesgo_")
    mapa["length"] = largo.reindex(mapa.index).values
    return mapa
