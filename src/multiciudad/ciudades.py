"""
Ciudades del estudio de transferencia (investigacion/protocolo.md; sorteo con 4818).

DESARROLLO: sus delitos se pueden descargar y explorar.
    aprender: Pittsburgh, Chapel Hill, Chicago, Seattle
    practica: Cincinnati, Gainesville
EXAMEN y RESERVA: aqui solo figuran para los datos PUBLICOS (calles, poblacion,
transporte...). Sus delitos estan en la caja fuerte y ningun programa de
desarrollo los toca (src/caja_cerrada.py).
"""
from pathlib import Path

PERIODO_DESCARGA = ("2023-12-01", "2026-09-30")   # con margen; el periodo del estudio lo fija reglas_de_datos.md

DESARROLLO = {
    "pittsburgh": {"grupo": "train", "nombre": "Pittsburgh, PA", "crs": 32617,
                   "lugar": "Pittsburgh, Pennsylvania, USA", "fuente": "ya_procesada"},
    "chapel_hill": {"grupo": "train", "nombre": "Chapel Hill, NC", "crs": 32617,
                    "lugar": "Chapel Hill, North Carolina, USA",
                    "fuente": {"tipo": "arcgis",
                               "url": "https://services2.arcgis.com/7KRXAKALbBGlCW77/arcgis/rest/services/Recoded_Incidents_New/FeatureServer/0",
                               "fecha": "Date_of_Report",
                               # sin datos de la victima (raza, edad, genero): las reglas prohiben usarlos
                               "campos": ["Incident_ID", "Agency", "Offense", "Street", "City", "Date_of_Report",
                                          "Date_of_Occurrence", "Date_Found", "Reported_As", "Premise_Description",
                                          "Forcible", "Weapon_Description", "Latitude", "Longitude"]}},
    "chicago": {"grupo": "train", "nombre": "Chicago, IL", "crs": 32616, "lugar": "Chicago, Illinois, USA",
                "fuente": {"tipo": "socrata", "dominio": "data.cityofchicago.org", "id": "ijzp-q8t2",
                           "fecha": "date", "orden": "id"}},
    "seattle": {"grupo": "train", "nombre": "Seattle, WA", "crs": 32610, "lugar": "Seattle, Washington, USA",
                "fuente": {"tipo": "socrata", "dominio": "data.seattle.gov", "id": "tazs-3rd5",
                           "fecha": "report_date_time", "orden": "offense_id"}},
    "cincinnati": {"grupo": "practice", "nombre": "Cincinnati, OH", "crs": 32616, "lugar": "Cincinnati, Ohio, USA",
                   "fuente": [{"tipo": "socrata", "dominio": "data.cincinnati-oh.gov", "id": "8xzn-kpn7",
                               "fecha": "datereported", "orden": "incident_no"},
                              {"tipo": "socrata", "dominio": "data.cincinnati-oh.gov", "id": "7aqy-xrv9",
                               "fecha": "datereported", "orden": "incident_no"}]},
    "gainesville": {"grupo": "practice", "nombre": "Gainesville, FL", "crs": 32617,
                    "lugar": "Gainesville, Florida, USA",
                    "fuente": {"tipo": "socrata", "dominio": "data.cityofgainesville.org", "id": "gvua-xt9q",
                               "fecha": "report_date", "orden": "id"}},
}

# Solo datos publicos (nunca delitos)
EXAMEN = {
    "filadelfia": {"grupo": "holdout_main", "nombre": "Philadelphia, PA", "crs": 32618, "lugar": "Philadelphia, Pennsylvania, USA"},
    "baton_rouge": {"grupo": "holdout_main", "nombre": "Baton Rouge, LA", "crs": 32615, "lugar": "Baton Rouge, Louisiana, USA"},
    "tempe": {"grupo": "holdout_main", "nombre": "Tempe, AZ", "crs": 32612, "lugar": "Tempe, Arizona, USA"},
}


MDB = "https://storage.googleapis.com/storage/v1/b/mdb-latest/o/{}?alt=media"   # Mobility Database
# Datos publicos de TODAS las ciudades (desarrollo y examen): mapa del estado (Geofabrik),
# codigo de estado para empleos (LEHD LODES) y horarios del operador urbano principal (GTFS)
PUBLICOS = {
    "pittsburgh": {"estado": "pennsylvania", "lodes": "pa",
                   "gtfs": [MDB.format("us-pennsylvania-port-authority-of-allegheny-county-gtfs-409.zip")]},
    "chapel_hill": {"estado": "north-carolina", "lodes": "nc",
                    "gtfs": ["http://data.trilliumtransit.com/gtfs/chapel-hill-transit-nc-us/chapel-hill-transit-nc-us.zip"]},
    "chicago": {"estado": "illinois", "lodes": "il",
                "gtfs": [MDB.format("us-illinois-chicago-transit-authority-cta-gtfs-389.zip")]},
    "seattle": {"estado": "washington", "lodes": "wa",
                "gtfs": [MDB.format("us-washington-king-county-metro-gtfs-1330.zip"),
                         MDB.format("us-washington-sound-transit-gtfs-268.zip")]},
    "cincinnati": {"estado": "ohio", "lodes": "oh", "gtfs": [MDB.format("us-ohio-cincinnati-metro-gtfs-307.zip")]},
    "gainesville": {"estado": "florida", "lodes": "fl",
                    # la copia del catalogo ya no existe: la del operador (RTS), vigente ago 2024 - ago 2025
                    "gtfs": ["http://go-rts.com/wp-content/uploads/2025/01/RTSGTFS_Spring2025.zip"]},
    "filadelfia": {"estado": "pennsylvania", "lodes": "pa",
                   "gtfs": [MDB.format("us-pennsylvania-southeastern-pennsylvania-transportation-authority-gtfs-502.zip"),
                            MDB.format("us-pennsylvania-southeastern-pennsylvania-transportation-authority-gtfs-503.zip")]},
    "baton_rouge": {"estado": "louisiana", "lodes": "la",
                    "gtfs": [MDB.format("us-louisiana-capital-area-transit-system-cats-gtfs-2065.zip")]},
    "tempe": {"estado": "arizona", "lodes": "az", "gtfs": [MDB.format("us-arizona-valley-metro-vm-gtfs-147.zip")]},
}
TODAS = {**DESARROLLO, **EXAMEN}


def carpeta(ciudad):
    """Carpeta de trabajo de una ciudad de desarrollo (data/train/<ciudad> o data/practice/<ciudad>)."""
    return Path("data") / DESARROLLO[ciudad]["grupo"] / ciudad


def carpeta_publica(ciudad):
    """Carpeta de datos publicos de cualquier ciudad (sin delitos)."""
    return Path("data/public_features") / ciudad
