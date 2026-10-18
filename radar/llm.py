"""Pasos del LLM (DeepSeek, API compatible con OpenAI): proponer temas y redactar.

El LLM nunca decide el ranking: propone nombres de temas y redacta. La búsqueda web vive en busqueda.py.
"""
import json
from urllib.parse import urlsplit

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .config import clave

_cliente = None


def cliente(gcfg: dict) -> OpenAI:
    global _cliente
    if _cliente is None:
        _cliente = OpenAI(api_key=clave("DEEPSEEK_API_KEY"), base_url=gcfg["llm"]["base_url"])
    return _cliente


def _norm(url: str) -> str:
    p = urlsplit(url)
    return (p.netloc.replace("www.", "") + p.path).rstrip("/").lower()


def _json(gcfg: dict, contador, paso: str, modelo: str, prompt: str, esquema: type[BaseModel]) -> BaseModel:
    """Modo JSON de DeepSeek + validación con Pydantic. Un reintento si el JSON no cumple el esquema."""
    sistema = ("Respond only with a valid JSON object that matches this JSON schema exactly:\n"
               + json.dumps(esquema.model_json_schema(), ensure_ascii=False))
    mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": prompt}]
    for intento in range(2):
        pensar = gcfg["llm"].get("pensar", {}).get(paso.replace("llm_", ""), False)
        resp = cliente(gcfg).chat.completions.create(
            model=modelo, messages=mensajes, response_format={"type": "json_object"}, max_tokens=8000,
            extra_body={"thinking": {"type": "enabled" if pensar else "disabled"}})
        u = resp.usage
        contador.llm(paso, modelo, u.prompt_tokens if u else 0, u.completion_tokens if u else 0)
        texto = resp.choices[0].message.content or ""
        try:
            return esquema.model_validate_json(texto)
        except ValidationError as e:
            if intento == 1:
                raise
            mensajes += [{"role": "assistant", "content": texto},
                         {"role": "user", "content": f"That JSON does not match the schema: {e.errors()[:3]}. Return the corrected JSON only."}]


# ---------- temas de la corrida ----------

class Tema(BaseModel):
    id: str
    nombre: str
    descripcion: str


class Temas(BaseModel):
    temas: list[Tema]


def proponer_temas(gcfg: dict, contador, cfg: dict, titulos: list[str], previos: list[dict]) -> list[dict]:
    lista = "\n".join(f"- {t[:140]}" for t in titulos[:600])
    pista_previos = ""
    if previos:
        pista_previos = "Topics from the previous run (reuse the same id and name when a topic is still present):\n" + \
            "\n".join(f"- {t['id']}: {t['nombre']}" for t in previos)
    prompt = f"""Below are titles of content pieces collected this week from YouTube, Reddit, Instagram, LinkedIn and TikTok.
Sector: {cfg['nombre']}. Guidance: {cfg['pista_temas']}

Propose between 15 and 20 specific, non-overlapping topics that group these pieces. A topic must be
specific enough to make a post about (e.g. "AI agents for customer service", not "AI"). Do not propose
a catch-all topic; "other" is added automatically.
- id: short snake_case in English
- nombre: short name in Spanish (max 6 words)
- descripcion: one sentence in English describing what belongs to this topic

Return JSON like {{"temas": [{{"id": "...", "nombre": "...", "descripcion": "..."}}]}}

{pista_previos}

Titles:
{lista}"""
    salida = _json(gcfg, contador, "llm_temas", gcfg["llm"]["modelo_pequeno"], prompt, Temas)
    vistos, unicos = set(), []
    for t in salida.temas:
        t = t.model_dump()
        if t["id"] not in vistos and t["id"] != "otro":
            vistos.add(t["id"])
            unicos.append(t)
    return unicos[:25]


# ---------- redacción ----------

class Porque(BaseModel):
    tema_id: str
    porque: str


class Idea(BaseModel):
    formato: str
    titulo: str
    gancho: str
    desarrollo: str


class Redaccion(BaseModel):
    explicaciones: list[Porque]
    ideas: list[Idea]


