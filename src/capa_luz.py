"""
Capa de ILUMINACION por tramo: combina todas las fuentes, de la mas confiable a
la menos, y dice de donde sale cada dato y cuanto se confia en el.

Estados (lista cerrada) y de donde salen, en orden de prioridad:
    apagada_reportada       tiempo real: farol reportado apagado, corte de luz o
                            apagon visto por el satelite (src/luz_tiempo_real.py)
    iluminada / oscura      marcado_osm: personas marcaron la calle con o sin luz
                            modelo_fotometrico: luz calculada en el suelo con los
                            faroles reales (Pittsburgh): <=20% oscuro / >=80% oscuro
    parcialmente_iluminada  modelo_fotometrico: entre 20% y 80% del tramo oscuro
    iluminada               inventario: hay un farol registrado a <= RADIO_FAROL m
                            (inventarios oficiales, faroles dibujados en OSM o
                            detectados en fotos de calle de Mapillary; no se sabe
                            si esta prendido: confianza media)
    probablemente_iluminada modelo_global (src/luz_modelo.py) con p >= seguro_luz
    probablemente_oscura    modelo_global con p <= seguro_oscuro
    sin_informacion         el modelo global duda: no se afirma nada
Los umbrales del modelo global (seguro_luz, seguro_oscuro) los elige el paso 13
para que se equivoque a lo sumo un 10% en ciudades que no vio.

p_luz: probabilidad de que el tramo tenga luz (para el riesgo: oscuridad = 1 - p_luz).
"""
import json

import geopandas as gpd
import lightgbm as lgb
import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree

import luz_modelo as LM
import luz_satelite as LS

ESTADOS = ["apagada_reportada", "iluminada", "oscura", "parcialmente_iluminada",
           "probablemente_iluminada", "probablemente_oscura", "sin_informacion"]
FUENTES = ["tiempo_real", "marcado_osm", "modelo_fotometrico", "inventario", "modelo_global"]
CONFIANZA = {"tiempo_real": "alta", "marcado_osm": "alta", "modelo_fotometrico": "alta",
             "inventario": "media", "modelo_global": "media"}
RADIO_FAROL = 35       # m: un farol registrado ilumina su tramo
P_CONFIRMADA = {"iluminada": 0.95, "oscura": 0.05, "apagada_reportada": 0.10, "inventario": 0.85}
OSCURO_SI, ILUMINADO_SI = 0.8, 0.2   # fraccion oscura del tramo (modelo fotometrico)
_S = requests.Session()
_S.headers["User-Agent"] = "safe-routes-pgh/0.1 (proyecto personal)"


def faroles_osm(caja):
    """Faroles dibujados en OpenStreetMap (lon, lat)."""
    oeste, sur, este, norte = caja
    el = LM.overpass(f'[out:json][timeout:300];node["highway"="street_lamp"]({sur},{oeste},{norte},{este});out;')
    return pd.DataFrame([(e["lon"], e["lat"]) for e in el], columns=["lon", "lat"])


def faroles_arcgis(url_capa):
    """Faroles de un inventario publicado en ArcGIS (lon, lat)."""
    filas, desde = [], 0
    while True:
        r = _S.get(f"{url_capa}/query", timeout=120, params={
            "where": "1=1", "returnGeometry": "true", "outSR": 4326,  # sin campos: no todas las capas tienen OBJECTID
            "resultOffset": desde, "resultRecordCount": 2000, "f": "json"}).json()
        feats = r.get("features", [])
        filas += [(f["geometry"]["x"], f["geometry"]["y"]) for f in feats if f.get("geometry")]
        desde += len(feats)
        if len(feats) < 2000:
            break
    return pd.DataFrame(filas, columns=["lon", "lat"])


def faroles_mapillary(caja, token, celda=0.01):
    """Faroles detectados por inteligencia artificial en las fotos de calle de
    Mapillary (gratis, con un token de una cuenta gratuita). La caja se recorre
    en celdas de 'celda' grados (la API limita el area por consulta)."""
    oeste, sur, este, norte = caja
    filas = []
    for x in np.arange(oeste, este, celda):
        for y in np.arange(sur, norte, celda):
            r = _S.get("https://graph.mapillary.com/map_features", timeout=120, params={
                "access_token": token, "fields": "id,geometry,last_seen_at",
                "object_values": "object--street-light",
                "bbox": f"{x},{y},{min(x + celda, este)},{min(y + celda, norte)}"})
            if r.ok:
                filas += [(f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1], f.get("last_seen_at"))
                          for f in r.json().get("data", [])]
    return pd.DataFrame(filas, columns=["lon", "lat", "visto"]).drop_duplicates(["lon", "lat"])


def _ids(osmid):
    return osmid if isinstance(osmid, list) else [osmid]


