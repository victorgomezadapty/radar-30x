"""Orquestación: recolectar, capturar métricas y correr el radar completo."""
import json
import time
from datetime import datetime, timezone

from . import jev, llm, scoring
from .config import DIR_CONFIG, DIR_OUT, DIR_WEB, cargar_global, cargar_sector, red_activa
from .connectors import hn, instagram, linkedin, reddit, tiktok, youtube
from .costos import Contador
from .db import conectar, guardar_piezas, piezas_sector
from .estado import REDES, estado_redes



def _redes(cfg: dict, redes: list[str] | None) -> list[str]:
    return [r for r in REDES if red_activa(cfg, r) and (not redes or r in redes)]


def recolectar(sector: str, contador: Contador | None = None, redes: list[str] | None = None) -> dict:
    cfg, gcfg = cargar_sector(sector), cargar_global()
    contador = contador or Contador(gcfg)
    con = conectar()
    print(f"Recolectando '{sector}'...")
    pasos = {
        "youtube": lambda: youtube.recolectar(cfg, con),
        "reddit": lambda: reddit.recolectar(cfg, con),
        "instagram": lambda: instagram.recolectar(cfg, gcfg, contador, con),
        "linkedin": lambda: linkedin.recolectar(cfg, gcfg, contador),
        "tiktok": lambda: tiktok.recolectar(cfg, gcfg, contador, con),
        "hn": lambda: hn.recolectar(cfg, con),
    }
    totales = {}
    for red in _redes(cfg, redes):
        try:  # una red caída no frena la corrida
            totales[red] = guardar_piezas(con, sector, pasos[red]())
        except Exception as e:
            print(f"  {red}: ERROR {type(e).__name__}: {e}")
            totales[red] = 0
    return totales


def capturar(sector: str) -> dict:
    con = conectar()
    return {"youtube": youtube.capturar(con, sector), "reddit": reddit.capturar(con, sector)}


def correr(sector: str, con_recoleccion: bool = True, redes: list[str] | None = None) -> dict:
    inicio = time.time()
    cfg, gcfg = cargar_sector(sector), cargar_global()
    contador = Contador(gcfg)
    elegidas = _redes(cfg, redes)
    print(f"PASO 1/6 Recolección ({', '.join(elegidas)})")
    if con_recoleccion:
        recolectar(sector, contador, elegidas)
    con = conectar()
    filas = [f for f in piezas_sector(con, sector, time.time() - cfg["dias_ventana"] * 86400) if f["red"] in elegidas]
    if not filas:
        raise SystemExit("No hay piezas recolectadas para esas redes. Revisa las claves en .env y corre 'recolectar'.")
    print(f"  Piezas en la ventana: {len(filas)}")

    previo = _leer_salida(sector)
    print("PASO 2/6 Temas de la corrida (LLM)")
    temas = llm.proponer_temas(gcfg, contador, cfg, [f["titulo"] for f in filas if f["titulo"]],
                               previo.get("temas_corrida", []) if previo else [])
    print(f"  {len(temas)} temas")

    print(f"PASO 3/6 Clasificación con JEV ({len(filas)} piezas)")
    respuestas = jev.clasificar(con, filas, cfg, temas, gcfg, contador)

    print("PASO 4/6 Score, etapas y rastreo de la fuente (código)")
    res = scoring.calcular(con, filas, respuestas, temas, cfg)
    top = res["temas"][:10]

    redaccion, predicciones = {"porque": {}, "ideas": []}, []
    if top:
        print("PASO 5/6 Explicaciones e ideas para 30X (LLM + JEV)")
        redaccion = llm.redactar(gcfg, contador, cfg, top)
        redaccion["ideas"] = jev.puntuar_ideas(redaccion["ideas"], cfg, gcfg, contador)
        print("PASO 6/6 Lo que viene: posibles próximas tendencias (LLM + JEV)")
        try:
            predicciones = jev.puntuar_predicciones(llm.predecir(gcfg, contador, cfg, res["temas"]),
                                                    res["temas"], cfg, gcfg, contador)
        except Exception as e:  # la predicción es un extra: si falla, el ranking sigue sirviendo
            print(f"  aviso: predicciones fallaron: {e}")
    for t in res["temas"]:
        t["porque"] = redaccion["porque"].get(t["id"])
    # posición en la corrida anterior, para mostrar si el tema sube, baja o es nuevo
    anterior = {}
    if previo:
        for i, t in enumerate(previo.get("temas", [])[:20], 1):
            anterior.setdefault(t["id"], i)
            anterior.setdefault(t["nombre"].strip().lower(), i)
    for t in res["temas"]:
        t["rank_anterior"] = anterior.get(t["id"]) or anterior.get(t["nombre"].strip().lower())

    costo = contador.resumen()
    if costo["modelos_sin_precio"]:
        print(f"  aviso: sin precio en config/global.yaml para {costo['modelos_sin_precio']}; su costo no se sumó")
    salida = {
        "sector": sector, "nombre": cfg["nombre"], "redes_elegidas": elegidas,
        "marca": cfg.get("marca", "30X"), "nicho_libre": cfg.get("nicho_libre"),
        "corrida_anterior": previo.get("generado") if previo else None, "ganchos": res.get("ganchos", []),
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duracion_s": round(time.time() - inicio, 1),
        "modelo_jev": gcfg["jev"]["modelo"],
        "modelos_llm": [gcfg["llm"]["modelo_pequeno"], gcfg["llm"]["modelo_grande"]],
        "pesos": cfg["pesos"]["tema"],
        "temas": res["temas"], "ideas": redaccion["ideas"], "predicciones": predicciones,
        "cobertura": res["cobertura"], "conteos": res["conteos"], "costo": costo, "temas_corrida": temas,
    }
    salida["costo"]["por_tema_usd"] = round(costo["total_usd"] / max(1, len(top)), 5)
    salida["costo"]["por_pieza_usd"] = round(costo["total_usd"] / max(1, len(filas)), 6)
    salida["costo"]["historial"] = historial_costos(sector) + [{"generado": salida["generado"], "usd": costo["total_usd"],
                                                                "piezas": len(filas)}]
    _escribir_salida(sector, salida)
    c = salida["costo"]
    print(f"\nListo en {salida['duracion_s']} s. Costo: ${c['total_usd']} (JEV ${c['jev_usd']}, {c['proveedor_llm']} ${c['llm_usd']})")
    for i, t in enumerate(top, 1):
        print(f"  {i:2}. [{t['etapa']:9}] {t['nombre']}  score={t['score']:.3f}  redes={','.join(t['redes'])}")
    return salida


