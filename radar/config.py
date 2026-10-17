"""Carga de configuración: sector (YAML), ajustes globales y claves del .env."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
DIR_CONFIG = RAIZ / "config"
DIR_DATA = RAIZ / "data"
DIR_OUT = RAIZ / "out"
DIR_WEB = RAIZ / "web"

load_dotenv(RAIZ / ".env")


def clave(nombre: str) -> str | None:
    valor = os.getenv(nombre, "").strip()
    return valor or None


def cargar_global() -> dict:
    with open(DIR_CONFIG / "global.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def cargar_sector(sector: str) -> dict:
    ruta = DIR_CONFIG / f"{sector}.yaml"
    if not ruta.exists():
        disponibles = [p.stem for p in DIR_CONFIG.glob("*.yaml") if p.stem != "global"]
        raise SystemExit(f"No existe la configuración '{sector}'. Disponibles: {', '.join(disponibles)}")
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def red_activa(cfg: dict, red: str) -> bool:
    return bool(cfg.get("redes", {}).get(red, {}).get("activa"))
