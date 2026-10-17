"""Cliente de JEV (TypeSafe System One) por HTTP: una llamada por pieza con todas las preguntas (fan-out)."""
import hashlib
import json
import time
from statistics import mean
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .config import clave

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
SESION = requests.Session()


class ErrorJEV(Exception):
    pass


def llamar(state, preguntas: dict, modelo: str, intentos: int = 5) -> dict:
    key = clave("TYPESAFE_API_KEY")
    if not key:
        raise ErrorJEV("Falta TYPESAFE_API_KEY en .env")
    cuerpo = {"state": state, "model": modelo, "questions": preguntas}
    espera = 1.0
    for intento in range(intentos):
        resp = SESION.post(ENDPOINT, json=cuerpo, timeout=60,
                           headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 529) or resp.status_code >= 500:
            retry = resp.headers.get("retry-after")
            time.sleep(float(retry) if retry and retry.replace(".", "").isdigit() else espera)
            espera = min(espera * 2, 30)
            continue
        raise ErrorJEV(f"JEV {resp.status_code}: {resp.text[:500]}")
    raise ErrorJEV(f"JEV no respondió tras {intentos} intentos")


def confianza(respuesta: dict) -> float:
    """choice y score traen confidence; noul no, se calcula |2p - 1|."""
    if respuesta.get("type") == "noul":
        return abs(2 * float(respuesta["noul"]) - 1)
    return float(respuesta.get("confidence", 0))


# ---------- preguntas del radar ----------

GANCHOS = {
    "pregunta": "Opens with a question to the viewer",
    "dato": "Opens with a surprising fact, number or statistic",
    "contraste": "Contrast: before/after, myth vs reality, old way vs new way",
    "promesa": "Promises a concrete benefit, result or shortcut",
    "historia": "Tells a personal story, experience or case",
    "polemica": "Controversial, provocative or alarming claim",
}
FORMATOS = {
    "tutorial": "Step-by-step tutorial or how-to",
    "opinion": "Opinion, reflection or commentary",
    "noticia": "News or announcement coverage",
    "caso": "Case study or real example from a company or person",
    "demo": "Live demo or showcase of a tool",
    "lista": "List or roundup (top N, tools, tips)",
}


def preguntas_pieza(cfg: dict, temas: list[dict]) -> dict:
    persona = cfg["persona"]
    criterios_tema = {t["id"]: f"{t['nombre']}: {t['descripcion']}" for t in temas}
    criterios_tema["otro"] = "None of the topics above fits well"
    return {
        "es_sector": {"type": "noul", "instructions": cfg["pregunta_es_sector"]},
        "tema": {"type": "choice", "instructions": "Which topic best describes what this content is about?",
                 "criteria": criterios_tema},
        "gancho": {"type": "choice", "instructions": "The main hook the title or first line uses to capture attention",
                   "criteria": GANCHOS},
        "formato": {"type": "choice", "instructions": "The format of this content piece", "criteria": FORMATOS},
        "menciona_lanzamiento": {"type": "noul", "instructions":
                                 "The content mentions a specific product launch, release, announcement or news event"},
        "aplicabilidad": {"type": "score", "instructions": f"How practically applicable this is for this audience: {persona}",
                          "criteria": ["Pure theory, no practical use", "Mostly conceptual",
                                       "Some practical ideas", "Practical, needs some adaptation",
                                       "Directly applicable tomorrow by this audience"]},
        "nivel_tecnico": {"type": "score", "instructions": f"How well the technical level fits this audience: {persona}",
                          "criteria": ["Only for engineers or specialists", "Requires strong technical background",
                                       "Mixed level", "Accessible with light technical terms",
                                       "Ideal for non-technical people"]},
        "relevancia_latam": {"type": "score", "instructions": "Relevance to Latin America and Spanish-speaking audiences",
                             "criteria": ["Irrelevant to Latin America", "Generic, no regional angle",
                                          "Applies to Latin America with adaptation",
                                          "Mentions Latin America or a Spanish-speaking context",
                                          "Specific to Latin America"]},
    }


def state_pieza(fila) -> dict:
    return {"platform": fila["red"], "title": fila["titulo"] or "", "text": (fila["texto"] or "")[:3000],
            "author": fila["cuenta"] or ""}


