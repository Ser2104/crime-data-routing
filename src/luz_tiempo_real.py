"""
Iluminacion en TIEMPO REAL: lo que puede haber cambiado desde la ultima
actualizacion de la capa base de iluminacion (src/capa_luz.py).

1. Faroles reportados apagados (reportes abiertos de los ultimos DIAS_REPORTE dias):
     Pittsburgh: 311 (WPRDC), al dia
     Nueva York: 311 (NYC Open Data), al dia
2. Cortes de luz de la empresa electrica (sin electricidad, los faroles tampoco
   prenden), cada 15-30 minutos, de los mapas publicos de cortes (plataforma Kubra):
     State College: FirstEnergy / West Penn Power
     Nueva York: Con Edison
   (Duquesne Light, en Pittsburgh, bloquea el acceso automatico a su mapa; SEAL,
   en Arequipa, no publica sus cortes en un formato que se pueda leer.)
3. Apagones vistos desde el satelite (cualquier ciudad, cada noche): zonas mucho
   mas oscuras que lo normal (src/luz_satelite.py).

Cada evento es un punto con un radio de efecto: (tipo, lon, lat, radio_m, detalle).
"""
import math
from datetime import date, datetime, timedelta

import numpy as np
import requests

import luz_satelite as LS

DIAS_REPORTE = 30          # un reporte abierto de hace mas dias probablemente ya se atendio
RADIO_FAROL = 40           # m: un farol apagado oscurece su tramo de calle
RADIO_CORTE_MIN, RADIO_CORTE_MAX = 150, 800   # m: segun cuantos clientes estan sin luz
_S = requests.Session()
_S.headers["User-Agent"] = "safe-routes-pgh/0.1 (proyecto personal)"

# Fuentes por ciudad
FUENTES = {
    "pittsburgh": {"reportes": "wprdc_311"},
    "state_college": {"cortes": ("kubra", "6c715f0e-bbec-465f-98cc-0b81623744be",
                                 "8587e451-e258-4692-b5e8-28010506d51a")},
    "nueva_york": {"reportes": "nyc_311",
                   "cortes": ("kubra_clasico", "https://outagemap.coned.com/resources/data/external/"
                                               "interval_generation_data")},
    "arequipa": {},
}


# ---------------------------------------------------------------------------
# 1. Faroles reportados apagados
def _wprdc_311(caja, desde):
    w = "https://data.wprdc.org/api/3/action"
    p = _S.get(f"{w}/package_search", params={"q": "Pittsburgh 311 Data", "rows": 1}, timeout=60).json()
    rid = next(r["id"] for r in p["result"]["results"][0]["resources"] if r.get("datastore_active"))
    # Los mas recientes primero; se para al llegar a reportes anteriores a 'desde'
    filas, pagina = [], 1000
    while True:
        res = _S.get(f"{w}/datastore_search", timeout=120, params={
            "resource_id": rid, "filters": '{"subject_code": "STREETLIGHT"}', "sort": "created_date_et desc",
            "fields": "created_date_et,closed_date_et,latitude,longitude", "limit": pagina,
            "offset": len(filas)}).json()["result"]["records"]
        filas += res
        if len(res) < pagina or res[-1]["created_date_et"][:10] < desde.isoformat():
            break
    return [("farol_apagado", float(f["longitude"]), float(f["latitude"]), RADIO_FAROL,
             f"311 del {f['created_date_et'][:10]}") for f in filas
            if f["created_date_et"][:10] >= desde.isoformat() and not f["closed_date_et"]
            and f["latitude"] and f["longitude"]]


def _nyc_311(caja, desde):
    oeste, sur, este, norte = caja
    filas = _S.get("https://data.cityofnewyork.us/resource/erm2-nwe9.json", timeout=120, params={
        "$where": (f"complaint_type='Street Light Condition' AND status != 'Closed' AND created_date > "
                   f"'{desde.isoformat()}' AND latitude BETWEEN {sur} AND {norte} AND longitude BETWEEN {oeste} AND {este}"),
        "$select": "created_date,descriptor,latitude,longitude", "$limit": 50000}).json()
    return [("farol_apagado", float(f["longitude"]), float(f["latitude"]), RADIO_FAROL,
             f"311 del {f['created_date'][:10]}: {f.get('descriptor', '')}") for f in filas
            if f.get("latitude") and f.get("longitude")]


# ---------------------------------------------------------------------------
# 2. Cortes de luz (mapas Kubra): mosaicos por quadkey, bajando de nivel en los grupos
def _quadkey(x, y, z):
    return "".join(str((1 if x & (1 << (i - 1)) else 0) + (2 if y & (1 << (i - 1)) else 0)) for i in range(z, 0, -1))


