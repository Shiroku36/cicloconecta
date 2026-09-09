"""
CicloConecta — Routing Engine Service for FastAPI.

Loads the pre-built navigable network graph for cities, indexes nodes spatially,
computes deterministic cycling and shortest routes, and manages caching.
"""

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from pipeline.graph_builder import deserialize_graph_from_json
from pipeline.router import (
    CoordinateOutOfBoundsError,
    RouteNotFoundError,
    SpatialNodeIndex,
    calculate_complete_route,
)

from ..config import settings
from ..schemas import RouteResponse
from .cache import RouteCache


class CityRoutingEngine:
    """Manages graph and routing queries for a specific city."""

    def __init__(self, city_id: str, nav_graph_path: Path):
        self.city_id = city_id
        self.nav_graph_path = nav_graph_path

        if not nav_graph_path.exists():
            raise FileNotFoundError(f"Archivo de grafo navegable no encontrado: {nav_graph_path}")

        with open(nav_graph_path, "r", encoding="utf-8") as f:
            graph_dict = json.load(f)

        self.G = deserialize_graph_from_json(graph_dict)
        self.spatial_index = SpatialNodeIndex(self.G)
        cache_file = nav_graph_path.parent / "routes_cache.json"
        self.cache = RouteCache(cache_file=cache_file)

    def route(
        self,
        origin: list[float],
        destination: list[float],
        max_snap_dist_m: float = 500.0,
    ) -> RouteResponse:
        """Calculates cycling and shortest routes with caching."""
        cached_result = self.cache.get(origin, destination)
        if cached_result:
            return RouteResponse(**{**cached_result, "cached": True})

        try:
            result = calculate_complete_route(
                self.G,
                self.spatial_index,
                origin_lon=origin[0],
                origin_lat=origin[1],
                dest_lon=destination[0],
                dest_lat=destination[1],
                max_snap_dist_m=max_snap_dist_m,
            )
        except CoordinateOutOfBoundsError as err:
            raise HTTPException(status_code=400, detail=str(err))
        except RouteNotFoundError as err:
            raise HTTPException(status_code=404, detail=str(err))
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Error interno calculando ruta: {err}")

        payload = {
            "city_id": self.city_id,
            "origin": result["origin"],
            "destination": result["destination"],
            "cycling_route": result["cycling_route"],
            "shortest_route": result["shortest_route"],
            "comparison": result["comparison"],
            "cached": False,
        }

        # Cache valid calculation
        self.cache.set(origin, destination, payload)

        return RouteResponse(**payload)


# Global in-memory registry of city routing engines
_ENGINES: dict[str, CityRoutingEngine] = {}


def get_city_routing_engine(city_id: str) -> CityRoutingEngine:
    """Retrieves or lazily initializes the routing engine for the requested city."""
    if city_id in _ENGINES:
        return _ENGINES[city_id]

    city_dir = settings.data_dir / city_id
    nav_graph_path = city_dir / "nav_graph.json"

    if not city_dir.exists() or not (city_dir / "city.json").exists():
        raise HTTPException(
            status_code=404,
            detail=f"Ciudad '{city_id}' no encontrada en el repositorio.",
        )

    if not nav_graph_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"El motor de routing aún no está generado para '{city_id}' (falta nav_graph.json).",
        )

    try:
        engine = CityRoutingEngine(city_id, nav_graph_path)
        _ENGINES[city_id] = engine
        return engine
    except Exception as err:
        raise HTTPException(
            status_code=500,
            detail=f"Error al inicializar motor de routing para '{city_id}': {err}",
        )
