"""
CicloConecta — OpenStreetMap Road Network Extractor.

Extracts the full navigable road network for a given city bounding box from OSM via Overpass API.
Preserves nodes, road tags, cycling infrastructure attributes, and stores a local cache
in data/cities/{city_id}/raw_network.json to enable deterministic offline processing.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional


def fetch_osm_road_network(
    bbox: tuple[float, float, float, float],
    cache_path: Optional[Path] = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Fetch all drivable and cyclable highways in bbox from Overpass API or local cache.
    bbox order: (south, west, north, east)
    """
    if cache_path and cache_path.exists() and not force_refresh:
        print(f"Cargando red vial desde caché local: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    s, w, n, e = bbox
    overpass_endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]

    # Query all road types that allow bicycles or connect urban sectors
    query = f"""[out:json][timeout:90];
(
  way["highway"~"^(cycleway|path|living_street|residential|unclassified|tertiary|tertiary_link|secondary|secondary_link|primary|primary_link|trunk|trunk_link|service|pedestrian|track)"]({s},{w},{n},{e});
);
out body;
>;
out skel qt;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    print(f"Descargando red vial desde Overpass API para bbox {bbox}...")
    last_err = None

    for endpoint in overpass_endpoints:
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"User-Agent": "CicloConecta-NetworkExtractor/1.0 (https://github.com/shiroku36/cicloconecta)"},
        )
        for attempt in range(1, 3):
            try:
                print(f"Intentando servidor Overpass: {endpoint} (intento {attempt}/2)...")
                with urllib.request.urlopen(req, timeout=120) as resp:
                    content = json.loads(resp.read().decode("utf-8"))
                    if cache_path:
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        tmp_path = cache_path.with_suffix(".tmp")
                        with open(tmp_path, "w", encoding="utf-8") as f:
                            json.dump(content, f, ensure_ascii=False)
                        tmp_path.replace(cache_path)
                        print(f"Red vial guardada en caché: {cache_path}")
                    return content
            except Exception as err:
                print(f"Endpoint {endpoint} intento {attempt} falló: {err}")
                last_err = err
                time.sleep(2 * attempt)

    raise RuntimeError(f"No se pudo descargar la red vial desde ningún servidor Overpass: {last_err}")


def extract_network_elements(osm_raw: dict[str, Any]) -> tuple[dict[int, list[float]], list[dict[str, Any]]]:
    """
    Separates raw OSM elements into:
      - nodes: { node_id: [lon, lat] }
      - ways: [ { id, nodes: [node_id, ...], tags: { ... } } ]
    """
    elements = osm_raw.get("elements", [])
    nodes: dict[int, list[float]] = {}
    ways: list[dict[str, Any]] = []

    for el in elements:
        el_type = el.get("type")
        if el_type == "node":
            nodes[el["id"]] = [round(el["lon"], 6), round(el["lat"], 6)]
        elif el_type == "way":
            ways.append({
                "id": el["id"],
                "nodes": el.get("nodes", []),
                "tags": el.get("tags", {})
            })

    return nodes, ways
