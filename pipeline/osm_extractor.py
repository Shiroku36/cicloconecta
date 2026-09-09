"""
CicloConecta — OpenStreetMap Data Extractor for Cycling Infrastructure.
Extracts real cycleway ways from OSM via Overpass API for a given city bounding box,
normalizes attributes transparently, computes geodesic distances, and outputs standard GeoJSON
and city metadata.
"""

import json
import math
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def compute_linestring_length(coords: list[list[float]]) -> float:
    """Compute total length of a GeoJSON LineString coordinates list [[lon, lat], ...] in meters."""
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine_distance(
            coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1]
        )
    return total


def classify_osm_cycling_way(tags: dict) -> tuple[str, str]:
    """
    Transparently classify an OSM way based on real tags.
    Returns (category_code, human_label).

    Categories:
    - dedicated: Vía ciclista dedicada (highway=cycleway)
    - on_street: Infraestructura ciclista sobre calle (cycleway=track|lane|etc.)
    - designated: Vía designada / preferente para bicicleta (bicycle=designated)
    - compatible: Infraestructura ciclista compatible
    """
    highway = tags.get("highway", "")
    has_cycleway_tag = any(k.startswith("cycleway") for k in tags)

    if highway == "cycleway":
        segregated = tags.get("segregated")
        if segregated == "yes":
            return "dedicated", "Vía ciclista dedicada (segregada)"
        return "dedicated", "Vía ciclista dedicada"

    if has_cycleway_tag:
        cycleway_val = tags.get("cycleway", "")
        is_track = (
            cycleway_val == "track"
            or tags.get("cycleway:left") == "track"
            or tags.get("cycleway:right") == "track"
            or tags.get("cycleway:both") == "track"
        )
        is_lane = (
            cycleway_val in ("lane", "share_busway")
            or tags.get("cycleway:left") == "lane"
            or tags.get("cycleway:right") == "lane"
            or tags.get("cycleway:both") == "lane"
        )
        if is_track:
            return "on_street", "Infraestructura ciclista sobre calle (segregada / track)"
        if is_lane:
            return "on_street", "Infraestructura ciclista sobre calle (ciclobanda / lane)"
        return "on_street", "Infraestructura ciclista sobre calle"

    if tags.get("bicycle") == "designated":
        return "designated", "Vía designada / preferente para bicicleta"

    return "compatible", "Infraestructura ciclista compatible"


def fetch_osm_cycleways(
    bbox: tuple[float, float, float, float],
    cache_path: Path | None = None,
    force_refresh: bool = False,
) -> dict:
    """
    Fetch cycling ways and their nodes from Overpass API or local cache.
    bbox order: (south, west, north, east)
    """
    if cache_path and cache_path.exists() and not force_refresh:
        print(f"Cargando vías ciclistas desde caché local: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    s, w, n, e = bbox
    overpass_endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]
    query = f"""[out:json][timeout:90];
(
  way["highway"="cycleway"]({s},{w},{n},{e});
  way["cycleway"]({s},{w},{n},{e});
  way["cycleway:left"]({s},{w},{n},{e});
  way["cycleway:right"]({s},{w},{n},{e});
  way["cycleway:both"]({s},{w},{n},{e});
  way["bicycle"="designated"]({s},{w},{n},{e});
);
out body;
>;
out skel qt;
"""
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    print(f"Consultando Overpass API para bbox {bbox}...")
    last_err = None

    for endpoint in overpass_endpoints:
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"User-Agent": "CicloConecta-Extractor/1.0 (https://github.com/shiroku36/cicloconecta)"},
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
                        print(f"Vías ciclistas guardadas en caché: {cache_path}")
                    return content
            except Exception as err:
                print(f"Endpoint {endpoint} intento {attempt} falló: {err}")
                last_err = err
                time.sleep(2 * attempt)

    raise RuntimeError(f"No se pudieron descargar vías ciclistas desde ningún servidor Overpass: {last_err}")


