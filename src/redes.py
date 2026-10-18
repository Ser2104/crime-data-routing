"""
Descarga de las redes de calles (OpenStreetMap, con OSMnx), iguales para todas
las ciudades:

red_peatonal(poligono): calles caminables dentro del poligono, sin las vias por
    donde un peaton no puede caminar (comun.prohibida_a_pie).
red_carro(rectangulo): calles para carros dentro del RECTANGULO (sin recortar al
    contorno de la ciudad: las calles que salen y vuelven a entrar quedarian
    cortadas), con sentido, velocidad y tiempo de viaje de cada tramo, y sin las
    vias que un carro particular no puede usar y que el filtro "drive" de OSMnx
    deja pasar: solo para bus, rampas de frenado de emergencia, carriles HOV,
    vias privadas para vehiculos y con acceso prohibido (salvo las que permiten
    expresamente vehiculos).
"""
import osmnx as ox

from comun import prohibida_a_pie, valores

# Etiquetas extra de OSM que se necesitan para detectar vias restringidas
ETIQUETAS_PIE = ["access", "foot"]
ETIQUETAS_CARRO = ["access", "hov", "motor_vehicle", "motorcar", "bus"]
ACCESO_PROHIBIDO_CARRO = {"no", "hov", "permit", "private", "bus", "psv"}
VEHICULOS_PERMITIDOS = {"yes", "designated", "permissive", "destination"}


def restringida(d):
    """True si un carro particular no puede usar esta via (d = datos de la arista)."""
    if "busway" in str(d.get("highway")) or "escape" in str(d.get("highway")):
        return True  # solo buses, o rampa de frenado de emergencia para camiones
    if (valores(d.get("motor_vehicle")) | valores(d.get("motorcar"))) & {"no", "private"}:
        return True
    if valores(d.get("hov")) & {"designated", "lane"}:
        return True
    if valores(d.get("access")) & ACCESO_PROHIBIDO_CARRO:
        # access=no con motor_vehicle=yes (p.ej. una rampa) si se puede usar
        return not (valores(d.get("motor_vehicle")) | valores(d.get("motorcar"))) & VEHICULOS_PERMITIDOS
    return False


def _con_etiquetas(extra):
    ox.settings.useful_tags_way = list(dict.fromkeys(ox.settings.useful_tags_way + extra))


def red_peatonal(poligono):
    """Red caminable dentro del poligono (grados), la parte conectada mas grande."""
    _con_etiquetas(ETIQUETAS_PIE)
    G = ox.graph_from_polygon(poligono, network_type="walk")
    quitar = [(u, v, k) for u, v, k, d in G.edges(keys=True, data=True) if prohibida_a_pie(d)]
    km = sum(G.edges[e]["length"] for e in quitar) / 2000  # cada via esta en los 2 sentidos
    G.remove_edges_from(quitar)
    print(f"Vias prohibidas a pie eliminadas (bus, acceso prohibido): {len(quitar)} tramos, {km:.1f} km")
    return ox.truncate.largest_component(G, strongly=True)


def red_carro(rectangulo):
    """Red para carros dentro del rectangulo (oeste, sur, este, norte), donde se puede
    ir de cualquier punto a cualquier otro respetando los sentidos, con velocidad
    (km/h; si OSM no la tiene, el promedio de su tipo de via) y tiempo (segundos)."""
    _con_etiquetas(ETIQUETAS_CARRO)
    print(f"Descargando red para carros del rectangulo {tuple(round(x, 3) for x in rectangulo)}...")
    G = ox.graph_from_bbox(rectangulo, network_type="drive", simplify=True)
    quitar = [(u, v, k) for u, v, k, d in G.edges(keys=True, data=True) if restringida(d)]
    km = sum(G.edges[e]["length"] for e in quitar) / 1000
    G.remove_edges_from(quitar)
    print(f"Tramos restringidos eliminados (bus, HOV, acceso prohibido): {len(quitar)} ({km:.1f} km)")
    G = ox.truncate.largest_component(G, strongly=True)
    G = ox.routing.add_edge_speeds(G)
    return ox.routing.add_edge_travel_times(G)
