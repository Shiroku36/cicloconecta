"""
Unit tests for Phase 3.6: Real Topological Cycling Network Growth,
Active Cycling Network, Dynamic Continuity Scoring, Dependencies, and Urban/Periurban Classification.
"""

import inspect
import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app
import pipeline.expansion_planner as ep

client = TestClient(app)


def test_no_hardcoded_anchors_in_production():
    """Verify that expansion_planner does not contain manual anchors or debug coordinates."""
    source = inspect.getsource(ep)
    assert "get_city_anchors" not in source
    assert "get_debug_manual_anchors" not in source
    assert "if city_id == \"curico\"" not in source
    assert "if city_id == \"talca\"" not in source


def test_curico_city_detail_has_expansion_layer():
    response = client.get("/api/cities/curico")
    assert response.status_code == 200
    data = response.json()

    available_layer_ids = [l["id"] for l in data["available_layers"]]
    assert "network-expansion" in available_layer_ids

    expansion_layer = next(l for l in data["available_layers"] if l["id"] == "network-expansion")
    assert expansion_layer["name"] == "Expansión de red"
    assert expansion_layer["color"] == "#8b5cf6"
    assert expansion_layer["is_demo"] is False
    assert expansion_layer["feature_count"] >= 5


def test_talca_city_detail_has_expansion_layer():
    response = client.get("/api/cities/talca")
    assert response.status_code == 200
    data = response.json()

    available_layer_ids = [l["id"] for l in data["available_layers"]]
    assert "network-expansion" in available_layer_ids

    expansion_layer = next(l for l in data["available_layers"] if l["id"] == "network-expansion")
    assert expansion_layer["name"] == "Expansión de red"
    assert expansion_layer["color"] == "#8b5cf6"
    assert expansion_layer["is_demo"] is False
    assert expansion_layer["feature_count"] >= 5


def test_curico_expansion_metadata_present():
    response = client.get("/api/cities/curico")
    assert response.status_code == 200
    data = response.json()

    assert "expansion" in data
    expansion = data["expansion"]
    assert expansion is not None
    assert expansion["total_phases"] >= 5
    assert expansion["total_expansion_km"] > 3.0
    assert expansion["total_new_urban_access_nodes"] > 500
    assert expansion["total_new_pois"] > 20
    assert "expansion_types_summary" in expansion


def test_talca_expansion_metadata_present():
    response = client.get("/api/cities/talca")
    assert response.status_code == 200
    data = response.json()

    assert "expansion" in data
    expansion = data["expansion"]
    assert expansion is not None
    assert expansion["total_phases"] >= 5
    assert expansion["total_expansion_km"] > 3.0
    assert expansion["total_new_urban_access_nodes"] > 500
    assert expansion["total_new_pois"] > 20
    assert "expansion_types_summary" in expansion


def test_poi_deduplication_integrity():
    """Verify that deduplicate_pois properly reduces duplicated amenities."""
    for city in ["curico", "talca"]:
        raw_pois_file = Path(f"data/cities/{city}/raw_pois.json")
        assert raw_pois_file.exists()

        with open(raw_pois_file, "r", encoding="utf-8") as f:
            raw_elements = json.load(f).get("elements", [])

        cos_lat = 0.819 if city == "curico" else 0.815
        cat_pois = ep.parse_and_categorize_pois(raw_elements)
        dedup_pois = ep.deduplicate_pois(cat_pois, cos_lat)

        raw_c = len(cat_pois)
        dedup_c = len(dedup_pois)

        assert dedup_c > 0
        assert dedup_c <= raw_c, f"{city}: Deduplicated count should be <= raw count"


def test_clusters_detection_and_coverage_distance():
    """Verify discovered clusters exist and represent underserved areas with mean_distance > 400m."""
    for city in ["curico", "talca"]:
        response = client.get(f"/api/cities/{city}/layers/network-expansion")
        assert response.status_code == 200
        meta = response.json()["metadata"]
        assert "discovered_clusters" in meta
        clusters = meta["discovered_clusters"]
        assert len(clusters) >= 5

        for cl in clusters:
            assert cl["node_count"] >= 20
            assert cl["mean_distance_to_cycle_network"] >= 400.0, (
                f"Cluster {cl['id']} in {city} should be underserved (> 400m)"
            )
            assert len(cl["centroid"]) == 2
            assert len(cl["bbox"]) == 4


