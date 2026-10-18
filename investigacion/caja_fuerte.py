"""
CAJA FUERTE de los datos de examen (investigacion/protocolo.md).

Los delitos de las ciudades de examen se descargan como un flujo de bytes:

    internet -> SHA-256 del original -> cifrado AES-256-GCM -> archivo .enc

NUNCA se escribe una copia legible en disco, y el programa no lee, cuenta ni
muestra nada del contenido (ni filas, ni columnas, ni tamano). La clave sale de
una frase-contrasena que escribe el investigador en su terminal (Scrypt con un
"salt" aleatorio); la frase no se guarda en ningun lado. Al terminar se calcula
la huella del archivo cifrado, y todo (fuente, fecha, huellas, salt, iv) se anota
en investigacion/caja_fuerte/manifiesto.json, que va a git.

Comandos (desde la carpeta del proyecto):
    python investigacion/caja_fuerte.py probar [grupo|todos]
        Comprueba que cada enlace responde, SIN leer el contenido (cierra la conexion).
    python investigacion/caja_fuerte.py sellar [grupo|todos]
        Descarga, cifra y verifica (pide la frase dos veces).
    python investigacion/caja_fuerte.py verificar [grupo|todos]
        Descifra en memoria, comprueba el sello y la huella del original, y descarta
        los datos sin mostrarlos.
    python investigacion/caja_fuerte.py formato [grupo|todos]
        Revision A CIEGAS: comprueba el sello completo y despues compara SOLO la
        primera linea (nombres de columnas) con los nombres que publica el portal
        oficial. Responde solo OK o REVISAR por ciudad: no cuenta filas ni muestra
        nada. Sirve para saber que el servidor entrego los datos y no un archivo de
        error, mientras todavia se puede volver a sellar.
    python investigacion/caja_fuerte.py abrir <grupo> --motivo "texto"
        SOLO el dia del examen: comprueba el sello completo y despues escribe los
        datos legibles en data/examen_abierto/<grupo>/. Queda anotado en aperturas.json.
Grupos: holdout_main, holdout_reserve, holdout_zona, holdout_tempe2.

DESCARGA DIRECTA de ArcGIS (tipo "arcgis_directo", agregado el 2026-10-08): el enlace
de ArcGIS Hub entrega una copia pregenerada que puede estar desactualizada (paso con
Tempe: la copia terminaba en 2024-06 y el servicio llegaba a 2026-10). Este tipo
consulta el servicio oficial (FeatureServer) por paginas y arma el CSV en memoria, sin
copia legible en disco y sin mostrar nada. Antes de sellar comprueba, respondiendo solo
OK o REVISAR (nunca fechas ni conteos):
    - cobertura: la fecha minima y maxima cubren el periodo del estudio (COBERTURA)
    - integridad: se bajaron todas las filas que el servidor dice tener
Si alguna falla, no se sella.
"""
import argparse
import csv
import getpass
import io
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

CARPETA_DATOS = Path("data")
REGISTRO = Path("investigacion/caja_fuerte")
MANIFIESTO = REGISTRO / "manifiesto.json"
APERTURAS = REGISTRO / "aperturas.json"
FORMATO = REGISTRO / "formato.json"
INICIO_MAX = 1 << 16      # formato: solo se retienen los primeros 64 KB descifrados (la cabecera)
COINCIDENCIA_MIN = 0.8    # formato: parte de las columnas que debe coincidir con el portal
COBERTURA = ("2024-01-01", "2026-08-31")   # periodo del estudio (reglas_de_datos.md, seccion 1)
EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)
MAGICO = b"SAFEROUTES-CAJA-v1\n"
SCRYPT = {"n": 2 ** 17, "r": 8, "p": 1}
TROZO = 1 << 20          # se lee y cifra de a 1 MB
UA = "safe-routes-pgh/0.1 (proyecto personal; datos de examen cifrados)"
# Solo se sella si el servidor anuncia un archivo de datos: una pagina de error o un
# aviso de "procesando" (HTML o JSON) se rechaza sin leerlo
TIPOS_DATOS = ("text/csv", "application/csv", "application/octet-stream", "application/vnd.ms-excel",
               "text/plain", "binary/octet-stream")

