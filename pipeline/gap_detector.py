"""
CicloConecta — Algorithmic Missing Connections (Gap) Detector.

Identifies structural disconnects in the cycling network and calculates
candidate connections over the real road network using graph topology.
Quantifies network gain, gain ratio, and multi-criteria priority score.
"""

import math
from dataclasses import dataclass
from typing import Any, Optional

import networkx as nx

from .graph_builder import haversine_distance


@dataclass
class CyclingComponent:
    """Represents an isolated or connected sub-network of cycling infrastructure."""
    id: int
    nodes: set[int]
    length_m: float
    length_km: float
    endpoints: list[int]
    bbox: tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat)


def build_cycling_subgraph(G_nav: nx.DiGraph) -> nx.Graph:
    """
    Constructs an undirected graph containing only verified cycling infrastructure edges.
    Treats cycleways as undirected for topological connectivity analysis.
    """
    G_cycling = nx.Graph()

    for u, v, data in G_nav.edges(data=True):
        if data.get("is_cycling_infra"):
            length_m = data.get("length_m", 0.0)
            name = data.get("name", "")
            category = data.get("category", "dedicated_cycleway")

            # In an undirected graph, add or preserve maximum length if parallel
            if G_cycling.has_edge(u, v):
                prev_len = G_cycling[u][v].get("length_m", 0.0)
                if length_m > prev_len:
                    G_cycling[u][v]["length_m"] = length_m
            else:
                G_cycling.add_edge(u, v, length_m=length_m, name=name, category=category)

    # Copy node coordinates
    for node in G_cycling.nodes:
        if node in G_nav.nodes:
            G_cycling.nodes[node]["lon"] = G_nav.nodes[node]["lon"]
            G_cycling.nodes[node]["lat"] = G_nav.nodes[node]["lat"]

    return G_cycling


def extract_cycling_components(G_cycling: nx.Graph) -> list[CyclingComponent]:
    """
    Identifies connected components in the cycling network and extracts
    their metrics: total length, endpoints (degree 1), and spatial bounds.
    """
    raw_components = list(nx.connected_components(G_cycling))
    raw_components.sort(key=len, reverse=True)

    components: list[CyclingComponent] = []

    for i, node_set in enumerate(raw_components, start=1):
        sub = G_cycling.subgraph(node_set)
        total_len_m = sum(d.get("length_m", 0.0) for _, _, d in sub.edges(data=True))
        total_len_km = round(total_len_m / 1000.0, 2)

        # Endpoints are nodes of degree 1 (where the cycleway abruptly terminates)
        # If component is an isolated loop without degree 1, take first node as anchor
        endpoints = [n for n in node_set if sub.degree[n] == 1]
        if not endpoints and node_set:
            endpoints = [next(iter(node_set))]

        lons = [sub.nodes[n]["lon"] for n in node_set if "lon" in sub.nodes[n]]
        lats = [sub.nodes[n]["lat"] for n in node_set if "lat" in sub.nodes[n]]

        bbox = (
            min(lons) if lons else 0.0,
            min(lats) if lats else 0.0,
            max(lons) if lons else 0.0,
            max(lats) if lats else 0.0,
        )

        components.append(
            CyclingComponent(
                id=i,
                nodes=node_set,
                length_m=round(total_len_m, 1),
                length_km=total_len_km,
                endpoints=endpoints,
                bbox=bbox,
            )
        )

    return components


def calculate_priority_score(
    len_a_km: float,
    len_b_km: float,
    gap_length_m: float,
    avg_penalty: float,
) -> float:
    """
    Computes a transparent, deterministic multi-criteria priority score from 0 to 100:
      1. Network Impact (0-50 pts): Proportional to sqrt(minor_component) and log(total_network).
         Rewards connecting substantial networks rather than trivial dead-ends.
      2. Gap Efficiency (0-35 pts): Proportional to compactness of the gap.
         Shorter, direct connections are easier and faster to implement.
      3. Road Comfort (0-15 pts): Evaluates the road typology of the candidate path.
         Calm residential streets (penalty ~1.0) score higher than busy multi-lane arterials.
    """
    min_len = min(len_a_km, len_b_km)
    total_net = len_a_km + len_b_km

    # 1. Network impact (0 to 50 pts)
    # sqrt(min_len) scales smoothly: min_len=4.4km gives ~42 pts; min_len=0.4km gives ~13 pts
    net_impact = min(50.0, (math.sqrt(min_len) * 19.5) + (math.log10(1.0 + total_net) * 12.0))

    # 2. Efficiency / compactness score (0 to 35 pts)
    # Gaps <= 100m get ~32-35 pts; gaps ~500m get ~20 pts; gaps >= 1200m get 0 pts
    eff_score = max(0.0, 35.0 * (1.0 - (gap_length_m / 1200.0)))

    # 3. Road comfort score (0 to 15 pts)
    # avg_penalty in [0.95, 2.60]. Lower penalty = calmer, safer street
    comfort_mult = max(0.3, 1.8 - (avg_penalty * 0.5))
    comfort_score = min(15.0, 15.0 * (comfort_mult / 1.3))

    total = net_impact + eff_score + comfort_score
    return round(max(0.0, min(100.0, total)), 1)


