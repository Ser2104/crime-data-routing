"""
Multiciudad, paso 9: EL EXAMEN (investigacion/protocolo.md). Escrito y guardado en
git ANTES de abrir la caja fuerte. Califica la formula SELLADA (models/multiciudad/v2,
huellas en investigacion/sello_v2.json) en las ciudades del examen principal:
Filadelfia, Baton Rouge y Tempe.

Requisito: el autor abrio la caja con su frase:
    python investigacion/caja_fuerte.py abrir holdout_main --motivo "examen formula v2"
Este programa solo puede leer data/examen_abierto/holdout_main/ (candado propio):
ni la reserva, ni las otras cajas.

Antes de calificar nada, un CHEQUEO DE LECTURA por ciudad (solo formato: fechas,
coordenadas y categorias que se pudieron leer). Si no pasa los minimos, el programa
se detiene sin calcular ningun resultado: se corrige SOLO el lector (nunca la formula
ni las tablas de categorias), se anota como desviacion y se vuelve a correr.

Para cada ciudad, con el MISMO procedimiento que el desarrollo:
    1. delitos: traduccion (categorias.py, escrita antes de abrir) y preparar.normalizar
    2. ubicacion en calles y exclusiones: preparar.asignar
    3. rasgos de delitos por nivel: rasgos_delitos.construir
    4. mapas: la formula sellada en cada nivel + referencias (mapas de calor, oraculo,
       "evitar avenidas", "evitar comercios") + prueba trampa (el mapa del mejor nivel
       con los valores mezclados al azar entre tramos)
    5. calificacion rapida (calificacion.py) + prueba trampa de etiquetas (el mismo mapa
       contra delitos del futuro mezclados al azar: debe dar ~0.10)
    6. rutas: 2,000 viajes por ciudad con el buscador de la app (evaluar_rutas.py), en
       delitos y por persona
Salida: investigacion/resultados/examen_v2/ (un archivo por ciudad y mapa, y resumen.md)

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/09_examen.py [--ciudades ...] [--viajes N] [--solo-lectura]
    python src/multiciudad/09_examen.py --grupo holdout_tempe2
        (examen de reemplazo de Tempe, 2026-10: descarga directa del servicio oficial,
         porque la del examen principal era una copia desactualizada;
         investigacion/desviaciones_examen_v2.md)
    python src/multiciudad/09_examen.py --ensayo gainesville --viajes 100
        (ensayo con una ciudad de PRACTICA y sus delitos ya preparados: prueba todo el
         camino sin tocar el examen; resultados en data/practice/ensayo_examen/)
"""
import argparse
import hashlib
import json
import os
import sys
import zlib
from pathlib import Path

# --- Candado propio: solo el examen principal ya abierto --------------------------
PERMITIDAS = ("/data/examen_abierto/holdout_main/", "/data/examen_abierto/holdout_tempe2/")


def _candado(evento, args):
    if evento in {"open", "os.listdir", "os.scandir", "shutil.copyfile", "shutil.copytree", "os.rename"} and args:
        try:
            ruta = os.path.abspath(os.fsdecode(args[0])).replace("\\", "/").lower()
        except (TypeError, ValueError):
            return
        if ("/data/holdout_" in ruta or "/data/examen_abierto" in ruta) and not any(x in ruta + "/" for x in PERMITIDAS):
            raise PermissionError(f"Candado del examen: solo se puede leer {PERMITIDAS} ({args[0]})")


sys.addaudithook(_candado)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd  # noqa: E402
import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import osmnx as ox  # noqa: E402
import pandas as pd  # noqa: E402

import calificacion as CA  # noqa: E402
import categorias as K  # noqa: E402
import evaluar_rutas as E  # noqa: E402
import flujo as F  # noqa: E402
import formula as FO  # noqa: E402
import preparar as PR  # noqa: E402
import rasgos_delitos as RD  # noqa: E402
import reparto as RR  # noqa: E402
from ciudades import DESARROLLO, EXAMEN, carpeta, carpeta_publica  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

# Cada examen: su carpeta abierta, sus ciudades y su carpeta de resultados
GRUPOS = {"holdout_main": {"ciudades": list(EXAMEN), "salida": "investigacion/resultados/examen_v2"},
          "holdout_tempe2": {"ciudades": ["tempe"], "salida": "investigacion/resultados/examen_v2_tempe"}}
