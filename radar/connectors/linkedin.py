"""LinkedIn: no hay API de métricas de posts públicos. Entra por búsqueda web sobre posts indexados
y por los links que pega la comunidad (data/comunidad.csv). Aporta presencia, saturación y ajuste."""
from .. import busqueda
from ..db import Pieza
from .comunidad import leer as leer_comunidad


def recolectar(cfg: dict, gcfg: dict, contador) -> list[Pieza]:
    rc = cfg["redes"]["linkedin"]
    piezas = busqueda.buscar_publicaciones(gcfg, contador, "linkedin", "linkedin.com", rc.get("consultas", []),
                                      cfg["persona"], cfg["dias_ventana"])
    piezas += leer_comunidad(cfg["sector"], "linkedin")
    print(f"  LinkedIn: {len(piezas)} posts (búsqueda web + comunidad, sin métricas)")
    return piezas
