"""
CicloConecta — Routing Cache.

Caches calculated routes in-memory and on disk to provide instantaneous responses
for repeated origin-destination queries.
"""

import json
from pathlib import Path
from typing import Any, Optional


class RouteCache:
    """Thread-safe and persistent cache for route queries."""

    def __init__(self, cache_file: Optional[Path] = None, max_mem_entries: int = 1000):
        self.cache_file = cache_file
        self.max_mem_entries = max_mem_entries
        self._cache: dict[str, dict[str, Any]] = {}
        self._load_from_disk()

    def _build_key(self, origin: list[float], destination: list[float]) -> str:
        # Round to 5 decimal places (~1.1 meter resolution)
        o_lon = round(origin[0], 5)
        o_lat = round(origin[1], 5)
        d_lon = round(destination[0], 5)
        d_lat = round(destination[1], 5)
        return f"{o_lon},{o_lat}->{d_lon},{d_lat}"

    def _load_from_disk(self) -> None:
        if self.cache_file and self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save_to_disk(self) -> None:
        if self.cache_file:
            try:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, ensure_ascii=False)
            except Exception:
                pass

    def get(self, origin: list[float], destination: list[float]) -> Optional[dict[str, Any]]:
        key = self._build_key(origin, destination)
        return self._cache.get(key)

    def set(self, origin: list[float], destination: list[float], value: dict[str, Any]) -> None:
        if len(self._cache) >= self.max_mem_entries:
            # Evict oldest key
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        key = self._build_key(origin, destination)
        self._cache[key] = value
        self._save_to_disk()