MODELOS = Path("models/multiciudad/v2")
SELLO = Path("investigacion/sello_v2.json")
ARCHIVOS = {"filadelfia": "filadelfia.csv", "baton_rouge": "baton_rouge.csv", "tempe": "tempe.csv"}
# Comparaciones PAREADAS pre-registradas (investigacion/preregistro.md): (mapa base, mapa comparado)
PAREJAS = [("mapa_de_calor_A", "A"), ("mapa_de_calor_B", "B"),
           ("evitar_avenidas", "sin_delitos"), ("evitar_comercios", "sin_delitos")]
RETENCION = ["A", "C", "zona", "totales", "sin_delitos", "solo_mapa"]   # parte del beneficio de B que conserva cada nivel
REMUESTREOS_VIAJES = 2000


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


def modelos_sellados():
    """Carga los modelos v2 SOLO si sus huellas coinciden con el sello."""
    sello = json.loads(SELLO.read_text(encoding="utf-8"))
    modelos = {}
    for nivel in FO.NIVELES:
        for ext in ("txt", "json"):
            archivo = MODELOS / f"{nivel}.{ext}"
            if sha256(archivo) != sello["huellas"][archivo.name]:
                sys.exit(f"El modelo {archivo} no coincide con el sello. No se califica nada.")
        modelos[nivel] = (lgb.Booster(model_file=str(MODELOS / f"{nivel}.txt")),
                          json.loads((MODELOS / f"{nivel}.json").read_text()))
    return modelos


# --- Lectura de cada ciudad de examen (formatos segun su documentacion) -----------
def _norm(nombre):
    return "".join(ch for ch in str(nombre).lower() if ch.isalnum())


def _col(d, *nombres):
    """Columna por nombre, sin importar mayusculas, espacios o guiones (los portales
    exportan a veces el nombre visible y a veces el nombre interno)."""
    mapa = {_norm(c): c for c in d.columns}
    for n in nombres:
        if _norm(n) in mapa:
            return d[mapa[_norm(n)]]
    raise KeyError(f"Falta la columna {nombres}")


def _fecha(serie):
    return pd.to_datetime(serie, errors="coerce", format="mixed")


def _uno_por_caso(d, columna_caso):
    """Un delito por caso: el de la clase mas importante del nucleo (como Pittsburgh)."""
    orden = {c: i for i, c in enumerate(["09A", "120", "13A", K.SEXUAL])}
    return (d.assign(_o=d["codigo"].map(orden).fillna(9)).sort_values("_o", kind="stable")
             .drop_duplicates(columna_caso).drop(columns="_o"))


def leer_examen(ciudad, grupo="holdout_main"):
    d = pd.read_csv(Path("data/examen_abierto") / grupo / ARCHIVOS[ciudad], dtype=str, low_memory=False)
    if ciudad == "filadelfia":
        # hora del despacho (local); ubicacion redondeada a la cuadra
        hora = _col(d, "dispatch_time").fillna(_col(d, "hour").str.split(".").str[0].str.zfill(2) + ":00:00")
        momento = _fecha(_col(d, "dispatch_date") + " " + hora.fillna("00:00:00"))
        texto = _col(d, "text_general_code")
        salida = pd.DataFrame({"id": _col(d, "dc_key", "objectid"), "momento": momento, "hora_tipo": "reporte",
                               "lat": _col(d, "point_y"), "lon": _col(d, "point_x"), "original": texto,
                               "codigo": [K.codigo_filadelfia(u, t) for u, t in zip(_col(d, "ucr_general"), texto)]})
    elif ciudad == "baton_rouge":
        # un renglon por cargo: un delito por caso
        salida = pd.DataFrame({"id": _col(d, "incident_number"), "momento": _fecha(_col(d, "report_date")),
                               "hora_tipo": "reporte", "lat": _col(d, "latitude"), "lon": _col(d, "longitude"),
                               "original": _col(d, "offense_description", "NIBRS DESCRIPTION"),
                               "codigo": _col(d, "nibrs_code").map(K.codigo_nibrs)})
        salida = _uno_por_caso(salida, "id")
    elif ciudad == "tempe":
        # Fecha y hora (local) en que se recibio la llamada. Corregido el 2026-10-08, antes del examen
        # de reemplazo: OccurrenceDatetime viene marcado "+00" pero es hora LOCAL (coincide en el 100%
        # con la hora, el dia, el mes y el anio que publica Tempe en columnas aparte), asi que se usa
        # tal cual, sin convertir (como Chapel Hill). OccurrenceDatePart es solo el DIA del mes.
        # Respaldo: anio, mes, dia y hora de las columnas de Tempe.
        momento = pd.to_datetime(_col(d, "OccurrenceDatetime"), errors="coerce", format="mixed", utc=True).dt.tz_localize(None)
        num = lambda *n: pd.to_numeric(_col(d, *n), errors="coerce")
        partes = pd.DataFrame({"year": num("OccurrenceYear"), "month": num("OccurrenceMonth"),
                               "day": num("OccurrenceDatePart"), "hour": num("OccurrenceHour")})
        momento = momento.fillna(pd.to_datetime(partes, errors="coerce"))
        texto = _col(d, "OffenseCustom")
        salida = pd.DataFrame({"id": _col(d, "PrimaryKey", "OBJECTID"), "momento": momento,
                               "hora_tipo": "reporte", "lat": _col(d, "Latitude"), "lon": _col(d, "Longitude"),
                               "original": texto, "codigo": texto.map(lambda n: K.codigo_por_nombre("generico", n))})
    else:
        raise ValueError(ciudad)
    return salida


