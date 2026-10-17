"""Contador de costo real: suma el campo usage de cada respuesta de JEV y del LLM."""
import threading
from collections import defaultdict


class Contador:
    def __init__(self, cfg_global: dict):
        self.precio_jev = cfg_global["jev"]["precio_entrada_mtok"]
        self.proveedor = cfg_global["llm"]["proveedor"]
        self.precios_llm = cfg_global["llm"]["precios"]
        self.precio_busqueda = cfg_global.get("busqueda", {}).get("precio_por_consulta", 0)
        self._lock = threading.Lock()
        self.pasos = defaultdict(lambda: {"llamadas": 0, "tokens_entrada": 0, "tokens_salida": 0,
                                          "busquedas_web": 0, "usd": 0.0})
        self.sin_precio: set[str] = set()

    def jev(self, paso: str, usage: dict):
        entrada = int(usage.get("input_tokens", 0))
        with self._lock:
            d = self.pasos[paso]
            d["llamadas"] += 1
            d["tokens_entrada"] += entrada
            d["tokens_salida"] += int(usage.get("output_tokens", 0))
            d["usd"] += entrada * self.precio_jev / 1e6

    def llm(self, paso: str, modelo: str, entrada: int, salida: int, busquedas: int = 0):
        precio = self._precio(modelo)
        if precio is None:
            self.sin_precio.add(modelo)
            precio = [0, 0]
        with self._lock:
            d = self.pasos[paso]
            d["llamadas"] += 1
            d["tokens_entrada"] += entrada
            d["tokens_salida"] += salida
            d["busquedas_web"] += busquedas
            d["usd"] += entrada * precio[0] / 1e6 + salida * precio[1] / 1e6 + busquedas * self.precio_busqueda

    def _precio(self, modelo: str):
        # la respuesta puede traer el id con fecha (modelo-2025-08-07): se busca el prefijo más largo
        for nombre in sorted(self.precios_llm, key=len, reverse=True):
            if modelo == nombre or modelo.startswith(nombre + "-2"):
                return self.precios_llm[nombre]
        return None

    def resumen(self) -> dict:
        pasos = {k: {**v, "usd": round(v["usd"], 5)} for k, v in self.pasos.items()}
        total = sum(v["usd"] for v in self.pasos.values())
        jev = sum(v["usd"] for k, v in self.pasos.items() if k.startswith("jev"))
        return {"total_usd": round(total, 4), "jev_usd": round(jev, 5), "llm_usd": round(total - jev, 4),
                "proveedor_llm": self.proveedor, "modelos_sin_precio": sorted(self.sin_precio), "pasos": pasos}
