"""Hacker News vía Algolia (pública, sin clave). Señal temprana opcional."""
import statistics
import time

from ..db import Pieza, guardar_referencia
from ..http import get_json


def recolectar(cfg: dict, con) -> list[Pieza]:
    desde = int(time.time() - cfg["dias_ventana"] * 86400)
    piezas = []
    for q in cfg["redes"]["hn"].get("consultas", []):
        datos = get_json("https://hn.algolia.com/api/v1/search", {
            "query": q, "tags": "story", "numericFilters": f"created_at_i>{desde},points>20", "hitsPerPage": 25}, ttl=3600)
        for h in datos.get("hits", []):
            piezas.append(Pieza(
                id=f"hn:{h['objectID']}", red="hn", url=f"https://news.ycombinator.com/item?id={h['objectID']}",
                titulo=h.get("title") or "", texto=h.get("url") or "", cuenta=h.get("author", ""), grupo="hn",
                publicado=float(h["created_at_i"]), via="api", metrica=float(h.get("points") or 0),
                comentarios=float(h.get("num_comments") or 0)))
    piezas = list({p.id: p for p in piezas}.values())
    if piezas:
        guardar_referencia(con, "hn", statistics.median(p.metrica for p in piezas))
    print(f"  Hacker News: {len(piezas)} hilos")
    return piezas
