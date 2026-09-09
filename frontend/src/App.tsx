import { useState, useEffect, useRef } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import type { FeatureCollection } from 'geojson'
import type { City, GapCandidateFeature, LayerConfig, LayerId, RouteResponse, RouteSelectionMode } from './types/map'
import { fetchCities, fetchLayerGeoJSON } from './services/api'
import { MapView } from './components/MapView'
import { CityHeader } from './components/CityHeader'
import { LayerControl } from './components/LayerControl'
import { RoutePlanner } from './components/RoutePlanner'
import { OpportunitiesList } from './components/OpportunitiesList'
import { InfoModal } from './components/InfoModal'
import './styles/index.css'

const DEFAULT_LAYERS: LayerConfig[] = [
  {
    id: 'cycling-infrastructure',
    name: 'Ciclovías existentes',
    shortName: 'Existentes',
    description: 'Infraestructura ciclista formal mapeada en OpenStreetMap.',
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

export function App() {
  const [city, setCity] = useState<City>({
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
  })

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

  // Load initial city and layer data
  useEffect(() => {
    let isMounted = true

    async function loadInitialData() {
      try {
        const cities = await fetchCities()
        const curico = cities.find((c) => c.id === 'curico') || cities[0]
        if (curico && isMounted) {
          setCity(curico)
        }

        // Fetch each layer GeoJSON
        const targetCityId = curico ? curico.id : 'curico'
        const layerPromises = DEFAULT_LAYERS.map(async (layer) => {
          try {
            const data = await fetchLayerGeoJSON(targetCityId, layer.id)
            return { id: layer.id, data, count: data.features.length }
          } catch (err) {
            console.warn(`No se pudo cargar la capa ${layer.id}:`, err)
            return { id: layer.id, data: null, count: 0 }
          }
        })

        const results = await Promise.all(layerPromises)
        if (!isMounted) return

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
            return match && match.data ? { ...l, count: match.count } : l
          })
        )

        setLayersData(newLayersData)
      } catch (err) {
        console.error('Error cargando datos iniciales:', err)
      }
    }

    loadInitialData()
    return () => {
      isMounted = false
    }
  }, [])

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

  // Gap Opportunities State
  const [selectedGap, setSelectedGap] = useState<GapCandidateFeature | null>(null)

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
      <CityHeader city={city} onOpenInfo={() => setIsInfoOpen(true)} />

      <RoutePlanner
        cityId={city.id}
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
        />

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