SOCRATA = "https://{dominio}/api/views/{ident}/rows.csv?accessType=DOWNLOAD"
# Fuentes oficiales. Se descarga lo publicado a la fecha (sin filtrar en el servidor,
# salvo Filadelfia, desde 2023, porque su tabla empieza en 2006). El periodo que se
# usa en el examen lo fija investigacion/reglas_de_datos.md.
FUENTES = {
    "holdout_main": [
        {"ciudad": "Filadelfia", "archivo": "filadelfia.csv.enc", "dataset": "OpenDataPhilly incidents_part1_part2",
         "url": "https://phl.carto.com/api/v2/sql",
         "params": {"q": "SELECT * FROM incidents_part1_part2 WHERE dispatch_date >= '2023-01-01'", "format": "csv"},
         "periodo": "desde 2023-01-01 hasta la fecha de descarga"},
        {"ciudad": "Baton Rouge", "archivo": "baton_rouge.csv.enc", "dataset": "data.brla.gov pbin-pcm7",
         "url": SOCRATA.format(dominio="data.brla.gov", ident="pbin-pcm7"), "params": {},
         "periodo": "todo lo publicado a la fecha de descarga"},
        {"ciudad": "Tempe", "archivo": "tempe.csv.enc", "dataset": "ArcGIS 1563be5b343b4f78b1163e97a9a503ad (General Offenses)",
         "url": "https://hub.arcgis.com/api/v3/datasets/1563be5b343b4f78b1163e97a9a503ad_0/downloads/data",
         "params": {"format": "csv", "spatialRefId": "4326", "where": "1=1"},
         "periodo": "todo lo publicado a la fecha de descarga"},
    ],
    "holdout_reserve": [
        {"ciudad": "Dallas", "archivo": "dallas.csv.enc", "dataset": "dallasopendata.com qv6i-rri7",
         "url": SOCRATA.format(dominio="www.dallasopendata.com", ident="qv6i-rri7"), "params": {},
         "periodo": "todo lo publicado a la fecha de descarga"},
        {"ciudad": "San Francisco", "archivo": "san_francisco.csv.enc", "dataset": "data.sfgov.org wg3w-h783",
         "url": SOCRATA.format(dominio="data.sfgov.org", ident="wg3w-h783"), "params": {},
         "periodo": "todo lo publicado a la fecha de descarga"},
        {"ciudad": "Boston", "archivo": "boston.csv.enc", "dataset": "data.boston.gov Crime Incident Reports - 2023 to Present",
         "url": "https://data.boston.gov/dataset/6220d948-eae2-4e4b-8723-2dc8e67722a3/resource/"
                "b973d8cb-eeb2-4e7e-99da-c92938efc9c0/download/tmp2lnsoz4a.csv", "params": {},
         "periodo": "2023 hasta la fecha de descarga"},
        {"ciudad": "Colorado Springs", "archivo": "colorado_springs.csv.enc", "dataset": "policedata.coloradosprings.gov bc88-hemr",
         "url": SOCRATA.format(dominio="policedata.coloradosprings.gov", ident="bc88-hemr"), "params": {},
         "periodo": "todo lo publicado a la fecha de descarga"},
    ],
    # Reemplazo de la descarga de Tempe del examen principal (copia de Hub desactualizada;
    # investigacion/desviaciones_examen_v2.md). Mismo conjunto de datos, descarga directa.
    "holdout_tempe2": [
        {"ciudad": "Tempe", "archivo": "tempe.csv.enc", "tipo": "arcgis_directo",
         "dataset": "Tempe General Offenses (Open Data), FeatureServer capa 0, descarga directa",
         "url": "https://services.arcgis.com/lQySeXwbBg53XWDi/arcgis/rest/services/General_Offenses_(Open_Data)/FeatureServer/0",
         "params": {"f": "json"}, "orden": "OBJECTID", "campo_fecha": "OccurrenceDatetime",
         "periodo": "todo lo publicado a la fecha de descarga (servicio directo, por paginas)"},
    ],
    "holdout_zona": [
        {"ciudad": "Austin", "archivo": "austin.csv.enc", "dataset": "datahub.austintexas.gov fdj4-gpfu",
         "url": SOCRATA.format(dominio="datahub.austintexas.gov", ident="fdj4-gpfu"), "params": {},
         "periodo": "todo lo publicado a la fecha de descarga"},
        {"ciudad": "Cambridge", "archivo": "cambridge.csv.enc", "dataset": "data.cambridgema.gov xuad-73uj",
         "url": SOCRATA.format(dominio="data.cambridgema.gov", ident="xuad-73uj"), "params": {},
         "periodo": "todo lo publicado a la fecha de descarga"},
        {"ciudad": "Somerville", "archivo": "somerville.csv.enc", "dataset": "data.somervillema.gov aghs-hqvg",
         "url": SOCRATA.format(dominio="data.somervillema.gov", ident="aghs-hqvg"), "params": {},
         "periodo": "todo lo publicado a la fecha de descarga"},
        {"ciudad": "Los Angeles", "archivo": "los_angeles.csv.enc", "dataset": "data.lacity.org k7nn-b2ep (NIBRS)",
         "url": SOCRATA.format(dominio="data.lacity.org", ident="k7nn-b2ep"), "params": {},
         "periodo": "todo lo publicado a la fecha de descarga"},
    ],
}


