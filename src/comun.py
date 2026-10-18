"""Funciones comunes a varios pasos del proyecto (y a rutas.py)."""


def id_tramo(u, v, osmid, largo):
    """Id de un tramo de calle, IGUAL para sus dos sentidos (u->v y v->u).

    Usa los dos nodos, la via de OpenStreetMap (osmid) y el largo (al decimetro),
    para que dos calles distintas entre los mismos nodos, o las dos ramas de un
    bucle, no compartan id. (Los dos sentidos de una misma calle tienen
    exactamente el mismo largo, asi que siguen compartiendo id.)"""
    ids = osmid if isinstance(osmid, list) else [osmid]
    return f"{min(u, v)}-{max(u, v)}-{'_'.join(sorted(str(i) for i in ids))}-{largo:.1f}"


def valores(dato):
    """Una etiqueta de OSM puede venir como texto, como lista o vacia: devuelve un set."""
    if isinstance(dato, list):
        return set(dato)
    return {dato} if isinstance(dato, str) else set()


# Vias que el filtro "walk" de OSMnx deja pasar pero por donde un peaton no
# puede caminar: solo para buses, o con acceso prohibido (salvo que permitan
# expresamente peatones). Lo usan las redes peatonales de todas las ciudades.
SOLO_BUS = ("busway", "bus_guideway")
ACCESO_PROHIBIDO = {"no", "private"}
PEATON_PERMITIDO = {"yes", "designated", "permissive"}


def prohibida_a_pie(d):
    """True si un peaton no puede caminar por esta via (d = datos de la arista)."""
    if any(t in str(d.get("highway")) for t in SOLO_BUS):
        return True
    if valores(d.get("foot")) & PEATON_PERMITIDO:
        return False
    return bool(valores(d.get("access")) & ACCESO_PROHIBIDO or "no" in valores(d.get("foot")))
