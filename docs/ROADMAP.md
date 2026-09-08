# Hoja de Ruta (Roadmap) — CicloConecta

Plan de evolución estratégica y técnica para expandir la cobertura y capacidades de análisis de CicloConecta a lo largo de Chile.

---

## Fase 1: Núcleo y Prototipo Funcional — Curicó (Completada en esta iteración)
- [x] Repositorio oficial público open source en `shiroku36/cicloconecta`.
- [x] Extractor determinista de ciclovías reales desde OpenStreetMap para Curicó (120+ tramos, 43+ km).
- [x] Backend en FastAPI con endpoints REST `/api/cities` y `/api/cities/{id}/layers/{layer_id}`.
- [x] Visualizador interactivo en React + TypeScript + MapLibre GL JS centrado en Curicó.
- [x] Sistema de capas flotante (activación/desactivación reactiva de ciclovías, conexiones faltantes y rutas sugeridas).
- [x] Popups interactivos con atributos de cada vía (nombre, superficie, tipo, distancia).
- [x] Documentación fundacional de arquitectura, decisiones y pipeline.

---

## Fase 2: Automatización del Pipeline de Gaps y Topología
- [ ] Implementación de script `pipeline/gap_detector.py` basado en NetworkX para detectar automáticamente componentes disconexas y puntos muertos (dead-ends) a partir de la red vial completa de Curicó.
- [ ] Asignación de puntajes de prioridad de conexión basados en cercanía a colegios, centros de salud y estaciones de tren (EFE Curicó).
- [ ] Reemplazo progresivo de los GeoJSON DEMO de Curicó por resultados generados por el algoritmo determinista.
- [ ] Exportación de métricas de conectividad (% de red conectada vs aislada).

---

## Fase 3: Expansión Regional (Maule e Intermedias)
- [ ] Incorporación de ciudades vecinas de la Región del Maule:
  - **Talca** (capital regional con red universitaria y corredores 1 Norte / 2 Sur).
  - **Linares**.
  - **Molina / Teno**.
- [ ] Selector visual de ciudades en la barra superior con transición animada (`flyTo`).
- [ ] Comparativa de indicadores ciclistas interurbanos (km de ciclovía por habitante, conectividad promedio).

---

## Fase 4: Colaboración Ciudadana y Reportes Comunitarios
- [ ] Mecanismo comunitario liviano para reportar incidencias en ciclovías (obstáculos físicos, falta de iluminación, deterioro de pavimento, obras de construcción).
- [ ] Validación comunitaria de tramos y retroalimentación directa para mejorar el mapeo en OpenStreetMap.
- [ ] Generación de reportes ejecutivos en PDF/Web para presentar ante comités de transporte municipal y colectivos ciclistas locales.

---

## Fase 5: Escala Nacional y Optimización Vectorial
- [ ] Incorporación de las principales áreas metropolitanas:
  - **Gran Concepción**.
  - **Gran Valparaíso**.
  - **Gran Santiago**.
- [ ] Transición a teselas vectoriales pre-renderizadas (PMTiles / Mapbox Vector Tiles) para soportar redes de decenas de miles de kilómetros sin degradar el rendimiento del navegador.
- [ ] Integración opcional de PostGIS en el backend para consultas espaciales en tiempo real.
