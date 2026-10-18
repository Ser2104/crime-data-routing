"""
Genera la FIGURA principal del articulo desde los archivos de resultados (sin copiar
numeros a mano). Ejecutar desde la carpeta del proyecto:
    python investigacion/articulo/generar_figuras.py
Salida: investigacion/articulo/figuras/fig_escalera.pdf y .png

Figura 1, "la escalera": cambio en delitos violentos del ano siguiente (ruta de menor
riesgo contra la mas rapida) por nivel de informacion y por ciudad, con su IC95.
Punto + intervalo (cada ciudad con su color y su forma), una sola escala, linea de
referencia en 0 y grupos de niveles separados.
Paleta: primeras 3 posiciones de la paleta de referencia de la guia dataviz
(validada: CVD y vision normal pasan en todos los pares).
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = Path(__file__).resolve().parent / "figuras"
CARPETA = {"filadelfia": RAIZ / "investigacion/resultados/examen_v2",
           "baton_rouge": RAIZ / "investigacion/resultados/examen_v2",
           "tempe": RAIZ / "investigacion/resultados/examen_v2_tempe"}
CIUDAD = {"filadelfia": ("Philadelphia", "#2a78d6", "o"),
          "baton_rouge": ("Baton Rouge", "#eb6834", "s"),
          "tempe": ("Tempe", "#1baf7a", "^")}
GRUPOS = [("Crime by street", [("B", "Detailed (B)"), ("A", "Core only (A)"), ("C", "Coarse (C)")]),
          ("Aggregated crime", [("zona", "Zone"), ("totales", "City total")]),
          ("Without crime data", [("sin_delitos", "No crime data"), ("solo_mapa", "Map only")])]
TINTA, TINTA_2, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"


def rutas(ciudad, mapa):
    return json.loads((CARPETA[ciudad] / f"{ciudad}_rutas_{mapa}_2000.json").read_text())


def escalera():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": TINTA_2,
                         "axes.labelcolor": TINTA, "xtick.color": TINTA_2, "ytick.color": TINTA})
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    y, posiciones, etiquetas, separadores, titulos = 0.0, [], [], [], []
    for g, (titulo, niveles) in enumerate(GRUPOS):
        if g:
            separadores.append(y + 0.35)
            y += 0.7
        titulos.append((y, titulo))
        y += 0.55
        for clave, nombre in niveles:
            posiciones.append((y, clave))
            etiquetas.append(nombre)
            y += 1.0
    desplazamiento = {"filadelfia": -0.24, "baton_rouge": 0.0, "tempe": 0.24}
    for yy, clave in posiciones:
        for ciudad, (nombre, color, marca) in CIUDAD.items():
            r = rutas(ciudad, clave)
            yc = yy + desplazamiento[ciudad]
            ax.plot(r["ic95"], [yc, yc], color=color, lw=1.6, solid_capstyle="round", zorder=2)
            ax.plot(r["cambio_pct"], yc, marker=marca, ms=6.5, color=color, mec="white", mew=1.0, ls="none", zorder=3)
    ax.axvline(0, color=TINTA_2, lw=1.0, zorder=1)
    ax.set_yticks([p for p, _ in posiciones])
    ax.set_yticklabels(etiquetas)
    for ys, t in titulos:
        ax.text(-0.01, ys, t, transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=9, fontweight="bold", color=TINTA)
    for s in separadores:
        ax.axhline(s, color=REJILLA, lw=0.8, zorder=0)
    ax.set_ylim(y - 0.4, -0.3)
    ax.set_xlim(-72, 30)
    ax.set_xticks(range(-70, 31, 10))
    ax.xaxis.grid(True, color=REJILLA, lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0, pad=4)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.set_xlabel("Change in future violent crime on the lowest-risk route vs. the fastest route (%)")
    ax.text(-1.5, 1.012, "← fewer crimes", transform=ax.get_xaxis_transform(), ha="right", va="bottom",
            fontsize=8, color=TINTA_2)
    ax.text(1.5, 1.012, "more crimes →", transform=ax.get_xaxis_transform(), ha="left", va="bottom",
            fontsize=8, color=TINTA_2)
    leyenda = [Line2D([0], [0], color=c, marker=m, ms=6.5, mec="white", lw=1.6, label=n) for n, c, m in CIUDAD.values()]
    ax.legend(handles=leyenda, loc="upper right", bbox_to_anchor=(1.0, 0.985), frameon=False, fontsize=8.5,
              handlelength=1.6, title="Point: estimate; line: 95% CI", title_fontsize=7.5)
    fig.tight_layout()
    SALIDA.mkdir(exist_ok=True)
    fig.savefig(SALIDA / "fig_escalera.pdf")
    fig.savefig(SALIDA / "fig_escalera.png", dpi=200)
    plt.close(fig)
    print("escrita fig_escalera (.pdf y .png)")


TRANSPORTE = RAIZ / "investigacion/resultados/transporte"
LIMITES = [("2", "2"), ("5", "5"), ("10", "10"), ("app", "App\ndefault")]
MAPAS_CURVA = [("B", "Detailed (B)"), ("sin_delitos", "No crime data"), ("oraculo", "Oracle (ceiling)")]


def curva(carpeta=TRANSPORTE, ciudades=None, salida=SALIDA):
    """Figura 2, la curva costo-beneficio (analisis de transporte A, exploratorio): cambio en
    delitos violentos del ano siguiente sobre TODOS los viajes segun el limite de minutos
    extra. Un panel por mapa, misma escala; cada ciudad con su color y su forma (como Fig. 1)."""
    import pandas as pd
    c = pd.read_csv(carpeta / "curva.csv", dtype={"limite": str})
    ciudades = ciudades or list(CIUDAD)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": TINTA_2,
                         "axes.labelcolor": TINTA, "xtick.color": TINTA_2, "ytick.color": TINTA_2})
    fig, ejes = plt.subplots(1, len(MAPAS_CURVA), figsize=(6.2, 3.6), sharey=True)   # ancho del texto: letra legible
    desplazamiento = {ci: (k - (len(ciudades) - 1) / 2) * 0.14 for k, ci in enumerate(ciudades)}
    for ax, (mapa, titulo) in zip(ejes, MAPAS_CURVA):
        for ci in ciudades:
            nombre, color, marca = CIUDAD[ci]
            f = c[(c["ciudad"] == ci) & (c["mapa"] == mapa)].set_index("limite").reindex([l for l, _ in LIMITES])
            x = [k + desplazamiento[ci] for k in range(len(LIMITES))]
            ic = [json.loads(v) for v in f["ic95_zonas"]]
            ax.plot(x[:3], f["cambio_todos"].values[:3], color=color, lw=1.4, zorder=2)   # 2-5-10 unidos; el de la app aparte
            for xi, yi, (lo, hi) in zip(x, f["cambio_todos"].values, ic):
                ax.plot([xi, xi], [lo, hi], color=color, lw=1.2, alpha=0.55, solid_capstyle="round", zorder=1)
            ax.plot(x, f["cambio_todos"].values, marker=marca, ms=5.5, color=color, mec="white", mew=0.9, ls="none", zorder=3)
        ax.axhline(0, color=TINTA_2, lw=1.0, zorder=0)
        ax.axvline(2.5, color=REJILLA, lw=0.8, ls=(0, (3, 3)), zorder=0)
        ax.set_title(titulo, fontsize=9, color=TINTA, loc="left")
        ax.set_xticks(range(len(LIMITES)))
        ax.set_xticklabels([e for _, e in LIMITES])
        ax.yaxis.grid(True, color=REJILLA, lw=0.6)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
    ejes[0].set_ylabel("Change in future violent crime,\nall trips (%)")
    fig.supxlabel("Limit on extra walking time (minutes)", fontsize=9, color=TINTA)
    leyenda = [Line2D([0], [0], color=CIUDAD[ci][1], marker=CIUDAD[ci][2], ms=5.5, mec="white", lw=1.4, label=CIUDAD[ci][0])
               for ci in ciudades]
    fig.legend(handles=leyenda, loc="upper center", ncol=len(ciudades), frameon=False, fontsize=8,
               bbox_to_anchor=(0.55, 1.0), title="Point: estimate; line: 95% CI (1-km zones)", title_fontsize=7.5)
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    salida.mkdir(exist_ok=True)
    fig.savefig(salida / "fig_curva.pdf")
    fig.savefig(salida / "fig_curva.png", dpi=200)
    plt.close(fig)
    print("escrita fig_curva (.pdf y .png)")


REVISION = RAIZ / "investigacion/resultados/revision"


def _ic_de(texto):
    import re
    v = [float(x) for x in re.findall(r"-?\d+\.?\d*(?:e-?\d+)?", str(texto).replace("np.float64", ""))]
    return v[-2:] if len(v) >= 2 else [float("nan"), float("nan")]


def sensibilidad(carpeta=REVISION, salida=SALIDA):
    """Figura de robustez (analisis posteriores al examen): la medida registrada de cada mapa con
    cada variante, por ciudad, con la estimacion del examen como referencia. Mismo diseno que la
    Figura 1 (punto + IC95, cada ciudad con su color y su forma)."""
    import pandas as pd
    lee = lambda n: pd.read_csv(carpeta / n) if (carpeta / n).exists() else None
    r2, r3, r5, r6, r8 = lee("r2_fondo.csv"), lee("r3_fuga_temporal.csv"), lee("r5_exclusiones.csv"), lee("r6_tempe_rutas.csv"), lee("r8_ponderado.csv")
    r6b = lee("r6b_tempe_rutas.csv")

    def fila(t, ciudad, mapa, col, col_ic, **filtro):
        if t is None:
            return None
        f = t[(t["ciudad"] == ciudad) & (t["mapa"] == mapa)]
        for k, v in filtro.items():
            f = f[f[k] == v]
        return (float(f.iloc[0][col]), _ic_de(f.iloc[0][col_ic])) if len(f) else None

    variantes = [
        ("As registered (exam)", lambda c, m: (rutas(c, m)["cambio_pct"], rutas(c, m)["ic95"])),
        ("Background risk 1×", lambda c, m: fila(r2, c, m, "cambio_registrado", "ic95_registrado", fondo=1)),
        ("Background risk 10×", lambda c, m: fila(r2, c, m, "cambio_registrado", "ic95_registrado", fondo=10)),
        ("Public features from 2025", lambda c, m: fila(r3, c, m, "cambio_registrado", "ic95_registrado")),
        ("Incidents near institutions kept", lambda c, m: fila(r5, c, m, "cambio_registrado", "ic95_registrado", variante="r5_lugares")),
        ("Street tolerance 100 m", lambda c, m: fila(r5, c, m, "cambio_registrado", "ic95_registrado", variante="r5_calle_100")),
        ("Tempe: category correction", lambda c, m: fila(r6, c, m, "cambio_registrado", "ic95_registrado") if c == "tempe" else None),
        ("Tempe: official codes (post hoc)", lambda c, m: fila(r6b, c, m, "cambio_registrado", "ic95_registrado") if c == "tempe" else None),
        ("Weighted by pedestrians", lambda c, m: fila(r8, c, m, "registrado_ponderado", "ic95_registrado")),
    ]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": TINTA_2,
                         "axes.labelcolor": TINTA, "xtick.color": TINTA_2, "ytick.color": TINTA})
    fig, ejes = plt.subplots(1, 2, figsize=(6.6, 4.2), sharey=True, sharex=True)
    desplazamiento = {"filadelfia": -0.22, "baton_rouge": 0.0, "tempe": 0.22}
    for ax, (mapa, titulo) in zip(ejes, [("B", "Detailed (B)"), ("sin_delitos", "No crime data")]):
        for k, (nombre, f) in enumerate(variantes):
            for ciudad, (_, color, marca) in CIUDAD.items():
                v = f(ciudad, mapa)
                if v is None:
                    continue
                y = k + desplazamiento[ciudad]
                ax.plot(v[1], [y, y], color=color, lw=1.4, solid_capstyle="round", zorder=2)
                ax.plot(v[0], y, marker=marca, ms=5.5, color=color, mec="white", mew=0.9, ls="none", zorder=3)
        ax.axvline(0, color=TINTA_2, lw=1.0, zorder=1)
        ax.axhline(0.5, color=REJILLA, lw=0.8, zorder=0)
        ax.set_title(titulo, fontsize=9, color=TINTA, loc="left")
        ax.xaxis.grid(True, color=REJILLA, lw=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
    ejes[0].set_yticks(range(len(variantes)))
    ejes[0].set_yticklabels([n for n, _ in variantes])
    ejes[0].set_ylim(len(variantes) - 0.5, -0.6)
    leyenda = [Line2D([0], [0], color=c, marker=m, ms=5.5, mec="white", lw=1.4, label=n) for n, c, m in CIUDAD.values()]
    fig.legend(handles=leyenda, loc="upper center", ncol=3, frameon=False, fontsize=8, bbox_to_anchor=(0.6, 1.0),
               title="Registered measure: trips with an alternative; point: estimate; line: 95% CI", title_fontsize=7.5)
    fig.supxlabel("Change in future violent crime on lowest-risk vs. fastest routes (%)", fontsize=9, color=TINTA)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    salida.mkdir(exist_ok=True)
    fig.savefig(salida / "fig_sensibilidad.pdf")
    fig.savefig(salida / "fig_sensibilidad.png", dpi=200)
    plt.close(fig)
    print("escrita fig_sensibilidad (.pdf y .png)")


def resumen_grafico(salida=SALIDA):
    """Resumen grafico (graphical abstract) para TR-C: una imagen horizontal, legible a 13 cm de
    ancho y de al menos 1,328 pixeles. Izquierda: cuanto delito violento evita la ruta de menor
    riesgo en cada nivel de datos (un punto por ciudad, con su color y su forma; la linea gris une
    la menor y la mayor). Derecha: los tres hallazgos. Las cifras salen de los archivos del examen."""
    filas = [("Street-level crime data", [("B", "Detailed records"), ("A", "Core violent only"), ("C", "Broad categories")]),
             ("Aggregated crime data", [("zona", "Counts by zone"), ("totales", "City-wide total")]),
             ("No crime data", [("sin_delitos", "National public data"), ("solo_mapa", "OpenStreetMap only")])]
    calle = [-rutas(c, m)["cambio_pct"] for c in CIUDAD for m in ("B", "A", "C")]
    minutos = [rutas(c, m)["min_extra_mediana"] for c in CIUDAD for m in ("B", "A", "C")]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.edgecolor": TINTA_2,
                         "axes.labelcolor": TINTA, "xtick.color": TINTA_2, "ytick.color": TINTA})
    fig = plt.figure(figsize=(13 / 2.54, 6.4 / 2.54))   # 13 cm de ancho: el tamano en que se lee
    ax = fig.add_axes((0.325, 0.20, 0.335, 0.60))
    desplazamiento = {"filadelfia": -0.3, "baton_rouge": 0.0, "tempe": 0.3}   # valores iguales no se tapan
    y, posiciones, etiquetas, titulos = 0.0, [], [], []
    for g, (titulo, niveles) in enumerate(filas):
        if g:
            y += 0.45
        titulos.append((y, titulo))
        y += 0.75
        for clave, nombre in niveles:
            posiciones.append((y, clave))
            etiquetas.append(nombre)
            y += 1.0
    for yy, clave in posiciones:
        valores = [-rutas(c, clave)["cambio_pct"] for c in CIUDAD]
        ax.plot([min(valores), max(valores)], [yy, yy], color="#d3d2cd", lw=2.0, solid_capstyle="round", zorder=1)
        for ciudad, (nombre, color, marca) in CIUDAD.items():
            ax.plot(-rutas(ciudad, clave)["cambio_pct"], yy + desplazamiento[ciudad], marker=marca, ms=5, color=color,
                    mec="white", mew=0.8, ls="none", zorder=3)
    ax.axvline(0, color=TINTA_2, lw=0.9, zorder=0)
    ax.set_yticks([p for p, _ in posiciones])
    ax.set_yticklabels(etiquetas)
    for ys, t in titulos:
        ax.text(-0.02, ys, t, transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=7.5,
                fontweight="bold", color=TINTA)
    ax.set_ylim(y - 0.35, -0.25)
    ax.set_xlim(-10, 62)
    ax.set_xticks([0, 20, 40, 60])
    ax.xaxis.grid(True, color=REJILLA, lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0, pad=3)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.set_xlabel("% fewer violent crimes on the safer route\nthan on the fastest route", fontsize=7)
    leyenda = [Line2D([0], [0], color=c, marker=m, ms=5.5, mec="white", lw=0, label=n) for n, c, m in CIUDAD.values()]
    ax.legend(handles=leyenda, loc="lower left", bbox_to_anchor=(-0.04, 1.01), ncol=3, frameon=False, fontsize=6.5,
              handletextpad=0.2, columnspacing=0.9, borderaxespad=0)

    fig.text(0.02, 0.96, "Pre-registered test in 3 U.S. cities the risk models never saw  ·  2,000 walking trips per city",
             fontsize=7, color=TINTA_2, va="top")
    hallazgos = [("Street-level crime data", f"{min(calle):.0f}–{max(calle):.0f}% fewer recorded violent\ncrimes, "
                  f"about {sum(minutos) / len(minutos):.0f} extra minute"),
                 ("Same data, simple map", "a map of past crime did\nabout as well as the model"),
                 ("Aggregated or public\ndata only", "about half the benefit,\nlike a simple rule")]
    for k, (cabeza, texto) in enumerate(hallazgos):
        yk = 0.82 - k * 0.245
        lineas = cabeza.count("\n")
        fig.text(0.695, yk, cabeza, fontsize=7, fontweight="bold", color=TINTA, va="top", linespacing=1.15)
        fig.text(0.695, yk - 0.06 - 0.05 * lineas, texto, fontsize=6.6, color=TINTA_2, va="top", linespacing=1.2)
    salida.mkdir(exist_ok=True)
    fig.savefig(salida / "resumen_grafico.pdf")
    fig.savefig(salida / "resumen_grafico.png", dpi=300)
    plt.close(fig)
    print("escrita resumen_grafico (.pdf y .png)")


if __name__ == "__main__":
    escalera()
    resumen_grafico()
    if REVISION.exists() and any(REVISION.glob("r*_*.csv")):
        sensibilidad()
    if (TRANSPORTE / "curva.csv").exists():
        curva()
    else:
        print("falta", TRANSPORTE / "curva.csv", "- fig_curva no generada")