# Minimos del chequeo de lectura (fijados antes de abrir; solo miden el formato).
# "meses_cubiertos" (agregado el 2026-10-08 por lo de Tempe): parte de los meses del estudio
# (2024-01 a 2026-08) con al menos un registro; debe ser 1 (todos).
MINIMOS = {"fecha_leida": 0.90, "ubicacion_leida": 0.70, "categoria_leida": 0.30, "meses_cubiertos": 1.0}
MESES_ESTUDIO = pd.period_range(PR.DESDE, PR.HASTA, freq="M")


def chequeo_lectura(ciudad, crudo, delitos):
    """Parte de los registros con fecha, ubicacion y categoria legibles. No mira la
    formula ni calcula ningun resultado del examen."""
    n = max(len(crudo), 1)
    fila = {"ciudad": ciudad, "registros_leidos": len(crudo),
            "fecha_leida": float(crudo["momento"].notna().mean()),
            "ubicacion_leida": float((pd.to_numeric(crudo["lat"], errors="coerce").between(20, 60)
                                      & pd.to_numeric(crudo["lon"], errors="coerce").between(-130, -60)).sum() / n),
            "categoria_leida": float(crudo["codigo"].notna().mean()),
            "meses_cubiertos": float(MESES_ESTUDIO.isin(crudo["momento"].dropna().dt.to_period("M").unique()).mean()),
            "en_el_periodo": len(delitos), "nucleo_en_el_periodo": int(delitos["clase_nucleo"].notna().sum())}
    fila["pasa"] = bool(all(fila[k] >= v for k, v in MINIMOS.items()) and fila["nucleo_en_el_periodo"] > 0)
    return fila


# --- Comparaciones por viaje -----------------------------------------------------
def por_viaje(v, futuro):
    """Delitos del nucleo del futuro en la ruta mas rapida y en la de menor riesgo de cada viaje."""
    v = v[~v["relleno"]]
    delitos = [futuro[f"fut_{f}"].reindex(ids).fillna(0).sum() for f, ids in zip(v["franja"], v["ids"])]
    t = v.assign(delitos=delitos).pivot_table(index="viaje", columns="etiqueta", values="delitos", aggfunc="first")
    if not {"Fastest", "Lowest risk"} <= set(t.columns):   # desviacion post-sello 1: el mapa no dio rutas Lowest risk
        return pd.DataFrame(columns=["Fastest", "Lowest risk"], dtype=float)
    return t.dropna(subset=["Fastest", "Lowest risk"])


def _cambios(tablas, rng):
    """Cambio (menor riesgo / mas rapida - 1) de cada tabla en los MISMOS viajes, y sus remuestreos.
    None si no hay ningun viaje con las dos rutas en todas las tablas (N.A.)."""
    comunes = tablas[0].index
    for tb in tablas[1:]:
        comunes = comunes.intersection(tb.index)
    if len(comunes) == 0:   # desviacion post-sello 1
        return None, 0
    m = rng.integers(0, len(comunes), (REMUESTREOS_VIAJES, len(comunes)))
    salida = []
    for tb in tablas:
        a, b = tb.loc[comunes, "Fastest"].values, tb.loc[comunes, "Lowest risk"].values
        salida.append((b.sum() / max(a.sum(), 1e-9) - 1, b[m].sum(1) / np.maximum(a[m].sum(1), 1e-9) - 1))
    return salida, len(comunes)


