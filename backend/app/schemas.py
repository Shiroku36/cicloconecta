from typing import Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str


class CityStats(BaseModel):
    cycleways_count: int
    total_km: float
    layers_available: list[str]
    last_updated: Optional[str] = None


class CitySummary(BaseModel):
    id: str
    name: str
    province: Optional[str] = None
    region: str
    country: str = "Chile"
    enabled: bool = True
    center: list[float] = Field(..., description="[longitude, latitude]")
    initial_zoom: float = 13.5
    bounds: Optional[list[list[float]]] = None
    description: Optional[str] = None
    presets: list[dict[str, Any]] = []
    stats: Optional[CityStats] = None
    connectivity: Optional[dict[str, Any]] = None


class LayerInfo(BaseModel):
    id: str
    name: str
    description: str
    type: str = "line"
    color: str
    is_demo: bool = False
    source: str
    feature_count: int = 0


class CityDetail(CitySummary):
    available_layers: list[LayerInfo] = []


class GeoJSONResponse(BaseModel):
    type: str = "FeatureCollection"
    name: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    features: list[dict[str, Any]]


class RouteRequest(BaseModel):
    origin: list[float] = Field(..., min_length=2, max_length=2, description="[lon, lat]")
    destination: list[float] = Field(..., min_length=2, max_length=2, description="[lon, lat]")
    max_snap_dist_m: float = Field(500.0, description="Distancia máxima de ajuste al grafo en metros")
    profile: str = Field("balanced", description="Perfil de enrutamiento ciclista: direct, balanced, max_cycleway")


class SnappedPoint(BaseModel):
    requested: list[float]
    snapped_node: int
    snap_distance_m: float


class RoutePathDetail(BaseModel):
    distance_km: float
    distance_m: float
    cycling_infra_km: float
    cycling_infra_pct: float
    cost_score: float
    streets: list[str] = []
    coordinates: list[list[float]]


class RouteComparison(BaseModel):
    distance_diff_km: float
    length_diff_pct: float
    cycling_gain_pct: float
    is_same_path: bool


class RouteResponse(BaseModel):
    city_id: str
    origin: SnappedPoint
    destination: SnappedPoint
    cycling_route: RoutePathDetail
    shortest_route: RoutePathDetail
    comparison: RouteComparison
    cached: bool = False

