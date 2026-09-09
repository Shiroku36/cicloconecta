"""
CicloConecta — Deterministic Cycling Router.

Calculates optimal bicycle routes over a navigable NetworkX graph using A* search.
Compares cycling-weighted paths against pure distance-shortest paths.
Extracts continuous geometries and detailed infrastructure metrics.
"""

import math
from typing import Any, Optional

import networkx as nx

from .cost_function import MIN_PENALTY_FACTOR
from .graph_builder import haversine_distance


class RoutingError(Exception):
    """Base exception for routing engine errors."""
    pass


class CoordinateOutOfBoundsError(RoutingError):
    """Raised when coordinates are further than threshold from any navigable node."""
    pass


class RouteNotFoundError(RoutingError):
    """Raised when no navigable path exists between origin and destination."""
    pass


class SpatialNodeIndex:
    """
    Fast spatial indexing for snapping arbitrary (lon, lat) coordinates
    to the nearest graph node within a maximum search radius.
    """

    def __init__(self, G: nx.DiGraph, grid_size_deg: float = 0.01):
        self.G = G
        self.grid_size = grid_size_deg
        self.grid: dict[tuple[int, int], list[tuple[int, float, float]]] = {}
        self._build_index()

    def _build_index(self) -> None:
        for node_id, data in self.G.nodes(data=True):
            lon = data.get("lon")
            lat = data.get("lat")
            if lon is None or lat is None:
                continue
            gx = int(math.floor(lon / self.grid_size))
            gy = int(math.floor(lat / self.grid_size))
            cell = (gx, gy)
            if cell not in self.grid:
                self.grid[cell] = []
            self.grid[cell].append((node_id, lon, lat))

    def snap_to_nearest_node(
        self,
        lon: float,
        lat: float,
        max_distance_m: float = 500.0,
    ) -> tuple[int, float]:
        """
        Finds the closest node to (lon, lat).
        Returns (node_id, distance_in_meters).
        Raises CoordinateOutOfBoundsError if closest node is further than max_distance_m.
        """
        gx = int(math.floor(lon / self.grid_size))
        gy = int(math.floor(lat / self.grid_size))

        # Check target cell and adjacent cells (ring 1)
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = (gx + dx, gy + dy)
                if cell in self.grid:
                    candidates.extend(self.grid[cell])

        # If candidates is empty (e.g. at edge of grid), expand search to ring 2
        if not candidates:
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    cell = (gx + dx, gy + dy)
                    if cell in self.grid:
                        candidates.extend(self.grid[cell])

        # If still empty, search all nodes as fallback
        if not candidates:
            candidates = [
                (n, d["lon"], d["lat"])
                for n, d in self.G.nodes(data=True)
                if "lon" in d and "lat" in d
            ]

        if not candidates:
            raise CoordinateOutOfBoundsError("El grafo no contiene nodos válidos para conectar.")

        best_node = None
        best_dist = float("inf")

        for node_id, n_lon, n_lat in candidates:
            dist = haversine_distance(lon, lat, n_lon, n_lat)
            if dist < best_dist:
                best_dist = dist
                best_node = node_id

        if best_dist > max_distance_m or best_node is None:
            raise CoordinateOutOfBoundsError(
                f"Coordenada ({lon:.5f}, {lat:.5f}) está a {best_dist:.1f} m del camino navegable más cercano (máximo permitido: {max_distance_m:.0f} m)."
            )

        return best_node, best_dist


def astar_cycling_heuristic(u: int, v: int, G: nx.DiGraph) -> float:
    """
    Admissible and monotonic heuristic for cycling routing:
    h(u, v) = haversine_distance(u, v) * MIN_PENALTY_FACTOR (0.70)
    Since no edge has penalty < MIN_PENALTY_FACTOR, this never overestimates actual cost.
    """
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    dist_m = haversine_distance(node_u["lon"], node_u["lat"], node_v["lon"], node_v["lat"])
    return dist_m * MIN_PENALTY_FACTOR


def astar_distance_heuristic(u: int, v: int, G: nx.DiGraph) -> float:
    """Admissible heuristic for shortest physical distance: geodesic distance."""
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    return haversine_distance(node_u["lon"], node_u["lat"], node_v["lon"], node_v["lat"])


def compute_path_metrics(
    G: nx.DiGraph,
    node_path: list[int],
) -> dict[str, Any]:
    """
    Computes distance, cycling infrastructure coverage, cost score,
    and street breakdowns along a node path.
    """
    if len(node_path) < 2:
        return {
            "distance_m": 0.0,
            "distance_km": 0.0,
            "cycling_infra_m": 0.0,
            "cycling_infra_km": 0.0,
            "cycling_infra_pct": 0.0,
            "cost_score": 0.0,
            "streets": [],
            "coordinates": [[G.nodes[n]["lon"], G.nodes[n]["lat"]] for n in node_path],
        }

    total_dist_m = 0.0
    cycling_dist_m = 0.0
    total_cost = 0.0
    coordinates: list[list[float]] = []
    streets: list[str] = []

    for i in range(len(node_path) - 1):
        u = node_path[i]
        v = node_path[i + 1]
        edge_data = G.get_edge_data(u, v, default={})

        length_m = edge_data.get("length_m", 0.0)
        cost = edge_data.get("cost", length_m)
        is_infra = edge_data.get("is_cycling_infra", False)
        street_name = edge_data.get("name")

        total_dist_m += length_m
        total_cost += cost
        if is_infra:
            cycling_dist_m += length_m

        if street_name and (not streets or streets[-1] != street_name):
            streets.append(street_name)

        if i == 0:
            coordinates.append([G.nodes[u]["lon"], G.nodes[u]["lat"]])
        coordinates.append([G.nodes[v]["lon"], G.nodes[v]["lat"]])

    cycling_pct = round((cycling_dist_m / total_dist_m) * 100.0, 1) if total_dist_m > 0 else 0.0

    return {
        "distance_m": round(total_dist_m, 1),
        "distance_km": round(total_dist_m / 1000.0, 2),
        "cycling_infra_m": round(cycling_dist_m, 1),
        "cycling_infra_km": round(cycling_dist_m / 1000.0, 2),
        "cycling_infra_pct": cycling_pct,
        "cost_score": round(total_cost, 1),
        "streets": streets,
        "coordinates": coordinates,
    }