def comparar_rutas(base, otro, rng):
    """Diferencia pareada del cambio de delitos (puntos porcentuales; negativo = 'otro' evita mas)."""
    cambios, n = _cambios([base, otro], rng)
    if cambios is None:
        return {"diferencia_pp": np.nan, "ic95": [np.nan, np.nan], "viajes": 0, "estado": "N.A."}
    (c1, b1), (c2, b2) = cambios
    return {"diferencia_pp": float((c2 - c1) * 100), "ic95": [float(v) for v in np.percentile((b2 - b1) * 100, [2.5, 97.5])],
            "viajes": n}


def retencion(nivel, completo, rng):
    """Parte del beneficio del nivel completo (B) que conserva otro nivel: cambio_nivel / cambio_B."""
    cambios, n = _cambios([nivel, completo], rng)
    if cambios is None:
        return {"retencion": np.nan, "ic95": [np.nan, np.nan], "viajes": 0, "estado": "N.A."}
    (cn, bn), (cb, bb) = cambios
    cociente = bn / np.where(bb != 0, bb, np.nan)
    return {"retencion": float(cn / cb) if cb else np.nan, "ic95": [float(v) for v in np.nanpercentile(cociente, [2.5, 97.5])],
            "viajes": n}


# --- Pruebas trampa ----------------------------------------------------------------
# Regla original: la trampa debe quedar mas cerca del azar que del mapa real. Aclaracion
# (2026-10-08, antes del examen de reemplazo de Tempe; el simulacro con datos inventados
# mostro el problema): si el mapa REAL no supera al azar, "mas cerca de uno o del otro" no
# significa nada y una trampa perfecta (= azar) podia declararse fuga. En ese caso la
# trampa pasa si es compatible con el azar (su IC95 lo incluye o queda por debajo). Cuando
# el mapa real si supera al azar, la regla es la original (mismo veredicto que en
# Filadelfia y Baton Rouge).
def _ic(texto):
    bajo, alto = str(texto).split("-")
    return float(bajo), float(alto)


def trampa_rapida(rapida, trampa, mejor, azar):
    q = {r["mapa"]: r for r in rapida}
    valor, real = q[trampa]["promedio"], q[mejor]["promedio"]
    real_supera = _ic(q[mejor]["ic95"])[0] > azar
    pasa = valor <= (azar + real) / 2 if real_supera else _ic(q[trampa]["ic95"])[0] <= azar
    return {"valor": valor, "azar": azar, "real": real, "real_supera_azar": bool(real_supera),
            "regla": "mitad entre azar y real" if real_supera else "compatible con el azar (IC95)", "pasa": bool(pasa)}


def trampa_rutas(trampa, real):
    """Rutas con el mapa mezclado: si el mapa real reduce delitos (IC95 bajo cero), la trampa
    debe evitar menos de la mitad que el real; si no, la trampa no debe mostrar una reduccion
    clara (el limite superior de su IC95 debe ser >= 0)."""
    real_reduce = real["ic95"][1] < 0
    pasa = trampa["cambio_pct"] > real["cambio_pct"] / 2 if real_reduce else trampa["ic95"][1] >= 0
    return {"valor": trampa["cambio_pct"], "real": real["cambio_pct"], "real_reduce": bool(real_reduce),
            "regla": "menos de la mitad del real" if real_reduce else "sin reduccion clara (IC95)", "pasa": bool(pasa)}


