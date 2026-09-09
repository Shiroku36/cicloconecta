"""
CicloConecta — Generic Pipeline for Processing Cities.

Ingests OSM data, builds navigable graphs, computes algorithmic suggested routes,
detects cycling components, identifies and ranks structural gaps, and publishes
standardized GeoJSON layers and city statistics.

Usage:
  python -m pipeline.build_city --city curico
  python -m pipeline.build_city --city talca
  python -m pipeline.build_city --city talca --refresh
  python -m pipeline.build_city --all-enabled
"""

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gap_detector import (
    build_cycling_subgraph,
    deduplicate_and_rank_candidates,
    extract_cycling_components,
    find_candidate_gaps,
    generate_missing_connections_geojson,
)
from .graph_builder import (
    build_navigable_graph,
    deserialize_graph_from_json,
    filter_largest_component,
    haversine_distance,
    serialize_graph_to_json,
)
from .network_extractor import extract_network_elements, fetch_osm_road_network
from .osm_extractor import fetch_osm_cycleways, process_osm_to_geojson
from .router import SpatialNodeIndex, calculate_complete_route

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "cities"
FRONTEND_DATA_DIR = BASE_DIR / "frontend" / "public" / "data" / "cities"
REGISTRY_PATH = DATA_DIR / "registry.json"


def load_registry() -> dict[str, Any]:
    """Loads the city registry from data/cities/registry.json."""
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Registro de ciudades no encontrado en: {REGISTRY_PATH}")
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def atomic_json_dump(data: Any, target_path: Path, indent: int = 2) -> None:
    """Safely writes JSON data to a temporary file and atomically replaces target."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    tmp_path.replace(target_path)


def compute_suggested_routes_for_city(
    G_nav: Any,
    spatial_index: SpatialNodeIndex,
    city_def: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Computes representative routes between real urban presets for the city.
    Uses defined representative_routes or pairs presets with the civic center.
    """
    rep_routes = city_def.get("representative_routes")
    if not rep_routes:
        presets = city_def.get("presets", [])
        if len(presets) < 2:
            print(f"  [Aviso] Menos de 2 presets definidos para {city_def['id']}, omitiendo rutas calculadas.")
            return []
        center_preset = presets[0]
        rep_routes = []
        for idx, other in enumerate(presets[1:6], start=1):
            rep_routes.append({
                "id": f"route-{city_def['id']}-{idx:02d}",
                "name": f"Ruta #{idx:02d}: {other['name']} → {center_preset['name']}",
                "description": f"Conexión desde {other['name']} hacia el centro cívico.",
                "origin_name": other["name"],
                "origin_coord": other["coord"],
                "dest_name": center_preset["name"],
                "dest_coord": center_preset["coord"],
            })

    routes = []
    for item in rep_routes:
        route_id = item["id"]
        route_name = item["name"]
        o_lon, o_lat = item["origin_coord"]
        d_lon, d_lat = item["dest_coord"]

        try:
            res = calculate_complete_route(
                G_nav,
                spatial_index,
                origin_lon=o_lon,
                origin_lat=o_lat,
                dest_lon=d_lon,
                dest_lat=d_lat,
                max_snap_dist_m=650.0,
            )
            c_route = res["cycling_route"]
            s_route = res["shortest_route"]
            comp = res["comparison"]

            routes.append({
                "type": "Feature",
                "id": route_id,
                "properties": {
                    "id": route_id,
                    "name": route_name,
                    "description": item.get("description", f"Conexión ciclista {route_name}"),
                    "origin_name": item.get("origin_name", "Origen"),
                    "dest_name": item.get("dest_name", "Destino"),
                    "is_demo": False,
                    "status": "ALGORITHMIC_RECOMMENDED",
                    "category": "Corredor ciclista recomendado",
                    "distance_km": c_route["distance_km"],
                    "distance_m": c_route["distance_m"],
                    "cycling_infra_km": c_route["cycling_infra_km"],
                    "cycling_infra_pct": c_route["cycling_infra_pct"],
                    "cost_score": c_route["cost_score"],
                    "shortest_distance_km": s_route["distance_km"],
                    "shortest_cycling_infra_pct": s_route["cycling_infra_pct"],
                    "distance_diff_km": comp["distance_diff_km"],
                    "length_diff_pct": comp["length_diff_pct"],
                    "cycling_gain_pct": comp["cycling_gain_pct"],
                    "is_same_path": comp["is_same_path"],
                    "streets": c_route["streets"][:8],
                    "source": "Motor de routing A* determinista CicloConecta sobre OpenStreetMap",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": c_route["coordinates"],
                },
            })
            print(f"  -> {route_name}: {c_route['distance_km']} km ({c_route['cycling_infra_pct']}% ciclovía, +{comp['cycling_gain_pct']}% ganancia)")
        except Exception as err:
            print(f"  [Aviso] No se pudo calcular ruta '{route_name}': {err}")

    return routes