def redactar(gcfg: dict, contador, cfg: dict, top: list[dict]) -> dict:
    resumen = []
    for t in top:
        resumen.append({
            "tema_id": t["id"], "nombre": t["nombre"], "etapa": t["etapa"], "redes": t["redes"],
            "ganchos_dominantes": t["rasgos"]["gancho"], "formatos_dominantes": t["rasgos"]["formato"],
            "pct_menciona_lanzamiento": t["rasgos"]["menciona_lanzamiento"],
            "ejemplos": [p["titulo"] for p in t["top_piezas"][:4]],
        })
    marca = cfg.get("marca_descripcion", "30X, a Latin American company that teaches AI and business skills to leaders")
    prompt = f"""You write content for {marca}.
Audience: {cfg['persona']}

These are this week's top trending topics, already ranked by code. For each, data says which hooks,
formats and networks it is working on. Write in Spanish (neutral Latin American).

1. explicaciones: for each topic, one line (max 25 words) explaining WHY it is working, based only on
   the data given (stage, hooks, formats, networks, launch mentions). No hype, no raw decimal numbers, and do
   not start with the stage name; lead with the insight a content strategist would act on.
2. ideas: exactly 3 content ideas about the #1 topic ("{top[0]['nombre']}"): one carrusel de
   Instagram, one reel/TikTok, one post de LinkedIn. Each with titulo, gancho (first line or first 3
   seconds) and desarrollo (3-5 sentences describing the content), adapted to the audience above.

Return JSON like {{"explicaciones": [{{"tema_id": "...", "porque": "..."}}], "ideas": [{{"formato": "...", "titulo": "...", "gancho": "...", "desarrollo": "..."}}]}}

Data:
{json.dumps(resumen, ensure_ascii=False, indent=1)}"""
    salida = _json(gcfg, contador, "llm_redaccion", gcfg["llm"]["modelo_grande"], prompt, Redaccion)
    return {"porque": {e.tema_id: e.porque for e in salida.explicaciones},
            "ideas": [i.model_dump() for i in salida.ideas]}


# ---------- lo que viene: re-identificación de tendencias ----------

class Prediccion(BaseModel):
    nombre: str
    tesis: str
    basado_en: list[str]
    senal_a_vigilar: str
    ventana: str
    que_publicar_hoy: str


class Predicciones(BaseModel):
    predicciones: list[Prediccion]


def predecir(gcfg: dict, contador, cfg: dict, temas: list[dict]) -> list[dict]:
    """Propone temas que todavía no son tendencia pero podrían serlo, combinando las tendencias de hoy
    con las señales tempranas (temas emergentes, poco volumen, aceleración alta)."""
    datos = []
    for t in temas[:20]:
        datos.append({
            "tema_id": t["id"], "nombre": t["nombre"], "etapa": t["etapa"], "score": t["score"],
            "aceleracion": t["senales"]["aceleracion"], "temprano": t["senales"]["temprano"],
            "volumen": t["volumen"], "redes": list(t["redes"]),
            "origen": (t.get("rastreo") or {}).get("origen", {}).get("red") if t.get("rastreo") else None,
            "ejemplos": [p["titulo"] for p in t["top_piezas"][:3]],
        })
    prompt = f"""You are a trend analyst for {cfg.get("marca", "30X")}, which creates content for this audience: {cfg['persona']}
Sector: {cfg['nombre']}

Below are this week's topics with signals computed by code (stage, acceleration, early-signal score,
volume, networks, where each topic first appeared). Propose exactly 5 topics that are NOT yet a big trend
but are likely to become one in the next 1-3 weeks for this audience. Good predictions:
- combine or extend current trends (e.g. a niche angle of a growing topic, or the business consequence of a tech trend),
- lean on topics with high acceleration and low volume ("emergente"), or topics that started in niche or
  technical communities (Hacker News, Reddit) and have not reached LinkedIn or Instagram yet. YouTube, TikTok,
  Instagram and LinkedIn are mainstream networks, never call them technical communities,
- are specific enough to make a post about.
Write in Spanish (neutral Latin American). Never quote raw decimal numbers from the data; describe signals in
words (e.g. "acelera más que la mayoría de los temas", "todavía con pocas publicaciones"). For each:
- nombre: short name (max 7 words)
- tesis: 1-2 sentences on why it will grow, citing the signals
- basado_en: list of tema_id values from the data that support it
- senal_a_vigilar: what concrete event or metric would confirm it
- ventana: e.g. "1-2 semanas"
- que_publicar_hoy: one concrete content idea 30X could publish today to get ahead

Return JSON like {{"predicciones": [{{"nombre": "...", "tesis": "...", "basado_en": ["..."], "senal_a_vigilar": "...", "ventana": "...", "que_publicar_hoy": "..."}}]}}

Data:
{json.dumps(datos, ensure_ascii=False, indent=1)}"""
    salida = _json(gcfg, contador, "llm_predicciones", gcfg["llm"]["modelo_grande"], prompt, Predicciones)
    validos = {t["id"] for t in temas}
    out = []
    for p in salida.predicciones:
        d = p.model_dump()
        d["basado_en"] = [b for b in d["basado_en"] if b in validos]  # solo temas reales de la corrida
        out.append(d)
    return out



