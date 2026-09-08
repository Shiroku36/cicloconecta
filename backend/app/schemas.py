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
    center: list[float] = Field(..., description="[longitude, latitude]")
    initial_zoom: float = 13.5
    bounds: Optional[list[list[float]]] = None
    description: Optional[str] = None
    stats: Optional[CityStats] = None


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
