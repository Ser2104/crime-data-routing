"""
Reparto del peligro de los delitos a las calles cercanas, RAPIDO y para cualquier
ciudad. Misma escala que Pittsburgh (src/riesgo_pie.py): 100% hasta 40 m caminando,
-10% cada 20 m, 0% a mas de 220 m, y cada tramo recibe el peso PROMEDIO a lo largo
de su largo.

Diferencia con riesgo_pie.repartir: cada delito se ubica en el CENTRO de su tramo
(no en su punto exacto). Asi el reparto se calcula una vez por ciudad, como una
matriz K (tramo de origen x tramo de destino), y repartir cualquier conteo
(periodo, franja, categoria) es una multiplicacion: riesgo = conteos @ K.
"""
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import dijkstra

import riesgo_pie as RP
from comun import id_tramo

LOTE = 64


def tramos_de(G):
    """Tramos de la red proyectada (uno por tramo_id): nodos u, v y largo."""
    filas = {}
    for u, v, d in G.edges(data=True):
        t = id_tramo(u, v, d["osmid"], d["length"])
        if t not in filas:
            filas[t] = (u, v, max(float(d["length"]), 0.01))
    return pd.DataFrame.from_dict(filas, orient="index", columns=["u", "v", "largo"])


def matriz(G, origenes=None, avisar=True):
    """K: para cada tramo de origen (por defecto todos), el peso que recibe cada tramo
    cercano de un delito en su centro. Devuelve (K csr, indice de tramos)."""
    tramos = tramos_de(G)
    indice = tramos.index
    pos_tramo = pd.Series(np.arange(len(tramos)), index=indice)
    nodos = pd.Index(pd.unique(np.concatenate([tramos["u"].values, tramos["v"].values])))
    a, b = nodos.get_indexer(tramos["u"]), nodos.get_indexer(tramos["v"])
    n = len(nodos)
    # grafo simple: entre dos nodos, el tramo mas corto
    par = pd.DataFrame({"a": np.minimum(a, b), "b": np.maximum(a, b), "l": tramos["largo"].values})
    par = par[par["a"] != par["b"]].groupby(["a", "b"])["l"].min().reset_index()
    adyacencia = csr_matrix((par["l"], (par["a"], par["b"])), shape=(n, n))
    # tramos que tocan cada nodo
    nodo_t = np.concatenate([a, b])
    tramo_t = np.concatenate([np.arange(len(tramos))] * 2)
    orden = np.argsort(nodo_t, kind="stable")
    inicio = np.searchsorted(nodo_t[orden], np.arange(n + 1))
    tramos_de_nodo = lambda i: tramo_t[orden[inicio[i]:inicio[i + 1]]]

    src = np.arange(len(tramos)) if origenes is None else pos_tramo.reindex(origenes).dropna().astype(int).values
    nodos_src = np.unique(np.concatenate([a[src], b[src]]))
    alcance = {}
    for k in range(0, len(nodos_src), LOTE):
        lote = nodos_src[k:k + LOTE]
        d = dijkstra(adyacencia, directed=False, indices=lote, limit=RP.RADIO)
        for fila, nodo in zip(d, lote):
            j = np.flatnonzero(np.isfinite(fila))
            alcance[nodo] = (j, fila[j])
        if avisar and (k // LOTE) % 200 == 0:
            print(f"    distancias: {k + len(lote):,} / {len(nodos_src):,} nodos", flush=True)

    largo, filas, cols, vals = tramos["largo"].values, [], [], []
    for s in src:
        L, mitad = largo[s], largo[s] / 2
        dist = {}
        for nodo in (a[s], b[s]):
            j, dj = alcance[nodo]
            for jj, dd in zip(j, dj + mitad):
                if dd < dist.get(jj, np.inf):
                    dist[jj] = dd
        pesos = {}
        for jj in dist:
            for t in tramos_de_nodo(jj):
                if t not in pesos:
                    pesos[t] = RP.peso_promedio(dist.get(a[t], RP.LEJOS), dist.get(b[t], RP.LEJOS), largo[t])
        pesos[s] = RP.peso_propio(mitad, L)
        for t, w in pesos.items():
            if w > 0:
                filas.append(s)
                cols.append(t)
                vals.append(w)
    K = coo_matrix((vals, (filas, cols)), shape=(len(tramos), len(tramos))).tocsr()
    return K, indice


def repartir(K, indice, conteos):
    """conteos: Series o DataFrame indexado por tramo_id (delitos por tramo). Devuelve el
    riesgo repartido por tramo (mismas columnas)."""
    tabla = conteos.to_frame() if isinstance(conteos, pd.Series) else conteos
    X = tabla.reindex(indice).fillna(0).values
    salida = pd.DataFrame(K.T @ X, index=indice, columns=tabla.columns)
    return salida.iloc[:, 0] if isinstance(conteos, pd.Series) else salida
