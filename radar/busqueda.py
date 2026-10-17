"""Búsqueda web de posts públicos indexados (LinkedIn, TikTok, Instagram sin Graph API) con Tavily.

Las URLs vienen directo de la API de búsqueda, así que ningún modelo puede inventarlas.
Sin TAVILY_API_KEY estas redes quedan solo con lo que pega la comunidad (data/comunidad.csv)."""
import re
from datetime import datetime, timezone

import requests

from .config import clave
from .db import Pieza
from .llm import _norm

API = "https://api.tavily.com/search"
# solo páginas de posts individuales, no perfiles ni empleos
RUTAS_POST = {
    "linkedin.com": re.compile(r"linkedin\.com/(posts|pulse|feed/update)/"),
    "tiktok.com": re.compile(r"tiktok\.com/@[^/]+/video/"),
    "instagram.com": re.compile(r"instagram\.com/(p|reel|reels)/"),
}
_avisado = set()


def _cuenta(url: str) -> str:
    if m := re.search(r"linkedin\.com/posts/([^_/]+)", url):
        return m.group(1)
    if m := re.search(r"tiktok\.com/@([^/]+)", url):
        return "@" + m.group(1)
    return ""


def _fecha(valor) -> float | None:
    if not valor:
        return None
    for formato in ("%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(str(valor)[:29], formato).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


ALFABETO_IG = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def fecha_desde_url(url: str) -> float | None:
    """Las tres redes codifican la fecha de publicación en el ID de la URL."""
    try:
        if m := re.search(r"tiktok\.com/@[^/]+/video/(\d{15,})", url):
            return float(int(m.group(1)) >> 32)                      # segundos desde 1970
        if m := re.search(r"activity[-:](\d{19})", url):
            return (int(m.group(1)) >> 22) / 1000                    # LinkedIn: milisegundos
        if m := re.search(r"instagram\.com/(?:p|reel|reels)/([A-Za-z0-9_-]{11})", url):
            media_id = 0
            for ch in m.group(1):
                media_id = media_id * 64 + ALFABETO_IG.index(ch)
            return ((media_id >> 23) + 1314220021721) / 1000         # época propia de Instagram
    except (ValueError, OverflowError):
        return None
    return None


def buscar_publicaciones(gcfg: dict, contador, red: str, dominio: str, consultas: list[str],
                         persona: str, dias: int) -> list[Pieza]:
    key = clave("TAVILY_API_KEY")
    if not key:
        if red not in _avisado:
            print(f"    {red}: sin TAVILY_API_KEY, se omite la búsqueda web")
            _avisado.add(red)
        return []
    rango = "week" if dias <= 7 else "month"
    patron = RUTAS_POST.get(dominio)
    piezas, busquedas = {}, 0
    for q in consultas[: gcfg["busqueda"]["consultas_por_red"]]:
        try:
            resp = requests.post(API, timeout=40, headers={"Authorization": f"Bearer {key}"}, json={
                "api_key": key, "query": q, "include_domains": [dominio], "time_range": rango,
                "max_results": gcfg["busqueda"]["resultados_por_consulta"], "search_depth": "basic", "topic": "general"})
            if resp.status_code in (401, 403):
                print(f"    {red}: Tavily rechazó la clave (TAVILY_API_KEY inválida o revocada); se omite la búsqueda web")
                break
            if resp.status_code in (429, 432, 433):
                print(f"    {red}: Tavily sin cuota disponible ({resp.status_code}); se omite la búsqueda web")
                break
            resp.raise_for_status()
            busquedas += 1
        except requests.RequestException as e:
            print(f"    aviso búsqueda {red} '{q}': {type(e).__name__}")
            continue
        for r in resp.json().get("results", []):
            url = r.get("url") or ""
            if dominio not in url or (patron and not patron.search(url)):
                continue
            pid = f"{red}:{_norm(url)}"
            piezas[pid] = Pieza(id=pid, red=red, url=url, titulo=(r.get("title") or "")[:300],
                                texto=(r.get("content") or "")[:1500], cuenta=_cuenta(url), grupo=f"{red}:web",
                                publicado=_fecha(r.get("published_date")) or fecha_desde_url(url), via="busqueda_web",
                                extra={"consulta": q})
    contador.llm(f"busqueda_{red}", "tavily", 0, 0, busquedas)
    return list(piezas.values())
