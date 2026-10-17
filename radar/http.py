"""GET con caché en disco para no gastar cuota de APIs durante el desarrollo."""
import hashlib
import json
import re
import time

import requests

from .config import DIR_DATA

DIR_CACHE = DIR_DATA / "cache"
SESION = requests.Session()


def get_json(url: str, params: dict | None = None, headers: dict | None = None,
             ttl: float = 3600, auth=None) -> dict:
    """ttl en segundos; ttl=0 desactiva la caché (capturas de métricas)."""
    params = params or {}
    llave_cache = hashlib.sha256(json.dumps([url, sorted(params.items())], default=str).encode()).hexdigest()[:32]
    ruta = DIR_CACHE / f"{llave_cache}.json"
    if ttl and ruta.exists() and time.time() - ruta.stat().st_mtime < ttl:
        return json.loads(ruta.read_text(encoding="utf-8"))
    resp = SESION.get(url, params=params, headers=headers, timeout=30, auth=auth)
    _verificar(resp)
    datos = resp.json()
    if ttl:
        DIR_CACHE.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(datos), encoding="utf-8")
    return datos


def get_texto(url: str, headers: dict | None = None, ttl: float = 3600) -> str:
    llave_cache = hashlib.sha256(url.encode()).hexdigest()[:32]
    ruta = DIR_CACHE / f"{llave_cache}.txt"
    if ttl and ruta.exists() and time.time() - ruta.stat().st_mtime < ttl:
        return ruta.read_text(encoding="utf-8")
    resp = SESION.get(url, headers=headers, timeout=30)
    _verificar(resp)
    if ttl:
        DIR_CACHE.mkdir(parents=True, exist_ok=True)
        ruta.write_text(resp.text, encoding="utf-8")
    return resp.text


def _verificar(resp: requests.Response):
    """Como raise_for_status, pero sin claves en el mensaje y con el motivo que da la API."""
    if resp.ok:
        return
    url = re.sub(r"(key|access_token|api_key)=[^&]+", r"\1=***", resp.url)
    motivo = ""
    try:
        err = resp.json().get("error", {})
        motivo = err.get("message", "") if isinstance(err, dict) else str(err)
    except ValueError:
        pass
    raise requests.HTTPError(f"{resp.status_code} en {url.split('?')[0]}: {motivo[:200]}", response=resp)
