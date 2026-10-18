"""
Revision mecanica del borrador antes de compilarlo en Overleaf (no hay LaTeX en esta
computadora). Ejecutar desde la carpeta del proyecto:
    python investigacion/articulo/revisar_latex.py
Comprueba:
  - que cada cita tenga su entrada en refs.bib (y que no sobren entradas);
  - que cada \\ref apunte a una \\label que existe;
  - caracteres no ASCII (pdfLaTeX con utf8 acepta acentos y guiones, pero no todo);
  - el largo del resumen (TR-C: maximo 250 palabras) y de los highlights (85 caracteres).
"""
import re
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def main():
    t = (AQUI / "main.tex").read_text(encoding="utf-8")
    citas = {k.strip() for g in re.findall(r"\\cite[pt]?\{([^}]+)\}", t) for k in g.split(",")}
    bib = set(re.findall(r"@\w+\{([^,]+),", (AQUI / "refs.bib").read_text(encoding="utf-8")))
    print("citas sin entrada en refs.bib:", sorted(citas - bib) or "ninguna")
    print("entradas de refs.bib sin citar:", sorted(bib - citas) or "ninguna")
    etiquetas = set(re.findall(r"\\label\{([^}]+)\}", t))
    refs = set(re.findall(r"\\ref\{([^}]+)\}", t))
    print("\\ref a etiquetas inexistentes:", sorted(refs - etiquetas) or "ninguna")
    print("etiquetas nunca referidas:", sorted(etiquetas - refs) or "ninguna")
    for p in [AQUI / "main.tex", AQUI / "refs.bib", *sorted((AQUI / "tablas").glob("*.tex"))]:
        raros = sorted({c for c in p.read_text(encoding="utf-8") if ord(c) > 127})
        if raros:
            print(f"{p.name}: caracteres no ASCII {raros}")
    for nombre in re.findall(r"\\input\{([^}]+)\}", t):
        if not (AQUI / f"{nombre}.tex").exists():
            print("FALTA tabla:", nombre)
    for nombre in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", t):
        if not (AQUI / nombre).exists():
            print("FALTA figura:", nombre)
    resumen = t[t.index(r"\begin{abstract}") + len(r"\begin{abstract}"):t.index(r"\end{abstract}")]
    print("palabras del resumen:", len(resumen.split()), "(maximo 250)")
    for h in (AQUI / "highlights.txt").read_text(encoding="utf-8").splitlines():
        if h.startswith("•"):
            print(f"highlight de {len(h[2:])} caracteres (maximo 85)")
    print("TODO pendientes:", len(re.findall(r"\\todo\{", t)))
    # Un % sin barra convierte el resto de la linea en comentario: el texto desaparece sin error
    for archivo in [AQUI / "main.tex", *sorted((AQUI / "tablas").glob("*.tex"))]:
        for i, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            if linea.lstrip().startswith("%"):
                continue
            for m in re.finditer(r"(?<!\\)%", linea):
                print(f"% SIN ESCAPAR en {archivo.name}:{i}: ...{linea[max(0, m.start() - 40):m.start() + 5]}")


if __name__ == "__main__":
    main()
