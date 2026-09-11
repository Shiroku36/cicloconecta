import React from 'react'
import type { LayerConfig, LayerId } from '../types/map'
import { Layers, RotateCcw, CheckSquare, Square, Bike, Eye, EyeOff } from 'lucide-react'

interface Props {
  isCicloConectaVisible: boolean
  onToggleMaster: () => void
  layers: LayerConfig[]
  onToggleLayer: (id: LayerId) => void
  onResetView: () => void
  cityName?: string
}

export const LayerControl: React.FC<Props> = ({
  isCicloConectaVisible,
  onToggleMaster,
  layers,
  onToggleLayer,
  onResetView,
  cityName = 'la ciudad',
}) => {
  return (
    <aside className="layer-control glass-panel" aria-label="Control de capas">
      <div className="layer-control-header">
        <div className="layer-control-title">
          <Layers size={17} color="#0f172a" />
          <span>Control Cartográfico</span>
        </div>
        <button
          className="action-btn"
          style={{ flex: 'none', padding: '4px 8px', fontSize: '0.72rem' }}
          onClick={onResetView}
          title={`Centrar mapa en ${cityName}`}
        >
          <RotateCcw size={12} /> Centrar
        </button>
      </div>

      {/* Capa Maestra CicloConecta */}
      <div
        className={`master-toggle-card ${!isCicloConectaVisible ? 'disabled' : ''}`}
        onClick={onToggleMaster}
        role="switch"
        aria-checked={isCicloConectaVisible}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault()
            onToggleMaster()
          }
        }}
        title={
          isCicloConectaVisible
            ? 'Ocultar toda la capa CicloConecta (deja solo el mapa base)'
            : 'Mostrar la capa CicloConecta'
        }
      >
        <div className="master-toggle-left">
          <div className="master-icon">
            <Bike size={18} strokeWidth={2.4} />
          </div>
          <div>
            <div className="master-title">Capa CicloConecta</div>
            <div className="master-subtitle">
              {isCicloConectaVisible
                ? 'Información ciclista activa'
                : 'Oculta (solo mapa base)'}
            </div>
          </div>
        </div>

        <div>
          {isCicloConectaVisible ? (
            <Eye size={18} color="#10b981" />
          ) : (
            <EyeOff size={18} color="#94a3b8" />
          )}
        </div>
      </div>

      <div className="sublayers-header">
        <span className="sublayers-label">Subcapas CicloConecta</span>
        {!isCicloConectaVisible && (
          <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontStyle: 'italic' }}>
            (Capa maestra inactiva)
          </span>
        )}
      </div>

      <div className={`layer-list ${!isCicloConectaVisible ? 'disabled-list' : ''}`}>
        {layers.map((layer) => {
          const isDashed = !!layer.lineDash && layer.lineDash.length > 0
          return (
            <div
              key={layer.id}
              className={`layer-card ${layer.visible && isCicloConectaVisible ? 'active' : ''}`}
              onClick={() => {
                if (isCicloConectaVisible) {
                  onToggleLayer(layer.id)
                }
              }}
              role="checkbox"
              aria-checked={layer.visible && isCicloConectaVisible}
              tabIndex={isCicloConectaVisible ? 0 : -1}
              onKeyDown={(e) => {
                if ((e.key === ' ' || e.key === 'Enter') && isCicloConectaVisible) {
                  e.preventDefault()
                  onToggleLayer(layer.id)
                }
              }}
            >
              <div className="layer-card-top">
                <div className="layer-info-left">
                  <div
                    className={`layer-indicator ${isDashed ? 'dashed' : ''}`}
                    style={{
                      backgroundColor: isDashed ? 'transparent' : layer.color,
                      opacity: layer.visible && isCicloConectaVisible ? 1 : 0.35,
                    }}
                  />
                  <span
                    className="layer-name"
                    style={{
                      color: layer.visible && isCicloConectaVisible ? '#0f172a' : '#94a3b8',
                      textDecoration: layer.visible ? 'none' : 'line-through',
                    }}
                  >
                    {layer.name}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {(() => {
                    let badgeLabel = 'ALGORÍTMICO'
                    let badgeClass = 'algo'
                    if (layer.isDemo) {
                      badgeLabel = 'DEMO'
                      badgeClass = 'demo'
                    } else if (layer.id === 'cycling-infrastructure') {
                      badgeLabel = 'OSM'
                      badgeClass = 'osm'
                    } else if (layer.id === 'network-expansion') {
                      badgeLabel = 'ANÁLISIS'
                      badgeClass = 'analysis'
                    } else if (layer.id === 'missing-connections' || layer.id === 'suggested-routes') {
                      badgeLabel = 'ALGORÍTMICO'
                      badgeClass = 'algo'
                    }
                    return (
                      <span className={`layer-badge ${badgeClass}`}>
                        {badgeLabel}
                      </span>
                    )
                  })()}
                  {layer.visible && isCicloConectaVisible ? (
                    <CheckSquare size={16} color={layer.color} />
                  ) : (
                    <Square size={16} color="#cbd5e1" />
                  )}
                </div>
              </div>

              <p className="layer-card-desc">{layer.description}</p>

              <div className="layer-meta-footer">
                <span>Fuente: {layer.source}</span>
                {typeof layer.count === 'number' && (
                  <span>
                    <strong>{layer.count}</strong>{' '}
                    {layer.id === 'network-expansion' ? 'fases' : 'tramos'}
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </aside>
  )
}
