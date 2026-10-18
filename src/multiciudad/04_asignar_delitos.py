"""
Multiciudad, paso 4: ubicar cada delito de las ciudades de DESARROLLO en su tramo
de calle y aplicar las exclusiones comunes (investigacion/reglas_de_datos.md, seccion 2).

Motivos de exclusion (lista cerrada, gana el primero):
    ninguno | sin_ubicacion | sin_fecha | sexual          (del paso 2)
    fuera_de_ciudad    fuera del contorno de la ciudad
    lejos_de_calle     a mas de DISTANCIA_MAX m de una calle caminable
    lugar_cerrado      a menos de DISTANCIA_LUGAR m de una carcel, hospital,
                       comisaria o centro de servicios sociales (OpenStreetMap)

Entradas: data/<grupo>/<ciudad>/delitos.csv (paso 2), data/public_features/<ciudad>/ (paso 3)
Salida:   data/<grupo>/<ciudad>/delitos_tramo.csv

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/04_asignar_delitos.py [ciudad ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import osmnx as ox  # noqa: E402
import pandas as pd  # noqa: E402

import preparar as PR  # noqa: E402
from ciudades import DESARROLLO, carpeta, carpeta_publica  # noqa: E402

MOTIVOS = PR.MOTIVOS

resumen = []
for ciudad in sys.argv[1:] or list(DESARROLLO):
    cfg, pub = DESARROLLO[ciudad], carpeta_publica(ciudad)
    print(f"{cfg['nombre']}...", flush=True)
    G = ox.project_graph(ox.load_graphml(pub / "red_peatonal.graphml"), to_crs=cfg["crs"])
    d = pd.read_csv(carpeta(ciudad) / "delitos.csv", dtype={"codigo": str, "clase_nucleo": str,
                                                            "categoria_amplia": str, "bolsa": str})
    limite = gpd.read_file(pub / "limite.geojson").to_crs(cfg["crs"]).geometry.iloc[0]
    lugares = gpd.read_file(pub / "osm.gpkg", layer="lugares")
    d = PR.asignar(d, G, limite, lugares, cfg["crs"])   # comun con el examen
    d.to_csv(carpeta(ciudad) / "delitos_tramo.csv", index=False)
    m = d["motivo_exclusion"].value_counts(normalize=True).mul(100).round(1)
    ok = d[d["motivo_exclusion"] == "ninguno"]
    fila = {"ciudad": ciudad, "registros": len(d), **{f"{k} %": m.get(k, 0.0) for k in MOTIVOS[1:]},
            "nucleo validos": int(ok["clase_nucleo"].notna().sum()),
            "tramos con delito": ok["tramo_id"].nunique(), "tramos en la red": G.number_of_edges() // 2}
    resumen.append(fila)

pd.set_option("display.width", 220)
print("\n" + pd.DataFrame(resumen).set_index("ciudad").to_string())