def find_cycling_route(
    G: nx.DiGraph,
    origin_node: int,
    dest_node: int,
) -> list[int]:
    """Computes optimal cycling route using A* with cycling cost weights."""
    if origin_node == dest_node:
        return [origin_node]

    try:
        return nx.astar_path(
            G,
            origin_node,
            dest_node,
            heuristic=lambda u, v: astar_cycling_heuristic(u, v, G),
            weight="cost",
        )
    except nx.NetworkXNoPath:
        raise RouteNotFoundError(f"No existe ruta ciclable entre nodo {origin_node} y nodo {dest_node}.")


def find_shortest_route(
    G: nx.DiGraph,
    origin_node: int,
    dest_node: int,
) -> list[int]:
    """Computes shortest physical distance route using A* with length_m weights."""
    if origin_node == dest_node:
        return [origin_node]

    try:
        return nx.astar_path(
            G,
            origin_node,
            dest_node,
            heuristic=lambda u, v: astar_distance_heuristic(u, v, G),
            weight="length_m",
        )
    except nx.NetworkXNoPath:
        raise RouteNotFoundError(f"No existe ruta física entre nodo {origin_node} y nodo {dest_node}.")


def calculate_complete_route(
    G: nx.DiGraph,
    spatial_index: SpatialNodeIndex,
    origin_lon: float,
    origin_lat: float,
    dest_lon: float,
    dest_lat: float,
    max_snap_dist_m: float = 500.0,
) -> dict[str, Any]:
    """
    Calculates:
      1. Cycling-optimal route (preferring cycling infrastructure and calm streets)
      2. Distance-shortest route (pure shortest path)
    Returns complete metrics, comparison differentials, and GeoJSON LineString coordinates.
    """
    origin_node, origin_snap_m = spatial_index.snap_to_nearest_node(origin_lon, origin_lat, max_snap_dist_m)
    dest_node, dest_snap_m = spatial_index.snap_to_nearest_node(dest_lon, dest_lat, max_snap_dist_m)

    cycling_path = find_cycling_route(G, origin_node, dest_node)
    shortest_path = find_shortest_route(G, origin_node, dest_node)

    cycling_metrics = compute_path_metrics(G, cycling_path)
    shortest_metrics = compute_path_metrics(G, shortest_path)

    dist_diff_km = round(cycling_metrics["distance_km"] - shortest_metrics["distance_km"], 2)
    length_diff_pct = (
        round(((cycling_metrics["distance_m"] - shortest_metrics["distance_m"]) / shortest_metrics["distance_m"]) * 100.0, 1)
        if shortest_metrics["distance_m"] > 0
        else 0.0
    )
    cycling_gain_pct = round(cycling_metrics["cycling_infra_pct"] - shortest_metrics["cycling_infra_pct"], 1)

    return {
        "origin": {
            "requested": [origin_lon, origin_lat],
            "snapped_node": origin_node,
            "snap_distance_m": round(origin_snap_m, 1),
        },
        "destination": {
            "requested": [dest_lon, dest_lat],
            "snapped_node": dest_node,
            "snap_distance_m": round(dest_snap_m, 1),
        },
        "cycling_route": {
            "distance_km": cycling_metrics["distance_km"],
            "distance_m": cycling_metrics["distance_m"],
            "cycling_infra_km": cycling_metrics["cycling_infra_km"],
            "cycling_infra_pct": cycling_metrics["cycling_infra_pct"],
            "cost_score": cycling_metrics["cost_score"],
            "streets": cycling_metrics["streets"],
            "coordinates": cycling_metrics["coordinates"],
        },
        "shortest_route": {
            "distance_km": shortest_metrics["distance_km"],
            "distance_m": shortest_metrics["distance_m"],
            "cycling_infra_km": shortest_metrics["cycling_infra_km"],
            "cycling_infra_pct": shortest_metrics["cycling_infra_pct"],
            "cost_score": shortest_metrics["cost_score"],
            "streets": shortest_metrics["streets"],
            "coordinates": shortest_metrics["coordinates"],
        },
        "comparison": {
            "distance_diff_km": dist_diff_km,
            "length_diff_pct": length_diff_pct,
            "cycling_gain_pct": cycling_gain_pct,
            "is_same_path": cycling_path == shortest_path,
        },
    }