def clasificar(con, filas, cfg: dict, temas: list[dict], gcfg: dict, contador) -> dict[str, dict]:
    """Devuelve {pieza_id: answers}. Cachea por pieza + preguntas para no pagar dos veces lo mismo."""
    con.execute("CREATE TABLE IF NOT EXISTS jev_cache (llave TEXT PRIMARY KEY, respuesta TEXT)")
    modelo = gcfg["jev"]["modelo"]
    preguntas = preguntas_pieza(cfg, temas)
    huella = hashlib.sha256(json.dumps([preguntas, modelo], sort_keys=True).encode()).hexdigest()[:16]
    resultados, pendientes = {}, []
    for f in filas:
        llave = f"{f['id']}|{huella}"
        fila = con.execute("SELECT respuesta FROM jev_cache WHERE llave=?", (llave,)).fetchone()
        if fila:
            resultados[f["id"]] = json.loads(fila["respuesta"])
        else:
            pendientes.append((llave, f))

    def una(llave, f):
        r = llamar(state_pieza(f), preguntas, modelo)
        contador.jev("jev_piezas", r.get("usage", {}))
        return llave, f["id"], r

    errores = 0
    with ThreadPoolExecutor(max_workers=gcfg["jev"]["paralelo"]) as pool:
        futuros = [pool.submit(una, ll, f) for ll, f in pendientes]
        for i, fut in enumerate(as_completed(futuros), 1):
            try:
                llave, pid, r = fut.result()
                resultados[pid] = r["answers"]
                con.execute("INSERT OR REPLACE INTO jev_cache VALUES (?,?)", (llave, json.dumps(r["answers"])))
            except ErrorJEV as e:
                errores += 1
                if errores <= 3:
                    print(f"    aviso JEV: {e}")
            if i % 25 == 0:
                print(f"    JEV: {i}/{len(pendientes)}")
    con.commit()
    print(f"  JEV: {len(pendientes) - errores} piezas nuevas clasificadas, {len(filas) - len(pendientes)} desde caché, {errores} errores")
    return resultados


def puntuar_ideas(ideas: list[dict], cfg: dict, gcfg: dict, contador) -> list[dict]:
    preguntas = {
        "ajuste_audiencia": {"type": "score", "instructions": f"How well this content idea fits this audience: {cfg['persona']}",
                             "criteria": ["Poor fit", "Weak fit", "Acceptable", "Good fit", "Excellent fit"]},
        "fuerza_gancho": {"type": "score", "instructions": "How strong the hook is at stopping the scroll",
                          "criteria": ["Weak", "Below average", "Average", "Strong", "Very strong"]},
    }
    for idea in ideas:
        try:
            r = llamar(idea, preguntas, gcfg["jev"]["modelo"])
            contador.jev("jev_ideas", r.get("usage", {}))
            a = r["answers"]
            idea["jev"] = {k: {"score": round(a[k]["score"] / 4, 3), "confianza": round(a[k]["confidence"], 3)}
                           for k in preguntas}
        except ErrorJEV as e:
            print(f"    aviso JEV ideas: {e}")
    return ideas


def puntuar_predicciones(preds: list[dict], temas: list[dict], cfg: dict, gcfg: dict, contador) -> list[dict]:
    """JEV juzga cada predicción y el código la respalda con las señales de los temas en que se basa."""
    por_id = {t["id"]: t for t in temas}
    preguntas = {
        "interes_audiencia": {"type": "score", "instructions": f"How much this audience would care about this topic: {cfg['persona']}",
                              "criteria": ["Not at all", "A little", "Somewhat", "A lot", "It's a must-know for them"]},
        "novedad": {"type": "score", "instructions": "How new or not-yet-mainstream this topic is",
                    "criteria": ["Already everywhere", "Widely known", "Known in niche circles", "Emerging", "Very early, almost unknown"]},
        "concreta": {"type": "noul", "instructions": "The prediction is specific and testable, not a vague generality"},
    }
    for p in preds:
        base = [por_id[b] for b in p["basado_en"] if b in por_id]
        respaldo = mean([0.6 * t["senales"]["aceleracion"] + 0.4 * t["senales"]["temprano"] for t in base]) if base else 0.0
        p["respaldo_datos"] = round(respaldo, 3)
        try:
            r = llamar({"prediction": p["nombre"], "thesis": p["tesis"], "signal_to_watch": p["senal_a_vigilar"]},
                       preguntas, gcfg["jev"]["modelo"])
            contador.jev("jev_predicciones", r.get("usage", {}))
            a = r["answers"]
            p["jev"] = {"interes_audiencia": round(a["interes_audiencia"]["score"] / 4, 3),
                        "novedad": round(a["novedad"]["score"] / 4, 3),
                        "concreta": round(a["concreta"]["noul"], 3)}
            p["fuerza"] = round(0.4 * respaldo + 0.3 * p["jev"]["interes_audiencia"] + 0.2 * p["jev"]["novedad"]
                                + 0.1 * p["jev"]["concreta"], 3)
        except ErrorJEV as e:
            print(f"    aviso JEV predicciones: {e}")
            p["fuerza"] = round(respaldo, 3)
    return sorted(preds, key=lambda p: p["fuerza"], reverse=True)
