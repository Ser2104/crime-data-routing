"""
Convierte el borrador (main.tex) en una pagina HTML para leerlo en el navegador, sin
instalar LaTeX, y arma el .zip para subir a Overleaf. Ejecutar desde esta carpeta o la
del proyecto:
    python investigacion/articulo/vista_html.py
Salida: investigacion/articulo/borrador_articulo.html y investigacion/articulo_overleaf.zip
"""
import re
import zipfile
from pathlib import Path

import pypandoc

AQUI = Path(__file__).resolve().parent
ESTILO = """<style>
body{max-width:900px;margin:2em auto;padding:0 16px;font-family:Georgia,serif;line-height:1.55;color:#222;background:#fff}
table{border-collapse:collapse;margin:1em 0;font-size:0.85em;display:block;overflow-x:auto}
td,th{border-bottom:1px solid #ccc;padding:4px 8px}
caption{font-size:0.9em;text-align:left;margin-bottom:6px}
h1{font-size:1.6em}
</style>"""


def _argumento(t, i):
    """Contenido del argumento entre llaves que empieza en t[i] == '{', y donde termina."""
    nivel = 0
    for j in range(i, len(t)):
        nivel += {"{": 1, "}": -1}.get(t[j], 0)
        if nivel == 0:
            return t[i + 1:j], j + 1
    raise ValueError("llaves sin cerrar")


def _quitar(t, comando):
    """Quita cada \\comando[opcional]{argumento} del texto y devuelve los argumentos."""
    argumentos = []
    while (i := t.find(comando + "[")) >= 0 or (i := t.find(comando + "{")) >= 0:
        j = i + len(comando)
        if t[j] == "[":
            j = t.index("]", j) + 1
        arg, fin = _argumento(t, j)
        argumentos.append(arg)
        t = t[:i] + t[fin:]
    return t, argumentos


def _portada_elsevier(t):
    """pandoc no entiende la portada de elsarticle (frontmatter, notas del autor,
    afiliacion, palabras clave): se pasa a parrafos normales, solo para la vista.
    Los highlights (archivo aparte para la revista) se muestran debajo del resumen."""
    t, notas = _quitar(t, "\\fntext")
    t, afiliacion = _quitar(t, "\\affiliation")
    for comando in ("\\cortext", "\\corref", "\\fnref", "\\ead", "\\journal"):
        t, _ = _quitar(t, comando)
    lugar = ", ".join(re.findall(r"=\{([^}]*)\}", afiliacion[0])) if afiliacion else ""
    highlights = [x.lstrip("• ").strip().replace("%", "\\%").replace("~", "$\\sim$")   # % y ~ son especiales en LaTeX
                  for x in (AQUI / "highlights.txt").read_text(encoding="utf-8").splitlines()
                  if x.strip() and not x.startswith("#")]
    nota = ("\\noindent\\emph{" + lugar + ". Correspondence: sayc2104@gmail.com. " + " ".join(notas) + "}\n\n"
            "\\paragraph{Highlights}\n\\begin{itemize}\n" + "".join(f"  \\item {h}\n" for h in highlights) + "\\end{itemize}\n")
    t = t.replace("\\begin{frontmatter}", "").replace("\\end{frontmatter}", nota, 1)
    t = t.replace("\\begin{keyword}", "\\noindent\\textbf{Keywords:} ").replace("\\end{keyword}", "")
    return t.replace("\\sep", ";")


def vista():
    t = _portada_elsevier((AQUI / "main.tex").read_text(encoding="utf-8"))
    # pandoc no entiende \resizebox, \ajustar (adjustbox) ni el macro \todo: se simplifican solo para la vista
    t = re.sub(r"\\(?:resizebox\{\\textwidth\}\{!\}|ajustar)\{(\\input\{[^}]+\})\}", lambda m: m.group(1), t)
    t = t.replace(r"\newcommand{\todo}[1]{\textcolor{red}{[TODO: #1]}}", "")
    t = re.sub(r"\\todo\{([^}]*)\}", lambda m: r"\textbf{[TODO: " + m.group(1) + "]}", t)
    t = t.replace(".pdf}", ".png}")   # figuras: el navegador muestra el PNG
    for nombre in re.findall(r"\\input\{(tablas/[^}]+)\}", t):
        t = t.replace("\\input{" + nombre + "}", (AQUI / (nombre + ".tex")).read_text(encoding="utf-8"))
    tmp, css = AQUI / "_vista.tex", AQUI / "_estilo.html"
    tmp.write_text(t, encoding="utf-8")
    css.write_text(ESTILO, encoding="utf-8")
    try:
        pypandoc.convert_file(str(tmp), "html5", outputfile=str(AQUI / "borrador_articulo.html"),
                              extra_args=["--standalone", "--citeproc", f"--bibliography={AQUI / 'refs.bib'}",
                                          "--mathjax", "--number-sections", f"--include-in-header={css}"])
    finally:
        tmp.unlink(missing_ok=True)
        css.unlink(missing_ok=True)


def zip_overleaf():
    destino = AQUI.parent / "articulo_overleaf.zip"
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for p in [AQUI / "main.tex", AQUI / "refs.bib", AQUI / "highlights.txt", *sorted((AQUI / "tablas").glob("*.tex")),
                  *sorted((AQUI / "figuras").glob("*.pdf"))]:
            z.write(p, p.relative_to(AQUI).as_posix())
    return destino


if __name__ == "__main__":
    vista()
    print("HTML:", AQUI / "borrador_articulo.html")
    print("ZIP para Overleaf:", zip_overleaf())