def crear_sector(sector: str, nicho: str, audiencia: str = "") -> dict:
    """Temática libre: genera la configuración con el LLM y la guarda como config/<sector>.yaml."""
    import yaml
    gcfg = cargar_global()
    cfg = llm.generar_sector(gcfg, Contador(gcfg), nicho, audiencia)
    cfg["sector"] = sector
    (DIR_CONFIG / f"{sector}.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Sector '{sector}' creado para el nicho: {nicho}")
    print(f"  YouTube: {cfg['redes']['youtube']['consultas']}")
    print(f"  Reddit: {cfg['redes']['reddit']['subreddits']}")
    return cfg


def historial_costos(sector: str) -> list[dict]:
    carpeta = DIR_OUT / "historial"
    salida = []
    for ruta in sorted(carpeta.glob(f"{sector}_*.json")) if carpeta.exists() else []:
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
            salida.append({"generado": d["generado"], "usd": d["costo"]["total_usd"],
                           "piezas": d["conteos"]["recolectadas"]})
        except (KeyError, ValueError):
            continue
    return salida


def _leer_salida(sector: str) -> dict | None:
    ruta = DIR_OUT / f"{sector}.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def _escribir_salida(sector: str, salida: dict):
    DIR_OUT.mkdir(exist_ok=True)
    (DIR_OUT / f"{sector}.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    sello = datetime.now().strftime("%Y%m%d_%H%M")
    (DIR_OUT / "historial").mkdir(exist_ok=True)
    (DIR_OUT / "historial" / f"{sector}_{sello}.json").write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    publicar_panel()


def publicar_panel():
    """Junta todas las corridas en web/data.js para que el panel abra sin servidor."""
    datos = {}
    for ruta in sorted(DIR_OUT.glob("*.json")):  # las copias con fecha viven en out/historial/
        datos[ruta.stem] = json.loads(ruta.read_text(encoding="utf-8"))
    DIR_WEB.mkdir(exist_ok=True)
    (DIR_WEB / "data.js").write_text("window.RADAR_DATA = " + json.dumps(datos, ensure_ascii=False) + ";\n",
                                     encoding="utf-8")
    # modo remoto (Vercel): la app lee estos archivos en vez de la API local
    (DIR_WEB / "datos.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    sectores = []
    for ruta in sorted(DIR_CONFIG.glob("*.yaml")):
        if ruta.stem != "global":
            cfg = cargar_sector(ruta.stem)
            sectores.append({"id": ruta.stem, "nombre": cfg["nombre"], "redes": estado_redes(cfg)})
    (DIR_WEB / "sectores.json").write_text(json.dumps(sectores, ensure_ascii=False), encoding="utf-8")