def find_candidate_gaps(
    G_nav: nx.DiGraph,
    components: list[CyclingComponent],
    min_crow_dist_m: float = 35.0,
    max_crow_dist_m: float = 850.0,
    max_path_len_m: float = 1200.0,
    min_component_len_km: float = 0.20,
) -> list[dict[str, Any]]:
    """
    Searches for candidate connections between endpoints of different components
    using the real navigable road network graph G_nav.
    """
    valid_components = [c for c in components if c.length_km >= min_component_len_km]
    comp_by_id = {c.id: c for c in valid_components}

    # Collect endpoints
    all_endpoints = []
    for c in valid_components:
        for ep in c.endpoints:
            if ep in G_nav.nodes:
                all_endpoints.append((ep, c.id))

    raw_candidates: list[dict[str, Any]] = []

    # Search end-to-end and end-to-side connections
    for i in range(len(all_endpoints)):
        ep1, cid1 = all_endpoints[i]
        node1 = G_nav.nodes[ep1]

        for j in range(i + 1, len(all_endpoints)):
            ep2, cid2 = all_endpoints[j]
            if cid1 == cid2:
                continue  # Connect different components

            node2 = G_nav.nodes[ep2]
            crow_dist = haversine_distance(node1["lon"], node1["lat"], node2["lon"], node2["lat"])

            if crow_dist < min_crow_dist_m or crow_dist > max_crow_dist_m:
                continue

            # Route along the real road network
            try:
                # Find shortest physical path along drivable/walkable street network
                path = nx.shortest_path(G_nav, ep1, ep2, weight="length_m")
                path_len_m = sum(
                    G_nav[u][v].get("length_m", 0.0) for u, v in zip(path[:-1], path[1:])
                )

                # Filter out absurd detours (path length should not exceed 2.2x crow distance)
                if path_len_m > max_path_len_m or path_len_m > (crow_dist * 2.2):
                    continue

                # Collect street details and penalties
                streets: list[str] = []
                highway_types: list[str] = []
                penalties: list[float] = []

                for u, v in zip(path[:-1], path[1:]):
                    edge = G_nav[u][v]
                    st_name = edge.get("name")
                    hw = edge.get("highway")
                    pen = edge.get("penalty_factor", 1.0)

                    if st_name and (not streets or streets[-1] != st_name):
                        streets.append(st_name)
                    if hw and hw not in highway_types:
                        highway_types.append(hw)
                    penalties.append(pen)

                avg_pen = sum(penalties) / len(penalties) if penalties else 1.0

                comp_a = comp_by_id[cid1]
                comp_b = comp_by_id[cid2]

                connected_km = round(comp_a.length_km + comp_b.length_km + (path_len_m / 1000.0), 2)
                network_gain_km = round(comp_a.length_km + comp_b.length_km, 2)
                gap_km = path_len_m / 1000.0
                gain_ratio = round(network_gain_km / gap_km, 1) if gap_km > 0 else 0.0

                score = calculate_priority_score(
                    comp_a.length_km, comp_b.length_km, path_len_m, avg_pen
                )

                coordinates = [[G_nav.nodes[n]["lon"], G_nav.nodes[n]["lat"]] for n in path]

                raw_candidates.append({
                    "comp_a_id": cid1,
                    "comp_b_id": cid2,
                    "comp_a_km": comp_a.length_km,
                    "comp_b_km": comp_b.length_km,
                    "node_origin": ep1,
                    "node_dest": ep2,
                    "gap_length_m": round(path_len_m, 1),
                    "crow_distance_m": round(crow_dist, 1),
                    "connected_network_km": connected_km,
                    "network_gain_km": network_gain_km,
                    "gain_ratio": gain_ratio,
                    "priority_score": score,
                    "streets": streets,
                    "highway_types": highway_types,
                    "avg_penalty": round(avg_pen, 2),
                    "path_nodes": path,
                    "coordinates": coordinates,
                })

            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

    return raw_candidates


