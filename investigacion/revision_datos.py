"""
ANALISIS DE LA REVISION (exploratorios, posteriores al examen) que releen los datos del
examen YA ABIERTOS (data/examen_abierto/, abiertos una sola vez: caja_fuerte/aperturas.json).
No se reabre ninguna caja ni se reentrena nada: los modelos se cargan solo si coinciden con
el sello. Plan fijado antes: investigacion/analisis_revision.md (commit 78484c0).

    python investigacion/revision_datos.py r4     sobredispersion de los delitos del futuro
    python investigacion/revision_datos.py r5     exclusiones: sin "lugares" y calle a 100 m
    python investigacion/revision_datos.py r6     auditoria de las categorias de Tempe
Antes de cada variante se comprueba que, con la configuracion del examen, el programa
reproduce exactamente el mapa de delitos que guardo el examen (<ciudad>_mapa_delitos.csv).
Salida: investigacion/resultados/revision/
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src" / "multiciudad"))
sys.path.insert(0, str(RAIZ / "investigacion"))
import analisis_transporte as AT  # noqa: E402
import auditoria_estadistica as AU  # noqa: E402
import categorias as K  # noqa: E402
import evaluar_rutas as E  # noqa: E402
import flujo as F  # noqa: E402
import formula as FO  # noqa: E402
import preparar as PR  # noqa: E402
import rasgos_delitos as RD  # noqa: E402
import reparto as RR  # noqa: E402
from ciudades import EXAMEN, carpeta_publica  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

SEMILLA = 20261011
SORTEOS = 1000
VIAJES = 2000
SALIDA = RAIZ / "investigacion/resultados/revision"
CIUDADES = {"filadelfia": ("holdout_main", RAIZ / "investigacion/resultados/examen_v2"),
            "baton_rouge": ("holdout_main", RAIZ / "investigacion/resultados/examen_v2"),
            "tempe": ("holdout_tempe2", RAIZ / "investigacion/resultados/examen_v2_tempe")}
LISTA = list(FRANJAS)
MITAD = "2026-03-01"   # futuro: sep-feb | mar-ago


def _examen():
    """El programa del examen (lector de cada ciudad, candado y modelos sellados)."""
    spec = importlib.util.spec_from_file_location("examen", RAIZ / "src/multiciudad/09_examen.py")
    ex = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, sys.argv[:1]
    spec.loader.exec_module(ex)
    sys.argv = argv
    return ex


# --------------------------------------------------------------------------------------
# Delitos del examen con una variante de las exclusiones (por defecto: las del examen)
def delitos(ex, ciudad, grupo, distancia_max=PR.DISTANCIA_MAX, sin_lugares=False, recodificar=None):
    cfg = EXAMEN[ciudad]
    crudo = ex.leer_examen(ciudad, grupo)
    if recodificar:
        nuevo = crudo["original"].map(recodificar)
        crudo["codigo"] = nuevo.where(nuevo.notna(), crudo["codigo"])
    d = PR.normalizar(crudo, ciudad, ciudad in K.CON_DETALLE)
    pub = carpeta_publica(ciudad)
    G = ox.project_graph(ox.load_graphml(pub / "red_peatonal.graphml"), to_crs=cfg["crs"])
    limite = gpd.read_file(pub / "limite.geojson").to_crs(cfg["crs"]).geometry.iloc[0]
    lugares = gpd.read_file(pub / "osm.gpkg", layer="lugares")
    if sin_lugares:
        lugares = lugares.iloc[0:0]
    original = PR.DISTANCIA_MAX
    PR.DISTANCIA_MAX = distancia_max
    try:
        d = PR.asignar(d, G, limite, lugares, cfg["crs"])
    finally:
        PR.DISTANCIA_MAX = original
    return d, G, limite


def mapa_delitos(ciudad, d, G, limite):
    """rasgos_delitos.construir con los mismos pasos que 09_examen.evaluar()."""
    cfg = EXAMEN[ciudad]
    pub = carpeta_publica(ciudad)
    manzanas = gpd.read_file(pub / "manzanas.gpkg").to_crs(cfg["crs"])
    _, medios = F.tramos_y_medios(G)
    cercana = gpd.sjoin_nearest(medios, manzanas[["geoid", "geometry"]])
    tramo_manzana = cercana.loc[~cercana.index.duplicated(), "geoid"]
    return RD.construir(G, d[d["motivo_exclusion"] == "ninguno"], manzanas[manzanas.within(limite)],
                        tramo_manzana, ciudad in K.CON_DETALLE, avisar=False)


def igual_al_examen(nuevo, carpeta, ciudad):
    viejo = pd.read_csv(carpeta / f"{ciudad}_mapa_delitos.csv", index_col="tramo_id")
    nuevo = nuevo.reindex(index=viejo.index, columns=viejo.columns)
    dif = float(np.nanmax(np.abs(nuevo.values - viejo.values)))
    return dif, bool(dif <= 1e-6 and nuevo.notna().all().all())


def exclusiones(d):
    return {"registros": len(d), **d["motivo_exclusion"].value_counts().to_dict(),
            "nucleo_conservados": int(d.loc[d["motivo_exclusion"] == "ninguno", "clase_nucleo"].notna().sum())}


# --------------------------------------------------------------------------------------
# R4: sobredispersion (dos mitades del futuro) y re-sorteo binomial negativo
def dispersion(d):
    f = d[(d["motivo_exclusion"] == "ninguno") & d["clase_nucleo"].notna()
          & (d["fecha"] >= RD.FUTURO[0]) & (d["fecha"] <= RD.FUTURO[1])]
    g = pd.DataFrame({"n": f.groupby("tramo_id").size(),
                      "h1": f[f["fecha"] < MITAD].groupby("tramo_id").size()}).fillna(0)
    p = g["h1"].sum() / g["n"].sum()
    phi = float(((g["h1"] - p * g["n"]) ** 2).sum() / (g["n"] * p * (1 - p)).sum())
    return phi, float(p), int(len(g)), int(g["n"].sum())


def sorteo(rng, mu, phi, n):
    """n sorteos de cada conteo: binomial negativo con media mu y varianza phi*mu (Poisson si phi<=1)."""
    if phi <= 1:
        return rng.poisson(mu, (n, len(mu))).astype(float)
    lam = rng.gamma(shape=np.maximum(mu, 1e-12) / (phi - 1), scale=phi - 1, size=(n, len(mu)))
    return rng.poisson(lam).astype(float) * (mu > 0)


def r4(ex):
    rng = np.random.default_rng(SEMILLA)
    filas, phis = [], []
    for ciudad, (grupo, carpeta) in CIUDADES.items():
        d, G, limite = delitos(ex, ciudad, grupo)
        phi, p, tramos, n = dispersion(d)
        phis.append({"ciudad": ciudad, "phi": phi, "parte_primera_mitad": p, "tramos_con_delitos": tramos, "delitos": n})
        print(f"  {ciudad}: phi = {phi:.3f} (p = {p:.3f}, {tramos:,} tramos, {n:,} delitos del futuro)", flush=True)
        mapa = pd.read_csv(carpeta / f"{ciudad}_mapa_delitos.csv", index_col="tramo_id")
        largo = mapa[[f"fut_{f}" for f in LISTA]].stack()
        columnas = pd.Index([f"{t}|{f.replace('fut_', '')}" for t, f in largo.index])
        fut = largo.values.astype(float)
        zonas = AU.zonas_de_origen(ciudad)
        rutas = {m: AU.Rutas(carpeta / f"{ciudad}_viajes_{m}_{VIAJES}.jsonl", columnas) for m in ["B", "A", "C", "sin_delitos"]}
        usados = np.unique(np.concatenate([r.M.indices for r in rutas.values()]))
        con = {m: r.por_viaje(fut).dropna() for m, r in rutas.items()}
        z1 = {m: zonas["zona1"].reindex(c.index).values for m, c in con.items()}
        valores = {(m, nombre): [] for m in rutas for nombre in ("poisson", "binomial_negativa")}
        for k in range(SORTEOS):   # un sorteo a la vez, el mismo para los 4 mapas (cambio 2 del plan)
            for nombre, phi_k in [("poisson", 1.0), ("binomial_negativa", phi)]:
                fut_p = fut.copy()
                fut_p[usados] = sorteo(rng, fut[usados], phi_k, 1)[0]
                for m, r in rutas.items():
                    tp = r.por_viaje(fut_p).reindex(con[m].index)
                    valores[(m, nombre)].append(
                        AU.remuestreo_zonas(tp["Fastest"].values, tp["Lowest risk"].values, z1[m], rng, n=1)[0])
        for m in rutas:
            fila = {"ciudad": ciudad, "mapa": m, "phi": phi,
                    "cambio_pct": AU.cambio(con[m]["Fastest"].values, con[m]["Lowest risk"].values) * 100,
                    **{f"ic95_zonas_y_{nombre}": AU.ic(np.array(valores[(m, nombre)])) for nombre in ("poisson", "binomial_negativa")}}
            filas.append(fila)
            print(f"    {m}: {fila['cambio_pct']:+.1f}% | Poisson {fila['ic95_zonas_y_poisson']} | "
                  f"binomial negativa {fila['ic95_zonas_y_binomial_negativa']}", flush=True)
    pd.DataFrame(phis).to_csv(SALIDA / "r4_dispersion.csv", index=False)
    t = pd.DataFrame(filas)
    t.to_csv(SALIDA / "r4_intervalos.csv", index=False)
    return t


# --------------------------------------------------------------------------------------
# R5: exclusiones (y R6 reutiliza la misma evaluacion)
def evaluar_variante(ex, modelos, ciudad, carpeta, nombre, mapa, mapas=("B",)):
    """Rutas de los mapas dados (re-predichos con el modelo sellado) y re-conteo de No crime
    data con sus rutas del examen, contra los delitos del futuro de la variante."""
    rng = np.random.default_rng(SEMILLA)
    pub = carpeta_publica(ciudad)
    red = pub / "red_peatonal.graphml"
    lista, zonas = AT.zonas_de(red, ciudad, VIAJES)
    x = FO.largo_formato(FO.leer_publicos(pub), mapa, ciudad)
    futuro = x.pivot_table(index=x.index, columns="franja", values="fut").add_prefix("fut_")
    largo_red = RR.tramos_de(ox.load_graphml(red))["largo"]
    filas = []
    for nivel in mapas:
        modelo, cats = modelos[nivel]
        archivo = SALIDA / f"{nombre}_{ciudad}_viajes_{nivel}_{VIAJES}.jsonl"
        if archivo.exists():
            v = pd.read_json(archivo, lines=True)
        else:
            ruta = SALIDA / f"{nombre}_{ciudad}_riesgo_{nivel}.csv"
            FO.mapa_de_riesgo(x, FO.predecir(modelo, cats, x, nivel), largo_red).to_csv(ruta)
            v = E.simular(f"{nombre}_{ciudad}_{nivel}", red, ruta, lista)
            v.to_json(archivo, orient="records", lines=True)
        filas.append({"variante": nombre, "ciudad": ciudad, "mapa": nivel, **_medidas(v, futuro, zonas, rng)})
    v = pd.read_json(carpeta / f"{ciudad}_viajes_sin_delitos_{VIAJES}.jsonl", lines=True)   # mismo mapa, mismas rutas
    filas.append({"variante": nombre, "ciudad": ciudad, "mapa": "sin_delitos", **_medidas(v, futuro, zonas, rng)})
    return filas


def _medidas(v, futuro, zonas, rng):
    reg = E.calificar(v, futuro)
    todos = AT.resumen(AT.por_viaje(v, {f: futuro[f"fut_{f}"] for f in LISTA}), zonas, rng)
    return {"cambio_registrado": reg.get("cambio_pct", np.nan), "ic95_registrado": reg.get("ic95", [np.nan, np.nan]),
            "viajes_con_alternativa": reg["viajes_con_menor_riesgo"], "cambio_todos": todos["cambio_todos"],
            "ic95_todos_zonas": todos["ic95_zonas"]}


def _agregar(archivo, nuevas, claves=("ciudad",)):
    """Guarda 'nuevas' reemplazando solo las filas de sus ciudades (las demas se conservan)."""
    nuevas = pd.DataFrame(nuevas)
    if archivo.exists() and len(nuevas):
        viejas = pd.read_csv(archivo)
        viejas = viejas[~viejas["ciudad"].isin(nuevas["ciudad"].unique())]
        nuevas = pd.concat([viejas, nuevas], ignore_index=True)
    nuevas.to_csv(archivo, index=False)


def r5(ex, ciudades=None, sin_control=()):
    """ciudades: las que se calculan (por defecto todas). sin_control: ciudades cuyo control ya
    paso en una corrida anterior (cambio 4 del plan); no se repite."""
    modelos = ex.modelos_sellados()
    filas, conteos, controles = [], [], []
    for ciudad, (grupo, carpeta) in CIUDADES.items():
        if ciudades and ciudad not in ciudades:
            continue
        print(f"=== {ciudad}", flush=True)
        d, G, limite = delitos(ex, ciudad, grupo)
        conteos.append({"ciudad": ciudad, "variante": "examen", **exclusiones(d)})
        if ciudad in sin_control:
            print("  control: ya paso en la corrida anterior (no se repite; cambio 4 del plan)", flush=True)
        else:
            dif, ok = igual_al_examen(mapa_delitos(ciudad, d, G, limite), carpeta, ciudad)
            controles.append({"ciudad": ciudad, "diferencia_maxima": dif, "reproduce_el_examen": ok})
            print(f"  control: el mapa de delitos del examen se reproduce: {ok} (diferencia maxima {dif:.2e})", flush=True)
            _agregar(SALIDA / "r5_control.csv", controles)
            if not ok:
                sys.exit("No se reproduce el mapa del examen: no se sigue (revisar antes de interpretar nada).")
        for nombre, kw in [("lugares", {"sin_lugares": True}), ("calle_100", {"distancia_max": 100})]:
            dv, G, limite = delitos(ex, ciudad, grupo, **kw)
            conteos.append({"ciudad": ciudad, "variante": nombre, **exclusiones(dv)})
            filas += evaluar_variante(ex, modelos, ciudad, carpeta, f"r5_{nombre}", mapa_delitos(ciudad, dv, G, limite))
            print(f"  {nombre}: " + " | ".join(f"{f['mapa']} {f['cambio_registrado']:+.1f}% / todos {f['cambio_todos']:+.1f}%"
                                              for f in filas[-2:]), flush=True)
            _agregar(SALIDA / "r5_exclusiones.csv", filas)
        _agregar(SALIDA / "r5_conteos.csv", conteos)
    return pd.DataFrame(filas)


# --------------------------------------------------------------------------------------
# R6: auditoria de las categorias de Tempe
PALABRAS = {"homicidio": r"MURDER|HOMICIDE|MANSLAUGHTER", "robo": r"ROBBERY|CARJACK",
            "agresion_grave": r"AGGRAVATED|\bAGG\b|AGG ASSAULT"}
CODIGO = {"homicidio": "09A", "robo": "120", "agresion_grave": "13A"}
NO_HOMICIDIO = r"NEGLIGENT|JUSTIFIABLE|VEHICULAR|ATTEMPT"
NEGACION = r"\b(NON|NOT)[\s-]*$"   # cambio 1 del plan: "NON-AGGRAVATED" no nombra el delito
# Chequeo (d), cambio 1 del plan: "agravado" que no es una agresion (delitos agravados de Arizona)
AGRESION = (r"ASSAULT|BATTERY|\bADW\b|\bA\.?D\.?W\b|DEADLY WEAPON|DANGEROUS INSTRUMENT|SHOOT|STAB|STRANGUL|CHOK|MAIM"
            r"|INJUR|ATTEMPT\w*\s+(MURDER|HOMICIDE)|(MURDER|HOMICIDE)\W+ATTEMPT")
OTRO_DELITO = (r"\bDUI\b|\bDWI\b|DRIV|CRIMINAL DAMAGE|DAMAGE|HARASS|IDENTITY|THEFT|TAKING|TRESPASS|FRAUD|FORGER"
               r"|SHOPLIFT|BURGL|LARCENY|ARSON|ESCAPE|ANIMAL")


def nombra(texto):
    """Clases del nucleo que nombra el texto (sin contar las negadas)."""
    t = re.sub(r"\s+", " ", str(texto).upper())
    clases = set()
    for clase, patron in PALABRAS.items():
        for m in re.finditer(patron, t):
            if re.search(NEGACION, t[:m.start()]):
                continue
            if clase == "homicidio" and re.search(NO_HOMICIDIO, t):
                continue
            clases.add(clase)
    return clases


def r6(ex):
    ciudad, (grupo, carpeta) = "tempe", CIUDADES["tempe"]
    crudo = ex.leer_examen(ciudad, grupo)
    d = PR.normalizar(crudo, ciudad, True)
    t = (d.groupby("original", dropna=False)
          .agg(registros=("id", "size"), codigo=("codigo", "first"), clase_nucleo=("clase_nucleo", "first"))
          .reset_index().sort_values("registros", ascending=False))
    t["nombra"] = t["original"].map(lambda x: ",".join(sorted(nombra(x))))
    sin = t["clase_nucleo"].isna() & (t["nombra"] != "")
    otra = t["clase_nucleo"].notna() & (t["nombra"] != "") & pd.Series(
        [c not in n.split(",") or len(n.split(",")) > 1 for c, n in zip(t["clase_nucleo"].fillna(""), t["nombra"])],
        index=t.index, dtype=bool)
    texto = t["original"].astype(str).str.upper()
    agravado = (t["clase_nucleo"] == "agresion_grave") & ~texto.str.contains(AGRESION, regex=True)
    t["chequeo"] = np.select([sin, otra, agravado], ["a: nombra el nucleo sin clase", "b: nombra otra clase",
                                                     "d: agravado sin agresion"], "")
    t.to_csv(SALIDA / "r6_tempe_descripciones.csv", index=False)
    marcadas = t[t["chequeo"] != ""]
    ab = marcadas[marcadas["chequeo"].str.startswith(("a", "b")) & (marcadas["nombra"] != "")
                  & (marcadas["nombra"].str.count(",") == 0)]
    recodificar = {o: CODIGO[n] for o, n in zip(ab["original"], ab["nombra"])}
    d_otro = marcadas[marcadas["chequeo"].str.startswith("d") & texto.reindex(marcadas.index).str.contains(OTRO_DELITO, regex=True)]
    recodificar.update({o: "90Z" for o in d_otro["original"]})   # "otro": fuera del nucleo
    recodificados = pd.concat([ab, d_otro])
    nucleo = int(t.loc[t["clase_nucleo"].notna(), "registros"].sum())
    resumen = {"descripciones": len(t), "registros": int(t["registros"].sum()), "registros_nucleo": nucleo,
               "descripciones_marcadas": len(marcadas), "registros_marcados": int(marcadas["registros"].sum()),
               "descripciones_recodificadas": len(recodificar), "registros_recodificados": int(recodificados["registros"].sum()),
               "registros_a_nucleo": int(ab["registros"].sum()), "registros_fuera_del_nucleo": int(d_otro["registros"].sum())}
    print(f"  auditoria: {resumen}", flush=True)
    print(marcadas[["original", "registros", "codigo", "clase_nucleo", "nombra", "chequeo"]].head(40).to_string(index=False), flush=True)
    tops = pd.concat([t[t["clase_nucleo"] == c].head(25).assign(grupo=c) for c in K.CLASES_NUCLEO]
                     + [t[t["clase_nucleo"].isna()].head(25).assign(grupo="sin clase del nucleo")])
    tops.to_csv(SALIDA / "r6_tempe_mas_frecuentes.csv", index=False)
    (SALIDA / "r6_tempe_resumen.json").write_text(json.dumps({**resumen, "recodificar": recodificar}, indent=2), encoding="utf-8")
    if not recodificar:
        print("  sin descripciones a recodificar: solo se reporta la auditoria", flush=True)
        return pd.DataFrame([resumen])
    modelos = ex.modelos_sellados()
    dv, G, limite = delitos(ex, ciudad, grupo, recodificar=recodificar)
    filas = evaluar_variante(ex, modelos, ciudad, carpeta, "r6_recodificado", mapa_delitos(ciudad, dv, G, limite),
                             mapas=("B", "A", "C"))
    t = pd.DataFrame(filas)
    t.to_csv(SALIDA / "r6_tempe_rutas.csv", index=False)
    return t


def r6b(ex):
    """R6b (cambio 3 del plan, decidido DESPUES de ver las descripciones): Tempe con el codigo
    NIBRS que trae cada descripcion entre corchetes ("[90D] DUI-AGGRAVATED"). Los codigos sexuales
    se excluyen como siempre; sin codigo o con "[0]", la regla generica de siempre."""
    ciudad, (grupo, carpeta) = "tempe", CIUDADES["tempe"]
    crudo = ex.leer_examen(ciudad, grupo)
    incrustado = crudo["original"].astype(str).str.extract(r"^\s*\[([0-9]{2}[0-9A-Z]?)\]")[0]
    incrustado = incrustado.where(~incrustado.isin(K.CODIGOS_SEXUALES), K.SEXUAL)
    recodificar = {o: c for o, c in zip(crudo["original"], incrustado) if isinstance(c, str)}
    antes = PR.normalizar(crudo, ciudad, True)
    despues = crudo.copy()
    despues["codigo"] = despues["original"].map(recodificar).where(lambda s: s.notna(), despues["codigo"])
    despues = PR.normalizar(despues, ciudad, True)
    resumen = {"descripciones_con_codigo": len(recodificar),
               "registros_con_codigo": int(crudo["original"].map(recodificar).notna().sum()),
               "nucleo_reglas": int(antes["clase_nucleo"].notna().sum()),
               "nucleo_codigo_oficial": int(despues["clase_nucleo"].notna().sum()),
               "nucleo_en_ambos": int((antes["clase_nucleo"].notna() & despues["clase_nucleo"].notna()).sum()),
               "por_clase_reglas": antes["clase_nucleo"].value_counts().to_dict(),
               "por_clase_codigo_oficial": despues["clase_nucleo"].value_counts().to_dict()}
    print(f"  {resumen}", flush=True)
    (SALIDA / "r6b_tempe_codigo_oficial.json").write_text(json.dumps(resumen, indent=2), encoding="utf-8")
    modelos = ex.modelos_sellados()
    dv, G, limite = delitos(ex, ciudad, grupo, recodificar=recodificar)
    filas = evaluar_variante(ex, modelos, ciudad, carpeta, "r6b_codigo_oficial", mapa_delitos(ciudad, dv, G, limite),
                             mapas=("B", "A", "C"))
    t = pd.DataFrame(filas)
    t.to_csv(SALIDA / "r6b_tempe_rutas.csv", index=False)
    return t


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    accion = sys.argv[1]
    ex = _examen()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    if accion == "r5":   # python revision_datos.py r5 [ciudad ...] [--sin-control ciudad,ciudad]
        args = sys.argv[2:]
        sin, ciudades = [], []
        i = 0
        while i < len(args):
            if args[i] == "--sin-control":
                sin = args[i + 1].split(",")
                i += 2
                continue
            ciudades.append(args[i])
            i += 1
        ciudades = ciudades or None
        t = r5(ex, ciudades=ciudades, sin_control=sin)
    else:
        t = {"r4": r4, "r6": r6, "r6b": r6b}[accion](ex)
    print("\n" + t.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