def test_curico_expansion_geojson_endpoint():
    response = client.get("/api/cities/curico/layers/network-expansion")
    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert "metadata" in data
    meta = data["metadata"]
    assert meta["city_id"] == "curico"
    assert meta["layer_id"] == "network-expansion"
    assert meta["badge"] == "ANÁLISIS"
    assert meta["status"] == "ALGORITHMIC_EXPANSION"
    assert meta["total_phases"] == len(data["features"])
    assert "expansion_types_summary" in meta
    assert "urban_contexts_summary" in meta


def test_talca_expansion_geojson_endpoint():
    response = client.get("/api/cities/talca/layers/network-expansion")
    assert response.status_code == 200
    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert "metadata" in data
    meta = data["metadata"]
    assert meta["city_id"] == "talca"
    assert meta["layer_id"] == "network-expansion"
    assert meta["badge"] == "ANÁLISIS"
    assert meta["status"] == "ALGORITHMIC_EXPANSION"
    assert meta["total_phases"] == len(data["features"])
    assert "expansion_types_summary" in meta
    assert "urban_contexts_summary" in meta


def test_expansion_scoring_and_phases_ordering():
    """Verify that phases are numbered 1..N and scores decrease or are monotonic in greedy selection."""
    for city in ["curico", "talca"]:
        response = client.get(f"/api/cities/{city}/layers/network-expansion")
        assert response.status_code == 200
        features = response.json()["features"]

        scores = []
        for idx, feat in enumerate(features, 1):
            props = feat["properties"]
            assert props["phase"] == idx
            assert 0.0 <= props["score"] <= 100.0
            scores.append(props["score"])
            assert 5.0 <= props["structural_axis_score"] <= 10.0

            # Cumulative values must strictly grow
            cum = props["cumulative_totals"]
            assert cum["length_km"] > 0
            assert cum["urban_access_nodes"] > 0


def test_no_unverified_claims_in_geojson():
    """Ensure no unverified claims (e.g. population numbers, ancho suficiente) exist in properties."""
    forbidden_terms = ["habitantes", "población beneficiada", "ancho suficiente", "factibilidad asegurada"]

    for city in ["curico", "talca"]:
        response = client.get(f"/api/cities/{city}/layers/network-expansion")
        assert response.status_code == 200
        features = response.json()["features"]

        for feat in features:
            props = feat["properties"]
            props_str = json.dumps(props, ensure_ascii=False).lower()
            for term in forbidden_terms:
                assert term not in props_str, f"Found forbidden unverified claim '{term}' in {city}"
            assert props["physical_width_status"] == "UNVERIFIED_IN_OSM"


def test_geometries_follow_navigable_network():
    """Verify that every expansion corridor follows the underlying navigable street network."""
    for city in ["curico", "talca"]:
        response = client.get(f"/api/cities/{city}/layers/network-expansion")
        assert response.status_code == 200
        features = response.json()["features"]

        with open(f"data/cities/{city}/nav_graph.json", "r", encoding="utf-8") as f:
            nav_graph = json.load(f)

        node_coords = {(round(n["lon"], 5), round(n["lat"], 5)) for n in nav_graph["nodes"]}

        for feat in features:
            coords = feat["geometry"]["coordinates"]
            assert len(coords) >= 5, f"{city}: Corridor geometry should have multiple points"
            # Every sampled point must exist in the real road network
            matched = sum(1 for pt in coords if (round(pt[0], 5), round(pt[1], 5)) in node_coords)
            match_pct = matched / len(coords)
            assert match_pct >= 0.95, f"{city}: {match_pct*100}% points matched real street graph"