def process_osm_to_geojson(osm_data: dict, city_id: str = "curico") -> tuple[dict, float, int]:
    """
    Transforms OSM JSON elements into a standard GeoJSON FeatureCollection for a city.
    Does NOT invent missing data (surface, segregated).
    Returns (geojson_dict, total_length_meters, count_features).
    """
    elements = osm_data.get("elements", [])
    nodes = {}
    ways = []

    for el in elements:
        if el.get("type") == "node":
            nodes[el["id"]] = [round(el["lon"], 6), round(el["lat"], 6)]
        elif el.get("type") == "way":
            ways.append(el)

    features = []
    total_length_m = 0.0

    for way in ways:
        way_nodes = way.get("nodes", [])
        coords = [nodes[nid] for nid in way_nodes if nid in nodes]

        if len(coords) < 2:
            continue

        length_m = compute_linestring_length(coords)
        total_length_m += length_m

        tags = way.get("tags", {})
        highway = tags.get("highway")
        name = tags.get("name")
        surface = tags.get("surface")  # None if not present, never invent "asfalto"
        segregated = tags.get("segregated")  # None if not present, never invent "yes"
        oneway = tags.get("oneway")

        category_code, infra_label = classify_osm_cycling_way(tags)

        feature = {
            "type": "Feature",
            "id": f"osm-{way['id']}",
            "properties": {
                "id": f"{city_id}-osm-{way['id']}",
                "name": name if name else "Vía ciclista sin nombre",
                "has_custom_name": bool(name),
                "type": infra_label,
                "category": category_code,
                "highway": highway,
                "surface": surface,  # None if unknown, preserved exactly from OSM
                "surface_display": surface if surface else "Sin información",
                "segregated": segregated,  # None if unknown
                "segregated_display": (
                    "Segregada físicamente"
                    if segregated == "yes"
                    else "No segregada"
                    if segregated == "no"
                    else "Sin información"
                ),
                "oneway": oneway,
                "length_m": round(length_m, 1),
                "length_km": round(length_m / 1000.0, 2),
                "source": "OpenStreetMap Contributors",
                "source_id": way["id"],
                "is_demo": False,
                "raw_osm_tags": tags,
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "name": f"Ciclovias_{city_id.capitalize()}_OSM",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "metadata": {
            "city": city_id,
            "source": "OpenStreetMap Contributors",
            "source_type": "open_data",
            "verified_in_situ": False,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "total_features": len(features),
            "total_km": round(total_length_m / 1000.0, 2),
        },
        "features": features,
    }

    return geojson, total_length_m, len(features)


def generate_curico_demo_layers(data_dir: Path):
    """
    Generates missing-connections.geojson and suggested-routes.geojson
    with clearly marked demo datasets based on Curico's urban fabric.
    """
    missing_connections = {
        "type": "FeatureCollection",
        "name": "Conexiones_Faltantes_Curico_Demo",
        "metadata": {
            "city": "curico",
            "is_demo": True,
            "status": "DEMO / ESTIMACIÓN CONCEPTUAL",
            "description": "Tramos faltantes identificados preliminarmente para conectar ejes ciclistas existentes.",
        },
        "features": [
            {
                "type": "Feature",
                "id": "gap-curico-01",
                "properties": {
                    "id": "gap-curico-01",
                    "name": "Eje Conexión Rauquén - Estación Curicó",
                    "description": "Falta tramo de ciclovía segura para conectar la zona norte residencial de Rauquén con la Estación de Trenes.",
                    "priority": "Alta",
                    "gap_length_m": 850,
                    "estimated_benefit": "Conecta 15.000 residentes con el eje ferroviario y centro comercial",
                    "is_demo": True,
                    "status": "DEMO",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-71.2285, -34.9720],
                        [-71.2330, -34.9775],
                        [-71.2370, -34.9820],
                    ],
                },
            },
            {
                "type": "Feature",
                "id": "gap-curico-02",
                "properties": {
                    "id": "gap-curico-02",
                    "name": "Interconexión Ciclovía O'Higgins con Av. España",
                    "description": "Corte crítico en el enlace este-oeste entre O'Higgins y los ejes hacia Los Niches.",
                    "priority": "Media-Alta",
                    "gap_length_m": 620,
                    "estimated_benefit": "Continuidad sin necesidad de circular por calzada vehicular de alto flujo",
                    "is_demo": True,
                    "status": "DEMO",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-71.2460, -34.9920],
                        [-71.2415, -34.9940],
                        [-71.2360, -34.9960],
                    ],
                },
            },
            {
                "type": "Feature",
                "id": "gap-curico-03",
                "properties": {
                    "id": "gap-curico-03",
                    "name": "Continuidad Ciclovía Merced al Río Guaiquillo",
                    "description": "Tramo sur para dar acceso a parque ribera y zonas recreativas.",
                    "priority": "Media",
                    "gap_length_m": 430,
                    "estimated_benefit": "Acceso a zona sur y áreas verdes protegidas",
                    "is_demo": True,
                    "status": "DEMO",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-71.2420, -35.0010],
                        [-71.2440, -35.0040],
                        [-71.2470, -35.0070],
                    ],
                },
            },
        ],
    }

    suggested_routes = {
        "type": "FeatureCollection",
        "name": "Rutas_Sugeridas_Curico_Demo",
        "metadata": {
            "city": "curico",
            "is_demo": True,
            "status": "DEMO / ESTIMACIÓN CONCEPTUAL",
            "description": "Rutas sugeridas de bajo estrés de tránsito mientras se completan las ciclovías formales.",
        },
        "features": [
            {
                "type": "Feature",
                "id": "route-curico-01",
                "properties": {
                    "id": "route-curico-01",
                    "name": "Ruta Barrial Calma: Zapallar - Plaza de Armas",
                    "type": "Ruta recomendada de bajo estrés vehicular",
                    "surface": "Pavimento urbano mixto",
                    "speed_limit_kmh": 30,
                    "length_km": 3.4,
                    "is_demo": True,
                    "status": "DEMO",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-71.2150, -34.9810],
                        [-71.2220, -34.9830],
                        [-71.2300, -34.9845],
                        [-71.2394, -34.9854],
                    ],
                },
            },
            {
                "type": "Feature",
                "id": "route-curico-02",
                "properties": {
                    "id": "route-curico-02",
                    "name": "Circuito Estudiante: Campus UTAL - Centro",
                    "type": "Corredor sugerido universitario",
                    "surface": "Asfalto",
                    "speed_limit_kmh": 30,
                    "length_km": 4.1,
                    "is_demo": True,
                    "status": "DEMO",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-71.2250, -34.9650],
                        [-71.2310, -34.9730],
                        [-71.2350, -34.9810],
                        [-71.2394, -34.9854],
                    ],
                },
            },
        ],
    }

    with open(data_dir / "missing-connections.geojson", "w", encoding="utf-8") as f:
        json.dump(missing_connections, f, ensure_ascii=False, indent=2)

    with open(data_dir / "suggested-routes.geojson", "w", encoding="utf-8") as f:
        json.dump(suggested_routes, f, ensure_ascii=False, indent=2)

    print("Capas DEMO (conexiones faltantes y rutas sugeridas) creadas con etiquetas explícitas.")


