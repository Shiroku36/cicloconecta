import React from 'react'
import type { City } from '../types/map'
import { Bike, Info, MapPin } from 'lucide-react'

interface Props {
  city: City
  cities?: City[]
  onSelectCity?: (cityId: string) => void
  onOpenInfo: () => void
}

export const CityHeader: React.FC<Props> = ({
  city,
  cities = [],
  onSelectCity,
  onOpenInfo,
}) => {
  return (
    <header className="top-header glass-panel">
      <div className="brand-row">
        <div className="brand-identity">
          <div className="brand-icon" title="CicloConecta Chile">
            <Bike size={22} strokeWidth={2.4} />
          </div>
          <div>
            <h1 className="brand-title">CicloConecta</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '3px' }}>
              {cities.length > 1 && onSelectCity ? (
                <div className="city-selector-container">
                  <MapPin size={13} className="city-selector-icon" />
                  <select
                    className="city-selector-dropdown"
                    value={city.id}
                    onChange={(e) => onSelectCity(e.target.value)}
                    aria-label="Seleccionar ciudad"
                  >
                    {cities.map((c) => (
                      <option key={c.id} value={c.id} disabled={c.enabled === false}>
                        {c.name} {c.enabled === false ? '• Próximamente' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <span className="city-badge">
                  <MapPin size={11} /> {city.name}
                </span>
              )}
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                {city.region}
              </span>
            </div>
          </div>
        </div>
        <button
          className="info-btn"
          onClick={onOpenInfo}
          title="Ver detalles del proyecto y metodología"
        >
          <Info size={14} /> Metodología
        </button>
      </div>

      {city.stats && (
        <div className="metrics-strip">
          <div className="metric-item">
            <span>Red ciclista:</span>
            <strong>{city.stats.total_km} km</strong>
          </div>
          <div className="metric-item">
            <span>•</span>
            <span>Tramos mapeados:</span>
            <strong>{city.stats.cycleways_count}</strong>
          </div>
          <div className="metric-item">
            <span>•</span>
            <span style={{ color: '#059669', fontWeight: 600 }}>Datos OpenStreetMap</span>
          </div>
        </div>
      )}
    </header>
  )
}