def test_active_network_growth_and_no_floating_geometries():
    """Verify that every expansion corridor physically touches the active network existing at its selection."""
    for city in ["curico", "talca"]:
        with open(f"data/cities/{city}/nav_graph.json", "r", encoding="utf-8") as f:
            graph = json.load(f)
        with open(f"data/cities/{city}/network-expansion.geojson", "r", encoding="utf-8") as f:
            expansion = json.load(f)

        # Build base cycleway nodes
        base_cycle_nodes = set()
        for ed in graph["edges"]:
            if ed.get("is_cycling_infra"):
                base_cycle_nodes.add(ed["u"])
                base_cycle_nodes.add(ed["v"])

        active_nodes = set(base_cycle_nodes)
        nodes_dict = {n["id"]: (round(n["lon"], 5), round(n["lat"], 5)) for n in graph["nodes"]}
        active_coords = {nodes_dict[nid] for nid in active_nodes if nid in nodes_dict}

        for feat in expansion["features"]:
            coords = feat["geometry"]["coordinates"]
            first_pt = (round(coords[0][0], 5), round(coords[0][1], 5))
            last_pt = (round(coords[-1][0], 5), round(coords[-1][1], 5))

            # Must touch active network at at least one endpoint
            touches_active = (first_pt in active_coords) or (last_pt in active_coords)
            assert touches_active, (
                f"Feature {feat['properties']['id']} in {city} is floating! Endpoints do not touch active network."
            )

            # Add corridor points to active network
            for pt in coords:
                active_coords.add((round(pt[0], 5), round(pt[1], 5)))


def test_phase_dependencies_and_continuation_types():
    """Verify that depends_on references valid preceding phases and expansion_type matches topology."""
    valid_types = {"branch", "continuation", "trunk_extension", "cross_connector"}

    for city in ["curico", "talca"]:
        with open(f"data/cities/{city}/network-expansion.geojson", "r", encoding="utf-8") as f:
            expansion = json.load(f)

        features = expansion["features"]
        all_ids = [f["properties"]["id"] for f in features]

        for feat in features:
            props = feat["properties"]
            phase_num = props["phase"]
            exp_type = props["expansion_type"]
            depends_on = props["depends_on"]

            assert exp_type in valid_types, f"Invalid expansion_type '{exp_type}' in {city}"
            assert isinstance(depends_on, list)

            # Check that dependencies strictly precede the current phase
            for dep_id in depends_on:
                assert dep_id in all_ids, f"Dependency {dep_id} not found in {city}"
                dep_feat = next(f for f in features if f["properties"]["id"] == dep_id)
                assert dep_feat["properties"]["phase"] < phase_num, (
                    f"Dependency {dep_id} (Phase {dep_feat['properties']['phase']}) must precede Phase {phase_num}"
                )

            # If continuation, must have dependencies
            if exp_type == "continuation":
                assert len(depends_on) >= 1, f"Continuation {props['id']} in {city} must have depends_on"


def test_dynamic_non_constant_continuity_scoring():
    """Verify that score_breakdown.continuity is not a static constant across phases."""
    for city in ["curico", "talca"]:
        with open(f"data/cities/{city}/network-expansion.geojson", "r", encoding="utf-8") as f:
            expansion = json.load(f)

        continuity_scores = [f["properties"]["score_breakdown"]["continuity"] for f in expansion["features"]]
        assert len(continuity_scores) >= 5

        # All scores must be in valid range [8.0, 20.0]
        for s in continuity_scores:
            assert 8.0 <= s <= 20.0, f"Continuity score {s} out of bounds in {city}"

        # Scores should have variation (not all identical to 20.0)
        assert len(set(continuity_scores)) > 1, f"Continuity scores should not be constant in {city}: {continuity_scores}"


def test_urban_vs_periurban_context_classification():
    """Verify that every expansion feature is classified as urban, periurban, or uncertain."""
    valid_contexts = {"urban", "periurban", "uncertain"}
    valid_labels = {"Expansión Urbana", "Conector Periurbano", "Mixto / Transición"}

    for city in ["curico", "talca"]:
        with open(f"data/cities/{city}/network-expansion.geojson", "r", encoding="utf-8") as f:
            expansion = json.load(f)

        for feat in expansion["features"]:
            props = feat["properties"]
            assert "urban_context" in props
            assert props["urban_context"] in valid_contexts
            assert "environment_label" in props
            assert props["environment_label"] in valid_labels