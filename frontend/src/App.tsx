import { useState, useEffect, useRef, useCallback } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import type { FeatureCollection } from 'geojson'
import type { City, GapCandidateFeature, LayerConfig, LayerId, RouteResponse, RouteSelectionMode } from './types/map'
import { fetchCities, fetchLayerGeoJSON } from './services/api'
import { MapView } from './components/MapView'
import { CityHeader } from './components/CityHeader'
import { LayerControl } from './components/LayerControl'
import { RoutePlanner } from './components/RoutePlanner'
import { OpportunitiesList } from './components/OpportunitiesList'
import { NetworkStatusCard } from './components/NetworkStatusCard'
import { InfoModal } from './components/InfoModal'
import './styles/index.css'

const DEFAULT_LAYERS: LayerConfig[] = [
  {
    id: 'cycling-infrastructure',
    name: 'Ciclovías existentes',
    shortName: 'Existentes',
    description: 'Infraestructura y vías ciclistas mapeadas en OpenStreetMap.',
    color: '#10b981',
    lineWidth: 3.5,
    isDemo: false,
    source: 'OpenStreetMap',
    visible: true,
    count: 0,
  },
  {
    id: 'missing-connections',
    name: 'Conexiones potenciales',
    shortName: 'Brechas',
    description: 'Brechas de continuidad prioritarias detectadas algorítmicamente en la red vial.',
    color: '#f59e0b',
    lineWidth: 3.5,
    lineDash: [4, 2],
    isDemo: false,
    source: 'Detector algorítmico sobre OSM',
    visible: true,
    count: 0,
  },
  {
    id: 'suggested-routes',
    name: 'Rutas sugeridas',
    shortName: 'Sugeridas',
    description: 'Rutas calculadas algorítmicamente priorizando ciclovías y vías de bajo estrés.',
    color: '#3b82f6',
    lineWidth: 3,
    isDemo: false,
    source: 'Algoritmo determinista A* sobre OSM',
    visible: true,
    count: 0,
  },
]

const FALLBACK_CURICO: City = {
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
  description: 'Ciudad intermedia en la Región del Maule, Chile.',
  stats: {
    cycleways_count: 121,
    total_km: 43.2,
    layers_available: [
      'cycling-infrastructure',
      'missing-connections',
      'suggested-routes',
    ],
  },
}

