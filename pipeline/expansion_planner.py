"""
CicloConecta — Algorithmic Cycling Network Expansion Planner (Fase 3.5).

Automated, purely data-driven territorial expansion planner.
Discovers underserved urban clusters automatically without hardcoded human anchors.
Evaluates urban access nodes (proxy for accessible urban fabric) and deduplicated OSM POIs,
generates multiple corridor alternatives per cluster, scores candidates multi-critically (0-100),
and constructs sequential investment phases through greedy iterative growth.
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
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"User-Agent": "CicloConecta-ExpansionPlanner/1.0 (https://github.com/shiroku36/cicloconecta)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
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
        elif amenity in ("police", "fire_station", "post_office", "townhall", "courthouse", "community_centre", "bus_station") or railway in ("station", "halt"):
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
    Deduplicates POIs based on spatial proximity and normalized names.
    Prevents multiple nodes/ways representing the same facility (e.g. courts in a club)
    from inflating coverage scores.
    """
    sorted_pois = sorted(pois, key=lambda p: (p.get("id") or 0, p["lon"], p["lat"]))
    deduped = []
    grid: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    cell_size = 0.003

    for p in sorted_pois:
        gx = int(p["lon"] / cell_size)
        gy = int(p["lat"] / cell_size)
        is_dup = False
        nname = normalize_text(p["name"])
        cat = p["category"]

        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for prev in grid.get((gx + dx, gy + dy), []):
                    d = fast_dist_m(p["lon"], p["lat"], prev["lon"], prev["lat"], cos_lat)
                    # 1. Exact or near duplicate location (< 15m)
                    if d <= 15.0:
                        is_dup = True
                        break
                    # 2. Same category and same normalized name within 150m
                    if d <= 150.0 and cat == prev["category"]:
                        pname = normalize_text(prev["name"])
                        if nname and pname and nname not in ("sin nombre", "") and pname not in ("sin nombre", ""):
                            if nname == pname or (len(nname) > 5 and (nname in pname or pname in nname)):
                                is_dup = True
                                break
                        # 3. Nameless facilities of same subcategory within 40m (e.g. adjacent pitches)
                        elif d <= 40.0 and p["subcategory"] == prev["subcategory"]:
                            is_dup = True
                            break
                if is_dup:
                    break

        if not is_dup:
            deduped.append(p)
            grid[(gx, gy)].append(p)

    return deduped


def cluster_uncovered_nodes(
    uncovered_nodes: list[dict[str, Any]],
    cos_lat: float,
    eps_m: float = 300.0,
    min_samples: int = 20,
) -> list[list[dict[str, Any]]]:
    """
    Deterministic DBSCAN spatial clustering over uncovered urban access nodes.
    Groups nodes into spatial clusters of underserved urban fabric without random seeds.
    """
    scell = 0.003
    sgrid: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for p in uncovered_nodes:
        gx = int(p["lon"] / scell)
        gy = int(p["lat"] / scell)
        sgrid[(gx, gy)].append(p)

    def get_neighbors(p: dict[str, Any]) -> list[dict[str, Any]]:
        gx = int(p["lon"] / scell)
        gy = int(p["lat"] / scell)
        res = []
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for q in sgrid.get((gx + dx, gy + dy), []):
                    if fast_dist_m(p["lon"], p["lat"], q["lon"], q["lat"], cos_lat) <= eps_m:
                        res.append(q)
        return res

    visited = set()
    clusters = []

    # Sort deterministically by node id
    for p in sorted(uncovered_nodes, key=lambda x: x["id"]):
        if p["id"] in visited:
            continue
        visited.add(p["id"])
        nbrs = get_neighbors(p)
        if len(nbrs) < min_samples:
            continue

        cluster = [p]
        queue = list(sorted(nbrs, key=lambda x: x["id"]))
        q_set = set(n["id"] for n in nbrs)

        while queue:
            q = queue.pop(0)
            if q["id"] not in visited:
                visited.add(q["id"])
                q_nbrs = get_neighbors(q)
                if len(q_nbrs) >= min_samples:
                    for n_pt in sorted(q_nbrs, key=lambda x: x["id"]):
                        if n_pt["id"] not in q_set:
                            q_set.add(n_pt["id"])
                            queue.append(n_pt)
            if q not in cluster:
                cluster.append(q)

        clusters.append(cluster)

    clusters.sort(key=lambda c: len(c), reverse=True)
    return clusters


