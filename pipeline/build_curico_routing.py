"""
CicloConecta — Curicó Routing & Graph Builder Pipeline Script.

1. Fetches / loads road network for Curicó.
2. Builds NetworkX DiGraph with cycling cost weights.
3. Saves data/cities/curico/nav_graph.json.
4. Computes 5 real representative cycling routes vs shortest paths.
5. Generates suggested-routes.geojson (replacing DEMO routes).
6. Syncs artifacts to frontend/public.
"""

import json
import shutil
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from pipeline.cost_function import evaluate_edge_cycling_cost
from pipeline.graph_builder import (
    build_navigable_graph,
    filter_largest_component,
    serialize_graph_to_json,
)
from pipeline.network_extractor import extract_network_elements, fetch_osm_road_network
from pipeline.router import SpatialNodeIndex, calculate_complete_route

# Curicó Bounding Box (south, west, north, east)
CURICO_BBOX = (-35.05, -71.30, -34.93, -71.18)
CURICO_DATA_DIR = BASE_DIR / "data" / "cities" / "curico"
FRONTEND_DATA_DIR = BASE_DIR / "frontend" / "public" / "data" / "cities" / "curico"

REPRESENTATIVE_OD_PAIRS = [
    {
        "id": "route-curico-01",
        "name": "Ruta Norte: Rauquén - Plaza de Armas",
        "description": "Conexión desde el sector habitacional Rauquén / Bombero Garrido hacia el centro cívico.",
        "origin_name": "Sector Rauquén (Av. Rauquén)",
        "origin_coord": [-71.2185, -34.9620],
        "dest_name": "Plaza de Armas Curicó",
        "dest_coord": [-71.2394, -34.9854],
    },
    {
        "id": "route-curico-02",
        "name": "Ruta Oriente: Zapallar / El Boldo - Plaza de Armas",
        "description": "Corredor oriente conectando barrios residenciales de Zapallar y El Boldo hacia el centro.",
        "origin_name": "El Boldo / Zapallar",
        "origin_coord": [-71.2120, -34.9815],
        "dest_name": "Plaza de Armas Curicó",
        "dest_coord": [-71.2394, -34.9854],
    },
    {
        "id": "route-curico-03",
        "name": "Ruta Poniente: Santa Fe / Alessandri - Plaza de Armas",
        "description": "Eje poniente conectando Población Santa Fe y Av. Alessandri con el centro de la ciudad.",
        "origin_name": "Santa Fe / Av. Alessandri",
        "origin_coord": [-71.2580, -34.9880],
        "dest_name": "Plaza de Armas Curicó",
        "dest_coord": [-71.2394, -34.9854],
    },
    {
        "id": "route-curico-04",
        "name": "Circuito Universitario: Los Niches - Plaza de Armas",
        "description": "Conexión sur-oriente desde el sector Los Niches y Campus UTalca hacia el núcleo central.",
        "origin_name": "Sector Los Niches / Av. España",
        "origin_coord": [-71.2290, -35.0030],
        "dest_name": "Plaza de Armas Curicó",
        "dest_coord": [-71.2394, -34.9854],
    },
    {
        "id": "route-curico-05",
        "name": "Eje Intermodal: Guaiquillo - Estación de Ferrocarriles",
        "description": "Conexión intermodal sur-centro desde Población Guaiquillo hacia la Estación de Trenes.",
        "origin_name": "Sector Guaiquillo Sur",
        "origin_coord": [-71.2460, -34.9980],
        "dest_name": "Estación de Trenes Curicó (EFE)",
        "dest_coord": [-71.2340, -34.9785],
    },
]


