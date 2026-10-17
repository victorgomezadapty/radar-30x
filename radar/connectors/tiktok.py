"""TikTok: la Research API es solo para academia. Entra por dos vías:
1. Ranking de hashtags por país que el equipo copia del Creative Center a data/tiktok_hashtags.csv
   (columnas: fecha,pais,hashtag,posicion,publicaciones). Da aceleración por hashtag.
2. Búsqueda web sobre videos indexados (presencia y ajuste, sin métricas)."""
import csv
from collections import defaultdict

from .. import busqueda
from ..config import DIR_DATA
from ..db import Pieza
from .comunidad import leer as leer_comunidad


def cargar_hashtags(con) -> int:
    ruta = DIR_DATA / "tiktok_hashtags.csv"
    if not ruta.exists():
        return 0
    n = 0
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            try:
                con.execute("INSERT OR REPLACE INTO hashtags_tiktok VALUES (?,?,?,?,?)",
                            (fila["fecha"], fila["pais"].upper(), fila["hashtag"].lstrip("#").lower(),
                             int(fila["posicion"]), float(fila["publicaciones"] or 0)))
                n += 1
            except (KeyError, ValueError):
                continue
    con.commit()
    return n


def hashtags_con_aceleracion(con, paises: list[str]) -> list[dict]:
    """Por hashtag: mejora de posición entre la primera y la última fecha registrada."""
    filas = con.execute("SELECT * FROM hashtags_tiktok ORDER BY fecha").fetchall()
    serie = defaultdict(list)
    for f in filas:
        if not paises or f["pais"] in paises:
            serie[f["hashtag"]].append((f["fecha"], f["posicion"], f["pais"]))
    salida = []
    for tag, puntos in serie.items():
        por_fecha = defaultdict(list)
        for fecha, pos, _ in puntos:
            por_fecha[fecha].append(pos)
        fechas = sorted(por_fecha)
        pos_ini = min(por_fecha[fechas[0]])
        pos_fin = min(por_fecha[fechas[-1]])
        salida.append({"hashtag": tag, "posicion": pos_fin, "mejora": pos_ini - pos_fin,
                       "dias": len(fechas), "paises": sorted({p for _, _, p in puntos})})
    return salida


def recolectar(cfg: dict, gcfg: dict, contador, con) -> list[Pieza]:
    rc = cfg["redes"]["tiktok"]
    cargar_hashtags(con)
    piezas = []
    for h in hashtags_con_aceleracion(con, rc.get("paises", [])):
        piezas.append(Pieza(id=f"tiktok:#{h['hashtag']}", red="tiktok", url=f"https://www.tiktok.com/tag/{h['hashtag']}",
                            titulo=f"#{h['hashtag']}", texto=f"Trending TikTok hashtag in {', '.join(h['paises'])}",
                            cuenta="Creative Center", grupo="tiktok:hashtags", via="manual",
                            extra={"hashtag": h}))
    n_tags = len(piezas)
    piezas += busqueda.buscar_publicaciones(gcfg, contador, "tiktok", "tiktok.com", rc.get("consultas_web", []),
                                       cfg["persona"], cfg["dias_ventana"])
    piezas += leer_comunidad(cfg["sector"], "tiktok")
    print(f"  TikTok: {n_tags} hashtags + {len(piezas) - n_tags} videos (búsqueda web/comunidad, sin métricas)")
    return piezas
