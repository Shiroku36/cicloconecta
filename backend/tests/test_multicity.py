"""
Unit tests for multi-city architecture and Talca ingestion.
"""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_list_cities_contains_curico_and_talca():
    response = client.get("/api/cities")
    assert response.status_code == 200
    cities = response.json()
    assert len(cities) >= 2

    curico = next((c for c in cities if c["id"] == "curico"), None)
    assert curico is not None
    assert curico["enabled"] is True
    assert curico["name"] == "Curicó"

    talca = next((c for c in cities if c["id"] == "talca"), None)
    assert talca is not None
    assert talca["enabled"] is True
    assert talca["name"] == "Talca"
    assert talca["stats"] is not None
    assert talca["stats"]["cycleways_count"] >= 200
    assert talca["stats"]["total_km"] >= 65.0


def test_talca_city_detail():
    response = client.get("/api/cities/talca")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "talca"
    assert data["name"] == "Talca"
    assert data["region"] == "Región del Maule"
    assert data["center"] == [-71.6554, -35.4264]
    assert len(data["available_layers"]) >= 3
    assert len(data["presets"]) >= 5

    layer_ids = [layer["id"] for layer in data["available_layers"]]
    assert "cycling-infrastructure" in layer_ids
    assert "missing-connections" in layer_ids
    assert "suggested-routes" in layer_ids


def test_talca_layers_endpoints():
    # 1. Cycling infrastructure
    res_infra = client.get("/api/cities/talca/layers/cycling-infrastructure")
    assert res_infra.status_code == 200
    data_infra = res_infra.json()
    assert data_infra["type"] == "FeatureCollection"
    assert len(data_infra["features"]) >= 200

    # 2. Missing connections
    res_gaps = client.get("/api/cities/talca/layers/missing-connections")
    assert res_gaps.status_code == 200
    data_gaps = res_gaps.json()
    assert len(data_gaps["features"]) == 10
    top_gap = data_gaps["features"][0]
    assert top_gap["properties"]["is_demo"] is False
    assert top_gap["properties"]["status"] == "ALGORITHMIC_CANDIDATE"
    assert top_gap["properties"]["priority_score"] >= 80.0

    # 3. Suggested routes
    res_routes = client.get("/api/cities/talca/layers/suggested-routes")
    assert res_routes.status_code == 200
    data_routes = res_routes.json()
    assert len(data_routes["features"]) == 5


def test_talca_route_calculation():
    # Campus Lircay UTalca -> Plaza de Armas Talca
    payload = {
        "origin": [-71.6360, -35.4045],
        "destination": [-71.6663, -35.4261],
        "max_snap_dist_m": 600.0,
        "profile": "balanced",
    }
    response = client.post("/api/cities/talca/route", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["city_id"] == "talca"
    assert data["cycling_route"]["distance_km"] > 3.0
    assert data["cycling_route"]["cycling_infra_pct"] > 40.0
    assert len(data["cycling_route"]["coordinates"]) > 10


def test_city_routing_engines_are_isolated():
    # Route in Curicó
    curico_payload = {
        "origin": [-71.2185, -34.9620],
        "destination": [-71.2394, -34.9854],
    }
    res_curico = client.post("/api/cities/curico/route", json=curico_payload)
    assert res_curico.status_code == 200
    assert res_curico.json()["city_id"] == "curico"

    # Route in Talca
    talca_payload = {
        "origin": [-71.6360, -35.4045],
        "destination": [-71.6663, -35.4261],
    }
    res_talca = client.post("/api/cities/talca/route", json=talca_payload)
    assert res_talca.status_code == 200
    assert res_talca.json()["city_id"] == "talca"
