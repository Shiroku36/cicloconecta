import React, { useEffect, useRef } from 'react'
import {
  Map as MapLibreMap,
  Marker,
  LngLatBounds,
  NavigationControl,
  Popup,
  setWorkerUrl,
  type MapLayerMouseEvent,
  type StyleSpecification,
  type GeoJSONSource,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import type {
  City,
  FeatureProperties,
  GapCandidateFeature,
  GapProperties,
  LayerConfig,
  LayerId,
  RouteResponse,
  RouteSelectionMode,
} from '../types/map'
import type { FeatureCollection } from 'geojson'

// Explicitly register MapLibre Web Worker URL to prevent Vite 404 in .vite/deps
setWorkerUrl(maplibreWorkerUrl)

interface Props {
  city: City
  isCicloConectaVisible: boolean
  layers: LayerConfig[]
  layersData: Record<LayerId, FeatureCollection | null>
  mapInstanceRef?: React.MutableRefObject<MapLibreMap | null>
  selectionMode?: RouteSelectionMode
  onSelectCoordinate?: (coord: [number, number]) => void
  origin?: [number, number] | null
  destination?: [number, number] | null
  activeRoute?: RouteResponse | null
  showShortestComparison?: boolean
  selectedGap?: GapCandidateFeature | null
  onSelectGap?: (gap: GapCandidateFeature | null) => void
}

const EMPTY_FEATURE_COLLECTION: FeatureCollection = {
  type: 'FeatureCollection',
  features: [],
}

function createPinElement(label: string, bgColor: string): HTMLElement {
  const el = document.createElement('div')
  el.className = 'route-map-pin'
  el.style.backgroundColor = bgColor
  el.style.color = '#ffffff'
  el.style.width = '30px'
  el.style.height = '30px'
  el.style.borderRadius = '50%'
  el.style.display = 'flex'
  el.style.alignItems = 'center'
  el.style.justifyContent = 'center'
  el.style.fontWeight = '800'
  el.style.fontSize = '14px'
  el.style.boxShadow = '0 2px 8px rgba(0,0,0,0.45)'
  el.style.border = '2.5px solid white'
  el.style.cursor = 'pointer'
  el.textContent = label
  return el
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
  const isAlgorithmicRoute =
    props.cycling_infra_pct !== undefined ||
    props.status === 'Ruta algorítmica calculada con red vial real'
  const isAlgorithmicGap =
    props.status === 'ALGORITHMIC_CANDIDATE' ||
    props.priority_score !== undefined

  // Title
  const titleEl = document.createElement('div')
  titleEl.className = 'popup-title'
  titleEl.textContent = props.name || 'Vía ciclista'
  container.appendChild(titleEl)

  // Badge
  const badgeEl = document.createElement('span')
  if (isAlgorithmicRoute) {
    badgeEl.className = 'popup-badge route'
    badgeEl.textContent = 'RUTA RECOMENDADA ALGORÍTMICA'
  } else if (isAlgorithmicGap) {
    badgeEl.className = 'popup-badge gap'
    badgeEl.textContent = 'OPORTUNIDAD ALGORÍTMICA'
  } else {
    badgeEl.className = `popup-badge ${isDemo ? 'demo' : 'real'}`
    badgeEl.textContent = isDemo ? 'ESTIMACIÓN DEMO' : 'DATOS OPENSTREETMAP'
  }
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

  if (isAlgorithmicRoute) {
    if (props.origin_name && props.dest_name) {
      addRow('Trayecto:', `${props.origin_name} → ${props.dest_name}`)
    }
    if (props.distance_km !== undefined) {
      addRow('Distancia total:', `${props.distance_km} km`)
    }
    if (props.cycling_infra_pct !== undefined) {
      addRow('Infraestructura ciclista:', `${props.cycling_infra_pct}% (${props.cycling_infra_km} km)`)
    }
    if (props.shortest_distance_km !== undefined) {
      addRow(
        'Ruta más corta vehicular:',
        `${props.shortest_distance_km} km (${props.shortest_cycling_infra_pct}% ciclovía)`
      )
    }
    if (props.cycling_gain_pct !== undefined && Number(props.cycling_gain_pct) > 0) {
      addRow(
        'Ganancia ciclista:',
        `+${props.cycling_gain_pct}% más ciclovía (+${props.distance_diff_km} km)`
      )
    }
    if (props.streets && Array.isArray(props.streets) && props.streets.length > 0) {
      addRow('Calles del trayecto:', props.streets.slice(0, 5).join(', '))
    }
  } else if (isAlgorithmicGap) {
    if (props.gap_length_m !== undefined) {
      addRow('Brecha a conectar:', `${props.gap_length_m} m`)
    }
    if (props.connected_network_km !== undefined) {
      const parts =
        props.component_a_km !== undefined && props.component_b_km !== undefined
          ? ` (${props.component_a_km} km + ${props.component_b_km} km)`
          : ''
      addRow('Red ciclista unida:', `${props.connected_network_km} km${parts}`)
    }
    if (props.priority_score !== undefined) {
      const gainText = props.gain_ratio ? ` (ganancia ${props.gain_ratio}x)` : ''
      addRow('Prioridad calculada:', `${props.priority_score} / 100${gainText}`)
    }
    const streetsVal = props.streets_display || (Array.isArray(props.streets) ? props.streets.join(', ') : null)
    if (streetsVal) {
      addRow('Calles a intervenir:', String(streetsVal))
    }
    addRow('Fuente:', 'Detector algorítmico CicloConecta sobre OSM')
  } else {
    // Tipología
    const typeStr = props.type || 'Infraestructura ciclista'
    addRow('Tipología:', typeStr)

    // Superficie
    const surfaceStr = props.surface_display || props.surface || 'Sin información'
    addRow('Superficie:', surfaceStr)

    // Segregación
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
  }

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

  // Disclaimer prudente para brechas algorítmicas
  if (props.disclaimer) {
    const discEl = document.createElement('div')
    discEl.className = 'popup-disclaimer'
    discEl.textContent = String(props.disclaimer)
    container.appendChild(discEl)
  }

  return container
}

export const MapView: React.FC<Props> = ({
  city,
  isCicloConectaVisible,
  layers,
  layersData,
  mapInstanceRef,
  selectionMode = 'none',
  onSelectCoordinate,
  origin,
  destination,
  activeRoute,
  showShortestComparison = false,
  selectedGap = null,
  onSelectGap,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const popupRef = useRef<Popup | null>(null)

  const originMarkerRef = useRef<Marker | null>(null)
  const destMarkerRef = useRef<Marker | null>(null)

  const layersDataRef = useRef(layersData)
  layersDataRef.current = layersData

  const layersRef = useRef(layers)
  layersRef.current = layers

  const isCicloConectaVisibleRef = useRef(isCicloConectaVisible)
  isCicloConectaVisibleRef.current = isCicloConectaVisible

  const selectionModeRef = useRef(selectionMode)
  selectionModeRef.current = selectionMode

  const onSelectCoordinateRef = useRef(onSelectCoordinate)
  onSelectCoordinateRef.current = onSelectCoordinate

  const selectedGapRef = useRef(selectedGap)
  selectedGapRef.current = selectedGap

  const onSelectGapRef = useRef(onSelectGap)
  onSelectGapRef.current = onSelectGap

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

  // Update active route layers
  const syncActiveRouteLayers = (map: MapLibreMap) => {
    if (!map || !isLayersInitializedRef.current) return

    const routeSource = map.getSource('source-active-route') as GeoJSONSource | undefined
    if (routeSource) {
      if (activeRoute) {
        routeSource.setData({
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              properties: { type: 'cycling_route' },
              geometry: {
                type: 'LineString',
                coordinates: activeRoute.cycling_route.coordinates,
              },
            },
          ],
        })
      } else {
        routeSource.setData(EMPTY_FEATURE_COLLECTION)
      }
    }

    const shortestSource = map.getSource('source-active-shortest-route') as GeoJSONSource | undefined
    if (shortestSource) {
      if (activeRoute && showShortestComparison) {
        shortestSource.setData({
          type: 'FeatureCollection',
          features: [
            {
              type: 'Feature',
              properties: { type: 'shortest_route' },
              geometry: {
                type: 'LineString',
                coordinates: activeRoute.shortest_route.coordinates,
              },
            },
          ],
        })
      } else {
        shortestSource.setData(EMPTY_FEATURE_COLLECTION)
      }
    }
  }

  // Update selected gap highlight layer
  const syncSelectedGapLayer = (map: MapLibreMap) => {
    if (!map || !isLayersInitializedRef.current) return

    const gapSource = map.getSource('source-selected-gap') as GeoJSONSource | undefined
    if (gapSource) {
      if (selectedGapRef.current && selectedGapRef.current.geometry?.coordinates?.length > 1) {
        gapSource.setData({
          type: 'FeatureCollection',
          features: [selectedGapRef.current],
        })
      } else {
        gapSource.setData(EMPTY_FEATURE_COLLECTION)
      }
    }
  }

  useEffect(() => {
    if (!mapContainerRef.current) return

    const style: StyleSpecification = {
      version: 8,
      sources: {
        'osm-tiles': {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
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
      ;(
        window as unknown as {
          cicloOpenPopup?: (
            props: FeatureProperties,
            lngLat: [number, number],
            isDemo?: boolean
          ) => void
        }
      ).cicloOpenPopup = (props, lngLat, isDemo = false) => {
        if (popupRef.current) popupRef.current.remove()
        const popupContent = createSafePopupContent(props, isDemo)
        popupRef.current = new Popup({ offset: 12 })
          .setLngLat(lngLat)
          .setDOMContent(popupContent)
          .addTo(map)
      }
      if (mapInstanceRef) {
        mapInstanceRef.current = map
      }

      // Initialize base GeoJSON layers
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

          // Casing Layer
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

          const lineLayerId = `line-${layer.id}`

          map.on('mouseenter', lineLayerId, () => {
            if (selectionModeRef.current === 'none') {
              map.getCanvas().style.cursor = 'pointer'
            }
          })

          map.on('mouseleave', lineLayerId, () => {
            if (selectionModeRef.current === 'none') {
              map.getCanvas().style.cursor = ''
            }
          })

          map.on('click', lineLayerId, (e: MapLayerMouseEvent) => {
            // Ignore layer popups if user is selecting origin/destination
            if (selectionModeRef.current !== 'none') return
            if (!e.features || e.features.length === 0) return

            const feature = e.features[0]
            const props = (feature.properties || {}) as FeatureProperties

            if (popupRef.current) {
              popupRef.current.remove()
            }

            const popupContent = createSafePopupContent(props, layer.isDemo)
            popupRef.current = new Popup({ offset: 12 })
              .setLngLat(e.lngLat)
              .setDOMContent(popupContent)
              .addTo(map)

            if (
              layer.id === 'missing-connections' &&
              props.status === 'ALGORITHMIC_CANDIDATE' &&
              onSelectGapRef.current
            ) {
              onSelectGapRef.current({
                type: 'Feature',
                id: String(props.id || feature.id || ''),
                geometry: feature.geometry as { type: 'LineString'; coordinates: [number, number][] },
                properties: props as unknown as GapProperties,
              })
            }
          })
        }
      })

      // Initialize sources and layers for calculated active routes
      if (!map.getSource('source-active-route')) {
        map.addSource('source-active-route', {
          type: 'geojson',
          data: EMPTY_FEATURE_COLLECTION,
        })
        map.addLayer({
          id: 'casing-active-route',
          type: 'line',
          source: 'source-active-route',
          layout: {
            'line-cap': 'round',
            'line-join': 'round',
          },
          paint: {
            'line-color': '#1d4ed8',
            'line-opacity': 0.4,
            'line-width': 10,
          },
        })
        map.addLayer({
          id: 'line-active-route',
          type: 'line',
          source: 'source-active-route',
          layout: {
            'line-cap': 'round',
            'line-join': 'round',
          },
          paint: {
            'line-color': '#2563eb',
            'line-opacity': 1.0,
            'line-width': 5.5,
          },
        })
      }

      if (!map.getSource('source-active-shortest-route')) {
        map.addSource('source-active-shortest-route', {
          type: 'geojson',
          data: EMPTY_FEATURE_COLLECTION,
        })
        map.addLayer({
          id: 'line-active-shortest-route',
          type: 'line',
          source: 'source-active-shortest-route',
          layout: {
            'line-cap': 'round',
            'line-join': 'round',
          },
          paint: {
            'line-color': '#ea580c',
            'line-width': 4.0,
            'line-dasharray': [2.5, 2.5],
            'line-opacity': 0.95,
          },
        })
      }

      // Initialize sources and layers for highlighted selected gap
      if (!map.getSource('source-selected-gap')) {
        map.addSource('source-selected-gap', {
          type: 'geojson',
          data: EMPTY_FEATURE_COLLECTION,
        })
        map.addLayer({
          id: 'casing-selected-gap',
          type: 'line',
          source: 'source-selected-gap',
          layout: {
            'line-cap': 'round',
            'line-join': 'round',
          },
          paint: {
            'line-color': '#f59e0b',
            'line-opacity': 0.5,
            'line-width': 12,
          },
        })
        map.addLayer({
          id: 'line-selected-gap',
          type: 'line',
          source: 'source-selected-gap',
          layout: {
            'line-cap': 'round',
            'line-join': 'round',
          },
          paint: {
            'line-color': '#b45309',
            'line-opacity': 1.0,
            'line-width': 6.0,
            'line-dasharray': [3, 1.5],
          },
        })
      }

      // Map canvas click for picking coordinates
      map.on('click', (e: MapLayerMouseEvent) => {
        if (selectionModeRef.current !== 'none' && onSelectCoordinateRef.current) {
          onSelectCoordinateRef.current([e.lngLat.lng, e.lngLat.lat])
        }
      })

      isLayersInitializedRef.current = true
      syncMapLayers(map)
      syncActiveRouteLayers(map)
      syncSelectedGapLayer(map)
    })

    return () => {
      isLayersInitializedRef.current = false
      if (originMarkerRef.current) originMarkerRef.current.remove()
      if (destMarkerRef.current) destMarkerRef.current.remove()
      map.remove()
      mapRef.current = null
      if (mapInstanceRef) {
        mapInstanceRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city.id])

  // Sync layersData or visibility changes
  useEffect(() => {
    const map = mapRef.current
    if (map && isLayersInitializedRef.current) {
      syncMapLayers(map)
    }
  }, [layersData, layers, isCicloConectaVisible])

  // Sync active route and comparison
  useEffect(() => {
    const map = mapRef.current
    if (map && isLayersInitializedRef.current) {
      syncActiveRouteLayers(map)
      if (activeRoute && activeRoute.cycling_route.coordinates.length > 1) {
        const bounds = new LngLatBounds()
        activeRoute.cycling_route.coordinates.forEach((c) => bounds.extend(c))
        map.fitBounds(bounds, { padding: 80, maxZoom: 16 })
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRoute, showShortestComparison])

  // Sync selected gap highlight and focus
  useEffect(() => {
    const map = mapRef.current
    if (!map || !isLayersInitializedRef.current) return

    syncSelectedGapLayer(map)

    if (selectedGap && selectedGap.geometry?.coordinates?.length > 1) {
      const coords = selectedGap.geometry.coordinates
      const bounds = new LngLatBounds()
      coords.forEach((c) => bounds.extend(c))
      map.fitBounds(bounds, { padding: 120, maxZoom: 16.5 })

      const midCoord = coords[Math.floor(coords.length / 2)]
      if (popupRef.current) popupRef.current.remove()
      const popupContent = createSafePopupContent(selectedGap.properties, false)
      popupRef.current = new Popup({ offset: 12 })
        .setLngLat(midCoord)
        .setDOMContent(popupContent)
        .addTo(map)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedGap])

  // Sync cursor when in selection mode
  useEffect(() => {
    const map = mapRef.current
    if (map) {
      map.getCanvas().style.cursor = selectionMode !== 'none' ? 'crosshair' : ''
    }
  }, [selectionMode])

  // Sync origin pin marker
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    if (origin) {
      if (!originMarkerRef.current) {
        originMarkerRef.current = new Marker({
          element: createPinElement('A', '#10b981'),
        })
          .setLngLat(origin)
          .addTo(map)
      } else {
        originMarkerRef.current.setLngLat(origin)
      }
    } else if (originMarkerRef.current) {
      originMarkerRef.current.remove()
      originMarkerRef.current = null
    }
  }, [origin])

  // Sync destination pin marker
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    if (destination) {
      if (!destMarkerRef.current) {
        destMarkerRef.current = new Marker({
          element: createPinElement('B', '#ef4444'),
        })
          .setLngLat(destination)
          .addTo(map)
      } else {
        destMarkerRef.current.setLngLat(destination)
      }
    } else if (destMarkerRef.current) {
      destMarkerRef.current.remove()
      destMarkerRef.current = null
    }
  }, [destination])

  return (
    <div
      ref={mapContainerRef}
      className="map-viewport"
      aria-label="Mapa interactivo de Curicó con capas ciclistas"
    />
  )
}
