"""Instagram Graph API con una cuenta profesional propia: Business Discovery y búsqueda por hashtag.
Sin IG_USER_ID / IG_ACCESS_TOKEN cae a búsqueda web (sin métricas)."""
import statistics
from datetime import datetime

from ..config import clave
from ..db import Pieza, guardar_referencia
from ..http import get_json
from .. import busqueda

CAMPOS_MEDIA = "id,caption,like_count,comments_count,timestamp,permalink,media_type"


def _epoch(iso: str) -> float:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S%z").timestamp()


def _a_pieza(m: dict, cuenta: str, grupo: str) -> Pieza:
    likes, coments = float(m.get("like_count") or 0), float(m.get("comments_count") or 0)
    caption = m.get("caption") or ""
    return Pieza(
        id=f"instagram:{m['id']}", red="instagram", url=m.get("permalink", ""),
        titulo=caption.split("\n")[0][:200], texto=caption[:1500], cuenta=cuenta, grupo=grupo,
        publicado=_epoch(m["timestamp"]) if m.get("timestamp") else None, via="api",
        metrica=likes + coments, likes=likes, comentarios=coments, extra={"tipo": m.get("media_type")})


def recolectar(cfg: dict, gcfg: dict, contador, con) -> list[Pieza]:
    rc = cfg["redes"]["instagram"]
    ig, token = clave("IG_USER_ID"), clave("IG_ACCESS_TOKEN")
    if not (ig and token):
        piezas = busqueda.buscar_publicaciones(gcfg, contador, "instagram", "instagram.com",
                                          rc.get("consultas_web", []), cfg["persona"], cfg["dias_ventana"])
        print(f"  Instagram: {len(piezas)} posts (búsqueda web, sin métricas)")
        return piezas
    base = f"https://graph.facebook.com/{gcfg['instagram']['graph_version']}"
    piezas: list[Pieza] = []
    for usuario in rc.get("cuentas", []):
        try:
            campos = f"business_discovery.username({usuario}){{followers_count,media.limit(25){{{CAMPOS_MEDIA}}}}}"
            datos = get_json(f"{base}/{ig}", {"fields": campos, "access_token": token}, ttl=3600)
            media = datos["business_discovery"]["media"]["data"]
            nuevas = [_a_pieza(m, usuario, f"ig:{usuario}") for m in media]
            if nuevas:
                guardar_referencia(con, f"ig:{usuario}", statistics.median(p.metrica for p in nuevas))
            piezas += nuevas
        except Exception as e:
            print(f"    aviso: cuenta {usuario} falló: {e}")
    for tag in rc.get("hashtags", []):
        try:
            hid = get_json(f"{base}/ig_hashtag_search", {"user_id": ig, "q": tag, "access_token": token},
                           ttl=7 * 86400)["data"][0]["id"]
            media = get_json(f"{base}/{hid}/top_media", {"user_id": ig, "fields": CAMPOS_MEDIA,
                                                         "access_token": token, "limit": 30}, ttl=3600)["data"]
            nuevas = [_a_pieza(m, f"#{tag}", f"ig:#{tag}") for m in media]
            if nuevas:
                guardar_referencia(con, f"ig:#{tag}", statistics.median(p.metrica for p in nuevas))
            piezas += nuevas
        except Exception as e:
            print(f"    aviso: hashtag #{tag} falló: {e}")
    print(f"  Instagram: {len(piezas)} posts (Graph API)")
    return piezas
