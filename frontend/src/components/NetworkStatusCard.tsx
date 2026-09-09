import React, { useState } from 'react'
import type { City } from '../types/map'
import { Activity, ChevronDown, ChevronUp } from 'lucide-react'

interface Props {
  city: City
}

export const NetworkStatusCard: React.FC<Props> = ({ city }) => {
  const [isOpen, setIsOpen] = useState(true)

  const kmTotal = city.stats?.total_km ?? city.connectivity?.total_cycling_km ?? 0
  const tramosCount = city.stats?.cycleways_count ?? 0
  const componentsCount = city.connectivity?.total_components ?? 0
  const mainKm = city.connectivity?.main_component_km ?? 0
  const mainPct = city.connectivity?.main_component_pct ?? 0
  const potentialCount = city.connectivity?.selected_opportunities_count ?? 10

  return (
    <div className="network-status-panel glass-panel" aria-label="Estado de la red ciclista">
      <div
        className="network-status-header"
        onClick={() => setIsOpen(!isOpen)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault()
            setIsOpen(!isOpen)
          }
        }}
      >
        <div className="network-status-title">
          <Activity size={16} color="#0284c7" />
          <div>
            <h4>Estado de la Red</h4>
            <span className="network-status-city">{city.name}</span>
          </div>
        </div>
        <button
          type="button"
          className="collapse-toggle-btn"
          aria-label={isOpen ? 'Minimizar estado' : 'Expandir estado'}
        >
          {isOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>

      {isOpen && (
        <div className="network-status-grid">
          <div className="network-stat-box">
            <span className="network-stat-label">Red Mapeada</span>
            <div className="network-stat-val">
              <strong>{kmTotal}</strong>
              <span className="network-stat-unit">km</span>
            </div>
            <span className="network-stat-sub">{tramosCount} tramos OSM</span>
          </div>

          <div className="network-stat-box">
            <span className="network-stat-label">Componentes</span>
            <div className="network-stat-val">
              <strong>{componentsCount}</strong>
            </div>
            <span className="network-stat-sub">redes inconexas</span>
          </div>

          <div className="network-stat-box">
            <span className="network-stat-label">Red Principal</span>
            <div className="network-stat-val">
              <strong>{mainKm}</strong>
              <span className="network-stat-unit">km</span>
            </div>
            <span className="network-stat-sub">{mainPct}% del total</span>
          </div>

          <div className="network-stat-box">
            <span className="network-stat-label">Conexiones Potenciales</span>
            <div className="network-stat-val highlight">
              <strong>{potentialCount}</strong>
            </div>
            <span className="network-stat-sub">gaps Top 10</span>
          </div>
        </div>
      )}
    </div>
  )
}
