import React, { useState } from 'react'
import type { GapCandidateFeature } from '../types/map'
import { GitFork, ChevronDown, ChevronUp, Sparkles, MapPin, ArrowRight, Layers } from 'lucide-react'

interface Props {
  opportunities: GapCandidateFeature[]
  selectedGap: GapCandidateFeature | null
  onSelectGap: (gap: GapCandidateFeature | null) => void
  isLayerVisible: boolean
  onEnsureLayerVisible?: () => void
}

export const OpportunitiesList: React.FC<Props> = ({
  opportunities,
  selectedGap,
  onSelectGap,
  isLayerVisible,
  onEnsureLayerVisible,
}) => {
  const [isExpanded, setIsExpanded] = useState(true)

  if (opportunities.length === 0) {
    return null
  }

  return (
    <aside
      className={`opportunities-panel glass-panel ${!isExpanded ? 'minimized' : ''}`}
      aria-label="Oportunidades de conexión ciclista prioritarias"
    >
      <div
        className="opportunities-header"
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault()
            setIsExpanded(!isExpanded)
          }
        }}
        title={isExpanded ? 'Minimizar oportunidades' : 'Expandir oportunidades'}
      >
        <div className="opportunities-title-wrap">
          <div className="opportunities-icon-badge">
            <GitFork size={16} strokeWidth={2.4} color="#b45309" />
          </div>
          <div>
            <div className="opportunities-title">
              <span>Brechas Prioritarias</span>
              <span className="opp-count-badge">Top {opportunities.length}</span>
            </div>
            <div className="opportunities-subtitle">
              {isExpanded ? 'Continuidad de red calculada' : 'Click para ver candidatos'}
            </div>
          </div>
        </div>

        <button
          type="button"
          className="opp-toggle-btn"
          aria-label={isExpanded ? 'Minimizar' : 'Expandir'}
        >
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>
      </div>

      {isExpanded && (
        <div className="opportunities-body">
          {!isLayerVisible && (
            <div className="opp-layer-warning">
              <span>Capa oculta en el mapa.</span>
              {onEnsureLayerVisible && (
                <button
                  type="button"
                  className="opp-enable-layer-btn"
                  onClick={(e) => {
                    e.stopPropagation()
                    onEnsureLayerVisible()
                  }}
                >
                  <Layers size={12} /> Mostrar capa
                </button>
              )}
            </div>
          )}

          <div className="opportunities-intro">
            <Sparkles size={13} color="#b45309" style={{ flexShrink: 0, marginTop: 2 }} />
            <span>
              Tramos cortos que maximizan la unión entre ciclovías existentes desconectadas.
            </span>
          </div>

          <div className="opportunities-scroll-list" role="list">
            {opportunities.map((opp, index) => {
              const props = opp.properties
              const isSelected = selectedGap?.id === opp.id
              const rank = props.rank ?? index + 1
              const mainStreet = props.streets?.[0] || 'Conexión barrial'
              const subStreets = props.streets && props.streets.length > 1
                ? props.streets.slice(1, 3).join(', ')
                : null

              return (
                <div
                  key={opp.id}
                  role="listitem"
                  className={`opportunity-card ${isSelected ? 'active' : ''}`}
                  onClick={() => {
                    if (isSelected) {
                      onSelectGap(null)
                    } else {
                      onSelectGap(opp)
                      if (!isLayerVisible && onEnsureLayerVisible) {
                        onEnsureLayerVisible()
                      }
                    }
                  }}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === ' ' || e.key === 'Enter') {
                      e.preventDefault()
                      onSelectGap(isSelected ? null : opp)
                    }
                  }}
                >
                  <div className="opp-card-header">
                    <div className="opp-rank-badge">#{rank < 10 ? `0${rank}` : rank}</div>
                    <div className="opp-card-name" title={mainStreet}>
                      {mainStreet}
                    </div>
                    <div className="opp-score-badge" title="Puntaje de prioridad multiobjetivo (0-100)">
                      {props.priority_score} <span className="score-unit">pts</span>
                    </div>
                  </div>

                  {subStreets && (
                    <div className="opp-substreets">
                      Vía: <span>{subStreets}</span>
                    </div>
                  )}

                  <div className="opp-metrics-grid">
                    <div className="opp-metric">
                      <span className="opp-metric-label">Brecha</span>
                      <strong className="opp-metric-val">{props.gap_length_m} m</strong>
                    </div>
                    <div className="opp-metric-divider" />
                    <div className="opp-metric">
                      <span className="opp-metric-label">Red unida</span>
                      <strong className="opp-metric-val">{props.connected_network_km} km</strong>
                    </div>
                    <div className="opp-metric-divider" />
                    <div className="opp-metric">
                      <span className="opp-metric-label">Ganancia</span>
                      <strong className="opp-metric-val accent">{props.gain_ratio}x</strong>
                    </div>
                  </div>

                  <div className="opp-card-footer">
                    <span className="opp-action-hint">
                      <MapPin size={11} /> {isSelected ? 'Enfocada en mapa' : 'Ver en mapa'}
                    </span>
                    <ArrowRight size={12} className="opp-arrow-icon" />
                  </div>
                </div>
              )
            })}
          </div>

          <div className="opp-footer-disclaimer">
            Candidatos analíticos preliminares sobre OSM. No constituyen proyectos de ingeniería aprobados.
          </div>
        </div>
      )}
    </aside>
  )
}
