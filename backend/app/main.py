import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routing.engine import get_city_routing_engine
from .schemas import (
    CityDetail,
    CitySummary,
    GeoJSONResponse,
    HealthResponse,
    LayerInfo,
    RouteRequest,
    RouteResponse,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="API REST de CicloConecta para servir capas de movilidad ciclista y metadatos de ciudades.",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LAYER_DEFINITIONS = {
    "cycling-infrastructure": {
        "name": "Ciclovías existentes",
        "description": "Infraestructura ciclista formal mapeada en OpenStreetMap.",
        "color": "#10b981",  # Emerald Green
        "is_demo": False,
        "source": "OpenStreetMap",
    },
    "missing-connections": {
        "name": "Conexiones faltantes",
        "description": "Gaps y tramos desconectados prioritarios para conectar la red.",
        "color": "#f59e0b",  # Amber
        "is_demo": True,
        "source": "Estimación algorítmica preliminar (DEMO)",
    },
    "suggested-routes": {
        "name": "Rutas sugeridas",
        "description": "Corredores calculados algorítmicamente priorizando ciclovías y vías de bajo estrés vehicular.",
        "color": "#3b82f6",  # Blue
        "is_demo": False,
        "source": "Algoritmo de routing A* sobre red vial OpenStreetMap",
    },
}


def get_city_path(city_id: str) -> Path:
    city_dir = settings.data_dir / city_id
    if not city_dir.exists() or not (city_dir / "city.json").exists():
        raise HTTPException(
            status_code=404,
            detail=f"Ciudad '{city_id}' no encontrada en el repositorio de datos.",
        )
    return city_dir


@app.get("/", tags=["General"])
def root():
    return {
        "name": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "message": "Bienvenido a la API de CicloConecta. Visualización y análisis ciclista para ciudades de Chile.",
    }


@app.get("/api/health", response_model=HealthResponse, tags=["General"])
def health_check():
    return HealthResponse(
        status="ok",
        version=settings.version,
        environment=settings.environment,
    )


@app.get("/api/cities", response_model=list[CitySummary], tags=["Ciudades"])
def list_cities():
    cities = []
    if not settings.data_dir.exists():
        return cities

    for city_folder in sorted(settings.data_dir.iterdir()):
        if city_folder.is_dir():
            city_meta_file = city_folder / "city.json"
            if city_meta_file.exists():
                try:
                    with open(city_meta_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        cities.append(CitySummary(**data))
                except Exception:
                    continue
    return cities


@app.get("/api/cities/{city_id}", response_model=CityDetail, tags=["Ciudades"])
def get_city_detail(city_id: str):
    city_dir = get_city_path(city_id)
    with open(city_dir / "city.json", "r", encoding="utf-8") as f:
        city_data = json.load(f)

    available_layers = []
    for layer_id, meta in LAYER_DEFINITIONS.items():
        layer_file = city_dir / f"{layer_id}.geojson"
        if layer_file.exists():
            count = 0
            try:
                with open(layer_file, "r", encoding="utf-8") as lf:
                    layer_content = json.load(lf)
                    count = len(layer_content.get("features", []))
            except Exception:
                pass

            available_layers.append(
                LayerInfo(
                    id=layer_id,
                    name=meta["name"],
                    description=meta["description"],
                    color=meta["color"],
                    is_demo=meta["is_demo"],
                    source=meta["source"],
                    feature_count=count,
                )
            )

    return CityDetail(**city_data, available_layers=available_layers)


@app.get("/api/cities/{city_id}/layers", response_model=list[LayerInfo], tags=["Capas"])
def get_city_layers(city_id: str):
    city_dir = get_city_path(city_id)
    layers = []
    for layer_id, meta in LAYER_DEFINITIONS.items():
        layer_file = city_dir / f"{layer_id}.geojson"
        if layer_file.exists():
            count = 0
            try:
                with open(layer_file, "r", encoding="utf-8") as lf:
                    layer_content = json.load(lf)
                    count = len(layer_content.get("features", []))
            except Exception:
                pass
            layers.append(
                LayerInfo(
                    id=layer_id,
                    name=meta["name"],
                    description=meta["description"],
                    color=meta["color"],
                    is_demo=meta["is_demo"],
                    source=meta["source"],
                    feature_count=count,
                )
            )
    return layers


@app.get(
    "/api/cities/{city_id}/layers/{layer_id}",
    response_model=GeoJSONResponse,
    tags=["Capas"],
)
def get_city_layer_geojson(city_id: str, layer_id: str):
    city_dir = get_city_path(city_id)
    layer_file = city_dir / f"{layer_id}.geojson"
    if not layer_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Capa '{layer_id}' no encontrada para la ciudad '{city_id}'.",
        )
    with open(layer_file, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post(
    "/api/cities/{city_id}/route",
    response_model=RouteResponse,
    tags=["Routing"],
    summary="Calcula ruta ciclista algorítmica y la compara con la ruta más corta",
)
def calculate_city_route(city_id: str, request: RouteRequest):
    engine = get_city_routing_engine(city_id)
    return engine.route(
        origin=request.origin,
        destination=request.destination,
        max_snap_dist_m=request.max_snap_dist_m,
    )

