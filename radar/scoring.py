"""Métricas, score por pieza y por tema, y etapa. Todo en código: el LLM no participa del ranking."""
import json
import time
from collections import Counter, defaultdict
from statistics import mean
from urllib.parse import urlsplit

from .db import capturas, referencia
from .jev import confianza

REDES_PRINCIPALES = ["youtube", "reddit", "instagram", "linkedin", "tiktok"]
NIVELES_SCORE = 4  # niveles 0..4


def percentiles(valores: dict[str, float]) -> dict[str, float]:
    """Rango percentil 0..1 (empates promediados). Un solo valor recibe 0.5."""
    if not valores:
        return {}
    if len(valores) == 1:
        return {k: 0.5 for k in valores}
    orden = sorted(valores.items(), key=lambda kv: kv[1])
    salida, i = {}, 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and orden[j + 1][1] == orden[i][1]:
            j += 1
        rango = (i + j) / 2 / (len(orden) - 1)
        for k in range(i, j + 1):
            salida[orden[k][0]] = rango
        i = j + 1
    return salida


def metricas_pieza(con, fila, ahora: float) -> dict:
    caps = capturas(con, fila["id"])
    m = {"metrica": None, "velocidad": None, "outlier": None, "aceleracion": None, "capturas": len(caps)}
    if not caps or not fila["publicado"]:
        return m
    ultima = caps[-1]
    edad_h = max(1.0, (ultima["ts"] - fila["publicado"]) / 3600)
    m["metrica"] = ultima["metrica"]
    m["velocidad"] = ultima["metrica"] / edad_h
    ref = referencia(con, fila["grupo"])
    if ref and ref > 0:
        m["outlier"] = ultima["metrica"] / ref
    if len(caps) >= 2:
        previa = next((c for c in reversed(caps[:-1]) if ultima["ts"] - c["ts"] >= 1800), None)
        if previa:
            v_reciente = (ultima["metrica"] - previa["metrica"]) / ((ultima["ts"] - previa["ts"]) / 3600)
            m["aceleracion"] = v_reciente / max(m["velocidad"], 1e-6)
    return m