# --- Evaluacion comun ------------------------------------------------------------
def evaluar(ciudad, cfg, delitos_norm, modelos, salida, viajes):
    rng = np.random.default_rng(zlib.crc32(f"examen-{ciudad}".encode()))
    pub = carpeta_publica(ciudad)
    G = ox.project_graph(ox.load_graphml(pub / "red_peatonal.graphml"), to_crs=cfg["crs"])
    limite = gpd.read_file(pub / "limite.geojson").to_crs(cfg["crs"]).geometry.iloc[0]
    lugares = gpd.read_file(pub / "osm.gpkg", layer="lugares")
    d = PR.asignar(delitos_norm, G, limite, lugares, cfg["crs"])
    resumen_delitos = {"registros": len(d), **d["motivo_exclusion"].value_counts().to_dict(),
                       "nucleo_validos": int(d.loc[d["motivo_exclusion"] == "ninguno", "clase_nucleo"].notna().sum()),
                       "sin_categoria": int(d.loc[d["motivo_exclusion"] == "ninguno", "codigo"].isna().sum())}
    print(f"  delitos: {resumen_delitos}", flush=True)

    manzanas = gpd.read_file(pub / "manzanas.gpkg").to_crs(cfg["crs"])
    _, medios = F.tramos_y_medios(G)
    cercana = gpd.sjoin_nearest(medios, manzanas[["geoid", "geometry"]])
    tramo_manzana = cercana.loc[~cercana.index.duplicated(), "geoid"]
    con_detalle = ciudad in K.CON_DETALLE
    mapa_delitos = RD.construir(G, d[d["motivo_exclusion"] == "ninguno"], manzanas[manzanas.within(limite)],
                                tramo_manzana, con_detalle, avisar=False)
    mapa_delitos.to_csv(salida / f"{ciudad}_mapa_delitos.csv")

    publicos = FO.leer_publicos(pub)
    x = FO.largo_formato(publicos, mapa_delitos, ciudad)
    mapas = {"mapa_de_calor_A": x["a"].values, "oraculo": x["y"].values,
             "evitar_avenidas": 1 / (1 + x["dist_principal"].values / 100),
             "evitar_comercios": 1 + x["locales_400"].values}
    if "b" in x:
        mapas["mapa_de_calor_B"] = x["b"].values
    for nivel, (modelo, cats) in modelos.items():
        if all(c in x.columns for c in FO.DELITOS[nivel]):
            mapas[nivel] = FO.predecir(modelo, cats, x, nivel)
    mejor = "B" if "B" in mapas else "C"
    permutado = mapas[mejor].copy()
    for f in FRANJAS:   # prueba trampa: los valores del mejor mapa, mezclados entre tramos
        m = (x["franja"] == f).values
        permutado[m] = rng.permutation(permutado[m])
    mapas["trampa_mapa_mezclado"] = permutado

    largo, zona = publicos["largo"], CA.zonas_de(publicos)
    rapida = []
    for nombre, riesgo in mapas.items():
        rapida.append({"ciudad": ciudad, "mapa": nombre, **CA.calificar_rapido(x, riesgo, largo, zona, rng)})
        print(f"  rapida {nombre}: {rapida[-1]['promedio']:.3f} ({rapida[-1]['ic95']})", flush=True)
    fut_mezclado = x["fut"].values.copy()
    for f in FRANJAS:   # prueba trampa de etiquetas: delitos del futuro mezclados entre tramos
        m = (x["franja"] == f).values
        fut_mezclado[m] = rng.permutation(fut_mezclado[m])
    rapida.append({"ciudad": ciudad, "mapa": "trampa_futuro_mezclado",
                   **CA.calificar_rapido(x, mapas[mejor], largo, zona, rng, futuro=fut_mezclado)})
    print(f"  rapida trampa_futuro_mezclado: {rapida[-1]['promedio']:.3f}", flush=True)
    pd.DataFrame(rapida).to_csv(salida / f"{ciudad}_rapida.csv", index=False)
    pareadas = []
    for base, otro in PAREJAS:
        if base in mapas and otro in mapas:
            pareadas.append({"metrica": "rapida", "base": base, "otro": otro,
                             **CA.comparar_rapido(x, mapas[base], mapas[otro], largo, zona, rng)})
    # azar de cada trampa: un mapa al azar captura ~0.10; con los delitos mezclados, la parte de tramos en el tope
    azar_etiquetas = np.mean([CA.captura(mapas[mejor][m], np.ones(m.sum()), largo.reindex(x.index[m]).values)
                              for m in [(x["franja"] == f).values for f in FRANJAS]])

    red = pub / "red_peatonal.graphml"
    lista = E.tareas(red, ciudad, n=viajes)
    futuro = x.pivot_table(index=x.index, columns="franja", values="fut").add_prefix("fut_")
    personas = publicos[[f"peatones_{f}" for f in FRANJAS]].rename(columns=lambda c: c.replace("peatones_", "pea_"))
    largo_red = RR.tramos_de(ox.load_graphml(red))["largo"]
    rutas, tablas = {}, {}
    for nombre, riesgo in mapas.items():
        guardado = salida / f"{ciudad}_rutas_{nombre}_{viajes}.json"
        crudos = salida / f"{ciudad}_viajes_{nombre}_{viajes}.jsonl"   # cada viaje y sus calles: para auditar
        if guardado.exists() and crudos.exists():
            rutas[nombre] = json.loads(guardado.read_text())
            tablas[nombre] = por_viaje(pd.read_json(crudos, lines=True), futuro)
            continue
        ruta = salida / f"{ciudad}_riesgo_{nombre}.csv"
        FO.mapa_de_riesgo(x, riesgo, largo_red).to_csv(ruta)
        v = E.simular(f"examen_{ciudad}_{nombre}", red, ruta, lista)
        v.to_json(crudos, orient="records", lines=True)
        rutas[nombre] = E.calificar(v, futuro, personas=personas)
        if "cambio_pct" not in rutas[nombre]:   # desviacion post-sello 1: se registra como no disponible
            rutas[nombre]["estado"] = "N.A."
            rutas[nombre]["motivo"] = ("ningun viaje con ruta Lowest risk" if rutas[nombre]["viajes_con_menor_riesgo"] == 0
                                       else "sin delitos del futuro en las rutas mas rapidas")
        tablas[nombre] = por_viaje(v, futuro)
        guardado.write_text(json.dumps(rutas[nombre], default=float))
        r = rutas[nombre]
        print(f"  rutas {nombre}: {r.get('cambio_pct', float('nan')):+.1f}% "
              f"(IC95 {r.get('ic95', [np.nan, np.nan])[0]:+.1f} a {r.get('ic95', [np.nan, np.nan])[1]:+.1f}) "
              f"| por persona {r.get('por_persona_pct', float('nan')):+.1f}%", flush=True)

    for base, otro in PAREJAS:
        if base in tablas and otro in tablas:
            pareadas.append({"metrica": "rutas", "base": base, "otro": otro, **comparar_rutas(tablas[base], tablas[otro], rng)})
    if "B" in tablas:
        b_reduce = bool(rutas.get("B", {}).get("ic95", [0, 0])[1] < 0)   # si B no reduce, la retencion no se interpreta
        for nivel in RETENCION:
            if nivel in tablas:
                pareadas.append({"metrica": "retencion_de_B", "base": "B", "otro": nivel,
                                 **retencion(tablas[nivel], tablas["B"], rng), "interpretable": b_reduce})
    pd.DataFrame(pareadas).to_csv(salida / f"{ciudad}_comparaciones.csv", index=False)

    # Pruebas trampa (protocolo.md, seccion 4): si "aciertan", hubo una fuga
    trampas = {"mapa_mezclado_rapida": trampa_rapida(rapida, "trampa_mapa_mezclado", mejor, 0.10),
               "futuro_mezclado_rapida": trampa_rapida(rapida, "trampa_futuro_mezclado", mejor, float(azar_etiquetas))}
    if "cambio_pct" in rutas.get("trampa_mapa_mezclado", {}) and "cambio_pct" in rutas.get(mejor, {}):
        trampas["mapa_mezclado_rutas"] = trampa_rutas(rutas["trampa_mapa_mezclado"], rutas[mejor])
    (salida / f"{ciudad}_trampas.json").write_text(json.dumps(trampas, indent=2, default=float), encoding="utf-8")
    print(f"  trampas: {trampas}", flush=True)
    return resumen_delitos, rapida, rutas, pareadas, trampas


