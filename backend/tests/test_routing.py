import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from pipeline.cost_function import evaluate_edge_cycling_cost, is_oneway_for_bicycle
from pipeline.router import SpatialNodeIndex, CoordinateOutOfBoundsError
import networkx as nx

client = TestClient(app)


def test_cost_function_dedicated_cycleway():
    tags = {"highway": "cycleway", "segregated": "yes"}
    is_cyclable, penalty, cat, label = evaluate_edge_cycling_cost(tags)
    assert is_cyclable is True
    assert penalty == 0.70
    assert cat == "dedicated_cycleway"


def test_cost_function_cycle_lane():
    tags = {"highway": "residential", "cycleway": "lane"}
    is_cyclable, penalty, cat, label = evaluate_edge_cycling_cost(tags)
    assert is_cyclable is True
    assert penalty == 0.88
    assert cat == "cycle_lane"


def test_cost_function_motorway_blocked():
    tags = {"highway": "motorway"}
    is_cyclable, penalty, cat, label = evaluate_edge_cycling_cost(tags)
    assert is_cyclable is False
    assert penalty == float("inf")


def test_cost_function_bicycle_no():
    tags = {"highway": "primary", "bicycle": "no"}
    is_cyclable, penalty, cat, label = evaluate_edge_cycling_cost(tags)
    assert is_cyclable is False


def test_oneway_rules_standard_and_exceptions():
    # Normal oneway
    fwd, bwd = is_oneway_for_bicycle({"oneway": "yes"})
    assert fwd is True
    assert bwd is False

    # Oneway for cars, but bidirectional for bikes
    fwd, bwd = is_oneway_for_bicycle({"oneway": "yes", "oneway:bicycle": "no"})
    assert fwd is True
    assert bwd is True

    # Contraflow lane
    fwd, bwd = is_oneway_for_bicycle({"oneway": "yes", "cycleway": "opposite_lane"})
    assert fwd is True
    assert bwd is True


def test_spatial_index_snapping():
    G = nx.DiGraph()
    G.add_node(1, lon=-71.2394, lat=-34.9854)
    G.add_node(2, lon=-71.2400, lat=-34.9860)
    index = SpatialNodeIndex(G)

    # Point very close to node 1
    node_id, dist = index.snap_to_nearest_node(-71.23945, -34.98542, max_distance_m=500.0)
    assert node_id == 1
    assert dist < 10.0

    # Point far away
    with pytest.raises(CoordinateOutOfBoundsError):
        index.snap_to_nearest_node(0.0, 0.0, max_distance_m=500.0)


def test_api_route_curico_valid():
    # Rauquén -> Plaza de Armas
    payload = {
        "origin": [-71.2185, -34.9620],
        "destination": [-71.2394, -34.9854],
        "max_snap_dist_m": 600.0,
    }
    response = client.post("/api/cities/curico/route", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["city_id"] == "curico"
    assert "cycling_route" in data
    assert "shortest_route" in data
    assert "comparison" in data

    # Check metrics
    cycling = data["cycling_route"]
    assert cycling["distance_km"] > 0
    assert cycling["cycling_infra_pct"] > 0
    assert len(cycling["coordinates"]) >= 2

    comparison = data["comparison"]
    assert "cycling_gain_pct" in comparison
    assert "distance_diff_km" in comparison

    # Repeat request to test caching
    response_cached = client.post("/api/cities/curico/route", json=payload)
    assert response_cached.status_code == 200
    assert response_cached.json()["cached"] is True


def test_api_route_out_of_bounds():
    payload = {
        "origin": [-70.0000, -33.0000],  # Outside Curicó
        "destination": [-71.2394, -34.9854],
        "max_snap_dist_m": 500.0,
    }
    response = client.post("/api/cities/curico/route", json=payload)
    assert response.status_code == 400
    assert "máximo permitido" in response.json()["detail"]


def test_api_route_nonexistent_city():
    payload = {
        "origin": [-71.2185, -34.9620],
        "destination": [-71.2394, -34.9854],
    }
    response = client.post("/api/cities/ciudad-fantasma/route", json=payload)
    assert response.status_code == 404