def calcular(con, filas, respuestas: dict, temas: list[dict], cfg: dict) -> dict:
    ahora = time.time()
    umbral_sector = cfg["umbrales"]["es_sector"]
    conf_min = cfg["umbrales"]["confianza_min"]
    conf_tema = cfg["umbrales"].get("confianza_tema", 0.35)
    w_pieza, w_tema = cfg["pesos"]["pieza"], cfg["pesos"]["tema"]

    # 1. Filtrar y medir piezas
    piezas, descartadas, baja_conf, sin_tema = [], 0, 0, 0
    for f in filas:
        a = respuestas.get(f["id"])
        if not a:
            continue
        if a["es_sector"]["noul"] < umbral_sector:
            descartadas += 1
            continue
        if confianza(a["es_sector"]) < conf_min or confianza(a["tema"]) < conf_tema:
            baja_conf += 1
            continue
        if a["tema"]["choice"] == "otro":
            sin_tema += 1
            continue
        p = {"id": f["id"], "red": f["red"], "url": f["url"], "titulo": f["titulo"], "cuenta": f["cuenta"],
             "link_externo": _link_externo(f),
             "publicado": f["publicado"], "via": f["via"], "tema": a["tema"]["choice"],
             "gancho": a["gancho"]["choice"], "formato": a["formato"]["choice"],
             "menciona_lanzamiento": a["menciona_lanzamiento"]["noul"],
             "ajuste": mean(a[k]["score"] for k in ("aplicabilidad", "nivel_tecnico", "relevancia_latam")) / NIVELES_SCORE,
             "confianza_tema": round(confianza(a["tema"]), 3)}
        p.update(metricas_pieza(con, f, ahora))
        piezas.append(p)

    # 2. Percentiles dentro de cada red
    for red in {p["red"] for p in piezas}:
        de_red = [p for p in piezas if p["red"] == red]
        for campo in ("velocidad", "outlier", "aceleracion"):
            pct = percentiles({p["id"]: p[campo] for p in de_red if p[campo] is not None})
            for p in de_red:
                p[f"pct_{campo}"] = pct.get(p["id"])
    # TikTok: aceleración por mejora de posición del hashtag
    tags = {p["id"]: _mejora_hashtag(con, p) for p in piezas if p["id"].startswith("tiktok:#")}
    pct_tags = percentiles({k: v for k, v in tags.items() if v is not None})
    for p in piezas:
        if p["id"] in pct_tags:
            p["pct_aceleracion"] = pct_tags[p["id"]]

    for p in piezas:
        p["con_metricas"] = p["pct_velocidad"] is not None
        if p["con_metricas"]:
            outl = p["pct_outlier"] if p["pct_outlier"] is not None else p["pct_velocidad"]
            p["crecimiento"] = 0.5 * p["pct_velocidad"] + 0.5 * outl
            p["score"] = w_pieza["crecimiento"] * p["crecimiento"] + w_pieza["ajuste"] * p["ajuste"]
        else:
            p["crecimiento"] = None
            p["score"] = p["ajuste"]

    # 3. Agregar por tema
    por_tema = defaultdict(list)
    for p in piezas:
        por_tema[p["tema"]].append(p)
    info = {t["id"]: t for t in temas}
    hace7, hace14 = ahora - 7 * 86400, ahora - 14 * 86400
    crudo = {}
    for tid, ps in por_tema.items():
        if tid not in info:
            continue
        con_m = sorted((p for p in ps if p["con_metricas"]), key=lambda p: p["score"], reverse=True)
        acels = [p["pct_aceleracion"] for p in ps if p.get("pct_aceleracion") is not None]
        estimada = not acels
        if estimada:  # sin capturas repetidas: la velocidad hace de proxy
            acels = [p["pct_velocidad"] for p in con_m]
        recientes = [p for p in ps if p["publicado"] and p["publicado"] >= hace7]
        previas = [p for p in ps if p["publicado"] and hace14 <= p["publicado"] < hace7]
        crudo[tid] = {
            "fuerza": mean(p["score"] for p in con_m[:3]) if con_m else 0.0,
            "aceleracion": mean(acels) if acels else 0.0,
            "aceleracion_estimada": estimada,
            "volumen": len(ps),
            "cuentas_7d": len({p["cuenta"] for p in recientes if p["cuenta"]}) or len(recientes),
            "multired": len({p["red"] for p in ps if p["red"] in REDES_PRINCIPALES}) / len(REDES_PRINCIPALES),
            "piezas_7d": len(recientes), "piezas_7d_previos": len(previas),
        }
    pct_vol = percentiles({k: v["volumen"] for k, v in crudo.items()})
    pct_sat = percentiles({k: v["cuentas_7d"] for k, v in crudo.items()})
    # la aceleración se compara entre temas: así las etapas reflejan quién acelera más que el resto
    pct_acel = percentiles({k: v["aceleracion"] for k, v in crudo.items()})

    resultado = []
    for tid, c in crudo.items():
        ps = por_tema[tid]
        senales = {
            "fuerza": round(c["fuerza"], 4),
            "aceleracion": round(pct_acel[tid], 4),
            "temprano": round(pct_acel[tid] * (1 - pct_vol[tid]), 4),
            "multired": round(c["multired"], 4),
            "frescura": round(1 - pct_sat[tid], 4),
        }
        score = sum(w_tema[k] * senales[k] for k in w_tema)
        temprana = min((p for p in ps if p["publicado"]), key=lambda p: p["publicado"], default=None)
        resultado.append({
            "id": tid, "nombre": info[tid]["nombre"], "descripcion": info[tid]["descripcion"],
            "score": round(score, 4), "senales": senales,
            "aceleracion_estimada": c["aceleracion_estimada"],
            "etapa": etapa(pct_acel[tid], pct_vol[tid], pct_sat[tid]),
            "volumen": c["volumen"], "piezas_7d": c["piezas_7d"], "piezas_7d_previos": c["piezas_7d_previos"],
            "redes": dict(Counter(p["red"] for p in ps)),
            "rasgos": {
                "gancho": _top(Counter(p["gancho"] for p in ps), len(ps)),
                "formato": _top(Counter(p["formato"] for p in ps), len(ps)),
                "menciona_lanzamiento": round(sum(p["menciona_lanzamiento"] > 0.5 for p in ps) / len(ps), 2),
            },
            "pieza_temprana": _resumen(temprana) if temprana else None,
            "rastreo": rastrear(ps, ahora),
            "top_piezas": [_resumen(p) for p in sorted(ps, key=lambda p: p["score"], reverse=True)[:6]],
        })
    # un tema con 1 o 2 piezas puede ser casualidad: queda como señal temprana, detrás de los temas con respaldo
    min_piezas = cfg["umbrales"].get("min_piezas_top", 3)
    for t in resultado:
        t["senal_temprana"] = t["volumen"] < min_piezas
    resultado.sort(key=lambda t: (not t["senal_temprana"], t["score"]), reverse=True)
    ganchos = resumen_ganchos([p for p in piezas if p["tema"] in {t["id"] for t in resultado[:10]}])
    cobertura = {}
    for f in filas:
        d = cobertura.setdefault(f["red"], {"recolectadas": 0, "en_ranking": 0, "con_metricas": 0, "vias": set()})
        d["recolectadas"] += 1
        d["vias"].add(f["via"])
    for p in piezas:
        cobertura[p["red"]]["en_ranking"] += 1
        cobertura[p["red"]]["con_metricas"] += int(p["con_metricas"])
    for d in cobertura.values():
        d["vias"] = sorted(d["vias"])
    return {"temas": resultado, "cobertura": cobertura, "ganchos": ganchos,
            "conteos": {"recolectadas": len(filas), "clasificadas": len(respuestas), "en_ranking": len(piezas),
                        "fuera_de_sector": descartadas, "baja_confianza": baja_conf,
                        "sin_tema": sin_tema}}


