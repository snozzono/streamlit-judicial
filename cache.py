"""
cache.py — Caché LRU para respuestas de consultas frecuentes.

Reduce latencia (~50ms vs ~2000ms) y costo de tokens en
consultas repetitivas. Usa un diccionario con orden de
acceso para evicción LRU.
"""

import hashlib
import logging
import time
from collections import OrderedDict
from threading import Lock

from config import CONFIG

logger = logging.getLogger(__name__)


class LRUCache:
    """
    Caché LRU thread-safe con TTL.

    Almacena respuestas completas indexadas por hash de la consulta.
    """

    def __init__(self, maxsize: int = None, ttl_minutes: int = None):
        self._maxsize = maxsize or CONFIG.cache_maxsize
        self._ttl_seconds = (ttl_minutes or CONFIG.cache_ttl_minutes) * 60
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._lock = Lock()

    def _hash(self, consulta: str) -> str:
        return hashlib.sha256(consulta.strip().lower().encode()).hexdigest()

    def obtener(self, consulta: str) -> str | None:
        key = self._hash(consulta)
        with self._lock:
            if key not in self._cache:
                return None
            timestamp, respuesta = self._cache[key]
            if time.time() - timestamp > self._ttl_seconds:
                del self._cache[key]
                logger.debug(f"Cache expired for: {consulta[:50]}...")
                return None
            self._cache.move_to_end(key)
            logger.info(f"Cache HIT for: {consulta[:50]}...")
            return respuesta

    def guardar(self, consulta: str, respuesta: str) -> None:
        key = self._hash(consulta)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (time.time(), respuesta)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)
            logger.debug(f"Cache saved for: {consulta[:50]}...")

    def limpiar(self) -> None:
        with self._lock:
            self._cache.clear()

    def tamaño(self) -> int:
        return len(self._cache)


_cache_instance: LRUCache | None = None


def get_cache() -> LRUCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = LRUCache()
    return _cache_instance
