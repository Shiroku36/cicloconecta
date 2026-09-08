import React from 'react'
import type { City } from '../types/map'
import { Bike, Info, MapPin } from 'lucide-react'

interface Props {
  city: City
  onOpenInfo: () => void
}

export const CityHeader: React.FC<Props> = ({ city, onOpenInfo }) => {
  return (
    <header className="top-header glass-panel">
      <div className="brand-row">
        <div className="brand-identity">
          <div className="brand-icon" title="CicloConecta Chile">
            <Bike size={22} strokeWidth={2.4} />
          </div>
          <div>
            <h1 className="brand-title">CicloConecta</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
              <span className="city-badge">
                <MapPin size={11} /> {city.name}, {city.region}
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
            <span style={{ color: '#059669', fontWeight: 600 }}>OSM Verificado</span>
          </div>
        </div>
      )}
    </header>
  )
}
