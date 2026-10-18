"""
SELLO de una version de la formula (investigacion/protocolo.md, seccion 2), antes de
abrir cualquier examen. Escribe investigacion/sello_<version>.json con:
    - las huellas SHA-256 de cada modelo (models/multiciudad/<version>/)
    - las huellas del codigo que prepara, aplica y califica (lo que corre el examen)
    - el commit de git en el que se sello
Despues: commit del sello + etiqueta git "formula-<version>-sellada", y el autor sube
el sello y el pre-registro a OSF (con fecha) antes de abrir la caja fuerte.

Ejecutar desde la carpeta del proyecto, con todo el codigo ya guardado en git:
    python investigacion/sellar_formula.py v2
    python investigacion/sellar_formula.py v2 tempe   (examen de reemplazo de Tempe:
        los MISMOS modelos; escribe investigacion/sello_v2_tempe.json)
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CODIGO = ["src/multiciudad/09_examen.py", "src/multiciudad/preparar.py", "src/multiciudad/categorias.py",
          "src/multiciudad/rasgos_delitos.py", "src/multiciudad/reparto.py", "src/multiciudad/formula.py",
          "src/multiciudad/calificacion.py", "src/multiciudad/evaluar_rutas.py", "src/multiciudad/ciudades.py",
          "src/rutas.py", "src/riesgo_pie.py", "src/comun.py", "src/flujo.py",
          "investigacion/caja_fuerte.py", "investigacion/protocolo.md", "investigacion/preregistro.md",
          "investigacion/reglas_de_datos.md"]
EXTRA = {"tempe": ["investigacion/preregistro_tempe.md", "investigacion/desviaciones_examen_v2.md"]}
NOTA = {"v2": "Modelos entrenados solo con las ciudades de aprender (Pittsburgh, Chapel Hill, Chicago, Seattle), "
              "los mismos evaluados en la practica v2 (investigacion/registro_practica.md)."}


def sha256(ruta):
    """Huella de los bytes tal cual (modelos: la misma que comprueba 09_examen.py)."""
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def sha256_texto(ruta):
    """Huella del codigo con saltos de linea normalizados (igual en Windows y Linux)."""
    return hashlib.sha256(Path(ruta).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main():
    version = sys.argv[1]
    examen = sys.argv[2] if len(sys.argv) > 2 else None
    nombre = f"sello_{version}" + (f"_{examen}" if examen else "")
    git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
    sucios = [r for r in git("status", "--porcelain", "--", "src", "investigacion").splitlines()
              if not r.endswith(f"{nombre}.json")]
    if sucios:
        sys.exit("Hay cambios sin guardar en git; primero commit:\n" + "\n".join(sucios))
    carpeta = Path("models/multiciudad") / version
    sello = {
        "version": version,
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": git("rev-parse", "HEAD"),
        "carpeta_modelos": carpeta.as_posix(),
        "huellas": {f.name: sha256(f) for f in sorted(carpeta.iterdir()) if f.suffix in (".txt", ".json")},
        "codigo": {c: sha256_texto(c) for c in CODIGO + EXTRA.get(examen, [])},
        "nota": NOTA.get(version, ""),
    }
    if examen:
        sello["examen"] = examen
    destino = Path(f"investigacion/{nombre}.json")
    destino.write_text(json.dumps(sello, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{destino}: {len(sello['huellas'])} modelos y {len(sello['codigo'])} archivos de codigo, commit {sello['commit'][:7]}")


if __name__ == "__main__":
    main()
