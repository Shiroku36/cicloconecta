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
  type?: string
  surface?: string
  highway?: string
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
  segregated?: string
  oneway?: string
  [key: string]: unknown
}