def clave(frase, salt, kdf=SCRYPT):
    return Scrypt(salt=salt, length=32, **kdf).derive(frase.encode("utf-8"))


def cabecera(fuente, grupo, salt, iv):
    """Datos publicos del archivo cifrado (van en claro al inicio y quedan autenticados)."""
    datos = {"ciudad": fuente["ciudad"], "grupo": grupo, "dataset": fuente["dataset"],
             "kdf": {"algoritmo": "scrypt", **SCRYPT, "salt": salt.hex()}, "cifrado": "AES-256-GCM", "iv": iv.hex()}
    return json.dumps(datos, ensure_ascii=False, sort_keys=True).encode("utf-8")


def leer_cabecera(f):
    if f.read(len(MAGICO)) != MAGICO:
        raise ValueError("no es un archivo de la caja fuerte")
    largo = int.from_bytes(f.read(4), "big")
    crudo = f.read(largo)
    return json.loads(crudo), MAGICO + largo.to_bytes(4, "big") + crudo


def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(TROZO), b""):
            h.update(trozo)
    return h.hexdigest()


def commit_actual():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return "desconocido"


def _flujo_http(fuente, info):
    """Bytes del archivo tal como lo entrega el servidor (fuentes de un solo archivo)."""
    with requests.get(fuente["url"], params=fuente["params"], headers={"User-Agent": UA},
                      stream=True, timeout=(30, 900)) as r:
        r.raise_for_status()
        tipo = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if tipo not in TIPOS_DATOS:
            raise RuntimeError(f"el servidor no entrego un archivo de datos (tipo '{tipo}'); no se sella")
        info["etag"] = r.headers.get("ETag")
        yield from r.iter_content(chunk_size=TROZO)   # nada se muestra ni se cuenta


