"""
CicloConecta — Algorithmic Cycling Network Expansion Planner.

Identifies territorial expansion corridors from existing cycling infrastructure
into underserved residential sectors and urban anchors without existing cycleways.
Evaluates before/after coverage gains (using road nodes as a proxy for urban coverage
and verified OSM POIs), scores candidates multi-critically (0-100), and grows the
network iteratively through sequential investment phases (Phase 1, 2, 3...).
"""

import argparse
import json
import math
import shutil
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

COS_LAT = 0.819  # Local cos(latitude) projection factor for Curicó (~ -35°)
DEG_TO_M = 111320.0
CELL_DEG = 0.004  # ~400m cell grid for spatial acceleration


def fast_dist_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculates planar approximation distance in meters for local urban scale."""
    dx = (lon2 - lon1) * COS_LAT
    dy = lat2 - lat1
    return math.hypot(dx, dy) * DEG_TO_M


class FastSpatialGrid:
    """Spatial 2D hash grid to accelerate radial distance checks in O(1)."""

    def __init__(self, cell_size: float = CELL_DEG):
        self.cell_size = cell_size
        self.grid: dict[tuple[int, int], list[tuple[Any, float, float]]] = defaultdict(list)

    def add(self, item_id: Any, lon: float, lat: float) -> None:
        gx = int(lon / self.cell_size)
        gy = int(lat / self.cell_size)
        self.grid[(gx, gy)].append((item_id, lon, lat))

    def is_within_dist(self, lon: float, lat: float, max_dist: float = 400.0) -> bool:
        gx = int(lon / self.cell_size)
        gy = int(lat / self.cell_size)
        rad = 2
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                for _, clon, clat in self.grid.get((gx + dx, gy + dy), []):
                    if fast_dist_m(lon, lat, clon, clat) <= max_dist:
                        return True
        return False

    def min_distance_m(self, lon: float, lat: float, max_search_m: float = 1200.0) -> float:
        gx = int(lon / self.cell_size)
        gy = int(lat / self.cell_size)
        rad = int(math.ceil(max_search_m / (self.cell_size * DEG_TO_M))) + 1
        min_d = float("inf")
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                for _, clon, clat in self.grid.get((gx + dx, gy + dy), []):
                    d = fast_dist_m(lon, lat, clon, clat)
                    if d < min_d:
                        min_d = d
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


def get_city_anchors(city_id: str) -> list[dict[str, Any]]:
    """
    Returns prioritized macro-sector urban anchors for expansion.
    Defined per city based on territorial master plans and underserved sectors.
    """
    if city_id == "curico":
        return [
            {
                "id": "rauquen-extension",
                "name": "Eje Norte: Av. Rauquén Norte → Don Sebastián / Los Héroes",
                "sector": "Rauquén Norte / Don Sebastián",
                "target_coords": (-71.2037, -34.9427),
                "axis": "Av. Rauquén Norte / Don Sebastián",
                "description": "Continuación de la red hacia los macro-conjuntos habitacionales de Rauquén Norte y el polo educativo Los Héroes.",
                "origin_anchor_hint": "Ciclovía Av. Rauquén (Componente Dorsal)",
            },
            {
                "id": "mataquito-licanten",
                "name": "Eje Surponiente: Mataquito → Villa Mejillones / Santos Martínez",
                "sector": "Mataquito / Licantén",
                "target_coords": (-71.2575, -34.9966),
                "axis": "Av. Licantén / Mataquito",
                "description": "Corredor surponiente conectando villas Mejillones y Santos Martínez con equipamientos educativos y comunitarios.",
                "origin_anchor_hint": "Ciclovía Av. Circunvalación / Los Niches",
            },
            {
                "id": "santa-fe",
                "name": "Eje Poniente: Av. Lautaro → Población Santa Fe",
                "sector": "Santa Fe Poniente",
                "target_coords": (-71.2580, -34.9880),
                "axis": "Av. Lautaro / Santa Fe",
                "description": "Extensión estratégica hacia el sector habitacional Santa Fe poniente a través del eje estructurante Lautaro.",
                "origin_anchor_hint": "Eje Lautaro / Red Central",
            },
            {
                "id": "sol-de-septiembre",
                "name": "Eje Norponiente: Av. Dr. Osorio → Sol de Septiembre / ANFA",
                "sector": "Sol de Septiembre",
                "target_coords": (-71.2542, -34.9715),
                "axis": "Av. Doctor Osorio / Apolonia",
                "description": "Extensión hacia el sector histórico Sol de Septiembre, Estadio ANFA y establecimientos escolares circundantes.",
                "origin_anchor_hint": "Ciclovía Balmaceda / Circunvalación",
            },
            {
                "id": "zapallar-oriente",
                "name": "Eje Oriente: Camino Zapallar → El Boldo Oriente / Los Cristales",
                "sector": "Zapallar / Los Cristales",
                "target_coords": (-71.1988, -34.9810),
                "axis": "Camino Zapallar",
                "description": "Proyección hacia la zona de expansión residencial oriente conectando Zapallar y colegios del sector.",
                "origin_anchor_hint": "Ciclovía El Boldo / O'Higgins",
            },
            {
                "id": "tutuquen-poniente",
                "name": "Eje Periurbano: Ruta J-60 → Sector Tutuquén",
                "sector": "Tutuquén Norponiente",
                "target_coords": (-71.2720, -34.9750),
                "axis": "Ruta J-60 / Tutuquén",
                "description": "Conexión periurbana de alta demanda ciclista hacia el sector Tutuquén y enlace costero de Curicó.",
                "origin_anchor_hint": "Ciclovía Av. Colón Poniente",
            },
            {
                "id": "los-niches-utalca",
                "name": "Eje Suroriente: Av. España Sur → Acceso Campus UTalca",
                "sector": "Los Niches Sur",
                "target_coords": (-71.2290, -35.0030),
                "axis": "Av. España Sur / Los Niches",
                "description": "Corredor hacia el campus universitario Los Niches y el polo periurbano sur de Curicó.",
                "origin_anchor_hint": "Ciclovía Av. Manso de Velasco Sur",
            },
        ]
    return []


def plan_city_expansion(
    city_def: dict[str, Any],
    data_dir: Path,
    frontend_dir: Path,
    force_refresh: bool = False,
    max_phases: int = 8,
) -> dict[str, Any]:
    """
    Computes territorial coverage, identifies urban anchors, generates continuous
    street corridors, calculates multi-criteria scores, and executes greedy iterative growth.
    Outputs network-expansion.geojson and updates city metadata.
    """
    city_id = city_def["id"]
    city_name = city_def["name"]
    bbox = tuple(city_def["bbox"])

    t0 = time.time()
    print(f"\n[Fase 3.5] Iniciando Planificador de Expansión de Red para {city_name} ({city_id})...")

    # 1. Load navigable graph
    nav_graph_path = data_dir / "nav_graph.json"
    if not nav_graph_path.exists():
        raise FileNotFoundError(f"nav_graph.json no encontrado para {city_id} en {nav_graph_path}")

    with open(nav_graph_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    nodes = {n["id"]: n for n in graph_data["nodes"]}
    edges = graph_data["edges"]

    # 2. Extract cycling network nodes & build spatial grid
    cycle_nodes = set()
    for e in edges:
        if e.get("is_cycling_infra"):
            cycle_nodes.add(e["u"])
            cycle_nodes.add(e["v"])

    if not cycle_nodes:
        print(f"  [Aviso] No se detectó infraestructura ciclista en {city_name} para proyectar expansiones.")
        return {"features": [], "metadata": {}}

    # Sample cycle origins spaced by at least 120m to ensure diverse candidate origins
    sampled_origins = []
    for cid in cycle_nodes:
        cn = nodes[cid]
        if not any(fast_dist_m(cn["lon"], cn["lat"], nodes[s]["lon"], nodes[s]["lat"]) < 120 for s in sampled_origins):
            sampled_origins.append(cid)

    # 3. Load & categorize POIs
    raw_pois_cache = data_dir / "raw_pois.json"
    raw_poi_elements = fetch_osm_pois(bbox, cache_path=raw_pois_cache, force_refresh=force_refresh)
    pois = parse_and_categorize_pois(raw_poi_elements)

    # 4. Measure initial baseline coverage (threshold: 400m)
    base_grid = FastSpatialGrid()
    for cid in cycle_nodes:
        cn = nodes[cid]
        base_grid.add(cid, cn["lon"], cn["lat"])

    base_covered_nodes = set()
    dist_bands = {"0-250m": 0, "250-500m": 0, "500-1000m": 0, ">1000m": 0}
    for nid, n in nodes.items():
        d = base_grid.min_distance_m(n["lon"], n["lat"], max_search_m=1500.0)
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
    for p in pois:
        if base_grid.is_within_dist(p["lon"], p["lat"], 400.0):
            base_covered_pois.add(p["id"])

    base_cov_pct = round((len(base_covered_nodes) / max(len(nodes), 1)) * 100.0, 1)
    base_poi_pct = round((len(base_covered_pois) / max(len(pois), 1)) * 100.0, 1)

    print(f"  Cobertura base ({base_cov_pct}% nodos, {base_poi_pct}% POIs):")
    print(f"    0–250 m: {dist_bands['0-250m']} nodos | 250–500 m: {dist_bands['250-500m']} | 500–1000 m: {dist_bands['500-1000m']} | >1000 m: {dist_bands['>1000m']}")

    # 5. Build graph adjacency with street-hierarchy cycling weights
    adj = defaultdict(list)
    for e in edges:
        u, v = e["u"], e["v"]
        length = e.get("length_m", 10.0)
        hw = e.get("highway", "residential")
        name = e.get("name") or "Calle sin nombre"
        is_infra = e.get("is_cycling_infra", False)

        if hw in ("motorway", "motorway_link"):
            continue

        if is_infra:
            cost_mult = 0.50
        elif hw in ("primary", "primary_link"):
            cost_mult = 1.25
        elif hw in ("secondary", "secondary_link"):
            cost_mult = 0.85
        elif hw in ("tertiary", "tertiary_link"):
            cost_mult = 0.80
        elif hw in ("residential", "living_street"):
            cost_mult = 1.00
        elif hw in ("service", "track"):
            cost_mult = 1.80
        else:
            cost_mult = 1.20

        edge_fwd = {"v": v, "length_m": length, "cost": length * cost_mult, "name": name, "highway": hw, "is_cycling_infra": is_infra}
        edge_rev = {"v": u, "length_m": length, "cost": length * cost_mult, "name": name, "highway": hw, "is_cycling_infra": is_infra}
        adj[u].append(edge_fwd)
        adj[v].append(edge_rev)

    # 6. Retrieve urban anchors and generate candidate corridors
    anchors = get_city_anchors(city_id)
    if not anchors:
        print(f"  [Aviso] Sin anclas predefinidas para {city_id}.")
        return {"features": [], "metadata": {}}

    import heapq

    def generate_corridor_from_anchor(anc: dict[str, Any]) -> Optional[dict[str, Any]]:
        t_lon, t_lat = anc["target_coords"]
        target_id = min(nodes.keys(), key=lambda k: fast_dist_m(nodes[k]["lon"], nodes[k]["lat"], t_lon, t_lat))

        # Reverse Dijkstra from target to find best origin in 1 pass
        dist = {target_id: 0.0}
        prev = {}
        heap = [(0.0, target_id)]

        while heap:
            cur, u = heapq.heappop(heap)
            if cur > 3600.0:
                continue
            if cur > dist.get(u, float("inf")):
                continue
            for edge in adj[u]:
                v = edge["v"]
                nc = cur + edge["cost"]
                if nc < dist.get(v, float("inf")) and nc <= 3600.0:
                    dist[v] = nc
                    prev[v] = (u, edge)
                    heapq.heappush(heap, (nc, v))

        best_cand = None
        best_cost = float("inf")

        for orig_id in sampled_origins:
            if orig_id in dist:
                path_nodes = []
                path_edges = []
                curr = orig_id
                tot_len = 0.0
                while curr != target_id:
                    nxt, edge = prev[curr]
                    path_nodes.append(curr)
                    path_edges.append(edge)
                    tot_len += edge["length_m"]
                    curr = nxt
                path_nodes.append(target_id)

                if tot_len < 450.0 or tot_len > 3500.0:
                    continue

                crow = fast_dist_m(
                    nodes[orig_id]["lon"], nodes[orig_id]["lat"],
                    nodes[target_id]["lon"], nodes[target_id]["lat"]
                )
                ratio = tot_len / max(crow, 1.0)
                if ratio > 1.70:
                    continue

                cand_score = tot_len * (ratio ** 1.2)
                if cand_score < best_cost:
                    best_cost = cand_score
                    streets = []
                    for e in path_edges:
                        nm = e["name"]
                        if nm and nm != "Calle sin nombre" and nm not in streets:
                            streets.append(nm)

                    best_cand = {
                        "anchor_id": anc["id"],
                        "name": anc["name"],
                        "sector": anc["sector"],
                        "axis": anc["axis"],
                        "description": anc["description"],
                        "origin_hint": anc.get("origin_anchor_hint", "Ciclovía existente"),
                        "origin_id": orig_id,
                        "target_id": target_id,
                        "nodes": path_nodes,
                        "edges": path_edges,
                        "length_m": round(tot_len, 1),
                        "length_km": round(tot_len / 1000.0, 2),
                        "crow_m": round(crow, 1),
                        "zigzag_ratio": round(ratio, 2),
                        "streets": streets,
                    }

        return best_cand

    candidate_corridors = []
    for anc in anchors:
        c = generate_corridor_from_anchor(anc)
        if c:
            candidate_corridors.append(c)

    print(f"  -> {len(candidate_corridors)} corredores candidatos generados.")

    # 7. Iterative Greedy Multi-Phase Execution
    active_grid = FastSpatialGrid()
    for cid in cycle_nodes:
        cn = nodes[cid]
        active_grid.add(cid, cn["lon"], cn["lat"])

    active_covered_nodes = set(base_covered_nodes)
    active_covered_pois = set(base_covered_pois)

    remaining_candidates = list(candidate_corridors)
    selected_phases: list[dict[str, Any]] = []

    for phase_idx in range(1, min(max_phases, len(candidate_corridors)) + 1):
        best_candidate = None
        best_score = -1.0
        best_eval = None

        for c in remaining_candidates:
            c_grid = FastSpatialGrid()
            for nid in c["nodes"]:
                cn = nodes[nid]
                c_grid.add(nid, cn["lon"], cn["lat"])

            new_nodes = 0
            for nid, n in nodes.items():
                if nid not in active_covered_nodes and c_grid.is_within_dist(n["lon"], n["lat"], 400.0):
                    new_nodes += 1

            new_pois = 0
            poi_summary = defaultdict(list)
            for p in pois:
                if p["id"] not in active_covered_pois and c_grid.is_within_dist(p["lon"], p["lat"], 400.0):
                    new_pois += 1
                    if p["name"] != "Sin nombre":
                        poi_summary[p["category"]].append(p["name"])

            if new_nodes < 15:
                continue

            cov_gain_pct = round((new_nodes / len(nodes)) * 100.0, 2)
            eff_ratio = round(new_nodes / max(c["length_km"], 0.1), 1)

            # Scoring formula
            s_cov = min(35.0, (new_nodes / 300.0) * 35.0)
            s_poi = min(25.0, (new_pois / 8.0) * 25.0)
            s_cont = 20.0
            s_qual = 10.0 if any(e["highway"] in ("secondary", "tertiary") for e in c["edges"]) else 7.5
            s_eff = min(10.0, (eff_ratio / 180.0) * 10.0)
            score = round(s_cov + s_poi + s_cont + s_qual + s_eff, 1)

            if score > best_score:
                best_score = score
                best_candidate = c
                best_eval = {
                    "score": score,
                    "new_nodes": new_nodes,
                    "new_pois": new_pois,
                    "cov_gain_pct": cov_gain_pct,
                    "eff_ratio": eff_ratio,
                    "poi_summary": {k: v[:3] for k, v in poi_summary.items()},
                }

        if not best_candidate or best_eval is None:
            break

        best_candidate["phase"] = phase_idx
        best_candidate["id"] = f"expansion-{city_id}-{phase_idx:02d}"
        best_candidate["expansion_score"] = best_eval["score"]
        best_candidate["coverage_gain_nodes"] = best_eval["new_nodes"]
        best_candidate["coverage_gain_pct"] = best_eval["cov_gain_pct"]
        best_candidate["new_pois_count"] = best_eval["new_pois"]
        best_candidate["efficiency_ratio"] = best_eval["eff_ratio"]
        best_candidate["poi_summary"] = best_eval["poi_summary"]

        selected_phases.append(best_candidate)
        remaining_candidates.remove(best_candidate)

        for nid in best_candidate["nodes"]:
            cn = nodes[nid]
            active_grid.add(nid, cn["lon"], cn["lat"])

        c_grid = FastSpatialGrid()
        for nid in best_candidate["nodes"]:
            cn = nodes[nid]
            c_grid.add(nid, cn["lon"], cn["lat"])

        for nid, n in nodes.items():
            if nid not in active_covered_nodes and c_grid.is_within_dist(n["lon"], n["lat"], 400.0):
                active_covered_nodes.add(nid)

        for p in pois:
            if p["id"] not in active_covered_pois and c_grid.is_within_dist(p["lon"], p["lat"], 400.0):
                active_covered_pois.add(p["id"])

    # 8. Assemble GeoJSON FeatureCollection
    features = []
    total_expansion_km = 0.0
    total_new_nodes = 0
    total_new_pois = 0

    disclaimer_text = (
        "Propuesta algorítmica de planificación territorial generada por CicloConecta "
        "utilizando proxies de cobertura urbana sobre OpenStreetMap. No representa ciclovías existentes "
        "ni proyectos con financiamiento asegurado."
    )

    for p in selected_phases:
        coords = [[round(nodes[nid]["lon"], 6), round(nodes[nid]["lat"], 6)] for nid in p["nodes"]]
        total_expansion_km += p["length_km"]
        total_new_nodes += p["coverage_gain_nodes"]
        total_new_pois += p["new_pois_count"]

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
                "name": p["name"],
                "sector": p["sector"],
                "axis": p["axis"],
                "status": "ALGORITHMIC_EXPANSION",
                "badge": "ANÁLISIS",
                "expansion_score": p["expansion_score"],
                "length_m": p["length_m"],
                "length_km": p["length_km"],
                "crow_m": p["crow_m"],
                "zigzag_ratio": p["zigzag_ratio"],
                "coverage_gain_nodes": p["coverage_gain_nodes"],
                "coverage_gain_pct": p["coverage_gain_pct"],
                "new_pois_count": p["new_pois_count"],
                "efficiency_ratio": p["efficiency_ratio"],
                "streets": p["streets"],
                "origin_anchor": p["origin_hint"],
                "target_sector": p["sector"],
                "description": p["description"],
                "poi_summary": p["poi_summary"],
                "disclaimer": disclaimer_text,
            },
        }
        features.append(feat)

    now_iso = datetime.now(timezone.utc).isoformat()
    total_cov_gain_pct = round((total_new_nodes / max(len(nodes), 1)) * 100.0, 2)

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
            "total_new_nodes": total_new_nodes,
            "total_coverage_gain_pct": total_cov_gain_pct,
            "total_new_pois": total_new_pois,
            "baseline_coverage": {
                "covered_nodes_pct": base_cov_pct,
                "covered_pois_pct": base_poi_pct,
                "distance_bands": dist_bands,
            },
            "generated_at": now_iso,
            "disclaimer": disclaimer_text,
        },
        "features": features,
    }

    # 9. Save to data/cities/{city_id}/network-expansion.geojson and sync
    output_path = data_dir / "network-expansion.geojson"
    tmp_path = output_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(expansion_geojson, f, ensure_ascii=False, indent=2)
    tmp_path.replace(output_path)
    print(f"  -> {len(features)} fases de expansión guardadas en {output_path.name}.")

    # Sync to frontend/public/data/cities/{city_id}/
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