def sync_data_to_frontend(city_data_dir: Path, base_dir: Path, city_id: str):
    """
    Synchronizes city data to frontend/public/data/cities/{city_id} automatically
    to maintain data/ as the single source of truth.
    """
    target_dir = base_dir / "frontend" / "public" / "data" / "cities" / city_id
    target_dir.mkdir(parents=True, exist_ok=True)

    for item in city_data_dir.glob("*.*"):
        shutil.copy2(item, target_dir / item.name)

    print(f"Sincronizados datasets de {city_id} hacia {target_dir}")


def main():
    curico_bbox = (-35.05, -71.30, -34.93, -71.18)
    curico_center = [-71.2394, -34.9854]  # [lon, lat]

    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "cities" / "curico"
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        osm_data = fetch_osm_cycleways(curico_bbox)
        geojson, total_m, count = process_osm_to_geojson(osm_data)
        out_file = data_dir / "cycling-infrastructure.geojson"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"Éxito: {count} vías ciclistas extraídas ({round(total_m/1000, 2)} km) guardadas en {out_file}")
    except Exception as e:
        print(f"Advertencia: no se pudo consultar Overpass en este momento ({e}).")
        sys.exit(1)

    # City metadata
    city_metadata = {
        "id": "curico",
        "name": "Curicó",
        "province": "Curicó",
        "region": "Región del Maule",
        "country": "Chile",
        "center": curico_center,
        "initial_zoom": 13.5,
        "bounds": [[-71.30, -35.05], [-71.18, -34.93]],
        "description": "Ciudad intermedia en la Región del Maule, con topografía plana favorable para el ciclismo urbano y desafíos de conectividad.",
        "stats": {
            "cycleways_count": count,
            "total_km": round(total_m / 1000.0, 2),
            "layers_available": [
                "cycling-infrastructure",
                "missing-connections",
                "suggested-routes",
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
    }

    with open(data_dir / "city.json", "w", encoding="utf-8") as f:
        json.dump(city_metadata, f, ensure_ascii=False, indent=2)
    print(f"Metadatos de ciudad guardados en {data_dir / 'city.json'}")

    generate_curico_demo_layers(data_dir)

    # Automatically synchronize to frontend/public to keep single source of truth
    sync_data_to_frontend(data_dir, base_dir, "curico")


if __name__ == "__main__":
    main()
