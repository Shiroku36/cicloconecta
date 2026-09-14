"""
Unit tests for Phase 3.5 Methodological Correction:
Algorithmic & Data-Driven Network Expansion Planner without hardcoded anchors.
"""

import inspect
import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app.main import app
import pipeline.expansion_planner as ep

client = TestClient(app)


def test_no_hardcoded_anchors_in_production():
    """Verify that plan_city_expansion does not call or depend on any get_city_anchors."""
    source = inspect.getsource(ep.plan_city_expansion)
    assert "get_city_anchors" not in source
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
    assert expansion["total_expansion_km"] >= 4.0
    assert expansion["total_new_nodes"] >= 500
    assert expansion["total_coverage_gain_pct"] > 0
    assert "baseline_coverage" in expansion
    assert "0-250m" in expansion["baseline_coverage"]["distance_bands"]


def test_poi_deduplication_integrity():
    """Verify that POIs are deduplicated and stats recorded."""
    for city in ["curico", "talca"]:
        response = client.get(f"/api/cities/{city}/layers/network-expansion")
        assert response.status_code == 200
        meta = response.json()["metadata"]
        assert "poi_deduplication" in meta
        raw_c = meta["poi_deduplication"]["raw_pois_count"]
        dedup_c = meta["poi_deduplication"]["deduplicated_pois_count"]
        assert raw_c > 0
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

    features = data["features"]
    assert len(features) >= 5

    for idx, feat in enumerate(features, start=1):
        assert feat["type"] == "Feature"
        geom = feat["geometry"]
        assert geom["type"] == "LineString"
        assert len(geom["coordinates"]) >= 2
        for coord in geom["coordinates"]:
            assert len(coord) == 2
            assert -71.35 <= coord[0] <= -71.15
            assert -35.10 <= coord[1] <= -34.90

        props = feat["properties"]
        assert props["id"] == f"expansion-curico-{idx:02d}"
        assert props["phase"] == idx
        assert props["badge"] == "ANÁLISIS"
        assert props["status"] == "ALGORITHMIC_EXPANSION"
        assert props["expansion_score"] > 0
        assert props["length_km"] > 0.3
        assert props["coverage_gain_nodes"] >= 15
        assert props["coverage_gain_urban_access_nodes"] >= 15
        assert "structural_axis_score" in props
        assert "physical_width_status" in props
        assert len(props["streets"]) > 0
        assert "disclaimer" in props
        assert "poi_summary" in props


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

    features = data["features"]
    assert len(features) >= 5

    for idx, feat in enumerate(features, start=1):
        assert feat["type"] == "Feature"
        geom = feat["geometry"]
        assert geom["type"] == "LineString"
        assert len(geom["coordinates"]) >= 2
        for coord in geom["coordinates"]:
            assert len(coord) == 2
            assert -71.72 <= coord[0] <= -71.58
            assert -35.50 <= coord[1] <= -35.38

        props = feat["properties"]
        assert props["id"] == f"expansion-talca-{idx:02d}"
        assert props["phase"] == idx
        assert props["badge"] == "ANÁLISIS"
        assert props["status"] == "ALGORITHMIC_EXPANSION"
        assert props["expansion_score"] > 0
        assert props["length_km"] > 0.3
        assert props["coverage_gain_nodes"] >= 15
        assert props["coverage_gain_urban_access_nodes"] >= 15
        assert "structural_axis_score" in props
        assert "physical_width_status" in props
        assert len(props["streets"]) > 0
        assert "disclaimer" in props


def test_expansion_scoring_and_phases_ordering():
    for city in ["curico", "talca"]:
        response = client.get(f"/api/cities/{city}/layers/network-expansion")
        assert response.status_code == 200
        data = response.json()
        features = data["features"]

        # Phase 1 must have high expansion score (>= 80 pts)
        phase_1 = features[0]["properties"]
        assert phase_1["phase"] == 1
        assert phase_1["expansion_score"] >= 80.0
        assert phase_1["coverage_gain_nodes"] >= 100


def test_no_unverified_claims_in_geojson():
    """Verify that features do not claim 'habitantes' or unverified physical capacity."""
    for city in ["curico", "talca"]:
        response = client.get(f"/api/cities/{city}/layers/network-expansion")
        assert response.status_code == 200
        text_content = json.dumps(response.json(), ensure_ascii=False).lower()

        assert "habitantes beneficiados" not in text_content
        assert "población beneficiada" not in text_content
        assert "perfil vial suficiente" not in text_content
        assert "ancho suficiente" not in text_content


def test_geometries_follow_navigable_network():
    """Verify that expansion corridor coordinates are not straight lines and exist in the road graph."""
    base_dir = Path(__file__).resolve().parent.parent.parent

    for city in ["curico", "talca"]:
        nav_graph_path = base_dir / "data" / "cities" / city / "nav_graph.json"
        with open(nav_graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)

        # Set of rounded graph coordinates
        graph_coords = {
            (round(n["lon"], 5), round(n["lat"], 5)) for n in graph_data["nodes"]
        }

        response = client.get(f"/api/cities/{city}/layers/network-expansion")
        features = response.json()["features"]

        for feat in features:
            coords = feat["geometry"]["coordinates"]
            # Must have multiple intermediate vertices (not just 2 points forming a straight line)
            assert len(coords) >= 10, f"Corridor {feat['id']} should have road vertices, got {len(coords)}"
            # Almost all vertices must match nodes from nav_graph
            matched = sum(1 for c in coords if (round(c[0], 5), round(c[1], 5)) in graph_coords)
            match_ratio = matched / len(coords)
            assert match_ratio >= 0.95, f"{city} {feat['id']}: match ratio {match_ratio} < 0.95"
