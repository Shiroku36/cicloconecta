import React, { useState } from 'react'
import type { ExpansionFeature } from '../types/map'
import { TrendingUp, ChevronDown, ChevronUp, Sparkles, Layers, Award, MapPin } from 'lucide-react'

interface Props {
  phases: ExpansionFeature[]
  selectedExpansion: ExpansionFeature | null
  onSelectExpansion: (phase: ExpansionFeature | null) => void
  isLayerVisible: boolean
  onEnsureLayerVisible?: () => void
}

export const ExpansionPlanCard: React.FC<Props> = ({
  phases,
  selectedExpansion,
  onSelectExpansion,
  isLayerVisible,
  onEnsureLayerVisible,
}) => {
  const [isExpanded, setIsExpanded] = useState(true)

  if (phases.length === 0) {
    return null
  }

  const totalKm = phases.reduce((acc, p) => acc + (p.properties.length_km || 0), 0)
  const totalNodes = phases.reduce(
    (acc, p) => acc + (p.properties.marginal_gain?.urban_access_nodes || p.properties.coverage_gain_nodes || 0),
    0
  )
  const totalPois = phases.reduce(
    (acc, p) => acc + (p.properties.marginal_gain?.pois || p.properties.new_pois_count || 0),
    0
  )

  const typeLabelMap: Record<string, string> = {
    trunk_extension: 'Troncal',
    continuation: 'Continuación',
    cross_connector: 'Conector',
    branch: 'Rama',
  }

  return (
    <aside
      className={`expansion-panel glass-panel ${!isExpanded ? 'minimized' : ''}`}
      aria-label="Plan maestro de expansión de red ciclista"
    >
      <div
        className="expansion-header"
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault()
            setIsExpanded(!isExpanded)
          }
        }}
        title={isExpanded ? 'Minimizar plan de expansión' : 'Expandir plan de expansión'}
      >
        <div className="expansion-title-wrap">
          <div className="expansion-icon-badge">
            <TrendingUp size={16} strokeWidth={2.4} color="#7c3aed" />
          </div>
          <div>
            <div className="expansion-title">
              <span>Expansión Territorial</span>
              <span className="expansion-count-badge">{phases.length} Fases</span>
            </div>
            <div className="expansion-subtitle">
              {isExpanded ? 'Crecimiento progresivo de red' : 'Click para ver fases'}
            </div>
          </div>
        </div>

        <button
          type="button"
          className="expansion-toggle-btn"
          aria-label={isExpanded ? 'Minimizar' : 'Expandir'}
        >
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>
      </div>

      {isExpanded && (
        <div className="expansion-body">
          {!isLayerVisible && (
            <div className="expansion-layer-warning">
              <span>Capa morada oculta en el mapa.</span>
              {onEnsureLayerVisible && (
                <button
                  type="button"
                  className="expansion-enable-layer-btn"
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

          <div className="expansion-summary-chips">
            <div className="expansion-summary-chip">
              <span className="chip-value">+{totalKm.toFixed(1)} km</span>
              <span className="chip-label">Proyectados</span>
            </div>
            <div className="expansion-summary-chip">
              <span className="chip-value">+{totalNodes}</span>
              <span className="chip-label">Nodos viales</span>
            </div>
            <div className="expansion-summary-chip">
              <span className="chip-value">+{totalPois}</span>
              <span className="chip-label">Destinos clave</span>
            </div>
          </div>

          <div className="expansion-intro">
            <Sparkles size={13} color="#7c3aed" style={{ flexShrink: 0, marginTop: 2 }} />
            <span>
              Corredores estructurantes para llevar la red ciclista hacia sectores habitacionales desatendidos.
            </span>
          </div>

          <div className="expansion-scroll-list" role="list">
            {phases.map((feat) => {
              const props = feat.properties
              const featureId = feat.id || props.id || `phase-${props.phase}`
              const isSelected =
                (selectedExpansion?.id || selectedExpansion?.properties?.id) === featureId
              const mainStreet = props.main_street || props.streets?.[0] || 'Eje estructurante'
              const title = props.sector || props.name || `Fase ${props.phase}`
              const score = props.score ?? props.expansion_score ?? 0
              const nodesGained = props.marginal_gain?.urban_access_nodes ?? props.coverage_gain_nodes ?? 0
              const poisGained = props.marginal_gain?.pois ?? props.new_pois_count ?? 0
              const expType = props.expansion_type || 'branch'
              const typeBadge = typeLabelMap[expType] || expType
              const envLabel = props.environment_label || (props.urban_context === 'periurban' ? 'Periurbano' : 'Urbano')
              const dependsOn = props.depends_on || []
              const depFormatted = dependsOn.length > 0
                ? dependsOn.map((d) => d.replace(/^expansion-[a-z]+-0?/, 'Fase ')).join(', ')
                : null

              return (
                <div
                  key={featureId}
                  className={`expansion-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => {
                    if (isSelected) {
                      onSelectExpansion(null)
                    } else {
                      onSelectExpansion(feat)
                      if (!isLayerVisible && onEnsureLayerVisible) {
                        onEnsureLayerVisible()
                      }
                    }
                  }}
                  role="listitem"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === ' ' || e.key === 'Enter') {
                      e.preventDefault()
                      onSelectExpansion(isSelected ? null : feat)
                    }
                  }}
                >
                  <div className="expansion-item-top">
                    <div className="expansion-phase-pill">
                      <span>Fase {props.phase}</span>
                    </div>

                    <span className="expansion-type-pill" title={`Tipo de expansión: ${expType}`}>
                      {typeBadge}
                    </span>

                    <span className="expansion-env-pill" title={`Contexto territorial: ${envLabel}`}>
                      {envLabel === 'Conector Periurbano' ? 'Periurbano' : 'Urbano'}
                    </span>

                    <div className="expansion-score-pill" title="Puntaje multicriterio (0-100)">
                      <Award size={12} color="#7c3aed" />
                      <span>{score.toFixed(1)} pts</span>
                    </div>
                  </div>

                  <div className="expansion-item-name">{title}</div>

                  {depFormatted && (
                    <div className="expansion-dep-indicator" title={`Dependencia topológica: requiere ${depFormatted}`}>
                      🔗 Requiere {depFormatted}
                    </div>
                  )}

                  <div className="expansion-item-meta">
                    <span className="expansion-sector-tag" title="Sector urbano beneficiado">
                      <MapPin size={11} /> {props.sector}
                    </span>
                    <span className="expansion-street-tag" title="Calle principal utilizada">
                      {mainStreet}
                    </span>
                  </div>

                  <div className="expansion-metrics-row">
                    <span className="expansion-metric" title="Longitud proyectada del corredor">
                      <strong>{props.length_km.toFixed(2)}</strong> km
                    </span>
                    <span className="metric-dot">•</span>
                    <span className="expansion-metric" title="Proxy de cobertura: nodos residenciales ganados">
                      +<strong>{nodesGained}</strong> nodos
                    </span>
                    <span className="metric-dot">•</span>
                    <span className="expansion-metric" title="POIs y equipamientos incorporados">
                      +<strong>{poisGained}</strong> POIs
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </aside>
  )
}