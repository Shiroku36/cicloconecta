import React, { useEffect, useRef } from 'react'
import {
  Map as MapLibreMap,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type MapLayerMouseEvent,
  type StyleSpecification,
  type GeoJSONSource,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import type { City, FeatureProperties, LayerConfig, LayerId } from '../types/map'

// Explicitly register MapLibre Web Worker URL to prevent Vite 404 in .vite/deps
setWorkerUrl(maplibreWorkerUrl)
import type { FeatureCollection } from 'geojson'

interface Props {
  city: City
  isCicloConectaVisible: boolean
  layers: LayerConfig[]
  layersData: Record<LayerId, FeatureCollection | null>
  mapInstanceRef?: React.MutableRefObject<MapLibreMap | null>
}

const EMPTY_FEATURE_COLLECTION: FeatureCollection = {
  type: 'FeatureCollection',
  features: [],
}

/**
 * Creates safe DOM content for MapLibre popups without HTML string interpolation.
 * Prevents XSS and safely renders attributes from OSM or demo layers.
 */
function createSafePopupContent(
  props: FeatureProperties,
  isDemoLayer: boolean
): HTMLElement {
  const container = document.createElement('div')
  container.className = 'cicloconecta-popup-content'

  const isDemo =
    Boolean(props.is_demo) || props.status === 'DEMO' || isDemoLayer

  // Title
  const titleEl = document.createElement('div')
  titleEl.className = 'popup-title'
  titleEl.textContent = props.name || 'Vía ciclista'
  container.appendChild(titleEl)

  // Badge
  const badgeEl = document.createElement('span')
  badgeEl.className = `popup-badge ${isDemo ? 'demo' : 'real'}`
  badgeEl.textContent = isDemo ? 'ESTIMACIÓN DEMO' : 'DATOS OPENSTREETMAP'
  container.appendChild(badgeEl)

  const addRow = (label: string, value: string) => {
    const row = document.createElement('div')
    row.className = 'popup-row'

    const labelSpan = document.createElement('span')
    labelSpan.className = 'popup-label'
    labelSpan.textContent = label

    const valSpan = document.createElement('span')
    valSpan.className = 'popup-value'
    valSpan.textContent = value

    row.appendChild(labelSpan)
    row.appendChild(valSpan)
    container.appendChild(row)
  }

  // Tipología
  const typeStr = props.type || 'Infraestructura ciclista'
  addRow('Tipología:', typeStr)

  // Superficie (transparent: shows Sin información if not tagged in OSM)
  const surfaceStr = props.surface_display || props.surface || 'Sin información'
  addRow('Superficie:', surfaceStr)

  // Segregación (if present in tags)
  if (props.segregated_display && props.segregated_display !== 'Sin información') {
    addRow('Segregación:', props.segregated_display)
  }

  // Extensión
  const lengthDisplay = props.length_km
    ? `${props.length_km} km (${props.length_m || Math.round(Number(props.length_km) * 1000)} m)`
    : props.gap_length_m
    ? `${props.gap_length_m} m`
    : 'Longitud en cálculo'
  addRow('Extensión:', lengthDisplay)

  // Fuente
  const sourceText = props.source || 'OpenStreetMap Contributors'
  addRow('Fuente:', sourceText)

  // Descripción opcional
  if (props.description) {
    const descEl = document.createElement('div')
    descEl.className = 'popup-desc'
    descEl.textContent = props.description
    container.appendChild(descEl)
  }

  // Beneficio estimado opcional
  if (props.estimated_benefit) {
    const benefitEl = document.createElement('div')
    benefitEl.className = 'popup-desc'
    benefitEl.style.marginTop = '4px'

    const strong = document.createElement('strong')
    strong.textContent = 'Impacto estimado: '
    benefitEl.appendChild(strong)

    const benefitText = document.createTextNode(props.estimated_benefit)
    benefitEl.appendChild(benefitText)

    container.appendChild(benefitEl)
  }

  return container
}

export const MapView: React.FC<Props> = ({
  city,
  isCicloConectaVisible,
  layers,
  layersData,
  mapInstanceRef,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const popupRef = useRef<Popup | null>(null)

  // Keep references always up-to-date to eliminate race conditions between data fetching and map loading
  const layersDataRef = useRef(layersData)
  layersDataRef.current = layersData

  const layersRef = useRef(layers)
  layersRef.current = layers

  const isCicloConectaVisibleRef = useRef(isCicloConectaVisible)
  isCicloConectaVisibleRef.current = isCicloConectaVisible

  const isLayersInitializedRef = useRef(false)

  // Synchronizes GeoJSON data and layer visibility into the map safely
  const syncMapLayers = (map: MapLibreMap) => {
    if (!map || !isLayersInitializedRef.current) return

    const currentData = layersDataRef.current
    const currentLayers = layersRef.current
    const masterVisible = isCicloConectaVisibleRef.current

    if (!masterVisible && popupRef.current) {
      popupRef.current.remove()
    }

    currentLayers.forEach((layer) => {
      const sourceId = `source-${layer.id}`
      const source = map.getSource(sourceId) as GeoJSONSource | undefined
      const data = currentData[layer.id]

      if (source && data) {
        source.setData(data)
      }

      const casingLayerId = `casing-${layer.id}`
      const lineLayerId = `line-${layer.id}`
      const visibility = masterVisible && layer.visible ? 'visible' : 'none'

      if (map.getLayer(casingLayerId)) {
        map.setLayoutProperty(casingLayerId, 'visibility', visibility)
      }
      if (map.getLayer(lineLayerId)) {
        map.setLayoutProperty(lineLayerId, 'visibility', visibility)
      }
    })
  }

  useEffect(() => {
    if (!mapContainerRef.current) return

    // Clean base map style using OpenStreetMap standard tiles (100% open, zero API keys or watermarks)
    const style: StyleSpecification = {
      version: 8,
      sources: {
        'osm-tiles': {
          type: 'raster',
          tiles: [
            'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          ],
          tileSize: 256,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        },
      },
      layers: [
        {
          id: 'osm-tiles-layer',
          type: 'raster',
          source: 'osm-tiles',
          minzoom: 0,
          maxzoom: 19,
        },
      ],
    }

    const map = new MapLibreMap({
      container: mapContainerRef.current,
      style,
      center: city.center,
      zoom: city.initial_zoom,
      minZoom: 10,
      maxZoom: 19,
    })

    map.addControl(new NavigationControl({ showCompass: true }), 'bottom-right')

    map.on('load', () => {
      mapRef.current = map
      ;(window as unknown as { cicloMap: MapLibreMap }).cicloMap = map
      if (mapInstanceRef) {
        mapInstanceRef.current = map
      }

      // Initialize GeoJSON sources for each layer using the freshest data from ref
      layersRef.current.forEach((layer) => {
        const sourceId = `source-${layer.id}`
        const initialData =
          layersDataRef.current[layer.id] || EMPTY_FEATURE_COLLECTION

        if (!map.getSource(sourceId)) {
          map.addSource(sourceId, {
            type: 'geojson',
            data: initialData,
          })

          const effectiveVisibility =
            isCicloConectaVisibleRef.current && layer.visible
              ? 'visible'
              : 'none'

          // Glow / Casing Layer (for high contrast over roads)
          map.addLayer({
            id: `casing-${layer.id}`,
            type: 'line',
            source: sourceId,
            layout: {
              'line-cap': 'round',
              'line-join': 'round',
              visibility: effectiveVisibility,
            },
            paint: {
              'line-color': layer.color,
              'line-opacity': 0.25,
              'line-width': layer.lineWidth + 4,
            },
          })

          // Main Line Layer
          const linePaint: Record<string, unknown> = {
            'line-color': layer.color,
            'line-width': layer.lineWidth,
            'line-opacity': 0.95,
          }

          const lineLayout: Record<string, unknown> = {
            'line-cap': 'round',
            'line-join': 'round',
            visibility: effectiveVisibility,
          }

          if (layer.lineDash && layer.lineDash.length > 0) {
            linePaint['line-dasharray'] = layer.lineDash
          }

          map.addLayer({
            id: `line-${layer.id}`,
            type: 'line',
            source: sourceId,
            layout: lineLayout,
            paint: linePaint,
          })

          // Interactive click and hover events
          const lineLayerId = `line-${layer.id}`

          map.on('mouseenter', lineLayerId, () => {
            map.getCanvas().style.cursor = 'pointer'
          })

          map.on('mouseleave', lineLayerId, () => {
            map.getCanvas().style.cursor = ''
          })

          map.on('click', lineLayerId, (e: MapLayerMouseEvent) => {
            if (!e.features || e.features.length === 0) return
            const feature = e.features[0]
            const props = (feature.properties || {}) as FeatureProperties

            if (popupRef.current) {
              popupRef.current.remove()
            }

            // Secure popup generation using DOM nodes and textContent
            const popupContent = createSafePopupContent(props, layer.isDemo)

            popupRef.current = new Popup({ offset: 12 })
              .setLngLat(e.lngLat)
              .setDOMContent(popupContent)
              .addTo(map)
          })
        }
      })

      isLayersInitializedRef.current = true

      // Immediate sync to ensure any data loaded before or during style load is set
      syncMapLayers(map)
    })

    return () => {
      isLayersInitializedRef.current = false
      map.remove()
      mapRef.current = null
      if (mapInstanceRef) {
        mapInstanceRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city.id])

  // Reactively sync data or layer visibility changes whenever layersData, layers or master toggle changes
  useEffect(() => {
    const map = mapRef.current
    if (map && isLayersInitializedRef.current) {
      syncMapLayers(map)
    }
  }, [layersData, layers, isCicloConectaVisible])

  return (
    <div
      ref={mapContainerRef}
      className="map-viewport"
      aria-label="Mapa interactivo de Curicó con capas ciclistas"
    />
  )
}
