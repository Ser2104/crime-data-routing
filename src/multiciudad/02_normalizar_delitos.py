"""
Multiciudad, paso 2: dejar los delitos de las ciudades de DESARROLLO en un formato
comun, con las categorias traducidas (src/multiciudad/categorias.py).

Columnas de salida (listas cerradas donde corresponde):
    ciudad, id, fecha (local, AAAA-MM-DD), hora (0-23), hora_tipo (ocurrencia | reporte),
    hora_desconocida (la hora exacta 00:00 suele ser "sin hora", como en Pittsburgh),
    lat, lon, original (categoria tal como la publica la ciudad), codigo,
    clase_nucleo, categoria_amplia, bolsa,
    motivo_exclusion (ninguno | sin_ubicacion | sin_fecha | sexual)
Solo se guarda el periodo del estudio (reglas_de_datos.md: 2024-01-01 a 2026-08-31).

Salida: data/<grupo>/<ciudad>/delitos.csv

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/02_normalizar_delitos.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import categorias as K  # noqa: E402
import preparar as PR  # noqa: E402
from ciudades import DESARROLLO, carpeta  # noqa: E402

DESDE, HASTA = PR.DESDE, PR.HASTA
pd.set_option("display.width", 200)


def hora_de(fecha_hora):
    """Hora local (0-23) de un texto de fecha y hora tal como lo publica la ciudad."""
    return pd.to_datetime(fecha_hora.str.slice(0, 19), errors="coerce", format="%Y-%m-%dT%H:%M:%S")


def leer(ciudad):
    """DataFrame con: id, momento (fecha y hora local), hora_tipo, lat, lon, original, codigo."""
    if ciudad == "pittsburgh":
        d = pd.read_excel("data/raw/pbp_incidents_2024_2026.xlsx", sheet_name="AllMergedTables")
        # un reporte puede tener varios delitos: uno por reporte, el de la clase mas importante
        d["codigo"] = d["NIBRS_Offense_Code"].map(K.codigo_nibrs)
        orden = {c: i for i, c in enumerate(["09A", "120", "13A", K.SEXUAL])}
        d = d.assign(_o=d["codigo"].map(orden).fillna(9)).sort_values("_o").drop_duplicates("Report_Number")
        hora = d["ReportedTime"].astype(str).str.strip().str.zfill(5)
        momento = pd.to_datetime(pd.to_datetime(d["ReportedDate"]).dt.strftime("%Y-%m-%d") + " " + hora,
                                 errors="coerce")
        return pd.DataFrame({"id": d["Report_Number"].astype(str), "momento": momento, "hora_tipo": "reporte",
                             "lat": d["YCOORD"], "lon": d["XCOORD"], "original": d["NIBRS_Offense_Type"],
                             "codigo": d["codigo"]})
    crudo = pd.read_csv(carpeta(ciudad) / "delitos_crudos.csv", dtype=str)
    if ciudad == "chicago":
        return pd.DataFrame({"id": crudo["id"], "momento": hora_de(crudo["date"]), "hora_tipo": "ocurrencia",
                             "lat": crudo["latitude"], "lon": crudo["longitude"],
                             "original": crudo["primary_type"] + " / " + crudo["description"],
                             "codigo": [K.codigo_chicago(f, t) for f, t in zip(crudo["fbi_code"], crudo["primary_type"])]})
    if ciudad == "seattle":
        return pd.DataFrame({"id": crudo["offense_id"], "momento": hora_de(crudo["offense_date"]),
                             "hora_tipo": "ocurrencia", "lat": crudo["latitude"], "lon": crudo["longitude"],
                             "original": crudo["nibrs_offense_code_description"],
                             "codigo": crudo["nibrs_offense_code"].map(K.codigo_nibrs)})
    if ciudad == "gainesville":
        return pd.DataFrame({"id": crudo["id"], "momento": hora_de(crudo["offense_date"]), "hora_tipo": "ocurrencia",
                             "lat": crudo["latitude"], "lon": crudo["longitude"], "original": crudo["narrative"],
                             "codigo": crudo["narrative"].map(lambda n: K.codigo_por_nombre("gainesville", n))})
    if ciudad == "chapel_hill":
        # ArcGIS marca la hora LOCAL como si fuera UTC (la hora mas tranquila sale a las 4-5 a. m.):
        # se usa tal como viene, sin convertir
        return pd.DataFrame({"id": crudo["Incident_ID"], "momento": hora_de(crudo["Date_of_Occurrence"]),
                             "hora_tipo": "ocurrencia", "lat": crudo["Latitude"], "lon": crudo["Longitude"],
                             "original": crudo["Offense"],
                             "codigo": crudo["Offense"].map(lambda n: K.codigo_por_nombre("chapel_hill", n))})
    if ciudad == "cincinnati":
        momento = hora_de(crudo["datefrom"]).fillna(hora_de(crudo["datereported"]))
        return pd.DataFrame({"id": crudo["incident_no"], "momento": momento, "hora_tipo": "ocurrencia",
                             "lat": crudo["latitude_x"], "lon": crudo["longitude_x"], "original": crudo["stars_category"],
                             "codigo": crudo["stars_category"].map(K.CINCINNATI_STARS)})
    raise ValueError(ciudad)


resumen = []
for ciudad, cfg in DESARROLLO.items():
    d = PR.normalizar(leer(ciudad), ciudad, ciudad in K.CON_DETALLE)   # comun con el examen
    carpeta(ciudad).mkdir(parents=True, exist_ok=True)
    d.to_csv(carpeta(ciudad) / "delitos.csv", index=False)

    v = d[d["motivo_exclusion"] == "ninguno"]
    anios = (pd.Timestamp(HASTA) - pd.Timestamp(DESDE)).days / 365.25
    nucleo = v["clase_nucleo"].value_counts()
    resumen.append({"ciudad": ciudad, "grupo": cfg["grupo"], "registros": len(d), "validos": len(v),
                    "sin_ubicacion %": round((d["motivo_exclusion"] == "sin_ubicacion").mean() * 100, 1),
                    "sin_hora %": round(v["hora_desconocida"].mean() * 100, 1),
                    "homicidio/anio": round(nucleo.get("homicidio", 0) / anios),
                    "robo/anio": round(nucleo.get("robo", 0) / anios),
                    "agresion_grave/anio": round(nucleo.get("agresion_grave", 0) / anios),
                    "nucleo/anio": round(nucleo.sum() / anios),
                    "amplia/anio": round(v["categoria_amplia"].notna().sum() / anios) if ciudad in K.CON_DETALLE else None})
    print(f"{ciudad}: listo ({len(d):,} registros)")

print("\n" + pd.DataFrame(resumen).set_index("ciudad").to_string())
