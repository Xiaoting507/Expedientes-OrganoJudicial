"""Límites de tasa en memoria (SEC-04 / SEC-06).

Ventana deslizante por clave (normalmente la IP). Es por réplica: con varias
réplicas el límite efectivo se multiplica; en producción conviene moverlo al Ingress.
"""
import threading
import time
from collections import defaultdict, deque


class VentanaFallos:
    def __init__(self, maximo: int, segundos: int):
        self.maximo = maximo
        self.segundos = segundos
        self._eventos: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _limpiar(self, clave: str, ahora: float) -> deque[float]:
        cola = self._eventos[clave]
        while cola and ahora - cola[0] > self.segundos:
            cola.popleft()
        return cola

    def excedido(self, clave: str) -> int:
        """0 si puede seguir; si no, los segundos que faltan para liberar la ventana."""
        ahora = time.monotonic()
        with self._lock:
            cola = self._limpiar(clave, ahora)
            if len(cola) < self.maximo:
                return 0
            return max(1, int(self.segundos - (ahora - cola[0])) + 1)

    def registrar(self, clave: str) -> None:
        with self._lock:
            self._limpiar(clave, time.monotonic()).append(time.monotonic())

    def limpiar(self, clave: str) -> None:
        with self._lock:
            self._eventos.pop(clave, None)
