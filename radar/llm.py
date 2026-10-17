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
    prompt = f"""You write for 30X, a Latin American company that teaches AI and business skills to leaders.
Audience: {cfg['persona']}

These are this week's top trending topics, already ranked by code. For each, data says which hooks,
formats and networks it is working on. Write in Spanish (neutral Latin American).

1. explicaciones: for each topic, one line (max 25 words) explaining WHY it is working, based only on
   the data given (stage, hooks, formats, networks, launch mentions). No hype, no raw decimal numbers, and do
   not start with the stage name; lead with the insight a content strategist would act on.
2. ideas: exactly 3 content ideas for 30X about the #1 topic ("{top[0]['nombre']}"): one carrusel de
   Instagram, one reel/TikTok, one post de LinkedIn. Each with titulo, gancho (first line or first 3
   seconds) and desarrollo (3-5 sentences describing the content), adapted to Latin American leaders.

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
    prompt = f"""You are a trend analyst for 30X, which creates content for this audience: {cfg['persona']}
Sector: {cfg['nombre']}

Below are this week's topics with signals computed by code (stage, acceleration, early-signal score,
volume, networks, where each topic first appeared). Propose exactly 5 topics that are NOT yet a big trend
but are likely to become one in the next 1-3 weeks for this audience. Good predictions:
- combine or extend current trends (e.g. a niche angle of a growing topic, or the business consequence of a tech trend),
- lean on topics with high acceleration and low volume ("emergente"), or topics that started in technical
  communities (Hacker News, Reddit) and have not reached LinkedIn or Instagram yet,
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
