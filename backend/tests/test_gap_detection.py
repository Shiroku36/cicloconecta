import json
from pathlib import Path
import pytest
import networkx as nx

from pipeline.gap_detector import (
    build_cycling_subgraph,
    extract_cycling_components,
    find_candidate_gaps,
    calculate_priority_score,
    deduplicate_and_rank_candidates,
    generate_missing_connections_geojson,
    CyclingComponent,
)
from pipeline.graph_builder import build_navigable_graph, deserialize_graph_from_json


DATA_DIR = Path(__file__).parent.parent.parent / "data" / "cities" / "curico"


def test_priority_score_formula_behavior():
    """Verify mathematical properties of the multi-criteria priority score."""
    # Case A: Short gap (100m) uniting huge network (20km + 5km = 25km) on low stress
    score_a = calculate_priority_score(
        len_a_km=20.0,
        len_b_km=5.0,
        gap_length_m=100.0,
        avg_penalty=1.0,
    )
    assert 70.0 <= score_a <= 100.0

    # Case B: Long gap (1500m) uniting tiny network (0.2km + 0.2km = 0.4km) on high stress
    score_b = calculate_priority_score(
        len_a_km=0.2,
        len_b_km=0.2,
        gap_length_m=1500.0,
        avg_penalty=3.0,
    )
    assert 0.0 <= score_b < score_a
    assert score_b < 40.0

    # Test determinism: same input always produces identical score
    assert calculate_priority_score(5.0, 3.0, 300.0, 1.5) == calculate_priority_score(5.0, 3.0, 300.0, 1.5)


def test_synthetic_graph_component_extraction():
    """Verify component extraction on a controlled synthetic graph."""
    G = nx.Graph()
    # Component 1: 3 nodes, 2 edges of 500m each -> 1000m
    G.add_node(1, lon=-71.24, lat=-34.98)
    G.add_node(2, lon=-71.241, lat=-34.981)
    G.add_node(3, lon=-71.242, lat=-34.982)
    G.add_edge(1, 2, length_m=500.0)
    G.add_edge(2, 3, length_m=500.0)

    # Component 2: 2 nodes, 1 edge of 300m -> 300m
    G.add_node(4, lon=-71.25, lat=-34.99)
    G.add_node(5, lon=-71.251, lat=-34.991)
    G.add_edge(4, 5, length_m=300.0)

    # Isolated node (ignored since 0 edges)
    G.add_node(6, lon=-71.26, lat=-34.97)

    comps = extract_cycling_components(G)
    assert len(comps) == 3  # 2 edge components + 1 node component
    assert comps[0].id == 1
    assert comps[0].length_m == 1000.0
    assert comps[0].nodes == {1, 2, 3}
    assert comps[1].id == 2
    assert comps[1].length_m == 300.0
    assert comps[1].nodes == {4, 5}


def test_curico_missing_connections_geojson_structure():
    """Verify that Curicó's generated missing-connections.geojson meets all quality requirements."""
    geojson_path = DATA_DIR / "missing-connections.geojson"
    assert geojson_path.exists()

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["type"] == "FeatureCollection"
    features = data["features"]
    assert 5 <= len(features) <= 20  # Expecting top 10 ranked opportunities

    # Check properties of all features
    prev_score = float("inf")
    for feat in features:
        assert feat["type"] == "Feature"
        geom = feat["geometry"]
        assert geom["type"] == "LineString"
        coords = geom["coordinates"]
        assert len(coords) >= 2
        for pt in coords:
            assert len(pt) == 2
            # Curicó bounds roughly: lon [-71.4, -71.1], lat [-35.1, -34.8]
            assert -71.4 < pt[0] < -71.1
            assert -35.1 < pt[1] < -34.8

        props = feat["properties"]
        assert props["is_demo"] is False
        assert props["status"] == "ALGORITHMIC_CANDIDATE"
        assert "id" in props
        assert "priority_score" in props
        assert "gap_length_m" in props
        assert "connected_network_km" in props
        assert "gain_ratio" in props
        assert "streets" in props
        assert "description" in props
        assert "name" in props

        # Priority scores must be non-negative and correctly sorted descending
        score = props["priority_score"]
        assert 0 <= score <= 100
        assert score <= prev_score + 1e-6  # sorted descending
        prev_score = score

        # Check prudent terminology in explanation
        explanation = props["description"]
        assert any(term in explanation.lower() for term in ["oportunidad", "conexión", "uniría", "brecha"])
        assert "debe construirse" not in explanation.lower()
        assert "proyecto aprobado" not in explanation.lower()


def test_curico_components_and_gap_candidates_pipeline():
    """Verify that the end-to-end gap detector works consistently on Curicó's real data."""
    nav_graph_path = DATA_DIR / "nav_graph.json"
    if not nav_graph_path.exists():
        pytest.skip("nav_graph.json not found")

    with open(nav_graph_path, "r", encoding="utf-8") as f:
        graph_dict = json.load(f)

    G_nav = deserialize_graph_from_json(graph_dict)
    G_cycling = build_cycling_subgraph(G_nav)

    assert G_cycling.number_of_nodes() > 100
    assert G_cycling.number_of_edges() > 100

    components = extract_cycling_components(G_cycling)
    assert len(components) >= 10

    # Top component should be the main backbone (> 15 km)
    assert components[0].length_m > 15000.0

    # Find candidates
    candidates = find_candidate_gaps(G_nav, components, max_path_len_m=1200.0)
    assert len(candidates) >= 10

    # Deduplicate & rank
    ranked = deduplicate_and_rank_candidates(candidates, max_results=10)
    assert len(ranked) == 10
    # The top candidate connects with high score
    assert ranked[0]["priority_score"] >= 70.0