def _flujo_arcgis(fuente, info):
    """Bytes de un CSV armado en memoria con la capa de ArcGIS, por paginas. Los campos de
    fecha se escriben como los exporta ArcGIS ("AAAA/MM/DD hh:mm:ss+00"). 'info' guarda,
    solo para los chequeos de cobertura e integridad, la fecha minima y maxima del campo
    de fecha y las filas esperadas y bajadas; nunca se imprimen ni van al manifiesto."""
    s = requests.Session()
    s.headers["User-Agent"] = UA
    pedir = lambda url, params: _json_ok(s.get(url, params=params, timeout=(30, 300)))
    capa = pedir(fuente["url"], {"f": "json"})
    campos = [c["name"] for c in capa["fields"]]
    fechas = {c["name"] for c in capa["fields"] if c["type"] == "esriFieldTypeDate"}
    pagina = int(capa.get("maxRecordCount") or 1000)
    info.update(esperadas=pedir(fuente["url"] + "/query", {"where": "1=1", "returnCountOnly": "true", "f": "json"})["count"],
                filas=0, minimo=None, maximo=None)
    texto = io.StringIO()
    csv.writer(texto, lineterminator="\n").writerow(campos)
    yield texto.getvalue().encode("utf-8")
    desde = 0
    while True:
        datos = pedir(fuente["url"] + "/query", {"where": "1=1", "outFields": "*", "orderByFields": fuente["orden"],
                                                 "resultOffset": desde, "resultRecordCount": pagina,
                                                 "returnGeometry": "false", "f": "json"})
        filas = datos.get("features", [])
        texto = io.StringIO()
        escritor = csv.writer(texto, lineterminator="\n")
        for f in filas:
            a = f["attributes"]
            escritor.writerow(["" if a.get(c) is None else
                               (EPOCA + timedelta(milliseconds=a[c])).strftime("%Y/%m/%d %H:%M:%S+00") if c in fechas
                               else a[c] for c in campos])
            v = a.get(fuente["campo_fecha"])
            if v is not None:
                info["minimo"] = v if info["minimo"] is None else min(info["minimo"], v)
                info["maximo"] = v if info["maximo"] is None else max(info["maximo"], v)
        info["filas"] += len(filas)
        yield texto.getvalue().encode("utf-8")
        if not filas or not (datos.get("exceededTransferLimit") or len(filas) >= pagina):
            break
        desde += len(filas)


def _json_ok(r):
    r.raise_for_status()
    datos = r.json()
    if "error" in datos:
        raise RuntimeError("el servicio respondio con un error; no se sella")
    return datos


def _chequeo_arcgis(info):
    """Cobertura e integridad de una descarga directa. Solo dice si pasa o no."""
    ms = lambda dia: (datetime.fromisoformat(dia).replace(tzinfo=timezone.utc) - EPOCA) // timedelta(milliseconds=1)
    cubre = (info["minimo"] is not None and info["minimo"] <= ms(COBERTURA[0])
             and info["maximo"] >= ms(COBERTURA[1]) + 86_399_000)
    completa = info["filas"] >= info["esperadas"]
    if not (cubre and completa):
        raise RuntimeError(f"cobertura del periodo {'OK' if cubre else 'REVISAR'}, "
                           f"descarga completa {'OK' if completa else 'REVISAR'}; no se sella")
    return {"cobertura_periodo": "OK", "descarga_completa": "OK"}


