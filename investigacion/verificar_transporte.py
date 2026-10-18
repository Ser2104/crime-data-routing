"""
Chequeos de los ANALISIS DE TRANSPORTE (investigacion/analisis_transporte.py) antes de
usarlos en el articulo. No calcula resultados nuevos: comprueba que los ya calculados
sean validos.
    python investigacion/verificar_transporte.py
1. Cada corrida con limite fijo respeta su limite: ninguna ruta "Lowest risk" (sin relleno)
   tarda mas que el limite sobre la mas rapida.
2. Cada corrida tiene los 2,000 viajes con ruta mas rapida.
3. La ruta mas rapida es la misma con cualquier mapa y limite (no depende del riesgo).
4. La curva esta completa: 3 ciudades x 3 mapas x (app + 3 limites).
"""
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
T = RAIZ / "investigacion/resultados/transporte"
CIUDADES = ["filadelfia", "baton_rouge", "tempe"]
MAPAS = ["B", "sin_delitos", "oraculo"]
LIMITES = [2, 5, 10]


def main():
    fallas = []
    rapidas = {}
    for c in CIUDADES:
        for m in MAPAS:
            for lim in LIMITES:
                v = pd.read_json(T / f"{c}_viajes_{m}_limite{lim}_2000.jsonl", lines=True)
                v = v[~v["relleno"]]
                rap = v[v["etiqueta"] == "Fastest"].drop_duplicates("viaje").set_index("viaje")
                seg = v[v["etiqueta"] == "Lowest risk"].drop_duplicates("viaje").set_index("viaje")
                extra = (seg["minutos"] - rap["minutos"].reindex(seg.index)).max()
                n = rap.index.nunique()
                print(f"{c:12s} {m:12s} limite {lim:2d}: viajes {n}, con alternativa {len(seg)}, "
                      f"maximo de minutos extra {extra:.1f}")
                if extra > lim + 0.11:      # los minutos se redondean a 0.1
                    fallas.append(f"{c} {m} {lim}: extra {extra:.1f} > {lim}")
                if n != 2000:
                    fallas.append(f"{c} {m} {lim}: {n} viajes")
                ids = rap["ids"].apply(lambda x: tuple(sorted(x)))
                if c in rapidas and not ids.sort_index().equals(rapidas[c]):
                    fallas.append(f"{c} {m} {lim}: la ruta mas rapida cambio")
                rapidas.setdefault(c, ids.sort_index())
    curva = pd.read_csv(T / "curva.csv", dtype={"limite": str})
    if len(curva) != len(CIUDADES) * len(MAPAS) * 4 or curva.duplicated(["ciudad", "mapa", "limite"]).any():
        fallas.append(f"curva.csv: {len(curva)} filas")
    print("\nRESULTADO:", "OK" if not fallas else "REVISAR")
    for f in fallas:
        print("  -", f)
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