def resumen_ganchos(piezas: list[dict]) -> list[dict]:
    """Por gancho: qué parte de las piezas del top 10 lo usa y cuánto crecen frente al promedio."""
    if not piezas:
        return []
    con_m = [p for p in piezas if p.get("crecimiento") is not None]
    media = mean(p["crecimiento"] for p in con_m) if con_m else None
    salida = []
    for g, n in Counter(p["gancho"] for p in piezas).most_common():
        crec = [p["crecimiento"] for p in con_m if p["gancho"] == g]
        mejor = max((p for p in piezas if p["gancho"] == g), key=lambda p: p["score"])
        salida.append({
            "gancho": g, "piezas": n, "pct": round(n / len(piezas), 3),
            "crecimiento_vs_media": round(mean(crec) / media - 1, 3) if crec and media else None,
            "ejemplo": {"titulo": mejor["titulo"], "url": mejor["url"], "red": mejor["red"]},
        })
    return sorted(salida, key=lambda g: (g["crecimiento_vs_media"] is None, -(g["crecimiento_vs_media"] or 0)))


def etapa(acel: float, pct_vol: float, pct_sat: float) -> str:
    if acel >= 0.6 and pct_vol < 0.5 and pct_sat < 0.5:
        return "emergente"
    if acel >= 0.6:
        return "creciendo"
    if acel < 0.4 and pct_sat >= 0.6:
        return "saturado"
    return "pico"


def _mejora_hashtag(con, p) -> float | None:
    tag = p["id"].split("#", 1)[1]
    filas = con.execute("SELECT fecha, MIN(posicion) AS pos FROM hashtags_tiktok WHERE hashtag=? GROUP BY fecha ORDER BY fecha",
                        (tag,)).fetchall()
    if len(filas) < 2:
        return None
    return float(filas[0]["pos"] - filas[-1]["pos"])


def _top(contador: Counter, total: int) -> list[dict]:
    return [{"valor": k, "pct": round(v / total, 2)} for k, v in contador.most_common(2)]


DOMINIOS_REDES = ("youtube.com", "youtu.be", "reddit.com", "redd.it", "instagram.com", "linkedin.com",
                  "tiktok.com", "ycombinator.com", "x.com", "twitter.com")


def _link_externo(f) -> str | None:
    """Fuente citada por la pieza: el link de un hilo de Hacker News o de un post de Reddit."""
    url = None
    if f["red"] == "hn" and (f["texto"] or "").startswith("http"):
        url = f["texto"]
    elif f["red"] == "reddit":
        url = json.loads(f["extra"] or "{}").get("link")
    if not url or any(d in url for d in DOMINIOS_REDES):
        return None
    return url


def rastrear(ps: list[dict], ahora: float) -> dict:
    """Origen y propagación del tema: primera aparición en cada red y fuentes externas más citadas."""
    con_fecha = sorted((p for p in ps if p["publicado"]), key=lambda p: p["publicado"])
    ruta, vistas = [], set()
    for p in con_fecha:
        if p["red"] not in vistas:
            vistas.add(p["red"])
            ruta.append({"red": p["red"], "fecha": p["publicado"], "url": p["url"], "titulo": p["titulo"],
                         "cuenta": p["cuenta"]})
    citas = Counter()
    ejemplo = {}
    for p in ps:
        if p.get("link_externo"):
            dominio = urlsplit(p["link_externo"]).netloc.replace("www.", "")
            citas[dominio] += 1
            ejemplo.setdefault(dominio, p["link_externo"])
    fuentes = [{"dominio": d, "veces": n, "url": ejemplo[d]} for d, n in citas.most_common(3)]
    origen = ruta[0] if ruta else None
    return {
        "origen": origen,
        "ruta": ruta,
        "fuentes_externas": fuentes,
        "dias_activo": round((ahora - origen["fecha"]) / 86400, 1) if origen else None,
        "horas_entre_redes": [round((b["fecha"] - a["fecha"]) / 3600, 1) for a, b in zip(ruta, ruta[1:])],
    }


def _resumen(p: dict) -> dict:
    return {k: p.get(k) for k in ("red", "url", "titulo", "cuenta", "publicado", "via", "metrica",
                                    "gancho", "formato", "score", "ajuste", "con_metricas")}
