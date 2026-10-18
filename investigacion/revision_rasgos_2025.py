"""
R3 de la revision (investigacion/analisis_revision.md, commit 78484c0): FUGA TEMPORAL de los
rasgos publicos. Se rehacen los rasgos que salen de OpenStreetMap y de los horarios (GTFS)
con datos ANTERIORES al periodo evaluado y se vuelven a aplicar los modelos SELLADOS.

    python investigacion/revision_rasgos_2025.py validar     Gainesville con sus entradas de 2026: el
                                                           constructor debe reproducir tramos.csv y
                                                           tramos_lugares.csv (los pasos 5 y 5b)
    python investigacion/revision_rasgos_2025.py construir [ciudad ...]
                                                           OSM 2025-01-01 (Geofabrik) + GTFS previos
    python investigacion/revision_rasgos_2025.py evaluar [ciudad ...]
                                                           control (con los rasgos de 2026 se
                                                           reproducen los mapas del examen) y rutas
El constructor NO copia el codigo de los pasos 5 y 5b: carga esos mismos programas y solo les
cambia la carpeta (y la luz satelital, que no tiene fuga: se copia la columna ya calculada).
Salida: data/public_features_2025/<ciudad>/ (rasgos) e investigacion/resultados/revision/ (rutas)
"""
import importlib.util
import json
import shutil
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src" / "multiciudad"))
sys.path.insert(0, str(RAIZ / "investigacion"))
import analisis_transporte as AT  # noqa: E402
import evaluar_rutas as E  # noqa: E402
import flujo as F  # noqa: E402
import formula as FO  # noqa: E402
import osm_local as OL  # noqa: E402
import reparto as RR  # noqa: E402
from ciudades import PUBLICOS, TODAS, carpeta_publica  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

MARGEN = 1000   # como los pasos 3 y 5b
DATOS_2025 = RAIZ / "data/public_features_2025"
SALIDA = RAIZ / "investigacion/resultados/revision"
CARPETAS = {"filadelfia": RAIZ / "investigacion/resultados/examen_v2",
            "baton_rouge": RAIZ / "investigacion/resultados/examen_v2",
            "tempe": RAIZ / "investigacion/resultados/examen_v2_tempe"}
# Horarios anteriores al 2025-09-01 (plan, R3). Solo SEPTA tiene una version publica previa;
# CATS y Valley Metro conservan los de 2026 (no se encontro ninguna anterior).
GTFS_2025 = {"filadelfia": ("septa", DATOS_2025 / "gtfs_septa/gtfs_public_v202508311.zip",
                            ["google_bus.zip", "google_rail.zip"])}
SEMILLA = 20261011
SELLO = RAIZ / "investigacion/sello_v2.json"
MODELOS = RAIZ / "models/multiciudad/v2"


def _modulo(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, archivo)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# --------------------------------------------------------------------------------------
# Constructor
def preparar_carpeta(ciudad, salida, pbf=None, cache_osm=None, cache_extra=None, gtfs=None):
    """Arma la carpeta de entradas como el paso 3: red, contorno y manzanas sin cambios (2026),
    capas de OSM desde 'pbf' (o desde los cache dados) y los horarios 'gtfs' (lista de zips)."""
    cfg, orig = TODAS[ciudad], carpeta_publica(ciudad)
    salida.mkdir(parents=True, exist_ok=True)
    for nombre in ["red_peatonal.graphml", "limite.geojson", "manzanas.gpkg"]:
        shutil.copy2(orig / nombre, salida / nombre)
    if cache_osm:
        shutil.copy2(cache_osm, salida / "osm.pkl")
    if cache_extra:
        shutil.copy2(cache_extra, salida / "osm_extra.pkl")
    limite = gpd.read_file(salida / "limite.geojson")
    poligono = limite.geometry.iloc[0]
    caja = tuple(limite.to_crs(cfg["crs"]).buffer(MARGEN).to_crs(4326).total_bounds)
    d = OL.leer_ciudad(pbf, caja, salida / "osm.pkl")
    if not (salida / "osm.gpkg").exists():   # mismas capas y columnas que el paso 3
        OL.calles_gdf(d).to_file(salida / "osm.gpkg", layer="calles", driver="GPKG")
        OL.parques_gdf(d).to_file(salida / "osm.gpkg", layer="parques", driver="GPKG")
        OL.paradas_gdf(d).to_file(salida / "osm.gpkg", layer="paradas", driver="GPKG")
        lugares = OL.lugares(d, poligono.buffer(0.01))
        columnas = [c for c in ["amenity", "shop", "name", "opening_hours", "parking", "capacity",
                                "building:levels", "access", "leisure"] if c in lugares]
        lugares[columnas + ["geometry"]].to_file(salida / "osm.gpkg", layer="lugares", driver="GPKG")
    OL.leer_extra(pbf, caja, salida / "osm_extra.pkl")   # el paso 5b lo encuentra ya hecho
    for viejo in salida.glob("gtfs_*.zip"):
        viejo.unlink()
    for i, z in enumerate(gtfs):
        shutil.copy2(z, salida / f"gtfs_{i}.zip")