def escribir_resumen(salida, resultados):
    lineas = ["# Examen de la formula v2 (generado por src/multiciudad/09_examen.py)", ""]
    for ciudad, (delitos, rapida, rutas, pareadas, trampas) in resultados.items():
        lineas += [f"## {ciudad}", "", f"Delitos: {delitos}", "",
                   "| Mapa | Rapida (promedio, IC95) | Rutas: delitos (IC95) | Rutas: por persona (IC95) |",
                   "|---|---|---|---|"]
        rap = {r["mapa"]: r for r in rapida}
        for nombre in list(rutas) + [m for m in rap if m not in rutas]:
            r, q = rutas.get(nombre, {}), rap.get(nombre, {})
            texto_r = (f"{r['cambio_pct']:+.0f}% ({r['ic95'][0]:+.0f} a {r['ic95'][1]:+.0f})" if "cambio_pct" in r else "N.A.")
            texto_p = (f"{r['por_persona_pct']:+.0f}% ({r['por_persona_ic95'][0]:+.0f} a {r['por_persona_ic95'][1]:+.0f})"
                       if "por_persona_pct" in r else "N.A.")
            lineas.append(f"| {nombre} | {q.get('promedio', float('nan')):.3f} ({q.get('ic95', '-')}) | {texto_r} | {texto_p} |")
        lineas += ["", "Comparaciones pareadas (rapida: diferencia de captura; rutas: puntos porcentuales, negativo = "
                   "el segundo evita mas; retencion: cambio del nivel / cambio de B):", "",
                   "| Medida | Base | Comparado | Valor | IC95 |", "|---|---|---|---|---|"]
        for c in pareadas:
            valor = c.get("diferencia", c.get("diferencia_pp", c.get("retencion")))
            if c.get("estado") == "N.A.":
                lineas.append(f"| {c['metrica']} | {c['base']} | {c['otro']} | N.A. | N.A. |")
                continue
            lineas.append(f"| {c['metrica']} | {c['base']} | {c['otro']} | {valor:+.3f} | {c['ic95'][0]:+.3f} a {c['ic95'][1]:+.3f} |")
        lineas += ["", "Pruebas trampa: " + ", ".join(f"{k} {'pasa' if v['pasa'] else 'FALLA'} ({v['valor']:.3f})"
                                                     for k, v in trampas.items()), ""]
    (salida / "resumen.md").write_text("\n".join(lineas), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grupo", choices=list(GRUPOS), default="holdout_main")
    ap.add_argument("--ciudades", nargs="*", default=None)
    ap.add_argument("--viajes", type=int, default=E.VIAJES)
    ap.add_argument("--ensayo", default=None, help="ciudad de PRACTICA para probar el programa sin tocar el examen")
    ap.add_argument("--solo-lectura", action="store_true", help="solo el chequeo de lectura (ningun resultado)")
    a = ap.parse_args()
    modelos = modelos_sellados()
    resultados = {}
    if a.ensayo:
        assert DESARROLLO[a.ensayo]["grupo"] == "practice", "el ensayo solo con ciudades de practica"
        salida = Path("data/practice/ensayo_examen")
        salida.mkdir(parents=True, exist_ok=True)
        delitos = pd.read_csv(carpeta(a.ensayo) / "delitos.csv", dtype={"codigo": str, "clase_nucleo": str,
                                                                         "categoria_amplia": str, "bolsa": str})
        print(f"ENSAYO con {a.ensayo} (practica)", flush=True)
        resultados[a.ensayo] = evaluar(a.ensayo, DESARROLLO[a.ensayo], delitos, modelos, salida, a.viajes)
    else:
        salida = Path(GRUPOS[a.grupo]["salida"])
        salida.mkdir(parents=True, exist_ok=True)
        a.ciudades = a.ciudades or GRUPOS[a.grupo]["ciudades"]
        preparados, lecturas = {}, []
        for ciudad in a.ciudades:   # primero leer TODAS: si una falla, no se califica ninguna
            assert ciudad in GRUPOS[a.grupo]["ciudades"], f"solo ciudades del grupo {a.grupo}"
            crudo = leer_examen(ciudad, a.grupo)
            preparados[ciudad] = PR.normalizar(crudo, ciudad, ciudad in K.CON_DETALLE)
            lecturas.append(chequeo_lectura(ciudad, crudo, preparados[ciudad]))
            print(f"Lectura {ciudad}: {lecturas[-1]}", flush=True)
        (salida / "chequeo_lectura.json").write_text(json.dumps(lecturas, indent=2), encoding="utf-8")
        if not all(x["pasa"] for x in lecturas):
            sys.exit(f"La lectura no paso los minimos {MINIMOS}. No se calculo ningun resultado. "
                     "Corregir solo el lector, anotarlo como desviacion y volver a correr.")
        if a.solo_lectura:
            return
        for ciudad in a.ciudades:
            print(f"=== {EXAMEN[ciudad]['nombre']}", flush=True)
            resultados[ciudad] = evaluar(ciudad, EXAMEN[ciudad], preparados[ciudad], modelos, salida, a.viajes)
    escribir_resumen(salida, resultados)
    print(f"\nResultados en {salida}/", flush=True)


if __name__ == "__main__":
    main()