# ---------- temática libre: generar la configuración de un sector nuevo ----------

class ConfigRedes(BaseModel):
    youtube_consultas: list[str]
    youtube_region: str
    subreddits: list[str]
    instagram_hashtags: list[str]
    instagram_consultas: list[str]
    linkedin_consultas: list[str]
    tiktok_consultas: list[str]
    es_tecnologico: bool
    hn_consultas: list[str]


class ConfigSector(BaseModel):
    nombre: str
    persona: str
    pista_temas: str
    pregunta_es_sector: str
    redes: ConfigRedes


def generar_sector(gcfg: dict, contador, nicho: str, audiencia: str = "") -> dict:
    """Arma la configuración de un sector a partir de un nicho libre escrito por el usuario."""
    prompt = f"""A user wants to monitor social media trends for this niche: "{nicho}".
Target audience (may be empty): "{audiencia or 'Latin American adults interested in this niche'}".
Build a configuration for a trend radar that searches YouTube, Reddit, Instagram, LinkedIn, TikTok and Hacker News.

- nombre: short Spanish name for the niche (max 6 words)
- persona: one or two English sentences describing the target audience (who they are, what they want)
- pista_temas: one English sentence on which kinds of topics matter for this audience
- pregunta_es_sector: an English statement JEV will judge as true/false for each post, like
  "The content is about specialty coffee (brewing, beans, cafés, coffee business)."
- redes.youtube_consultas: 6 search queries, mostly in Spanish, 1-2 in English, specific to the niche
- redes.youtube_region: ISO country code that best matches the audience (e.g. MX, CO, AR, ES, US)
- redes.subreddits: 5 existing, active subreddit names without "r/" (prefer large well-known ones)
- redes.instagram_hashtags: 3 popular hashtags without "#"
- redes.instagram_consultas, redes.linkedin_consultas, redes.tiktok_consultas: 3 short search queries each, in Spanish
- redes.es_tecnologico: true only if Hacker News (a tech community) is relevant to this niche
- redes.hn_consultas: 3 English queries if es_tecnologico, else an empty list

Return JSON with exactly these fields."""
    c = _json(gcfg, contador, "llm_sector", gcfg["llm"]["modelo_pequeno"], prompt, ConfigSector)
    r = c.redes
    return {
        "nombre": c.nombre.strip(),
        "nicho_libre": nicho,
        "marca": "tu marca",
        "marca_descripcion": f"a creator or brand in this niche: {nicho}",
        "persona": c.persona.strip(),
        "pista_temas": c.pista_temas.strip(),
        "pregunta_es_sector": c.pregunta_es_sector.strip(),
        "dias_ventana": 14,
        "max_piezas_por_red": 80,
        "redes": {
            "youtube": {"activa": True, "consultas": r.youtube_consultas[:8], "canales_semilla": [],
                        "region": (r.youtube_region or "MX").upper()[:2], "idioma": "es"},
            "reddit": {"activa": True, "subreddits": [s.replace("r/", "").strip("/ ") for s in r.subreddits][:6]},
            "instagram": {"activa": True, "cuentas": [], "hashtags": [h.lstrip("#") for h in r.instagram_hashtags][:3],
                          "consultas_web": r.instagram_consultas[:3]},
            "linkedin": {"activa": True, "consultas": r.linkedin_consultas[:4]},
            "tiktok": {"activa": True, "paises": ["MX", "CO", "AR", "CL", "PE"], "consultas_web": r.tiktok_consultas[:3]},
            "hn": {"activa": bool(r.es_tecnologico and r.hn_consultas), "consultas": r.hn_consultas[:4]},
        },
        "pesos": {"pieza": {"crecimiento": 0.5, "ajuste": 0.5},
                  "tema": {"fuerza": 0.35, "aceleracion": 0.20, "temprano": 0.20, "multired": 0.15, "frescura": 0.10}},
        "umbrales": {"es_sector": 0.6, "confianza_min": 0.6, "min_piezas_top": 3},
    }