def process_city(
    city_def: dict[str, Any],
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Executes the complete generic pipeline for a single city.
    """
    city_id = city_def["id"]
    city_name = city_def["name"]
    bbox = tuple(city_def["bbox"])  # (s, w, n, e)

    t0 = time.time()
    print(f"\n{'='*55}")
    print(f"Iniciando procesamiento para: {city_name} ({city_id})")
    print(f"Bounding box: {bbox}")
    print(f"{'='*55}")

    city_data_dir = DATA_DIR / city_id
    city_data_dir.mkdir(parents=True, exist_ok=True)
    city_frontend_dir = FRONTEND_DATA_DIR / city_id
    city_frontend_dir.mkdir(parents=True, exist_ok=True)

    # 1. Extracción de infraestructura ciclista existente
    print("\n[1/6] Extrayendo infraestructura ciclista OSM...")
    raw_cycleways_cache = city_data_dir / "raw_cycleways.json"
    osm_cycleways_raw = fetch_osm_cycleways(
        bbox=bbox,
        cache_path=raw_cycleways_cache,
        force_refresh=force_refresh,
    )
    cycleways_geojson, total_cycleway_m, cycleways_count = process_osm_to_geojson(
        osm_cycleways_raw,
        city_id=city_id,
    )
    cycleways_path = city_data_dir / "cycling-infrastructure.geojson"
    atomic_json_dump(cycleways_geojson, cycleways_path)
    total_cycleway_km = round(total_cycleway_m / 1000.0, 2)
    print(f"  -> {cycleways_count} tramos de ciclovías ({total_cycleway_km} km) guardados.")

    # 2. Extracción de red vial y construcción del grafo navegable
    print("\n[2/6] Extrayendo red vial y construyendo grafo navegable G_nav...")
    raw_network_cache = city_data_dir / "raw_network.json"
    osm_network_raw = fetch_osm_road_network(
        bbox=bbox,
        cache_path=raw_network_cache,
        force_refresh=force_refresh,
    )
    nodes, ways = extract_network_elements(osm_network_raw)
    G_raw = build_navigable_graph(nodes, ways)
    G_nav = filter_largest_component(G_raw)
    print(f"  -> Grafo conectado: {len(G_nav)} nodos, {G_nav.number_of_edges()} aristas.")

    nav_graph_path = city_data_dir / "nav_graph.json"
    serialized_graph = serialize_graph_to_json(G_nav, city_id=city_id)
    atomic_json_dump(serialized_graph, nav_graph_path, indent=None)
    print(f"  -> nav_graph.json guardado ({nav_graph_path.stat().st_size / 1_000_000:.1f} MB).")

    # 3. Cálculo de rutas sugeridas representativas
    print("\n[3/6] Calculando rutas representativas deterministas (A*)...")
    spatial_index = SpatialNodeIndex(G_nav)
    route_features = compute_suggested_routes_for_city(G_nav, spatial_index, city_def)
    suggested_routes_geojson = {
        "type": "FeatureCollection",
        "name": f"Rutas_Sugeridas_{city_id.capitalize()}_Algoritmicas",
        "metadata": {
            "city": city_id,
            "is_demo": False,
            "status": "ALGORITHMIC_RECOMMENDED",
            "total_routes": len(route_features),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "features": route_features,
    }
    routes_path = city_data_dir / "suggested-routes.geojson"
    atomic_json_dump(suggested_routes_geojson, routes_path)
    print(f"  -> {len(route_features)} rutas representativas guardadas en {routes_path.name}.")

    # 4. Detección algorítmica de componentes y brechas (gaps)
    print("\n[4/6] Analizando conectividad ciclista y detectando brechas (gaps)...")
    G_cycling = build_cycling_subgraph(G_nav)
    components = extract_cycling_components(G_cycling)
    main_comp_km = components[0].length_km if components else 0.0
    isolated_count = sum(1 for c in components if c.length_km < 1.0)
    print(f"  -> {len(components)} componentes ciclistas. Componente dorsal: {main_comp_km} km.")

    candidates = find_candidate_gaps(G_nav, components, max_path_len_m=1200.0)
    ranked_candidates = deduplicate_and_rank_candidates(candidates, max_results=10)
    gaps_geojson = generate_missing_connections_geojson(ranked_candidates, city_id=city_id)
    gaps_path = city_data_dir / "missing-connections.geojson"
    atomic_json_dump(gaps_geojson, gaps_path)
    print(f"  -> {len(ranked_candidates)} oportunidades prioritarias guardadas en {gaps_path.name}.")

    # 5. Generación de estadísticas de red y actualización de city.json
    print("\n[5/6] Generando estadísticas objetivas de la red y metadatos...")
    median_gap_m = 0
    max_score = 0.0
    if ranked_candidates:
        gap_lengths = sorted(c["gap_length_m"] for c in ranked_candidates)
        median_gap_m = int(gap_lengths[len(gap_lengths) // 2])
        max_score = ranked_candidates[0]["priority_score"]

    main_pct = round((main_comp_km / max(total_cycleway_km, 0.01)) * 100.0, 1)
    if main_pct > 100.0:
        main_pct = 100.0

    now_iso = datetime.now(timezone.utc).isoformat()
    city_metadata = {
        "id": city_id,
        "name": city_name,
        "province": city_def.get("province", city_name),
        "region": city_def.get("region", ""),
        "country": city_def.get("country", "Chile"),
        "center": city_def["center"],
        "initial_zoom": city_def.get("initial_zoom", 13.5),
        "bounds": city_def["bounds"],
        "bbox": city_def["bbox"],
        "description": city_def.get(
            "description",
            f"Red ciclista y análisis de conectividad urbana para {city_name}, {city_def.get('region', '')}."
        ),
        "presets": city_def.get("presets", []),
        "stats": {
            "cycleways_count": cycleways_count,
            "total_km": total_cycleway_km,
            "layers_available": [
                "cycling-infrastructure",
                "missing-connections",
                "suggested-routes",
            ],
            "last_updated": now_iso,
        },
        "connectivity": {
            "total_cycling_km": total_cycleway_km,
            "total_components": len(components),
            "main_component_km": main_comp_km,
            "main_component_pct": main_pct,
            "isolated_components_count": isolated_count,
            "selected_opportunities_count": len(ranked_candidates),
            "median_gap_m": median_gap_m,
            "max_score": max_score,
            "last_analyzed": now_iso,
        },
    }
    city_json_path = city_data_dir / "city.json"
    atomic_json_dump(city_metadata, city_json_path)

    # 6. Sincronización a frontend/public/
    print("\n[6/6] Sincronizando capas públicas hacia frontend/public/data/cities/...")
    for filename in [
        "city.json",
        "cycling-infrastructure.geojson",
        "missing-connections.geojson",
        "suggested-routes.geojson",
    ]:
        src = city_data_dir / filename
        dst = city_frontend_dir / filename
        if src.exists():
            shutil.copy2(src, dst)

    elapsed = round(time.time() - t0, 1)

    # Resumen estructurado en consola
    print(f"\n{'='*55}")
    print(f"Resumen de {city_name} ({city_id})")
    print(f"{'-'*55}")
    print(f"  Infraestructura ciclista : {total_cycleway_km} km ({cycleways_count} tramos)")
    print(f"  Grafo navegable          : {len(G_nav)} nodos, {G_nav.number_of_edges()} aristas")
    print(f"  Componentes ciclistas    : {len(components)} (Principal: {main_comp_km} km, {main_pct}%)")
    print(f"  Rutas calculadas         : {len(route_features)}")
    print(f"  Oportunidades Top 10     : {len(ranked_candidates)} (Max score: {max_score}, Brecha mediana: {median_gap_m} m)")
    print(f"  Tiempo de procesamiento  : {elapsed} s")
    print(f"{'='*55}\n")

    return {
        "city_id": city_id,
        "cycleways_count": cycleways_count,
        "total_km": total_cycleway_km,
        "nodes": len(G_nav),
        "edges": G_nav.number_of_edges(),
        "components": len(components),
        "main_component_km": main_comp_km,
        "opportunities": len(ranked_candidates),
        "elapsed_seconds": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description="Pipeline genérico multi-ciudad de CicloConecta.")
    parser.add_argument("--city", type=str, help="ID de la ciudad a procesar (ej. curico, talca).")
    parser.add_argument("--refresh", action="store_true", help="Forzar re-descarga de datos OSM crudos.")
    parser.add_argument("--all-enabled", action="store_true", help="Procesar todas las ciudades habilitadas en registry.json.")

    args = parser.parse_args()

    registry = load_registry()
    cities = registry.get("cities", [])

    if args.all_enabled:
        enabled_cities = [c for c in cities if c.get("enabled", False)]
        print(f"Procesando {len(enabled_cities)} ciudades habilitadas: {[c['id'] for c in enabled_cities]}")
        for c in enabled_cities:
            process_city(c, force_refresh=args.refresh)
    elif args.city:
        target_city = next((c for c in cities if c["id"] == args.city), None)
        if not target_city:
            print(f"Error: Ciudad '{args.city}' no encontrada en registry.json.")
            sys.exit(1)
        process_city(target_city, force_refresh=args.refresh)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
