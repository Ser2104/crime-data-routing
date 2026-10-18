"""
Genera las TABLAS del articulo (LaTeX) directamente de los archivos de resultados, para
que ningun numero se copie a mano. Ejecutar desde la carpeta del proyecto:
    python investigacion/articulo/generar_tablas.py
Salida: investigacion/articulo/tablas/*.tex (se incluyen en main.tex con \\input).

Fuentes:
    investigacion/resultados/examen_v2/        examen principal (Filadelfia, Baton Rouge)
    investigacion/resultados/examen_v2_tempe/  examen de reemplazo (Tempe)
    investigacion/resultados/auditoria/        auditoria exploratoria
"""
import ast
import json
import re
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent / "tablas"
CARPETA = {"filadelfia": RAIZ / "investigacion/resultados/examen_v2",
           "baton_rouge": RAIZ / "investigacion/resultados/examen_v2",
           "tempe": RAIZ / "investigacion/resultados/examen_v2_tempe"}
NOMBRE = {"filadelfia": "Philadelphia", "baton_rouge": "Baton Rouge", "tempe": "Tempe"}
CIUDADES = list(CARPETA)
MAPAS = [("B", "Detailed (B)"), ("A", "Core only (A)"), ("C", "Coarse (C)"),
         ("zona", "Zone"), ("totales", "City total"),
         ("sin_delitos", "No crime data"), ("solo_mapa", "Map only"),
         ("mapa_de_calor_B", "Heat map B (no model)"), ("mapa_de_calor_A", "Heat map A (no model)"),
         ("evitar_comercios", "Rule: avoid commercial areas"), ("evitar_avenidas", "Rule: avoid arterials"),
         ("oraculo", "Oracle (future crime; ceiling)")]
PAREJAS = {("mapa_de_calor_A", "A"): "H2: Core only (A) vs.\\ heat map A", ("mapa_de_calor_B", "B"): "H2: Detailed (B) vs.\\ heat map B",
           ("evitar_avenidas", "sin_delitos"): "H3b: no crime data vs.\\ avoid arterials",
           ("evitar_comercios", "sin_delitos"): "H3b: no crime data vs.\\ avoid commercial"}
MARGEN_NI = 5.0


def rutas(ciudad, mapa):
    return json.loads((CARPETA[ciudad] / f"{ciudad}_rutas_{mapa}_2000.json").read_text())


def numeros(texto):
    """Lista de numeros de un texto (los IC se guardaron como '[np.float64(a), np.float64(b)]' o '[a, b]')."""
    return [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", str(texto).replace("np.float64", ""))]


def pareada(ciudad, base, otro):
    c = pd.read_csv(CARPETA[ciudad] / f"{ciudad}_comparaciones.csv")
    f = c[(c["metrica"] == "rutas") & (c["base"] == base) & (c["otro"] == otro)].iloc[0]
    return float(f["diferencia_pp"]), numeros(f["ic95"])[-2:]


def retencion(ciudad, nivel):
    c = pd.read_csv(CARPETA[ciudad] / f"{ciudad}_comparaciones.csv")
    f = c[(c["metrica"] == "retencion_de_B") & (c["otro"] == nivel)].iloc[0]
    return float(f["retencion"]), numeros(f["ic95"])[-2:]


def num(v, d=0):
    """Con signo; un valor que redondearia a 0 (por ejemplo -0.3) se muestra con un decimal."""
    return f"{v:+.1f}" if d == 0 and 0 < abs(v) < 0.5 else f"{v:+.{d}f}"


def pct(v, ic=None, d=0):
    return num(v, d) if ic is None else f"{num(v, d)} ({num(ic[0], d)}, {num(ic[1], d)})"


def encabezado(*lineas):
    """Encabezado en varias lineas (la tabla queda angosta y no hay que achicar la letra)."""
    return "\\begin{tabular}[b]{@{}c@{}}" + " \\\\ ".join(lineas) + "\\end{tabular}"


def escribir(nombre, cuerpo):
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / f"{nombre}.tex").write_text(cuerpo.replace("−", "-"), encoding="utf-8")
    print("escrita", nombre)


