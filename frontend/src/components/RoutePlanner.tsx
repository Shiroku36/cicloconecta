import React, { useState } from 'react'
import type { RouteResponse, RouteSelectionMode } from '../types/map'
import { calculateRoute } from '../services/api'

interface PresetLocation {
  name: string
  coord: [number, number]
}

const CURICO_PRESETS: PresetLocation[] = [
  { name: 'Plaza de Armas', coord: [-71.2394, -34.9854] },
  { name: 'Rauquén (Norte)', coord: [-71.2185, -34.9620] },
  { name: 'Zapallar / El Boldo (Oriente)', coord: [-71.2120, -34.9815] },
  { name: 'Santa Fe (Poniente)', coord: [-71.2580, -34.9880] },
  { name: 'Campus UTalca (Los Niches)', coord: [-71.2290, -35.0030] },
  { name: 'Guaiquillo (Sur)', coord: [-71.2460, -34.9980] },
  { name: 'Estación de Trenes', coord: [-71.2340, -34.9785] },
]

interface Props {
  cityId: string
  cityName?: string
  presets?: PresetLocation[]
  selectionMode: RouteSelectionMode
  onSetSelectionMode: (mode: RouteSelectionMode) => void
  origin: [number, number] | null
  destination: [number, number] | null
  onSetOrigin: (coord: [number, number] | null) => void
  onSetDestination: (coord: [number, number] | null) => void
  activeRoute: RouteResponse | null
  onRouteCalculated: (route: RouteResponse | null) => void
  showShortestComparison: boolean
  onToggleShortestComparison: (show: boolean) => void
}

