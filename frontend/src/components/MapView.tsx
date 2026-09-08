import React, { useEffect, useRef } from 'react'
import {
  Map as MapLibreMap,
  NavigationControl,
  Popup,
  type MapLayerMouseEvent,
  type StyleSpecification,
  type GeoJSONSource,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { City, FeatureProperties, LayerConfig, LayerId } from '../types/map'
import type { FeatureCollection } from 'geojson'

interface Props {
  city: City
  isCicloConectaVisible: boolean
  layers: LayerConfig[]
  layersData: Record<LayerId, FeatureCollection | null>
  mapInstanceRef?: React.MutableRefObject<MapLibreMap | null>
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

  useEffect(() => {
    if (!mapContainerRef.current) return

    // Clean base map style using CARTO Voyager
    const style: StyleSpecification = {
      version: 8,
      sources: {
        'carto-voyager': {
          type: 'raster',
          tiles: [
            'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
            'https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
            'https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
          ],
          tileSize: 256,
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attributions">CARTO</a>',
        },
      },
      layers: [
        {
          id: 'carto-voyager-layer',
          type: 'raster',
          source: 'carto-voyager',
          minzoom: 0,
          maxzoom: 20,
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
      if (mapInstanceRef) {
        mapInstanceRef.current = map
      }

      // Initialize GeoJSON sources for each layer
      layers.forEach((layer) => {
        const sourceId = `source-${layer.id}`
        const initialData: FeatureCollection = layersData[layer.id] || {
          type: 'FeatureCollection',
          features: [],
        }

        if (!map.getSource(sourceId)) {
          map.addSource(sourceId, {
            type: 'geojson',
            data: initialData,
          })

          const effectiveVisibility = isCicloConectaVisible && layer.visible ? 'visible' : 'none'

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

            const isDemo =
              Boolean(props.is_demo) ||
              props.status === 'DEMO' ||
              layer.isDemo

            const title = props.name || 'Tramo ciclista'
            const typeStr = props.type || 'Ciclovía'
            const lengthDisplay = props.length_km
              ? `${props.length_km} km (${props.length_m || Math.round(Number(props.length_km) * 1000)} m)`
              : props.gap_length_m
              ? `${props.gap_length_m} m`
              : 'Longitud en cálculo'
            const surface = props.surface || 'Asfalto / Pavimento'
            const sourceText = props.source || 'OpenStreetMap'

            let extraHtml = ''
            if (props.description) {
              extraHtml += `<div class="popup-desc">${props.description}</div>`
            }
            if (props.estimated_benefit) {
              extraHtml += `<div class="popup-desc" style="margin-top:4px;"><strong>Impacto estimado:</strong> ${props.estimated_benefit}</div>`
            }

            const htmlContent = `
              <div class="popup-title">${title}</div>
              <span class="popup-badge ${isDemo ? 'demo' : 'real'}">
                ${isDemo ? 'ESTIMACIÓN DEMO' : 'DATO REAL OSM'}
              </span>
              <div class="popup-row">
                <span class="popup-label">Tipología:</span>
                <span class="popup-value">${typeStr}</span>
              </div>
              <div class="popup-row">
                <span class="popup-label">Superficie:</span>
                <span class="popup-value">${surface}</span>
              </div>
              <div class="popup-row">
                <span class="popup-label">Extensión:</span>
                <span class="popup-value">${lengthDisplay}</span>
              </div>
              <div class="popup-row">
                <span class="popup-label">Fuente:</span>
                <span class="popup-value" style="font-size:0.75rem;">${sourceText}</span>
              </div>
              ${extraHtml}
            `

            popupRef.current = new Popup({ offset: 12 })
              .setLngLat(e.lngLat)
              .setHTML(htmlContent)
              .addTo(map)
          })
        }
      })
    })

    return () => {
      map.remove()
      mapRef.current = null
      if (mapInstanceRef) {
        mapInstanceRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city.center, city.initial_zoom])

  // Update GeoJSON data dynamically
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return

    layers.forEach((layer) => {
      const sourceId = `source-${layer.id}`
      const source = map.getSource(sourceId) as GeoJSONSource | undefined
      const data = layersData[layer.id]
      if (source && data) {
        source.setData(data)
      }
    })
  }, [layersData, layers])

  // Update layer visibility reactively (combining master toggle & sublayer visibility)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) return

    // If master toggle is OFF, hide popups too
    if (!isCicloConectaVisible && popupRef.current) {
      popupRef.current.remove()
    }

    layers.forEach((layer) => {
      const casingLayerId = `casing-${layer.id}`
      const lineLayerId = `line-${layer.id}`
      const visibility = isCicloConectaVisible && layer.visible ? 'visible' : 'none'

      if (map.getLayer(casingLayerId)) {
        map.setLayoutProperty(casingLayerId, 'visibility', visibility)
      }
      if (map.getLayer(lineLayerId)) {
        map.setLayoutProperty(lineLayerId, 'visibility', visibility)
      }
    })
  }, [layers, isCicloConectaVisible])

  return (
    <div
      ref={mapContainerRef}
      className="map-viewport"
      aria-label="Mapa interactivo de Curicó con capas ciclistas"
    />
  )
}
