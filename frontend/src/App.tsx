import { useState, useEffect, useRef } from 'react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import type { FeatureCollection } from 'geojson'
import type { City, LayerConfig, LayerId } from './types/map'
import { fetchCities, fetchLayerGeoJSON } from './services/api'
import { MapView } from './components/MapView'
import { CityHeader } from './components/CityHeader'
import { LayerControl } from './components/LayerControl'
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
    name: 'Conexiones faltantes',
    shortName: 'Gaps',
    description: 'Tramos desconectados prioritarios para unir la red.',
    color: '#f59e0b',
    lineWidth: 3,
    lineDash: [3, 2],
    isDemo: true,
    source: 'DEMO / Conceptual',
    visible: true,
    count: 0,
  },
  {
    id: 'suggested-routes',
    name: 'Rutas sugeridas',
    shortName: 'Sugeridas',
    description: 'Corredores de bajo estrés vehicular para ciclistas.',
    color: '#3b82f6',
    lineWidth: 3,
    isDemo: true,
    source: 'DEMO / Conceptual',
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

        setLayers((prev) =>
          prev.map((l) => {
            const match = results.find((r) => r.id === l.id)
            if (match && match.data) {
              newLayersData[l.id] = match.data
              return { ...l, count: match.count }
            }
            return l
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

  return (
    <main className="app-container">
      <CityHeader city={city} onOpenInfo={() => setIsInfoOpen(true)} />

      <LayerControl
        isCicloConectaVisible={isCicloConectaVisible}
        onToggleMaster={handleToggleMaster}
        layers={layers}
        onToggleLayer={handleToggleLayer}
        onResetView={handleResetView}
      />

      <MapView
        city={city}
        isCicloConectaVisible={isCicloConectaVisible}
        layers={layers}
        layersData={layersData}
        mapInstanceRef={mapInstanceRef}
      />

      <InfoModal isOpen={isInfoOpen} onClose={() => setIsInfoOpen(false)} />
    </main>
  )
}

export default App
