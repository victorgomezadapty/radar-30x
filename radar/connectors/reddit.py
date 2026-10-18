"""Reddit: API oficial con app OAuth (client_credentials). Sin claves, feeds RSS públicos sin métricas."""
import re
import statistics
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape

import requests

from ..config import clave
from ..db import Pieza, guardar_captura, guardar_referencia
from ..http import get_json, get_texto

_token = {"valor": None, "expira": 0}


def _ua() -> str:
    return clave("REDDIT_USER_AGENT") or "radar-30x/0.1 (hackathon JEV)"


def _oauth() -> str | None:
    cid, secreto = clave("REDDIT_CLIENT_ID"), clave("REDDIT_CLIENT_SECRET")
    if not (cid and secreto):
        return None
    if _token["valor"] and time.time() < _token["expira"]:
        return _token["valor"]
    resp = requests.post("https://www.reddit.com/api/v1/access_token", auth=(cid, secreto),
                         data={"grant_type": "client_credentials"}, headers={"User-Agent": _ua()}, timeout=30)
    resp.raise_for_status()
    datos = resp.json()
    _token.update(valor=datos["access_token"], expira=time.time() + datos.get("expires_in", 3600) - 60)
    return _token["valor"]


def _a_pieza(d: dict) -> Pieza:
    return Pieza(
        id=f"reddit:{d['id']}", red="reddit", url=f"https://www.reddit.com{d['permalink']}",
        titulo=d["title"], texto=(d.get("selftext") or "")[:1500], cuenta=f"r/{d['subreddit']}",
        grupo=f"rd:{d['subreddit']}", publicado=float(d["created_utc"]), via="api",
        metrica=float(d.get("score", 0)), comentarios=float(d.get("num_comments", 0)),
        extra={"upvote_ratio": d.get("upvote_ratio"), "link": d.get("url")},
    )


def recolectar(cfg: dict, con) -> list[Pieza]:
    subs = cfg["redes"]["reddit"].get("subreddits", [])
    limite = max(10, cfg["max_piezas_por_red"] // max(1, len(subs)))
    try:
        token = _oauth()
    except Exception as e:
        print(f"  Reddit: OAuth falló ({e}); uso RSS.")
        token = None
    piezas: list[Pieza] = []
    if not token:  # RSS: un solo pedido con todos los subreddits juntos, para no chocar con el límite
        try:
            piezas = _rss(subs, min(100, limite * len(subs)))
        except Exception as e:  # un subreddit inexistente puede tumbar el pedido combinado: se prueba uno por uno
            print(f"    aviso: RSS combinado de Reddit falló ({type(e).__name__}); pruebo subreddit por subreddit")
            for sub in subs:
                try:
                    piezas += _rss([sub], limite)
                except Exception:
                    print(f"    aviso: r/{sub} no disponible")
                time.sleep(3)
        print(f"  Reddit: {len(piezas)} posts (RSS, sin métricas)")
        return piezas
    for sub in subs:
        try:
            datos = get_json(f"https://oauth.reddit.com/r/{sub}/top", {"t": "week", "limit": limite},
                             headers={"Authorization": f"bearer {token}", "User-Agent": _ua()}, ttl=3600)
            nuevas = [_a_pieza(c["data"]) for c in datos["data"]["children"] if not c["data"].get("stickied")]
            if nuevas:
                guardar_referencia(con, f"rd:{sub}", statistics.median(p.metrica for p in nuevas))
            piezas += nuevas
        except Exception as e:
            print(f"    aviso: r/{sub} falló: {e}")
    print(f"  Reddit: {len(piezas)} posts (API)")
    return piezas


def _rss(subs: list[str], limite: int) -> list[Pieza]:
    url = f"https://www.reddit.com/r/{'+'.join(subs)}/top/.rss?t=week&limit={limite}"
    for intento in range(3):  # el RSS público limita rápido: pausa y reintento
        try:
            xml = get_texto(url, headers={"User-Agent": _ua()})
            break
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 429 or intento == 2:
                raise
            time.sleep(6 * (intento + 1))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    piezas = []
    for e in ET.fromstring(xml).findall("a:entry", ns):
        ident = (e.findtext("a:id", "", ns) or "").replace("t3_", "")
        fecha = e.findtext("a:published", None, ns) or e.findtext("a:updated", None, ns)
        link = e.find("a:link", ns)
        cat = e.find("a:category", ns)
        sub = cat.get("term") if cat is not None else "reddit"
        piezas.append(Pieza(
            id=f"reddit:{ident}", red="reddit", url=link.get("href") if link is not None else "",
            titulo=e.findtext("a:title", "", ns), texto=_limpiar(e.findtext("a:content", "", ns)), cuenta=f"r/{sub}", grupo=f"rd:{sub}",
            publicado=datetime.fromisoformat(fecha).timestamp() if fecha else None, via="rss",
        ))
    return piezas


def _limpiar(html: str) -> str:
    texto = re.sub(r"<[^>]+>", " ", unescape(html or ""))
    texto = re.sub(r"submitted by .*$", "", texto, flags=re.S)
    return re.sub(r"\s+", " ", texto).strip()[:1500]


def capturar(con, sector: str) -> int:
    token = _oauth() if clave("REDDIT_CLIENT_ID") else None
    if not token:
        return 0
    ids = [r["id"].split(":", 1)[1] for r in con.execute(
        "SELECT id FROM piezas WHERE sector=? AND red='reddit' AND via='api'", (sector,))]
    ahora = time.time()
    for i in range(0, len(ids), 100):
        nombres = ",".join(f"t3_{x}" for x in ids[i:i + 100])
        datos = get_json(f"https://oauth.reddit.com/by_id/{nombres}", {},
                         headers={"Authorization": f"bearer {token}", "User-Agent": _ua()}, ttl=0)
        for c in datos["data"]["children"]:
            d = c["data"]
            guardar_captura(con, f"reddit:{d['id']}", float(d.get("score", 0)), None,
                            float(d.get("num_comments", 0)), ahora)
    con.commit()
    return len(ids)
