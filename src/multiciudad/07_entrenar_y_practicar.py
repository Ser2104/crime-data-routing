"""
Multiciudad, paso 7: entrenar la formula de cada nivel con las ciudades de APRENDER
y probarla en las de PRACTICA (investigacion/protocolo.md). Nunca toca el examen.

Referencias (no son formulas):
    mapa_de_calor_A   el nucleo del pasado repartido, sin modelo
    mapa_de_calor_B   la definicion amplia del pasado repartida, sin modelo
    oraculo           el nucleo del FUTURO repartido (el techo: imposible en la practica)

Calificacion:
    rapida   parte de los delitos del nucleo del futuro que cae en el 10% de la red
             (por largo) que el mapa marca como mas riesgosa, por franja y su promedio,
             con intervalo del 95% remuestreando zonas de 1 km (las calles vecinas no
             son independientes; las coordenadas solo se usan para armar las zonas)
    rutas    (con --rutas) los viajes de evaluar_rutas.py: cambio de delitos del nucleo
             del futuro en la ruta de menor riesgo frente a la mas rapida

Salidas: data/practice/resultados/<fecha>_rapida.csv y _rutas.json; models/multiciudad/<nivel>.txt

Ejecutar desde la carpeta del proyecto:
    python src/multiciudad/07_entrenar_y_practicar.py [--rutas] [--viajes N]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import caja_cerrada  # noqa: E402,F401

import gc  # noqa: E402

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import osmnx as ox  # noqa: E402
import pandas as pd  # noqa: E402

import calificacion as CA  # noqa: E402
import evaluar_rutas as E  # noqa: E402
import formula as FO  # noqa: E402
import reparto as RR  # noqa: E402
from ciudades import DESARROLLO, carpeta, carpeta_publica  # noqa: E402
from riesgo_pie import FRANJAS  # noqa: E402

APRENDER = [c for c, d in DESARROLLO.items() if d["grupo"] == "train"]
PRACTICA = [c for c, d in DESARROLLO.items() if d["grupo"] == "practice"]
MODELOS = Path("models/multiciudad") / FO.VERSION
RESULTADOS = Path("data/practice/resultados")


def cargar(ciudad):
    publicos = FO.leer_publicos(carpeta_publica(ciudad))
    delitos = pd.read_csv(carpeta(ciudad) / "mapa_delitos.csv", index_col="tramo_id")
    zona = CA.zonas_de(publicos)
    return FO.largo_formato(publicos, delitos, ciudad), publicos["largo"], zona, publicos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rutas", action="store_true")
    ap.add_argument("--viajes", type=int, default=E.VIAJES)
    ap.add_argument("--aprender", nargs="*", default=APRENDER, help="subconjunto de ciudades de aprender (ensayos)")
    ap.add_argument("--solo-calificar", action="store_true", help="usar los modelos ya entrenados (models/multiciudad)")
    ap.add_argument("--ciudades", nargs="*", default=PRACTICA, help="subconjunto de ciudades de practica")
    ap.add_argument("--mapas", nargs="*", default=None, help="solo estos mapas en la prueba de rutas")
    a = ap.parse_args()
    assert set(a.aprender) <= set(APRENDER), "solo ciudades del grupo aprender"
    MODELOS.mkdir(parents=True, exist_ok=True)
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M")

    rng = np.random.default_rng(3)
    modelos = {}
    if a.solo_calificar:
        for nivel in FO.NIVELES:
            cats = json.loads((MODELOS / f"{nivel}.json").read_text())
            modelos[nivel] = (lgb.Booster(model_file=str(MODELOS / f"{nivel}.txt")), cats)
        print("Modelos cargados de", MODELOS)
    else:
        print("Cargando ciudades de aprender:", ", ".join(a.aprender))
        datos = pd.concat([cargar(c)[0] for c in a.aprender])
        print(f"  {len(datos):,} filas (tramo x franja)")
        for nivel in FO.NIVELES:
            modelos[nivel] = FO.entrenar(datos, nivel)
            modelos[nivel][0].save_model(str(MODELOS / f"{nivel}.txt"))
            (MODELOS / f"{nivel}.json").write_text(json.dumps(modelos[nivel][1]))
            print(f"  nivel {nivel}: entrenado", flush=True)
        del datos   # liberar memoria antes de calificar
        gc.collect()

    filas, rutas = [], {}
    assert set(a.ciudades) <= set(PRACTICA), "solo ciudades del grupo practica"
    for ciudad in a.ciudades:
        x, largo, zona, publicos = cargar(ciudad)
        mapas = {"mapa_de_calor_A": x["a"].values, "oraculo": x["y"].values,
                 # comparaciones simples, sin formula ni delitos
                 "evitar_avenidas": 1 / (1 + x["dist_principal"].values / 100),
                 "evitar_comercios": 1 + x["locales_400"].values}
        if "b" in x:
            mapas["mapa_de_calor_B"] = x["b"].values
        for nivel, (modelo, cats) in modelos.items():
            if all(c in x.columns for c in FO.DELITOS[nivel]):
                mapas[nivel] = FO.predecir(modelo, cats, x, nivel)
        for nombre, riesgo in mapas.items():
            filas.append({"ciudad": ciudad, "mapa": nombre, **CA.calificar_rapido(x, riesgo, largo, zona, rng)})
            print(f"  {ciudad} {nombre}: promedio {filas[-1]['promedio']:.3f} (IC95 {filas[-1]['ic95']})", flush=True)
        if a.rutas:
            red = carpeta_publica(ciudad) / "red_peatonal.graphml"
            lista = E.tareas(red, ciudad, n=a.viajes)
            futuro = x.pivot_table(index=x.index, columns="franja", values="fut").add_prefix("fut_")
            largo_red = RR.tramos_de(ox.load_graphml(red))["largo"]
            rutas[ciudad] = {}
            for nombre, riesgo in mapas.items():
                if a.mapas and nombre not in a.mapas:
                    continue
                version = "" if nombre in ("mapa_de_calor_A", "mapa_de_calor_B", "oraculo",
                                           "evitar_avenidas", "evitar_comercios") else f"{FO.VERSION}_"
                guardado = RESULTADOS / f"rutas_{ciudad}_{version}{nombre}_{a.viajes}.json"
                if guardado.exists():   # ya calculado (se puede retomar si el proceso se corta)
                    rutas[ciudad][nombre] = json.loads(guardado.read_text())
                    continue
                ruta = RESULTADOS / f"riesgo_{ciudad}_{nombre}.csv"
                FO.mapa_de_riesgo(x, riesgo, largo_red).to_csv(ruta)
                v = E.simular(f"{ciudad}_{nombre}", red, ruta, lista)
                personas = publicos[[f"peatones_{f}" for f in FRANJAS]].rename(columns=lambda c: c.replace("peatones_", "pea_"))
                rutas[ciudad][nombre] = E.calificar(v, futuro, personas=personas)
                guardado.write_text(json.dumps(rutas[ciudad][nombre], default=float))
                r = rutas[ciudad][nombre]
                print(f"  {ciudad:12s} {nombre:16s} rutas: {r.get('cambio_pct', float('nan')):+.1f}% "
                      f"(IC95 {r.get('ic95', [np.nan, np.nan])[0]:+.1f} a {r.get('ic95', [np.nan, np.nan])[1]:+.1f}) "
                      f"| viajes con menor riesgo {r['viajes_con_menor_riesgo']}", flush=True)

    tabla = pd.DataFrame(filas)
    tabla.to_csv(RESULTADOS / f"{sello}_{FO.VERSION}_rapida.csv", index=False)
    pd.set_option("display.width", 200)
    print("\nCalificacion rapida: parte del nucleo del futuro en el 10% mas riesgoso de la red")
    print(tabla.set_index(["ciudad", "mapa"]).round(3).to_string())
    if a.rutas:
        (RESULTADOS / f"{sello}_rutas.json").write_text(json.dumps(rutas, indent=2, default=float))


if __name__ == "__main__":
    main()