def select_cluster_anchors(
    cluster: list[dict[str, Any]],
    dedup_pois: list[dict[str, Any]],
    node_streets: dict[Any, set[str]],
    cos_lat: float,
    city_id: str,
    cluster_idx: int,
) -> list[dict[str, Any]]:
    """
    Selects 1 or 2 representative anchor nodes for a cluster based on local density,
    proximity to POIs, and geometric centrality. Derives sector names automatically.
    """
    c_lons = [p["lon"] for p in cluster]
    c_lats = [p["lat"] for p in cluster]
    mean_lon, mean_lat = sum(c_lons) / len(cluster), sum(c_lats) / len(cluster)

    # Primary anchor
    best_node = None
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
    poi_dist = fast_dist_m(best_node["lon"], best_node["lat"], near_poi["lon"], near_poi["lat"], cos_lat) if near_poi else float("inf")
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


def get_debug_manual_anchors(city_id: str) -> list[dict[str, Any]]:
    """
    OPTIONAL debugging helper retaining legacy manual points for benchmarking comparisons.
    NOT used in the production algorithm.
    """
    if city_id == "curico":
        return [
            {"id": "rauquen-extension", "sector": "Rauquén Norte / Don Sebastián", "coords": (-71.2037, -34.9427)},
            {"id": "mataquito-licanten", "sector": "Mataquito / Licantén", "coords": (-71.2575, -34.9966)},
            {"id": "santa-fe", "sector": "Santa Fe Poniente", "coords": (-71.2580, -34.9880)},
            {"id": "zapallar-oriente", "sector": "Zapallar / Los Cristales", "coords": (-71.1988, -34.9810)},
            {"id": "tutuquen-poniente", "sector": "Tutuquén Norponiente", "coords": (-71.2720, -34.9750)},
        ]
    return []


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
    multi-criteria scores, and produces an iterative greedy expansion master plan.
    """
    city_id = city_def["id"]
    city_name = city_def["name"]
    bbox = tuple(city_def["bbox"])
    s, w, n, e = bbox
    center_lat = (s + n) / 2.0
    cos_lat = get_cos_lat(center_lat)

    t0 = time.time()
    print(f"[Fase 3.5] Iniciando Planificador de Expansión Inductivo para {city_name} ({city_id})...")

    # 1. Load navigable graph
    nav_graph_path = data_dir / "nav_graph.json"
    if not nav_graph_path.exists():
        raise FileNotFoundError(f"nav_graph.json no encontrado para {city_id} en {nav_graph_path}")

    with open(nav_graph_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    nodes = {nd["id"]: nd for nd in graph_data["nodes"]}
    edges = graph_data["edges"]

    # 2. Extract cycling network nodes & sample origins
    cycle_nodes = set()
    for ed in edges:
        if ed.get("is_cycling_infra"):
            cycle_nodes.add(ed["u"])
            cycle_nodes.add(ed["v"])

    if not cycle_nodes:
        print(f"  [Aviso] No se detectó infraestructura ciclista en {city_name} para proyectar expansiones.")
        return {"features": [], "metadata": {}}

    sampled_origins = []
    for cid in sorted(cycle_nodes):
        cn = nodes[cid]
        if not any(fast_dist_m(cn["lon"], cn["lat"], nodes[s]["lon"], nodes[s]["lat"], cos_lat) < 140.0 for s in sampled_origins):
            sampled_origins.append(cid)

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
    raw_poi_elements = fetch_osm_pois(bbox, cache_path=raw_pois_cache, force_refresh=force_refresh)
    cat_pois = parse_and_categorize_pois(raw_poi_elements)
    dedup_pois = deduplicate_pois(cat_pois, cos_lat)
    print(f"  POIs urbanos: {len(cat_pois)} brutos -> {len(dedup_pois)} únicos tras deduplicación espacial.")

    # 5. Baseline coverage and distance bands
    cgrid = FastSpatialGrid(cell_size=CELL_DEG, cos_lat=cos_lat)
    for cid in cycle_nodes:
        cn = nodes[cid]
        cgrid.add(cid, cn["lon"], cn["lat"])

    dist_bands = {"0-250m": 0, "250-500m": 0, "500-1000m": 0, ">1000m": 0}
    base_covered_nodes = set()
    uncovered_nodes = []

    for nid in sorted(urban_access_nodes):
        n_pt = nodes[nid]
        d = cgrid.min_distance_m(n_pt["lon"], n_pt["lat"], max_search_m=1600.0)
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
        else:
            uncovered_nodes.append({"id": nid, "lon": n_pt["lon"], "lat": n_pt["lat"], "dist": d})

    base_covered_pois = set()
    for p in dedup_pois:
        if cgrid.is_within_dist(p["lon"], p["lat"], 400.0):
            base_covered_pois.add(p["id"])

    base_cov_pct = round((len(base_covered_nodes) / max(len(urban_access_nodes), 1)) * 100.0, 1)
    base_poi_pct = round((len(base_covered_pois) / max(len(dedup_pois), 1)) * 100.0, 1)

    print(f"  Cobertura base ({base_cov_pct}% nodos de acceso urbano, {base_poi_pct}% POIs a <= 400m):")
    print(f"    0–250 m: {dist_bands['0-250m']} | 250–500 m: {dist_bands['250-500m']} | 500–1000 m: {dist_bands['500-1000m']} | >1000 m: {dist_bands['>1000m']}")
    print(f"  Nodos de acceso desatendidos (> 400 m): {len(uncovered_nodes)}")

    # 6. Automated spatial clustering of uncovered nodes (DBSCAN)
    clusters = cluster_uncovered_nodes(uncovered_nodes, cos_lat=cos_lat, eps_m=300.0, min_samples=20)
    print(f"  -> {len(clusters)} clusters territoriales desatendidos descubiertos algorítmicamente.")

    discovered_clusters_meta = []
    for c_idx, cl in enumerate(clusters[:10], 1):
        c_lons = [p["lon"] for p in cl]
        c_lats = [p["lat"] for p in cl]
        mean_lon, mean_lat = sum(c_lons) / len(cl), sum(c_lats) / len(cl)
        mean_d = sum(p["dist"] for p in cl) / len(cl)
        max_d = max(p["dist"] for p in cl)
        bbox_cl = [min(c_lats), min(c_lons), max(c_lats), max(c_lons)]

        # Nearby POIs within 400m of any node in cluster
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

    # 7. Build routing graph adjacencies (Direct & Structural Axis)
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

    # 8. Generate multi-alternative candidate corridors from discovered cluster anchors
    all_candidates = []

    for c_idx, cl in enumerate(clusters[:8], 1):
        anchors = select_cluster_anchors(cl, dedup_pois, node_streets, cos_lat, city_id, c_idx)

        for anc in anchors:
            target_id = anc["node_id"]
            t_lon, t_lat = anc["lon"], anc["lat"]

            for alt_name, adj_graph in [("Directo", adj_direct), ("Eje Estructurante", adj_structural)]:
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

                origins_reached = [(dist[orig], orig) for orig in sampled_origins if orig in dist]
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

                    # Overlap with existing cycleway
                    cycle_len = sum(e["length_m"] for e in path_edges if e["is_infra"])
                    if (cycle_len / total_len_m) > 0.30:
                        continue

                    # Structural axis calculation
                    struct_len = sum(e["length_m"] for e in path_edges if e["highway"] in ("secondary", "tertiary", "primary"))
                    struct_ratio = round(struct_len / total_len_m, 2)
                    axis_score = round(5.0 + 5.0 * struct_ratio, 1)

                    st_names = [e["name"] for e in path_edges if e["name"] != "Calle sin nombre"]
                    st_unique = list(dict.fromkeys(st_names))[:4]
                    main_st = st_unique[0] if st_unique else anc["main_street"]

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
                    }

                    node_key = tuple(path_nodes)
                    if not any(tuple(c["nodes"]) == node_key for c in all_candidates):
                        all_candidates.append(cand)

    print(f"  -> {len(all_candidates)} alternativas de corredores generadas.")

    # 9. Greedy iterative selection across phases
    active_covered_nodes = set(base_covered_nodes)
    active_covered_pois = set(base_covered_pois)
    selected_phases = []
    remaining_candidates = list(all_candidates)

    for phase_idx in range(1, max_phases + 1):
        best_cand = None
        best_score = -1e9
        best_eval = None

        for c in remaining_candidates:
            c_nodes = c["nodes"]
            # Newly covered urban access nodes
            new_nodes = 0
            for nid in urban_access_nodes:
                if nid not in active_covered_nodes:
                    un = nodes[nid]
                    if any(fast_dist_m(un["lon"], un["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in c_nodes[::3]):
                        new_nodes += 1

            # Newly covered POIs
            new_pois = 0
            for p in dedup_pois:
                if p["id"] not in active_covered_pois:
                    if any(fast_dist_m(p["lon"], p["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in c_nodes[::3]):
                        new_pois += 1

            eff_ratio = round(new_nodes / max(c["length_km"], 0.1), 1)
            s_cov = min(35.0, (new_nodes / 250.0) * 35.0)
            s_poi = min(25.0, (new_pois / 8.0) * 25.0)
            s_cont = 20.0
            s_axis = c["structural_axis_score"]
            s_eff = min(10.0, (eff_ratio / 180.0) * 10.0)
            total_score = round(s_cov + s_poi + s_cont + s_axis + s_eff, 1)

            if total_score > best_score:
                best_score = total_score
                best_cand = c
                best_eval = {
                    "score": total_score,
                    "new_nodes": new_nodes,
                    "new_pois": new_pois,
                    "eff_ratio": eff_ratio,
                }

        if not best_cand or best_eval["new_nodes"] < 20:
            print(f"  Deteniendo selección en fase {phase_idx}: sin más candidatos con impacto significativo.")
            break

        best_cand["phase"] = phase_idx
        best_cand["id"] = f"expansion-{city_id}-{phase_idx:02d}"
        best_cand["expansion_score"] = best_eval["score"]
        best_cand["new_nodes"] = best_eval["new_nodes"]
        best_cand["new_pois"] = best_eval["new_pois"]
        best_cand["eff_ratio"] = best_eval["eff_ratio"]
        selected_phases.append(best_cand)
        remaining_candidates.remove(best_cand)

        # Update covered sets
        for nid in urban_access_nodes:
            if nid not in active_covered_nodes:
                un = nodes[nid]
                if any(fast_dist_m(un["lon"], un["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in best_cand["nodes"]):
                    active_covered_nodes.add(nid)
        for p in dedup_pois:
            if p["id"] not in active_covered_pois:
                if any(fast_dist_m(p["lon"], p["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in best_cand["nodes"]):
                    active_covered_pois.add(p["id"])

        print(f"  [Fase {phase_idx}] {best_cand['sector']} | {best_cand['length_km']} km | +{best_eval['new_nodes']} nodos | +{best_eval['new_pois']} POIs | Score: {best_eval['score']} pts")

    # 10. Assemble RFC 7946 GeoJSON
    features = []
    total_expansion_km = 0.0
    total_new_nodes = len(active_covered_nodes) - len(base_covered_nodes)
    total_new_pois = len(active_covered_pois) - len(base_covered_pois)

    disclaimer_text = (
        "Propuesta algorítmica de planificación territorial generada inductivamente por CicloConecta "
        "utilizando proxies de tejido urbano accesible sobre OpenStreetMap. No representa infraestructura física existente "
        "ni garantiza factibilidad constructiva o financiamiento."
    )

    for p in selected_phases:
        coords = [[round(nodes[nid]["lon"], 6), round(nodes[nid]["lat"], 6)] for nid in p["nodes"]]
        total_expansion_km += p["length_km"]

        # Collect POI summary
        poi_summary = defaultdict(list)
        for poi in dedup_pois:
            if any(fast_dist_m(poi["lon"], poi["lat"], nodes[cnid]["lon"], nodes[cnid]["lat"], cos_lat) <= 400.0 for cnid in p["nodes"]):
                if poi["name"] != "Sin nombre":
                    poi_summary[poi["category"]].append(poi["name"])

        feat = {
            "type": "Feature",
            "id": p["id"],
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "id": p["id"],
                "phase": p["phase"],
                "name": f"Fase {p['phase']}: {p['sector']}",
                "sector": p["sector"],
                "axis": p["main_street"],
                "cluster_id": p["cluster_id"],
                "alternative_type": p["alt_type"],
                "status": "ALGORITHMIC_EXPANSION",
                "badge": "ANÁLISIS",
                "expansion_score": p["expansion_score"],
                "length_m": p["length_m"],
                "length_km": p["length_km"],
                "crow_m": p["crow_m"],
                "zigzag_ratio": p["zigzag_ratio"],
                "structural_axis_score": p["structural_axis_score"],
                "structural_ratio": p["structural_ratio"],
                "physical_width_status": "Desconocido en OSM (ancho y factibilidad constructiva no verificados en terreno)",
                "coverage_gain_urban_access_nodes": p["new_nodes"],
                "coverage_gain_nodes": p["new_nodes"],  # Compatibility with UI chips
                "coverage_gain_pct": round((p["new_nodes"] / max(len(urban_access_nodes), 1)) * 100.0, 2),
                "new_pois_count": p["new_pois"],
                "efficiency_ratio": p["eff_ratio"],
                "streets": p["streets"],
                "origin_anchor": f"Red Ciclista Existente ({nodes[p['origin_id']]['lon']:.4f}, {nodes[p['origin_id']]['lat']:.4f})",
                "target_sector": p["sector"],
                "description": (
                    f"Corredor propuesto hacia el {p['sector']} ({p['alt_type']}). "
                    f"Incorpora +{p['new_nodes']} nodos de acceso urbano y +{p['new_pois']} equipamientos desatendidos."
                ),
                "poi_summary": {k: list(dict.fromkeys(v))[:3] for k, v in poi_summary.items()},
                "disclaimer": disclaimer_text,
            },
        }
        features.append(feat)

    now_iso = datetime.now(timezone.utc).isoformat()
    total_cov_gain_pct = round((total_new_nodes / max(len(urban_access_nodes), 1)) * 100.0, 2)

    expansion_geojson = {
        "type": "FeatureCollection",
        "metadata": {
            "city_id": city_id,
            "city_name": city_name,
            "layer_id": "network-expansion",
            "layer_name": "Expansión de red",
            "badge": "ANÁLISIS",
            "status": "ALGORITHMIC_EXPANSION",
            "total_phases": len(features),
            "total_expansion_km": round(total_expansion_km, 2),
            "total_new_urban_access_nodes": total_new_nodes,
            "total_new_nodes": total_new_nodes,
            "total_coverage_gain_pct": total_cov_gain_pct,
            "total_new_pois": total_new_pois,
            "poi_deduplication": {
                "raw_pois_count": len(cat_pois),
                "deduplicated_pois_count": len(dedup_pois),
            },
            "discovered_clusters": discovered_clusters_meta,
            "baseline_coverage": {
                "total_urban_access_nodes": len(urban_access_nodes),
                "covered_nodes_pct": base_cov_pct,
                "covered_pois_pct": base_poi_pct,
                "distance_bands": dist_bands,
            },
            "generated_at": now_iso,
            "disclaimer": disclaimer_text,
        },
        "features": features,
    }

    # 11. Save and sync
    output_path = data_dir / "network-expansion.geojson"
    tmp_path = output_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(expansion_geojson, f, ensure_ascii=False, indent=2)
    tmp_path.replace(output_path)
    print(f"  -> {len(features)} fases de expansión guardadas en {output_path.name}.")

    frontend_dir.mkdir(parents=True, exist_ok=True)
    dst_public = frontend_dir / "network-expansion.geojson"
    shutil.copy2(output_path, dst_public)
    print(f"  -> Sincronizado a {dst_public}.")

    elapsed = round(time.time() - t0, 1)
    print(f"  Completado en {elapsed}s: {len(features)} fases, +{round(total_expansion_km, 2)} km de red proyectada.")

    return expansion_geojson


def main():
    parser = argparse.ArgumentParser(description="Planificador Algorítmico de Expansión de Red Ciclista.")
    parser.add_argument("--city", type=str, default="curico", help="ID de la ciudad (por defecto: curico).")
    parser.add_argument("--refresh", action="store_true", help="Forzar re-descarga de POIs desde Overpass.")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "cities" / args.city
    frontend_dir = base_dir / "frontend" / "public" / "data" / "cities" / args.city

    registry_path = base_dir / "data" / "cities" / "registry.json"
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    city_def = next((c for c in registry.get("cities", []) if c["id"] == args.city), None)
    if not city_def:
        print(f"Error: Ciudad '{args.city}' no encontrada en registry.json")
        sys.exit(1)

    plan_city_expansion(city_def, data_dir, frontend_dir, force_refresh=args.refresh)


if __name__ == "__main__":
    main()
