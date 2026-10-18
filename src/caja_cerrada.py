"""
Candado de las cajas fuertes para el codigo de DESARROLLO (investigacion/protocolo.md).

Todo programa que construye o prueba la formula importa este modulo al empezar:

    import caja_cerrada  # noqa: F401  (primero de todo)

Desde ese momento, si el programa intenta abrir, listar o copiar algo dentro de
data/holdout_* o data/examen_abierto/, se detiene con un error. Usa los "audit
hooks" de Python, que no se pueden quitar una vez puestos.

Limite: protege lo que Python abre directamente (open, pandas, listar carpetas).
La proteccion fuerte es el cifrado: sin la frase del autor, los archivos de examen
no se pueden leer de ninguna forma.
"""
import os
import sys

PROHIBIDAS = ("/data/holdout_", "/data/examen_abierto")
EVENTOS = {"open", "os.listdir", "os.scandir", "shutil.copyfile", "shutil.copytree", "os.rename"}


def _prohibida(ruta):
    try:
        texto = os.path.abspath(os.fsdecode(ruta)).replace("\\", "/").lower()
    except (TypeError, ValueError):
        return False   # descriptores numericos y otros: no son rutas
    return any(p in texto for p in PROHIBIDAS)


def _candado(evento, args):
    if evento in EVENTOS and args and _prohibida(args[0]):
        raise PermissionError(f"Candado de la caja fuerte: el codigo de desarrollo no puede tocar {args[0]}")


if not getattr(sys, "_caja_cerrada", False):
    sys.addaudithook(_candado)
    sys._caja_cerrada = True
