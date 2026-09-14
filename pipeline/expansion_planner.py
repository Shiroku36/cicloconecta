"""
CicloConecta — Algorithmic Cycling Network Expansion Planner (Fase 3.6).

Iterative topological network growth model with dynamic active cycling network.
Discovers underserved urban clusters automatically without hardcoded human anchors.
Regenerates candidates across sequential phases, allowing subsequent phases to branch
from, continue, or cross-connect previously built expansions.
Distinguishes urban expansion vs periurban connectors, calculates dynamic continuity
scores, and explicitly models phase dependencies (depends_on).
"""

import argparse
import heapq
import json
import math
import re
import shutil
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEG_TO_M = 111320.0
CELL_DEG = 0.003  # ~300m spatial grid cell

ACCESS_HIGHWAYS = {
    "residential",
    "living_street",
    "service",
    "unclassified",
    "pedestrian",
    "footway",
    "track",
}


def get_cos_lat(lat_deg: float) -> float:
    """Computes planar latitude scaling factor."""
    return math.cos(math.radians(lat_deg))


def fast_dist_m(lon1: float, lat1: float, lon2: float, lat2: float, cos_lat: float) -> float:
    """Calculates planar approximation distance in meters for local urban scale."""
    dx = (lon2 - lon1) * cos_lat
    dy = lat2 - lat1
    return math.hypot(dx, dy) * DEG_TO_M


def normalize_text(text: str) -> str:
    """Normalizes text for robust matching (lowercase, no accents, alphanumeric)."""
    if not text:
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


class FastSpatialGrid:
    """Spatial 2D hash grid to accelerate radial distance checks in O(1)."""

    def __init__(self, cell_size: float = CELL_DEG, cos_lat: float = 0.819):
        self.cell_size = cell_size
        self.cos_lat = cos_lat
        self.grid: dict[tuple[int, int], list[tuple[Any, float, float]]] = defaultdict(list)
        self.all_coords: list[tuple[float, float]] = []

    def add(self, item_id: Any, lon: float, lat: float) -> None:
        gx = int(lon / self.cell_size)
        gy = int(lat / self.cell_size)
        self.grid[(gx, gy)].append((item_id, lon, lat))
        self.all_coords.append((lon, lat))

    def is_within_dist(self, lon: float, lat: float, max_dist: float = 400.0) -> bool:
        gx = int(lon / self.cell_size)
        gy = int(lat / self.cell_size)
        rad = int(math.ceil(max_dist / (self.cell_size * DEG_TO_M))) + 1
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                for _, clon, clat in self.grid.get((gx + dx, gy + dy), []):
                    if fast_dist_m(lon, lat, clon, clat, self.cos_lat) <= max_dist:
                        return True
        return False

    def min_distance_m(self, lon: float, lat: float, max_search_m: float = 1500.0) -> float:
        gx = int(lon / self.cell_size)
        gy = int(lat / self.cell_size)
        rad = int(math.ceil(max_search_m / (self.cell_size * DEG_TO_M))) + 1
        min_d = float("inf")
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                for _, clon, clat in self.grid.get((gx + dx, gy + dy), []):
                    d = fast_dist_m(lon, lat, clon, clat, self.cos_lat)
                    if d < min_d:
                        min_d = d
        if min_d == float("inf") and self.all_coords:
            min_d = min(fast_dist_m(lon, lat, clon, clat, self.cos_lat) for clon, clat in self.all_coords)
        return min_d


class ActiveCyclingNetwork:
    """
    Explicit representation of the growing cycling network across phases.
    Accumulates base OSM infrastructure and dynamically integrates newly selected phases.
    Allows subsequent phases to branch out from, continue, or cross-connect with
    previously constructed corridors.
    """

    def __init__(
        self,
        base_cycle_nodes: set[int],
        edges: list[dict[str, Any]],
        nodes: dict[int, dict[str, float]],
        cos_lat: float,
    ):
        self.base_cycle_nodes = set(base_cycle_nodes)
        self.active_cycle_nodes = set(base_cycle_nodes)
        self.nodes = nodes
        self.edges = edges
        self.cos_lat = cos_lat

        # Mapping node_id -> set of sources: {"base"} or {"expansion-curico-01", ...}
        self.node_sources: dict[int, set[str]] = defaultdict(set)
        for nid in base_cycle_nodes:
            self.node_sources[nid].add("base")

        # History of added phases
        self.phases: list[dict[str, Any]] = []

        # Spatial grid of active network for fast coverage & distance queries
        self.grid = FastSpatialGrid(cell_size=CELL_DEG, cos_lat=cos_lat)
        for nid in self.active_cycle_nodes:
            pt = self.nodes[nid]
            self.grid.add(nid, pt["lon"], pt["lat"])

        # Origins sampled for reverse Dijkstra routing
        self.sampled_origins: list[int] = []
        self._rebuild_sampled_origins()

    def _rebuild_sampled_origins(self) -> None:
        """Sample origins ~140m apart to keep reverse Dijkstra search fast and thorough."""
        origins = []
        for cid in sorted(self.active_cycle_nodes):
            cn = self.nodes[cid]
            if not any(
                fast_dist_m(cn["lon"], cn["lat"], self.nodes[s]["lon"], self.nodes[s]["lat"], self.cos_lat) < 140.0
                for s in origins
            ):
                origins.append(cid)
        self.sampled_origins = origins

    def add_phase(self, phase_id: str, phase_cand: dict[str, Any]) -> None:
        """Adds selected corridor nodes and edges to the active cycling network."""
        p_nodes = phase_cand["nodes"]
        for nid in p_nodes:
            self.active_cycle_nodes.add(nid)
            self.node_sources[nid].add(phase_id)
            pt = self.nodes[nid]
            self.grid.add(nid, pt["lon"], pt["lat"])

        self.phases.append({
            "phase_id": phase_id,
            "nodes": set(p_nodes),
            "corridor": phase_cand,
        })
        self._rebuild_sampled_origins()

    def get_topology_info(
        self,
        path_nodes: list[int],
        best_orig: int,
        is_structural: bool,
    ) -> tuple[str, list[str]]:
        """
        Determines the expansion_type and explicit dependencies (depends_on).
        - branch: Sprouts from OSM base infrastructure (no prior phases).
        - continuation: Sprouted from a prior phase, extending an existing corridor.
        - trunk_extension: Follows a major structural arterial axis.
        - cross_connector: Links two distinct parts of the active network.
        """
        intersections = set()
        for nid in path_nodes:
            if nid in self.active_cycle_nodes:
                intersections.update(self.node_sources.get(nid, set()))

        dep_phases = sorted(list(intersections - {"base"}))

        if len(dep_phases) == 0:
            exp_type = "trunk_extension" if is_structural else "branch"
        elif "base" in intersections and len(dep_phases) >= 1:
            exp_type = "cross_connector"
        elif len(dep_phases) >= 2:
            exp_type = "cross_connector"
        else:
            exp_type = "trunk_extension" if is_structural else "continuation"

        return exp_type, dep_phases