def rasgos(ciudad, salida):
    """Los pasos 5 y 5b, sin cambios, sobre 'salida'. La luz se copia del paso 5 original."""
    cfg = TODAS[ciudad]
    radiancia = pd.read_csv(carpeta_publica(ciudad) / "tramos.csv", index_col="tramo_id")["radiancia"]
    G = ox.project_graph(ox.load_graphml(salida / "red_peatonal.graphml"), to_crs=cfg["crs"])
    _, medios = F.tramos_y_medios(G)
    orden = medios.index
    luz = SimpleNamespace(brillo=lambda caja, hasta, noches: {"noches": "copiada del paso 5 (sin fuga)"},
                          valor_en=lambda brillo, x, y: radiancia.reindex(orden).values)
    argv = sys.argv
    try:
        for archivo in ["05_rasgos_publicos.py", "05b_rasgos_lugares.py"]:
            m = _modulo(archivo[:-3], RAIZ / "src/multiciudad" / archivo)
            m.carpeta_publica = lambda c: salida
            if hasattr(m, "LS"):
                m.LS = luz
            sys.argv = [archivo, ciudad]
            m.main()
    finally:
        sys.argv = argv


def comparar(original, nuevo, columnas):
    """Diferencia relativa maxima por columna (las que usa el modelo)."""
    a = pd.read_csv(original, index_col="tramo_id")
    b = pd.read_csv(nuevo, index_col="tramo_id").reindex(a.index)
    filas = []
    for c in columnas:
        if c not in a:
            continue
        numerica = lambda s: pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
        if not (numerica(a[c]) and numerica(b[c])):   # texto o verdadero/falso: deben ser identicos
            ok = bool((a[c].astype(str) == b[c].astype(str)).all())
            filas.append({"columna": c, "diferencia_relativa_max": 0.0 if ok else np.inf})
            continue
        dif = (a[c] - b[c]).abs() / np.maximum(a[c].abs(), 1e-9)
        filas.append({"columna": c, "diferencia_relativa_max": float(dif.max())})
    return pd.DataFrame(filas)


def columnas_del_modelo():
    fijas = FO.FIJOS_MAPA + FO.LUGARES_MAPA + FO.PARADAS_OSM + FO.FIJOS_OTROS + ["tipo"]
    por_franja = [f"{n}_{f}" for n in FO.POR_FRANJA_MAPA + FO.POR_FRANJA_OTROS for f in FRANJAS]
    return fijas + por_franja


def validar():
    ciudad = "gainesville"
    orig = carpeta_publica(ciudad)
    salida = RAIZ / "data/practice/revision/rasgos_validacion_gainesville"
    if salida.exists():
        shutil.rmtree(salida)
    preparar_carpeta(ciudad, salida, pbf=None, cache_osm=orig / "osm.pkl", cache_extra=orig / "osm_extra.pkl",
                     gtfs=sorted(orig.glob("gtfs_*.zip")))
    rasgos(ciudad, salida)
    t = pd.concat([comparar(orig / "tramos.csv", salida / "tramos.csv", columnas_del_modelo()),
                   comparar(orig / "tramos_lugares.csv", salida / "tramos_lugares.csv", columnas_del_modelo())])
    t.to_csv(RAIZ / "data/practice/revision/r3_validacion_constructor.csv", index=False)
    print(t.to_string(index=False))
    ok = bool((t["diferencia_relativa_max"] <= 1e-6).all())
    print(f"\nVALIDACION DEL CONSTRUCTOR (Gainesville, entradas de 2026): {'OK' if ok else 'NO REPRODUCE'}")
    return ok