def sellar_uno(fuente, grupo, frase):
    destino = CARPETA_DATOS / grupo / fuente["archivo"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    salt, iv = os.urandom(16), os.urandom(12)
    cab = cabecera(fuente, grupo, salt, iv)
    aad = MAGICO + len(cab).to_bytes(4, "big") + cab
    cifrador = Cipher(algorithms.AES(clave(frase, salt)), modes.GCM(iv)).encryptor()
    cifrador.authenticate_additional_data(aad)
    h_original = hashlib.sha256()
    inicio = datetime.now(timezone.utc)
    info = {}
    directo = fuente.get("tipo") == "arcgis_directo"
    trozos = _flujo_arcgis(fuente, info) if directo else _flujo_http(fuente, info)
    parcial = destino.with_suffix(".parcial")
    try:
        with open(parcial, "wb") as f:
            f.write(aad)
            for trozo in trozos:   # nada se muestra ni se cuenta en pantalla
                h_original.update(trozo)
                f.write(cifrador.update(trozo))
            f.write(cifrador.finalize())
            f.write(cifrador.tag)
        chequeos = _chequeo_arcgis(info) if directo else {}
    except BaseException:
        parcial.unlink(missing_ok=True)   # si se corta o no pasa los chequeos, no quedan restos
        raise
    parcial.replace(destino)
    return {
        "ciudad": fuente["ciudad"], "grupo": grupo, "dataset": fuente["dataset"],
        "url": fuente["url"], "params": fuente["params"], "periodo_solicitado": fuente["periodo"],
        **({"tipo_descarga": "arcgis_directo", "orden": fuente["orden"], **chequeos} if directo else {}),
        "etag_servidor": info.get("etag"), "descarga_utc": inicio.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "archivo": str(destino).replace("\\", "/"),
        "sha256_original": h_original.hexdigest(), "sha256_cifrado": sha256_archivo(destino),
        "cifrado": "AES-256-GCM", "kdf": {"algoritmo": "scrypt", **SCRYPT, "salt": salt.hex()}, "iv": iv.hex(),
        "programa_commit": commit_actual(), "python": platform.python_version(),
    }


def descifrar(ruta, frase, salida=None, inicio=None):
    """Descifra de a trozos. Devuelve la huella del original. Si 'salida' es None,
    los datos se descartan. 'inicio' (un bytearray) recibe solo los primeros
    INICIO_MAX bytes descifrados, en memoria. Lanza InvalidTag si el archivo fue
    alterado o la frase es incorrecta (y en ese caso no queda nada escrito; quien
    use 'inicio' debe descartarlo)."""
    total = ruta.stat().st_size
    with open(ruta, "rb") as f:
        cab, aad = leer_cabecera(f)
        cuerpo = total - len(aad) - 16
        f.seek(total - 16)
        tag = f.read(16)
        f.seek(len(aad))
        kdf = {k: cab["kdf"][k] for k in ("n", "r", "p")}
        descifrador = Cipher(algorithms.AES(clave(frase, bytes.fromhex(cab["kdf"]["salt"]), kdf)),
                             modes.GCM(bytes.fromhex(cab["iv"]))).decryptor()
        descifrador.authenticate_additional_data(aad)
        h = hashlib.sha256()
        restante = cuerpo
        destino = open(salida, "wb") if salida else None
        try:
            while restante:
                trozo = descifrador.update(f.read(min(TROZO, restante)))
                restante -= min(TROZO, restante)
                h.update(trozo)
                if inicio is not None and len(inicio) < INICIO_MAX:
                    inicio.extend(trozo[:INICIO_MAX - len(inicio)])
                if destino:
                    destino.write(trozo)
            descifrador.finalize_with_tag(tag)
        except InvalidTag:
            if destino:
                destino.close()
                Path(salida).unlink()
            raise
        finally:
            if destino and not destino.closed:
                destino.close()
    return h.hexdigest()


def normalizar(nombre):
    return re.sub(r"[^a-z0-9]", "", nombre.lower())


def columnas_publicadas(url):
    """Nombres de columnas que publica el portal oficial para esta fuente (solo la
    descripcion del dataset, nunca sus filas), normalizados."""
    s = requests.Session()
    s.headers["User-Agent"] = UA
    m = re.match(r"https://([^/]+)/api/views/([^/]+)/rows\.csv", url)
    if m:   # Socrata: el CSV usa el nombre visible de cada columna
        meta = s.get(f"https://{m.group(1)}/api/views/{m.group(2)}.json", timeout=60).json()
        nombres = [c.get("name", "") for c in meta["columns"]] + [c.get("fieldName", "") for c in meta["columns"]]
    elif "phl.carto.com" in url:   # Carto: solo la estructura de la tabla (LIMIT 0)
        meta = s.get(url, params={"q": "SELECT * FROM incidents_part1_part2 LIMIT 0"}, timeout=60).json()
        nombres = list(meta["fields"])
    elif "/FeatureServer/" in url:   # servicio directo de ArcGIS: campos de la capa (nombre y alias)
        capa = s.get(url, params={"f": "json"}, timeout=60).json()
        nombres = [f["name"] for f in capa["fields"]] + [f.get("alias", "") for f in capa["fields"]]
    elif "hub.arcgis.com" in url:   # ArcGIS Hub: campos de la capa (nombre y alias)
        item = re.search(r"datasets/([0-9a-f]{32})_(\d+)", url)
        servicio = s.get(f"https://www.arcgis.com/sharing/rest/content/items/{item.group(1)}",
                         params={"f": "json"}, timeout=60).json()["url"].rstrip("/")
        capa = s.get(f"{servicio}/{item.group(2)}", params={"f": "json"}, timeout=60).json()
        nombres = [f["name"] for f in capa["fields"]] + [f.get("alias", "") for f in capa["fields"]]
    elif "data.boston.gov" in url:   # CKAN: campos del recurso (limit=0, sin filas)
        recurso = re.search(r"resource/([0-9a-f-]{36})", url).group(1)
        meta = s.get("https://data.boston.gov/api/3/action/datastore_search",
                     params={"resource_id": recurso, "limit": 0}, timeout=60).json()
        nombres = [f["id"] for f in meta["result"]["fields"]]
    else:
        raise ValueError("portal sin regla de columnas")
    return {normalizar(n) for n in nombres if n}


def motivo_formato(inicio, esperadas):
    """None si la cabecera coincide con las columnas del portal y hay datos despues;
    si no, el motivo (nunca muestra el contenido)."""
    texto = bytes(inicio).decode("utf-8-sig", errors="replace")
    primera, _, resto = texto.partition("\n")
    if primera.lstrip().startswith(("<", "{", "[")):
        return "no parece un CSV (parece una pagina o un mensaje del servidor)"
    try:
        cabecera = {normalizar(c) for c in next(csv.reader([primera])) if c.strip()}
    except (csv.Error, StopIteration):
        return "no parece un CSV"
    if len(cabecera) < 5:
        return "la cabecera tiene muy pocas columnas"
    if len(cabecera & esperadas) / len(cabecera) < COINCIDENCIA_MIN:
        return "las columnas no coinciden con las del portal"
    if not resto.strip():
        return "no hay datos despues de la cabecera"
    return None


def cargar_manifiesto():
    return json.loads(MANIFIESTO.read_text(encoding="utf-8")) if MANIFIESTO.exists() else []


def grupos_de(nombre):
    return list(FUENTES) if nombre == "todos" else [nombre]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["probar", "sellar", "verificar", "formato", "abrir"])
    ap.add_argument("grupo", choices=list(FUENTES) + ["todos"])
    ap.add_argument("--motivo", default="")
    a = ap.parse_args()
    REGISTRO.mkdir(parents=True, exist_ok=True)

    if a.accion == "probar":
        for g in grupos_de(a.grupo):
            for fu in FUENTES[g]:
                try:
                    with requests.get(fu["url"], params=fu["params"], headers={"User-Agent": UA},
                                      stream=True, timeout=(30, 120)) as r:   # se cierra sin leer el contenido
                        print(f"{g:16s} {fu['ciudad']:18s} HTTP {r.status_code} {r.headers.get('Content-Type', '')[:30]}")
                except requests.RequestException as e:
                    print(f"{g:16s} {fu['ciudad']:18s} ERROR {type(e).__name__}")
        return

    if a.accion == "sellar":
        frase = getpass.getpass("Frase-contrasena (no se muestra): ")
        if frase != getpass.getpass("Repitela: ") or len(frase) < 20:
            sys.exit("Las frases no coinciden o tienen menos de 20 caracteres. No se hizo nada.")
        manifiesto = cargar_manifiesto()
        for g in grupos_de(a.grupo):
            for fu in FUENTES[g]:
                if any(m["archivo"].endswith(f"{g}/{fu['archivo']}") for m in manifiesto):
                    print(f"{fu['ciudad']}: ya estaba sellada, no se toca.")
                    continue
                print(f"{fu['ciudad']}: descargando y cifrando...", flush=True)
                try:
                    entrada = sellar_uno(fu, g, frase)
                except (requests.RequestException, RuntimeError) as e:
                    print(f"   NO se sello ({type(e).__name__}: {e}). Se puede volver a intentar.")
                    continue
                ok = descifrar(Path(entrada["archivo"]), frase) == entrada["sha256_original"]
                entrada["verificacion_inmediata"] = "ok" if ok else "FALLO"
                manifiesto.append(entrada)
                MANIFIESTO.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"   sellada. huella original {entrada['sha256_original'][:16]}... "
                      f"cifrada {entrada['sha256_cifrado'][:16]}... verificacion: {entrada['verificacion_inmediata']}")
        print(f"\nManifiesto: {MANIFIESTO}")
        return

    frase = getpass.getpass("Frase-contrasena (no se muestra): ")
    manifiesto = [m for m in cargar_manifiesto() if a.grupo == "todos" or m["grupo"] == a.grupo]
    if a.accion == "verificar":
        for m in manifiesto:
            ruta = Path(m["archivo"])
            try:
                bien = (sha256_archivo(ruta) == m["sha256_cifrado"]
                        and descifrar(ruta, frase) == m["sha256_original"])
                print(f"{m['ciudad']:18s} {'OK' if bien else 'NO COINCIDE LA HUELLA'}")
            except InvalidTag:
                print(f"{m['ciudad']:18s} SELLO ROTO o frase incorrecta")
        return

    if a.accion == "formato":
        resultados = json.loads(FORMATO.read_text(encoding="utf-8")) if FORMATO.exists() else []
        for m in manifiesto:
            ruta, inicio = Path(m["archivo"]), bytearray()
            try:
                esperadas = columnas_publicadas(m["url"])
                if sha256_archivo(ruta) != m["sha256_cifrado"] or descifrar(ruta, frase, inicio=inicio) != m["sha256_original"]:
                    motivo = "la huella no coincide"
                else:
                    motivo = motivo_formato(inicio, esperadas)
            except InvalidTag:
                motivo = "sello roto o frase incorrecta"
            except (requests.RequestException, ValueError, KeyError) as e:
                motivo = f"no se pudo leer la descripcion del portal ({type(e).__name__})"
            del inicio
            print(f"{m['ciudad']:18s} {'OK' if motivo is None else 'REVISAR: ' + motivo}")
            resultados.append({"ciudad": m["ciudad"], "grupo": m["grupo"], "sha256_original": m["sha256_original"],
                               "resultado": "OK" if motivo is None else "REVISAR", "motivo": motivo,
                               "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "programa_commit": commit_actual()})
        FORMATO.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nResultado anotado en {FORMATO}")
        return

    # abrir: solo el dia del examen, un grupo a la vez, con motivo
    if a.grupo == "todos" or not a.motivo:
        sys.exit("Para abrir hay que indicar UN grupo y --motivo. Recuerda: cada grupo se abre una sola vez.")
    aperturas = json.loads(APERTURAS.read_text(encoding="utf-8")) if APERTURAS.exists() else []
    if any(x["grupo"] == a.grupo for x in aperturas):
        sys.exit(f"El grupo {a.grupo} ya se abrio antes (ver {APERTURAS}). No se vuelve a abrir.")
    salida = CARPETA_DATOS / "examen_abierto" / a.grupo
    salida.mkdir(parents=True, exist_ok=True)
    for m in manifiesto:
        ruta = Path(m["archivo"])
        if sha256_archivo(ruta) != m["sha256_cifrado"] or descifrar(ruta, frase) != m["sha256_original"]:
            sys.exit(f"{m['ciudad']}: el sello no coincide. No se abre nada.")
    for m in manifiesto:   # sellos comprobados: recien ahora se escriben los datos legibles
        descifrar(Path(m["archivo"]), frase, salida / Path(m["archivo"]).name.replace(".enc", ""))
    aperturas.append({"grupo": a.grupo, "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "motivo": a.motivo, "programa_commit": commit_actual()})
    APERTURAS.write_text(json.dumps(aperturas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Grupo {a.grupo} abierto en {salida}. Apertura anotada en {APERTURAS}.")


if __name__ == "__main__":
    main()
