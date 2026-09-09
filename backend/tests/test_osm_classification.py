import pytest
from pipeline.osm_extractor import classify_osm_cycling_way, process_osm_to_geojson


def test_classification_dedicated_cycleway():
    tags = {"highway": "cycleway", "segregated": "yes"}
    category, label = classify_osm_cycling_way(tags)
    assert category == "dedicated"
    assert "segregada" in label.lower()

    tags_non_seg = {"highway": "cycleway"}
    category, label = classify_osm_cycling_way(tags_non_seg)
    assert category == "dedicated"
    assert label == "Vía ciclista dedicada"


def test_classification_on_street_lane_and_track():
    tags_lane = {"highway": "secondary", "cycleway": "lane"}
    category, label = classify_osm_cycling_way(tags_lane)
    assert category == "on_street"
    assert "lane" in label.lower() or "ciclobanda" in label.lower()

    tags_track = {"highway": "primary", "cycleway:right": "track"}
    category, label = classify_osm_cycling_way(tags_track)
    assert category == "on_street"
    assert "track" in label.lower() or "segregada" in label.lower()


def test_classification_designated():
    tags_designated = {"highway": "residential", "bicycle": "designated"}
    category, label = classify_osm_cycling_way(tags_designated)
    assert category == "designated"
    assert "designada" in label.lower()


def test_unknown_attributes_are_not_invented():
    """Verify that missing tags in OSM are not given fake default values."""
    mock_osm_data = {
        "elements": [
            {"type": "node", "id": 1, "lat": -34.98, "lon": -71.24},
            {"type": "node", "id": 2, "lat": -34.981, "lon": -71.241},
            {
                "type": "way",
                "id": 100,
                "nodes": [1, 2],
                "tags": {
                    "highway": "cycleway",
                    # Note: No 'surface', no 'segregated', no 'name'
                },
            },
        ]
    }

    geojson, total_m, count = process_osm_to_geojson(mock_osm_data)
    assert count == 1
    feature = geojson["features"][0]
    props = feature["properties"]

    # surface must NOT default to "asfalto / pavimento"
    assert props["surface"] is None
    assert props["surface_display"] == "Sin información"

    # segregated must NOT default to "yes"
    assert props["segregated"] is None
    assert props["segregated_display"] == "Sin información"

    # Raw tags must be preserved
    assert "raw_osm_tags" in props
    assert props["raw_osm_tags"] == {"highway": "cycleway"}


def test_geojson_structure_validity():
    """Verify standard GeoJSON structure and metadata compliance."""
    mock_osm_data = {
        "elements": [
            {"type": "node", "id": 10, "lat": -34.985, "lon": -71.239},
            {"type": "node", "id": 20, "lat": -34.986, "lon": -71.240},
            {
                "type": "way",
                "id": 200,
                "nodes": [10, 20],
                "tags": {
                    "highway": "cycleway",
                    "name": "Ciclovía Av. O'Higgins",
                    "surface": "asphalt",
                    "segregated": "yes",
                },
            },
        ]
    }

    geojson, total_m, count = process_osm_to_geojson(mock_osm_data)
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    assert geojson["metadata"]["source"] == "OpenStreetMap Contributors"
    assert geojson["metadata"]["verified_in_situ"] is False

    feat = geojson["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "LineString"
    assert len(feat["geometry"]["coordinates"]) == 2
    assert feat["properties"]["surface"] == "asphalt"
    assert feat["properties"]["segregated"] == "yes"
    assert feat["properties"]["length_m"] > 0
