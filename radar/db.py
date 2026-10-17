"""Almacenamiento en SQLite: piezas, capturas de métricas y hashtags de TikTok."""
import json
import sqlite3
import time
from dataclasses import dataclass, field

from .config import DIR_DATA

ESQUEMA = """
CREATE TABLE IF NOT EXISTS piezas (
    id TEXT PRIMARY KEY,          -- red:id_nativo
    sector TEXT NOT NULL,
    red TEXT NOT NULL,
    url TEXT,
    titulo TEXT,
    texto TEXT,
    cuenta TEXT,                  -- cuenta pública (nombre de canal, usuario, subreddit)
    grupo TEXT,                   -- referencia para outlier: canal, subreddit, cuenta o hashtag
    publicado REAL,               -- epoch segundos
    via TEXT,                     -- api, rss, busqueda_web, manual
    extra TEXT,                   -- JSON libre
    creado REAL
);
CREATE TABLE IF NOT EXISTS capturas (
    pieza_id TEXT NOT NULL,
    ts REAL NOT NULL,
    metrica REAL NOT NULL,        -- vistas (YouTube), score (Reddit/HN), likes+comentarios (Instagram)
    likes REAL,
    comentarios REAL,
    PRIMARY KEY (pieza_id, ts)
);
CREATE TABLE IF NOT EXISTS referencia (
    grupo TEXT PRIMARY KEY,       -- mediana de la métrica en el grupo (para outlier ratio)
    mediana REAL,
    ts REAL
);
CREATE TABLE IF NOT EXISTS hashtags_tiktok (
    fecha TEXT NOT NULL,
    pais TEXT NOT NULL,
    hashtag TEXT NOT NULL,
    posicion INTEGER NOT NULL,
    publicaciones REAL,
    PRIMARY KEY (fecha, pais, hashtag)
);
"""


@dataclass
class Pieza:
    id: str
    red: str
    url: str
    titulo: str
    texto: str = ""
    cuenta: str = ""
    grupo: str = ""
    publicado: float | None = None
    via: str = "api"
    metrica: float | None = None
    likes: float | None = None
    comentarios: float | None = None
    extra: dict = field(default_factory=dict)


def conectar() -> sqlite3.Connection:
    DIR_DATA.mkdir(exist_ok=True)
    con = sqlite3.connect(DIR_DATA / "radar.db")
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def guardar_piezas(con: sqlite3.Connection, sector: str, piezas: list[Pieza]) -> int:
    ahora = time.time()
    for p in piezas:
        con.execute(
            """INSERT INTO piezas (id, sector, red, url, titulo, texto, cuenta, grupo, publicado, via, extra, creado)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET titulo=excluded.titulo, texto=excluded.texto,
                 extra=excluded.extra, via=excluded.via,
                 publicado=COALESCE(excluded.publicado, piezas.publicado)""",
            (p.id, sector, p.red, p.url, p.titulo, p.texto[:4000], p.cuenta, p.grupo, p.publicado,
             p.via, json.dumps(p.extra, ensure_ascii=False), ahora),
        )
        if p.metrica is not None:
            guardar_captura(con, p.id, p.metrica, p.likes, p.comentarios, ahora)
    con.commit()
    return len(piezas)


def guardar_captura(con, pieza_id, metrica, likes=None, comentarios=None, ts=None):
    con.execute(
        "INSERT OR REPLACE INTO capturas (pieza_id, ts, metrica, likes, comentarios) VALUES (?,?,?,?,?)",
        (pieza_id, ts or time.time(), metrica, likes, comentarios),
    )


def guardar_referencia(con, grupo: str, mediana: float):
    con.execute("INSERT OR REPLACE INTO referencia (grupo, mediana, ts) VALUES (?,?,?)", (grupo, mediana, time.time()))
    con.commit()


def piezas_sector(con, sector: str, desde: float) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM piezas WHERE sector=? AND (publicado IS NULL OR publicado>=?)", (sector, desde)
    ).fetchall()


def capturas(con, pieza_id: str) -> list[sqlite3.Row]:
    return con.execute("SELECT * FROM capturas WHERE pieza_id=? ORDER BY ts", (pieza_id,)).fetchall()


def referencia(con, grupo: str) -> float | None:
    fila = con.execute("SELECT mediana FROM referencia WHERE grupo=?", (grupo,)).fetchone()
    return fila["mediana"] if fila else None
