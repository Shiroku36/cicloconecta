export type LayerId = 'cycling-infrastructure' | 'missing-connections' | 'suggested-routes'

export interface CityStats {
  cycleways_count: number
  total_km: number
  layers_available: string[]
  last_updated?: string
}

export interface City {
  id: string
  name: string
  province?: string
  region: string
  country: string
  center: [number, number] // [lon, lat]
  initial_zoom: number
  bounds?: [[number, number], [number, number]] // [[west, south], [east, north]]
  description?: string
  stats?: CityStats
}

export interface LayerConfig {
  id: LayerId
  name: string
  shortName: string
  description: string
  color: string
  lineWidth: number
  lineDash?: number[]
  isDemo: boolean
  source: string
  visible: boolean
  count?: number
}

export interface FeatureProperties {
  id?: string
  name?: string
  has_custom_name?: boolean
  type?: string
  category?: string
  surface?: string | null
  surface_display?: string
  highway?: string | null
  length_km?: number
  length_m?: number
  is_demo?: boolean
  status?: string
  priority?: string
  description?: string
  estimated_benefit?: string
  speed_limit_kmh?: number
  source?: string
  source_id?: number | string
  segregated?: string | null
  segregated_display?: string
  oneway?: string | null
  raw_osm_tags?: Record<string, string>
  cycling_infra_pct?: number
  cycling_infra_km?: number
  cost_score?: number
  shortest_distance_km?: number
  shortest_cycling_infra_pct?: number
  distance_diff_km?: number
  length_diff_pct?: number
  cycling_gain_pct?: number
  is_same_path?: boolean
  streets?: string[]
  [key: string]: unknown
}

export interface SnappedPoint {
  requested: [number, number]
  snapped_node: number
  snap_distance_m: number
}

export interface RoutePathDetail {
  distance_km: number
  distance_m: number
  cycling_infra_km: number
  cycling_infra_pct: number
  cost_score: number
  streets: string[]
  coordinates: [number, number][]
}

export interface RouteComparison {
  distance_diff_km: number
  length_diff_pct: number
  cycling_gain_pct: number
  is_same_path: boolean
}

export interface RouteResponse {
  city_id: string
  origin: SnappedPoint
  destination: SnappedPoint
  cycling_route: RoutePathDetail
  shortest_route: RoutePathDetail
  comparison: RouteComparison
  cached?: boolean
}

export type RouteSelectionMode = 'none' | 'origin' | 'destination'

export interface GapProperties extends FeatureProperties {
  rank?: number
  priority_score: number
  gap_length_m: number
  component_a_km: number
  component_b_km: number
  connected_network_km: number
  network_gain_km: number
  gain_ratio: number
  streets: string[]
  streets_display?: string
  disclaimer?: string
}

export interface GapCandidateFeature {
  type: 'Feature'
  id: string
  geometry: {
    type: 'LineString'
    coordinates: [number, number][]
  }
  properties: GapProperties
}

