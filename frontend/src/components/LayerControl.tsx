import React from 'react'
import type { LayerConfig, LayerId } from '../types/map'
import { Layers, RotateCcw, CheckSquare, Square } from 'lucide-react'

interface Props {
  layers: LayerConfig[]
  onToggleLayer: (id: LayerId) => void
  onResetView: () => void
}

export const LayerControl: React.FC<Props> = ({
  layers,
  onToggleLayer,
  onResetView,
}) => {
  return (
    <aside className="layer-control glass-panel" aria-label="Control de capas">
      <div className="layer-control-header">
        <div className="layer-control-title">
          <Layers size={17} color="#0f172a" />
          <span>Capas del Mapa</span>
        </div>
        <button
          className="action-btn"
          style={{ flex: 'none', padding: '4px 8px', fontSize: '0.72rem' }}
          onClick={onResetView}
          title="Centrar mapa en Curicó"
        >
          <RotateCcw size={12} /> Centrar
        </button>
      </div>

      <div className="layer-list">
        {layers.map((layer) => {
          const isDashed = !!layer.lineDash && layer.lineDash.length > 0
          return (
            <div
              key={layer.id}
              className={`layer-card ${layer.visible ? 'active' : ''}`}
              onClick={() => onToggleLayer(layer.id)}
              role="checkbox"
              aria-checked={layer.visible}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === ' ' || e.key === 'Enter') {
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
                      opacity: layer.visible ? 1 : 0.35,
                    }}
                  />
                  <span
                    className="layer-name"
                    style={{
                      color: layer.visible ? '#0f172a' : '#94a3b8',
                      textDecoration: layer.visible ? 'none' : 'line-through',
                    }}
                  >
                    {layer.name}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    className={`layer-badge ${layer.isDemo ? 'demo' : 'real'}`}
                  >
                    {layer.isDemo ? 'DEMO' : 'REAL'}
                  </span>
                  {layer.visible ? (
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
                    <strong>{layer.count}</strong> tramos
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
