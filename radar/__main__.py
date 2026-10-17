"""Uso:
  python -m radar probar                       # verifica cada clave del .env con una llamada mínima
  python -m radar recolectar --sector ia_latam # trae piezas de las redes y guarda la primera captura
  python -m radar capturar --sector ia_latam [--cada 3]   # nueva captura de métricas (en bucle cada N horas)
  python -m radar correr --sector ia_latam [--sin-recolectar]
  python -m radar panel                        # regenera web/data.js con las corridas guardadas
  python -m radar servir [--puerto 8765]       # app web: inicio, elegir redes, correr y ver resultados
  Opcional en correr/recolectar: --redes youtube,reddit,linkedin
"""
import argparse
import sys
import time

from . import pipeline


def probar():
    from .config import clave, cargar_global
    from .http import get_json
    gcfg = cargar_global()
    print("TypeSafe (JEV):", end=" ")
    try:
        from .jev import llamar
        r = llamar("Probando el radar de 30X", {"ok": {"type": "noul", "instructions": "This text is in Spanish"}},
                   gcfg["jev"]["modelo"])
        print(f"OK ({r['model']}, noul={r['answers']['ok']['noul']:.2f})")
    except Exception as e:
        print(f"FALLA: {e}")
    print("YouTube:", end=" ")
    try:
        k = clave("YOUTUBE_API_KEY")
        if not k:
            raise RuntimeError("falta YOUTUBE_API_KEY")
        get_json("https://www.googleapis.com/youtube/v3/videos", {"part": "id", "id": "dQw4w9WgXcQ", "key": k}, ttl=0)
        print("OK")
    except Exception as e:
        print(f"FALLA: {e}")
    print("DeepSeek:", end=" ")
    try:
        if not clave("DEEPSEEK_API_KEY"):
            raise RuntimeError("falta DEEPSEEK_API_KEY")
        from .llm import cliente
        disponibles = {m.id for m in cliente(gcfg).models.list()}
        faltan = [m for m in (gcfg["llm"]["modelo_pequeno"], gcfg["llm"]["modelo_grande"]) if m not in disponibles]
        r = cliente(gcfg).chat.completions.create(model=gcfg["llm"]["modelo_pequeno"], max_tokens=5,
                                                  messages=[{"role": "user", "content": "Responde solo: ok"}])
        print(f"OK ({r.model})" + (f"; modelos no disponibles: {faltan}, disponibles: {sorted(disponibles)}" if faltan else ""))
    except Exception as e:
        print(f"FALLA: {e}")
    print("Tavily (búsqueda web):", end=" ")
    try:
        import requests
        k = clave("TAVILY_API_KEY")
        if not k:
            raise RuntimeError("falta TAVILY_API_KEY (LinkedIn, TikTok e Instagram quedarán solo con la comunidad)")
        r = requests.post("https://api.tavily.com/search", headers={"Authorization": f"Bearer {k}"}, timeout=30,
                          json={"api_key": k, "query": "inteligencia artificial", "max_results": 1})
        r.raise_for_status()
        print("OK")
    except Exception as e:
        print(f"FALLA: {e}")
    print("Reddit:", end=" ")
    try:
        from .connectors.reddit import _oauth
        print("OK (API)" if _oauth() else "sin claves, se usará RSS")
    except Exception as e:
        print(f"FALLA: {e} (se usará RSS)")
    print("Instagram:", "Graph API configurada" if clave("IG_USER_ID") and clave("IG_ACCESS_TOKEN")
          else "sin claves, se usará búsqueda web")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="radar")
    ap.add_argument("comando", choices=["probar", "recolectar", "capturar", "correr", "panel", "servir"])
    ap.add_argument("--sector", default="ia_latam")
    ap.add_argument("--cada", type=float, default=0, help="horas entre capturas (bucle)")
    ap.add_argument("--sin-recolectar", action="store_true")
    ap.add_argument("--redes", default="", help="lista separada por comas; vacío = todas las activas")
    ap.add_argument("--puerto", type=int, default=8765)
    a = ap.parse_args()
    redes = [r.strip() for r in a.redes.split(",") if r.strip()] or None
    if a.comando == "probar":
        probar()
    elif a.comando == "recolectar":
        print(pipeline.recolectar(a.sector, redes=redes))
    elif a.comando == "capturar":
        while True:
            print(time.strftime("%H:%M"), "captura:", pipeline.capturar(a.sector))
            if not a.cada:
                break
            time.sleep(a.cada * 3600)
    elif a.comando == "correr":
        pipeline.correr(a.sector, con_recoleccion=not a.sin_recolectar, redes=redes)
    elif a.comando == "servir":
        from .servidor import servir
        servir(a.puerto)
    elif a.comando == "panel":
        pipeline.publicar_panel()
        print("web/data.js actualizado")


if __name__ == "__main__":
    main()