def _mosaicos(caja, z):
    """Mosaicos (x, y) de nivel z que cubren la caja."""
    oeste, sur, este, norte = caja
    def xy(lon, lat):
        x = int((lon + 180) / 360 * 2 ** z)
        y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2 ** z)
        return x, y
    (x0, y0), (x1, y1) = xy(oeste, norte), xy(este, sur)
    return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def _decodificar(polilinea):
    """Primer punto (lat, lon) de una polilinea codificada de Google."""
    valores, i = [], 0
    while i < len(polilinea) and len(valores) < 2:
        resultado, corrimiento = 0, 0
        while True:
            b = ord(polilinea[i]) - 63
            i += 1
            resultado |= (b & 0x1F) << corrimiento
            corrimiento += 5
            if b < 0x20:
                break
        valores.append(~(resultado >> 1) if resultado & 1 else resultado >> 1)
    return valores[0] / 1e5, valores[1] / 1e5


def _kubra(caja, url_mosaico, z=10, z_max=16):
    """Cortes de un mapa Kubra dentro de la caja. url_mosaico(quadkey) -> URL del mosaico."""
    eventos, pendientes = [], [(x, y, z) for x, y in _mosaicos(caja, z)]
    oeste, sur, este, norte = caja
    while pendientes:
        x, y, zz = pendientes.pop()
        r = _S.get(url_mosaico(_quadkey(x, y, zz)), timeout=60)
        if r.status_code != 200 or not r.text.startswith("{"):
            continue  # sin cortes en ese mosaico
        for f in r.json().get("file_data", []):
            d = f.get("desc", {})
            if d.get("cluster") and zz < z_max:  # grupo de cortes: mirar con mas detalle
                pendientes += [(2 * x + dx, 2 * y + dy, zz + 1) for dx in (0, 1) for dy in (0, 1)]
                continue
            lat, lon = _decodificar(f["geom"]["p"][0])
            if not (oeste <= lon <= este and sur <= lat <= norte):
                continue
            clientes = (d.get("cust_a") or {}).get("val") or 1
            radio = min(max(math.sqrt(clientes) * 40, RADIO_CORTE_MIN), RADIO_CORTE_MAX)
            eventos.append(("corte_luz", lon, lat, radio,
                            f"corte de luz: {clientes} clientes, reparacion estimada {d.get('etr') or 'sin dato'}"))
    # Un grupo grande puede repetirse en varios mosaicos hijos
    return list({(round(e[1], 5), round(e[2], 5)): e for e in eventos}.values())


def _cortes(caja, fuente):
    if fuente[0] == "kubra":
        _, inst, vista = fuente
        estado = _S.get(f"https://kubra.io/stormcenter/api/v1/stormcenters/{inst}/views/{vista}/currentState"
                        f"?preview=false", timeout=60).json()
        plantilla = estado["data"]["cluster_interval_generation_data"]
        return _kubra(caja, lambda q: f"https://kubra.io/{plantilla.replace('{qkh}', q[-3:][::-1])}"
                                      f"/public/cluster-6/{q}.json")
    if fuente[0] == "kubra_clasico":
        base = fuente[1]
        carpeta = _S.get(f"{base}/metadata.json", timeout=60).json()["directory"]
        return _kubra(caja, lambda q: f"{base}/{carpeta}/outages/{q}.json", z=9)
    return []


# ---------------------------------------------------------------------------
# 3. Apagones vistos desde el satelite (la ultima noche vs lo normal)
def _apagones_satelite(caja):
    """Zonas en apagon la ultima noche (regla prudente de luz_satelite.apagones:
    los dos satelites, noche limpia, zona normalmente bien iluminada)."""
    datos = LS.brillo(caja, noches=15)
    marcas = datos["apagones"]
    if marcas is None:  # noche con nubes o luna, o falta un satelite: no se afirma nada
        return []
    oeste, sur, este, norte = caja
    eventos = []
    for f, c in zip(*np.where(marcas)):
        lat = norte - (f + 0.5) / marcas.shape[0] * (norte - sur)
        lon = oeste + (c + 0.5) / marcas.shape[1] * (este - oeste)
        eventos.append(("apagon_satelite", lon, lat, 300,
                        f"zona mucho mas oscura que lo normal la noche del {datos['fecha_ultima']}"))
    return eventos


def eventos(ciudad, caja, satelite=True):
    """Todos los eventos de oscuridad recientes de una ciudad. Una fuente que
    falla no detiene a las demas (se informa en 'errores')."""
    fuentes = FUENTES.get(ciudad, {})
    desde = date.today() - timedelta(days=DIAS_REPORTE)
    salida, errores = [], []
    tareas = []
    if fuentes.get("reportes") == "wprdc_311":
        tareas.append(("311 Pittsburgh", lambda: _wprdc_311(caja, desde)))
    if fuentes.get("reportes") == "nyc_311":
        tareas.append(("311 Nueva York", lambda: _nyc_311(caja, desde)))
    if fuentes.get("cortes"):
        tareas.append(("cortes de luz", lambda: _cortes(caja, fuentes["cortes"])))
    if satelite:
        tareas.append(("satelite", lambda: _apagones_satelite(caja)))
    for nombre, tarea in tareas:
        try:
            salida += tarea()
        except Exception as e:  # una fuente caida no debe tumbar las demas
            errores.append(f"{nombre}: {e}")
    return {"eventos": salida, "errores": errores, "actualizado": datetime.now().isoformat(timespec="minutes")}