export const RoutePlanner: React.FC<Props> = ({
  cityId,
  cityName = 'la ciudad',
  presets,
  selectionMode,
  onSetSelectionMode,
  origin,
  destination,
  onSetOrigin,
  onSetDestination,
  activeRoute,
  onRouteCalculated,
  showShortestComparison,
  onToggleShortestComparison,
}) => {
  const activePresets = presets && presets.length > 0 ? presets : CURICO_PRESETS
  const [isOpen, setIsOpen] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleSwap = () => {
    const temp = origin
    onSetOrigin(destination)
    onSetDestination(temp)
    if (activeRoute) {
      onRouteCalculated(null)
    }
  }

  const handleClear = () => {
    onSetOrigin(null)
    onSetDestination(null)
    onSetSelectionMode('none')
    onRouteCalculated(null)
    setErrorMessage(null)
  }

  const handleCalculate = async () => {
    if (!origin || !destination) return

    setIsLoading(true)
    setErrorMessage(null)

    try {
      const result = await calculateRoute(cityId, origin, destination, 600)
      onRouteCalculated(result)
      onSetSelectionMode('none')
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error desconocido al calcular ruta.'
      setErrorMessage(msg)
      onRouteCalculated(null)
    } finally {
      setIsLoading(false)
    }
  }

  const getCoordDisplay = (coord: [number, number] | null, role: 'origin' | 'destination') => {
    if (!coord) {
      return selectionMode === role
        ? '📍 Haz clic en el mapa...'
        : 'Sin seleccionar'
    }
    const matchingPreset = activePresets.find(
      (p) => Math.abs(p.coord[0] - coord[0]) < 0.0005 && Math.abs(p.coord[1] - coord[1]) < 0.0005
    )
    if (matchingPreset) return matchingPreset.name
    return `${coord[1].toFixed(4)}, ${coord[0].toFixed(4)}`
  }

  return (
    <div className={`route-planner-card ${isOpen ? 'open' : 'minimized'}`}>
      <div className="planner-header" onClick={() => setIsOpen(!isOpen)}>
        <div className="planner-title">
          <span className="planner-icon" role="img" aria-label="Bicicleta">
            🚲
          </span>
          <div>
            <h3>Planificador Ciclista</h3>
            <span className="planner-subtitle">Motor algorítmico determinista</span>
          </div>
        </div>
        <button
          type="button"
          className="toggle-btn"
          aria-label={isOpen ? 'Minimizar' : 'Expandir'}
          onClick={(e) => {
            e.stopPropagation()
            setIsOpen(!isOpen)
          }}
        >
          {isOpen ? '▲' : '▼'}
        </button>
      </div>

      {isOpen && (
        <div className="planner-body">
          {/* Preset quick shortcuts */}
          <div className="planner-presets">
            <span className="presets-label">Puntos frecuentes en {cityName}:</span>
            <div className="presets-chips">
              {activePresets.slice(0, 4).map((p) => (
                <button
                  key={p.name}
                  type="button"
                  className="preset-chip"
                  title={`Fijar ${p.name}`}
                  onClick={() => {
                    if (!origin) {
                      onSetOrigin(p.coord)
                    } else {
                      onSetDestination(p.coord)
                    }
                  }}
                >
                  {p.name.split(' ')[0]}
                </button>
              ))}
            </div>
          </div>

          {/* Origin selector */}
          <div className="route-point-row">
            <div className="point-indicator origin">A</div>
            <div className="point-info">
              <span className="point-label">Punto de Origen</span>
              <span className="point-value">{getCoordDisplay(origin, 'origin')}</span>
            </div>
            <button
              type="button"
              className={`btn-map-pick ${selectionMode === 'origin' ? 'active' : ''}`}
              title="Seleccionar origen en el mapa"
              onClick={() =>
                onSetSelectionMode(selectionMode === 'origin' ? 'none' : 'origin')
              }
            >
              {selectionMode === 'origin' ? 'Cancel' : 'Fijar'}
            </button>
          </div>

          {/* Swap button */}
          <div className="swap-row">
            <button
              type="button"
              className="btn-swap"
              title="Invertir origen y destino"
              onClick={handleSwap}
              disabled={!origin && !destination}
            >
              ⇅ Invertir
            </button>
          </div>

          {/* Destination selector */}
          <div className="route-point-row">
            <div className="point-indicator destination">B</div>
            <div className="point-info">
              <span className="point-label">Punto de Destino</span>
              <span className="point-value">{getCoordDisplay(destination, 'destination')}</span>
            </div>
            <button
              type="button"
              className={`btn-map-pick ${selectionMode === 'destination' ? 'active' : ''}`}
              title="Seleccionar destino en el mapa"
              onClick={() =>
                onSetSelectionMode(selectionMode === 'destination' ? 'none' : 'destination')
              }
            >
              {selectionMode === 'destination' ? 'Cancel' : 'Fijar'}
            </button>
          </div>

          {selectionMode !== 'none' && (
            <div className="selection-tip">
              💡 Haz clic en cualquier calle del mapa para fijar el punto {selectionMode === 'origin' ? 'A (Origen)' : 'B (Destino)'}.
            </div>
          )}

          {errorMessage && <div className="route-error-alert">{errorMessage}</div>}

          {/* Action buttons */}
          <div className="planner-actions">
            <button
              type="button"
              className="btn-calculate"
              onClick={handleCalculate}
              disabled={!origin || !destination || isLoading}
            >
              {isLoading ? 'Calculando red vial...' : 'Calcular Ruta Ciclista'}
            </button>
            {(origin || destination || activeRoute) && (
              <button
                type="button"
                className="btn-clear"
                onClick={handleClear}
                disabled={isLoading}
              >
                Limpiar
              </button>
            )}
          </div>

          {/* Results Comparison Panel */}
          {activeRoute && (
            <div className="route-results">
              <div className="results-header">
                <span className="results-badge">RUTA ÓPTIMA ENCONTRADA</span>
                {activeRoute.cached && <span className="cache-badge">Caché</span>}
              </div>

              <div className="metrics-grid">
                <div className="metric-box primary">
                  <span className="metric-val">
                    {activeRoute.cycling_route.distance_km} <small>km</small>
                  </span>
                  <span className="metric-lbl">Distancia total</span>
                </div>
                <div className="metric-box success">
                  <span className="metric-val">
                    {activeRoute.cycling_route.cycling_infra_pct}%
                  </span>
                  <span className="metric-lbl">En ciclovías</span>
                </div>
              </div>

              {/* Comparison vs shortest */}
              <div className="comparison-card">
                <div className="comparison-title">
                  ⚖ Comparación con ruta más corta vehicular
                </div>
                <div className="comparison-detail">
                  <div className="comp-row">
                    <span>Ruta más corta directa:</span>
                    <strong>{activeRoute.shortest_route.distance_km} km</strong>
                  </div>
                  <div className="comp-row">
                    <span>Ciclovías en ruta más corta:</span>
                    <span>{activeRoute.shortest_route.cycling_infra_pct}%</span>
                  </div>
                  <div className="comp-row highlight">
                    <span>Ganancia de infraestructura segura:</span>
                    <strong>+{activeRoute.comparison.cycling_gain_pct}%</strong>
                  </div>
                  <div className="comp-row sub">
                    <span>Desvío adicional necesario:</span>
                    <span>
                      {activeRoute.comparison.distance_diff_km > 0
                        ? `+${activeRoute.comparison.distance_diff_km} km (+${activeRoute.comparison.length_diff_pct}%)`
                        : '0 km (mismo trayecto)'}
                    </span>
                  </div>
                </div>

                <label className="toggle-shortest">
                  <input
                    type="checkbox"
                    checked={showShortestComparison}
                    onChange={(e) => onToggleShortestComparison(e.target.checked)}
                  />
                  <span>Mostrar trazado vehicular alternativo en el mapa</span>
                </label>
              </div>

              {/* Traversed streets */}
              {activeRoute.cycling_route.streets.length > 0 && (
                <div className="traversed-streets">
                  <span className="streets-title">Calles recomendadas:</span>
                  <div className="street-tags">
                    {activeRoute.cycling_route.streets.map((st, i) => (
                      <span key={`${st}-${i}`} className="street-tag">
                        {st}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
