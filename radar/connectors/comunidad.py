"""Comunidad como sensor: links que el equipo pega en data/comunidad.csv.
Columnas: sector,red,url,titulo,autor,fecha(YYYY-MM-DD)"""
import csv
from datetime import datetime, timezone

from ..config import DIR_DATA
from ..db import Pieza
from ..llm import _norm


def leer(sector: str, red: str) -> list[Pieza]:
    ruta = DIR_DATA / "comunidad.csv"
    if not ruta.exists():
        return []
    piezas = []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            if fila.get("sector") != sector or fila.get("red") != red or not fila.get("url"):
                continue
            publicado = None
            if fila.get("fecha"):
                try:
                    publicado = datetime.fromisoformat(fila["fecha"]).replace(tzinfo=timezone.utc).timestamp()
                except ValueError:
                    pass
            piezas.append(Pieza(id=f"{red}:{_norm(fila['url'])}", red=red, url=fila["url"],
                                titulo=fila.get("titulo", ""), cuenta=fila.get("autor", ""),
                                grupo=f"{red}:comunidad", publicado=publicado, via="comunidad"))
    return piezas
