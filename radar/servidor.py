"""Servidor web local: sirve la app (web/) y una API mínima para lanzar corridas y ver el progreso.

  GET  /api/sectores          sectores disponibles con el estado de cada red
  GET  /api/datos             todas las corridas guardadas (out/*.json)
  GET  /api/estado            progreso de la corrida en curso
  POST /api/correr            {"sector": "ia_latam", "redes": ["youtube", ...], "recolectar": true}
"""
import io
import json
import sys
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from . import pipeline
from .config import DIR_CONFIG, DIR_OUT, DIR_WEB, cargar_sector
from .estado import REDES, estado_redes

class Trabajo:
    def __init__(self):
        self.lock = threading.Lock()
        self.hilo = None
        self.log: list[str] = []
        self.inicio = None
        self.fin = None
        self.error = None
        self.sector = None

    def ocupado(self) -> bool:
        return bool(self.hilo and self.hilo.is_alive())

    def estado(self) -> dict:
        return {"corriendo": self.ocupado(), "sector": self.sector, "log": self.log[-200:], "error": self.error,
                "inicio": self.inicio, "fin": self.fin}


TRABAJO = Trabajo()
_stdout_original = sys.stdout


class _Salida(io.TextIOBase):
    """Copia al log del trabajo lo que imprime el hilo de la corrida; el resto va a la consola."""
    def write(self, texto):
        if TRABAJO.hilo is threading.current_thread():
            for linea in texto.splitlines():
                if linea.strip():
                    TRABAJO.log.append(linea)
        return _stdout_original.write(texto)

    def flush(self):
        _stdout_original.flush()


def lanzar(sector: str, redes: list[str], recolectar: bool) -> bool:
    with TRABAJO.lock:
        if TRABAJO.ocupado():
            return False
        TRABAJO.log, TRABAJO.error, TRABAJO.sector = [], None, sector
        TRABAJO.inicio, TRABAJO.fin = time.time(), None

        def correr():
            try:
                pipeline.correr(sector, con_recoleccion=recolectar, redes=redes or None)
            except SystemExit as e:
                TRABAJO.error = str(e)
            except Exception as e:
                TRABAJO.error = f"{type(e).__name__}: {e}"
                traceback.print_exc()
            finally:
                TRABAJO.fin = time.time()

        TRABAJO.hilo = threading.Thread(target=correr, daemon=True)
        TRABAJO.hilo.start()
        return True


class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(DIR_WEB), **k)

    def log_message(self, *a):
        pass

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/api/estado":
            return self._json({**TRABAJO.estado(), "modo": "local"})
        if ruta == "/api/datos":
            datos = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR_OUT.glob("*.json"))}
            return self._json(datos)
        if ruta == "/api/sectores":
            sectores = []
            for p in sorted(DIR_CONFIG.glob("*.yaml")):
                if p.stem == "global":
                    continue
                cfg = cargar_sector(p.stem)
                sectores.append({"id": p.stem, "nombre": cfg["nombre"], "redes": estado_redes(cfg)})
            return self._json(sectores)
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/correr":
            return self._json({"error": "no encontrado"}, 404)
        largo = int(self.headers.get("Content-Length") or 0)
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
        except ValueError:
            return self._json({"error": "JSON inválido"}, 400)
        sector = datos.get("sector", "ia_latam")
        if not (DIR_CONFIG / f"{sector}.yaml").exists():
            return self._json({"error": f"sector desconocido: {sector}"}, 400)
        redes = [r for r in datos.get("redes", []) if r in REDES]
        if not lanzar(sector, redes, bool(datos.get("recolectar", True))):
            return self._json({"error": "ya hay una corrida en curso"}, 409)
        return self._json({"ok": True})


def servir(puerto: int = 8765):
    sys.stdout = _Salida()
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
    print(f"Radar 30X en http://localhost:{puerto}  (Ctrl+C para salir)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
