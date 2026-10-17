"""YouTube Data API v3. Búsqueda cuesta 100 unidades; lecturas 1 unidad por cada 50 ids."""
import statistics
import time
from datetime import datetime, timedelta, timezone

from ..config import clave
from ..db import Pieza, guardar_captura, guardar_referencia
from ..http import get_json

API = "https://www.googleapis.com/youtube/v3"


def _epoch(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _detalles(ids: list[str], key: str, ttl: float) -> list[dict]:
    items = []
    for i in range(0, len(ids), 50):
        datos = get_json(f"{API}/videos", {"part": "snippet,statistics", "id": ",".join(ids[i:i + 50]),
                                           "key": key, "maxResults": 50}, ttl=ttl)
        items.extend(datos.get("items", []))
    return items


def _a_pieza(v: dict) -> Pieza:
    sn, st = v["snippet"], v.get("statistics", {})
    vistas = float(st.get("viewCount", 0))
    texto = f"{sn.get('description', '')[:1500]}\nTags: {', '.join(sn.get('tags', [])[:15])}"
    return Pieza(
        id=f"youtube:{v['id']}", red="youtube", url=f"https://www.youtube.com/watch?v={v['id']}",
        titulo=sn["title"], texto=texto, cuenta=sn.get("channelTitle", ""), grupo=f"yt:{sn['channelId']}",
        publicado=_epoch(sn["publishedAt"]), via="api", metrica=vistas,
        likes=float(st.get("likeCount", 0)), comentarios=float(st.get("commentCount", 0)),
        extra={"canal_id": sn["channelId"], "idioma": sn.get("defaultAudioLanguage")},
    )


def recolectar(cfg: dict, con) -> list[Pieza]:
    key = clave("YOUTUBE_API_KEY")
    if not key:
        print("  YouTube: falta YOUTUBE_API_KEY, se omite.")
        return []
    rc = cfg["redes"]["youtube"]
    desde = (datetime.now(timezone.utc) - timedelta(days=cfg["dias_ventana"])).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    for q in rc.get("consultas", []):
        datos = get_json(f"{API}/search", {
            "part": "id", "q": q, "type": "video", "order": "viewCount", "publishedAfter": desde,
            "maxResults": 25, "relevanceLanguage": rc.get("idioma", "es"), "regionCode": rc.get("region", "MX"),
            "key": key}, ttl=6 * 3600)
        ids += [it["id"]["videoId"] for it in datos.get("items", []) if it["id"].get("videoId")]
    for canal in rc.get("canales_semilla", []):
        datos = get_json(f"{API}/playlistItems", {"part": "contentDetails", "playlistId": "UU" + canal[2:],
                                                  "maxResults": 15, "key": key}, ttl=6 * 3600)
        ids += [it["contentDetails"]["videoId"] for it in datos.get("items", [])]
    ids = list(dict.fromkeys(ids))[: cfg["max_piezas_por_red"]]
    piezas = [_a_pieza(v) for v in _detalles(ids, key, ttl=3600)]
    _referencias(piezas, key, con)
    print(f"  YouTube: {len(piezas)} videos")
    return piezas


def _referencias(piezas: list[Pieza], key: str, con):
    """Mediana de vistas de los últimos videos de cada canal, para el outlier ratio."""
    canales = {p.extra["canal_id"] for p in piezas}
    for canal in canales:
        try:
            datos = get_json(f"{API}/playlistItems", {"part": "contentDetails", "playlistId": "UU" + canal[2:],
                                                      "maxResults": 15, "key": key}, ttl=24 * 3600)
            vids = [it["contentDetails"]["videoId"] for it in datos.get("items", [])]
            vistas = [float(v.get("statistics", {}).get("viewCount", 0)) for v in _detalles(vids, key, 24 * 3600)]
            if vistas:
                guardar_referencia(con, f"yt:{canal}", statistics.median(vistas))
        except Exception as e:  # un canal sin lista pública no debe frenar la corrida
            print(f"    aviso: sin referencia para canal {canal}: {e}")


def capturar(con, sector: str) -> int:
    key = clave("YOUTUBE_API_KEY")
    if not key:
        return 0
    ids = [r["id"].split(":", 1)[1] for r in con.execute(
        "SELECT id FROM piezas WHERE sector=? AND red='youtube'", (sector,))]
    ahora = time.time()
    for v in _detalles(ids, key, ttl=0):
        st = v.get("statistics", {})
        guardar_captura(con, f"youtube:{v['id']}", float(st.get("viewCount", 0)),
                        float(st.get("likeCount", 0)), float(st.get("commentCount", 0)), ahora)
    con.commit()
    return len(ids)
