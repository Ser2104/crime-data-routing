"""
Rasgos de DELITOS por tramo para cada nivel (investigacion/reglas_de_datos.md,
seccion 3) y lo que se califica (seccion 2). Una sola funcion para todas las
ciudades: la usan las ciudades de desarrollo ahora y las de examen el dia de la
apertura, sin cambios.

Columnas (todas por tramo; "repartido" = src/multiciudad/reparto.py):
    nivel A      a_<franja>              nucleo del PASADO repartido
    nivel B      b_<franja>              definicion amplia del pasado repartida
                 b_cat_<categoria>       cada categoria amplia del pasado repartida (todas las horas)
    nivel C      c_<bolsa>_<franja>      cada bolsa del pasado repartida
    por zona     z_<franja>              nucleo del pasado del grupo de manzanas / km de calle del grupo
    totales      t_tasa                  nucleo del pasado por anio por 1,000 habitantes de la ciudad
    calificacion y_<franja>              nucleo del FUTURO repartido (lo que aprende el modelo)
                 fut_<franja>            nucleo del FUTURO contado en el tramo (lo que se mide en las rutas)
Las columnas de un nivel solo existen si la ciudad publica esa informacion (por
ejemplo, sin categoria amplia no hay columnas b_).
"""
import numpy as np
import pandas as pd

import categorias as K
import reparto as RR
from riesgo_pie import FRANJAS

PASADO = ("2024-01-01", "2025-08-31")
FUTURO = ("2025-09-01", "2026-08-31")
FRANJA_DE_HORA = {h: f for f, horas in FRANJAS.items() for h in horas}


def por_franja(d, columna=None, valor=None):
    """Conteo por tramo y franja (la hora desconocida se reparte en partes iguales).
    Si 'columna' se da, solo las filas con d[columna] == valor."""
    if columna is not None:
        d = d[d[columna] == valor]
    conocida = ~d["hora_desconocida"].astype(bool)
    partes = []
    for f in FRANJAS:
        peso = np.where(conocida, (d["hora"].map(FRANJA_DE_HORA) == f).astype(float), 1 / len(FRANJAS))
        partes.append(pd.Series(peso, index=d.index).groupby(d["tramo_id"]).sum().rename(f))
    return pd.concat(partes, axis=1).fillna(0) if partes else pd.DataFrame(columns=list(FRANJAS))


def construir(G, delitos, manzanas, tramo_manzana, con_detalle, avisar=True):
    """G: red proyectada. delitos: salida del paso 4 (solo motivo 'ninguno').
    manzanas: GeoDataFrame con geoid y poblacion. tramo_manzana: geoid de la manzana
    mas cercana a cada tramo (Series por tramo_id)."""
    d = delitos.copy()
    d["fecha"] = pd.to_datetime(d["fecha"])
    pas = d[(d["fecha"] >= PASADO[0]) & (d["fecha"] <= PASADO[1])]
    fut = d[(d["fecha"] >= FUTURO[0]) & (d["fecha"] <= FUTURO[1])]
    origenes = d["tramo_id"].dropna().unique()
    if avisar:
        print(f"    reparto: {len(origenes):,} tramos con delitos", flush=True)
    Kmat, indice = RR.matriz(G, origenes, avisar=avisar)
    rep = lambda conteo: RR.repartir(Kmat, indice, conteo.reindex(columns=list(FRANJAS)).fillna(0))
    salida = pd.DataFrame(index=indice)
    nucleo_pas = por_franja(pas[pas["clase_nucleo"].notna()])
    salida = salida.join(rep(nucleo_pas).add_prefix("a_"))
    if con_detalle:
        amplia = pas[pas["categoria_amplia"].notna()]
        salida = salida.join(rep(por_franja(amplia)).add_prefix("b_"))
        for cat in K.CATEGORIAS_AMPLIAS:
            conteo = amplia[amplia["categoria_amplia"] == cat].groupby("tramo_id").size()
            salida[f"b_cat_{cat}"] = RR.repartir(Kmat, indice, conteo.astype(float).rename(cat)).values
    for bolsa in K.BOLSAS:
        salida = salida.join(rep(por_franja(pas, "bolsa", bolsa)).add_prefix(f"c_{bolsa}_"))
    # Por zona: grupo de manzanas (los primeros 12 digitos del codigo del Censo)
    grupo = tramo_manzana.reindex(indice).str.slice(0, 12)
    largo = RR.tramos_de(G)["largo"].reindex(indice)
    km_grupo = largo.groupby(grupo).sum() / 1000
    conteo_grupo = nucleo_pas.groupby(grupo.reindex(nucleo_pas.index)).sum()
    for f in FRANJAS:
        tasa = (conteo_grupo[f] / km_grupo).reindex(grupo.values).values if len(conteo_grupo) else 0
        salida[f"z_{f}"] = np.nan_to_num(tasa)
    anios = (pd.Timestamp(PASADO[1]) - pd.Timestamp(PASADO[0])).days / 365.25
    salida["t_tasa"] = nucleo_pas.values.sum() / anios / max(manzanas["poblacion"].sum(), 1) * 1000
    # Lo que se califica (futuro)
    nucleo_fut = por_franja(fut[fut["clase_nucleo"].notna()])
    salida = salida.join(rep(nucleo_fut).add_prefix("y_"))
    salida = salida.join(nucleo_fut.reindex(indice).fillna(0).add_prefix("fut_"))
    salida.index.name = "tramo_id"
    return salida.fillna(0)