def deduplicate_and_rank_candidates(
    candidates: list[dict[str, Any]],
    max_results: int = 12,
) -> list[dict[str, Any]]:
    """
    Deduplicates candidates by:
      1. Component pair: retains the single highest-scoring connection between any two components.
      2. Spatial edge overlap: prevents nearly identical parallel proposals.
    Ranks the final list in descending order of priority score.
    """
    # 1. Group by component pair
    pair_best: dict[tuple[int, int], dict[str, Any]] = {}
    for c in candidates:
        key = tuple(sorted([c["comp_a_id"], c["comp_b_id"]]))
        if key not in pair_best or c["priority_score"] > pair_best[key]["priority_score"]:
            pair_best[key] = c

    sorted_candidates = sorted(pair_best.values(), key=lambda x: x["priority_score"], reverse=True)

    # 2. Filter spatial overlap (if two candidates share > 60% of street names or nodes)
    filtered: list[dict[str, Any]] = []
    seen_node_sets: list[set[int]] = []

    for cand in sorted_candidates:
        cand_nodes = set(cand["path_nodes"])
        is_duplicate = False

        for prev_nodes in seen_node_sets:
            intersection = len(cand_nodes & prev_nodes)
            if intersection > 0.60 * min(len(cand_nodes), len(prev_nodes)):
                is_duplicate = True
                break

        if not is_duplicate:
            seen_node_sets.append(cand_nodes)
            filtered.append(cand)
            if len(filtered) >= max_results:
                break

    return filtered


def generate_missing_connections_geojson(
    candidates: list[dict[str, Any]],
    city_id: str = "curico",
) -> dict[str, Any]:
    """
    Converts ranked candidate connections into a compliant GeoJSON FeatureCollection
    following standard CicloConecta property schemas with cautious terminology.
    """
    features = []

    for i, c in enumerate(candidates, start=1):
        gap_id = f"gap-{city_id}-{i:02d}"
        main_street = c["streets"][0] if c["streets"] else "Conexión barrial"
        streets_str = ", ".join(c["streets"][:3]) if c["streets"] else "Vías urbanas"

        # Cautious, professional community explanation
        explanation = (
            f"Una conexión potencial de aproximadamente {int(c['gap_length_m'])} m en este tramo "
            f"uniría {c['connected_network_km']} km de infraestructura ciclista actualmente separada."
        )

        properties = {
            "id": gap_id,
            "name": f"Oportunidad #{i:02d}: {main_street}",
            "status": "ALGORITHMIC_CANDIDATE",
            "category": "Conexión potencial de continuidad",
            "is_demo": False,
            "rank": i,
            "priority_score": c["priority_score"],
            "gap_length_m": int(c["gap_length_m"]),
            "component_a_km": c["comp_a_km"],
            "component_b_km": c["comp_b_km"],
            "connected_network_km": c["connected_network_km"],
            "network_gain_km": c["network_gain_km"],
            "gain_ratio": c["gain_ratio"],
            "streets": c["streets"],
            "streets_display": streets_str,
            "highway_types": c["highway_types"],
            "description": explanation,
            "reason": "Conecta dos componentes actualmente separados de la red ciclista",
            "disclaimer": "Candidato analítico preliminar. No representa estudio de ingeniería ni proyecto aprobado.",
            "source": "Detector algorítmico de brechas CicloConecta sobre OpenStreetMap",
        }

        feature = {
            "type": "Feature",
            "id": gap_id,
            "properties": properties,
            "geometry": {
                "type": "LineString",
                "coordinates": c["coordinates"],
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "name": f"Conexiones_Potenciales_{city_id.capitalize()}_Algoritmicas",
        "metadata": {
            "city": city_id,
            "is_demo": False,
            "status": "ALGORITHMIC_ANALYSIS",
            "analysis_type": "Multi-criteria Network Component Continuity",
            "total_opportunities": len(features),
            "description": "Oportunidades de continuidad detectadas algorítmicamente sobre la red vial real de OpenStreetMap.",
        },
        "features": features,
    }
