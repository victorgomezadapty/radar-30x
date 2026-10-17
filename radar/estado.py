"""Qué aporta cada red con las claves disponibles hoy (en .env local o en los secretos de GitHub)."""
from .config import clave

REDES = ["youtube", "reddit", "instagram", "linkedin", "tiktok", "hn"]

NOMBRES = {"youtube": "YouTube", "reddit": "Reddit", "instagram": "Instagram", "linkedin": "LinkedIn",
           "tiktok": "TikTok", "hn": "Hacker News"}


def estado_redes(cfg: dict) -> list[dict]:
    """Qué aporta cada red con las claves que hay hoy en .env."""
    tavily = bool(clave("TAVILY_API_KEY"))
    info = {
        "youtube": (bool(clave("YOUTUBE_API_KEY")), True, "YouTube Data API" if clave("YOUTUBE_API_KEY") else "falta YOUTUBE_API_KEY"),
        "reddit": (True, bool(clave("REDDIT_CLIENT_ID")), "API oficial" if clave("REDDIT_CLIENT_ID") else "RSS público (sin métricas)"),
        "instagram": (bool(clave("IG_ACCESS_TOKEN")) or tavily, bool(clave("IG_ACCESS_TOKEN")),
                      "Graph API" if clave("IG_ACCESS_TOKEN") else ("búsqueda web (sin métricas)" if tavily else "falta TAVILY_API_KEY")),
        "linkedin": (tavily, False, "búsqueda web + comunidad (sin métricas)" if tavily else "solo comunidad"),
        "tiktok": (True, False, "búsqueda web + hashtags del Creative Center" if tavily else "solo hashtags del Creative Center"),
        "hn": (True, True, "API Algolia"),
    }
    salida = []
    for red in REDES:
        disponible, metricas, via = info[red]
        salida.append({"id": red, "nombre": NOMBRES[red], "activa": bool(cfg["redes"].get(red, {}).get("activa")),
                       "disponible": disponible, "con_metricas": metricas, "via": via})
    return salida
