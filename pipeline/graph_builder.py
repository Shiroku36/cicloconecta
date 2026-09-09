"""
CicloConecta — Navigable Graph Builder for Cycling Routing.

Converts OSM road network elements into a directed graph (NetworkX DiGraph).
Calculates Haversine distances, applies bicycle oneway rules and cycling cost penalties.
Serializes the graph into an optimized JSON format for fast offline loading by FastAPI.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx

from .cost_function import evaluate_edge_cycling_cost, is_oneway_for_bicycle


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculates great-circle distance between two coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def build_navigable_graph(
    nodes: dict[int, list[float]],
    ways: list[dict[str, Any]],
) -> nx.DiGraph:
    """
    Builds a directed NetworkX graph where edges have cycling costs,
    geodesic lengths, and metadata attributes.
    """
    G = nx.DiGraph()

    for way in ways:
        tags = way.get("tags", {})
        is_cyclable, penalty_factor, category, infra_label = evaluate_edge_cycling_cost(tags)
        if not is_cyclable:
            continue

        fwd_allowed, bwd_allowed = is_oneway_for_bicycle(tags)
        way_nodes = way.get("nodes", [])

        is_cycling_infra = category in ("dedicated_cycleway", "cycle_lane")
        name = tags.get("name") or "Calle sin nombre"
        highway = tags.get("highway", "")

        for i in range(len(way_nodes) - 1):
            u = way_nodes[i]
            v = way_nodes[i + 1]

            if u not in nodes or v not in nodes:
                continue

            coord_u = nodes[u]
            coord_v = nodes[v]

            dist_m = haversine_distance(coord_u[0], coord_u[1], coord_v[0], coord_v[1])
            if dist_m < 0.1:
                continue

            cost = dist_m * penalty_factor

            # Register node coordinates if not yet in graph
            if u not in G:
                G.add_node(u, lon=coord_u[0], lat=coord_u[1])
            if v not in G:
                G.add_node(v, lon=coord_v[0], lat=coord_v[1])

            edge_attrs = {
                "length_m": round(dist_m, 2),
                "cost": round(cost, 2),
                "penalty_factor": penalty_factor,
                "way_id": way["id"],
                "name": name,
                "highway": highway,
                "category": category,
                "infra_label": infra_label,
                "is_cycling_infra": is_cycling_infra,
                "surface": tags.get("surface"),
                "maxspeed": tags.get("maxspeed"),
            }

            if fwd_allowed:
                G.add_edge(u, v, **edge_attrs, geometry=[coord_u, coord_v])
            if bwd_allowed:
                G.add_edge(v, u, **edge_attrs, geometry=[coord_v, coord_u])

    return G


def filter_largest_component(G: nx.DiGraph) -> nx.DiGraph:
    """Retains the largest weakly connected component to ensure route continuity."""
    if len(G) == 0:
        return G
    largest_cc = max(nx.weakly_connected_components(G), key=len)
    return G.subgraph(largest_cc).copy()


def serialize_graph_to_json(G: nx.DiGraph, city_id: str) -> dict[str, Any]:
    """Serializes a NetworkX DiGraph to an efficient JSON structure."""
    nodes_list = []
    for node_id, data in G.nodes(data=True):
        nodes_list.append({
            "id": node_id,
            "lon": data.get("lon"),
            "lat": data.get("lat"),
        })

    edges_list = []
    for u, v, data in G.edges(data=True):
        edges_list.append({
            "u": u,
            "v": v,
            "length_m": data.get("length_m"),
            "cost": data.get("cost"),
            "penalty_factor": data.get("penalty_factor"),
            "way_id": data.get("way_id"),
            "name": data.get("name"),
            "highway": data.get("highway"),
            "category": data.get("category"),
            "infra_label": data.get("infra_label"),
            "is_cycling_infra": data.get("is_cycling_infra"),
        })

    return {
        "version": "1.0",
        "city": city_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "node_count": len(nodes_list),
            "edge_count": len(edges_list),
        },
        "nodes": nodes_list,
        "edges": edges_list,
    }


def deserialize_graph_from_json(graph_dict: dict[str, Any]) -> nx.DiGraph:
    """Reconstructs a NetworkX DiGraph from serialized JSON."""
    G = nx.DiGraph()

    for n in graph_dict.get("nodes", []):
        G.add_node(n["id"], lon=n["lon"], lat=n["lat"])

    for e in graph_dict.get("edges", []):
        u = e["u"]
        v = e["v"]
        attrs = {k: v for k, v in e.items() if k not in ("u", "v")}
        G.add_edge(u, v, **attrs)

    return G
