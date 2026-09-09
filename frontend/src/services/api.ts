import type { City, LayerId, RouteResponse } from '../types/map'
import type { FeatureCollection } from 'geojson'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

export async function fetchCities(): Promise<City[]> {
  try {
    const res = await fetch(`${API_BASE}/cities`)
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // Backend API unavailable, fallback to static Curicó metadata
  }

  // Static registry fallback
  try {
    const regRes = await fetch('/data/cities/registry.json')
    if (regRes.ok) {
      const regData = await regRes.json()
      if (Array.isArray(regData.cities)) {
        return regData.cities
      }
    }
  } catch (err) {
    console.warn('Error fetching static registry:', err)
  }

  // Static single city fallback
  try {
    const fallbackRes = await fetch('/data/cities/curico/city.json')
    if (fallbackRes.ok) {
      const curico = await fallbackRes.json()
      return [curico]
    }
  } catch (err) {
    console.error('Error fetching fallback city:', err)
  }

  // Hardcoded emergency fallback for Curicó
  return [
    {
      id: 'curico',
      name: 'Curicó',
      province: 'Curicó',
      region: 'Región del Maule',
      country: 'Chile',
      center: [-71.2394, -34.9854],
      initial_zoom: 13.5,
      bounds: [
        [-71.3, -35.05],
        [-71.18, -34.93],
      ],
      description: 'Ciudad intermedia en la Región del Maule.',
      stats: {
        cycleways_count: 121,
        total_km: 43.2,
        layers_available: ['cycling-infrastructure', 'missing-connections', 'suggested-routes'],
      },
    },
  ]
}

export async function fetchCity(cityId: string): Promise<City> {
  try {
    const res = await fetch(`${API_BASE}/cities/${cityId}`)
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // Try static
  }

  const staticRes = await fetch(`/data/cities/${cityId}/city.json`)
  if (!staticRes.ok) {
    throw new Error(`No se pudo cargar la ciudad ${cityId}`)
  }
  return await staticRes.json()
}

export async function fetchLayerGeoJSON(
  cityId: string,
  layerId: LayerId
): Promise<FeatureCollection> {
  try {
    const res = await fetch(`${API_BASE}/cities/${cityId}/layers/${layerId}`)
    if (res.ok) {
      return await res.json()
    }
  } catch {
    // Try static
  }

  const staticRes = await fetch(`/data/cities/${cityId}/${layerId}.geojson`)
  if (!staticRes.ok) {
    throw new Error(`Error cargando la capa ${layerId} para ${cityId}`)
  }
  return await staticRes.json()
}

export async function calculateRoute(
  cityId: string,
  origin: [number, number],
  destination: [number, number],
  maxSnapDistM = 600
): Promise<RouteResponse> {
  const res = await fetch(`${API_BASE}/cities/${cityId}/route`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      origin,
      destination,
      max_snap_dist_m: maxSnapDistM,
    }),
  })

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(errorData.detail || `Error al calcular ruta (${res.status})`)
  }

  return (await res.json()) as RouteResponse
}