def encabezados_sin_espacios(contenido_zip, destino):
    """Copia un GTFS (bytes de un .zip) quitando los espacios alrededor de los nombres de columna
    de cada .txt (cambio 4 del plan: SEPTA 2025-08-30 trae " start_date"). Los datos no cambian;
    las carpetas __MACOSX del archivo original se omiten."""
    import io
    with zipfile.ZipFile(io.BytesIO(contenido_zip)) as z, zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as w:
        for n in z.namelist():
            if n.startswith("__MACOSX") or n.endswith("/"):
                continue
            datos = z.read(n)
            if n.endswith(".txt"):
                texto = datos.decode("utf-8-sig")
                primera, _, resto = texto.partition("\n")
                fin = "\r" if primera.endswith("\r") else ""
                primera = ",".join(c.strip() for c in primera.rstrip("\r").split(",")) + fin
                datos = (primera + "\n" + resto).encode("utf-8")
            w.writestr(n, datos)


def agregar_filas(archivo, nuevas, clave="ciudad"):
    """Guarda 'nuevas' reemplazando solo las filas de sus ciudades (las demas se conservan)."""
    if archivo.exists() and len(nuevas):
        viejas = pd.read_csv(archivo)
        viejas = viejas[~viejas[clave].isin(nuevas[clave].unique())]
        nuevas = pd.concat([viejas, nuevas], ignore_index=True)
    nuevas.to_csv(archivo, index=False)


def construir(ciudades):
    for ciudad in ciudades:
        estado = PUBLICOS[ciudad]["estado"]
        pbf = DATOS_2025 / "osm" / f"{estado}-250101.osm.pbf"
        salida = DATOS_2025 / ciudad
        if ciudad in GTFS_2025:
            _, archivo, nombres = GTFS_2025[ciudad]
            extraidos = []
            with zipfile.ZipFile(archivo) as z:
                for n in nombres:
                    destino = DATOS_2025 / "gtfs_septa" / f"limpio_{n}"
                    encabezados_sin_espacios(z.read(n), destino)   # cambio 4 del plan
                    extraidos.append(destino)
            gtfs = extraidos
        else:
            gtfs = sorted(carpeta_publica(ciudad).glob("gtfs_*.zip"))   # 2026: no hay version previa
        print(f"=== {ciudad}: OSM {pbf.name}, GTFS {[g.name for g in gtfs]}", flush=True)
        preparar_carpeta(ciudad, salida, pbf=pbf, gtfs=gtfs)
        rasgos(ciudad, salida)
        (salida / "fuentes.json").write_text(json.dumps({"osm": pbf.name, "gtfs": [Path(g).resolve().relative_to(RAIZ).as_posix() for g in gtfs],
                                                         "gtfs_es_2026": ciudad not in GTFS_2025}, indent=2))


# --------------------------------------------------------------------------------------
# Evaluacion
def modelos_sellados():
    import hashlib
    import lightgbm as lgb
    sello = json.loads(SELLO.read_text(encoding="utf-8"))
    modelos = {}
    for nivel in FO.NIVELES:
        for ext in ("txt", "json"):
            archivo = MODELOS / f"{nivel}.{ext}"
            if hashlib.sha256(archivo.read_bytes()).hexdigest() != sello["huellas"][archivo.name]:
                sys.exit(f"El modelo {archivo} no coincide con el sello.")
        modelos[nivel] = (lgb.Booster(model_file=str(MODELOS / f"{nivel}.txt")),
                          json.loads((MODELOS / f"{nivel}.json").read_text()))
    return modelos


def mapas_de(publicos, mapa_delitos, ciudad, modelos):
    x = FO.largo_formato(publicos, mapa_delitos, ciudad)
    mapas = {nivel: FO.predecir(modelo, cats, x, nivel) for nivel, (modelo, cats) in modelos.items()
             if all(c in x.columns for c in FO.DELITOS[nivel])}
    mapas["evitar_avenidas"] = 1 / (1 + x["dist_principal"].values / 100)
    mapas["evitar_comercios"] = 1 + x["locales_400"].values
    return x, mapas