def tabla_datos():
    filas = []
    for c in CIUDADES:
        lect = json.loads((CARPETA[c] / "chequeo_lectura.json").read_text())
        lect = [x for x in lect if x["ciudad"] == c][0]
        texto = (CARPETA[c] / "resumen.md").read_text(encoding="utf-8")
        bloque = texto[texto.index(f"## {c}"):]
        delitos = ast.literal_eval(re.search(r"Delitos: (\{.*?\})", bloque).group(1))
        filas.append(f"{NOMBRE[c]} & {lect['registros_leidos']:,} & {lect['en_el_periodo']:,} & {delitos['ninguno']:,} & "
                     f"{delitos['nucleo_validos']:,} & {lect['meses_cubiertos'] if 'meses_cubiertos' in lect else 1:.0%} \\\\")
    escribir("t_datos", "\\begin{tabular}{lrrrrr}\n\\toprule\n"
             "City & Records read & In study period & Kept after exclusions & Core incidents kept & Months covered \\\\\n"
             "\\midrule\n" + "\n".join(filas).replace("%", "\\%") + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_rutas():
    filas = []
    for m, nombre in MAPAS:
        celdas = []
        for c in CIUDADES:
            r = rutas(c, m)
            celdas.append(pct(r["cambio_pct"], r["ic95"]) if "cambio_pct" in r else "N.A.")
        filas.append(f"{nombre} & " + " & ".join(celdas) + " \\\\")
        if m in ("C", "totales", "solo_mapa", "evitar_avenidas"):   # grupos: por calle | agregados | sin delitos | referencias
            filas.append("\\midrule")
    escribir("t_rutas", "\\begin{tabular}{lccc}\n\\toprule\n"
             "Map & " + " & ".join(NOMBRE[c] for c in CIUDADES) + " \\\\\n\\midrule\n" + "\n".join(filas)
             + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_hipotesis():
    filas = []
    for m, h in [("B", "H1: Detailed (B) reduces crime"), ("A", "H1: Core only (A) reduces crime"),
                 ("C", "H1: Coarse (C) reduces crime"), ("sin_delitos", "H3a: No crime data reduces crime")]:
        celdas, todas = [], True
        for c in CIUDADES:
            r = rutas(c, m)
            ok = "cambio_pct" in r and r["ic95"][1] < 0
            todas &= ok
            celdas.append(("yes" if ok else "no") + f" ({r['ic95'][1]:+.0f})")
        filas.append(f"{h} & " + " & ".join(celdas) + f" & {'yes' if todas else 'no'} \\\\")
    for (base, otro), h in PAREJAS.items():
        celdas, ni_todas, sup_todas = [], True, True
        for c in CIUDADES:
            d, ic = pareada(c, base, otro)
            sup = ic[1] < 0
            ni = ic[1] < MARGEN_NI
            sup_todas &= sup
            ni_todas &= ni
            if base.startswith("mapa_de_calor"):
                etiqueta = "superior" if sup else ("non-inferior" if ni else "no")
            else:
                etiqueta = "superior" if sup else "no"
            celdas.append(f"{etiqueta} ({ic[1]:+.1f})")
        tres = ("superior" if sup_todas else ("non-inferior" if ni_todas else "no")) if base.startswith("mapa_de_calor") \
            else ("superior" if sup_todas else "no")
        filas.append(f"{h} & " + " & ".join(celdas) + f" & {tres} \\\\")
    escribir("t_hipotesis", "\\begin{tabular}{lcccc}\n\\toprule\n"
             "Hypothesis & " + " & ".join(NOMBRE[c] for c in CIUDADES) + " & All three \\\\\n\\midrule\n"
             + "\n".join(filas) + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_controles():
    filas = []
    for c in CIUDADES:
        o = rutas(c, "oraculo")
        t = json.loads((CARPETA[c] / f"{c}_trampas.json").read_text())
        filas.append(f"{NOMBRE[c]} & {pct(o['cambio_pct'], o['ic95'])} & "
                     f"{t['mapa_mezclado_rapida']['valor']:.3f} / {t['mapa_mezclado_rapida']['azar']:.3f} & "
                     f"{t['futuro_mezclado_rapida']['valor']:.3f} / {t['futuro_mezclado_rapida']['azar']:.3f} & "
                     f"{t['mapa_mezclado_rapida']['real']:.3f} & {t['mapa_mezclado_rutas']['valor']:+.0f} & "
                     f"{'all pass' if all(v['pasa'] for v in t.values()) else 'FAIL'} \\\\")
    escribir("t_controles", "\\begin{tabular}{lcccccc}\n\\toprule\n"
             " & " + encabezado("Oracle: route", "change, \\% (95\\% CI)") + " & " + encabezado("Shuffled map:", "capture / chance")
             + " & " + encabezado("Shuffled future:", "capture / chance") + " & " + encabezado("Real map:", "capture")
             + " & " + encabezado("Shuffled map:", "route change, \\%") + " & Traps \\\\\n\\midrule\n" + "\n".join(filas)
             + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_retencion():
    filas = []
    for m, nombre in MAPAS[1:7]:
        celdas = []
        for c in CIUDADES:
            v, ic = retencion(c, m)
            celdas.append(f"{v:.2f} ({ic[0]:.2f}, {ic[1]:.2f})")
        filas.append(f"{nombre} & " + " & ".join(celdas) + " \\\\")
        if m in ("C", "totales"):
            filas.append("\\midrule")
    escribir("t_retencion", "\\begin{tabular}{lccc}\n\\toprule\n"
             "Level & " + " & ".join(NOMBRE[c] for c in CIUDADES) + " \\\\\n\\midrule\n" + "\n".join(filas)
             + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_robustez():
    a = pd.read_csv(RAIZ / "investigacion/resultados/auditoria/intervalos_y_todos_los_viajes.csv")
    filas = []
    for m, nombre in [("B", "Detailed (B)"), ("A", "Core only (A)"), ("C", "Coarse (C)"), ("sin_delitos", "No crime data")]:
        for c in CIUDADES:
            f = a[(a["ciudad"] == c) & (a["mapa"] == m)].iloc[0]
            r = rutas(c, m)   # el intervalo REGISTRADO (el de la auditoria usa otra semilla)
            filas.append(f"{nombre} & {NOMBRE[c]} & {pct(r['cambio_pct'], r['ic95'])} & "
                         f"({num(numeros(f['ic95_zonas_1km'])[0])}, {num(numeros(f['ic95_zonas_1km'])[1])}) & "
                         f"({num(numeros(f['ic95_zonas_1km_y_poisson'])[0])}, {num(numeros(f['ic95_zonas_1km_y_poisson'])[1])}) & "
                         f"{pct(f['todos_cambio_pct'], numeros(f['todos_ic95_zonas_1km']))} \\\\")
        filas.append("\\midrule")
    escribir("t_robustez", "\\begin{tabular}{llcccc}\n\\toprule\n"
             "Level & City & " + encabezado("Change, trips with an", "alternative (trip CI)") + " & " + encabezado("CI, 1-km", "zones")
             + " & " + encabezado("CI, zones and", "redrawn crimes") + " & " + encabezado("Change, all", "trips (zone CI)") + " \\\\\n"
             "\\midrule\n" + "\n".join(filas[:-1]) + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_rapida():
    filas = []
    for m, nombre in MAPAS:
        celdas = []
        for c in CIUDADES:
            r = pd.read_csv(CARPETA[c] / f"{c}_rapida.csv")
            f = r[r["mapa"] == m].iloc[0]
            lo, hi = (float(x) for x in str(f["ic95"]).split("-"))   # "0.400-0.452" (siempre positivos)
            celdas.append(f"{f['promedio']:.2f} ({lo:.2f}, {hi:.2f})")
        filas.append(f"{nombre} & " + " & ".join(celdas) + " \\\\")
    escribir("t_rapida", "\\begin{tabular}{lccc}\n\\toprule\n"
             "Map & " + " & ".join(NOMBRE[c] for c in CIUDADES) + " \\\\\n\\midrule\n" + "\n".join(filas)
             + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_comparacion():
    """Comparacion exploratoria con Galbrun et al. (2016): cambio sobre TODOS los viajes (IC por zonas de 1 km)."""
    c = pd.read_csv(RAIZ / "investigacion/resultados/comparacion_metodos/cambio_todos_los_viajes.csv")
    filas = [("A", "Ours, Core only (A)"), ("B", "Ours, Detailed (B)"),
             ("C", "Ours, Coarse (C)"), ("mapa_de_calor_A", "Heat map A (no model)"),
             ("mapa_de_calor_B", "Heat map B (no model)"), None,
             ("G16_nucleo", "G16 as published, core crime"), ("G16_todos", "G16 as published, all crime"),
             ("G16u_nucleo", "G16, uniform sampling, core crime"), ("G16u_todos", "G16, uniform sampling, all crime"),
             ("KDE_nucleo", "G16 density map in our router, core crime"), ("KDE_todos", "G16 density map in our router, all crime")]
    lineas = []
    for f in filas:
        if f is None:
            lineas.append("\\midrule")
            continue
        m, nombre = f
        celdas = []
        for ciudad in CIUDADES:
            x = c[(c["ciudad"] == ciudad) & (c["metodo"] == m)].iloc[0]
            celdas.append(pct(x["cambio_todos_los_viajes"], numeros(x["ic95_zonas_1km"])))
        lineas.append(f"{nombre} & " + " & ".join(celdas) + " \\\\")
    escribir("t_comparacion", "\\begin{tabular}{lccc}\n\\toprule\n"
             "Method & " + " & ".join(NOMBRE[c] for c in CIUDADES) + " \\\\\n\\midrule\n" + "\n".join(lineas)
             + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_por_persona():
    """Medida secundaria registrada: cambio por persona (delitos / peatones simulados), con su IC."""
    filas = []
    for m, nombre in MAPAS:
        celdas = []
        for c in CIUDADES:
            r = rutas(c, m)
            celdas.append(pct(r["por_persona_pct"], r["por_persona_ic95"]) if "por_persona_pct" in r else "N.A.")
        filas.append(f"{nombre} & " + " & ".join(celdas) + " \\\\")
        if m in ("C", "totales", "solo_mapa", "evitar_avenidas"):
            filas.append("\\midrule")
    escribir("t_por_persona", "\\begin{tabular}{lccc}\n\\toprule\n"
             "Map & " + " & ".join(NOMBRE[c] for c in CIUDADES) + " \\\\\n\\midrule\n" + "\n".join(filas)
             + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_exclusiones():
    """Delitos del periodo del estudio por motivo de exclusion (resumen.md del examen)."""
    motivos = [("sin_ubicacion", "No valid location"), ("sin_fecha", "No valid date"), ("sexual", "Sexual offense"),
               ("fuera_de_ciudad", "Outside the city"), ("lejos_de_calle", "More than 50 m from a walkable street"),
               ("lugar_cerrado", "Within 30 m of an institution"), ("ninguno", "Kept")]
    datos = {}
    for c in CIUDADES:
        texto = (CARPETA[c] / "resumen.md").read_text(encoding="utf-8")
        bloque = texto[texto.index(f"## {c}"):]
        datos[c] = ast.literal_eval(re.search(r"Delitos: (\{.*?\})", bloque).group(1))
    filas = [f"Records in the study period & " + " & ".join(f"{datos[c]['registros']:,}" for c in CIUDADES) + " \\\\", "\\midrule"]
    for clave, nombre in motivos:
        celdas = [f"{datos[c].get(clave, 0):,} ({datos[c].get(clave, 0) / datos[c]['registros']:.1%})" for c in CIUDADES]
        filas.append(f"{nombre} & " + " & ".join(celdas) + " \\\\")
        if clave == "lugar_cerrado":
            filas.append("\\midrule")
    escribir("t_exclusiones", "\\begin{tabular}{lrrr}\n\\toprule\nReason & " + " & ".join(NOMBRE[c] for c in CIUDADES)
             + " \\\\\n\\midrule\n" + "\n".join(filas).replace("%", "\\%") + "\n\\bottomrule\n\\end{tabular}\n")


RASGOS = [  # (nombre en formula.py, descripcion) en el orden del apendice
    ("largo", "Segment length"), ("tipo", "Segment type (OpenStreetMap highway class; categorical)"),
    ("es_sendero", "Footpath away from streets (0/1)"), ("en_parque", "Inside a park (0/1)"),
    ("dist_principal", "Distance to the nearest trunk, primary or secondary road"),
    ("locales_150", "Shops and selected amenities within 150 m"), ("locales_400", "Shops and selected amenities within 400 m"),
    ("intersecciones_300", "Street intersections (3+ streets) within 300 m"),
    ("alcance_400", "Intersections reachable along streets within 400 m"),
    ("escuelas_400", "Schools within 400 m"), ("universidades_400", "Universities and colleges within 400 m"),
    ("hospitales_400", "Hospitals within 400 m"), ("comisarias_800", "Police stations within 800 m"),
    ("gasolineras_150", "Fuel stations within 150 m"), ("estaciones_400", "Rail and transit stations within 400 m"),
    ("estadios_800", "Stadiums within 800 m"), ("locales", "Shops and amenities open within 150 m (by band, opening hours)"),
    ("bares", "Bars, pubs and nightclubs open within 150 m (by band)"),
    ("paradas_300", "Transit stops mapped in OpenStreetMap within 300 m"),
    ("habitantes_400", "Residents within 400 m (Census 2020)"), ("empleos_400", "Jobs within 400 m (LODES 2023)"),
    ("radiancia", "Night-time radiance (VIIRS)"), ("paradas_gtfs_300", "Scheduled transit stops within 300 m (GTFS)"),
    ("buses", "Bus departures per hour within 150 m (by band, typical Wednesday)"),
    ("peatones", "Simulated pedestrians per hour (by band)"), ("franja", "Time band (categorical)"),
    ("a", "Core incidents, spread (by band)"), ("a_todas", "Core incidents, spread (all bands)"),
    ("b", "All incidents of the broad definition, spread (by band)"), ("b_todas", "The same, all bands"),
    ("b_cat_*", "Each of the ten broad categories, spread (all hours; 10 features)"),
    ("c_*", "Incidents in each bag (violent, property, other), spread, by band and all bands (6 features)"),
    ("z", "Core incidents per km of street in the Census block group (by band)"), ("z_todas", "The same, all bands"),
    ("t_tasa", "City-wide core incidents per year per 1,000 residents"),
]


def tabla_rasgos():
    """Rasgos de cada nivel, leidos de formula.py (los del modelo sellado)."""
    import sys
    sys.path.insert(0, str(RAIZ / "src" / "multiciudad"))
    sys.path.insert(0, str(RAIZ / "src"))
    import formula as FO
    niveles = [("B", "B"), ("A", "A"), ("C", "C"), ("zona", "Zone"), ("totales", "Total"), ("sin_delitos", "None"),
               ("solo_mapa", "Map")]
    usados = {n: set(FO.rasgos_de(n)) for n, _ in niveles}
    filas = []
    for clave, descripcion in RASGOS:
        if clave.endswith("*"):
            marca = [any(r.startswith(clave[:-1]) for r in usados[n]) for n, _ in niveles]
        else:
            marca = [clave in usados[n] for n, _ in niveles]
        filas.append(f"{descripcion} & " + " & ".join("$\\bullet$" if m else "" for m in marca) + " \\\\")
        if clave in ("franja",):
            filas.append("\\midrule")
    faltan = set().union(*usados.values()) - {c for c, _ in RASGOS} - {r for r in set().union(*usados.values())
                                                                        if r.startswith(("b_cat_", "c_"))}
    assert not faltan, f"rasgos sin descripcion: {faltan}"
    escribir("t_rasgos", "\\begin{tabular}{p{0.52\\textwidth}ccccccc}\n\\toprule\nFeature & "
             + " & ".join(n for _, n in niveles) + " \\\\\n\\midrule\n" + "\n".join(filas) + "\n\\bottomrule\n\\end{tabular}\n")


REVISION = RAIZ / "investigacion/resultados/revision"


def _lee(nombre):
    archivo = REVISION / nombre
    return pd.read_csv(archivo) if archivo.exists() else None


def _celda(valor, ic):
    if valor is None or pd.isna(valor):
        return "--"
    return pct(valor, numeros(ic)[-2:]) if ic is not None and len(numeros(ic)) >= 2 else num(valor)


def tabla_sensibilidad():
    """Analisis posteriores al examen (exploratorios): la medida registrada de Detailed (B) y de
    No crime data con cada variante, frente a lo registrado."""
    r2, r3, r5, r6 = _lee("r2_fondo.csv"), _lee("r3_fuga_temporal.csv"), _lee("r5_exclusiones.csv"), _lee("r6_tempe_rutas.csv")
    r6b = _lee("r6b_tempe_rutas.csv")
    r4, r8 = _lee("r4_intervalos.csv"), _lee("r8_ponderado.csv")

    def de(t, ciudad, mapa, **filtro):
        if t is None:
            return None
        f = t[(t["ciudad"] == ciudad) & (t["mapa"] == mapa)]
        for k, v in filtro.items():
            f = f[f[k] == v]
        return f.iloc[0] if len(f) else None

    variantes = [
        ("As registered (exam)", lambda c, m: (rutas(c, m).get("cambio_pct"), rutas(c, m).get("ic95"))),
        ("Background risk $1\\times$ (exam: $3\\times$)", lambda c, m: _par(de(r2, c, m, fondo=1), "cambio_registrado", "ic95_registrado")),
        ("Background risk $10\\times$", lambda c, m: _par(de(r2, c, m, fondo=10), "cambio_registrado", "ic95_registrado")),
        ("Public features from 2025", lambda c, m: _par(de(r3, c, m), "cambio_registrado", "ic95_registrado")),
        ("Incidents near institutions kept", lambda c, m: _par(de(r5, c, m, variante="r5_lugares"), "cambio_registrado", "ic95_registrado")),
        ("Street tolerance 100 m (exam: 50 m)", lambda c, m: _par(de(r5, c, m, variante="r5_calle_100"), "cambio_registrado", "ic95_registrado")),
        ("Tempe: pre-specified category correction", lambda c, m: _par(de(r6, c, m), "cambio_registrado", "ic95_registrado") if c == "tempe" else (None, None)),
        ("Tempe: official NIBRS codes (post hoc)", lambda c, m: _par(de(r6b, c, m), "cambio_registrado", "ic95_registrado") if c == "tempe" else (None, None)),
        ("Trips weighted by simulated pedestrians", lambda c, m: _par(de(r8, c, m), "registrado_ponderado", "ic95_registrado")),
        ("Overdispersed crime counts (interval only)", lambda c, m: _par(de(r4, c, m), "cambio_pct", "ic95_zonas_y_binomial_negativa")),
    ]
    lineas = []
    for k, (mapa, titulo) in enumerate([("B", "Detailed (B)"), ("sin_delitos", "No crime data")]):
        lineas.append(("\\midrule\n" if k else "") + f"\\multicolumn{{4}}{{l}}{{\\textit{{{titulo}}}}} \\\\")
        for nombre, f in variantes:
            celdas = []
            for c in CIUDADES:
                valor, ic_ = f(c, mapa)
                celdas.append(_celda(valor, ic_))
            lineas.append(f"\\quad {nombre} & " + " & ".join(celdas) + " \\\\")
    escribir("t_sensibilidad", "\\begin{tabular}{lccc}\n\\toprule\nAnalysis & " + " & ".join(NOMBRE[c] for c in CIUDADES)
             + " \\\\\n\\midrule\n" + "\n".join(lineas) + "\n\\bottomrule\n\\end{tabular}\n")


def _par(fila, columna, columna_ic):
    return (None, None) if fila is None else (fila[columna], fila[columna_ic])


def tabla_buscador():
    """R1: la ruta de la app frente a la cota de Lagrange (puntos del % de exposicion)."""
    t = _lee("r1_buscador.csv")
    if t is None:
        return
    filas = []
    for c in CIUDADES:
        for mapa, nombre in [("B", "Detailed (B)"), ("sin_delitos", "No crime data")]:
            f = t[(t["ciudad"] == c) & (t["mapa"] == mapa)]
            if not len(f):
                continue
            f = f.iloc[0]
            filas.append(f"{NOMBRE[c] if mapa == 'B' else ''} & {nombre} & {f['brecha_mediana']:.2f} & {f['brecha_p95']:.1f} & "
                         f"{f['parte_brecha_hasta_1']:.1%} & {f['parte_brecha_hasta_3']:.1%} & {f['parte_mejora_perdida_3']:.1%} \\\\")
    escribir("t_buscador", "\\begin{tabular}{llrrrrr}\n\\toprule\nCity & Map & Median gap & 95th pct. gap & Gap $\\le 1$ & Gap $\\le 3$ "
             "& Missed $\\ge 3$ \\\\\n\\midrule\n" + "\n".join(filas).replace("%", "\\%") + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_g16_variantes():
    """R10: variantes de G16 (todas sobre todos los viajes) y diferencia pareada con nuestros mapas."""
    t, p = _lee("r10_g16_cambio_todos.csv"), _lee("r10_g16_pareadas.csv")
    if t is None:
        return
    nombres = [("G16i_nucleo", "Isotropic kernel, core crime"), ("G16i_todos", "Isotropic kernel, all crime"),
               ("G16ui_nucleo", "Isotropic, uniform sampling, core crime"), ("G16ui_todos", "Isotropic, uniform sampling, all crime"),
               ("G16f_nucleo", "By time band, core crime"), ("G16f_todos", "By time band, all crime"),
               ("G16uf_nucleo", "By time band, uniform sampling, core crime"), ("G16uf_todos", "By time band, uniform sampling, all crime")]
    filas = []
    for m, nombre in nombres:
        celdas = []
        for c in CIUDADES:
            f = t[(t["ciudad"] == c) & (t["metodo"] == m)]
            g = p[(p["ciudad"] == c) & (p["publicado"] == m)] if p is not None else []
            if not len(f):
                celdas.append("--")
                continue
            texto = pct(f.iloc[0]["cambio_todos_los_viajes"], numeros(f.iloc[0]["ic95_zonas_1km"]))
            if len(g):
                texto += f"; {num(g.iloc[0]['diferencia_pp'])}"
            celdas.append(texto)
        filas.append(f"{nombre} & " + " & ".join(celdas) + " \\\\")
    escribir("t_g16_variantes", "\\begin{tabular}{lccc}\n\\toprule\nG16 variant & " + " & ".join(NOMBRE[c] for c in CIUDADES)
             + " \\\\\n\\midrule\n" + "\n".join(filas) + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_r3_completa():
    """R3: todos los mapas con los rasgos publicos de 2025 frente al examen."""
    t = _lee("r3_fuga_temporal.csv")
    if t is None:
        return
    filas = []
    for m, nombre in MAPAS:
        if not len(t[t["mapa"] == m]):
            continue
        celdas = []
        for c in CIUDADES:
            f = t[(t["ciudad"] == c) & (t["mapa"] == m)]
            celdas.append("--" if not len(f) else f"{pct(f.iloc[0]['cambio_registrado'], numeros(f.iloc[0]['ic95_registrado']))} "
                                                   f"[{num(f.iloc[0]['examen_registrado'])}]")
        filas.append(f"{nombre} & " + " & ".join(celdas) + " \\\\")
    escribir("t_r3", "\\begin{tabular}{lccc}\n\\toprule\nMap & " + " & ".join(NOMBRE[c] for c in CIUDADES)
             + " \\\\\n\\midrule\n" + "\n".join(filas) + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_r7():
    """R7: medida por persona con otros pisos y sin las franjas de noche."""
    t = _lee("r7_por_persona.csv")
    if t is None:
        return
    variantes = [("mediana (registrada)", "Median floor (registered)"), ("percentil 25", "25th-percentile floor"),
                 ("percentil 75", "75th-percentile floor"), ("sin noche", "Day bands only")]
    filas = []
    for m, nombre in MAPAS[:7]:
        for k, (v, vn) in enumerate(variantes):
            celdas = []
            for c in CIUDADES:
                f = t[(t["ciudad"] == c) & (t["mapa"] == m) & (t["variante"] == v)]
                celdas.append("--" if not len(f) else pct(f.iloc[0]["por_persona_pct"], numeros(f.iloc[0]["ic95"])))
            filas.append(f"{nombre if k == 0 else ''} & {vn} & " + " & ".join(celdas) + " \\\\")
        filas.append("\\midrule")
    escribir("t_r7", "\\begin{tabular}{llccc}\n\\toprule\nMap & Variant & " + " & ".join(NOMBRE[c] for c in CIUDADES)
             + " \\\\\n\\midrule\n" + "\n".join(filas[:-1]) + "\n\\bottomrule\n\\end{tabular}\n")


TRANSPORTE = RAIZ / "investigacion/resultados/transporte"
LIMITES = [("2", "2 min"), ("5", "5 min"), ("10", "10 min"), ("app", "App default")]
MAPAS_CURVA = [("B", "Detailed (B)"), ("sin_delitos", "No crime data"), ("oraculo", "Oracle (ceiling)")]


def _curva(carpeta=TRANSPORTE):
    c = pd.read_csv(carpeta / "curva.csv", dtype={"limite": str})
    return {(f["ciudad"], f["mapa"], f["limite"]): f for _, f in c.iterrows()}


def tabla_curva(carpeta=TRANSPORTE, ciudades=None):
    """Analisis de transporte A (exploratorio): cambio sobre todos los viajes segun el
    limite de minutos extra, y el costo (parte de viajes con alternativa, minutos extra)."""
    c, ciudades = _curva(carpeta), ciudades or CIUDADES
    cambio, costo = [], []
    for k, (m, nombre) in enumerate(MAPAS_CURVA):
        if k:
            cambio.append("\\midrule")
            costo.append("\\midrule")
        for lim, etiqueta in LIMITES:
            f = [c[(ci, m, lim)] for ci in ciudades]
            cambio.append(f"{nombre if lim == '2' else ''} & {etiqueta} & "
                          + " & ".join(pct(x["cambio_todos"], numeros(x["ic95_zonas"])) for x in f) + " \\\\")
            costo.append(f"{nombre if lim == '2' else ''} & {etiqueta} & "
                         + " & ".join(f"{x['parte_con_alternativa']:.0%} & {x['min_extra_mediana_con_alternativa']:.1f}" for x in f)
                         + " \\\\")
    cab = " & ".join(NOMBRE.get(ci, ci) for ci in ciudades)
    escribir("t_curva", "\\begin{tabular}{ll" + "c" * len(ciudades) + "}\n\\toprule\n"
             f"Map & Detour limit & {cab} \\\\\n\\midrule\n" + "\n".join(cambio) + "\n\\bottomrule\n\\end{tabular}\n")
    escribir("t_curva_costo", "\\begin{tabular}{ll" + "rr" * len(ciudades) + "}\n\\toprule\n"
             " & & " + " & ".join(f"\\multicolumn{{2}}{{c}}{{{NOMBRE.get(ci, ci)}}}" for ci in ciudades) + " \\\\\n"
             "Map & Detour limit & " + " & ".join(["Alt. (\\%) & Extra min."] * len(ciudades)) + " \\\\\n\\midrule\n"
             + "\n".join(costo).replace("%", "\\%") + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_sistema(carpeta=TRANSPORTE):
    """Analisis de transporte B (descriptivo): concentracion de los metros caminados por tramo."""
    s = pd.read_csv(carpeta / "sistema.csv")
    filas = []
    for ci in CIUDADES:
        for m, nombre in MAPAS_CURVA[:2]:
            a = s[(s["ciudad"] == ci) & (s["mapa"] == m) & (s["escenario"] == "mas_rapida")].iloc[0]
            b = s[(s["ciudad"] == ci) & (s["mapa"] == m) & (s["escenario"] == "sugerencia_app")].iloc[0]
            filas.append(f"{NOMBRE[ci] if m == 'B' else ''} & {nombre} & "
                         f"{a['tramos_distintos_usados']:,} & {b['tramos_distintos_usados']:,} & "
                         f"{a['parte_metros_en_1pct_mas_usado']:.1%} & {b['parte_metros_en_1pct_mas_usado']:.1%} & "
                         f"{a['gini_metros']:.3f} & {b['gini_metros']:.3f} \\\\")
        filas.append("\\midrule")
    escribir("t_sistema", "\\begin{tabular}{llrrrrrr}\n\\toprule\n"
             " & & \\multicolumn{2}{c}{Distinct segments used} & \\multicolumn{2}{c}{Meters on top 1\\% segments}"
             " & \\multicolumn{2}{c}{Gini of meters} \\\\\n"
             "City & Map & Fastest & Suggested & Fastest & Suggested & Fastest & Suggested \\\\\n\\midrule\n"
             + "\n".join(filas[:-1]).replace("%", "\\%") + "\n\\bottomrule\n\\end{tabular}\n")


def tabla_tiempos(carpeta=TRANSPORTE):
    """Analisis de transporte C: tiempo por consulta del buscador (sin cargar la red)."""
    t = pd.read_csv(carpeta / "tiempos.csv")
    filas = [f"{NOMBRE[f['ciudad']]} & {f['tramos']:,} & {f['consultas']} & {f['mediana_s']:.2f} & {f['p95_s']:.2f} \\\\"
             for _, f in t.iterrows()]
    escribir("t_tiempos", "\\begin{tabular}{lrrrr}\n\\toprule\n"
             "City & Street segments & Queries & Median (s) & 95th percentile (s) \\\\\n\\midrule\n"
             + "\n".join(filas) + "\n\\bottomrule\n\\end{tabular}\n")


if __name__ == "__main__":
    tabla_datos()
    tabla_rutas()
    tabla_hipotesis()
    tabla_controles()
    tabla_retencion()
    tabla_robustez()
    tabla_rapida()
    tabla_comparacion()
    tabla_por_persona()
    tabla_exclusiones()
    tabla_rasgos()
    # Analisis posteriores al examen (revision externa): solo las tablas cuyos archivos existen
    if REVISION.exists():
        tabla_sensibilidad()
        tabla_buscador()
        tabla_g16_variantes()
        tabla_r3_completa()
        tabla_r7()
    # Analisis de transporte (exploratorios): solo si ya existen sus archivos
    for archivo, funcion in [("curva.csv", tabla_curva), ("sistema.csv", tabla_sistema), ("tiempos.csv", tabla_tiempos)]:
        if (TRANSPORTE / archivo).exists():
            funcion()
        else:
            print("falta", TRANSPORTE / archivo, "- tabla no generada")
