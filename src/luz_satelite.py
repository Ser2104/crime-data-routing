"""
Luz nocturna vista desde el satelite (NASA, sensor VIIRS "Day/Night Band"), para
CUALQUIER lugar del mundo, cada noche (~1:30 am hora local), gratis y sin cuenta
(servicio GIBS de la NASA). Cada pixel mide ~500 m: dice que ZONAS tienen luz,
no que calle.

La imagen viene en tonos de gris; la tabla de colores de la NASA dice que
radiancia (nW/cm2/sr) representa cada tono, de 0 a 38.2 (mas brillante satura).
Una sola noche puede tener nubes o luna; por eso:
    brillo normal: mediana de muchas noches (lo que tiene una zona habitualmente)
    apagones:      zonas bien iluminadas que la ultima noche, en los DOS satelites,
                   tienen mucho menos brillo que lo normal, en una noche limpia
                   (ver apagones(); calibrado con noches pasadas en el paso 15)
"""
import io
import re
from datetime import date, timedelta

import numpy as np
import requests
from PIL import Image

WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"
CAPAS = ["VIIRS_SNPP_DayNightBand_At_Sensor_Radiance", "VIIRS_NOAA20_DayNightBand_At_Sensor_Radiance"]
COLORES = "https://gibs.earthdata.nasa.gov/colormaps/v1.3/VIIRS_DayNightBand_At_Sensor_Radiance.xml"
GRADOS_PIXEL = 0.004   # ~450 m: la resolucion del sensor (se pide un poco mas fino y se repite)
SATURA = 38.2          # nW/cm2/sr: por encima, la imagen ya no distingue
NOCHES = 45            # noches para el brillo normal
_SESION = requests.Session()
_SESION.headers["User-Agent"] = "safe-routes-pgh/0.1 (proyecto personal)"
_tabla = None


def tabla_radiancia():
    """Tono de gris (0-255) -> radiancia (centro de su rango, nW/cm2/sr)."""
    global _tabla
    if _tabla is None:
        texto = _SESION.get(COLORES, timeout=60).text
        tabla = np.full(256, np.nan)
        for rgb, valor in re.findall(r'rgb="(\d+),\d+,\d+" transparent="false"[^>]*? value="\[([^)\]]+)\)"', texto):
            a, b = (float(x) for x in valor.split(","))
            tabla[int(rgb)] = SATURA if a >= SATURA else (a + b) / 2
        _tabla = tabla
    return _tabla


def una_noche(caja, dia, capa=CAPAS[0]):
    """Radiancia de una noche en la caja (oeste, sur, este, norte). NaN = sin dato."""
    oeste, sur, este, norte = caja
    ancho = max(int(np.ceil((este - oeste) / GRADOS_PIXEL)), 8)
    alto = max(int(np.ceil((norte - sur) / GRADOS_PIXEL)), 8)
    r = _SESION.get(WMS, timeout=120, params={
        "SERVICE": "WMS", "REQUEST": "GetMap", "VERSION": "1.3.0", "LAYERS": capa, "STYLES": "",
        "CRS": "EPSG:4326", "BBOX": f"{sur},{oeste},{norte},{este}", "WIDTH": ancho, "HEIGHT": alto,
        "FORMAT": "image/png", "TIME": dia.isoformat()})
    if not r.ok or not r.headers.get("content-type", "").startswith("image"):
        return None
    img = np.array(Image.open(io.BytesIO(r.content)).convert("RGBA"))
    valor = tabla_radiancia()[img[..., 0]]
    valor[img[..., 3] == 0] = np.nan  # transparente = fuera de la pasada del satelite
    return valor


def imagenes(caja, hasta=None, n=NOCHES):
    """Imagenes de las ultimas n noches de los dos satelites: lista de (dia, capa, grilla)."""
    hasta = hasta or date.today() - timedelta(days=1)
    salida = []
    for k in range(n):
        dia = hasta - timedelta(days=k)
        for capa in CAPAS:
            g = una_noche(caja, dia, capa)
            if g is not None and np.isfinite(g).mean() > 0.5:
                salida.append((dia, capa, g))
    return salida


# Apagon: una zona normalmente bien iluminada que, la misma noche y en los DOS
# satelites, tiene menos de UMBRAL_APAGON de su brillo normal, en una noche
# "limpia" (el brillo de toda la ciudad entre CIUDAD_MIN y CIUDAD_MAX de lo
# normal: si toda la ciudad cambia, son nubes o la luna). Valores calibrados para
# que en noches normales casi no haya falsas alarmas (ver paso 15).
# Calibrado (paso 15, 30 noches de 4 ciudades): con 25% hay alarmas en el 4% de
# las noches limpias (con 35%, en el 23%: demasiadas falsas alarmas)
NORMAL_MIN = 5         # nW/cm2/sr: solo zonas normalmente iluminadas
UMBRAL_APAGON = 0.25
CIUDAD_MIN, CIUDAD_MAX = 0.75, 1.35


def apagones(normal, imagenes_noche, umbral=UMBRAL_APAGON, normal_min=NORMAL_MIN):
    """Pixeles en apagon una noche. imagenes_noche: grillas de esa noche (una por
    satelite). Devuelve una grilla booleana (o None si la noche no es limpia)."""
    if len(imagenes_noche) < len(CAPAS):
        return None  # sin los dos satelites no se confirma nada
    marcas = []
    for g in imagenes_noche:
        ciudad = np.nanmedian(g) / np.nanmedian(normal)
        if not CIUDAD_MIN <= ciudad <= CIUDAD_MAX:
            return None  # nubes o luna: noche no limpia
        with np.errstate(invalid="ignore", divide="ignore"):
            marcas.append((g / normal < umbral) & (normal >= normal_min))
    return np.logical_and.reduce(marcas)


def brillo(caja, hasta=None, noches=NOCHES):
    """Brillo normal (mediana de 'noches' noches, con los dos satelites) y los
    apagones de la ultima noche con datos de los dos satelites."""
    todas = imagenes(caja, hasta, noches)
    normal = np.nanmedian(np.stack([g for _, _, g in todas]), axis=0)
    ultimo_dia = todas[0][0]
    de_la_noche = [g for d, _, g in todas if d == ultimo_dia]
    return {"caja": caja, "normal": normal, "ultima": de_la_noche[0], "fecha_ultima": ultimo_dia,
            "noches": len(todas), "apagones": apagones(normal, de_la_noche)}


def valor_en(datos, lon, lat, grilla="normal"):
    """Valor de la grilla en cada punto (lon, lat en grados)."""
    oeste, sur, este, norte = datos["caja"]
    g = datos[grilla]
    filas = np.clip(((norte - np.asarray(lat)) / (norte - sur) * g.shape[0]).astype(int), 0, g.shape[0] - 1)
    cols = np.clip(((np.asarray(lon) - oeste) / (este - oeste) * g.shape[1]).astype(int), 0, g.shape[1] - 1)
    return g[filas, cols]
