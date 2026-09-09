import React from 'react'
import { X, CheckCircle, GitBranch } from 'lucide-react'

interface Props {
  isOpen: boolean
  onClose: () => void
}

export const InfoModal: React.FC<Props> = ({ isOpen, onClose }) => {
  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3 className="modal-title">Acerca de CicloConecta</h3>
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
              Plataforma comunitaria de análisis y visualización ciclista
            </span>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Cerrar modal">
            <X size={20} />
          </button>
        </div>

        <div className="modal-section">
          <h4>Propósito del Proyecto</h4>
          <p>
            CicloConecta es un proyecto de código abierto para entender, diagnosticar
            y proyectar la red de infraestructura ciclista en ciudades de Chile.
            La primera ciudad piloto es <strong>Curicó, Región del Maule</strong>.
          </p>
        </div>

        <div className="modal-section">
          <h4>Transparencia de Datos: ¿Qué es real y qué es demo?</h4>

          <div className="modal-callout">
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, marginBottom: '4px' }}>
              <CheckCircle size={16} /> Infraestructura Mapeada: OpenStreetMap
            </div>
            <p>
              Los datos provienen directamente de <strong>OpenStreetMap (OSM)</strong>,
              extraídos mediante consultas espaciales a la API Overpass según el etiquetado
              colaborativo de la comunidad ciclista.
            </p>
          </div>

          <div className="modal-callout" style={{ background: '#eff6ff', borderLeftColor: '#3b82f6', color: '#1e40af' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, marginBottom: '4px' }}>
              <CheckCircle size={16} /> Análisis Algorítmico Determinista (Fase 2 y 3)
            </div>
            <p>
              Tanto el <strong>Planificador de Rutas Ciclistas</strong> (A* sobre la red vial real ponderada por estrés vehicular)
              como el <strong>Detector de Brechas de Red</strong> (continuidad topológica entre componentes ciclistas desconectadas)
              son calculados determinísticamente sin datos sintéticos ni líneas rectas inventadas.
            </p>
          </div>
        </div>

        <div className="modal-section">
          <h4>Filosofía de Arquitectura</h4>
          <p>
            No realizamos análisis pesados cada vez que abres el mapa. El procesamiento
            topológico ocurre en segundo plano (batch), generando capas GeoJSON ultra-livianas
            que el frontend visualiza de forma instantánea sobre MapLibre GL JS.
          </p>
        </div>

        <div className="modal-section" style={{ borderTop: '1px solid #e2e8f0', paddingTop: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
              Proyecto Comunitario Open Source (MIT)
            </span>
            <a
              href="https://github.com/shiroku36/cicloconecta"
              target="_blank"
              rel="noopener noreferrer"
              className="action-btn"
              style={{ flex: 'none', textDecoration: 'none' }}
            >
              <GitBranch size={14} /> Ver en GitHub
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