def fetch_osm_pois(
    bbox: tuple[float, float, float, float],
    cache_path: Optional[Path] = None,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """
    Fetches urban amenities, educational centers, health facilities, parks,
    and public services from OpenStreetMap Overpass API or local cache.
    """
    if cache_path and cache_path.exists() and not force_refresh:
        print(f"  Cargando POIs urbanos desde caché local: {cache_path.name}")
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("elements", [])

    s, w, n, e = bbox
    overpass_endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

    query = f"""[out:json][timeout:45];
(
  node['amenity'~'^(school|college|university|hospital|clinic|doctors|pharmacy|police|fire_station|post_office|townhall|courthouse|community_centre|marketplace|bus_station)']({s},{w},{n},{e});
  node['leisure'~'^(park|pitch|sports_centre|playground)']({s},{w},{n},{e});
  node['shop'~'^(supermarket|mall|department_store)']({s},{w},{n},{e});
  node['railway'~'^(station|halt)']({s},{w},{n},{e});
  way['amenity'~'^(school|college|university|hospital|clinic|townhall|community_centre|marketplace)']({s},{w},{n},{e});
  way['leisure'~'^(park|pitch|sports_centre)']({s},{w},{n},{e});
  way['shop'~'^(supermarket|mall)']({s},{w},{n},{e});
);
out center;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    print(f"  Descargando POIs desde Overpass API para bbox {bbox}...")

    last_err = None
    for endpoint in overpass_endpoints:
        try:
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={"User-Agent": "CicloConecta-ExpansionPlanner/3.6 (contacto@cicloconecta.cl)"},
            )
            with urllib.request.urlopen(req, timeout=50) as resp:
                content = json.loads(resp.read().decode("utf-8"))
                elements = content.get("elements", [])
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)
                print(f"  -> {len(elements)} POIs obtenidos exitosamente desde {endpoint}.")
                return elements
        except Exception as err:
            last_err = err
            print(f"  [Aviso] Fallo en {endpoint}: {err}. Reintentando con otro endpoint...")

    raise RuntimeError(f"Error al descargar POIs desde Overpass: {last_err}")


def parse_and_categorize_pois(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Standardizes POI elements with coordinates, category and subcategory."""
    standard_pois = []
    for el in elements:
        lon = el.get("lon") or (el.get("center", {}).get("lon"))
        lat = el.get("lat") or (el.get("center", {}).get("lat"))
        if lon is None or lat is None:
            continue

        tags = el.get("tags", {})
        amenity = tags.get("amenity", "")
        leisure = tags.get("leisure", "")
        shop = tags.get("shop", "")
        railway = tags.get("railway", "")
        name = tags.get("name") or "Sin nombre"

        if amenity in ("school", "college", "university", "kindergarten"):
            cat = "education"
            subcat = amenity
        elif amenity in ("hospital", "clinic", "doctors", "pharmacy"):
            cat = "healthcare"
            subcat = amenity
        elif shop in ("supermarket", "mall", "department_store") or amenity == "marketplace":
            cat = "commercial"
            subcat = shop or amenity
        elif leisure in ("park", "pitch", "sports_centre", "playground"):
            cat = "parks_leisure"
            subcat = leisure
        elif (
            amenity in ("police", "fire_station", "post_office", "townhall", "courthouse", "community_centre", "bus_station")
            or railway in ("station", "halt")
        ):
            cat = "public_services"
            subcat = amenity or railway
        else:
            cat = "other"
            subcat = amenity or leisure or shop

        standard_pois.append({
            "id": el.get("id"),
            "name": name,
            "category": cat,
            "subcategory": subcat,
            "lon": float(lon),
            "lat": float(lat),
        })

    return standard_pois


def deduplicate_pois(pois: list[dict[str, Any]], cos_lat: float) -> list[dict[str, Any]]:
    """
    Spatial and nominal POI deduplication:
    1. Consolidates POIs within < 15 m of each other regardless of name.
    2. Consolidates POIs of the same category within < 150 m sharing normalized name.
    """
    dedup: list[dict[str, Any]] = []

    for poi in pois:
        p_lon, p_lat = poi["lon"], poi["lat"]
        p_name = normalize_text(poi["name"])
        p_cat = poi["category"]

        merged = False
        for existing in dedup:
            d = fast_dist_m(p_lon, p_lat, existing["lon"], existing["lat"], cos_lat)
            if d < 15.0:
                merged = True
                break
            if d < 150.0 and p_cat == existing["category"] and p_name and p_name != "sin nombre":
                e_name = normalize_text(existing["name"])
                if p_name in e_name or e_name in p_name:
                    merged = True
                    break

        if not merged:
            dedup.append(poi)

    return dedup


def cluster_uncovered_nodes(
    uncovered_nodes: list[dict[str, Any]],
    cos_lat: float,
    eps_m: float = 300.0,
    min_samples: int = 20,
) -> list[list[dict[str, Any]]]:
    """
    DBSCAN spatial clustering on uncovered urban access nodes (> 400m from cycle network).
    Groups dense residential fabrics into macro-sectors purely from data.
    """
    n = len(uncovered_nodes)
    if n < min_samples:
        return []

    grid = defaultdict(list)
    cell_size = eps_m / DEG_TO_M

    for i, node in enumerate(uncovered_nodes):
        gx = int(node["lon"] * cos_lat / cell_size)
        gy = int(node["lat"] / cell_size)
        grid[(gx, gy)].append(i)

    def region_query(idx: int) -> list[int]:
        p = uncovered_nodes[idx]
        gx = int(p["lon"] * cos_lat / cell_size)
        gy = int(p["lat"] / cell_size)
        neighbors = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other_idx in grid.get((gx + dx, gy + dy), []):
                    q = uncovered_nodes[other_idx]
                    if fast_dist_m(p["lon"], p["lat"], q["lon"], q["lat"], cos_lat) <= eps_m:
                        neighbors.append(other_idx)
        return neighbors

    visited = set()
    clusters = []

    for i in range(n):
        if i in visited:
            continue
        visited.add(i)
        neighbors = region_query(i)
        if len(neighbors) < min_samples:
            continue

        cluster = [i]
        queue = list(neighbors)
        in_queue = set(neighbors)

        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                curr_neighbors = region_query(curr)
                if len(curr_neighbors) >= min_samples:
                    for cn in curr_neighbors:
                        if cn not in in_queue and cn not in visited:
                            in_queue.add(cn)
                            queue.append(cn)
            if curr not in cluster:
                cluster.append(curr)

        clusters.append([uncovered_nodes[idx] for idx in cluster])

    clusters.sort(key=lambda cl: len(cl), reverse=True)
    return clusters


def select_cluster_anchors(
    cluster: list[dict[str, Any]],
    dedup_pois: list[dict[str, Any]],
    node_streets: dict[int, set[str]],
    cos_lat: float,
    city_id: str,
    cluster_idx: int,
) -> list[dict[str, Any]]:
    """
    Identifies representative primary and optional secondary anchors for a cluster.
    Maximizes neighborhood density, POI proximity and geometric centrality.
    """
    c_lons = [p["lon"] for p in cluster]
    c_lats = [p["lat"] for p in cluster]
    mean_lon = sum(c_lons) / len(cluster)
    mean_lat = sum(c_lats) / len(cluster)

    best_node = cluster[0]
    best_n_score = -1e9

    for p in cluster:
        n_250 = sum(1 for q in cluster if fast_dist_m(p["lon"], p["lat"], q["lon"], q["lat"], cos_lat) <= 250.0)
        pois_350 = sum(1 for poi in dedup_pois if fast_dist_m(p["lon"], p["lat"], poi["lon"], poi["lat"], cos_lat) <= 350.0)
        d_cent = fast_dist_m(p["lon"], p["lat"], mean_lon, mean_lat, cos_lat)
        n_score = n_250 + 12.0 * pois_350 - 0.05 * d_cent
        if n_score > best_n_score:
            best_n_score = n_score
            best_node = p

    # Representative street names
    st_counter: Counter[str] = Counter()
    for p in cluster:
        for st in node_streets.get(p["id"], []):
            if st != "Calle sin nombre":
                st_counter[st] += 1
    top_st = st_counter.most_common(1)[0][0] if st_counter else "Vía Local"

    # Nearest landmark POI
    near_poi = min(
        dedup_pois,
        key=lambda poi: fast_dist_m(best_node["lon"], best_node["lat"], poi["lon"], poi["lat"], cos_lat),
    ) if dedup_pois else None
    poi_dist = fast_dist_m(best_node["lon"], best_node["lat"], near_poi["lon"], near_poi["lat"], cos_lat) if near_poi else 99999.0
    poi_label = near_poi["name"] if (near_poi and near_poi["name"] != "Sin nombre" and poi_dist < 400.0) else None

    sector_name = f"Sector {top_st}" + (f" / {poi_label}" if poi_label else "")

    anchors = [
        {
            "anchor_type": "primary",
            "node_id": best_node["id"],
            "lon": best_node["lon"],
            "lat": best_node["lat"],
            "sector": sector_name,
            "main_street": top_st,
            "poi_label": poi_label,
        }
    ]

    # Secondary anchor if cluster is large (> 250 nodes)
    if len(cluster) > 250:
        sec_node = None
        sec_score = -1e9
        for p in cluster:
            d_from_prim = fast_dist_m(p["lon"], p["lat"], best_node["lon"], best_node["lat"], cos_lat)
            if d_from_prim < 550.0:
                continue
            n_250 = sum(1 for q in cluster if fast_dist_m(p["lon"], p["lat"], q["lon"], q["lat"], cos_lat) <= 250.0)
            pois_350 = sum(1 for poi in dedup_pois if fast_dist_m(p["lon"], p["lat"], poi["lon"], poi["lat"], cos_lat) <= 350.0)
            d_cent = fast_dist_m(p["lon"], p["lat"], mean_lon, mean_lat, cos_lat)
            n_score = n_250 + 12.0 * pois_350 - 0.05 * d_cent
            if n_score > sec_score:
                sec_score = n_score
                sec_node = p

        if sec_node:
            sec_st_counter: Counter[str] = Counter()
            for p in cluster:
                if fast_dist_m(p["lon"], p["lat"], sec_node["lon"], sec_node["lat"], cos_lat) <= 350.0:
                    for st in node_streets.get(p["id"], []):
                        if st != "Calle sin nombre":
                            sec_st_counter[st] += 1
            sec_top_st = sec_st_counter.most_common(1)[0][0] if sec_st_counter else top_st
            sec_sector = f"Sector {sec_top_st}"
            anchors.append({
                "anchor_type": "secondary",
                "node_id": sec_node["id"],
                "lon": sec_node["lon"],
                "lat": sec_node["lat"],
                "sector": sec_sector,
                "main_street": sec_top_st,
                "poi_label": None,
            })

    return anchors


def plan_city_expansion(
    city_def: dict[str, Any],
    data_dir: Path,
    frontend_dir: Path,
    force_refresh: bool = False,
    max_phases: int = 6,
) -> dict[str, Any]:
    """
    Computes territorial coverage, discovers underserved clusters automatically,
    derives optimal anchors, generates multiple corridor alternatives, evaluates
    candidates multi-critically with dynamic topology scoring, and constructs sequential
    investment phases through iterative active-network growth.
    """
    city_id = city_def["id"]
    city_name = city_def["name"]
    bbox = tuple(city_def.get("bounds", [-35.05, -71.3, -34.93, -71.18]))
    s, w, n, e = bbox[0][1], bbox[0][0], bbox[1][1], bbox[1][0]
    bbox_tuple = (s, w, n, e)

    start_time = time.time()
    print(f"\n[Fase 3.6] Iniciando Planificador Topológico de Expansión para {city_name} ({city_id})...")

    # 1. Load navigable graph
    nav_graph_path = data_dir / "nav_graph.json"
    if not nav_graph_path.exists():
        raise FileNotFoundError(f"No se encontró nav_graph.json en {data_dir}. Ejecute build_city primero.")

    with open(nav_graph_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    nodes = {node["id"]: {"lon": node["lon"], "lat": node["lat"]} for node in graph_data["nodes"]}
    edges = graph_data["edges"]

    cos_lat = math.cos(math.radians((s + n) / 2.0))

    # 2. Extract base cycling infrastructure nodes
    cycle_nodes = set()
    for ed in edges:
        if ed.get("is_cycling_infra"):
            cycle_nodes.add(ed["u"])
            cycle_nodes.add(ed["v"])

    if not cycle_nodes:
        print(f"  [Aviso] No se detectó infraestructura ciclista en {city_name} para proyectar expansiones.")
        return {"features": [], "metadata": {}}

    # 3. Extract urban access nodes (proxy de tejido urbano accesible)
    urban_access_nodes = set()
    node_streets = defaultdict(set)
    for ed in edges:
        st = ed.get("name")
        if st:
            node_streets[ed["u"]].add(st)
            node_streets[ed["v"]].add(st)
        if ed.get("highway") in ACCESS_HIGHWAYS:
            urban_access_nodes.add(ed["u"])
            urban_access_nodes.add(ed["v"])

    # 4. Fetch, categorize, and deduplicate POIs
    raw_pois_cache = data_dir / "raw_pois.json"
    raw_poi_elements = fetch_osm_pois(bbox_tuple, cache_path=raw_pois_cache, force_refresh=force_refresh)
    cat_pois = parse_and_categorize_pois(raw_poi_elements)
    dedup_pois = deduplicate_pois(cat_pois, cos_lat)
    print(f"  POIs urbanos: {len(cat_pois)} brutos -> {len(dedup_pois)} únicos tras deduplicación espacial.")

    # 5. Initialize Active Cycling Network
    active_net = ActiveCyclingNetwork(cycle_nodes, edges, nodes, cos_lat)

    # Calculate baseline distance bands with base network
    dist_bands = {"0-250m": 0, "250-500m": 0, "500-1000m": 0, ">1000m": 0}
    base_covered_nodes = set()
    for nid in sorted(urban_access_nodes):
        n_pt = nodes[nid]
        d = active_net.grid.min_distance_m(n_pt["lon"], n_pt["lat"], max_search_m=1600.0)
        if d <= 250.0:
            dist_bands["0-250m"] += 1
        elif d <= 500.0:
            dist_bands["250-500m"] += 1
        elif d <= 1000.0:
            dist_bands["500-1000m"] += 1
        else:
            dist_bands[">1000m"] += 1

        if d <= 400.0:
            base_covered_nodes.add(nid)

    base_covered_pois = set()
    for p in dedup_pois:
        if active_net.grid.is_within_dist(p["lon"], p["lat"], 400.0):
            base_covered_pois.add(p["id"])

    base_cov_pct = round((len(base_covered_nodes) / max(len(urban_access_nodes), 1)) * 100.0, 1)
    base_poi_pct = round((len(base_covered_pois) / max(len(dedup_pois), 1)) * 100.0, 1)

    print(f"  Cobertura base ({base_cov_pct}% nodos de acceso urbano, {base_poi_pct}% POIs a <= 400m):")
    print(f"    0–250 m: {dist_bands['0-250m']} | 250–500 m: {dist_bands['250-500m']} | 500–1000 m: {dist_bands['500-1000m']} | >1000 m: {dist_bands['>1000m']}")

    # 6. Build routing graph adjacencies (Direct & Structural Axis)
    adj_direct = defaultdict(list)
    adj_structural = defaultdict(list)

    for ed in edges:
        u, v = ed["u"], ed["v"]
        length = ed.get("length_m", 10.0)
        hw = ed.get("highway", "residential")
        name = ed.get("name") or "Calle sin nombre"
        is_infra = ed.get("is_cycling_infra", False)

        if hw in ("motorway", "motorway_link"):
            continue

        c_dir = length * (0.50 if is_infra else 1.00)

        if is_infra:
            c_str = length * 0.50
        elif hw in ("secondary", "secondary_link"):
            c_str = length * 0.60
        elif hw in ("tertiary", "tertiary_link"):
            c_str = length * 0.70
        elif hw in ("residential", "living_street"):
            c_str = length * 1.25
        else:
            c_str = length * 1.50

        adj_direct[u].append({"v": v, "length_m": length, "cost": c_dir, "name": name, "highway": hw, "is_infra": is_infra})
        adj_direct[v].append({"v": u, "length_m": length, "cost": c_dir, "name": name, "highway": hw, "is_infra": is_infra})
        adj_structural[u].append({"v": v, "length_m": length, "cost": c_str, "name": name, "highway": hw, "is_infra": is_infra})
        adj_structural[v].append({"v": u, "length_m": length, "cost": c_str, "name": name, "highway": hw, "is_infra": is_infra})

    # Baseline clusters discovery for metadata reporting
    initial_uncovered = []
    for nid in sorted(urban_access_nodes):
        n_pt = nodes[nid]
        if nid not in base_covered_nodes:
            d = active_net.grid.min_distance_m(n_pt["lon"], n_pt["lat"], max_search_m=1600.0)
            initial_uncovered.append({"id": nid, "lon": n_pt["lon"], "lat": n_pt["lat"], "dist": d})

    initial_clusters = cluster_uncovered_nodes(initial_uncovered, cos_lat=cos_lat, eps_m=300.0, min_samples=20)
    print(f"  Nodos de acceso desatendidos base (> 400 m): {len(initial_uncovered)}")
    print(f"  -> {len(initial_clusters)} clusters territoriales desatendidos iniciales descubiertos.")

    discovered_clusters_meta = []
    for c_idx, cl in enumerate(initial_clusters[:10], 1):
        c_lons = [p["lon"] for p in cl]
        c_lats = [p["lat"] for p in cl]
        mean_lon, mean_lat = sum(c_lons) / len(cl), sum(c_lats) / len(cl)
        mean_d = sum(p["dist"] for p in cl) / len(cl)
        max_d = max(p["dist"] for p in cl)
        bbox_cl = [min(c_lats), min(c_lons), max(c_lats), max(c_lons)]

        nearby_p_ids = set()
        for p in dedup_pois:
            if any(fast_dist_m(p["lon"], p["lat"], q["lon"], q["lat"], cos_lat) <= 400.0 for q in cl[::4]):
                nearby_p_ids.add(p["id"])

        need_score = round(len(cl) * (1.0 + mean_d / 500.0) + 12.0 * len(nearby_p_ids), 1)
        discovered_clusters_meta.append({
            "id": f"cluster-{city_id}-{c_idx:02d}",
            "centroid": [round(mean_lon, 6), round(mean_lat, 6)],
            "node_count": len(cl),
            "mean_distance_to_cycle_network": round(mean_d, 1),
            "max_distance_to_cycle_network": round(max_d, 1),
            "bbox": [round(b, 6) for b in bbox_cl],
            "nearby_pois_count": len(nearby_p_ids),
            "coverage_need_score": need_score,
        })

    # 7. Iterative Topological Growth Across Sequential Phases
    active_covered_pois = set(base_covered_pois)
    selected_phases = []
    all_evaluated_candidates_count = 0

    for phase_num in range(1, max_phases + 1):
        # 7.1 Recalculate currently uncovered nodes against the active network
        current_uncovered = []
        for nid in sorted(urban_access_nodes):
            n_pt = nodes[nid]
            if not active_net.grid.is_within_dist(n_pt["lon"], n_pt["lat"], 400.0):
                d = active_net.grid.min_distance_m(n_pt["lon"], n_pt["lat"], max_search_m=1600.0)
                current_uncovered.append({"id": nid, "lon": n_pt["lon"], "lat": n_pt["lat"], "dist": d})

        if not current_uncovered:
            print("  [Fin] Todos los nodos urbanos están cubiertos.")
            break

        # 7.2 Discover active clusters of remaining uncovered nodes
        active_clusters = cluster_uncovered_nodes(current_uncovered, cos_lat=cos_lat, eps_m=300.0, min_samples=20)
        if not active_clusters:
            print("  [Fin] No se detectaron más concentraciones densas de demanda insatisfecha.")
            break

        # 7.3 Generate multi-alternative candidate corridors targeting the CURRENT active_net
        phase_candidates = []

        for c_idx, cl in enumerate(active_clusters[:8], 1):
            anchors = select_cluster_anchors(cl, dedup_pois, node_streets, cos_lat, city_id, c_idx)

            for anc in anchors:
                target_id = anc["node_id"]
                t_lon, t_lat = anc["lon"], anc["lat"]

                for alt_name, adj_graph in [("Directo", adj_direct), ("Eje Estructurante", adj_structural)]:
                    is_struct = (alt_name == "Eje Estructurante")
                    dist = {target_id: 0.0}
                    prev = {}
                    heap = [(0.0, target_id)]

                    while heap:
                        cur, u = heapq.heappop(heap)
                        if cur > 3800.0 or cur > dist.get(u, float("inf")):
                            continue
                        for edge in adj_graph[u]:
                            v = edge["v"]
                            nc = cur + edge["cost"]
                            if nc < dist.get(v, float("inf")) and nc <= 3800.0:
                                dist[v] = nc
                                prev[v] = (u, edge)
                                heapq.heappush(heap, (nc, v))

                    # Reached origins within the CURRENT active cycling network!
                    origins_reached = [(dist[orig], orig) for orig in active_net.sampled_origins if orig in dist]
                    origins_reached.sort()

                    for _, best_orig in origins_reached[:2]:
                        curr = best_orig
                        path_nodes = [curr]
                        path_edges = []

                        while curr != target_id:
                            if curr not in prev:
                                break
                            parent, e_info = prev[curr]
                            path_edges.append(e_info)
                            curr = parent
                            path_nodes.append(curr)

                        if curr != target_id or len(path_nodes) < 2:
                            continue

                        total_len_m = sum(e["length_m"] for e in path_edges)
                        if total_len_m < 500.0 or total_len_m > 3500.0:
                            continue

                        crow_m = fast_dist_m(t_lon, t_lat, nodes[best_orig]["lon"], nodes[best_orig]["lat"], cos_lat)
                        zigzag = total_len_m / max(crow_m, 1.0)
                        if zigzag > 1.35:
                            continue

                        # Overlap check with existing and projected active network
                        active_overlap_len = sum(
                            e["length_m"] for e in path_edges
                            if e["is_infra"] or e["v"] in active_net.active_cycle_nodes
                        )
                        if (active_overlap_len / total_len_m) > 0.35:
                            continue

                        # Structural axis analysis
                        struct_len = sum(e["length_m"] for e in path_edges if e["highway"] in ("secondary", "tertiary", "primary"))
                        struct_ratio = round(struct_len / total_len_m, 2)
                        axis_score = round(5.0 + 5.0 * struct_ratio, 1)

                        st_names = [e["name"] for e in path_edges if e["name"] != "Calle sin nombre"]
                        st_unique = list(dict.fromkeys(st_names))[:4]
                        main_st = st_unique[0] if st_unique else anc["main_street"]

                        # Urban vs Periurban classification
                        track_len = sum(e["length_m"] for e in path_edges if e["highway"] in ("track", "unclassified"))
                        track_ratio = track_len / total_len_m

                        nearby_pois_count = sum(
                            1 for p in dedup_pois
                            if any(fast_dist_m(p["lon"], p["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in path_nodes[::4])
                        )

                        is_rural_name = any(r in main_st.lower() for r in ["ruta j-", "camino", "callejón"])
                        if track_ratio >= 0.35 or (total_len_m > 1800.0 and nearby_pois_count <= 3) or (is_rural_name and nearby_pois_count <= 2):
                            urban_context = "periurban"
                            env_label = "Conector Periurbano"
                        elif nearby_pois_count >= 4 or track_ratio <= 0.15:
                            urban_context = "urban"
                            env_label = "Expansión Urbana"
                        else:
                            urban_context = "uncertain"
                            env_label = "Mixto / Transición"

                        # Topological role and dependencies
                        exp_type, dep_phases = active_net.get_topology_info(path_nodes, best_orig, is_struct)

                        # Dynamic continuity score S_cont in [8.0, 20.0]
                        s_conn = 6.0 if len(dep_phases) == 0 else 5.0
                        if exp_type == "cross_connector":
                            s_syn = 5.0
                        elif exp_type == "continuation":
                            s_syn = 4.5
                        elif exp_type == "trunk_extension":
                            s_syn = 4.0
                        else:
                            s_syn = 2.5

                        s_align = 4.0 if is_struct or struct_ratio >= 0.30 else 2.5
                        s_role = 3.0 if urban_context == "urban" else (2.0 if exp_type == "trunk_extension" else 1.5)
                        s_cont = round(min(20.0, max(8.0, s_conn + s_syn + s_align + s_role)), 1)

                        # Newly covered access nodes
                        new_nodes = sum(
                            1 for nid in current_uncovered
                            if any(fast_dist_m(nodes[nid["id"]]["lon"], nodes[nid["id"]]["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in path_nodes[::3])
                        )

                        # Newly covered POIs
                        new_pois = sum(
                            1 for p in dedup_pois
                            if p["id"] not in active_covered_pois
                            and any(fast_dist_m(p["lon"], p["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in path_nodes[::3])
                        )

                        eff_ratio = round(new_nodes / max(total_len_m / 1000.0, 0.1), 1)
                        s_cov = min(35.0, (new_nodes / 250.0) * 35.0)
                        s_poi = min(25.0, (new_pois / 8.0) * 25.0)
                        s_eff = min(10.0, (eff_ratio / 180.0) * 10.0)
                        total_score = round(s_cov + s_poi + s_cont + axis_score + s_eff, 1)

                        cand = {
                            "cluster_id": f"cluster-{city_id}-{c_idx:02d}",
                            "cluster_size": len(cl),
                            "anchor_type": anc["anchor_type"],
                            "alt_type": alt_name,
                            "sector": anc["sector"],
                            "target_id": target_id,
                            "origin_id": best_orig,
                            "nodes": path_nodes,
                            "edges": path_edges,
                            "length_m": round(total_len_m, 1),
                            "length_km": round(total_len_m / 1000.0, 2),
                            "crow_m": round(crow_m, 1),
                            "zigzag_ratio": round(zigzag, 2),
                            "structural_ratio": struct_ratio,
                            "structural_axis_score": axis_score,
                            "streets": st_unique,
                            "main_street": main_st,
                            "expansion_type": exp_type,
                            "depends_on": dep_phases,
                            "urban_context": urban_context,
                            "environment_label": env_label,
                            "new_nodes": new_nodes,
                            "new_pois": new_pois,
                            "s_cov": round(s_cov, 1),
                            "s_poi": round(s_poi, 1),
                            "s_cont": s_cont,
                            "s_axis": axis_score,
                            "s_eff": round(s_eff, 1),
                            "total_score": total_score,
                            "nearby_pois_count": nearby_pois_count,
                        }

                        # Check uniqueness against this phase candidates
                        node_key = tuple(path_nodes)
                        if not any(tuple(c["nodes"]) == node_key for c in phase_candidates):
                            phase_candidates.append(cand)

        if not phase_candidates:
            print(f"  [Aviso] No se encontraron corredores viables para la Fase {phase_num}.")
            break

        all_evaluated_candidates_count += len(phase_candidates)

        # 7.4 Select best candidate for this phase
        phase_candidates.sort(key=lambda c: c["total_score"], reverse=True)
        best_cand = phase_candidates[0]

        phase_id = f"expansion-{city_id}-{phase_num:02d}"
        active_net.add_phase(phase_id, best_cand)

        # Update covered POIs
        for p in dedup_pois:
            if p["id"] not in active_covered_pois:
                if any(fast_dist_m(p["lon"], p["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in best_cand["nodes"][::3]):
                    active_covered_pois.add(p["id"])

        selected_phases.append(best_cand)

        dep_str = f" | Dep: {best_cand['depends_on']}" if best_cand["depends_on"] else ""
        print(
            f"  [Fase {phase_num}] {best_cand['sector']} ({best_cand['environment_label']}) | "
            f"{best_cand['length_km']} km | +{best_cand['new_nodes']} nodos | +{best_cand['new_pois']} POIs | "
            f"Tipo: {best_cand['expansion_type']}{dep_str} | S_cont: {best_cand['s_cont']} | Score: {best_cand['total_score']} pts"
        )

    # 8. Build GeoJSON Features
    features = []
    cum_km = 0.0
    cum_nodes = 0
    cum_pois = 0

    for idx, c in enumerate(selected_phases, 1):
        cum_km += c["length_km"]
        cum_nodes += c["new_nodes"]
        cum_pois += c["new_pois"]

        coords = [[nodes[nid]["lon"], nodes[nid]["lat"]] for nid in c["nodes"]]

        feat = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "id": f"expansion-{city_id}-{idx:02d}",
                "phase": idx,
                "sector": c["sector"],
                "target_sector": c["sector"],
                "main_street": c["main_street"],
                "streets": c["streets"],
                "corridor_type": c["alt_type"],
                "expansion_type": c["expansion_type"],
                "depends_on": c["depends_on"],
                "urban_context": c["urban_context"],
                "environment_label": c["environment_label"],
                "length_m": c["length_m"],
                "length_km": c["length_km"],
                "score": c["total_score"],
                "structural_axis_score": c["structural_axis_score"],
                "structural_ratio": c["structural_ratio"],
                "physical_width_status": "UNVERIFIED_IN_OSM",
                "score_breakdown": {
                    "coverage": c["s_cov"],
                    "pois": c["s_poi"],
                    "continuity": c["s_cont"],
                    "structural_axis": c["s_axis"],
                    "efficiency": c["s_eff"],
                },
                "marginal_gain": {
                    "urban_access_nodes": c["new_nodes"],
                    "pois": c["new_pois"],
                },
                "cumulative_totals": {
                    "length_km": round(cum_km, 2),
                    "urban_access_nodes": cum_nodes,
                    "pois": cum_pois,
                },
                "disclaimer": (
                    "Propuesta analítica de expansión de red basada en conectividad vial y equipamientos de OpenStreetMap. "
                    "No evalúa ancho físico ni garantiza factibilidad constructiva sin estudio de ingeniería de tránsito."
                ),
            },
        }
        features.append(feat)

    total_km = round(sum(f["properties"]["length_km"] for f in features), 2)
    total_nodes_gained = sum(f["properties"]["marginal_gain"]["urban_access_nodes"] for f in features)
    total_pois_gained = sum(f["properties"]["marginal_gain"]["pois"] for f in features)
    final_cov_pct = round(((len(base_covered_nodes) + total_nodes_gained) / max(len(urban_access_nodes), 1)) * 100.0, 1)
    cov_gain_pct = round(final_cov_pct - base_cov_pct, 2)

    # Breakdown by expansion type
    type_counts = Counter(f["properties"]["expansion_type"] for f in features)
    context_counts = Counter(f["properties"]["urban_context"] for f in features)

    geojson_output = {
        "type": "FeatureCollection",
        "metadata": {
            "city_id": city_id,
            "city_name": city_name,
            "layer_id": "network-expansion",
            "layer_name": "Expansión de red",
            "badge": "ANÁLISIS",
            "status": "ALGORITHMIC_EXPANSION",
            "model_version": "3.6-iterative-topological",
            "total_phases": len(features),
            "total_expansion_km": total_km,
            "total_new_urban_access_nodes": total_nodes_gained,
            "total_new_nodes": total_nodes_gained,
            "total_coverage_gain_pct": cov_gain_pct,
            "total_new_pois": total_pois_gained,
            "expansion_types_summary": dict(type_counts),
            "urban_contexts_summary": dict(context_counts),
            "poi_deduplication": {
                "raw_pois_count": len(cat_pois),
                "deduplicated_pois_count": len(dedup_pois),
            },
            "discovered_clusters": discovered_clusters_meta,
            "evaluated_candidates_count": all_evaluated_candidates_count,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
        "features": features,
    }

    # 9. Save and sync GeoJSON
    out_file = data_dir / "network-expansion.geojson"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(geojson_output, f, ensure_ascii=False, indent=2)
    print(f"  -> {len(features)} fases de expansión guardadas en {out_file.name}.")

    pub_dir = frontend_dir / "public" / "data" / "cities" / city_id
    if pub_dir.exists():
        pub_file = pub_dir / "network-expansion.geojson"
        shutil.copy2(out_file, pub_file)
        print(f"  -> Sincronizado a {pub_file}.")

    # 10. Update city.json
    city_json_path = data_dir / "city.json"
    if city_json_path.exists():
        with open(city_json_path, "r", encoding="utf-8") as f:
            city_json = json.load(f)

        city_json["expansion"] = {
            "total_phases": len(features),
            "total_expansion_km": total_km,
            "total_new_urban_access_nodes": total_nodes_gained,
            "total_coverage_gain_pct": cov_gain_pct,
            "total_new_pois": total_pois_gained,
            "expansion_types_summary": dict(type_counts),
            "urban_contexts_summary": dict(context_counts),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        with open(city_json_path, "w", encoding="utf-8") as f:
            json.dump(city_json, f, ensure_ascii=False, indent=2)

        pub_city_json = pub_dir / "city.json"
        if pub_city_json.exists():
            shutil.copy2(city_json_path, pub_city_json)

    elapsed = round(time.time() - start_time, 1)
    print(f"  Completado en {elapsed}s: {len(features)} fases, +{total_km} km de red proyectada.")
    return geojson_output


def main():
    parser = argparse.ArgumentParser(description="CicloConecta — Planificador Topológico de Expansión (Fase 3.6)")
    parser.add_argument("--city", default="curico", help="ID de la ciudad a procesar (ej. curico, talca)")
    parser.add_argument("--refresh", action="store_true", help="Forzar recarga de POIs desde Overpass")
    parser.add_argument("--max-phases", type=int, default=6, help="Número máximo de fases de expansión")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data" / "cities" / args.city
    frontend_dir = project_root / "frontend"

    city_json = data_dir / "city.json"
    if not city_json.exists():
        print(f"Error: No existe {city_json}")
        sys.exit(1)

    with open(city_json, "r", encoding="utf-8") as f:
        city_def = json.load(f)

    plan_city_expansion(
        city_def=city_def,
        data_dir=data_dir,
        frontend_dir=frontend_dir,
        force_refresh=args.refresh,
        max_phases=args.max_phases,
    )


if __name__ == "__main__":
    main()