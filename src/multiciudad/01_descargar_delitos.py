"""
Multiciudad, paso 1: descargar los delitos de las ciudades de DESARROLLO
(aprender y practica). Las de examen no estan aqui: sus delitos ya estan en la
caja fuerte, y el candado (src/caja_cerrada.py) impide tocarlos.

Se descarga el periodo PERIODO_DESCARGA (con margen) tal como lo publica cada
ciudad, sin cambiar nada. La limpieza y la traduccion de categorias se hacen
en el paso 2.

Salida: data/train/<ciudad>/delitos_crudos.csv y data/practice/<ciudad>/delitos_crudos.csv

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/01_descargar_delitos.py [ciudad ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401  (primero: candado de las cajas fuertes)

import io  # noqa: E402

import pandas as pd  # noqa: E402
import requests  # noqa: E402

from ciudades import DESARROLLO, PERIODO_DESCARGA, carpeta  # noqa: E402

S = requests.Session()
S.headers["User-Agent"] = "safe-routes-pgh/0.1 (proyecto personal)"
PAGINA = 50_000


def socrata(f):
    desde, hasta = PERIODO_DESCARGA
    partes, offset = [], 0
    while True:
        r = S.get(f"https://{f['dominio']}/resource/{f['id']}.csv", timeout=300, params={
            "$where": f"{f['fecha']} between '{desde}T00:00:00' and '{hasta}T23:59:59'",
            "$order": f["orden"], "$limit": PAGINA, "$offset": offset})
        r.raise_for_status()
        parte = pd.read_csv(io.StringIO(r.text), dtype=str)
        partes.append(parte)
        offset += len(parte)
        print(f"    {f['id']}: {offset:,} filas", flush=True)
        if len(parte) < PAGINA:
            break
    return pd.concat(partes, ignore_index=True).assign(_dataset=f["id"])


def arcgis(f):
    desde, hasta = PERIODO_DESCARGA
    filas, offset = [], 0
    while True:
        r = S.get(f"{f['url']}/query", timeout=300, params={
            "where": f"{f['fecha']} >= DATE '{desde}' AND {f['fecha']} <= DATE '{hasta}'",
            "outFields": ",".join(f["campos"]), "returnGeometry": "false", "orderByFields": "OBJECTID",
            "resultOffset": offset, "resultRecordCount": 2000, "f": "json"}).json()
        if "error" in r:
            raise RuntimeError(r["error"])
        feats = r.get("features", [])
        filas += [x["attributes"] for x in feats]
        offset += len(feats)
        if not r.get("exceededTransferLimit") and len(feats) < 2000:
            break
    d = pd.DataFrame(filas)
    for c in d.columns:   # fechas de ArcGIS: milisegundos desde 1970 (UTC)
        if c.startswith("Date_"):
            d[c] = pd.to_datetime(d[c], unit="ms", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"    arcgis: {len(d):,} filas")
    return d.astype(str).replace({"nan": None, "None": None}).assign(_dataset="arcgis")


ciudades = sys.argv[1:] or [c for c, d in DESARROLLO.items() if d["fuente"] != "ya_procesada"]
for ciudad in ciudades:
    cfg = DESARROLLO[ciudad]
    salida = carpeta(ciudad) / "delitos_crudos.csv"
    if salida.exists():
        print(f"{cfg['nombre']}: ya descargada ({salida})")
        continue
    print(f"{cfg['nombre']} ({cfg['grupo']}): descargando {PERIODO_DESCARGA[0]} a {PERIODO_DESCARGA[1]}...")
    fuentes = cfg["fuente"] if isinstance(cfg["fuente"], list) else [cfg["fuente"]]
    datos = pd.concat([socrata(f) if f["tipo"] == "socrata" else arcgis(f) for f in fuentes], ignore_index=True)
    salida.parent.mkdir(parents=True, exist_ok=True)
    datos.to_csv(salida, index=False)
    print(f"  guardado {salida}: {len(datos):,} filas, {datos.shape[1]} columnas")
