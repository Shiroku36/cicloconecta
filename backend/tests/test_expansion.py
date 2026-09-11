"""
Unit tests for Phase 3.5: Algorithmic Network Expansion Planner.
"""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


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

    # Validate each feature structure and sequential phases
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
        assert props["coverage_gain_pct"] > 0
        assert len(props["streets"]) > 0
        assert "disclaimer" in props
        assert "poi_summary" in props


def test_expansion_scoring_and_phases_ordering():
    response = client.get("/api/cities/curico/layers/network-expansion")
    assert response.status_code == 200
    data = response.json()
    features = data["features"]

    # Phase 1 must have high expansion score (>= 80 pts)
    phase_1 = features[0]["properties"]
    assert phase_1["phase"] == 1
    assert phase_1["expansion_score"] >= 80.0
    assert phase_1["coverage_gain_nodes"] >= 100