"""
SIMULACRO del examen de reemplazo de Tempe con DATOS INVENTADOS (2026-10-08), antes del
registro en OSF y antes de abrir la caja holdout_tempe2. No toca ningun dato real del
examen ni cambia el codigo sellado: fabrica un archivo falso con el MISMO formato que
entrega la descarga directa de la caja fuerte y lo pasa por el programa del examen
(src/multiciudad/09_examen.py), llamando a sus funciones tal cual.

Que se fabrica (todo al azar, con semilla fija):
    - las columnas de la capa oficial de Tempe, en su orden (descripcion publica del servicio)
    - fechas "AAAA/MM/DD hh:mm:ss+00" (hora local) de 2023-12 a 2026-09, y las columnas de
      anio, mes, dia y hora coherentes; un 1% sin fecha (prueba el respaldo)
    - ubicaciones en nodos reales de la red peatonal de Tempe (datos publicos), con un
      pequeno desplazamiento; un 1% sin ubicacion
    - categorias inventadas (OffenseCustom)
Como los "delitos" son al azar, los resultados NO significan nada: deben salir cerca del
azar, salvo el oraculo. Solo se comprueba que todo corre de punta a punta.

Ejecutar desde la carpeta del proyecto:
    python investigacion/simulacro_tempe.py [--viajes 100]
Salida: data/simulacro/ (no va a git)
"""
import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import osmnx as ox
import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "data" / "simulacro"
CAPA = "https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services/General_Offenses_(Open_Data)/FeatureServer/0"
CATEGORIAS = {"THEFT": 0.28, "SHOPLIFTING": 0.10, "BURGLARY": 0.05, "ASSAULT-SIMPLE": 0.10,
              "ASSAULT-AGGRAVATED": 0.05, "ROBBERY": 0.03, "HOMICIDE": 0.002, "CRIMINAL DAMAGE": 0.08,
              "DUI": 0.05, "DRUG POSSESSION": 0.05, "TRAFFIC STOP": 0.05, "INFORMATION": 0.05,
              "THREATS": 0.03, "WEAPONS VIOLATION": 0.02, "FRAUD": 0.048, "SEX OFFENSE": 0.01}


def fabricar(n, meses_faltantes=(), semilla=7):
    """Archivo falso con el formato de la descarga directa. meses_faltantes: 'AAAA-MM' sin registros."""
    rng = np.random.default_rng(semilla)
    campos = [f["name"] for f in requests.get(CAPA, params={"f": "json"}, timeout=60).json()["fields"]]
    G = ox.load_graphml(RAIZ / "data/public_features/tempe/red_peatonal.graphml")
    nodos = np.array([(d["x"], d["y"]) for _, d in G.nodes(data=True)])
    segundos = rng.integers(pd.Timestamp("2023-12-01").value // 10**9, pd.Timestamp("2026-09-30").value // 10**9, n)
    momento = pd.to_datetime(segundos, unit="s")
    momento = momento[~momento.strftime("%Y-%m").isin(meses_faltantes)]
    n = len(momento)
    lugar = nodos[rng.integers(len(nodos), size=n)] + rng.normal(0, 0.0001, (n, 2))
    d = pd.DataFrame({c: "" for c in campos}, index=range(n))
    d["OBJECTID"] = np.arange(1, n + 1)
    d["PrimaryKey"] = [f"SIM{i:07d}" for i in range(n)]
    d["OccurrenceDatetime"] = momento.strftime("%Y/%m/%d %H:%M:%S+00")
    d["OccurrenceYear"], d["OccurrenceMonth"] = momento.year, momento.month
    d["OccurrenceDatePart"], d["OccurrenceHour"] = momento.day, momento.hour
    d["OffenseCustom"] = rng.choice(list(CATEGORIAS), size=n, p=np.array(list(CATEGORIAS.values())) / sum(CATEGORIAS.values()))
    d["Longitude"], d["Latitude"] = lugar[:, 0].round(6), lugar[:, 1].round(6)
    sin_fecha = rng.random(n) < 0.01
    d.loc[sin_fecha, "OccurrenceDatetime"] = ""   # se reconstruye con anio, mes, dia y hora
    d.loc[rng.random(n) < 0.01, ["Latitude", "Longitude"]] = np.nan   # sale vacio en el CSV
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--viajes", type=int, default=100)
    ap.add_argument("--registros", type=int, default=30000)
    a = ap.parse_args()
    sys.path.insert(0, str(RAIZ / "src" / "multiciudad"))
    spec = importlib.util.spec_from_file_location("examen", RAIZ / "src/multiciudad/09_examen.py")
    ex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex)

    # 1) El chequeo de cobertura debe DETENER un archivo al que le faltan meses
    falso = CARPETA / "falta_un_mes"
    falso.mkdir(parents=True, exist_ok=True)
    fabricar(a.registros, meses_faltantes=("2025-11",)).to_csv(falso / "tempe.csv", index=False)
    crudo = ex.leer_examen("tempe", str(falso))
    lectura = ex.chequeo_lectura("tempe", crudo, ex.PR.normalizar(crudo, "tempe", True))
    print(f"1) archivo sin 2025-11: meses_cubiertos={lectura['meses_cubiertos']:.3f} pasa={lectura['pasa']} "
          f"-> {'BIEN (se detendria)' if not lectura['pasa'] else 'MAL'}", flush=True)

    # 2) Un archivo completo debe pasar la lectura y correr el examen de punta a punta
    falso = CARPETA / "completo"
    falso.mkdir(parents=True, exist_ok=True)
    fabricar(a.registros).to_csv(falso / "tempe.csv", index=False)
    crudo = ex.leer_examen("tempe", str(falso))
    sin_fecha_rescatada = crudo["momento"].notna().mean()
    delitos = ex.PR.normalizar(crudo, "tempe", True)
    lectura = ex.chequeo_lectura("tempe", crudo, delitos)
    print(f"2) lectura: {lectura}", flush=True)
    print(f"   fechas leidas (incluye las reconstruidas): {sin_fecha_rescatada:.3f}", flush=True)
    assert lectura["pasa"], "el archivo completo deberia pasar la lectura"
    modelos = ex.modelos_sellados()
    salida = CARPETA / "resultados"
    salida.mkdir(parents=True, exist_ok=True)
    resultado = ex.evaluar("tempe", ex.EXAMEN["tempe"], delitos, modelos, salida, a.viajes)
    ex.escribir_resumen(salida, {"tempe": resultado})
    print(f"\nSIMULACRO TERMINADO. Resumen en {salida / 'resumen.md'}", flush=True)


if __name__ == "__main__":
    main()