def main() -> None:
    print("=== CicloConecta: Pipeline de Routing para Curicó ===")
    CURICO_DATA_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)

    cache_raw_path = CURICO_DATA_DIR / "raw_network.json"
    osm_raw = fetch_osm_road_network(CURICO_BBOX, cache_path=cache_raw_path)

    print(f"Extrayendo elementos de la red vial...")
    nodes, ways = extract_network_elements(osm_raw)
    print(f"Nodos OSM encontrados: {len(nodes)}, Vías OSM encontradas: {len(ways)}")

    print(f"Construyendo grafo dirigible de navegación ciclista...")
    G = build_navigable_graph(nodes, ways)
    print(f"Grafo inicial: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas.")

    print(f"Filtrando componente conexa principal...")
    G = filter_largest_component(G)
    print(f"Grafo conectado final: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas.")

    # Guardar nav_graph.json para el backend
    nav_graph_path = CURICO_DATA_DIR / "nav_graph.json"
    serialized_graph = serialize_graph_to_json(G, "curico")
    with open(nav_graph_path, "w", encoding="utf-8") as f:
        json.dump(serialized_graph, f, ensure_ascii=False)
    print(f"Grafo navegable guardado en: {nav_graph_path}")

    # Indexar nodos espacialmente
    print("Construyendo índice espacial de nodos...")
    spatial_index = SpatialNodeIndex(G)

    # Calcular las 5 rutas representativas
    print("\nCalculando 5 rutas representativas para Curicó...")
    features = []

    for item in REPRESENTATIVE_OD_PAIRS:
        r_id = item["id"]
        r_name = item["name"]
        o_lon, o_lat = item["origin_coord"]
        d_lon, d_lat = item["dest_coord"]

        route_res = calculate_complete_route(
            G, spatial_index, o_lon, o_lat, d_lon, d_lat, max_snap_dist_m=600.0
        )

        c_route = route_res["cycling_route"]
        s_route = route_res["shortest_route"]
        comp = route_res["comparison"]

        print(f"\n-> {r_name}")
        print(f"   Ruta Ciclista: {c_route['distance_km']} km | {c_route['cycling_infra_pct']}% ciclovías | Costo: {c_route['cost_score']}")
        print(f"   Ruta Más Corta: {s_route['distance_km']} km | {s_route['cycling_infra_pct']}% ciclovías | Costo: {s_route['cost_score']}")
        print(f"   Diferencia: +{comp['distance_diff_km']} km ({comp['length_diff_pct']}%) | Ganancia en ciclovías: +{comp['cycling_gain_pct']}%")

        feature = {
            "type": "Feature",
            "id": r_id,
            "properties": {
                "id": r_id,
                "name": r_name,
                "description": item["description"],
                "origin_name": item["origin_name"],
                "dest_name": item["dest_name"],
                "is_demo": False,
                "status": "Ruta algorítmica calculada con red vial real",
                "distance_km": c_route["distance_km"],
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
            },
            "geometry": {
                "type": "LineString",
                "coordinates": c_route["coordinates"],
            },
        }
        features.append(feature)

    suggested_routes_geojson = {
        "type": "FeatureCollection",
        "name": "Rutas_Recomendadas_Curico_Algoritmicas",
        "metadata": {
            "city": "curico",
            "is_demo": False,
            "routing_engine": "NetworkX A* with cycling-weighted cost function",
            "description": "Rutas calculadas algorítmicamente sobre la red vial real de OpenStreetMap, priorizando infraestructura ciclista.",
            "route_count": len(features),
        },
        "features": features,
    }

    routes_path = CURICO_DATA_DIR / "suggested-routes.geojson"
    with open(routes_path, "w", encoding="utf-8") as f:
        json.dump(suggested_routes_geojson, f, ensure_ascii=False, indent=2)
    print(f"\nRutas guardadas en: {routes_path}")

    # Sincronizar a frontend
    frontend_routes_path = FRONTEND_DATA_DIR / "suggested-routes.geojson"
    shutil.copy2(routes_path, frontend_routes_path)
    print(f"Rutas sincronizadas a frontend: {frontend_routes_path}")

    print("\n¡Pipeline de routing para Curicó completado con éxito!")


if __name__ == "__main__":
    main()