def base(tramos, vias, brillo, modelo, meta, faroles=None, fotometrico=None):
    """Capa base (sin tiempo real) de cada tramo.
    tramos: GeoDataFrame proyectado indexado por tramo_id (con 'osmid').
    vias: vias de OSM de la zona (luz_modelo.vias_osm). brillo: satelite de la zona.
    faroles: DataFrame lon/lat de faroles registrados (inventarios + OSM).
    fotometrico: DataFrame por tramo con 'oscuridad' (luz calculada en el suelo)."""
    # 1. Modelo global por via de OSM -> por tramo (promedio de sus vias)
    x = LM.caracteristicas(vias, brillo)
    p_via = pd.Series(modelo.predict(LM.preparar(x, meta["categorias_tipo"])), index=vias["osm_id"].values)
    lit_via = pd.Series(vias["lit"].values, index=vias["osm_id"].values)
    p_via, lit_via = p_via[~p_via.index.duplicated()], lit_via[~lit_via.index.duplicated()]
    filas = []
    for t, osmid in zip(tramos.index, tramos["osmid"]):
        ids = [i for i in _ids(osmid) if i in p_via.index]
        marcas = {lit_via[i] for i in ids if isinstance(lit_via[i], str)}
        filas.append((t, float(np.mean([p_via[i] for i in ids])) if ids else np.nan,
                      "yes" if marcas == {"yes"} else "no" if marcas == {"no"} else None))
    capa = pd.DataFrame(filas, columns=["tramo_id", "p_modelo", "marca_osm"]).set_index("tramo_id")

    # 2. Faroles registrados cerca del tramo
    capa["farol_cerca"] = False
    if faroles is not None and len(faroles):
        pts = gpd.GeoSeries(gpd.points_from_xy(faroles["lon"], faroles["lat"]), crs=4326).to_crs(tramos.crs)
        arbol = cKDTree(np.column_stack([pts.x, pts.y]))
        cerca = []
        for linea in tramos.geometry:
            n = max(int(linea.length // 10), 1)
            muestras = [linea.interpolate(d) for d in (np.arange(n) + 0.5) * linea.length / n]
            d, _ = arbol.query([(p.x, p.y) for p in muestras], distance_upper_bound=RADIO_FAROL)
            cerca.append(bool(np.isfinite(d).any()))
        capa["farol_cerca"] = cerca

    # 3. Estado, fuente y probabilidad, de la fuente mas confiable a la menos
    osc_foto = fotometrico["oscuridad"].reindex(capa.index) if fotometrico is not None else pd.Series(np.nan, capa.index)
    estado, fuente, p = [], [], []
    for (t, fila), of in zip(capa.iterrows(), osc_foto):
        if fila["marca_osm"] == "yes":
            e, f, pp = "iluminada", "marcado_osm", P_CONFIRMADA["iluminada"]
        elif fila["marca_osm"] == "no":
            e, f, pp = "oscura", "marcado_osm", P_CONFIRMADA["oscura"]
        elif np.isfinite(of):
            pp = 1 - of
            e = "iluminada" if of <= ILUMINADO_SI else "oscura" if of >= OSCURO_SI else "parcialmente_iluminada"
            f = "modelo_fotometrico"
        elif fila["farol_cerca"]:
            e, f, pp = "iluminada", "inventario", max(P_CONFIRMADA["inventario"], fila["p_modelo"] or 0)
        elif np.isfinite(fila["p_modelo"]):
            pp = fila["p_modelo"]
            e = ("probablemente_iluminada" if pp >= meta["seguro_luz"] else
                 "probablemente_oscura" if pp <= meta["seguro_oscuro"] else "sin_informacion")
            f = "modelo_global"
        else:
            e, f, pp = "sin_informacion", "modelo_global", 0.5
        estado.append(e)
        fuente.append(f)
        p.append(pp)
    capa["estado"], capa["fuente"], capa["p_luz"] = estado, fuente, np.round(p, 3)
    capa["confianza"] = [("baja" if e == "sin_informacion" else CONFIANZA[f]) for e, f in zip(estado, fuente)]
    assert set(capa["estado"]) <= set(ESTADOS) and set(capa["fuente"]) <= set(FUENTES)
    return capa


def con_tiempo_real(capa, tramos, eventos):
    """Aplica los eventos de oscuridad en tiempo real (farol apagado, corte de luz,
    apagon) sobre la capa base: los tramos a menos de su radio pasan a
    'apagada_reportada'. Devuelve una copia."""
    capa = capa.copy()
    if not eventos:
        return capa
    medios = tramos.geometry.interpolate(0.5, normalized=True)
    arbol = cKDTree(np.column_stack([medios.x, medios.y]))
    ev = gpd.GeoSeries(gpd.points_from_xy([e[1] for e in eventos], [e[2] for e in eventos]), crs=4326).to_crs(tramos.crs)
    afectados = {}
    for (tipo, _, _, radio, detalle), p in zip(eventos, ev):
        for i in arbol.query_ball_point((p.x, p.y), radio):
            afectados.setdefault(tramos.index[i], detalle)
    sel = capa.index.isin(list(afectados))
    capa.loc[sel, "estado"] = "apagada_reportada"
    capa.loc[sel, "fuente"] = "tiempo_real"
    capa.loc[sel, "confianza"] = "alta"
    capa.loc[sel, "p_luz"] = P_CONFIRMADA["apagada_reportada"]
    capa.loc[sel, "detalle"] = [afectados[t] for t in capa.index[sel]]
    return capa


def cargar_modelo(carpeta="models"):
    modelo = lgb.Booster(model_file=f"{carpeta}/luz_global.txt")
    meta = json.loads(open(f"{carpeta}/luz_global.json", encoding="utf-8").read())
    return modelo, meta


def brillo_zona(caja, noches=30):
    return LS.brillo(caja, noches=noches)
