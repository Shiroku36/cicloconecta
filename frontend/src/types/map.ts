export type LayerId = 'cycling-infrastructure' | 'missing-connections' | 'suggested-routes' | 'network-expansion'

export interface CityStats {
  cycleways_count: number
  total_km: number
  layers_available: string[]
  last_updated?: string
}

export interface PresetLocation {
  id?: string
  name: string
  coord: [number, number]
  description?: string
}

export interface CityConnectivity {
  total_cycling_km: number
  total_components: number
  main_component_km: number
  main_component_pct: number
  isolated_components_count: number
  selected_opportunities_count: number
  median_gap_m: number
  max_score: number
  last_analyzed?: string
}

export interface CityExpansion {
  total_phases: number
  total_expansion_km: number
  total_new_nodes: number
  total_coverage_gain_pct: number
  total_new_pois: number
  baseline_coverage?: {
    covered_nodes_pct: number
    covered_pois_pct: number
    distance_bands: Record<string, number>
  }
  last_analyzed?: string
}

export interface City {
  id: string
  name: string
  province?: string
  region: string
  country: string
  enabled?: boolean
  center: [number, number] // [lon, lat]
  initial_zoom: number
  bounds?: [[number, number], [number, number]] // [[west, south], [east, north]]
  description?: string
  presets?: PresetLocation[]
  stats?: CityStats
  connectivity?: CityConnectivity
  expansion?: CityExpansion
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

export interface ExpansionProperties extends FeatureProperties {
  id: string
  phase: number
  name: string
  sector: string
  axis: string
  status: string
  badge: string
  expansion_score: number
  length_m: number
  length_km: number
  crow_m: number
  zigzag_ratio: number
  coverage_gain_nodes: number
  coverage_gain_pct: number
  new_pois_count: number
  efficiency_ratio: number
  streets: string[]
  origin_anchor: string
  target_sector: string
  description: string
  poi_summary: Record<string, string[]>
  disclaimer: string
}

export interface ExpansionFeature {
  type: 'Feature'
  id: string
  geometry: {
    type: 'LineString'
    coordinates: [number, number][]
  }
  properties: ExpansionProperties
}

