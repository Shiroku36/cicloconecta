"""
CicloConecta — Curicó Missing Connections Pipeline Script.

Executes algorithmic gap detection for Curicó, identifies disconnected cycling components,
computes priority scores, exports missing-connections.geojson (replacing DEMO),
updates city connectivity statistics, and synchronizes to frontend/public.
"""

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from pipeline.gap_detector import (
    build_cycling_subgraph,
    deduplicate_and_rank_candidates,
    extract_cycling_components,
    find_candidate_gaps,
    generate_missing_connections_geojson,
)
from pipeline.graph_builder import deserialize_graph_from_json

CURICO_DATA_DIR = BASE_DIR / "data" / "cities" / "curico"
FRONTEND_DATA_DIR = BASE_DIR / "frontend" / "public" / "data" / "cities" / "curico"


def main() -> None:
    print("=== CicloConecta: Pipeline Detector de Conexiones Faltantes para Curicó ===")

    nav_graph_path = CURICO_DATA_DIR / "nav_graph.json"
    if not nav_graph_path.exists():
        print(f"Error: No se encontró el grafo navegable en {nav_graph_path}")
        print("Ejecuta primero: python pipeline/build_curico_routing.py")
        sys.exit(1)

    print(f"Cargando grafo navegable desde: {nav_graph_path}")
    with open(nav_graph_path, "r", encoding="utf-8") as f:
        graph_dict = json.load(f)

    G_nav = deserialize_graph_from_json(graph_dict)
    print(f"Grafo navegable cargado: {G_nav.number_of_nodes()} nodos, {G_nav.number_of_edges()} aristas.")

    # 1. Construir subgrafo ciclista exclusivo
    print("\nConstruyendo subgrafo ciclista exclusivo (G_cycling)...")
    G_cycling = build_cycling_subgraph(G_nav)
    print(f"Subgrafo ciclista: {G_cycling.number_of_nodes()} nodos, {G_cycling.number_of_edges()} tramos ciclistas.")

    # 2. Extraer componentes conexas
    print("\nAnalizando componentes conexas de la red ciclista...")
    components = extract_cycling_components(G_cycling)
    total_cycling_km = round(sum(c.length_km for c in components), 2)
    main_component_km = components[0].length_km if components else 0.0
    substantial_components = [c for c in components if c.length_km >= 0.20]
    isolated_components = [c for c in components if c.length_km < 0.20]
    total_endpoints = sum(len(c.endpoints) for c in substantial_components)

    print(f"Total infraestructura ciclista: {total_cycling_km} km")
    print(f"Total componentes detectadas: {len(components)}")
    print(f"Componente principal (#1): {main_component_km} km")
    print(f"Componentes sustanciales (>= 200m): {len(substantial_components)}")
    print(f"Fragmentos aislados menores (< 200m): {len(isolated_components)}")
    print(f"Total endpoints relevantes: {total_endpoints}")

    # 3. Buscar conexiones candidatas sobre la red vial
    print("\nBuscando conexiones candidatas sobre la red vial real...")
    raw_candidates = find_candidate_gaps(
        G_nav,
        components,
        min_crow_dist_m=35.0,
        max_crow_dist_m=850.0,
        max_path_len_m=1200.0,
        min_component_len_km=0.20,
    )
    print(f"Candidatos brutos encontrados: {len(raw_candidates)}")

    # 4. Deduplicar y rankear candidatos
    print("\nDeduplicando corredores y rankeando por Priority Score...")
    ranked_candidates = deduplicate_and_rank_candidates(raw_candidates, max_results=10)
    print(f"Oportunidades seleccionadas (Top 10):")

    for i, c in enumerate(ranked_candidates, start=1):
        streets_str = ", ".join(c["streets"][:3]) if c["streets"] else "Vía local"
        print(
            f"  {i:2d}. Score {c['priority_score']:4.1f} | "
            f"Comp #{c['comp_a_id']} ({c['comp_a_km']}km) <-> Comp #{c['comp_b_id']} ({c['comp_b_km']}km) | "
            f"{int(c['gap_length_m'])}m vía {streets_str} | "
            f"Red unida: {c['connected_network_km']}km (Gain Ratio: {c['gain_ratio']}x)"
        )

    # 5. Generar GeoJSON
    geojson_data = generate_missing_connections_geojson(ranked_candidates, city_id="curico")

    # Guardar en data/cities/curico/missing-connections.geojson
    output_path = CURICO_DATA_DIR / "missing-connections.geojson"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    print(f"\nArchivo GeoJSON guardado en: {output_path}")

    # Sincronizar a frontend
    frontend_output_path = FRONTEND_DATA_DIR / "missing-connections.geojson"
    shutil.copy2(output_path, frontend_output_path)
    print(f"Archivo sincronizado a: {frontend_output_path}")

    # 6. Actualizar city.json con estadísticas de conectividad
    city_meta_path = CURICO_DATA_DIR / "city.json"
    if city_meta_path.exists():
        with open(city_meta_path, "r", encoding="utf-8") as f:
            city_data = json.load(f)

        city_data["connectivity"] = {
            "total_cycling_km": total_cycling_km,
            "total_components": len(components),
            "main_component_km": main_component_km,
            "isolated_components_count": len(isolated_components),
            "relevant_endpoints_count": total_endpoints,
            "candidates_analyzed": len(raw_candidates),
            "selected_opportunities_count": len(ranked_candidates),
            "last_analyzed": datetime.now(timezone.utc).isoformat(),
        }

        with open(city_meta_path, "w", encoding="utf-8") as f:
            json.dump(city_data, f, ensure_ascii=False, indent=2)
        print(f"Metadatos de conectividad actualizados en: {city_meta_path}")

        frontend_city_meta = FRONTEND_DATA_DIR / "city.json"
        shutil.copy2(city_meta_path, frontend_city_meta)
        print(f"Metadatos sincronizados a: {frontend_city_meta}")

    print("\n¡Pipeline de conexiones faltantes completado con éxito!")


if __name__ == "__main__":
    main()
