from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "CicloConecta" in data["name"]
    assert "version" in data


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_list_cities():
    response = client.get("/api/cities")
    assert response.status_code == 200
    cities = response.json()
    assert isinstance(cities, list)
    assert len(cities) >= 1
    curico = next((c for c in cities if c["id"] == "curico"), None)
    assert curico is not None
    assert curico["name"] == "Curicó"
    assert curico["center"] == [-71.2394, -34.9854]
    assert curico["stats"]["cycleways_count"] > 0


def test_get_city_detail():
    response = client.get("/api/cities/curico")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "curico"
    assert len(data["available_layers"]) >= 3
    layer_ids = [l["id"] for l in data["available_layers"]]
    assert "cycling-infrastructure" in layer_ids
    assert "missing-connections" in layer_ids
    assert "suggested-routes" in layer_ids


def test_get_cycling_infrastructure_layer():
    response = client.get("/api/cities/curico/layers/cycling-infrastructure")
    assert response.status_code == 200
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) > 50
    first_feat = geojson["features"][0]
    assert "geometry" in first_feat
    assert first_feat["geometry"]["type"] == "LineString"
    assert "properties" in first_feat
    assert first_feat["properties"]["is_demo"] is False
    assert "source" in first_feat["properties"]


def test_get_missing_connections_layer():
    response = client.get("/api/cities/curico/layers/missing-connections")
    assert response.status_code == 200
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 1
    first_feat = geojson["features"][0]
    assert first_feat["properties"]["is_demo"] is True
    assert first_feat["properties"]["status"] == "DEMO"


def test_nonexistent_city_returns_404():
    response = client.get("/api/cities/ciudad-inexistente")
    assert response.status_code == 404


def test_nonexistent_layer_returns_404():
    response = client.get("/api/cities/curico/layers/capa-fantasma")
    assert response.status_code == 404