export function App() {
  const [availableCities, setAvailableCities] = useState<City[]>([])
  const [city, setCity] = useState<City>(FALLBACK_CURICO)

  // Master CicloConecta Layer Toggle
  const [isCicloConectaVisible, setIsCicloConectaVisible] = useState(true)

  // Sublayer configurations
  const [layers, setLayers] = useState<LayerConfig[]>(DEFAULT_LAYERS)
  const [layersData, setLayersData] = useState<Record<LayerId, FeatureCollection | null>>({
    'cycling-infrastructure': null,
    'missing-connections': null,
    'suggested-routes': null,
  })
  const [isInfoOpen, setIsInfoOpen] = useState(false)
  const mapInstanceRef = useRef<MapLibreMap | null>(null)

  // Route Planning State
  const [selectionMode, setSelectionMode] = useState<RouteSelectionMode>('none')
  const [origin, setOrigin] = useState<[number, number] | null>(null)
  const [destination, setDestination] = useState<[number, number] | null>(null)
  const [activeRoute, setActiveRoute] = useState<RouteResponse | null>(null)
  const [showShortestComparison, setShowShortestComparison] = useState(false)

  // Gap Opportunities State
  const [selectedGap, setSelectedGap] = useState<GapCandidateFeature | null>(null)

  const loadLayersForCity = useCallback(async (cityId: string) => {
    const layerPromises = DEFAULT_LAYERS.map(async (layer) => {
      try {
        const data = await fetchLayerGeoJSON(cityId, layer.id)
        return { id: layer.id, data, count: data.features.length }
      } catch (err) {
        console.warn(`No se pudo cargar la capa ${layer.id} para ${cityId}:`, err)
        return { id: layer.id, data: null, count: 0 }
      }
    })

    const results = await Promise.all(layerPromises)
    const newLayersData: Record<LayerId, FeatureCollection | null> = {
      'cycling-infrastructure': null,
      'missing-connections': null,
      'suggested-routes': null,
    }

    results.forEach((r) => {
      if (r.data) {
        newLayersData[r.id as LayerId] = r.data
      }
    })

    setLayers((prev) =>
      prev.map((l) => {
        const match = results.find((r) => r.id === l.id)
        return match && match.data ? { ...l, count: match.count } : { ...l, count: 0 }
      })
    )

    setLayersData(newLayersData)
  }, [])

  // Load initial cities list and layers based on URL query param
  useEffect(() => {
    let isMounted = true

    async function loadInitialData() {
      try {
        const cities = await fetchCities()
        if (!isMounted) return

        setAvailableCities(cities)

        const params = new URLSearchParams(window.location.search)
        const queryCityId = params.get('city')

        const selected =
          (queryCityId && cities.find((c) => c.id === queryCityId && c.enabled !== false)) ||
          cities.find((c) => c.id === 'curico') ||
          cities[0] ||
          FALLBACK_CURICO

        setCity(selected)

        // Ensure URL reflects selected city
        if (queryCityId !== selected.id) {
          const url = new URL(window.location.href)
          url.searchParams.set('city', selected.id)
          window.history.replaceState(null, '', url.toString())
        }

        await loadLayersForCity(selected.id)
      } catch (err) {
        console.error('Error cargando datos iniciales:', err)
      }
    }

    loadInitialData()
    return () => {
      isMounted = false
    }
  }, [loadLayersForCity])

  // Handle switching city via dropdown
  const handleCityChange = useCallback(
    async (newCityId: string) => {
      if (newCityId === city.id) return
      const target = availableCities.find((c) => c.id === newCityId)
      if (!target || target.enabled === false) return

      // Clean up previous route and gap state
      setOrigin(null)
      setDestination(null)
      setActiveRoute(null)
      setSelectedGap(null)
      setSelectionMode('none')
      setShowShortestComparison(false)

      // Sync URL without reloading
      const url = new URL(window.location.href)
      url.searchParams.set('city', target.id)
      window.history.pushState(null, '', url.toString())

      // Update active city
      setCity(target)

      // Fetch layers for new city
      await loadLayersForCity(target.id)

      // Camera will fly or adjust
      if (mapInstanceRef.current) {
        mapInstanceRef.current.flyTo({
          center: target.center,
          zoom: target.initial_zoom,
          essential: true,
          pitch: 0,
          bearing: 0,
        })
      }
    },
    [city.id, availableCities, loadLayersForCity]
  )

  // Listen for browser Back/Forward (popstate)
  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search)
      const cityFromUrl = params.get('city')
      if (cityFromUrl && cityFromUrl !== city.id) {
        const target = availableCities.find((c) => c.id === cityFromUrl)
        if (target && target.enabled !== false) {
          handleCityChange(target.id)
        }
      }
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [city.id, availableCities, handleCityChange])

  const handleToggleMaster = () => {
    setIsCicloConectaVisible((prev) => !prev)
  }

  const handleToggleLayer = (layerId: LayerId) => {
    setLayers((prev) =>
      prev.map((layer) =>
        layer.id === layerId ? { ...layer, visible: !layer.visible } : layer
      )
    )
  }

  const handleResetView = () => {
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo({
        center: city.center,
        zoom: city.initial_zoom,
        essential: true,
        pitch: 0,
        bearing: 0,
      })
    }
  }

  const handleSelectCoordinate = (coord: [number, number]) => {
    if (selectionMode === 'origin') {
      setOrigin(coord)
      setSelectionMode('destination')
      if (activeRoute) setActiveRoute(null)
    } else if (selectionMode === 'destination') {
      setDestination(coord)
      setSelectionMode('none')
      if (activeRoute) setActiveRoute(null)
    }
  }

  const gapOpportunities: GapCandidateFeature[] = (
    (layersData['missing-connections']?.features as unknown as GapCandidateFeature[]) || []
  ).filter(
    (f) => f.geometry?.type === 'LineString' && f.properties?.priority_score !== undefined
  )

  const handleEnsureGapsLayerVisible = () => {
    if (!isCicloConectaVisible) setIsCicloConectaVisible(true)
    setLayers((prev) =>
      prev.map((l) => (l.id === 'missing-connections' ? { ...l, visible: true } : l))
    )
  }

  return (
    <main className="app-container">
      <CityHeader
        city={city}
        cities={availableCities}
        onSelectCity={handleCityChange}
        onOpenInfo={() => setIsInfoOpen(true)}
      />

      <RoutePlanner
        cityId={city.id}
        cityName={city.name}
        presets={city.presets}
        selectionMode={selectionMode}
        onSetSelectionMode={setSelectionMode}
        origin={origin}
        destination={destination}
        onSetOrigin={setOrigin}
        onSetDestination={setDestination}
        activeRoute={activeRoute}
        onRouteCalculated={setActiveRoute}
        showShortestComparison={showShortestComparison}
        onToggleShortestComparison={setShowShortestComparison}
      />

      <div className="right-sidebar">
        <LayerControl
          isCicloConectaVisible={isCicloConectaVisible}
          onToggleMaster={handleToggleMaster}
          layers={layers}
          onToggleLayer={handleToggleLayer}
          onResetView={handleResetView}
          cityName={city.name}
        />

        <NetworkStatusCard city={city} />

        <OpportunitiesList
          opportunities={gapOpportunities}
          selectedGap={selectedGap}
          onSelectGap={setSelectedGap}
          isLayerVisible={
            isCicloConectaVisible &&
            (layers.find((l) => l.id === 'missing-connections')?.visible ?? false)
          }
          onEnsureLayerVisible={handleEnsureGapsLayerVisible}
        />
      </div>

      <MapView
        city={city}
        isCicloConectaVisible={isCicloConectaVisible}
        layers={layers}
        layersData={layersData}
        mapInstanceRef={mapInstanceRef}
        selectionMode={selectionMode}
        onSelectCoordinate={handleSelectCoordinate}
        origin={origin}
        destination={destination}
        activeRoute={activeRoute}
        showShortestComparison={showShortestComparison}
        selectedGap={selectedGap}
        onSelectGap={setSelectedGap}
      />

      <InfoModal isOpen={isInfoOpen} onClose={() => setIsInfoOpen(false)} />
    </main>
  )
}

export default App
