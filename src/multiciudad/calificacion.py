"""
Calificacion RAPIDA de un mapa de riesgo, comun a la practica (paso 7) y al examen
(paso 9): parte de los delitos del nucleo del futuro que cae en el TOPE de la red
(por largo) que el mapa marca como mas riesgosa, por franja y su promedio, con
intervalo del 95% remuestreando zonas de ZONA m (las calles vecinas no son
independientes; las coordenadas solo se usan para armar las zonas).
"""
import numpy as np
import pandas as pd

from riesgo_pie import FRANJAS

TOPE = 0.10
ZONA = 1000
REMUESTREOS = 300


def zonas_de(publicos):
    return (publicos["cx"] // ZONA).astype(int).astype(str) + "_" + (publicos["cy"] // ZONA).astype(int).astype(str)


def captura(riesgo, futuro, largo):
    """Parte de los delitos futuros en el TOPE de la red (por largo) con mas riesgo."""
    orden = np.argsort(-riesgo, kind="stable")
    acumulado = np.cumsum(largo[orden]) / largo.sum()
    dentro = orden[acumulado <= TOPE]
    return futuro[dentro].sum() / max(futuro.sum(), 1e-9)


def calificar_rapido(x, riesgo, largo, zona, rng, futuro=None):
    """Captura por franja y su promedio, con intervalo (remuestreo de zonas).
    futuro: delitos a usar en lugar de x['fut'] (para la prueba trampa)."""
    fut = x["fut"].values if futuro is None else np.asarray(futuro)
    por_franja = {}
    for f in FRANJAS:
        m = (x["franja"] == f).values
        por_franja[f] = (riesgo[m], fut[m], largo.reindex(x.index[m]).values, zona.reindex(x.index[m]).values)
    fila = {f: captura(r, fu, la) for f, (r, fu, la, _) in por_franja.items()}
    fila["promedio"] = float(np.mean([fila[f] for f in FRANJAS]))
    zonas = np.unique(zona.values)
    boot = []
    for _ in range(REMUESTREOS):
        elegidas = pd.Series(rng.choice(zonas, len(zonas))).value_counts()
        valores = []
        for r, fu, la, zo in por_franja.values():
            veces = pd.Series(zo).map(elegidas).fillna(0).astype(int).values
            idx = np.repeat(np.arange(len(r)), veces)
            valores.append(captura(r[idx], fu[idx], la[idx]))
        boot.append(np.mean(valores))
    fila["ic95"] = f"{np.percentile(boot, 2.5):.3f}-{np.percentile(boot, 97.5):.3f}"
    return fila


def comparar_rapido(x, riesgo1, riesgo2, largo, zona, rng):
    """Diferencia PAREADA de la calificacion rapida (mapa 2 menos mapa 1), con
    intervalo remuestreando las MISMAS zonas para los dos mapas."""
    partes = []
    for f in FRANJAS:
        m = (x["franja"] == f).values
        partes.append((riesgo1[m], riesgo2[m], x["fut"].values[m], largo.reindex(x.index[m]).values,
                       zona.reindex(x.index[m]).values))
    diferencia = lambda idx: np.mean([captura(r2[i], fu[i], la[i]) - captura(r1[i], fu[i], la[i])
                                      for (r1, r2, fu, la, _), i in zip(partes, idx)])
    punto = diferencia([np.arange(len(p[0])) for p in partes])
    zonas = np.unique(zona.values)
    boot = []
    for _ in range(REMUESTREOS):
        elegidas = pd.Series(rng.choice(zonas, len(zonas))).value_counts()
        boot.append(diferencia([np.repeat(np.arange(len(p[0])), pd.Series(p[4]).map(elegidas).fillna(0).astype(int).values)
                                for p in partes]))
    return {"diferencia": float(punto), "ic95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}