def evaluar(ciudades):
    modelos = modelos_sellados()
    rng = np.random.default_rng(SEMILLA)
    filas, controles = [], []
    for ciudad in ciudades:
        carpeta = CARPETAS[ciudad]
        red = carpeta_publica(ciudad) / "red_peatonal.graphml"
        largo_red = RR.tramos_de(ox.load_graphml(red))["largo"]
        mapa_delitos = pd.read_csv(carpeta / f"{ciudad}_mapa_delitos.csv", index_col="tramo_id")
        # control: con los rasgos de 2026, el programa reproduce los mapas del examen
        x26, m26 = mapas_de(FO.leer_publicos(carpeta_publica(ciudad)), mapa_delitos, ciudad, modelos)
        for nombre, riesgo in m26.items():
            viejo = pd.read_csv(carpeta / f"{ciudad}_riesgo_{nombre}.csv", index_col="tramo_id")
            nuevo = FO.mapa_de_riesgo(x26, riesgo, largo_red).reindex(index=viejo.index, columns=viejo.columns)
            dif = float(np.nanmax(np.abs(nuevo.values - viejo.values)))
            controles.append({"ciudad": ciudad, "mapa": nombre, "diferencia_maxima": dif, "reproduce": dif <= 1e-9})
        if not all(c["reproduce"] for c in controles if c["ciudad"] == ciudad):
            agregar_filas(SALIDA / "r3_control.csv", pd.DataFrame(controles))
            sys.exit(f"{ciudad}: con los rasgos de 2026 no se reproducen los mapas del examen. No se sigue.")
        print(f"  {ciudad}: control OK (los {len(m26)} mapas del examen se reproducen)", flush=True)
        x, mapas = mapas_de(FO.leer_publicos(DATOS_2025 / ciudad), mapa_delitos, ciudad, modelos)
        lista, zonas = AT.zonas_de(red, ciudad, 2000)
        futuro = mapa_delitos[[f"fut_{f}" for f in FRANJAS]]
        for nombre, riesgo in mapas.items():
            archivo = SALIDA / f"r3_{ciudad}_viajes_{nombre}_2000.jsonl"
            if archivo.exists():
                v = pd.read_json(archivo, lines=True)
            else:
                ruta = SALIDA / f"r3_{ciudad}_riesgo_{nombre}.csv"
                FO.mapa_de_riesgo(x, riesgo, largo_red).to_csv(ruta)
                v = E.simular(f"r3_{ciudad}_{nombre}", red, ruta, lista)
                v.to_json(archivo, orient="records", lines=True)
            reg = E.calificar(v, futuro)
            todos = AT.resumen(AT.por_viaje(v, {f: futuro[f"fut_{f}"] for f in FRANJAS}), zonas, rng)
            examen = json.loads((carpeta / f"{ciudad}_rutas_{nombre}_2000.json").read_text())
            filas.append({"ciudad": ciudad, "mapa": nombre, "cambio_registrado": reg.get("cambio_pct", np.nan),
                          "ic95_registrado": reg.get("ic95", [np.nan, np.nan]), "examen_registrado": examen.get("cambio_pct", np.nan),
                          "cambio_todos": todos["cambio_todos"], "ic95_todos_zonas": todos["ic95_zonas"],
                          "viajes_con_alternativa": reg["viajes_con_menor_riesgo"]})
            print(f"  {ciudad} {nombre}: {filas[-1]['cambio_registrado']:+.1f}% (examen {filas[-1]['examen_registrado']:+.1f}%) "
                  f"| todos {filas[-1]['cambio_todos']:+.1f}%", flush=True)
            agregar_filas(SALIDA / "r3_fuga_temporal.csv", pd.DataFrame(filas))
        agregar_filas(SALIDA / "r3_control.csv", pd.DataFrame(controles))
    return pd.DataFrame(filas)


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    accion = sys.argv[1]
    ciudades = sys.argv[2:] or list(CARPETAS)
    if accion == "validar":
        sys.exit(0 if validar() else 1)
    if accion == "construir":
        construir(ciudades)
    elif accion == "evaluar":
        pd.set_option("display.width", 250)
        print(evaluar(ciudades).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
